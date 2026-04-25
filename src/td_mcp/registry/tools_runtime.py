"""Runtime control tools — timeline, project lifecycle, pulse, Python help.

Part of the v1.5.0 Phase 2 module split.

Tools in this module (6):
    td_timeline             — current timeline frame/state (zero-arg)
    td_timeline_set         — play/pause/set frame/set FPS
    td_project_lifecycle    — save/load/undo/redo + undo blocks
    td_pulse_param          — trigger pulse-type parameters
    td_python_help          — Python docs for TD classes
    td_python_classes       — list TD Python classes (zero-arg)

All six are thin ``_forward()`` wrappers — no local state, no
managers beyond the base TD client.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

# Intentional cycle — see registry/__init__.py.
from td_mcp import tool_registry as _tr  # noqa: E402
from td_mcp.models import ProjectLifecycleInput
from td_mcp.tool_registry import mcp  # noqa: E402


@mcp.tool(name="td_timeline")
async def td_timeline(ctx: Context) -> str:
    return await _tr._forward(ctx, "td_timeline", "timeline")


@mcp.tool(name="td_timeline_set")
async def td_timeline_set(
    ctx: Context,
    action: Annotated[
        str | None,
        Field(
            default=None,
            description="Timeline action: 'play', 'pause', or 'frame' (set specific frame)",
        ),
    ] = None,
    frame: Annotated[
        int | None,
        Field(
            default=None,
            ge=0,
            description="Frame number to jump to (when action='frame')",
        ),
    ] = None,
    fps: Annotated[
        float | None,
        Field(default=None, gt=0, le=240, description="Set cook rate / FPS"),
    ] = None,
) -> str:
    """Control timeline playback: play/pause, jump to frame, set FPS."""
    body: dict[str, Any] = {}
    if action is not None:
        body["action"] = action
    if frame is not None:
        body["frame"] = frame
    if fps is not None:
        body["fps"] = fps
    return await _tr._forward(
        ctx,
        "td_timeline_set",
        "timeline/set",
        body,
        audit_event="td_timeline_set",
    )


@mcp.tool(name="td_project_lifecycle")
async def td_project_lifecycle(
    ctx: Context,
    action: Annotated[
        str,
        Field(
            description=(
                "Lifecycle action: status, save, load, undo, redo, "
                "start_undo_block, end_undo_block, clear_undo"
            ),
            min_length=1,
        ),
    ],
    path: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Project path for save/load. For save with no path, "
                "TouchDesigner will perform its default incremental save behavior."
            ),
        ),
    ] = None,
    save_external_toxs: Annotated[
        bool,
        Field(
            default=False,
            description="Also save external tox contents on save",
        ),
    ] = False,
    name: Annotated[
        str | None,
        Field(
            default=None,
            description="Undo block name when action=start_undo_block",
        ),
    ] = None,
    enable: Annotated[
        bool,
        Field(
            default=True,
            description="Whether a started undo block should record undo state",
        ),
    ] = True,
) -> str:
    """Save/load/undo/redo project lifecycle operations."""
    # Re-instantiate so the ProjectLifecycleInput custom @field_validator on
    # ``action`` (allowed-set check) still runs and lowercases the value.
    validated = ProjectLifecycleInput(
        action=action,
        path=path,
        save_external_toxs=save_external_toxs,
        name=name,
        enable=enable,
    )
    return await _tr._forward(
        ctx,
        "td_project_lifecycle",
        "project/lifecycle",
        validated.model_dump(),
        audit_event="td_project_lifecycle",
    )


@mcp.tool(name="td_pulse_param")
async def td_pulse_param(
    ctx: Context,
    path: Annotated[
        str,
        Field(description="Node path", min_length=1),
    ],
    param: Annotated[
        str,
        Field(description="Parameter name to pulse", min_length=1),
    ],
) -> str:
    """Pulse a pulse-type parameter (e.g. a button par)."""
    return await _tr._forward(
        ctx,
        "td_pulse_param",
        "pulse",
        {"path": path, "param": param},
        audit_event="td_pulse_param",
    )


@mcp.tool(name="td_python_help")
async def td_python_help(
    ctx: Context,
    target: Annotated[
        str,
        Field(
            description=("Python object/class to get help for (e.g. 'td', 'td.OP', 'tdu', 'td.TOP')"),
            min_length=1,
        ),
    ],
) -> str:
    """Get Python help documentation for a TD class/module."""
    return await _tr._forward(ctx, "td_python_help", "python/help", {"target": target})


@mcp.tool(name="td_python_classes")
async def td_python_classes(ctx: Context) -> str:
    return await _tr._forward(ctx, "td_python_classes", "python/classes")


# Extended tools
