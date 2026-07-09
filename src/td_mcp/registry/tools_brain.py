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
from td_mcp.brain.concept_compiler import compile_visual_task
from td_mcp.brain.corpus_bridge import build_corpus_evidence
from td_mcp.brain.llm_contract import review_draft_candidate_graph
from td_mcp.brain.operator_availability import build_operator_availability_matrix
from td_mcp.brain.param_semantics import semantics_by_op_and_param
from td_mcp.brain.param_semantics_drafts import official_card_param_names
from td_mcp.brain.patterns import load_pattern_registry
from td_mcp.brain.planner import (
    build_brain_plan,
    build_brain_plan_from_reviewed_candidate,
    read_available_operator_types,
)
from td_mcp.brain.trace_promotion import (
    promote_trace_to_pattern,
    trace_promotion_rejection_evidence,
)
from td_mcp.brain.traces import append_brain_trace
from td_mcp.brain.transaction import apply_transaction
from td_mcp.errors import format_tool_error_dict
from td_mcp.models.brain import BrainPlan, BrainTrace, TransactionOptions, VisualTaskSpec
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
    name="td_brain_ground",
    title="Ground Host-Authored TD Brain Draft",
    description=(
        "Use this when td_brain_plan returns blocked or unsupported, or when you want to "
        "author a creative BrainPlan draft yourself: it returns a read-only grounding pack "
        "(task features, corpus evidence, candidate operators, parameter contracts, operator "
        "availability, live state, exemplars, and the draft authoring contract) so you can "
        "write a draft for td_brain_propose. Do not use it for trivial single-node edits."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=False, openWorldHint=True
    ),
    meta={"anthropic/alwaysLoad": True},
    structured_output=True,
)
async def td_brain_ground(
    ctx: Context,
    intent: Annotated[
        str,
        Field(description="Natural-language visual programming task to ground.", min_length=1),
    ],
    target_root: Annotated[
        str,
        Field(default="/project1", description="Absolute TD parent/root path the draft will build inside."),
    ] = "/project1",
    preferred_domains: Annotated[
        list[str] | None,
        Field(default=None, description="Preferred TD data domains: TOP, CHOP, SOP, POP, DAT, COMP, MAT."),
    ] = None,
    include_live_state: Annotated[
        bool,
        Field(
            default=True, description="Include existing node names/types at target_root when TD is reachable."
        ),
    ] = True,
) -> dict[str, Any]:
    """Return the grounding pack the host LLM uses to author a draft candidate graph."""
    finish = _tr._start_tool(ctx, "td_brain_ground")
    try:
        client = _tr._get_client(ctx)
        services = _tr._get_services(ctx)
        card_index = getattr(services, "card_index", None)
        compiled_task = compile_visual_task(
            intent,
            target_root=target_root,
            preferred_domains=preferred_domains or [],
            card_index=card_index,
        )
        corpus_records = build_corpus_evidence(
            intent=intent,
            operators=_docs_ops_from_markers(compiled_task.grounding_evidence),
            card_index=card_index,
            limit_per_query=16,
            max_records=24,
        )
        candidate_ops = _candidate_op_types(compiled_task, corpus_records, limit=12)
        available_ops = await read_available_operator_types(client)
        live_state: dict[str, Any]
        if include_live_state:
            live_state = await _live_state_pack(client, target_root)
        else:
            live_state = {"available": False, "reason": "include_live_state=false"}
        pack: dict[str, Any] = {
            "task_features": compiled_task.model_dump(mode="json"),
            "corpus_evidence": [record.model_dump(mode="json") for record in corpus_records],
            "candidate_operators": _candidate_operator_cards(card_index, candidate_ops, corpus_records),
            "param_semantics": _param_semantics_for_ops(candidate_ops, card_index),
            "param_semantics_tiers": dict(PARAM_SEMANTICS_TIERS),
            "operator_availability": _operator_availability_pack(available_ops, candidate_ops),
            "live_state": live_state,
            "exemplars": _pattern_exemplars(compiled_task, limit=2),
            "authoring_contract": dict(DRAFT_AUTHORING_CONTRACT),
        }
        _tr._audit_log(
            ctx,
            "td_brain_ground",
            {
                "compiled_task_id": compiled_task.id,
                "candidate_profiles": compiled_task.candidate_profiles,
                "candidate_op_count": len(candidate_ops),
                "corpus_record_count": len(corpus_records),
                "td_reachable": bool(available_ops),
            },
        )
        return {"success": True, "grounding_pack": pack}
    except Exception as exc:  # noqa: BLE001
        _tr._record_tool_error(ctx, "td_brain_ground")
        return format_tool_error_dict(exc)
    finally:
        finish()


@mcp.tool(
    name="td_brain_propose",
    title="Propose Host-Authored TD Brain Draft",
    description=(
        "Use this when you have authored a draft candidate graph from a td_brain_ground "
        "grounding pack and need TDPilot to validate it into an executable BrainPlan. It is "
        "read-only and never mutates TouchDesigner: accepted drafts are compiled, gated by "
        "parameter semantics, and cached server-side so td_brain_execute(plan_id=...) can run "
        "them immediately; rejected drafts return machine-readable rejections to fix and retry."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=False, openWorldHint=True
    ),
    meta={"anthropic/alwaysLoad": True},
    structured_output=True,
)
async def td_brain_propose(
    ctx: Context,
    draft: Annotated[
        dict[str, Any],
        Field(
            description=(
                "Host-authored draft candidate graph matching the td_brain_ground "
                "authoring_contract draft_schema (label, concepts, edges, required_ops, ...)."
            ),
        ),
    ],
    target_root: Annotated[
        str,
        Field(default="/project1", description="Absolute TD parent/root path the plan will build inside."),
    ] = "/project1",
    validation_profile: Annotated[
        str,
        Field(default="auto", description="Validation profile. 'auto' resolves to structural_visual_safe."),
    ] = "auto",
    intent: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Original natural-language intent behind the draft. Defaults to the "
                "draft label so the same intent used for td_brain_ground can be carried through."
            ),
        ),
    ] = None,
) -> dict[str, Any]:
    """Validate a host-authored draft through the review gate and cache the resulting plan."""
    finish = _tr._start_tool(ctx, "td_brain_propose")
    try:
        if not isinstance(draft, dict) or not draft:
            return format_tool_error_dict(
                ValueError(
                    "draft must be a non-empty object shaped by the td_brain_ground "
                    "authoring_contract (call td_brain_ground first)"
                )
            )
        client = _tr._get_client(ctx)
        services = _tr._get_services(ctx)
        card_index = getattr(services, "card_index", None)
        resolved_intent = (
            (intent or "").strip()
            or str(draft.get("label") or "").strip()
            or str(draft.get("explanation") or "").strip()
            or "host-authored draft candidate graph"
        )
        compiled_task = compile_visual_task(
            resolved_intent,
            target_root=target_root,
            validation_profile=validation_profile,
            card_index=card_index,
        )
        available_ops = await read_available_operator_types(client)
        review = review_draft_candidate_graph(
            draft,
            compiled_task=compiled_task,
            # Empty set means TD is unreachable: availability is unknown, so the
            # availability gate is skipped (same degradation as build_brain_plan).
            available_ops=available_ops or None,
            card_index=card_index,
        )
        if not review.accepted or review.candidate_graph is None:
            rejections = _draft_rejections(review.rejection_reasons)
            _tr._audit_log(
                ctx,
                "td_brain_propose",
                {"accepted": False, "rejection_count": len(rejections)},
            )
            return {
                "success": False,
                "rejections": rejections,
                "review": review.model_dump(mode="json"),
            }
        task = VisualTaskSpec(
            intent=resolved_intent,
            target_root=target_root,
            validation_profile=validation_profile,
        )
        plan = await build_brain_plan_from_reviewed_candidate(
            client,
            task=task,
            compiled_task=compiled_task,
            candidate=review.candidate_graph,
            card_index=card_index,
            validation_profile=validation_profile,
            available_ops=available_ops,
        )
        if plan.blocked_questions:
            # The deeper patch-level gate (availability re-check, param-semantics
            # value contracts, device sources) blocked the compiled plan.
            rejections = [
                {
                    "code": "plan_blocked",
                    "subject": "; ".join(plan.missing_facts[:6]),
                    "message": question,
                    "fix": (
                        "Adjust the draft (operators, param values, or declared device "
                        "sources) per the td_brain_ground param_semantics and "
                        "operator_availability sections, then re-run td_brain_propose."
                    ),
                }
                for question in plan.blocked_questions
            ]
            _tr._audit_log(
                ctx,
                "td_brain_propose",
                {"accepted": False, "plan_blocked": True, "rejection_count": len(rejections)},
            )
            return {
                "success": False,
                "rejections": rejections,
                "review": review.model_dump(mode="json"),
                "plan": plan.model_dump(mode="json"),
            }
        _cache_brain_plan(plan)
        plan_summary = {
            "plan_id": plan.id,
            "profile": plan.concept_graph.profile,
            "operators": list(plan.concept_graph.operators),
            "operation_count": len(plan.patch_plan.operations),
            "validation_profile": plan.validation_profile,
            "review_status": review.status,
            "review_score": review.score,
            # Loud strip surface: param values whose names neither the
            # semantics registry nor the operator's official docs card
            # key_params verify were REMOVED by the review gate, not rejected.
            # The host must re-check this list and re-author if a stripped
            # value mattered. With TD/atlas reachable this list SHRINKS versus
            # the old registry-only polarity.
            "stripped_params": list(review.rewrites),
        }
        _tr._audit_log(
            ctx,
            "td_brain_propose",
            {
                "accepted": True,
                "brain_plan_id": plan.id,
                "ops": len(plan.patch_plan.operations),
                "stripped_param_count": len(review.rewrites),
            },
        )
        return {
            "success": True,
            "plan_id": plan.id,
            "plan_summary": plan_summary,
            "plan": plan.model_dump(mode="json"),
        }
    except Exception as exc:  # noqa: BLE001
        _tr._record_tool_error(ctx, "td_brain_propose")
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
                "error": (
                    "BrainPlan is blocked and must not be executed. Resolve the "
                    "blocked_questions, or author the plan yourself: call "
                    "td_brain_ground for a grounding pack, write a draft candidate "
                    "graph, validate it with td_brain_propose, then re-run "
                    "td_brain_execute(plan_id=...)."
                ),
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


# --------------------------------------------------------------------------
# Host-authored draft loop (td_brain_ground / td_brain_propose)
# --------------------------------------------------------------------------

# How the host LLM must author a draft the review gate accepts. Shipped inside
# every td_brain_ground grounding pack so the contract travels with the facts.
DRAFT_AUTHORING_CONTRACT: dict[str, Any] = {
    "accepted_by": "td_brain_propose",
    "draft_schema": {
        "label": "str, required, non-empty — short name for the draft graph",
        "profiles": (
            "list[str], optional — BrainProfile values such as 'audio_reactive', "
            "'feedback', 'pop', 'glsl', 'render_pipeline', 'panel_ui', 'generic'"
        ),
        "concepts": (
            "list of concept nodes, each: {id: str, label: str, role: one of "
            "source|process|feedback|control|render|output|material|ui|validator, "
            "domain: one of TOP|CHOP|SOP|POP|DAT|COMP|MAT|ANY, op_type: exact TD "
            "operator type (e.g. 'noiseTOP'), params: {param_name: value}} — "
            "optional create_type/content/generated_code as in ConceptNode"
        ),
        "edges": (
            "list of {source: concept id, target: concept id, kind: one of "
            "data|control|reference|feedback, source_index: int>=0, "
            "target_index: int>=0}; source/target must reference declared concept ids"
        ),
        "required_ops": "list[str] — every op_type the draft depends on",
        "optional_ops": "list[str], optional",
        "validation_needs": "list[str], optional — validation probe names to run after apply",
        "risk_flags": "list[str], optional",
        "grounding_evidence": "list[str], optional — cite the docs/corpus markers you used",
        "explanation": "str, optional — why this topology serves the intent",
    },
    "rules": [
        (
            "Use only operators from candidate_operators (or otherwise backed by an "
            "official docs card); unknown operators are rejected with missing_docs."
        ),
        (
            "When operator_availability.available is true, avoid operators it marks "
            "unavailable — they are rejected with unavailable_op."
        ),
        (
            "Keep param values inside the param_semantics contracts (enum values, "
            "valid ranges, op_ref families). A param value survives when its name is "
            "verified by a registry contract (tier registry_contract) OR by the "
            "operator card's official key_params (tier atlas_name_verified — value "
            "checked by post-apply live validation). Params neither tier can verify "
            "are STRIPPED (not rejected) and surfaced in plan_summary.stripped_params."
        ),
        (
            "Connections must be type-compatible: 'data' edges wire same-family "
            "operator inputs; use 'reference' edges plus an op-path param binding "
            "(e.g. params {'top': '${path:concept_id}'}) for cross-family links."
        ),
        (
            "End every chain in a stable output null (nullTOP/nullCHOP/...) with "
            "role 'output'. The draft schema is closed — unknown fields are rejected."
        ),
    ],
    "loop": (
        "td_brain_ground -> author draft JSON -> td_brain_propose(draft) -> fix any "
        "rejections and re-propose -> td_brain_execute(plan_id=<returned plan_id>)"
    ),
}

_DRAFT_REJECTION_FIXES: dict[str, str] = {
    "invalid_schema": (
        "Fix the draft shape to match the td_brain_ground authoring_contract "
        "draft_schema: the schema is closed (remove unknown fields) and every edge "
        "must reference declared concept ids."
    ),
    "missing_required_ops": (
        "Declare at least one concept with an op_type (or list required_ops) so the "
        "review gate can prove the operators exist."
    ),
    "missing_docs": (
        "This op_type has no official docs card. Pick an operator from the "
        "td_brain_ground candidate_operators list instead."
    ),
    "unavailable_op": (
        "This operator is not available in the connected TouchDesigner build. Pick "
        "an available alternative from the operator_availability section."
    ),
}


def _draft_rejections(reasons: list[str]) -> list[dict[str, Any]]:
    """Turn review rejection markers into machine-readable fix instructions."""
    rejections: list[dict[str, Any]] = []
    for reason in reasons:
        code, _, subject = str(reason).partition(":")
        rejections.append(
            {
                "code": code,
                "subject": subject,
                "message": reason,
                "fix": _DRAFT_REJECTION_FIXES.get(
                    code, "Adjust the draft per the authoring_contract and re-run td_brain_propose."
                ),
            }
        )
    return rejections


def _docs_ops_from_markers(grounding_evidence: list[str]) -> list[str]:
    """Extract docs-proven op types from ``docs:<op_type>`` grounding markers."""
    ops: list[str] = []
    for marker in grounding_evidence:
        text = str(marker)
        if text.startswith("docs:"):
            op_type = text.split(":", 1)[1].strip()
            if op_type and op_type not in ops:
                ops.append(op_type)
    return ops


def _candidate_op_types(compiled_task, corpus_records, *, limit: int = 12) -> list[str]:
    """Rank candidate operator types: compiled-task seed ops first, then corpus hits."""
    ordered: list[str] = []
    for op_type in _docs_ops_from_markers(compiled_task.grounding_evidence):
        if op_type not in ordered:
            ordered.append(op_type)
    for record in corpus_records:
        op_type = record.op_type
        if op_type and op_type not in ordered:
            ordered.append(op_type)
    return ordered[:limit]


def _candidate_operator_cards(
    card_index,
    candidate_ops: list[str],
    corpus_records,
) -> list[dict[str, Any]]:
    """Compact per-operator authoring cards: op_type, family, summary, key_params, gotchas."""
    records_by_op = {record.op_type: record for record in corpus_records if record.op_type}
    cards: list[dict[str, Any]] = []
    for op_type in candidate_ops:
        raw_card = None
        if card_index is not None:
            try:
                raw_card = card_index.get_operator(op_type)
            except Exception:
                raw_card = None
        raw_card = raw_card if isinstance(raw_card, dict) else {}
        record = records_by_op.get(op_type)
        summary = str(raw_card.get("summary") or (record.summary if record else "") or "")
        key_params = raw_card.get("key_params") or raw_card.get("parameters") or []
        key_param_names = [
            str(item.get("name")) if isinstance(item, dict) else str(item)
            for item in key_params
            if (item.get("name") if isinstance(item, dict) else item)
        ][:12]
        if not key_param_names and record is not None:
            key_param_names = list(record.key_params)[:12]
        gotchas = [str(item) for item in (raw_card.get("common_gotchas") or []) if str(item).strip()][:6]
        cards.append(
            {
                "op_type": op_type,
                "family": raw_card.get("family") or (record.family if record else None),
                "summary": " ".join(summary.split())[:360],
                "key_params": key_param_names,
                "gotchas": gotchas,
                "docs_url": raw_card.get("docs_url") or (record.docs_url if record else None),
            }
        )
    return cards


# How param values survive td_brain_propose (see td_mcp.brain.llm_contract):
# shipped inside every grounding pack so the host knows which values persist.
PARAM_SEMANTICS_TIERS: dict[str, str] = {
    "registry_contract": (
        "Hand-verified ParamSemantics entry: name AND static value contract "
        "(enum values, valid ranges, op_ref families, cook_risk) are enforced "
        "before mutation. Values outside the contract block the plan."
    ),
    "atlas_name_verified": (
        "Parameter name is listed in the operator's official docs card "
        "key_params: the value SURVIVES td_brain_propose (name proven, no "
        "static value contract) and is checked by post-apply live validation."
    ),
    "unverified": (
        "Neither tier knows the name: the value is STRIPPED (not rejected) "
        "and surfaced in plan_summary.stripped_params."
    ),
}


def _param_semantics_for_ops(
    candidate_ops: list[str],
    card_index=None,
) -> dict[str, list[dict[str, Any]]]:
    """Serialize the parameter contracts for the candidate operators, compactly.

    Registry entries carry their full static value contract and
    ``tier: registry_contract``. Names known only from the operator's official
    docs card are appended as ``tier: atlas_name_verified`` rows so the host
    knows those values survive td_brain_propose without a static contract.
    """
    wanted = set(candidate_ops)
    by_op: dict[str, list[dict[str, Any]]] = {}
    for (op_type, name), semantic in sorted(semantics_by_op_and_param().items()):
        if op_type not in wanted:
            continue
        entry: dict[str, Any] = {
            "name": name,
            "tier": "registry_contract",
            "value_kind": semantic.value_kind,
            "default_strategy": semantic.default_strategy,
            "cook_risk": semantic.cook_risk,
        }
        if semantic.valid_range is not None:
            entry["valid_range"] = list(semantic.valid_range)
        if semantic.enum_values:
            entry["enum_values"] = list(semantic.enum_values)
        if semantic.tuple_size is not None:
            entry["tuple_size"] = semantic.tuple_size
        if semantic.expected_family is not None:
            entry["expected_family"] = semantic.expected_family
        if semantic.expected_op_type is not None:
            entry["expected_op_type"] = semantic.expected_op_type
        by_op.setdefault(op_type, []).append(entry)
    for op_type in candidate_ops:
        registry_names = {entry["name"] for entry in by_op.get(op_type, [])}
        atlas_names = sorted(official_card_param_names(card_index, op_type) - registry_names)
        for name in atlas_names:
            by_op.setdefault(op_type, []).append({"name": name, "tier": "atlas_name_verified"})
    return by_op


def _operator_availability_pack(available_ops: set[str], candidate_ops: list[str]) -> dict[str, Any]:
    """Availability rows for the candidate operators; degraded when TD is unreachable."""
    if not available_ops:
        return {
            "available": False,
            "reason": (
                "TouchDesigner not reachable (or empty family list); operator "
                "availability unknown. Drafts are still reviewable — availability "
                "is re-checked at td_brain_propose/td_brain_execute time."
            ),
        }
    matrix = build_operator_availability_matrix(available_ops, required_ops=candidate_ops)
    return {
        "available": True,
        "td_build": matrix.td_build,
        "platform": matrix.platform,
        "available_op_count": len(available_ops),
        "operators": {op_type: matrix.operators.get(op_type, {}) for op_type in candidate_ops},
        "unavailable_reasons": {
            op_type: reason
            for op_type, reason in matrix.unavailable_reasons.items()
            if op_type in set(candidate_ops)
        },
    }


async def _live_state_pack(client, target_root: str) -> dict[str, Any]:
    """Existing node names/types at target_root; degraded instead of failing the tool."""
    try:
        response = await client.request("nodes", {"path": target_root, "limit": 200})
    except Exception as exc:  # noqa: BLE001 — degrade, never fail the grounding pack
        return {"available": False, "reason": str(exc) or type(exc).__name__}
    nodes = (
        response
        if isinstance(response, list)
        else response.get("nodes", [])
        if isinstance(response, dict)
        else []
    )
    compact = [
        {"name": str(node.get("name")), "type": str(node.get("type") or node.get("op_type") or "")}
        for node in nodes
        if isinstance(node, dict) and node.get("name")
    ][:200]
    return {
        "available": True,
        "target_root": target_root,
        "node_count": len(compact),
        "nodes": compact,
    }


def _pattern_exemplars(compiled_task, *, limit: int = 2) -> list[dict[str, Any]]:
    """1-2 registry patterns closest to the detected profile, as structural examples."""
    try:
        patterns = load_pattern_registry()
    except Exception:
        return []
    wanted_profiles = set(compiled_task.candidate_profiles)
    wanted_tags = set(compiled_task.motifs)
    scored: list[tuple[int, str, Any]] = []
    for pattern in patterns:
        profile_overlap = len(wanted_profiles.intersection(pattern.profiles))
        tag_overlap = len(wanted_tags.intersection(pattern.intent_tags))
        score = (profile_overlap * 2) + tag_overlap
        if score > 0:
            scored.append((score, pattern.pattern_id, pattern))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [_exemplar_from_pattern(pattern) for _, _, pattern in scored[:limit]]


def _exemplar_from_pattern(pattern) -> dict[str, Any]:
    return {
        "pattern_id": pattern.pattern_id,
        "title": pattern.title,
        "profiles": list(pattern.profiles),
        "required_ops": list(pattern.required_ops),
        "concepts": [
            {
                "id": node.id,
                "role": node.role,
                "domain": node.domain,
                "op_type": node.op_type,
                "params": dict(node.params),
            }
            for node in pattern.concept_nodes
        ],
        "edges": [
            {"source": edge.source, "target": edge.target, "kind": edge.kind}
            for edge in pattern.concept_edges
        ],
        "validation_probes": list(pattern.validation_probes),
    }
