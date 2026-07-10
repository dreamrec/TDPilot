"""Server-derived intent coverage and semantic-edge execution gates.

This module deliberately uses deterministic request facets and concrete graph /
PatchPlan artifacts.  Host-authored prose and claimed ``complete`` flags are
never accepted as proof.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from td_mcp.brain.param_semantics import semantics_by_op_and_param
from td_mcp.models.brain import (
    BrainPlan,
    CompiledVisualTaskSpec,
    ConceptEdge,
    ConceptGraph,
    CoverageEvidence,
    IntentCoverage,
    IntentRequirement,
)
from td_mcp.models.patch import PatchPlan

_INTERNAL_CONSTRAINT_KEYS = {
    "validation_profile",
    "device_sources",
    "availability_report_path",
    "operator_availability",
    "availability_matrix",
    "availability_report",
    "sampled_unavailable_ops",
    "sampled_unavailable_reasons",
    "td_build",
    "platform",
    "installed_addons",
    "_brain_mode",
    "_brain_inspect",
    "_brain_trace_level",
}

_SPATIAL_TERMS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bparticles?\b|\bpop\b", re.I), "particles"),
    (re.compile(r"\btunnel\b|\bcorridor\b", re.I), "tunnel_depth"),
    (re.compile(r"\bfog\b|\bmist\b|\bhaze\b", re.I), "fog_atmosphere"),
    (re.compile(r"\bvolumetric\b", re.I), "volumetric_space"),
    (re.compile(r"\b3d\b|\bthree[- ]dimensional\b", re.I), "three_dimensional"),
    (re.compile(r"\bcamera\b|\bperspective\b", re.I), "camera_perspective"),
)

_QUALITY_TERMS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bnon[- ]?black\b", re.I), "nonblack_output"),
    (re.compile(r"\btempor(?:al|ally)\s+(?:change|motion)\b", re.I), "temporal_change"),
)


def build_intent_requirements(compiled: CompiledVisualTaskSpec) -> list[IntentRequirement]:
    """Extract stable material facets from deterministic compiler output plus narrow spatial terms."""
    rows: list[tuple[str, str]] = []
    rows.extend(("capability", item) for item in compiled.required_capabilities)
    for item in compiled.inputs:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "input")
        domain = str(item.get("domain") or "ANY")
        rows.append(("input", f"{kind}:{domain}"))
    for item in compiled.outputs:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "output")
        domain = str(item.get("domain") or "ANY")
        rows.append(("output", f"{kind}:{domain}"))
    rows.extend(("behavior", item) for item in compiled.time_behavior)
    rows.extend(("validation", item) for item in compiled.validation_needs)

    for key, value in sorted(compiled.constraints.items()):
        if key in _INTERNAL_CONSTRAINT_KEYS or value in (None, "", [], {}):
            continue
        rows.append(("constraint", f"{key}={_compact_constraint(value)}"))

    for pattern, label in _SPATIAL_TERMS:
        if pattern.search(compiled.intent):
            rows.append(("spatial", label))
    for pattern, label in _QUALITY_TERMS:
        if pattern.search(compiled.intent):
            rows.append(("quality", label))

    has_audio = any(str(item.get("kind")) == "audio" for item in compiled.inputs if isinstance(item, dict))
    has_visual_output = any(
        str(item.get("domain")) in {"TOP", "SOP", "POP", "COMP", "MAT"}
        for item in compiled.outputs
        if isinstance(item, dict)
    )
    if has_audio and has_visual_output:
        rows.append(("binding", "audio_to_visual_control"))

    requirements: list[IntentRequirement] = []
    seen: set[tuple[str, str]] = set()
    for kind, label in rows:
        normalized = str(label).strip()
        key = (kind, normalized)
        if not normalized or key in seen:
            continue
        seen.add(key)
        requirements.append(
            IntentRequirement(
                id=f"req:{kind}:{_slug(normalized)}",
                kind=kind,
                label=normalized,
            )
        )
    return requirements


def compute_intent_coverage(
    compiled: CompiledVisualTaskSpec,
    graph: ConceptGraph,
    patch_plan: PatchPlan,
    *,
    validation_needs: Iterable[str] = (),
) -> IntentCoverage:
    """Recompute coverage from authoritative compiler, graph, and PatchPlan artifacts."""
    requirements = build_intent_requirements(compiled)
    validation_set = {str(item) for item in validation_needs}
    evidence: list[CoverageEvidence] = []
    for requirement in requirements:
        provider_kind, provider_ids, note = _providers_for_requirement(
            requirement,
            graph,
            patch_plan,
            validation_needs=validation_set,
        )
        if provider_ids:
            evidence.append(
                CoverageEvidence(
                    requirement_id=requirement.id,
                    provider_kind=provider_kind,
                    provider_ids=provider_ids,
                    note=note,
                )
            )
    return IntentCoverage(
        requirements=requirements,
        evidence=evidence,
        unresolved_semantic_edges=semantic_edge_issues(graph, patch_plan),
    )


def recompute_plan_intent_coverage(plan: BrainPlan) -> IntentCoverage | None:
    """Rebuild a v2 plan's coverage from its authoritative artifacts.

    ``None`` is the explicit legacy compatibility marker.  If a coverage
    object is present, execution must use this recomputed result rather than
    trusting serialized evidence from the caller.
    """
    if plan.intent_coverage is None:
        return None
    if plan.compiled_task is None:
        return IntentCoverage(
            requirements=[],
            evidence=[],
            unresolved_semantic_edges=["v2_plan:missing_compiled_task"],
        )
    validation_needs = (
        plan.candidate_graphs[0].validation_needs
        if plan.candidate_graphs
        else plan.compiled_task.validation_needs
    )
    return compute_intent_coverage(
        plan.compiled_task,
        plan.concept_graph,
        plan.patch_plan,
        validation_needs=validation_needs,
    )


def semantic_edge_issues(graph: ConceptGraph, patch_plan: PatchPlan) -> list[str]:
    """Return stable issue markers for semantic edges not realized by PatchOperations."""
    concepts = {item.id: item for item in graph.concepts}
    paths = _concept_paths(graph, patch_plan)
    issues = [f"unresolved_concept:{item}" for item in graph.unresolved]
    for index, edge in enumerate(graph.edges):
        edge_id = _edge_id(edge, index)
        source = concepts.get(edge.source)
        target = concepts.get(edge.target)
        source_path = paths.get(edge.source)
        target_path = paths.get(edge.target)
        if source is None or target is None or source_path is None or target_path is None:
            issues.append(f"{edge_id}:missing_concept_operation")
            continue
        if edge.kind in {"data", "feedback"}:
            if not _has_connect(patch_plan, source_path, target_path, edge):
                issues.append(f"{edge_id}:missing_connect")
        elif edge.kind == "reference":
            if not _has_reference(patch_plan, source_path, target_path):
                issues.append(f"{edge_id}:missing_reference_binding")
        elif edge.kind == "control":
            binding_issue = _control_binding_issue(edge, source, target, source_path, target_path, patch_plan)
            if binding_issue:
                issues.append(f"{edge_id}:{binding_issue}")
    return list(dict.fromkeys(issues))


def control_binding_operation(
    edge: ConceptEdge,
    *,
    source_op_type: str | None,
    target_op_type: str | None,
    source_path: str,
    target_path: str,
    target_params: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Return ``(target_param, expression payload)`` or raise for an unsafe binding."""
    binding = edge.binding
    if edge.kind != "control" or binding is None:
        raise ValueError("control edge requires an explicit binding")
    if not source_op_type or not source_op_type.endswith("CHOP"):
        raise ValueError("control binding source must be a CHOP concept")
    if target_op_type != "levelTOP":
        raise ValueError("v2 control bindings currently support levelTOP targets only")
    if binding.target_param in target_params:
        raise ValueError(f"control binding conflicts with static target param {binding.target_param}")
    semantic = semantics_by_op_and_param().get((target_op_type, binding.target_param))
    if semantic is None or semantic.validation_rule != "numeric_level_adjustment":
        raise ValueError("control binding target must be a registry-backed numeric levelTOP parameter")
    channel = binding.source_channel
    selector = str(channel) if isinstance(channel, int) else repr(channel)
    return binding.target_param, {"expr": f"op({source_path!r})[{selector}]"}


def _providers_for_requirement(
    requirement: IntentRequirement,
    graph: ConceptGraph,
    patch_plan: PatchPlan,
    *,
    validation_needs: set[str],
) -> tuple[str, list[str], str]:
    if requirement.kind == "capability":
        providers = _capability_providers(requirement.label, graph)
        return "concept", providers, "operator/profile capability proof"
    if requirement.kind == "input":
        kind, _, domain = requirement.label.partition(":")
        providers = [
            item.id
            for item in graph.concepts
            if item.role == "source"
            and (domain == "ANY" or item.domain == domain)
            and _input_kind_matches(kind, item.op_type or "")
        ]
        return "concept", providers, "source concept proof"
    if requirement.kind == "output":
        output_kind, _, domain = requirement.label.partition(":")
        providers = [
            item.id
            for item in graph.concepts
            if (
                item.role in {"output", "render"}
                or (output_kind == "debug_output" and item.role == "validator")
            )
            and (domain == "ANY" or item.domain == domain)
        ]
        return "concept", providers, "stable output concept proof"
    if requirement.kind == "behavior":
        providers = _behavior_providers(requirement.label, graph, patch_plan)
        return "concept", providers, "time-behavior graph proof"
    if requirement.kind == "validation":
        providers = [requirement.label] if requirement.label in validation_needs else []
        return "validation", providers, "selected validation probe"
    if requirement.kind == "spatial":
        providers = _spatial_providers(requirement.label, graph)
        return "concept", providers, "spatial architecture proof"
    if requirement.kind == "quality":
        aliases = {
            "nonblack_output": {"nonblack_output", "cheap_visual_metrics", "feedback_output_readback"},
            "temporal_change": {"cheap_visual_metrics", "feedback_output_readback"},
        }
        matched = sorted(aliases.get(requirement.label, set()).intersection(validation_needs))
        return "validation", matched, "quality validation proof"
    if requirement.kind == "binding":
        paths = _concept_paths(graph, patch_plan)
        providers = []
        concepts = {item.id: item for item in graph.concepts}
        for index, edge in enumerate(graph.edges):
            source = concepts.get(edge.source)
            target = concepts.get(edge.target)
            if edge.kind != "control" or source is None or target is None:
                continue
            source_path = paths.get(edge.source)
            target_path = paths.get(edge.target)
            if not source_path or not target_path:
                continue
            if _control_binding_issue(edge, source, target, source_path, target_path, patch_plan) is None:
                providers.append(_edge_id(edge, index))
        return "binding", providers, "lowered CHOP reference expression"
    # Hard constraints remain uncovered until a compiler emits explicit proof.
    return "constraint", [], "constraint requires compiler evidence"


def _capability_providers(label: str, graph: ConceptGraph) -> list[str]:
    by_type: dict[str, list[str]] = {}
    for item in graph.concepts:
        if item.op_type:
            by_type.setdefault(item.op_type, []).append(item.id)
    if label == "debug_output":
        return [item.id for item in graph.concepts if item.role == "validator" and item.domain == "DAT"]
    profile = graph.profile
    rules: dict[str, tuple[str, ...]] = {
        "audio_analysis": ("analyzeCHOP", "mathCHOP", "nullCHOP"),
        "feedback_loop": ("feedbackTOP", "levelTOP", "compositeTOP"),
        "render_pipeline": ("renderTOP", "cameraCOMP", "geometryCOMP"),
        "material_modulation": ("glslMAT",),
        "panel_controls": ("containerCOMP", "panelCHOP"),
        "pop_particle_field_preview": ("nullPOP", "rendersimpleTOP"),
        "glsl_advanced_pop_topology": ("glsladvancedPOP", "nullPOP"),
        "glsl_top_shader": ("glslTOP", "textDAT"),
        "terrain_surface": ("gridSOP", "noiseSOP", "nullSOP"),
        "midi_control": ("midiinCHOP", "nullCHOP"),
        "serial_dat_protocol": ("serialDAT", "nullDAT"),
        "osc_dat_protocol": ("oscinDAT", "nullDAT"),
        "websocket_dat_protocol": ("websocketDAT", "nullDAT"),
        "mqtt_dat_protocol": ("mqttclientDAT", "nullDAT"),
        "udp_dat_protocol": ("udpinDAT", "nullDAT"),
        "dat_table_render_switch": ("tableDAT", "switchTOP", "nullTOP"),
        "dat_execute_callback": ("datexecuteDAT", "tableDAT"),
        "ndi_input": ("ndiinTOP",),
        "post_fx_output": ("levelTOP", "nullTOP"),
    }
    if label == "render_pipeline" and "rendersimpleTOP" in by_type:
        return [by_type["rendersimpleTOP"][0]]
    required_types = rules.get(label)
    if required_types is None:
        # A profile name is weak evidence only for known single-profile routes.
        return [f"profile:{profile}"] if label == profile else []
    if not all(op_type in by_type for op_type in required_types):
        return []
    return [by_type[op_type][0] for op_type in required_types]


def _behavior_providers(label: str, graph: ConceptGraph, patch_plan: PatchPlan) -> list[str]:
    types = {item.op_type for item in graph.concepts if item.op_type}
    if label == "beat_or_amplitude_modulation":
        bindings = compute_binding_provider_ids(graph, patch_plan)
        if bindings:
            return bindings
        analysis_types = {"analyzeCHOP", "mathCHOP", "nullCHOP"}
        if analysis_types.issubset(types):
            return [item.id for item in graph.concepts if item.op_type in analysis_types]
        return []
    if label == "continuous_feedback" and "feedbackTOP" in types:
        return [item.id for item in graph.concepts if item.op_type == "feedbackTOP"]
    if label == "continuous_animation" and types.intersection(
        {
            "noiseTOP",
            "noiseSOP",
            "noisePOP",
            "glslTOP",
            "glslPOP",
            "glsladvancedPOP",
            "renderTOP",
            "rendersimpleTOP",
        }
    ):
        return [item.id for item in graph.concepts if item.op_type in types][:1]
    if label in {"shader_frame_cook", "gpu_compute_dispatch"} and types.intersection(
        {"glslTOP", "glslMAT", "glsladvancedPOP"}
    ):
        return [
            item.id for item in graph.concepts if item.op_type in {"glslTOP", "glslMAT", "glsladvancedPOP"}
        ]
    if label in {
        "event_driven_control",
        "event_driven_callback",
        "table_driven_switching",
    } and types.intersection({"midiinCHOP", "panelCHOP", "datexecuteDAT", "switchTOP"}):
        return [
            item.id
            for item in graph.concepts
            if item.op_type in {"midiinCHOP", "panelCHOP", "datexecuteDAT", "switchTOP"}
        ]
    if label in {"streaming_input", "live_device_stream"}:
        return [item.id for item in graph.concepts if item.role == "source"]
    return []


def compute_binding_provider_ids(graph: ConceptGraph, patch_plan: PatchPlan) -> list[str]:
    paths = _concept_paths(graph, patch_plan)
    concepts = {item.id: item for item in graph.concepts}
    providers: list[str] = []
    for index, edge in enumerate(graph.edges):
        source = concepts.get(edge.source)
        target = concepts.get(edge.target)
        if edge.kind != "control" or source is None or target is None:
            continue
        source_path = paths.get(edge.source)
        target_path = paths.get(edge.target)
        if not source_path or not target_path:
            continue
        if _control_binding_issue(edge, source, target, source_path, target_path, patch_plan) is None:
            providers.append(_edge_id(edge, index))
    return providers


def _spatial_providers(label: str, graph: ConceptGraph) -> list[str]:
    if label == "particles":
        return [item.id for item in graph.concepts if item.domain == "POP"]
    if label in {"three_dimensional", "camera_perspective"}:
        needed = {"cameraCOMP", "geometryCOMP", "renderTOP"}
        present = {item.op_type for item in graph.concepts if item.op_type}
        return (
            [item.id for item in graph.concepts if item.op_type in needed] if needed.issubset(present) else []
        )
    # A generic render pipeline does not prove a tunnel, fog, or volumetric scene.
    return []


def _input_kind_matches(kind: str, op_type: str) -> bool:
    prefixes = {
        "audio": ("audiofilein", "audiodevicein"),
        "midi": ("midiin",),
        "serial": ("serial",),
        "osc": ("oscin",),
        "websocket": ("websocket",),
        "mqtt": ("mqttclient",),
        "udp": ("udpin",),
        "ndi": ("ndiin",),
    }
    wanted = prefixes.get(kind)
    return True if wanted is None else op_type.lower().startswith(wanted)


def _concept_paths(graph: ConceptGraph, patch_plan: PatchPlan) -> dict[str, str]:
    create_ops = [
        operation
        for operation in patch_plan.operations
        if operation.kind == "create_node"
        and operation.args.get("assembly_macro_id") != "make_component_shell"
    ]
    paths: dict[str, str] = {}
    create_index = 0
    for concept in graph.concepts:
        if not concept.op_type:
            continue
        if create_index >= len(create_ops):
            break
        operation = create_ops[create_index]
        name = operation.args.get("name")
        parent = operation.target or patch_plan.target_root
        if name:
            paths[concept.id] = f"{str(parent).rstrip('/')}/{name}".replace("//", "/")
        create_index += 1
    return paths


def _has_connect(plan: PatchPlan, source_path: str, target_path: str, edge: ConceptEdge) -> bool:
    return any(
        operation.kind == "connect"
        and operation.args.get("from") == source_path
        and operation.args.get("to") == target_path
        and int(operation.args.get("from_output", 0)) == edge.source_index
        and int(operation.args.get("to_input", 0)) == edge.target_index
        for operation in plan.operations
    )


def _has_reference(plan: PatchPlan, source_path: str, target_path: str) -> bool:
    return any(
        operation.target == target_path
        and (
            (operation.kind == "set_params" and _value_contains(operation.args.get("params"), source_path))
            or (
                operation.kind == "set_dat_content"
                and _value_contains(operation.args.get("generated_code"), source_path)
            )
        )
        for operation in plan.operations
    )


def _control_binding_issue(edge, source, target, source_path, target_path, plan) -> str | None:
    try:
        target_param, payload = control_binding_operation(
            edge,
            source_op_type=source.create_type or source.op_type,
            target_op_type=target.op_type,
            source_path=source_path,
            target_path=target_path,
            target_params=target.params,
        )
    except ValueError as exc:
        return _slug(str(exc)).replace("-", "_")
    if not any(
        operation.kind == "set_params"
        and operation.target == target_path
        and (operation.args.get("params") or {}).get(target_param) == payload
        for operation in plan.operations
    ):
        return "binding_not_lowered"
    return None


def _value_contains(value: Any, expected: str) -> bool:
    if isinstance(value, dict):
        return any(_value_contains(item, expected) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_value_contains(item, expected) for item in value)
    if isinstance(value, str):
        return value == expected or expected in value
    return value == expected


def _edge_id(edge: ConceptEdge, index: int) -> str:
    return f"edge:{index}:{edge.source}->{edge.target}:{edge.kind}"


def _compact_constraint(value: Any) -> str:
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return ",".join(str(item) for item in value[:8])
    if isinstance(value, dict):
        return ",".join(f"{key}:{value[key]}" for key in sorted(value)[:8])
    return type(value).__name__


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-") or "unspecified"


__all__ = [
    "build_intent_requirements",
    "compute_binding_provider_ids",
    "compute_intent_coverage",
    "control_binding_operation",
    "recompute_plan_intent_coverage",
    "semantic_edge_issues",
]
