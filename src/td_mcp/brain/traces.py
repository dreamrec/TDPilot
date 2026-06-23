"""JSONL trace export for TDPilot brain executions."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    records = read_brain_traces(path, limit=limit)
    clustered: dict[str, BrainPattern] = {}
    replay_validation_by_fingerprint: dict[str, dict[str, Any]] = {}

    for record in records:
        replay_validation = _replay_validation_aggregate(record)
        if replay_validation is not None:
            fingerprint = replay_validation["trace_fingerprint"]
            replay_validation_by_fingerprint[fingerprint] = _merge_replay_validation_aggregate(
                replay_validation_by_fingerprint.get(fingerprint),
                replay_validation,
            )

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

    for fingerprint, replay_validation in replay_validation_by_fingerprint.items():
        pattern = clustered.get(fingerprint)
        if pattern is not None:
            clustered[fingerprint] = _pattern_with_replay_validation_aggregate(
                pattern,
                replay_validation,
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
    promoted_runtime_issues = _promoted_pattern_runtime_validation_issues(record)
    promoted_runtime_clean = promoted_runtime_issues is None
    trace_promotion_rejection_issues = _trace_promotion_rejection_issues(record)
    trace_promotion_rejection_clean = trace_promotion_rejection_issues is None
    return {
        "schema_version": 1,
        "ok": (
            profile_match
            and operators_match
            and promoted_pattern_match
            and promoted_runtime_clean
            and trace_promotion_rejection_clean
            and not plan.blocked_questions
        ),
        "profile_match": profile_match,
        "operators_match": operators_match,
        "promoted_pattern_match": promoted_pattern_match,
        "promoted_pattern_operator_drift": promoted_pattern_drift,
        "promoted_pattern_runtime_validation_clean": promoted_runtime_clean,
        "promoted_pattern_runtime_validation_issues": promoted_runtime_issues,
        "trace_promotion_rejection_clean": trace_promotion_rejection_clean,
        "trace_promotion_rejection_issues": trace_promotion_rejection_issues,
        "expected_profile": expected_profile,
        "actual_profile": plan.concept_graph.profile,
        "expected_operators": operators,
        "actual_operators": plan.concept_graph.operators,
        "blocked_questions": plan.blocked_questions,
    }


def _trace_promotion_rejection_issues(record: dict[str, Any]) -> dict[str, Any] | None:
    rejection = record.get("trace_promotion_rejection")
    if not isinstance(rejection, Mapping):
        return None
    blockers = _string_list(rejection.get("blockers"))
    runtime = rejection.get("runtime_validation_issues")
    generated_code = rejection.get("generated_code_runtime_issues")
    issues: dict[str, Any] = {}
    if blockers:
        issues["blockers"] = blockers
    if isinstance(runtime, Mapping):
        runtime_issues = {
            "missing_probe_ids": _string_list(runtime.get("missing_probe_ids")),
            "failed_probe_ids": _string_list(runtime.get("failed_probe_ids")),
            "failed_probe_statuses": _status_mapping(runtime.get("failed_probe_statuses")),
        }
        missing_details = _probe_detail_mapping(runtime.get("missing_probe_details"))
        if missing_details:
            runtime_issues["missing_probe_details"] = missing_details
        failed_required_ids = _string_list(runtime.get("failed_required_probe_ids"))
        if failed_required_ids:
            runtime_issues["failed_required_probe_ids"] = failed_required_ids
        failed_optional_ids = _string_list(runtime.get("failed_optional_probe_ids"))
        if failed_optional_ids:
            runtime_issues["failed_optional_probe_ids"] = failed_optional_ids
        failed_required_details = _probe_detail_mapping(runtime.get("failed_required_probe_details"))
        if failed_required_details:
            runtime_issues["failed_required_probe_details"] = failed_required_details
        failed_details = _probe_detail_mapping(runtime.get("failed_probe_details"))
        if failed_details:
            runtime_issues["failed_probe_details"] = failed_details
        runtime_issues.update(_confidence_issue_fields(runtime))
        issues["runtime_validation_issues"] = runtime_issues
    if isinstance(generated_code, Mapping):
        generated_code_issues = {
            "missing_contract_ids": _string_list(generated_code.get("missing_contract_ids")),
        }
        missing_details = _generated_code_contract_detail_mapping(
            generated_code.get("missing_contract_details")
        )
        if missing_details:
            generated_code_issues["missing_contract_details"] = missing_details
        failed_ids = _string_list(generated_code.get("failed_contract_ids"))
        if failed_ids:
            generated_code_issues["failed_contract_ids"] = failed_ids
        failed_statuses = _status_mapping(generated_code.get("failed_contract_statuses"))
        if failed_statuses:
            generated_code_issues["failed_contract_statuses"] = failed_statuses
        failed_details = _generated_code_contract_detail_mapping(
            generated_code.get("failed_contract_details")
        )
        if failed_details:
            generated_code_issues["failed_contract_details"] = failed_details
        generated_code_issues.update(_confidence_issue_fields(generated_code))
        issues["generated_code_runtime_issues"] = generated_code_issues
    return issues or None


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


def _promoted_pattern_runtime_validation_issues(record: dict[str, Any]) -> dict[str, Any] | None:
    promoted = record.get("promoted_pattern_candidate")
    if not isinstance(promoted, dict):
        return None
    runtime = (
        promoted.get("layout", {}).get("runtime_validation")
        if isinstance(promoted.get("layout"), dict)
        else None
    )
    if not isinstance(runtime, Mapping):
        return None
    required = _string_list(runtime.get("required_probe_ids"))
    passed = set(_string_list(runtime.get("passed_probe_ids")))
    explicit_missing = _string_list(runtime.get("missing_probe_ids"))
    derived_missing = [probe_id for probe_id in required if probe_id not in passed]
    missing_probe_ids = list(dict.fromkeys([*explicit_missing, *derived_missing]))
    failed_probe_ids = _string_list(runtime.get("failed_probe_ids"))
    if not missing_probe_ids and not failed_probe_ids:
        return None
    statuses = runtime.get("failed_probe_statuses")
    failed_statuses = (
        {probe_id: str(statuses.get(probe_id) or "runtime_fail") for probe_id in failed_probe_ids}
        if isinstance(statuses, Mapping)
        else {probe_id: "runtime_fail" for probe_id in failed_probe_ids}
    )
    issues = {
        "pattern_id": str(promoted.get("pattern_id") or ""),
        "missing_probe_ids": missing_probe_ids,
        "failed_probe_ids": failed_probe_ids,
        "failed_probe_statuses": failed_statuses,
    }
    failed_required_ids = _string_list(runtime.get("failed_required_probe_ids"))
    if failed_required_ids:
        issues["failed_required_probe_ids"] = failed_required_ids
    failed_optional_ids = _string_list(runtime.get("failed_optional_probe_ids"))
    if failed_optional_ids:
        issues["failed_optional_probe_ids"] = failed_optional_ids
    missing_details = _probe_detail_mapping(runtime.get("missing_probe_details"))
    if missing_details:
        issues["missing_probe_details"] = missing_details
    failed_details = _probe_detail_mapping(runtime.get("failed_probe_details"))
    if failed_details:
        issues["failed_probe_details"] = failed_details
    issues.update(_confidence_issue_fields(runtime))
    return issues


def _confidence_issue_fields(value: Mapping[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    decay = _confidence_decay(value)
    if decay is not None and decay != 1.0:
        fields["confidence_decay"] = decay
    reasons = _string_list(value.get("confidence_penalty_reasons"))
    if reasons:
        fields["confidence_penalty_reasons"] = reasons
    return fields


def _replay_validation_aggregate(record: dict[str, Any]) -> dict[str, Any] | None:
    rejection = record.get("trace_promotion_rejection")
    if not isinstance(rejection, Mapping):
        return None
    fingerprint = _rejection_trace_fingerprint(rejection)
    if not fingerprint:
        return None
    runtime = rejection.get("runtime_validation_issues")
    if not isinstance(runtime, Mapping):
        return None

    missing_ids = _string_list(runtime.get("missing_probe_ids"))
    failed_ids = _string_list(runtime.get("failed_probe_ids"))
    failed_required_ids = _string_list(runtime.get("failed_required_probe_ids"))
    failed_optional_ids = _string_list(runtime.get("failed_optional_probe_ids"))
    if not missing_ids and not failed_ids and not failed_required_ids and not failed_optional_ids:
        return None

    aggregate = {
        "trace_fingerprint": fingerprint,
        "trace_ids": _record_trace_ids(record),
        "missing_probe_counts": _probe_counts(missing_ids),
        "failed_probe_counts": _probe_counts(failed_ids),
        "failed_required_probe_counts": _probe_counts(failed_required_ids),
        "failed_optional_probe_counts": _probe_counts(failed_optional_ids),
        "failed_probe_statuses": _status_mapping(runtime.get("failed_probe_statuses")),
        "missing_probe_details": _probe_detail_mapping(runtime.get("missing_probe_details")),
        "failed_probe_details": _probe_detail_mapping(runtime.get("failed_probe_details")),
        "failed_required_probe_details": _probe_detail_mapping(runtime.get("failed_required_probe_details")),
    }
    return aggregate


def _rejection_trace_fingerprint(rejection: Mapping[str, Any]) -> str:
    fingerprints = rejection.get("trace_fingerprints")
    if isinstance(fingerprints, Mapping):
        value = str(fingerprints.get("trace_fingerprint") or "").strip()
        if value:
            return value
    return str(rejection.get("trace_fingerprint") or "").strip()


def _record_trace_ids(record: Mapping[str, Any]) -> list[str]:
    trace = record.get("trace")
    values: list[str] = []
    if isinstance(trace, Mapping):
        trace_id = str(trace.get("id") or "").strip()
        if trace_id:
            values.append(trace_id)
    for key in ("trace_id", "id"):
        value = str(record.get(key) or "").strip()
        if value:
            values.append(value)
    return list(dict.fromkeys(values))


def _probe_counts(probe_ids: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for probe_id in dict.fromkeys(probe_ids):
        counts[probe_id] = counts.get(probe_id, 0) + 1
    return counts


def _merge_replay_validation_aggregate(
    existing: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, Any]:
    if existing is None:
        return {
            **current,
            "trace_ids": list(current.get("trace_ids") or []),
            "missing_probe_counts": dict(current.get("missing_probe_counts") or {}),
            "failed_probe_counts": dict(current.get("failed_probe_counts") or {}),
            "failed_required_probe_counts": dict(current.get("failed_required_probe_counts") or {}),
            "failed_optional_probe_counts": dict(current.get("failed_optional_probe_counts") or {}),
            "failed_probe_statuses": _mapping_copy(current.get("failed_probe_statuses")),
            "missing_probe_details": _mapping_copy(current.get("missing_probe_details")),
            "failed_probe_details": _mapping_copy(current.get("failed_probe_details")),
            "failed_required_probe_details": _mapping_copy(current.get("failed_required_probe_details")),
        }

    merged = {
        **existing,
        "trace_ids": list(dict.fromkeys([*existing.get("trace_ids", []), *current.get("trace_ids", [])])),
        "missing_probe_counts": _merge_count_maps(
            existing.get("missing_probe_counts"),
            current.get("missing_probe_counts"),
        ),
        "failed_probe_counts": _merge_count_maps(
            existing.get("failed_probe_counts"),
            current.get("failed_probe_counts"),
        ),
        "failed_required_probe_counts": _merge_count_maps(
            existing.get("failed_required_probe_counts"),
            current.get("failed_required_probe_counts"),
        ),
        "failed_optional_probe_counts": _merge_count_maps(
            existing.get("failed_optional_probe_counts"),
            current.get("failed_optional_probe_counts"),
        ),
        "failed_probe_statuses": {
            **_mapping_copy(existing.get("failed_probe_statuses")),
            **_mapping_copy(current.get("failed_probe_statuses")),
        },
        "missing_probe_details": _merge_detail_maps(
            existing.get("missing_probe_details"),
            current.get("missing_probe_details"),
        ),
        "failed_probe_details": _merge_detail_maps(
            existing.get("failed_probe_details"),
            current.get("failed_probe_details"),
        ),
        "failed_required_probe_details": _merge_detail_maps(
            existing.get("failed_required_probe_details"),
            current.get("failed_required_probe_details"),
        ),
    }
    return merged


def _merge_count_maps(left: Any, right: Any) -> dict[str, int]:
    merged: dict[str, int] = {}
    for source in (left, right):
        if not isinstance(source, Mapping):
            continue
        for probe_id, count in source.items():
            key = str(probe_id).strip()
            if not key or isinstance(count, bool) or not isinstance(count, int | float):
                continue
            merged[key] = merged.get(key, 0) + int(count)
    return merged


def _merge_detail_maps(left: Any, right: Any) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for source in (left, right):
        if not isinstance(source, Mapping):
            continue
        for probe_id, detail in source.items():
            key = str(probe_id).strip()
            if key and isinstance(detail, Mapping):
                merged[key] = dict(detail)
    return merged


def _mapping_copy(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _pattern_with_replay_validation_aggregate(
    pattern: BrainPattern,
    aggregate: dict[str, Any],
) -> BrainPattern:
    repeated_missing = _repeated_probe_counts(aggregate.get("missing_probe_counts"))
    repeated_failed = _repeated_probe_counts(aggregate.get("failed_probe_counts"))
    repeated_failed_required = _repeated_probe_counts(aggregate.get("failed_required_probe_counts"))
    repeated_failed_optional = _repeated_probe_counts(aggregate.get("failed_optional_probe_counts"))
    if not repeated_missing and not repeated_failed:
        return pattern

    layout = dict(pattern.layout)
    runtime_raw = layout.get("runtime_validation")
    runtime = dict(runtime_raw) if isinstance(runtime_raw, Mapping) else {}

    if repeated_missing:
        runtime["missing_probe_ids"] = _dedupe_string_values(
            [*_string_list(runtime.get("missing_probe_ids")), *repeated_missing]
        )
        missing_details = _mapping_copy(runtime.get("missing_probe_details"))
        aggregate_missing_details = aggregate.get("missing_probe_details")
        for probe_id, count in repeated_missing.items():
            detail = (
                dict(aggregate_missing_details.get(probe_id))
                if isinstance(aggregate_missing_details, Mapping)
                and isinstance(aggregate_missing_details.get(probe_id), Mapping)
                else {}
            )
            detail.setdefault("status", "replay_repeated_missing")
            detail.setdefault("issue_code", "repeated_trace_promotion_missing_probe")
            detail.setdefault(
                "issue_message",
                f"{probe_id} was missing from {count} trace promotion attempts.",
            )
            missing_details[probe_id] = detail
        runtime["missing_probe_details"] = missing_details

    if repeated_failed:
        runtime["failed_probe_ids"] = _dedupe_string_values(
            [*_string_list(runtime.get("failed_probe_ids")), *repeated_failed]
        )
        statuses = _mapping_copy(runtime.get("failed_probe_statuses"))
        statuses.update(_mapping_copy(aggregate.get("failed_probe_statuses")))
        runtime["failed_probe_statuses"] = statuses
        failed_details = _mapping_copy(runtime.get("failed_probe_details"))
        aggregate_failed_details = aggregate.get("failed_probe_details")
        for probe_id, count in repeated_failed.items():
            detail = (
                dict(aggregate_failed_details.get(probe_id))
                if isinstance(aggregate_failed_details, Mapping)
                and isinstance(aggregate_failed_details.get(probe_id), Mapping)
                else {}
            )
            detail.setdefault("status", statuses.get(probe_id, "replay_repeated_failed"))
            detail.setdefault("issue_code", "repeated_trace_promotion_failed_probe")
            detail.setdefault(
                "issue_message",
                f"{probe_id} failed in {count} trace promotion attempts.",
            )
            failed_details[probe_id] = detail
        runtime["failed_probe_details"] = failed_details

    if repeated_failed_required:
        runtime["failed_required_probe_ids"] = _dedupe_string_values(
            [
                *_string_list(runtime.get("failed_required_probe_ids")),
                *repeated_failed_required,
            ]
        )
        required_details = _mapping_copy(runtime.get("failed_required_probe_details"))
        aggregate_required_details = aggregate.get("failed_required_probe_details")
        for probe_id in repeated_failed_required:
            if isinstance(aggregate_required_details, Mapping) and isinstance(
                aggregate_required_details.get(probe_id), Mapping
            ):
                required_details[probe_id] = dict(aggregate_required_details[probe_id])
        if required_details:
            runtime["failed_required_probe_details"] = required_details

    if repeated_failed_optional:
        runtime["failed_optional_probe_ids"] = _dedupe_string_values(
            [
                *_string_list(runtime.get("failed_optional_probe_ids")),
                *repeated_failed_optional,
            ]
        )

    replay_payload = {
        "trace_fingerprint": aggregate["trace_fingerprint"],
        "trace_ids": list(aggregate.get("trace_ids") or []),
        "missing_probe_counts": repeated_missing,
        "failed_probe_counts": repeated_failed,
        "failed_required_probe_counts": repeated_failed_required,
        "failed_optional_probe_counts": repeated_failed_optional,
    }
    runtime["aggregated_replay_validation"] = replay_payload

    reasons = _dedupe_string_values(
        [
            *_string_list(runtime.get("confidence_penalty_reasons")),
            *[f"repeated_missing_probe:{probe_id}:{count}" for probe_id, count in repeated_missing.items()],
            *[f"repeated_failed_probe:{probe_id}:{count}" for probe_id, count in repeated_failed.items()],
        ]
    )
    if reasons:
        runtime["confidence_penalty_reasons"] = reasons
    runtime["confidence_decay"] = min(
        _runtime_confidence_decay(runtime),
        _aggregate_confidence_decay(repeated_missing, repeated_failed, repeated_failed_required),
    )

    layout["runtime_validation"] = runtime
    return pattern.model_copy(update={"layout": layout})


def _repeated_probe_counts(value: Any, *, threshold: int = 2) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    repeated: dict[str, int] = {}
    for probe_id, count in value.items():
        key = str(probe_id).strip()
        if not key or isinstance(count, bool) or not isinstance(count, int | float):
            continue
        numeric = int(count)
        if numeric >= threshold:
            repeated[key] = numeric
    return repeated


def _aggregate_confidence_decay(
    repeated_missing: Mapping[str, int],
    repeated_failed: Mapping[str, int],
    repeated_failed_required: Mapping[str, int],
) -> float:
    missing_penalty = sum(repeated_missing.values()) * 0.04
    failed_penalty = sum(repeated_failed.values()) * 0.08
    required_penalty = sum(repeated_failed_required.values()) * 0.08
    return round(max(0.4, 1.0 - min(0.6, missing_penalty + failed_penalty + required_penalty)), 4)


def _runtime_confidence_decay(runtime: Mapping[str, Any]) -> float:
    decay = _confidence_decay(runtime)
    return 1.0 if decay is None else decay


def _dedupe_string_values(values: list[Any]) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _confidence_decay(value: Mapping[str, Any]) -> float | None:
    raw = value.get("confidence_decay", value.get("validation_decay"))
    if isinstance(raw, bool):
        return None
    if not isinstance(raw, int | float | str):
        return None
    try:
        return round(float(raw), 4)
    except (TypeError, ValueError):
        return None


def _status_mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(status) for key, status in value.items() if str(key).strip()}


def _probe_detail_mapping(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        return {}
    details: dict[str, dict[str, Any]] = {}
    for probe_id, raw_detail in value.items():
        probe_key = str(probe_id).strip()
        if not probe_key or not isinstance(raw_detail, Mapping):
            continue
        detail: dict[str, Any] = {}
        for key in (
            "profile",
            "status",
            "issue_code",
            "issue_message",
            "failure_message",
            "readback_strategy",
            "readback_path",
        ):
            raw_value = raw_detail.get(key)
            if raw_value is not None and str(raw_value).strip():
                detail[key] = str(raw_value)
        runtime_required = raw_detail.get("runtime_required")
        if isinstance(runtime_required, bool):
            detail["runtime_required"] = runtime_required
        for key in (
            "missing_required_inputs",
            "present_required_inputs",
            "pending_metric_names",
            "metric_names",
            "pass_conditions",
        ):
            raw_value = raw_detail.get(key)
            if isinstance(raw_value, list):
                detail[key] = [str(item) for item in raw_value]
        metrics = raw_detail.get("runtime_metric_values")
        if isinstance(metrics, Mapping):
            detail["runtime_metric_values"] = dict(metrics)
        if detail:
            details[probe_key] = detail
    return details


def _generated_code_contract_detail_mapping(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        return {}
    details: dict[str, dict[str, Any]] = {}
    for contract_id, raw_detail in value.items():
        contract_key = str(contract_id).strip()
        if not contract_key or not isinstance(raw_detail, Mapping):
            continue
        detail: dict[str, Any] = {}
        for key in (
            "block_id",
            "check_id",
            "language",
            "target_op",
            "target_param",
            "endpoint",
            "status",
            "issue_code",
            "issue_message",
        ):
            raw_value = raw_detail.get(key)
            if raw_value is not None and str(raw_value).strip():
                detail[key] = str(raw_value)
        issue_count = raw_detail.get("issue_count")
        if isinstance(issue_count, int):
            detail["issue_count"] = issue_count
        for key in ("expected_outputs", "risk_flags", "official_sources"):
            raw_list = raw_detail.get(key)
            if isinstance(raw_list, list):
                detail[key] = [str(item) for item in raw_list]
        details[contract_key] = detail
    return details


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


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
