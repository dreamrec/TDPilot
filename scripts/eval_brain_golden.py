#!/usr/bin/env python3
"""Run deterministic TDPilot brain golden evals."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from td_mcp.brain.evals import (  # noqa: E402
    evaluate_golden_cases,
    load_golden_cases,
    trace_baseline_envelope_from_eval_results,
    trace_replay_baseline_report,
)


async def _run_eval_report(
    cases_path: Path,
    trace_baseline_path: Path | None,
    write_trace_baseline_path: Path | None,
) -> dict:
    report = await evaluate_golden_cases(cases_path)
    if write_trace_baseline_path is not None:
        baseline_envelope = trace_baseline_envelope_from_eval_results(report.get("cases", []))
        _write_trace_baseline(write_trace_baseline_path, baseline_envelope)
        report["trace_baseline"] = {
            "path": str(write_trace_baseline_path),
            "case_count": baseline_envelope["case_count"],
        }

    if trace_baseline_path is not None:
        baseline = _load_trace_baseline(trace_baseline_path)
    else:
        baseline = trace_baseline_envelope_from_eval_results(report.get("cases", [])).get("traces", {})
    report["trace_replay"] = await trace_replay_baseline_report(
        load_golden_cases(cases_path),
        baseline,
    )
    report["ok"] = bool(report["ok"] and report["trace_replay"]["ok"])
    return report


def _write_trace_baseline(path: Path, baseline: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_trace_baseline(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("trace baseline must be a JSON object keyed by eval case id")
    traces = payload.get("traces")
    if isinstance(traces, dict):
        return traces
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        type=Path,
        default=ROOT / "tests" / "evals" / "td_brain_golden.jsonl",
        help="Golden JSONL cases path.",
    )
    parser.add_argument(
        "--trace-baseline",
        type=Path,
        default=None,
        help="Optional JSON trace baseline keyed by eval case id.",
    )
    parser.add_argument(
        "--write-trace-baseline",
        type=Path,
        default=None,
        help="Write the current golden eval profile/operator trace baseline to this JSON path.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    report = asyncio.run(_run_eval_report(args.cases, args.trace_baseline, args.write_trace_baseline))
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    coverage = report.get("param_value_coverage", {}) or {}
    print(
        "param_value_coverage: "
        f"{coverage.get('carrying_case_count')}/{coverage.get('eligible_case_count')} "
        f"= {coverage.get('coverage')} (min {coverage.get('min_coverage')}; "
        f"expected-value cases {coverage.get('expected_param_value_case_count')}, "
        f"failures {coverage.get('expected_param_value_failure_count')})",
        file=sys.stderr,
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
