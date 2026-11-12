from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from td_mcp.macros.engine import MacroEngine
from td_mcp.models.patch import PatchOperation, PatchPlan, PatchResult, ValidationPlan
from td_mcp.patch.native import apply_native, expand_operations
from td_mcp.td_client import TouchDesignerAPIError


def plan():
    return PatchPlan(
        target_root="/project1/test",
        source="operations",
        undo_label="Native",
        validation_plan=ValidationPlan(target_root="/project1/test"),
        operations=[
            PatchOperation(
                kind="create_node", target="/project1/test", args={"op_type": "constantTOP", "name": "a"}
            )
        ],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [asyncio.CancelledError, TimeoutError])
async def test_cancel_or_lost_result_resolves_exact_receipt_and_rolls_back(failure):
    calls = []
    receipt = {}

    async def request(endpoint, body=None):
        calls.append((endpoint, body))
        if endpoint == "patch/status" and body is None:
            return {"native_atomic": 1, "session": "session"}
        if endpoint == "patch/apply":
            receipt.update({"session": body["session"], "request_id": body["request_id"]})
            raise failure()
        if endpoint == "patch/status":
            assert body == receipt
            return {"session": "session", "receipt": {"status": "clean"}}
        if endpoint == "patch/rollback":
            assert body == receipt
            return {"ok": True, "method": "native_undo_exact_state"}
        raise AssertionError(endpoint)

    client = type("Client", (), {"request": staticmethod(request)})()
    p = plan()
    result = PatchResult(plan_id=p.id, status="clean", undo_label=p.undo_label)
    if failure is asyncio.CancelledError:
        with pytest.raises(asyncio.CancelledError):
            await apply_native(client, p, result)
    else:
        result = await apply_native(client, p, result)
        assert result.native_rollback["ok"]
    assert [c[0] for c in calls] == ["patch/status", "patch/apply", "patch/status", "patch/rollback"]


@pytest.mark.asyncio
async def test_unknown_outcome_never_reports_noop_rollback():
    client = type(
        "Client",
        (),
        {
            "request": AsyncMock(
                side_effect=[
                    {"native_atomic": 1, "session": "session"},
                    TimeoutError(),
                    {"session": "session", "receipt": None},
                ]
            )
        },
    )()
    p = plan()
    result = await apply_native(client, p, PatchResult(plan_id=p.id, status="clean", undo_label=p.undo_label))
    assert not result.native_rollback["ok"]
    assert result.native_receipt
    assert result.status == "broken"


@pytest.mark.asyncio
async def test_old_td_component_fails_before_any_mutation():
    client = type(
        "Client", (), {"request": AsyncMock(side_effect=TouchDesignerAPIError("Unknown endpoint", 404))}
    )()
    p = plan()
    result = await apply_native(client, p, PatchResult(plan_id=p.id, status="clean", undo_label=p.undo_label))
    assert result.status == "broken"
    assert not result.undo_block_opened
    client.request.assert_awaited_once_with("patch/status")


def test_macro_expansion_is_typed_and_does_not_dispatch_http():
    client = type("Client", (), {"request": AsyncMock()})()
    engine = MacroEngine(client)
    p = plan().model_copy(
        update={
            "operations": [
                PatchOperation(
                    kind="macro",
                    target="/project1/test",
                    args={"macro_type": "feedback_loop", "name_prefix": "safe"},
                )
            ]
        }
    )
    expanded, origins = expand_operations(p, engine)
    assert len(expanded) > 3
    assert set(origins) == {0}
    assert all(o.kind != "macro" for o in expanded)
    assert any(o.kind == "connect" for o in expanded)
    client.request.assert_not_called()
