"""Promote verified BrainTrace records into reusable pattern candidates."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from typing import Any, Mapping

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
        blockers.append(
            "missing runtime validation passes: " + ", ".join(missing_runtime_passes)
        )
    missing_generated_code_passes = _missing_generated_code_runtime_passes(
        validation_report,
        patch_plan_generated_code_runtime_contracts(brain_plan.patch_plan),
    )
    if missing_generated_code_passes:
        blockers.append(
            "missing generated code runtime validation passes: "
            + ", ".join(missing_generated_code_passes)
        )
    return blockers


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
    required_generated_code_contract_ids = _generated_code_contract_ids(
        generated_code_contracts or []
    )
    if not required_probe_ids and not required_generated_code_contract_ids:
        return {}
    passed = _runtime_probe_passes(validation_report)
    generated_code_passes = _generated_code_runtime_passes(validation_report)
    summary = {
        "required_probe_ids": required_probe_ids,
        "passed_probe_ids": [probe_id for probe_id in required_probe_ids if probe_id in passed],
        "readback_paths": {
            probe_id: str(record["readback_path"])
            for probe_id, record in passed.items()
            if probe_id in required_probe_ids and record.get("readback_path")
        },
    }
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


def _missing_generated_code_runtime_passes(
    validation_report: Mapping[str, Any] | None,
    generated_code_contracts: list[dict[str, Any]],
) -> list[str]:
    required_contract_ids = _generated_code_contract_ids(generated_code_contracts)
    if not required_contract_ids:
        return []
    passed_contract_ids = set(_generated_code_runtime_passes(validation_report))
    return [
        contract_id
        for contract_id in required_contract_ids
        if contract_id not in passed_contract_ids
    ]


def _runtime_probe_ids(validation_probes: list[str]) -> list[str]:
    return [
        probe_id
        for probe_id in dict.fromkeys(validation_probes)
        if probe_id in _RUNTIME_PROMOTION_PROBES
    ]


def _runtime_probe_passes(
    validation_report: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    if not validation_report:
        return {}
    cheap_metrics = validation_report.get("cheap_metrics")
    if not isinstance(cheap_metrics, Mapping):
        return {}
    profile_results = cheap_metrics.get("profile_probe_results")
    if not isinstance(profile_results, list):
        return {}
    passed: dict[str, Mapping[str, Any]] = {}
    for result in profile_results:
        if not isinstance(result, Mapping):
            continue
        probe_id = str(result.get("probe_id") or "")
        if probe_id in _RUNTIME_PROMOTION_PROBES and result.get("status") == "runtime_pass":
            passed[probe_id] = result
    return passed


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
    passed: dict[str, Mapping[str, Any]] = {}
    for record in evidence:
        if not isinstance(record, Mapping):
            continue
        contract_id = _generated_code_contract_id(record)
        if contract_id and record.get("status") == "runtime_pass":
            passed[contract_id] = record
    return passed


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
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return f"{prefix}:{hashlib.sha256(encoded).hexdigest()[:16]}"


__all__ = [
    "promote_trace_to_pattern",
    "trace_pattern_fingerprints",
    "trace_promotion_blockers",
]
