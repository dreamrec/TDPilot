from __future__ import annotations

import pytest
from pydantic import ValidationError

from td_mcp.models.brain import (
    AssemblyMacro,
    BrainPattern,
    BrainPlan,
    CandidateConceptGraph,
    CompiledVisualTaskSpec,
    ConceptEdge,
    ConceptGraph,
    ConceptNode,
    GeneratedCodeBlock,
    OperatorAvailabilityMatrix,
    OperatorSubstitutionRule,
    ParamSemantics,
    ProfileValidationProbe,
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
        time_behavior=["beat_or_amplitude_modulation", "continuous_feedback"],
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
    assert compiled.time_behavior == ["beat_or_amplitude_modulation", "continuous_feedback"]
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


def test_brain_pattern_declares_ports_and_safety_contract():
    pattern = BrainPattern(
        pattern_id="audio_file_to_analysis_chop",
        title="Audio File To Analysis CHOP",
        intent_tags=["audio"],
        profiles=["audio_reactive"],
        required_ops=["audiofileinCHOP", "analyzeCHOP", "mathCHOP", "nullCHOP"],
        concept_nodes=[
            ConceptNode(
                id="audio_out",
                label="Audio out",
                role="output",
                domain="CHOP",
                op_type="nullCHOP",
            )
        ],
        concept_edges=[],
        exposes=[{"port_id": "analysis_chop", "domain": "CHOP", "node_id": "audio_out"}],
        consumes=[],
        safety="safe_live",
        validation_profile="structural_visual_safe",
        validation_probes=["audio_source_present", "analysis_stage", "range_mapping"],
        official_sources=["https://docs.derivative.ca/Audio_File_In_CHOP"],
    )

    assert pattern.exposes[0]["port_id"] == "analysis_chop"
    assert pattern.safety == "safe_live"


def test_brain_pattern_declares_required_addons_for_availability_scoring():
    pattern = BrainPattern(
        pattern_id="addon_pattern",
        title="Add-on Backed Pattern",
        intent_tags=["addon"],
        profiles=["pop"],
        required_ops=["nullPOP"],
        required_addons=["POPX"],
        concept_nodes=[
            ConceptNode(
                id="pop_out",
                label="POP output",
                role="output",
                domain="POP",
                op_type="nullPOP",
            )
        ],
        concept_edges=[],
        safety="safe_live",
        validation_profile="structural_visual_safe",
        validation_probes=["output_node_present"],
        official_sources=["https://docs.derivative.ca/Null_POP"],
    )

    assert pattern.required_addons == ["POPX"]


def test_brain_pattern_schema_rejects_invalid_port_and_debug_domains():
    base_pattern = {
        "pattern_id": "bad_domain_pattern",
        "title": "Bad Domain Pattern",
        "intent_tags": ["debug"],
        "profiles": ["concept_compiled"],
        "required_ops": ["nullTOP"],
        "concept_nodes": [
            ConceptNode(
                id="stable_output",
                label="Stable TOP output",
                role="output",
                domain="TOP",
                op_type="nullTOP",
            )
        ],
        "concept_edges": [],
        "validation_profile": "structural_visual_safe",
        "validation_probes": ["output_node_present"],
        "official_sources": ["https://docs.derivative.ca/Null_TOP"],
    }

    with pytest.raises(ValidationError, match="invalid pattern domain"):
        BrainPattern(
            **base_pattern,
            exposes=[{"port_id": "stable_top", "domain": "NOT_A_DOMAIN", "node_id": "stable_output"}],
        )

    with pytest.raises(ValidationError, match="invalid pattern domain"):
        BrainPattern(
            **base_pattern,
            consumes=[{"port_id": "analysis_chop", "domain": "NOT_A_DOMAIN"}],
        )

    with pytest.raises(ValidationError, match="invalid pattern domain"):
        BrainPattern(
            **base_pattern,
            debug_outputs=[{"node": "stable_output", "domain": "NOT_A_DOMAIN"}],
        )


def test_brain_pattern_schema_rejects_unknown_port_and_debug_node_references():
    base_pattern = {
        "pattern_id": "bad_reference_pattern",
        "title": "Bad Reference Pattern",
        "intent_tags": ["debug"],
        "profiles": ["concept_compiled"],
        "required_ops": ["nullTOP"],
        "concept_nodes": [
            ConceptNode(
                id="stable_output",
                label="Stable TOP output",
                role="output",
                domain="TOP",
                op_type="nullTOP",
            )
        ],
        "concept_edges": [],
        "validation_profile": "structural_visual_safe",
        "validation_probes": ["output_node_present"],
        "official_sources": ["https://docs.derivative.ca/Null_TOP"],
    }

    with pytest.raises(ValidationError, match="pattern exposes references unknown concept id"):
        BrainPattern(
            **base_pattern,
            exposes=[{"port_id": "stable_top", "domain": "TOP", "node_id": "missing_output"}],
        )

    with pytest.raises(ValidationError, match="pattern consumes references unknown concept id"):
        BrainPattern(
            **base_pattern,
            consumes=[{"port_id": "analysis_chop", "domain": "CHOP", "target_node_id": "missing_target"}],
        )

    with pytest.raises(ValidationError, match="pattern debug_outputs references unknown concept id"):
        BrainPattern(
            **base_pattern,
            debug_outputs=[{"node": "missing_debug", "domain": "TOP"}],
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


def test_operator_availability_matrix_and_substitution_rule_contracts():
    matrix = OperatorAvailabilityMatrix(
        td_build="2025.32820",
        platform="macOS",
        generated_at="2026-06-20T00:00:00+00:00",
        installed_addons=["POPX"],
        operators={
            "audiofileinCHOP": {"family": "CHOP", "available": False},
            "audiodeviceinCHOP": {"family": "CHOP", "available": True},
        },
        family_aliases={"CHOP": ["audiofileinCHOP", "audiodeviceinCHOP"]},
        unavailable_reasons={"audiofileinCHOP": "missing from live family list"},
    )
    rule = OperatorSubstitutionRule(
        missing_op="audiofileinCHOP",
        replacement_ops=["audiodeviceinCHOP"],
        replacement_pattern="audio_device_to_analysis_chop",
        confidence="medium",
        tradeoffs=["requires an available audio input device"],
        official_sources=[
            "https://docs.derivative.ca/Audio_File_In_CHOP",
            "https://docs.derivative.ca/Audio_Device_In_CHOP",
        ],
        requires_user_approval=True,
    )

    assert matrix.operators["audiofileinCHOP"]["available"] is False
    assert matrix.unavailable_reasons["audiofileinCHOP"] == "missing from live family list"
    assert rule.replacement_pattern == "audio_device_to_analysis_chop"

    with pytest.raises(ValidationError):
        OperatorSubstitutionRule(
            missing_op="audiofileinCHOP",
            replacement_ops=["audiodeviceinCHOP"],
            confidence="medium",
            official_sources=["https://example.com/not-official"],
        )


def test_operator_availability_matrix_rejects_inconsistent_operator_entries():
    base_matrix = {
        "td_build": "2025.32820",
        "platform": "macOS",
        "generated_at": "2026-06-20T00:00:00+00:00",
        "operators": {
            "audiofileinCHOP": {"family": "CHOP", "available": False},
            "audiodeviceinCHOP": {"family": "CHOP", "available": True},
        },
        "family_aliases": {"CHOP": ["audiofileinCHOP", "audiodeviceinCHOP"]},
        "unavailable_reasons": {"audiofileinCHOP": "missing from live family list"},
    }

    with pytest.raises(ValidationError, match="invalid operator family"):
        OperatorAvailabilityMatrix(
            **{
                **base_matrix,
                "operators": {"fakeThing": {"family": "NOPE", "available": False}},
                "family_aliases": {"NOPE": ["fakeThing"]},
                "unavailable_reasons": {"fakeThing": "missing from live family list"},
            }
        )

    with pytest.raises(ValidationError, match="operator availability must be boolean"):
        OperatorAvailabilityMatrix(
            **{
                **base_matrix,
                "operators": {"audiofileinCHOP": {"family": "CHOP", "available": "yes"}},
                "family_aliases": {"CHOP": ["audiofileinCHOP"]},
                "unavailable_reasons": {},
            }
        )

    with pytest.raises(ValidationError, match="unavailable operator requires a reason"):
        OperatorAvailabilityMatrix(
            **{
                **base_matrix,
                "unavailable_reasons": {},
            }
        )

    with pytest.raises(ValidationError, match="unavailable reason references available operator"):
        OperatorAvailabilityMatrix(
            **{
                **base_matrix,
                "unavailable_reasons": {
                    "audiofileinCHOP": "missing from live family list",
                    "audiodeviceinCHOP": "not actually unavailable",
                },
            }
        )

    with pytest.raises(ValidationError, match="family alias references unknown operator"):
        OperatorAvailabilityMatrix(
            **{
                **base_matrix,
                "family_aliases": {"CHOP": ["audiofileinCHOP", "missingCHOP"]},
            }
        )


def test_param_semantics_contracts_are_docs_grounded_and_narrow():
    semantics = ParamSemantics(
        op_type="levelTOP",
        name="opacity",
        label="Opacity",
        value_kind="float",
        valid_range=(0.0, 1.0),
        default_strategy="safe_feedback_decay",
        cook_risk="medium",
        validation_rule="bounded_feedback_decay",
        official_source="https://docs.derivative.ca/Level_TOP",
    )

    assert semantics.valid_range == (0.0, 1.0)

    with pytest.raises(ValidationError):
        ParamSemantics(
            op_type="levelTOP",
            name="opacity",
            label="Opacity",
            value_kind="float",
            valid_range=(1.0, 0.0),
            default_strategy="safe_feedback_decay",
            cook_risk="medium",
            official_source="https://docs.derivative.ca/Level_TOP",
        )

    with pytest.raises(ValidationError):
        ParamSemantics(
            op_type="levelTOP",
            name="opacity",
            label="Opacity",
            value_kind="float",
            default_strategy="safe_feedback_decay",
            cook_risk="medium",
            official_source="https://example.com/Level_TOP",
        )

    with pytest.raises(ValidationError):
        ParamSemantics(
            op_type="compositeTOP",
            name="operand",
            label="Composite Operation",
            value_kind="enum",
            default_strategy="keep_default",
            cook_risk="low",
            official_source="https://docs.derivative.ca/Composite_TOP",
        )


def test_profile_validation_probe_contract_is_cost_aware_and_docs_grounded():
    probe = ProfileValidationProbe(
        probe_id="feedback_cycle",
        profile="feedback",
        required_inputs=["feedbackTOP", "levelTOP", "nullTOP"],
        readback_strategy="static_graph",
        metric_names=["feedback_cycle_present", "decay_stage_present"],
        pass_conditions=["feedback path contains a decay stage before stable output"],
        cost_level="cheap",
        failure_message="Feedback networks must include a bounded feedback cycle.",
        official_sources=["https://docs.derivative.ca/Feedback_TOP"],
    )

    assert probe.cost_level == "cheap"
    assert probe.metric_names == ["feedback_cycle_present", "decay_stage_present"]

    with pytest.raises(ValidationError):
        ProfileValidationProbe(
            probe_id="bad_probe",
            profile="feedback",
            required_inputs=["feedbackTOP"],
            readback_strategy="static_graph",
            metric_names=["feedback_cycle_present"],
            pass_conditions=[],
            cost_level="cheap",
            failure_message="missing pass condition",
            official_sources=["https://docs.derivative.ca/Feedback_TOP"],
        )

    with pytest.raises(ValidationError):
        ProfileValidationProbe(
            probe_id="bad_source",
            profile="feedback",
            required_inputs=["feedbackTOP"],
            readback_strategy="static_graph",
            metric_names=["feedback_cycle_present"],
            pass_conditions=["feedback path exists"],
            cost_level="cheap",
            failure_message="bad source",
            official_sources=["https://example.com/Feedback_TOP"],
        )


def test_generated_code_block_contract_is_explicit_and_docs_grounded():
    block = GeneratedCodeBlock(
        block_id="pixel_shader",
        language="glsl",
        target_op="/project1/glsl",
        target_param="pixeldat",
        source_kind="generated",
        source_refs=["/project1/pixel_code"],
        code="layout(location = 0) out vec4 fragColor;\nvoid main(){ fragColor = TDOutputSwizzle(vec4(1.0)); }",
        static_checks=["glsl_no_version_line", "glsl_top_uses_td_output_swizzle"],
        runtime_checks=["compile_state"],
        expected_outputs=["/project1/out1"],
        risk_flags=["validate-glsl-compile-state"],
        official_sources=["https://docs.derivative.ca/GLSL_TOP"],
    )

    assert block.target_param == "pixeldat"
    assert block.language == "glsl"

    with pytest.raises(ValidationError, match="runtime check"):
        GeneratedCodeBlock(
            block_id="syntax_only_shader",
            language="glsl",
            target_op="/project1/glsl",
            target_param="pixeldat",
            source_kind="generated",
            source_refs=["/project1/pixel_code"],
            code="layout(location = 0) out vec4 fragColor;\nvoid main(){ fragColor = TDOutputSwizzle(vec4(1.0)); }",
            static_checks=["glsl_no_version_line", "glsl_top_uses_td_output_swizzle"],
            runtime_checks=[],
            expected_outputs=["/project1/out1"],
            risk_flags=["validate-glsl-compile-state"],
            official_sources=["https://docs.derivative.ca/GLSL_TOP"],
        )

    with pytest.raises(ValidationError, match="expected output"):
        GeneratedCodeBlock(
            block_id="outputless_shader",
            language="glsl",
            target_op="/project1/glsl",
            target_param="pixeldat",
            source_kind="generated",
            source_refs=["/project1/pixel_code"],
            code="layout(location = 0) out vec4 fragColor;\nvoid main(){ fragColor = TDOutputSwizzle(vec4(1.0)); }",
            static_checks=["glsl_no_version_line", "glsl_top_uses_td_output_swizzle"],
            runtime_checks=["compile_state"],
            expected_outputs=[],
            risk_flags=["validate-glsl-compile-state"],
            official_sources=["https://docs.derivative.ca/GLSL_TOP"],
        )

    with pytest.raises(ValidationError):
        GeneratedCodeBlock(
            block_id="bad_language",
            language="javascript",
            target_op="/project1/script",
            target_param="callbacks",
            source_kind="generated",
            source_refs=["/project1/script_callbacks"],
            code="function cook() {}",
            static_checks=["syntax"],
            runtime_checks=[],
            expected_outputs=[],
            risk_flags=[],
            official_sources=["https://docs.derivative.ca/Script_CHOP"],
        )


def test_assembly_macro_contract_is_docs_grounded_and_phase4_scoped():
    macro = AssemblyMacro(
        macro_id="add_named_outputs",
        label="Add Named Outputs",
        applies_to_profiles=["concept_compiled", "feedback"],
        layout_strategy="stable_output_contract",
        created_controls=[{"name": "feedback_decay", "target_param": "opacity"}],
        debug_nodes=[{"name": "debug_notes", "domain": "DAT"}],
        notes=["Stable output and debug taps preserve the assembled concept graph."],
        output_contract=["out1", "out_chop", "debug_notes"],
        validation_addons=["output_node_present", "cheap_visual_metrics"],
        official_sources=[
            "https://docs.derivative.ca/Component_Editor_Dialog",
            "https://docs.derivative.ca/Palette%3AsceneChanger",
        ],
    )

    assert macro.macro_id == "add_named_outputs"
    assert "concept_compiled" in macro.applies_to_profiles
    assert macro.output_contract == ["out1", "out_chop", "debug_notes"]

    with pytest.raises(ValidationError):
        AssemblyMacro(
            macro_id="bad_source",
            label="Bad Source",
            applies_to_profiles=["concept_compiled"],
            layout_strategy="group_by_domain",
            created_controls=[],
            debug_nodes=[],
            notes=["bad"],
            output_contract=["out1"],
            validation_addons=["output_node_present"],
            official_sources=["https://example.com/not-derivative"],
        )

    with pytest.raises(ValidationError):
        GeneratedCodeBlock(
            block_id="bad_source",
            language="python",
            target_op="/project1/script",
            target_param="callbacks",
            source_kind="generated",
            source_refs=["/project1/script_callbacks"],
            code="def cook(scriptOp):\n    return",
            static_checks=["python_syntax"],
            runtime_checks=[],
            expected_outputs=[],
            risk_flags=[],
            official_sources=["https://example.com/Script_CHOP"],
        )
