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

    assert [pattern.pattern_id for pattern in patterns] == [
        "trace_audio_feedback_green_audio_feedback_panel"
    ]
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
