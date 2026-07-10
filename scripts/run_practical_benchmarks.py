#!/usr/bin/env python3
"""Validate practical benchmark observations and compare a frozen baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from td_mcp.brain.practical_benchmarks import (  # noqa: E402
    compare_benchmark_runs,
    load_benchmark_scenarios,
    read_benchmark_run,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenarios",
        type=Path,
        default=ROOT / "data" / "benchmarks" / "practical_intelligence_scenarios.json",
    )
    parser.add_argument("--current", type=Path, help="Measured current BenchmarkRun JSON")
    parser.add_argument("--baseline", type=Path, help="Frozen v2.1.1 or v2.2 BenchmarkRun JSON")
    parser.add_argument("--list", action="store_true", help="Print the scenario corpus and exit")
    args = parser.parse_args()

    scenarios = load_benchmark_scenarios(args.scenarios)
    if args.list:
        print(json.dumps([item.model_dump(mode="json") for item in scenarios], indent=2))
        return 0
    if args.current is None:
        parser.error("--current is required unless --list is used")
    current = read_benchmark_run(args.current)
    baseline = read_benchmark_run(args.baseline) if args.baseline else None
    comparison = compare_benchmark_runs(baseline, current, scenarios)
    print(comparison.model_dump_json(indent=2))
    return 0 if comparison.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
