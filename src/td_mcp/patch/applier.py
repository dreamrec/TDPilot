"""PatchPlan → TD application, one undo block, PatchResult output.

See spec §6.2 (flow), §6.3 (nested block detection via sentinel),
§6.4 (per-kind args validation), §6.5 (name-collision readback).
MCP-free: accepts td_client and sentinel by injection.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from td_mcp.models.patch import (
    PatchOperation,
    PatchPlan,
    PatchResult,
    ValidationReport,
)
from td_mcp.patch.undo_sentinel import UndoBlockSentinel
from td_mcp.patch.validator import validate_target

ParamPreflightCallback = Callable[..., Any]


class NestedBlockError(RuntimeError):
    """Raised when apply_plan sees the sentinel already active."""


class PatchOperationArgsError(ValueError):
    """Raised when a PatchOperation.args dict is malformed for its kind."""


# ─── Per-kind argument specs (spec §6.4) ─────────────────────────
_KIND_REQUIRED: dict[str, tuple[str, ...]] = {
    "create_node": ("op_type", "name"),
    "set_params": ("params",),
    "set_dat_content": (),
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
    if op.kind == "set_dat_content":
        if not op.target:
            raise PatchOperationArgsError(f"op[{index}] kind={op.kind}: missing target path")
        if "text" not in op.args and "table" not in op.args:
            raise PatchOperationArgsError(
                f"op[{index}] kind={op.kind}: missing required arg 'text' or 'table'"
            )


async def apply_plan(
    td_client,
    plan: PatchPlan,
    *,
    sentinel: UndoBlockSentinel,
    label: str | None = None,
    auto_validate: bool = True,
    macro_engine=None,
    param_preflight: ParamPreflightCallback | None = None,
    param_semantics_policy: str = "warn",
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

    effective_plan, preflight_info = await _preflight_set_param_ops(
        td_client,
        plan,
        macro_engine=macro_engine,
        param_preflight=param_preflight,
        param_semantics_policy=param_semantics_policy,
    )
    result.safety_warnings.extend(preflight_info.get("safety_warnings", []))
    result.param_semantics_warnings.extend(preflight_info.get("param_semantics_warnings", []))
    if preflight_info.get("blocked"):
        result.status = "broken"
        result.failed_op = preflight_info.get("index")
        result.failed_reason = str(preflight_info.get("reason") or "set_params preflight blocked mutation")
        return result

    sentinel.mark_active(block_label)
    try:
        await td_client.request(
            "project/lifecycle",
            {"action": "start_undo_block", "name": block_label},
        )
        try:
            for i, op in enumerate(effective_plan.operations):
                try:
                    _validate_args(op, i)
                    outcome = await _apply_op(
                        td_client,
                        op,
                        macro_engine=macro_engine,
                        param_semantics_policy=param_semantics_policy,
                    )
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


async def _preflight_set_param_ops(
    td_client,
    plan: PatchPlan,
    *,
    macro_engine=None,
    param_preflight: ParamPreflightCallback | None,
    param_semantics_policy: str,
) -> tuple[PatchPlan, dict[str, Any]]:
    can_preflight_macro = (
        param_semantics_policy == "block"
        and macro_engine is not None
        and hasattr(macro_engine, "preflight_macro")
    )
    if param_preflight is None and not can_preflight_macro:
        return plan, {}

    created_op_types = _created_op_types_by_path(plan)
    operations: list[PatchOperation] = []
    safety_warnings: list[str] = []
    param_semantics_warnings: list[Any] = []

    for index, op in enumerate(plan.operations):
        if param_preflight is not None and op.kind == "annotate" and "text" in op.args:
            params = {"text": str(op.args["text"])}
            preflight = param_preflight(
                path=_predicted_annotate_path(plan, op),
                params=params,
                op_type="annotateCOMP",
                param_semantics_policy=param_semantics_policy,
            )
            safety_warnings.extend(str(item) for item in getattr(preflight, "safety_warnings", []) or [])
            param_semantics_warnings.extend(
                _serialize_param_semantics_warning(item)
                for item in getattr(preflight, "param_semantics_warnings", []) or []
            )
            if bool(getattr(preflight, "blocked", False)):
                return plan, {
                    "blocked": True,
                    "index": index,
                    "reason": "param semantics blocked annotate text preflight",
                    "safety_warnings": safety_warnings,
                    "param_semantics_warnings": param_semantics_warnings,
                }
            adjusted = getattr(preflight, "adjusted_params", params) or params
            operations.append(
                op.model_copy(
                    update={"args": {**op.args, "text": str(dict(adjusted).get("text", params["text"]))}}
                )
            )
            continue

        if op.kind == "macro" and can_preflight_macro and op.args.get("macro_type"):
            preflight = macro_engine.preflight_macro(
                parent_path=op.target or plan.target_root or "/project1",
                macro_type=str(op.args.get("macro_type") or ""),
                name_prefix=op.args.get("name_prefix") or op.args.get("prefix") or None,
                overrides=op.args.get("params"),
                param_semantics_policy=param_semantics_policy,
            )
            safety_warnings.extend(str(item) for item in preflight.get("warnings", []) or [])
            param_semantics_warnings.extend(
                _serialize_param_semantics_warning(item)
                for item in preflight.get("param_semantics_warnings", []) or []
            )
            if bool(preflight.get("blocked")):
                return plan, {
                    "blocked": True,
                    "index": index,
                    "reason": "param semantics blocked macro preflight",
                    "safety_warnings": safety_warnings,
                    "param_semantics_warnings": param_semantics_warnings,
                }
            operations.append(op)
            continue

        if param_preflight is None or op.kind != "set_params" or not isinstance(op.args.get("params"), dict):
            operations.append(op)
            continue
        path = str(op.target or "")
        params = dict(op.args["params"])
        op_type = created_op_types.get(path)
        if op_type is None:
            op_type = await _read_existing_op_type(td_client, path)
        preflight = param_preflight(
            path=path,
            params=params,
            op_type=op_type,
            param_semantics_policy=param_semantics_policy,
        )
        safety_warnings.extend(str(item) for item in getattr(preflight, "safety_warnings", []) or [])
        param_semantics_warnings.extend(
            _serialize_param_semantics_warning(item)
            for item in getattr(preflight, "param_semantics_warnings", []) or []
        )
        if bool(getattr(preflight, "blocked", False)):
            return plan, {
                "blocked": True,
                "index": index,
                "reason": f"param semantics blocked set_params preflight for {path}",
                "safety_warnings": safety_warnings,
                "param_semantics_warnings": param_semantics_warnings,
            }
        adjusted = getattr(preflight, "adjusted_params", params) or params
        operations.append(op.model_copy(update={"args": {**op.args, "params": dict(adjusted)}}))

    return (
        plan.model_copy(update={"operations": operations}),
        {
            "safety_warnings": safety_warnings,
            "param_semantics_warnings": param_semantics_warnings,
        }
        if safety_warnings or param_semantics_warnings
        else {},
    )


def _predicted_annotate_path(plan: PatchPlan, op: PatchOperation) -> str:
    parent = str(op.target or plan.target_root or "/project1").rstrip("/") or "/"
    name = str(op.args.get("name") or "annotation1").strip() or "annotation1"
    return f"{parent}/{name}".replace("//", "/")


def _created_op_types_by_path(plan: PatchPlan) -> dict[str, str]:
    created: dict[str, str] = {}
    for op in plan.operations:
        if op.kind != "create_node":
            continue
        name = str(op.args.get("name") or "").strip()
        op_type = str(op.args.get("op_type") or "").strip()
        if not name or not op_type:
            continue
        parent = str(op.target or plan.target_root or "/project1").rstrip("/")
        created[f"{parent}/{name}"] = op_type
    return created


async def _read_existing_op_type(td_client, path: str) -> str | None:
    if not path:
        return None
    try:
        detail = await td_client.request("node/detail", {"path": path})
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(detail, dict):
        return None
    raw_type = str(detail.get("type") or detail.get("op_type") or detail.get("node_type") or "").strip()
    family = str(detail.get("family") or "").strip().upper()
    if not raw_type:
        return None
    if family and not raw_type.upper().endswith(family):
        return f"{raw_type}{family}"
    return raw_type


def _serialize_param_semantics_warning(item: Any) -> Any:
    if hasattr(item, "model_dump"):
        try:
            return item.model_dump(mode="json")
        except Exception:  # noqa: BLE001
            return str(item)
    return item


async def _apply_op(
    td_client,
    op: PatchOperation,
    *,
    macro_engine=None,
    param_semantics_policy: str = "warn",
) -> dict[str, Any]:
    """Route one operation to its TD endpoint. Returns the response.

    Wire formats are aligned with the legacy MCP tools (see tools_graph.py /
    tools_macros.py) and TD's webserver handlers in
    td_component/mcp_webserver_callbacks.py. Phase 3 model args use friendlier
    aliases (``op_type``/``x``/``y``/``from``/``to``) at the typed layer; we
    translate to the on-the-wire names here.
    """
    if op.kind == "create_node":
        # Mirrors legacy td_create_node (tools_graph.py:308):
        # body uses ``node_type`` / ``nodeX`` / ``nodeY``.
        return (
            await td_client.request(
                "node/create",
                {
                    "parent_path": op.target or "/project1",
                    "node_type": op.args["op_type"],
                    "name": op.args["name"],
                    **({"nodeX": op.args["x"]} if "x" in op.args else {}),
                    **({"nodeY": op.args["y"]} if "y" in op.args else {}),
                },
            )
            or {}
        )
    if op.kind == "set_params":
        # Mirrors legacy td_set_params (tools_graph.py:227):
        # endpoint is ``node/params/set`` (NOT ``nodes/set_params``).
        return (
            await td_client.request(
                "node/params/set",
                {"path": op.target, "params": op.args["params"]},
            )
            or {}
        )
    if op.kind == "set_dat_content":
        body = {"path": op.target}
        if "text" in op.args:
            body["text"] = op.args["text"]
        if "table" in op.args:
            body["table"] = op.args["table"]
        return await td_client.request("node/content/set", body) or {}
    if op.kind == "connect":
        # Mirrors legacy td_connect_nodes (tools_graph.py:415):
        # body uses ``source_path`` / ``target_path`` / ``source_index`` /
        # ``target_index``. Phase 3 args use friendlier aliases.
        return (
            await td_client.request(
                "node/connect",
                {
                    "source_path": op.args["from"],
                    "target_path": op.args["to"],
                    "source_index": op.args.get("from_output", 0),
                    "target_index": op.args.get("to_input", 0),
                },
            )
            or {}
        )
    if op.kind == "layout":
        # TD has no dedicated set-position endpoint, so we route through
        # /api/exec with a minimal one-liner. Restricted exec mode allows
        # this — no imports, no banned tokens. Returns whatever exec
        # returns; the path itself is the readback we record.
        target = op.target
        x = int(op.args["x"])
        y = int(op.args["y"])
        # Use repr() for the path so quoting is correct regardless of
        # special characters; coords are int so they're inline-safe.
        code = f"o = op({target!r})\nif o is not None:\n    o.nodeX = {x}\n    o.nodeY = {y}"
        await td_client.request("exec", {"code": code})
        return {"path": target, "nodeX": x, "nodeY": y}
    if op.kind == "annotate":
        # TD's annotation primitive is ``annotateCOMP`` — a Base COMP variant
        # whose ``text`` parameter holds the annotation body. Two calls:
        # 1) node/create node_type=annotateCOMP
        # 2) node/params/set on the new path with text=<text>
        text = str(op.args["text"])
        create_resp = (
            await td_client.request(
                "node/create",
                {
                    "parent_path": op.target or "/project1",
                    "node_type": "annotateCOMP",
                    "name": op.args.get("name") or "annotation1",
                },
            )
            or {}
        )
        # Extract the actual created path (TD may have suffixed it for
        # collision avoidance — see _record_outcome's nested-shape parsing).
        created_path = None
        if isinstance(create_resp, dict):
            node_info = create_resp.get("node")
            if isinstance(node_info, dict):
                created_path = node_info.get("path")
            created_path = created_path or create_resp.get("path")
        if created_path:
            await td_client.request(
                "node/params/set",
                {"path": created_path, "params": {"text": text}},
            )
        return create_resp
    if op.kind == "macro":
        # TD has no /api/macro/create endpoint — macros are server-side
        # compositions of multiple TD calls (see tools_macros.py). The
        # macro_engine encapsulates that logic. The MCP wrapper
        # td_patch_apply injects the engine via DI; if absent (e.g.
        # called directly without an MCP context), we surface a clear
        # error rather than calling a phantom HTTP endpoint.
        if macro_engine is None:
            raise PatchOperationArgsError(
                f"op kind={op.kind!r} requires macro_engine DI; "
                "this only works through td_patch_apply, not via patch.apply_plan() "
                "called directly without injecting the macro engine."
            )
        result = await macro_engine.create_macro(
            parent_path=op.target or "/project1",
            macro_type=op.args["macro_type"],
            name_prefix=op.args.get("name_prefix") or op.args.get("prefix") or None,
            node_x=int(op.args.get("nodeX", 0)),
            node_y=int(op.args.get("nodeY", 0)),
            overrides=op.args.get("params"),
            param_semantics_policy=str(op.args.get("param_semantics_policy") or param_semantics_policy),
        )
        if isinstance(result, dict) and result.get("blocked"):
            raise PatchOperationArgsError("param semantics blocked macro params")
        if isinstance(result, dict) and result.get("success") is False:
            raise PatchOperationArgsError(str(result.get("error") or "macro creation failed"))
        return result or {}
    raise PatchOperationArgsError(f"unreachable: unknown kind {op.kind!r}")


def _record_outcome(
    result: PatchResult,
    index: int,
    op: PatchOperation,
    outcome: dict[str, Any],
) -> None:
    result.applied_ops.append(index)
    if op.kind in ("create_node", "annotate", "macro"):
        # TD's /api/node/create returns {"success": True, "node": {"path": ..., ...}}
        # — the path lives under the "node" key. Older spec versions of this
        # function looked for top-level "path" and silently lost the readback.
        # Accept either shape so unit tests with simpler scripted responses
        # still work.
        path = None
        if isinstance(outcome, dict):
            node_info = outcome.get("node")
            if isinstance(node_info, dict):
                path = node_info.get("path")
            if not path:
                path = outcome.get("path")
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
    elif op.kind == "set_dat_content":
        result.changed_params.append(
            {
                "path": op.target,
                "name": "content",
                "new": op.args.get("text", op.args.get("table")),
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
