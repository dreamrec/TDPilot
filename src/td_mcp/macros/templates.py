"""Built-in macro template library."""

from __future__ import annotations

from td_mcp.macros.models import (
    ConnectionSpec,
    ExpressionSpec,
    MacroTemplate,
    NodeRefParam,
    NodeSpec,
    ParamSpec,
    ParamTarget,
)


def build_default_templates() -> dict[str, MacroTemplate]:
    """Return built-in macro templates keyed by macro type string."""
    templates: dict[str, MacroTemplate] = {}

    templates["feedback_loop"] = MacroTemplate(
        name="feedback_loop",
        description="Classic feedback chain: feedback -> level -> composite -> out.",
        nodes=[
            NodeSpec("feedbackTOP", "feedback", dx=0, dy=0),
            NodeSpec("levelTOP", "decay", dx=220, dy=0, params={"opacity": 0.95}),
            NodeSpec("compositeTOP", "merge", dx=440, dy=0, params={"operand": "over"}),
            NodeSpec("nullTOP", "out", dx=660, dy=0),
        ],
        connections=[
            ConnectionSpec("feedback", "decay"),
            ConnectionSpec("decay", "merge", source_index=0, target_index=0),
            ConnectionSpec("merge", "out"),
        ],
        node_references=[
            NodeRefParam(node="feedback", param="top", target_node="out"),
        ],
        param_schema={
            "feedback_opacity": ParamSpec(
                type="float",
                default=0.95,
                min_value=0.0,
                max_value=1.0,
                description="Trail persistence in level TOP opacity.",
            ),
        },
        param_targets={
            "feedback_opacity": [ParamTarget(node="decay", param="opacity", mode="value")],
        },
        entry_node="merge",
        exit_node="out",
    )

    templates["post_processing"] = MacroTemplate(
        name="post_processing",
        description="Simple post-FX chain: level -> blur -> out.",
        nodes=[
            NodeSpec("levelTOP", "grade", dx=0, dy=0, params={"brightness1": 1.0}),
            NodeSpec("blurTOP", "blur", dx=220, dy=0, params={"filtersize": 4}),
            NodeSpec("nullTOP", "out", dx=440, dy=0),
        ],
        connections=[
            ConnectionSpec("grade", "blur"),
            ConnectionSpec("blur", "out"),
        ],
        param_schema={
            "brightness": ParamSpec(
                type="float",
                default=1.0,
                min_value=0.0,
                max_value=3.0,
                description="Overall gain (levelTOP brightness1).",
            ),
            "blur_size": ParamSpec(
                type="int",
                default=4,
                min_value=0,
                max_value=128,
                description="Blur kernel size.",
            ),
        },
        param_targets={
            "brightness": [ParamTarget(node="grade", param="brightness1", mode="value")],
            "blur_size": [ParamTarget(node="blur", param="filtersize", mode="value")],
        },
        entry_node="grade",
        exit_node="out",
    )

    templates["audio_reactive"] = MacroTemplate(
        name="audio_reactive",
        description="Audio signal preprocessing chain with gain stage and null output.",
        nodes=[
            NodeSpec("audiodeviceinCHOP", "audio_in", dx=0, dy=0),
            NodeSpec("analyzeCHOP", "audio_level", dx=220, dy=0),
            NodeSpec("mathCHOP", "gain", dx=440, dy=0, params={"mult": 1.0}),
            NodeSpec("nullCHOP", "out", dx=660, dy=0),
        ],
        connections=[
            ConnectionSpec("audio_in", "audio_level"),
            ConnectionSpec("audio_level", "gain"),
            ConnectionSpec("gain", "out"),
        ],
        param_schema={
            "gain": ParamSpec(
                type="float",
                default=1.0,
                min_value=0.0,
                max_value=10.0,
                description="Math CHOP multiplier.",
            ),
        },
        param_targets={
            "gain": [ParamTarget(node="gain", param="mult", mode="value")],
        },
        entry_node="audio_in",
        exit_node="out",
    )

    templates["particle_gpu"] = MacroTemplate(
        name="particle_gpu",
        description="Minimal POP chain: particle -> noise -> render.",
        nodes=[
            NodeSpec("particlePOP", "particles", dx=0, dy=0),
            NodeSpec("noisePOP", "noise", dx=220, dy=0),
            NodeSpec("renderPOP", "render", dx=440, dy=0),
            NodeSpec("nullTOP", "out", dx=660, dy=0),
        ],
        connections=[
            ConnectionSpec("particles", "noise"),
            ConnectionSpec("noise", "render"),
            ConnectionSpec("render", "out"),
        ],
        param_schema={},
        entry_node="particles",
        exit_node="out",
    )

    templates["feedback_displacement"] = MacroTemplate(
        name="feedback_displacement",
        description="Feedback displacement loop with source noise and composite merge.",
        nodes=[
            NodeSpec("noiseTOP", "source", dx=0, dy=0, params={"type": "simplex3d"}),
            NodeSpec("feedbackTOP", "feedback", dx=220, dy=0),
            NodeSpec("levelTOP", "decay", dx=440, dy=0, params={"opacity": 0.95}),
            NodeSpec("displaceTOP", "displace", dx=660, dy=0, params={"weightx": 0.05, "weighty": 0.05}),
            NodeSpec("compositeTOP", "merge", dx=880, dy=0, params={"operand": "over"}),
            NodeSpec("nullTOP", "out", dx=1100, dy=0),
        ],
        connections=[
            ConnectionSpec("feedback", "decay"),
            ConnectionSpec("source", "displace", source_index=0, target_index=0),
            ConnectionSpec("decay", "displace", source_index=0, target_index=1),
            ConnectionSpec("source", "merge", source_index=0, target_index=0),
            ConnectionSpec("displace", "merge", source_index=0, target_index=1),
            ConnectionSpec("merge", "out"),
        ],
        node_references=[
            NodeRefParam(node="feedback", param="top", target_node="out"),
        ],
        expressions=[
            ExpressionSpec(node="source", param="tz", expr="absTime.seconds * 0.3"),
        ],
        param_schema={
            "feedback_opacity": ParamSpec(
                type="float",
                default=0.95,
                min_value=0.0,
                max_value=1.0,
                description="Feedback level opacity.",
            ),
            "displacement_weight": ParamSpec(
                type="float",
                default=0.05,
                min_value=0.0,
                max_value=1.0,
                description="Displace weight (x and y).",
            ),
        },
        param_targets={
            "feedback_opacity": [ParamTarget(node="decay", param="opacity", mode="value")],
            "displacement_weight": [
                ParamTarget(node="displace", param="weightx", mode="value"),
                ParamTarget(node="displace", param="weighty", mode="value"),
            ],
        },
        entry_node="source",
        exit_node="out",
    )

    return templates
