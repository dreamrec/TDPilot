"""Tests for TDClient's freshness-on-every-request auth resolution (v1.6.14).

Why this exists
---------------
Before v1.6.14, ``TDClient`` captured the shared secret once at construction
and baked it into the cached ``httpx.AsyncClient`` headers. If
``bootstrap_auth`` ran late (the v1.5.2 / v1.6.13 bug-class), the captured
value was empty and every subsequent request sent an empty
``X-TD-MCP-Secret`` header to TD, producing
``401 Unauthorized: missing or invalid TD_MCP_SHARED_SECRET`` forever until
process restart — even after the file had been correctly written.

v1.6.14 makes the client resolve the secret fresh on each request (with a
5-second TTL cache), with a file fallback that mirrors v1.6.13's TD-side
fix, and a 401-retry that invalidates the cache and re-resolves once.

These tests pin all four properties:
    1. Resolution priority: env → file → explicit constructor arg
    2. TTL cache avoids file I/O thrash
    3. Setter / cache invalidation works
    4. 401 triggers cache invalidation + single retry
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

from td_mcp.td_client import (
    TDClient,
    TouchDesignerAPIError,
    _read_secret_from_env_file,
)

# ---------------------------------------------------------------------------
# Helper: redirect TDPILOT_ENV_FILE to a tmp_path so we never touch the
# user's real ~/.tdpilot/.tdpilot.env during testing.
# ---------------------------------------------------------------------------


@pytest.fixture
def env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / ".tdpilot.env"
    monkeypatch.setenv("TDPILOT_ENV_FILE", str(path))
    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
    return path


# ---------------------------------------------------------------------------
# Pure parser: _read_secret_from_env_file
# ---------------------------------------------------------------------------


class TestReadSecretFromEnvFile:
    def test_returns_value_when_key_present(self, tmp_path: Path):
        p = tmp_path / "env"
        p.write_text("TD_MCP_SHARED_SECRET=abc123\n")
        assert _read_secret_from_env_file(p) == "abc123"

    def test_returns_none_when_file_missing(self, tmp_path: Path):
        assert _read_secret_from_env_file(tmp_path / "nope") is None

    def test_returns_none_when_key_absent(self, tmp_path: Path):
        p = tmp_path / "env"
        p.write_text("OTHER_KEY=value\n")
        assert _read_secret_from_env_file(p) is None

    def test_strips_matched_double_quotes(self, tmp_path: Path):
        p = tmp_path / "env"
        p.write_text('TD_MCP_SHARED_SECRET="quoted"\n')
        assert _read_secret_from_env_file(p) == "quoted"

    def test_strips_matched_single_quotes(self, tmp_path: Path):
        p = tmp_path / "env"
        p.write_text("TD_MCP_SHARED_SECRET='quoted'\n")
        assert _read_secret_from_env_file(p) == "quoted"

    def test_does_not_strip_mismatched_quotes(self, tmp_path: Path):
        p = tmp_path / "env"
        p.write_text("TD_MCP_SHARED_SECRET=\"mismatched'\n")
        assert _read_secret_from_env_file(p) == "\"mismatched'"

    def test_skips_comments_and_blanks(self, tmp_path: Path):
        p = tmp_path / "env"
        p.write_text("# comment\n\nTD_MCP_SHARED_SECRET=real\n")
        assert _read_secret_from_env_file(p) == "real"

    def test_preserves_value_with_equals_sign(self, tmp_path: Path):
        p = tmp_path / "env"
        p.write_text("TD_MCP_SHARED_SECRET=a=b=c\n")
        assert _read_secret_from_env_file(p) == "a=b=c"

    def test_only_matches_exact_key(self, tmp_path: Path):
        p = tmp_path / "env"
        p.write_text("PREFIX_TD_MCP_SHARED_SECRET=wrong\nTD_MCP_SHARED_SECRET=right\n")
        assert _read_secret_from_env_file(p) == "right"


# ---------------------------------------------------------------------------
# Resolution priority: env > file > explicit-constructor
# ---------------------------------------------------------------------------


class TestResolveSecretPriority:
    def test_env_wins_over_file_and_explicit(self, env_file: Path, monkeypatch):
        env_file.write_text("TD_MCP_SHARED_SECRET=file-val\n")
        monkeypatch.setenv("TD_MCP_SHARED_SECRET", "env-val")
        client = TDClient(shared_secret="explicit-val")
        assert client._resolve_secret_uncached() == "env-val"

    def test_file_wins_over_explicit_when_env_empty(self, env_file: Path):
        env_file.write_text("TD_MCP_SHARED_SECRET=file-val\n")
        client = TDClient(shared_secret="explicit-val")
        assert client._resolve_secret_uncached() == "file-val"

    def test_explicit_used_when_env_and_file_empty(self, env_file: Path):
        # env_file fixture cleared env; file doesn't exist
        assert not env_file.exists()
        client = TDClient(shared_secret="explicit-val")
        assert client._resolve_secret_uncached() == "explicit-val"

    def test_empty_string_when_no_source(self, env_file: Path):
        assert not env_file.exists()
        client = TDClient()
        assert client._resolve_secret_uncached() == ""

    def test_env_whitespace_stripped(self, env_file: Path, monkeypatch):
        monkeypatch.setenv("TD_MCP_SHARED_SECRET", "  padded  ")
        client = TDClient()
        assert client._resolve_secret_uncached() == "padded"


# ---------------------------------------------------------------------------
# Cache TTL + invalidation
# ---------------------------------------------------------------------------


class TestSecretCache:
    def test_cached_value_returned_within_ttl(self, env_file: Path):
        env_file.write_text("TD_MCP_SHARED_SECRET=v1\n")
        client = TDClient()
        first = client.shared_secret  # populates cache
        # Mutate the file — cache should hide the change until TTL expires
        env_file.write_text("TD_MCP_SHARED_SECRET=v2\n")
        second = client.shared_secret
        assert first == "v1"
        assert second == "v1"

    def test_invalidate_forces_reresolve(self, env_file: Path):
        env_file.write_text("TD_MCP_SHARED_SECRET=v1\n")
        client = TDClient()
        assert client.shared_secret == "v1"
        env_file.write_text("TD_MCP_SHARED_SECRET=v2\n")
        client._invalidate_secret_cache()
        assert client.shared_secret == "v2"

    def test_ttl_expiry_causes_reresolve(self, env_file: Path):
        env_file.write_text("TD_MCP_SHARED_SECRET=v1\n")
        client = TDClient()
        assert client.shared_secret == "v1"
        env_file.write_text("TD_MCP_SHARED_SECRET=v2\n")
        # Simulate TTL passing without sleeping
        client._secret_cache_expires_at = 0.0
        assert client.shared_secret == "v2"


# ---------------------------------------------------------------------------
# Back-compat setter
# ---------------------------------------------------------------------------


class TestSharedSecretSetter:
    def test_setter_updates_explicit_fallback(self, env_file: Path):
        assert not env_file.exists()  # no env, no file → only explicit matters
        client = TDClient()
        assert client.shared_secret == ""
        client.shared_secret = "from-setter"
        assert client.shared_secret == "from-setter"

    def test_setter_does_not_override_env(self, env_file: Path, monkeypatch):
        monkeypatch.setenv("TD_MCP_SHARED_SECRET", "env-wins")
        client = TDClient()
        client.shared_secret = "from-setter"
        # env still wins on next resolve
        assert client.shared_secret == "env-wins"

    def test_setter_clearing_resets_to_empty(self, env_file: Path):
        client = TDClient(shared_secret="initial")
        assert client.shared_secret == "initial"
        client.shared_secret = None
        assert client.shared_secret == ""


# ---------------------------------------------------------------------------
# Auth header construction
# ---------------------------------------------------------------------------


class TestAuthHeaders:
    def test_both_header_styles_emitted(self, env_file: Path, monkeypatch):
        monkeypatch.setenv("TD_MCP_SHARED_SECRET", "secret-xyz")
        client = TDClient()
        headers = client._auth_headers()
        assert headers["X-TD-MCP-Secret"] == "secret-xyz"
        assert headers["Authorization"] == "Bearer secret-xyz"

    def test_empty_dict_when_no_secret_available(self, env_file: Path):
        client = TDClient()
        assert client._auth_headers() == {}


# ---------------------------------------------------------------------------
# Integration: 401 → cache invalidation + retry once with fresh secret
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_401_triggers_resolve_and_retry(env_file: Path, monkeypatch):
    """First request 401s; before the retry the file gets a valid secret;
    the retry uses the freshly-resolved secret and succeeds.

    Mirrors the actual production failure mode: bootstrap_auth has not yet
    written the file when TDClient is constructed, so the first request goes
    out unauthenticated. Then the file appears, the 401 fires, the client
    invalidates its cache, the retry reads the file, succeeds.
    """
    captured_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.append(dict(request.headers))
        if len(captured_headers) == 1:
            return httpx.Response(401, json={"error": "Unauthorized"})
        return httpx.Response(200, json={"build": "2025.32820"})

    transport = httpx.MockTransport(handler)
    client = TDClient(max_retries=0)  # no other retries — only the 401 path
    # Bypass _get_client's real httpx.AsyncClient creation
    client._client = httpx.AsyncClient(base_url=client.base_url, transport=transport)

    # First call: no secret yet → 401 → bootstrap writes the file → retry
    # picks up the new secret
    def schedule_file_write():
        env_file.write_text("TD_MCP_SHARED_SECRET=resolved-secret\n")

    original_invalidate = client._invalidate_secret_cache

    def invalidate_and_seed_file():
        schedule_file_write()
        original_invalidate()

    client._invalidate_secret_cache = invalidate_and_seed_file  # type: ignore[assignment]

    result = await client.request("info")

    assert result == {"build": "2025.32820"}
    assert len(captured_headers) == 2
    # First request had no auth header (no secret resolved yet)
    assert "x-td-mcp-secret" not in captured_headers[0]
    # Second request carried the freshly-resolved secret
    assert captured_headers[1].get("x-td-mcp-secret") == "resolved-secret"
    assert captured_headers[1].get("authorization") == "Bearer resolved-secret"

    await client.close()


@pytest.mark.asyncio
async def test_401_retry_at_most_once(env_file: Path):
    """If the retry also 401s (e.g. file is genuinely wrong), the error
    propagates after exactly two attempts — no infinite loop."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(401, json={"error": "Unauthorized"})

    transport = httpx.MockTransport(handler)
    client = TDClient(max_retries=0)
    client._client = httpx.AsyncClient(base_url=client.base_url, transport=transport)

    with pytest.raises(TouchDesignerAPIError) as exc_info:
        await client.request("info")

    assert exc_info.value.status_code == 401
    assert call_count == 2  # one initial + one auth retry

    await client.close()


@pytest.mark.asyncio
async def test_non_401_http_error_does_not_trigger_auth_retry(env_file: Path):
    """5xx and other 4xx don't burn the auth retry budget — they fail fast."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(500, json={"error": "boom"})

    transport = httpx.MockTransport(handler)
    client = TDClient(max_retries=0)
    client._client = httpx.AsyncClient(base_url=client.base_url, transport=transport)

    with pytest.raises(TouchDesignerAPIError) as exc_info:
        await client.request("info")

    assert exc_info.value.status_code == 500
    assert call_count == 1

    await client.close()


@pytest.mark.asyncio
async def test_successful_request_uses_resolved_secret(env_file: Path, monkeypatch):
    """Happy path: env has the secret, request goes out with the right
    headers, response succeeds. No retry needed."""
    monkeypatch.setenv("TD_MCP_SHARED_SECRET", "happy-secret")
    captured_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.append(dict(request.headers))
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = TDClient(max_retries=0)
    client._client = httpx.AsyncClient(base_url=client.base_url, transport=transport)

    result = await client.request("info")

    assert result == {"ok": True}
    assert len(captured_headers) == 1
    assert captured_headers[0].get("x-td-mcp-secret") == "happy-secret"

    await client.close()


# ---------------------------------------------------------------------------
# TDPILOT_ENV_FILE override
# ---------------------------------------------------------------------------


def test_tdpilot_env_file_override_honored(tmp_path: Path, monkeypatch):
    """Setting TDPILOT_ENV_FILE redirects the file fallback to that path."""
    custom = tmp_path / "custom.env"
    custom.write_text("TD_MCP_SHARED_SECRET=custom-val\n")
    monkeypatch.setenv("TDPILOT_ENV_FILE", str(custom))
    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)

    client = TDClient()
    assert client._resolve_secret_uncached() == "custom-val"


def test_no_env_var_pollution_after_resolve(env_file: Path, monkeypatch):
    """Unlike the TD-side fallback (which writes back to os.environ for the
    fast path), the MCP client side must NOT mutate os.environ — multiple
    TDClient instances must each resolve independently."""
    env_file.write_text("TD_MCP_SHARED_SECRET=file-only\n")
    client = TDClient()
    assert client._resolve_secret_uncached() == "file-only"
    # env should remain unset — we didn't cache the file value into env
    assert os.environ.get("TD_MCP_SHARED_SECRET") is None
