"""Brain and transaction tools for correctness-first TD task execution."""

from __future__ import annotations

import json
import time
from typing import Annotated, Any
from urllib.parse import quote

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations
from pydantic import Field, ValidationError

from td_mcp import tool_registry as _tr
from td_mcp.brain.cockpit import COCKPIT_RESOURCE_URI, build_cockpit_payload
from td_mcp.brain.patterns import load_pattern_registry
from td_mcp.brain.planner import build_brain_plan
from td_mcp.brain.trace_promotion import (
    promote_trace_to_pattern,
    trace_promotion_rejection_evidence,
)
from td_mcp.brain.traces import append_brain_trace
from td_mcp.brain.transaction import apply_transaction
from td_mcp.errors import format_tool_error_dict
from td_mcp.models.brain import BrainPlan, BrainTrace, TransactionOptions
from td_mcp.models.patch import PatchPlan
from td_mcp.registry.resources import get_cached_resource, set_cached_resource
from td_mcp.tool_registry import mcp


def _direct_param_preflight(ctx: Context):
    return _tr._direct_param_preflight_callback(ctx)


@mcp.tool(
    name="td_brain_plan",
    title="Plan TD Brain Task",
    description=(
        "Use this when the user asks TDPilot to build or debug a real TouchDesigner visual "
        "system and you need a grounded, non-mutating concept graph plus typed patch plan."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=False, openWorldHint=True
    ),
    meta={"anthropic/alwaysLoad": True},
    structured_output=True,
)
async def td_brain_plan(
    ctx: Context,
    intent: Annotated[
        str,
        Field(description="Natural-language visual programming task.", min_length=1),
    ],
    target_root: Annotated[
        str,
        Field(default="/project1", description="Absolute TD parent/root path to plan inside."),
    ] = "/project1",
    output_top: Annotated[
        str | None,
        Field(default=None, description="Optional TOP path expected to show final visual output."),
    ] = None,
    constraints: Annotated[
        dict[str, Any] | None,
        Field(
            default=None,
            description="Optional hard constraints, e.g. palette, FPS, node count, or operators.",
        ),
    ] = None,
    preferred_domains: Annotated[
        list[str] | None,
        Field(default=None, description="Preferred TD data domains: TOP, CHOP, SOP, POP, DAT, COMP, MAT."),
    ] = None,
    validation_profile: Annotated[
        str,
        Field(default="auto", description="Validation profile. 'auto' resolves to structural_visual_safe."),
    ] = "auto",
    include_memory: Annotated[
        bool,
        Field(default=True, description="Search local technique memory while grounding the plan."),
    ] = True,
    include_docs: Annotated[
        bool,
        Field(
            default=True,
            description="Use loaded DocsBrain/CardIndex operator knowledge while grounding the plan.",
        ),
    ] = True,
) -> dict[str, Any]:
    """Build a grounded BrainPlan without mutating TouchDesigner."""
    finish = _tr._start_tool(ctx, "td_brain_plan")
    try:
        client = _tr._get_client(ctx)
        services = _tr._get_services(ctx)
        store = getattr(services, "technique_store", None)
        card_index = getattr(services, "card_index", None)
        plan = await build_brain_plan(
            client,
            intent=intent,
            target_root=target_root,
            output_top=output_top,
            constraints=constraints or {},
            preferred_domains=preferred_domains or [],
            validation_profile=validation_profile,
            include_memory=include_memory,
            include_docs=include_docs,
            technique_store=store,
            card_index=card_index,
        )
        _cache_brain_plan(plan)
        _tr._audit_log(
            ctx,
            "td_brain_plan",
            {
                "brain_plan_id": plan.id,
                "profile": plan.concept_graph.profile,
                "blocked": bool(plan.blocked_questions),
                "ops": len(plan.patch_plan.operations),
            },
        )
        return {"success": True, "plan": plan.model_dump(mode="json")}
    except Exception as exc:  # noqa: BLE001
        _tr._record_tool_error(ctx, "td_brain_plan")
        return format_tool_error_dict(exc)
    finally:
        finish()


@mcp.tool(
    name="td_brain_execute",
    title="Execute TD Brain Plan",
    description=(
        "Use this when you already have a BrainPlan from td_brain_plan and need TDPilot "
        "to apply it transactionally with validation, rollback, and optional local learning."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True
    ),
    structured_output=True,
)
async def td_brain_execute(
    ctx: Context,
    plan: Annotated[
        dict[str, Any] | None,
        Field(
            default=None,
            description=(
                "BrainPlan dict returned by td_brain_plan. Raw free text is not "
                "accepted here. Omit when passing plan_id instead."
            ),
        ),
    ] = None,
    plan_id: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "ID of the most recent td_brain_plan result. Server-side lookup — "
                "avoids echoing the full multi-KB plan back through the host "
                "context window (and the silent-corruption risk of hosts that "
                "re-serialize large tool arguments). Provide exactly one of "
                "plan or plan_id."
            ),
        ),
    ] = None,
    transaction_policy: Annotated[
        str,
        Field(
            default="rollback_on_failure",
            description="'rollback_on_failure' (default), 'dry_run', or 'no_rollback'.",
        ),
    ] = "rollback_on_failure",
    learn_on_success: Annotated[
        bool,
        Field(default=False, description="Persist a compact validated task trace to td_knowledge_* memory."),
    ] = False,
    confirm_visual_payload: Annotated[
        bool,
        Field(
            default=False,
            description="Reserved for future image payload confirmation; currently no large images returned.",
        ),
    ] = False,
) -> dict[str, Any]:
    """Execute a BrainPlan through the transaction layer."""
    started = time.perf_counter()
    finish = _tr._start_tool(ctx, "td_brain_execute")
    try:
        if (plan is None) == (plan_id is None):
            return format_tool_error_dict(ValueError("provide exactly one of 'plan' or 'plan_id'"))
        if plan is None:
            cached = get_cached_resource("td://project/state") or {}
            cached_plan = cached.get("latest_brain_plan")
            cached_id = (cached_plan or {}).get("id")
            if not cached_plan or cached_id != plan_id:
                hint = (
                    f" (latest cached plan is {cached_id!r})"
                    if cached_id
                    else " (cache is empty — was the server restarted?)"
                )
                return format_tool_error_dict(
                    ValueError(
                        f"plan_id {plan_id!r} not found in the server-side plan "
                        f"cache{hint}. Re-run td_brain_plan and retry."
                    )
                )
            plan = cached_plan
        try:
            brain_plan = BrainPlan.model_validate(plan)
        except ValidationError as exc:
            return format_tool_error_dict(ValueError(f"invalid BrainPlan: {exc}"))
        if brain_plan.blocked_questions:
            return {
                "success": False,
                "error": "BrainPlan is blocked and must not be executed.",
                "blocked_questions": brain_plan.blocked_questions,
                "missing_facts": brain_plan.missing_facts,
            }

        options = _options_for_policy(transaction_policy, brain_plan.validation_profile)
        tx_result = await _run_transaction(
            ctx,
            brain_plan.patch_plan,
            options,
            concept_profile=brain_plan.concept_graph.profile,
            concept_profiles=_concept_profiles_for_brain_plan(brain_plan),
        )
        learned_id = None
        if learn_on_success and tx_result.status in {"clean", "warnings"} and not tx_result.validation_failed:
            learned_id = await _learn_brain_trace(ctx, brain_plan, tx_result.model_dump(mode="json"))

        trace = BrainTrace(
            intent=brain_plan.task.intent,
            profile=brain_plan.concept_graph.profile,
            target_root=brain_plan.task.target_root,
            operators=brain_plan.concept_graph.operators,
            plan_id=brain_plan.id,
            transaction_id=tx_result.trace_id,
            transaction_status=tx_result.status,
            validation_ok=not tx_result.validation_failed,
            rollback_performed=tx_result.rollback_performed,
            learned_memory_id=learned_id,
        )
        trace_export_path = _export_trace_safely(
            brain_plan=brain_plan,
            tx_result=tx_result.model_dump(mode="json"),
            trace=trace.model_dump(mode="json"),
            learned_id=learned_id,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
        )
        _cache_transaction(brain_plan, tx_result.model_dump(mode="json"), trace.model_dump(mode="json"))
        _tr._audit_log(
            ctx,
            "td_brain_execute",
            {
                "brain_plan_id": brain_plan.id,
                "status": tx_result.status,
                "rollback": tx_result.rollback_performed,
                "learned_id": learned_id,
                "confirm_visual_payload": confirm_visual_payload,
            },
        )
        return {
            "success": tx_result.status in {"clean", "warnings", "dry_run"},
            "result": tx_result.model_dump(mode="json"),
            "trace": trace.model_dump(mode="json"),
            "trace_export_path": trace_export_path,
            "learned_memory_id": learned_id,
        }
    except Exception as exc:  # noqa: BLE001
        _tr._record_tool_error(ctx, "td_brain_execute")
        return format_tool_error_dict(exc)
    finally:
        finish()


@mcp.tool(
    name="td_transaction_apply",
    title="Apply TD Transaction",
    description=(
        "Use this when you need to apply an existing PatchPlan or BrainPlan with preflight, "
        "snapshot, validation, dry-run, max-op, and rollback controls."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True
    ),
    structured_output=True,
)
async def td_transaction_apply(
    ctx: Context,
    plan: Annotated[
        dict[str, Any],
        Field(description="PatchPlan dict or BrainPlan dict."),
    ],
    options: Annotated[
        dict[str, Any] | None,
        Field(default=None, description="TransactionOptions override. Missing fields use safe defaults."),
    ] = None,
) -> dict[str, Any]:
    """Apply a PatchPlan or BrainPlan through the transaction layer."""
    finish = _tr._start_tool(ctx, "td_transaction_apply")
    try:
        patch_plan, brain_plan = _extract_patch_plan(plan)
        try:
            tx_options = TransactionOptions.model_validate(options or {})
        except ValidationError as exc:
            return format_tool_error_dict(ValueError(f"invalid TransactionOptions: {exc}"))
        concept_profile = brain_plan.concept_graph.profile if brain_plan is not None else None
        concept_profiles = _concept_profiles_for_brain_plan(brain_plan) if brain_plan is not None else None
        result = await _run_transaction(
            ctx,
            patch_plan,
            tx_options,
            concept_profile=concept_profile,
            concept_profiles=concept_profiles,
        )
        if brain_plan is not None:
            _cache_transaction(brain_plan, result.model_dump(mode="json"), None)
        _tr._audit_log(
            ctx,
            "td_transaction_apply",
            {"plan_id": patch_plan.id, "status": result.status, "rollback": result.rollback_performed},
        )
        return {
            "success": result.status in {"clean", "warnings", "dry_run"},
            "result": result.model_dump(mode="json"),
        }
    except ValueError as exc:
        return format_tool_error_dict(exc)
    except Exception as exc:  # noqa: BLE001
        _tr._record_tool_error(ctx, "td_transaction_apply")
        return format_tool_error_dict(exc)
    finally:
        finish()


@mcp.tool(
    name="td_cockpit_render",
    title="Render TD Brain Cockpit",
    description=(
        "Use this when you already have BrainPlan or transaction data and want to render "
        "the optional local cockpit UI. This is read-only presentation; call td_brain_plan "
        "or td_brain_execute first for authoritative data."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
    ),
    meta={
        "ui": {"resourceUri": COCKPIT_RESOURCE_URI},
        "openai/outputTemplate": COCKPIT_RESOURCE_URI,
        "openai/toolInvocation/invoking": "Rendering TDPilot cockpit...",
        "openai/toolInvocation/invoked": "Rendered TDPilot cockpit.",
    },
    structured_output=True,
)
async def td_cockpit_render(
    ctx: Context,
    plan: Annotated[
        dict[str, Any] | None,
        Field(default=None, description="BrainPlan dict or td_brain_plan result to summarize."),
    ] = None,
    transaction_result: Annotated[
        dict[str, Any] | None,
        Field(default=None, description="TransactionResult dict or td_brain_execute result to summarize."),
    ] = None,
    trace: Annotated[
        dict[str, Any] | None,
        Field(default=None, description="Optional BrainTrace or trace summary."),
    ] = None,
    title: Annotated[
        str,
        Field(default="TDPilot Brain Cockpit", description="Human-readable cockpit title."),
    ] = "TDPilot Brain Cockpit",
) -> dict[str, Any]:
    """Render-only structured payload for the optional MCP Apps cockpit."""
    finish = _tr._start_tool(ctx, "td_cockpit_render")
    try:
        payload = build_cockpit_payload(
            plan=plan,
            transaction_result=transaction_result,
            trace=trace,
            title=title,
        )
        _tr._audit_log(
            ctx,
            "td_cockpit_render",
            {
                "plan_id": payload.get("plan", {}).get("id"),
                "transaction_status": payload.get("transaction", {}).get("status"),
            },
        )
        return {"success": True, "cockpit": payload}
    except Exception as exc:  # noqa: BLE001
        _tr._record_tool_error(ctx, "td_cockpit_render")
        return format_tool_error_dict(exc)
    finally:
        finish()


def _extract_patch_plan(plan: dict[str, Any]) -> tuple[PatchPlan, BrainPlan | None]:
    if not isinstance(plan, dict):
        raise ValueError("plan must be an object")
    if plan.get("source") == "brain" or "patch_plan" in plan:
        try:
            brain_plan = BrainPlan.model_validate(plan)
        except ValidationError as exc:
            raise ValueError(f"invalid BrainPlan: {exc}") from exc
        if brain_plan.blocked_questions:
            raise ValueError("BrainPlan is blocked and cannot be applied")
        return brain_plan.patch_plan, brain_plan
    try:
        return PatchPlan.model_validate(plan), None
    except ValidationError as exc:
        raise ValueError(f"invalid PatchPlan: {exc}") from exc


def _options_for_policy(policy: str, validation_profile: str) -> TransactionOptions:
    if policy == "dry_run":
        return TransactionOptions(dry_run=True, validation_profile=validation_profile)
    if policy == "no_rollback":
        return TransactionOptions(
            rollback_on_apply_failure=False,
            rollback_on_validation_failure=False,
            validation_profile=validation_profile,
        )
    return TransactionOptions(validation_profile=validation_profile)


async def _run_transaction(
    ctx: Context,
    patch_plan: PatchPlan,
    options: TransactionOptions,
    *,
    concept_profile: str | None = None,
    concept_profiles: list[str] | None = None,
):
    client = _tr._get_client(ctx)
    services = _tr._get_services(ctx)
    macro_engine = getattr(services, "macro_engine", None)

    async def create_snapshot(path: str) -> str | None:
        payload = await _tr._capture_snapshot_payload(ctx, path=path, include_visual=False)
        saved = _tr._get_snapshot_manager(ctx).add_snapshot(
            payload,
            name=f"brain_tx_{patch_plan.id[:8]}",
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
        patch_plan,
        options=options,
        sentinel=_tr._PATCH_SENTINEL,
        concept_profile=concept_profile,
        concept_profiles=concept_profiles,
        macro_engine=macro_engine,
        create_snapshot=create_snapshot,
        restore_snapshot=restore_snapshot,
        param_preflight=_direct_param_preflight(ctx),
    )


def _concept_profiles_for_brain_plan(brain_plan: BrainPlan) -> list[str]:
    """Return validation profile layers selected by a BrainPlan."""
    profiles: list[str] = []
    if brain_plan.concept_graph.profile == "concept_compiled" and brain_plan.candidate_graphs:
        profiles.extend(brain_plan.candidate_graphs[0].profiles)
    if brain_plan.concept_graph.profile:
        profiles.append(brain_plan.concept_graph.profile)
    return list(dict.fromkeys(profiles))


async def _learn_brain_trace(ctx: Context, brain_plan: BrainPlan, tx_result: dict[str, Any]) -> str | None:
    await _tr._ensure_project_scope(ctx)
    store = _tr._get_knowledge_store(ctx)
    body = json.dumps(
        {
            "intent": brain_plan.task.intent,
            "profile": brain_plan.concept_graph.profile,
            "operators": brain_plan.concept_graph.operators,
            "concept_graph": brain_plan.concept_graph.model_dump(mode="json"),
            "transaction": tx_result,
            "grounding_evidence": brain_plan.grounding_evidence,
        },
        indent=2,
        sort_keys=True,
    )
    return store.add(
        body,
        name=f"Validated brain task: {brain_plan.task.intent[:48]}",
        description=f"{brain_plan.concept_graph.profile} brain execution trace",
        tags=["tdpilot-brain", brain_plan.concept_graph.profile],
        source="td_brain_execute",
        scope="project",
    )


def _cache_brain_plan(plan: BrainPlan) -> None:
    payload = {
        "resource_schema_version": 2,
        "mode": "cached",
        "latest_brain_plan": plan.model_dump(mode="json"),
    }
    set_cached_resource("td://project/state", payload)
    set_cached_resource(
        "td://activity/recent",
        {
            "resource_schema_version": 2,
            "mode": "cached",
            "latest_event": {
                "type": "brain_plan",
                "brain_plan_id": plan.id,
                "profile": plan.concept_graph.profile,
                "blocked": bool(plan.blocked_questions),
            },
        },
    )


def _cache_transaction(
    plan: BrainPlan,
    tx_result: dict[str, Any],
    trace: dict[str, Any] | None,
) -> None:
    set_cached_resource(
        "td://project/state",
        {
            "resource_schema_version": 2,
            "mode": "cached",
            "latest_brain_plan": plan.model_dump(mode="json"),
            "latest_transaction": tx_result,
            "latest_trace": trace,
        },
    )
    if plan.task.output_top:
        set_cached_resource(
            f"td://top/path/{quote(plan.task.output_top, safe='')}/analysis",
            {
                "resource_schema_version": 2,
                "mode": "cached",
                "path": plan.task.output_top,
                "transaction_status": tx_result.get("status"),
                "validation_failed": tx_result.get("validation_failed"),
            },
        )


def _export_trace_safely(
    *,
    brain_plan: BrainPlan,
    tx_result: dict[str, Any],
    trace: dict[str, Any],
    learned_id: str | None,
    duration_ms: float,
) -> str | None:
    try:
        promoted_pattern = _promoted_pattern_candidate_for_export(
            brain_plan,
            trace,
            validation_report=tx_result.get("validation_report"),
        )
        promotion_rejection = None
        if promoted_pattern is None:
            promotion_rejection = _trace_promotion_rejection_for_export(
                brain_plan,
                trace,
                validation_report=tx_result.get("validation_report"),
            )
        return append_brain_trace(
            {
                "type": "brain_execution",
                "intent": brain_plan.task.intent,
                "profile": brain_plan.concept_graph.profile,
                "target_root": brain_plan.task.target_root,
                "tools": ["td_brain_execute"],
                "arguments_summary": {
                    "brain_plan_id": brain_plan.id,
                    "patch_plan_id": brain_plan.patch_plan.id,
                    "op_count": len(brain_plan.patch_plan.operations),
                    "validation_profile": brain_plan.validation_profile,
                },
                "duration_ms": duration_ms,
                "snapshots": {
                    "before": tx_result.get("before_snapshot_id"),
                    "after": tx_result.get("after_snapshot_id"),
                },
                "validation": tx_result.get("validation_report"),
                "rollback": {
                    "performed": tx_result.get("rollback_performed"),
                    "error": tx_result.get("rollback_error"),
                    "needs_manual_recovery": tx_result.get("needs_manual_recovery"),
                    "failed_op": tx_result.get("failed_op"),
                },
                "learned_memory_id": learned_id,
                "promoted_pattern_candidate": promoted_pattern,
                "trace_promotion_rejection": promotion_rejection,
                "trace": trace,
            }
        )
    except Exception:
        return None


def _promoted_pattern_candidate_for_export(
    brain_plan: BrainPlan,
    trace: dict[str, Any],
    *,
    validation_report: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    try:
        brain_trace = BrainTrace.model_validate(trace)
        pattern = promote_trace_to_pattern(
            brain_plan,
            brain_trace,
            pattern_registry=load_pattern_registry(),
            validation_report=validation_report,
        )
    except Exception:
        return None
    return pattern.model_dump(mode="json")


def _trace_promotion_rejection_for_export(
    brain_plan: BrainPlan,
    trace: dict[str, Any],
    *,
    validation_report: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    try:
        brain_trace = BrainTrace.model_validate(trace)
        return trace_promotion_rejection_evidence(
            brain_plan,
            brain_trace,
            pattern_registry=load_pattern_registry(),
            validation_report=validation_report,
        )
    except Exception:
        return None
