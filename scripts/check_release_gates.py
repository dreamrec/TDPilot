#!/usr/bin/env python3
"""Evaluate release-gate metrics from benchmark/soak reports."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


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


def evaluate(bench: dict[str, Any] | None, soak: dict[str, Any] | None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    if bench is None and soak is None:
        checks.append(
            {
                "label": "input reports provided",
                "status": "fail",
                "value": "none",
                "target": "bench and/or soak report required",
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

    passed = [c for c in checks if c["status"] == "pass"]
    failed = [c for c in checks if c["status"] == "fail"]
    missing = [c for c in checks if c["status"] == "missing"]

    return {
        "schema_version": 1,
        "summary": {
            "total": len(checks),
            "passed": len(passed),
            "failed": len(failed),
            "missing": len(missing),
            "ok": len(failed) == 0,
        },
        "checks": checks,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check release gates")
    parser.add_argument("--bench-report", default="")
    parser.add_argument("--soak-report", default="")
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

    report = evaluate(bench, soak)
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
