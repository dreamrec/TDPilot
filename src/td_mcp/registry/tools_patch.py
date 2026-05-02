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

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field, ValidationError

from td_mcp import patch
from td_mcp import tool_registry as _tr  # intentional cycle — see registry/__init__.py
from td_mcp.errors import format_tool_error
from td_mcp.models.patch import PatchPlan, PatchPreview, ValidationPlan
from td_mcp.tool_registry import mcp


@mcp.tool(name="td_patch_plan")
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
        return {"success": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        _tr._record_tool_error(ctx, "td_patch_plan")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_patch_preview")
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
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_patch_apply")
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
) -> dict[str, Any]:
    """Apply a PatchPlan in one undo block. Surface-to-caller on failure (no auto-rollback)."""
    finish = _tr._start_tool(ctx, "td_patch_apply")
    try:
        try:
            parsed = PatchPlan.model_validate(plan)
        except ValidationError as exc:
            return {"success": False, "error": f"invalid plan: {exc}"}
        client = _tr._get_client(ctx)
        # Inject the macro engine so kind=macro ops can route through the
        # server-side composition path (TD has no /api/macro/create endpoint).
        # If the engine isn't available (rare — only if services aren't
        # configured), pass None and let the applier surface a clear error
        # for any kind=macro op it encounters.
        services = _tr._get_services(ctx)
        macro_engine = getattr(services, "macro_engine", None)
        try:
            result = await patch.apply_plan(
                client,
                parsed,
                sentinel=_tr._PATCH_SENTINEL,
                label=label,
                auto_validate=auto_validate,
                macro_engine=macro_engine,
            )
        except patch.NestedBlockError as exc:
            return {"success": False, "error": str(exc)}
        _tr._audit_log(
            ctx,
            "td_patch_apply",
            {"plan_id": parsed.id, "status": result.status, "ops": len(result.applied_ops)},
        )
        return {"success": True, "result": result.model_dump(mode="json")}
    except Exception as exc:  # noqa: BLE001
        _tr._record_tool_error(ctx, "td_patch_apply")
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_patch_validate")
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
        return format_tool_error(exc)
    finally:
        finish()


@mcp.tool(name="td_patch_variations")
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
        return format_tool_error(exc)
    finally:
        finish()
