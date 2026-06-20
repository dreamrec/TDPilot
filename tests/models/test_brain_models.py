from __future__ import annotations

import pytest
from pydantic import ValidationError

from td_mcp.models.brain import (
    BrainPattern,
    BrainPlan,
    CandidateConceptGraph,
    CompiledVisualTaskSpec,
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


def test_phase_one_compiler_models_validate_narrow_contracts():
    compiled = CompiledVisualTaskSpec(
        intent="Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        domains=["CHOP", "TOP", "COMP"],
        motifs=["audio-reactive", "feedback", "control-panel", "debug-output"],
        inputs=[{"kind": "audio", "domain": "CHOP"}],
        outputs=[
            {"kind": "stable_output", "domain": "TOP"},
            {"kind": "debug_output", "domain": "DAT"},
        ],
        required_capabilities=["audio_analysis", "feedback_loop", "panel_controls", "debug_output"],
        candidate_profiles=["audio_reactive", "feedback", "panel_ui"],
        candidate_operator_families=["CHOP", "TOP", "COMP", "DAT"],
        validation_needs=["audio_source_present", "feedback_cycle", "panel_state_reader"],
        grounding_evidence=["docs:audiofileinCHOP", "docs:feedbackTOP", "docs:panelCHOP"],
    )
    concepts = [
        ConceptNode(
            id="audio_out", label="Audio control output", role="output", domain="CHOP", op_type="nullCHOP"
        ),
        ConceptNode(
            id="feedback_decay", label="Feedback decay", role="process", domain="TOP", op_type="levelTOP"
        ),
    ]

    candidate = CandidateConceptGraph(
        compiled_task_id=compiled.id,
        label="Audio-reactive feedback with panel controls",
        profiles=["audio_reactive", "feedback", "panel_ui"],
        pattern_ids=["audio_analysis_chop_chain", "feedback_top_loop", "panel_control_output"],
        concepts=concepts,
        edges=[ConceptEdge(source="audio_out", target="feedback_decay", kind="control")],
        required_ops=["audiofileinCHOP", "analyzeCHOP", "feedbackTOP", "levelTOP", "panelCHOP", "nullTOP"],
        expected_outputs=["/project1/out1"],
        validation_needs=["audio_source_present", "feedback_cycle", "panel_state_reader"],
        grounding_evidence=["docs:audiofileinCHOP", "docs:feedbackTOP", "docs:panelCHOP"],
        score=0.9,
        explanation="Composes audio analysis, feedback, and panel control patterns.",
    )

    assert candidate.compiled_task_id == compiled.id
    assert candidate.profiles == ["audio_reactive", "feedback", "panel_ui"]
    assert candidate.pattern_ids == ["audio_analysis_chop_chain", "feedback_top_loop", "panel_control_output"]


def test_brain_pattern_schema_rejects_ungrounded_or_empty_patterns():
    with pytest.raises(ValidationError):
        BrainPattern(
            pattern_id="bad",
            title="Bad Pattern",
            intent_tags=["bad"],
            profiles=["feedback"],
            required_ops=[],
            concept_nodes=[],
            concept_edges=[],
            validation_profile="structural_visual_safe",
            validation_probes=["feedback_cycle"],
            official_sources=["https://example.com/not-official"],
        )


def test_brain_pattern_schema_rejects_unknown_validation_probes():
    with pytest.raises(ValidationError):
        BrainPattern(
            pattern_id="bad_probe",
            title="Bad Probe Pattern",
            intent_tags=["bad"],
            profiles=["feedback"],
            required_ops=["feedbackTOP"],
            concept_nodes=[],
            concept_edges=[],
            validation_profile="structural_visual_safe",
            validation_probes=["totally_invented_probe"],
            official_sources=["https://docs.derivative.ca/Feedback_TOP"],
        )
