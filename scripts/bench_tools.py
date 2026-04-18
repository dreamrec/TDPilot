#!/usr/bin/env python3
"""Benchmark core TD MCP HTTP endpoints used by TDPilot tools.

This script targets the local TouchDesigner WebServer API (default :9981)
through TDClient, and reports latency distributions for key operations.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from td_mcp.td_client import TDClient


def percentile(values: list[float], p: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    if p <= 0:
        return ordered[0]
    if p >= 100:
        return ordered[-1]
    rank = (len(ordered) - 1) * (p / 100.0)
    lower = int(math.floor(rank))
    upper = int(math.ceil(rank))
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


async def run_benchmark(
    name: str,
    iterations: int,
    warmup: int,
    call: Callable[[int], Awaitable[Any]],
) -> dict[str, Any]:
    timings: list[float] = []
    measured_errors = 0
    total_errors = 0

    total = warmup + iterations
    for i in range(total):
        started = time.perf_counter()
        failed = False
        try:
            await call(i)
        except Exception:
            failed = True
            total_errors += 1
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if i >= warmup:
            timings.append(elapsed_ms)
            if failed:
                measured_errors += 1

    success = max(0, len(timings) - measured_errors)
    return {
        "name": name,
        "iterations": iterations,
        "warmup": warmup,
        "errors": measured_errors,
        "warmup_errors": max(0, total_errors - measured_errors),
        "total_errors": total_errors,
        "success": success,
        "error_rate_pct": (measured_errors / len(timings) * 100.0) if timings else 0.0,
        "latency_ms": {
            "min": min(timings) if timings else math.nan,
            "max": max(timings) if timings else math.nan,
            "mean": statistics.fmean(timings) if timings else math.nan,
            "p50": percentile(timings, 50),
            "p95": percentile(timings, 95),
            "p99": percentile(timings, 99),
        },
    }


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    client = TDClient(host=args.host, port=args.port, timeout=args.timeout, max_retries=args.max_retries)
    await client.health_check()

    async def bench_get_nodes(_: int):
        await client.request(
            "nodes",
            {
                "path": args.nodes_path,
                "limit": args.nodes_limit,
                "offset": 0,
                "include_params": False,
            },
        )

    async def bench_get_params(_: int):
        await client.request("node/params", {"path": args.params_path})

    async def bench_set_params(i: int):
        value = args.set_a if i % 2 == 0 else args.set_b
        await client.request(
            "node/params/set",
            {
                "path": args.set_path,
                "params": {
                    args.set_param: {"val": value},
                },
            },
        )

    async def bench_screenshot(_: int):
        await client.request(
            "screenshot",
            {
                "path": args.capture_path,
                "quality": args.capture_quality,
            },
        )

    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": {
            "host": args.host,
            "port": args.port,
        },
        "benchmarks": {
            "td_get_nodes": await run_benchmark("td_get_nodes", args.calls, args.warmup, bench_get_nodes),
            "td_get_params": await run_benchmark("td_get_params", args.calls, args.warmup, bench_get_params),
            "td_set_params": await run_benchmark("td_set_params", args.calls, args.warmup, bench_set_params),
            "td_capture_and_analyze_capture_only": await run_benchmark(
                "td_capture_and_analyze_capture_only",
                args.capture_calls,
                args.capture_warmup,
                bench_screenshot,
            ),
        },
    }

    await client.close()
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark core TD MCP operations.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9981)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-retries", type=int, default=1)

    parser.add_argument("--calls", type=int, default=1000, help="Iterations for core benchmarks")
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--capture-calls", type=int, default=500)
    parser.add_argument("--capture-warmup", type=int, default=10)

    parser.add_argument("--nodes-path", default="/project1")
    parser.add_argument("--nodes-limit", type=int, default=100)
    parser.add_argument("--params-path", default="/project1")
    parser.add_argument("--set-path", default="/project1")
    parser.add_argument("--set-param", default="cook")
    parser.add_argument("--set-a", type=float, default=1.0)
    parser.add_argument("--set-b", type=float, default=0.0)
    parser.add_argument("--capture-path", default="/project1")
    parser.add_argument("--capture-quality", type=float, default=0.3)

    parser.add_argument("--out", default="", help="Optional JSON output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = asyncio.run(main_async(args))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1

    output = json.dumps(report, indent=2)
    print(output)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
