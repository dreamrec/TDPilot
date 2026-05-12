"""
TouchDesigner HTTP Client
=========================
Async HTTP client that communicates with the WebServer DAT inside
TouchDesigner. Handles connection pooling, retries, health checks,
and error normalization.

Auth resolution (v1.6.14+)
--------------------------
The shared secret is resolved fresh on each request, with a 5-second TTL
cache to avoid file I/O thrash. Priority order:

    1. ``os.environ['TD_MCP_SHARED_SECRET']`` — fast path; ``bootstrap_auth``
       and parent processes write here.
    2. ``~/.tdpilot/.tdpilot.env`` (or ``$TDPILOT_ENV_FILE``) — file
       fallback that absorbs the auth-race documented in
       ``docs/TD_INTRICACIES_AND_PATTERNS.md`` §15. Symmetric with the
       TD-side ``_current_shared_secret`` fix shipped in v1.6.13.
    3. ``shared_secret`` constructor argument — last-resort default,
       kept for back-compat with tests that pass an explicit value.

Auth headers are attached per-request rather than baked into the cached
httpx client, so secret rotation or late ``bootstrap_auth`` execution is
picked up on the very next request. An HTTP 401 invalidates the cache
and retries once with a freshly-resolved secret — this auto-heals the
bug-class (v1.5.2 / v1.6.13) where the MCP server captured an empty
secret at module load before ``bootstrap_auth`` had populated the env.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("td_mcp.client")

# Brief cache that prevents per-request file I/O while still being short
# enough that secret rotation self-heals quickly. The 401-retry path
# invalidates the cache explicitly, so this TTL only governs the steady
# state.
_SECRET_CACHE_TTL_SECONDS = 5.0


def _default_env_file_path() -> Path:
    """Resolve the canonical .tdpilot.env path at call time.

    Inlined (rather than importing from ``auth_bootstrap``) so this module
    stays leaf-only — preventing any future import-cycle if
    ``auth_bootstrap`` ever pulls in ``TDClient``. Honors the
    ``TDPILOT_ENV_FILE`` override for isolated test runs / custom installs.
    """
    override = (os.environ.get("TDPILOT_ENV_FILE") or "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".tdpilot" / ".tdpilot.env"


def _read_secret_from_env_file(path: Path) -> str | None:
    """Best-effort read of ``TD_MCP_SHARED_SECRET`` from a .tdpilot.env file.

    Parsing mirrors ``auth_bootstrap.load_env_file`` and the TD-side
    ``_current_shared_secret`` in ``td_component/mcp_webserver_callbacks.py``
    (strip matched surrounding quotes, skip comments / blanks). Returns
    ``None`` silently on any I/O failure or missing key so callers fall
    through to the next resolution path.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, FileNotFoundError):
        return None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() != "TD_MCP_SHARED_SECRET":
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        return value
    return None


class TouchDesignerConnectionError(Exception):
    """Raised when TouchDesigner is not reachable."""

    pass


class TouchDesignerAPIError(Exception):
    """Raised when the TD API returns an error response."""

    def __init__(self, message: str, status_code: int = 0, details: dict | None = None):
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class TDClient:
    """
    Async HTTP client for the TouchDesigner WebServer DAT.

    Usage:
        client = TDClient(host="127.0.0.1", port=9981)
        result = await client.request("info")
        await client.close()

    See module docstring for the auth resolution + 401-retry policy.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9981,
        timeout: float = 15.0,
        max_retries: int = 2,
        shared_secret: str | None = None,
        scheme: str = "http",
    ):
        # If host already includes a scheme (e.g. "https://myhost"), extract it.
        if "://" in host:
            scheme, host = host.split("://", 1)
        # Strip trailing slashes from host (e.g. from copy-pasted URLs).
        host = host.rstrip("/")
        self.base_url = f"{scheme}://{host}:{port}"
        self.timeout = timeout
        self.max_retries = max_retries
        # Constructor secret is the LAST-resort fallback (used only when env
        # and file both come up empty). We deliberately do NOT make it the
        # primary source — that's what bit users in v1.5.2 / v1.6.13, where a
        # stale module-level capture got baked into self.shared_secret and
        # never refreshed across the process lifetime.
        self._explicit_secret: str | None = (shared_secret or "").strip() or None
        self._cached_secret: str | None = None
        self._secret_cache_expires_at: float = 0.0
        self._client: httpx.AsyncClient | None = None
        self._last_health_check: float = 0
        self._health_cache_ttl: float = 5.0
        self._is_connected: bool = False

    # ── Auth secret resolution ────────────────────────────────────────────

    def _resolve_secret_uncached(self) -> str:
        """Resolve the shared secret right now, with no cache lookup.

        Returns the secret as a string, or ``""`` if no source has a value.
        """
        env_value = (os.environ.get("TD_MCP_SHARED_SECRET") or "").strip()
        if env_value:
            return env_value
        file_value = _read_secret_from_env_file(_default_env_file_path())
        if file_value:
            return file_value
        return self._explicit_secret or ""

    @property
    def shared_secret(self) -> str:
        """Current shared secret, resolved fresh with a 5-second cache."""
        now = time.monotonic()
        if self._cached_secret is not None and now < self._secret_cache_expires_at:
            return self._cached_secret
        resolved = self._resolve_secret_uncached()
        self._cached_secret = resolved
        self._secret_cache_expires_at = now + _SECRET_CACHE_TTL_SECONDS
        return resolved

    @shared_secret.setter
    def shared_secret(self, value: str | None) -> None:
        """Override the explicit fallback; clears any cached resolved value.

        Back-compat for callers that assigned to ``client.shared_secret``
        directly. The next ``shared_secret`` read will re-resolve through
        the priority chain — env still wins over this explicit value.
        """
        self._explicit_secret = (value or "").strip() or None
        self._invalidate_secret_cache()

    def _invalidate_secret_cache(self) -> None:
        self._cached_secret = None
        self._secret_cache_expires_at = 0.0

    def _auth_headers(self) -> dict[str, str]:
        secret = self.shared_secret
        if not secret:
            return {}
        return {
            "X-TD-MCP-Secret": secret,
            "Authorization": f"Bearer {secret}",
        }

    # ── HTTP client lifecycle ─────────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client.

        Auth headers are NOT attached here — they're built per-request in
        ``_raw_request`` so a stale-at-init secret can't leak into every
        future request via the cached httpx client.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout, connect=5.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        self._is_connected = False

    async def health_check(self) -> dict[str, Any]:
        """Check if TouchDesigner is reachable and the MCP WebServer is running.

        Results are cached for ``_health_cache_ttl`` seconds *from a successful
        probe*. Any failure elsewhere in ``request()`` (same transport that real
        tools use) resets the connected flag, so the next health check probes
        fresh rather than returning a stale "ok".
        """
        now = time.time()
        if self._is_connected and now - self._last_health_check < self._health_cache_ttl:
            return {
                "status": "ok",
                "cached": True,
                "cached_age_s": round(now - self._last_health_check, 3),
            }

        try:
            # Route through request() to ensure endpoint normalization to /api/health.
            result = await self.request("health")
            self._is_connected = True
            self._last_health_check = now
            return result
        except Exception as e:
            self._is_connected = False
            self._last_health_check = 0.0
            raise TouchDesignerConnectionError(
                f"Cannot reach TouchDesigner at {self.base_url}. "
                f"Ensure TD is running and the MCP WebServer component is active on the correct port. "
                f"Error: {e!s}"
            ) from e

    async def request(self, endpoint: str, body: dict | None = None) -> dict[str, Any]:
        """
        Send a request to the TouchDesigner WebServer DAT.

        Layered retry policy:
          - Inner loop (``_send_with_retries``): connect/timeout retries with
            exponential backoff, governed by ``max_retries``.
          - Outer loop (this method): at most one auth-retry. A 401 from the
            inner loop invalidates the secret cache and re-runs the whole
            inner loop with a freshly-resolved secret. This auto-heals the
            bug-class where the constructor captured an empty secret before
            ``bootstrap_auth`` populated env / wrote the file.

        Args:
            endpoint: API endpoint path (without /api/ prefix)
            body: Optional JSON body

        Returns:
            Parsed JSON response dict

        Raises:
            TouchDesignerConnectionError: If TD is unreachable
            TouchDesignerAPIError: If the API returns an error
        """
        # Ensure /api/ prefix
        if not endpoint.startswith("/"):
            endpoint = f"/api/{endpoint}"
        elif not endpoint.startswith("/api/"):
            endpoint = f"/api{endpoint}"

        # auth_attempt 0 → original; auth_attempt 1 → retry with re-resolved secret
        for auth_attempt in range(2):
            try:
                return await self._send_with_retries(endpoint, body)
            except TouchDesignerAPIError as e:
                if e.status_code == 401 and auth_attempt == 0:
                    logger.warning(
                        "TD returned 401; re-resolving shared secret from env + file and retrying once"
                    )
                    self._invalidate_secret_cache()
                    continue
                raise
        # Unreachable: either the inner loop returned, or both auth attempts raised
        raise TouchDesignerConnectionError("auth retry budget exhausted (unreachable)")

    async def _send_with_retries(self, endpoint: str, body: dict | None) -> dict[str, Any]:
        """Inner retry loop for connect/timeout/5xx; surfaces 4xx as APIError.

        Note that 401 is surfaced as an APIError too — the outer ``request``
        loop catches it and re-runs this method once with a freshly-resolved
        secret. We deliberately do NOT consume the connect/timeout retry
        budget on auth failures.
        """
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                result = await self._raw_request(endpoint, body)

                # Check for application-level errors
                if isinstance(result, dict) and "error" in result:
                    raise TouchDesignerAPIError(
                        result["error"],
                        status_code=200,
                        details=result,
                    )

                return result

            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                self._is_connected = False
                last_error = e
                if attempt < self.max_retries:
                    backoff = min(2**attempt, 8)  # 1s, 2s, 4s, 8s max
                    logger.warning(f"Connection failed (attempt {attempt + 1}), retrying in {backoff}s...")
                    await asyncio.sleep(backoff)
                    continue
                raise TouchDesignerConnectionError(
                    f"Cannot reach TouchDesigner at {self.base_url} after {self.max_retries + 1} attempts. "
                    f"Make sure TouchDesigner is running and the MCP WebServer component is active. "
                    f"Error: {str(e)}"
                ) from e

            except httpx.TimeoutException as e:
                # Treat timeouts as a connection blip: clear cached health so the
                # next probe refreshes instead of returning a stale "ok".
                self._is_connected = False
                last_error = e
                if attempt < self.max_retries:
                    backoff = min(2**attempt, 8)
                    logger.warning(f"Request timed out (attempt {attempt + 1}), retrying in {backoff}s...")
                    await asyncio.sleep(backoff)
                    continue
                raise TouchDesignerAPIError(
                    f"Request to {endpoint} timed out after {self.timeout}s. "
                    f"The operation may be too heavy for TouchDesigner to process quickly. "
                    f"Try reducing the scope (fewer nodes, smaller data ranges).",
                    status_code=408,
                ) from e

            except httpx.HTTPStatusError as e:
                # 5xx means TD is up but the request failed. Don't mark disconnected,
                # but do invalidate the health cache so it re-probes.
                if 500 <= e.response.status_code < 600:
                    self._is_connected = False
                raise TouchDesignerAPIError(
                    f"TouchDesigner returned HTTP {e.response.status_code}: {e.response.text[:500]}",
                    status_code=e.response.status_code,
                ) from e

        raise TouchDesignerConnectionError(f"All retry attempts failed: {last_error}")

    async def _raw_request(self, endpoint: str, body: dict | None = None) -> dict[str, Any]:
        """Execute a single HTTP request with freshly-resolved auth headers."""
        client = await self._get_client()
        headers = self._auth_headers()
        post_body = body if body is not None else {}
        response = await client.post(endpoint, json=post_body, headers=headers)
        response.raise_for_status()

        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        else:
            return {"raw": response.text}
