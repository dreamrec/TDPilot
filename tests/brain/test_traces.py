from __future__ import annotations

import json

import pytest

from td_mcp.brain.traces import append_brain_trace, read_brain_traces, replay_brain_trace


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
