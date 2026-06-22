"""JSONL trace export for TDPilot brain executions."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from td_mcp.brain.evals import StaticEvalTDClient, families_for_ops
from td_mcp.brain.planner import build_brain_plan
from td_mcp.models.brain import BrainPattern

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


def promoted_patterns_from_traces(
    path: str | Path | None = None,
    *,
    limit: int | None = None,
) -> list[BrainPattern]:
    """Return runtime-proven promoted pattern memories clustered by fingerprint."""
    clustered: dict[str, BrainPattern] = {}
    for record in read_brain_traces(path, limit=limit):
        candidate = record.get("promoted_pattern_candidate")
        if not isinstance(candidate, dict):
            continue
        try:
            pattern = BrainPattern.model_validate(candidate)
        except Exception:
            continue
        if not pattern.promoted_from_trace:
            continue
        if not _has_runtime_validation_evidence(pattern):
            continue
        cluster_key = _trace_cluster_key(pattern)
        existing = clustered.get(cluster_key)
        clustered[cluster_key] = (
            _merge_clustered_pattern(existing, pattern) if existing is not None else pattern
        )
    return list(clustered.values())


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
    promoted_pattern_drift = _promoted_pattern_operator_drift(record, plan.concept_graph.operators)
    promoted_pattern_match = promoted_pattern_drift is None
    return {
        "schema_version": 1,
        "ok": profile_match and operators_match and promoted_pattern_match and not plan.blocked_questions,
        "profile_match": profile_match,
        "operators_match": operators_match,
        "promoted_pattern_match": promoted_pattern_match,
        "promoted_pattern_operator_drift": promoted_pattern_drift,
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


def _promoted_pattern_operator_drift(
    record: dict[str, Any],
    actual_operators: list[str],
) -> dict[str, Any] | None:
    promoted = record.get("promoted_pattern_candidate")
    if not isinstance(promoted, dict):
        return None
    required_ops = promoted.get("required_ops")
    if not isinstance(required_ops, list):
        return None
    missing = sorted(str(op_type) for op_type in required_ops if str(op_type) not in set(actual_operators))
    if not missing:
        return None
    return {
        "pattern_id": str(promoted.get("pattern_id") or ""),
        "missing": missing,
    }


def _trace_cluster_key(pattern: BrainPattern) -> str:
    layout = pattern.layout if isinstance(pattern.layout, Mapping) else {}
    fingerprint = str(layout.get("trace_fingerprint") or "").strip()
    return fingerprint or pattern.pattern_id


def _has_runtime_validation_evidence(pattern: BrainPattern) -> bool:
    layout = pattern.layout if isinstance(pattern.layout, Mapping) else {}
    runtime = layout.get("runtime_validation")
    if not isinstance(runtime, Mapping):
        return False
    passed_probes = runtime.get("passed_probe_ids")
    passed_generated_code = runtime.get("generated_code_passed_contract_ids")
    return bool(passed_probes or passed_generated_code)


def _merge_clustered_pattern(first: BrainPattern, next_pattern: BrainPattern) -> BrainPattern:
    first_layout = dict(first.layout)
    support_trace_ids = [
        *list(_support_trace_ids(first)),
        *list(_support_trace_ids(next_pattern)),
    ]
    support_trace_ids = list(dict.fromkeys(trace_id for trace_id in support_trace_ids if trace_id))
    first_layout["trace_support_count"] = len(support_trace_ids)
    first_layout["support_trace_ids"] = support_trace_ids
    return first.model_copy(update={"layout": first_layout})


def _support_trace_ids(pattern: BrainPattern) -> list[str]:
    layout = pattern.layout if isinstance(pattern.layout, Mapping) else {}
    support = layout.get("support_trace_ids")
    if isinstance(support, list):
        values = [str(item) for item in support if str(item)]
    else:
        values = []
    if pattern.promoted_from_trace:
        values.append(pattern.promoted_from_trace)
    return list(dict.fromkeys(values))


__all__ = [
    "append_brain_trace",
    "brain_trace_path",
    "promoted_patterns_from_traces",
    "read_brain_traces",
    "replay_brain_trace",
]
