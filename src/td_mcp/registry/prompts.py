"""Portable MCP prompts for TDPilot brain workflows."""

from __future__ import annotations

from td_mcp.tool_registry import mcp


@mcp.prompt(
    name="td_brain_build",
    title="Build TD Brain Network",
    description="Plan and execute a grounded TouchDesigner network build through td_brain_plan and td_brain_execute.",
)
def td_brain_build(intent: str = "", target_root: str = "/project1") -> str:
    return (
        "Use TDPilot's correctness-first brain loop.\n"
        f"Intent: {intent or '<ask user for the exact visual system>'}\n"
        f"Target root: {target_root}\n"
        "Call td_brain_plan first. If blocked_questions are returned, ask those before mutating. "
        "Only call td_brain_execute with the returned BrainPlan after checking the risks."
    )


@mcp.prompt(
    name="td_brain_debug",
    title="Debug TD Brain Network",
    description="Inspect and debug a TouchDesigner network with brain planning, errors, cook stats, and hints.",
)
def td_brain_debug(path: str = "/project1") -> str:
    return (
        f"Debug {path} with TDPilot. Inspect focus/state, get node errors recursively, read cook stats, "
        "load relevant hints, and propose a BrainPlan only if a mutation is needed."
    )


@mcp.prompt(
    name="td_brain_validate",
    title="Validate TD Brain Result",
    description="Run structural, cook, error, and cheap visual validation for a recently built network.",
)
def td_brain_validate(path: str = "/project1", output_top: str = "") -> str:
    return (
        f"Validate {path}. Run td_patch_validate and, when output_top is provided, td_analyze_frame for "
        f"{output_top or '<output TOP>'}. Report remaining errors, warnings, and whether rollback is recommended."
    )


@mcp.prompt(
    name="td_snapshot_before_edit",
    title="Snapshot Before TD Edit",
    description="Create a rollback point before risky TouchDesigner edits.",
)
def td_snapshot_before_edit(path: str = "/project1") -> str:
    return f"Before editing {path}, call td_snapshot_scene(include_visual=false), then proceed with a small verified edit."


@mcp.prompt(
    name="td_recover_network",
    title="Recover TD Network",
    description="Recover a broken TouchDesigner network using errors, undo, snapshots, and validation.",
)
def td_recover_network(path: str = "/project1") -> str:
    return (
        f"Recover {path}. Inspect errors and recent activity, prefer undo for recent structural damage, "
        "use snapshots for parameter fallback, then validate the recovered state."
    )


@mcp.prompt(
    name="td_learn_validated_technique",
    title="Learn Validated TD Technique",
    description="Capture a validated TouchDesigner network as reusable local memory.",
)
def td_learn_validated_technique(path: str, name: str = "") -> str:
    return (
        f"Learn the validated network at {path}. Use td_memory_learn, validate the extracted technique, "
        f"then save it with name {name or '<descriptive name>'} and tags tied to the visual concept."
    )
