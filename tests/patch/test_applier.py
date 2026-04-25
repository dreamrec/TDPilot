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
            "cooking": {"total_cook_ms": 1.0, "stuck": []},
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
            "cooking": {"total_cook_ms": 0.1, "stuck": []},
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
            "cooking": {"total_cook_ms": 0.2, "stuck": []},
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


# ─── Wire-format tests (v1.5.1) ─────────────────────────────────────
# These pin the on-the-wire endpoint paths and body field names against
# what TD's actual /api/* handlers expect. Caught the v1.5.0 → v1.5.1
# wire-mismatch surface that unit tests with permissive FakeTDClient
# scripts had let through.


@pytest.mark.asyncio
async def test_set_params_uses_node_params_set_endpoint():
    """v1.5.1: set_params dispatches to ``node/params/set``, not the
    fictional ``nodes/set_params`` from the v1.5.0 spec."""
    ops = [PatchOperation(kind="set_params", target="/p/n", args={"params": {"period": 0.5}})]
    client = FakeTDClient(
        scripted={
            "node/params/set": {"ok": True},
            "node/errors": {"issues": []},
            "cooking": {},
        }
    )
    sentinel = UndoBlockSentinel()
    result = await apply_plan(client, _plan(ops), sentinel=sentinel)
    assert result.status == "clean"
    set_calls = [c for c in client.calls if c[0] == "node/params/set"]
    assert len(set_calls) == 1
    body = set_calls[0][1]
    assert body == {"path": "/p/n", "params": {"period": 0.5}}


@pytest.mark.asyncio
async def test_connect_uses_source_target_path_fields():
    """v1.5.1: connect body uses ``source_path`` / ``target_path`` /
    ``source_index`` / ``target_index`` matching TD's handle_connect_nodes."""
    ops = [
        PatchOperation(
            kind="connect",
            target="/p",
            args={"from": "/p/a", "to": "/p/b", "from_output": 1, "to_input": 0},
        )
    ]
    client = FakeTDClient(
        scripted={
            "node/connect": {"ok": True},
            "node/errors": {"issues": []},
            "cooking": {},
        }
    )
    sentinel = UndoBlockSentinel()
    result = await apply_plan(client, _plan(ops), sentinel=sentinel)
    assert result.status == "clean"
    body = next(c[1] for c in client.calls if c[0] == "node/connect")
    assert body == {
        "source_path": "/p/a",
        "target_path": "/p/b",
        "source_index": 1,
        "target_index": 0,
    }


@pytest.mark.asyncio
async def test_layout_uses_exec_endpoint():
    """v1.5.1: layout has no dedicated TD endpoint — routes through /api/exec
    to set ``op.nodeX`` / ``op.nodeY`` directly."""
    ops = [PatchOperation(kind="layout", target="/p/n", args={"x": 100, "y": 200})]
    client = FakeTDClient(
        scripted={
            "exec": {"ok": True},
            "node/errors": {"issues": []},
            "cooking": {},
        }
    )
    sentinel = UndoBlockSentinel()
    result = await apply_plan(client, _plan(ops), sentinel=sentinel)
    assert result.status == "clean"
    exec_calls = [c for c in client.calls if c[0] == "exec"]
    assert len(exec_calls) == 1
    code = exec_calls[0][1]["code"]
    assert "/p/n" in code
    assert ".nodeX = 100" in code
    assert ".nodeY = 200" in code


@pytest.mark.asyncio
async def test_annotate_creates_annotateCOMP():
    """v1.5.1: annotate uses ``node/create`` with ``node_type=annotateCOMP``
    then sets the text via a follow-up ``node/params/set`` call."""
    ops = [PatchOperation(kind="annotate", target="/p", args={"text": "hello"})]
    client = FakeTDClient(
        scripted={
            "node/create": lambda p: {
                "success": True,
                "node": {"path": "/p/" + p["name"], "name": p["name"]},
            },
            "node/params/set": {"ok": True},
            "node/errors": {"issues": []},
            "cooking": {},
        }
    )
    sentinel = UndoBlockSentinel()
    result = await apply_plan(client, _plan(ops), sentinel=sentinel)
    assert result.status == "clean"
    create_body = next(c[1] for c in client.calls if c[0] == "node/create")
    assert create_body["node_type"] == "annotateCOMP"
    set_body = next(c[1] for c in client.calls if c[0] == "node/params/set")
    assert set_body["params"] == {"text": "hello"}


@pytest.mark.asyncio
async def test_macro_requires_macro_engine_di():
    """v1.5.1: kind=macro raises if macro_engine isn't injected — TD has
    no /api/macro/create endpoint, so direct apply_plan() invocations
    (e.g., scripts that don't go through td_patch_apply) can't dispatch
    macros and we surface that clearly rather than calling a phantom
    HTTP endpoint."""
    ops = [PatchOperation(kind="macro", target="/p", args={"macro_type": "feedback_loop"})]
    client = FakeTDClient()
    sentinel = UndoBlockSentinel()
    result = await apply_plan(client, _plan(ops), sentinel=sentinel, auto_validate=False)
    assert result.status == "broken"
    assert "macro_engine" in (result.failed_reason or "")


@pytest.mark.asyncio
async def test_macro_dispatches_through_macro_engine():
    """v1.5.1: when macro_engine is injected, kind=macro routes to
    engine.create_macro(...) with the spec'd kwargs. No phantom HTTP."""

    class FakeMacroEngine:
        def __init__(self):
            self.calls = []

        async def create_macro(self, **kwargs):
            self.calls.append(kwargs)
            return {"path": "/p/feedback_macro", "created": ["/p/feedback_macro/inner"]}

    engine = FakeMacroEngine()
    ops = [
        PatchOperation(
            kind="macro",
            target="/p",
            args={"macro_type": "feedback_loop", "name_prefix": "fb"},
        )
    ]
    client = FakeTDClient(scripted={"node/errors": {"issues": []}, "cooking": {}})
    sentinel = UndoBlockSentinel()
    result = await apply_plan(client, _plan(ops), sentinel=sentinel, macro_engine=engine)
    assert result.status == "clean"
    assert len(engine.calls) == 1
    assert engine.calls[0]["macro_type"] == "feedback_loop"
    assert engine.calls[0]["parent_path"] == "/p"
    assert engine.calls[0]["name_prefix"] == "fb"
    # No phantom macro/create HTTP calls.
    macro_http = [c for c in client.calls if c[0] == "macro/create"]
    assert macro_http == []
