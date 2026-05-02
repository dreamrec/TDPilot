"""Info/metadata tools — TD build, capabilities, runtime metrics.

Part of the v1.5.0 Phase 2 module split. This is the final extraction
— all 103 tools + 7 resources now live in themed submodules (the 5 new
td_patch_* tools landed in Phase 3).

Tools in this module (4):
    td_get_info            — TD build, version, mcp-component version
    td_list_families       — enumerate operator families (COMP/TOP/CHOP/…)
    td_get_capabilities    — client capabilities + component sync status
    td_get_server_metrics  — runtime telemetry dashboard

``td_get_capabilities`` and ``td_get_server_metrics`` are the heaviest
aggregators — they pull from EVERY manager (safety, snapshot, job,
event, visual_monitor, top_streamer, telemetry, audit). Kept together
here because they're the "server introspection" surface.
"""

from __future__ import annotations

from mcp.server.fastmcp import Context

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.capabilities import detect_capabilities
from td_mcp.errors import format_tool_error
from td_mcp.tool_registry import (  # noqa: E402
    TD_HOST,
    TD_PORT,
    TD_SHARED_SECRET,
    TD_SNAPSHOT_DIR,
    TD_STREAM_MAX_FPS,
    TD_TRANSPORT,
    TD_WS_PORT,
    mcp,
)


@mcp.tool(name="td_get_info")
async def td_get_info(ctx: Context) -> str:
    return await _tr._forward(ctx, "td_get_info", "info")


@mcp.tool(name="td_list_families")
async def td_list_families(ctx: Context) -> str:
    return await _tr._forward(ctx, "td_list_families", "families")


@mcp.tool(name="td_get_capabilities")
async def td_get_capabilities(ctx: Context) -> str:
    finish = _tr._start_tool(ctx, "td_get_capabilities")
    try:
        services = _tr._get_services(ctx)
        capabilities = detect_capabilities(ctx, td_build=services.td_build)
        from td_mcp import __version__ as server_version

        # Check component version if TD is connected
        version_status = {"server_version": server_version}
        try:
            info = await _tr._get_client(ctx).request("info")
            if isinstance(info, dict):
                comp_ver = info.get("mcp_component_version") or info.get("api_version", "")
                version_status["component_version"] = comp_ver
                if comp_ver and comp_ver != server_version:
                    version_status["mismatch"] = True
                    version_status["warning"] = (
                        f"TD component is v{comp_ver} but server is v{server_version}. "
                        f"Re-export the .tox to fix."
                    )
                elif comp_ver:
                    version_status["mismatch"] = False
        except Exception:
            version_status["component_version"] = "unknown (TD not reachable)"

        payload = {
            "schema_version": 1,
            "client_capabilities": capabilities.to_dict(),
            "version": version_status,
            "runtime": {
                "transport": TD_TRANSPORT,
                "exec_mode": _tr._current_exec_mode(),
                "shared_secret_enabled": bool(TD_SHARED_SECRET),
                "event_ws_port": TD_WS_PORT,
                "snapshot_persistence": bool(TD_SNAPSHOT_DIR),
                "stream_max_fps": TD_STREAM_MAX_FPS,
            },
        }
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_get_capabilities")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_get_server_metrics")
async def td_get_server_metrics(ctx: Context) -> str:
    finish = _tr._start_tool(ctx, "td_get_server_metrics")
    try:
        telemetry = _tr._get_telemetry(ctx)
        event_manager = _tr._get_event_manager(ctx)
        visual_monitor = _tr._get_visual_monitor(ctx)
        top_streamer = _tr._get_top_streamer(ctx)
        safety_manager = _tr._get_safety_manager(ctx)
        snapshot_manager = _tr._get_snapshot_manager(ctx)
        job_manager = _tr._get_job_manager(ctx)

        payload = {
            "schema_version": 1,
            "runtime": {
                "transport": TD_TRANSPORT,
                "exec_mode": _tr._current_exec_mode(),
                "host": TD_HOST,
                "port": TD_PORT,
                "event_ws_port": TD_WS_PORT,
                "stream_max_fps": TD_STREAM_MAX_FPS,
            },
            "telemetry": telemetry.snapshot() if telemetry else {},
            "events": event_manager.stats(),
            "visual_monitor": {
                "active": visual_monitor.active_monitors(),
            },
            "top_stream": top_streamer.stats(),
            "safety": safety_manager.stats(),
            "snapshots": snapshot_manager.stats(),
            "jobs": job_manager.stats(),
            "audit_enabled": bool(_tr._get_audit(ctx) and _tr._get_audit(ctx).enabled()),
        }
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_get_server_metrics")
        return format_tool_error(exc)
    finally:
        finish()
