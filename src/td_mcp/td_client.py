"""
TouchDesigner HTTP Client
=========================
Async HTTP client that communicates with the WebServer DAT inside
TouchDesigner. Handles connection pooling, retries, health checks,
and error normalization.
"""

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger("td_mcp.client")


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
        self.shared_secret = (shared_secret or "").strip()
        self._client: httpx.AsyncClient | None = None
        self._last_health_check: float = 0
        self._health_cache_ttl: float = 5.0
        self._is_connected: bool = False

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {}
            if self.shared_secret:
                headers = {
                    "X-TD-MCP-Secret": self.shared_secret,
                    "Authorization": f"Bearer {self.shared_secret}",
                }
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout, connect=5.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                headers=headers,
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

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                result = await self._raw_request(endpoint, body)

                # Check for application-level errors
                if isinstance(result, dict) and 'error' in result:
                    raise TouchDesignerAPIError(
                        result['error'],
                        status_code=200,
                        details=result,
                    )

                return result

            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                self._is_connected = False
                last_error = e
                if attempt < self.max_retries:
                    backoff = min(2 ** attempt, 8)  # 1s, 2s, 4s, 8s max
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
                    backoff = min(2 ** attempt, 8)
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
        """Execute a single HTTP request."""
        client = await self._get_client()

        if body is not None:
            response = await client.post(endpoint, json=body)
        else:
            response = await client.post(endpoint, json={})

        response.raise_for_status()

        if response.headers.get('content-type', '').startswith('application/json'):
            return response.json()
        else:
            return {"raw": response.text}
