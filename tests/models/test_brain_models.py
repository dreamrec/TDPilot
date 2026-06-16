from __future__ import annotations

import pytest
from pydantic import ValidationError

from td_mcp.models.brain import (
    BrainPlan,
    ConceptEdge,
    ConceptGraph,
    ConceptNode,
    TransactionOptions,
    VisualTaskSpec,
)
from td_mcp.models.patch import PatchPlan, ValidationPlan


def test_concept_graph_rejects_dangling_edges():
    task = VisualTaskSpec(intent="build a feedback loop")
    with pytest.raises(ValidationError) as exc:
        ConceptGraph(
            task=task,
            profile="feedback",
            concepts=[ConceptNode(id="source", label="Noise", role="source", domain="TOP")],
            edges=[ConceptEdge(source="source", target="missing", kind="data")],
        )

    assert "unknown concept id" in str(exc.value)


def test_transaction_options_defaults_are_safe():
    opts = TransactionOptions()

    assert opts.preflight is True
    assert opts.snapshot_before is True
    assert opts.rollback_on_apply_failure is True
    assert opts.rollback_on_validation_failure is True
    assert opts.dry_run is False
    assert opts.max_ops == 80
    assert opts.validation_profile == "structural_visual_safe"


def test_brain_plan_wraps_existing_patch_plan_without_changing_patch_contract():
    task = VisualTaskSpec(intent="build feedback", target_root="/project1")
    graph = ConceptGraph(
        task=task,
        profile="feedback",
        concepts=[ConceptNode(id="out", label="Output", role="output", domain="TOP", op_type="nullTOP")],
    )
    patch = PatchPlan(
        target_root="/project1",
        source="operations",
        operations=[],
        required_ops=["nullTOP"],
        risk_flags=[],
        undo_label="td brain: build feedback",
        validation_plan=ValidationPlan(target_root="/project1", capture_frames=[]),
    )

    plan = BrainPlan(task=task, concept_graph=graph, patch_plan=patch)

    dumped = plan.model_dump(mode="json")
    assert dumped["source"] == "brain"
    assert dumped["patch_plan"]["source"] == "operations"
    assert dumped["validation_profile"] == "structural_visual_safe"
