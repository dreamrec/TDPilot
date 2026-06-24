from __future__ import annotations

import pytest
from patch.conftest import FakeTDClient

from td_mcp.brain.transaction import apply_transaction
from td_mcp.brain.validators import (
    build_validation_report_v2,
    checks_for_profile,
    classify_intent_profile,
    static_profile_probe_metrics_for_plan,
    validate_reference_params_for_plan,
)
from td_mcp.models.brain import TransactionOptions
from td_mcp.models.patch import PatchOperation, PatchPlan, PatchResult, ValidationPlan, ValidationReport
from td_mcp.patch.undo_sentinel import UndoBlockSentinel


def _patch_plan(operations: list[PatchOperation], *, required_ops: list[str] | None = None) -> PatchPlan:
    return PatchPlan(
        intent="test reference params",
        target_root="/project1",
        source="operations",
        operations=operations,
        required_ops=required_ops or [],
        undo_label="test reference params",
        validation_plan=ValidationPlan(target_root="/project1"),
    )


def test_checks_for_profile_combines_structural_and_concept_checks():
    checks = checks_for_profile("structural_visual_safe", "glsl")

    assert "graph_structure" in checks
    assert "td_errors" in checks
    assert "shader_source_present" in checks
    assert "compile_state" in checks


def test_static_profile_probe_metrics_adds_default_visual_output_sample_for_null_top():
    plan = _patch_plan(
        [PatchOperation(kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"})],
        required_ops=["nullTOP"],
    )

    metrics = static_profile_probe_metrics_for_plan(
        plan,
        validation_profile="structural_visual_safe",
        concept_profile="panel_ui",
    )

    sample = next(
        item for item in metrics["profile_probe_results"] if item["probe_id"] == "visual_output_sample"
    )
    assert sample["readback_strategy"] == "top_visual_cheap_runtime"
    assert sample["status"] == "runtime_contract_present"
    assert sample["runtime_required"] is True
    assert sample["pending_metric_names"] == [
        "output_luminance",
        "output_alpha_coverage",
        "output_entropy",
    ]
    assert sample["present_required_inputs"] == ["nullTOP"]


def test_validation_report_promotes_cook_health_stuck_entries_to_stable_issues():
    patch_result = PatchResult(
        plan_id="plan-cook",
        status="warnings",
        undo_label="cook health",
        validation=ValidationReport(
            target_root="/project1",
            errors=[],
            cook_stats={
                "total_cook_ms": 42.0,
                "stuck": [{"path": "/project1/out1", "cook_time_ms": 999.0}],
            },
            ok=False,
            summary="issues present at /project1: 0 error(s)",
        ),
    )

    report = build_validation_report_v2(
        target_root="/project1",
        profile="structural_visual_safe",
        concept_profile=None,
        patch_result=patch_result,
    )

    assert report.ok is False
    assert report.severity_counts["error"] == 1
    assert report.cheap_metrics["cook_health"]["stuck_count"] == 1
    issue = report.issues[0]
    assert issue.code == "cook_health_stuck"
    assert issue.path == "/project1/out1"
    assert issue.source == "touchdesigner"
    assert "cook_health" in issue.message
    assert "999" in issue.message


@pytest.mark.asyncio
async def test_transaction_rolls_back_when_cook_health_reports_stuck_nodes():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
        ],
        required_ops=["nullTOP"],
    )
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/errors": {"issues": []},
            "cooking": {"stuck": [{"path": "/project1/out1", "cook_time_ms": 999.0}]},
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
    )

    assert result.status == "rolled_back"
    assert result.rollback_performed is True
    assert result.validation_failed is True
    assert result.validation_report is not None
    assert result.validation_report.issues[0].code == "cook_health_stuck"
    assert result.validation_report.issues[0].path == "/project1/out1"
    assert ("project/lifecycle", {"action": "undo"}) in client.calls


@pytest.mark.asyncio
async def test_transaction_report_includes_static_profile_probe_results():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "noiseTOP", "name": "noise"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "feedbackTOP", "name": "feedback"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "levelTOP", "name": "level"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "compositeTOP", "name": "composite"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
        ],
        required_ops=["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
    )
    client = FakeTDClient(
        scripted={
            "analyze_frame": {
                "path": "/project1/out1",
                "resolution": [128, 128],
                "channels": 4,
                "modes": {"luminance": {"mean": 0.2, "min": 0.0, "max": 0.6, "std": 0.05}},
            }
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="feedback",
    )

    assert result.status == "clean"
    assert result.validation_report is not None
    probe_results = result.validation_report.cheap_metrics["profile_probe_results"]
    feedback_cycle = next(item for item in probe_results if item["probe_id"] == "feedback_cycle")
    decay_control = next(item for item in probe_results if item["probe_id"] == "decay_control")
    output_readback = next(item for item in probe_results if item["probe_id"] == "feedback_output_readback")

    assert feedback_cycle["present_required_inputs"] == ["feedbackTOP", "compositeTOP"]
    assert feedback_cycle["missing_required_inputs"] == []
    assert decay_control["present_required_inputs"] == ["levelTOP"]
    assert decay_control["missing_required_inputs"] == []
    assert output_readback["status"] == "runtime_pass"


@pytest.mark.asyncio
async def test_transaction_runs_default_visual_output_sample_for_any_null_top_plan():
    plan = _patch_plan(
        [PatchOperation(kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"})],
        required_ops=["nullTOP"],
    )
    client = FakeTDClient(
        scripted={
            "analyze_frame": {
                "path": "/project1/out1",
                "resolution": [64, 64],
                "channels": 4,
                "modes": {
                    "luminance": {"mean": 0.23, "min": 0.0, "max": 0.62, "std": 0.08},
                    "alpha_coverage": {"opaque_fraction": 0.91},
                },
            }
        }
    )

    result = await apply_transaction(client, plan, sentinel=UndoBlockSentinel())

    assert result.status == "clean"
    assert result.validation_report is not None
    probe_results = result.validation_report.cheap_metrics["profile_probe_results"]
    sample = next(item for item in probe_results if item["probe_id"] == "visual_output_sample")
    assert sample["status"] == "runtime_pass"
    assert sample["readback_path"] == "/project1/out1"
    assert sample["runtime_metric_values"] == {
        "output_luminance": 0.23,
        "output_alpha_coverage": 0.91,
        "output_entropy": 0.08,
    }
    assert (
        "analyze_frame",
        {"path": "/project1/out1", "modes": ["luminance", "alpha_coverage"]},
    ) in client.calls


@pytest.mark.asyncio
async def test_default_visual_output_sample_defers_when_analysis_endpoint_is_absent():
    plan = _patch_plan(
        [PatchOperation(kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"})],
        required_ops=["nullTOP"],
    )
    client = FakeTDClient()

    result = await apply_transaction(client, plan, sentinel=UndoBlockSentinel())

    assert result.status == "clean"
    assert result.validation_report is not None
    sample = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "visual_output_sample"
    )
    assert sample["status"] == "runtime_deferred"
    assert sample["runtime_required"] is True
    assert result.validation_report.ok is True


@pytest.mark.asyncio
async def test_transaction_auto_repair_revalidates_empty_visual_output_when_enabled():
    plan = _patch_plan(
        [PatchOperation(kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"})],
        required_ops=["nullTOP"],
    )
    samples = [
        {
            "path": "/project1/out1",
            "resolution": [64, 64],
            "channels": 4,
            "modes": {
                "luminance": {"mean": 0.0, "min": 0.0, "max": 0.0, "std": 0.0},
                "alpha_coverage": {"opaque_fraction": 0.0},
            },
        },
        {
            "path": "/project1/out1",
            "resolution": [64, 64],
            "channels": 4,
            "modes": {
                "luminance": {"mean": 0.2, "min": 0.0, "max": 0.6, "std": 0.05},
                "alpha_coverage": {"opaque_fraction": 1.0},
            },
        },
    ]

    def analyze_frame(_params):
        return samples.pop(0)

    client = FakeTDClient(
        scripted={
            "analyze_frame": analyze_frame,
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/params/set": {"ok": True},
            "node/connect": {"ok": True},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        options=TransactionOptions(auto_repair=True, max_repair_attempts=1),
    )

    assert result.status == "clean"
    assert result.validation_failed is False
    assert result.repair_attempts[0]["status"] == "applied"
    assert result.repair_attempts[0]["repair_plan"]["risk_flags"] == ["auto-repair:visual-output-sample"]
    assert len([call for call in client.calls if call[0] == "analyze_frame"]) == 2


@pytest.mark.asyncio
async def test_transaction_auto_repair_then_validation_fails_reverts_both_undo_blocks():
    """An applied auto-repair opens a SECOND undo block. If re-validation still
    fails, rollback must undo BOTH blocks — a single undo would revert only the
    repair and leave the original mutation live while reporting rolled_back."""
    plan = _patch_plan(
        [PatchOperation(kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"})],
        required_ops=["nullTOP"],
    )
    # Every visual sample is empty, so the repair is applied but re-validation
    # still fails, forcing a rollback after two undo blocks were sealed.
    empty_sample = {
        "path": "/project1/out1",
        "resolution": [64, 64],
        "channels": 4,
        "modes": {
            "luminance": {"mean": 0.0, "min": 0.0, "max": 0.0, "std": 0.0},
            "alpha_coverage": {"opaque_fraction": 0.0},
        },
    }
    client = FakeTDClient(
        scripted={
            "analyze_frame": lambda _params: empty_sample,
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/params/set": {"ok": True},
            "node/connect": {"ok": True},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        options=TransactionOptions(auto_repair=True, max_repair_attempts=1),
    )

    assert result.repair_attempts and result.repair_attempts[0]["status"] == "validation_failed"
    assert result.undo_blocks_opened == 2
    undo_calls = [call for call in client.calls if call == ("project/lifecycle", {"action": "undo"})]
    assert len(undo_calls) == 2
    assert result.status == "rolled_back"
    assert result.rollback_performed is True
    assert any(call[0] == "node/connect" for call in client.calls)


@pytest.mark.asyncio
async def test_transaction_report_aggregates_compiler_candidate_profile_probe_results():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "baseCOMP", "name": "tdpilot_concept"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1/tdpilot_concept",
                args={"op_type": "audiofileinCHOP", "name": "audio"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1/tdpilot_concept",
                args={"op_type": "analyzeCHOP", "name": "analyze"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1/tdpilot_concept",
                args={"op_type": "mathCHOP", "name": "range"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1/tdpilot_concept",
                args={"op_type": "nullCHOP", "name": "out_chop"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1/tdpilot_concept",
                args={"op_type": "feedbackTOP", "name": "feedback"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1/tdpilot_concept",
                args={"op_type": "levelTOP", "name": "level"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1/tdpilot_concept",
                args={"op_type": "compositeTOP", "name": "composite"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1/tdpilot_concept",
                args={"op_type": "nullTOP", "name": "out1"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1/tdpilot_concept",
                args={"op_type": "containerCOMP", "name": "panel_container"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1/tdpilot_concept",
                args={"op_type": "sliderCOMP", "name": "panel_slider"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1/tdpilot_concept",
                args={"op_type": "buttonCOMP", "name": "panel_button"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1/tdpilot_concept",
                args={"op_type": "panelCHOP", "name": "panel_reader"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1/tdpilot_concept",
                args={"op_type": "textDAT", "name": "debug_notes"},
            ),
        ],
        required_ops=[
            "baseCOMP",
            "audiofileinCHOP",
            "analyzeCHOP",
            "mathCHOP",
            "nullCHOP",
            "feedbackTOP",
            "levelTOP",
            "compositeTOP",
            "nullTOP",
            "containerCOMP",
            "sliderCOMP",
            "buttonCOMP",
            "panelCHOP",
            "textDAT",
        ],
    )
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
            "analyze_frame": {
                "path": "/project1/tdpilot_concept/out1",
                "resolution": [128, 128],
                "channels": 4,
                "modes": {
                    "luminance": {
                        "mean": 0.31,
                        "min": 0.02,
                        "max": 0.88,
                        "std": 0.11,
                    }
                },
            },
            "chop/data": {
                "path": "/project1/tdpilot_concept/out_chop",
                "numChans": 1,
                "numSamples": 3,
                "channels": {"chan1": {"values": [0.0, 0.5, 1.0]}},
            },
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="concept_compiled",
        concept_profiles=["audio_reactive", "feedback", "panel_ui", "concept_compiled"],
    )

    assert result.status == "clean"
    assert result.validation_report is not None
    probe_results = {
        (item["profile"], item["probe_id"]): item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
    }

    assert ("audio_reactive", "audio_signal_activity") in probe_results
    assert probe_results[("audio_reactive", "audio_signal_activity")]["status"] == "runtime_pass"
    assert ("feedback", "feedback_cycle") in probe_results
    assert probe_results[("feedback", "feedback_output_readback")]["status"] == "runtime_pass"
    assert ("panel_ui", "panel_state_reader") in probe_results
    assert ("concept_compiled", "component_shell_present") in probe_results
    assert result.validation_report.cheap_metrics["concept_profiles"] == [
        "audio_reactive",
        "feedback",
        "panel_ui",
        "concept_compiled",
    ]
    assert "audio_signal_activity" in result.validation_report.checks
    assert "feedback_output_readback" in result.validation_report.checks
    assert "panel_state_reader" in result.validation_report.checks


@pytest.mark.asyncio
async def test_transaction_audio_activity_probe_records_runtime_pass_from_chop_samples():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "audiofileinCHOP", "name": "audio"},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "analyzeCHOP", "name": "analyze"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "mathCHOP", "name": "range"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullCHOP", "name": "out_chop"}
            ),
        ],
        required_ops=["audiofileinCHOP", "analyzeCHOP", "mathCHOP", "nullCHOP"],
    )
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
            "chop/data": {
                "path": "/project1/out_chop",
                "numChans": 1,
                "numSamples": 4,
                "channels": {"chan1": {"values": [0.0, 0.1, 0.35, 0.8]}},
            },
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="audio_reactive",
    )

    assert result.status == "clean"
    assert result.validation_report is not None
    activity = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "audio_signal_activity"
    )
    assert activity["status"] == "runtime_pass"
    assert activity["runtime_required"] is True
    assert activity["readback_path"] == "/project1/out_chop"
    assert activity["runtime_metric_values"]["audio_analysis_channel_delta"] == pytest.approx(0.8)
    assert activity["runtime_metric_values"]["audio_analysis_channel_samples"] == 4
    assert ("chop/data", {"path": "/project1/out_chop"}) in client.calls


@pytest.mark.asyncio
async def test_transaction_audio_activity_probe_rolls_back_when_chop_samples_are_flat():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "audiofileinCHOP", "name": "audio"},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "analyzeCHOP", "name": "analyze"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "mathCHOP", "name": "range"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullCHOP", "name": "out_chop"}
            ),
        ],
        required_ops=["audiofileinCHOP", "analyzeCHOP", "mathCHOP", "nullCHOP"],
    )
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
            "chop/data": {
                "path": "/project1/out_chop",
                "numChans": 1,
                "numSamples": 4,
                "channels": {"chan1": {"values": [0.25, 0.25, 0.25, 0.25]}},
            },
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="audio_reactive",
    )

    assert result.status == "rolled_back"
    assert result.rollback_performed is True
    assert result.validation_failed is True
    assert result.validation_report is not None
    activity = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "audio_signal_activity"
    )
    assert activity["status"] == "runtime_failed"
    assert activity["issue_code"] == "profile_probe_runtime_no_activity"
    assert activity["runtime_metric_values"]["audio_analysis_channel_delta"] == 0.0
    assert result.validation_report.issues[0].code == "profile_probe_runtime_no_activity"
    assert "audio_signal_activity" in result.validation_report.issues[0].message
    assert ("project/lifecycle", {"action": "undo"}) in client.calls


def test_static_profile_probe_metrics_treat_audio_source_inputs_as_alternatives():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "audiofileinCHOP", "name": "audio"},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullCHOP", "name": "out_chop"}
            ),
        ],
        required_ops=["audiofileinCHOP", "nullCHOP"],
    )

    metrics = static_profile_probe_metrics_for_plan(
        plan,
        validation_profile="structural_visual_safe",
        concept_profile="concept_compiled",
    )
    audio_source = next(
        item for item in metrics["profile_probe_results"] if item["probe_id"] == "audio_source_present"
    )

    assert audio_source["present_required_inputs"] == ["audiofileinCHOP"]
    assert audio_source["missing_required_inputs"] == []
    assert audio_source["status"] == "static_pass"


def test_static_profile_probe_metrics_reports_audio_activity_runtime_contract():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "audiofileinCHOP", "name": "audio"},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "analyzeCHOP", "name": "analyze"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "mathCHOP", "name": "range"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullCHOP", "name": "out_chop"}
            ),
        ],
        required_ops=["audiofileinCHOP", "analyzeCHOP", "mathCHOP", "nullCHOP"],
    )

    metrics = static_profile_probe_metrics_for_plan(
        plan,
        validation_profile="structural_visual_safe",
        concept_profile="audio_reactive",
    )
    activity = next(
        item for item in metrics["profile_probe_results"] if item["probe_id"] == "audio_signal_activity"
    )

    assert activity["status"] == "runtime_contract_present"
    assert activity["present_required_inputs"] == ["audiofileinCHOP", "analyzeCHOP", "nullCHOP"]
    assert activity["missing_required_inputs"] == []
    assert activity["runtime_required"] is True
    assert activity["pending_metric_names"] == [
        "audio_analysis_channel_delta",
        "audio_analysis_channel_samples",
    ]


def test_static_profile_probe_metrics_reports_feedback_output_runtime_contract():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "noiseTOP", "name": "noise"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "feedbackTOP", "name": "feedback"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "levelTOP", "name": "level"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "compositeTOP", "name": "composite"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
        ],
        required_ops=["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
    )

    metrics = static_profile_probe_metrics_for_plan(
        plan,
        validation_profile="structural_visual_safe",
        concept_profile="feedback",
    )
    readback = next(
        item for item in metrics["profile_probe_results"] if item["probe_id"] == "feedback_output_readback"
    )

    assert readback["status"] == "runtime_contract_present"
    assert readback["present_required_inputs"] == ["feedbackTOP", "nullTOP"]
    assert readback["missing_required_inputs"] == []
    assert readback["runtime_required"] is True
    assert readback["pending_metric_names"] == [
        "feedback_output_luminance_mean",
        "feedback_output_luminance_max",
    ]


def test_static_profile_probe_metrics_excludes_render_top_output_until_expensive_profile():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "cameraCOMP", "name": "camera"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "geometryCOMP", "name": "geo"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "renderTOP", "name": "render"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/render",
                args={"params": {"camera": "/project1/camera", "geometry": "/project1/geo"}},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
        ],
        required_ops=["cameraCOMP", "geometryCOMP", "renderTOP", "nullTOP"],
    )

    safe_metrics = static_profile_probe_metrics_for_plan(
        plan,
        validation_profile="structural_visual_safe",
        concept_profile="render_pipeline",
    )
    expensive_metrics = static_profile_probe_metrics_for_plan(
        plan,
        validation_profile="structural_visual_expensive",
        concept_profile="render_pipeline",
    )

    assert all(item["probe_id"] != "render_top_output" for item in safe_metrics["profile_probe_results"])
    render_output = next(
        item for item in expensive_metrics["profile_probe_results"] if item["probe_id"] == "render_top_output"
    )
    assert render_output["readback_strategy"] == "top_sample_optional"
    assert render_output["status"] == "runtime_contract_present"
    assert render_output["runtime_required"] is True
    assert render_output["pending_metric_names"] == ["render_luminance", "render_coverage"]


def test_static_profile_probe_metrics_requires_render_camera_frustum_runtime_contract():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "cameraCOMP", "name": "camera"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "geometryCOMP", "name": "geo"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "renderTOP", "name": "render"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/render",
                args={"params": {"camera": "/project1/camera", "geometry": "/project1/geo"}},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
        ],
        required_ops=["cameraCOMP", "geometryCOMP", "renderTOP", "nullTOP"],
    )

    metrics = static_profile_probe_metrics_for_plan(
        plan,
        validation_profile="structural_visual_safe",
        concept_profile="render_pipeline",
    )

    coverage = next(
        item for item in metrics["profile_probe_results"] if item["probe_id"] == "camera_frustum_coverage"
    )
    assert coverage["readback_strategy"] == "render_camera_frustum_runtime"
    assert coverage["status"] == "runtime_contract_present"
    assert coverage["runtime_required"] is True
    assert coverage["pending_metric_names"] == [
        "render_camera_ref_bound",
        "render_geometry_ref_bound",
    ]


@pytest.mark.asyncio
async def test_transaction_feedback_output_probe_records_runtime_pass_from_top_luminance():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "noiseTOP", "name": "noise"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "feedbackTOP", "name": "feedback"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "levelTOP", "name": "level"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "compositeTOP", "name": "composite"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
        ],
        required_ops=["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
    )
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
            "analyze_frame": {
                "path": "/project1/out1",
                "resolution": [128, 128],
                "channels": 4,
                "modes": {
                    "luminance": {
                        "mean": 0.25,
                        "min": 0.0,
                        "max": 0.75,
                        "std": 0.08,
                    }
                },
            },
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="feedback",
    )

    assert result.status == "clean"
    assert result.validation_report is not None
    readback = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "feedback_output_readback"
    )
    assert readback["status"] == "runtime_pass"
    assert readback["runtime_required"] is True
    assert readback["readback_path"] == "/project1/out1"
    assert readback["runtime_metric_values"]["feedback_output_luminance_mean"] == pytest.approx(0.25)
    assert readback["runtime_metric_values"]["feedback_output_luminance_max"] == pytest.approx(0.75)
    assert ("analyze_frame", {"path": "/project1/out1", "modes": ["luminance"]}) in client.calls


@pytest.mark.asyncio
async def test_transaction_expensive_render_output_probe_records_runtime_pass_from_top_analysis():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "cameraCOMP", "name": "camera"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "geometryCOMP", "name": "geo"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "renderTOP", "name": "render"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/render",
                args={"params": {"camera": "/project1/camera", "geometry": "/project1/geo"}},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
        ],
        required_ops=["cameraCOMP", "geometryCOMP", "renderTOP", "nullTOP"],
    )
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/params/set": {"ok": True},
            "node/params": {
                "path": "/project1/render",
                "type": "renderTOP",
                "parameters": {
                    "camera": {"value": "/project1/camera"},
                    "geometry": {"value": "/project1/geo"},
                },
            },
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
            "analyze_frame": {
                "path": "/project1/out1",
                "resolution": [128, 128],
                "channels": 4,
                "modes": {
                    "luminance": {"mean": 0.34, "min": 0.0, "max": 0.82, "std": 0.12},
                    "alpha_coverage": {"mean_alpha": 1.0, "opaque_fraction": 0.91},
                },
            },
        }
    )

    result = await apply_transaction(
        client,
        plan,
        options=TransactionOptions(validation_profile="structural_visual_expensive"),
        sentinel=UndoBlockSentinel(),
        concept_profile="render_pipeline",
    )

    assert result.status == "clean"
    assert result.validation_report is not None
    render_output = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "render_top_output"
    )
    assert render_output["status"] == "runtime_pass"
    assert render_output["runtime_required"] is True
    assert render_output["readback_path"] == "/project1/out1"
    assert render_output["runtime_metric_values"]["render_luminance"] == pytest.approx(0.34)
    assert render_output["runtime_metric_values"]["render_coverage"] == pytest.approx(0.91)
    assert render_output["runtime_evidence"]["endpoint"] == "analyze_frame"
    assert (
        "analyze_frame",
        {"path": "/project1/out1", "modes": ["luminance", "alpha_coverage"]},
    ) in client.calls


@pytest.mark.asyncio
async def test_transaction_render_camera_frustum_probe_records_runtime_pass_from_render_params():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "cameraCOMP", "name": "camera"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "geometryCOMP", "name": "geo"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "renderTOP", "name": "render"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/render",
                args={"params": {"camera": "/project1/camera", "geometry": "/project1/geo"}},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
        ],
        required_ops=["cameraCOMP", "geometryCOMP", "renderTOP", "nullTOP"],
    )
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/params/set": {"ok": True},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
            "node/params": {
                "path": "/project1/render",
                "type": "renderTOP",
                "parameters": {
                    "camera": {"value": "/project1/camera"},
                    "geometry": {"value": "/project1/geo"},
                },
            },
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="render_pipeline",
    )

    assert result.status == "clean"
    assert result.validation_report is not None
    coverage = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "camera_frustum_coverage"
    )
    assert coverage["status"] == "runtime_pass"
    assert coverage["readback_path"] == "/project1/render"
    assert coverage["runtime_metric_values"] == {
        "render_camera_ref_bound": True,
        "render_geometry_ref_bound": True,
    }
    assert coverage["runtime_evidence"]["endpoint"] == "node/params"
    assert (
        "node/params",
        {"path": "/project1/render", "names": ["camera", "geometry"]},
    ) in client.calls


@pytest.mark.asyncio
async def test_transaction_render_camera_frustum_probe_rolls_back_when_refs_are_unbound():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "cameraCOMP", "name": "camera"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "geometryCOMP", "name": "geo"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "renderTOP", "name": "render"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/render",
                args={"params": {"camera": "/project1/camera", "geometry": "/project1/geo"}},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
        ],
        required_ops=["cameraCOMP", "geometryCOMP", "renderTOP", "nullTOP"],
    )
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/params/set": {"ok": True},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
            "node/params": {
                "path": "/project1/render",
                "type": "renderTOP",
                "parameters": {
                    "camera": {"value": ""},
                    "geometry": {"value": "/project1/missing_geo"},
                },
            },
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="render_pipeline",
    )

    assert result.status == "rolled_back"
    assert result.rollback_performed is True
    assert result.validation_failed is True
    assert result.validation_report is not None
    coverage = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "camera_frustum_coverage"
    )
    assert coverage["status"] == "runtime_failed"
    assert coverage["issue_code"] == "profile_probe_runtime_render_refs_unbound"
    assert result.validation_report.issues[0].code == "profile_probe_runtime_render_refs_unbound"
    assert "camera_frustum_coverage" in result.validation_report.issues[0].message
    assert ("project/lifecycle", {"action": "undo"}) in client.calls


@pytest.mark.asyncio
async def test_transaction_expensive_render_output_probe_rolls_back_when_render_is_invisible():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "cameraCOMP", "name": "camera"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "geometryCOMP", "name": "geo"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "renderTOP", "name": "render"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/render",
                args={"params": {"camera": "/project1/camera", "geometry": "/project1/geo"}},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
        ],
        required_ops=["cameraCOMP", "geometryCOMP", "renderTOP", "nullTOP"],
    )
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/params/set": {"ok": True},
            "node/params": {
                "path": "/project1/render",
                "type": "renderTOP",
                "parameters": {
                    "camera": {"value": "/project1/camera"},
                    "geometry": {"value": "/project1/geo"},
                },
            },
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
            "analyze_frame": {
                "path": "/project1/out1",
                "resolution": [128, 128],
                "channels": 4,
                "modes": {
                    "luminance": {"mean": 0.0, "min": 0.0, "max": 0.0, "std": 0.0},
                    "alpha_coverage": {"mean_alpha": 0.0, "opaque_fraction": 0.0},
                },
            },
        }
    )

    result = await apply_transaction(
        client,
        plan,
        options=TransactionOptions(validation_profile="structural_visual_expensive"),
        sentinel=UndoBlockSentinel(),
        concept_profile="render_pipeline",
    )

    assert result.status == "rolled_back"
    assert result.rollback_performed is True
    assert result.validation_failed is True
    assert result.validation_report is not None
    render_output = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "render_top_output"
    )
    assert render_output["status"] == "runtime_failed"
    assert render_output["issue_code"] == "profile_probe_runtime_invisible_render_output"
    assert render_output["runtime_metric_values"]["render_luminance"] == 0.0
    assert render_output["runtime_metric_values"]["render_coverage"] == 0.0
    assert result.validation_report.issues[0].code == "profile_probe_runtime_invisible_render_output"
    assert "render_top_output" in result.validation_report.issues[0].message
    assert ("project/lifecycle", {"action": "undo"}) in client.calls


@pytest.mark.asyncio
async def test_transaction_feedback_output_probe_rolls_back_when_top_is_black():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "noiseTOP", "name": "noise"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "feedbackTOP", "name": "feedback"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "levelTOP", "name": "level"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "compositeTOP", "name": "composite"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
        ],
        required_ops=["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
    )
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
            "analyze_frame": {
                "path": "/project1/out1",
                "resolution": [128, 128],
                "channels": 4,
                "modes": {
                    "luminance": {
                        "mean": 0.0,
                        "min": 0.0,
                        "max": 0.0,
                        "std": 0.0,
                    }
                },
            },
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="feedback",
    )

    assert result.status == "rolled_back"
    assert result.rollback_performed is True
    assert result.validation_failed is True
    assert result.validation_report is not None
    readback = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "feedback_output_readback"
    )
    assert readback["status"] == "runtime_failed"
    assert readback["issue_code"] == "profile_probe_runtime_black_feedback_output"
    assert readback["runtime_metric_values"]["feedback_output_luminance_mean"] == 0.0
    assert readback["runtime_metric_values"]["feedback_output_luminance_max"] == 0.0
    assert result.validation_report.issues[0].code == "profile_probe_runtime_black_feedback_output"
    assert "feedback_output_readback" in result.validation_report.issues[0].message
    assert ("project/lifecycle", {"action": "undo"}) in client.calls


def test_static_profile_probe_metrics_reports_panel_state_readback_runtime_contract():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "containerCOMP", "name": "panel"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "sliderCOMP", "name": "slider"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "buttonCOMP", "name": "button"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "panelCHOP", "name": "panel_reader"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullCHOP", "name": "out_chop"}
            ),
        ],
        required_ops=["containerCOMP", "sliderCOMP", "buttonCOMP", "panelCHOP", "nullCHOP"],
    )

    metrics = static_profile_probe_metrics_for_plan(
        plan,
        validation_profile="structural_visual_safe",
        concept_profile="panel_ui",
    )
    readback = next(
        item for item in metrics["profile_probe_results"] if item["probe_id"] == "panel_state_readback"
    )

    assert readback["status"] == "runtime_contract_present"
    assert readback["present_required_inputs"] == ["panelCHOP", "nullCHOP"]
    assert readback["missing_required_inputs"] == []
    assert readback["runtime_required"] is True
    assert readback["pending_metric_names"] == ["panel_state_channel_count", "panel_state_sample_count"]


def test_static_profile_probe_metrics_reports_pop_bounds_runtime_contract():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "circlePOP", "name": "source"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullPOP", "name": "out_pop"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "rendersimpleTOP", "name": "preview"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/preview",
                args={"params": {"pop": "/project1/out_pop"}},
            ),
        ],
        required_ops=["circlePOP", "nullPOP", "rendersimpleTOP"],
    )

    metrics = static_profile_probe_metrics_for_plan(
        plan,
        validation_profile="structural_visual_safe",
        concept_profile="pop",
    )
    bounds = next(
        item for item in metrics["profile_probe_results"] if item["probe_id"] == "finite_pop_bounds"
    )

    assert bounds["status"] == "runtime_contract_present"
    assert bounds["present_required_inputs"] == ["nullPOP"]
    assert bounds["missing_required_inputs"] == []
    assert bounds["runtime_required"] is True
    assert bounds["pending_metric_names"] == ["pop_bounds_finite"]


def test_static_profile_probe_metrics_reports_glsl_compile_runtime_contract():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "constantTOP", "name": "input"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "pixel"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glslTOP", "name": "shader"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/shader",
                args={"params": {"pixeldat": "/project1/pixel"}},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
        ],
        required_ops=["constantTOP", "textDAT", "glslTOP", "nullTOP"],
    )

    metrics = static_profile_probe_metrics_for_plan(
        plan,
        validation_profile="structural_visual_safe",
        concept_profile="glsl",
    )
    compile_state = next(
        item for item in metrics["profile_probe_results"] if item["probe_id"] == "compile_state"
    )

    assert compile_state["status"] == "runtime_contract_present"
    assert compile_state["present_required_inputs"] == ["glslTOP"]
    assert compile_state["missing_required_inputs"] == []
    assert compile_state["runtime_required"] is True
    assert compile_state["pending_metric_names"] == ["shader_compile_clean"]


def test_static_profile_probe_metrics_reports_dat_callback_guard_runtime_contract():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "tableDAT", "name": "table"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "datexecuteDAT", "name": "callback"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/callback",
                args={"params": {"dat": "/project1/table"}},
            ),
        ],
        required_ops=["tableDAT", "datexecuteDAT"],
    )

    metrics = static_profile_probe_metrics_for_plan(
        plan,
        validation_profile="structural_visual_safe",
        concept_profile="dat_protocol",
    )
    guard = next(
        item for item in metrics["profile_probe_results"] if item["probe_id"] == "callback_guard_present"
    )

    assert guard["status"] == "runtime_contract_present"
    assert guard["present_required_inputs"] == ["datexecuteDAT"]
    assert guard["missing_required_inputs"] == []
    assert guard["runtime_required"] is True
    assert guard["pending_metric_names"] == ["modern_table_change_callback_present"]


def _complete_dat_protocol_callback_plan(callback_text: str) -> PatchPlan:
    return _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "serialDAT", "name": "serial"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "oscinDAT", "name": "osc"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "websocketDAT", "name": "websocket"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "mqttclientDAT", "name": "mqtt"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "udpinDAT", "name": "udp"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "tableDAT", "name": "table"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullDAT", "name": "out_dat"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "constantTOP", "name": "input_a"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "noiseTOP", "name": "input_b"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "switchTOP", "name": "switch"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/switch",
                args={
                    "params": {
                        "index": {"expr": "min(1, max(0, int(op('/project1/table')[1, 'selected_index'])))"}
                    }
                },
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "callback_source"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "datexecuteDAT", "name": "callback"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/callback",
                args={"params": {"dat": "/project1/table"}},
            ),
            PatchOperation(
                kind="set_dat_content",
                target="/project1/callback",
                args={"text": callback_text},
            ),
        ],
        required_ops=[
            "serialDAT",
            "oscinDAT",
            "websocketDAT",
            "mqttclientDAT",
            "udpinDAT",
            "tableDAT",
            "nullDAT",
            "constantTOP",
            "noiseTOP",
            "switchTOP",
            "nullTOP",
            "textDAT",
            "datexecuteDAT",
        ],
    )


@pytest.mark.asyncio
async def test_transaction_panel_state_readback_probe_records_runtime_pass_from_chop_channels():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "containerCOMP", "name": "panel"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "sliderCOMP", "name": "slider"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "buttonCOMP", "name": "button"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "panelCHOP", "name": "panel_reader"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullCHOP", "name": "out_chop"}
            ),
        ],
        required_ops=["containerCOMP", "sliderCOMP", "buttonCOMP", "panelCHOP", "nullCHOP"],
    )
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
            "chop/data": {
                "path": "/project1/out_chop",
                "numChans": 2,
                "numSamples": 1,
                "channels": {
                    "slider": {"values": [0.5]},
                    "select": {"values": [1.0]},
                },
            },
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="panel_ui",
    )

    assert result.status == "clean"
    assert result.validation_report is not None
    readback = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "panel_state_readback"
    )
    assert readback["status"] == "runtime_pass"
    assert readback["runtime_required"] is True
    assert readback["readback_path"] == "/project1/out_chop"
    assert readback["runtime_metric_values"]["panel_state_channel_count"] == 2
    assert readback["runtime_metric_values"]["panel_state_sample_count"] == 2
    assert ("chop/data", {"path": "/project1/out_chop"}) in client.calls


@pytest.mark.asyncio
async def test_transaction_panel_state_readback_probe_rolls_back_when_channels_missing():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "containerCOMP", "name": "panel"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "sliderCOMP", "name": "slider"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "buttonCOMP", "name": "button"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "panelCHOP", "name": "panel_reader"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullCHOP", "name": "out_chop"}
            ),
        ],
        required_ops=["containerCOMP", "sliderCOMP", "buttonCOMP", "panelCHOP", "nullCHOP"],
    )
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
            "chop/data": {
                "path": "/project1/out_chop",
                "numChans": 0,
                "numSamples": 0,
                "channels": {},
            },
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="panel_ui",
    )

    assert result.status == "rolled_back"
    assert result.rollback_performed is True
    assert result.validation_failed is True
    assert result.validation_report is not None
    readback = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "panel_state_readback"
    )
    assert readback["status"] == "runtime_failed"
    assert readback["issue_code"] == "profile_probe_runtime_no_panel_state"
    assert readback["runtime_metric_values"]["panel_state_channel_count"] == 0
    assert readback["runtime_metric_values"]["panel_state_sample_count"] == 0
    assert result.validation_report.issues[0].code == "profile_probe_runtime_no_panel_state"
    assert "panel_state_readback" in result.validation_report.issues[0].message
    assert ("project/lifecycle", {"action": "undo"}) in client.calls


@pytest.mark.asyncio
async def test_transaction_pop_bounds_probe_records_runtime_pass_from_pop_bounds():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "circlePOP", "name": "source"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullPOP", "name": "out_pop"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "rendersimpleTOP", "name": "preview"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/preview",
                args={"params": {"pop": "/project1/out_pop"}},
            ),
        ],
        required_ops=["circlePOP", "nullPOP", "rendersimpleTOP"],
    )
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
            "pop/bounds": {
                "bounds": {
                    "min": [-1.0, -0.5, 0.0],
                    "max": [1.0, 0.5, 0.0],
                }
            },
            "pop/inspect": {
                "path": "/project1/out_pop",
                "family": "POP",
                "attributes": {
                    "point": [{"name": "P", "size": 3, "type": "float"}],
                    "prim": [],
                    "vert": [],
                },
            },
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="pop",
    )

    assert result.status == "clean"
    assert result.validation_report is not None
    bounds = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "finite_pop_bounds"
    )
    assert bounds["status"] == "runtime_pass"
    assert bounds["runtime_required"] is True
    assert bounds["readback_path"] == "/project1/out_pop"
    assert bounds["runtime_metric_values"]["pop_bounds_finite"] is True
    assert ("pop/bounds", {"path": "/project1/out_pop"}) in client.calls


@pytest.mark.asyncio
async def test_transaction_pop_bounds_probe_rolls_back_when_bounds_are_nonfinite():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "circlePOP", "name": "source"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullPOP", "name": "out_pop"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "rendersimpleTOP", "name": "preview"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/preview",
                args={"params": {"pop": "/project1/out_pop"}},
            ),
        ],
        required_ops=["circlePOP", "nullPOP", "rendersimpleTOP"],
    )
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
            "pop/bounds": {
                "bounds": {
                    "min": [-1.0, float("nan"), 0.0],
                    "max": [1.0, 0.5, 0.0],
                }
            },
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="pop",
    )

    assert result.status == "rolled_back"
    assert result.rollback_performed is True
    assert result.validation_failed is True
    assert result.validation_report is not None
    bounds = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "finite_pop_bounds"
    )
    assert bounds["status"] == "runtime_failed"
    assert bounds["issue_code"] == "profile_probe_runtime_nonfinite_pop_bounds"
    assert bounds["runtime_metric_values"]["pop_bounds_finite"] is False
    assert result.validation_report.issues[0].code == "profile_probe_runtime_nonfinite_pop_bounds"
    assert "finite_pop_bounds" in result.validation_report.issues[0].message
    assert ("project/lifecycle", {"action": "undo"}) in client.calls


def test_static_profile_probe_metrics_reports_pop_attribute_runtime_contract():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "circlePOP", "name": "source"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullPOP", "name": "out_pop"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "rendersimpleTOP", "name": "preview"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/preview",
                args={"params": {"pop": "/project1/out_pop"}},
            ),
        ],
        required_ops=["circlePOP", "nullPOP", "rendersimpleTOP"],
    )

    metrics = static_profile_probe_metrics_for_plan(
        plan,
        validation_profile="structural_visual_safe",
        concept_profile="pop",
    )

    attributes = next(
        item for item in metrics["profile_probe_results"] if item["probe_id"] == "attribute_sample_available"
    )
    assert attributes["readback_strategy"] == "pop_attribute_metadata_runtime"
    assert attributes["status"] == "runtime_contract_present"
    assert attributes["runtime_required"] is True
    assert attributes["pending_metric_names"] == ["pop_attribute_count_present"]


@pytest.mark.asyncio
async def test_transaction_pop_attribute_probe_records_runtime_pass_from_pop_inspect():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "circlePOP", "name": "source"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullPOP", "name": "out_pop"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "rendersimpleTOP", "name": "preview"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/preview",
                args={"params": {"pop": "/project1/out_pop"}},
            ),
        ],
        required_ops=["circlePOP", "nullPOP", "rendersimpleTOP"],
    )
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
            "pop/bounds": {
                "bounds": {
                    "min": [-1.0, -0.5, 0.0],
                    "max": [1.0, 0.5, 0.0],
                }
            },
            "pop/inspect": {
                "path": "/project1/out_pop",
                "family": "POP",
                "attributes": {
                    "point": [{"name": "P", "size": 3, "type": "float"}],
                    "prim": [],
                    "vert": [],
                },
                "samples": {"points": {"P": {"values": [[0.0, 0.0, 0.0]]}}},
            },
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="pop",
    )

    assert result.status == "clean"
    assert result.validation_report is not None
    attributes = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "attribute_sample_available"
    )
    assert attributes["status"] == "runtime_pass"
    assert attributes["runtime_required"] is True
    assert attributes["readback_path"] == "/project1/out_pop"
    assert attributes["runtime_metric_values"]["pop_attribute_count_present"] is True
    assert attributes["runtime_evidence"]["endpoint"] == "pop/inspect"
    assert attributes["runtime_evidence"]["attribute_count"] == 1
    assert (
        "pop/inspect",
        {
            "path": "/project1/out_pop",
            "include_bounds": False,
            "include_attributes": True,
            "point_attributes": ["P"],
            "prim_attributes": [],
            "vert_attributes": [],
            "start": 0,
            "count": 8,
            "delayed": True,
        },
    ) in client.calls


@pytest.mark.asyncio
async def test_transaction_pop_attribute_probe_rolls_back_when_pop_inspect_has_no_attributes():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "circlePOP", "name": "source"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullPOP", "name": "out_pop"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "rendersimpleTOP", "name": "preview"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/preview",
                args={"params": {"pop": "/project1/out_pop"}},
            ),
        ],
        required_ops=["circlePOP", "nullPOP", "rendersimpleTOP"],
    )
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
            "pop/bounds": {
                "bounds": {
                    "min": [-1.0, -0.5, 0.0],
                    "max": [1.0, 0.5, 0.0],
                }
            },
            "pop/inspect": {
                "path": "/project1/out_pop",
                "family": "POP",
                "attributes": {"point": [], "prim": [], "vert": []},
                "samples": {"points": {}},
            },
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="pop",
    )

    assert result.status == "rolled_back"
    assert result.rollback_performed is True
    assert result.validation_failed is True
    assert result.validation_report is not None
    attributes = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "attribute_sample_available"
    )
    assert attributes["status"] == "runtime_failed"
    assert attributes["issue_code"] == "profile_probe_runtime_missing_pop_attributes"
    assert attributes["runtime_metric_values"]["pop_attribute_count_present"] is False
    assert result.validation_report.issues[0].code == "profile_probe_runtime_missing_pop_attributes"
    assert "attribute_sample_available" in result.validation_report.issues[0].message
    assert ("project/lifecycle", {"action": "undo"}) in client.calls


@pytest.mark.asyncio
async def test_transaction_glsl_compile_probe_records_runtime_pass_from_node_errors():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "constantTOP", "name": "input"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "pixel"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glslTOP", "name": "shader"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/shader",
                args={"params": {"pixeldat": "/project1/pixel"}},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
        ],
        required_ops=["constantTOP", "textDAT", "glslTOP", "nullTOP"],
    )
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/params/set": {"ok": True},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="glsl",
    )

    assert result.status == "clean"
    assert result.validation_report is not None
    compile_state = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "compile_state"
    )
    assert compile_state["status"] == "runtime_pass"
    assert compile_state["runtime_required"] is True
    assert compile_state["readback_path"] == "/project1/shader"
    assert compile_state["runtime_metric_values"]["shader_compile_clean"] is True
    assert ("node/errors", {"path": "/project1/shader"}) in client.calls


@pytest.mark.asyncio
async def test_transaction_glsl_compile_probe_rolls_back_on_node_errors():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "constantTOP", "name": "input"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "pixel"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glslTOP", "name": "shader"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/shader",
                args={"params": {"pixeldat": "/project1/pixel"}},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
        ],
        required_ops=["constantTOP", "textDAT", "glslTOP", "nullTOP"],
    )

    def node_errors(params):
        if params.get("path") == "/project1/shader":
            return {"issues": [{"path": "/project1/shader", "message": "shader compile failed"}]}
        return {"issues": []}

    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/params/set": {"ok": True},
            "node/errors": node_errors,
            "cooking": {"stuck": []},
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="glsl",
    )

    assert result.status == "rolled_back"
    assert result.rollback_performed is True
    assert result.validation_failed is True
    assert result.validation_report is not None
    compile_state = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "compile_state"
    )
    assert compile_state["status"] == "runtime_failed"
    assert compile_state["issue_code"] == "profile_probe_runtime_compile_state_error"
    assert compile_state["runtime_metric_values"]["shader_compile_clean"] is False
    assert result.validation_report.issues[0].code == "profile_probe_runtime_compile_state_error"
    assert "compile_state" in result.validation_report.issues[0].message
    assert ("project/lifecycle", {"action": "undo"}) in client.calls


@pytest.mark.asyncio
async def test_transaction_dat_callback_guard_probe_records_runtime_pass_from_node_content():
    callback_text = (
        "tdpilot_callback_guard = False\n\n"
        "def onTableChange(dat, prevDAT, info):\n"
        "    global tdpilot_callback_guard\n"
        "    if tdpilot_callback_guard:\n"
        "        return\n"
        "    tdpilot_callback_guard = True\n"
        "    try:\n"
        "        return\n"
        "    finally:\n"
        "        tdpilot_callback_guard = False\n"
    )
    plan = _complete_dat_protocol_callback_plan(callback_text)
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/params/set": {"ok": True},
            "node/content/set": {"ok": True},
            "node/content": {"text": callback_text},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="dat_protocol",
    )

    assert result.status == "clean"
    assert result.validation_report is not None
    guard = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "callback_guard_present"
    )
    assert guard["status"] == "runtime_pass"
    assert guard["runtime_required"] is True
    assert guard["readback_path"] == "/project1/callback"
    assert guard["runtime_metric_values"]["modern_table_change_callback_present"] is True
    assert ("node/content", {"path": "/project1/callback"}) in client.calls


@pytest.mark.asyncio
async def test_transaction_dat_callback_guard_probe_rolls_back_when_guard_is_missing():
    callback_text = "def onTableChange(dat, prevDAT, info):\n    return\n"
    plan = _complete_dat_protocol_callback_plan(callback_text)
    client = FakeTDClient(
        scripted={
            "node/create": lambda params: {"path": f"{params['parent_path'].rstrip('/')}/{params['name']}"},
            "node/params/set": {"ok": True},
            "node/content/set": {"ok": True},
            "node/content": {"text": callback_text},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
        }
    )

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="dat_protocol",
    )

    assert result.status == "rolled_back"
    assert result.rollback_performed is True
    assert result.validation_failed is True
    assert result.validation_report is not None
    guard = next(
        item
        for item in result.validation_report.cheap_metrics["profile_probe_results"]
        if item["probe_id"] == "callback_guard_present"
    )
    assert guard["status"] == "runtime_failed"
    assert guard["issue_code"] == "profile_probe_runtime_callback_guard_missing"
    assert guard["runtime_metric_values"]["modern_table_change_callback_present"] is False
    assert result.validation_report.issues[0].code == "profile_probe_runtime_callback_guard_missing"
    assert "callback_guard_present" in result.validation_report.issues[0].message
    assert ("project/lifecycle", {"action": "undo"}) in client.calls


def test_static_profile_probe_metrics_treat_stable_output_families_as_alternatives():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "debug"}
            ),
        ],
        required_ops=["nullTOP", "textDAT"],
    )

    metrics = static_profile_probe_metrics_for_plan(
        plan,
        validation_profile="structural_visual_safe",
        concept_profile="concept_compiled",
    )
    output_probe = next(
        item for item in metrics["profile_probe_results"] if item["probe_id"] == "output_node_present"
    )

    assert output_probe["present_required_inputs"] == ["nullTOP", "textDAT"]
    assert output_probe["missing_required_inputs"] == []
    assert output_probe["status"] == "static_pass"


def test_static_profile_probe_metrics_requires_render_switch_index_binding():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "tableDAT", "name": "table"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "switchTOP", "name": "switch"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
        ],
        required_ops=["tableDAT", "switchTOP", "nullTOP"],
    )

    metrics = static_profile_probe_metrics_for_plan(
        plan,
        validation_profile="structural_visual_safe",
        concept_profile="dat_protocol",
    )
    binding_probe = next(
        item for item in metrics["profile_probe_results"] if item["probe_id"] == "render_switch_index_binding"
    )

    assert binding_probe["present_required_inputs"] == ["tableDAT", "switchTOP"]
    assert binding_probe["missing_required_inputs"] == []
    assert binding_probe["status"] == "static_incomplete"
    assert binding_probe["issue_code"] == "profile_probe_missing_parameter_binding"
    assert binding_probe["missing_parameter_bindings"] == ["switchTOP.index<-tableDAT"]
    assert "switchTOP.index<-tableDAT" in binding_probe["issue_message"]


def test_static_profile_probe_metrics_accepts_render_switch_table_index_binding():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "tableDAT", "name": "table"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "switchTOP", "name": "switch"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/switch",
                args={
                    "params": {
                        "index": {"expr": "min(1, max(0, int(op('/project1/table')[1, 'selected_index'])))"}
                    }
                },
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
        ],
        required_ops=["tableDAT", "switchTOP", "nullTOP"],
    )

    metrics = static_profile_probe_metrics_for_plan(
        plan,
        validation_profile="structural_visual_safe",
        concept_profile="dat_protocol",
    )
    binding_probe = next(
        item for item in metrics["profile_probe_results"] if item["probe_id"] == "render_switch_index_binding"
    )

    assert binding_probe["status"] == "static_pass"
    assert binding_probe["present_parameter_bindings"] == ["switchTOP.index<-tableDAT"]
    assert binding_probe["missing_parameter_bindings"] == []


def test_profile_probe_failures_emit_stable_validation_issues():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "feedbackTOP", "name": "feedback"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "compositeTOP", "name": "composite"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
        ],
        required_ops=["feedbackTOP", "compositeTOP", "nullTOP"],
    )
    metrics = static_profile_probe_metrics_for_plan(
        plan,
        validation_profile="structural_visual_safe",
        concept_profile="feedback",
    )
    decay_probe = next(
        item for item in metrics["profile_probe_results"] if item["probe_id"] == "decay_control"
    )

    report = build_validation_report_v2(
        target_root="/project1",
        profile="structural_visual_safe",
        concept_profile="feedback",
        patch_result=None,
        cheap_metrics=metrics,
    )

    assert report.ok is False
    assert report.severity_counts["error"] == 1
    assert report.summary == "1 validation issue(s)"
    assert decay_probe["issue_code"] == "profile_probe_missing_required_inputs"
    assert decay_probe["issue_message"] == (
        "decay_control: Feedback plans must include a bounded decay control stage. "
        "Missing required inputs: levelTOP."
    )
    issue = report.issues[0]
    assert issue.code == "profile_probe_missing_required_inputs"
    assert issue.severity == "error"
    assert issue.path == "/project1"
    assert issue.source == "tdpilot-brain"
    assert "decay_control" in issue.message
    assert "levelTOP" in issue.message


def test_profile_classifier_does_not_match_ui_inside_build():
    profile = classify_intent_profile("Build a custom parameter control rig with default values")

    assert profile == "control_rig"


def test_profile_classifier_splits_glsl_material_from_top_shader():
    assert classify_intent_profile("build a GLSL material with vertex shader") == "glsl_material"
    assert classify_intent_profile("write a GLSL POP attribute shader") == "glsl_pop"
    assert classify_intent_profile("write a GLSL fragment shader TOP") == "glsl"


def test_reference_param_validator_accepts_shader_render_and_material_refs():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "pixel"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "vertex"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glslMAT", "name": "mat"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/mat",
                args={"params": {"vdat": "/project1/vertex", "pdat": "/project1/pixel"}},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "geometryCOMP", "name": "geo"}
            ),
            PatchOperation(
                kind="set_params", target="/project1/geo", args={"params": {"material": "/project1/mat"}}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "cameraCOMP", "name": "cam"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "renderTOP", "name": "render"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/render",
                args={"params": {"camera": "/project1/cam", "geometry": "/project1/geo"}},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "circlePOP", "name": "pop"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "rendersimple", "name": "preview"}
            ),
            PatchOperation(
                kind="set_params", target="/project1/preview", args={"params": {"pop": "/project1/pop"}}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glsl", "name": "top_shader"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/top_shader",
                args={"params": {"pixeldat": "/project1/pixel"}},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glslPOP", "name": "pop_shader"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/pop_shader",
                args={"params": {"computedat": "/project1/pixel"}},
            ),
        ],
        required_ops=[
            "glslMAT",
            "geometryCOMP",
            "cameraCOMP",
            "renderTOP",
            "rendersimpleTOP",
            "glslTOP",
            "glslPOP",
        ],
    )

    assert validate_reference_params_for_plan(plan) == []


def test_reference_param_validator_rejects_missing_required_refs():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glslMAT", "name": "mat"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "geometryCOMP", "name": "geo"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "renderTOP", "name": "render"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "rendersimpleTOP", "name": "preview"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glslPOP", "name": "pop_shader"}
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "glsladvancedPOP", "name": "advanced_pop_shader"},
            ),
        ],
        required_ops=[
            "glslMAT",
            "geometryCOMP",
            "renderTOP",
            "rendersimpleTOP",
            "glslPOP",
            "glsladvancedPOP",
        ],
    )

    issues = validate_reference_params_for_plan(plan)
    messages = "\n".join(issue.message for issue in issues)

    assert all(issue.code == "missing_reference_param" for issue in issues)
    assert "/project1/mat" in messages
    assert "vdat" in messages and "pdat" in messages
    assert "/project1/geo" in messages and "material" in messages
    assert "/project1/render" in messages and "camera" in messages and "geometry" in messages
    assert "/project1/preview" in messages and "pop" in messages
    assert "/project1/pop_shader" in messages and "computedat" in messages
    assert "/project1/advanced_pop_shader" in messages and "computedat" in messages


def test_reference_param_validator_rejects_wrong_created_target_type():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "geometryCOMP", "name": "geo"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "cameraCOMP", "name": "cam"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "renderTOP", "name": "render"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/render",
                args={"params": {"camera": "/project1/geo", "geometry": "/project1/cam"}},
            ),
        ],
        required_ops=["geometryCOMP", "cameraCOMP", "renderTOP"],
    )

    issues = validate_reference_params_for_plan(plan)

    assert {issue.code for issue in issues} == {"invalid_reference_param"}
    assert any("camera" in issue.message and "cameraCOMP" in issue.message for issue in issues)
    assert any("geometry" in issue.message and "geometryCOMP" in issue.message for issue in issues)


@pytest.mark.asyncio
async def test_transaction_preflight_blocks_invalid_reference_params_before_apply():
    plan = _patch_plan(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glsl", "name": "shader"}
            ),
        ],
        required_ops=["glslTOP"],
    )
    client = FakeTDClient(scripted={"project/lifecycle": {"snapshot_id": "unused"}})

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="glsl",
    )

    assert result.status == "blocked"
    assert result.failed_reason
    assert "pixeldat" in result.failed_reason
    assert result.apply_result is None
    assert result.validation_report is not None
    assert result.validation_report.ok is False
    assert result.validation_report.checks == ["reference_params"]
