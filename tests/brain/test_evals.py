from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from td_mcp.brain.evals import evaluate_golden_cases, load_golden_cases

ROOT = Path(__file__).resolve().parent.parent.parent
EVAL_PATH = ROOT / "tests" / "evals" / "td_brain_golden.jsonl"


def test_load_golden_cases_preserves_ids_and_expected_ops():
    cases = load_golden_cases(EVAL_PATH)

    assert {case["id"] for case in cases} >= {
        "feedback_loop_basic",
        "glsl_top_shader",
        "glsl_material_shader",
        "glsl_pop_attribute_shader",
    }
    assert all(case["expected_ops"] for case in cases)


@pytest.mark.asyncio
async def test_evaluate_golden_cases_scores_all_current_profiles():
    report = await evaluate_golden_cases(EVAL_PATH)

    assert report["ok"] is True
    assert report["case_count"] >= 8
    assert report["passed"] == report["case_count"]
    assert all(item["passed"] for item in report["cases"])
    assert all("concept_correctness" in item["checks"] for item in report["cases"])


def test_eval_brain_golden_cli_outputs_json_report():
    proc = subprocess.run(
        [sys.executable, "scripts/eval_brain_golden.py", "--cases", str(EVAL_PATH)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["case_count"] >= 6
