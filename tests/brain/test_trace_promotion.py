from __future__ import annotations

import json

import pytest

from td_mcp.brain.concept_compiler import build_candidate_graphs, compile_visual_task
from td_mcp.brain.patterns import load_pattern_registry
from td_mcp.models.brain import BrainPattern, BrainPlan, BrainTrace, ConceptGraph, VisualTaskSpec
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan


class FakeCardIndex:
    def __init__(self, known: set[str]):
        self.known = known

    def get_operator(self, op_type: str):
        if op_type in self.known:
            return {
                "op_type": op_type,
                "docs_url": f"https://docs.derivative.ca/{op_type}",
                "summary": f"{op_type} official docs",
            }
        return None


SEED_OPS = {
    "audiofileinCHOP",
    "analyzeCHOP",
    "mathCHOP",
    "nullCHOP",
    "noiseTOP",
    "feedbackTOP",
    "levelTOP",
    "compositeTOP",
    "nullTOP",
    "containerCOMP",
    "sliderCOMP",
    "buttonCOMP",
    "panelCHOP",
    "textDAT",
}

GLSL_TOP_OPS = {
    "constantTOP",
    "glslTOP",
    "textDAT",
    "nullTOP",
}


def _audio_feedback_plan() -> BrainPlan:
    task = VisualTaskSpec(
        intent="Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        validation_profile="structural_visual_safe",
    )
    compiled = compile_visual_task(
        task.intent,
        target_root=task.target_root,
        output_top=task.output_top,
        card_index=FakeCardIndex(SEED_OPS),
    )
    candidate = build_candidate_graphs(compiled, patterns=load_pattern_registry())[0]
    concept_graph = ConceptGraph(
        task=task,
        profile="concept_compiled",
        concepts=candidate.concepts,
        edges=candidate.edges,
        operators=candidate.required_ops,
        evidence=candidate.grounding_evidence,
        risk_flags=candidate.risk_flags,
    )
    patch_plan = PatchPlan(
        intent=task.intent,
        target_root=task.target_root,
        source="operations",
        operations=[],
        required_ops=candidate.required_ops,
        risk_flags=candidate.risk_flags,
        undo_label="trace promotion fixture",
        validation_plan=ValidationPlan(target_root=task.target_root),
    )
    return BrainPlan(
        task=task,
        concept_graph=concept_graph,
        patch_plan=patch_plan,
        compiled_task=compiled,
        candidate_graphs=[candidate],
        validation_profile="structural_visual_safe",
        grounding_evidence=candidate.grounding_evidence,
        risk_flags=candidate.risk_flags,
    )


def _successful_trace(plan: BrainPlan) -> BrainTrace:
    return BrainTrace(
        id="trace-audio-feedback-green",
        intent=plan.task.intent,
        profile="concept_compiled",
        target_root=plan.task.target_root,
        operators=plan.candidate_graphs[0].required_ops,
        plan_id=plan.id,
        transaction_id="tx-clean",
        transaction_status="clean",
        validation_ok=True,
        rollback_performed=False,
    )


def _successful_runtime_validation_report() -> dict[str, object]:
    return {
        "ok": True,
        "cheap_metrics": {
            "profile_probe_results": [
                {
                    "profile": "audio_reactive",
                    "probe_id": "audio_signal_activity",
                    "status": "runtime_pass",
                    "runtime_required": True,
                    "readback_path": "/project1/tdpilot_concept/out_chop",
                    "runtime_metric_values": {
                        "audio_analysis_channel_delta": 0.8,
                        "audio_analysis_channel_samples": 4,
                    },
                },
                {
                    "profile": "feedback",
                    "probe_id": "feedback_output_readback",
                    "status": "runtime_pass",
                    "runtime_required": True,
                    "readback_path": "/project1/tdpilot_concept/out1",
                    "runtime_metric_values": {
                        "feedback_output_luminance_mean": 0.25,
                        "feedback_output_luminance_max": 0.75,
                    },
                },
                {
                    "profile": "panel_ui",
                    "probe_id": "panel_state_readback",
                    "status": "runtime_pass",
                    "runtime_required": True,
                    "readback_path": "/project1/tdpilot_concept/out_chop",
                    "runtime_metric_values": {
                        "panel_state_channel_count": 2,
                        "panel_state_sample_count": 2,
                    },
                },
            ]
        },
    }


def _successful_runtime_validation_report_with_failed_optional_probe() -> dict[str, object]:
    report = _successful_runtime_validation_report()
    profile_results = report["cheap_metrics"]["profile_probe_results"]  # type: ignore[index]
    profile_results.append(
        {
            "profile": "visual",
            "probe_id": "cheap_visual_metrics",
            "status": "runtime_fail",
            "runtime_required": False,
            "readback_path": "/project1/tdpilot_concept/out1",
            "runtime_metric_values": {
                "luminance_mean": 0.0,
                "entropy": 0.0,
            },
        }
    )
    return report


def _glsl_top_plan() -> BrainPlan:
    task = VisualTaskSpec(
        intent="Build a GLSL TOP shader with source texture, shader DAT, stable TOP output, and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        validation_profile="structural_visual_safe",
    )
    compiled = compile_visual_task(
        task.intent,
        target_root=task.target_root,
        output_top=task.output_top,
        card_index=FakeCardIndex(GLSL_TOP_OPS),
    )
    candidate = build_candidate_graphs(compiled, patterns=load_pattern_registry())[0]
    concept_graph = ConceptGraph(
        task=task,
        profile="concept_compiled",
        concepts=candidate.concepts,
        edges=candidate.edges,
        operators=candidate.required_ops,
        evidence=candidate.grounding_evidence,
        risk_flags=candidate.risk_flags,
    )
    patch_plan = PatchPlan(
        intent=task.intent,
        target_root=task.target_root,
        source="operations",
        operations=[
            PatchOperation(
                kind="set_dat_content",
                target="/project1/text",
                args={
                    "text": (
                        "layout(location = 0) out vec4 fragColor;\n"
                        "void main() { fragColor = TDOutputSwizzle(vec4(1.0)); }\n"
                    ),
                    "generated_code": {
                        "block_id": "glsl_top_pixel_shader",
                        "language": "glsl",
                        "target_op": "/project1/glsl",
                        "target_param": "pixeldat",
                        "source_kind": "generated",
                        "source_refs": ["/project1/text"],
                        "code": (
                            "layout(location = 0) out vec4 fragColor;\n"
                            "void main() { fragColor = TDOutputSwizzle(vec4(1.0)); }\n"
                        ),
                        "static_checks": [
                            "glsl_no_version_line",
                            "glsl_top_declares_pixel_output",
                            "glsl_top_uses_td_output_swizzle",
                        ],
                        "runtime_checks": ["compile_state"],
                        "expected_outputs": ["/project1/out1"],
                        "risk_flags": ["validate-glsl-compile-state"],
                        "official_sources": ["https://docs.derivative.ca/GLSL_TOP"],
                    },
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/glsl",
                args={"params": {"pixeldat": "/project1/text"}},
            ),
        ],
        required_ops=candidate.required_ops,
        risk_flags=candidate.risk_flags,
        undo_label="trace promotion glsl fixture",
        validation_plan=ValidationPlan(target_root=task.target_root),
    )
    return BrainPlan(
        task=task,
        concept_graph=concept_graph,
        patch_plan=patch_plan,
        compiled_task=compiled,
        candidate_graphs=[candidate],
        validation_profile="structural_visual_safe",
        grounding_evidence=candidate.grounding_evidence,
        risk_flags=candidate.risk_flags,
    )


def _successful_glsl_trace(plan: BrainPlan) -> BrainTrace:
    return BrainTrace(
        id="trace-glsl-top-green",
        intent=plan.task.intent,
        profile="concept_compiled",
        target_root=plan.task.target_root,
        operators=plan.candidate_graphs[0].required_ops,
        plan_id=plan.id,
        transaction_id="tx-glsl-clean",
        transaction_status="clean",
        validation_ok=True,
        rollback_performed=False,
    )


def _successful_generated_code_runtime_validation_report() -> dict[str, object]:
    return {
        "ok": True,
        "cheap_metrics": {
            "generated_code_runtime": {
                "contract_count": 1,
                "checked_contract_count": 1,
                "evidence": [
                    {
                        "block_id": "glsl_top_pixel_shader",
                        "check_id": "compile_state",
                        "language": "glsl",
                        "target_op": "/project1/glsl",
                        "target_param": "pixeldat",
                        "expected_outputs": ["/project1/out1"],
                        "risk_flags": ["validate-glsl-compile-state"],
                        "official_sources": ["https://docs.derivative.ca/GLSL_TOP"],
                        "endpoint": "node/errors",
                        "status": "runtime_pass",
                        "issue_count": 0,
                    }
                ],
            }
        },
    }


def _failed_generated_code_runtime_validation_report() -> dict[str, object]:
    return {
        "ok": False,
        "cheap_metrics": {
            "generated_code_runtime": {
                "contract_count": 1,
                "checked_contract_count": 1,
                "evidence": [
                    {
                        "block_id": "glsl_top_pixel_shader",
                        "check_id": "compile_state",
                        "language": "glsl",
                        "target_op": "/project1/glsl",
                        "target_param": "pixeldat",
                        "expected_outputs": ["/project1/out1"],
                        "risk_flags": ["validate-glsl-compile-state"],
                        "official_sources": ["https://docs.derivative.ca/GLSL_TOP"],
                        "endpoint": "node/errors",
                        "status": "runtime_fail",
                        "issue_count": 1,
                    }
                ],
            }
        },
    }


def test_successful_brain_trace_promotes_to_docs_grounded_pattern_candidate():
    from td_mcp.brain.trace_promotion import promote_trace_to_pattern

    plan = _audio_feedback_plan()
    trace = _successful_trace(plan)

    pattern = promote_trace_to_pattern(
        plan,
        trace,
        pattern_registry=load_pattern_registry(),
        validation_report=_successful_runtime_validation_report(),
    )

    assert pattern.promoted_from_trace == "trace-audio-feedback-green"
    assert pattern.pattern_id.startswith("trace_audio_feedback_green_")
    assert pattern.profiles == ["audio_reactive", "feedback", "panel_ui"]
    assert {"audiofileinCHOP", "feedbackTOP", "panelCHOP", "textDAT"}.issubset(set(pattern.required_ops))
    assert {"audio_source_present", "feedback_cycle", "panel_components_present"}.issubset(
        set(pattern.validation_probes)
    )
    assert pattern.layout["runtime_validation"]["passed_probe_ids"] == [
        "audio_signal_activity",
        "feedback_output_readback",
        "panel_state_readback",
    ]
    assert pattern.layout["trace_support_count"] == 1
    assert pattern.layout["support_trace_ids"] == ["trace-audio-feedback-green"]
    assert pattern.layout["trace_fingerprint"].startswith("tracefp:")
    assert pattern.layout["operator_fingerprint"].startswith("ops:")
    assert pattern.layout["validation_fingerprint"].startswith("validation:")
    assert all(source.startswith("https://docs.derivative.ca/") for source in pattern.official_sources)


def test_trace_promotion_records_failed_optional_runtime_probes_for_later_demotions():
    from td_mcp.brain.trace_promotion import promote_trace_to_pattern

    plan = _audio_feedback_plan()
    trace = _successful_trace(plan)

    pattern = promote_trace_to_pattern(
        plan,
        trace,
        pattern_registry=load_pattern_registry(),
        validation_report=_successful_runtime_validation_report_with_failed_optional_probe(),
    )

    runtime = pattern.layout["runtime_validation"]
    assert runtime["passed_probe_ids"] == [
        "audio_signal_activity",
        "feedback_output_readback",
        "panel_state_readback",
    ]
    assert runtime["failed_probe_ids"] == ["cheap_visual_metrics"]
    assert runtime["failed_probe_statuses"] == {"cheap_visual_metrics": "runtime_fail"}
    assert runtime["failed_optional_probe_ids"] == ["cheap_visual_metrics"]
    assert runtime["confidence_decay"] == 0.94
    assert runtime["confidence_penalty_reasons"] == ["failed_optional_probe:cheap_visual_metrics"]


def test_trace_promotion_records_failed_runtime_probe_without_required_runtime_promotions():
    from td_mcp.brain.trace_promotion import promote_trace_to_pattern

    plan = _audio_feedback_plan()
    candidate = plan.candidate_graphs[0].model_copy(
        update={
            "pattern_ids": ["visual_optional_runtime_only"],
            "validation_needs": ["cheap_visual_metrics"],
        }
    )
    plan = plan.model_copy(update={"candidate_graphs": [candidate]})
    trace = _successful_trace(plan)
    visual_pattern = BrainPattern(
        pattern_id="visual_optional_runtime_only",
        title="Visual optional runtime probe fixture",
        profiles=list(candidate.profiles),
        required_ops=list(candidate.required_ops),
        concept_nodes=list(candidate.concepts),
        concept_edges=list(candidate.edges),
        validation_probes=["cheap_visual_metrics"],
        official_sources=["https://docs.derivative.ca/Null_TOP"],
    )
    validation_report = {
        "ok": False,
        "cheap_metrics": {
            "profile_probe_results": [
                {
                    "profile": "visual",
                    "probe_id": "cheap_visual_metrics",
                    "status": "runtime_fail",
                    "runtime_required": False,
                    "readback_path": "/project1/tdpilot_concept/out1",
                    "issue_code": "cheap_visual_metrics_black_frame",
                    "runtime_metric_values": {
                        "luminance_mean": 0.0,
                        "entropy": 0.0,
                    },
                }
            ]
        },
    }

    pattern = promote_trace_to_pattern(
        plan,
        trace,
        pattern_registry=[visual_pattern],
        validation_report=validation_report,
    )

    runtime = pattern.layout["runtime_validation"]
    assert runtime["required_probe_ids"] == []
    assert runtime["passed_probe_ids"] == []
    assert runtime["failed_probe_ids"] == ["cheap_visual_metrics"]
    assert runtime["failed_probe_statuses"] == {"cheap_visual_metrics": "runtime_fail"}
    assert runtime["failed_optional_probe_ids"] == ["cheap_visual_metrics"]
    assert runtime["confidence_decay"] == 0.94
    assert runtime["confidence_penalty_reasons"] == ["failed_optional_probe:cheap_visual_metrics"]
    assert runtime["failed_probe_details"] == {
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
    }


def test_brain_tool_profile_layers_include_selected_compiler_candidate_profiles():
    from td_mcp import tool_registry as _tool_registry  # noqa: F401
    from td_mcp.registry import tools_brain

    plan = _audio_feedback_plan()

    assert tools_brain._concept_profiles_for_brain_plan(plan) == [
        "audio_reactive",
        "feedback",
        "panel_ui",
        "concept_compiled",
    ]


def test_trace_promotion_blocks_rolled_back_or_unvalidated_transactions():
    from td_mcp.brain.trace_promotion import promote_trace_to_pattern

    plan = _audio_feedback_plan()
    trace = _successful_trace(plan).model_copy(
        update={
            "transaction_status": "rolled_back",
            "validation_ok": False,
            "rollback_performed": True,
        }
    )

    with pytest.raises(ValueError, match="validation_ok must be true"):
        promote_trace_to_pattern(
            plan,
            trace,
            pattern_registry=load_pattern_registry(),
            validation_report=_successful_runtime_validation_report(),
        )


def test_trace_promotion_blocks_when_official_docs_grounding_is_missing():
    from td_mcp.brain.trace_promotion import promote_trace_to_pattern

    plan = _audio_feedback_plan()
    trace = _successful_trace(plan)

    with pytest.raises(ValueError, match="official Derivative docs"):
        promote_trace_to_pattern(
            plan,
            trace,
            pattern_registry=[],
            validation_report=_successful_runtime_validation_report(),
        )


def test_trace_promotion_blocks_when_required_runtime_probe_evidence_is_missing():
    from td_mcp.brain.trace_promotion import promote_trace_to_pattern

    plan = _audio_feedback_plan()
    trace = _successful_trace(plan)

    with pytest.raises(ValueError, match="missing runtime validation passes"):
        promote_trace_to_pattern(
            plan,
            trace,
            pattern_registry=load_pattern_registry(),
            validation_report={"ok": True, "cheap_metrics": {"profile_probe_results": []}},
        )


def test_trace_promotion_rejection_records_missing_runtime_probe_details():
    from td_mcp.brain.trace_promotion import trace_promotion_rejection_evidence

    plan = _audio_feedback_plan()
    trace = _successful_trace(plan)
    validation_report = _successful_runtime_validation_report()
    profile_results = validation_report["cheap_metrics"]["profile_probe_results"]  # type: ignore[index]
    profile_results[1] = {
        "profile": "feedback",
        "probe_id": "feedback_output_readback",
        "status": "runtime_contract_present",
        "runtime_required": True,
        "readback_strategy": "top_luminance_runtime",
        "metric_names": ["feedback_output_luminance_mean", "feedback_output_luminance_max"],
        "present_required_inputs": ["feedbackTOP", "nullTOP"],
        "missing_required_inputs": [],
        "pending_metric_names": ["feedback_output_luminance_mean", "feedback_output_luminance_max"],
        "failure_message": "Feedback plans require runtime evidence that the stable TOP output is visible.",
    }

    evidence = trace_promotion_rejection_evidence(
        plan,
        trace,
        pattern_registry=load_pattern_registry(),
        validation_report=validation_report,
    )

    assert evidence is not None
    assert evidence["trace_fingerprints"]["trace_fingerprint"].startswith("tracefp:")
    runtime_issues = evidence["runtime_validation_issues"]
    assert runtime_issues["missing_probe_ids"] == ["feedback_output_readback"]
    assert runtime_issues["failed_required_probe_ids"] == ["feedback_output_readback"]
    assert runtime_issues["confidence_decay"] == 0.74
    assert runtime_issues["confidence_penalty_reasons"] == [
        "missing_required_probe:feedback_output_readback",
        "failed_required_probe:feedback_output_readback",
    ]
    assert runtime_issues["missing_probe_details"] == {
        "feedback_output_readback": {
            "profile": "feedback",
            "status": "runtime_contract_present",
            "failure_message": "Feedback plans require runtime evidence that the stable TOP output is visible.",
            "readback_strategy": "top_luminance_runtime",
            "runtime_required": True,
            "missing_required_inputs": [],
            "present_required_inputs": ["feedbackTOP", "nullTOP"],
            "pending_metric_names": [
                "feedback_output_luminance_mean",
                "feedback_output_luminance_max",
            ],
            "metric_names": [
                "feedback_output_luminance_mean",
                "feedback_output_luminance_max",
            ],
        }
    }


def test_trace_promotion_blocks_generated_code_without_runtime_contract_passes():
    from td_mcp.brain.trace_promotion import promote_trace_to_pattern

    plan = _glsl_top_plan()
    trace = _successful_glsl_trace(plan)

    with pytest.raises(ValueError, match="generated code runtime validation"):
        promote_trace_to_pattern(
            plan,
            trace,
            pattern_registry=load_pattern_registry(),
            validation_report={"ok": True, "cheap_metrics": {}},
        )


def test_trace_promotion_rejection_records_generated_code_runtime_failure_details():
    from td_mcp.brain.trace_promotion import trace_promotion_rejection_evidence

    plan = _glsl_top_plan()
    trace = _successful_glsl_trace(plan)

    evidence = trace_promotion_rejection_evidence(
        plan,
        trace,
        pattern_registry=load_pattern_registry(),
        validation_report=_failed_generated_code_runtime_validation_report(),
    )

    assert evidence is not None
    assert evidence["trace_fingerprints"]["trace_fingerprint"].startswith("tracefp:")
    assert evidence["blockers"] == [
        "missing generated code runtime validation passes: glsl_top_pixel_shader:compile_state"
    ]
    generated_code_issues = evidence["generated_code_runtime_issues"]
    assert generated_code_issues["missing_contract_ids"] == ["glsl_top_pixel_shader:compile_state"]
    assert generated_code_issues["failed_contract_ids"] == ["glsl_top_pixel_shader:compile_state"]
    assert generated_code_issues["failed_contract_statuses"] == {
        "glsl_top_pixel_shader:compile_state": "runtime_fail"
    }
    assert generated_code_issues["confidence_decay"] == 0.66
    assert generated_code_issues["confidence_penalty_reasons"] == [
        "missing_generated_code_contract:glsl_top_pixel_shader:compile_state",
        "failed_generated_code_contract:glsl_top_pixel_shader:compile_state",
    ]
    assert generated_code_issues["failed_contract_details"] == {
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
    }


def test_generated_code_trace_promotion_records_runtime_contract_passes():
    from td_mcp.brain.trace_promotion import promote_trace_to_pattern

    plan = _glsl_top_plan()
    trace = _successful_glsl_trace(plan)

    pattern = promote_trace_to_pattern(
        plan,
        trace,
        pattern_registry=load_pattern_registry(),
        validation_report=_successful_generated_code_runtime_validation_report(),
    )

    assert pattern.promoted_from_trace == "trace-glsl-top-green"
    assert pattern.layout["runtime_validation"]["generated_code_passed_contract_ids"] == [
        "glsl_top_pixel_shader:compile_state"
    ]
    assert pattern.layout["runtime_validation"]["generated_code_readback_targets"] == {
        "glsl_top_pixel_shader:compile_state": "/project1/glsl"
    }


def test_promoted_trace_pattern_becomes_ranked_resolver_candidate():
    from td_mcp.brain.pattern_resolver import resolve_candidate_graphs
    from td_mcp.brain.trace_promotion import promote_trace_to_pattern

    plan = _audio_feedback_plan()
    trace = _successful_trace(plan)
    promoted = promote_trace_to_pattern(
        plan,
        trace,
        pattern_registry=load_pattern_registry(),
        validation_report=_successful_runtime_validation_report(),
    )

    candidates = resolve_candidate_graphs(
        plan.compiled_task,
        patterns=[*load_pattern_registry(), promoted],
        available_ops=SEED_OPS,
    )

    assert candidates[0].pattern_ids == [promoted.pattern_id]
    assert f"trace-promoted:{trace.id}" in candidates[0].grounding_evidence
    assert f"trace-fingerprint:{promoted.layout['trace_fingerprint']}" in candidates[0].grounding_evidence
    assert "trace-support:1" in candidates[0].grounding_evidence
    assert candidates[0].score <= 1.0
    assert candidates[0].score > next(
        candidate.score for candidate in candidates if "audio_file_to_analysis_chop" in candidate.pattern_ids
    )


def test_failed_required_runtime_probe_demotes_trace_pattern_candidate():
    from td_mcp.brain.pattern_resolver import resolve_candidate_graphs
    from td_mcp.brain.trace_promotion import promote_trace_to_pattern

    plan = _audio_feedback_plan()
    trace = _successful_trace(plan)
    promoted = promote_trace_to_pattern(
        plan,
        trace,
        pattern_registry=load_pattern_registry(),
        validation_report=_successful_runtime_validation_report(),
    )
    promoted = promoted.model_copy(
        update={
            "layout": {
                **promoted.layout,
                "runtime_validation": {
                    **promoted.layout["runtime_validation"],
                    "passed_probe_ids": [
                        "audio_signal_activity",
                        "panel_state_readback",
                    ],
                    "failed_probe_ids": ["feedback_output_readback"],
                    "failed_probe_statuses": {
                        "feedback_output_readback": "runtime_failed",
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
                        }
                    },
                },
            }
        }
    )

    candidates = resolve_candidate_graphs(
        plan.compiled_task,
        patterns=[*load_pattern_registry(), promoted],
        available_ops=SEED_OPS,
    )

    failed_trace_candidate = next(
        candidate for candidate in candidates if candidate.pattern_ids == [promoted.pattern_id]
    )
    registry_candidate = next(
        candidate for candidate in candidates if "audio_file_to_analysis_chop" in candidate.pattern_ids
    )
    assert failed_trace_candidate.score < registry_candidate.score
    assert "runtime-validation-failed-required" in failed_trace_candidate.risk_flags
    assert (
        f"runtime-validation-failed-required:{promoted.pattern_id}:feedback_output_readback"
        in failed_trace_candidate.grounding_evidence
    )
    assert (
        "runtime-validation-failed-detail:"
        f"{promoted.pattern_id}:feedback_output_readback:"
        "profile_probe_runtime_feedback_output_missing"
    ) in failed_trace_candidate.grounding_evidence
    assert "runtime_validation_failed_required:1" in failed_trace_candidate.explanation


def test_failed_optional_runtime_probe_decay_demotes_promoted_trace_candidate():
    from td_mcp.brain.pattern_resolver import resolve_candidate_graphs
    from td_mcp.brain.trace_promotion import promote_trace_to_pattern

    plan = _audio_feedback_plan()
    trace = _successful_trace(plan)
    promoted = promote_trace_to_pattern(
        plan,
        trace,
        pattern_registry=load_pattern_registry(),
        validation_report=_successful_runtime_validation_report_with_failed_optional_probe(),
    )

    candidates = resolve_candidate_graphs(
        plan.compiled_task,
        patterns=[*load_pattern_registry(), promoted],
        available_ops=SEED_OPS,
    )

    failed_trace_candidate = next(
        candidate for candidate in candidates if candidate.pattern_ids == [promoted.pattern_id]
    )
    registry_candidate = next(
        candidate for candidate in candidates if "audio_file_to_analysis_chop" in candidate.pattern_ids
    )
    assert failed_trace_candidate.score < registry_candidate.score
    assert "runtime-validation-failed" in failed_trace_candidate.risk_flags
    assert (
        f"runtime-validation-failed:{promoted.pattern_id}:cheap_visual_metrics:runtime_fail"
        in failed_trace_candidate.grounding_evidence
    )
    assert (
        f"runtime-validation-decay:{promoted.pattern_id}:0.9400" in failed_trace_candidate.grounding_evidence
    )
    assert (
        f"runtime-validation-score:{promoted.pattern_id}:3.2900" in failed_trace_candidate.grounding_evidence
    )
    assert "runtime_validation_score:3.2900" in failed_trace_candidate.explanation
    assert "runtime_validation_failed:1" in failed_trace_candidate.explanation


def test_missing_required_runtime_probe_detail_is_ranked_grounding_evidence():
    from td_mcp.brain.pattern_resolver import resolve_candidate_graphs
    from td_mcp.brain.trace_promotion import promote_trace_to_pattern

    plan = _audio_feedback_plan()
    trace = _successful_trace(plan)
    promoted = promote_trace_to_pattern(
        plan,
        trace,
        pattern_registry=load_pattern_registry(),
        validation_report=_successful_runtime_validation_report(),
    )
    promoted = promoted.model_copy(
        update={
            "layout": {
                **promoted.layout,
                "runtime_validation": {
                    **promoted.layout["runtime_validation"],
                    "passed_probe_ids": [
                        "audio_signal_activity",
                        "panel_state_readback",
                    ],
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
                },
            }
        }
    )

    candidates = resolve_candidate_graphs(
        plan.compiled_task,
        patterns=[*load_pattern_registry(), promoted],
        available_ops=SEED_OPS,
    )

    missing_trace_candidate = next(
        candidate for candidate in candidates if candidate.pattern_ids == [promoted.pattern_id]
    )
    assert "runtime-validation-missing" in missing_trace_candidate.risk_flags
    assert (
        f"runtime-validation-missing:{promoted.pattern_id}:feedback_output_readback"
        in missing_trace_candidate.grounding_evidence
    )
    assert (
        "runtime-validation-missing-detail:"
        f"{promoted.pattern_id}:feedback_output_readback:top_luminance_runtime"
    ) in missing_trace_candidate.grounding_evidence
    assert (
        "runtime-validation-missing-status:"
        f"{promoted.pattern_id}:feedback_output_readback:runtime_contract_present"
    ) in missing_trace_candidate.grounding_evidence
    assert "runtime_validation_missing:1" in missing_trace_candidate.explanation


def test_clustered_trace_pattern_gets_support_evidence_and_rank_boost():
    from td_mcp.brain.pattern_resolver import resolve_candidate_graphs
    from td_mcp.brain.trace_promotion import promote_trace_to_pattern

    plan = _audio_feedback_plan()
    trace = _successful_trace(plan)
    promoted = promote_trace_to_pattern(
        plan,
        trace,
        pattern_registry=load_pattern_registry(),
        validation_report=_successful_runtime_validation_report(),
    )
    promoted = promoted.model_copy(
        update={
            "layout": {
                **promoted.layout,
                "trace_support_count": 4,
                "support_trace_ids": [
                    "trace-audio-feedback-green",
                    "trace-audio-feedback-green-2",
                    "trace-audio-feedback-green-3",
                    "trace-audio-feedback-green-4",
                ],
            }
        }
    )

    candidates = resolve_candidate_graphs(
        plan.compiled_task,
        patterns=[*load_pattern_registry(), promoted],
        available_ops=SEED_OPS,
    )

    assert candidates[0].pattern_ids == [promoted.pattern_id]
    assert "trace-support:4" in candidates[0].grounding_evidence
    assert f"trace-fingerprint:{promoted.layout['trace_fingerprint']}" in candidates[0].grounding_evidence
    assert "trace_support:4" in candidates[0].explanation


def test_repeated_trace_rejections_feed_clustered_runtime_demotion_audit(tmp_path):
    from td_mcp.brain.pattern_resolver import resolve_candidate_graphs
    from td_mcp.brain.trace_promotion import promote_trace_to_pattern
    from td_mcp.brain.traces import promoted_patterns_from_traces

    plan = _audio_feedback_plan()
    trace = _successful_trace(plan)
    promoted = promote_trace_to_pattern(
        plan,
        trace,
        pattern_registry=load_pattern_registry(),
        validation_report=_successful_runtime_validation_report(),
    )
    trace_fingerprint = promoted.layout["trace_fingerprint"]

    def rejection_record(trace_id: str) -> dict[str, object]:
        trace_payload = trace.model_dump(mode="json")
        trace_payload["id"] = trace_id
        return {
            "schema_version": 1,
            "type": "brain_execution",
            "trace": trace_payload,
            "trace_promotion_rejection": {
                "blockers": [
                    "missing runtime validation passes: feedback_output_readback",
                    "failed required runtime validation probes: feedback_output_readback",
                ],
                "trace_fingerprints": {"trace_fingerprint": trace_fingerprint},
                "runtime_validation_issues": {
                    "missing_probe_ids": ["feedback_output_readback"],
                    "missing_probe_details": {
                        "feedback_output_readback": {
                            "profile": "feedback",
                            "status": "runtime_contract_present",
                            "readback_strategy": "top_luminance_runtime",
                        }
                    },
                    "failed_required_probe_ids": ["feedback_output_readback"],
                    "failed_probe_ids": ["feedback_output_readback"],
                    "failed_probe_statuses": {
                        "feedback_output_readback": "runtime_failed",
                    },
                    "failed_required_probe_details": {
                        "feedback_output_readback": {
                            "profile": "feedback",
                            "status": "runtime_failed",
                            "issue_code": "profile_probe_runtime_feedback_output_missing",
                            "readback_path": "/project1/tdpilot_concept/out1",
                        }
                    },
                    "failed_probe_details": {
                        "feedback_output_readback": {
                            "profile": "feedback",
                            "status": "runtime_failed",
                            "issue_code": "profile_probe_runtime_feedback_output_missing",
                            "readback_path": "/project1/tdpilot_concept/out1",
                        }
                    },
                },
            },
        }

    trace_path = tmp_path / "brain_traces.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": 1,
                        "type": "brain_execution",
                        "promoted_pattern_candidate": promoted.model_dump(mode="json"),
                    }
                ),
                json.dumps(rejection_record("trace-audio-feedback-reject-a")),
                json.dumps(rejection_record("trace-audio-feedback-reject-b")),
            ]
        ),
        encoding="utf-8",
    )

    patterns = promoted_patterns_from_traces(trace_path)

    assert [pattern.pattern_id for pattern in patterns] == [promoted.pattern_id]
    clustered = patterns[0]
    runtime = clustered.layout["runtime_validation"]
    replay = runtime["aggregated_replay_validation"]
    assert replay["trace_ids"] == [
        "trace-audio-feedback-reject-a",
        "trace-audio-feedback-reject-b",
    ]
    assert replay["missing_probe_counts"] == {"feedback_output_readback": 2}
    assert replay["failed_probe_counts"] == {"feedback_output_readback": 2}
    assert replay["failed_required_probe_counts"] == {"feedback_output_readback": 2}
    assert "feedback_output_readback" in runtime["missing_probe_ids"]
    assert "feedback_output_readback" in runtime["failed_probe_ids"]

    candidates = resolve_candidate_graphs(
        plan.compiled_task,
        patterns=[*load_pattern_registry(), clustered],
        available_ops=SEED_OPS,
    )

    trace_candidate = next(
        candidate for candidate in candidates if candidate.pattern_ids == [clustered.pattern_id]
    )
    registry_candidate = next(
        candidate for candidate in candidates if "audio_file_to_analysis_chop" in candidate.pattern_ids
    )
    assert trace_candidate.score < registry_candidate.score
    assert "runtime-validation-missing" in trace_candidate.risk_flags
    assert "runtime-validation-failed-required" in trace_candidate.risk_flags
    assert (
        f"runtime-validation-replay-aggregate:{clustered.pattern_id}:missing:feedback_output_readback:2"
    ) in trace_candidate.grounding_evidence
    assert (
        "runtime-validation-replay-aggregate:"
        f"{clustered.pattern_id}:failed-required:feedback_output_readback:2"
    ) in trace_candidate.grounding_evidence


def test_successful_trace_export_includes_promoted_pattern_candidate(monkeypatch):
    from td_mcp import tool_registry as _tool_registry  # noqa: F401
    from td_mcp.registry import tools_brain

    plan = _audio_feedback_plan()
    trace = _successful_trace(plan)
    captured: dict[str, object] = {}

    def fake_append(record):
        captured.update(record)
        return "/tmp/brain_traces.jsonl"

    monkeypatch.setattr(tools_brain, "append_brain_trace", fake_append)

    path = tools_brain._export_trace_safely(
        brain_plan=plan,
        tx_result={
            "status": "clean",
            "validation_failed": False,
            "rollback_performed": False,
            "validation_report": _successful_runtime_validation_report(),
        },
        trace=trace.model_dump(mode="json"),
        learned_id=None,
        duration_ms=1.0,
    )

    assert path == "/tmp/brain_traces.jsonl"
    promoted = captured["promoted_pattern_candidate"]
    assert promoted["promoted_from_trace"] == trace.id
    assert promoted["pattern_id"].startswith("trace_audio_feedback_green_")
    assert {"audiofileinCHOP", "feedbackTOP", "panelCHOP"}.issubset(set(promoted["required_ops"]))
    assert promoted["layout"]["runtime_validation"]["passed_probe_ids"] == [
        "audio_signal_activity",
        "feedback_output_readback",
        "panel_state_readback",
    ]


def test_trace_export_skips_promoted_pattern_candidate_without_runtime_probe_passes(monkeypatch):
    from td_mcp import tool_registry as _tool_registry  # noqa: F401
    from td_mcp.registry import tools_brain

    plan = _audio_feedback_plan()
    trace = _successful_trace(plan)
    captured: dict[str, object] = {}

    def fake_append(record):
        captured.update(record)
        return "/tmp/brain_traces.jsonl"

    monkeypatch.setattr(tools_brain, "append_brain_trace", fake_append)

    path = tools_brain._export_trace_safely(
        brain_plan=plan,
        tx_result={
            "status": "clean",
            "validation_failed": False,
            "rollback_performed": False,
            "validation_report": {"ok": True},
        },
        trace=trace.model_dump(mode="json"),
        learned_id=None,
        duration_ms=1.0,
    )

    assert path == "/tmp/brain_traces.jsonl"
    assert captured["promoted_pattern_candidate"] is None
    rejection = dict(captured["trace_promotion_rejection"])
    fingerprints = rejection.pop("trace_fingerprints")
    assert fingerprints["trace_fingerprint"].startswith("tracefp:")
    assert rejection == {
        "blockers": [
            (
                "missing runtime validation passes: "
                "audio_signal_activity, feedback_output_readback, panel_state_readback"
            )
        ],
        "runtime_validation_issues": {
            "missing_probe_ids": [
                "audio_signal_activity",
                "feedback_output_readback",
                "panel_state_readback",
            ],
            "failed_probe_ids": [],
            "failed_probe_statuses": {},
            "missing_probe_details": {
                "audio_signal_activity": {
                    "status": "runtime_missing",
                    "issue_code": "runtime_probe_pass_missing",
                    "issue_message": "audio_signal_activity did not produce a runtime_pass result.",
                },
                "feedback_output_readback": {
                    "status": "runtime_missing",
                    "issue_code": "runtime_probe_pass_missing",
                    "issue_message": "feedback_output_readback did not produce a runtime_pass result.",
                },
                "panel_state_readback": {
                    "status": "runtime_missing",
                    "issue_code": "runtime_probe_pass_missing",
                    "issue_message": "panel_state_readback did not produce a runtime_pass result.",
                },
            },
            "confidence_decay": 0.76,
            "confidence_penalty_reasons": [
                "missing_required_probe:audio_signal_activity",
                "missing_required_probe:feedback_output_readback",
                "missing_required_probe:panel_state_readback",
            ],
        },
    }


def test_trace_export_records_failed_required_runtime_probe_details(monkeypatch):
    from td_mcp import tool_registry as _tool_registry  # noqa: F401
    from td_mcp.registry import tools_brain

    plan = _audio_feedback_plan()
    trace = _successful_trace(plan)
    validation_report = _successful_runtime_validation_report()
    profile_results = validation_report["cheap_metrics"]["profile_probe_results"]  # type: ignore[index]
    profile_results[1] = {
        "profile": "feedback",
        "probe_id": "feedback_output_readback",
        "status": "runtime_failed",
        "runtime_required": True,
        "issue_code": "profile_probe_runtime_feedback_output_missing",
        "readback_path": "/project1/tdpilot_concept/out1",
        "runtime_metric_values": {
            "feedback_output_luminance_mean": 0.0,
            "feedback_output_luminance_max": 0.0,
        },
    }
    captured: dict[str, object] = {}

    def fake_append(record):
        captured.update(record)
        return "/tmp/brain_traces.jsonl"

    monkeypatch.setattr(tools_brain, "append_brain_trace", fake_append)

    path = tools_brain._export_trace_safely(
        brain_plan=plan,
        tx_result={
            "status": "clean",
            "validation_failed": True,
            "rollback_performed": False,
            "validation_report": validation_report,
        },
        trace=trace.model_dump(mode="json"),
        learned_id=None,
        duration_ms=1.0,
    )

    assert path == "/tmp/brain_traces.jsonl"
    assert captured["promoted_pattern_candidate"] is None
    assert captured["trace_promotion_rejection"]["blockers"] == [  # type: ignore[index]
        "missing runtime validation passes: feedback_output_readback",
        "failed required runtime validation probes: feedback_output_readback",
    ]
    fingerprints = captured["trace_promotion_rejection"]["trace_fingerprints"]  # type: ignore[index]
    assert fingerprints["trace_fingerprint"].startswith("tracefp:")
    runtime_issues = captured["trace_promotion_rejection"]["runtime_validation_issues"]  # type: ignore[index]
    assert runtime_issues["failed_required_probe_ids"] == ["feedback_output_readback"]
    assert runtime_issues["failed_probe_ids"] == ["feedback_output_readback"]
    assert runtime_issues["failed_probe_statuses"] == {"feedback_output_readback": "runtime_failed"}
    assert runtime_issues["confidence_decay"] == 0.74
    assert runtime_issues["confidence_penalty_reasons"] == [
        "missing_required_probe:feedback_output_readback",
        "failed_required_probe:feedback_output_readback",
    ]
    assert runtime_issues["failed_required_probe_details"] == {
        "feedback_output_readback": {
            "profile": "feedback",
            "status": "runtime_failed",
            "issue_code": "profile_probe_runtime_feedback_output_missing",
            "readback_path": "/project1/tdpilot_concept/out1",
            "runtime_required": True,
            "runtime_metric_values": {
                "feedback_output_luminance_mean": 0.0,
                "feedback_output_luminance_max": 0.0,
            },
        }
    }
    assert runtime_issues["failed_probe_details"] == {
        "feedback_output_readback": {
            "profile": "feedback",
            "status": "runtime_failed",
            "issue_code": "profile_probe_runtime_feedback_output_missing",
            "readback_path": "/project1/tdpilot_concept/out1",
            "runtime_required": True,
            "runtime_metric_values": {
                "feedback_output_luminance_mean": 0.0,
                "feedback_output_luminance_max": 0.0,
            },
        }
    }
