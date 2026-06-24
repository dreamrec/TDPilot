from __future__ import annotations

import pytest
from patch.conftest import FakeTDClient

from td_mcp.brain.transaction import _rollback, apply_transaction
from td_mcp.models.brain import TransactionOptions, TransactionResult
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
async def test_transaction_rollback_verifies_created_node_paths_are_absent_after_undo():
    ops = [PatchOperation(kind="create_node", target="/p", args={"op_type": "nullTOP", "name": "out1"})]

    def detail(params):
        if params.get("path") == "/p/out1":
            return {"path": "/p/out1", "type": "nullTOP", "family": "TOP"}
        return {"error": "not found"}

    client = FakeTDClient(
        scripted={
            "nodes": {"nodes": []},
            "node/create": {"path": "/p/out1"},
            "node/errors": {"issues": [{"path": "/p/out1", "message": "broken"}]},
            "node/detail": detail,
            "cooking": {"stuck": []},
        }
    )

    result = await apply_transaction(client, _plan(ops), sentinel=UndoBlockSentinel())

    assert ("node/detail", {"path": "/p/out1"}) in client.calls
    assert result.status == "broken"
    assert result.rollback_performed is False
    assert result.needs_manual_recovery is True
    assert result.rollback_verification["created_paths"]["remaining"] == ["/p/out1"]
    assert "created paths still exist" in (result.rollback_error or "")


def _txn_result(**kwargs) -> TransactionResult:
    base = {"plan_id": "p1", "status": "broken"}
    base.update(kwargs)
    return TransactionResult(**base)


def _undo_count(client: FakeTDClient) -> int:
    return len([c for c in client.calls if c == ("project/lifecycle", {"action": "undo"})])


@pytest.mark.asyncio
async def test_rollback_issues_one_undo_per_sealed_block():
    client = FakeTDClient()
    result = _txn_result(undo_blocks_opened=2)
    await _rollback(client, result, restore_snapshot=None, undo_block_count=2)
    assert _undo_count(client) == 2
    assert result.rollback_performed is True
    assert result.needs_manual_recovery is False


@pytest.mark.asyncio
async def test_rollback_no_block_opened_is_noop_success_without_stray_undo():
    # A preflight-blocked apply seals no undo block; rollback must not fire a
    # stray undo that would revert an unrelated prior action.
    client = FakeTDClient()
    result = _txn_result(undo_blocks_opened=0)
    await _rollback(client, result, restore_snapshot=None, undo_block_count=0)
    assert _undo_count(client) == 0
    assert result.rollback_performed is True


@pytest.mark.asyncio
async def test_rollback_partial_undo_failure_without_snapshot_needs_manual_recovery():
    state = {"n": 0}

    def lifecycle(params):
        if params.get("action") == "undo":
            state["n"] += 1
            if state["n"] >= 2:  # second block (the original) cannot be undone
                raise RuntimeError("nothing to undo")
        return {}

    client = FakeTDClient(scripted={"project/lifecycle": lifecycle})
    result = _txn_result(undo_blocks_opened=2)
    await _rollback(client, result, restore_snapshot=None, undo_block_count=2)
    assert result.rollback_performed is False
    assert result.needs_manual_recovery is True
    assert result.rollback_error is not None


@pytest.mark.asyncio
async def test_rollback_undo_failure_falls_back_to_snapshot_when_no_created_nodes():
    async def restore(_snapshot_id):
        return {"failures": []}

    def undo_fails(params):
        if params.get("action") == "undo":
            raise RuntimeError("nothing to undo")
        return {}

    client = FakeTDClient(scripted={"project/lifecycle": undo_fails})
    result = _txn_result(undo_blocks_opened=1, before_snapshot_id="snap1")
    await _rollback(client, result, restore_snapshot=restore, undo_block_count=1, created_node_paths=())
    assert result.rollback_performed is True
    assert result.rollback_error is None
    assert result.needs_manual_recovery is False


@pytest.mark.asyncio
async def test_rollback_undo_failure_with_created_nodes_refuses_param_only_restore():
    # A param-only snapshot restore cannot delete nodes the transaction created,
    # so it must NOT report a clean rollback — escalate to manual recovery.
    async def restore(_snapshot_id):
        return {"failures": []}

    def undo_fails(params):
        if params.get("action") == "undo":
            raise RuntimeError("nothing to undo")
        return {}

    client = FakeTDClient(scripted={"project/lifecycle": undo_fails})
    result = _txn_result(undo_blocks_opened=1, before_snapshot_id="snap1")
    await _rollback(
        client,
        result,
        restore_snapshot=restore,
        undo_block_count=1,
        created_node_paths=("/p/new",),
    )
    assert result.rollback_performed is False
    assert result.needs_manual_recovery is True


@pytest.mark.asyncio
async def test_rollback_readback_detects_changed_param_still_holding_transaction_value():
    client = FakeTDClient(
        scripted={
            "node/params": {
                "path": "/p/level",
                "parameters": {"opacity": {"value": 0.5}},
            }
        }
    )
    result = _txn_result(undo_blocks_opened=1)

    await _rollback(
        client,
        result,
        restore_snapshot=None,
        undo_block_count=1,
        changed_params=({"path": "/p/level", "name": "opacity", "new": 0.5},),
    )

    assert result.rollback_performed is False
    assert result.needs_manual_recovery is True
    assert result.rollback_verification["changed_params"]["still_changed"] == [
        {"path": "/p/level", "name": "opacity", "value": 0.5}
    ]


@pytest.mark.asyncio
async def test_rollback_readback_detects_stale_param_expression_after_undo():
    client = FakeTDClient(
        scripted={
            "node/params": {
                "path": "/p/level",
                "parameters": {"brightness1": {"value": 0.2, "expr": "op('/p/chop')[0]"}},
            }
        }
    )
    result = _txn_result(undo_blocks_opened=1)

    await _rollback(
        client,
        result,
        restore_snapshot=None,
        undo_block_count=1,
        changed_params=({"path": "/p/level", "name": "brightness1", "new": {"expr": "op('/p/chop')[0]"}},),
    )

    assert result.rollback_performed is False
    assert result.needs_manual_recovery is True
    assert result.rollback_verification["changed_params"]["still_changed"] == [
        {"path": "/p/level", "name": "brightness1", "expr": "op('/p/chop')[0]"}
    ]


@pytest.mark.asyncio
async def test_rollback_readback_detects_table_dat_content_still_live_after_undo():
    # A table-shaped set_dat_content op records `new` as a bare list-of-rows. If
    # TD's undo silently fails, the readback must still flag it — regression: the
    # readback string was compared against the raw list and could never match, so
    # a still-live table-DAT mutation passed as a clean rollback.
    table = [["a", "b"], ["c", "d"]]
    client = FakeTDClient(scripted={"node/content": {"path": "/p/table", "rows": table}})
    result = _txn_result(undo_blocks_opened=1)

    await _rollback(
        client,
        result,
        restore_snapshot=None,
        undo_block_count=1,
        changed_params=({"path": "/p/table", "name": "content", "new": table},),
    )

    assert result.rollback_performed is False
    assert result.needs_manual_recovery is True
    assert result.rollback_verification["changed_params"]["still_changed"] == [
        {"path": "/p/table", "name": "content", "value": "a\tb\nc\td"}
    ]


@pytest.mark.asyncio
async def test_rollback_readback_detects_created_connection_still_present_after_undo():
    def connections(params):
        if params.get("path") == "/p/src":
            return {"path": "/p/src", "outputs": [{"to_path": "/p/out", "from_index": 0, "to_index": 0}]}
        if params.get("path") == "/p/out":
            return {"path": "/p/out", "inputs": [{"from_path": "/p/src", "from_index": 0, "to_index": 0}]}
        return {"path": params.get("path"), "inputs": [], "outputs": []}

    client = FakeTDClient(scripted={"node/connections": connections})
    result = _txn_result(undo_blocks_opened=1)

    await _rollback(
        client,
        result,
        restore_snapshot=None,
        undo_block_count=1,
        connections_made=(("/p/src", "/p/out"),),
    )

    assert result.rollback_performed is False
    assert result.needs_manual_recovery is True
    assert result.rollback_verification["connections"]["remaining"] == [{"from": "/p/src", "to": "/p/out"}]


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
