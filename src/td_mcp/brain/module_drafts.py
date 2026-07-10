"""Closed review gate for v2 module-level build drafts."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from td_mcp.brain.build_compiler import compile_module_graph, load_compiled_techniques
from td_mcp.brain.intent_coverage import build_intent_requirements, compute_intent_coverage
from td_mcp.models.brain import (
    BrainPlan,
    CompiledVisualTaskSpec,
    ConceptEdge,
    ConceptGraph,
    ConceptNode,
    ControlBindingSpec,
    VisualTaskSpec,
)
from td_mcp.models.build import (
    BuildConstraints,
    BuildIntent,
    BuildPreferences,
    IntentInput,
    IntentOutput,
    ModuleGraph,
    SuccessCriterion,
)

_CONTROL_EXPR_RE = re.compile(r"^op\((?P<quote>['\"])(?P<path>/[^'\"]+)(?P=quote)\)\[(?P<channel>.+)\]$")


class ModuleDraftReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool = False
    rejection_reasons: list[str] = Field(default_factory=list)
    plan: BrainPlan | None = None


def review_module_draft(
    draft: dict[str, Any],
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
    grounding_id: str | None,
    available_ops: set[str] | None = None,
    card_index: Any = None,
) -> ModuleDraftReview:
    """Validate and deterministically compile an untrusted module draft."""
    if not isinstance(draft, dict) or "module_graph" not in draft:
        return ModuleDraftReview(accepted=False, rejection_reasons=["missing_module_graph"])
    try:
        graph = ModuleGraph.model_validate(draft["module_graph"])
    except ValidationError as exc:
        return ModuleDraftReview(
            accepted=False,
            rejection_reasons=[f"invalid_module_graph:{_compact_error(exc)}"],
        )
    if graph.target_root != task.target_root:
        return ModuleDraftReview(
            accepted=False,
            rejection_reasons=["module_graph_target_mismatch"],
        )
    registry = load_compiled_techniques()
    technique_ids = sorted({module.technique_id for module in graph.modules})
    unknown = sorted(set(technique_ids) - registry.keys())
    if unknown:
        return ModuleDraftReview(
            accepted=False,
            rejection_reasons=[f"unknown_technique:{item}" for item in unknown],
        )
    required_ops = sorted(
        {op_type for technique_id in technique_ids for op_type in registry[technique_id].required_ops}
    )
    missing_docs = [op_type for op_type in required_ops if not _has_operator_card(card_index, op_type)]
    if card_index is not None and missing_docs:
        return ModuleDraftReview(
            accepted=False,
            rejection_reasons=[f"missing_docs:{item}" for item in missing_docs],
        )
    if available_ops is not None:
        unavailable = sorted(set(required_ops) - available_ops)
        if unavailable:
            return ModuleDraftReview(
                accepted=False,
                rejection_reasons=[f"unavailable_op:{item}" for item in unavailable],
            )
    try:
        intent = _derive_build_intent(
            draft.get("build_intent"),
            task=task,
            compiled_task=compiled_task,
        )
        patch_plan, artifacts = compile_module_graph(intent, graph, registry=registry)
    except (ValueError, TypeError) as exc:
        return ModuleDraftReview(
            accepted=False,
            rejection_reasons=[f"compile_failed:{type(exc).__name__}:{exc}"],
        )
    concept_graph = _concept_graph_from_compiler(task, graph, patch_plan)
    coverage = compute_intent_coverage(
        compiled_task,
        concept_graph,
        patch_plan,
        validation_needs=compiled_task.validation_needs,
    )
    if not coverage.complete:
        reasons = [f"uncovered_requirement:{item}" for item in coverage.uncovered_requirement_ids]
        reasons.extend(f"unresolved_semantic_edge:{item}" for item in coverage.unresolved_semantic_edges)
        return ModuleDraftReview(accepted=False, rejection_reasons=reasons)
    plan = BrainPlan(
        task=task,
        concept_graph=concept_graph,
        patch_plan=patch_plan,
        compiled_task=compiled_task,
        route="host_authored",
        grounding_id=grounding_id,
        intent_coverage=coverage,
        validation_profile=task.validation_profile,
        grounding_evidence=[
            "compiler:minimal-visual-v2",
            *[f"technique:{technique_id}" for technique_id in technique_ids],
            *[f"docs:{op_type}" for op_type in required_ops],
        ],
        risk_flags=list(patch_plan.risk_flags),
        compiler_artifacts=artifacts,
    )
    return ModuleDraftReview(accepted=True, plan=plan)


def _derive_build_intent(
    raw: Any,
    *,
    task: VisualTaskSpec,
    compiled_task: CompiledVisualTaskSpec,
) -> BuildIntent:
    host = raw if isinstance(raw, dict) else {}
    mode = str(host.get("mode") or task.constraints.get("_brain_mode") or "production")
    if mode == "auto":
        mode = "production"
    constraint_keys = set(BuildConstraints.model_fields)
    constraint_payload = {key: value for key, value in task.constraints.items() if key in constraint_keys}
    if isinstance(host.get("constraints"), dict):
        constraint_payload.update(
            {key: value for key, value in host["constraints"].items() if key in constraint_keys}
        )
    preferences = BuildPreferences.model_validate(host.get("preferences") or {})
    inputs = [
        IntentInput(
            name=str(item.get("kind") or f"input_{index}"),
            domain=_intent_input_domain(str(item.get("domain") or "unknown")),
            path=item.get("path"),
            required=bool(item.get("required", True)),
        )
        for index, item in enumerate(compiled_task.inputs)
        if isinstance(item, dict)
    ]
    outputs = [
        IntentOutput(
            name=str(item.get("kind") or f"output_{index}"),
            domain=_intent_output_domain(str(item.get("domain") or "TOP")),
            target_path=item.get("path") or task.output_top,
        )
        for index, item in enumerate(compiled_task.outputs)
        if isinstance(item, dict)
    ]
    criteria = [
        SuccessCriterion(
            id=f"validation:{name}",
            description=f"Live validation passes: {name}",
            kind=_criterion_kind(name),
        )
        for name in compiled_task.validation_needs
    ]
    requirements = build_intent_requirements(compiled_task)
    return BuildIntent(
        compiled_task_id=compiled_task.id,
        mode=mode,
        target_path=task.target_root,
        operation=str(host.get("operation") or "create"),
        outcome=compiled_task.intent,
        visual_keywords=compiled_task.motifs[:8],
        behavior_keywords=compiled_task.time_behavior[:8],
        inputs=inputs,
        outputs=outputs,
        constraints=BuildConstraints.model_validate(constraint_payload),
        preferences=preferences,
        unknowns=[str(item) for item in host.get("unknowns") or []][:5],
        assumptions=[str(item) for item in host.get("assumptions") or []][:5],
        success_criteria=criteria,
        requirement_ids=[item.id for item in requirements],
    )


def _concept_graph_from_compiler(
    task: VisualTaskSpec,
    module_graph: ModuleGraph,
    patch_plan,
) -> ConceptGraph:
    module_roles = {module.id: _concept_role(module.role) for module in module_graph.modules}
    path_to_id: dict[str, str] = {}
    concepts: list[ConceptNode] = []
    for operation in patch_plan.operations:
        if operation.kind != "create_node":
            continue
        name = str(operation.args.get("name") or "")
        op_type = str(operation.args.get("op_type") or "")
        if not name or not op_type:
            continue
        path = f"{str(operation.target).rstrip('/')}/{name}"
        concept_id = f"node_{len(concepts)}"
        module_id = _module_id_for_name(name, module_roles)
        concepts.append(
            ConceptNode(
                id=concept_id,
                label=name,
                role=module_roles.get(module_id, "process"),
                domain=_domain_from_op_type(op_type),
                op_type=op_type,
                evidence=[f"compiled-path:{path}", f"module:{module_id}" if module_id else "compiler:v2"],
            )
        )
        path_to_id[path] = concept_id

    edges: list[ConceptEdge] = []
    seen: set[tuple[str, str, str, str]] = set()
    for operation in patch_plan.operations:
        if operation.kind == "connect":
            source_path = str(operation.args.get("from") or "")
            target_path = str(operation.args.get("to") or "")
            if source_path not in path_to_id or target_path not in path_to_id:
                continue
            edge = ConceptEdge(
                source=path_to_id[source_path],
                target=path_to_id[target_path],
                kind="data",
                source_index=int(operation.args.get("from_output") or 0),
                target_index=int(operation.args.get("to_input") or 0),
            )
            _append_edge(edges, seen, edge)
        elif operation.kind == "set_params" and operation.target in path_to_id:
            params = operation.args.get("params") or {}
            for param_name, value in params.items():
                if isinstance(value, str) and value in path_to_id:
                    _append_edge(
                        edges,
                        seen,
                        ConceptEdge(
                            source=path_to_id[value],
                            target=path_to_id[str(operation.target)],
                            kind="reference",
                        ),
                    )
                    continue
                expression = value.get("expr") if isinstance(value, dict) else None
                match = _CONTROL_EXPR_RE.fullmatch(str(expression or ""))
                if not match or match.group("path") not in path_to_id:
                    continue
                channel_raw = match.group("channel").strip()
                channel: int | str
                if channel_raw.isdigit():
                    channel = int(channel_raw)
                else:
                    channel = channel_raw.strip("'\"")
                _append_edge(
                    edges,
                    seen,
                    ConceptEdge(
                        source=path_to_id[match.group("path")],
                        target=path_to_id[str(operation.target)],
                        kind="control",
                        binding=ControlBindingSpec(
                            source_channel=channel,
                            target_param=str(param_name),
                        ),
                    ),
                )
    return ConceptGraph(
        task=task,
        profile="concept_compiled",
        concepts=concepts,
        edges=edges,
        evidence=["compiler:minimal-visual-v2"],
        risk_flags=list(patch_plan.risk_flags),
    )


def _append_edge(
    edges: list[ConceptEdge],
    seen: set[tuple[str, str, str, str]],
    edge: ConceptEdge,
) -> None:
    binding = edge.binding.target_param if edge.binding else ""
    key = (edge.source, edge.target, edge.kind, binding)
    if key not in seen:
        seen.add(key)
        edges.append(edge)


def _module_id_for_name(name: str, roles: dict[str, str]) -> str | None:
    matches = [module_id for module_id in roles if name.startswith(f"{module_id}_")]
    return max(matches, key=len) if matches else None


def _concept_role(role: str) -> str:
    return {
        "source": "source",
        "generator": "source",
        "simulation": "feedback",
        "render": "render",
        "output": "output",
        "control": "control",
    }.get(role, "process")


def _domain_from_op_type(op_type: str) -> str:
    for domain in ("TOP", "CHOP", "SOP", "POP", "DAT", "COMP", "MAT"):
        if op_type.endswith(domain):
            return domain
    return "ANY"


def _intent_input_domain(domain: str) -> str:
    return domain if domain in {"TOP", "CHOP", "SOP", "POP", "DAT", "COMP", "MAT", "device"} else "unknown"


def _intent_output_domain(domain: str) -> str:
    return domain if domain in {"TOP", "CHOP", "SOP", "POP", "DAT", "COMP", "MAT"} else "TOP"


def _criterion_kind(name: str) -> str:
    lowered = name.lower()
    if any(token in lowered for token in ("visual", "nonblack", "motion", "output")):
        return "visual"
    if any(token in lowered for token in ("signal", "binding", "activity")):
        return "signal"
    if "cook" in lowered or "fps" in lowered:
        return "performance"
    return "graph"


def _has_operator_card(card_index: Any, op_type: str) -> bool:
    try:
        return isinstance(card_index.get_operator(op_type), dict)
    except Exception:
        return False


def _compact_error(exc: ValidationError) -> str:
    error = exc.errors()[0] if exc.errors() else {"msg": str(exc), "loc": ()}
    location = ".".join(str(item) for item in error.get("loc", ())) or "module_graph"
    return f"{location}:{error.get('msg', 'invalid')}"


__all__ = ["ModuleDraftReview", "review_module_draft"]
