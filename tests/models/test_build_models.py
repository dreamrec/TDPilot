from __future__ import annotations

import pytest
from pydantic import ValidationError

from td_mcp.models.build import (
    BuildConstraints,
    BuildIntent,
    ModuleEdge,
    ModuleGraph,
    ModulePort,
    VisualModule,
    budget_for_mode,
)


def _module(
    module_id: str,
    *,
    role: str,
    technique_id: str,
    inputs: list[ModulePort] | None = None,
    outputs: list[ModulePort] | None = None,
) -> VisualModule:
    return VisualModule(
        id=module_id,
        role=role,
        technique_id=technique_id,
        label=module_id.replace("_", " ").title(),
        td_family="TOP",
        inputs=inputs or [],
        outputs=outputs or [],
    )


def test_build_intent_enforces_compact_prompt_projection():
    intent = BuildIntent(
        outcome="Build an animated feedback texture",
        visual_keywords=["dense", "organic"],
        behavior_keywords=["slow", "looping"],
    )

    assert intent.schema_version == 2
    assert intent.mode == "production"
    assert intent.target_path == "/project1"

    with pytest.raises(ValidationError):
        BuildIntent(outcome="x" * 241)


def test_module_graph_rejects_dangling_modules_and_ports():
    source = _module(
        "source",
        role="source",
        technique_id="noise_source",
        outputs=[ModulePort(name="image", domain="TOP")],
    )
    output = _module(
        "output",
        role="output",
        technique_id="stable_output_null",
        inputs=[ModulePort(name="image", domain="TOP")],
        outputs=[ModulePort(name="image", domain="TOP")],
    )
    graph = ModuleGraph(
        target_root="/project1",
        modules=[source, output],
        edges=[
            ModuleEdge(
                source_module="source",
                source_port="image",
                target_module="output",
                target_port="image",
            )
        ],
        output_module_id="output",
    )
    assert graph.output_module_id == "output"

    with pytest.raises(ValidationError, match="unknown source port"):
        ModuleGraph(
            target_root="/project1",
            modules=[source, output],
            edges=[
                ModuleEdge(
                    source_module="source",
                    source_port="missing",
                    target_module="output",
                    target_port="image",
                )
            ],
            output_module_id="output",
        )


def test_mode_budgets_match_public_contract():
    assert budget_for_mode("fast").maximum_round_trips == 12
    assert budget_for_mode("production").maximum_round_trips == 20
    assert budget_for_mode("show_safe").maximum_round_trips == 26
    assert budget_for_mode("fast").maximum_repair_loops == 1
    assert budget_for_mode("production").maximum_repair_loops == 2


def test_show_safe_route_constraints_require_absolute_paths():
    constraints = BuildConstraints(
        active_output_path="/project1/generated/old",
        route_target_path="/project1/generated/active",
        route_target_input=1,
    )

    assert constraints.route_target_input == 1
    with pytest.raises(ValidationError):
        BuildConstraints(active_output_path="../foreign")
