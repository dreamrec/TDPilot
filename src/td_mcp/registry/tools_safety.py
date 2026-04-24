"""Safety + stability tools.

Part of the v1.5.0 Phase 2 module split.

Tools in this module (4):
    td_set_param_bounds     — install parameter-value clamps
    td_clear_param_bounds   — remove clamps (all or by path)
    td_detect_instability   — FPS/cook/error diagnostic scan
    td_emergency_stabilize  — pause timeline, clamp safety, baseline snap
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.errors import format_tool_error
from td_mcp.models import ParamBound, SetBoundsInput
from td_mcp.tool_registry import mcp  # noqa: E402


@mcp.tool(name="td_set_param_bounds")
async def td_set_param_bounds(
    ctx: Context,
    bounds: Annotated[
        list[ParamBound],
        Field(
            min_length=1,
            max_length=500,
            description=(
                "One or more parameter safety bounds. Each bound has "
                "path, param, and optional min_val / max_val / max_rate."
            ),
        ),
    ],
    enforce_mode: Annotated[
        str,
        Field(
            default="clamp",
            description="Enforcement mode: clamp | reject | warn",
        ),
    ] = "clamp",
) -> str:
    """Set parameter safety bounds with enforcement mode."""
    # Re-instantiate so the SetBoundsInput @field_validator on enforce_mode
    # (clamp|reject|warn) still runs.
    validated = SetBoundsInput(bounds=bounds, enforce_mode=enforce_mode)
    finish = _tr._start_tool(ctx, "td_set_param_bounds")
    try:
        safety = _tr._get_safety_manager(ctx)
        safety.set_mode(validated.enforce_mode)

        for bound in validated.bounds:
            key = f"{bound.path}/{bound.param}"
            safety.set_bound(
                key,
                min_val=bound.min_val,
                max_val=bound.max_val,
                max_rate=bound.max_rate,
            )

        payload = {
            "success": True,
            "mode": safety.get_mode(),
            "bounds_count": len(safety.list_bounds()),
            "bounds": safety.list_bounds(),
        }

        _tr._audit_log(
            ctx,
            "td_set_param_bounds",
            {
                "mode": validated.enforce_mode,
                "count": len(validated.bounds),
            },
        )
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_set_param_bounds")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_clear_param_bounds")
async def td_clear_param_bounds(
    ctx: Context,
    paths: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="Clear bounds for specific node paths (None = clear all).",
        ),
    ] = None,
) -> str:
    """Clear parameter bounds for specific paths, or all bounds if paths is None."""
    finish = _tr._start_tool(ctx, "td_clear_param_bounds")
    try:
        safety = _tr._get_safety_manager(ctx)

        cleared = 0
        if paths:
            keys = list(safety.list_bounds().keys())
            for key in keys:
                if any(key.startswith(p.rstrip("/") + "/") or key == p for p in paths):
                    if safety.clear_bound(key):
                        cleared += 1
        else:
            cleared = safety.clear_all()

        payload = {
            "success": True,
            "cleared": cleared,
            "remaining": len(safety.list_bounds()),
            "mode": safety.get_mode(),
        }
        _tr._audit_log(
            ctx,
            "td_clear_param_bounds",
            {"paths": paths, "cleared": cleared},
        )
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_clear_param_bounds")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_detect_instability")
async def td_detect_instability(
    ctx: Context,
    path: Annotated[
        str,
        Field(default="/project1", description="Root path to inspect."),
    ] = "/project1",
) -> str:
    """Detect instability signals: FPS, heavy cookers, critical errors."""
    finish = _tr._start_tool(ctx, "td_detect_instability")
    try:
        client = _tr._get_client(ctx)
        cooking = await client.request(
            "cooking",
            {
                "path": path,
                "recurse": True,
                "limit": 50,
                "sort_by": "cookTime",
            },
        )
        errors = await client.request(
            "node/errors",
            {
                "path": path,
                "recurse": True,
                "max_depth": 10,
            },
        )

        fps = float(cooking.get("fps", 0.0) or 0.0)
        realtime = bool(cooking.get("realTime", False))
        target_fps = float(cooking.get("target_fps", fps) or fps or 60.0) or 60.0
        all_cook_nodes = cooking.get("nodes", [])
        issues = errors.get("issues", []) if isinstance(errors, dict) else []

        # Delegate to the shared helper so state_vector's health section and
        # detect_instability never disagree again (N3 audit). Heavy-node
        # reporting stays here because it's only relevant to this tool.
        unstable, reasons, metrics = _tr._compute_unstable_signal(
            fps, all_cook_nodes, issues, target_fps=target_fps
        )
        frame_budget_ms = metrics["frame_budget_ms"]
        top_cook_ms = metrics["top_cook_ms"]
        critical_issues = [
            item for item in issues if isinstance(item, dict) and (item.get("errors") or "").strip()
        ]
        heavy_threshold_ms = max(frame_budget_ms * 0.25, 1.0)
        heavy_nodes = [
            node
            for node in all_cook_nodes
            if isinstance(node, dict) and float(node.get("cookTime", 0.0) or 0.0) >= heavy_threshold_ms
        ]

        payload = {
            "schema_version": 2,
            "path": path,
            "unstable": unstable,
            "reasons": reasons,
            "signals": {
                "fps": fps,
                "target_fps": target_fps,
                "frame_budget_ms": round(frame_budget_ms, 3),
                "heavy_threshold_ms": round(heavy_threshold_ms, 3),
                "realtime": realtime,
                "issues_count": len(issues),
                "critical_issues_count": len(critical_issues),
                "heavy_nodes_count": len(heavy_nodes),
                "top_cook_ms": round(top_cook_ms, 3),
            },
            "heavy_nodes": heavy_nodes[:10],
            "issues": issues[:20],
            "suggested_actions": [
                "Pause timeline and inspect top cook-time operators.",
                "Clamp unstable parameters via td_set_param_bounds.",
                "Use td_snapshot_scene before large edits.",
            ],
        }
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_detect_instability")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_emergency_stabilize")
async def td_emergency_stabilize(
    ctx: Context,
    path: Annotated[
        str,
        Field(default="/project1", description="Root path to stabilize."),
    ] = "/project1",
) -> str:
    """Emergency stabilization: pause timeline, clamp safety, capture baseline snapshot."""
    finish = _tr._start_tool(ctx, "td_emergency_stabilize")
    try:
        client = _tr._get_client(ctx)
        snapshots = _tr._get_snapshot_manager(ctx)

        snapshot_payload = await _tr._capture_snapshot_payload(
            ctx,
            path=path,
            include_visual=False,
        )
        saved = snapshots.add_snapshot(snapshot_payload, name="emergency_pre_stabilize")

        actions = []
        timeline = await client.request("timeline")
        if timeline.get("playing"):
            await client.request("timeline/set", {"action": "pause"})
            actions.append("timeline_paused")

        safety = _tr._get_safety_manager(ctx)
        if safety.get_mode() != "clamp":
            safety.set_mode("clamp")
            actions.append("safety_mode_clamp")

        payload = {
            "success": True,
            "path": path,
            "actions": actions,
            "snapshot": {
                "snapshot_id": saved["snapshot_id"],
                "name": saved["name"],
                "timestamp": saved["timestamp"],
            },
            "next": [
                "Inspect td_detect_instability for current bottlenecks.",
                "Restore from snapshot if needed with td_restore_snapshot.",
            ],
        }

        _tr._audit_log(
            ctx,
            "td_emergency_stabilize",
            {
                "path": path,
                "actions": actions,
                "snapshot_id": saved["snapshot_id"],
            },
        )
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_emergency_stabilize")
        return format_tool_error(exc)
    finally:
        finish()
