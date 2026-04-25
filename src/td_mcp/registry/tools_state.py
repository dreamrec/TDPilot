"""State / timescale tools — aggregated scene state + beat/phrase timing.

Part of the v1.5.0 Phase 2 module split.

Tools in this module (2):
    td_get_state_vector     — cached aggregated scene-state diagnostic
    td_get_timescale_state  — beat/phrase phase from timeline + BPM hint

``td_get_state_vector`` reads + writes ``_tr._STATE_VECTOR_CACHE`` (a
module-level dict in tool_registry.py). Module-attribute lookup keeps
the cache shared across requests.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.errors import format_tool_error
from td_mcp.tool_registry import mcp  # noqa: E402


@mcp.tool(name="td_get_state_vector")
async def td_get_state_vector(
    ctx: Context,
    path: Annotated[
        str,
        Field(
            default="/project1",
            description="Root path for aggregated diagnostics.",
        ),
    ] = "/project1",
    force_refresh: Annotated[
        bool,
        Field(
            default=False,
            description="Bypass cache and fetch fresh state.",
        ),
    ] = False,
) -> str:
    """Aggregated scene state vector (cached for _tr.TD_STATE_VECTOR_TTL seconds)."""
    finish = _tr._start_tool(ctx, "td_get_state_vector")
    try:
        cache_key = path
        cached = _tr._STATE_VECTOR_CACHE.get(cache_key)
        now = time.time()

        if not force_refresh and cached:
            cached_at = float(cached.get("cached_at", 0.0) or 0.0)
            age = now - cached_at
            if age <= max(0.0, _tr.TD_STATE_VECTOR_TTL):
                payload = dict(cached["data"])
                payload["cache"] = {
                    "hit": True,
                    "age_sec": age,
                    "ttl_sec": _tr.TD_STATE_VECTOR_TTL,
                }
                return _tr._as_json_output(payload)

        state_vector = await _tr._build_state_vector(path, ctx)
        if len(_tr._STATE_VECTOR_CACHE) >= 100:
            _tr._STATE_VECTOR_CACHE.clear()
        _tr._STATE_VECTOR_CACHE[cache_key] = {
            "cached_at": now,
            "data": state_vector,
        }
        state_vector["cache"] = {
            "hit": False,
            "ttl_sec": _tr.TD_STATE_VECTOR_TTL,
        }
        return _tr._as_json_output(state_vector)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_get_state_vector")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_get_timescale_state")
async def td_get_timescale_state(
    ctx: Context,
    bpm_hint: Annotated[
        float | None,
        Field(
            default=None,
            gt=0.0,
            le=400.0,
            description="Optional BPM hint. Defaults to 120 when omitted.",
        ),
    ] = None,
    beats_per_bar: Annotated[
        int,
        Field(
            default=4,
            ge=1,
            le=32,
            description="Musical beats per bar for phase calculations.",
        ),
    ] = 4,
) -> str:
    """Beat/phrase derived timeline state."""
    finish = _tr._start_tool(ctx, "td_get_timescale_state")
    try:
        timeline = await _tr._get_client(ctx).request("timeline")
        bpm = float(bpm_hint if bpm_hint is not None else 120.0)

        payload = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "timeline": timeline,
            "timescale": _tr._compute_timescale_from_timeline(
                timeline if isinstance(timeline, dict) else {},
                bpm=bpm,
                beats_per_bar=beats_per_bar,
            ),
            "notes": [
                "BPM is currently hint-based; use an external detector to feed live BPM.",
                "Beat/bar/phrase phases can drive modulation curves or macro transitions.",
            ],
        }
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_get_timescale_state")
        return format_tool_error(exc)
    finally:
        finish()
