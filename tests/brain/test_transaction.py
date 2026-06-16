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
