"""Golden eval scoring for the TDPilot brain planner."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from td_mcp.brain.assembly_macros import validate_assembly_macro_control_bindings
from td_mcp.brain.code_harness import (
    extract_generated_code_blocks,
    generated_code_harness_coverage_report,
    generated_code_runtime_contracts,
    validate_generated_code_blocks,
)
from td_mcp.brain.operator_availability import operator_availability_coverage_report
from td_mcp.brain.param_semantics import param_semantics_coverage_report
from td_mcp.brain.patterns import load_pattern_registry
from td_mcp.brain.planner import build_brain_plan
from td_mcp.brain.trace_promotion import promote_trace_to_pattern, trace_promotion_blockers
from td_mcp.brain.validation_probes import validation_probe_coverage_report
from td_mcp.brain.validators import checks_for_profiles
from td_mcp.models.brain import BrainTrace


MIN_VALIDATION_CHECKS_PER_CASE = 6


class StaticEvalTDClient:
    """Small TDClient stand-in for deterministic planner evals."""

    def __init__(
        self, families: dict[str, list[str]] | None = None, nodes: list[dict[str, Any]] | None = None
    ) -> None:
        self.families = families or {}
        self.nodes = nodes or []

    async def request(self, endpoint: str, params: dict | None = None):
        if endpoint == "families":
            return {"families": self.families}
        if endpoint == "nodes":
            return {"nodes": self.nodes}
        return {}


def load_golden_cases(path: str | Path) -> list[dict[str, Any]]:
    """Load golden brain eval cases from JSONL."""
    source = Path(path)
    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        payload.setdefault("line_number", line_number)
        cases.append(payload)
    return cases


def families_for_ops(op_types: list[str]) -> dict[str, list[str]]:
    """Group expected TD operator types by family suffix."""
    families: dict[str, list[str]] = {}
    for op_type in op_types:
        family = family_for_op(op_type)
        families.setdefault(family, []).append(op_type)
    return families


def family_for_op(op_type: str) -> str:
    for suffix in ("TOP", "CHOP", "SOP", "POP", "DAT", "COMP", "MAT"):
        if op_type.endswith(suffix):
            return suffix
    return "ANY"


async def evaluate_golden_cases(path: str | Path) -> dict[str, Any]:
    """Run deterministic planner scoring over golden eval cases."""
    report_start = time.perf_counter()
    cases = load_golden_cases(path)
    results = [await evaluate_case(case) for case in cases]
    passed = sum(1 for item in results if item["passed"])
    pattern_coverage = pattern_eval_coverage_report(cases)
    assembly_control_bindings = assembly_control_binding_report()
    param_semantics_coverage = param_semantics_coverage_report()
    parameter_safety_metrics = _parameter_safety_metrics(param_semantics_coverage)
    operator_availability_coverage = operator_availability_coverage_report()
    validation_probe_coverage = validation_probe_coverage_report()
    generated_code_harness_coverage = generated_code_harness_coverage_report()
    trace_promotion_coverage = await trace_promotion_coverage_report(cases)
    trace_memory_reuse_coverage = await trace_memory_reuse_coverage_report(cases)
    decomposition_accuracy_metrics = _aggregate_decomposition_accuracy_metrics(results)
    validation_metrics = _aggregate_validation_metrics(results)
    operator_coverage_metrics = _aggregate_operator_coverage_metrics(results)
    unsupported_operator_avoidance_metrics = _aggregate_unsupported_operator_avoidance_metrics(results)
    generated_code_success_metrics = _aggregate_generated_code_success_metrics(results)
    readability_metrics = _aggregate_readability_metrics(results)
    showpiece_assembly_metrics = _aggregate_showpiece_assembly_metrics(results)
    prompt_safety_metrics = _aggregate_prompt_safety_metrics(results)
    runtime_safety_metrics = _aggregate_runtime_safety_metrics(results)
    rollback_frequency_metrics = _aggregate_rollback_frequency_metrics(results)
    substitution_quality_metrics = _aggregate_substitution_quality_metrics(results)
    availability_matrix_metrics = _aggregate_availability_matrix_metrics(results)
    messy_project_metrics = _aggregate_messy_project_metrics(results)
    compiler_stability = _aggregate_compiler_stability(results)
    delivery_phase_coverage = _delivery_phase_coverage_report(
        case_count=len(results),
        failed_count=len(results) - passed,
        pattern_coverage=pattern_coverage,
        compiler_stability=compiler_stability,
        assembly_control_bindings=assembly_control_bindings,
        param_semantics_coverage=param_semantics_coverage,
        parameter_safety_metrics=parameter_safety_metrics,
        operator_availability_coverage=operator_availability_coverage,
        validation_probe_coverage=validation_probe_coverage,
        generated_code_harness_coverage=generated_code_harness_coverage,
        generated_code_success_metrics=generated_code_success_metrics,
        decomposition_accuracy_metrics=decomposition_accuracy_metrics,
        validation_metrics=validation_metrics,
        readability_metrics=readability_metrics,
        showpiece_assembly_metrics=showpiece_assembly_metrics,
        availability_matrix_metrics=availability_matrix_metrics,
    )
    return {
        "schema_version": 1,
        "ok": passed == len(results)
        and pattern_coverage["ok"]
        and assembly_control_bindings["ok"]
        and param_semantics_coverage["ok"]
        and parameter_safety_metrics["ok"]
        and operator_availability_coverage["ok"]
        and validation_probe_coverage["ok"]
        and generated_code_harness_coverage["ok"]
        and trace_promotion_coverage["ok"]
        and trace_memory_reuse_coverage["ok"]
        and decomposition_accuracy_metrics["ok"]
        and validation_metrics["ok"]
        and operator_coverage_metrics["ok"]
        and unsupported_operator_avoidance_metrics["ok"]
        and generated_code_success_metrics["ok"]
        and readability_metrics["ok"]
        and showpiece_assembly_metrics["ok"]
        and prompt_safety_metrics["ok"]
        and runtime_safety_metrics["ok"]
        and rollback_frequency_metrics["ok"]
        and substitution_quality_metrics["ok"]
        and availability_matrix_metrics["ok"]
        and messy_project_metrics["ok"]
        and delivery_phase_coverage["ok"],
        "case_count": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pattern_coverage": pattern_coverage,
        "assembly_control_bindings": assembly_control_bindings,
        "param_semantics_coverage": param_semantics_coverage,
        "parameter_safety_metrics": parameter_safety_metrics,
        "operator_availability_coverage": operator_availability_coverage,
        "validation_probe_coverage": validation_probe_coverage,
        "generated_code_harness_coverage": generated_code_harness_coverage,
        "trace_promotion_coverage": trace_promotion_coverage,
        "trace_memory_reuse_coverage": trace_memory_reuse_coverage,
        "compiler_stability": compiler_stability,
        "decomposition_accuracy_metrics": decomposition_accuracy_metrics,
        "delivery_phase_coverage": delivery_phase_coverage,
        "validation_metrics": validation_metrics,
        "operator_coverage_metrics": operator_coverage_metrics,
        "unsupported_operator_avoidance_metrics": unsupported_operator_avoidance_metrics,
        "generated_code_success_metrics": generated_code_success_metrics,
        "readability_metrics": readability_metrics,
        "showpiece_assembly_metrics": showpiece_assembly_metrics,
        "prompt_safety_metrics": prompt_safety_metrics,
        "runtime_safety_metrics": runtime_safety_metrics,
        "rollback_frequency_metrics": rollback_frequency_metrics,
        "substitution_quality_metrics": substitution_quality_metrics,
        "availability_matrix_metrics": availability_matrix_metrics,
        "messy_project_metrics": messy_project_metrics,
        "time_metrics": _aggregate_time_metrics(results, report_start),
        "cases": results,
    }


def _parameter_safety_metrics(param_semantics_coverage: dict[str, Any]) -> dict[str, Any]:
    priority_groups = param_semantics_coverage.get("priority_groups", {})
    if not isinstance(priority_groups, dict):
        priority_groups = {}

    priority_group_missing_operator_count = sum(
        len(group.get("missing_operators", []))
        for group in priority_groups.values()
        if isinstance(group, dict) and isinstance(group.get("missing_operators", []), list)
    )
    missing_operator_count = int(param_semantics_coverage.get("missing_operator_count") or 0)
    invalid_source_count = int(param_semantics_coverage.get("invalid_source_count") or 0)

    return {
        "schema_version": 1,
        "ok": bool(priority_groups)
        and bool(param_semantics_coverage.get("ok"))
        and missing_operator_count == 0
        and invalid_source_count == 0
        and priority_group_missing_operator_count == 0,
        "covered_operator_count": int(param_semantics_coverage.get("covered_operator_count") or 0),
        "priority_operator_count": int(param_semantics_coverage.get("priority_operator_count") or 0),
        "missing_operator_count": missing_operator_count,
        "invalid_source_count": invalid_source_count,
        "priority_group_count": len(priority_groups),
        "priority_group_missing_operator_count": priority_group_missing_operator_count,
        "priority_groups": sorted(priority_groups),
    }


def _delivery_phase_coverage_report(
    *,
    case_count: int,
    failed_count: int,
    pattern_coverage: dict[str, Any],
    compiler_stability: dict[str, Any],
    assembly_control_bindings: dict[str, Any],
    param_semantics_coverage: dict[str, Any],
    parameter_safety_metrics: dict[str, Any],
    operator_availability_coverage: dict[str, Any],
    validation_probe_coverage: dict[str, Any],
    generated_code_harness_coverage: dict[str, Any],
    generated_code_success_metrics: dict[str, Any],
    decomposition_accuracy_metrics: dict[str, Any],
    validation_metrics: dict[str, Any],
    readability_metrics: dict[str, Any],
    showpiece_assembly_metrics: dict[str, Any],
    availability_matrix_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Map the master-plan phased MVP to current brain eval evidence."""
    phases = [
        _phase_record(
            "phase_1",
            "Compiler And Pattern Seed",
            {
                "eval_case_count": case_count,
                "failed_case_count": failed_count,
                "pattern_count": int(pattern_coverage.get("pattern_count") or 0),
                "covered_pattern_count": int(pattern_coverage.get("covered_pattern_count") or 0),
                "source_checked_pattern_count": int(
                    pattern_coverage.get("source_checked_pattern_count") or 0
                ),
                "invalid_pattern_source_count": int(
                    pattern_coverage.get("invalid_source_count") or 0
                ),
                "compiled_case_count": int(compiler_stability.get("compiled_case_count") or 0),
                "compiled_domain_failure_count": int(
                    compiler_stability.get("compiled_domain_failure_count") or 0
                ),
                "pattern_composition_failure_count": int(
                    compiler_stability.get("pattern_composition_failure_count") or 0
                ),
            },
            [
                ("at least 20 concept-to-node eval cases", case_count >= 20),
                ("all golden eval cases pass", failed_count == 0),
                ("at least 8 registered BrainPattern records", int(pattern_coverage.get("pattern_count") or 0) >= 8),
                ("pattern registry is fully covered by evals", bool(pattern_coverage.get("ok"))),
                (
                    "pattern registry uses only official Derivative docs sources",
                    int(pattern_coverage.get("invalid_source_count") or 0) == 0,
                ),
                ("compiler-backed cases are present", int(compiler_stability.get("compiled_case_count") or 0) >= 1),
            ],
        ),
        _phase_record(
            "phase_2",
            "Availability And Parameter Safety",
            {
                "availability_matrix_structured_case_count": int(
                    availability_matrix_metrics.get("structured_case_count") or 0
                ),
                "availability_matrix_known_build_case_count": int(
                    availability_matrix_metrics.get("known_build_case_count") or 0
                ),
                "param_semantics_priority_operator_count": int(
                    param_semantics_coverage.get("priority_operator_count") or 0
                ),
                "param_semantics_missing_operator_count": int(
                    param_semantics_coverage.get("missing_operator_count") or 0
                ),
                "parameter_safety_invalid_source_count": int(
                    parameter_safety_metrics.get("invalid_source_count") or 0
                ),
                "operator_availability_missing_rule_count": int(
                    operator_availability_coverage.get("missing_required_rule_count") or 0
                ),
            },
            [
                (
                    "operator availability matrix has structured cases",
                    int(availability_matrix_metrics.get("structured_case_count") or 0) >= 1,
                ),
                (
                    "operator availability matrix has known-build evidence",
                    int(availability_matrix_metrics.get("known_build_case_count") or 0) >= 1,
                ),
                ("operator substitution rules are covered", bool(operator_availability_coverage.get("ok"))),
                ("parameter safety metrics pass", bool(parameter_safety_metrics.get("ok"))),
                (
                    "top high-risk parameter semantics are covered",
                    int(param_semantics_coverage.get("priority_operator_count") or 0) >= 40,
                ),
            ],
        ),
        _phase_record(
            "phase_3",
            "Validators And Code Harness",
            {
                "validation_required_profile_count": int(
                    validation_probe_coverage.get("covered_required_profile_count") or 0
                ),
                "validation_missing_required_profile_count": int(
                    validation_probe_coverage.get("missing_required_profile_count") or 0
                ),
                "min_validation_check_count": int(validation_metrics.get("min_validation_check_count") or 0),
                "generated_code_case_count": int(
                    generated_code_success_metrics.get("generated_code_case_count") or 0
                ),
                "generated_code_block_count": int(
                    generated_code_success_metrics.get("generated_code_block_count") or 0
                ),
                "generated_code_runtime_contract_count": int(
                    generated_code_success_metrics.get("runtime_contract_count") or 0
                ),
            },
            [
                ("profile validation probes cover required profiles", bool(validation_probe_coverage.get("ok"))),
                ("validation reports include strong per-case checks", bool(validation_metrics.get("ok"))),
                ("generated code harness coverage passes", bool(generated_code_harness_coverage.get("ok"))),
                (
                    "generated code success cases are present",
                    int(generated_code_success_metrics.get("generated_code_case_count") or 0) >= 1,
                ),
                (
                    "generated code runtime contracts are present",
                    int(generated_code_success_metrics.get("runtime_contract_count") or 0) >= 1,
                ),
            ],
        ),
        _phase_record(
            "phase_4",
            "Fast Assembly, Plugin Surface, And Broad Evals",
            {
                "eval_case_count": case_count,
                "assembled_case_count": int(readability_metrics.get("assembled_case_count") or 0),
                "fully_readable_assembled_case_count": int(
                    readability_metrics.get("fully_readable_assembled_case_count") or 0
                ),
                "showpiece_case_count": int(showpiece_assembly_metrics.get("showpiece_case_count") or 0),
                "assembled_showpiece_case_count": int(
                    showpiece_assembly_metrics.get("assembled_showpiece_case_count") or 0
                ),
                "assembly_control_binding_missing_count": int(
                    assembly_control_bindings.get("missing_count") or 0
                ),
                "multi_domain_case_count": int(
                    decomposition_accuracy_metrics.get("multi_domain_case_count") or 0
                ),
            },
            [
                ("at least 50 concept-to-node eval cases", case_count >= 50),
                ("assembly macro control bindings pass", bool(assembly_control_bindings.get("ok"))),
                ("readability metrics pass for assembled cases", bool(readability_metrics.get("ok"))),
                ("showpiece assembly metrics pass", bool(showpiece_assembly_metrics.get("ok"))),
                (
                    "multi-domain decomposition coverage is broad",
                    int(decomposition_accuracy_metrics.get("multi_domain_case_count") or 0) >= 20,
                ),
            ],
        ),
    ]
    complete = [phase for phase in phases if phase["ok"]]
    incomplete = [phase for phase in phases if not phase["ok"]]
    return {
        "schema_version": 1,
        "ok": not incomplete,
        "scope": "brain_eval_phased_delivery_mvp",
        "phase_count": len(phases),
        "complete_phase_count": len(complete),
        "incomplete_phase_count": len(incomplete),
        "phases": phases,
    }


def _phase_record(
    phase_id: str,
    title: str,
    evidence: dict[str, Any],
    checks: list[tuple[str, bool]],
) -> dict[str, Any]:
    missing = [label for label, ok in checks if not ok]
    return {
        "phase_id": phase_id,
        "title": title,
        "ok": not missing,
        "missing": missing,
        "evidence": evidence,
    }


async def trace_memory_reuse_coverage_report(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Prove promoted trace candidates can be reloaded and reused by planning."""
    fixtures = [
        case
        for case in cases
        if _case_id(case) in {"audio_feedback_panel_debug", "glsl_top_shader_compiled"}
    ]
    reused: list[dict[str, Any]] = []
    missed: list[dict[str, Any]] = []
    loaded_pattern_count = 0

    for case in fixtures:
        case_id = str(_case_id(case) or "")
        try:
            promoted_pattern = await _promoted_pattern_for_trace_memory_fixture(case)
        except ValueError as exc:
            missed.append({"case_id": case_id, "reason": str(exc)})
            continue

        with tempfile.TemporaryDirectory(prefix="tdpilot_trace_memory_") as tmpdir:
            trace_path = Path(tmpdir) / "brain_traces.jsonl"
            trace_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "type": "brain_execution",
                        "promoted_pattern_candidate": promoted_pattern.model_dump(mode="json"),
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            from td_mcp.brain.traces import promoted_patterns_from_traces

            loaded_patterns = promoted_patterns_from_traces(trace_path)
            loaded_pattern_count += len(loaded_patterns)
            old_trace_path = os.environ.get("TDPILOT_BRAIN_TRACE_PATH")
            os.environ["TDPILOT_BRAIN_TRACE_PATH"] = str(trace_path)
            try:
                replay_plan = await _plan_for_trace_promotion_fixture(case)
            finally:
                if old_trace_path is None:
                    os.environ.pop("TDPILOT_BRAIN_TRACE_PATH", None)
                else:
                    os.environ["TDPILOT_BRAIN_TRACE_PATH"] = old_trace_path

        selected = replay_plan.candidate_graphs[0] if replay_plan.candidate_graphs else None
        selected_pattern_ids = list(selected.pattern_ids if selected else [])
        trace_promoted_evidence = (
            f"trace-promoted:{promoted_pattern.promoted_from_trace}" in replay_plan.grounding_evidence
        )
        record = {
            "case_id": case_id,
            "promoted_pattern_id": promoted_pattern.pattern_id,
            "selected_pattern_ids": selected_pattern_ids,
            "trace_promoted_evidence": trace_promoted_evidence,
        }
        if selected_pattern_ids == [promoted_pattern.pattern_id] and trace_promoted_evidence:
            reused.append(record)
        else:
            missed.append(record)

    return {
        "schema_version": 1,
        "ok": bool(fixtures) and len(reused) == len(fixtures) and loaded_pattern_count >= len(fixtures),
        "fixture_count": len(fixtures),
        "loaded_pattern_count": loaded_pattern_count,
        "reused_fixture_count": len(reused),
        "miss_count": len(missed),
        "reused_case_ids": [item["case_id"] for item in reused],
        "reused_fixtures": reused,
        "missed_fixtures": missed,
    }


async def _promoted_pattern_for_trace_memory_fixture(case: dict[str, Any]):
    registry = load_pattern_registry()
    case_id = str(_case_id(case) or "")
    plan = await _plan_for_trace_promotion_fixture(case)
    candidate = plan.candidate_graphs[0] if plan.candidate_graphs else None
    trace = BrainTrace(
        id=f"trace-{case_id}-green",
        intent=plan.task.intent,
        profile=str(plan.concept_graph.profile),
        target_root=plan.task.target_root,
        operators=list(candidate.required_ops if candidate else plan.concept_graph.operators),
        plan_id=plan.id,
        transaction_id=f"tx-{case_id}-clean",
        transaction_status="clean",
        validation_ok=True,
        rollback_performed=False,
    )
    return promote_trace_to_pattern(
        plan,
        trace,
        pattern_registry=registry,
        validation_report=_trace_promotion_fixture_validation_report(plan),
    )


async def trace_promotion_coverage_report(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Prove at least one successful golden trace promotes into a pattern candidate."""
    registry = load_pattern_registry()
    fixtures = [
        case
        for case in cases
        if _case_id(case) in {"audio_feedback_panel_debug", "glsl_top_shader_compiled"}
    ]
    promoted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    invalid_sources: list[dict[str, str]] = []

    for case in fixtures:
        case_id = str(_case_id(case) or "")
        plan = await _plan_for_trace_promotion_fixture(case)
        candidate = plan.candidate_graphs[0] if plan.candidate_graphs else None
        trace = BrainTrace(
            id=f"trace-{case_id}-green",
            intent=plan.task.intent,
            profile=str(plan.concept_graph.profile),
            target_root=plan.task.target_root,
            operators=list(candidate.required_ops if candidate else plan.concept_graph.operators),
            plan_id=plan.id,
            transaction_id=f"tx-{case_id}-clean",
            transaction_status="clean",
            validation_ok=True,
            rollback_performed=False,
        )
        validation_report = _trace_promotion_fixture_validation_report(plan)
        blockers = trace_promotion_blockers(
            plan,
            trace,
            pattern_registry=registry,
            validation_report=validation_report,
        )
        if blockers:
            blocked.append({"case_id": case_id, "blockers": blockers})
            continue
        pattern = promote_trace_to_pattern(
            plan,
            trace,
            pattern_registry=registry,
            validation_report=validation_report,
        )
        promoted.append(
            {
                "case_id": case_id,
                "pattern_id": pattern.pattern_id,
                "promoted_from_trace": pattern.promoted_from_trace,
                "required_ops": list(pattern.required_ops),
            }
        )
        for source in pattern.official_sources:
            if not source.startswith("https://docs.derivative.ca/"):
                invalid_sources.append(
                    {
                        "case_id": case_id,
                        "pattern_id": pattern.pattern_id,
                        "official_source": source,
                    }
                )

    return {
        "schema_version": 1,
        "ok": bool(fixtures) and len(promoted) == len(fixtures) and not blocked and not invalid_sources,
        "eligible_trace_fixture_count": len(fixtures),
        "promoted_fixture_count": len(promoted),
        "blocked_fixture_count": len(blocked),
        "invalid_source_count": len(invalid_sources),
        "promoted_case_ids": [item["case_id"] for item in promoted],
        "promoted_patterns": promoted,
        "blocked_fixtures": blocked,
        "invalid_sources": invalid_sources,
    }


async def _plan_for_trace_promotion_fixture(case: dict[str, Any]):
    expected_operator_sets = _expected_operator_sets(case)
    expected_ops = _expected_ops_for_client(case, expected_operator_sets)
    client = StaticEvalTDClient(
        families=families_for_ops(expected_ops), nodes=case.get("existing_nodes") or []
    )
    return await build_brain_plan(
        client,
        intent=_case_prompt(case),
        target_root=str(case.get("target_root") or "/project1"),
        constraints=case.get("constraints") if isinstance(case.get("constraints"), dict) else None,
        validation_profile=str(case.get("validation_profile") or "auto"),
    )


def _trace_promotion_fixture_validation_report(plan) -> dict[str, Any]:
    candidate = plan.candidate_graphs[0] if plan.candidate_graphs else None
    validation_needs = list(candidate.validation_needs if candidate else [])
    generated_code_contracts = generated_code_runtime_contracts(
        extract_generated_code_blocks(plan.patch_plan)
    )
    cheap_metrics: dict[str, Any] = {
        "profile_probe_results": [
            _trace_promotion_runtime_probe_result(probe_id)
            for probe_id in validation_needs
            if probe_id
            in {
                "audio_signal_activity",
                "feedback_output_readback",
                "panel_state_readback",
            }
        ]
    }
    if generated_code_contracts:
        cheap_metrics["generated_code_runtime"] = {
            "contract_count": len(generated_code_contracts),
            "checked_contract_count": len(generated_code_contracts),
            "evidence": [
                _trace_promotion_generated_code_runtime_result(contract)
                for contract in generated_code_contracts
            ],
        }
    return {
        "ok": True,
        "cheap_metrics": cheap_metrics,
    }


def _trace_promotion_generated_code_runtime_result(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "block_id": str(contract.get("block_id") or ""),
        "check_id": str(contract.get("check_id") or ""),
        "language": str(contract.get("language") or ""),
        "target_op": str(contract.get("target_op") or ""),
        "target_param": contract.get("target_param"),
        "expected_outputs": [str(item) for item in contract.get("expected_outputs", [])],
        "risk_flags": [str(item) for item in contract.get("risk_flags", [])],
        "official_sources": [str(item) for item in contract.get("official_sources", [])],
        "endpoint": "node/errors" if contract.get("check_id") == "compile_state" else None,
        "status": "runtime_pass",
        "issue_count": 0,
    }


def _trace_promotion_runtime_probe_result(probe_id: str) -> dict[str, Any]:
    if probe_id == "audio_signal_activity":
        return {
            "profile": "audio_reactive",
            "probe_id": probe_id,
            "status": "runtime_pass",
            "runtime_required": True,
            "readback_path": "/project1/tdpilot_concept/out_chop",
            "runtime_metric_values": {
                "audio_analysis_channel_delta": 0.8,
                "audio_analysis_channel_samples": 4,
            },
        }
    if probe_id == "feedback_output_readback":
        return {
            "profile": "feedback",
            "probe_id": probe_id,
            "status": "runtime_pass",
            "runtime_required": True,
            "readback_path": "/project1/tdpilot_concept/out1",
            "runtime_metric_values": {
                "feedback_output_luminance_mean": 0.25,
                "feedback_output_luminance_max": 0.75,
            },
        }
    return {
        "profile": "panel_ui",
        "probe_id": probe_id,
        "status": "runtime_pass",
        "runtime_required": True,
        "readback_path": "/project1/tdpilot_concept/out_chop",
        "runtime_metric_values": {
            "panel_state_channel_count": 2,
            "panel_state_sample_count": 2,
        },
    }


async def trace_replay_drift_report(
    cases: list[dict[str, Any]],
    expected_traces: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Replay golden cases and detect profile/operator drift from saved traces."""
    replayed = [await evaluate_case(case) for case in cases]
    drifts: list[dict[str, Any]] = []
    for result in replayed:
        case_id = str(result["id"])
        expected = expected_traces.get(case_id)
        if not expected:
            drifts.append(
                {
                    "case_id": case_id,
                    "profile_drift": None,
                    "operator_drift": None,
                    "missing_trace": True,
                }
            )
            continue
        profile_drift = _trace_profile_drift(expected.get("profile"), result["profile"])
        operator_drift = _trace_operator_drift(expected.get("operators") or [], result["operators"])
        promoted_pattern_drift = _trace_promoted_pattern_operator_drift(
            expected.get("promoted_pattern_candidate"),
            result["operators"],
        )
        if profile_drift or operator_drift or promoted_pattern_drift:
            drifts.append(
                {
                    "case_id": case_id,
                    "profile_drift": profile_drift,
                    "operator_drift": operator_drift,
                    "promoted_pattern_operator_drift": promoted_pattern_drift,
                    "missing_trace": False,
                }
            )
    return {
        "schema_version": 1,
        "ok": not drifts,
        "case_count": len(replayed),
        "drift_count": len(drifts),
        "drifts": drifts,
    }


async def trace_replay_baseline_report(
    cases: list[dict[str, Any]],
    expected_traces: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Replay only cases present in a saved baseline and report drift."""
    case_by_id = {_case_id(case): case for case in cases}
    replay_cases: list[dict[str, Any]] = []
    missing_case_drifts: list[dict[str, Any]] = []

    for case_id in expected_traces:
        case = case_by_id.get(str(case_id))
        if case is None:
            missing_case_drifts.append(
                {
                    "case_id": str(case_id),
                    "profile_drift": None,
                    "operator_drift": None,
                    "missing_trace": False,
                    "missing_case": True,
                }
            )
            continue
        replay_cases.append(case)

    replay_report = await trace_replay_drift_report(replay_cases, expected_traces)
    drifts = [*missing_case_drifts, *replay_report["drifts"]]
    return {
        "schema_version": 1,
        "ok": not drifts,
        "case_count": len(replay_cases),
        "baseline_case_count": len(expected_traces),
        "skipped_case_count": max(len(cases) - len(replay_cases), 0),
        "drift_count": len(drifts),
        "drifts": drifts,
    }


def trace_baseline_from_eval_results(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build a persisted trace baseline from golden eval result records."""
    baseline: dict[str, dict[str, Any]] = {}
    for result in results:
        case_id = result.get("id")
        if case_id is None:
            continue
        baseline[str(case_id)] = {
            "profile": str(result.get("profile") or ""),
            "operators": [str(operator) for operator in result.get("operators", [])],
        }
    return baseline


def trace_baseline_envelope_from_eval_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a schema-versioned trace baseline envelope from eval results."""
    traces = trace_baseline_from_eval_results(results)
    return {
        "schema_version": 1,
        "case_count": len(traces),
        "traces": traces,
    }


def pattern_eval_coverage_report(
    cases: list[dict[str, Any]],
    *,
    registry_pattern_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Report whether golden cases cover every registered BrainPattern."""
    registry_patterns = [] if registry_pattern_ids is not None else load_pattern_registry()
    pattern_ids = registry_pattern_ids or {pattern.pattern_id for pattern in registry_patterns}
    coverage_by_pattern = {pattern_id: [] for pattern_id in sorted(pattern_ids)}
    stale_references: dict[str, list[str]] = {}
    invalid_sources = [
        {"pattern_id": pattern.pattern_id, "official_source": source}
        for pattern in registry_patterns
        for source in pattern.official_sources
        if not source.startswith("https://docs.derivative.ca/")
    ]

    for case in cases:
        case_id = str(case.get("id") or f"line:{case.get('line_number', 'unknown')}")
        references = [
            *case.get("covers_patterns", []),
            *case.get("expected_patterns", []),
        ]
        for pattern_id in references:
            if pattern_id in coverage_by_pattern:
                coverage_by_pattern[pattern_id].append(case_id)
            else:
                stale_references.setdefault(str(pattern_id), []).append(case_id)

    missing = [pattern_id for pattern_id, case_ids in coverage_by_pattern.items() if not case_ids]
    stale = [
        {"pattern_id": pattern_id, "case_ids": case_ids}
        for pattern_id, case_ids in sorted(stale_references.items())
    ]
    return {
        "ok": not missing and not stale and not invalid_sources,
        "pattern_count": len(pattern_ids),
        "covered_pattern_count": len(pattern_ids) - len(missing),
        "source_checked_pattern_count": len(registry_patterns),
        "invalid_source_count": len(invalid_sources),
        "invalid_sources": invalid_sources,
        "missing_patterns": missing,
        "stale_pattern_references": stale,
        "coverage_by_pattern": coverage_by_pattern,
    }


def assembly_control_binding_report() -> dict[str, Any]:
    """Report whether assembly macro controls bind to known pattern parameters."""
    missing = validate_assembly_macro_control_bindings()
    return {
        "schema_version": 1,
        "ok": not missing,
        "missing_count": len(missing),
        "missing": missing,
    }


def _expected_blocked_safety_check(plan, operation_count: int) -> dict[str, Any]:
    evidence_text = " ".join(
        str(item)
        for item in [
            *plan.missing_facts,
            *plan.grounding_evidence,
            *plan.risk_flags,
        ]
    ).lower()
    normalized_evidence = evidence_text.replace("_", "-")
    has_under_specified_evidence = any(
        marker in normalized_evidence
        for marker in (
            "under-specified",
            "underspecified",
            "vague",
            "block-under-specified",
        )
    )
    return {
        "ok": bool(plan.blocked_questions)
        and operation_count == 0
        and has_under_specified_evidence,
        "blocked_question_count": len(plan.blocked_questions),
        "operation_count": operation_count,
        "has_under_specified_evidence": has_under_specified_evidence,
    }


async def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    case_start = time.perf_counter()
    expected_operator_sets = _expected_operator_sets(case)
    expected_ops = _expected_ops_for_client(case, expected_operator_sets)
    client = StaticEvalTDClient(
        families=families_for_ops(expected_ops), nodes=case.get("existing_nodes") or []
    )
    planning_start = time.perf_counter()
    plan = await build_brain_plan(
        client,
        intent=_case_prompt(case),
        target_root=str(case.get("target_root") or "/project1"),
        constraints=case.get("constraints") if isinstance(case.get("constraints"), dict) else None,
        validation_profile=str(case.get("validation_profile") or "auto"),
    )
    planning_ms = _elapsed_ms(planning_start)
    scoring_start = time.perf_counter()
    assembly_macros = _assembly_macro_ids(plan.patch_plan.operations)
    checks = {
        "tool_choice": {
            # A usable (non-blocked) plan with operations is what justifies the
            # td_brain_plan -> td_brain_execute routing. Measure the plan, not the
            # case metadata.
            "ok": not plan.blocked_questions and bool(plan.patch_plan.operations),
            "weight": _weight(case, "tool_choice"),
        },
        "concept_correctness": {
            "ok": plan.concept_graph.profile == case.get("expected_profile"),
            "weight": _weight(case, "concept_correctness"),
        },
        "network_structure": {
            "ok": _network_structure_ok(expected_ops, expected_operator_sets, plan.concept_graph.operators)
            and bool(plan.patch_plan.operations),
            "weight": _weight(case, "network_structure"),
        },
        "validation_discipline": {
            "ok": plan.validation_profile == (case.get("validation_profile") or "structural_visual_safe"),
            "weight": _weight(case, "validation_discipline"),
        },
        "rollback_behavior": {
            # An undo label on the patch plan is what enables rollback; the
            # must_use_tools list is case metadata, not plan behavior.
            "ok": bool(plan.patch_plan.undo_label),
            "weight": _weight(case, "rollback_behavior"),
        },
        "final_state_quality": {
            "ok": not plan.blocked_questions and not plan.missing_facts,
            "weight": _weight(case, "final_state_quality"),
        },
    }
    expected_domains = case.get("expected_compiled_domains") or case.get("expected_domains") or []
    if expected_domains:
        checks["compiled_domains"] = {
            "ok": plan.compiled_task is not None
            and set(expected_domains).issubset(set(plan.compiled_task.domains)),
            "weight": _weight(case, "compiled_domains"),
        }
    expected_time_behavior = case.get("expected_time_behavior") or []
    if expected_time_behavior:
        checks["time_behavior"] = {
            "ok": plan.compiled_task is not None
            and set(expected_time_behavior).issubset(set(plan.compiled_task.time_behavior)),
            "weight": _weight(case, "time_behavior"),
        }
    matched_operator_set = _matched_operator_set(expected_operator_sets, plan.concept_graph.operators)
    if expected_operator_sets:
        checks["operator_set"] = {
            "ok": matched_operator_set is not None,
            "weight": _weight(case, "operator_set"),
        }
    operator_coverage = _operator_coverage_for_case(
        expected_ops,
        expected_operator_sets,
        plan.concept_graph.operators,
        matched_operator_set,
    )
    expected_patterns = case.get("expected_patterns") or []
    actual_patterns = [
        pattern_id for candidate in plan.candidate_graphs for pattern_id in candidate.pattern_ids
    ]
    if expected_patterns:
        checks["pattern_composition"] = {
            "ok": set(expected_patterns).issubset(set(actual_patterns)),
            "weight": _weight(case, "pattern_composition"),
        }
    required_patterns = case.get("required_patterns") or []
    if required_patterns:
        checks["required_patterns"] = {
            "ok": set(required_patterns).issubset(set(actual_patterns)),
            "weight": _weight(case, "required_patterns"),
        }
    candidate_profiles = _candidate_profiles(plan)
    validation_checks = checks_for_profiles(plan.validation_profile, candidate_profiles)
    expected_profiles = case.get("expected_profiles") or []
    if expected_profiles:
        checks["expected_profiles"] = {
            "ok": set(expected_profiles).issubset(set(candidate_profiles)),
            "weight": _weight(case, "expected_profiles"),
        }
    validation_expectations = list(case.get("validation_expectations") or [])
    missing_validation_expectations = [
        item for item in validation_expectations if item not in validation_checks
    ]
    if validation_expectations:
        checks["validation_expectations"] = {
            "ok": not missing_validation_expectations,
            "weight": _weight(case, "validation_expectations"),
        }
    forbidden_ops = list(case.get("forbidden_ops") or [])
    forbidden_ops_present = sorted(set(forbidden_ops).intersection(plan.concept_graph.operators))
    if forbidden_ops:
        checks["forbidden_ops"] = {
            "ok": not forbidden_ops_present,
            "weight": _weight(case, "forbidden_ops"),
        }
    max_plan_ops = case.get("max_plan_ops")
    operation_count = len(plan.patch_plan.operations)
    existing_state_metrics = _existing_state_metrics(case, plan.patch_plan.operations)
    if max_plan_ops is not None:
        checks["max_plan_ops"] = {
            "ok": operation_count <= int(max_plan_ops),
            "weight": _weight(case, "max_plan_ops"),
        }
    expected_assembly_macros = case.get("expected_assembly_macros") or []
    if expected_assembly_macros:
        checks["assembly_macros"] = {
            "ok": set(expected_assembly_macros).issubset(set(assembly_macros)),
            "weight": _weight(case, "assembly_macros"),
        }
    expected_blocked = bool(case.get("expected_blocked"))
    if expected_blocked:
        expected_blocked_safety = _expected_blocked_safety_check(plan, operation_count)
        checks = {
            "expected_blocked_safety": {
                "ok": expected_blocked_safety["ok"],
                "weight": 1,
                "blocked_question_count": expected_blocked_safety["blocked_question_count"],
                "operation_count": expected_blocked_safety["operation_count"],
                "has_under_specified_evidence": expected_blocked_safety[
                    "has_under_specified_evidence"
                ],
            }
        }
    max_score = sum(item["weight"] for item in checks.values())
    score = sum(item["weight"] for item in checks.values() if item["ok"])
    passed = score == max_score
    scoring_ms = _elapsed_ms(scoring_start)
    generated_code_metrics = _generated_code_metrics_for_plan(plan.patch_plan)
    rollback_metrics = {
        "undo_label_present": bool(plan.patch_plan.undo_label),
        "rollback_required": False,
        "rollback_performed": False,
    }
    return {
        "id": _case_id(case),
        "passed": passed,
        "expected_blocked": expected_blocked,
        "score": score,
        "max_score": max_score,
        "checks": checks,
        "profile": plan.concept_graph.profile,
        "operators": plan.concept_graph.operators,
        "operation_count": operation_count,
        "max_plan_ops": max_plan_ops,
        "matched_operator_set": matched_operator_set,
        "operator_coverage": operator_coverage,
        "forbidden_ops_present": forbidden_ops_present,
        "compiled_domains": plan.compiled_task.domains if plan.compiled_task else [],
        "compiled_time_behavior": plan.compiled_task.time_behavior if plan.compiled_task else [],
        "candidate_profiles": candidate_profiles,
        "validation_checks": validation_checks,
        "missing_validation_expectations": missing_validation_expectations,
        "candidate_patterns": actual_patterns,
        "assembly_macros": assembly_macros,
        "blocked_questions": plan.blocked_questions,
        "missing_facts": plan.missing_facts,
        "grounding_evidence": plan.grounding_evidence,
        "availability_matrix": _availability_matrix_metrics(plan.availability_matrix),
        "decomposition_metrics": {
            "compiled_domain_count": len(plan.compiled_task.domains) if plan.compiled_task else 0,
            "compiled_time_behavior_count": len(plan.compiled_task.time_behavior)
            if plan.compiled_task
            else 0,
            "candidate_profile_count": len(candidate_profiles),
            "candidate_pattern_count": len(set(actual_patterns)),
        },
        "plan_metrics": {
            "operation_count": operation_count,
            "operator_count": len(plan.concept_graph.operators),
            "assembly_macro_count": len(assembly_macros),
        },
        "generated_code_metrics": generated_code_metrics,
        "rollback_metrics": rollback_metrics,
        "validation_metrics": {
            "validation_check_count": len(validation_checks),
            "missing_validation_expectation_count": len(missing_validation_expectations),
            "blocked_question_count": len(plan.blocked_questions),
        },
        "readability_metrics": _readability_metrics(plan, assembly_macros),
        "messy_scenarios": list(case.get("messy_scenarios") or []),
        "existing_state_metrics": existing_state_metrics,
        "time_metrics": {
            "planning_ms": planning_ms,
            "scoring_ms": scoring_ms,
            "total_ms": _elapsed_ms(case_start),
            "time_to_first_green_cycles": 1 if passed else None,
        },
    }


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 3)


def _availability_matrix_metrics(matrix) -> dict[str, Any] | None:
    if matrix is None:
        return None
    available_count = sum(1 for item in matrix.operators.values() if item.get("available") is True)
    unavailable_count = sum(1 for item in matrix.operators.values() if item.get("available") is False)
    return {
        "td_build": matrix.td_build,
        "platform": matrix.platform,
        "installed_addons": list(matrix.installed_addons),
        "operator_count": len(matrix.operators),
        "available_count": available_count,
        "unavailable_count": unavailable_count,
        "unavailable_reasons": dict(matrix.unavailable_reasons),
    }


def _existing_state_metrics(case: dict[str, Any], operations: list[Any]) -> dict[str, Any]:
    existing_nodes = [node for node in case.get("existing_nodes") or [] if isinstance(node, dict)]
    existing_names = {str(node.get("name") or "") for node in existing_nodes if node.get("name")}
    created_names = [
        str(operation.args.get("name") or "")
        for operation in operations
        if getattr(operation, "kind", "") == "create_node" and isinstance(operation.args, dict)
    ]
    conflicts = sorted(existing_names.intersection(name for name in created_names if name))
    return {
        "ok": not conflicts,
        "existing_node_count": len(existing_nodes),
        "created_node_count": len(created_names),
        "created_node_names": created_names,
        "created_existing_name_conflicts": conflicts,
        "created_existing_name_conflict_count": len(conflicts),
    }


def _aggregate_messy_project_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    existing_state_cases = [
        result
        for result in results
        if int(result.get("existing_state_metrics", {}).get("existing_node_count") or 0) > 0
    ]
    name_conflict_cases = _messy_scenario_results(results, "name_conflicts")
    name_conflict_failures = [
        result
        for result in name_conflict_cases
        if result.get("existing_state_metrics", {}).get("ok") is not True
    ]
    availability_pressure_cases = _messy_scenario_results(results, "availability_pressure")
    unsupported_operator_cases = [
        result
        for result in results
        if result.get("checks", {}).get("forbidden_ops") is not None
    ]
    ambiguous_blocked_cases = [
        result for result in results if result.get("expected_blocked") is True
    ]
    return {
        "schema_version": 1,
        "ok": bool(existing_state_cases)
        and bool(name_conflict_cases)
        and bool(availability_pressure_cases)
        and bool(unsupported_operator_cases)
        and bool(ambiguous_blocked_cases)
        and not name_conflict_failures,
        "existing_state_case_count": len(existing_state_cases),
        "existing_state_case_ids": _case_ids(existing_state_cases),
        "name_conflict_case_count": len(name_conflict_cases),
        "name_conflict_case_ids": _case_ids(name_conflict_cases),
        "name_conflict_failure_count": len(name_conflict_failures),
        "name_conflict_failure_case_ids": _case_ids(name_conflict_failures),
        "availability_pressure_case_count": len(availability_pressure_cases),
        "availability_pressure_case_ids": _case_ids(availability_pressure_cases),
        "unsupported_operator_case_count": len(unsupported_operator_cases),
        "unsupported_operator_case_ids": _case_ids(unsupported_operator_cases),
        "ambiguous_blocked_case_count": len(ambiguous_blocked_cases),
        "ambiguous_blocked_case_ids": _case_ids(ambiguous_blocked_cases),
    }


def _messy_scenario_results(results: list[dict[str, Any]], scenario: str) -> list[dict[str, Any]]:
    return [result for result in results if scenario in set(result.get("messy_scenarios") or [])]


def _aggregate_time_metrics(results: list[dict[str, Any]], report_start: float) -> dict[str, Any]:
    case_totals = [
        float(result.get("time_metrics", {}).get("total_ms", 0))
        for result in results
    ]
    cycles = [
        int(cycle)
        for result in results
        if (cycle := result.get("time_metrics", {}).get("time_to_first_green_cycles")) is not None
    ]
    return {
        "total_ms": _elapsed_ms(report_start),
        "avg_case_total_ms": round(sum(case_totals) / len(case_totals), 3) if case_totals else 0,
        "time_to_first_green_cycles": {
            "min": min(cycles) if cycles else None,
            "max": max(cycles) if cycles else None,
            "avg": round(sum(cycles) / len(cycles), 3) if cycles else None,
        },
    }


def _readability_metrics(plan, assembly_macros: list[str]) -> dict[str, Any]:
    macro_ids = set(assembly_macros)
    operations = plan.patch_plan.operations
    create_names = {
        str(operation.args.get("name"))
        for operation in operations
        if operation.kind == "create_node" and operation.args.get("name")
    }
    annotations = [
        operation
        for operation in operations
        if operation.kind == "annotate"
        and operation.args.get("assembly_macro_id") == "annotate_operator_chain"
    ]
    checks = {
        "component_shell": "make_component_shell" in macro_ids and "tdpilot_concept" in create_names,
        "domain_layout": any(
            operation.kind == "layout"
            and operation.args.get("assembly_macro_id") == "group_by_domain"
            and operation.args.get("domain")
            for operation in operations
        ),
        "named_outputs": "add_named_outputs" in macro_ids and any(name.startswith("out") for name in create_names),
        "debug_surface": "add_debug_panel" in macro_ids
        and bool({"debug_notes", "debug_info", "error_log"}.intersection(create_names)),
        "annotation_notes": any(
            "notes:" in str(operation.args.get("text") or "")
            and bool(operation.args.get("macro_notes"))
            for operation in annotations
        ),
    }
    score = sum(1 for ok in checks.values() if ok)
    return {"score": score, "max_score": len(checks), "checks": checks}


def _aggregate_readability_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    assembled = [result for result in results if result.get("assembly_macros")]
    scores = [int(result["readability_metrics"]["score"]) for result in assembled]
    max_scores = [int(result["readability_metrics"]["max_score"]) for result in assembled]
    fully_readable = [
        result
        for result in assembled
        if result["readability_metrics"]["score"] == result["readability_metrics"]["max_score"]
    ]
    not_fully_readable = [
        result
        for result in assembled
        if result["readability_metrics"]["score"] != result["readability_metrics"]["max_score"]
    ]
    return {
        "schema_version": 1,
        "ok": bool(assembled) and not not_fully_readable,
        "assembled_case_count": len(assembled),
        "fully_readable_assembled_case_count": len(fully_readable),
        "avg_assembled_score": round(sum(scores) / len(scores), 3) if scores else 0,
        "avg_assembled_max_score": round(sum(max_scores) / len(max_scores), 3) if max_scores else 0,
        "not_fully_readable_assembled_case_ids": _case_ids(not_fully_readable),
    }


def _aggregate_validation_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    results = _normal_case_results(results)
    validation_counts = [
        int((result.get("validation_metrics", {}) or {}).get("validation_check_count") or 0)
        for result in results
    ]
    weak_cases = [
        result
        for result in results
        if int((result.get("validation_metrics", {}) or {}).get("validation_check_count") or 0)
        < MIN_VALIDATION_CHECKS_PER_CASE
    ]
    missing_expectation_cases = [
        result
        for result in results
        if int(
            (result.get("validation_metrics", {}) or {}).get(
                "missing_validation_expectation_count"
            )
            or 0
        )
        > 0
    ]
    missing_expectation_count = sum(
        int(
            (result.get("validation_metrics", {}) or {}).get(
                "missing_validation_expectation_count"
            )
            or 0
        )
        for result in results
    )
    return {
        "schema_version": 1,
        "ok": bool(results) and not weak_cases and not missing_expectation_cases,
        "case_count": len(results),
        "min_validation_check_count": min(validation_counts) if validation_counts else 0,
        "avg_validation_check_count": round(sum(validation_counts) / len(validation_counts), 3)
        if validation_counts
        else 0,
        "weak_validation_case_count": len(weak_cases),
        "missing_validation_expectation_count": missing_expectation_count,
        "weak_validation_case_ids": _case_ids(weak_cases),
        "missing_validation_expectation_case_ids": _case_ids(missing_expectation_cases),
    }


def _aggregate_operator_coverage_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    checked = [
        result
        for result in results
        if int((result.get("operator_coverage", {}) or {}).get("expected_operator_count") or 0)
        > 0
    ]
    missing_cases = [
        result
        for result in checked
        if result.get("operator_coverage", {}).get("missing_required_operators")
    ]
    operator_set_failures = [
        result for result in checked if _case_check_failed(result, "operator_set")
    ]
    missing_count = sum(
        len(result.get("operator_coverage", {}).get("missing_required_operators") or [])
        for result in missing_cases
    )
    return {
        "schema_version": 1,
        "ok": bool(checked) and missing_count == 0 and not operator_set_failures,
        "case_count": len(results),
        "checked_case_count": len(checked),
        "missing_required_operator_count": missing_count,
        "operator_set_failure_count": len(operator_set_failures),
        "checked_case_ids": _case_ids(checked),
        "missing_required_operator_case_ids": _case_ids(missing_cases),
        "operator_set_failure_case_ids": _case_ids(operator_set_failures),
    }


def _generated_code_metrics_for_plan(patch_plan) -> dict[str, Any]:
    blocks = extract_generated_code_blocks(patch_plan)
    issues = [
        issue
        for issue in validate_generated_code_blocks(blocks)
        if issue.severity in {"error", "critical"}
    ]
    runtime_contracts = generated_code_runtime_contracts(blocks)
    runtime_contract_missing = [
        block.block_id
        for block in blocks
        if not block.runtime_checks or not block.expected_outputs
    ]
    invalid_source_blocks = sorted(
        {
            block.block_id
            for block in blocks
            for source in block.official_sources
            if not source.startswith("https://docs.derivative.ca/")
        }
    )
    runtime_checks = sorted({check for block in blocks for check in block.runtime_checks})
    static_checks = sorted({check for block in blocks for check in block.static_checks})
    languages = sorted({str(block.language) for block in blocks})
    return {
        "ok": not issues and not runtime_contract_missing and not invalid_source_blocks,
        "block_count": len(blocks),
        "block_ids": [block.block_id for block in blocks],
        "language_count": len(languages),
        "languages": languages,
        "static_check_count": len(static_checks),
        "static_checks": static_checks,
        "static_issue_count": len(issues),
        "static_issue_codes": sorted({issue.code for issue in issues}),
        "runtime_contract_count": len(runtime_contracts),
        "runtime_contract_missing_count": len(runtime_contract_missing),
        "runtime_contract_missing_block_ids": runtime_contract_missing,
        "runtime_check_count": len(runtime_checks),
        "runtime_checks": runtime_checks,
        "invalid_source_count": len(invalid_source_blocks),
        "invalid_source_block_ids": invalid_source_blocks,
    }


def _aggregate_generated_code_success_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    generated_cases = [
        result
        for result in results
        if int((result.get("generated_code_metrics", {}) or {}).get("block_count") or 0) > 0
    ]
    languages = sorted(
        {
            language
            for result in generated_cases
            for language in (result.get("generated_code_metrics", {}) or {}).get("languages", [])
        }
    )
    runtime_checks = sorted(
        {
            check
            for result in generated_cases
            for check in (result.get("generated_code_metrics", {}) or {}).get("runtime_checks", [])
        }
    )
    static_issue_cases = [
        result
        for result in generated_cases
        if int((result.get("generated_code_metrics", {}) or {}).get("static_issue_count") or 0) > 0
    ]
    missing_runtime_contract_cases = [
        result
        for result in generated_cases
        if int(
            (result.get("generated_code_metrics", {}) or {}).get(
                "runtime_contract_missing_count"
            )
            or 0
        )
        > 0
    ]
    invalid_source_cases = [
        result
        for result in generated_cases
        if int((result.get("generated_code_metrics", {}) or {}).get("invalid_source_count") or 0)
        > 0
    ]
    generated_code_block_count = sum(
        int((result.get("generated_code_metrics", {}) or {}).get("block_count") or 0)
        for result in generated_cases
    )
    runtime_contract_count = sum(
        int((result.get("generated_code_metrics", {}) or {}).get("runtime_contract_count") or 0)
        for result in generated_cases
    )
    static_issue_count = sum(
        int((result.get("generated_code_metrics", {}) or {}).get("static_issue_count") or 0)
        for result in generated_cases
    )
    runtime_contract_missing_count = sum(
        int(
            (result.get("generated_code_metrics", {}) or {}).get(
                "runtime_contract_missing_count"
            )
            or 0
        )
        for result in generated_cases
    )
    invalid_source_count = sum(
        int((result.get("generated_code_metrics", {}) or {}).get("invalid_source_count") or 0)
        for result in generated_cases
    )
    return {
        "schema_version": 1,
        "ok": bool(generated_cases)
        and len(languages) >= 2
        and static_issue_count == 0
        and runtime_contract_missing_count == 0
        and invalid_source_count == 0
        and runtime_contract_count >= generated_code_block_count,
        "generated_code_case_count": len(generated_cases),
        "generated_code_block_count": generated_code_block_count,
        "language_count": len(languages),
        "languages": languages,
        "static_issue_count": static_issue_count,
        "static_issue_case_ids": _case_ids(static_issue_cases),
        "runtime_contract_count": runtime_contract_count,
        "runtime_contract_missing_count": runtime_contract_missing_count,
        "runtime_contract_missing_case_ids": _case_ids(missing_runtime_contract_cases),
        "runtime_check_count": len(runtime_checks),
        "runtime_checks": runtime_checks,
        "invalid_source_count": invalid_source_count,
        "invalid_source_case_ids": _case_ids(invalid_source_cases),
        "generated_code_case_ids": _case_ids(generated_cases),
    }


def _aggregate_unsupported_operator_avoidance_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    checked = [result for result in results if "forbidden_ops" in result.get("checks", {})]
    forbidden_cases = [result for result in checked if result.get("forbidden_ops_present")]
    forbidden_present = sorted(
        {
            str(operator)
            for result in forbidden_cases
            for operator in result.get("forbidden_ops_present", [])
        }
    )
    return {
        "schema_version": 1,
        "ok": bool(checked) and not forbidden_cases,
        "checked_forbidden_operator_case_count": len(checked),
        "forbidden_operator_case_count": len(forbidden_cases),
        "checked_forbidden_operator_case_ids": _case_ids(checked),
        "forbidden_operator_case_ids": _case_ids(forbidden_cases),
        "forbidden_ops_present": forbidden_present,
    }


def _aggregate_decomposition_accuracy_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    compiled = [result for result in results if result.get("compiled_domains")]
    multi_domain = [
        result
        for result in compiled
        if int((result.get("decomposition_metrics", {}) or {}).get("compiled_domain_count") or 0)
        >= 2
    ]
    three_plus_domain = [
        result
        for result in compiled
        if int((result.get("decomposition_metrics", {}) or {}).get("compiled_domain_count") or 0)
        >= 3
    ]
    domain_failures = [result for result in compiled if _case_check_failed(result, "compiled_domains")]
    time_behavior_checked = [
        result for result in compiled if "time_behavior" in result.get("checks", {})
    ]
    time_behavior_failures = [
        result for result in time_behavior_checked if _case_check_failed(result, "time_behavior")
    ]
    pattern_failures = [
        result for result in compiled if _case_check_failed(result, "pattern_composition")
    ]
    failed_case_ids = sorted(
        set(_case_ids(domain_failures) + _case_ids(time_behavior_failures) + _case_ids(pattern_failures))
    )
    return {
        "schema_version": 1,
        "ok": bool(compiled) and not domain_failures and not time_behavior_failures and not pattern_failures,
        "compiled_case_count": len(compiled),
        "multi_domain_case_count": len(multi_domain),
        "three_plus_domain_case_count": len(three_plus_domain),
        "compiled_domain_failure_count": len(domain_failures),
        "time_behavior_checked_case_count": len(time_behavior_checked),
        "time_behavior_failure_count": len(time_behavior_failures),
        "pattern_composition_failure_count": len(pattern_failures),
        "compiled_case_ids": _case_ids(compiled),
        "multi_domain_case_ids": _case_ids(multi_domain),
        "three_plus_domain_case_ids": _case_ids(three_plus_domain),
        "time_behavior_checked_case_ids": _case_ids(time_behavior_checked),
        "failed_case_ids": failed_case_ids,
    }


def _aggregate_showpiece_assembly_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    showpieces = [result for result in results if _is_showpiece_result(result)]
    assembled = [result for result in showpieces if result.get("assembly_macros")]
    fully_readable = [
        result
        for result in assembled
        if result["readability_metrics"]["score"] == result["readability_metrics"]["max_score"]
    ]
    unassembled_ids = [
        str(result.get("id") or "")
        for result in showpieces
        if not result.get("assembly_macros")
    ]
    unreadable_ids = [
        str(result.get("id") or "")
        for result in assembled
        if result["readability_metrics"]["score"] != result["readability_metrics"]["max_score"]
    ]
    return {
        "schema_version": 1,
        "ok": bool(showpieces) and not unassembled_ids and not unreadable_ids,
        "showpiece_case_count": len(showpieces),
        "assembled_showpiece_case_count": len(assembled),
        "fully_readable_showpiece_case_count": len(fully_readable),
        "unassembled_showpiece_case_ids": unassembled_ids,
        "not_fully_readable_showpiece_case_ids": unreadable_ids,
        "showpiece_case_ids": [str(result.get("id") or "") for result in showpieces],
    }


def _is_showpiece_result(result: dict[str, Any]) -> bool:
    decomposition = result.get("decomposition_metrics", {}) or {}
    return (
        result.get("profile") == "concept_compiled"
        and int(decomposition.get("compiled_domain_count") or 0) >= 3
        and int(decomposition.get("candidate_pattern_count") or 0) >= 3
    )


def _aggregate_prompt_safety_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    expected_blocked_cases = [
        result for result in results if result.get("expected_blocked") is True
    ]
    passed_expected_blocked = [
        result
        for result in expected_blocked_cases
        if result.get("passed")
        and result.get("checks", {}).get("expected_blocked_safety", {}).get("ok") is True
    ]
    passed_expected_blocked_ids = {id(result) for result in passed_expected_blocked}
    failed_expected_blocked = [
        result for result in expected_blocked_cases if id(result) not in passed_expected_blocked_ids
    ]
    return {
        "schema_version": 1,
        "ok": bool(expected_blocked_cases) and not failed_expected_blocked,
        "expected_blocked_case_count": len(expected_blocked_cases),
        "passed_expected_blocked_case_count": len(passed_expected_blocked),
        "failed_expected_blocked_case_count": len(failed_expected_blocked),
        "expected_blocked_case_ids": _case_ids(expected_blocked_cases),
        "passed_expected_blocked_case_ids": _case_ids(passed_expected_blocked),
        "failed_expected_blocked_case_ids": _case_ids(failed_expected_blocked),
    }


def _normal_case_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [result for result in results if result.get("expected_blocked") is not True]


def _aggregate_runtime_safety_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    results = _normal_case_results(results)
    checked_forbidden_operator_cases = [
        result for result in results if "forbidden_ops" in result.get("checks", {})
    ]
    blocked_cases = [result for result in results if result.get("blocked_questions")]
    missing_fact_cases = [result for result in results if result.get("missing_facts")]
    forbidden_operator_cases = [
        result for result in results if result.get("forbidden_ops_present")
    ]
    rollback_behavior_failures = [
        result for result in results if _case_check_failed(result, "rollback_behavior")
    ]
    final_state_quality_failures = [
        result for result in results if _case_check_failed(result, "final_state_quality")
    ]
    operator_set_failures = [
        result for result in results if _case_check_failed(result, "operator_set")
    ]
    max_plan_ops_failures = [
        result for result in results if _case_check_failed(result, "max_plan_ops")
    ]
    return {
        "ok": bool(results)
        and bool(checked_forbidden_operator_cases)
        and not blocked_cases
        and not missing_fact_cases
        and not forbidden_operator_cases
        and not rollback_behavior_failures
        and not final_state_quality_failures
        and not operator_set_failures
        and not max_plan_ops_failures,
        "case_count": len(results),
        "checked_forbidden_operator_case_count": len(checked_forbidden_operator_cases),
        "blocked_case_count": len(blocked_cases),
        "missing_fact_case_count": len(missing_fact_cases),
        "forbidden_operator_case_count": len(forbidden_operator_cases),
        "rollback_behavior_failure_count": len(rollback_behavior_failures),
        "final_state_quality_failure_count": len(final_state_quality_failures),
        "operator_set_failure_count": len(operator_set_failures),
        "max_plan_ops_failure_count": len(max_plan_ops_failures),
        "checked_forbidden_operator_case_ids": _case_ids(checked_forbidden_operator_cases),
        "blocked_case_ids": _case_ids(blocked_cases),
        "missing_fact_case_ids": _case_ids(missing_fact_cases),
        "forbidden_operator_case_ids": _case_ids(forbidden_operator_cases),
        "rollback_behavior_failure_case_ids": _case_ids(rollback_behavior_failures),
        "final_state_quality_failure_case_ids": _case_ids(final_state_quality_failures),
        "operator_set_failure_case_ids": _case_ids(operator_set_failures),
        "max_plan_ops_failure_case_ids": _case_ids(max_plan_ops_failures),
    }


def _aggregate_rollback_frequency_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    results = _normal_case_results(results)
    rollback_enabled = [
        result
        for result in results
        if bool((result.get("rollback_metrics", {}) or {}).get("undo_label_present"))
    ]
    rollback_behavior_failures = [
        result for result in results if _case_check_failed(result, "rollback_behavior")
    ]
    rollback_required = [
        result
        for result in results
        if bool((result.get("rollback_metrics", {}) or {}).get("rollback_required"))
    ]
    rollback_performed = [
        result
        for result in results
        if bool((result.get("rollback_metrics", {}) or {}).get("rollback_performed"))
    ]
    rollback_frequency = (
        round(len(rollback_performed) / len(results), 6)
        if results
        else 0.0
    )
    return {
        "schema_version": 1,
        "ok": bool(results)
        and len(rollback_enabled) == len(results)
        and not rollback_behavior_failures
        and not rollback_required
        and not rollback_performed,
        "case_count": len(results),
        "rollback_enabled_case_count": len(rollback_enabled),
        "rollback_behavior_failure_count": len(rollback_behavior_failures),
        "rollback_required_case_count": len(rollback_required),
        "rollback_performed_count": len(rollback_performed),
        "rollback_frequency": rollback_frequency,
        "rollback_enabled_case_ids": _case_ids(rollback_enabled),
        "rollback_behavior_failure_case_ids": _case_ids(rollback_behavior_failures),
        "rollback_required_case_ids": _case_ids(rollback_required),
        "rollback_performed_case_ids": _case_ids(rollback_performed),
    }


def _case_check_failed(result: dict[str, Any], check_name: str) -> bool:
    check = result.get("checks", {}).get(check_name)
    return isinstance(check, dict) and check.get("ok") is False


def _case_ids(results: list[dict[str, Any]]) -> list[str]:
    return [str(result.get("id") or "") for result in results]


def _aggregate_substitution_quality_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    substitution_cases: list[str] = []
    approved_substitutions: list[dict[str, Any]] = []
    pending_substitutions: list[dict[str, Any]] = []
    approval_required_substitutions: list[dict[str, Any]] = []
    unapproved_required_substitutions: list[dict[str, Any]] = []
    substitutions_without_rule: list[dict[str, Any]] = []
    replacement_operator_missing: list[dict[str, Any]] = []
    low_confidence: list[dict[str, Any]] = []

    for result in results:
        case_id = str(result.get("id") or "")
        evidence = [str(item) for item in result.get("grounding_evidence", [])]
        events = [_parse_substitution_event(item) for item in evidence]
        events = [event for event in events if event is not None]
        if not events:
            continue
        substitution_cases.append(case_id)
        rules = _substitution_rules_by_missing_op(evidence)
        operators = {str(operator) for operator in result.get("operators", [])}
        for event in events:
            rule = rules.get(event["missing_op"])
            if event["pending_approval"]:
                pending_substitutions.append({"case_id": case_id, **event})
                continue
            if rule is None:
                substitutions_without_rule.append({"case_id": case_id, **event})
                continue
            replacement_ops = list(rule["replacement_ops"])
            requires_approval = bool(rule["requires_approval"])
            approval_evidence = _substitution_approval_evidence(event, evidence) if requires_approval else []
            substitution_record = {
                "case_id": case_id,
                "missing_op": event["missing_op"],
                "replacement_target": event["replacement_target"],
                "replacement_ops": replacement_ops,
                "confidence": rule["confidence"],
                "requires_approval": requires_approval,
                "approval_evidence": approval_evidence,
            }
            if requires_approval:
                approval_required_substitutions.append(substitution_record)
            if requires_approval and not approval_evidence:
                pending_substitutions.append(substitution_record)
                unapproved_required_substitutions.append(substitution_record)
                continue
            missing_replacements = sorted(set(replacement_ops) - operators)
            if missing_replacements:
                replacement_operator_missing.append(
                    {
                        "case_id": case_id,
                        **event,
                        "replacement_ops": replacement_ops,
                        "missing_replacement_ops": missing_replacements,
                        "confidence": rule["confidence"],
                        "requires_approval": requires_approval,
                        "approval_evidence": approval_evidence,
                    }
                )
                continue
            if rule["confidence"] == "low":
                low_confidence.append(
                    {
                        "case_id": case_id,
                        **event,
                        "replacement_ops": replacement_ops,
                        "confidence": rule["confidence"],
                        "requires_approval": requires_approval,
                        "approval_evidence": approval_evidence,
                    }
                )
                continue
            approved_substitutions.append(substitution_record)

    return {
        "schema_version": 1,
        "ok": bool(results)
        and bool(approved_substitutions)
        and not pending_substitutions
        and not unapproved_required_substitutions
        and not substitutions_without_rule
        and not replacement_operator_missing
        and not low_confidence,
        "case_count": len(results),
        "substitution_case_count": len(set(substitution_cases)),
        "approved_substitution_count": len(approved_substitutions),
        "pending_approval_count": len(pending_substitutions),
        "approval_required_count": len(approval_required_substitutions),
        "unapproved_required_count": len(unapproved_required_substitutions),
        "substitution_without_rule_count": len(substitutions_without_rule),
        "replacement_operator_missing_count": len(replacement_operator_missing),
        "low_confidence_count": len(low_confidence),
        "substitution_case_ids": sorted(set(substitution_cases)),
        "approved_substitutions": approved_substitutions,
        "pending_substitutions": pending_substitutions,
        "approval_required_substitutions": approval_required_substitutions,
        "unapproved_required_substitutions": unapproved_required_substitutions,
        "substitutions_without_rule": substitutions_without_rule,
        "replacement_operator_missing": replacement_operator_missing,
        "low_confidence_substitutions": low_confidence,
    }


def _parse_substitution_event(evidence: str) -> dict[str, Any] | None:
    if not evidence.startswith("substitution:") or evidence.startswith("substitution-rule:"):
        return None
    payload = evidence.removeprefix("substitution:")
    parts = payload.split(":")
    mapping = parts[0]
    if "->" not in mapping:
        return None
    missing_op, replacement_target = mapping.split("->", 1)
    return {
        "missing_op": missing_op,
        "replacement_target": replacement_target,
        "pending_approval": "pending-approval" in parts[1:],
    }


def _substitution_rules_by_missing_op(evidence: list[str]) -> dict[str, dict[str, Any]]:
    rules: dict[str, dict[str, Any]] = {}
    for item in evidence:
        rule = _parse_substitution_rule(item)
        if rule is not None:
            rules[rule["missing_op"]] = rule
    return rules


def _substitution_approval_evidence(event: dict[str, Any], evidence: list[str]) -> list[str]:
    expected_by_target = {
        "audio_device_to_analysis_chop": "device-source-declared:audio_device",
    }
    expected = expected_by_target.get(str(event.get("replacement_target") or ""))
    if expected is not None:
        return [item for item in evidence if item == expected]
    return [item for item in evidence if item.startswith("device-source-declared:")]


def _parse_substitution_rule(evidence: str) -> dict[str, Any] | None:
    if not evidence.startswith("substitution-rule:"):
        return None
    payload = evidence.removeprefix("substitution-rule:")
    parts = payload.split(":")
    if len(parts) < 2 or "->" not in parts[0]:
        return None
    missing_op, replacement_expr = parts[0].split("->", 1)
    return {
        "missing_op": missing_op,
        "replacement_ops": [item for item in replacement_expr.split("+") if item],
        "confidence": parts[1],
        "requires_approval": "requires-approval" in parts[2:],
    }


def _aggregate_availability_matrix_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    structured_cases: list[dict[str, Any]] = []
    known_build_cases: list[dict[str, Any]] = []
    missing_reason_records: list[dict[str, Any]] = []
    substitution_without_matrix: list[dict[str, Any]] = []

    for result in results:
        case_id = str(result.get("id") or "")
        matrix = result.get("availability_matrix")
        has_matrix = isinstance(matrix, dict)
        if has_matrix:
            structured_cases.append(result)
            td_build = str(matrix.get("td_build") or "")
            platform = str(matrix.get("platform") or "")
            if td_build and td_build != "unknown" and platform and platform != "unknown":
                known_build_cases.append(result)

            unavailable_count = int(matrix.get("unavailable_count") or 0)
            reasons = matrix.get("unavailable_reasons")
            reason_count = len(reasons) if isinstance(reasons, dict) else 0
            if unavailable_count > reason_count:
                missing_reason_records.append(
                    {
                        "case_id": case_id,
                        "unavailable_count": unavailable_count,
                        "reason_count": reason_count,
                    }
                )

        evidence = [str(item) for item in result.get("grounding_evidence", [])]
        substitution_events = [_parse_substitution_event(item) for item in evidence]
        if any(event is not None for event in substitution_events) and not has_matrix:
            substitution_without_matrix.append(result)

    return {
        "schema_version": 1,
        "ok": bool(structured_cases)
        and bool(known_build_cases)
        and not missing_reason_records
        and not substitution_without_matrix,
        "case_count": len(results),
        "structured_case_count": len(structured_cases),
        "known_build_case_count": len(known_build_cases),
        "missing_unavailable_reason_count": len(missing_reason_records),
        "substitution_without_matrix_count": len(substitution_without_matrix),
        "structured_case_ids": _case_ids(structured_cases),
        "known_build_case_ids": _case_ids(known_build_cases),
        "missing_unavailable_reason_cases": missing_reason_records,
        "substitution_without_matrix_case_ids": _case_ids(substitution_without_matrix),
    }


def _aggregate_compiler_stability(results: list[dict[str, Any]]) -> dict[str, Any]:
    results = _normal_case_results(results)
    compiled = [result for result in results if result.get("profile") == "concept_compiled"]
    blocked = [
        result
        for result in compiled
        if result.get("blocked_questions") or result.get("missing_facts")
    ]
    domain_failures = [
        result
        for result in compiled
        if result.get("checks", {}).get("compiled_domains", {}).get("ok") is False
    ]
    pattern_failures = [
        result
        for result in compiled
        if result.get("checks", {}).get("pattern_composition", {}).get("ok") is False
        or result.get("checks", {}).get("required_patterns", {}).get("ok") is False
    ]
    passed_compiled = [result for result in compiled if result.get("passed")]
    return {
        "ok": bool(compiled)
        and len(passed_compiled) == len(compiled)
        and not blocked
        and not domain_failures
        and not pattern_failures,
        "compiled_case_count": len(compiled),
        "passed_compiled_case_count": len(passed_compiled),
        "blocked_compiled_case_count": len(blocked),
        "compiled_domain_failure_count": len(domain_failures),
        "pattern_composition_failure_count": len(pattern_failures),
        "compiled_case_ids": [str(result["id"]) for result in compiled],
        "blocked_compiled_case_ids": [str(result["id"]) for result in blocked],
        "compiled_domain_failure_case_ids": [str(result["id"]) for result in domain_failures],
        "pattern_composition_failure_case_ids": [str(result["id"]) for result in pattern_failures],
    }


def _trace_profile_drift(expected_profile: Any, actual_profile: str) -> dict[str, str] | None:
    if expected_profile is None or str(expected_profile) == actual_profile:
        return None
    return {"expected": str(expected_profile), "actual": actual_profile}


def _trace_operator_drift(expected_operators: list[Any], actual_operators: list[str]) -> dict[str, list[str]] | None:
    expected = {str(operator) for operator in expected_operators}
    actual = set(actual_operators)
    missing = sorted(expected - actual)
    added = sorted(actual - expected)
    if not missing and not added:
        return None
    return {"missing": missing, "added": added}


def _trace_promoted_pattern_operator_drift(
    promoted_pattern: Any,
    actual_operators: list[str],
) -> dict[str, Any] | None:
    if not isinstance(promoted_pattern, dict):
        return None
    required_ops = promoted_pattern.get("required_ops")
    if not isinstance(required_ops, list):
        return None
    actual = set(actual_operators)
    missing = sorted(str(operator) for operator in required_ops if str(operator) not in actual)
    if not missing:
        return None
    return {
        "pattern_id": str(promoted_pattern.get("pattern_id") or ""),
        "missing": missing,
    }


def _weight(case: dict[str, Any], name: str) -> int:
    scoring = case.get("scoring") if isinstance(case.get("scoring"), dict) else {}
    if not scoring and isinstance(case.get("scoring_weights"), dict):
        scoring = case["scoring_weights"]
    return int(scoring.get(name, 1))


def _case_id(case: dict[str, Any]) -> str | None:
    raw = case.get("id", case.get("case_id"))
    return str(raw) if raw is not None else None


def _case_prompt(case: dict[str, Any]) -> str:
    raw = case.get("intent", case.get("prompt"))
    if raw is None:
        raise KeyError("intent")
    return str(raw)


def _expected_operator_sets(case: dict[str, Any]) -> list[list[str]]:
    return [
        [str(op_type) for op_type in operator_set]
        for operator_set in case.get("expected_operator_sets", [])
        if isinstance(operator_set, list)
    ]


def _expected_ops_for_client(case: dict[str, Any], expected_operator_sets: list[list[str]]) -> list[str]:
    expected_ops = list(case.get("expected_ops") or [])
    if expected_ops or not expected_operator_sets:
        return expected_ops
    return list(dict.fromkeys(op_type for operator_set in expected_operator_sets for op_type in operator_set))


def _network_structure_ok(
    expected_ops: list[str],
    expected_operator_sets: list[list[str]],
    actual_ops: list[str],
) -> bool:
    actual = set(actual_ops)
    if expected_operator_sets:
        return _matched_operator_set(expected_operator_sets, actual_ops) is not None
    return set(expected_ops).issubset(actual)


def _matched_operator_set(
    expected_operator_sets: list[list[str]],
    actual_ops: list[str],
) -> list[str] | None:
    actual = set(actual_ops)
    for operator_set in expected_operator_sets:
        if set(operator_set).issubset(actual):
            return operator_set
    return None


def _operator_coverage_for_case(
    expected_ops: list[str],
    expected_operator_sets: list[list[str]],
    actual_ops: list[str],
    matched_operator_set: list[str] | None,
) -> dict[str, Any]:
    actual = set(actual_ops)
    if expected_operator_sets:
        selected = matched_operator_set or min(
            expected_operator_sets,
            key=lambda operator_set: len(set(operator_set) - actual),
            default=[],
        )
        missing = sorted(str(operator) for operator in set(selected) - actual)
        return {
            "expected_operator_count": len(selected),
            "actual_operator_count": len(actual_ops),
            "missing_required_operators": missing,
            "operator_set_satisfied": matched_operator_set is not None,
            "matched_operator_set": matched_operator_set or [],
        }

    missing = sorted(str(operator) for operator in set(expected_ops) - actual)
    return {
        "expected_operator_count": len(expected_ops),
        "actual_operator_count": len(actual_ops),
        "missing_required_operators": missing,
        "operator_set_satisfied": True,
        "matched_operator_set": [],
    }


def _assembly_macro_ids(operations) -> list[str]:
    ids: list[str] = []
    for operation in operations:
        macro_id = operation.args.get("assembly_macro_id") if hasattr(operation, "args") else None
        if macro_id:
            ids.append(str(macro_id))
    return list(dict.fromkeys(ids))


def _candidate_profiles(plan) -> list[str]:
    if plan.candidate_graphs:
        return list(
            dict.fromkeys(profile for candidate in plan.candidate_graphs for profile in candidate.profiles)
        )
    return [plan.concept_graph.profile]


__all__ = [
    "StaticEvalTDClient",
    "evaluate_case",
    "evaluate_golden_cases",
    "assembly_control_binding_report",
    "families_for_ops",
    "family_for_op",
    "load_golden_cases",
    "pattern_eval_coverage_report",
    "trace_memory_reuse_coverage_report",
    "trace_promotion_coverage_report",
    "trace_baseline_envelope_from_eval_results",
    "trace_baseline_from_eval_results",
    "trace_replay_baseline_report",
    "trace_replay_drift_report",
]
