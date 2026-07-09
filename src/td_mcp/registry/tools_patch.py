"""Patch Session MCP tools (Phase 3, v1.5.0).

Tools in this module (5):
    td_patch_plan        — build typed PatchPlan from intent/recipe/operations
    td_patch_preview     — human-readable + live_risk_flags (no mutation)
    td_patch_apply       — execute one undo block; returns PatchResult
    td_patch_validate    — composite errors + cook + frame checks on a subtree
    td_patch_variations  — derive N variants from a base PatchPlan

Thin delegators to src/td_mcp/patch/. The patch package is MCP-free;
this module adapts MCP Context + envelopes to the patch/* async API.

See docs/superpowers/specs/2026-04-24-v1.5.0-phase-3-patch-session-design.md
§5 for tool signatures.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations
from pydantic import Field, ValidationError

from td_mcp import patch
from td_mcp import tool_registry as _tr  # intentional cycle — see registry/__init__.py
from td_mcp.brain.param_semantics import validate_patch_plan_parameter_contract
from td_mcp.brain.transaction import apply_transaction
from td_mcp.errors import format_tool_error_dict
from td_mcp.models.brain import TransactionOptions
from td_mcp.models.patch import PatchPlan, PatchPreview, ValidationPlan
from td_mcp.tool_registry import mcp


def _direct_param_preflight(ctx: Context):
    return _tr._direct_param_preflight_callback(ctx)


@mcp.tool(
    name="td_patch_plan",
    title="Plan Legacy TD Patch",
    description=(
        "(Legacy — prefer td_brain_plan → td_brain_execute; slated for removal in v3.0.) "
        "Compatibility/expert surface for typed PatchPlan construction. For new concept-to-network "
        "TouchDesigner builds, prefer td_brain_plan followed by td_brain_execute."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=False, openWorldHint=True
    ),
)
async def td_patch_plan(
    ctx: Context,
    target_root: Annotated[
        str,
        Field(description="Absolute TD path the plan operates on, e.g. '/project1'", min_length=1),
    ],
    intent: Annotated[
        str | None,
        Field(default=None, description="Free-text goal; triggers heuristic macro match"),
    ] = None,
    recipe_id: Annotated[
        str | None,
        Field(default=None, description="Technique/recipe ID to materialize into a plan"),
    ] = None,
    operations: Annotated[
        list[dict[str, Any]] | None,
        Field(default=None, description="Pre-built operation list (LLM-authored)"),
    ] = None,
    undo_label: Annotated[
        str | None,
        Field(default=None, description="Override for the TD undo block label"),
    ] = None,
) -> dict[str, Any]:
    """Build a typed PatchPlan. Exactly one of intent/recipe_id/operations required."""
    finish = _tr._start_tool(ctx, "td_patch_plan")
    try:
        client = _tr._get_client(ctx)
        services = _tr._get_services(ctx)
        store = _tr._get_technique_store(ctx)
        card_index = getattr(services, "card_index", None)

        plan = await patch.build_plan(
            td_client=client,
            target_root=target_root,
            intent=intent,
            recipe_id=recipe_id,
            operations=operations,
            undo_label=undo_label,
            technique_store=store,
            card_index=card_index,
        )
        _tr._audit_log(ctx, "td_patch_plan", {"plan_id": plan.id, "source": plan.source})
        return {"success": True, "plan": plan.model_dump(mode="json")}
    except ValueError as exc:
        return format_tool_error_dict(exc)
    except Exception as exc:  # noqa: BLE001
        _tr._record_tool_error(ctx, "td_patch_plan")
        return format_tool_error_dict(exc)
    finally:
        finish()


@mcp.tool(
    name="td_patch_preview",
    title="Preview Legacy TD Patch",
    description=(
        "(Legacy — prefer td_brain_plan → td_brain_execute; slated for removal in v3.0.) "
        "Read-only PatchPlan preview for compatibility/expert workflows. For new visual builds, "
        "prefer td_brain_plan because it carries concept, corpus, and validation context."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=False, openWorldHint=True
    ),
)
async def td_patch_preview(
    ctx: Context,
    plan: Annotated[
        dict[str, Any],
        Field(description="PatchPlan dict (from td_patch_plan)"),
    ],
    include_hints: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "If True, attach a ``hints`` block via td_get_hints. "
                "Auto-injection still fires when the plan touches feedback, "
                "GLSL, or audio-reactive territory."
            ),
        ),
    ] = False,
) -> dict[str, Any]:
    """Preview what a patch will change. Checks live state; does not mutate."""
    finish = _tr._start_tool(ctx, "td_patch_preview")
    try:
        try:
            parsed = PatchPlan.model_validate(plan)
        except ValidationError as exc:
            return {"success": False, "error": f"invalid plan: {exc}"}
        client = _tr._get_client(ctx)
        preview_dict = await patch.preview_plan(client, parsed)
        preview = PatchPreview(**preview_dict)
        _tr._audit_log(ctx, "td_patch_preview", {"plan_id": parsed.id})
        result = {"success": True, "preview": preview.model_dump(mode="json")}
        return _tr._attach_hints(
            result,
            tool_name="td_patch_preview",
            payload={"plan": plan},
            force_query={"intent": "patch preview"} if include_hints else None,
        )
    except Exception as exc:  # noqa: BLE001
        _tr._record_tool_error(ctx, "td_patch_preview")
        return format_tool_error_dict(exc)
    finally:
        finish()


@mcp.tool(
    name="td_patch_apply",
    title="Apply Legacy TD Patch",
    description=(
        "(Legacy — prefer td_brain_plan → td_brain_execute; slated for removal in v3.0.) "
        "Destructive compatibility/expert PatchPlan executor. Prefer td_brain_execute for BrainPlans "
        "because it is the default validated transaction path for TDPilot-authored builds."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True
    ),
)
async def td_patch_apply(
    ctx: Context,
    plan: Annotated[
        dict[str, Any],
        Field(description="PatchPlan dict to execute"),
    ],
    label: Annotated[
        str | None,
        Field(default=None, description="Override plan.undo_label"),
    ] = None,
    auto_validate: Annotated[
        bool,
        Field(default=True, description="Run validate_target after apply"),
    ] = True,
    transaction_options: Annotated[
        dict[str, Any] | None,
        Field(
            default=None,
            description=(
                "Optional TransactionOptions dict. When provided, td_patch_apply uses the "
                "vNext transaction executor with preflight, snapshot, validation, and rollback policy."
            ),
        ),
    ] = None,
    param_semantics_policy: Annotated[
        Literal["warn", "block"],
        Field(
            default="warn",
            description=(
                "Docs-grounded parameter safety policy for legacy patch applies. "
                "'warn' preserves legacy behavior and attaches findings; 'block' refuses "
                "invalid or high-risk set_params operations before mutation."
            ),
        ),
    ] = "warn",
) -> dict[str, Any]:
    """Apply a PatchPlan in one undo block, optionally through the transaction executor."""
    finish = _tr._start_tool(ctx, "td_patch_apply")
    try:
        try:
            parsed = PatchPlan.model_validate(plan)
        except ValidationError as exc:
            return {"success": False, "error": f"invalid plan: {exc}"}
        if label:
            parsed = parsed.model_copy(update={"undo_label": label})
        param_semantics_issues = validate_patch_plan_parameter_contract(parsed)
        if param_semantics_policy == "block" and param_semantics_issues:
            _tr._audit_log(
                ctx,
                "td_patch_apply",
                {
                    "plan_id": parsed.id,
                    "ops": len(parsed.operations),
                    "param_semantics_warning_count": len(param_semantics_issues),
                    "param_semantics_policy": param_semantics_policy,
                    "blocked": True,
                },
            )
            return {
                "success": False,
                "blocked": True,
                "param_semantics_status": "blocked",
                "param_semantics_warnings": [
                    issue.model_dump(mode="json") for issue in param_semantics_issues
                ],
            }
        client = _tr._get_client(ctx)
        # Inject the macro engine so kind=macro ops can route through the
        # server-side composition path (TD has no /api/macro/create endpoint).
        # If the engine isn't available (rare — only if services aren't
        # configured), pass None and let the applier surface a clear error
        # for any kind=macro op it encounters.
        services = _tr._get_services(ctx)
        macro_engine = getattr(services, "macro_engine", None)
        if transaction_options is not None:
            try:
                tx_options = TransactionOptions.model_validate(transaction_options)
            except ValidationError as exc:
                return {"success": False, "error": f"invalid transaction_options: {exc}"}
            result = await _apply_patch_transaction(
                ctx,
                parsed,
                tx_options,
                macro_engine=macro_engine,
                param_preflight=_direct_param_preflight(ctx),
                param_semantics_policy=param_semantics_policy,
            )
            _tr._audit_log(
                ctx,
                "td_patch_apply",
                {
                    "plan_id": parsed.id,
                    "status": result.status,
                    "ops": len(parsed.operations),
                    "transaction": True,
                },
            )
            return {
                "success": result.status in {"clean", "warnings", "dry_run"},
                "result": result.model_dump(mode="json"),
            }
        try:
            result = await patch.apply_plan(
                client,
                parsed,
                sentinel=_tr._PATCH_SENTINEL,
                label=label,
                auto_validate=auto_validate,
                macro_engine=macro_engine,
                param_preflight=_direct_param_preflight(ctx),
                param_semantics_policy=param_semantics_policy,
            )
        except patch.NestedBlockError as exc:
            return {"success": False, "error": str(exc)}
        _tr._audit_log(
            ctx,
            "td_patch_apply",
            {
                "plan_id": parsed.id,
                "status": result.status,
                "ops": len(result.applied_ops),
                "param_semantics_warning_count": len(param_semantics_issues),
                "param_semantics_policy": param_semantics_policy,
            },
        )
        payload = {
            "success": result.status in {"clean", "warnings"},
            "result": result.model_dump(mode="json"),
        }
        if result.status == "broken" and result.param_semantics_warnings:
            payload["blocked"] = True
            payload["param_semantics_status"] = "blocked"
            payload["param_semantics_warnings"] = result.param_semantics_warnings
        if param_semantics_issues:
            payload["param_semantics_status"] = "warnings"
            payload["param_semantics_warnings"] = [
                issue.model_dump(mode="json") for issue in param_semantics_issues
            ]
        return payload
    except Exception as exc:  # noqa: BLE001
        _tr._record_tool_error(ctx, "td_patch_apply")
        return format_tool_error_dict(exc)
    finally:
        finish()


async def _apply_patch_transaction(
    ctx: Context,
    plan: PatchPlan,
    options: TransactionOptions,
    *,
    macro_engine=None,
    param_preflight=None,
    param_semantics_policy: str = "warn",
):
    client = _tr._get_client(ctx)

    async def create_snapshot(path: str) -> str | None:
        payload = await _tr._capture_snapshot_payload(ctx, path=path, include_visual=False)
        saved = _tr._get_snapshot_manager(ctx).add_snapshot(
            payload,
            name=f"patch_tx_{plan.id[:8]}",
        )
        return saved.get("snapshot_id")

    async def restore_snapshot(snapshot_id: str) -> dict[str, Any] | None:
        manager = _tr._get_snapshot_manager(ctx)
        snapshot = manager.get_snapshot(snapshot_id)
        if snapshot is None:
            return {"failures": [{"error": f"snapshot not found: {snapshot_id}"}]}
        nodes = snapshot.get("snapshot", {}).get("nodes", {})
        if not isinstance(nodes, dict):
            nodes = {}
        return await _tr._restore_snapshot_nodes(
            client,
            _tr._get_safety_manager(ctx),
            nodes,
            partial_filters=[],
            dry_run=False,
        )

    return await apply_transaction(
        client,
        plan,
        options=options.model_copy(
            update={
                "param_semantics_policy": (
                    param_semantics_policy
                    if param_semantics_policy != "warn"
                    else options.param_semantics_policy
                )
            }
        ),
        sentinel=_tr._PATCH_SENTINEL,
        macro_engine=macro_engine,
        create_snapshot=create_snapshot,
        restore_snapshot=restore_snapshot,
        param_preflight=param_preflight,
    )


@mcp.tool(
    name="td_patch_validate",
    title="Validate TD Patch Target",
    description=(
        "(Legacy — prefer td_brain_plan → td_brain_execute; slated for removal in v3.0.) "
        "Read-only validation for patch compatibility workflows. BrainPlan workflows should use "
        "td_brain_plan and td_brain_execute so validation is tied to the authored plan."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=False, openWorldHint=True
    ),
)
async def td_patch_validate(
    ctx: Context,
    target_root: Annotated[
        str,
        Field(description="Subtree to validate", min_length=1),
    ],
    capture_frames: Annotated[
        list[str] | None,
        Field(default=None, description="TOP paths to capture; None = none (cheap)"),
    ] = None,
) -> dict[str, Any]:
    """Composite errors + cook + optional frame captures on a TD subtree."""
    finish = _tr._start_tool(ctx, "td_patch_validate")
    try:
        client = _tr._get_client(ctx)
        plan = ValidationPlan(
            target_root=target_root,
            capture_frames=capture_frames or [],
        )
        report = await patch.validate_target(client, plan)
        _tr._audit_log(
            ctx,
            "td_patch_validate",
            {"target_root": target_root, "ok": report.ok, "errors": len(report.errors)},
        )
        return {"success": True, "report": report.model_dump(mode="json")}
    except Exception as exc:  # noqa: BLE001
        _tr._record_tool_error(ctx, "td_patch_validate")
        return format_tool_error_dict(exc)
    finally:
        finish()


@mcp.tool(
    name="td_patch_variations",
    title="Vary Legacy TD Patch",
    description=(
        "(Legacy — prefer td_brain_plan → td_brain_execute; slated for removal in v3.0.) "
        "Generate PatchPlan variants for compatibility/expert workflows. For new creative builds, "
        "start with td_brain_plan so variants remain grounded in a BrainPlan."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=False, openWorldHint=False
    ),
)
async def td_patch_variations(
    ctx: Context,
    plan: Annotated[
        dict[str, Any],
        Field(description="Base PatchPlan dict to derive variants from"),
    ],
    n: Annotated[
        int,
        Field(default=3, ge=1, le=6, description="Number of variants"),
    ] = 3,
    strategies: Annotated[
        list[str] | None,
        Field(default=None, description="None defaults to ['param_jitter']"),
    ] = None,
    seed: Annotated[
        int | None,
        Field(default=None, description="RNG seed; None = random"),
    ] = None,
) -> dict[str, Any]:
    """Generate N PatchVariants from a base plan using the given strategies."""
    finish = _tr._start_tool(ctx, "td_patch_variations")
    try:
        try:
            parsed = PatchPlan.model_validate(plan)
        except ValidationError as exc:
            return {"success": False, "error": f"invalid plan: {exc}"}
        strategies_eff = strategies or ["param_jitter"]
        try:
            variants, skipped = patch.generate_variants(parsed, n, strategies_eff, seed)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        _tr._audit_log(
            ctx,
            "td_patch_variations",
            {"plan_id": parsed.id, "count": len(variants), "strategies": strategies_eff},
        )
        return {
            "success": True,
            "variants": [v.model_dump(mode="json") for v in variants],
            "skipped_strategies": skipped,
        }
    except Exception as exc:  # noqa: BLE001
        _tr._record_tool_error(ctx, "td_patch_variations")
        return format_tool_error_dict(exc)
    finally:
        finish()
