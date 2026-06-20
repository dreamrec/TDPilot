"""JSONL trace export for TDPilot brain executions."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from td_mcp.brain.evals import StaticEvalTDClient, families_for_ops
from td_mcp.brain.planner import build_brain_plan

DEFAULT_TRACE_PATH = Path("~/.tdpilot/traces/brain_traces.jsonl")


def brain_trace_path() -> Path:
    """Return the configured local JSONL trace path."""
    raw = os.environ.get("TDPILOT_BRAIN_TRACE_PATH")
    return Path(raw).expanduser() if raw else DEFAULT_TRACE_PATH.expanduser()


def append_brain_trace(record: dict[str, Any], path: Path | None = None) -> str:
    """Append one JSONL brain trace record and return the output path."""
    output = path or brain_trace_path()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **record,
    }
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
    return str(output)


def read_brain_traces(path: str | Path | None = None, *, limit: int | None = None) -> list[dict[str, Any]]:
    """Read local JSONL brain traces."""
    source = Path(path).expanduser() if path is not None else brain_trace_path()
    if not source.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    if limit is not None:
        return records[-limit:]
    return records


async def replay_brain_trace(record: dict[str, Any]) -> dict[str, Any]:
    """Replan a trace intent and compare current behavior against the saved trace."""
    operators = _trace_operators(record)
    client = StaticEvalTDClient(families=families_for_ops(operators), nodes=[])
    plan = await build_brain_plan(
        client,
        intent=str(record.get("intent") or ""),
        target_root=str(record.get("target_root") or "/project1"),
    )
    expected_profile = record.get("profile") or record.get("trace", {}).get("profile")
    profile_match = expected_profile is None or plan.concept_graph.profile == expected_profile
    operators_match = set(operators).issubset(set(plan.concept_graph.operators))
    return {
        "schema_version": 1,
        "ok": profile_match and operators_match and not plan.blocked_questions,
        "profile_match": profile_match,
        "operators_match": operators_match,
        "expected_profile": expected_profile,
        "actual_profile": plan.concept_graph.profile,
        "expected_operators": operators,
        "actual_operators": plan.concept_graph.operators,
        "blocked_questions": plan.blocked_questions,
    }


def _trace_operators(record: dict[str, Any]) -> list[str]:
    trace = record.get("trace") if isinstance(record.get("trace"), dict) else {}
    operators = (
        trace.get("operators") if isinstance(trace.get("operators"), list) else record.get("operators")
    )
    return [str(item) for item in operators or []]


__all__ = ["append_brain_trace", "brain_trace_path", "read_brain_traces", "replay_brain_trace"]
