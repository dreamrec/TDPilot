#!/usr/bin/env python3
"""Evaluate release-gate metrics from benchmark/soak reports."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


REQUIRED_PARAM_SEMANTICS_PRIORITY_GROUPS = {
    "audio_control",
    "dat_callbacks_protocols",
    "feedback_top_processing",
    "glsl",
    "panel_parameters",
    "pop",
    "render_material",
}
MIN_SHOWPIECE_ASSEMBLED_CASES = 10
MIN_VALIDATION_CHECKS_PER_CASE = 6
MIN_PARAMETER_SAFETY_COVERED_OPERATORS = 40
MIN_PARAMETER_SAFETY_PRIORITY_OPERATORS = 40
MIN_PARAMETER_SAFETY_PRIORITY_GROUPS = 7
MIN_GENERATED_CODE_SUCCESS_CASES = 18
MIN_GENERATED_CODE_SUCCESS_BLOCKS = 25
MIN_GENERATED_CODE_SUCCESS_LANGUAGES = 2
MIN_GENERATED_CODE_RUNTIME_CONTRACTS = 25
MIN_OPERATOR_COVERAGE_CASES = 50
MIN_UNSUPPORTED_OPERATOR_AVOIDANCE_CASES = 1
MIN_DECOMPOSITION_MULTI_DOMAIN_CASES = 20
MIN_DECOMPOSITION_THREE_PLUS_DOMAIN_CASES = 10
MIN_DECOMPOSITION_TIME_BEHAVIOR_CASES = 1
MIN_AVAILABILITY_MATRIX_CASES = 1
MIN_AVAILABILITY_MATRIX_KNOWN_BUILD_CASES = 1
MIN_EXPECTED_BLOCKED_PROMPT_SAFETY_CASES = 1


def load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check_threshold(label: str, value: float, op: str, limit: float) -> dict[str, Any]:
    if math.isnan(value):
        return {"label": label, "status": "missing", "value": value, "target": f"{op} {limit}"}

    if op == "<=":
        passed = value <= limit
    elif op == ">=":
        passed = value >= limit
    else:
        raise ValueError(f"Unsupported operator: {op}")

    return {
        "label": label,
        "status": "pass" if passed else "fail",
        "value": value,
        "target": f"{op} {limit}",
    }


def evaluate(
    bench: dict[str, Any] | None,
    soak: dict[str, Any] | None,
    brain_eval: dict[str, Any] | None = None,
    brain_smoke: dict[str, Any] | None = None,
    brain_live_smoke: dict[str, Any] | None = None,
    operator_availability: dict[str, Any] | None = None,
    plugin_surface: dict[str, Any] | None = None,
    required_reports: set[str] | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    required_reports = required_reports or set()

    if (
        bench is None
        and soak is None
        and brain_eval is None
        and brain_smoke is None
        and brain_live_smoke is None
        and operator_availability is None
        and plugin_surface is None
    ):
        checks.append(
            {
                "label": "input reports provided",
                "status": "fail",
                "value": "none",
                "target": "bench and/or soak report required",
            }
        )
    if "brain_eval" in required_reports and brain_eval is None:
        checks.append(
            {
                "label": "brain eval report provided",
                "status": "missing",
                "value": "none",
                "target": "--brain-eval-report required",
            }
        )
    if "brain_smoke" in required_reports and brain_smoke is None:
        checks.append(
            {
                "label": "brain smoke report provided",
                "status": "missing",
                "value": "none",
                "target": "--brain-smoke-report required",
            }
        )
    if "plugin_surface" in required_reports and plugin_surface is None:
        checks.append(
            {
                "label": "plugin surface report provided",
                "status": "missing",
                "value": "none",
                "target": "--plugin-surface-report required",
            }
        )
    if "brain_live_smoke" in required_reports and brain_live_smoke is None:
        checks.append(
            {
                "label": "brain live smoke report provided",
                "status": "missing",
                "value": "none",
                "target": "--brain-live-smoke-report required",
            }
        )
    if "operator_availability" in required_reports and operator_availability is None:
        checks.append(
            {
                "label": "operator availability report provided",
                "status": "missing",
                "value": "none",
                "target": "--operator-availability-report required",
            }
        )

    if bench:
        benches = bench.get("benchmarks", {})
        bench_targets = {
            "td_get_nodes": 300.0,
            "td_get_params": 300.0,
            "td_set_params": 300.0,
            "td_capture_and_analyze_capture_only": 700.0,
        }
        for key, latency_limit in bench_targets.items():
            bench_entry = benches.get(key, {}) or {}
            p95 = float((bench_entry.get("latency_ms", {}) or {}).get("p95", math.nan))
            checks.append(check_threshold(f"{key} p95 latency ms", p95, "<=", latency_limit))

            error_rate = float(bench_entry.get("error_rate_pct", math.nan))
            checks.append(check_threshold(f"{key} error rate pct", error_rate, "<=", 1.0))

    if soak:
        results = soak.get("results", {})
        drop_rate = float(results.get("drop_rate_pct", math.nan))
        reconnect_median = float((results.get("reconnect_ms", {}) or {}).get("median", math.nan))
        reconnect_p95 = float((results.get("reconnect_ms", {}) or {}).get("p95", math.nan))

        checks.append(check_threshold("event drop rate pct", drop_rate, "<=", 0.5))
        checks.append(check_threshold("reconnect median ms", reconnect_median, "<=", 3000.0))
        checks.append(check_threshold("reconnect p95 ms", reconnect_p95, "<=", 8000.0))

    if brain_eval:
        checks.append(
            check_threshold(
                "brain golden eval report ok",
                _bool_value(brain_eval.get("ok")),
                ">=",
                1.0,
            )
        )

        case_count = float(brain_eval.get("case_count", math.nan))
        checks.append(check_threshold("brain golden eval case count", case_count, ">=", 50.0))

        failed_cases = float(brain_eval.get("failed", math.nan))
        checks.append(check_threshold("brain golden eval failed cases", failed_cases, "<=", 0.0))

        coverage = brain_eval.get("pattern_coverage", {}) or {}
        missing_patterns = coverage.get("missing_patterns", [])
        stale_patterns = coverage.get("stale_pattern_references", [])
        pattern_count = float(coverage.get("pattern_count", math.nan))
        checks.append(
            check_threshold(
                "brain pattern coverage missing count",
                float(len(missing_patterns) if isinstance(missing_patterns, list) else math.nan),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain pattern coverage stale reference count",
                float(len(stale_patterns) if isinstance(stale_patterns, list) else math.nan),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain pattern coverage official source checked count",
                float(coverage.get("source_checked_pattern_count", math.nan)),
                ">=",
                pattern_count,
            )
        )
        checks.append(
            check_threshold(
                "brain pattern coverage invalid source count",
                float(coverage.get("invalid_source_count", math.nan)),
                "<=",
                0.0,
            )
        )

        compiler = brain_eval.get("compiler_stability", {}) or {}
        checks.append(
            check_threshold(
                "brain compiler stability compiled case count",
                float(compiler.get("compiled_case_count", math.nan)),
                ">=",
                30.0,
            )
        )
        compiled_case_count = float(compiler.get("compiled_case_count", math.nan))
        passed_compiled_case_count = float(compiler.get("passed_compiled_case_count", math.nan))
        checks.append(
            check_threshold(
                "brain compiler stability failed cases",
                compiled_case_count - passed_compiled_case_count,
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain compiler stability blocked cases",
                float(compiler.get("blocked_compiled_case_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain compiler stability domain failures",
                float(compiler.get("compiled_domain_failure_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain compiler stability pattern failures",
                float(compiler.get("pattern_composition_failure_count", math.nan)),
                "<=",
                0.0,
            )
        )

        trace = brain_eval.get("trace_replay", {}) or {}
        checks.append(
            check_threshold(
                "brain trace replay drift count",
                float(trace.get("drift_count", math.nan)),
                "<=",
                0.0,
            )
        )

        readability = brain_eval.get("readability_metrics", {}) or {}
        assembled_count = float(readability.get("assembled_case_count", math.nan))
        fully_readable_count = float(readability.get("fully_readable_assembled_case_count", math.nan))
        avg_readability_score = float(readability.get("avg_assembled_score", math.nan))
        avg_readability_max_score = float(readability.get("avg_assembled_max_score", math.nan))
        checks.append(
            check_threshold(
                "brain readability assembled case count",
                assembled_count,
                ">=",
                1.0,
            )
        )
        checks.append(
            check_threshold(
                "brain readability fully assembled count",
                fully_readable_count - assembled_count,
                ">=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain readability average score gap",
                avg_readability_score - avg_readability_max_score,
                ">=",
                0.0,
            )
        )
        showpiece = brain_eval.get("showpiece_assembly_metrics", {}) or {}
        checks.append(
            check_threshold(
                "brain showpiece case count",
                float(showpiece.get("showpiece_case_count", math.nan)),
                ">=",
                float(MIN_SHOWPIECE_ASSEMBLED_CASES),
            )
        )
        checks.append(
            check_threshold(
                "brain showpiece assembled case count",
                float(showpiece.get("assembled_showpiece_case_count", math.nan)),
                ">=",
                float(MIN_SHOWPIECE_ASSEMBLED_CASES),
            )
        )
        checks.append(
            check_threshold(
                "brain showpiece fully readable case count",
                float(showpiece.get("fully_readable_showpiece_case_count", math.nan)),
                ">=",
                float(MIN_SHOWPIECE_ASSEMBLED_CASES),
            )
        )
        checks.append(
            check_threshold(
                "brain showpiece unassembled case count",
                _list_count(showpiece.get("unassembled_showpiece_case_ids")),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain showpiece unreadable case count",
                _list_count(showpiece.get("not_fully_readable_showpiece_case_ids")),
                "<=",
                0.0,
            )
        )
        validation_metrics = brain_eval.get("validation_metrics", {}) or {}
        checks.append(
            check_threshold(
                "brain validation metrics minimum check count",
                float(validation_metrics.get("min_validation_check_count", math.nan)),
                ">=",
                float(MIN_VALIDATION_CHECKS_PER_CASE),
            )
        )
        checks.append(
            check_threshold(
                "brain validation metrics weak case count",
                float(validation_metrics.get("weak_validation_case_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain validation metrics missing expectation count",
                float(validation_metrics.get("missing_validation_expectation_count", math.nan)),
                "<=",
                0.0,
            )
        )
        parameter_safety = brain_eval.get("parameter_safety_metrics", {}) or {}
        checks.append(
            check_threshold(
                "brain parameter safety covered operator count",
                float(parameter_safety.get("covered_operator_count", math.nan)),
                ">=",
                float(MIN_PARAMETER_SAFETY_COVERED_OPERATORS),
            )
        )
        checks.append(
            check_threshold(
                "brain parameter safety priority operator count",
                float(parameter_safety.get("priority_operator_count", math.nan)),
                ">=",
                float(MIN_PARAMETER_SAFETY_PRIORITY_OPERATORS),
            )
        )
        checks.append(
            check_threshold(
                "brain parameter safety missing operator count",
                float(parameter_safety.get("missing_operator_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain parameter safety invalid source count",
                float(parameter_safety.get("invalid_source_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain parameter safety priority group count",
                float(parameter_safety.get("priority_group_count", math.nan)),
                ">=",
                float(MIN_PARAMETER_SAFETY_PRIORITY_GROUPS),
            )
        )
        checks.append(
            check_threshold(
                "brain parameter safety priority group missing operator count",
                float(parameter_safety.get("priority_group_missing_operator_count", math.nan)),
                "<=",
                0.0,
            )
        )
        operator_coverage = brain_eval.get("operator_coverage_metrics", {}) or {}
        checks.append(
            check_threshold(
                "brain operator coverage checked case count",
                float(operator_coverage.get("checked_case_count", math.nan)),
                ">=",
                float(MIN_OPERATOR_COVERAGE_CASES),
            )
        )
        checks.append(
            check_threshold(
                "brain operator coverage missing required operator count",
                float(operator_coverage.get("missing_required_operator_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain operator coverage operator set failure count",
                float(operator_coverage.get("operator_set_failure_count", math.nan)),
                "<=",
                0.0,
            )
        )
        unsupported_operators = brain_eval.get("unsupported_operator_avoidance_metrics", {}) or {}
        checks.append(
            check_threshold(
                "brain unsupported operator checked case count",
                float(unsupported_operators.get("checked_forbidden_operator_case_count", math.nan)),
                ">=",
                float(MIN_UNSUPPORTED_OPERATOR_AVOIDANCE_CASES),
            )
        )
        checks.append(
            check_threshold(
                "brain unsupported operator forbidden case count",
                float(unsupported_operators.get("forbidden_operator_case_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain unsupported operator present count",
                _list_count(unsupported_operators.get("forbidden_ops_present")),
                "<=",
                0.0,
            )
        )
        decomposition = brain_eval.get("decomposition_accuracy_metrics", {}) or {}
        checks.append(
            check_threshold(
                "brain decomposition multi-domain case count",
                float(decomposition.get("multi_domain_case_count", math.nan)),
                ">=",
                float(MIN_DECOMPOSITION_MULTI_DOMAIN_CASES),
            )
        )
        checks.append(
            check_threshold(
                "brain decomposition three-plus-domain case count",
                float(decomposition.get("three_plus_domain_case_count", math.nan)),
                ">=",
                float(MIN_DECOMPOSITION_THREE_PLUS_DOMAIN_CASES),
            )
        )
        checks.append(
            check_threshold(
                "brain decomposition domain failure count",
                float(decomposition.get("compiled_domain_failure_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain decomposition time behavior checked case count",
                float(decomposition.get("time_behavior_checked_case_count", math.nan)),
                ">=",
                float(MIN_DECOMPOSITION_TIME_BEHAVIOR_CASES),
            )
        )
        checks.append(
            check_threshold(
                "brain decomposition time behavior failure count",
                float(decomposition.get("time_behavior_failure_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain decomposition pattern failure count",
                float(decomposition.get("pattern_composition_failure_count", math.nan)),
                "<=",
                0.0,
            )
        )
        delivery_phases = brain_eval.get("delivery_phase_coverage", {}) or {}
        checks.append(
            check_threshold(
                "brain delivery phase coverage phase count",
                float(delivery_phases.get("phase_count", math.nan)),
                ">=",
                4.0,
            )
        )
        checks.append(
            check_threshold(
                "brain delivery phase coverage complete phase count",
                float(delivery_phases.get("complete_phase_count", math.nan)),
                ">=",
                4.0,
            )
        )
        checks.append(
            check_threshold(
                "brain delivery phase coverage incomplete phase count",
                float(delivery_phases.get("incomplete_phase_count", math.nan)),
                "<=",
                0.0,
            )
        )
        time_metrics = brain_eval.get("time_metrics", {}) or {}
        first_green = time_metrics.get("time_to_first_green_cycles", {}) or {}
        checks.append(
            check_threshold(
                "brain time to first green max cycles",
                float(first_green.get("max", math.nan)),
                "<=",
                1.0,
            )
        )
        checks.append(
            check_threshold(
                "brain time to first green average cycles",
                float(first_green.get("avg", math.nan)),
                "<=",
                1.0,
            )
        )
        assembly_bindings = brain_eval.get("assembly_control_bindings", {}) or {}
        checks.append(
            check_threshold(
                "brain assembly control binding missing count",
                float(assembly_bindings.get("missing_count", math.nan)),
                "<=",
                0.0,
            )
        )
        param_semantics = brain_eval.get("param_semantics_coverage", {}) or {}
        checks.append(
            check_threshold(
                "brain param semantics missing operator count",
                float(param_semantics.get("missing_operator_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain param semantics invalid source count",
                float(param_semantics.get("invalid_source_count", math.nan)),
                "<=",
                0.0,
            )
        )
        priority_groups = param_semantics.get("priority_groups", {})
        present_priority_groups = set(priority_groups) if isinstance(priority_groups, dict) else set()
        missing_priority_group_count = len(REQUIRED_PARAM_SEMANTICS_PRIORITY_GROUPS - present_priority_groups)
        checks.append(
            check_threshold(
                "brain param semantics missing priority group count",
                float(missing_priority_group_count),
                "<=",
                0.0,
            )
        )
        priority_group_missing_ops = math.nan
        if isinstance(priority_groups, dict):
            priority_group_missing_ops = float(
                sum(
                    len(group.get("missing_operators", []))
                    for group in priority_groups.values()
                    if isinstance(group, dict) and isinstance(group.get("missing_operators", []), list)
                )
            )
        checks.append(
            check_threshold(
                "brain param semantics priority group missing operator count",
                priority_group_missing_ops,
                "<=",
                0.0,
            )
        )
        availability = brain_eval.get("operator_availability_coverage", {}) or {}
        checks.append(
            check_threshold(
                "brain operator availability missing substitution rule count",
                float(availability.get("missing_required_rule_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain operator availability invalid source count",
                float(availability.get("invalid_source_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain operator availability missing tradeoff count",
                float(availability.get("missing_tradeoff_count", math.nan)),
                "<=",
                0.0,
            )
        )
        availability_matrix = brain_eval.get("availability_matrix_metrics", {}) or {}
        checks.append(
            check_threshold(
                "brain availability matrix structured case count",
                float(availability_matrix.get("structured_case_count", math.nan)),
                ">=",
                float(MIN_AVAILABILITY_MATRIX_CASES),
            )
        )
        checks.append(
            check_threshold(
                "brain availability matrix known build case count",
                float(availability_matrix.get("known_build_case_count", math.nan)),
                ">=",
                float(MIN_AVAILABILITY_MATRIX_KNOWN_BUILD_CASES),
            )
        )
        checks.append(
            check_threshold(
                "brain availability matrix missing reason count",
                float(availability_matrix.get("missing_unavailable_reason_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain availability matrix substitution missing count",
                float(availability_matrix.get("substitution_without_matrix_count", math.nan)),
                "<=",
                0.0,
            )
        )
        validation_probes = brain_eval.get("validation_probe_coverage", {}) or {}
        checks.append(
            check_threshold(
                "brain validation probe missing profile count",
                float(validation_probes.get("missing_required_profile_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain validation probe invalid source count",
                float(validation_probes.get("invalid_source_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain validation probe uncontrolled expensive count",
                float(validation_probes.get("uncontrolled_expensive_probe_count", math.nan)),
                "<=",
                0.0,
            )
        )
        generated_code_harness = brain_eval.get("generated_code_harness_coverage", {}) or {}
        checks.append(
            check_threshold(
                "brain generated code harness missing language count",
                float(generated_code_harness.get("missing_language_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain generated code harness missing static check count",
                float(generated_code_harness.get("missing_static_check_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain generated code harness missing runtime check count",
                float(generated_code_harness.get("missing_runtime_check_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain generated code harness invalid source count",
                float(generated_code_harness.get("invalid_source_count", math.nan)),
                "<=",
                0.0,
            )
        )
        generated_code_success = brain_eval.get("generated_code_success_metrics", {}) or {}
        checks.append(
            check_threshold(
                "brain generated code success case count",
                float(generated_code_success.get("generated_code_case_count", math.nan)),
                ">=",
                float(MIN_GENERATED_CODE_SUCCESS_CASES),
            )
        )
        checks.append(
            check_threshold(
                "brain generated code success block count",
                float(generated_code_success.get("generated_code_block_count", math.nan)),
                ">=",
                float(MIN_GENERATED_CODE_SUCCESS_BLOCKS),
            )
        )
        checks.append(
            check_threshold(
                "brain generated code success language coverage",
                float(generated_code_success.get("language_count", math.nan)),
                ">=",
                float(MIN_GENERATED_CODE_SUCCESS_LANGUAGES),
            )
        )
        checks.append(
            check_threshold(
                "brain generated code success static issue count",
                float(generated_code_success.get("static_issue_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain generated code success runtime contract count",
                float(generated_code_success.get("runtime_contract_count", math.nan)),
                ">=",
                float(MIN_GENERATED_CODE_RUNTIME_CONTRACTS),
            )
        )
        checks.append(
            check_threshold(
                "brain generated code success missing runtime contract count",
                float(generated_code_success.get("runtime_contract_missing_count", math.nan)),
                "<=",
                0.0,
            )
        )
        trace_promotion = brain_eval.get("trace_promotion_coverage", {}) or {}
        checks.append(
            check_threshold(
                "brain trace promotion eligible fixture count",
                float(trace_promotion.get("eligible_trace_fixture_count", math.nan)),
                ">=",
                2.0,
            )
        )
        checks.append(
            check_threshold(
                "brain trace promotion promoted fixture count",
                float(trace_promotion.get("promoted_fixture_count", math.nan)),
                ">=",
                2.0,
            )
        )
        checks.append(
            check_threshold(
                "brain trace promotion blocked fixture count",
                float(trace_promotion.get("blocked_fixture_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain trace promotion invalid source count",
                float(trace_promotion.get("invalid_source_count", math.nan)),
                "<=",
                0.0,
            )
        )
        trace_memory = brain_eval.get("trace_memory_reuse_coverage", {}) or {}
        checks.append(
            check_threshold(
                "brain trace memory reuse fixture count",
                float(trace_memory.get("fixture_count", math.nan)),
                ">=",
                2.0,
            )
        )
        checks.append(
            check_threshold(
                "brain trace memory reuse loaded pattern count",
                float(trace_memory.get("loaded_pattern_count", math.nan)),
                ">=",
                2.0,
            )
        )
        checks.append(
            check_threshold(
                "brain trace memory reuse reused fixture count",
                float(trace_memory.get("reused_fixture_count", math.nan)),
                ">=",
                2.0,
            )
        )
        checks.append(
            check_threshold(
                "brain trace memory reuse miss count",
                float(trace_memory.get("miss_count", math.nan)),
                "<=",
                0.0,
            )
        )
        prompt_safety = brain_eval.get("prompt_safety_metrics", {}) or {}
        checks.append(
            check_threshold(
                "brain prompt safety expected blocked case count",
                float(prompt_safety.get("expected_blocked_case_count", math.nan)),
                ">=",
                float(MIN_EXPECTED_BLOCKED_PROMPT_SAFETY_CASES),
            )
        )
        checks.append(
            check_threshold(
                "brain prompt safety failed expected blocked case count",
                _list_count(prompt_safety.get("failed_expected_blocked_case_ids")),
                "<=",
                0.0,
            )
        )
        runtime_safety = brain_eval.get("runtime_safety_metrics", {}) or {}
        checks.append(
            check_threshold(
                "brain runtime safety case count",
                float(runtime_safety.get("case_count", math.nan)),
                ">=",
                1.0,
            )
        )
        checks.append(
            check_threshold(
                "brain runtime safety forbidden operator fixture count",
                float(runtime_safety.get("checked_forbidden_operator_case_count", math.nan)),
                ">=",
                1.0,
            )
        )
        checks.append(
            check_threshold(
                "brain runtime safety blocked case count",
                float(runtime_safety.get("blocked_case_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain runtime safety missing fact case count",
                float(runtime_safety.get("missing_fact_case_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain runtime safety forbidden operator case count",
                float(runtime_safety.get("forbidden_operator_case_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain runtime safety rollback behavior failures",
                float(runtime_safety.get("rollback_behavior_failure_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain runtime safety final state failures",
                float(runtime_safety.get("final_state_quality_failure_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain runtime safety operator set failures",
                float(runtime_safety.get("operator_set_failure_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain runtime safety max plan op failures",
                float(runtime_safety.get("max_plan_ops_failure_count", math.nan)),
                "<=",
                0.0,
            )
        )
        rollback_frequency = brain_eval.get("rollback_frequency_metrics", {}) or {}
        rollback_case_count = float(rollback_frequency.get("case_count", math.nan))
        rollback_enabled_count = float(
            rollback_frequency.get("rollback_enabled_case_count", math.nan)
        )
        checks.append(
            check_threshold(
                "brain rollback frequency enabled case count",
                rollback_enabled_count - rollback_case_count,
                ">=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain rollback frequency behavior failure count",
                float(rollback_frequency.get("rollback_behavior_failure_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain rollback frequency required case count",
                float(rollback_frequency.get("rollback_required_case_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain rollback frequency performed case count",
                float(rollback_frequency.get("rollback_performed_count", math.nan)),
                "<=",
                0.0,
            )
        )
        substitution_quality = brain_eval.get("substitution_quality_metrics", {}) or {}
        checks.append(
            check_threshold(
                "brain substitution quality case count",
                float(substitution_quality.get("case_count", math.nan)),
                ">=",
                1.0,
            )
        )
        checks.append(
            check_threshold(
                "brain substitution quality substitution case count",
                float(substitution_quality.get("substitution_case_count", math.nan)),
                ">=",
                1.0,
            )
        )
        checks.append(
            check_threshold(
                "brain substitution quality approved count",
                float(substitution_quality.get("approved_substitution_count", math.nan)),
                ">=",
                1.0,
            )
        )
        checks.append(
            check_threshold(
                "brain substitution quality pending approvals",
                float(substitution_quality.get("pending_approval_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain substitution quality unapproved required substitutions",
                float(substitution_quality.get("unapproved_required_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain substitution quality missing rule count",
                float(substitution_quality.get("substitution_without_rule_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain substitution quality missing replacement count",
                float(substitution_quality.get("replacement_operator_missing_count", math.nan)),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain substitution quality low confidence count",
                float(substitution_quality.get("low_confidence_count", math.nan)),
                "<=",
                0.0,
            )
        )

    if brain_smoke:
        checks.append(
            check_threshold("brain smoke report ok", _bool_value(brain_smoke.get("ok")), ">=", 1.0)
        )

        scenario_count = float(brain_smoke.get("scenario_count", math.nan))
        checks.append(check_threshold("brain smoke scenario count", scenario_count, ">=", 1.0))

        scenarios = brain_smoke.get("scenarios", [])
        failed_scenarios = math.nan
        if isinstance(scenarios, list):
            failed_scenarios = float(
                sum(
                    1
                    for scenario in scenarios
                    if not isinstance(scenario, dict)
                    or scenario.get("status") != "planned"
                    or bool(scenario.get("missing_expected_ops"))
                    or bool(scenario.get("blocked_questions"))
                )
            )
        checks.append(check_threshold("brain smoke failed scenarios", failed_scenarios, "<=", 0.0))
        missing_probe_evidence = math.nan
        if isinstance(scenarios, list):
            missing_probe_evidence = float(
                sum(
                    1
                    for scenario in scenarios
                    if isinstance(scenario, dict)
                    and scenario.get("status") == "planned"
                    and (
                        not isinstance(scenario.get("profile_probes"), list)
                        or not scenario.get("profile_probes")
                        or not isinstance(scenario.get("profile_probe_results"), list)
                        or not scenario.get("profile_probe_results")
                    )
                )
            )
        checks.append(
            check_threshold("brain smoke missing profile probe evidence", missing_probe_evidence, "<=", 0.0)
        )
        invalid_probe_results = math.nan
        if isinstance(scenarios, list):
            valid_probe_statuses = {"static_pass", "static_incomplete", "runtime_contract_present"}
            invalid_probe_results = float(
                sum(
                    1
                    for scenario in scenarios
                    if isinstance(scenario, dict)
                    for result in scenario.get("profile_probe_results", [])
                    if not isinstance(result, dict) or result.get("status") not in valid_probe_statuses
                )
            )
        checks.append(
            check_threshold("brain smoke invalid profile probe results", invalid_probe_results, "<=", 0.0)
        )
        expensive_probe_metrics = _expensive_probe_opt_in_metrics(scenarios)
        checks.append(
            check_threshold(
                "brain smoke expensive probe opt-in scenario count",
                expensive_probe_metrics["opt_in_scenario_count"],
                ">=",
                1.0,
            )
        )
        checks.append(
            check_threshold(
                "brain smoke uncontrolled expensive probe count",
                expensive_probe_metrics["uncontrolled_expensive_probe_count"],
                "<=",
                0.0,
            )
        )

        checks.append(
            check_threshold("brain smoke mutated td", _bool_value(brain_smoke.get("mutated_td")), "<=", 0.0)
        )

        generated = brain_smoke.get("generated_code_summary", {}) or {}
        generated_block_count = float(generated.get("block_count", math.nan))
        checks.append(
            check_threshold(
                "brain smoke generated code block count",
                generated_block_count,
                ">=",
                1.0,
            )
        )
        checks.append(
            check_threshold(
                "brain smoke generated code language coverage",
                _required_item_coverage(generated.get("languages"), {"glsl", "python"}),
                ">=",
                2.0,
            )
        )
        checks.append(
            check_threshold(
                "brain smoke generated code runtime contract count",
                float(generated.get("runtime_contract_count", math.nan)) - generated_block_count,
                ">=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain smoke generated code runtime contract coverage",
                _required_item_coverage(
                    generated.get("runtime_contract_checks"),
                    {"compile_state", "callback_guard_present", "topology_capacity"},
                ),
                ">=",
                3.0,
            )
        )
        checks.append(
            check_threshold(
                "brain smoke generated code source payload leak",
                _bool_value(generated.get("source_payloads_included")),
                "<=",
                0.0,
            )
        )

    if brain_live_smoke:
        checks.append(
            check_threshold(
                "brain live smoke report ok",
                _bool_value(brain_live_smoke.get("ok")),
                ">=",
                1.0,
            )
        )
        checks.append(
            check_threshold(
                "brain live smoke mode",
                _matches_value(brain_live_smoke.get("mode"), "live"),
                ">=",
                1.0,
            )
        )
        checks.append(
            check_threshold(
                "brain live smoke connection error",
                _present_value(brain_live_smoke.get("connection_error")),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain live smoke td health ok",
                _td_health_ok_value(brain_live_smoke.get("td_health")),
                ">=",
                1.0,
            )
        )
        checks.append(
            check_threshold(
                "brain live smoke scenario count",
                float(brain_live_smoke.get("scenario_count", math.nan)),
                ">=",
                1.0,
            )
        )

        scenarios = brain_live_smoke.get("scenarios", [])
        planned_scenarios = math.nan
        unexpected_scenarios = math.nan
        missing_probe_evidence = math.nan
        invalid_probe_results = math.nan
        glsl_advanced_pop_topology_scenarios = math.nan
        if isinstance(scenarios, list):
            planned_scenarios = float(
                sum(
                    1
                    for scenario in scenarios
                    if isinstance(scenario, dict) and scenario.get("status") == "planned"
                )
            )
            allowed_statuses = {"planned", "skipped_unavailable"}
            unexpected_scenarios = float(
                sum(
                    1
                    for scenario in scenarios
                    if not isinstance(scenario, dict)
                    or scenario.get("status") not in allowed_statuses
                    or (
                        scenario.get("status") == "planned"
                        and (
                            bool(scenario.get("missing_expected_ops"))
                            or bool(scenario.get("blocked_questions"))
                        )
                    )
                )
            )
            missing_probe_evidence = float(
                sum(
                    1
                    for scenario in scenarios
                    if isinstance(scenario, dict)
                    and scenario.get("status") == "planned"
                    and (
                        not isinstance(scenario.get("profile_probes"), list)
                        or not scenario.get("profile_probes")
                        or not isinstance(scenario.get("profile_probe_results"), list)
                        or not scenario.get("profile_probe_results")
                    )
                )
            )
            valid_probe_statuses = {"static_pass", "static_incomplete", "runtime_contract_present"}
            invalid_probe_results = float(
                sum(
                    1
                    for scenario in scenarios
                    if isinstance(scenario, dict) and scenario.get("status") == "planned"
                    for result in scenario.get("profile_probe_results", [])
                    if not isinstance(result, dict) or result.get("status") not in valid_probe_statuses
                )
            )
            glsl_advanced_pop_topology_scenarios = float(
                sum(
                    1
                    for scenario in scenarios
                    if isinstance(scenario, dict)
                    and scenario.get("id") == "glsl_advanced_pop_topology"
                    and scenario.get("status") == "planned"
                )
            )
        checks.append(
            check_threshold("brain live smoke planned scenario count", planned_scenarios, ">=", 1.0)
        )
        checks.append(
            check_threshold(
                "brain live smoke unexpected scenario count",
                unexpected_scenarios,
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain live smoke missing profile probe evidence",
                missing_probe_evidence,
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain live smoke invalid profile probe results",
                invalid_probe_results,
                "<=",
                0.0,
            )
        )
        expensive_probe_metrics = _expensive_probe_opt_in_metrics(scenarios)
        checks.append(
            check_threshold(
                "brain live smoke expensive probe opt-in scenario count",
                expensive_probe_metrics["opt_in_scenario_count"],
                ">=",
                1.0,
            )
        )
        checks.append(
            check_threshold(
                "brain live smoke uncontrolled expensive probe count",
                expensive_probe_metrics["uncontrolled_expensive_probe_count"],
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain live smoke mutated td",
                _bool_value(brain_live_smoke.get("mutated_td")),
                ">=",
                1.0,
            )
        )
        checks.append(
            check_threshold(
                "brain live smoke glsl advanced pop topology scenario",
                glsl_advanced_pop_topology_scenarios,
                ">=",
                1.0,
            )
        )
        generated = brain_live_smoke.get("generated_code_summary", {}) or {}
        generated_block_count = float(generated.get("block_count", math.nan))
        checks.append(
            check_threshold(
                "brain live smoke generated code block count",
                generated_block_count,
                ">=",
                1.0,
            )
        )
        checks.append(
            check_threshold(
                "brain live smoke generated code language coverage",
                _required_item_coverage(generated.get("languages"), {"glsl", "python"}),
                ">=",
                2.0,
            )
        )
        checks.append(
            check_threshold(
                "brain live smoke generated code runtime contract count",
                float(generated.get("runtime_contract_count", math.nan)) - generated_block_count,
                ">=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "brain live smoke generated code runtime contract coverage",
                _required_item_coverage(
                    generated.get("runtime_contract_checks"),
                    {"compile_state", "callback_guard_present", "topology_capacity"},
                ),
                ">=",
                3.0,
            )
        )
        checks.append(
            check_threshold(
                "brain live smoke generated code source payload leak",
                _bool_value(generated.get("source_payloads_included")),
                "<=",
                0.0,
            )
        )
        transactional_smoke = brain_live_smoke.get("transactional_generated_code_smoke", {}) or {}
        checks.append(
            check_threshold(
                "brain live smoke transactional generated code ok",
                _strict_bool_value(transactional_smoke.get("ok")),
                ">=",
                1.0,
            )
        )
        checks.append(
            check_threshold(
                "brain live smoke transactional generated code cleanup ok",
                _transactional_cleanup_ok_value(transactional_smoke),
                ">=",
                1.0,
            )
        )

    if operator_availability is not None:
        checks.extend(_operator_availability_checks(operator_availability))

    if plugin_surface is not None:
        checks.append(
            check_threshold(
                "plugin surface report ok", _bool_value(plugin_surface.get("ok")), ">=", 1.0
            )
        )
        checks.append(
            check_threshold(
                "plugin surface tool count",
                float(plugin_surface.get("tool_count", math.nan)),
                ">=",
                110.0,
            )
        )
        checks.append(
            check_threshold(
                "plugin surface brain skill count",
                float(plugin_surface.get("brain_skill_count", math.nan)),
                ">=",
                5.0,
            )
        )
        checks.append(
            check_threshold(
                "plugin surface agent count",
                float(plugin_surface.get("agent_count", math.nan)),
                ">=",
                4.0,
            )
        )
        checks.append(
            check_threshold(
                "plugin surface hook count",
                float(plugin_surface.get("hook_count", math.nan)),
                ">=",
                1.0,
            )
        )
        checks.append(
            check_threshold(
                "plugin surface missing artifact count",
                _list_count(plugin_surface.get("missing_artifacts")),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "plugin surface mirror mismatch count",
                _list_count(plugin_surface.get("mirror_mismatches")),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "plugin surface personal path leak count",
                _list_count(plugin_surface.get("personal_path_leaks")),
                "<=",
                0.0,
            )
        )

        local_first = plugin_surface.get("local_first", {}) or {}
        checks.append(
            check_threshold(
                "plugin surface hosted llm dependency leak count",
                _list_count(local_first.get("hosted_llm_dependency_leaks")),
                "<=",
                0.0,
            )
        )
        checks.append(
            check_threshold(
                "plugin surface local-first report ok",
                _bool_value(local_first.get("ok")),
                ">=",
                1.0,
            )
        )

        mcp_config = plugin_surface.get("mcp_config", {}) or {}
        hooks = plugin_surface.get("hooks", {}) or {}
        codex_manifest = plugin_surface.get("codex_manifest", {}) or {}
        claude_manifest = plugin_surface.get("claude_manifest", {}) or {}
        checks.append(
            check_threshold(
                "plugin surface mcp placeholder",
                _bool_value(mcp_config.get("uses_plugin_root_placeholder")),
                ">=",
                1.0,
            )
        )
        for label, value in (
            ("plugin surface hook check module", hooks.get("uses_hook_check_module")),
            ("plugin surface hook runner", hooks.get("uses_hook_runner")),
            ("plugin surface post tool hook", hooks.get("has_post_tool_use_guard")),
            ("plugin surface stop release hook", hooks.get("has_stop_release_guard")),
            ("plugin surface codex skills manifest", codex_manifest.get("has_skills")),
            ("plugin surface codex agents manifest", codex_manifest.get("has_agents")),
            ("plugin surface codex mcp manifest", codex_manifest.get("has_mcp_servers")),
            ("plugin surface claude skills manifest", claude_manifest.get("has_skills")),
            ("plugin surface claude agents manifest", claude_manifest.get("has_agents")),
            ("plugin surface claude hooks manifest", claude_manifest.get("has_hooks")),
            ("plugin surface claude mcp manifest", claude_manifest.get("has_mcp_servers")),
        ):
            checks.append(check_threshold(label, _bool_value(value), ">=", 1.0))

    passed = [c for c in checks if c["status"] == "pass"]
    failed = [c for c in checks if c["status"] == "fail"]
    missing = [c for c in checks if c["status"] == "missing"]
    ok = len(failed) == 0
    release_readiness = _release_readiness_report(
        brain_eval=brain_eval,
        brain_smoke=brain_smoke,
        brain_live_smoke=brain_live_smoke,
        operator_availability=operator_availability,
        plugin_surface=plugin_surface,
        required_reports=required_reports,
        failed_check_count=len(failed),
        missing_check_count=len(missing),
    )

    return {
        "schema_version": 1,
        "ok": ok,
        "summary": {
            "total": len(checks),
            "passed": len(passed),
            "failed": len(failed),
            "missing": len(missing),
            "ok": ok,
        },
        "release_readiness": release_readiness,
        "checks": checks,
    }


def _release_readiness_report(
    *,
    brain_eval: dict[str, Any] | None,
    brain_smoke: dict[str, Any] | None,
    brain_live_smoke: dict[str, Any] | None,
    operator_availability: dict[str, Any] | None,
    plugin_surface: dict[str, Any] | None,
    required_reports: set[str],
    failed_check_count: int,
    missing_check_count: int,
) -> dict[str, Any]:
    categories = [
        _readiness_category(
            category_id="brain_eval",
            required="brain_eval" in required_reports,
            report=brain_eval,
            ok=bool(brain_eval)
            and bool(brain_eval.get("ok"))
            and bool((brain_eval.get("delivery_phase_coverage") or {}).get("ok")),
            evidence={
                "case_count": (brain_eval or {}).get("case_count"),
                "delivery_phase_complete_count": (
                    (brain_eval or {}).get("delivery_phase_coverage") or {}
                ).get("complete_phase_count"),
                "delivery_phase_incomplete_count": (
                    (brain_eval or {}).get("delivery_phase_coverage") or {}
                ).get("incomplete_phase_count"),
            }
            if brain_eval
            else {},
        ),
        _readiness_category(
            category_id="brain_smoke",
            required="brain_smoke" in required_reports,
            report=brain_smoke,
            ok=bool(brain_smoke)
            and bool(brain_smoke.get("ok"))
            and str(brain_smoke.get("mode")) == "dry_run"
            and not bool(brain_smoke.get("mutated_td")),
            evidence={
                "mode": (brain_smoke or {}).get("mode"),
                "scenario_count": (brain_smoke or {}).get("scenario_count"),
                "generated_code_block_count": (
                    (brain_smoke or {}).get("generated_code_summary") or {}
                ).get("block_count"),
            }
            if brain_smoke
            else {},
        ),
        _readiness_category(
            category_id="brain_live_smoke",
            required="brain_live_smoke" in required_reports,
            report=brain_live_smoke,
            ok=bool(brain_live_smoke)
            and bool(brain_live_smoke.get("ok"))
            and str(brain_live_smoke.get("mode")) == "live"
            and bool(brain_live_smoke.get("mutated_td"))
            and _td_health_ok_value(brain_live_smoke.get("td_health")) >= 1.0,
            evidence={
                "mode": (brain_live_smoke or {}).get("mode"),
                "scenario_count": (brain_live_smoke or {}).get("scenario_count"),
                "td_health_status": ((brain_live_smoke or {}).get("td_health") or {}).get("status"),
            }
            if brain_live_smoke
            else {},
        ),
        _readiness_category(
            category_id="operator_availability",
            required="operator_availability" in required_reports,
            report=operator_availability,
            ok=_operator_availability_report_core_ok(operator_availability),
            evidence={
                "target_count": (operator_availability or {}).get("target_count"),
                "td_build": ((operator_availability or {}).get("availability_matrix") or {}).get(
                    "td_build"
                ),
                "platform": ((operator_availability or {}).get("availability_matrix") or {}).get(
                    "platform"
                ),
                "stored_availability_report": (operator_availability or {}).get(
                    "stored_availability_report"
                ),
            }
            if operator_availability
            else {},
        ),
        _readiness_category(
            category_id="plugin_surface",
            required="plugin_surface" in required_reports,
            report=plugin_surface,
            ok=bool(plugin_surface) and bool(plugin_surface.get("ok")),
            evidence={
                "tool_count": (plugin_surface or {}).get("tool_count"),
                "brain_skill_count": (plugin_surface or {}).get("brain_skill_count"),
                "mirror_mismatch_count": len((plugin_surface or {}).get("mirror_mismatches") or []),
            }
            if plugin_surface
            else {},
        ),
    ]
    missing_required = [
        category for category in categories if category["required"] and not category["present"]
    ]
    failed_categories = [
        category for category in categories if category["present"] and not category["ok"]
    ]
    return {
        "schema_version": 1,
        "ok": not missing_required
        and not failed_categories
        and failed_check_count == 0
        and missing_check_count == 0,
        "required_category_count": sum(1 for category in categories if category["required"]),
        "present_category_count": sum(1 for category in categories if category["present"]),
        "missing_required_category_count": len(missing_required),
        "failed_category_count": len(failed_categories),
        "failed_check_count": failed_check_count,
        "missing_check_count": missing_check_count,
        "categories": categories,
    }


def _readiness_category(
    *,
    category_id: str,
    required: bool,
    report: dict[str, Any] | None,
    ok: bool,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": category_id,
        "required": required,
        "present": report is not None,
        "ok": bool(ok) if report is not None else False,
        "evidence": evidence,
    }


def _bool_value(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return math.nan


def _strict_bool_value(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return 0.0


def _matches_value(value: Any, expected: str) -> float:
    return 1.0 if str(value) == expected else 0.0


def _present_value(value: Any) -> float:
    return 0.0 if value in (None, "", [], {}) else 1.0


def _td_health_ok_value(value: Any) -> float:
    if not isinstance(value, dict):
        return math.nan
    return 1.0 if value.get("status") == "ok" else 0.0


def _known_text_value(value: Any) -> float:
    text = str(value or "").strip().lower()
    return 1.0 if text and text not in {"unknown", "none", "--"} else 0.0


def _transactional_cleanup_ok_value(value: Any) -> float:
    if not isinstance(value, dict):
        return math.nan
    cleanup = value.get("cleanup")
    if not isinstance(cleanup, dict):
        return 0.0
    if cleanup.get("td_stable") is not True:
        return 0.0
    if cleanup.get("rollback_performed") is not True:
        return 0.0
    if cleanup.get("remaining_created_paths") not in ([], None):
        return 0.0
    return 1.0


def _operator_availability_checks(report: dict[str, Any]) -> list[dict[str, Any]]:
    matrix = report.get("availability_matrix") or {}
    results = report.get("results")
    target_count = float(report.get("target_count", math.nan))
    return [
        check_threshold(
            "operator availability sample report ok",
            _bool_value(report.get("ok")),
            ">=",
            1.0,
        ),
        check_threshold(
            "operator availability sample target count",
            target_count,
            ">=",
            3.0,
        ),
        check_threshold(
            "operator availability sample result count",
            _list_count(results),
            ">=",
            target_count,
        ),
        check_threshold(
            "operator availability sample td build known",
            _known_text_value(matrix.get("td_build") if isinstance(matrix, dict) else None),
            ">=",
            1.0,
        ),
        check_threshold(
            "operator availability sample platform known",
            _known_text_value(matrix.get("platform") if isinstance(matrix, dict) else None),
            ">=",
            1.0,
        ),
        check_threshold(
            "operator availability sample cleanup ok",
            _bool_value(report.get("cleanup_ok")),
            ">=",
            1.0,
        ),
        check_threshold(
            "operator availability stored artifact path",
            _stored_operator_availability_path_value(report),
            ">=",
            1.0,
        ),
        check_threshold(
            "operator availability glsl advanced pop replacement coverage",
            _glsl_advanced_pop_replacement_coverage(report),
            ">=",
            1.0,
        ),
    ]


def _stored_operator_availability_path_value(report: dict[str, Any]) -> float:
    path = str(report.get("stored_availability_report") or "").strip()
    if not path:
        return 0.0
    return 1.0 if Path(path).is_file() else 0.0


def _glsl_advanced_pop_replacement_coverage(report: dict[str, Any]) -> float:
    results = report.get("results")
    if not isinstance(results, list):
        return math.nan
    by_op = {
        str(item.get("op_type") or ""): item
        for item in results
        if isinstance(item, dict) and item.get("op_type")
    }
    deprecated = by_op.get("glslcreatePOP")
    advanced = by_op.get("glsladvancedPOP")
    topology = by_op.get("topologyPOP")
    if not isinstance(deprecated, dict) or not isinstance(advanced, dict) or not isinstance(topology, dict):
        return 0.0
    if deprecated.get("role") != "deprecated_gap":
        return 0.0
    if advanced.get("replacement_for") != "glslcreatePOP":
        return 0.0
    if topology.get("replacement_for") != "glslcreatePOP":
        return 0.0
    return 1.0 if advanced.get("available") is True and topology.get("available") is True else 0.0


def _operator_availability_report_core_ok(report: dict[str, Any] | None) -> bool:
    if not isinstance(report, dict):
        return False
    return all(check["status"] == "pass" for check in _operator_availability_checks(report))


def _required_item_coverage(values: Any, required: set[str]) -> float:
    if not isinstance(values, list):
        return math.nan
    normalized = {str(value) for value in values}
    return float(len(required & normalized))


def _expensive_probe_opt_in_metrics(scenarios: Any) -> dict[str, float]:
    if not isinstance(scenarios, list):
        return {
            "opt_in_scenario_count": math.nan,
            "uncontrolled_expensive_probe_count": math.nan,
        }

    opt_in_scenario_count = 0
    uncontrolled_expensive_probe_count = 0
    for scenario in scenarios:
        if not isinstance(scenario, dict) or scenario.get("status") != "planned":
            continue
        probes = scenario.get("profile_probes")
        if not isinstance(probes, list):
            continue
        expensive_probe_count = sum(
            1
            for probe in probes
            if isinstance(probe, dict) and probe.get("cost_level") == "expensive"
        )
        if expensive_probe_count == 0:
            continue
        if scenario.get("validation_profile") == "structural_visual_expensive":
            opt_in_scenario_count += 1
        else:
            uncontrolled_expensive_probe_count += expensive_probe_count

    return {
        "opt_in_scenario_count": float(opt_in_scenario_count),
        "uncontrolled_expensive_probe_count": float(uncontrolled_expensive_probe_count),
    }


def _list_count(values: Any) -> float:
    if not isinstance(values, list):
        return math.nan
    return float(len(values))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check release gates")
    parser.add_argument("--bench-report", default="")
    parser.add_argument("--soak-report", default="")
    parser.add_argument("--brain-eval-report", default="")
    parser.add_argument("--brain-smoke-report", default="")
    parser.add_argument("--brain-live-smoke-report", default="")
    parser.add_argument("--operator-availability-report", default="")
    parser.add_argument("--plugin-surface-report", default="")
    parser.add_argument(
        "--require-plugin-surface",
        action="store_true",
        help="Require a plugin surface audit report for complete release gates.",
    )
    parser.add_argument(
        "--require-live-smoke",
        action="store_true",
        help="Require a live TouchDesigner brain smoke report for complete release gates.",
    )
    parser.add_argument("--out", default="")
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Fail if any expected metric is missing",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    bench = load_json(args.bench_report) if args.bench_report else None
    soak = load_json(args.soak_report) if args.soak_report else None
    brain_eval = load_json(args.brain_eval_report) if args.brain_eval_report else None
    brain_smoke = load_json(args.brain_smoke_report) if args.brain_smoke_report else None
    brain_live_smoke = (
        load_json(args.brain_live_smoke_report) if args.brain_live_smoke_report else None
    )
    operator_availability = (
        load_json(args.operator_availability_report) if args.operator_availability_report else None
    )
    plugin_surface = load_json(args.plugin_surface_report) if args.plugin_surface_report else None
    required_reports = set()
    if args.require_plugin_surface:
        required_reports.add("plugin_surface")
    if args.require_live_smoke:
        required_reports.add("brain_live_smoke")
    if args.require_complete:
        required_reports.update(
            {
                "brain_eval",
                "brain_smoke",
                "brain_live_smoke",
                "operator_availability",
                "plugin_surface",
            }
        )

    report = evaluate(
        bench,
        soak,
        brain_eval=brain_eval,
        brain_smoke=brain_smoke,
        brain_live_smoke=brain_live_smoke,
        operator_availability=operator_availability,
        plugin_surface=plugin_surface,
        required_reports=required_reports,
    )
    output = json.dumps(report, indent=2)
    print(output)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n", encoding="utf-8")

    summary = report["summary"]
    if not summary["ok"]:
        return 1
    if args.require_complete and summary["missing"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
