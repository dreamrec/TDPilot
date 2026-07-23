from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_release_gates.py"
_SPEC = importlib.util.spec_from_file_location("check_release_gates", _SCRIPT_PATH)
assert _SPEC and _SPEC.loader
check_release_gates = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_release_gates)


def _candidate_report_identity() -> dict:
    return {
        "version": check_release_gates._canonical_version(),
        "tool_count": 114,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def test_evaluate_fails_when_no_reports_are_provided():
    report = check_release_gates.evaluate(None, None)
    assert report["summary"]["ok"] is False
    assert report["summary"]["failed"] >= 1


def test_evaluate_marks_plugin_surface_missing_when_required():
    bench = {
        "benchmarks": {
            "td_get_nodes": {"latency_ms": {"p95": 250.0}, "error_rate_pct": 0.0},
            "td_get_params": {"latency_ms": {"p95": 200.0}, "error_rate_pct": 0.2},
            "td_set_params": {"latency_ms": {"p95": 150.0}, "error_rate_pct": 0.0},
            "td_capture_and_analyze_capture_only": {"latency_ms": {"p95": 650.0}, "error_rate_pct": 0.5},
        }
    }

    report = check_release_gates.evaluate(
        bench,
        None,
        required_reports={"plugin_surface"},
    )

    labels = {check["label"]: check for check in report["checks"]}
    assert labels["plugin surface report provided"]["status"] == "missing"
    assert report["summary"]["missing"] == 1


def test_evaluate_marks_live_smoke_missing_when_required():
    report = check_release_gates.evaluate(
        None,
        None,
        required_reports={"brain_live_smoke"},
    )

    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain live smoke report provided"]["status"] == "missing"
    assert report["summary"]["missing"] == 1


def test_evaluate_marks_operator_availability_missing_when_required():
    report = check_release_gates.evaluate(
        None,
        None,
        required_reports={"operator_availability"},
    )

    labels = {check["label"]: check for check in report["checks"]}
    assert labels["operator availability report provided"]["status"] == "missing"
    assert report["summary"]["missing"] == 1


def test_evaluate_gates_direct_param_preflight_report():
    report = check_release_gates.evaluate(
        None,
        None,
        direct_param_preflight={
            "ok": True,
            "write_count": 11,
            "guarded_count": 11,
            "unguarded_count": 0,
            "unguarded_writes": [],
            "wrapper_call_count": 10,
            "wrapper_guarded_count": 10,
            "wrapper_unguarded_count": 0,
            "wrapper_unguarded_calls": [],
        },
    )

    labels = {check["label"]: check for check in report["checks"]}
    assert labels["direct param preflight report ok"]["status"] == "pass"
    assert labels["direct param preflight unguarded write count"]["status"] == "pass"
    assert labels["direct param preflight guarded coverage"]["status"] == "pass"
    assert labels["direct param preflight unguarded wrapper count"]["status"] == "pass"
    assert labels["direct param preflight wrapper coverage"]["status"] == "pass"

    failed = check_release_gates.evaluate(
        None,
        None,
        direct_param_preflight={
            "ok": False,
            "write_count": 11,
            "guarded_count": 10,
            "unguarded_count": 1,
            "unguarded_writes": [{"path": "src/td_mcp/registry/unsafe.py"}],
            "wrapper_call_count": 10,
            "wrapper_guarded_count": 9,
            "wrapper_unguarded_count": 1,
            "wrapper_unguarded_calls": [{"path": "src/td_mcp/registry/unsafe_wrapper.py"}],
        },
    )
    failed_labels = {check["label"]: check for check in failed["checks"]}
    assert failed_labels["direct param preflight report ok"]["status"] == "fail"
    assert failed_labels["direct param preflight unguarded write count"]["status"] == "fail"
    assert failed_labels["direct param preflight guarded coverage"]["status"] == "fail"
    assert failed_labels["direct param preflight unguarded wrapper count"]["status"] == "fail"
    assert failed_labels["direct param preflight wrapper coverage"]["status"] == "fail"
    assert failed["summary"]["ok"] is False


def test_evaluate_marks_param_semantics_risk_missing_when_required():
    report = check_release_gates.evaluate(
        None,
        None,
        required_reports={"param_semantics_risk"},
    )

    labels = {check["label"]: check for check in report["checks"]}
    assert labels["param semantics risk report provided"]["status"] == "missing"
    assert report["summary"]["missing"] == 1


def test_evaluate_gates_param_semantics_risk_report():
    report = check_release_gates.evaluate(
        None,
        None,
        param_semantics_risk=_complete_param_semantics_risk_payload(),
    )

    labels = {check["label"]: check for check in report["checks"]}
    assert labels["param semantics high cook risk report ok"]["status"] == "pass"
    assert labels["param semantics high cook risk unclassified count"]["status"] == "pass"
    assert labels["param semantics high cook risk classified coverage"]["status"] == "pass"
    assert labels["param semantics direct risk parameter count"]["status"] == "pass"

    failed_payload = _complete_param_semantics_risk_payload()
    failed_payload["ok"] = False
    failed_payload["unclassified_count"] = 1
    failed_payload["unclassified_high_cook_risk_parameters"] = [
        {"op_type": "executeDAT", "name": "active", "behavior": "unclassified"}
    ]
    failed_payload["validation_only_count"] = 5
    failed = check_release_gates.evaluate(
        None,
        None,
        param_semantics_risk=failed_payload,
    )

    failed_labels = {check["label"]: check for check in failed["checks"]}
    assert failed_labels["param semantics high cook risk report ok"]["status"] == "fail"
    assert failed_labels["param semantics high cook risk unclassified count"]["status"] == "fail"
    assert failed_labels["param semantics high cook risk classified coverage"]["status"] == "fail"
    assert failed["summary"]["ok"] is False


def test_cli_require_plugin_surface_fails_complete_gate_when_report_absent(tmp_path: Path):
    bench_path = tmp_path / "bench.json"
    bench_path.write_text(
        json.dumps(
            {
                "benchmarks": {
                    "td_get_nodes": {"latency_ms": {"p95": 250.0}, "error_rate_pct": 0.0},
                    "td_get_params": {"latency_ms": {"p95": 200.0}, "error_rate_pct": 0.2},
                    "td_set_params": {"latency_ms": {"p95": 150.0}, "error_rate_pct": 0.0},
                    "td_capture_and_analyze_capture_only": {
                        "latency_ms": {"p95": 650.0},
                        "error_rate_pct": 0.5,
                    },
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/check_release_gates.py",
            "--bench-report",
            str(bench_path),
            "--require-plugin-surface",
            "--require-complete",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    labels = {check["label"]: check for check in payload["checks"]}
    assert labels["plugin surface report provided"]["status"] == "missing"


def test_cli_require_live_smoke_fails_complete_gate_when_report_absent(tmp_path: Path):
    brain_eval_path = tmp_path / "brain_eval.json"
    brain_eval_path.write_text(json.dumps(_complete_brain_eval_payload()) + "\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/check_release_gates.py",
            "--brain-eval-report",
            str(brain_eval_path),
            "--require-live-smoke",
            "--require-complete",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    labels = {check["label"]: check for check in payload["checks"]}
    assert labels["brain live smoke report provided"]["status"] == "missing"


def test_cli_require_complete_requires_brain_eval_and_dry_run_smoke_reports(tmp_path: Path):
    brain_live_smoke_path = tmp_path / "brain_live_smoke.json"
    brain_live_smoke_path.write_text(
        json.dumps(_complete_brain_live_smoke_payload()) + "\n",
        encoding="utf-8",
    )
    plugin_surface_path = tmp_path / "plugin_surface.json"
    plugin_surface_path.write_text(
        json.dumps(_complete_plugin_surface_payload()) + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/check_release_gates.py",
            "--brain-live-smoke-report",
            str(brain_live_smoke_path),
            "--plugin-surface-report",
            str(plugin_surface_path),
            "--require-complete",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    labels = {check["label"]: check for check in payload["checks"]}
    readiness = payload["release_readiness"]
    assert labels["brain eval report provided"]["status"] == "missing"
    assert labels["brain smoke report provided"]["status"] == "missing"
    assert labels["operator availability report provided"]["status"] == "missing"
    assert labels["param semantics risk report provided"]["status"] == "missing"
    assert readiness["required_category_count"] == 6
    assert readiness["missing_required_category_count"] == 4


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


def test_evaluate_exposes_top_level_ok_for_release_payload():
    bench = {
        "benchmarks": {
            "td_get_nodes": {"latency_ms": {"p95": 250.0}, "error_rate_pct": 0.0},
            "td_get_params": {"latency_ms": {"p95": 200.0}, "error_rate_pct": 0.2},
            "td_set_params": {"latency_ms": {"p95": 150.0}, "error_rate_pct": 0.0},
            "td_capture_and_analyze_capture_only": {"latency_ms": {"p95": 650.0}, "error_rate_pct": 0.5},
        }
    }

    report = check_release_gates.evaluate(bench, None)

    assert report["ok"] is True
    assert report["ok"] is report["summary"]["ok"]


def _complete_param_semantics_priority_groups() -> dict:
    return {
        group: {
            "operator_count": 1,
            "covered_operator_count": 1,
            "missing_operators": [],
        }
        for group in {
            "audio_control",
            "dat_callbacks_protocols",
            "feedback_top_processing",
            "glsl",
            "panel_parameters",
            "pop",
            "render_material",
        }
    }


def _complete_showpiece_assembly_metrics() -> dict:
    return {
        "ok": True,
        "showpiece_case_count": 10,
        "assembled_showpiece_case_count": 10,
        "fully_readable_showpiece_case_count": 10,
        "unassembled_showpiece_case_ids": [],
        "not_fully_readable_showpiece_case_ids": [],
        "showpiece_case_ids": ["audio_feedback_panel_debug"],
    }


def _complete_validation_metrics() -> dict:
    return {
        "ok": True,
        "case_count": 50,
        "min_validation_check_count": 6,
        "avg_validation_check_count": 10.0,
        "weak_validation_case_count": 0,
        "missing_validation_expectation_count": 0,
        "weak_validation_case_ids": [],
        "missing_validation_expectation_case_ids": [],
    }


def _complete_parameter_safety_metrics() -> dict:
    return {
        "ok": True,
        "covered_operator_count": 40,
        "priority_operator_count": 40,
        "missing_operator_count": 0,
        "invalid_source_count": 0,
        "priority_group_count": 7,
        "priority_group_missing_operator_count": 0,
        "priority_groups": [
            "audio_control",
            "dat_callbacks_protocols",
            "feedback_top_processing",
            "glsl",
            "panel_parameters",
            "pop",
            "render_material",
        ],
    }


def _complete_generated_code_success_metrics() -> dict:
    return {
        "ok": True,
        "generated_code_case_count": 18,
        "generated_code_block_count": 25,
        "language_count": 2,
        "languages": ["glsl", "python"],
        "static_issue_count": 0,
        "runtime_contract_count": 25,
        "runtime_contract_missing_count": 0,
        "runtime_check_count": 3,
        "runtime_checks": ["callback_guard_present", "compile_state", "finite_pop_bounds"],
        "generated_code_case_ids": ["glsl_top_shader_compiled"],
    }


def _complete_rollback_frequency_metrics() -> dict:
    return {
        "ok": True,
        "case_count": 50,
        "rollback_enabled_case_count": 50,
        "rollback_behavior_failure_count": 0,
        "rollback_required_case_count": 0,
        "rollback_performed_count": 0,
        "rollback_frequency": 0.0,
        "rollback_enabled_case_ids": ["audio_feedback_panel_debug"],
        "rollback_behavior_failure_case_ids": [],
        "rollback_required_case_ids": [],
        "rollback_performed_case_ids": [],
    }


def _complete_operator_coverage_metrics() -> dict:
    return {
        "ok": True,
        "case_count": 50,
        "checked_case_count": 50,
        "missing_required_operator_count": 0,
        "operator_set_failure_count": 0,
        "missing_required_operator_case_ids": [],
        "operator_set_failure_case_ids": [],
        "checked_case_ids": ["audio_feedback_panel_debug"],
    }


def _complete_unsupported_operator_avoidance_metrics() -> dict:
    return {
        "ok": True,
        "checked_forbidden_operator_case_count": 1,
        "forbidden_operator_case_count": 0,
        "checked_forbidden_operator_case_ids": ["audio_feedback_panel_live_source"],
        "forbidden_operator_case_ids": [],
        "forbidden_ops_present": [],
    }


def _complete_prompt_safety_metrics() -> dict:
    return {
        "ok": True,
        "expected_blocked_case_count": 1,
        "passed_expected_blocked_case_count": 1,
        "failed_expected_blocked_case_count": 0,
        "expected_blocked_case_ids": ["vague_prompt_make_it_cool"],
        "passed_expected_blocked_case_ids": ["vague_prompt_make_it_cool"],
        "failed_expected_blocked_case_ids": [],
    }


def _complete_decomposition_accuracy_metrics() -> dict:
    return {
        "ok": True,
        "compiled_case_count": 31,
        "multi_domain_case_count": 20,
        "three_plus_domain_case_count": 10,
        "compiled_domain_failure_count": 0,
        "time_behavior_checked_case_count": 1,
        "time_behavior_failure_count": 0,
        "pattern_composition_failure_count": 0,
        "failed_case_ids": [],
        "multi_domain_case_ids": ["audio_feedback_panel_debug"],
        "time_behavior_checked_case_ids": ["audio_feedback_panel_debug"],
    }


def _complete_delivery_phase_coverage() -> dict:
    return {
        "schema_version": 1,
        "ok": True,
        "scope": "brain_eval_phased_delivery_mvp",
        "phase_count": 4,
        "complete_phase_count": 4,
        "incomplete_phase_count": 0,
        "phases": [
            {"phase_id": "phase_1", "ok": True, "missing": []},
            {"phase_id": "phase_2", "ok": True, "missing": []},
            {"phase_id": "phase_3", "ok": True, "missing": []},
            {"phase_id": "phase_4", "ok": True, "missing": []},
        ],
    }


def _complete_brain_smoke_payload() -> dict:
    return {
        **_candidate_report_identity(),
        "ok": True,
        "mode": "dry_run",
        "mutated_td": False,
        "scenario_count": 16,
        "generated_code_summary": {
            "block_count": 7,
            "languages": ["glsl", "python"],
            "runtime_checks": ["callback_guard_present", "compile_state", "topology_capacity"],
            "runtime_contract_count": 9,
            "runtime_contract_checks": ["callback_guard_present", "compile_state", "topology_capacity"],
            "risk_flags": ["validate-glsl-compile-state"],
            "source_payloads_included": False,
        },
        "scenarios": [
            {
                "id": "feedback_loop",
                "status": "planned",
                "missing_expected_ops": [],
                "blocked_questions": [],
                "profile_probes": [{"probe_id": "feedback_cycle"}],
                "profile_probe_results": [{"probe_id": "feedback_cycle", "status": "static_pass"}],
            },
            {
                "id": "audio_reactive_top",
                "status": "planned",
                "missing_expected_ops": [],
                "blocked_questions": [],
                "profile_probes": [{"probe_id": "audio_signal_activity"}],
                "profile_probe_results": [
                    {"probe_id": "audio_signal_activity", "status": "runtime_contract_present"}
                ],
            },
            {
                "id": "glsl_shader_top",
                "status": "planned",
                "missing_expected_ops": [],
                "blocked_questions": [],
                "profile_probes": [{"probe_id": "shader_source_present"}],
                "profile_probe_results": [{"probe_id": "shader_source_present", "status": "static_pass"}],
            },
            {
                "id": "render_pipeline_expensive_validation",
                "status": "planned",
                "validation_profile": "structural_visual_expensive",
                "missing_expected_ops": [],
                "blocked_questions": [],
                "profile_probes": [{"probe_id": "render_top_output", "cost_level": "expensive"}],
                "profile_probe_results": [
                    {"probe_id": "render_top_output", "status": "runtime_contract_present"}
                ],
            },
        ],
    }


def _complete_brain_live_smoke_payload() -> dict:
    payload = _complete_brain_smoke_payload()
    payload.update(
        {
            "mode": "live",
            "mutated_td": True,
            "connection_error": None,
            "td_health": {"status": "ok", "api_version": "2.0.0"},
            "sync_diagnostic": {"overall": {"status": "pass"}, "auth": {"matches": True}},
            "visual_quality_summary": {"checked_count": 2, "failed_count": 0, "missing_count": 0},
            "panel_interaction_results": {
                "ok": True,
                "checked_count": 5,
                "failed_count": 0,
                "actions": ["reset", "thumb", "next", "prev", "back"],
            },
            "performance_summary": {
                "ok": True,
                "steady_state_max_ms": 11.5,
                "frame_budget_ms": 16.667,
                "safety_target_ms": 12.0,
                "warmup_spike_recorded": True,
                "target_root_spike_count": 0,
                "sys_ui_spike_count": 1,
            },
            "incident_replay": {"ok": True, "bug_count": 45, "untriaged": []},
            "transactional_generated_code_smoke": {
                "status": "cleaned_up",
                "ok": True,
                "mutated_td": True,
                "runtime_evidence": [
                    {"check_id": "compile_state", "status": "pass"},
                    {"check_id": "callback_guard_present", "status": "pass"},
                ],
                "cleanup": {
                    "rollback_performed": True,
                    "td_stable": True,
                    "remaining_created_paths": [],
                },
            },
        }
    )
    payload["generated_code_summary"]["runtime_contract_checks"] = [
        "callback_guard_present",
        "compile_state",
        "topology_capacity",
    ]
    payload["scenarios"].append(
        {
            "id": "glsl_advanced_pop_topology",
            "status": "planned",
            "missing_expected_ops": [],
            "blocked_questions": [],
            "profile_probes": [{"probe_id": "topology_capacity"}],
            "profile_probe_results": [
                {"probe_id": "topology_capacity", "status": "runtime_contract_present"}
            ],
        }
    )
    payload["scenarios"].append(
        {
            "id": "serial_dat_protocol_bridge",
            "status": "skipped_unavailable",
            "blocked_questions": ["Required operator is unavailable in this TouchDesigner build."],
            "missing_facts": ["missing_op:serialDAT"],
        }
    )
    return payload


def _complete_plugin_surface_payload() -> dict:
    return {
        **_candidate_report_identity(),
        "ok": True,
        "tool_count": 114,
        "brain_skill_count": 7,
        "agent_count": 3,
        "hook_count": 1,
        "missing_artifacts": [],
        "mirror_mismatches": [],
        "personal_path_leaks": [],
        "local_first": {"ok": True, "hosted_llm_dependency_leaks": []},
        "mcp_config": {"uses_plugin_root_placeholder": True},
        "hooks": {
            "uses_hook_check_module": True,
            "uses_hook_runner": True,
            "has_post_tool_use_guard": True,
            "has_stop_release_guard": True,
            "shipped_stop_hook": False,
            "post_tool_use_scoped": True,
            "uses_project_runtime_fallback": False,
            "source_release_guard": True,
            "stop_hook_reentry_guard": True,
            "safe_for_distribution": True,
        },
        "codex_manifest": {"has_skills": True, "has_agents": True, "has_mcp_servers": True},
        "claude_manifest": {
            "has_skills": True,
            "has_agents": True,
            "has_hooks": True,
            "has_mcp_servers": True,
        },
    }


def _complete_param_semantics_risk_payload() -> dict:
    return {
        **_candidate_report_identity(),
        "ok": True,
        "contract": "high_cook_risk_direct_param_coverage_v1",
        "high_cook_risk_count": 10,
        "direct_risk_count": 4,
        "validation_only_count": 6,
        "unclassified_count": 0,
        "direct_risk_parameters": [
            {"op_type": "executeDAT", "name": "active", "behavior": "direct-risk"},
            {"op_type": "mqttclientDAT", "name": "password", "behavior": "direct-risk"},
            {"op_type": "webclientDAT", "name": "pw", "behavior": "direct-risk"},
            {"op_type": "webserverDAT", "name": "password", "behavior": "direct-risk"},
        ],
        "validation_only_parameters": [
            {"op_type": "renderTOP", "name": "camera", "behavior": "validation-only"}
        ],
        "unclassified_high_cook_risk_parameters": [],
    }


def _complete_operator_availability_payload(stored_path: str | None = None) -> dict:
    payload = {
        **_candidate_report_identity(),
        "schema_version": 1,
        "ok": True,
        "target_count": 6,
        "available_count": 5,
        "unavailable_count": 1,
        "cleanup_ok": True,
        "availability_matrix": {
            "schema_version": 1,
            "td_build": "2025.32820",
            "platform": "macOS",
            "generated_at": "2026-06-22T00:00:00+00:00",
            "installed_addons": ["POPX"],
            "operators": {
                "glslcreatePOP": {"family": "POP", "available": False},
                "glsladvancedPOP": {"family": "POP", "available": True},
                "topologyPOP": {"family": "POP", "available": True},
                "gltfinCOMP": {"family": "COMP", "available": True},
                "gltfoutCOMP": {"family": "COMP", "available": True},
                "scriptPOP": {"family": "POP", "available": True},
            },
            "family_aliases": {
                "POP": ["glsladvancedPOP", "glslcreatePOP", "topologyPOP"],
                "COMP": ["gltfinCOMP", "gltfoutCOMP"],
            },
            "unavailable_reasons": {
                "glslcreatePOP": "deprecated and unavailable in this TD build",
            },
        },
        "results": [
            {
                "op_type": "glslcreatePOP",
                "family": "POP",
                "role": "deprecated_gap",
                "replacement_for": None,
                "available": False,
                "error": "deprecated and unavailable in this TD build",
            },
            {
                "op_type": "glsladvancedPOP",
                "family": "POP",
                "role": "replacement",
                "replacement_for": "glslcreatePOP",
                "available": True,
                "error": "",
            },
            {
                "op_type": "topologyPOP",
                "family": "POP",
                "role": "replacement",
                "replacement_for": "glslcreatePOP",
                "available": True,
                "error": "",
            },
            {
                "op_type": "gltfinCOMP",
                "family": "COMP",
                "role": "release_new_op",
                "replacement_for": None,
                "available": True,
                "error": "",
            },
            {
                "op_type": "gltfoutCOMP",
                "family": "COMP",
                "role": "release_new_op",
                "replacement_for": None,
                "available": True,
                "error": "",
            },
            {
                "op_type": "scriptPOP",
                "family": "POP",
                "role": "release_new_op",
                "replacement_for": None,
                "available": True,
                "error": "",
            },
        ],
    }
    if stored_path is not None:
        payload["stored_availability_report"] = stored_path
    return payload


def _complete_brain_eval_payload(*, case_count: int = 50, passed: int = 50) -> dict:
    return {
        **_candidate_report_identity(),
        "ok": True,
        "case_count": case_count,
        "passed": passed,
        "failed": 0,
        "pattern_coverage": {
            "ok": True,
            "pattern_count": 18,
            "covered_pattern_count": 18,
            "source_checked_pattern_count": 18,
            "invalid_source_count": 0,
            "invalid_sources": [],
            "missing_patterns": [],
            "stale_pattern_references": [],
        },
        "compiler_stability": {
            "ok": True,
            "compiled_case_count": 31,
            "passed_compiled_case_count": 31,
            "blocked_compiled_case_count": 0,
            "compiled_domain_failure_count": 0,
            "pattern_composition_failure_count": 0,
        },
        "readability_metrics": {
            "assembled_case_count": 31,
            "fully_readable_assembled_case_count": 31,
            "avg_assembled_score": 5.0,
            "avg_assembled_max_score": 5.0,
        },
        "showpiece_assembly_metrics": _complete_showpiece_assembly_metrics(),
        "validation_metrics": _complete_validation_metrics(),
        "parameter_safety_metrics": _complete_parameter_safety_metrics(),
        "generated_code_success_metrics": _complete_generated_code_success_metrics(),
        "rollback_frequency_metrics": _complete_rollback_frequency_metrics(),
        "operator_coverage_metrics": _complete_operator_coverage_metrics(),
        "unsupported_operator_avoidance_metrics": _complete_unsupported_operator_avoidance_metrics(),
        "prompt_safety_metrics": _complete_prompt_safety_metrics(),
        "decomposition_accuracy_metrics": _complete_decomposition_accuracy_metrics(),
        "delivery_phase_coverage": _complete_delivery_phase_coverage(),
        "time_metrics": {
            "time_to_first_green_cycles": {"min": 1, "max": 1, "avg": 1.0},
        },
        "assembly_control_bindings": {
            "ok": True,
            "missing_count": 0,
            "missing": [],
        },
        "param_semantics_coverage": {
            "ok": True,
            "missing_operator_count": 0,
            "invalid_source_count": 0,
            "priority_groups": _complete_param_semantics_priority_groups(),
        },
        "operator_availability_coverage": {
            "ok": True,
            "missing_required_rule_count": 0,
            "invalid_source_count": 0,
            "missing_tradeoff_count": 0,
        },
        "availability_matrix_metrics": {
            "ok": True,
            "structured_case_count": 1,
            "known_build_case_count": 1,
            "missing_unavailable_reason_count": 0,
            "substitution_without_matrix_count": 0,
            "structured_case_ids": ["audio_feedback_panel_device_substitution"],
            "substitution_without_matrix_case_ids": [],
        },
        "validation_probe_coverage": {
            "ok": True,
            "missing_required_profile_count": 0,
            "invalid_source_count": 0,
            "uncontrolled_expensive_probe_count": 0,
        },
        "generated_code_harness_coverage": {
            "ok": True,
            "missing_language_count": 0,
            "missing_static_check_count": 0,
            "missing_runtime_check_count": 0,
            "invalid_source_count": 0,
        },
        "trace_promotion_coverage": {
            "ok": True,
            "eligible_trace_fixture_count": 2,
            "promoted_fixture_count": 2,
            "blocked_fixture_count": 0,
            "invalid_source_count": 0,
            "promoted_case_ids": ["audio_feedback_panel_debug", "glsl_top_shader_compiled"],
        },
        "trace_memory_reuse_coverage": {
            "ok": True,
            "fixture_count": 2,
            "loaded_pattern_count": 2,
            "reused_fixture_count": 2,
            "miss_count": 0,
            "reused_case_ids": ["audio_feedback_panel_debug", "glsl_top_shader_compiled"],
            "missed_fixtures": [],
        },
        "runtime_safety_metrics": {
            "ok": True,
            "case_count": case_count,
            "checked_forbidden_operator_case_count": 1,
            "blocked_case_count": 0,
            "missing_fact_case_count": 0,
            "forbidden_operator_case_count": 0,
            "rollback_behavior_failure_count": 0,
            "final_state_quality_failure_count": 0,
            "operator_set_failure_count": 0,
            "max_plan_ops_failure_count": 0,
        },
        "substitution_quality_metrics": {
            "ok": True,
            "case_count": case_count,
            "substitution_case_count": 1,
            "approved_substitution_count": 1,
            "pending_approval_count": 0,
            "approval_required_count": 1,
            "unapproved_required_count": 0,
            "substitution_without_rule_count": 0,
            "replacement_operator_missing_count": 0,
            "low_confidence_count": 0,
        },
        "trace_replay": {
            "ok": True,
            "baseline_case_count": case_count,
            "case_count": case_count,
            "drift_count": 0,
            "drifts": [],
        },
        "param_value_coverage": _complete_param_value_coverage(case_count=case_count),
    }


def _complete_param_value_coverage(*, case_count: int = 50) -> dict:
    return {
        "ok": True,
        "eligible_case_count": case_count,
        "carrying_case_count": case_count,
        "coverage": 1.0,
        "min_coverage": 0.70,
        "expected_param_value_case_count": 12,
        "min_expected_param_value_case_count": 10,
        "expected_param_value_failure_count": 0,
        "expected_param_value_failure_case_ids": [],
    }


def test_evaluate_gates_param_value_coverage():
    """Param-gating polarity flip acceptance gate: plans must keep carrying
    non-default param values, and the expected_param_values corpus must stay
    populated and green."""
    brain_eval = _complete_brain_eval_payload()

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain param value coverage fraction"]["status"] == "pass"
    assert labels["brain param value expected case count"]["status"] == "pass"
    assert labels["brain param value expected failure count"]["status"] == "pass"

    regressed = _complete_brain_eval_payload()
    regressed["param_value_coverage"] = {
        "ok": False,
        "eligible_case_count": 101,
        "carrying_case_count": 30,
        "coverage": 0.297,
        "min_coverage": 0.70,
        "expected_param_value_case_count": 3,
        "min_expected_param_value_case_count": 10,
        "expected_param_value_failure_count": 2,
        "expected_param_value_failure_case_ids": ["glsl_top_shader", "midi_control_bridge"],
    }
    failed = check_release_gates.evaluate(None, None, regressed)
    failed_labels = {check["label"]: check for check in failed["checks"]}
    assert failed_labels["brain param value coverage fraction"]["status"] == "fail"
    assert failed_labels["brain param value expected case count"]["status"] == "fail"
    assert failed_labels["brain param value expected failure count"]["status"] == "fail"
    assert failed["summary"]["ok"] is False


def test_evaluate_passes_with_valid_brain_eval_payload():
    brain_eval = {
        "ok": True,
        "case_count": 50,
        "passed": 50,
        "failed": 0,
        "pattern_coverage": {
            "ok": True,
            "pattern_count": 18,
            "covered_pattern_count": 18,
            "source_checked_pattern_count": 18,
            "invalid_source_count": 0,
            "invalid_sources": [],
            "missing_patterns": [],
            "stale_pattern_references": [],
        },
        "compiler_stability": {
            "ok": True,
            "compiled_case_count": 31,
            "passed_compiled_case_count": 31,
            "blocked_compiled_case_count": 0,
            "compiled_domain_failure_count": 0,
            "pattern_composition_failure_count": 0,
        },
        "readability_metrics": {
            "assembled_case_count": 31,
            "fully_readable_assembled_case_count": 31,
            "avg_assembled_score": 5.0,
            "avg_assembled_max_score": 5.0,
        },
        "showpiece_assembly_metrics": _complete_showpiece_assembly_metrics(),
        "validation_metrics": _complete_validation_metrics(),
        "parameter_safety_metrics": _complete_parameter_safety_metrics(),
        "generated_code_success_metrics": _complete_generated_code_success_metrics(),
        "rollback_frequency_metrics": _complete_rollback_frequency_metrics(),
        "operator_coverage_metrics": _complete_operator_coverage_metrics(),
        "unsupported_operator_avoidance_metrics": _complete_unsupported_operator_avoidance_metrics(),
        "prompt_safety_metrics": _complete_prompt_safety_metrics(),
        "decomposition_accuracy_metrics": _complete_decomposition_accuracy_metrics(),
        "delivery_phase_coverage": _complete_delivery_phase_coverage(),
        "time_metrics": {
            "time_to_first_green_cycles": {"min": 1, "max": 1, "avg": 1.0},
        },
        "assembly_control_bindings": {
            "ok": True,
            "missing_count": 0,
            "missing": [],
        },
        "param_semantics_coverage": {
            "ok": True,
            "missing_operator_count": 0,
            "invalid_source_count": 0,
            "priority_groups": _complete_param_semantics_priority_groups(),
        },
        "operator_availability_coverage": {
            "ok": True,
            "missing_required_rule_count": 0,
            "invalid_source_count": 0,
            "missing_tradeoff_count": 0,
        },
        "availability_matrix_metrics": {
            "ok": True,
            "structured_case_count": 1,
            "known_build_case_count": 1,
            "missing_unavailable_reason_count": 0,
            "substitution_without_matrix_count": 0,
            "structured_case_ids": ["audio_feedback_panel_device_substitution"],
            "substitution_without_matrix_case_ids": [],
        },
        "validation_probe_coverage": {
            "ok": True,
            "missing_required_profile_count": 0,
            "invalid_source_count": 0,
            "uncontrolled_expensive_probe_count": 0,
        },
        "generated_code_harness_coverage": {
            "ok": True,
            "missing_language_count": 0,
            "missing_static_check_count": 0,
            "missing_runtime_check_count": 0,
            "invalid_source_count": 0,
        },
        "trace_promotion_coverage": {
            "ok": True,
            "eligible_trace_fixture_count": 2,
            "promoted_fixture_count": 2,
            "blocked_fixture_count": 0,
            "invalid_source_count": 0,
            "promoted_case_ids": ["audio_feedback_panel_debug", "glsl_top_shader_compiled"],
        },
        "trace_memory_reuse_coverage": {
            "ok": True,
            "fixture_count": 2,
            "loaded_pattern_count": 2,
            "reused_fixture_count": 2,
            "miss_count": 0,
            "reused_case_ids": ["audio_feedback_panel_debug", "glsl_top_shader_compiled"],
            "missed_fixtures": [],
        },
        "runtime_safety_metrics": {
            "ok": True,
            "case_count": 50,
            "checked_forbidden_operator_case_count": 1,
            "blocked_case_count": 0,
            "missing_fact_case_count": 0,
            "forbidden_operator_case_count": 0,
            "rollback_behavior_failure_count": 0,
            "final_state_quality_failure_count": 0,
            "operator_set_failure_count": 0,
            "max_plan_ops_failure_count": 0,
        },
        "substitution_quality_metrics": {
            "ok": True,
            "case_count": 50,
            "substitution_case_count": 1,
            "approved_substitution_count": 1,
            "pending_approval_count": 0,
            "approval_required_count": 1,
            "unapproved_required_count": 0,
            "substitution_without_rule_count": 0,
            "replacement_operator_missing_count": 0,
            "low_confidence_count": 0,
        },
        "trace_replay": {
            "ok": True,
            "baseline_case_count": 50,
            "case_count": 50,
            "drift_count": 0,
            "drifts": [],
        },
    }

    report = check_release_gates.evaluate(None, None, brain_eval)

    assert report["summary"]["ok"] is True
    assert report["summary"]["failed"] == 0
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain golden eval case count"]["status"] == "pass"
    assert labels["brain golden eval failed cases"]["status"] == "pass"
    assert labels["brain pattern coverage missing count"]["status"] == "pass"
    assert labels["brain pattern coverage official source checked count"]["status"] == "pass"
    assert labels["brain pattern coverage invalid source count"]["status"] == "pass"
    assert labels["brain compiler stability failed cases"]["status"] == "pass"
    assert labels["brain trace replay drift count"]["status"] == "pass"
    assert labels["brain readability fully assembled count"]["status"] == "pass"
    assert labels["brain readability assembled case count"]["status"] == "pass"
    assert labels["brain readability average score gap"]["status"] == "pass"
    assert labels["brain showpiece case count"]["status"] == "pass"
    assert labels["brain showpiece assembled case count"]["status"] == "pass"
    assert labels["brain showpiece fully readable case count"]["status"] == "pass"
    assert labels["brain showpiece unassembled case count"]["status"] == "pass"
    assert labels["brain showpiece unreadable case count"]["status"] == "pass"
    assert labels["brain validation metrics minimum check count"]["status"] == "pass"
    assert labels["brain validation metrics weak case count"]["status"] == "pass"
    assert labels["brain validation metrics missing expectation count"]["status"] == "pass"
    assert labels["brain parameter safety covered operator count"]["status"] == "pass"
    assert labels["brain parameter safety priority operator count"]["status"] == "pass"
    assert labels["brain parameter safety missing operator count"]["status"] == "pass"
    assert labels["brain parameter safety invalid source count"]["status"] == "pass"
    assert labels["brain parameter safety priority group count"]["status"] == "pass"
    assert labels["brain parameter safety priority group missing operator count"]["status"] == "pass"
    assert labels["brain generated code success case count"]["status"] == "pass"
    assert labels["brain generated code success block count"]["status"] == "pass"
    assert labels["brain generated code success language coverage"]["status"] == "pass"
    assert labels["brain generated code success static issue count"]["status"] == "pass"
    assert labels["brain generated code success runtime contract count"]["status"] == "pass"
    assert labels["brain generated code success missing runtime contract count"]["status"] == "pass"
    assert labels["brain operator coverage checked case count"]["status"] == "pass"
    assert labels["brain operator coverage missing required operator count"]["status"] == "pass"
    assert labels["brain operator coverage operator set failure count"]["status"] == "pass"
    assert labels["brain unsupported operator checked case count"]["status"] == "pass"
    assert labels["brain unsupported operator forbidden case count"]["status"] == "pass"
    assert labels["brain unsupported operator present count"]["status"] == "pass"
    assert labels["brain decomposition multi-domain case count"]["status"] == "pass"
    assert labels["brain decomposition three-plus-domain case count"]["status"] == "pass"
    assert labels["brain decomposition domain failure count"]["status"] == "pass"
    assert labels["brain decomposition time behavior checked case count"]["status"] == "pass"
    assert labels["brain decomposition time behavior failure count"]["status"] == "pass"
    assert labels["brain decomposition pattern failure count"]["status"] == "pass"
    assert labels["brain delivery phase coverage phase count"]["status"] == "pass"
    assert labels["brain delivery phase coverage complete phase count"]["status"] == "pass"
    assert labels["brain delivery phase coverage incomplete phase count"]["status"] == "pass"
    assert labels["brain time to first green max cycles"]["status"] == "pass"
    assert labels["brain time to first green average cycles"]["status"] == "pass"
    assert labels["brain assembly control binding missing count"]["status"] == "pass"
    assert labels["brain param semantics missing operator count"]["status"] == "pass"
    assert labels["brain param semantics invalid source count"]["status"] == "pass"
    assert labels["brain operator availability missing substitution rule count"]["status"] == "pass"
    assert labels["brain operator availability invalid source count"]["status"] == "pass"
    assert labels["brain operator availability missing tradeoff count"]["status"] == "pass"
    assert labels["brain availability matrix structured case count"]["status"] == "pass"
    assert labels["brain availability matrix known build case count"]["status"] == "pass"
    assert labels["brain availability matrix missing reason count"]["status"] == "pass"
    assert labels["brain availability matrix substitution missing count"]["status"] == "pass"
    assert labels["brain validation probe missing profile count"]["status"] == "pass"
    assert labels["brain validation probe invalid source count"]["status"] == "pass"
    assert labels["brain validation probe uncontrolled expensive count"]["status"] == "pass"
    assert labels["brain generated code harness missing language count"]["status"] == "pass"
    assert labels["brain generated code harness missing static check count"]["status"] == "pass"
    assert labels["brain generated code harness missing runtime check count"]["status"] == "pass"
    assert labels["brain generated code harness invalid source count"]["status"] == "pass"
    assert labels["brain trace promotion eligible fixture count"]["status"] == "pass"
    assert labels["brain trace promotion promoted fixture count"]["status"] == "pass"
    assert labels["brain trace promotion blocked fixture count"]["status"] == "pass"
    assert labels["brain trace promotion invalid source count"]["status"] == "pass"
    assert labels["brain trace memory reuse fixture count"]["status"] == "pass"
    assert labels["brain trace memory reuse loaded pattern count"]["status"] == "pass"
    assert labels["brain trace memory reuse reused fixture count"]["status"] == "pass"
    assert labels["brain trace memory reuse miss count"]["status"] == "pass"
    assert labels["brain runtime safety case count"]["status"] == "pass"
    assert labels["brain runtime safety forbidden operator fixture count"]["status"] == "pass"
    assert labels["brain runtime safety blocked case count"]["status"] == "pass"
    assert labels["brain runtime safety missing fact case count"]["status"] == "pass"
    assert labels["brain runtime safety forbidden operator case count"]["status"] == "pass"
    assert labels["brain runtime safety rollback behavior failures"]["status"] == "pass"
    assert labels["brain runtime safety final state failures"]["status"] == "pass"
    assert labels["brain runtime safety operator set failures"]["status"] == "pass"
    assert labels["brain runtime safety max plan op failures"]["status"] == "pass"
    assert labels["brain rollback frequency enabled case count"]["status"] == "pass"
    assert labels["brain rollback frequency behavior failure count"]["status"] == "pass"
    assert labels["brain rollback frequency required case count"]["status"] == "pass"
    assert labels["brain rollback frequency performed case count"]["status"] == "pass"
    assert labels["brain substitution quality case count"]["status"] == "pass"
    assert labels["brain substitution quality approved count"]["status"] == "pass"
    assert labels["brain substitution quality pending approvals"]["status"] == "pass"
    assert labels["brain substitution quality unapproved required substitutions"]["status"] == "pass"
    assert labels["brain substitution quality missing rule count"]["status"] == "pass"
    assert labels["brain substitution quality missing replacement count"]["status"] == "pass"
    assert labels["brain substitution quality low confidence count"]["status"] == "pass"


def test_evaluate_fails_when_brain_eval_case_count_is_below_phase_four_floor():
    brain_eval = _complete_brain_eval_payload(case_count=49, passed=49)

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain golden eval case count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_report_ok_is_false():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["ok"] = False

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain golden eval report ok"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_compiled_case_count_is_below_compiler_floor():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["compiler_stability"]["compiled_case_count"] = 29
    brain_eval["compiler_stability"]["passed_compiled_case_count"] = 29

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain compiler stability compiled case count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_decomposition_accuracy_regresses():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["decomposition_accuracy_metrics"] = {
        "ok": False,
        "compiled_case_count": 31,
        "multi_domain_case_count": 19,
        "three_plus_domain_case_count": 9,
        "compiled_domain_failure_count": 1,
        "time_behavior_checked_case_count": 0,
        "time_behavior_failure_count": 1,
        "pattern_composition_failure_count": 1,
        "failed_case_ids": ["audio_feedback_panel_debug"],
        "multi_domain_case_ids": [],
        "time_behavior_checked_case_ids": [],
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain decomposition multi-domain case count"]["status"] == "fail"
    assert labels["brain decomposition three-plus-domain case count"]["status"] == "fail"
    assert labels["brain decomposition domain failure count"]["status"] == "fail"
    assert labels["brain decomposition time behavior checked case count"]["status"] == "fail"
    assert labels["brain decomposition time behavior failure count"]["status"] == "fail"
    assert labels["brain decomposition pattern failure count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_runtime_safety_regresses():
    brain_eval = {
        "ok": False,
        "failed": 0,
        "pattern_coverage": {"ok": True, "missing_patterns": [], "stale_pattern_references": []},
        "compiler_stability": {
            "ok": True,
            "compiled_case_count": 1,
            "passed_compiled_case_count": 1,
            "blocked_compiled_case_count": 0,
            "compiled_domain_failure_count": 0,
            "pattern_composition_failure_count": 0,
        },
        "readability_metrics": {
            "assembled_case_count": 1,
            "fully_readable_assembled_case_count": 1,
            "avg_assembled_score": 5.0,
            "avg_assembled_max_score": 5.0,
        },
        "runtime_safety_metrics": {
            "ok": False,
            "case_count": 1,
            "checked_forbidden_operator_case_count": 1,
            "blocked_case_count": 1,
            "missing_fact_case_count": 0,
            "forbidden_operator_case_count": 1,
            "rollback_behavior_failure_count": 1,
            "final_state_quality_failure_count": 1,
            "operator_set_failure_count": 1,
            "max_plan_ops_failure_count": 1,
        },
        "trace_replay": {"ok": True, "drift_count": 0},
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain runtime safety blocked case count"]["status"] == "fail"
    assert labels["brain runtime safety forbidden operator case count"]["status"] == "fail"
    assert labels["brain runtime safety rollback behavior failures"]["status"] == "fail"
    assert labels["brain runtime safety final state failures"]["status"] == "fail"
    assert labels["brain runtime safety operator set failures"]["status"] == "fail"
    assert labels["brain runtime safety max plan op failures"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_has_no_expected_blocked_prompt_safety_cases():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["prompt_safety_metrics"] = {
        "ok": False,
        "expected_blocked_case_count": 0,
        "passed_expected_blocked_case_count": 0,
        "failed_expected_blocked_case_ids": [],
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain prompt safety expected blocked case count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_has_failed_expected_blocked_prompt_safety_cases():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["prompt_safety_metrics"] = {
        "ok": False,
        "expected_blocked_case_count": 1,
        "passed_expected_blocked_case_count": 0,
        "failed_expected_blocked_case_ids": ["vague_prompt_make_it_cool"],
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain prompt safety failed expected blocked case count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_rollback_frequency_regresses():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["rollback_frequency_metrics"] = {
        "ok": False,
        "case_count": 50,
        "rollback_enabled_case_count": 49,
        "rollback_behavior_failure_count": 1,
        "rollback_required_case_count": 1,
        "rollback_performed_count": 1,
        "rollback_frequency": 0.02,
        "rollback_enabled_case_ids": [],
        "rollback_behavior_failure_case_ids": ["audio_feedback_panel_debug"],
        "rollback_required_case_ids": ["audio_feedback_panel_debug"],
        "rollback_performed_case_ids": ["audio_feedback_panel_debug"],
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain rollback frequency enabled case count"]["status"] == "fail"
    assert labels["brain rollback frequency behavior failure count"]["status"] == "fail"
    assert labels["brain rollback frequency required case count"]["status"] == "fail"
    assert labels["brain rollback frequency performed case count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_operator_coverage_regresses():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["operator_coverage_metrics"] = {
        "ok": False,
        "case_count": 50,
        "checked_case_count": 49,
        "missing_required_operator_count": 1,
        "operator_set_failure_count": 1,
        "missing_required_operator_case_ids": ["audio_feedback_panel_debug"],
        "operator_set_failure_case_ids": ["audio_feedback_panel_debug"],
        "checked_case_ids": [],
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain operator coverage checked case count"]["status"] == "fail"
    assert labels["brain operator coverage missing required operator count"]["status"] == "fail"
    assert labels["brain operator coverage operator set failure count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_unsupported_operator_avoidance_regresses():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["unsupported_operator_avoidance_metrics"] = {
        "ok": False,
        "checked_forbidden_operator_case_count": 0,
        "forbidden_operator_case_count": 1,
        "checked_forbidden_operator_case_ids": [],
        "forbidden_operator_case_ids": ["audio_feedback_panel_live_source"],
        "forbidden_ops_present": ["audiofileinCHOP"],
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain unsupported operator checked case count"]["status"] == "fail"
    assert labels["brain unsupported operator forbidden case count"]["status"] == "fail"
    assert labels["brain unsupported operator present count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_substitution_quality_regresses():
    brain_eval = {
        "ok": False,
        "failed": 0,
        "pattern_coverage": {"ok": True, "missing_patterns": [], "stale_pattern_references": []},
        "compiler_stability": {
            "ok": True,
            "compiled_case_count": 1,
            "passed_compiled_case_count": 1,
            "blocked_compiled_case_count": 0,
            "compiled_domain_failure_count": 0,
            "pattern_composition_failure_count": 0,
        },
        "readability_metrics": {
            "assembled_case_count": 1,
            "fully_readable_assembled_case_count": 1,
            "avg_assembled_score": 5.0,
            "avg_assembled_max_score": 5.0,
        },
        "substitution_quality_metrics": {
            "ok": False,
            "case_count": 1,
            "substitution_case_count": 1,
            "approved_substitution_count": 0,
            "pending_approval_count": 1,
            "approval_required_count": 1,
            "unapproved_required_count": 1,
            "substitution_without_rule_count": 1,
            "replacement_operator_missing_count": 1,
            "low_confidence_count": 1,
        },
        "trace_replay": {"ok": True, "drift_count": 0},
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain substitution quality approved count"]["status"] == "fail"
    assert labels["brain substitution quality pending approvals"]["status"] == "fail"
    assert labels["brain substitution quality unapproved required substitutions"]["status"] == "fail"
    assert labels["brain substitution quality missing rule count"]["status"] == "fail"
    assert labels["brain substitution quality missing replacement count"]["status"] == "fail"
    assert labels["brain substitution quality low confidence count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_has_missing_assembly_control_bindings():
    brain_eval = {
        "ok": True,
        "failed": 0,
        "pattern_coverage": {"ok": True, "missing_patterns": [], "stale_pattern_references": []},
        "compiler_stability": {
            "ok": True,
            "compiled_case_count": 1,
            "passed_compiled_case_count": 1,
            "blocked_compiled_case_count": 0,
            "compiled_domain_failure_count": 0,
            "pattern_composition_failure_count": 0,
        },
        "readability_metrics": {
            "assembled_case_count": 1,
            "fully_readable_assembled_case_count": 1,
        },
        "assembly_control_bindings": {
            "ok": False,
            "missing_count": 1,
            "missing": [
                {
                    "macro_id": "add_user_controls",
                    "control": "feedback_decay",
                    "reason": "unknown_pattern_parameter",
                }
            ],
        },
        "trace_replay": {"ok": True, "drift_count": 0},
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain assembly control binding missing count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_readability_average_regresses():
    brain_eval = {
        "ok": False,
        "failed": 0,
        "pattern_coverage": {"ok": True, "missing_patterns": [], "stale_pattern_references": []},
        "compiler_stability": {
            "ok": True,
            "compiled_case_count": 31,
            "passed_compiled_case_count": 31,
            "blocked_compiled_case_count": 0,
            "compiled_domain_failure_count": 0,
            "pattern_composition_failure_count": 0,
        },
        "readability_metrics": {
            "assembled_case_count": 31,
            "fully_readable_assembled_case_count": 31,
            "avg_assembled_score": 4.5,
            "avg_assembled_max_score": 5.0,
        },
        "trace_replay": {"ok": True, "drift_count": 0},
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain readability average score gap"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_showpiece_assembly_regresses():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["showpiece_assembly_metrics"] = {
        "ok": False,
        "showpiece_case_count": 8,
        "assembled_showpiece_case_count": 7,
        "fully_readable_showpiece_case_count": 7,
        "unassembled_showpiece_case_ids": ["audio_feedback_panel_debug"],
        "not_fully_readable_showpiece_case_ids": ["audio_feedback_panel_debug"],
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain showpiece assembled case count"]["status"] == "fail"
    assert labels["brain showpiece unassembled case count"]["status"] == "fail"
    assert labels["brain showpiece unreadable case count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_validation_strength_regresses():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["validation_metrics"] = {
        "ok": False,
        "case_count": 50,
        "min_validation_check_count": 5,
        "weak_validation_case_count": 1,
        "missing_validation_expectation_count": 1,
        "weak_validation_case_ids": ["audio_feedback_panel_debug"],
        "missing_validation_expectation_case_ids": ["audio_feedback_panel_debug"],
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain validation metrics minimum check count"]["status"] == "fail"
    assert labels["brain validation metrics weak case count"]["status"] == "fail"
    assert labels["brain validation metrics missing expectation count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_parameter_safety_regresses():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["parameter_safety_metrics"] = {
        "ok": False,
        "covered_operator_count": 39,
        "priority_operator_count": 39,
        "missing_operator_count": 1,
        "invalid_source_count": 1,
        "priority_group_count": 6,
        "priority_group_missing_operator_count": 1,
        "priority_groups": ["audio_control"],
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain parameter safety covered operator count"]["status"] == "fail"
    assert labels["brain parameter safety priority operator count"]["status"] == "fail"
    assert labels["brain parameter safety missing operator count"]["status"] == "fail"
    assert labels["brain parameter safety invalid source count"]["status"] == "fail"
    assert labels["brain parameter safety priority group count"]["status"] == "fail"
    assert labels["brain parameter safety priority group missing operator count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_generated_code_success_regresses():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["generated_code_success_metrics"] = {
        "ok": False,
        "generated_code_case_count": 11,
        "generated_code_block_count": 11,
        "language_count": 1,
        "languages": ["glsl"],
        "static_issue_count": 1,
        "runtime_contract_count": 11,
        "runtime_contract_missing_count": 1,
        "runtime_check_count": 2,
        "runtime_checks": ["compile_state"],
        "generated_code_case_ids": [],
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain generated code success case count"]["status"] == "fail"
    assert labels["brain generated code success block count"]["status"] == "fail"
    assert labels["brain generated code success language coverage"]["status"] == "fail"
    assert labels["brain generated code success static issue count"]["status"] == "fail"
    assert labels["brain generated code success runtime contract count"]["status"] == "fail"
    assert labels["brain generated code success missing runtime contract count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_time_to_first_green_regresses():
    brain_eval = {
        "ok": False,
        "failed": 0,
        "pattern_coverage": {"ok": True, "missing_patterns": [], "stale_pattern_references": []},
        "compiler_stability": {
            "ok": True,
            "compiled_case_count": 31,
            "passed_compiled_case_count": 31,
            "blocked_compiled_case_count": 0,
            "compiled_domain_failure_count": 0,
            "pattern_composition_failure_count": 0,
        },
        "readability_metrics": {
            "assembled_case_count": 31,
            "fully_readable_assembled_case_count": 31,
            "avg_assembled_score": 5.0,
            "avg_assembled_max_score": 5.0,
        },
        "time_metrics": {
            "time_to_first_green_cycles": {"min": 1, "max": 2, "avg": 1.25},
        },
        "trace_replay": {"ok": True, "drift_count": 0},
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain time to first green max cycles"]["status"] == "fail"
    assert labels["brain time to first green average cycles"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_has_missing_param_semantics_coverage():
    brain_eval = {
        "ok": True,
        "failed": 0,
        "pattern_coverage": {"ok": True, "missing_patterns": [], "stale_pattern_references": []},
        "compiler_stability": {
            "ok": True,
            "compiled_case_count": 1,
            "passed_compiled_case_count": 1,
            "blocked_compiled_case_count": 0,
            "compiled_domain_failure_count": 0,
            "pattern_composition_failure_count": 0,
        },
        "readability_metrics": {
            "assembled_case_count": 1,
            "fully_readable_assembled_case_count": 1,
        },
        "assembly_control_bindings": {
            "ok": True,
            "missing_count": 0,
            "missing": [],
        },
        "param_semantics_coverage": {
            "ok": False,
            "missing_operator_count": 1,
            "invalid_source_count": 0,
            "priority_groups": {
                "feedback_top_processing": {
                    "missing_operators": ["feedbackTOP"],
                }
            },
        },
        "trace_replay": {"ok": True, "drift_count": 0},
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain param semantics missing operator count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_param_semantics_priority_bands_are_missing():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["param_semantics_coverage"]["priority_groups"] = {
        "audio_control": {
            "operator_count": 6,
            "covered_operator_count": 6,
            "missing_operators": [],
        }
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain param semantics missing priority group count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_has_missing_operator_availability_coverage():
    brain_eval = {
        "ok": True,
        "failed": 0,
        "pattern_coverage": {"ok": True, "missing_patterns": [], "stale_pattern_references": []},
        "compiler_stability": {
            "ok": True,
            "compiled_case_count": 1,
            "passed_compiled_case_count": 1,
            "blocked_compiled_case_count": 0,
            "compiled_domain_failure_count": 0,
            "pattern_composition_failure_count": 0,
        },
        "readability_metrics": {
            "assembled_case_count": 1,
            "fully_readable_assembled_case_count": 1,
        },
        "assembly_control_bindings": {
            "ok": True,
            "missing_count": 0,
            "missing": [],
        },
        "param_semantics_coverage": {
            "ok": True,
            "missing_operator_count": 0,
            "invalid_source_count": 0,
        },
        "operator_availability_coverage": {
            "ok": False,
            "missing_required_rule_count": 1,
            "invalid_source_count": 0,
            "missing_tradeoff_count": 0,
            "missing_required_rules": ["glslcreatePOP"],
        },
        "trace_replay": {"ok": True, "drift_count": 0},
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain operator availability missing substitution rule count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_lacks_structured_availability_matrix_metrics():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["availability_matrix_metrics"] = {
        "ok": False,
        "structured_case_count": 0,
        "known_build_case_count": 0,
        "missing_unavailable_reason_count": 1,
        "substitution_without_matrix_count": 1,
        "structured_case_ids": [],
        "substitution_without_matrix_case_ids": ["audio_feedback_panel_device_substitution"],
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain availability matrix structured case count"]["status"] == "fail"
    assert labels["brain availability matrix known build case count"]["status"] == "fail"
    assert labels["brain availability matrix missing reason count"]["status"] == "fail"
    assert labels["brain availability matrix substitution missing count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_operator_availability_report_gate_requires_real_sample_fields(tmp_path: Path):
    stored_path = tmp_path / "operator_availability.json"
    stored_path.write_text("{}", encoding="utf-8")
    operator_availability = _complete_operator_availability_payload(str(stored_path))

    report = check_release_gates.evaluate(
        None,
        None,
        operator_availability=operator_availability,
    )

    labels = {check["label"]: check for check in report["checks"]}
    assert labels["operator availability sample report ok"]["status"] == "pass"
    assert labels["operator availability sample target count"]["status"] == "pass"
    assert labels["operator availability sample result count"]["status"] == "pass"
    assert labels["operator availability sample td build known"]["status"] == "pass"
    assert labels["operator availability sample platform known"]["status"] == "pass"
    assert labels["operator availability sample cleanup ok"]["status"] == "pass"
    assert labels["operator availability stored artifact path"]["status"] == "pass"
    assert labels["operator availability glsl advanced pop replacement coverage"]["status"] == "pass"


def test_operator_availability_report_gate_fails_unknown_build_and_missing_advanced_pop(tmp_path: Path):
    stored_path = tmp_path / "operator_availability.json"
    stored_path.write_text("{}", encoding="utf-8")
    operator_availability = _complete_operator_availability_payload(str(stored_path))
    operator_availability["availability_matrix"]["td_build"] = "unknown"
    operator_availability["availability_matrix"]["platform"] = "unknown"
    operator_availability["results"] = [
        item for item in operator_availability["results"] if item["op_type"] != "glsladvancedPOP"
    ]

    report = check_release_gates.evaluate(
        None,
        None,
        operator_availability=operator_availability,
    )

    labels = {check["label"]: check for check in report["checks"]}
    assert labels["operator availability sample td build known"]["status"] == "fail"
    assert labels["operator availability sample platform known"]["status"] == "fail"
    assert labels["operator availability glsl advanced pop replacement coverage"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_has_missing_validation_probe_coverage():
    brain_eval = {
        "ok": True,
        "failed": 0,
        "pattern_coverage": {"ok": True, "missing_patterns": [], "stale_pattern_references": []},
        "compiler_stability": {
            "ok": True,
            "compiled_case_count": 1,
            "passed_compiled_case_count": 1,
            "blocked_compiled_case_count": 0,
            "compiled_domain_failure_count": 0,
            "pattern_composition_failure_count": 0,
        },
        "readability_metrics": {
            "assembled_case_count": 1,
            "fully_readable_assembled_case_count": 1,
        },
        "assembly_control_bindings": {
            "ok": True,
            "missing_count": 0,
            "missing": [],
        },
        "param_semantics_coverage": {
            "ok": True,
            "missing_operator_count": 0,
            "invalid_source_count": 0,
        },
        "operator_availability_coverage": {
            "ok": True,
            "missing_required_rule_count": 0,
            "invalid_source_count": 0,
            "missing_tradeoff_count": 0,
        },
        "validation_probe_coverage": {
            "ok": False,
            "missing_required_profile_count": 1,
            "invalid_source_count": 0,
            "uncontrolled_expensive_probe_count": 0,
            "missing_required_profiles": ["glsl"],
        },
        "trace_replay": {"ok": True, "drift_count": 0},
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain validation probe missing profile count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_eval_has_missing_generated_code_harness_coverage():
    brain_eval = {
        "ok": True,
        "failed": 0,
        "pattern_coverage": {"ok": True, "missing_patterns": [], "stale_pattern_references": []},
        "compiler_stability": {
            "ok": True,
            "compiled_case_count": 1,
            "passed_compiled_case_count": 1,
            "blocked_compiled_case_count": 0,
            "compiled_domain_failure_count": 0,
            "pattern_composition_failure_count": 0,
        },
        "readability_metrics": {
            "assembled_case_count": 1,
            "fully_readable_assembled_case_count": 1,
        },
        "assembly_control_bindings": {
            "ok": True,
            "missing_count": 0,
            "missing": [],
        },
        "param_semantics_coverage": {
            "ok": True,
            "missing_operator_count": 0,
            "invalid_source_count": 0,
        },
        "operator_availability_coverage": {
            "ok": True,
            "missing_required_rule_count": 0,
            "invalid_source_count": 0,
            "missing_tradeoff_count": 0,
        },
        "validation_probe_coverage": {
            "ok": True,
            "missing_required_profile_count": 0,
            "invalid_source_count": 0,
            "uncontrolled_expensive_probe_count": 0,
        },
        "generated_code_harness_coverage": {
            "ok": False,
            "missing_language_count": 0,
            "missing_static_check_count": 1,
            "missing_runtime_check_count": 0,
            "invalid_source_count": 0,
            "missing_static_checks": ["glsl_pop_bounds_guard"],
        },
        "trace_replay": {"ok": True, "drift_count": 0},
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain generated code harness missing static check count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_trace_promotion_has_blockers():
    brain_eval = {
        "ok": False,
        "case_count": 50,
        "passed": 50,
        "failed": 0,
        "pattern_coverage": {"ok": True, "missing_patterns": [], "stale_pattern_references": []},
        "compiler_stability": {
            "ok": True,
            "compiled_case_count": 31,
            "passed_compiled_case_count": 31,
            "blocked_compiled_case_count": 0,
            "compiled_domain_failure_count": 0,
            "pattern_composition_failure_count": 0,
        },
        "readability_metrics": {
            "assembled_case_count": 31,
            "fully_readable_assembled_case_count": 31,
        },
        "trace_promotion_coverage": {
            "ok": False,
            "eligible_trace_fixture_count": 1,
            "promoted_fixture_count": 0,
            "blocked_fixture_count": 1,
            "invalid_source_count": 0,
            "blocked_fixtures": [
                {
                    "case_id": "audio_feedback_panel_debug",
                    "blockers": ["missing official Derivative docs grounding"],
                }
            ],
        },
        "trace_replay": {"ok": True, "drift_count": 0},
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain trace promotion blocked fixture count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_trace_promotion_lacks_generated_code_fixture():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["trace_promotion_coverage"] = {
        "ok": True,
        "eligible_trace_fixture_count": 1,
        "promoted_fixture_count": 1,
        "blocked_fixture_count": 0,
        "invalid_source_count": 0,
        "promoted_case_ids": ["audio_feedback_panel_debug"],
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain trace promotion eligible fixture count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_trace_memory_reuse_regresses():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["trace_memory_reuse_coverage"] = {
        "ok": False,
        "fixture_count": 2,
        "loaded_pattern_count": 1,
        "reused_fixture_count": 1,
        "miss_count": 1,
        "reused_case_ids": ["audio_feedback_panel_debug"],
        "missed_fixtures": [{"case_id": "glsl_top_shader_compiled"}],
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain trace memory reuse fixture count"]["status"] == "pass"
    assert labels["brain trace memory reuse loaded pattern count"]["status"] == "fail"
    assert labels["brain trace memory reuse reused fixture count"]["status"] == "fail"
    assert labels["brain trace memory reuse miss count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_passes_with_valid_brain_smoke_payload():
    brain_smoke = {
        "ok": True,
        "mode": "dry_run",
        "mutated_td": False,
        "scenario_count": 16,
        "generated_code_summary": {
            "block_count": 7,
            "languages": ["glsl", "python"],
            "runtime_checks": ["callback_guard_present", "compile_state", "topology_capacity"],
            "runtime_contract_count": 9,
            "runtime_contract_checks": ["callback_guard_present", "compile_state", "topology_capacity"],
            "risk_flags": ["validate-glsl-compile-state"],
            "source_payloads_included": False,
        },
        "scenarios": [
            {
                "id": "feedback_loop",
                "status": "planned",
                "missing_expected_ops": [],
                "blocked_questions": [],
                "profile_probes": [{"probe_id": "feedback_cycle"}],
                "profile_probe_results": [{"probe_id": "feedback_cycle", "status": "static_pass"}],
            },
            {
                "id": "audio_reactive_top",
                "status": "planned",
                "missing_expected_ops": [],
                "blocked_questions": [],
                "profile_probes": [{"probe_id": "audio_signal_activity"}],
                "profile_probe_results": [
                    {"probe_id": "audio_signal_activity", "status": "runtime_contract_present"}
                ],
            },
            {
                "id": "glsl_shader_top",
                "status": "planned",
                "missing_expected_ops": [],
                "blocked_questions": [],
                "profile_probes": [{"probe_id": "shader_source_present"}],
                "profile_probe_results": [{"probe_id": "shader_source_present", "status": "static_pass"}],
            },
            {
                "id": "render_pipeline_expensive_validation",
                "status": "planned",
                "validation_profile": "structural_visual_expensive",
                "missing_expected_ops": [],
                "blocked_questions": [],
                "profile_probes": [{"probe_id": "render_top_output", "cost_level": "expensive"}],
                "profile_probe_results": [
                    {"probe_id": "render_top_output", "status": "runtime_contract_present"}
                ],
            },
        ],
    }

    report = check_release_gates.evaluate(None, None, None, brain_smoke=brain_smoke)

    assert report["summary"]["ok"] is True
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain smoke failed scenarios"]["status"] == "pass"
    assert labels["brain smoke mutated td"]["status"] == "pass"
    assert labels["brain smoke generated code block count"]["status"] == "pass"
    assert labels["brain smoke generated code runtime contract count"]["status"] == "pass"
    assert labels["brain smoke generated code source payload leak"]["status"] == "pass"
    assert labels["brain smoke expensive probe opt-in scenario count"]["status"] == "pass"
    assert labels["brain smoke uncontrolled expensive probe count"]["status"] == "pass"


def test_evaluate_fails_when_brain_smoke_lacks_explicit_expensive_probe_opt_in():
    brain_smoke = {
        "ok": True,
        "mode": "dry_run",
        "mutated_td": False,
        "scenario_count": 1,
        "generated_code_summary": {
            "block_count": 1,
            "languages": ["glsl", "python"],
            "runtime_contract_count": 1,
            "runtime_contract_checks": [
                "callback_guard_present",
                "compile_state",
                "topology_capacity",
            ],
            "source_payloads_included": False,
        },
        "scenarios": [
            {
                "id": "render_pipeline",
                "status": "planned",
                "validation_profile": "structural_visual_safe",
                "missing_expected_ops": [],
                "blocked_questions": [],
                "profile_probes": [{"probe_id": "camera_present"}],
                "profile_probe_results": [{"probe_id": "camera_present", "status": "static_pass"}],
            }
        ],
    }

    report = check_release_gates.evaluate(None, None, None, brain_smoke=brain_smoke)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain smoke expensive probe opt-in scenario count"]["status"] == "fail"
    assert labels["brain smoke uncontrolled expensive probe count"]["status"] == "pass"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_smoke_has_uncontrolled_expensive_probe():
    brain_smoke = {
        "ok": True,
        "mode": "dry_run",
        "mutated_td": False,
        "scenario_count": 1,
        "generated_code_summary": {
            "block_count": 1,
            "languages": ["glsl", "python"],
            "runtime_contract_count": 1,
            "runtime_contract_checks": [
                "callback_guard_present",
                "compile_state",
                "topology_capacity",
            ],
            "source_payloads_included": False,
        },
        "scenarios": [
            {
                "id": "render_pipeline",
                "status": "planned",
                "validation_profile": "structural_visual_safe",
                "missing_expected_ops": [],
                "blocked_questions": [],
                "profile_probes": [{"probe_id": "render_top_output", "cost_level": "expensive"}],
                "profile_probe_results": [
                    {"probe_id": "render_top_output", "status": "runtime_contract_present"}
                ],
            }
        ],
    }

    report = check_release_gates.evaluate(None, None, None, brain_smoke=brain_smoke)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain smoke expensive probe opt-in scenario count"]["status"] == "fail"
    assert labels["brain smoke uncontrolled expensive probe count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_smoke_missing_topology_runtime_contract():
    brain_smoke = {
        "ok": True,
        "mode": "dry_run",
        "mutated_td": False,
        "scenario_count": 16,
        "generated_code_summary": {
            "block_count": 7,
            "languages": ["glsl", "python"],
            "runtime_checks": ["callback_guard_present", "compile_state"],
            "runtime_contract_count": 9,
            "runtime_contract_checks": ["callback_guard_present", "compile_state"],
            "risk_flags": ["validate-glsl-compile-state"],
            "source_payloads_included": False,
        },
        "scenarios": [
            {
                "id": "glsl_shader_top",
                "status": "planned",
                "missing_expected_ops": [],
                "blocked_questions": [],
                "profile_probes": [{"probe_id": "shader_source_present"}],
                "profile_probe_results": [{"probe_id": "shader_source_present", "status": "static_pass"}],
            }
        ],
    }

    report = check_release_gates.evaluate(None, None, None, brain_smoke=brain_smoke)

    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain smoke generated code runtime contract coverage"]["status"] == "fail"


def test_evaluate_passes_with_valid_brain_live_smoke_payload():
    brain_live_smoke = _complete_brain_live_smoke_payload()

    report = check_release_gates.evaluate(
        None,
        None,
        None,
        brain_live_smoke=brain_live_smoke,
    )

    assert report["summary"]["ok"] is True
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain live smoke report ok"]["status"] == "pass"
    assert labels["brain live smoke td health ok"]["status"] == "pass"
    assert labels["brain live smoke sync diagnostic ok"]["status"] == "pass"
    assert labels["brain live smoke visual quality checked"]["status"] == "pass"
    assert labels["brain live smoke visual quality failures"]["status"] == "pass"
    assert labels["brain live smoke panel interactions ok"]["status"] == "pass"
    assert labels["brain live smoke performance ok"]["status"] == "pass"
    assert labels["brain live smoke steady-state frame budget"]["status"] == "pass"
    assert labels["brain live smoke incident replay ok"]["status"] == "pass"
    assert labels["brain live smoke incident replay bug count"]["status"] == "pass"
    assert labels["brain live smoke unexpected scenario count"]["status"] == "pass"
    assert labels["brain live smoke missing profile probe evidence"]["status"] == "pass"
    assert labels["brain live smoke invalid profile probe results"]["status"] == "pass"
    assert labels["brain live smoke expensive probe opt-in scenario count"]["status"] == "pass"
    assert labels["brain live smoke uncontrolled expensive probe count"]["status"] == "pass"
    assert labels["brain live smoke mutated td"]["status"] == "pass"
    assert labels["brain live smoke glsl advanced pop topology scenario"]["status"] == "pass"
    assert labels["brain live smoke generated code block count"]["status"] == "pass"
    assert labels["brain live smoke generated code language coverage"]["status"] == "pass"
    assert labels["brain live smoke generated code runtime contract count"]["status"] == "pass"
    assert labels["brain live smoke generated code runtime contract coverage"]["status"] == "pass"
    assert labels["brain live smoke generated code source payload leak"]["status"] == "pass"
    assert labels["brain live smoke transactional generated code ok"]["status"] == "pass"
    assert labels["brain live smoke transactional generated code cleanup ok"]["status"] == "pass"


def test_evaluate_fails_when_brain_live_smoke_lacks_real_world_evidence():
    brain_live_smoke = _complete_brain_live_smoke_payload()
    brain_live_smoke.pop("sync_diagnostic")
    brain_live_smoke.pop("visual_quality_summary")
    brain_live_smoke.pop("panel_interaction_results")
    brain_live_smoke.pop("performance_summary")
    brain_live_smoke.pop("incident_replay")

    report = check_release_gates.evaluate(
        None,
        None,
        None,
        brain_live_smoke=brain_live_smoke,
    )

    labels = {check["label"]: check for check in report["checks"]}
    assert report["summary"]["ok"] is False
    assert labels["brain live smoke sync diagnostic ok"]["status"] == "fail"
    assert labels["brain live smoke visual quality checked"]["status"] == "missing"
    assert labels["brain live smoke panel interactions ok"]["status"] == "fail"
    assert labels["brain live smoke performance ok"]["status"] == "fail"
    assert labels["brain live smoke incident replay ok"]["status"] == "fail"


def test_evaluate_fails_when_brain_live_smoke_visual_or_panel_evidence_fails():
    brain_live_smoke = _complete_brain_live_smoke_payload()
    brain_live_smoke["visual_quality_summary"] = {"checked_count": 2, "failed_count": 1, "missing_count": 0}
    brain_live_smoke["panel_interaction_results"] = {"ok": False, "checked_count": 5, "failed_count": 1}
    brain_live_smoke["performance_summary"] = {
        "ok": False,
        "steady_state_max_ms": 20.0,
        "frame_budget_ms": 16.667,
        "safety_target_ms": 12.0,
        "warmup_spike_recorded": True,
    }
    brain_live_smoke["incident_replay"] = {"ok": False, "bug_count": 45, "untriaged": ["BUG-040"]}

    report = check_release_gates.evaluate(
        None,
        None,
        None,
        brain_live_smoke=brain_live_smoke,
    )

    labels = {check["label"]: check for check in report["checks"]}
    assert report["summary"]["ok"] is False
    assert labels["brain live smoke visual quality failures"]["status"] == "fail"
    assert labels["brain live smoke panel interactions ok"]["status"] == "fail"
    assert labels["brain live smoke performance ok"]["status"] == "fail"
    assert labels["brain live smoke steady-state frame budget"]["status"] == "fail"
    assert labels["brain live smoke incident replay ok"]["status"] == "fail"


def test_evaluate_fails_when_brain_live_smoke_cannot_reach_td():
    brain_live_smoke = {
        "ok": False,
        "mode": "live",
        "mutated_td": False,
        "connection_error": "connection refused",
        "td_health": None,
        "scenario_count": 0,
        "scenarios": [],
    }

    report = check_release_gates.evaluate(
        None,
        None,
        None,
        brain_live_smoke=brain_live_smoke,
    )

    assert report["summary"]["ok"] is False
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain live smoke report ok"]["status"] == "fail"
    assert labels["brain live smoke connection error"]["status"] == "fail"
    assert labels["brain live smoke td health ok"]["status"] == "missing"


def test_evaluate_fails_when_brain_live_smoke_has_no_generated_code_path():
    brain_live_smoke = {
        "ok": True,
        "mode": "live",
        "mutated_td": False,
        "connection_error": None,
        "td_health": {"status": "ok", "api_version": "2.0.0"},
        "scenario_count": 2,
        "generated_code_summary": {
            "block_count": 0,
            "languages": [],
            "runtime_contract_count": 0,
            "runtime_contract_checks": [],
            "source_payloads_included": False,
        },
        "scenarios": [
            {"id": "feedback_loop", "status": "planned", "blocked_questions": []},
            {"id": "glsl_shader_top", "status": "planned", "blocked_questions": []},
        ],
    }

    report = check_release_gates.evaluate(
        None,
        None,
        None,
        brain_live_smoke=brain_live_smoke,
    )

    assert report["summary"]["ok"] is False
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain live smoke generated code block count"]["status"] == "fail"
    assert labels["brain live smoke generated code language coverage"]["status"] == "fail"
    assert labels["brain live smoke generated code runtime contract coverage"]["status"] == "fail"


def test_live_gate_requires_glsl_advanced_pop_topology_scenario():
    brain_live_smoke = _complete_brain_live_smoke_payload()
    brain_live_smoke["scenarios"] = [
        scenario
        for scenario in brain_live_smoke["scenarios"]
        if scenario.get("id") != "glsl_advanced_pop_topology"
    ]

    report = check_release_gates.evaluate(
        None,
        None,
        None,
        brain_live_smoke=brain_live_smoke,
    )

    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain live smoke glsl advanced pop topology scenario"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_live_gate_requires_topology_capacity_runtime_contract():
    brain_live_smoke = _complete_brain_live_smoke_payload()
    brain_live_smoke["generated_code_summary"]["runtime_contract_checks"] = [
        "callback_guard_present",
        "compile_state",
    ]

    report = check_release_gates.evaluate(
        None,
        None,
        None,
        brain_live_smoke=brain_live_smoke,
    )

    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain live smoke generated code runtime contract coverage"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_live_gate_requires_transactional_generated_code_smoke():
    brain_live_smoke = _complete_brain_live_smoke_payload()
    brain_live_smoke["transactional_generated_code_smoke"] = {"status": "not_run"}

    report = check_release_gates.evaluate(
        None,
        None,
        None,
        brain_live_smoke=brain_live_smoke,
    )

    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain live smoke transactional generated code ok"]["status"] == "fail"
    assert labels["brain live smoke transactional generated code cleanup ok"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_live_smoke_missing_profile_probe_evidence():
    brain_live_smoke = {
        "ok": True,
        "mode": "live",
        "mutated_td": False,
        "connection_error": None,
        "td_health": {"status": "ok", "api_version": "2.0.0"},
        "scenario_count": 2,
        "generated_code_summary": {
            "block_count": 2,
            "languages": ["glsl", "python"],
            "runtime_contract_count": 2,
            "runtime_contract_checks": ["callback_guard_present", "compile_state"],
            "source_payloads_included": False,
        },
        "scenarios": [
            {
                "id": "feedback_loop",
                "status": "planned",
                "blocked_questions": [],
                "profile_probes": [],
                "profile_probe_results": [],
            },
            {
                "id": "serial_dat_protocol_bridge",
                "status": "skipped_unavailable",
                "blocked_questions": [],
            },
        ],
    }

    report = check_release_gates.evaluate(
        None,
        None,
        None,
        brain_live_smoke=brain_live_smoke,
    )

    assert report["summary"]["ok"] is False
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain live smoke missing profile probe evidence"]["status"] == "fail"


def test_evaluate_fails_when_brain_live_smoke_has_invalid_profile_probe_result_status():
    brain_live_smoke = {
        "ok": True,
        "mode": "live",
        "mutated_td": False,
        "connection_error": None,
        "td_health": {"status": "ok", "api_version": "2.0.0"},
        "scenario_count": 1,
        "generated_code_summary": {
            "block_count": 2,
            "languages": ["glsl", "python"],
            "runtime_contract_count": 2,
            "runtime_contract_checks": ["callback_guard_present", "compile_state"],
            "source_payloads_included": False,
        },
        "scenarios": [
            {
                "id": "glsl_shader_top",
                "status": "planned",
                "blocked_questions": [],
                "profile_probes": [{"probe_id": "compile_state"}],
                "profile_probe_results": [{"probe_id": "compile_state", "status": "runtime_failed"}],
            }
        ],
    }

    report = check_release_gates.evaluate(
        None,
        None,
        None,
        brain_live_smoke=brain_live_smoke,
    )

    assert report["summary"]["ok"] is False
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain live smoke invalid profile probe results"]["status"] == "fail"


def test_evaluate_fails_when_brain_live_smoke_has_uncontrolled_expensive_probe():
    brain_live_smoke = {
        "ok": True,
        "mode": "live",
        "mutated_td": False,
        "connection_error": None,
        "td_health": {"status": "ok", "api_version": "2.0.0"},
        "scenario_count": 1,
        "generated_code_summary": {
            "block_count": 2,
            "languages": ["glsl", "python"],
            "runtime_contract_count": 2,
            "runtime_contract_checks": ["callback_guard_present", "compile_state"],
            "source_payloads_included": False,
        },
        "scenarios": [
            {
                "id": "render_pipeline",
                "status": "planned",
                "validation_profile": "structural_visual_safe",
                "blocked_questions": [],
                "profile_probes": [{"probe_id": "render_top_output", "cost_level": "expensive"}],
                "profile_probe_results": [
                    {"probe_id": "render_top_output", "status": "runtime_contract_present"}
                ],
            }
        ],
    }

    report = check_release_gates.evaluate(
        None,
        None,
        None,
        brain_live_smoke=brain_live_smoke,
    )
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain live smoke expensive probe opt-in scenario count"]["status"] == "fail"
    assert labels["brain live smoke uncontrolled expensive probe count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_passes_with_valid_plugin_surface_payload():
    plugin_surface = {
        "ok": True,
        "tool_count": 114,
        "brain_skill_count": 7,
        "agent_count": 3,
        "hook_count": 1,
        "missing_artifacts": [],
        "mirror_mismatches": [],
        "personal_path_leaks": [],
        "local_first": {"ok": True, "hosted_llm_dependency_leaks": []},
        "mcp_config": {"uses_plugin_root_placeholder": True},
        "hooks": {
            "uses_hook_check_module": True,
            "uses_hook_runner": True,
            "has_post_tool_use_guard": True,
            "has_stop_release_guard": True,
            "shipped_stop_hook": False,
            "post_tool_use_scoped": True,
            "uses_project_runtime_fallback": False,
            "source_release_guard": True,
            "stop_hook_reentry_guard": True,
            "safe_for_distribution": True,
        },
        "codex_manifest": {"has_skills": True, "has_agents": True, "has_mcp_servers": True},
        "claude_manifest": {
            "has_skills": True,
            "has_agents": True,
            "has_hooks": True,
            "has_mcp_servers": True,
        },
    }

    report = check_release_gates.evaluate(None, None, None, brain_smoke=None, plugin_surface=plugin_surface)

    assert report["summary"]["ok"] is True
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["plugin surface report ok"]["status"] == "pass"
    assert labels["plugin surface missing artifact count"]["status"] == "pass"
    assert labels["plugin surface mirror mismatch count"]["status"] == "pass"
    assert labels["plugin surface hosted llm dependency leak count"]["status"] == "pass"
    assert labels["plugin surface hook runner"]["status"] == "pass"
    assert labels["plugin surface no shipped stop hook"]["status"] == "pass"
    assert labels["plugin surface scoped post tool matcher"]["status"] == "pass"
    assert labels["plugin surface trusted runtime roots"]["status"] == "pass"
    assert labels["plugin surface stop hook re-entry guard"]["status"] == "pass"
    assert labels["plugin surface mcp placeholder"]["status"] == "pass"


def test_evaluate_fails_when_plugin_surface_ships_stop_hook():
    plugin_surface = _complete_plugin_surface_payload()
    plugin_surface["ok"] = False
    plugin_surface["hooks"]["shipped_stop_hook"] = True
    plugin_surface["hooks"]["safe_for_distribution"] = False

    report = check_release_gates.evaluate(
        None,
        None,
        None,
        brain_smoke=None,
        plugin_surface=plugin_surface,
    )

    assert report["summary"]["ok"] is False
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["plugin surface no shipped stop hook"]["status"] == "fail"
    assert labels["plugin surface hook safety"]["status"] == "fail"


def test_evaluate_fails_when_plugin_surface_has_hosted_llm_dependency_leaks():
    plugin_surface = _complete_plugin_surface_payload()
    plugin_surface["ok"] = False
    plugin_surface["local_first"] = {
        "ok": False,
        "hosted_llm_dependency_leaks": ["pyproject.toml dependency openai"],
    }

    report = check_release_gates.evaluate(None, None, None, brain_smoke=None, plugin_surface=plugin_surface)

    assert report["summary"]["ok"] is False
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["plugin surface hosted llm dependency leak count"]["status"] == "fail"


def test_evaluate_fails_when_plugin_surface_packaging_is_incomplete():
    plugin_surface = {
        "ok": False,
        "tool_count": 112,
        "brain_skill_count": 5,
        "agent_count": 4,
        "hook_count": 2,
        "missing_artifacts": ["plugins/tdpilot/hooks/hooks.json"],
        "mirror_mismatches": ["plugins/tdpilot/skills/tdpilot-brain-builder/SKILL.md differs"],
        "personal_path_leaks": [],
        "local_first": {"ok": True, "hosted_llm_dependency_leaks": []},
        "mcp_config": {"uses_plugin_root_placeholder": False},
        "hooks": {
            "uses_hook_check_module": True,
            "uses_hook_runner": True,
            "has_post_tool_use_guard": True,
            "has_stop_release_guard": True,
            "shipped_stop_hook": False,
            "post_tool_use_scoped": True,
            "uses_project_runtime_fallback": False,
            "source_release_guard": True,
            "stop_hook_reentry_guard": True,
            "safe_for_distribution": True,
        },
        "codex_manifest": {"has_skills": True, "has_agents": True, "has_mcp_servers": True},
        "claude_manifest": {
            "has_skills": True,
            "has_agents": True,
            "has_hooks": True,
            "has_mcp_servers": True,
        },
    }

    report = check_release_gates.evaluate(None, None, None, brain_smoke=None, plugin_surface=plugin_surface)

    assert report["summary"]["ok"] is False
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["plugin surface missing artifact count"]["status"] == "fail"
    assert labels["plugin surface mirror mismatch count"]["status"] == "fail"
    assert labels["plugin surface mcp placeholder"]["status"] == "fail"


def test_plugin_surface_counts_are_exact_not_minimums():
    plugin_surface = _complete_plugin_surface_payload()
    plugin_surface["tool_count"] = 115
    plugin_surface["brain_skill_count"] = 8
    plugin_surface["agent_count"] = 4

    report = check_release_gates.evaluate(None, None, plugin_surface=plugin_surface)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["plugin surface tool count"]["status"] == "fail"
    assert labels["plugin surface brain skill count"]["status"] == "fail"
    assert labels["plugin surface agent count"]["status"] == "fail"


def test_required_report_identity_rejects_stale_version_tool_count_and_timestamp():
    plugin_surface = _complete_plugin_surface_payload()
    plugin_surface.update(
        {
            "version": "1.0.0",
            "tool_count": 110,
            "generated_at": "2020-01-01T00:00:00+00:00",
        }
    )

    report = check_release_gates.evaluate(
        None,
        None,
        plugin_surface=plugin_surface,
        required_reports={"plugin_surface"},
    )
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["plugin_surface candidate version"]["status"] == "fail"
    assert labels["plugin_surface candidate tool count"]["status"] == "fail"
    assert labels["plugin_surface generated timestamp"]["status"] == "pass"
    assert labels["plugin_surface report age hours"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_brain_smoke_missing_profile_probe_evidence():
    brain_smoke = {
        "ok": True,
        "mode": "dry_run",
        "mutated_td": False,
        "scenario_count": 16,
        "generated_code_summary": {
            "block_count": 7,
            "languages": ["glsl", "python"],
            "runtime_checks": ["callback_guard_present", "compile_state"],
            "risk_flags": ["validate-glsl-compile-state"],
            "source_payloads_included": False,
        },
        "scenarios": [
            {
                "id": "feedback_loop",
                "status": "planned",
                "missing_expected_ops": [],
                "blocked_questions": [],
                "profile_probes": [],
                "profile_probe_results": [],
            },
        ],
    }

    report = check_release_gates.evaluate(None, None, None, brain_smoke=brain_smoke)

    assert report["summary"]["ok"] is False
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain smoke missing profile probe evidence"]["status"] == "fail"


def test_evaluate_fails_when_brain_smoke_has_invalid_profile_probe_result_status():
    brain_smoke = {
        "ok": True,
        "mode": "dry_run",
        "mutated_td": False,
        "scenario_count": 16,
        "generated_code_summary": {
            "block_count": 7,
            "languages": ["glsl", "python"],
            "runtime_checks": ["callback_guard_present", "compile_state"],
            "risk_flags": ["validate-glsl-compile-state"],
            "source_payloads_included": False,
        },
        "scenarios": [
            {
                "id": "feedback_loop",
                "status": "planned",
                "missing_expected_ops": [],
                "blocked_questions": [],
                "profile_probes": [{"probe_id": "feedback_cycle"}],
                "profile_probe_results": [{"probe_id": "feedback_cycle", "status": "runtime_failed"}],
            },
        ],
    }

    report = check_release_gates.evaluate(None, None, None, brain_smoke=brain_smoke)

    assert report["summary"]["ok"] is False
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain smoke invalid profile probe results"]["status"] == "fail"


def test_evaluate_fails_when_brain_smoke_missing_generated_code_language_coverage():
    brain_smoke = {
        "ok": True,
        "mode": "dry_run",
        "mutated_td": False,
        "scenario_count": 16,
        "generated_code_summary": {
            "block_count": 3,
            "languages": ["glsl"],
            "runtime_checks": ["compile_state"],
            "risk_flags": ["validate-glsl-compile-state"],
            "source_payloads_included": False,
        },
        "scenarios": [
            {
                "id": "glsl_shader_top",
                "status": "planned",
                "missing_expected_ops": [],
                "blocked_questions": [],
            },
        ],
    }

    report = check_release_gates.evaluate(None, None, None, brain_smoke=brain_smoke)

    assert report["summary"]["ok"] is False
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain smoke generated code language coverage"]["status"] == "fail"


def test_evaluate_fails_when_brain_smoke_generated_code_runtime_contracts_disappear():
    brain_smoke = {
        "ok": True,
        "mode": "dry_run",
        "mutated_td": False,
        "scenario_count": 16,
        "generated_code_summary": {
            "block_count": 7,
            "languages": ["glsl", "python"],
            "runtime_checks": ["callback_guard_present", "compile_state"],
            "runtime_contract_count": 0,
            "runtime_contract_checks": [],
            "risk_flags": ["validate-glsl-compile-state"],
            "source_payloads_included": False,
        },
        "scenarios": [
            {
                "id": "glsl_shader_top",
                "status": "planned",
                "missing_expected_ops": [],
                "blocked_questions": [],
                "profile_probes": [{"probe_id": "compile_state"}],
                "profile_probe_results": [{"probe_id": "compile_state", "status": "static_pass"}],
            },
        ],
    }

    report = check_release_gates.evaluate(None, None, None, brain_smoke=brain_smoke)

    assert report["summary"]["ok"] is False
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain smoke generated code runtime contract count"]["status"] == "fail"
    assert labels["brain smoke generated code runtime contract coverage"]["status"] == "fail"


def test_evaluate_fails_when_brain_trace_replay_drifts():
    brain_eval = {
        "ok": False,
        "case_count": 50,
        "passed": 50,
        "failed": 0,
        "pattern_coverage": {"ok": True, "missing_patterns": [], "stale_pattern_references": []},
        "readability_metrics": {
            "assembled_case_count": 31,
            "fully_readable_assembled_case_count": 31,
        },
        "trace_replay": {
            "ok": False,
            "baseline_case_count": 50,
            "case_count": 50,
            "drift_count": 1,
            "drifts": [{"case_id": "audio_feedback_panel_debug"}],
        },
    }

    report = check_release_gates.evaluate(None, None, brain_eval)

    assert report["summary"]["ok"] is False
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain trace replay drift count"]["status"] == "fail"
    assert labels["brain trace replay drift count"]["value"] == 1.0


def test_evaluate_fails_when_brain_compiler_stability_regresses():
    brain_eval = {
        "ok": False,
        "case_count": 50,
        "passed": 50,
        "failed": 0,
        "pattern_coverage": {"ok": True, "missing_patterns": [], "stale_pattern_references": []},
        "compiler_stability": {
            "ok": False,
            "compiled_case_count": 31,
            "passed_compiled_case_count": 29,
            "blocked_compiled_case_count": 1,
            "compiled_domain_failure_count": 1,
            "pattern_composition_failure_count": 0,
        },
        "readability_metrics": {
            "assembled_case_count": 31,
            "fully_readable_assembled_case_count": 31,
        },
        "trace_replay": {
            "ok": True,
            "baseline_case_count": 50,
            "case_count": 50,
            "drift_count": 0,
            "drifts": [],
        },
    }

    report = check_release_gates.evaluate(None, None, brain_eval)

    assert report["summary"]["ok"] is False
    labels = {check["label"]: check for check in report["checks"]}
    assert labels["brain compiler stability failed cases"]["status"] == "fail"
    assert labels["brain compiler stability blocked cases"]["status"] == "fail"
    assert labels["brain compiler stability domain failures"]["status"] == "fail"


def test_evaluate_fails_when_brain_pattern_coverage_has_unofficial_sources():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["pattern_coverage"] = {
        "ok": False,
        "pattern_count": 18,
        "covered_pattern_count": 18,
        "source_checked_pattern_count": 17,
        "invalid_source_count": 1,
        "invalid_sources": [
            {
                "pattern_id": "unsafe_pattern",
                "official_source": "https://example.com/not-derivative",
            }
        ],
        "missing_patterns": [],
        "stale_pattern_references": [],
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain pattern coverage official source checked count"]["status"] == "fail"
    assert labels["brain pattern coverage invalid source count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_fails_when_delivery_phase_coverage_regresses():
    brain_eval = _complete_brain_eval_payload()
    brain_eval["delivery_phase_coverage"] = {
        "schema_version": 1,
        "ok": False,
        "scope": "brain_eval_phased_delivery_mvp",
        "phase_count": 4,
        "complete_phase_count": 3,
        "incomplete_phase_count": 1,
        "phases": [
            {"phase_id": "phase_1", "ok": True, "missing": []},
            {"phase_id": "phase_2", "ok": True, "missing": []},
            {"phase_id": "phase_3", "ok": True, "missing": []},
            {"phase_id": "phase_4", "ok": False, "missing": ["broad eval corpus"]},
        ],
    }

    report = check_release_gates.evaluate(None, None, brain_eval)
    labels = {check["label"]: check for check in report["checks"]}

    assert labels["brain delivery phase coverage complete phase count"]["status"] == "fail"
    assert labels["brain delivery phase coverage incomplete phase count"]["status"] == "fail"
    assert report["summary"]["ok"] is False


def test_evaluate_reports_release_readiness_for_complete_master_plan_payloads(tmp_path: Path):
    stored_path = tmp_path / "operator_availability.json"
    stored_path.write_text("{}", encoding="utf-8")
    report = check_release_gates.evaluate(
        None,
        None,
        brain_eval=_complete_brain_eval_payload(),
        brain_smoke=_complete_brain_smoke_payload(),
        brain_live_smoke=_complete_brain_live_smoke_payload(),
        operator_availability=_complete_operator_availability_payload(str(stored_path)),
        plugin_surface=_complete_plugin_surface_payload(),
        param_semantics_risk=_complete_param_semantics_risk_payload(),
        required_reports={
            "brain_eval",
            "brain_smoke",
            "brain_live_smoke",
            "operator_availability",
            "plugin_surface",
            "param_semantics_risk",
        },
    )

    readiness = report["release_readiness"]
    categories = {category["id"]: category for category in readiness["categories"]}

    assert readiness["ok"] is True
    assert readiness["required_category_count"] == 6
    assert readiness["missing_required_category_count"] == 0
    assert readiness["failed_category_count"] == 0
    assert categories["brain_eval"]["present"] is True
    assert categories["brain_eval"]["ok"] is True
    assert categories["brain_eval"]["evidence"]["delivery_phase_complete_count"] == 4
    assert categories["brain_smoke"]["ok"] is True
    assert categories["brain_live_smoke"]["ok"] is True
    assert categories["operator_availability"]["ok"] is True
    assert categories["plugin_surface"]["ok"] is True
    assert categories["param_semantics_risk"]["ok"] is True


def test_evaluate_release_readiness_marks_required_brain_smoke_missing():
    report = check_release_gates.evaluate(
        None,
        None,
        brain_eval=_complete_brain_eval_payload(),
        plugin_surface=_complete_plugin_surface_payload(),
        required_reports={"brain_eval", "brain_smoke", "plugin_surface"},
    )

    readiness = report["release_readiness"]
    categories = {category["id"]: category for category in readiness["categories"]}
    labels = {check["label"]: check for check in report["checks"]}

    assert readiness["ok"] is False
    assert readiness["missing_required_category_count"] == 1
    assert categories["brain_smoke"]["present"] is False
    assert categories["brain_smoke"]["required"] is True
    assert labels["brain smoke report provided"]["status"] == "missing"


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


# --- tamper-evident release-gate provenance + verification (eval-truth P1) ---


def _live_ok_report(sha: str) -> dict:
    """A minimal gate report shaped like a passing, live+mutated release run."""
    return {
        "schema_version": 1,
        "ok": True,
        "summary": {"total": 1, "passed": 1, "failed": 0, "missing": 0, "ok": True},
        "release_readiness": {
            "ok": True,
            "categories": [
                {"id": "brain_live_smoke", "present": True, "ok": True, "evidence": {"mode": "live"}},
            ],
        },
        "checks": [],
        "provenance": {
            "commit_sha": sha,
            "commit_short": sha[:12],
            "git_dirty": False,
            "generated_at": "2026-07-09T00:00:00+00:00",
        },
    }


def test_build_provenance_stamps_commit_sha():
    prov = check_release_gates.build_provenance()
    # In a git checkout the sha and dirty flag resolve; shape is always present.
    assert set(prov) == {"commit_sha", "commit_short", "git_dirty", "generated_at"}
    if prov["commit_sha"] is not None:
        assert len(prov["commit_sha"]) >= 12
        assert prov["commit_short"] == prov["commit_sha"][:12]


def test_verify_report_accepts_fresh_live_clean_report():
    result = check_release_gates.verify_report(_live_ok_report("a" * 40), expected_sha="a" * 40)
    assert result["ok"] is True
    assert all(result["conditions"].values())


def test_verify_report_rejects_stale_sha():
    result = check_release_gates.verify_report(_live_ok_report("a" * 40), expected_sha="b" * 40)
    assert result["ok"] is False
    assert result["conditions"]["fresh"] is False
    # The gate itself passed and it was live — only freshness failed.
    assert result["conditions"]["gates_ok"] is True
    assert result["conditions"]["live_mutated"] is True


def test_verify_report_rejects_dirty_tree():
    report = _live_ok_report("a" * 40)
    report["provenance"]["git_dirty"] = True
    result = check_release_gates.verify_report(report, expected_sha="a" * 40)
    assert result["ok"] is False
    assert result["conditions"]["clean_tree"] is False


def test_verify_report_rejects_non_live_smoke():
    report = _live_ok_report("a" * 40)
    report["release_readiness"]["categories"][0]["ok"] = False  # dry-run / not mutated
    result = check_release_gates.verify_report(report, expected_sha="a" * 40)
    assert result["ok"] is False
    assert result["conditions"]["live_mutated"] is False


def test_verify_report_rejects_failed_gate():
    report = _live_ok_report("a" * 40)
    report["ok"] = False
    result = check_release_gates.verify_report(report, expected_sha="a" * 40)
    assert result["ok"] is False
    assert result["conditions"]["gates_ok"] is False


def test_verify_report_rejects_missing_provenance():
    report = _live_ok_report("a" * 40)
    del report["provenance"]
    result = check_release_gates.verify_report(report, expected_sha="a" * 40)
    assert result["ok"] is False
    assert result["conditions"]["provenance"] is False
    assert result["conditions"]["fresh"] is False
