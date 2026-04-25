"""Post-apply validation: errors + cook stats + optional frame capture.

Composite wrapper over existing TD endpoints:
  - node/errors      -> ValidationReport.errors
  - cooking          -> ValidationReport.cook_stats
  - screenshot       -> ValidationReport.frames (one call per path in
                       capture_frames; empty list skips)

See spec §6 + §5.4. This module is MCP-free.
"""

from __future__ import annotations

from typing import Any

from td_mcp.models.patch import ValidationPlan, ValidationReport


async def validate_target(td_client, plan: ValidationPlan) -> ValidationReport:
    """Run errors + cook checks on target_root; capture frames if requested."""
    errors: list[dict[str, Any]] = []
    try:
        resp = await td_client.request(
            "node/errors", {"path": plan.target_root, "recurse": True, "max_depth": 10}
        )
        if isinstance(resp, dict):
            errors = resp.get("issues", []) or []
        elif isinstance(resp, list):
            errors = resp
    except Exception as exc:  # noqa: BLE001
        errors = [{"source": "validator", "message": f"errors probe failed: {exc}"}]

    cook_stats: dict[str, Any] = {}
    try:
        cook_stats = await td_client.request("cooking", {"path": plan.target_root}) or {}
    except Exception as exc:  # noqa: BLE001
        cook_stats = {"probe_error": str(exc)}

    # v1.5.1: TD has no /api/frame/capture endpoint — the canonical path
    # for capturing a TOP frame is /api/screenshot which returns base64
    # JPEG under the ``data_base64`` key (see handle_screenshot in
    # mcp_webserver_callbacks.py:1612). Pre-v1.5.1 the validator silently
    # 404'd on every capture_frames entry and reported "ERROR: …" strings.
    frames: dict[str, str] = {}
    for top_path in plan.capture_frames:
        try:
            frame = await td_client.request("screenshot", {"path": top_path, "quality": 0.5})
            if isinstance(frame, dict):
                b64 = frame.get("data_base64") or frame.get("b64")
                if b64:
                    frames[top_path] = b64
                elif frame.get("error"):
                    frames[top_path] = f"ERROR: {frame['error']}"
        except Exception as exc:  # noqa: BLE001
            frames[top_path] = f"ERROR: {exc}"

    ok = not errors and not cook_stats.get("stuck")
    summary = (
        f"clean: {plan.target_root}"
        if ok
        else f"issues present at {plan.target_root}: {len(errors)} error(s)"
    )

    return ValidationReport(
        target_root=plan.target_root,
        errors=errors,
        cook_stats=cook_stats,
        frames=frames,
        ok=ok,
        summary=summary,
    )
