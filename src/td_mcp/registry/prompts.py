"""Portable MCP prompts for TDPilot brain workflows."""

from __future__ import annotations

from td_mcp.tool_registry import mcp


@mcp.prompt(
    name="td_brain_build",
    title="Build TD Brain Network",
    description="Route, ground, review, execute, and validate a complete TouchDesigner network build.",
)
def td_brain_build(intent: str = "", target_root: str = "/project1") -> str:
    return (
        "Use TDPilot's practical-intelligence brain loop.\n"
        f"Intent: {intent or '<ask user for the exact visual system>'}\n"
        f"Target root: {target_root}\n"
        "Inspect the relevant live scope and extract every required capability, input, output, constraint, "
        "spatial feature, behavior, binding, and validation need. Use td_brain_plan(detail_level='summary') "
        "only for an exact validated pattern. For artistic, multi-domain, spatial, camera/depth/fog, or "
        "implicit architecture, call td_brain_ground(include_memory=true, trace_level='summary'), author against "
        "its contract, and review with td_brain_propose using the returned grounding_id and detail_level='summary'. "
        "Execute only an accepted plan_id "
        "whose required intent coverage is complete and whose semantic edges are fully lowered. Validate the "
        "actual graph, runtime, and requested visual behavior before reporting completion."
    )


@mcp.prompt(
    name="td_brain_debug",
    title="Debug TD Brain Network",
    description="Inspect and debug a TouchDesigner network with brain planning, errors, cook stats, and hints.",
)
def td_brain_debug(path: str = "/project1") -> str:
    return (
        f"Debug {path} with TDPilot. Inspect focus/state, get node errors recursively, read cook stats, "
        "load relevant hints and recent activity, and identify the failed assertion before mutating. "
        "Use a typed direct repair for one proven edit; otherwise choose the exact-pattern or "
        "ground-author-propose brain route. Validate the repaired behavior and rollback state."
    )


@mcp.prompt(
    name="td_brain_validate",
    title="Validate TD Brain Result",
    description="Run structural, cook, error, and cheap visual validation for a recently built network.",
)
def td_brain_validate(path: str = "/project1", output_top: str = "") -> str:
    return (
        f"Validate the actual result at {path}, not only its plan structure. Check requirement coverage, "
        "graph topology, references and bindings, TD errors, cook health, and relevant signal/readback. "
        f"When an output is available, analyze {output_top or '<output TOP>'} for the requested visual and "
        "temporal behavior. Report unavailable evidence as unverified and say whether rollback is recommended."
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
