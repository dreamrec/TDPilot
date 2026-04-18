from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "bench_tools.py"
_SPEC = importlib.util.spec_from_file_location("bench_tools", _SCRIPT_PATH)
assert _SPEC and _SPEC.loader
bench_tools = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bench_tools)


@pytest.mark.asyncio
async def test_run_benchmark_excludes_warmup_failures_from_error_rate():
    async def call(i: int):
        if i < 2:
            raise RuntimeError("warmup failure")

    result = await bench_tools.run_benchmark("warmup-only-failures", iterations=3, warmup=2, call=call)
    assert result["errors"] == 0
    assert result["warmup_errors"] == 2
    assert result["total_errors"] == 2
    assert result["success"] == 3
    assert result["error_rate_pct"] == 0.0


@pytest.mark.asyncio
async def test_run_benchmark_counts_measured_failures_only():
    async def call(i: int):
        if i == 3:
            raise RuntimeError("measured failure")

    result = await bench_tools.run_benchmark("measured-failures", iterations=4, warmup=2, call=call)
    assert result["errors"] == 1
    assert result["warmup_errors"] == 0
    assert result["total_errors"] == 1
    assert result["success"] == 3
    assert result["error_rate_pct"] == pytest.approx(25.0)
