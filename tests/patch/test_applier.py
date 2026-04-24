"""Tests for src/td_mcp/patch/applier.py."""

from __future__ import annotations

import pytest

from patch.conftest import FakeTDClient
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan
from td_mcp.patch.applier import (
    NestedBlockError,
    PatchOperationArgsError,
    apply_plan,
)
from td_mcp.patch.undo_sentinel import UndoBlockSentinel


def _plan(ops, target_root="/p", capture_frames=None):
    return PatchPlan(
        target_root=target_root,
        source="operations",
        operations=ops,
        undo_label="test patch",
        validation_plan=ValidationPlan(target_root=target_root, capture_frames=capture_frames or []),
    )


@pytest.mark.asyncio
async def test_clean_apply_three_ops():
    # Create 2 nodes + set params on first. All succeed.
    ops = [
        PatchOperation(kind="create_node", target="/p", args={"op_type": "noise", "name": "n1"}),
        PatchOperation(kind="create_node", target="/p", args={"op_type": "level", "name": "l1"}),
        PatchOperation(kind="set_params", target="/p/n1", args={"params": {"amp": 0.5}}),
    ]
    client = FakeTDClient(
        scripted={
            "node/create": lambda p: {"path": f"/p/{p['name']}", "name": p["name"]},
            "nodes/set_params": {"ok": True},
            "node/errors": {"issues": []},
            "cooking_info": {"total_cook_ms": 1.0, "stuck": []},
        }
    )
    sentinel = UndoBlockSentinel()
    result = await apply_plan(client, _plan(ops), sentinel=sentinel)

    assert result.status == "clean"
    assert result.applied_ops == [0, 1, 2]
    assert result.failed_op is None
    assert "/p/n1" in result.created_paths
    assert "/p/l1" in result.created_paths
    assert sentinel.is_active() is False  # released after run


@pytest.mark.asyncio
async def test_op_n_fails_seals_block():
    # op 2 of 4 raises. Expected status=broken, applied_ops=[0,1], failed_op=2.
    ops = [
        PatchOperation(kind="create_node", target="/p", args={"op_type": "n", "name": "a"}),
        PatchOperation(kind="create_node", target="/p", args={"op_type": "n", "name": "b"}),
        PatchOperation(kind="create_node", target="/p", args={"op_type": "n", "name": "c"}),
        PatchOperation(kind="create_node", target="/p", args={"op_type": "n", "name": "d"}),
    ]
    call_count = {"n": 0}

    def create_response(params):
        call_count["n"] += 1
        if call_count["n"] == 3:
            raise RuntimeError("TD backend exploded on c")
        return {"path": f"/p/{params['name']}", "name": params["name"]}

    client = FakeTDClient(scripted={"node/create": create_response})
    sentinel = UndoBlockSentinel()
    result = await apply_plan(client, _plan(ops), sentinel=sentinel, auto_validate=False)

    assert result.status == "broken"
    assert result.applied_ops == [0, 1]
    assert result.failed_op == 2
    assert "TD backend exploded" in (result.failed_reason or "")
    assert result.rollback_hint is not None
    # Verify undo block was ended (seal invariant)
    end_calls = [
        c
        for c in client.calls
        if c[0] == "project/lifecycle" and c[1] and c[1].get("action") == "end_undo_block"
    ]
    assert len(end_calls) == 1
    assert sentinel.is_active() is False


@pytest.mark.asyncio
async def test_bad_args_raises_before_td():
    # set_params op missing required "params" key → PatchOperationArgsError,
    # never touches TD.
    ops = [PatchOperation(kind="set_params", target="/p/n", args={})]
    client = FakeTDClient()
    sentinel = UndoBlockSentinel()

    result = await apply_plan(client, _plan(ops), sentinel=sentinel, auto_validate=False)
    assert result.status == "broken"
    assert result.failed_op == 0
    assert "missing required arg" in (result.failed_reason or "")
    # No params endpoint hit (but start/end undo block calls will be there)
    td_calls = [c for c in client.calls if c[0] not in ("project/lifecycle",)]
    assert td_calls == []


@pytest.mark.asyncio
async def test_nested_block_refused():
    ops = [PatchOperation(kind="create_node", args={"op_type": "n", "name": "a"})]
    client = FakeTDClient()
    sentinel = UndoBlockSentinel()
    sentinel.mark_active("someone else's block")

    with pytest.raises(NestedBlockError):
        await apply_plan(client, _plan(ops), sentinel=sentinel)
    # No TD calls at all
    assert client.calls == []


@pytest.mark.asyncio
async def test_name_collision_readback():
    ops = [PatchOperation(kind="create_node", target="/p", args={"op_type": "noise", "name": "noise1"})]
    client = FakeTDClient(
        scripted={
            "node/create": lambda p: {"path": "/p/noise2", "name": "noise2"},
            "node/errors": {"issues": []},
            "cooking_info": {"total_cook_ms": 0.1, "stuck": []},
        }
    )
    sentinel = UndoBlockSentinel()
    result = await apply_plan(client, _plan(ops), sentinel=sentinel)
    # Must record actual path, not requested name
    assert result.created_paths == ["/p/noise2"]


@pytest.mark.asyncio
async def test_auto_validate_promotes_to_warnings():
    ops = [PatchOperation(kind="create_node", target="/p", args={"op_type": "n", "name": "x"})]
    client = FakeTDClient(
        scripted={
            "node/create": lambda p: {"path": "/p/x", "name": "x"},
            "node/errors": {"issues": [{"node": "/p/x", "message": "something stinks"}]},
            "cooking_info": {"total_cook_ms": 0.2, "stuck": []},
        }
    )
    sentinel = UndoBlockSentinel()
    result = await apply_plan(client, _plan(ops), sentinel=sentinel, auto_validate=True)
    assert result.status == "warnings"
    assert result.validation is not None
    assert result.validation.ok is False


@pytest.mark.asyncio
async def test_auto_validate_skipped_on_broken():
    # If apply breaks, validation should NOT run (state is mid-corrupt).
    ops = [PatchOperation(kind="set_params", args={})]  # bad args → fail
    client = FakeTDClient()
    sentinel = UndoBlockSentinel()
    result = await apply_plan(client, _plan(ops), sentinel=sentinel, auto_validate=True)
    assert result.status == "broken"
    assert result.validation is None
    err_calls = [c for c in client.calls if c[0] == "node/errors"]
    assert err_calls == []
