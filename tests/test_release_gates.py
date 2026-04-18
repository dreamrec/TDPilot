from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_release_gates.py"
_SPEC = importlib.util.spec_from_file_location("check_release_gates", _SCRIPT_PATH)
assert _SPEC and _SPEC.loader
check_release_gates = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_release_gates)


def test_evaluate_fails_when_no_reports_are_provided():
    report = check_release_gates.evaluate(None, None)
    assert report["summary"]["ok"] is False
    assert report["summary"]["failed"] >= 1


def test_evaluate_passes_with_valid_benchmark_payload():
    bench = {
        "benchmarks": {
            "td_get_nodes": {"latency_ms": {"p95": 250.0}, "error_rate_pct": 0.0},
            "td_get_params": {"latency_ms": {"p95": 200.0}, "error_rate_pct": 0.2},
            "td_set_params": {"latency_ms": {"p95": 150.0}, "error_rate_pct": 0.0},
            "td_capture_and_analyze_capture_only": {"latency_ms": {"p95": 650.0}, "error_rate_pct": 0.5},
        }
    }
    report = check_release_gates.evaluate(bench, None)
    assert report["summary"]["ok"] is True
    assert report["summary"]["failed"] == 0
    assert report["summary"]["total"] == 8


def test_evaluate_fails_when_benchmark_error_rate_is_high():
    bench = {
        "benchmarks": {
            "td_get_nodes": {"latency_ms": {"p95": 120.0}, "error_rate_pct": 0.0},
            "td_get_params": {"latency_ms": {"p95": 120.0}, "error_rate_pct": 0.0},
            "td_set_params": {"latency_ms": {"p95": 120.0}, "error_rate_pct": 0.0},
            "td_capture_and_analyze_capture_only": {"latency_ms": {"p95": 120.0}, "error_rate_pct": 100.0},
        }
    }
    report = check_release_gates.evaluate(bench, None)
    assert report["summary"]["ok"] is False
    assert report["summary"]["failed"] >= 1
