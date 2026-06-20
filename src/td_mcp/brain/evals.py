"""Golden eval scoring for the TDPilot brain planner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from td_mcp.brain.planner import build_brain_plan


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
    cases = load_golden_cases(path)
    results = [await evaluate_case(case) for case in cases]
    passed = sum(1 for item in results if item["passed"])
    return {
        "schema_version": 1,
        "ok": passed == len(results),
        "case_count": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "cases": results,
    }


async def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    expected_ops = list(case.get("expected_ops") or [])
    client = StaticEvalTDClient(
        families=families_for_ops(expected_ops), nodes=case.get("existing_nodes") or []
    )
    plan = await build_brain_plan(
        client,
        intent=str(case["intent"]),
        target_root=str(case.get("target_root") or "/project1"),
        validation_profile=str(case.get("validation_profile") or "auto"),
    )
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
            "ok": set(expected_ops).issubset(set(plan.concept_graph.operators))
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
    expected_domains = case.get("expected_compiled_domains") or []
    if expected_domains:
        checks["compiled_domains"] = {
            "ok": plan.compiled_task is not None
            and set(expected_domains).issubset(set(plan.compiled_task.domains)),
            "weight": _weight(case, "compiled_domains"),
        }
    expected_patterns = case.get("expected_patterns") or []
    if expected_patterns:
        actual_patterns = {
            pattern_id for candidate in plan.candidate_graphs for pattern_id in candidate.pattern_ids
        }
        checks["pattern_composition"] = {
            "ok": set(expected_patterns).issubset(actual_patterns),
            "weight": _weight(case, "pattern_composition"),
        }
    max_score = sum(item["weight"] for item in checks.values())
    score = sum(item["weight"] for item in checks.values() if item["ok"])
    return {
        "id": case.get("id"),
        "passed": score == max_score,
        "score": score,
        "max_score": max_score,
        "checks": checks,
        "profile": plan.concept_graph.profile,
        "operators": plan.concept_graph.operators,
        "compiled_domains": plan.compiled_task.domains if plan.compiled_task else [],
        "candidate_patterns": [
            pattern_id for candidate in plan.candidate_graphs for pattern_id in candidate.pattern_ids
        ],
        "blocked_questions": plan.blocked_questions,
        "missing_facts": plan.missing_facts,
    }


def _weight(case: dict[str, Any], name: str) -> int:
    scoring = case.get("scoring") if isinstance(case.get("scoring"), dict) else {}
    return int(scoring.get(name, 1))


__all__ = [
    "StaticEvalTDClient",
    "evaluate_case",
    "evaluate_golden_cases",
    "families_for_ops",
    "family_for_op",
    "load_golden_cases",
]
