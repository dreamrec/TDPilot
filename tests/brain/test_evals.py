from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from td_mcp.brain import evals
from td_mcp.brain.evals import (
    evaluate_case,
    evaluate_golden_cases,
    load_golden_cases,
)

ROOT = Path(__file__).resolve().parent.parent.parent
EVAL_PATH = ROOT / "tests" / "evals" / "td_brain_golden.jsonl"


def test_load_golden_cases_preserves_ids_and_expected_ops():
    cases = load_golden_cases(EVAL_PATH)

    assert {case["id"] for case in cases} >= {
        "feedback_loop_basic",
        "audio_feedback_panel_debug",
        "glsl_top_shader",
        "glsl_material_shader",
        "glsl_pop_attribute_shader",
    }
    assert all(case.get("expected_ops") or case.get("expected_blocked") is True for case in cases)


def test_golden_eval_corpus_meets_phase_one_breadth_target():
    cases = load_golden_cases(EVAL_PATH)
    ids = {case["id"] for case in cases}

    assert len(cases) >= 20
    assert {
        "audio_feedback_panel_debug",
        "audio_feedback_panel_live_source",
        "audio_feedback_panel_diagnostics",
        "audio_glsl_material_render",
        "audio_glsl_material_render_panel",
        "audio_terrain_glass_controls",
        "audio_glsl_material_surface",
        "render_pipeline_basic",
        "panel_ui_controls",
        "midi_control_bridge",
        "serial_dat_protocol_bridge",
        "mqtt_dat_protocol_bridge",
        "udp_dat_protocol_bridge",
        "dat_execute_table_change_callback",
        "dat_table_render_switch",
        "ndi_post_fx_output",
        "pop_particle_preview_sparse",
        "glsl_top_shader_compiled",
        "glsl_advanced_pop_topology",
        "glsl_fragment_texture_effect",
        "panel_button_slider_controls",
    }.issubset(ids)


def test_golden_eval_corpus_meets_phase_four_breadth_floor():
    cases = load_golden_cases(EVAL_PATH)

    assert len(cases) >= 50


def test_golden_eval_corpus_covers_messy_project_inputs():
    cases = load_golden_cases(EVAL_PATH)

    assert any(case.get("existing_nodes") for case in cases)
    assert any(case.get("expected_blocked") is True for case in cases)
    assert any(case.get("forbidden_ops") for case in cases)
    assert any(
        isinstance(case.get("constraints"), dict)
        and isinstance(case["constraints"].get("availability_report"), dict)
        for case in cases
    )


def test_golden_eval_corpus_covers_master_plan_seed_patterns():
    cases = load_golden_cases(EVAL_PATH)
    covered_patterns = {
        pattern_id
        for case in cases
        for pattern_id in [
            *case.get("covers_patterns", []),
            *case.get("expected_patterns", []),
        ]
    }

    assert {
        "audio_file_to_analysis_chop",
        "audio_device_to_analysis_chop",
        "feedback_decay_top_loop",
        "pop_particle_field_preview",
        "glsl_top_shader_with_text_dat",
        "glsl_advanced_pop_topology_shader",
        "glsl_material_render_pipeline",
        "render_geo_camera_light_output",
        "panel_controls_to_chop_output",
        "dat_execute_table_change_callback",
        "serial_dat_protocol_bridge",
        "osc_in_dat_protocol_bridge",
        "websocket_dat_protocol_bridge",
        "mqtt_client_dat_protocol_bridge",
        "udp_in_dat_protocol_bridge",
        "dat_table_render_switch_top",
        "midi_in_to_control_chop",
        "ndi_in_to_post_fx_output",
    }.issubset(covered_patterns)


def test_golden_eval_corpus_uses_validation_expectations_for_showpiece_cases():
    cases = load_golden_cases(EVAL_PATH)
    by_id = {case["id"]: case for case in cases}

    material = by_id["audio_glsl_material_render"]

    assert {"analysis_stage", "camera_present", "material_assigned"}.issubset(
        set(material["validation_expectations"])
    )
    assert material["scoring"]["validation_expectations"] >= 1


def test_golden_eval_corpus_locks_dynamic_atlas_evidence_for_preview_and_binding():
    cases = load_golden_cases(EVAL_PATH)
    by_id = {case["id"]: case for case in cases}

    chop_binding = by_id["open_prompt_chop_binding_texture_synthesis"]
    sop_preview = by_id["open_prompt_sop_render_preview_top_synthesis"]
    typed_sop_preview = by_id["open_prompt_typed_role_sop_render_output_synthesis"]
    typed_bridge = by_id["open_prompt_typed_bridge_dat_to_chop_output"]
    typed_chop_top_bridge = by_id["open_prompt_typed_bridge_chop_to_top_source_output"]
    typed_dat_chop_top_bridge = by_id["open_prompt_typed_bridge_dat_to_chop_to_top_output"]
    typed_dat_pop_top_chop_bridge = by_id["open_prompt_typed_bridge_dat_to_pop_to_top_to_chop_output"]
    typed_sop_pop_top_bridge = by_id["open_prompt_typed_bridge_sop_to_pop_to_top_preview"]
    messy_sop_preview = by_id["open_prompt_typed_role_sop_render_preview_top_with_bridge_distractors"]
    sop_role_search = by_id["open_prompt_sop_role_graph_noise_over_transform_distractor"]
    messy_chop_sop_export = by_id["open_prompt_chop_export_bound_sop_preview_with_transform_distractor"]
    messy_chop_export = by_id["open_prompt_chop_export_binding_with_bridge_distractor"]

    assert "atlas:synthesized:chop_controlled_top_card_chain" in chop_binding["required_patterns"]
    assert (
        "atlas-synthesis:binding:out_chop->levelTOP.brightness1"
        in chop_binding["required_grounding_evidence"]
    )
    assert "atlas:synthesized:sop_render_preview_top_card_chain" in sop_preview["required_patterns"]
    assert (
        "atlas-synthesis:multi-domain:sop-to-render-top-preview" in sop_preview["required_grounding_evidence"]
    )
    assert (
        "atlas:synthesized:typed_role_graph_sop_render_preview_top_card_chain"
        in typed_sop_preview["required_patterns"]
    )
    assert (
        "atlas-synthesis:role-graph:source->preview->output"
        in typed_sop_preview["required_grounding_evidence"]
    )
    assert "atlas:synthesized:typed_bridge_graph_dat_to_chop_card_chain" in typed_bridge["required_patterns"]
    assert "atlas-synthesis:typed-role-graph-search" in typed_bridge["required_grounding_evidence"]
    assert "atlas-synthesis:bridge:DAT->CHOP:dattoCHOP" in typed_bridge["required_grounding_evidence"]
    assert (
        "atlas:synthesized:typed_bridge_graph_chop_to_top_card_chain"
        in typed_chop_top_bridge["required_patterns"]
    )
    assert (
        "atlas-synthesis:source-output-before-bridge:nullCHOP"
        in typed_chop_top_bridge["required_grounding_evidence"]
    )
    assert (
        "atlas:synthesized:typed_bridge_graph_dat_to_chop_to_top_card_chain"
        in typed_dat_chop_top_bridge["required_patterns"]
    )
    assert (
        "atlas-synthesis:typed-bridge-graph-search:multi-hop"
        in typed_dat_chop_top_bridge["required_grounding_evidence"]
    )
    assert (
        "atlas:synthesized:typed_bridge_graph_dat_to_pop_to_top_to_chop_card_chain"
        in (typed_dat_pop_top_chop_bridge["required_patterns"])
    )
    assert (
        "atlas-synthesis:bridge:TOP->CHOP:toptoCHOP"
        in typed_dat_pop_top_chop_bridge["required_grounding_evidence"]
    )
    assert (
        "atlas-synthesis:role-graph:"
        "source->bridge->process->output->bridge->process->output->bridge->process->output"
    ) in typed_dat_pop_top_chop_bridge["required_grounding_evidence"]
    assert (
        "atlas:synthesized:typed_bridge_graph_sop_to_pop_to_top_card_chain"
        in (typed_sop_pop_top_bridge["required_patterns"])
    )
    assert (
        "atlas-synthesis:bridge:SOP->POP:soptoPOP" in typed_sop_pop_top_bridge["required_grounding_evidence"]
    )
    assert (
        "atlas-synthesis:bridge:POP->TOP:poptoTOP" in typed_sop_pop_top_bridge["required_grounding_evidence"]
    )
    assert (
        "atlas-synthesis:topology-selected:1:atlas:synthesized:sop_render_preview_top_card_chain"
        in (messy_sop_preview["required_grounding_evidence"])
    )
    assert (
        "atlas-synthesis:topology-role-family:1:source:SOP:3"
        in (messy_sop_preview["required_grounding_evidence"])
    )
    assert "transformSOP" in sop_role_search["forbidden_ops"]
    assert (
        "atlas-synthesis:role-graph-search:SOP:source->process->output"
        in (sop_role_search["required_grounding_evidence"])
    )
    assert (
        "atlas-synthesis:role-graph-selected:SOP:1:gridSOP>noiseSOP>nullSOP"
        in (sop_role_search["required_grounding_evidence"])
    )
    assert (
        "atlas-synthesis:role-node:SOP:process:noiseSOP" in (sop_role_search["required_grounding_evidence"])
    )
    assert "transformSOP" in messy_chop_sop_export["forbidden_ops"]
    assert (
        "atlas:synthesized:chop_export_bound_sop_render_preview_card_chain"
        in (messy_chop_sop_export["required_patterns"])
    )
    assert (
        "atlas-synthesis:sop-control-target-selected:noiseSOP.amp"
        in (messy_chop_sop_export["required_grounding_evidence"])
    )
    assert (
        "atlas-synthesis:role-graph-selected:SOP:1:gridSOP>noiseSOP>nullSOP"
        in (messy_chop_sop_export["required_grounding_evidence"])
    )
    assert (
        "atlas-synthesis:topology-selected:1:atlas:synthesized:chop_export_bound_top_card_chain"
        in (messy_chop_export["required_grounding_evidence"])
    )
    assert (
        "atlas-synthesis:topology-role-family:1:control:CHOP:1"
        in (messy_chop_export["required_grounding_evidence"])
    )


def test_golden_eval_report_includes_registry_pattern_coverage():
    assert hasattr(evals, "pattern_eval_coverage_report")

    cases = load_golden_cases(EVAL_PATH)
    coverage = evals.pattern_eval_coverage_report(cases)

    assert coverage["ok"] is True
    assert coverage["pattern_count"] == 23
    assert coverage["covered_pattern_count"] == coverage["pattern_count"]
    assert coverage["missing_patterns"] == []
    assert coverage["stale_pattern_references"] == []
    assert coverage["source_checked_pattern_count"] == coverage["pattern_count"]
    assert coverage["invalid_source_count"] == 0
    assert coverage["invalid_sources"] == []
    assert "audio_feedback_panel_debug" in coverage["coverage_by_pattern"]["debug_output_conventions"]
    assert "audio_terrain_glass_controls" in coverage["coverage_by_pattern"]["sop_noise_terrain_surface"]


@pytest.mark.asyncio
async def test_evaluate_golden_cases_scores_all_current_profiles():
    report = await evaluate_golden_cases(EVAL_PATH)

    assert report["ok"] is True
    assert report["pattern_coverage"]["ok"] is True
    assert report["assembly_control_bindings"]["ok"] is True
    assert report["assembly_control_bindings"]["missing"] == []
    assert report["param_semantics_coverage"]["ok"] is True
    assert report["param_semantics_coverage"]["missing_operator_count"] == 0
    assert report["operator_availability_coverage"]["ok"] is True
    assert report["operator_availability_coverage"]["missing_required_rule_count"] == 0
    assert report["availability_matrix_metrics"]["ok"] is True
    assert report["availability_matrix_metrics"]["structured_case_count"] >= 1
    assert report["availability_matrix_metrics"]["known_build_case_count"] >= 1
    assert report["availability_matrix_metrics"]["missing_unavailable_reason_count"] == 0
    assert report["availability_matrix_metrics"]["substitution_without_matrix_count"] == 0
    assert (
        "audio_feedback_panel_device_substitution"
        in report["availability_matrix_metrics"]["structured_case_ids"]
    )
    assert report["validation_probe_coverage"]["ok"] is True
    assert report["validation_probe_coverage"]["missing_required_profile_count"] == 0
    assert report["generated_code_harness_coverage"]["ok"] is True
    assert report["generated_code_harness_coverage"]["missing_static_check_count"] == 0
    assert report["generated_code_harness_coverage"]["missing_runtime_check_count"] == 0
    assert report["trace_promotion_coverage"]["ok"] is True
    assert report["trace_promotion_coverage"]["eligible_trace_fixture_count"] >= 2
    assert report["trace_promotion_coverage"]["blocked_fixture_count"] == 0
    assert "audio_feedback_panel_debug" in report["trace_promotion_coverage"]["promoted_case_ids"]
    assert "glsl_top_shader_compiled" in report["trace_promotion_coverage"]["promoted_case_ids"]
    # Honesty marker: the runtime evidence behind this report is synthetic, not a
    # live-TD readback, so a green trace_promotion_coverage is plumbing proof only.
    assert report["trace_promotion_coverage"]["runtime_evidence_source"] == "synthetic_fixture"
    assert report["trace_memory_reuse_coverage"]["ok"] is True
    assert report["trace_memory_reuse_coverage"]["fixture_count"] >= 2
    assert report["trace_memory_reuse_coverage"]["loaded_pattern_count"] >= 2
    assert report["trace_memory_reuse_coverage"]["reused_fixture_count"] >= 2
    assert report["trace_memory_reuse_coverage"]["miss_count"] == 0
    assert "audio_feedback_panel_debug" in report["trace_memory_reuse_coverage"]["reused_case_ids"]
    assert "glsl_top_shader_compiled" in report["trace_memory_reuse_coverage"]["reused_case_ids"]
    assert report["case_count"] >= 8
    assert report["passed"] == report["case_count"]
    assert all(item["passed"] for item in report["cases"])
    assert all(
        "concept_correctness" in item["checks"]
        for item in report["cases"]
        if item.get("expected_blocked") is not True
    )
    audio_case = next(item for item in report["cases"] if item["id"] == "audio_feedback_panel_debug")
    assert audio_case["checks"]["assembly_macros"]["ok"] is True
    assert set(audio_case["assembly_macros"]) >= {
        "make_component_shell",
        "group_by_domain",
        "add_named_outputs",
        "add_debug_panel",
        "add_user_controls",
        "annotate_operator_chain",
    }
    material_case = next(item for item in report["cases"] if item["id"] == "audio_glsl_material_render")
    assert material_case["profile"] == "concept_compiled"
    assert material_case["checks"]["pattern_composition"]["ok"] is True
    assert {"CHOP", "TOP", "COMP", "DAT", "MAT"}.issubset(set(material_case["compiled_domains"]))
    assert {
        "audio_analysis_chop_chain",
        "glsl_material_render_pipeline",
        "debug_output_conventions",
    }.issubset(set(material_case["candidate_patterns"]))
    material_panel_case = next(
        item for item in report["cases"] if item["id"] == "audio_glsl_material_render_panel"
    )
    assert material_panel_case["profile"] == "concept_compiled"
    assert material_panel_case["checks"]["pattern_composition"]["ok"] is True
    assert material_panel_case["checks"]["assembly_macros"]["ok"] is True
    assert {"CHOP", "TOP", "COMP", "DAT", "MAT"}.issubset(set(material_panel_case["compiled_domains"]))
    assert {
        "audio_analysis_chop_chain",
        "glsl_material_render_pipeline",
        "panel_control_output",
        "debug_output_conventions",
    }.issubset(set(material_panel_case["candidate_patterns"]))
    terrain_case = next(item for item in report["cases"] if item["id"] == "audio_terrain_glass_controls")
    assert terrain_case["profile"] == "concept_compiled"
    assert terrain_case["checks"]["pattern_composition"]["ok"] is True
    assert {"CHOP", "TOP", "COMP", "DAT", "SOP", "MAT"}.issubset(set(terrain_case["compiled_domains"]))
    assert {
        "audio_analysis_chop_chain",
        "sop_noise_terrain_surface",
        "glsl_material_render_pipeline",
        "panel_control_output",
        "debug_output_conventions",
    }.issubset(set(terrain_case["candidate_patterns"]))
    glsl_top_case = next(item for item in report["cases"] if item["id"] == "glsl_top_shader_compiled")
    assert glsl_top_case["profile"] == "concept_compiled"
    assert glsl_top_case["checks"]["pattern_composition"]["ok"] is True
    assert {"TOP", "DAT"}.issubset(set(glsl_top_case["compiled_domains"]))
    assert {
        "glsl_top_shader_with_text_dat",
        "debug_output_conventions",
    }.issubset(set(glsl_top_case["candidate_patterns"]))
    midi_case = next(item for item in report["cases"] if item["id"] == "midi_control_bridge")
    assert "device-source-declared:midi_device" in midi_case["grounding_evidence"]
    render_switch_case = next(item for item in report["cases"] if item["id"] == "dat_table_render_switch")
    assert render_switch_case["profile"] == "concept_compiled"
    assert render_switch_case["checks"]["pattern_composition"]["ok"] is True
    assert {"TOP", "DAT"}.issubset(set(render_switch_case["compiled_domains"]))
    assert "dat_table_render_switch_top" in render_switch_case["candidate_patterns"]


@pytest.mark.asyncio
async def test_evaluate_case_expected_blocked_vague_prompt_passes_safely():
    result = await evaluate_case(
        {
            "id": "vague_prompt_make_it_cool",
            "intent": "make it cool",
            "target_root": "/project1",
            "expected_profile": "generic",
            "expected_ops": [],
            "validation_profile": "structural_visual_safe",
            "expected_blocked": True,
        }
    )

    assert result.get("expected_blocked") is True
    assert result["passed"] is True
    assert result["operation_count"] == 0
    assert result["validation_metrics"]["blocked_question_count"] > 0
    assert result["checks"]["expected_blocked_safety"]["ok"] is True


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_prompt_safety_metrics_for_expected_blocked_cases():
    report = await evaluate_golden_cases(EVAL_PATH)

    assert report["prompt_safety_metrics"]["ok"] is True
    assert report["prompt_safety_metrics"]["expected_blocked_case_count"] >= 1
    assert (
        report["prompt_safety_metrics"]["passed_expected_blocked_case_count"]
        == report["prompt_safety_metrics"]["expected_blocked_case_count"]
    )
    assert report["prompt_safety_metrics"]["failed_expected_blocked_case_ids"] == []


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_messy_project_metrics():
    report = await evaluate_golden_cases(EVAL_PATH)

    metrics = report["messy_project_metrics"]

    assert metrics["ok"] is True
    assert metrics["existing_state_case_count"] >= 1
    assert metrics["name_conflict_case_count"] >= 1
    assert metrics["name_conflict_failure_count"] == 0
    assert metrics["availability_pressure_case_count"] >= 1
    assert metrics["unsupported_operator_case_count"] >= 1
    assert metrics["ambiguous_blocked_case_count"] >= 1


@pytest.mark.asyncio
async def test_trace_memory_reuse_report_replays_promoted_patterns_from_local_trace():
    assert hasattr(evals, "trace_memory_reuse_coverage_report")

    cases = load_golden_cases(EVAL_PATH)
    report = await evals.trace_memory_reuse_coverage_report(cases)

    assert report["ok"] is True
    assert report["fixture_count"] >= 2
    assert report["loaded_pattern_count"] >= 2
    assert report["reused_fixture_count"] >= 2
    assert report["miss_count"] == 0
    assert "audio_feedback_panel_debug" in report["reused_case_ids"]
    assert "glsl_top_shader_compiled" in report["reused_case_ids"]
    for case_id in {"audio_feedback_panel_debug", "glsl_top_shader_compiled"}:
        reused = next(item for item in report["reused_fixtures"] if item["case_id"] == case_id)
        assert reused["selected_pattern_ids"] == [reused["promoted_pattern_id"]]
        assert reused["trace_promoted_evidence"] is True


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_aggregate_time_metrics():
    report = await evaluate_golden_cases(EVAL_PATH)

    assert set(report["time_metrics"]) == {
        "total_ms",
        "avg_case_total_ms",
        "time_to_first_green_cycles",
    }
    assert report["time_metrics"]["total_ms"] >= 0
    assert report["time_metrics"]["avg_case_total_ms"] >= 0


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_master_plan_phase_coverage():
    report = await evaluate_golden_cases(EVAL_PATH)

    coverage = report["delivery_phase_coverage"]
    phases = {phase["phase_id"]: phase for phase in coverage["phases"]}

    assert coverage["ok"] is True
    assert coverage["scope"] == "brain_eval_phased_delivery_mvp"
    assert coverage["phase_count"] == 4
    assert coverage["complete_phase_count"] == 4
    assert coverage["incomplete_phase_count"] == 0
    assert set(phases) == {"phase_1", "phase_2", "phase_3", "phase_4"}

    assert phases["phase_1"]["evidence"]["eval_case_count"] >= 20
    assert phases["phase_1"]["evidence"]["pattern_count"] >= 8
    assert phases["phase_1"]["evidence"]["compiled_case_count"] >= 1
    assert phases["phase_2"]["evidence"]["param_semantics_priority_operator_count"] >= 40
    assert phases["phase_2"]["evidence"]["availability_matrix_known_build_case_count"] >= 1
    assert phases["phase_3"]["evidence"]["validation_required_profile_count"] >= 8
    assert phases["phase_3"]["evidence"]["generated_code_case_count"] >= 1
    assert phases["phase_4"]["evidence"]["eval_case_count"] >= 50
    assert phases["phase_4"]["evidence"]["assembled_showpiece_case_count"] >= 10
    assert report["time_metrics"]["time_to_first_green_cycles"] == {
        "min": 1,
        "max": 1,
        "avg": 1.0,
    }


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_aggregate_validation_strength_metrics():
    report = await evaluate_golden_cases(EVAL_PATH)

    metrics = report["validation_metrics"]
    normal_case_count = sum(1 for item in report["cases"] if item.get("expected_blocked") is not True)

    assert metrics["ok"] is True
    assert metrics["case_count"] == normal_case_count
    assert metrics["min_validation_check_count"] >= 6
    assert metrics["weak_validation_case_count"] == 0
    assert metrics["missing_validation_expectation_count"] == 0
    assert metrics["weak_validation_case_ids"] == []
    assert metrics["missing_validation_expectation_case_ids"] == []


@pytest.mark.asyncio
async def test_evaluate_case_scores_expected_compiled_time_behavior():
    result = await evaluate_case(
        {
            "id": "time_behavior_probe",
            "intent": "Build an audio-reactive feedback visual with a control panel and debug output",
            "target_root": "/project1",
            "expected_profile": "concept_compiled",
            "expected_ops": [
                "audiofileinCHOP",
                "analyzeCHOP",
                "mathCHOP",
                "nullCHOP",
                "noiseTOP",
                "feedbackTOP",
                "levelTOP",
                "compositeTOP",
                "nullTOP",
                "baseCOMP",
                "containerCOMP",
                "sliderCOMP",
                "buttonCOMP",
                "panelCHOP",
                "textDAT",
                "annotateCOMP",
                "infoCHOP",
                "errorDAT",
            ],
            "expected_time_behavior": [
                "beat_or_amplitude_modulation",
                "continuous_feedback",
                "event_driven_control",
            ],
            "validation_profile": "structural_visual_safe",
        }
    )

    assert result["checks"]["time_behavior"]["ok"] is True
    assert result["compiled_time_behavior"] == [
        "beat_or_amplitude_modulation",
        "continuous_feedback",
        "event_driven_control",
    ]
    assert result["decomposition_metrics"]["compiled_time_behavior_count"] == 3


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_time_behavior_decomposition_coverage():
    report = await evaluate_golden_cases(EVAL_PATH)

    metrics = report["decomposition_accuracy_metrics"]

    assert metrics["time_behavior_checked_case_count"] >= 1
    assert metrics["time_behavior_failure_count"] == 0
    assert "audio_feedback_panel_debug" in metrics["time_behavior_checked_case_ids"]


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_parameter_safety_metrics():
    report = await evaluate_golden_cases(EVAL_PATH)

    metrics = report["parameter_safety_metrics"]

    assert metrics["ok"] is True
    assert metrics["covered_operator_count"] >= 40
    assert metrics["priority_operator_count"] >= 40
    assert metrics["missing_operator_count"] == 0
    assert metrics["invalid_source_count"] == 0
    assert metrics["priority_group_count"] >= 7
    assert metrics["priority_group_missing_operator_count"] == 0
    assert "audio_control" in metrics["priority_groups"]


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_aggregate_readability_metrics():
    report = await evaluate_golden_cases(EVAL_PATH)
    assembled_cases = [case for case in report["cases"] if case["assembly_macros"]]

    assert report["readability_metrics"]["ok"] is True
    assert report["readability_metrics"]["assembled_case_count"] == len(assembled_cases)
    assert report["readability_metrics"]["fully_readable_assembled_case_count"] == len(assembled_cases)
    assert report["readability_metrics"]["avg_assembled_score"] == 5.0
    assert report["readability_metrics"]["avg_assembled_max_score"] == 5.0
    assert report["readability_metrics"]["not_fully_readable_assembled_case_ids"] == []


def test_aggregate_readability_metrics_reports_unreadable_assembled_cases():
    metrics = evals._aggregate_readability_metrics(
        [
            {
                "id": "readable_case",
                "assembly_macros": ["make_component_shell"],
                "readability_metrics": {"score": 5, "max_score": 5},
            },
            {
                "id": "missing_debug_surface",
                "assembly_macros": ["make_component_shell"],
                "readability_metrics": {"score": 4, "max_score": 5},
            },
        ]
    )

    assert metrics["ok"] is False
    assert metrics["assembled_case_count"] == 2
    assert metrics["fully_readable_assembled_case_count"] == 1
    assert metrics["not_fully_readable_assembled_case_ids"] == ["missing_debug_surface"]


@pytest.mark.asyncio
async def test_evaluate_golden_cases_ok_includes_readability_metrics(monkeypatch):
    original = evals._aggregate_readability_metrics

    def regressed(results):
        metrics = original(results)
        return {
            **metrics,
            "ok": False,
            "not_fully_readable_assembled_case_ids": ["audio_feedback_panel_debug"],
        }

    monkeypatch.setattr(evals, "_aggregate_readability_metrics", regressed)

    report = await evaluate_golden_cases(EVAL_PATH)

    assert report["ok"] is False


@pytest.mark.asyncio
async def test_evaluate_golden_cases_ok_includes_showpiece_assembly_metrics(monkeypatch):
    original = evals._aggregate_showpiece_assembly_metrics

    def regressed(results):
        metrics = original(results)
        return {
            **metrics,
            "ok": False,
            "not_fully_readable_showpiece_case_ids": ["audio_feedback_panel_debug"],
        }

    monkeypatch.setattr(evals, "_aggregate_showpiece_assembly_metrics", regressed)

    report = await evaluate_golden_cases(EVAL_PATH)

    assert report["ok"] is False


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_showpiece_assembly_metrics():
    report = await evaluate_golden_cases(EVAL_PATH)

    metrics = report["showpiece_assembly_metrics"]

    assert metrics["ok"] is True
    assert metrics["showpiece_case_count"] >= 10
    assert metrics["assembled_showpiece_case_count"] == metrics["showpiece_case_count"]
    assert metrics["fully_readable_showpiece_case_count"] == metrics["showpiece_case_count"]
    assert metrics["unassembled_showpiece_case_ids"] == []
    assert metrics["not_fully_readable_showpiece_case_ids"] == []
    assert "audio_feedback_panel_debug" in metrics["showpiece_case_ids"]


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_runtime_safety_metrics():
    report = await evaluate_golden_cases(EVAL_PATH)

    safety = report["runtime_safety_metrics"]
    normal_case_count = sum(1 for item in report["cases"] if item.get("expected_blocked") is not True)

    assert safety["ok"] is True
    assert safety["case_count"] == normal_case_count
    assert safety["checked_forbidden_operator_case_count"] >= 1
    assert "audio_feedback_panel_live_source" in safety["checked_forbidden_operator_case_ids"]
    assert safety["blocked_case_count"] == 0
    assert safety["missing_fact_case_count"] == 0
    assert safety["forbidden_operator_case_count"] == 0
    assert safety["rollback_behavior_failure_count"] == 0
    assert safety["final_state_quality_failure_count"] == 0
    assert safety["operator_set_failure_count"] == 0
    assert safety["max_plan_ops_failure_count"] == 0


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_rollback_frequency_metrics():
    report = await evaluate_golden_cases(EVAL_PATH)

    metrics = report["rollback_frequency_metrics"]
    normal_case_count = sum(1 for item in report["cases"] if item.get("expected_blocked") is not True)

    assert metrics["ok"] is True
    assert metrics["case_count"] == normal_case_count
    assert metrics["rollback_enabled_case_count"] == normal_case_count
    assert metrics["rollback_behavior_failure_count"] == 0
    assert metrics["rollback_required_case_count"] == 0
    assert metrics["rollback_performed_count"] == 0
    assert metrics["rollback_frequency"] == 0.0
    assert metrics["rollback_behavior_failure_case_ids"] == []
    assert "audio_feedback_panel_debug" in metrics["rollback_enabled_case_ids"]


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_unsupported_operator_avoidance_metrics():
    report = await evaluate_golden_cases(EVAL_PATH)

    metrics = report["unsupported_operator_avoidance_metrics"]

    assert metrics["ok"] is True
    assert metrics["checked_forbidden_operator_case_count"] >= 1
    assert metrics["forbidden_operator_case_count"] == 0
    assert metrics["forbidden_operator_case_ids"] == []
    assert metrics["forbidden_ops_present"] == []
    assert "audio_feedback_panel_live_source" in metrics["checked_forbidden_operator_case_ids"]


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_required_operator_coverage_metrics():
    report = await evaluate_golden_cases(EVAL_PATH)

    coverage = report["operator_coverage_metrics"]

    assert coverage["ok"] is True
    assert coverage["checked_case_count"] >= 50
    assert coverage["missing_required_operator_count"] == 0
    assert coverage["operator_set_failure_count"] == 0
    assert coverage["missing_required_operator_case_ids"] == []
    assert coverage["operator_set_failure_case_ids"] == []
    assert "audio_feedback_panel_debug" in coverage["checked_case_ids"]


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_substitution_quality_metrics():
    report = await evaluate_golden_cases(EVAL_PATH)

    substitution = report["substitution_quality_metrics"]

    assert substitution["ok"] is True
    assert substitution["case_count"] == report["case_count"]
    assert substitution["substitution_case_count"] >= 1
    assert substitution["approved_substitution_count"] >= 1
    assert substitution["pending_approval_count"] == 0
    assert substitution["approval_required_count"] >= 1
    assert substitution["unapproved_required_count"] == 0
    assert substitution["substitution_without_rule_count"] == 0
    assert substitution["replacement_operator_missing_count"] == 0
    assert substitution["low_confidence_count"] == 0
    assert "audio_feedback_panel_device_substitution" in substitution["substitution_case_ids"]
    approved = {
        (
            item["case_id"],
            item["missing_op"],
            tuple(item["replacement_ops"]),
            item["confidence"],
            item["requires_approval"],
        )
        for item in substitution["approved_substitutions"]
    }
    assert (
        "audio_feedback_panel_device_substitution",
        "audiofileinCHOP",
        ("audiodeviceinCHOP",),
        "medium",
        True,
    ) in approved


@pytest.mark.asyncio
async def test_evaluate_case_reports_structured_availability_matrix_metadata():
    cases = {case["id"]: case for case in load_golden_cases(EVAL_PATH)}

    result = await evaluate_case(cases["audio_feedback_panel_device_substitution"])

    availability = result["availability_matrix"]
    assert availability["td_build"] == "2025.32820"
    assert availability["platform"] == "macOS"
    assert availability["installed_addons"] == []
    assert availability["operator_count"] >= 2
    assert availability["unavailable_count"] >= 1
    assert availability["unavailable_reasons"]["audiofileinCHOP"] == "missing from live family list"


def test_decomposition_accuracy_metrics_track_time_behavior_failures():
    metrics = evals._aggregate_decomposition_accuracy_metrics(
        [
            {
                "id": "time_behavior_regression",
                "compiled_domains": ["CHOP", "TOP"],
                "checks": {
                    "compiled_domains": {"ok": True},
                    "time_behavior": {"ok": False},
                    "pattern_composition": {"ok": True},
                },
                "decomposition_metrics": {
                    "compiled_domain_count": 2,
                    "candidate_pattern_count": 2,
                },
            }
        ]
    )

    assert metrics["ok"] is False
    assert metrics["time_behavior_checked_case_count"] == 1
    assert metrics["time_behavior_failure_count"] == 1
    assert metrics["time_behavior_checked_case_ids"] == ["time_behavior_regression"]
    assert metrics["failed_case_ids"] == ["time_behavior_regression"]


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_generated_code_success_metrics():
    report = await evaluate_golden_cases(EVAL_PATH)

    metrics = report["generated_code_success_metrics"]

    assert metrics["ok"] is True
    assert metrics["generated_code_case_count"] >= 18
    assert metrics["generated_code_block_count"] >= 25
    assert metrics["language_count"] == 2
    assert set(metrics["languages"]) == {"glsl", "python"}
    assert metrics["static_issue_count"] == 0
    assert metrics["runtime_contract_missing_count"] == 0
    assert metrics["runtime_contract_count"] >= metrics["generated_code_block_count"]
    assert {"compile_state", "callback_guard_present", "finite_pop_bounds"}.issubset(
        set(metrics["runtime_checks"])
    )
    assert "glsl_top_shader_compiled" in metrics["generated_code_case_ids"]
    shader_case = next(item for item in report["cases"] if item["id"] == "glsl_top_shader_compiled")
    assert shader_case["generated_code_metrics"]["block_count"] >= 1
    assert shader_case["generated_code_metrics"]["static_issue_count"] == 0


def test_substitution_quality_requires_approval_evidence_for_approval_required_rules():
    metrics = evals._aggregate_substitution_quality_metrics(
        [
            {
                "id": "approval_missing_probe",
                "operators": ["audiodeviceinCHOP"],
                "grounding_evidence": [
                    "substitution:audiofileinCHOP->audio_device_to_analysis_chop",
                    "substitution-rule:audiofileinCHOP->audiodeviceinCHOP:medium:requires-approval",
                ],
            }
        ]
    )

    assert metrics["ok"] is False
    assert metrics["approval_required_count"] == 1
    assert metrics["unapproved_required_count"] == 1
    assert metrics["approved_substitution_count"] == 0
    assert metrics["pending_approval_count"] == 1
    assert metrics["pending_substitutions"] == [
        {
            "case_id": "approval_missing_probe",
            "missing_op": "audiofileinCHOP",
            "replacement_target": "audio_device_to_analysis_chop",
            "replacement_ops": ["audiodeviceinCHOP"],
            "confidence": "medium",
            "requires_approval": True,
            "approval_evidence": [],
        }
    ]


def test_substitution_quality_accepts_declared_device_source_as_approval_evidence():
    metrics = evals._aggregate_substitution_quality_metrics(
        [
            {
                "id": "approval_declared_probe",
                "operators": ["audiodeviceinCHOP"],
                "grounding_evidence": [
                    "device-source-declared:audio_device",
                    "substitution:audiofileinCHOP->audio_device_to_analysis_chop",
                    "substitution-rule:audiofileinCHOP->audiodeviceinCHOP:medium:requires-approval",
                ],
            }
        ]
    )

    assert metrics["ok"] is True
    assert metrics["approval_required_count"] == 1
    assert metrics["unapproved_required_count"] == 0
    assert metrics["pending_approval_count"] == 0
    assert metrics["approved_substitutions"] == [
        {
            "case_id": "approval_declared_probe",
            "missing_op": "audiofileinCHOP",
            "replacement_target": "audio_device_to_analysis_chop",
            "replacement_ops": ["audiodeviceinCHOP"],
            "confidence": "medium",
            "requires_approval": True,
            "approval_evidence": ["device-source-declared:audio_device"],
        }
    ]


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_compiler_stability_summary():
    report = await evaluate_golden_cases(EVAL_PATH)

    summary = report["compiler_stability"]

    assert summary["ok"] is True
    assert summary["compiled_case_count"] >= 30
    assert summary["passed_compiled_case_count"] == summary["compiled_case_count"]
    assert summary["blocked_compiled_case_count"] == 0
    assert summary["compiled_domain_failure_count"] == 0
    assert summary["pattern_composition_failure_count"] == 0
    assert "audio_feedback_panel_debug" in summary["compiled_case_ids"]
    assert "audio_terrain_glass_controls" in summary["compiled_case_ids"]


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_decomposition_accuracy_metrics():
    report = await evaluate_golden_cases(EVAL_PATH)

    metrics = report["decomposition_accuracy_metrics"]

    assert metrics["ok"] is True
    assert metrics["compiled_case_count"] >= 30
    assert metrics["multi_domain_case_count"] >= 20
    assert metrics["three_plus_domain_case_count"] >= 10
    assert metrics["compiled_domain_failure_count"] == 0
    assert metrics["pattern_composition_failure_count"] == 0
    assert metrics["failed_case_ids"] == []
    assert "audio_feedback_panel_debug" in metrics["multi_domain_case_ids"]


@pytest.mark.asyncio
async def test_trace_replay_detects_profile_drift():
    cases = {case["id"]: case for case in load_golden_cases(EVAL_PATH)}

    report = await evals.trace_replay_drift_report(
        [cases["audio_feedback_panel_debug"]],
        {
            "audio_feedback_panel_debug": {
                "profile": "feedback",
                "operators": [
                    "audiofileinCHOP",
                    "analyzeCHOP",
                    "mathCHOP",
                    "nullCHOP",
                ],
            }
        },
    )

    assert report["ok"] is False
    assert report["case_count"] == 1
    assert report["drift_count"] == 1
    drift = report["drifts"][0]
    assert drift["case_id"] == "audio_feedback_panel_debug"
    assert drift["profile_drift"] == {
        "expected": "feedback",
        "actual": "concept_compiled",
    }


@pytest.mark.asyncio
async def test_trace_replay_detects_operator_drift():
    cases = {case["id"]: case for case in load_golden_cases(EVAL_PATH)}

    report = await evals.trace_replay_drift_report(
        [cases["audio_feedback_panel_debug"]],
        {
            "audio_feedback_panel_debug": {
                "profile": "concept_compiled",
                "operators": [
                    "audiofileinCHOP",
                    "futureMagicTOP",
                ],
            }
        },
    )

    assert report["ok"] is False
    drift = report["drifts"][0]
    assert drift["profile_drift"] is None
    assert drift["operator_drift"]["missing"] == ["futureMagicTOP"]
    assert "feedbackTOP" in drift["operator_drift"]["added"]
    assert "baseCOMP" in drift["operator_drift"]["added"]


@pytest.mark.asyncio
async def test_trace_replay_detects_promoted_pattern_operator_drift():
    cases = {case["id"]: case for case in load_golden_cases(EVAL_PATH)}
    case = cases["audio_feedback_panel_debug"]
    baseline = await evaluate_case(case)

    report = await evals.trace_replay_drift_report(
        [case],
        {
            "audio_feedback_panel_debug": {
                "profile": baseline["profile"],
                "operators": baseline["operators"],
                "promoted_pattern_candidate": {
                    "pattern_id": "trace_audio_feedback_green_audio_feedback_panel",
                    "required_ops": ["audiofileinCHOP", "feedbackTOP", "futureMagicTOP"],
                },
            }
        },
    )

    assert report["ok"] is False
    assert report["drift_count"] == 1
    drift = report["drifts"][0]
    assert drift["profile_drift"] is None
    assert drift["operator_drift"] is None
    assert drift["promoted_pattern_operator_drift"] == {
        "pattern_id": "trace_audio_feedback_green_audio_feedback_panel",
        "missing": ["futureMagicTOP"],
    }


@pytest.mark.asyncio
async def test_trace_replay_detects_promoted_pattern_runtime_validation_issues():
    cases = {case["id"]: case for case in load_golden_cases(EVAL_PATH)}
    case = cases["audio_feedback_panel_debug"]
    baseline = await evaluate_case(case)

    report = await evals.trace_replay_drift_report(
        [case],
        {
            "audio_feedback_panel_debug": {
                "profile": baseline["profile"],
                "operators": baseline["operators"],
                "promoted_pattern_candidate": {
                    "pattern_id": "trace_audio_feedback_green_audio_feedback_panel",
                    "required_ops": ["audiofileinCHOP", "feedbackTOP"],
                    "layout": {
                        "runtime_validation": {
                            "required_probe_ids": [
                                "audio_signal_activity",
                                "feedback_output_readback",
                            ],
                            "passed_probe_ids": ["audio_signal_activity"],
                            "missing_probe_details": {
                                "feedback_output_readback": {
                                    "profile": "feedback",
                                    "status": "runtime_contract_present",
                                    "readback_strategy": "top_luminance_runtime",
                                    "pending_metric_names": [
                                        "feedback_output_luminance_mean",
                                        "feedback_output_luminance_max",
                                    ],
                                }
                            },
                            "failed_probe_ids": ["cheap_visual_metrics"],
                            "failed_probe_statuses": {
                                "cheap_visual_metrics": "runtime_fail",
                            },
                        }
                    },
                },
            }
        },
    )

    assert report["ok"] is False
    assert report["drift_count"] == 1
    drift = report["drifts"][0]
    assert drift["profile_drift"] is None
    assert drift["operator_drift"] is None
    assert drift["promoted_pattern_operator_drift"] is None
    assert drift["promoted_pattern_runtime_validation_issues"] == {
        "pattern_id": "trace_audio_feedback_green_audio_feedback_panel",
        "missing_probe_ids": ["feedback_output_readback"],
        "missing_probe_details": {
            "feedback_output_readback": {
                "profile": "feedback",
                "status": "runtime_contract_present",
                "readback_strategy": "top_luminance_runtime",
                "pending_metric_names": [
                    "feedback_output_luminance_mean",
                    "feedback_output_luminance_max",
                ],
            }
        },
        "failed_probe_ids": ["cheap_visual_metrics"],
        "failed_probe_statuses": {"cheap_visual_metrics": "runtime_fail"},
    }


@pytest.mark.asyncio
async def test_trace_replay_detects_failed_only_promoted_pattern_runtime_probe():
    cases = {case["id"]: case for case in load_golden_cases(EVAL_PATH)}
    case = cases["audio_feedback_panel_debug"]
    baseline = await evaluate_case(case)

    report = await evals.trace_replay_drift_report(
        [case],
        {
            "audio_feedback_panel_debug": {
                "profile": baseline["profile"],
                "operators": baseline["operators"],
                "promoted_pattern_candidate": {
                    "pattern_id": "trace_audio_feedback_visual_optional_failure",
                    "required_ops": ["audiofileinCHOP", "feedbackTOP"],
                    "layout": {
                        "runtime_validation": {
                            "required_probe_ids": [],
                            "passed_probe_ids": [],
                            "failed_probe_ids": ["cheap_visual_metrics"],
                            "failed_probe_statuses": {
                                "cheap_visual_metrics": "runtime_fail",
                            },
                            "failed_probe_details": {
                                "cheap_visual_metrics": {
                                    "profile": "visual",
                                    "status": "runtime_fail",
                                    "issue_code": "cheap_visual_metrics_black_frame",
                                    "readback_path": "/project1/tdpilot_concept/out1",
                                    "runtime_required": False,
                                    "runtime_metric_values": {
                                        "luminance_mean": 0.0,
                                        "entropy": 0.0,
                                    },
                                }
                            },
                        }
                    },
                },
            }
        },
    )

    assert report["ok"] is False
    assert report["drift_count"] == 1
    drift = report["drifts"][0]
    assert drift["profile_drift"] is None
    assert drift["operator_drift"] is None
    assert drift["promoted_pattern_operator_drift"] is None
    assert drift["promoted_pattern_runtime_validation_issues"] == {
        "pattern_id": "trace_audio_feedback_visual_optional_failure",
        "missing_probe_ids": [],
        "failed_probe_ids": ["cheap_visual_metrics"],
        "failed_probe_statuses": {"cheap_visual_metrics": "runtime_fail"},
        "failed_probe_details": {
            "cheap_visual_metrics": {
                "profile": "visual",
                "status": "runtime_fail",
                "issue_code": "cheap_visual_metrics_black_frame",
                "readback_path": "/project1/tdpilot_concept/out1",
                "runtime_required": False,
                "runtime_metric_values": {
                    "luminance_mean": 0.0,
                    "entropy": 0.0,
                },
            }
        },
    }


@pytest.mark.asyncio
async def test_trace_replay_aggregates_repeated_validation_issue_memory():
    cases = {case["id"]: case for case in load_golden_cases(EVAL_PATH)}
    selected_ids = ["audio_feedback_panel_debug", "audio_feedback_panel_diagnostics"]
    selected_cases = [cases[case_id] for case_id in selected_ids]
    baselines = {case_id: await evaluate_case(cases[case_id]) for case_id in selected_ids}
    runtime_validation = {
        "required_probe_ids": [
            "audio_signal_activity",
            "feedback_output_readback",
        ],
        "passed_probe_ids": ["audio_signal_activity"],
        "missing_probe_ids": ["feedback_output_readback"],
        "failed_probe_ids": ["cheap_visual_metrics"],
        "failed_probe_statuses": {"cheap_visual_metrics": "runtime_fail"},
        "failed_optional_probe_ids": ["cheap_visual_metrics"],
        "confidence_decay": 0.86,
        "confidence_penalty_reasons": [
            "missing_required_probe:feedback_output_readback",
            "failed_optional_probe:cheap_visual_metrics",
        ],
    }

    report = await evals.trace_replay_drift_report(
        selected_cases,
        {
            case_id: {
                "profile": baselines[case_id]["profile"],
                "operators": baselines[case_id]["operators"],
                "trace_id": f"trace-{case_id}-weak-runtime",
                "promoted_pattern_candidate": {
                    "pattern_id": f"trace_{case_id}_weak_runtime",
                    "required_ops": ["audiofileinCHOP", "feedbackTOP"],
                    "layout": {
                        "trace_fingerprint": "tracefp:audio-feedback-weak-runtime",
                        "intent_fingerprint": "intent:audio-feedback-panel",
                        "operator_fingerprint": "ops:audio-feedback-panel",
                        "validation_fingerprint": "validation:feedback-output-readback",
                        "runtime_validation": runtime_validation,
                    },
                },
            }
            for case_id in selected_ids
        },
    )

    assert report["ok"] is False
    assert report["drift_count"] == 2
    memory = report["validation_issue_memory"]
    assert memory["ok"] is False
    assert memory["issue_count"] == 4
    assert memory["unique_issue_count"] == 2
    assert memory["repeated_issue_count"] == 2
    assert memory["promotion_demotion_candidate_count"] == 2

    repeated = {(item["kind"], item["id"]): item for item in memory["repeated_issues"]}
    missing = repeated[("runtime_missing_probe", "feedback_output_readback")]
    assert missing["count"] == 2
    assert missing["case_ids"] == sorted(selected_ids)
    assert missing["sources"] == ["promoted_pattern"]
    assert missing["promotion_audit_action"] == "block_promotion"
    assert missing["min_confidence_decay"] == 0.86
    assert missing["trace_ids"] == sorted(f"trace-{case_id}-weak-runtime" for case_id in selected_ids)
    assert missing["trace_fingerprints"] == {
        "intent_fingerprint": ["intent:audio-feedback-panel"],
        "operator_fingerprint": ["ops:audio-feedback-panel"],
        "trace_fingerprint": ["tracefp:audio-feedback-weak-runtime"],
        "validation_fingerprint": ["validation:feedback-output-readback"],
    }
    assert missing["trace_fingerprint_count"] == 1
    assert missing["promotion_audit_cluster_ids"] == ["tracefp:audio-feedback-weak-runtime"]
    assert missing["confidence_penalty_reasons"] == [
        "failed_optional_probe:cheap_visual_metrics",
        "missing_required_probe:feedback_output_readback",
    ]

    optional = repeated[("runtime_failed_optional_probe", "cheap_visual_metrics")]
    assert optional["count"] == 2
    assert optional["case_ids"] == sorted(selected_ids)
    assert optional["statuses"] == ["runtime_fail"]
    assert optional["promotion_audit_action"] == "demote_promoted_pattern"
    assert optional["demotion_cluster_ids"] == ["tracefp:audio-feedback-weak-runtime"]


@pytest.mark.asyncio
async def test_trace_replay_blocks_promotion_for_repeated_unclassified_runtime_failures():
    cases = {case["id"]: case for case in load_golden_cases(EVAL_PATH)}
    selected_ids = ["audio_feedback_panel_debug", "audio_feedback_panel_diagnostics"]
    selected_cases = [cases[case_id] for case_id in selected_ids]
    baselines = {case_id: await evaluate_case(cases[case_id]) for case_id in selected_ids}
    runtime_validation = {
        "failed_probe_ids": ["feedback_output_readback"],
        "failed_probe_statuses": {
            "feedback_output_readback": "runtime_failed",
        },
        "confidence_decay": 0.78,
        "confidence_penalty_reasons": [
            "failed_probe:feedback_output_readback",
        ],
    }

    report = await evals.trace_replay_drift_report(
        selected_cases,
        {
            case_id: {
                "profile": baselines[case_id]["profile"],
                "operators": baselines[case_id]["operators"],
                "trace_id": f"trace-{case_id}-rejected",
                "trace_promotion_rejection": {
                    "blockers": [
                        "failed runtime validation probes: feedback_output_readback",
                    ],
                    "trace_fingerprints": {
                        "trace_fingerprint": "tracefp:feedback-output-readback-failed",
                        "intent_fingerprint": "intent:audio-feedback-panel",
                        "operator_fingerprint": "ops:audio-feedback-panel",
                        "validation_fingerprint": "validation:feedback-output-readback",
                    },
                    "runtime_validation_issues": runtime_validation,
                },
            }
            for case_id in selected_ids
        },
    )

    assert report["ok"] is False
    memory = report["validation_issue_memory"]
    assert memory["promotion_demotion_candidate_count"] == 1
    repeated = {(item["kind"], item["id"]): item for item in memory["promotion_demotion_candidates"]}
    failed = repeated[("runtime_failed_probe", "feedback_output_readback")]
    assert failed["count"] == 2
    assert failed["case_ids"] == sorted(selected_ids)
    assert failed["sources"] == ["trace_promotion_rejection"]
    assert failed["statuses"] == ["runtime_failed"]
    assert failed["promotion_audit_action"] == "block_promotion"
    assert failed["min_confidence_decay"] == 0.78
    assert failed["trace_ids"] == sorted(f"trace-{case_id}-rejected" for case_id in selected_ids)
    assert failed["trace_fingerprints"] == {
        "intent_fingerprint": ["intent:audio-feedback-panel"],
        "operator_fingerprint": ["ops:audio-feedback-panel"],
        "trace_fingerprint": ["tracefp:feedback-output-readback-failed"],
        "validation_fingerprint": ["validation:feedback-output-readback"],
    }
    assert failed["trace_fingerprint_count"] == 1
    assert failed["promotion_audit_cluster_ids"] == ["tracefp:feedback-output-readback-failed"]
    assert failed["confidence_penalty_reasons"] == [
        "failed_probe:feedback_output_readback",
    ]


@pytest.mark.asyncio
async def test_trace_replay_aggregates_repeated_generated_code_contract_memory():
    cases = {case["id"]: case for case in load_golden_cases(EVAL_PATH)}
    selected_ids = ["glsl_top_shader_compiled", "glsl_fragment_inspector_compiled"]
    selected_cases = [cases[case_id] for case_id in selected_ids]
    baselines = {case_id: await evaluate_case(cases[case_id]) for case_id in selected_ids}
    generated_code_issues = {
        "missing_contract_ids": ["glsl_top_pixel_shader:compile_state"],
        "failed_contract_ids": ["glsl_top_pixel_shader:compile_state"],
        "failed_contract_statuses": {"glsl_top_pixel_shader:compile_state": "runtime_fail"},
        "confidence_decay": 0.66,
        "confidence_penalty_reasons": [
            "missing_generated_code_contract:glsl_top_pixel_shader:compile_state",
            "failed_generated_code_contract:glsl_top_pixel_shader:compile_state",
        ],
    }

    report = await evals.trace_replay_drift_report(
        selected_cases,
        {
            case_id: {
                "profile": baselines[case_id]["profile"],
                "operators": baselines[case_id]["operators"],
                "trace_id": f"trace-{case_id}-generated-code-rejected",
                "trace_promotion_rejection": {
                    "blockers": [
                        "missing generated code runtime validation passes: "
                        "glsl_top_pixel_shader:compile_state"
                    ],
                    "trace_fingerprints": {
                        "trace_fingerprint": "tracefp:glsl-compile-contract-failed",
                        "intent_fingerprint": "intent:glsl-top-shader",
                        "operator_fingerprint": "ops:glsl-top",
                        "validation_fingerprint": "validation:glsl-compile-state",
                    },
                    "generated_code_runtime_issues": generated_code_issues,
                },
            }
            for case_id in selected_ids
        },
    )

    assert report["ok"] is False
    assert report["drift_count"] == 2
    memory = report["validation_issue_memory"]
    assert memory["issue_count"] == 4
    assert memory["unique_issue_count"] == 2
    assert memory["repeated_issue_count"] == 2
    assert memory["promotion_demotion_candidate_count"] == 2

    repeated = {(item["kind"], item["id"]): item for item in memory["repeated_issues"]}
    missing = repeated[
        (
            "generated_code_missing_contract",
            "glsl_top_pixel_shader:compile_state",
        )
    ]
    assert missing["count"] == 2
    assert missing["case_ids"] == sorted(selected_ids)
    assert missing["promotion_audit_action"] == "block_promotion"
    assert missing["min_confidence_decay"] == 0.66
    assert missing["trace_ids"] == sorted(
        f"trace-{case_id}-generated-code-rejected" for case_id in selected_ids
    )
    assert missing["trace_fingerprints"] == {
        "intent_fingerprint": ["intent:glsl-top-shader"],
        "operator_fingerprint": ["ops:glsl-top"],
        "trace_fingerprint": ["tracefp:glsl-compile-contract-failed"],
        "validation_fingerprint": ["validation:glsl-compile-state"],
    }
    assert missing["promotion_audit_cluster_ids"] == ["tracefp:glsl-compile-contract-failed"]

    failed = repeated[
        (
            "generated_code_failed_contract",
            "glsl_top_pixel_shader:compile_state",
        )
    ]
    assert failed["count"] == 2
    assert failed["statuses"] == ["runtime_fail"]
    assert failed["promotion_audit_action"] == "block_promotion"
    assert failed["trace_fingerprint_count"] == 1


@pytest.mark.asyncio
async def test_trace_replay_detects_trace_promotion_rejection_probe_issues():
    cases = {case["id"]: case for case in load_golden_cases(EVAL_PATH)}
    case = cases["audio_feedback_panel_debug"]
    baseline = await evaluate_case(case)

    report = await evals.trace_replay_drift_report(
        [case],
        {
            "audio_feedback_panel_debug": {
                "profile": baseline["profile"],
                "operators": baseline["operators"],
                "trace_promotion_rejection": {
                    "blockers": [
                        "missing runtime validation passes: feedback_output_readback",
                        "failed required runtime validation probes: feedback_output_readback",
                    ],
                    "runtime_validation_issues": {
                        "missing_probe_ids": ["feedback_output_readback"],
                        "missing_probe_details": {
                            "feedback_output_readback": {
                                "profile": "feedback",
                                "status": "runtime_contract_present",
                                "readback_strategy": "top_luminance_runtime",
                                "pending_metric_names": [
                                    "feedback_output_luminance_mean",
                                    "feedback_output_luminance_max",
                                ],
                            }
                        },
                        "failed_required_probe_ids": ["feedback_output_readback"],
                        "failed_probe_ids": [
                            "feedback_output_readback",
                            "cheap_visual_metrics",
                        ],
                        "failed_probe_statuses": {
                            "feedback_output_readback": "runtime_failed",
                            "cheap_visual_metrics": "runtime_fail",
                        },
                        "failed_required_probe_details": {
                            "feedback_output_readback": {
                                "profile": "feedback",
                                "status": "runtime_failed",
                                "issue_code": "profile_probe_runtime_feedback_output_missing",
                                "readback_path": "/project1/tdpilot_concept/out1",
                                "runtime_metric_values": {
                                    "feedback_output_luminance_mean": 0.0,
                                    "feedback_output_luminance_max": 0.0,
                                },
                            }
                        },
                        "failed_probe_details": {
                            "feedback_output_readback": {
                                "profile": "feedback",
                                "status": "runtime_failed",
                                "issue_code": "profile_probe_runtime_feedback_output_missing",
                                "readback_path": "/project1/tdpilot_concept/out1",
                                "runtime_metric_values": {
                                    "feedback_output_luminance_mean": 0.0,
                                    "feedback_output_luminance_max": 0.0,
                                },
                            },
                            "cheap_visual_metrics": {
                                "profile": "visual",
                                "status": "runtime_fail",
                                "issue_code": "cheap_visual_metrics_black_frame",
                                "readback_path": "/project1/tdpilot_concept/out1",
                                "runtime_metric_values": {
                                    "luminance_mean": 0.0,
                                    "entropy": 0.0,
                                },
                            },
                        },
                    },
                },
            }
        },
    )

    assert report["ok"] is False
    assert report["drift_count"] == 1
    drift = report["drifts"][0]
    assert drift["profile_drift"] is None
    assert drift["operator_drift"] is None
    assert drift["promoted_pattern_operator_drift"] is None
    assert drift["promoted_pattern_runtime_validation_issues"] is None
    assert drift["trace_promotion_rejection_issues"] == {
        "blockers": [
            "missing runtime validation passes: feedback_output_readback",
            "failed required runtime validation probes: feedback_output_readback",
        ],
        "runtime_validation_issues": {
            "missing_probe_ids": ["feedback_output_readback"],
            "missing_probe_details": {
                "feedback_output_readback": {
                    "profile": "feedback",
                    "status": "runtime_contract_present",
                    "readback_strategy": "top_luminance_runtime",
                    "pending_metric_names": [
                        "feedback_output_luminance_mean",
                        "feedback_output_luminance_max",
                    ],
                }
            },
            "failed_required_probe_ids": ["feedback_output_readback"],
            "failed_probe_ids": ["feedback_output_readback", "cheap_visual_metrics"],
            "failed_probe_statuses": {
                "feedback_output_readback": "runtime_failed",
                "cheap_visual_metrics": "runtime_fail",
            },
            "failed_required_probe_details": {
                "feedback_output_readback": {
                    "profile": "feedback",
                    "status": "runtime_failed",
                    "issue_code": "profile_probe_runtime_feedback_output_missing",
                    "readback_path": "/project1/tdpilot_concept/out1",
                    "runtime_metric_values": {
                        "feedback_output_luminance_mean": 0.0,
                        "feedback_output_luminance_max": 0.0,
                    },
                }
            },
            "failed_probe_details": {
                "feedback_output_readback": {
                    "profile": "feedback",
                    "status": "runtime_failed",
                    "issue_code": "profile_probe_runtime_feedback_output_missing",
                    "readback_path": "/project1/tdpilot_concept/out1",
                    "runtime_metric_values": {
                        "feedback_output_luminance_mean": 0.0,
                        "feedback_output_luminance_max": 0.0,
                    },
                },
                "cheap_visual_metrics": {
                    "profile": "visual",
                    "status": "runtime_fail",
                    "issue_code": "cheap_visual_metrics_black_frame",
                    "readback_path": "/project1/tdpilot_concept/out1",
                    "runtime_metric_values": {
                        "luminance_mean": 0.0,
                        "entropy": 0.0,
                    },
                },
            },
        },
    }


@pytest.mark.asyncio
async def test_trace_replay_detects_generated_code_runtime_rejection_details():
    cases = {case["id"]: case for case in load_golden_cases(EVAL_PATH)}
    case = cases["glsl_top_shader_compiled"]
    baseline = await evaluate_case(case)

    report = await evals.trace_replay_drift_report(
        [case],
        {
            "glsl_top_shader_compiled": {
                "profile": baseline["profile"],
                "operators": baseline["operators"],
                "trace_promotion_rejection": {
                    "blockers": [
                        "missing generated code runtime validation passes: glsl_top_pixel_shader:compile_state"
                    ],
                    "generated_code_runtime_issues": {
                        "missing_contract_ids": ["glsl_top_pixel_shader:compile_state"],
                        "missing_contract_details": {
                            "glsl_top_pixel_shader:compile_state": {
                                "block_id": "glsl_top_pixel_shader",
                                "check_id": "compile_state",
                                "language": "glsl",
                                "target_op": "/project1/glsl",
                                "target_param": "pixeldat",
                                "endpoint": "node/errors",
                                "status": "runtime_fail",
                                "issue_count": 1,
                                "expected_outputs": ["/project1/out1"],
                                "risk_flags": ["validate-glsl-compile-state"],
                                "official_sources": ["https://docs.derivative.ca/GLSL_TOP"],
                            }
                        },
                        "failed_contract_ids": ["glsl_top_pixel_shader:compile_state"],
                        "failed_contract_statuses": {"glsl_top_pixel_shader:compile_state": "runtime_fail"},
                        "failed_contract_details": {
                            "glsl_top_pixel_shader:compile_state": {
                                "block_id": "glsl_top_pixel_shader",
                                "check_id": "compile_state",
                                "language": "glsl",
                                "target_op": "/project1/glsl",
                                "target_param": "pixeldat",
                                "endpoint": "node/errors",
                                "status": "runtime_fail",
                                "issue_count": 1,
                                "expected_outputs": ["/project1/out1"],
                                "risk_flags": ["validate-glsl-compile-state"],
                                "official_sources": ["https://docs.derivative.ca/GLSL_TOP"],
                            }
                        },
                    },
                },
            }
        },
    )

    assert report["ok"] is False
    assert report["drift_count"] == 1
    drift = report["drifts"][0]
    assert drift["profile_drift"] is None
    assert drift["operator_drift"] is None
    assert drift["promoted_pattern_operator_drift"] is None
    assert drift["promoted_pattern_runtime_validation_issues"] is None
    assert drift["trace_promotion_rejection_issues"] == {
        "blockers": ["missing generated code runtime validation passes: glsl_top_pixel_shader:compile_state"],
        "generated_code_runtime_issues": {
            "missing_contract_ids": ["glsl_top_pixel_shader:compile_state"],
            "missing_contract_details": {
                "glsl_top_pixel_shader:compile_state": {
                    "block_id": "glsl_top_pixel_shader",
                    "check_id": "compile_state",
                    "language": "glsl",
                    "target_op": "/project1/glsl",
                    "target_param": "pixeldat",
                    "endpoint": "node/errors",
                    "status": "runtime_fail",
                    "issue_count": 1,
                    "expected_outputs": ["/project1/out1"],
                    "risk_flags": ["validate-glsl-compile-state"],
                    "official_sources": ["https://docs.derivative.ca/GLSL_TOP"],
                }
            },
            "failed_contract_ids": ["glsl_top_pixel_shader:compile_state"],
            "failed_contract_statuses": {"glsl_top_pixel_shader:compile_state": "runtime_fail"},
            "failed_contract_details": {
                "glsl_top_pixel_shader:compile_state": {
                    "block_id": "glsl_top_pixel_shader",
                    "check_id": "compile_state",
                    "language": "glsl",
                    "target_op": "/project1/glsl",
                    "target_param": "pixeldat",
                    "endpoint": "node/errors",
                    "status": "runtime_fail",
                    "issue_count": 1,
                    "expected_outputs": ["/project1/out1"],
                    "risk_flags": ["validate-glsl-compile-state"],
                    "official_sources": ["https://docs.derivative.ca/GLSL_TOP"],
                }
            },
        },
    }


@pytest.mark.asyncio
async def test_trace_replay_passes_when_saved_trace_matches_current_plan():
    cases = {case["id"]: case for case in load_golden_cases(EVAL_PATH)}
    case = cases["audio_feedback_panel_debug"]
    baseline = await evaluate_case(case)

    report = await evals.trace_replay_drift_report(
        [case],
        {
            "audio_feedback_panel_debug": {
                "profile": baseline["profile"],
                "operators": baseline["operators"],
            }
        },
    )

    assert report == {
        "schema_version": 1,
        "ok": True,
        "case_count": 1,
        "drift_count": 0,
        "drifts": [],
        "validation_issue_memory": {
            "schema_version": 1,
            "ok": True,
            "issue_count": 0,
            "unique_issue_count": 0,
            "repeated_issue_count": 0,
            "repeated_issues": [],
            "promotion_demotion_candidate_count": 0,
            "promotion_demotion_candidates": [],
        },
    }


@pytest.mark.asyncio
async def test_trace_replay_baseline_scopes_to_saved_cases():
    cases = {case["id"]: case for case in load_golden_cases(EVAL_PATH)}
    case = cases["audio_feedback_panel_debug"]
    baseline = await evaluate_case(case)

    report = await evals.trace_replay_baseline_report(
        list(cases.values()),
        {
            "audio_feedback_panel_debug": {
                "profile": baseline["profile"],
                "operators": baseline["operators"],
            }
        },
    )

    assert report["ok"] is True
    assert report["case_count"] == 1
    assert report["baseline_case_count"] == 1
    assert report["skipped_case_count"] == len(cases) - 1
    assert report["drift_count"] == 0
    assert report["drifts"] == []


def test_trace_baseline_from_eval_results_uses_case_ids_profiles_and_operators():
    baseline = evals.trace_baseline_from_eval_results(
        [
            {
                "id": "audio_feedback_panel_debug",
                "profile": "concept_compiled",
                "operators": ["audiofileinCHOP", "feedbackTOP"],
                "candidate_patterns": ["audio_analysis_chop_chain"],
            }
        ]
    )

    assert baseline == {
        "audio_feedback_panel_debug": {
            "profile": "concept_compiled",
            "operators": ["audiofileinCHOP", "feedbackTOP"],
        }
    }


def test_trace_baseline_envelope_from_eval_results_is_schema_versioned():
    envelope = evals.trace_baseline_envelope_from_eval_results(
        [
            {
                "id": "audio_feedback_panel_debug",
                "profile": "concept_compiled",
                "operators": ["audiofileinCHOP", "feedbackTOP"],
            }
        ]
    )

    assert envelope == {
        "schema_version": 1,
        "case_count": 1,
        "traces": {
            "audio_feedback_panel_debug": {
                "profile": "concept_compiled",
                "operators": ["audiofileinCHOP", "feedbackTOP"],
            }
        },
    }


@pytest.mark.asyncio
async def test_evaluate_case_scores_expected_candidate_profiles():
    result = await evaluate_case(
        {
            "id": "profile_coverage_probe",
            "intent": "Build an audio-reactive 3D render with material modulation",
            "target_root": "/project1",
            "expected_profile": "concept_compiled",
            "expected_profiles": ["audio_reactive", "render_pipeline", "glsl_material"],
            "expected_compiled_domains": ["CHOP", "TOP", "COMP", "DAT", "MAT"],
            "expected_ops": [
                "audiofileinCHOP",
                "analyzeCHOP",
                "mathCHOP",
                "nullCHOP",
                "geometryCOMP",
                "cameraCOMP",
                "glslMAT",
                "renderTOP",
                "nullTOP",
                "textDAT",
                "baseCOMP",
                "annotateCOMP",
                "infoCHOP",
                "errorDAT",
            ],
            "validation_profile": "structural_visual_safe",
            "scoring": {"expected_profiles": 1},
        }
    )

    assert result["checks"]["expected_profiles"]["ok"] is True
    assert {"audio_reactive", "render_pipeline", "glsl_material"}.issubset(set(result["candidate_profiles"]))


@pytest.mark.asyncio
async def test_evaluate_case_reports_decomposition_plan_validation_and_time_metrics():
    result = await evaluate_case(
        {
            "id": "metrics_probe",
            "intent": "Build an audio-reactive 3D render with material modulation",
            "target_root": "/project1",
            "expected_profile": "concept_compiled",
            "expected_profiles": ["audio_reactive", "render_pipeline", "glsl_material"],
            "expected_compiled_domains": ["CHOP", "TOP", "COMP", "DAT", "MAT"],
            "expected_ops": [
                "audiofileinCHOP",
                "analyzeCHOP",
                "mathCHOP",
                "nullCHOP",
                "geometryCOMP",
                "cameraCOMP",
                "glslMAT",
                "renderTOP",
                "nullTOP",
                "textDAT",
                "baseCOMP",
                "annotateCOMP",
                "infoCHOP",
                "errorDAT",
            ],
            "validation_expectations": ["analysis_stage", "camera_present", "material_assigned"],
            "validation_profile": "structural_visual_safe",
        }
    )

    assert result["decomposition_metrics"]["compiled_domain_count"] == 5
    assert result["decomposition_metrics"]["candidate_profile_count"] == 3
    assert result["decomposition_metrics"]["candidate_pattern_count"] == len(
        set(result["candidate_patterns"])
    )
    assert result["decomposition_metrics"]["candidate_pattern_count"] >= 3
    assert result["plan_metrics"]["operation_count"] == result["operation_count"]
    assert result["plan_metrics"]["operator_count"] == len(result["operators"])
    assert result["plan_metrics"]["assembly_macro_count"] == len(result["assembly_macros"])
    assert result["validation_metrics"]["validation_check_count"] == len(result["validation_checks"])
    assert result["validation_metrics"]["missing_validation_expectation_count"] == 0
    assert result["validation_metrics"]["blocked_question_count"] == 0
    assert set(result["time_metrics"]) == {
        "planning_ms",
        "scoring_ms",
        "total_ms",
        "time_to_first_green_cycles",
    }
    assert result["time_metrics"]["planning_ms"] >= 0
    assert result["time_metrics"]["scoring_ms"] >= 0
    assert result["time_metrics"]["total_ms"] >= result["time_metrics"]["planning_ms"]
    assert result["time_metrics"]["time_to_first_green_cycles"] == 1


@pytest.mark.asyncio
async def test_evaluate_case_reports_human_readability_score_for_assembled_showpiece():
    cases = {case["id"]: case for case in load_golden_cases(EVAL_PATH)}

    result = await evaluate_case(cases["audio_feedback_panel_debug"])

    assert result["readability_metrics"]["score"] == result["readability_metrics"]["max_score"]
    assert result["readability_metrics"]["score"] >= 5
    assert result["readability_metrics"]["checks"] == {
        "component_shell": True,
        "domain_layout": True,
        "named_outputs": True,
        "debug_surface": True,
        "annotation_notes": True,
    }


@pytest.mark.asyncio
async def test_evaluate_case_fails_when_forbidden_operator_appears():
    result = await evaluate_case(
        {
            "id": "forbidden_operator_probe",
            "intent": "Build a stable feedback trail with noise source and visible output",
            "target_root": "/project1",
            "expected_profile": "feedback",
            "expected_ops": ["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
            "forbidden_ops": ["feedbackTOP"],
            "validation_profile": "structural_visual_safe",
            "scoring": {"forbidden_ops": 1},
        }
    )

    assert result["checks"]["forbidden_ops"]["ok"] is False
    assert result["forbidden_ops_present"] == ["feedbackTOP"]
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_evaluate_case_fails_when_plan_exceeds_max_ops():
    result = await evaluate_case(
        {
            "id": "max_plan_ops_probe",
            "intent": "Build a stable feedback trail with noise source and visible output",
            "target_root": "/project1",
            "expected_profile": "feedback",
            "expected_ops": ["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
            "max_plan_ops": 1,
            "validation_profile": "structural_visual_safe",
            "scoring": {"max_plan_ops": 1},
        }
    )

    assert result["checks"]["max_plan_ops"]["ok"] is False
    assert result["operation_count"] > result["max_plan_ops"]
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_evaluate_case_scores_validation_expectations():
    result = await evaluate_case(
        {
            "id": "validation_strength_probe",
            "intent": "Build an audio-reactive 3D render with material modulation",
            "target_root": "/project1",
            "expected_profile": "concept_compiled",
            "expected_profiles": ["audio_reactive", "render_pipeline", "glsl_material"],
            "expected_compiled_domains": ["CHOP", "TOP", "COMP", "DAT", "MAT"],
            "expected_ops": [
                "audiofileinCHOP",
                "analyzeCHOP",
                "mathCHOP",
                "nullCHOP",
                "geometryCOMP",
                "cameraCOMP",
                "glslMAT",
                "renderTOP",
                "nullTOP",
                "textDAT",
                "baseCOMP",
                "annotateCOMP",
                "infoCHOP",
                "errorDAT",
            ],
            "validation_expectations": ["analysis_stage", "camera_present", "material_assigned"],
            "validation_profile": "structural_visual_safe",
            "scoring": {"validation_expectations": 1},
        }
    )

    assert result["checks"]["validation_expectations"]["ok"] is True
    assert {"analysis_stage", "camera_present", "material_assigned"}.issubset(
        set(result["validation_checks"])
    )
    assert result["missing_validation_expectations"] == []


@pytest.mark.asyncio
async def test_evaluate_case_scores_required_patterns_future_field():
    result = await evaluate_case(
        {
            "id": "required_patterns_probe",
            "intent": "Build an audio-reactive 3D render with material modulation",
            "target_root": "/project1",
            "expected_profile": "concept_compiled",
            "expected_compiled_domains": ["CHOP", "TOP", "COMP", "DAT", "MAT"],
            "required_patterns": ["audio_analysis_chop_chain", "glsl_material_render_pipeline"],
            "expected_ops": [
                "audiofileinCHOP",
                "analyzeCHOP",
                "mathCHOP",
                "nullCHOP",
                "geometryCOMP",
                "cameraCOMP",
                "glslMAT",
                "renderTOP",
                "nullTOP",
                "textDAT",
                "baseCOMP",
                "annotateCOMP",
                "infoCHOP",
                "errorDAT",
            ],
            "validation_profile": "structural_visual_safe",
            "scoring": {"required_patterns": 1},
        }
    )

    assert result["checks"]["required_patterns"]["ok"] is True
    assert {"audio_analysis_chop_chain", "glsl_material_render_pipeline"}.issubset(
        set(result["candidate_patterns"])
    )


@pytest.mark.asyncio
async def test_evaluate_case_scores_required_grounding_evidence():
    result = await evaluate_case(
        {
            "id": "required_grounding_evidence_probe",
            "intent": "Build an audio-reactive 3D render with material modulation",
            "target_root": "/project1",
            "expected_profile": "concept_compiled",
            "expected_compiled_domains": ["CHOP", "TOP", "COMP", "DAT", "MAT"],
            "required_grounding_evidence": [
                "pattern:audio_file_to_analysis_chop",
                "pattern:glsl_material_render_pipeline",
            ],
            "expected_ops": [
                "audiofileinCHOP",
                "analyzeCHOP",
                "mathCHOP",
                "nullCHOP",
                "geometryCOMP",
                "cameraCOMP",
                "glslMAT",
                "renderTOP",
                "nullTOP",
                "textDAT",
                "baseCOMP",
                "annotateCOMP",
                "infoCHOP",
                "errorDAT",
            ],
            "validation_profile": "structural_visual_safe",
            "scoring": {"required_grounding_evidence": 1},
        }
    )

    assert result["checks"]["required_grounding_evidence"]["ok"] is True
    assert result["missing_required_grounding_evidence"] == []


@pytest.mark.asyncio
async def test_evaluate_case_scores_expected_operator_sets_future_field():
    result = await evaluate_case(
        {
            "id": "operator_sets_probe",
            "intent": "Build a stable feedback trail with noise source and visible output",
            "target_root": "/project1",
            "expected_profile": "feedback",
            "expected_operator_sets": [
                ["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
                ["moviefileinTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
            ],
            "validation_profile": "structural_visual_safe",
            "scoring": {"operator_set": 1},
        }
    )

    assert result["checks"]["operator_set"]["ok"] is True
    assert result["matched_operator_set"] == [
        "noiseTOP",
        "feedbackTOP",
        "levelTOP",
        "compositeTOP",
        "nullTOP",
    ]


@pytest.mark.asyncio
async def test_evaluate_case_accepts_future_case_field_names():
    result = await evaluate_case(
        {
            "case_id": "future_schema_probe",
            "prompt": "Build an audio-reactive 3D render with material modulation",
            "target_root": "/project1",
            "expected_profile": "concept_compiled",
            "expected_domains": ["CHOP", "TOP", "COMP", "DAT", "MAT"],
            "expected_operator_sets": [
                [
                    "audiofileinCHOP",
                    "analyzeCHOP",
                    "mathCHOP",
                    "nullCHOP",
                    "geometryCOMP",
                    "cameraCOMP",
                    "glslMAT",
                    "renderTOP",
                    "nullTOP",
                    "textDAT",
                    "baseCOMP",
                    "annotateCOMP",
                    "infoCHOP",
                    "errorDAT",
                ]
            ],
            "required_patterns": ["audio_analysis_chop_chain", "glsl_material_render_pipeline"],
            "validation_expectations": ["analysis_stage", "camera_present", "material_assigned"],
            "validation_profile": "structural_visual_safe",
            "scoring_weights": {
                "compiled_domains": 2,
                "operator_set": 2,
                "required_patterns": 2,
                "validation_expectations": 2,
            },
        }
    )

    assert result["id"] == "future_schema_probe"
    assert result["checks"]["compiled_domains"]["weight"] == 2
    assert result["checks"]["operator_set"]["ok"] is True
    assert result["checks"]["required_patterns"]["ok"] is True
    assert result["checks"]["validation_expectations"]["ok"] is True


def test_eval_brain_golden_cli_outputs_json_report():
    proc = subprocess.run(
        [sys.executable, "scripts/eval_brain_golden.py", "--cases", str(EVAL_PATH)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["case_count"] >= 6
    assert payload["trace_replay"]["ok"] is True
    assert payload["trace_replay"]["baseline_case_count"] == payload["case_count"]
    assert payload["trace_replay"]["drift_count"] == 0


def test_eval_brain_golden_cli_fails_on_trace_baseline_drift(tmp_path):
    baseline_path = tmp_path / "trace_baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "audio_feedback_panel_debug": {
                    "profile": "feedback",
                    "operators": ["audiofileinCHOP"],
                }
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/eval_brain_golden.py",
            "--cases",
            str(EVAL_PATH),
            "--trace-baseline",
            str(baseline_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["trace_replay"]["ok"] is False
    assert payload["trace_replay"]["drift_count"] == 1
    assert payload["trace_replay"]["drifts"][0]["case_id"] == "audio_feedback_panel_debug"


def test_eval_brain_golden_cli_writes_trace_baseline_that_replays_cleanly(tmp_path):
    baseline_path = tmp_path / "trace_baseline.json"

    write_proc = subprocess.run(
        [
            sys.executable,
            "scripts/eval_brain_golden.py",
            "--cases",
            str(EVAL_PATH),
            "--write-trace-baseline",
            str(baseline_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    write_payload = json.loads(write_proc.stdout)
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    assert write_payload["ok"] is True
    assert write_payload["trace_baseline"]["path"] == str(baseline_path)
    assert write_payload["trace_baseline"]["case_count"] == write_payload["case_count"]
    assert baseline["schema_version"] == 1
    assert baseline["case_count"] == write_payload["case_count"]
    assert baseline["traces"]["audio_feedback_panel_debug"]["profile"] == "concept_compiled"
    assert "feedbackTOP" in baseline["traces"]["audio_feedback_panel_debug"]["operators"]

    replay_proc = subprocess.run(
        [
            sys.executable,
            "scripts/eval_brain_golden.py",
            "--cases",
            str(EVAL_PATH),
            "--trace-baseline",
            str(baseline_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    replay_payload = json.loads(replay_proc.stdout)

    assert replay_payload["ok"] is True
    assert replay_payload["trace_replay"]["ok"] is True
    assert replay_payload["trace_replay"]["baseline_case_count"] == baseline["case_count"]
    assert replay_payload["trace_replay"]["drift_count"] == 0


# ---------------------------------------------------------------------------
# Param-gating polarity flip acceptance harness (param_value_coverage)
# ---------------------------------------------------------------------------


def test_param_values_match_handles_bools_numbers_lists_and_exprs():
    assert evals._param_values_match(True, True) is True
    # Guard against the Python `1 == True` pitfall: bools only match bools.
    assert evals._param_values_match(1, True) is False
    assert evals._param_values_match(True, 1) is False
    assert evals._param_values_match(0.92, 0.92) is True
    assert evals._param_values_match(80, 80.0) is True
    assert evals._param_values_match(0.92, 0.93) is False
    assert evals._param_values_match([0.0, 127.0], [0.0, 127.0]) is True
    assert evals._param_values_match([0.0, 127.0], [0.0, 1.0]) is False
    expr = {"expr": "op('/project1/out_chop')[0]"}
    assert evals._param_values_match(dict(expr), dict(expr)) is True
    assert evals._param_values_match({"expr": "absTime.seconds"}, dict(expr)) is False


@pytest.mark.asyncio
async def test_evaluate_case_scores_expected_param_values():
    cases = {case["id"]: case for case in load_golden_cases(EVAL_PATH)}
    case = cases["serial_dat_protocol_bridge"]

    result = await evaluate_case(case)

    assert result["checks"]["expected_param_values"]["ok"] is True
    assert result["param_value_metrics"]["carries_param_values"] is True
    assert result["param_value_metrics"]["expected_param_value_count"] == 2
    assert result["param_value_metrics"]["missing_expected_param_values"] == []


@pytest.mark.asyncio
async def test_evaluate_case_fails_when_expected_param_value_is_missing():
    cases = {case["id"]: case for case in load_golden_cases(EVAL_PATH)}
    case = dict(cases["serial_dat_protocol_bridge"])
    case["expected_param_values"] = [
        {"op_type": "serialDAT", "param": "format", "value": "not-the-planned-value"}
    ]

    result = await evaluate_case(case)

    assert result["checks"]["expected_param_values"]["ok"] is False
    assert result["passed"] is False
    assert result["param_value_metrics"]["missing_expected_param_values"] == [
        {"op_type": "serialDAT", "param": "format", "value": "not-the-planned-value"}
    ]


@pytest.mark.asyncio
async def test_evaluate_golden_cases_reports_param_value_coverage():
    report = await evaluate_golden_cases(EVAL_PATH)

    metrics = report["param_value_coverage"]

    assert metrics["ok"] is True
    assert metrics["eligible_case_count"] == report["case_count"] - 1  # one expected_blocked case
    assert metrics["coverage"] >= evals.MIN_PARAM_VALUE_COVERAGE
    assert metrics["carrying_case_count"] >= 70
    assert metrics["expected_param_value_case_count"] >= evals.MIN_EXPECTED_PARAM_VALUE_CASES
    assert metrics["expected_param_value_failure_count"] == 0
    assert metrics["expected_param_value_failure_case_ids"] == []


def test_aggregate_param_value_coverage_flags_regressions():
    def _result(case_id: str, *, carries: bool, expected: int = 0, missing: int = 0) -> dict:
        return {
            "id": case_id,
            "expected_blocked": False,
            "param_value_metrics": {
                "carries_param_values": carries,
                "param_value_count": 3 if carries else 0,
                "expected_param_value_count": expected,
                "missing_expected_param_values": [{"param": "x"}] * missing,
            },
        }

    healthy = evals._aggregate_param_value_coverage(
        [
            *[_result(f"carrying_{index}", carries=True, expected=1) for index in range(10)],
            _result("zero_param", carries=False),
            {"id": "blocked", "expected_blocked": True, "param_value_metrics": {}},
        ]
    )
    assert healthy["ok"] is True
    assert healthy["eligible_case_count"] == 11
    assert healthy["carrying_case_count"] == 10
    assert healthy["coverage"] == round(10 / 11, 4)
    assert healthy["zero_param_case_ids"] == ["zero_param"]

    # Regression to default-gray plans: coverage collapses below the floor.
    stripped = evals._aggregate_param_value_coverage(
        [
            *[_result(f"carrying_{index}", carries=True, expected=1) for index in range(10)],
            *[_result(f"zero_{index}", carries=False) for index in range(10)],
        ]
    )
    assert stripped["ok"] is False

    # A pinned expected value going missing fails the gate even at coverage 1.0.
    value_drift = evals._aggregate_param_value_coverage(
        [
            *[_result(f"carrying_{index}", carries=True, expected=1) for index in range(10)],
            _result("drifted", carries=True, expected=1, missing=1),
        ]
    )
    assert value_drift["ok"] is False
    assert value_drift["expected_param_value_failure_case_ids"] == ["drifted"]
