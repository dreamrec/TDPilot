"""Snapshot tools — capture + restore + diff project state.

Part of the v1.5.0 Phase 2 module split. See
``src/td_mcp/registry/__init__.py`` for the intentional-cycle pattern.

Tools in this module (4):
    td_snapshot_scene    — capture current scene (+optional visual)
    td_list_snapshots    — list saved snapshots
    td_diff_snapshots    — diff two snapshots (or snap vs. live)
    td_restore_snapshot  — replay parameter values from a snapshot

Restores are PARAMETER-ONLY — for structural rollback (nodes added,
removed, rewired) use TouchDesigner's native Ctrl+Z stack instead.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.errors import format_tool_error
from td_mcp.tool_registry import mcp  # noqa: E402


@mcp.tool(name="td_snapshot_scene")
async def td_snapshot_scene(
    ctx: Context,
    name: Annotated[
        str | None,
        Field(default=None, description="Optional snapshot label."),
    ] = None,
    path: Annotated[
        str,
        Field(default="/project1", description="Root path to snapshot."),
    ] = "/project1",
    include_visual: Annotated[
        bool,
        Field(default=False, description="Include screenshot payload."),
    ] = False,
) -> str:
    """Capture a scene snapshot (structure + params; optionally visual)."""
    finish = _tr._start_tool(ctx, "td_snapshot_scene")
    try:
        payload = await _tr._capture_snapshot_payload(
            ctx,
            path=path,
            include_visual=include_visual,
        )
        snapshot = _tr._get_snapshot_manager(ctx).add_snapshot(payload, name=name)

        result = {
            "success": True,
            "snapshot_id": snapshot["snapshot_id"],
            "name": snapshot["name"],
            "timestamp": snapshot["timestamp"],
            "summary": {
                "captured_nodes": payload.get("captured_nodes", 0),
                "connection_count": len(payload.get("connections", [])),
                "truncated": payload.get("truncated", False),
                "include_visual": include_visual,
            },
        }
        return _tr._as_json_output(result)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_snapshot_scene")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_list_snapshots")
async def td_list_snapshots(
    ctx: Context,
    limit: Annotated[
        int,
        Field(
            default=20,
            ge=1,
            le=100,
            description="Max number of snapshots to return (newest first).",
        ),
    ] = 20,
) -> str:
    """List saved scene snapshots (newest first)."""
    finish = _tr._start_tool(ctx, "td_list_snapshots")
    try:
        snapshots = _tr._get_snapshot_manager(ctx).list_snapshots(limit=limit)
        return _tr._as_json_output(
            {
                "schema_version": 1,
                "count": len(snapshots),
                "snapshots": snapshots,
            }
        )
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_list_snapshots")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_diff_snapshots")
async def td_diff_snapshots(
    ctx: Context,
    snapshot_a: Annotated[
        str,
        Field(description="Baseline snapshot id.", min_length=1),
    ],
    snapshot_b: Annotated[
        str | None,
        Field(
            default=None,
            description="If omitted, diff snapshot_a vs live state.",
        ),
    ] = None,
) -> str:
    """Diff two snapshots, or a snapshot against live state."""
    finish = _tr._start_tool(ctx, "td_diff_snapshots")
    try:
        manager = _tr._get_snapshot_manager(ctx)

        snap_a = manager.get_snapshot(snapshot_a)
        if snap_a is None:
            raise ValueError(f"Snapshot not found: {snapshot_a}")

        if snapshot_b:
            snap_b = manager.get_snapshot(snapshot_b)
            if snap_b is None:
                raise ValueError(f"Snapshot not found: {snapshot_b}")
            compare_target = {
                "type": "snapshot",
                "snapshot_id": snapshot_b,
            }
            snapshot_b_payload = snap_b["snapshot"]
        else:
            live = await _tr._capture_snapshot_payload(
                ctx,
                path=snap_a["snapshot"].get("root_path", "/project1"),
                include_visual=False,
            )
            compare_target = {
                "type": "live",
                "path": live.get("root_path", "/project1"),
            }
            snapshot_b_payload = live

        diff = manager.diff(snap_a["snapshot"], snapshot_b_payload)
        payload = {
            "schema_version": 1,
            "snapshot_a": snapshot_a,
            "compare_target": compare_target,
            "diff": diff,
        }
        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_diff_snapshots")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_restore_snapshot")
async def td_restore_snapshot(
    ctx: Context,
    snapshot_id: Annotated[
        str,
        Field(
            description="Snapshot id to restore parameter values from.",
            min_length=1,
        ),
    ],
    partial: Annotated[
        list[str] | None,
        Field(
            default=None,
            description=(
                "Optional subset of node paths. When provided, only these nodes "
                "(and no others) have their parameters restored from the snapshot."
            ),
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        Field(
            default=False,
            description="Return diff only without applying.",
        ),
    ] = False,
) -> str:
    """Restore parameter values from a previously saved snapshot.

    This tool replays the parameter values captured in the snapshot back onto
    the live TouchDesigner network.  It restores *parameter values only* — it
    does not add, remove, or rewire nodes.  For structural rollback (topology
    changes such as added/deleted nodes or connection changes) use
    TouchDesigner's native Ctrl+Z undo stack instead.

    Use ``dry_run=True`` to preview what would be changed without applying
    anything.  Supply ``partial`` with a list of node paths to limit the
    restore to a subset of the snapshot.
    """
    finish = _tr._start_tool(ctx, "td_restore_snapshot")
    try:
        manager = _tr._get_snapshot_manager(ctx)
        snapshot = manager.get_snapshot(snapshot_id)
        if snapshot is None:
            raise ValueError(f"Snapshot not found: {snapshot_id}")

        snapshot_nodes = snapshot.get("snapshot", {}).get("nodes", {})
        if not isinstance(snapshot_nodes, dict):
            snapshot_nodes = {}

        client = _tr._get_client(ctx)
        safety = _tr._get_safety_manager(ctx)
        restore_result = await _tr._restore_snapshot_nodes(
            client,
            safety,
            snapshot_nodes,
            partial_filters=partial or [],
            dry_run=dry_run,
        )
        restored = restore_result["restored"]
        skipped = restore_result["skipped"]
        failures = restore_result["failures"]
        warnings = restore_result["safety_warnings"]

        payload = {
            "success": not failures,
            "snapshot_id": snapshot_id,
            "dry_run": dry_run,
            "restored_count": len(restored),
            "skipped_count": len(skipped),
            "failure_count": len(failures),
            "restored": restored,
            "skipped": skipped,
            "failures": failures,
            "safety_warnings": warnings,
        }

        if not dry_run:
            _tr._audit_log(
                ctx,
                "td_restore_snapshot",
                {
                    "snapshot_id": snapshot_id,
                    "restored_count": len(restored),
                    "failure_count": len(failures),
                    "partial": partial,
                },
            )

        return _tr._as_json_output(payload)
    except Exception as exc:
        _tr._record_tool_error(ctx, "td_restore_snapshot")
        return format_tool_error(exc)
    finally:
        finish()
