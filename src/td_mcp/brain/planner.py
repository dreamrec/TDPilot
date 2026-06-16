"""Semantic TD brain planner: intent -> concept graph -> typed PatchPlan."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from td_mcp.brain.validators import classify_intent_profile
from td_mcp.hints import query_hints
from td_mcp.models.brain import BrainPlan, ConceptEdge, ConceptGraph, ConceptNode, VisualTaskSpec
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan


@dataclass(frozen=True)
class _ProfileSpec:
    concepts: tuple[dict[str, Any], ...]
    edges: tuple[tuple[str, str, int, int, str], ...] = field(default_factory=tuple)
    topic: str | None = None
    primary_op: str | None = None
    risk_flags: tuple[str, ...] = field(default_factory=tuple)


_PROFILE_SPECS: dict[str, _ProfileSpec] = {
    "feedback": _ProfileSpec(
        topic="feedback",
        primary_op="feedbackTOP",
        concepts=(
            {"id": "source", "label": "Noise source", "role": "source", "domain": "TOP", "op_type": "noiseTOP"},
            {
                "id": "feedback",
                "label": "Feedback buffer",
                "role": "feedback",
                "domain": "TOP",
                "op_type": "feedbackTOP",
            },
            {"id": "decay", "label": "Decay and level", "role": "process", "domain": "TOP", "op_type": "levelTOP"},
            {
                "id": "composite",
                "label": "Composite merge",
                "role": "process",
                "domain": "TOP",
                "op_type": "compositeTOP",
            },
            {"id": "output", "label": "Stable output", "role": "output", "domain": "TOP", "op_type": "nullTOP"},
        ),
        edges=(
            ("source", "composite", 0, 0, "data"),
            ("feedback", "decay", 0, 0, "feedback"),
            ("decay", "composite", 0, 1, "data"),
            ("composite", "feedback", 0, 0, "feedback"),
            ("composite", "output", 0, 0, "data"),
        ),
    ),
    "audio_reactive": _ProfileSpec(
        topic="audio_reactive",
        primary_op="audiofileinCHOP",
        concepts=(
            {
                "id": "audio",
                "label": "Audio input",
                "role": "source",
                "domain": "CHOP",
                "op_type": "audiofileinCHOP",
            },
            {"id": "analyze", "label": "Signal analysis", "role": "process", "domain": "CHOP", "op_type": "analyzeCHOP"},
            {"id": "math", "label": "Range shaping", "role": "process", "domain": "CHOP", "op_type": "mathCHOP"},
            {"id": "output", "label": "Control output", "role": "output", "domain": "CHOP", "op_type": "nullCHOP"},
        ),
        edges=(("audio", "analyze", 0, 0, "data"), ("analyze", "math", 0, 0, "data"), ("math", "output", 0, 0, "data")),
    ),
    "render_pipeline": _ProfileSpec(
        topic="render_pipeline",
        primary_op="renderTOP",
        concepts=(
            {"id": "geo", "label": "Geometry", "role": "render", "domain": "COMP", "op_type": "geometryCOMP"},
            {"id": "camera", "label": "Camera", "role": "render", "domain": "COMP", "op_type": "cameraCOMP"},
            {"id": "render", "label": "Render output", "role": "output", "domain": "TOP", "op_type": "renderTOP"},
            {"id": "output", "label": "Stable output", "role": "output", "domain": "TOP", "op_type": "nullTOP"},
        ),
        edges=(("render", "output", 0, 0, "data"),),
    ),
    "pop": _ProfileSpec(
        topic="pop",
        primary_op="circlePOP",
        concepts=(
            {"id": "emit", "label": "Particle emitter", "role": "source", "domain": "POP", "op_type": "circlePOP"},
            {"id": "motion", "label": "Particle motion field", "role": "process", "domain": "POP", "op_type": "noisePOP"},
            {"id": "output", "label": "Finite POP output", "role": "output", "domain": "POP", "op_type": "nullPOP"},
        ),
        edges=(("emit", "motion", 0, 0, "data"), ("motion", "output", 0, 0, "data")),
        risk_flags=("validate-finite-pop-bounds",),
    ),
    "glsl": _ProfileSpec(
        topic="glsl",
        primary_op="glslTOP",
        concepts=(
            {"id": "source", "label": "Input texture", "role": "source", "domain": "TOP", "op_type": "constantTOP"},
            {
                "id": "shader",
                "label": "GLSL shader TOP",
                "role": "process",
                "domain": "TOP",
                "op_type": "glslTOP",
                "create_type": "glsl",
            },
            {"id": "source_code", "label": "Shader source DAT", "role": "validator", "domain": "DAT", "op_type": "textDAT"},
            {"id": "output", "label": "Stable shader output", "role": "output", "domain": "TOP", "op_type": "nullTOP"},
        ),
        edges=(("source", "shader", 0, 0, "data"), ("source_code", "shader", 0, 0, "reference"), ("shader", "output", 0, 0, "data")),
        risk_flags=("validate-glsl-compile-state",),
    ),
    "panel_ui": _ProfileSpec(
        topic="panel_ui",
        primary_op="panelCOMP",
        concepts=(
            {"id": "panel", "label": "Panel container", "role": "ui", "domain": "COMP", "op_type": "containerCOMP"},
            {"id": "slider", "label": "Continuous control", "role": "ui", "domain": "COMP", "op_type": "sliderCOMP"},
            {"id": "button", "label": "Discrete trigger", "role": "ui", "domain": "COMP", "op_type": "buttonCOMP"},
            {"id": "panel_chop", "label": "Panel state reader", "role": "control", "domain": "CHOP", "op_type": "panelCHOP"},
            {"id": "output", "label": "UI control output", "role": "output", "domain": "CHOP", "op_type": "nullCHOP"},
        ),
        edges=(
            ("slider", "panel_chop", 0, 0, "reference"),
            ("button", "panel_chop", 0, 0, "reference"),
            ("panel_chop", "output", 0, 0, "data"),
        ),
        risk_flags=("validate-panel-callbacks-or-exports",),
    ),
    "control_rig": _ProfileSpec(
        topic="custom_parameters",
        primary_op="baseCOMP",
        concepts=(
            {"id": "ctrl", "label": "Custom parameter control COMP", "role": "control", "domain": "COMP", "op_type": "baseCOMP"},
            {"id": "values", "label": "Default control values", "role": "source", "domain": "CHOP", "op_type": "constantCHOP"},
            {"id": "scale", "label": "Range scaling", "role": "process", "domain": "CHOP", "op_type": "mathCHOP"},
            {"id": "output", "label": "Rig control output", "role": "output", "domain": "CHOP", "op_type": "nullCHOP"},
        ),
        edges=(
            ("ctrl", "values", 0, 0, "reference"),
            ("values", "scale", 0, 0, "data"),
            ("scale", "output", 0, 0, "data"),
        ),
        risk_flags=("custom-parameters-required",),
    ),
    "generic": _ProfileSpec(
        concepts=(
            {"id": "output", "label": "Stable output", "role": "output", "domain": "TOP", "op_type": "nullTOP"},
        )
    ),
}


async def build_brain_plan(
    td_client,
    *,
    intent: str,
    target_root: str = "/project1",
    output_top: str | None = None,
    constraints: dict[str, Any] | None = None,
    preferred_domains: list[str] | None = None,
    validation_profile: str = "auto",
    include_memory: bool = True,
    include_docs: bool = True,
    technique_store=None,
    card_index=None,
) -> BrainPlan:
    """Build a grounded BrainPlan without mutating TouchDesigner."""
    task = VisualTaskSpec(
        intent=intent,
        target_root=target_root,
        output_top=output_top,
        constraints=constraints or {},
        preferred_domains=preferred_domains or [],
        validation_profile=validation_profile,
        include_memory=include_memory,
        include_docs=include_docs,
    )
    profile = classify_intent_profile(intent, preferred_domains)
    spec = _PROFILE_SPECS.get(profile)
    if profile == "generic" and _intent_is_under_specified(intent, preferred_domains):
        spec = _PROFILE_SPECS["generic"]
        graph = _empty_graph(task, profile="generic")
        patch_plan = _empty_patch(task, reason="under-specified intent")
        return BrainPlan(
            task=task,
            concept_graph=graph,
            patch_plan=patch_plan,
            blocked_questions=[
                "What visual system should TDPilot build: feedback, audio-reactive, POP, GLSL, render pipeline, panel UI, or a specific operator chain?"
            ],
            missing_facts=["under-specified intent: no supported visual concept matched"],
            grounding_evidence=["profile:generic", "planner:block_under_specified"],
            risk_flags=["under-specified"],
        )

    spec = spec or _PROFILE_SPECS["generic"]
    available_ops = await _read_available_ops(td_client)
    existing_names = await _read_existing_names(td_client, target_root)
    concepts = [ConceptNode(**item) for item in spec.concepts]
    operators = sorted({node.op_type for node in concepts if node.op_type})
    grounding = _grounding_evidence(
        profile=profile,
        spec=spec,
        intent=intent,
        operators=operators,
        card_index=card_index if include_docs else None,
    )
    if technique_store is not None and include_memory:
        grounding.extend(_memory_evidence(technique_store, intent))

    missing_ops, family_omitted_ops = _classify_required_ops(
        operators,
        available_ops,
        card_index=card_index if include_docs else None,
    )
    graph = ConceptGraph(
        task=task,
        profile=profile,
        concepts=concepts,
        edges=[
            ConceptEdge(source=src, target=dst, source_index=src_i, target_index=dst_i, kind=kind)
            for src, dst, src_i, dst_i, kind in spec.edges
        ],
        operators=operators,
        unresolved=missing_ops,
        evidence=grounding,
        risk_flags=[
            *spec.risk_flags,
            *[f"missing-op:{op}" for op in missing_ops],
            *[f"family-list-omitted:{op}" for op in family_omitted_ops],
        ],
    )

    missing_facts = [f"missing_op:{op}" for op in missing_ops]
    blocked_questions = []
    if missing_ops:
        blocked_questions.append(
            "The current TouchDesigner operator family list does not include every required operator. Install/enable the needed TD build or choose an alternate approach."
        )
        patch_plan = _empty_patch(task, reason="missing required operators")
    else:
        patch_plan = _compile_patch_plan(task, graph, existing_names)

    return BrainPlan(
        task=task,
        concept_graph=graph,
        patch_plan=patch_plan,
        validation_profile=_resolve_validation_profile(validation_profile),
        blocked_questions=blocked_questions,
        missing_facts=missing_facts,
        grounding_evidence=grounding,
        risk_flags=list(graph.risk_flags),
    )


def _intent_is_under_specified(intent: str, preferred_domains: list[str] | None) -> bool:
    text = (intent or "").strip().lower()
    if preferred_domains:
        return False
    if len(text.split()) <= 3:
        return True
    vague_tokens = ("better", "cool", "nice", "awesome", "improve", "enhance")
    return any(token in text for token in vague_tokens) and not any(
        token in text
        for token in (
            "feedback",
            "audio",
            "particle",
            "pop",
            "glsl",
            "shader",
            "render",
            "panel",
            "custom parameter",
        )
    )


async def _read_available_ops(td_client) -> set[str]:
    try:
        response = await td_client.request("families", {})
    except Exception:
        return set()
    if not isinstance(response, dict):
        return set()
    families = response.get("families") if isinstance(response.get("families"), dict) else response
    available: set[str] = set()
    if isinstance(families, dict):
        for family, values in families.items():
            if isinstance(values, list):
                for value in values:
                    if value:
                        available.update(_available_op_names(str(family), str(value)))
    return available


_LIVE_FAMILY_ALIASES: dict[tuple[str, str], tuple[str, ...]] = {
    ("COMP", "cam"): ("cameraCOMP",),
    ("COMP", "geo"): ("geometryCOMP",),
}


def _available_op_names(family: str, raw_name: str) -> set[str]:
    family_name = family.upper()
    name = raw_name.strip()
    if not name:
        return set()
    names = {name}
    if not name.upper().endswith(family_name):
        names.add(f"{name}{family_name}")
    names.update(_LIVE_FAMILY_ALIASES.get((family_name, name.lower()), ()))
    return names


async def _read_existing_names(td_client, target_root: str) -> set[str]:
    try:
        response = await td_client.request("nodes", {"path": target_root, "limit": 500})
    except Exception:
        return set()
    nodes = response if isinstance(response, list) else response.get("nodes", []) if isinstance(response, dict) else []
    return {str(node.get("name", "")) for node in nodes if isinstance(node, dict) and node.get("name")}


def _grounding_evidence(
    *,
    profile: str,
    spec: _ProfileSpec,
    intent: str,
    operators: list[str],
    card_index,
) -> list[str]:
    evidence = [f"profile:{profile}"]
    if card_index is not None:
        for op_type in operators:
            try:
                card = card_index.get_operator(op_type)
            except Exception:
                card = None
            if card is not None:
                evidence.append(f"docs:{op_type}")
    try:
        hints = query_hints(topic=spec.topic, op_type=spec.primary_op, intent=intent, max_hints=3)
        for hint in hints.get("hints", [])[:3]:
            hint_id = hint.get("id") or hint.get("source") or spec.topic or profile
            evidence.append(f"hint:{hint_id}")
    except Exception:
        pass
    if not any(item.startswith("hint:") for item in evidence):
        evidence.append(f"hint:profile:{profile}")
    return evidence


def _memory_evidence(technique_store, intent: str) -> list[str]:
    try:
        hits = technique_store.search(query=intent, scope="all", limit=3)
    except Exception:
        return []
    return [f"memory:{item.get('id')}" for item in hits if isinstance(item, dict) and item.get("id")]


def _missing_required_ops(operators: list[str], available_ops: set[str]) -> list[str]:
    missing, _omitted = _classify_required_ops(operators, available_ops, card_index=None)
    return missing


def _classify_required_ops(
    operators: list[str],
    available_ops: set[str],
    *,
    card_index,
) -> tuple[list[str], list[str]]:
    if not available_ops:
        return [], []
    missing: list[str] = []
    family_omitted: list[str] = []
    for op_type in operators:
        if op_type in available_ops:
            continue
        if _operator_has_docs(card_index, op_type):
            family_omitted.append(op_type)
            continue
        missing.append(op_type)
    return sorted(missing), sorted(family_omitted)


def _operator_has_docs(card_index, op_type: str) -> bool:
    if card_index is None:
        return False
    try:
        return card_index.get_operator(op_type) is not None
    except Exception:
        return False


def _compile_patch_plan(task: VisualTaskSpec, graph: ConceptGraph, existing_names: set[str]) -> PatchPlan:
    concept_names = _assign_node_names(graph.concepts, existing_names)
    operations: list[PatchOperation] = []
    for index, concept in enumerate(graph.concepts):
        if not concept.op_type:
            continue
        name = concept_names[concept.id]
        args: dict[str, Any] = {
            "op_type": concept.create_type or concept.op_type,
            "name": name,
            "x": index * 180,
            "y": 0 if concept.domain in {"TOP", "COMP", "MAT"} else -160,
        }
        operations.append(PatchOperation(kind="create_node", target=task.target_root, args=args))
        if concept.params:
            operations.append(
                PatchOperation(
                    kind="set_params",
                    target=_join_path(task.target_root, name),
                    args={"params": concept.params},
                )
            )

    for edge in graph.edges:
        if edge.kind not in {"data", "feedback"}:
            continue
        src_name = concept_names.get(edge.source)
        dst_name = concept_names.get(edge.target)
        if not src_name or not dst_name:
            continue
        operations.append(
            PatchOperation(
                kind="connect",
                target=task.target_root,
                args={
                    "from": _join_path(task.target_root, src_name),
                    "to": _join_path(task.target_root, dst_name),
                    "from_output": edge.source_index,
                    "to_input": edge.target_index,
                },
            )
        )

    return PatchPlan(
        intent=task.intent,
        target_root=task.target_root,
        source="operations",
        operations=operations,
        required_ops=list(graph.operators),
        risk_flags=list(graph.risk_flags),
        undo_label=f"td brain: {task.intent[:42]}",
        validation_plan=ValidationPlan(
            target_root=task.target_root,
            capture_frames=[task.output_top] if task.output_top else [],
        ),
    )


def _assign_node_names(concepts: list[ConceptNode], existing_names: set[str]) -> dict[str, str]:
    used = set(existing_names)
    names: dict[str, str] = {}
    for concept in concepts:
        base = _base_name_for(concept)
        candidate = base
        counter = 1
        while candidate in used:
            counter += 1
            candidate = f"{base}{counter}"
        used.add(candidate)
        names[concept.id] = candidate
    return names


def _base_name_for(concept: ConceptNode) -> str:
    if concept.role == "output":
        return "out1"
    if concept.role in {"control", "ui"}:
        return concept.id
    if concept.op_type:
        suffixes = ("TOP", "CHOP", "SOP", "DAT", "COMP", "MAT", "POP")
        name = concept.op_type
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        return name.lower() or concept.id
    return concept.id


def _join_path(parent: str, name: str) -> str:
    return f"{parent.rstrip('/')}/{name}".replace("//", "/")


def _empty_graph(task: VisualTaskSpec, *, profile: str) -> ConceptGraph:
    return ConceptGraph(task=task, profile=profile, concepts=[], edges=[], operators=[])


def _empty_patch(task: VisualTaskSpec, *, reason: str) -> PatchPlan:
    return PatchPlan(
        intent=task.intent,
        target_root=task.target_root,
        source="operations",
        operations=[],
        required_ops=[],
        risk_flags=[reason],
        undo_label=f"td brain blocked: {task.intent[:32]}",
        validation_plan=ValidationPlan(target_root=task.target_root, capture_frames=[]),
    )


def _resolve_validation_profile(requested: str) -> str:
    if not requested or requested == "auto":
        return "structural_visual_safe"
    return requested
