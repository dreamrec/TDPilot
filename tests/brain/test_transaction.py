from __future__ import annotations

import pytest
from patch.conftest import FakeTDClient

from td_mcp.brain.transaction import apply_transaction
from td_mcp.models.brain import TransactionOptions
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan
from td_mcp.patch.undo_sentinel import UndoBlockSentinel


def _plan(ops, target_root="/p"):
    return PatchPlan(
        target_root=target_root,
        source="operations",
        operations=ops,
        undo_label="brain transaction",
        validation_plan=ValidationPlan(target_root=target_root, capture_frames=[]),
    )


@pytest.mark.asyncio
async def test_transaction_dry_run_preflights_without_mutating():
    ops = [PatchOperation(kind="create_node", target="/p", args={"op_type": "nullTOP", "name": "out1"})]
    client = FakeTDClient(scripted={"nodes": {"nodes": []}})

    result = await apply_transaction(
        client,
        _plan(ops),
        options=TransactionOptions(dry_run=True),
        sentinel=UndoBlockSentinel(),
    )

    assert result.status == "dry_run"
    assert result.preview is not None
    assert not any(call[0] == "project/lifecycle" for call in client.calls)


@pytest.mark.asyncio
async def test_transaction_rolls_back_when_apply_breaks():
    ops = [
        PatchOperation(kind="create_node", target="/p", args={"op_type": "nullTOP", "name": "ok"}),
        PatchOperation(kind="create_node", target="/p", args={"op_type": "nullTOP", "name": "boom"}),
    ]

    def create(params):
        if params["name"] == "boom":
            raise RuntimeError("create failed")
        return {"path": f"/p/{params['name']}"}

    client = FakeTDClient(scripted={"nodes": {"nodes": []}, "node/create": create})

    result = await apply_transaction(client, _plan(ops), sentinel=UndoBlockSentinel())

    assert result.status == "rolled_back"
    assert result.rollback_performed is True
    assert result.apply_result is not None
    assert result.apply_result.failed_op == 1
    assert result.validation_report is not None
    assert ("project/lifecycle", {"action": "undo"}) in client.calls


@pytest.mark.asyncio
async def test_transaction_rolls_back_when_validation_fails():
    ops = [PatchOperation(kind="create_node", target="/p", args={"op_type": "nullTOP", "name": "out1"})]
    client = FakeTDClient(
        scripted={
            "nodes": {"nodes": []},
            "node/create": {"path": "/p/out1"},
            "node/errors": {"issues": [{"path": "/p/out1", "message": "broken"}]},
            "cooking": {"stuck": []},
        }
    )

    result = await apply_transaction(client, _plan(ops), sentinel=UndoBlockSentinel())

    assert result.status == "rolled_back"
    assert result.rollback_performed is True
    assert result.validation_failed is True
    assert result.validation_report is not None
    assert result.validation_report.ok is False
    assert ("project/lifecycle", {"action": "undo"}) in client.calls


@pytest.mark.asyncio
async def test_transaction_preflights_set_params_before_apply():
    ops = [
        PatchOperation(kind="create_node", target="/p", args={"op_type": "levelTOP", "name": "level"}),
        PatchOperation(kind="set_params", target="/p/level", args={"params": {"opacity": 0.5}}),
    ]
    client = FakeTDClient(
        scripted={
            "nodes": {"nodes": []},
            "node/create": {"path": "/p/level"},
            "node/params/set": {"ok": True},
            "node/errors": {"issues": []},
            "cooking": {"stuck": []},
        }
    )
    preflight_calls = []

    def fake_preflight(**kwargs):
        preflight_calls.append(kwargs)
        return type(
            "PreflightResult",
            (),
            {
                "adjusted_params": {"opacity": 0.75},
                "safety_warnings": ["opacity clamped"],
                "param_semantics_warnings": [],
                "blocked": False,
            },
        )()

    result = await apply_transaction(
        client,
        _plan(ops),
        sentinel=UndoBlockSentinel(),
        param_preflight=fake_preflight,
    )

    assert result.status == "clean"
    assert preflight_calls
    assert preflight_calls[0]["path"] == "/p/level"
    assert preflight_calls[0]["op_type"] == "levelTOP"
    assert ("node/params/set", {"path": "/p/level", "params": {"opacity": 0.75}}) in client.calls


@pytest.mark.asyncio
async def test_transaction_rolls_back_when_generated_code_runtime_contract_fails():
    ops = [
        PatchOperation(kind="create_node", target="/p", args={"op_type": "glslTOP", "name": "glsl1"}),
        PatchOperation(kind="create_node", target="/p", args={"op_type": "textDAT", "name": "pixel_code"}),
        PatchOperation(kind="set_params", target="/p/glsl1", args={"params": {"pixeldat": "/p/pixel_code"}}),
        PatchOperation(
            kind="set_dat_content",
            target="/p/pixel_code",
            args={
                "text": "out vec4 fragColor;\nvoid main() { fragColor = vec4(1.0); }\n",
                "generated_code": {
                    "block_id": "pixel_shader",
                    "language": "glsl",
                    "target_op": "/p/glsl1",
                    "target_param": "pixeldat",
                    "source_kind": "textDAT",
                    "source_refs": ["/p/pixel_code"],
                    "static_checks": ["glsl_entrypoint"],
                    "runtime_checks": ["compile_state"],
                    "expected_outputs": ["/p/out1"],
                    "risk_flags": ["generated_code"],
                    "official_sources": ["https://docs.derivative.ca/GLSL_TOP"],
                },
            },
        ),
    ]

    def node_errors(params):
        if params.get("path") == "/p/glsl1":
            return {"issues": [{"path": "/p/glsl1", "message": "shader compile failed"}]}
        return {"issues": []}

    client = FakeTDClient(
        scripted={
            "nodes": {"nodes": []},
            "node/create": lambda params: {"path": f"{params['parent_path']}/{params['name']}"},
            "node/params/set": {"ok": True},
            "node/content/set": {"ok": True},
            "node/errors": node_errors,
            "cooking": {"stuck": []},
        }
    )

    result = await apply_transaction(
        client,
        _plan(ops),
        options=TransactionOptions(validation_profile="structural_visual_safe"),
        sentinel=UndoBlockSentinel(),
    )

    assert result.status == "rolled_back"
    assert result.rollback_performed is True
    assert result.validation_failed is True
    assert result.validation_report is not None
    assert result.validation_report.ok is False
    assert "generated_code_runtime_checks" in result.validation_report.checks
    assert result.validation_report.cheap_metrics["generated_code_runtime"]["checked_contract_count"] == 1
    assert any(
        issue.code == "generated_code_runtime_compile_state_error"
        for issue in result.validation_report.issues
    )
    assert ("project/lifecycle", {"action": "undo"}) in client.calls
