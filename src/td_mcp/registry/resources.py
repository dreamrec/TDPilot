"""MCP resource handlers — cached read-through context for TD state.

FastMCP resource handlers in this repo avoid Context injection for SDK
compatibility, so they cannot synchronously query live TouchDesigner. Tools and
event handlers can populate the process-local cache below; resource reads then
return the latest known truth with an explicit ``mode`` marker.
"""

from __future__ import annotations

from td_mcp.brain.cockpit import COCKPIT_RESOURCE_URI, cockpit_html
from td_mcp.events.uri import (
    chop_uri,
    cook_uri,
    decode_td_path,
    error_uri,
    par_uri,
    top_frame_uri,
)
from td_mcp.tool_registry import mcp  # noqa: E402 — intentional cycle

_RESOURCE_CACHE: dict[str, dict] = {}


def set_cached_resource(resource_uri: str, payload: dict) -> None:
    """Store a small resource payload for context-free MCP resource reads."""
    _RESOURCE_CACHE[resource_uri] = payload


def _cached_or_note(resource_uri: str, note: str, **extra) -> dict:
    cached = _RESOURCE_CACHE.get(resource_uri)
    if cached is not None:
        return cached
    return {
        "resource_schema_version": 1,
        "resource_uri": resource_uri,
        "mode": "static",
        "available": False,
        "note": note,
        **extra,
    }


@mcp.resource("td://timeline/state", name="td_timeline_state")
async def td_resource_timeline() -> str:
    fallback = {"mode": "static"}
    return _cached_or_note(
        "td://timeline/state",
        "Use td_get_timescale_state tool for live timeline data.",
        **fallback,
    )


@mcp.resource("td://project/state", name="td_project_state")
async def td_resource_project_state() -> str:
    fallback = {"mode": "static"}
    return _cached_or_note(
        "td://project/state",
        "Use td_get_state_vector or td_brain_plan to populate cached project state.",
        **fallback,
    )


@mcp.resource("td://activity/recent", name="td_activity_recent")
async def td_resource_activity_recent() -> str:
    fallback = {"mode": "static"}
    return _cached_or_note(
        "td://activity/recent",
        "Use td_get_activity_log or a brain tool to populate cached activity.",
        **fallback,
    )


@mcp.resource("ui://tdpilot/cockpit.html",
    name="tdpilot_cockpit",
    title="TDPilot Brain Cockpit",
    description="Render-only MCP Apps cockpit for BrainPlan, transaction, validation, and rollback state.",
    mime_type="text/html;profile=mcp-app",
    meta={
        "openai/widgetDescription": "Interactive summary of a TDPilot BrainPlan and transaction result.",
        "openai/widgetPrefersBorder": True,
    },
)
async def td_resource_cockpit() -> str:
    return cockpit_html()


@mcp.resource("td://chop/path/{encoded_path}/channel/{channel}", name="td_chop_channel")
async def td_resource_chop_channel(encoded_path: str, channel: str) -> str:
    fallback = {"mode": "static"}
    try:
        path = decode_td_path(encoded_path)
        uri = chop_uri(path, channel)
    except Exception:  # noqa: BLE001 - resource fallbacks must never raise.
        path = encoded_path
        uri = f"td://chop/path/{encoded_path}/channel/{channel}"
    return _cached_or_note(
        uri,
        "Use td_chop_data tool for live CHOP channel data.",
        **fallback,
        path=path,
        channel=channel,
    )


@mcp.resource("td://par/path/{encoded_path}/name/{name}", name="td_parameter")
async def td_resource_parameter(encoded_path: str, name: str) -> str:
    fallback = {"mode": "static"}
    try:
        path = decode_td_path(encoded_path)
        uri = par_uri(path, name)
    except Exception:  # noqa: BLE001 - resource fallbacks must never raise.
        path = encoded_path
        uri = f"td://par/path/{encoded_path}/name/{name}"
    return _cached_or_note(
        uri,
        "Use td_get_params tool for live parameter data.",
        **fallback,
        path=path,
        name=name,
    )


@mcp.resource("td://cook/path/{encoded_path}", name="td_cook_state")
async def td_resource_cook(encoded_path: str) -> str:
    fallback = {"mode": "static"}
    try:
        path = decode_td_path(encoded_path)
        uri = cook_uri(path)
    except Exception:  # noqa: BLE001 - resource fallbacks must never raise.
        path = encoded_path
        uri = f"td://cook/path/{encoded_path}"
    return _cached_or_note(
        uri,
        "Use td_cooking_info tool for live cook state data.",
        **fallback,
        path=path,
    )


@mcp.resource("td://error/path/{encoded_path}", name="td_error_state")
async def td_resource_error(encoded_path: str) -> str:
    fallback = {"mode": "static"}
    try:
        path = decode_td_path(encoded_path)
        uri = error_uri(path)
    except Exception:  # noqa: BLE001 - resource fallbacks must never raise.
        path = encoded_path
        uri = f"td://error/path/{encoded_path}"
    return _cached_or_note(
        uri,
        "Use td_get_errors tool for live error data.",
        **fallback,
        path=path,
    )


@mcp.resource("td://node/path/{encoded_path}", name="td_node_context")
async def td_resource_node(encoded_path: str) -> str:
    fallback = {"mode": "static"}
    path = decode_td_path(encoded_path)
    uri = f"td://node/path/{encoded_path}"
    return _cached_or_note(uri, "Use td_get_node_detail to populate cached node context.", **fallback, path=path)


@mcp.resource("td://top/path/{encoded_path}/frame", name="td_top_frame")
async def td_resource_top_frame(encoded_path: str) -> str:
    fallback = {"mode": "static"}
    path = decode_td_path(encoded_path)
    uri = top_frame_uri(path)
    return _cached_or_note(
        uri,
        "Use td_screenshot or td_stream_top tool for live TOP frame data.",
        **fallback,
        path=path,
    )


@mcp.resource("td://top/path/{encoded_path}/analysis", name="td_top_analysis")
async def td_resource_top_analysis(encoded_path: str) -> str:
    fallback = {"mode": "static"}
    path = decode_td_path(encoded_path)
    uri = f"td://top/path/{encoded_path}/analysis"
    return _cached_or_note(
        uri,
        "Use td_analyze_frame or td_brain_execute to populate TOP analysis.",
        **fallback,
        path=path,
    )


@mcp.resource("td://memory/technique/{technique_id}", name="td_memory_technique")
async def td_resource_memory_technique(technique_id: str) -> str:
    fallback = {"mode": "static"}
    uri = f"td://memory/technique/{technique_id}"
    return _cached_or_note(
        uri,
        "Use td_memory_recall/td_memory_replay or td_brain_execute learning to populate technique context.",
        **fallback,
        technique_id=technique_id,
    )


@mcp.resource("td://job/{job_id}", name="td_job_state")
async def td_resource_job(job_id: str) -> str:
    fallback = {"mode": "static"}
    uri = f"td://job/{job_id}"
    return _cached_or_note(uri, "Use job tracking tools for live job state.", **fallback, job_id=job_id)


# Core tools (v1)
