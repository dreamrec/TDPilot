from __future__ import annotations

import json

import pytest

from td_mcp.brain.traces import (
    append_brain_trace,
    promoted_patterns_from_traces,
    read_brain_traces,
    replay_brain_trace,
)
from td_mcp.models.brain import BrainPattern


def _promoted_audio_feedback_pattern() -> BrainPattern:
    return BrainPattern(
        pattern_id="trace_audio_feedback_green_audio_feedback_panel",
        title="Promoted Audio Feedback Panel",
        intent_tags=[
            "audio_analysis",
            "feedback_loop",
            "panel_controls",
            "debug_output",
        ],
        profiles=["audio_reactive", "feedback", "panel_ui"],
        required_ops=[
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
        ],
        concept_nodes=[
            {
                "id": "audio_source",
                "label": "Audio source",
                "role": "source",
                "domain": "CHOP",
                "op_type": "audiofileinCHOP",
            },
            {
                "id": "feedback_visual",
                "label": "Feedback visual",
                "role": "feedback",
                "domain": "TOP",
                "op_type": "feedbackTOP",
            },
            {
                "id": "panel_controls",
                "label": "Panel controls",
                "role": "control",
                "domain": "COMP",
                "op_type": "containerCOMP",
            },
            {
                "id": "debug_notes",
                "label": "Debug notes",
                "role": "validator",
                "domain": "DAT",
                "op_type": "textDAT",
            },
        ],
        concept_edges=[],
        layout={
            "source": "trace_promotion",
            "trace_fingerprint": "tracefp:audio-feedback-panel",
            "operator_fingerprint": "ops:audio-feedback-panel",
            "validation_fingerprint": "validation:audio-feedback-panel",
            "trace_support_count": 1,
            "support_trace_ids": ["trace-audio-feedback-green"],
            "runtime_validation": {
                "required_probe_ids": [
                    "audio_signal_activity",
                    "feedback_output_readback",
                    "panel_state_readback",
                ],
                "passed_probe_ids": [
                    "audio_signal_activity",
                    "feedback_output_readback",
                    "panel_state_readback",
                ],
                "readback_paths": {
                    "audio_signal_activity": "/project1/out_chop",
                    "feedback_output_readback": "/project1/out1",
                    "panel_state_readback": "/project1/out_chop",
                },
            },
        },
        debug_outputs=[{"node": "debug_notes", "domain": "DAT"}],
        validation_profile="structural_visual_safe",
        validation_probes=[
            "audio_signal_activity",
            "feedback_output_readback",
            "panel_state_readback",
        ],
        rollback_risks=["trace-promoted-pattern"],
        official_sources=[
            "https://docs.derivative.ca/Audio_File_In_CHOP",
            "https://docs.derivative.ca/Feedback_TOP",
            "https://docs.derivative.ca/Panel_CHOP",
            "https://docs.derivative.ca/Text_DAT",
        ],
        promoted_from_trace="trace-audio-feedback-green",
    )


def test_append_brain_trace_writes_jsonl(tmp_path):
    trace_path = tmp_path / "brain_traces.jsonl"

    written = append_brain_trace(
        {
            "type": "brain_execution",
            "intent": "feedback trail",
            "transaction": {"status": "clean"},
        },
        path=trace_path,
    )

    assert written == str(trace_path)
    lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["schema_version"] == 1
    assert payload["type"] == "brain_execution"
    assert payload["transaction"]["status"] == "clean"


def test_read_brain_traces_ignores_blank_lines(tmp_path):
    trace_path = tmp_path / "brain_traces.jsonl"
    trace_path.write_text('\n{"schema_version": 1, "type": "brain_execution", "intent": "build feedback"}\n')

    traces = read_brain_traces(trace_path)

    assert len(traces) == 1
    assert traces[0]["intent"] == "build feedback"


def test_promoted_patterns_from_traces_loads_valid_docs_grounded_candidates(tmp_path):
    trace_path = tmp_path / "brain_traces.jsonl"
    promoted = _promoted_audio_feedback_pattern()
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
                json.dumps(
                    {
                        "schema_version": 1,
                        "type": "brain_execution",
                        "promoted_pattern_candidate": {
                            **promoted.model_dump(mode="json"),
                            "pattern_id": "invalid_unofficial_pattern",
                            "official_sources": ["https://example.com/not-derivative"],
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    patterns = promoted_patterns_from_traces(trace_path)

    assert [pattern.pattern_id for pattern in patterns] == ["trace_audio_feedback_green_audio_feedback_panel"]
    assert patterns[0].promoted_from_trace == "trace-audio-feedback-green"
    assert patterns[0].required_ops == promoted.required_ops
    assert all(source.startswith("https://docs.derivative.ca/") for source in patterns[0].official_sources)


def test_promoted_patterns_from_traces_clusters_runtime_verified_memories(tmp_path):
    trace_path = tmp_path / "brain_traces.jsonl"
    base = _promoted_audio_feedback_pattern()
    runtime_validation = {
        "required_probe_ids": ["audio_signal_activity", "feedback_output_readback"],
        "passed_probe_ids": ["audio_signal_activity", "feedback_output_readback"],
        "readback_paths": {
            "audio_signal_activity": "/project1/out_chop",
            "feedback_output_readback": "/project1/out1",
        },
    }
    first = base.model_copy(
        update={
            "pattern_id": "trace_audio_feedback_green_a",
            "promoted_from_trace": "trace-audio-feedback-green-a",
            "layout": {
                "source": "trace_promotion",
                "trace_fingerprint": "tracefp:audio-feedback-panel",
                "operator_fingerprint": "ops:audio-feedback-panel",
                "validation_fingerprint": "validation:audio-feedback-panel",
                "trace_support_count": 1,
                "support_trace_ids": ["trace-audio-feedback-green-a"],
                "runtime_validation": runtime_validation,
            },
        }
    )
    second = base.model_copy(
        update={
            "pattern_id": "trace_audio_feedback_green_b",
            "promoted_from_trace": "trace-audio-feedback-green-b",
            "layout": {
                "source": "trace_promotion",
                "trace_fingerprint": "tracefp:audio-feedback-panel",
                "operator_fingerprint": "ops:audio-feedback-panel",
                "validation_fingerprint": "validation:audio-feedback-panel",
                "trace_support_count": 1,
                "support_trace_ids": ["trace-audio-feedback-green-b"],
                "runtime_validation": runtime_validation,
            },
        }
    )
    no_runtime_evidence = base.model_copy(
        update={
            "pattern_id": "trace_audio_feedback_unverified",
            "promoted_from_trace": "trace-audio-feedback-unverified",
            "layout": {
                "source": "trace_promotion",
                "trace_fingerprint": "tracefp:audio-feedback-panel",
                "trace_support_count": 1,
                "support_trace_ids": ["trace-audio-feedback-unverified"],
            },
        }
    )
    trace_path.write_text(
        "\n".join(
            json.dumps(
                {
                    "schema_version": 1,
                    "type": "brain_execution",
                    "promoted_pattern_candidate": pattern.model_dump(mode="json"),
                }
            )
            for pattern in (first, second, no_runtime_evidence)
        ),
        encoding="utf-8",
    )

    patterns = promoted_patterns_from_traces(trace_path)

    assert [pattern.pattern_id for pattern in patterns] == ["trace_audio_feedback_green_a"]
    clustered = patterns[0]
    assert clustered.promoted_from_trace == "trace-audio-feedback-green-a"
    assert clustered.layout["trace_fingerprint"] == "tracefp:audio-feedback-panel"
    assert clustered.layout["trace_support_count"] == 2
    assert clustered.layout["support_trace_ids"] == [
        "trace-audio-feedback-green-a",
        "trace-audio-feedback-green-b",
    ]
    assert clustered.layout["runtime_validation"]["passed_probe_ids"] == [
        "audio_signal_activity",
        "feedback_output_readback",
    ]


@pytest.mark.asyncio
async def test_replay_brain_trace_detects_profile_and_operator_drift():
    record = {
        "type": "brain_execution",
        "intent": "Create a GLSL shader TOP",
        "profile": "glsl",
        "target_root": "/project1",
        "trace": {"operators": ["constantTOP", "glslTOP", "textDAT", "nullTOP"]},
    }

    result = await replay_brain_trace(record)

    assert result["ok"] is True
    assert result["profile_match"] is True
    assert result["operators_match"] is True


@pytest.mark.asyncio
async def test_replay_brain_trace_detects_promoted_pattern_operator_drift():
    record = {
        "type": "brain_execution",
        "intent": "Build an audio-reactive feedback visual with a control panel and debug output",
        "profile": "concept_compiled",
        "target_root": "/project1",
        "trace": {
            "operators": [
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
                "baseCOMP",
                "annotateCOMP",
                "infoCHOP",
                "errorDAT",
            ]
        },
        "promoted_pattern_candidate": {
            "pattern_id": "trace_audio_feedback_green_audio_feedback_panel",
            "promoted_from_trace": "trace-audio-feedback-green",
            "required_ops": ["audiofileinCHOP", "feedbackTOP", "futureMagicTOP"],
        },
    }

    result = await replay_brain_trace(record)

    assert result["ok"] is False
    assert result["promoted_pattern_match"] is False
    assert result["promoted_pattern_operator_drift"] == {
        "pattern_id": "trace_audio_feedback_green_audio_feedback_panel",
        "missing": ["futureMagicTOP"],
    }


@pytest.mark.asyncio
async def test_replay_brain_trace_reports_promoted_pattern_runtime_probe_issues():
    record = {
        "type": "brain_execution",
        "intent": "Build an audio-reactive feedback visual with a control panel and debug output",
        "profile": "concept_compiled",
        "target_root": "/project1",
        "trace": {
            "operators": [
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
                "baseCOMP",
                "annotateCOMP",
                "infoCHOP",
                "errorDAT",
            ]
        },
        "promoted_pattern_candidate": {
            "pattern_id": "trace_audio_feedback_green_audio_feedback_panel",
            "promoted_from_trace": "trace-audio-feedback-green",
            "required_ops": ["audiofileinCHOP", "feedbackTOP"],
            "layout": {
                "runtime_validation": {
                    "required_probe_ids": [
                        "audio_signal_activity",
                        "feedback_output_readback",
                    ],
                    "passed_probe_ids": ["audio_signal_activity"],
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
                    "failed_probe_statuses": {
                        "cheap_visual_metrics": "runtime_fail",
                    },
                    "failed_optional_probe_ids": ["cheap_visual_metrics"],
                    "confidence_decay": 0.86,
                    "confidence_penalty_reasons": [
                        "missing_required_probe:feedback_output_readback",
                        "failed_optional_probe:cheap_visual_metrics",
                    ],
                }
            },
        },
    }

    result = await replay_brain_trace(record)

    assert result["ok"] is False
    assert result["promoted_pattern_runtime_validation_clean"] is False
    assert result["promoted_pattern_runtime_validation_issues"] == {
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
        "failed_optional_probe_ids": ["cheap_visual_metrics"],
        "confidence_decay": 0.86,
        "confidence_penalty_reasons": [
            "missing_required_probe:feedback_output_readback",
            "failed_optional_probe:cheap_visual_metrics",
        ],
    }


@pytest.mark.asyncio
async def test_replay_brain_trace_reports_trace_promotion_rejection_probe_issues():
    record = {
        "type": "brain_execution",
        "intent": "Build an audio-reactive feedback visual with a control panel and debug output",
        "profile": "concept_compiled",
        "target_root": "/project1",
        "trace": {
            "operators": [
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
                "baseCOMP",
                "annotateCOMP",
                "infoCHOP",
                "errorDAT",
            ]
        },
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
                        "runtime_metric_values": {"luminance_mean": 0.0, "entropy": 0.0},
                    },
                },
                "failed_optional_probe_ids": ["cheap_visual_metrics"],
                "confidence_decay": 0.68,
                "confidence_penalty_reasons": [
                    "missing_required_probe:feedback_output_readback",
                    "failed_required_probe:feedback_output_readback",
                    "failed_optional_probe:cheap_visual_metrics",
                ],
            },
        },
    }

    result = await replay_brain_trace(record)

    assert result["ok"] is False
    assert result["trace_promotion_rejection_clean"] is False
    assert result["trace_promotion_rejection_issues"] == {
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
            "failed_optional_probe_ids": ["cheap_visual_metrics"],
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
                    "runtime_metric_values": {"luminance_mean": 0.0, "entropy": 0.0},
                },
            },
            "confidence_decay": 0.68,
            "confidence_penalty_reasons": [
                "missing_required_probe:feedback_output_readback",
                "failed_required_probe:feedback_output_readback",
                "failed_optional_probe:cheap_visual_metrics",
            ],
        },
    }


@pytest.mark.asyncio
async def test_replay_brain_trace_reports_generated_code_runtime_rejection_details():
    record = {
        "type": "brain_execution",
        "intent": "Build a GLSL TOP shader with source texture, shader DAT, stable TOP output, and debug output",
        "profile": "concept_compiled",
        "target_root": "/project1",
        "trace": {
            "operators": ["constantTOP", "glslTOP", "textDAT", "nullTOP"],
        },
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
                "confidence_decay": 0.66,
                "confidence_penalty_reasons": [
                    "missing_generated_code_contract:glsl_top_pixel_shader:compile_state",
                    "failed_generated_code_contract:glsl_top_pixel_shader:compile_state",
                ],
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

    result = await replay_brain_trace(record)

    assert result["ok"] is False
    assert result["trace_promotion_rejection_clean"] is False
    assert result["trace_promotion_rejection_issues"] == {
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
            "confidence_decay": 0.66,
            "confidence_penalty_reasons": [
                "missing_generated_code_contract:glsl_top_pixel_shader:compile_state",
                "failed_generated_code_contract:glsl_top_pixel_shader:compile_state",
            ],
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
