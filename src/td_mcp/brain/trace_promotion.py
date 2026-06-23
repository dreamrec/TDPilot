"""Promote verified BrainTrace records into reusable pattern candidates."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

from td_mcp.brain.code_harness import patch_plan_generated_code_runtime_contracts
from td_mcp.models.brain import BrainPattern, BrainPlan, BrainTrace, CandidateConceptGraph

_RUNTIME_PROMOTION_PROBES = {
    "audio_signal_activity",
    "feedback_output_readback",
    "panel_state_readback",
}


def promote_trace_to_pattern(
    brain_plan: BrainPlan,
    trace: BrainTrace,
    *,
    pattern_registry: Iterable[BrainPattern] | None = None,
    pattern_id: str | None = None,
    validation_report: Mapping[str, Any] | None = None,
) -> BrainPattern:
    """Return a docs-grounded pattern candidate for a verified trace."""
    source_patterns = list(pattern_registry or [])
    blockers = trace_promotion_blockers(
        brain_plan,
        trace,
        pattern_registry=source_patterns,
        validation_report=validation_report,
    )
    if blockers:
        raise ValueError(f"trace cannot be promoted: {'; '.join(blockers)}")

    candidate = _selected_candidate(brain_plan)
    if candidate is None:
        raise ValueError("trace cannot be promoted: BrainPlan has no candidate graph")

    matched_patterns = _matched_patterns(candidate, source_patterns)
    official_sources = _official_sources(matched_patterns)
    validation_probes = _validation_probes(candidate, matched_patterns)
    generated_code_contracts = patch_plan_generated_code_runtime_contracts(brain_plan.patch_plan)
    runtime_validation = _runtime_validation_summary(
        validation_report,
        validation_probes,
        generated_code_contracts,
    )
    fingerprints = trace_pattern_fingerprints(
        brain_plan,
        trace,
        candidate,
        validation_probes=validation_probes,
        generated_code_contracts=generated_code_contracts,
        runtime_validation=runtime_validation,
    )
    rollback_risks = _rollback_risks(candidate, matched_patterns)

    return BrainPattern(
        pattern_id=pattern_id or _pattern_id_for_trace(trace, candidate),
        title=f"Promoted {candidate.label}",
        intent_tags=_intent_tags(brain_plan, candidate),
        profiles=list(candidate.profiles),
        required_ops=list(candidate.required_ops),
        optional_ops=list(candidate.optional_ops),
        concept_nodes=list(candidate.concepts),
        concept_edges=list(candidate.edges),
        parameters=[],
        layout={
            "source": "trace_promotion",
            "candidate_graph_id": candidate.id,
            **fingerprints,
            "trace_support_count": 1,
            "support_trace_ids": [trace.id],
            **({"runtime_validation": runtime_validation} if runtime_validation else {}),
        },
        debug_outputs=[],
        safety=_combined_safety(matched_patterns),
        validation_profile=brain_plan.validation_profile,
        validation_probes=validation_probes,
        rollback_risks=rollback_risks,
        official_sources=official_sources,
        promoted_from_trace=trace.id,
    )


def trace_pattern_fingerprints(
    brain_plan: BrainPlan,
    trace: BrainTrace,
    candidate: CandidateConceptGraph,
    *,
    validation_probes: list[str],
    generated_code_contracts: list[dict[str, Any]],
    runtime_validation: Mapping[str, Any],
) -> dict[str, str]:
    """Return stable fingerprints for clustering validated trace memories."""
    operator_payload = {
        "required_ops": sorted(candidate.required_ops),
        "optional_ops": sorted(candidate.optional_ops),
        "profiles": sorted(candidate.profiles),
    }
    generated_contract_ids = _generated_code_contract_ids(generated_code_contracts)
    validation_payload = {
        "validation_profile": brain_plan.validation_profile,
        "validation_probes": sorted(set(validation_probes)),
        "runtime_probe_ids": sorted(runtime_validation.get("required_probe_ids") or []),
        "generated_code_contract_ids": sorted(generated_contract_ids),
    }
    intent_payload = {
        "profile": trace.profile,
        "candidate_profiles": sorted(candidate.profiles),
        "motifs": sorted(brain_plan.compiled_task.motifs if brain_plan.compiled_task else []),
        "capabilities": sorted(
            brain_plan.compiled_task.required_capabilities if brain_plan.compiled_task else []
        ),
        "pattern_ids": sorted(candidate.pattern_ids),
    }
    operator_fingerprint = _stable_digest("ops", operator_payload)
    validation_fingerprint = _stable_digest("validation", validation_payload)
    intent_fingerprint = _stable_digest("intent", intent_payload)
    trace_fingerprint = _stable_digest(
        "tracefp",
        {
            "intent": intent_fingerprint,
            "operators": operator_fingerprint,
            "validation": validation_fingerprint,
        },
    )
    return {
        "trace_fingerprint": trace_fingerprint,
        "intent_fingerprint": intent_fingerprint,
        "operator_fingerprint": operator_fingerprint,
        "validation_fingerprint": validation_fingerprint,
    }


def trace_promotion_blockers(
    brain_plan: BrainPlan,
    trace: BrainTrace,
    *,
    pattern_registry: Iterable[BrainPattern] | None = None,
    validation_report: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return reasons a BrainTrace is not eligible for pattern promotion."""
    blockers: list[str] = []
    if trace.validation_ok is not True:
        blockers.append("validation_ok must be true")
    if trace.transaction_status not in {"clean", "warnings"}:
        blockers.append("transaction_status must be clean or warnings")
    if trace.rollback_performed:
        blockers.append("rollback_performed must be false")
    if trace.plan_id and trace.plan_id != brain_plan.id:
        blockers.append("trace plan_id must match BrainPlan id")
    if brain_plan.blocked_questions:
        blockers.append("BrainPlan must not have blocked questions")

    candidate = _selected_candidate(brain_plan)
    if candidate is None:
        blockers.append("BrainPlan has no candidate graph")
        return blockers

    if trace.operators and not set(candidate.required_ops).issubset(set(trace.operators)):
        blockers.append("trace operators must cover candidate required_ops")

    matched_patterns = _matched_patterns(candidate, list(pattern_registry or []))
    if not _official_sources(matched_patterns):
        blockers.append("missing official Derivative docs grounding")
    validation_probes = _validation_probes(candidate, matched_patterns)
    if not validation_probes:
        blockers.append("missing validation probes")
    missing_runtime_passes = _missing_runtime_probe_passes(validation_report, validation_probes)
    if missing_runtime_passes:
        blockers.append("missing runtime validation passes: " + ", ".join(missing_runtime_passes))
    failed_required_runtime_probes = _failed_required_runtime_probe_ids(
        validation_report,
        validation_probes,
    )
    if failed_required_runtime_probes:
        blockers.append(
            "failed required runtime validation probes: " + ", ".join(failed_required_runtime_probes)
        )
    missing_generated_code_passes = _missing_generated_code_runtime_passes(
        validation_report,
        patch_plan_generated_code_runtime_contracts(brain_plan.patch_plan),
    )
    if missing_generated_code_passes:
        blockers.append(
            "missing generated code runtime validation passes: " + ", ".join(missing_generated_code_passes)
        )
    return blockers


def trace_promotion_rejection_evidence(
    brain_plan: BrainPlan,
    trace: BrainTrace,
    *,
    pattern_registry: Iterable[BrainPattern] | None = None,
    validation_report: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return structured replay evidence when a trace cannot be promoted."""
    source_patterns = list(pattern_registry or [])
    blockers = trace_promotion_blockers(
        brain_plan,
        trace,
        pattern_registry=source_patterns,
        validation_report=validation_report,
    )
    if not blockers:
        return None

    candidate = _selected_candidate(brain_plan)
    validation_probes: list[str] = []
    if candidate is not None:
        validation_probes = _validation_probes(candidate, _matched_patterns(candidate, source_patterns))
    generated_code_contracts = patch_plan_generated_code_runtime_contracts(brain_plan.patch_plan)
    runtime_issues = _runtime_validation_rejection_issues(validation_report, validation_probes)
    evidence: dict[str, Any] = {"blockers": blockers}
    if candidate is not None:
        runtime_validation = _runtime_validation_summary(
            validation_report,
            validation_probes,
            generated_code_contracts,
        )
        evidence["trace_fingerprints"] = trace_pattern_fingerprints(
            brain_plan,
            trace,
            candidate,
            validation_probes=validation_probes,
            generated_code_contracts=generated_code_contracts,
            runtime_validation=runtime_validation,
        )
    if runtime_issues:
        evidence["runtime_validation_issues"] = runtime_issues
    generated_code_issues = _generated_code_runtime_rejection_issues(
        validation_report,
        generated_code_contracts,
    )
    if generated_code_issues:
        evidence["generated_code_runtime_issues"] = generated_code_issues
    return evidence


def _selected_candidate(brain_plan: BrainPlan) -> CandidateConceptGraph | None:
    if not brain_plan.candidate_graphs:
        return None
    return max(brain_plan.candidate_graphs, key=lambda candidate: candidate.score)


def _matched_patterns(
    candidate: CandidateConceptGraph,
    pattern_registry: Iterable[BrainPattern],
) -> list[BrainPattern]:
    by_id = {pattern.pattern_id: pattern for pattern in pattern_registry}
    return [by_id[pattern_id] for pattern_id in candidate.pattern_ids if pattern_id in by_id]


def _official_sources(patterns: Iterable[BrainPattern]) -> list[str]:
    sources: list[str] = []
    for pattern in patterns:
        sources.extend(pattern.official_sources)
    return list(dict.fromkeys(sources))


def _validation_probes(
    candidate: CandidateConceptGraph,
    patterns: Iterable[BrainPattern],
) -> list[str]:
    probes = list(candidate.validation_needs)
    for pattern in patterns:
        probes.extend(pattern.validation_probes)
    return list(dict.fromkeys(probes))


def _runtime_validation_summary(
    validation_report: Mapping[str, Any] | None,
    validation_probes: list[str],
    generated_code_contracts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    required_probe_ids = _runtime_probe_ids(validation_probes)
    required_generated_code_contract_ids = _generated_code_contract_ids(generated_code_contracts or [])
    passed = _runtime_probe_passes(validation_report)
    failed = _runtime_probe_failures(validation_report)
    if not required_probe_ids and not required_generated_code_contract_ids and not failed:
        return {}
    missing = [probe_id for probe_id in required_probe_ids if probe_id not in passed]
    failed_required_probe_ids = [probe_id for probe_id in failed if probe_id in set(required_probe_ids)]
    failed_optional_probe_ids = [probe_id for probe_id in failed if probe_id not in set(required_probe_ids)]
    generated_code_passes = _generated_code_runtime_passes(validation_report)
    generated_code_missing_contract_ids = [
        contract_id
        for contract_id in required_generated_code_contract_ids
        if contract_id not in generated_code_passes
    ]
    generated_code_failed_contracts = _generated_code_runtime_failures(
        validation_report,
        required_generated_code_contract_ids,
    )
    summary = {
        "required_probe_ids": required_probe_ids,
        "passed_probe_ids": [probe_id for probe_id in required_probe_ids if probe_id in passed],
        "readback_paths": {
            probe_id: str(record["readback_path"])
            for probe_id, record in passed.items()
            if probe_id in required_probe_ids and record.get("readback_path")
        },
    }
    if missing:
        summary["missing_probe_ids"] = missing
        missing_details = _missing_runtime_probe_details(validation_report, missing)
        if missing_details:
            summary["missing_probe_details"] = missing_details
    if failed:
        summary["failed_probe_ids"] = list(failed)
        summary["failed_probe_statuses"] = {
            probe_id: str(record.get("status") or "runtime_fail") for probe_id, record in failed.items()
        }
        failed_details = _runtime_probe_failure_details(failed)
        if failed_details:
            summary["failed_probe_details"] = failed_details
    if failed_required_probe_ids:
        summary["failed_required_probe_ids"] = failed_required_probe_ids
    if failed_optional_probe_ids:
        summary["failed_optional_probe_ids"] = failed_optional_probe_ids
    if required_generated_code_contract_ids:
        summary.update(
            {
                "generated_code_required_contract_ids": required_generated_code_contract_ids,
                "generated_code_passed_contract_ids": [
                    contract_id
                    for contract_id in required_generated_code_contract_ids
                    if contract_id in generated_code_passes
                ],
                "generated_code_readback_targets": {
                    contract_id: str(record["target_op"])
                    for contract_id, record in generated_code_passes.items()
                    if contract_id in required_generated_code_contract_ids and record.get("target_op")
                },
            }
        )
    if generated_code_missing_contract_ids:
        summary["generated_code_missing_contract_ids"] = generated_code_missing_contract_ids
    if generated_code_failed_contracts:
        summary["generated_code_failed_contract_ids"] = list(generated_code_failed_contracts)
        summary["generated_code_failed_contract_statuses"] = {
            contract_id: str(record.get("status") or "runtime_fail")
            for contract_id, record in generated_code_failed_contracts.items()
        }
        failed_contract_details = _generated_code_runtime_failure_details(generated_code_failed_contracts)
        if failed_contract_details:
            summary["generated_code_failed_contract_details"] = failed_contract_details
    confidence = _runtime_validation_confidence(summary)
    if confidence["confidence_decay"] != 1.0:
        summary.update(confidence)
    return summary


def _missing_runtime_probe_passes(
    validation_report: Mapping[str, Any] | None,
    validation_probes: list[str],
) -> list[str]:
    required_probe_ids = _runtime_probe_ids(validation_probes)
    if not required_probe_ids:
        return []
    passed_probe_ids = set(_runtime_probe_passes(validation_report))
    return [probe_id for probe_id in required_probe_ids if probe_id not in passed_probe_ids]


def _failed_required_runtime_probe_ids(
    validation_report: Mapping[str, Any] | None,
    validation_probes: list[str],
) -> list[str]:
    required_probe_ids = _runtime_probe_ids(validation_probes)
    if not required_probe_ids:
        return []
    failed_probe_ids = set(_runtime_probe_failures(validation_report))
    return [probe_id for probe_id in required_probe_ids if probe_id in failed_probe_ids]


def _missing_generated_code_runtime_passes(
    validation_report: Mapping[str, Any] | None,
    generated_code_contracts: list[dict[str, Any]],
) -> list[str]:
    required_contract_ids = _generated_code_contract_ids(generated_code_contracts)
    if not required_contract_ids:
        return []
    passed_contract_ids = set(_generated_code_runtime_passes(validation_report))
    return [contract_id for contract_id in required_contract_ids if contract_id not in passed_contract_ids]


def _runtime_probe_ids(validation_probes: list[str]) -> list[str]:
    return [
        probe_id for probe_id in dict.fromkeys(validation_probes) if probe_id in _RUNTIME_PROMOTION_PROBES
    ]


def _runtime_probe_passes(
    validation_report: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    passed: dict[str, Mapping[str, Any]] = {}
    for result in _runtime_probe_records(validation_report):
        probe_id = str(result.get("probe_id") or "")
        if probe_id in _RUNTIME_PROMOTION_PROBES and result.get("status") == "runtime_pass":
            passed[probe_id] = result
    return passed


def _runtime_probe_failures(
    validation_report: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    failed: dict[str, Mapping[str, Any]] = {}
    for result in _runtime_probe_records(validation_report):
        probe_id = str(result.get("probe_id") or "")
        status = str(result.get("status") or "")
        if probe_id and status.startswith("runtime_") and status != "runtime_pass":
            failed[probe_id] = result
    return failed


def _runtime_probe_records(
    validation_report: Mapping[str, Any] | None,
) -> list[Mapping[str, Any]]:
    if not validation_report:
        return []
    cheap_metrics = validation_report.get("cheap_metrics")
    if not isinstance(cheap_metrics, Mapping):
        return []
    profile_results = cheap_metrics.get("profile_probe_results")
    if not isinstance(profile_results, list):
        return []
    return [result for result in profile_results if isinstance(result, Mapping)]


def _generated_code_contract_ids(contracts: list[dict[str, Any]]) -> list[str]:
    return list(
        dict.fromkeys(
            _generated_code_contract_id(contract)
            for contract in contracts
            if _generated_code_contract_id(contract)
        )
    )


def _generated_code_contract_id(contract: Mapping[str, Any]) -> str:
    block_id = str(contract.get("block_id") or "")
    check_id = str(contract.get("check_id") or "")
    if not block_id or not check_id:
        return ""
    return f"{block_id}:{check_id}"


def _generated_code_runtime_passes(
    validation_report: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    records = _generated_code_runtime_records(validation_report)
    return {
        contract_id: record
        for contract_id, record in records.items()
        if record.get("status") == "runtime_pass"
    }


def _generated_code_runtime_records(
    validation_report: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    if not validation_report:
        return {}
    cheap_metrics = validation_report.get("cheap_metrics")
    if not isinstance(cheap_metrics, Mapping):
        return {}
    generated = cheap_metrics.get("generated_code_runtime")
    if not isinstance(generated, Mapping):
        return {}
    evidence = generated.get("evidence")
    if not isinstance(evidence, list):
        return {}
    records: dict[str, Mapping[str, Any]] = {}
    for record in evidence:
        if not isinstance(record, Mapping):
            continue
        contract_id = _generated_code_contract_id(record)
        if contract_id:
            records[contract_id] = record
    return records


def _generated_code_runtime_failures(
    validation_report: Mapping[str, Any] | None,
    required_contract_ids: list[str],
) -> dict[str, Mapping[str, Any]]:
    required = set(required_contract_ids)
    return {
        contract_id: record
        for contract_id, record in _generated_code_runtime_records(validation_report).items()
        if contract_id in required
        and str(record.get("status") or "").startswith("runtime_")
        and record.get("status") != "runtime_pass"
    }


def _runtime_validation_confidence(runtime_summary: Mapping[str, Any]) -> dict[str, Any]:
    """Return explicit confidence decay from missing/failed runtime evidence."""

    penalties: list[tuple[str, float]] = []
    penalties.extend(
        (f"missing_required_probe:{probe_id}", 0.08)
        for probe_id in _string_list(runtime_summary.get("missing_probe_ids"))
    )
    penalties.extend(
        (f"failed_required_probe:{probe_id}", 0.18)
        for probe_id in _string_list(runtime_summary.get("failed_required_probe_ids"))
    )
    penalties.extend(
        (f"failed_optional_probe:{probe_id}", 0.06)
        for probe_id in _string_list(runtime_summary.get("failed_optional_probe_ids"))
    )
    penalties.extend(
        (f"missing_generated_code_contract:{contract_id}", 0.12)
        for contract_id in _string_list(runtime_summary.get("generated_code_missing_contract_ids"))
    )
    penalties.extend(
        (f"failed_generated_code_contract:{contract_id}", 0.22)
        for contract_id in _string_list(runtime_summary.get("generated_code_failed_contract_ids"))
    )
    if not penalties:
        return {"confidence_decay": 1.0, "confidence_penalty_reasons": []}
    total_penalty = min(0.6, sum(penalty for _reason, penalty in penalties))
    return {
        "confidence_decay": round(max(0.4, 1.0 - total_penalty), 4),
        "confidence_penalty_reasons": [reason for reason, _penalty in penalties],
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := str(item).strip())]


def _runtime_validation_rejection_issues(
    validation_report: Mapping[str, Any] | None,
    validation_probes: list[str],
) -> dict[str, Any]:
    required_probe_ids = set(_runtime_probe_ids(validation_probes))
    missing = _missing_runtime_probe_passes(validation_report, validation_probes)
    failed_required_ids = _failed_required_runtime_probe_ids(
        validation_report,
        validation_probes,
    )
    failed = _runtime_probe_failures(validation_report)
    failed_ids = list(failed)
    failed_optional_ids = [probe_id for probe_id in failed_ids if probe_id not in required_probe_ids]
    statuses = {probe_id: str(record.get("status") or "runtime_fail") for probe_id, record in failed.items()}
    details = _runtime_probe_failure_details(failed)
    if not missing and not failed_ids:
        return {}
    issues = {
        "missing_probe_ids": missing,
        "failed_probe_ids": failed_ids,
        "failed_probe_statuses": statuses,
    }
    missing_details = _missing_runtime_probe_details(validation_report, missing)
    if missing_details:
        issues["missing_probe_details"] = missing_details
    if failed_required_ids:
        issues["failed_required_probe_ids"] = failed_required_ids
        required_details = {
            probe_id: details[probe_id] for probe_id in failed_required_ids if probe_id in details
        }
        if required_details:
            issues["failed_required_probe_details"] = required_details
    if failed_optional_ids:
        issues["failed_optional_probe_ids"] = failed_optional_ids
    if details:
        issues["failed_probe_details"] = details
    confidence = _runtime_validation_confidence(issues)
    if confidence["confidence_decay"] != 1.0:
        issues.update(confidence)
    return issues


def _runtime_probe_failure_details(
    failed: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for probe_id, record in failed.items():
        detail = _runtime_probe_detail(record)
        if detail:
            details[probe_id] = detail
    return details


def _missing_runtime_probe_details(
    validation_report: Mapping[str, Any] | None,
    missing_probe_ids: list[str],
) -> dict[str, dict[str, Any]]:
    if not missing_probe_ids:
        return {}
    records = {
        str(record.get("probe_id") or ""): record
        for record in _runtime_probe_records(validation_report)
        if str(record.get("probe_id") or "")
    }
    details: dict[str, dict[str, Any]] = {}
    for probe_id in missing_probe_ids:
        record = records.get(probe_id)
        if record is None:
            details[probe_id] = {
                "status": "runtime_missing",
                "issue_code": "runtime_probe_pass_missing",
                "issue_message": f"{probe_id} did not produce a runtime_pass result.",
            }
            continue
        detail = _runtime_probe_detail(record)
        if detail:
            details[probe_id] = detail
    return details


def _runtime_probe_detail(record: Mapping[str, Any]) -> dict[str, Any]:
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
        value = record.get(key)
        if value is not None and str(value).strip():
            detail[key] = str(value)
    runtime_required = record.get("runtime_required")
    if isinstance(runtime_required, bool):
        detail["runtime_required"] = runtime_required
    for key in (
        "missing_required_inputs",
        "present_required_inputs",
        "pending_metric_names",
        "metric_names",
        "pass_conditions",
    ):
        value = record.get(key)
        if isinstance(value, list):
            detail[key] = [str(item) for item in value]
    metrics = record.get("runtime_metric_values")
    if isinstance(metrics, Mapping):
        detail["runtime_metric_values"] = dict(metrics)
    return detail


def _generated_code_runtime_rejection_issues(
    validation_report: Mapping[str, Any] | None,
    generated_code_contracts: list[dict[str, Any]],
) -> dict[str, Any]:
    missing = _missing_generated_code_runtime_passes(validation_report, generated_code_contracts)
    required_ids = set(_generated_code_contract_ids(generated_code_contracts))
    records = {
        contract_id: record
        for contract_id, record in _generated_code_runtime_records(validation_report).items()
        if contract_id in required_ids
    }
    failed = {
        contract_id: record
        for contract_id, record in records.items()
        if str(record.get("status") or "").startswith("runtime_") and record.get("status") != "runtime_pass"
    }
    if not missing and not failed:
        return {}
    issues: dict[str, Any] = {"missing_contract_ids": missing}
    missing_details = _missing_generated_code_runtime_details(
        generated_code_contracts,
        records,
        missing,
    )
    if missing_details:
        issues["missing_contract_details"] = missing_details
    if failed:
        issues["failed_contract_ids"] = list(failed)
        issues["failed_contract_statuses"] = {
            contract_id: str(record.get("status") or "runtime_fail") for contract_id, record in failed.items()
        }
        failed_details = _generated_code_runtime_failure_details(failed)
        if failed_details:
            issues["failed_contract_details"] = failed_details
    confidence = _runtime_validation_confidence(
        {
            "generated_code_missing_contract_ids": missing,
            "generated_code_failed_contract_ids": list(failed),
        }
    )
    if confidence["confidence_decay"] != 1.0:
        issues.update(confidence)
    return issues


def _missing_generated_code_runtime_details(
    generated_code_contracts: list[dict[str, Any]],
    records: Mapping[str, Mapping[str, Any]],
    missing_contract_ids: list[str],
) -> dict[str, dict[str, Any]]:
    if not missing_contract_ids:
        return {}
    contracts_by_id = {
        _generated_code_contract_id(contract): contract
        for contract in generated_code_contracts
        if _generated_code_contract_id(contract)
    }
    details: dict[str, dict[str, Any]] = {}
    for contract_id in missing_contract_ids:
        record = records.get(contract_id)
        if record is not None:
            detail = _generated_code_runtime_detail(record)
            if detail:
                details[contract_id] = detail
            continue
        contract = contracts_by_id.get(contract_id, {})
        details[contract_id] = {
            **_generated_code_runtime_detail(contract),
            "status": "runtime_missing",
            "issue_code": "generated_code_runtime_contract_pass_missing",
            "issue_message": (f"{contract_id} did not produce a generated-code runtime_pass result."),
        }
    return details


def _generated_code_runtime_failure_details(
    failed: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    details: dict[str, dict[str, Any]] = {}
    for contract_id, record in failed.items():
        detail = _generated_code_runtime_detail(record)
        if detail:
            details[contract_id] = detail
    return details


def _generated_code_runtime_detail(record: Mapping[str, Any]) -> dict[str, Any]:
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
        value = record.get(key)
        if value is not None and str(value).strip():
            detail[key] = str(value)
    issue_count = record.get("issue_count")
    if isinstance(issue_count, int):
        detail["issue_count"] = issue_count
    for key in ("expected_outputs", "risk_flags", "official_sources"):
        value = record.get(key)
        if isinstance(value, list):
            detail[key] = [str(item) for item in value]
    return detail


def _rollback_risks(
    candidate: CandidateConceptGraph,
    patterns: Iterable[BrainPattern],
) -> list[str]:
    risks = list(candidate.risk_flags)
    for pattern in patterns:
        risks.extend(pattern.rollback_risks)
    return list(dict.fromkeys(risks))


def _combined_safety(patterns: list[BrainPattern]) -> str:
    safeties = {pattern.safety for pattern in patterns}
    if "dry_run_only" in safeties:
        return "dry_run_only"
    if "device_dependent" in safeties:
        return "device_dependent"
    return "safe_live"


def _intent_tags(brain_plan: BrainPlan, candidate: CandidateConceptGraph) -> list[str]:
    tags: list[str] = []
    if brain_plan.compiled_task is not None:
        tags.extend(brain_plan.compiled_task.motifs)
        tags.extend(brain_plan.compiled_task.required_capabilities)
    tags.extend(candidate.profiles)
    return list(dict.fromkeys(str(tag) for tag in tags if str(tag).strip()))


def _pattern_id_for_trace(trace: BrainTrace, candidate: CandidateConceptGraph) -> str:
    trace_slug = _slug(trace.id)
    label_slug = _slug(candidate.label)
    prefix = trace_slug if trace_slug.startswith("trace_") else f"trace_{trace_slug}"
    return f"{prefix}_{label_slug}"[:120].rstrip("_")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "pattern"


def _stable_digest(prefix: str, payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(encoded).hexdigest()[:16]}"


__all__ = [
    "promote_trace_to_pattern",
    "trace_pattern_fingerprints",
    "trace_promotion_blockers",
    "trace_promotion_rejection_evidence",
]
