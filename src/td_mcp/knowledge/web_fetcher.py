"""Optional web fetcher for refreshing knowledge cards from derivative.ca.

Opt-in only: set environment variable ``TD_MCP_WEB_FETCH=true`` to enable.
Requires the ``httpx`` package (not a hard dependency).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

# Rate-limit state (module-level)
_last_request_time: float = 0.0
_RATE_LIMIT_SECONDS: float = 1.0
_rate_limit_lock: asyncio.Lock = asyncio.Lock()

_CACHE_DIR = Path.home() / ".tdpilot" / "cache" / "cards"


def is_enabled() -> bool:
    """Return True if web fetching is opted-in via environment variable."""
    return os.environ.get("TD_MCP_WEB_FETCH", "").lower() in ("true", "1", "yes")


async def _rate_limit() -> None:
    """Enforce a minimum 1-second gap between requests."""
    global _last_request_time
    async with _rate_limit_lock:
        now = time.monotonic()
        wait = _RATE_LIMIT_SECONDS - (now - _last_request_time)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request_time = time.monotonic()


def _cache_path(kind: str, key: str) -> Path:
    directory = _CACHE_DIR / kind
    directory.mkdir(parents=True, exist_ok=True)
    safe_key = key.replace("/", "_").replace("\\", "_")
    return directory / f"{safe_key}.json"


def _read_cache(kind: str, key: str) -> dict | None:
    path = _cache_path(kind, key)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _write_cache(kind: str, key: str, data: dict) -> None:
    path = _cache_path(kind, key)
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


async def fetch_operator_page(op_type: str) -> dict | None:
    """Fetch operator documentation from docs.derivative.ca.

    Returns a minimal dict with the page content, or None on any failure.
    Caches results in ``~/.tdpilot/cache/cards/operators/``.
    """
    if not is_enabled():
        return None

    cached = _read_cache("operators", op_type)
    if cached is not None:
        return cached

    try:
        import httpx  # noqa: F811 — optional dependency
    except ImportError:
        return None

    # Build a reasonable URL (e.g. noiseTOP -> Noise_TOP)
    doc_name = op_type[0].upper() + op_type[1:]
    # Insert underscore before the family suffix (TOP/CHOP/SOP/DAT/MAT/COMP)
    for family in ("TOP", "CHOP", "SOP", "DAT", "MAT", "COMP", "POP"):
        if doc_name.endswith(family) and len(doc_name) > len(family):
            doc_name = doc_name[: -len(family)] + "_" + family
            break
    url = f"https://docs.derivative.ca/{doc_name}"

    await _rate_limit()

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            data = {
                "op_type": op_type,
                "url": url,
                "status": resp.status_code,
                "content_length": len(resp.text),
            }
            _write_cache("operators", op_type, data)
            return data
    except Exception:
        return None


async def fetch_release_notes(build: str) -> dict | None:
    """Fetch release notes for a given build from derivative.ca.

    Returns a minimal dict, or None on any failure.
    Caches results in ``~/.tdpilot/cache/cards/release/``.
    """
    if not is_enabled():
        return None

    cached = _read_cache("release", build)
    if cached is not None:
        return cached

    try:
        import httpx  # noqa: F811
    except ImportError:
        return None

    url = f"https://docs.derivative.ca/Release_Notes_{build}"

    await _rate_limit()

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            data = {
                "build": build,
                "url": url,
                "status": resp.status_code,
                "content_length": len(resp.text),
            }
            _write_cache("release", build, data)
            return data
    except Exception:
        return None
