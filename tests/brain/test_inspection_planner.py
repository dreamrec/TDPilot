from __future__ import annotations

import pytest

from td_mcp.brain.inspection_planner import (
    InspectionPlan,
    InspectionPlanner,
    InspectionProbe,
)


@pytest.mark.parametrize(
    ("mode", "budget"),
    [("fast", 4), ("production", 7), ("show_safe", 10)],
)
def test_inspection_planner_enforces_mode_budget(mode: str, budget: int) -> None:
    plan = InspectionPlanner().plan(
        mode=mode,
        target_root="/project1/build",
        output_path="/project1/out1",
        selected_paths=[f"/project1/build/node{index}" for index in range(8)],
        relevant_param_paths=[f"/project1/build/par{index}" for index in range(8)],
        modification=True,
        include_runtime_info=True,
    )

    assert plan.maximum_probes == budget
    assert len(plan.probes) == budget
    assert len(plan.probes) + len(plan.omitted_probe_ids) > budget
    assert {probe.id for probe in plan.probes}.issuperset({"state", "children", "errors"})


def test_inspection_plan_is_byte_stable_and_deduplicates_reads() -> None:
    planner = InspectionPlanner()
    kwargs = {
        "mode": "production",
        "target_root": "/project1",
        "selected_paths": ["/project1/a", "/project1/a", "/project1/b"],
        "relevant_param_paths": ["/project1/b", "/project1/b"],
    }

    first = planner.plan(**kwargs)
    second = planner.plan(**kwargs)

    assert first.model_dump_json() == second.model_dump_json()
    keys = [(probe.tool, tuple(sorted(probe.arguments.items()))) for probe in first.probes]
    assert len(keys) == len(set(keys))


@pytest.mark.asyncio
async def test_executor_cache_is_plan_local_and_normalizes_results() -> None:
    duplicate = InspectionProbe(
        id="duplicate",
        tool="td_get_nodes",
        arguments={"path": "/project1"},
        purpose="duplicate read",
    )
    plan = InspectionPlan(
        plan_id="inspect-test",
        mode="fast",
        target_root="/project1",
        maximum_probes=4,
        probes=[duplicate.model_copy(update={"id": "first"}), duplicate],
    )
    calls: list[tuple[str, dict]] = []

    async def caller(tool: str, arguments: dict) -> dict:
        calls.append((tool, arguments))
        return {"z": 1, "a": {"b": 2}}

    planner = InspectionPlanner()
    first_result = await planner.execute(plan, caller)
    second_result = await planner.execute(plan, caller)

    assert first_result.calls_made == 1
    assert first_result.cache_hits == ["duplicate"]
    assert first_result.values["first"] == {"a": {"b": 2}, "z": 1}
    assert second_result.calls_made == 1
    assert len(calls) == 2  # a fresh cache is created for the second plan execution
