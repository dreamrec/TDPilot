"""PatchPlan → TD application, one undo block, PatchResult output.

See spec §6.2 (flow), §6.3 (nested block detection via sentinel),
§6.4 (per-kind args validation), §6.5 (name-collision readback).
MCP-free: accepts td_client and sentinel by injection.
"""

from __future__ import annotations

from typing import Any

from td_mcp.models.patch import (
    PatchOperation,
    PatchPlan,
    PatchResult,
    ValidationReport,
)
from td_mcp.patch.undo_sentinel import UndoBlockSentinel
from td_mcp.patch.validator import validate_target


class NestedBlockError(RuntimeError):
    """Raised when apply_plan sees the sentinel already active."""


class PatchOperationArgsError(ValueError):
    """Raised when a PatchOperation.args dict is malformed for its kind."""


# ─── Per-kind argument specs (spec §6.4) ─────────────────────────
_KIND_REQUIRED: dict[str, tuple[str, ...]] = {
    "create_node": ("op_type", "name"),
    "set_params": ("params",),
    "connect": ("from", "to"),
    "layout": ("x", "y"),
    "annotate": ("text",),
    "macro": ("macro_type",),
}


def _validate_args(op: PatchOperation, index: int) -> None:
    required = _KIND_REQUIRED[op.kind]
    missing = [k for k in required if k not in op.args]
    if missing:
        raise PatchOperationArgsError(f"op[{index}] kind={op.kind}: missing required arg(s) {missing}")


async def apply_plan(
    td_client,
    plan: PatchPlan,
    *,
    sentinel: UndoBlockSentinel,
    label: str | None = None,
    auto_validate: bool = True,
) -> PatchResult:
    """Apply a PatchPlan inside one TD undo block.

    Raises NestedBlockError if sentinel is already active (caller must
    end the prior block first). Surface-to-caller on per-op failure:
    returns PatchResult with status=broken, undo block still sealed.
    """
    if sentinel.is_active():
        raise NestedBlockError(
            f"prior patch undo block still active ({sentinel.active_label!r}); "
            f"call td_project_lifecycle action=end_undo_block first"
        )

    block_label = label or plan.undo_label
    result = PatchResult(plan_id=plan.id, status="clean", undo_label=block_label)

    sentinel.mark_active(block_label)
    try:
        await td_client.request(
            "project/lifecycle",
            {"action": "start_undo_block", "name": block_label},
        )
        try:
            for i, op in enumerate(plan.operations):
                try:
                    _validate_args(op, i)
                    outcome = await _apply_op(td_client, op)
                    _record_outcome(result, i, op, outcome)
                except Exception as exc:  # noqa: BLE001
                    result.failed_op = i
                    result.failed_reason = str(exc)
                    break
        finally:
            try:
                await td_client.request("project/lifecycle", {"action": "end_undo_block"})
            except Exception:  # noqa: BLE001
                pass
    finally:
        sentinel.mark_inactive()

    _compute_status_and_hint(result)

    if auto_validate and result.status != "broken":
        result.validation = await validate_target(td_client, plan.validation_plan)
        if result.status == "clean" and not result.validation.ok:
            result.status = "warnings"

    return result


async def _apply_op(td_client, op: PatchOperation) -> dict[str, Any]:
    """Route one operation to its TD endpoint. Returns the response."""
    if op.kind == "create_node":
        return (
            await td_client.request(
                "node/create",
                {
                    "parent_path": op.target or "/project1",
                    "op_type": op.args["op_type"],
                    "name": op.args["name"],
                    **({"x": op.args["x"]} if "x" in op.args else {}),
                    **({"y": op.args["y"]} if "y" in op.args else {}),
                },
            )
            or {}
        )
    if op.kind == "set_params":
        return (
            await td_client.request(
                "nodes/set_params",
                {"path": op.target, "params": op.args["params"]},
            )
            or {}
        )
    if op.kind == "connect":
        return (
            await td_client.request(
                "node/connect",
                {
                    "from": op.args["from"],
                    "to": op.args["to"],
                    "from_output": op.args.get("from_output", 0),
                    "to_input": op.args.get("to_input", 0),
                },
            )
            or {}
        )
    if op.kind == "layout":
        return (
            await td_client.request(
                "nodes/set_position",
                {"path": op.target, "x": op.args["x"], "y": op.args["y"]},
            )
            or {}
        )
    if op.kind == "annotate":
        return (
            await td_client.request(
                "node/create",
                {
                    "parent_path": op.target or "/project1",
                    "op_type": "annotate",
                    "name": "annotate1",
                    "annotation_text": op.args["text"],
                },
            )
            or {}
        )
    if op.kind == "macro":
        return (
            await td_client.request(
                "macro/create",
                {
                    "parent_path": op.target or "/project1",
                    "macro_type": op.args["macro_type"],
                    "prefix": op.args.get("prefix", ""),
                },
            )
            or {}
        )
    raise PatchOperationArgsError(f"unreachable: unknown kind {op.kind!r}")


def _record_outcome(
    result: PatchResult,
    index: int,
    op: PatchOperation,
    outcome: dict[str, Any],
) -> None:
    result.applied_ops.append(index)
    if op.kind in ("create_node", "annotate", "macro"):
        path = outcome.get("path") if isinstance(outcome, dict) else None
        if path:
            result.created_paths.append(path)
    elif op.kind == "set_params":
        for name, new_value in op.args.get("params", {}).items():
            result.changed_params.append(
                {
                    "path": op.target,
                    "name": name,
                    "new": new_value,
                }
            )
    elif op.kind == "connect":
        result.connections_made.append((op.args["from"], op.args["to"]))


def _compute_status_and_hint(result: PatchResult) -> None:
    if result.failed_op is not None:
        result.status = "broken"
        result.rollback_hint = (
            f"call td_project_lifecycle action=undo to revert {len(result.applied_ops)} applied op(s)"
        )
    else:
        result.status = "clean"
