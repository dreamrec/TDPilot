"""Compile typed patches into one native TD callback, with receipt recovery."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import anyio

from td_mcp.models.patch import PatchOperation, PatchPlan, PatchResult

log = logging.getLogger(__name__)


def expand_operations(plan: PatchPlan, macro_engine=None) -> tuple[list[PatchOperation], list[int]]:
    operations, origins = [], []
    for index, operation in enumerate(plan.operations):
        if operation.kind == "macro":
            if macro_engine is None:
                raise ValueError("Native macro operations require a macro engine")
            expanded = macro_engine.expand_macro(operation, target_root=plan.target_root)
        elif operation.kind == "annotate":
            parent = operation.target or plan.target_root
            name = operation.args.get("name") or "annotation1"
            expanded = [
                PatchOperation(
                    kind="create_node", target=parent, args={"op_type": "annotateCOMP", "name": name}
                ),
                PatchOperation(
                    kind="set_params",
                    target=parent + "/" + name,
                    args={"params": {"text": operation.args["text"]}},
                ),
            ]
        else:
            expanded = [operation]
        operations.extend(expanded)
        origins.extend([index] * len(expanded))
    return operations, origins


async def apply_native(td_client, plan: PatchPlan, result: PatchResult, *, macro_engine=None) -> PatchResult:
    from td_mcp.patch.applier import _record_outcome

    try:
        operations, origins = expand_operations(plan, macro_engine)
        capabilities = await td_client.request("patch/status")
        if capabilities.get("native_atomic") != 1 or not capabilities.get("session"):
            raise ValueError("Upgrade the TD component: native atomic transactions are required")
    except Exception as exc:
        result.status, result.failed_reason = "broken", str(exc)
        return result
    receipt = {"request_id": str(uuid.uuid4()), "session": capabilities["session"]}
    result.native_receipt = receipt
    body = {
        **receipt,
        "target_root": plan.target_root,
        "undo_label": plan.undo_label,
        "operations": [operation.model_dump(mode="json") for operation in operations],
    }
    try:
        response = await td_client.request("patch/apply", body)
        if (
            not isinstance(response, dict)
            or response.get("request_id") != receipt["request_id"]
            or response.get("session") != receipt["session"]
            or response.get("status") not in {"clean", "broken", "rolled_back"}
            or not isinstance(response.get("undo_label"), str)
            or not isinstance(response.get("outcomes"), list)
        ):
            raise RuntimeError("Malformed native transaction receipt; resolving outcome")
        indexes = [entry.get("index") if isinstance(entry, dict) else None for entry in response["outcomes"]]
        failed_index = response.get("failed_op")
        if failed_index is not None:
            indexes.append(failed_index)
        if any(
            isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < len(operations) for i in indexes
        ):
            raise RuntimeError("Invalid operation index in native receipt; resolving outcome")

    except BaseException as exc:
        # The HTTP request may have completed in TD after the caller stopped
        # waiting. Do not send a new apply. Resolve this exact receipt and undo
        # only its owned block, using a bounded cancellation shield.
        recovered = None
        with anyio.move_on_after(20, shield=True):
            try:
                status = await td_client.request("patch/status", receipt)
                if status.get("session") == receipt["session"] and status.get("receipt"):
                    recovered = await td_client.request("patch/rollback", receipt)
            except Exception:
                log.exception("Could not resolve native transaction receipt %s", receipt)
        if not isinstance(exc, Exception):
            log.warning("Cancelled native transaction %s; rollback=%s", receipt, recovered)
            raise
        result.status, result.failed_reason = "broken", str(exc)
        # An explicit application error means rejection before mutation; a
        # transport failure without a receipt remains indeterminate.
        from td_mcp.td_client import TouchDesignerAPIError

        rejected = isinstance(exc, TouchDesignerAPIError) and exc.status_code in (200, 400, 401, 404)
        result.native_rollback = recovered or (
            {"ok": True, "method": "rejected_before_mutation"}
            if rejected
            else {"ok": False, "reason": "Outcome unknown; inspect receipt before any further edits"}
        )
        return result
    result.undo_label = response["undo_label"]
    result.undo_block_opened = bool(response.get("undo_block_opened"))
    result.native_rollback = response.get("rollback")
    result.status = "broken" if response["status"] == "rolled_back" else response["status"]
    failed = response.get("failed_op")
    result.failed_op = origins[failed] if failed is not None else None
    result.failed_reason = response.get("failed_reason")
    if response["status"] == "rolled_back" and not result.failed_reason:
        result.failed_reason = "This transaction receipt has already been rolled back"
    for entry in response.get("outcomes", []):
        index = entry["index"]
        _record_outcome(result, origins[index], operations[index], entry["outcome"])
    result.applied_ops = sorted(set(result.applied_ops))
    if result.failed_reason:
        result.rollback_hint = "Inspect native_rollback; never issue a blind undo."
    return result
