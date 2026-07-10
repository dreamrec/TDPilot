from __future__ import annotations

from pathlib import Path

from td_mcp.brain.practical_benchmarks import (
    BenchmarkMetrics,
    BenchmarkRun,
    compare_benchmark_runs,
    load_benchmark_scenarios,
)

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / "data" / "benchmarks" / "practical_intelligence_scenarios.json"


def _metric(scenario_id: str, *, current: bool, category: str) -> BenchmarkMetrics:
    return BenchmarkMetrics(
        scenario_id=scenario_id,
        passed=True,
        mode="fixture",
        model_round_trips=6 if current else 10,
        tool_calls=12 if current else 20,
        tool_subcalls=18 if current else 28,
        repeated_read_calls=2 if current else 5,
        patch_operations=20,
        screenshots=1,
        doc_queries=1,
        repair_loops=1 if category == "repair" else 0,
        generated_nodes=8,
        max_comp_depth=2,
        error_count=0,
        warning_count=0,
        output_valid=True,
        visual_score=0.9,
        runtime_score=0.9,
        rollback_safe=True,
        first_pass=category != "repair",
        repair_succeeded=True if category == "repair" else None,
        elapsed_seconds=1.0,
    )


def test_corpus_has_locked_six_three_three_shape() -> None:
    scenarios = load_benchmark_scenarios(SCENARIOS)
    counts = {
        category: sum(item.category == category for item in scenarios)
        for category in ("build", "modify", "repair")
    }

    assert len(scenarios) == 12
    assert counts == {"build": 6, "modify": 3, "repair": 3}
    assert sum(item.medium_build for item in scenarios) == 9
    assert all(item.injected_failure for item in scenarios if item.category == "repair")


def test_missing_baseline_blocks_efficiency_claims() -> None:
    scenarios = load_benchmark_scenarios(SCENARIOS)
    current = BenchmarkRun(
        version="2.4.0",
        tool_count=114,
        mode="fixture",
        observations=[_metric(item.id, current=True, category=item.category) for item in scenarios],
    )

    result = compare_benchmark_runs(None, current, scenarios)

    assert result.comparable is False
    assert result.passed is False
    assert result.gates[0].id == "baseline_present"
    assert "blocked" in result.gates[0].detail


def test_comparison_calculates_all_locked_release_targets() -> None:
    scenarios = load_benchmark_scenarios(SCENARIOS)
    baseline = BenchmarkRun(
        version="2.1.1",
        tool_count=114,
        mode="fixture",
        baseline_label="frozen-v2.1.1",
        observations=[_metric(item.id, current=False, category=item.category) for item in scenarios],
    )
    current = BenchmarkRun(
        version="2.4.0",
        tool_count=114,
        mode="fixture",
        observations=[_metric(item.id, current=True, category=item.category) for item in scenarios],
    )

    result = compare_benchmark_runs(baseline, current, scenarios)
    by_id = {gate.id: gate for gate in result.gates}

    assert result.comparable is True
    assert result.passed is True
    assert by_id["tool_call_reduction"].actual == 0.4
    assert by_id["repeated_read_reduction"].actual == 0.6
    assert by_id["model_round_trip_reduction"].actual == 0.4
    assert by_id["orchestration_round_trip_soft_budgets"].passed is True
    assert by_id["validated_first_pass_success"].passed is True
    assert by_id["known_repair_success"].passed is True


def test_round_trip_soft_budget_requires_trace_reason_for_overrun() -> None:
    scenarios = load_benchmark_scenarios(SCENARIOS)
    baseline = BenchmarkRun(
        version="2.1.1",
        tool_count=114,
        mode="fixture",
        observations=[_metric(item.id, current=False, category=item.category) for item in scenarios],
    )
    observations = [_metric(item.id, current=True, category=item.category) for item in scenarios]
    observations[0] = observations[0].model_copy(
        update={"orchestration_mode": "fast", "model_round_trips": 13}
    )
    current = BenchmarkRun(
        version="2.4.0",
        tool_count=114,
        mode="fixture",
        observations=observations,
    )

    failed = compare_benchmark_runs(baseline, current, scenarios)
    gate = next(item for item in failed.gates if item.id == "orchestration_round_trip_soft_budgets")
    assert gate.passed is False
    assert "13>12" in gate.detail

    current.observations[0].trace_reason = "live device discovery required one retry"
    explained = compare_benchmark_runs(baseline, current, scenarios)
    explained_gate = next(
        item for item in explained.gates if item.id == "orchestration_round_trip_soft_budgets"
    )
    assert explained_gate.passed is True
