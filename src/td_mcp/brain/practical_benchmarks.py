"""Practical-intelligence benchmark contracts and release comparisons.

The benchmark harness intentionally separates measurement from claims.  It can
load fixture or live observations, but it will not synthesize a historical
baseline when one has not been recorded on the frozen implementation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ScenarioCategory = Literal["build", "modify", "repair"]
BenchmarkMode = Literal["fixture", "live"]
OrchestrationMode = Literal["fast", "production", "show_safe"]
ROUND_TRIP_SOFT_BUDGETS: dict[OrchestrationMode, int] = {
    "fast": 12,
    "production": 20,
    "show_safe": 26,
}


class BenchmarkScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    category: ScenarioCategory
    intent: str = Field(min_length=1)
    required_outcomes: list[str] = Field(min_length=1)
    expected_techniques: list[str] = Field(default_factory=list)
    injected_failure: str | None = None
    medium_build: bool = False
    validated_template: bool = False


class BenchmarkMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    passed: bool
    mode: BenchmarkMode
    orchestration_mode: OrchestrationMode = "production"
    model_round_trips: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    tool_subcalls: int = Field(ge=0)
    repeated_read_calls: int = Field(ge=0)
    patch_operations: int = Field(ge=0)
    screenshots: int = Field(ge=0)
    doc_queries: int = Field(ge=0)
    repair_loops: int = Field(ge=0)
    planning_tokens: int | None = Field(default=None, ge=0)
    execution_tokens: int | None = Field(default=None, ge=0)
    generated_nodes: int = Field(ge=0)
    max_comp_depth: int = Field(ge=0)
    error_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    output_valid: bool
    visual_score: float | None = Field(default=None, ge=0.0, le=1.0)
    runtime_score: float | None = Field(default=None, ge=0.0, le=1.0)
    rollback_safe: bool
    first_pass: bool
    repair_succeeded: bool | None = None
    elapsed_seconds: float = Field(ge=0.0)
    trace_reason: str | None = None

    @model_validator(mode="after")
    def _repair_shape(self) -> BenchmarkMetrics:
        if self.repair_loops == 0 and self.repair_succeeded is True:
            raise ValueError("repair_succeeded=true requires at least one repair loop")
        return self


class BenchmarkRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    version: str
    tool_count: int
    mode: BenchmarkMode
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    baseline_label: str | None = None
    observations: list[BenchmarkMetrics]


class GateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    passed: bool
    measured: bool
    actual: float | None = None
    required: float | None = None
    detail: str


class BenchmarkComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    comparable: bool
    gates: list[GateResult]

    @property
    def passed(self) -> bool:
        return self.comparable and all(gate.passed for gate in self.gates)


def load_benchmark_scenarios(path: str | Path) -> list[BenchmarkScenario]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("benchmark scenario corpus must be a JSON list")
    scenarios = [BenchmarkScenario.model_validate(item) for item in payload]
    ids = [scenario.id for scenario in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("benchmark scenario ids must be unique")
    return scenarios


def compare_benchmark_runs(
    baseline: BenchmarkRun | None,
    current: BenchmarkRun,
    scenarios: list[BenchmarkScenario],
) -> BenchmarkComparison:
    """Evaluate frozen release targets without inventing missing evidence."""
    if baseline is None:
        return BenchmarkComparison(
            comparable=False,
            gates=[
                GateResult(
                    id="baseline_present",
                    passed=False,
                    measured=False,
                    detail="No frozen baseline run was supplied; efficiency claims are blocked.",
                )
            ],
        )
    scenario_ids = {scenario.id for scenario in scenarios}
    baseline_by_id = {item.scenario_id: item for item in baseline.observations}
    current_by_id = {item.scenario_id: item for item in current.observations}
    missing = sorted(scenario_ids - baseline_by_id.keys() | scenario_ids - current_by_id.keys())
    if missing:
        return BenchmarkComparison(
            comparable=False,
            gates=[
                GateResult(
                    id="scenario_closure",
                    passed=False,
                    measured=False,
                    detail="Missing observations: " + ", ".join(missing),
                )
            ],
        )

    medium_ids = {scenario.id for scenario in scenarios if scenario.medium_build}
    validated_ids = {scenario.id for scenario in scenarios if scenario.validated_template}
    repair_ids = {scenario.id for scenario in scenarios if scenario.category == "repair"}

    def avg(source: dict[str, BenchmarkMetrics], ids: set[str], field: str) -> float:
        return mean(float(getattr(source[scenario_id], field)) for scenario_id in sorted(ids))

    gates: list[GateResult] = []
    for gate_id, field, required in (
        ("tool_call_reduction", "tool_calls", 0.30),
        ("repeated_read_reduction", "repeated_read_calls", 0.40),
        ("model_round_trip_reduction", "model_round_trips", 0.25),
    ):
        old = avg(baseline_by_id, medium_ids, field)
        new = avg(current_by_id, medium_ids, field)
        reduction = 0.0 if old <= 0 else (old - new) / old
        gates.append(
            GateResult(
                id=gate_id,
                passed=reduction >= required,
                measured=True,
                actual=round(reduction, 6),
                required=required,
                detail=f"{field}: baseline={old:.3f}, current={new:.3f}",
            )
        )

    baseline_success = mean(float(item.passed) for item in baseline.observations)
    current_success = mean(float(item.passed) for item in current.observations)
    gates.append(
        GateResult(
            id="success_rate_no_regression",
            passed=current_success >= baseline_success,
            measured=True,
            actual=current_success,
            required=baseline_success,
            detail=f"baseline={baseline_success:.3f}, current={current_success:.3f}",
        )
    )
    unexplained_round_trip_overruns = [
        item
        for item in current.observations
        if item.model_round_trips > ROUND_TRIP_SOFT_BUDGETS[item.orchestration_mode]
        and not str(item.trace_reason or "").strip()
    ]
    gates.append(
        GateResult(
            id="orchestration_round_trip_soft_budgets",
            passed=not unexplained_round_trip_overruns,
            measured=True,
            actual=float(len(unexplained_round_trip_overruns)),
            required=0.0,
            detail=(
                "all observations stayed within fast/production/show-safe soft budgets "
                "or recorded a trace reason"
                if not unexplained_round_trip_overruns
                else "unexplained overruns: "
                + ", ".join(
                    f"{item.scenario_id}={item.model_round_trips}>"
                    f"{ROUND_TRIP_SOFT_BUDGETS[item.orchestration_mode]}"
                    for item in unexplained_round_trip_overruns
                )
            ),
        )
    )
    baseline_rollback = mean(float(item.rollback_safe) for item in baseline.observations)
    current_rollback = mean(float(item.rollback_safe) for item in current.observations)
    gates.append(
        GateResult(
            id="rollback_safety_no_regression",
            passed=current_rollback >= baseline_rollback,
            measured=True,
            actual=current_rollback,
            required=baseline_rollback,
            detail=f"baseline={baseline_rollback:.3f}, current={current_rollback:.3f}",
        )
    )
    first_pass_rate = mean(float(current_by_id[item].first_pass) for item in sorted(validated_ids))
    gates.append(
        GateResult(
            id="validated_first_pass_success",
            passed=first_pass_rate >= 0.80,
            measured=True,
            actual=first_pass_rate,
            required=0.80,
            detail=f"{sum(current_by_id[item].first_pass for item in validated_ids)}/{len(validated_ids)}",
        )
    )
    repair_rate = mean(float(current_by_id[item].repair_succeeded is True) for item in sorted(repair_ids))
    gates.append(
        GateResult(
            id="known_repair_success",
            passed=repair_rate >= 0.80,
            measured=True,
            actual=repair_rate,
            required=0.80,
            detail=f"{sum(current_by_id[item].repair_succeeded is True for item in repair_ids)}/{len(repair_ids)}",
        )
    )
    return BenchmarkComparison(comparable=True, gates=gates)


def read_benchmark_run(path: str | Path) -> BenchmarkRun:
    return BenchmarkRun.model_validate_json(Path(path).read_text(encoding="utf-8"))


def write_benchmark_run(path: str | Path, run: BenchmarkRun) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")


__all__ = [
    "BenchmarkComparison",
    "BenchmarkMetrics",
    "BenchmarkRun",
    "BenchmarkScenario",
    "GateResult",
    "OrchestrationMode",
    "ROUND_TRIP_SOFT_BUDGETS",
    "compare_benchmark_runs",
    "load_benchmark_scenarios",
    "read_benchmark_run",
    "write_benchmark_run",
]
