"""MCP resource handlers — URI templates for timeline/chop/par/cook/error/frame/job.

Part of the v1.5.0 Phase 2 module split. See
``src/td_mcp/registry/__init__.py`` for the intentional-cycle pattern.

Resource handlers exposed (7):
    td://timeline/state                              — static hint to use tool
    td://chop/path/{encoded_path}/channel/{channel}  — CHOP channel hint
    td://par/path/{encoded_path}/name/{name}         — parameter hint
    td://cook/path/{encoded_path}                    — cook state hint
    td://error/path/{encoded_path}                   — node error hint
    td://top/path/{encoded_path}/frame               — TOP frame hint
    td://job/{job_id}                                — async job state hint

All are static "read-through" placeholders that redirect clients to the
corresponding live tool (e.g. ``td_chop_data``). The URI-template shape
lets clients discover via MCP resource listing without having to know
the right tool name first.

Context injection was removed for mcp>=1.3 compatibility, so these
resources don't need tool_registry helper access — they only emit URI
metadata. No ``_tr.`` prefix needed.
"""

from __future__ import annotations

from td_mcp.events.uri import (
    chop_uri,
    cook_uri,
    decode_td_path,
    error_uri,
    par_uri,
    top_frame_uri,
)
from td_mcp.tool_registry import mcp  # noqa: E402 — intentional cycle


@mcp.resource("td://timeline/state", name="td_timeline_state")
async def td_resource_timeline() -> str:
    # NOTE: Context injection not supported for parameter-less resources in mcp>=1.3.
    # Clients should use the td_get_timescale_state tool for live timeline data.
    return {
        "resource_schema_version": 1,
        "resource_uri": "td://timeline/state",
        "mode": "static",
        "note": "Use td_get_timescale_state tool for live timeline data.",
    }


@mcp.resource("td://chop/path/{encoded_path}/channel/{channel}", name="td_chop_channel")
async def td_resource_chop_channel(encoded_path: str, channel: str) -> str:
    # NOTE: Context injection removed for mcp>=1.3 compatibility.
    # Use td_chop_data tool for live CHOP data.
    path = decode_td_path(encoded_path)
    uri = chop_uri(path, channel)
    try:
        pass  # read-through fallback requires context; see td_chop_data tool
    except Exception:
        pass
    return {
        "resource_schema_version": 1,
        "resource_uri": uri,
        "mode": "static",
        "path": path,
        "channel": channel,
        "available": False,
        "note": "Use td_chop_data tool for live CHOP channel data.",
    }


@mcp.resource("td://par/path/{encoded_path}/name/{name}", name="td_parameter")
async def td_resource_parameter(encoded_path: str, name: str) -> str:
    # NOTE: Context injection removed for mcp>=1.3 compatibility.
    # Use td_get_params tool for live parameter data.
    path = decode_td_path(encoded_path)
    uri = par_uri(path, name)
    try:
        pass  # read-through fallback requires context; see td_get_params tool
    except Exception:
        pass
    return {
        "resource_schema_version": 1,
        "resource_uri": uri,
        "mode": "static",
        "path": path,
        "name": name,
        "available": False,
        "note": "Use td_get_params tool for live parameter data.",
    }


@mcp.resource("td://cook/path/{encoded_path}", name="td_cook_state")
async def td_resource_cook(encoded_path: str) -> str:
    # NOTE: Context injection removed for mcp>=1.3 compatibility.
    # Use td_cooking_info tool for live cook data.
    path = decode_td_path(encoded_path)
    uri = cook_uri(path)
    try:
        pass  # read-through fallback requires context; see td_cooking_info tool
    except Exception:
        pass
    return {
        "resource_schema_version": 1,
        "resource_uri": uri,
        "mode": "static",
        "path": path,
        "available": False,
        "note": "Use td_cooking_info tool for live cook state data.",
    }


@mcp.resource("td://error/path/{encoded_path}", name="td_error_state")
async def td_resource_error(encoded_path: str) -> str:
    # NOTE: Context injection removed for mcp>=1.3 compatibility.
    # Use td_get_errors tool for live error data.
    path = decode_td_path(encoded_path)
    uri = error_uri(path)
    try:
        pass  # read-through fallback requires context; see td_get_errors tool
    except Exception:
        pass
    return {
        "resource_schema_version": 1,
        "resource_uri": uri,
        "mode": "static",
        "path": path,
        "available": False,
        "note": "Use td_get_errors tool for live error data.",
    }


@mcp.resource("td://top/path/{encoded_path}/frame", name="td_top_frame")
async def td_resource_top_frame(encoded_path: str) -> str:
    # NOTE: Context injection removed for mcp>=1.3 compatibility.
    # Use td_screenshot or td_stream_top tool for live TOP frame data.
    path = decode_td_path(encoded_path)
    uri = top_frame_uri(path)
    return {
        "resource_schema_version": 1,
        "resource_uri": uri,
        "mode": "static",
        "path": path,
        "available": False,
        "note": "Use td_screenshot or td_stream_top tool for live TOP frame data.",
    }


@mcp.resource("td://job/{job_id}", name="td_job_state")
async def td_resource_job(job_id: str) -> str:
    # NOTE: Context injection removed for mcp>=1.3 compatibility.
    # Job state cannot be retrieved via resource; use job tracking tools.
    return {
        "resource_schema_version": 1,
        "resource_uri": f"td://job/{job_id}",
        "mode": "static",
        "job_id": job_id,
        "available": False,
        "note": "Use job tracking tools for live job state.",
    }


# Core tools (v1)
