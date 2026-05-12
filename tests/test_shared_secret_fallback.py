"""Tests for `_current_shared_secret()` file-fallback (v1.6.13).

Why this exists:
  Pre-1.6.13, `_current_shared_secret()` read ONLY from `os.environ`. That's
  fine when the npx wrapper launches TD with the secret already in the
  environment, but it fails the common case where:

    1. User opens TouchDesigner directly (Dock icon, double-click .toe, etc.)
    2. The .toe auto-loads tdpilot — env is whatever TD inherited (empty)
    3. Later, `npx tdpilot` writes `~/.tdpilot/.tdpilot.env` with a fresh secret
    4. Every MCP→TD request returns 401 until the user manually pastes a
       Textport one-liner that injects the secret into `os.environ`

  The fix: when env is empty, fall back to reading the file directly. This
  mirrors deepseek-v4's `fetch_api_key()` pattern (env = cache, file = truth).
  See docs/TD_INTRICACIES_AND_PATTERNS.md §15.

Test strategy:
  - Module is loaded via importlib (same as test_td_component_auth.py) because
    `td_component/` is not a Python package — these files are sourced into TD
    as callback DATs, not imported as modules in production.
  - Each test monkeypatches `_ENV_FALLBACK_FILE` to point at a tmp_path file,
    so tests never touch the user's real `~/.tdpilot/.tdpilot.env`.
  - `monkeypatch.delenv(..., raising=False)` clears env between tests so the
    env-cache write inside `_current_shared_secret` doesn't bleed across cases.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "td_component" / "mcp_webserver_callbacks.py"


def _load_callbacks_module():
    """Fresh module load — mirrors test_td_component_auth.py helper."""
    spec = importlib.util.spec_from_file_location("td_cb_secret_test", str(MODULE_PATH))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def callbacks_module(monkeypatch, tmp_path):
    """Load module + point fallback at a tmp file + clear env.

    Critical: we delenv TWICE — once before module load (so the module
    can't see a pre-existing env), and once after (because the module-level
    `SHARED_SECRET = _current_shared_secret()` at line ~77 runs at IMPORT
    time and may have read the user's REAL ~/.tdpilot/.tdpilot.env via the
    not-yet-monkeypatched _ENV_FALLBACK_FILE, then cached the result back
    into os.environ. Without the second delenv, the cache leaks across
    tests as the user's real secret.)
    """
    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
    module = _load_callbacks_module()
    # Clean up any import-time env-cache pollution from the real user file
    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
    # Redirect the file fallback to a tmp location for the test
    tmp_env_file = tmp_path / ".tdpilot.env"
    monkeypatch.setattr(module, "_ENV_FALLBACK_FILE", str(tmp_env_file))
    return module, tmp_env_file


# ---------------------------------------------------------------------------
# Fast path: env wins, file is never read
# ---------------------------------------------------------------------------


class TestEnvFastPath:
    def test_env_value_returned_directly(self, callbacks_module, monkeypatch):
        module, env_file = callbacks_module
        monkeypatch.setenv("TD_MCP_SHARED_SECRET", "env-secret")
        # File contains a DIFFERENT value — env must win
        env_file.write_text("TD_MCP_SHARED_SECRET=file-secret\n", encoding="utf-8")

        assert module._current_shared_secret() == "env-secret"

    def test_env_whitespace_stripped(self, callbacks_module, monkeypatch):
        module, _ = callbacks_module
        monkeypatch.setenv("TD_MCP_SHARED_SECRET", "  padded-secret  ")

        assert module._current_shared_secret() == "padded-secret"

    def test_env_with_nonexistent_file_returns_env(self, callbacks_module, monkeypatch):
        """File missing must not crash when env has value."""
        module, env_file = callbacks_module
        # Make sure the tmp env file does NOT exist
        assert not env_file.exists()
        monkeypatch.setenv("TD_MCP_SHARED_SECRET", "env-only")

        assert module._current_shared_secret() == "env-only"


# ---------------------------------------------------------------------------
# File fallback: env empty, file has value
# ---------------------------------------------------------------------------


class TestFileFallback:
    def test_file_value_read_when_env_empty(self, callbacks_module):
        module, env_file = callbacks_module
        env_file.write_text("TD_MCP_SHARED_SECRET=file-secret\n", encoding="utf-8")

        assert module._current_shared_secret() == "file-secret"

    def test_file_value_cached_into_env(self, callbacks_module):
        """First call populates os.environ; second call hits the fast path."""
        module, env_file = callbacks_module
        env_file.write_text("TD_MCP_SHARED_SECRET=cached-secret\n", encoding="utf-8")

        # First call — reads file
        assert module._current_shared_secret() == "cached-secret"
        # Now os.environ must have it
        assert os.environ.get("TD_MCP_SHARED_SECRET") == "cached-secret"
        # Delete the file — subsequent call still works (cache wins)
        env_file.unlink()
        assert module._current_shared_secret() == "cached-secret"

    def test_file_strips_double_quotes(self, callbacks_module):
        module, env_file = callbacks_module
        env_file.write_text('TD_MCP_SHARED_SECRET="quoted-secret"\n', encoding="utf-8")

        assert module._current_shared_secret() == "quoted-secret"

    def test_file_strips_single_quotes(self, callbacks_module):
        module, env_file = callbacks_module
        env_file.write_text("TD_MCP_SHARED_SECRET='quoted-secret'\n", encoding="utf-8")

        assert module._current_shared_secret() == "quoted-secret"

    def test_file_does_not_strip_mismatched_quotes(self, callbacks_module):
        """`"foo'` should NOT have either quote stripped — only matched pairs."""
        module, env_file = callbacks_module
        env_file.write_text("TD_MCP_SHARED_SECRET=\"foo'\n", encoding="utf-8")

        # The leading-" and trailing-' are NOT a matched pair, so kept as-is
        assert module._current_shared_secret() == "\"foo'"

    def test_file_skips_comments_and_blanks(self, callbacks_module):
        module, env_file = callbacks_module
        env_file.write_text(
            "# header comment\n\n  # indented comment\nTD_MCP_SHARED_SECRET=from-file\nOTHER_KEY=ignored\n",
            encoding="utf-8",
        )

        assert module._current_shared_secret() == "from-file"

    def test_file_only_matches_exact_key(self, callbacks_module):
        """A line like `MY_TD_MCP_SHARED_SECRET=...` must NOT match."""
        module, env_file = callbacks_module
        env_file.write_text(
            "MY_TD_MCP_SHARED_SECRET=wrong-prefix\nTD_MCP_SHARED_SECRET=correct-one\n",
            encoding="utf-8",
        )

        assert module._current_shared_secret() == "correct-one"

    def test_file_empty_value_returns_empty(self, callbacks_module):
        """An explicit `TD_MCP_SHARED_SECRET=` (empty value) returns ''."""
        module, env_file = callbacks_module
        env_file.write_text("TD_MCP_SHARED_SECRET=\n", encoding="utf-8")

        assert module._current_shared_secret() == ""

    def test_file_value_with_equals_sign_preserved(self, callbacks_module):
        """Secret containing `=` must round-trip (split only on first `=`)."""
        module, env_file = callbacks_module
        env_file.write_text("TD_MCP_SHARED_SECRET=abc=def=ghi\n", encoding="utf-8")

        assert module._current_shared_secret() == "abc=def=ghi"


# ---------------------------------------------------------------------------
# Both empty: return empty string
# ---------------------------------------------------------------------------


class TestNoSecretAvailable:
    def test_env_empty_file_missing_returns_empty(self, callbacks_module):
        module, env_file = callbacks_module
        assert not env_file.exists()

        assert module._current_shared_secret() == ""

    def test_env_empty_file_has_no_relevant_key(self, callbacks_module):
        module, env_file = callbacks_module
        env_file.write_text("SOME_OTHER_KEY=value\n", encoding="utf-8")

        assert module._current_shared_secret() == ""

    def test_env_empty_file_only_comments(self, callbacks_module):
        module, env_file = callbacks_module
        env_file.write_text("# only comments here\n# nothing else\n", encoding="utf-8")

        assert module._current_shared_secret() == ""


# ---------------------------------------------------------------------------
# Integration: file-fallback flows through `_check_auth_error`
# ---------------------------------------------------------------------------


class TestAuthIntegration:
    """Ensure the full auth path picks up file-only secrets, not just the
    bare `_current_shared_secret` helper. This is the property that matters
    for the user — that an MCP request actually succeeds."""

    def test_auth_succeeds_with_file_only_secret(self, callbacks_module):
        module, env_file = callbacks_module
        env_file.write_text("TD_MCP_SHARED_SECRET=integration-secret\n", encoding="utf-8")

        err = module._check_auth_error({"headers": {"X-TD-MCP-Secret": "integration-secret"}})

        assert err is None, f"auth should succeed with file-only secret, got {err!r}"

    def test_auth_rejects_wrong_secret_against_file_value(self, callbacks_module):
        module, env_file = callbacks_module
        env_file.write_text("TD_MCP_SHARED_SECRET=integration-secret\n", encoding="utf-8")

        err = module._check_auth_error({"headers": {"X-TD-MCP-Secret": "wrong"}})

        assert err is not None
        assert "Unauthorized" in err

    def test_auth_refuses_when_neither_env_nor_file_have_secret(self, callbacks_module, monkeypatch):
        module, env_file = callbacks_module
        # require_auth=1 by default; no secret anywhere
        monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "1")
        assert not env_file.exists()

        err = module._check_auth_error({})

        assert err is not None
        assert "TD_MCP_SHARED_SECRET" in err
