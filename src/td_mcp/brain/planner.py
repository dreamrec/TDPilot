"""Semantic TD brain planner: intent -> concept graph -> typed PatchPlan."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from td_mcp.brain.assembly_macros import macros_for_profiles
from td_mcp.brain.atlas_drafter import AtlasDraftResult, draft_atlas_candidate_graph
from td_mcp.brain.code_harness import validate_patch_plan_generated_code
from td_mcp.brain.concept_compiler import (
    build_candidate_graphs,
    compile_visual_task,
    is_supported_compiler_route,
)
from td_mcp.brain.corpus_bridge import build_corpus_evidence, corpus_evidence_markers
from td_mcp.brain.operator_availability import (
    build_operator_availability_matrix,
    load_operator_availability_report,
    substitution_explanations_from_evidence,
)
from td_mcp.brain.param_semantics import (
    load_param_semantics_registry,
    parameter_risk_flags_for_plan,
    validate_patch_plan_parameter_contract,
)
from td_mcp.brain.param_semantics_drafts import draft_param_semantics_from_docs
from td_mcp.brain.validators import classify_intent_profile
from td_mcp.hints import query_hints
from td_mcp.models.brain import (
    BrainPlan,
    CandidateConceptGraph,
    ConceptEdge,
    ConceptGraph,
    ConceptNode,
    OperatorAvailabilityMatrix,
    VisualTaskSpec,
)
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
            {
                "id": "source",
                "label": "Noise source",
                "role": "source",
                "domain": "TOP",
                "op_type": "noiseTOP",
            },
            {
                "id": "feedback",
                "label": "Feedback buffer",
                "role": "feedback",
                "domain": "TOP",
                "op_type": "feedbackTOP",
            },
            {
                "id": "decay",
                "label": "Decay and level",
                "role": "process",
                "domain": "TOP",
                "op_type": "levelTOP",
            },
            {
                "id": "composite",
                "label": "Composite merge",
                "role": "process",
                "domain": "TOP",
                "op_type": "compositeTOP",
            },
            {
                "id": "output",
                "label": "Stable output",
                "role": "output",
                "domain": "TOP",
                "op_type": "nullTOP",
            },
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
            {
                "id": "analyze",
                "label": "Signal analysis",
                "role": "process",
                "domain": "CHOP",
                "op_type": "analyzeCHOP",
            },
            {
                "id": "math",
                "label": "Range shaping",
                "role": "process",
                "domain": "CHOP",
                "op_type": "mathCHOP",
            },
            {
                "id": "output",
                "label": "Control output",
                "role": "output",
                "domain": "CHOP",
                "op_type": "nullCHOP",
            },
        ),
        edges=(
            ("audio", "analyze", 0, 0, "data"),
            ("analyze", "math", 0, 0, "data"),
            ("math", "output", 0, 0, "data"),
        ),
    ),
    "render_pipeline": _ProfileSpec(
        topic="render_pipeline",
        primary_op="renderTOP",
        concepts=(
            {"id": "geo", "label": "Geometry", "role": "render", "domain": "COMP", "op_type": "geometryCOMP"},
            {"id": "camera", "label": "Camera", "role": "render", "domain": "COMP", "op_type": "cameraCOMP"},
            {
                "id": "render",
                "label": "Render output",
                "role": "output",
                "domain": "TOP",
                "op_type": "renderTOP",
                "params": {"camera": "${path:camera}", "geometry": "${path:geo}"},
            },
            {
                "id": "output",
                "label": "Stable output",
                "role": "output",
                "domain": "TOP",
                "op_type": "nullTOP",
            },
        ),
        edges=(("render", "output", 0, 0, "data"),),
    ),
    "pop": _ProfileSpec(
        topic="pop",
        primary_op="circlePOP",
        concepts=(
            {
                "id": "emit",
                "label": "Particle emitter",
                "role": "source",
                "domain": "POP",
                "op_type": "circlePOP",
            },
            {
                "id": "motion",
                "label": "Particle motion field",
                "role": "process",
                "domain": "POP",
                "op_type": "noisePOP",
            },
            {
                "id": "shape",
                "label": "Attribute shaping",
                "role": "process",
                "domain": "POP",
                "op_type": "mathmixPOP",
            },
            {
                "id": "pop_out",
                "label": "Finite POP output",
                "role": "output",
                "domain": "POP",
                "op_type": "nullPOP",
            },
            {
                "id": "preview",
                "label": "POP render preview",
                "role": "render",
                "domain": "TOP",
                "op_type": "rendersimpleTOP",
                "create_type": "rendersimple",
                "params": {"pop": "${path:pop_out}", "normalizegeo": True},
            },
            {
                "id": "output",
                "label": "Stable rendered output",
                "role": "output",
                "domain": "TOP",
                "op_type": "nullTOP",
            },
        ),
        edges=(
            ("emit", "motion", 0, 0, "data"),
            ("motion", "shape", 0, 0, "data"),
            ("shape", "pop_out", 0, 0, "data"),
            ("pop_out", "preview", 0, 0, "reference"),
            ("preview", "output", 0, 0, "data"),
        ),
        risk_flags=("validate-finite-pop-bounds", "validate-pop-render-preview"),
    ),
    "glsl": _ProfileSpec(
        topic="glsl",
        primary_op="glslTOP",
        concepts=(
            {
                "id": "source",
                "label": "Input texture",
                "role": "source",
                "domain": "TOP",
                "op_type": "constantTOP",
            },
            {
                "id": "shader",
                "label": "GLSL shader TOP",
                "role": "process",
                "domain": "TOP",
                "op_type": "glslTOP",
                "create_type": "glsl",
                "params": {"pixeldat": "${path:source_code}", "glslversion": "glsl460"},
            },
            {
                "id": "source_code",
                "label": "Shader source DAT",
                "role": "validator",
                "domain": "DAT",
                "op_type": "textDAT",
                "content": {
                    "text": (
                        "layout(location = 0) out vec4 fragColor;\n"
                        "void main() {\n"
                        "    vec4 color = vec4(vUV.st, 0.5, 1.0);\n"
                        "    fragColor = TDOutputSwizzle(color);\n"
                        "}\n"
                    )
                },
                "generated_code": {
                    "block_id": "glsl_top_shader",
                    "language": "glsl",
                    "target_op": "${path:shader}",
                    "target_param": "pixeldat",
                    "source_kind": "generated",
                    "source_refs": ["${path:source_code}"],
                    "static_checks": [
                        "glsl_no_version_line",
                        "glsl_top_declares_pixel_output",
                        "glsl_top_uses_td_output_swizzle",
                    ],
                    "runtime_checks": ["compile_state"],
                    "expected_outputs": ["${path:output}"],
                    "risk_flags": ["validate-glsl-compile-state"],
                    "official_sources": [
                        "https://docs.derivative.ca/GLSL_TOP",
                        "https://docs.derivative.ca/Write_a_GLSL_TOP",
                    ],
                },
            },
            {
                "id": "output",
                "label": "Stable shader output",
                "role": "output",
                "domain": "TOP",
                "op_type": "nullTOP",
            },
        ),
        edges=(
            ("source", "shader", 0, 0, "data"),
            ("source_code", "shader", 0, 0, "reference"),
            ("shader", "output", 0, 0, "data"),
        ),
        risk_flags=("validate-glsl-compile-state",),
    ),
    "glsl_material": _ProfileSpec(
        topic="glsl",
        primary_op="glslMAT",
        concepts=(
            {
                "id": "geo",
                "label": "Geometry container",
                "role": "render",
                "domain": "COMP",
                "op_type": "geometryCOMP",
                "params": {"material": "${path:material}"},
            },
            {"id": "camera", "label": "Camera", "role": "render", "domain": "COMP", "op_type": "cameraCOMP"},
            {
                "id": "material",
                "label": "GLSL material",
                "role": "material",
                "domain": "MAT",
                "op_type": "glslMAT",
                "create_type": "glslMAT",
                "params": {
                    "vdat": "${path:vertex_code}",
                    "pdat": "${path:pixel_code}",
                    "glslversion": "glsl460",
                },
            },
            {
                "id": "vertex_code",
                "label": "Vertex shader DAT",
                "role": "validator",
                "domain": "DAT",
                "op_type": "textDAT",
            },
            {
                "id": "pixel_code",
                "label": "Pixel shader DAT",
                "role": "validator",
                "domain": "DAT",
                "op_type": "textDAT",
            },
            {
                "id": "render",
                "label": "Rendered material output",
                "role": "output",
                "domain": "TOP",
                "op_type": "renderTOP",
                "params": {"camera": "${path:camera}", "geometry": "${path:geo}"},
            },
            {
                "id": "output",
                "label": "Stable render output",
                "role": "output",
                "domain": "TOP",
                "op_type": "nullTOP",
            },
        ),
        edges=(
            ("material", "geo", 0, 0, "reference"),
            ("vertex_code", "material", 0, 0, "reference"),
            ("pixel_code", "material", 0, 0, "reference"),
            ("geo", "render", 0, 0, "reference"),
            ("camera", "render", 0, 0, "reference"),
            ("render", "output", 0, 0, "data"),
        ),
        risk_flags=("validate-glsl-compile-state", "validate-material-assignment"),
    ),
    "glsl_pop": _ProfileSpec(
        topic="glsl",
        primary_op="glslPOP",
        concepts=(
            {
                "id": "source",
                "label": "POP source",
                "role": "source",
                "domain": "POP",
                "op_type": "circlePOP",
            },
            {
                "id": "shader",
                "label": "GLSL POP attribute shader",
                "role": "process",
                "domain": "POP",
                "op_type": "glslPOP",
                "params": {"computedat": "${path:source_code}", "attrclass": "point"},
            },
            {
                "id": "source_code",
                "label": "Compute shader DAT",
                "role": "validator",
                "domain": "DAT",
                "op_type": "textDAT",
                "content": {
                    "text": (
                        "void main() {\n"
                        "    uint idx = TDIndex();\n"
                        "    if (idx >= TDNumElements()) {\n"
                        "        return;\n"
                        "    }\n"
                        "    P += vec3(0.0, 0.04 * sin(float(idx) * 0.17), 0.0);\n"
                        "}\n"
                    )
                },
                "generated_code": {
                    "block_id": "glsl_pop_compute_shader",
                    "language": "glsl",
                    "target_op": "${path:shader}",
                    "target_param": "computedat",
                    "source_kind": "generated",
                    "source_refs": ["${path:source_code}"],
                    "static_checks": ["glsl_no_version_line", "glsl_pop_bounds_guard"],
                    "runtime_checks": ["compile_state", "finite_pop_bounds"],
                    "expected_outputs": ["${path:pop_out}", "${path:output}"],
                    "risk_flags": ["validate-glsl-compile-state", "validate-finite-pop-bounds"],
                    "official_sources": [
                        "https://docs.derivative.ca/GLSL_POP",
                        "https://docs.derivative.ca/Write_a_GLSL_POP",
                    ],
                },
            },
            {
                "id": "pop_out",
                "label": "Stable POP output",
                "role": "output",
                "domain": "POP",
                "op_type": "nullPOP",
            },
            {
                "id": "preview",
                "label": "Rendered POP preview",
                "role": "render",
                "domain": "TOP",
                "op_type": "rendersimpleTOP",
                "create_type": "rendersimple",
                "params": {"pop": "${path:pop_out}", "normalizegeo": True},
            },
            {
                "id": "output",
                "label": "Stable rendered output",
                "role": "output",
                "domain": "TOP",
                "op_type": "nullTOP",
            },
        ),
        edges=(
            ("source", "shader", 0, 0, "data"),
            ("source_code", "shader", 0, 0, "reference"),
            ("shader", "pop_out", 0, 0, "data"),
            ("pop_out", "preview", 0, 0, "reference"),
            ("preview", "output", 0, 0, "data"),
        ),
        risk_flags=("validate-glsl-compile-state", "validate-finite-pop-bounds"),
    ),
    "panel_ui": _ProfileSpec(
        topic="panel_ui",
        primary_op="panelCOMP",
        concepts=(
            {
                "id": "panel",
                "label": "Panel container",
                "role": "ui",
                "domain": "COMP",
                "op_type": "containerCOMP",
            },
            {
                "id": "slider",
                "label": "Continuous control",
                "role": "ui",
                "domain": "COMP",
                "op_type": "sliderCOMP",
            },
            {
                "id": "button",
                "label": "Discrete trigger",
                "role": "ui",
                "domain": "COMP",
                "op_type": "buttonCOMP",
            },
            {
                "id": "panel_chop",
                "label": "Panel state reader",
                "role": "control",
                "domain": "CHOP",
                "op_type": "panelCHOP",
            },
            {
                "id": "output",
                "label": "UI control output",
                "role": "output",
                "domain": "CHOP",
                "op_type": "nullCHOP",
            },
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
            {
                "id": "ctrl",
                "label": "Custom parameter control COMP",
                "role": "control",
                "domain": "COMP",
                "op_type": "baseCOMP",
            },
            {
                "id": "values",
                "label": "Default control values",
                "role": "source",
                "domain": "CHOP",
                "op_type": "constantCHOP",
            },
            {
                "id": "scale",
                "label": "Range scaling",
                "role": "process",
                "domain": "CHOP",
                "op_type": "mathCHOP",
            },
            {
                "id": "output",
                "label": "Rig control output",
                "role": "output",
                "domain": "CHOP",
                "op_type": "nullCHOP",
            },
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
            {
                "id": "output",
                "label": "Stable output",
                "role": "output",
                "domain": "TOP",
                "op_type": "nullTOP",
            },
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
    constraints_data = constraints or {}
    task = VisualTaskSpec(
        intent=intent,
        target_root=target_root,
        output_top=output_top,
        constraints=constraints_data,
        preferred_domains=preferred_domains or [],
        validation_profile=validation_profile,
        include_memory=include_memory,
        include_docs=include_docs,
    )
    compiled_task = compile_visual_task(
        intent,
        target_root=target_root,
        output_top=output_top,
        constraints=constraints,
        preferred_domains=preferred_domains,
        validation_profile=validation_profile,
        card_index=card_index if include_docs else None,
    )
    if _intent_is_complex_multi_output_library(intent):
        graph = _empty_graph(task, profile="generic")
        patch_plan = _empty_patch(
            task, reason="complex multi-output library brief requires explicit compiler"
        )
        return BrainPlan(
            task=task,
            concept_graph=graph,
            patch_plan=patch_plan,
            validation_profile=_resolve_validation_profile(validation_profile),
            blocked_questions=[
                "This request asks for multiple distinct visual systems plus an interactive review library. The current safe compiler cannot guarantee concept diversity, panel navigation, visual QA, and 60 fps performance in one BrainPlan yet. Split the brief into smaller systems: for each one, call td_brain_ground, author a draft candidate graph, validate it with td_brain_propose, then run td_brain_execute(plan_id=...)."
            ],
            missing_facts=["complex_multi_output_library"],
            grounding_evidence=[
                "profile:generic",
                "planner:blocked_complex_multi_output",
                "requires:multi_output_diversity",
                "requires:panel_interaction_validation",
                "requires:visual_quality_gate",
            ],
            risk_flags=["multi-output-brief", "needs-diversity-compiler", "needs-panel-validator"],
        )
    supported_compiler_route = is_supported_compiler_route(compiled_task)
    if supported_compiler_route:
        available_ops = await _read_available_ops(td_client)
        constraint_availability_matrix = _availability_matrix_from_constraints(constraints_data)
        sampled_unavailable_ops = _sampled_unavailable_ops_from_constraints(constraints_data)
        sampled_unavailable_reasons = _sampled_unavailable_reasons_from_constraints(constraints_data)
        available_ops = available_ops - sampled_unavailable_ops
        availability_matrix = build_operator_availability_matrix(
            available_ops,
            required_ops=_compiler_route_required_ops(),
            td_build=_availability_td_build(constraints_data, constraint_availability_matrix),
            platform=_availability_platform(constraints_data, constraint_availability_matrix),
            installed_addons=_availability_installed_addons(constraints_data, constraint_availability_matrix),
        )
        availability_matrix = _availability_matrix_with_sampled_reasons(
            availability_matrix,
            sampled_unavailable_reasons,
        )
        candidate_graphs = build_candidate_graphs(
            compiled_task,
            patterns=_compiler_pattern_registry(include_memory=include_memory),
            availability_matrix=availability_matrix,
            device_sources=_device_sources_from_constraints(constraints_data),
        )
        if candidate_graphs:
            existing_names = await _read_existing_names(td_client, target_root)
            return _plan_from_candidate_graph(
                task=task,
                compiled_task=compiled_task,
                candidate_graphs=candidate_graphs,
                available_ops=available_ops,
                existing_names=existing_names,
                card_index=card_index if include_docs else None,
                validation_profile=validation_profile,
                sampled_unavailable_ops=sampled_unavailable_ops,
                sampled_unavailable_reasons=sampled_unavailable_reasons,
                availability_matrix=availability_matrix,
            )

    profile = classify_intent_profile(intent, preferred_domains)
    spec = _PROFILE_SPECS.get(profile)
    if profile == "generic" and _intent_is_under_specified(intent, preferred_domains):
        corpus_evidence = build_corpus_evidence(
            intent=intent,
            operators=[],
            card_index=card_index if include_docs else None,
            limit_per_query=16,
            max_records=12,
        )
        spec = _PROFILE_SPECS["generic"]
        graph = _empty_graph(task, profile="generic")
        patch_plan = _empty_patch(task, reason="under-specified intent")
        grounding = _dedupe(
            [
                "profile:generic",
                "planner:block_under_specified",
                *corpus_evidence_markers(corpus_evidence),
            ]
        )
        return BrainPlan(
            task=task,
            concept_graph=graph,
            patch_plan=patch_plan,
            blocked_questions=[
                "What visual system should TDPilot build: feedback, audio-reactive, POP, GLSL, render pipeline, panel UI, or a specific operator chain? If the intent is already clear to you, call td_brain_ground with a sharper intent, author a draft candidate graph, and validate it with td_brain_propose instead of stopping here."
            ],
            missing_facts=["under-specified intent: no supported visual concept matched"],
            grounding_evidence=grounding,
            corpus_evidence=corpus_evidence,
            risk_flags=["under-specified"],
        )

    if profile == "generic" and not supported_compiler_route:
        corpus_evidence = build_corpus_evidence(
            intent=intent,
            operators=[],
            card_index=card_index if include_docs else None,
            limit_per_query=16,
            max_records=24,
        )
        atlas_draft = draft_atlas_candidate_graph(
            task=task,
            compiled_task=compiled_task,
            corpus_evidence=corpus_evidence,
            card_index=card_index if include_docs else None,
        )
        if atlas_draft.accepted and atlas_draft.candidate_graph is not None:
            available_ops = await _read_available_ops(td_client)
            existing_names = await _read_existing_names(td_client, target_root)
            return _plan_from_atlas_candidate_graph(
                task=task,
                compiled_task=compiled_task,
                atlas_draft=atlas_draft,
                available_ops=available_ops,
                existing_names=existing_names,
                card_index=card_index if include_docs else None,
                validation_profile=validation_profile,
            )

        graph = _empty_graph(task, profile="generic")
        patch_plan = _empty_patch(task, reason="open prompt requires atlas-grounded planner")
        grounding = _dedupe(
            [
                "profile:generic",
                "planner:open_prompt_atlas_grounded",
                *atlas_draft.grounding_evidence,
                *corpus_evidence_markers(corpus_evidence),
            ]
        )
        return BrainPlan(
            task=task,
            concept_graph=graph,
            patch_plan=patch_plan,
            validation_profile=_resolve_validation_profile(validation_profile),
            blocked_questions=[
                "The operator atlas returned grounding evidence, but no safe topology compiler route exists yet. Do not stop here: call td_brain_ground with this intent to get a grounding pack, author a draft candidate graph from its candidate_operators and param_semantics, validate it with td_brain_propose, then run td_brain_execute(plan_id=...)."
            ],
            missing_facts=[
                "unsupported_open_prompt:atlas_grounded_planner_required",
                *atlas_draft.rejection_reasons,
            ],
            grounding_evidence=grounding,
            corpus_evidence=corpus_evidence,
            risk_flags=["open-prompt-atlas-grounding"],
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
    corpus_evidence = build_corpus_evidence(
        intent=intent,
        operators=operators,
        card_index=card_index if include_docs else None,
    )
    grounding = _dedupe([*grounding, *corpus_evidence_markers(corpus_evidence)])
    if technique_store is not None and include_memory:
        grounding.extend(_memory_evidence(technique_store, intent))

    missing_ops, family_omitted_ops = _classify_required_ops(
        operators,
        available_ops,
        card_index=card_index if include_docs else None,
    )
    if missing_ops and include_docs and card_index is not None:
        atlas_corpus_evidence = build_corpus_evidence(
            intent=intent,
            operators=[],
            card_index=card_index,
            limit_per_query=16,
            max_records=16,
        )
        atlas_draft = draft_atlas_candidate_graph(
            task=task,
            compiled_task=compiled_task,
            corpus_evidence=atlas_corpus_evidence,
            card_index=card_index,
        )
        if atlas_draft.accepted and atlas_draft.candidate_graph is not None:
            atlas_missing_ops, _atlas_family_omitted_ops = _classify_required_ops(
                atlas_draft.candidate_graph.required_ops,
                available_ops,
                card_index=card_index,
            )
            if not atlas_missing_ops:
                return _plan_from_atlas_candidate_graph(
                    task=task,
                    compiled_task=compiled_task,
                    atlas_draft=atlas_draft,
                    available_ops=available_ops,
                    existing_names=existing_names,
                    card_index=card_index,
                    validation_profile=validation_profile,
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
        patch_plan = _with_graph_output_capture(task, graph, patch_plan)
        graph, patch_plan = _with_param_semantics_risk_flags(graph, patch_plan)
        param_issues = _blocking_param_issues(patch_plan)
        if param_issues:
            blocked_questions.append(_param_semantics_block_message(param_issues))
            missing_facts.extend(_param_issue_facts(param_issues))
            graph.risk_flags = _dedupe([*graph.risk_flags, *_param_issue_risk_flags(param_issues)])
            patch_plan = _empty_patch(task, reason="invalid parameter semantics")

    return BrainPlan(
        task=task,
        concept_graph=graph,
        patch_plan=patch_plan,
        validation_profile=_resolve_validation_profile(validation_profile),
        blocked_questions=blocked_questions,
        missing_facts=missing_facts,
        grounding_evidence=list(graph.evidence),
        corpus_evidence=corpus_evidence,
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


def _intent_is_complex_multi_output_library(intent: str) -> bool:
    text = (intent or "").lower()
    asks_many = any(token in text for token in ("10 ", "ten ", "ten-", "ten_"))
    asks_projects = any(token in text for token in ("projects", "outputs", "comps", "patches"))
    asks_library = any(token in text for token in ("thumbnail", "library", "gallery", "review wall"))
    asks_navigation = any(token in text for token in ("back", "next", "previous", "prev", "detail"))
    asks_qa = any(token in text for token in ("visual qa", "pixel", "bug ledger", "metrics", "60 fps"))
    return asks_many and asks_projects and asks_library and (asks_navigation or asks_qa)


def _device_sources_from_constraints(constraints: dict[str, Any]) -> set[str]:
    raw_sources = constraints.get("device_sources")
    if raw_sources is None:
        return set()
    if isinstance(raw_sources, str):
        return {raw_sources} if raw_sources else set()
    if isinstance(raw_sources, list | tuple | set):
        return {str(item) for item in raw_sources if str(item)}
    return set()


def _sampled_unavailable_ops_from_constraints(constraints: dict[str, Any]) -> set[str]:
    unavailable = _unavailable_ops_from_availability_matrix(
        _availability_matrix_from_constraints(constraints)
    )
    report = constraints.get("availability_report")
    if not isinstance(report, dict):
        return unavailable
    results = report.get("results")
    if not isinstance(results, list):
        return unavailable
    for item in results:
        if not isinstance(item, dict) or item.get("available") is not False:
            continue
        op_type = str(item.get("op_type") or "").strip()
        if op_type:
            unavailable.add(op_type)
    return unavailable


def _sampled_unavailable_reasons_from_constraints(constraints: dict[str, Any]) -> dict[str, str]:
    reasons: dict[str, str] = {}
    matrix = _availability_matrix_from_constraints(constraints)
    if matrix is not None:
        for op_type, reason in matrix.unavailable_reasons.items():
            if matrix.operators.get(op_type, {}).get("available") is False:
                reasons[op_type] = _availability_reason_text(reason)

    report = constraints.get("availability_report")
    if not isinstance(report, dict):
        return {op_type: reason for op_type, reason in reasons.items() if reason}
    results = report.get("results")
    if not isinstance(results, list):
        return {op_type: reason for op_type, reason in reasons.items() if reason}
    for item in results:
        if not isinstance(item, dict) or item.get("available") is not False:
            continue
        op_type = str(item.get("op_type") or "").strip()
        reason = _availability_reason_text(item.get("error") or item.get("reason"))
        if op_type and reason:
            reasons[op_type] = reason
    return {op_type: reason for op_type, reason in reasons.items() if reason}


def _availability_matrix_from_constraints(constraints: dict[str, Any]) -> OperatorAvailabilityMatrix | None:
    raw = constraints.get("availability_matrix") or constraints.get("operator_availability_matrix")
    if isinstance(raw, OperatorAvailabilityMatrix):
        return raw
    if raw is None:
        report_path = constraints.get("availability_report_path") or constraints.get(
            "operator_availability_report_path"
        )
        if isinstance(report_path, str) and report_path.strip():
            report = load_operator_availability_report(report_path)
            raw = report.get("availability_matrix")
    if not isinstance(raw, dict):
        return None
    try:
        return OperatorAvailabilityMatrix.model_validate(raw)
    except ValueError:
        return None


def _unavailable_ops_from_availability_matrix(matrix: OperatorAvailabilityMatrix | None) -> set[str]:
    if matrix is None:
        return set()
    return {op_type for op_type, data in matrix.operators.items() if data.get("available") is False}


def _availability_td_build(
    constraints: dict[str, Any],
    matrix: OperatorAvailabilityMatrix | None,
) -> str:
    return str(constraints.get("td_build") or (matrix.td_build if matrix is not None else None) or "unknown")


def _availability_platform(
    constraints: dict[str, Any],
    matrix: OperatorAvailabilityMatrix | None,
) -> str:
    return str(constraints.get("platform") or (matrix.platform if matrix is not None else None) or "unknown")


def _availability_installed_addons(
    constraints: dict[str, Any],
    matrix: OperatorAvailabilityMatrix | None,
) -> list[str]:
    addons = constraints.get("installed_addons")
    if not isinstance(addons, list) and matrix is not None:
        addons = matrix.installed_addons
    if not isinstance(addons, list):
        return []
    return [str(item) for item in addons]


def _availability_sample_evidence(
    unavailable_ops: set[str] | None,
    unavailable_reasons: dict[str, str] | None = None,
) -> list[str]:
    reasons = unavailable_reasons or {}
    evidence: list[str] = []
    for op_type in sorted(unavailable_ops or set()):
        evidence.append(f"availability-sample:unavailable:{op_type}")
        reason = _availability_reason_text(reasons.get(op_type))
        if reason:
            evidence.append(f"availability-sample-reason:{op_type}:{reason}")
    return evidence


def _availability_matrix_with_sampled_reasons(
    matrix: OperatorAvailabilityMatrix,
    unavailable_reasons: dict[str, str] | None,
) -> OperatorAvailabilityMatrix:
    reasons = dict(matrix.unavailable_reasons)
    changed = False
    for op_type, reason_value in (unavailable_reasons or {}).items():
        reason = _availability_reason_text(reason_value)
        if not reason:
            continue
        if matrix.operators.get(op_type, {}).get("available") is not False:
            continue
        if reasons.get(op_type) == reason:
            continue
        reasons[op_type] = reason
        changed = True
    if not changed:
        return matrix
    return matrix.model_copy(update={"unavailable_reasons": reasons})


def _availability_reason_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _compiler_route_required_ops() -> list[str]:
    return [
        "analyzeCHOP",
        "audiodeviceinCHOP",
        "audiofileinCHOP",
        "baseCOMP",
        "buttonCOMP",
        "cameraCOMP",
        "circlePOP",
        "compositeTOP",
        "constantTOP",
        "containerCOMP",
        "datexecuteDAT",
        "errorDAT",
        "feedbackTOP",
        "geometryCOMP",
        "glslMAT",
        "glsladvancedPOP",
        "glslTOP",
        "gridSOP",
        "infoCHOP",
        "levelTOP",
        "mathCHOP",
        "mathmixPOP",
        "midiinCHOP",
        "ndiinTOP",
        "noisePOP",
        "noiseSOP",
        "noiseTOP",
        "nullDAT",
        "nullCHOP",
        "nullPOP",
        "nullSOP",
        "nullTOP",
        "oscinDAT",
        "panelCHOP",
        "renderTOP",
        "rendersimpleTOP",
        "serialDAT",
        "sliderCOMP",
        "tableDAT",
        "textDAT",
        "topologyPOP",
        "websocketDAT",
    ]


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
    ("POP", "glsladv"): ("glsladvancedPOP",),
}

_AVAILABILITY_CRITICAL_OPS = {"glsladvancedPOP", "topologyPOP"}


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
    nodes = (
        response
        if isinstance(response, list)
        else response.get("nodes", [])
        if isinstance(response, dict)
        else []
    )
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
    strict_missing_ops: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    if not available_ops:
        return [], []
    missing: list[str] = []
    family_omitted: list[str] = []
    strict_missing = strict_missing_ops or set()
    for op_type in operators:
        if op_type in strict_missing:
            missing.append(op_type)
            continue
        if op_type in available_ops:
            continue
        if op_type in _AVAILABILITY_CRITICAL_OPS:
            missing.append(op_type)
            continue
        if _operator_has_docs(card_index, op_type):
            family_omitted.append(op_type)
            continue
        missing.append(op_type)
    return sorted(missing), sorted(family_omitted)


_COMPILER_PATH_CAPABILITY_PARTS = {
    "debug_output": "debug-output",
    "terrain_surface": "terrain-surface",
    "serial_dat_protocol": "serial-dat-protocol",
    "osc_dat_protocol": "osc-dat-protocol",
    "websocket_dat_protocol": "websocket-dat-protocol",
    "mqtt_dat_protocol": "mqtt-dat-protocol",
    "udp_dat_protocol": "udp-dat-protocol",
    "dat_table_render_switch": "dat-table-render-switch",
    "dat_execute_callback": "dat-execute-callback",
    "ndi_input": "ndi-input",
    "post_fx_output": "post-fx-output",
    "glsl_top_shader": "glsl-top-shader",
    "pop_particle_field_preview": "pop-particle-field-preview",
    "glsl_advanced_pop_topology": "glsl-advanced-pop-topology",
}


def _compiler_path_evidence(compiled_task, candidate: CandidateConceptGraph) -> list[str]:
    if _is_audio_feedback_panel_debug_route(compiled_task, candidate):
        return ["compiler:path:phase1-audio-feedback-panel-debug"]

    route_parts = [_compiler_path_part(profile) for profile in candidate.profiles]
    for capability in compiled_task.required_capabilities:
        part = _COMPILER_PATH_CAPABILITY_PARTS.get(str(capability))
        if part and part not in route_parts:
            route_parts.append(part)

    if not route_parts and candidate.pattern_ids:
        route_parts.append(_compiler_path_part(candidate.pattern_ids[0]))

    route_slug = "-".join(part for part in route_parts if part) or "unknown"
    return [f"compiler:path:phase1-{route_slug}"]


def _is_audio_feedback_panel_debug_route(compiled_task, candidate: CandidateConceptGraph) -> bool:
    return {"audio_reactive", "feedback", "panel_ui"}.issubset(set(candidate.profiles)) and {
        "audio_analysis",
        "feedback_loop",
        "panel_controls",
        "debug_output",
    }.issubset(set(compiled_task.required_capabilities))


def _compiler_path_part(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")


def _plan_from_candidate_graph(
    *,
    task: VisualTaskSpec,
    compiled_task,
    candidate_graphs: list[CandidateConceptGraph],
    available_ops: set[str],
    existing_names: set[str],
    card_index,
    validation_profile: str,
    sampled_unavailable_ops: set[str] | None = None,
    sampled_unavailable_reasons: dict[str, str] | None = None,
    availability_matrix: OperatorAvailabilityMatrix | None = None,
) -> BrainPlan:
    candidate = candidate_graphs[0]
    assembly_macros = macros_for_profiles(["concept_compiled", *candidate.profiles])
    assembly_required_ops = _assembly_required_ops(assembly_macros)
    required_ops = _dedupe([*candidate.required_ops, *assembly_required_ops])
    sample_evidence = _availability_sample_evidence(sampled_unavailable_ops, sampled_unavailable_reasons)
    corpus_evidence = build_corpus_evidence(
        intent=task.intent,
        operators=required_ops,
        card_index=card_index,
    )
    grounding = _dedupe(
        [
            *compiled_task.grounding_evidence,
            *candidate.grounding_evidence,
            *sample_evidence,
            *[f"docs:{op_type}" for op_type in assembly_required_ops],
            *corpus_evidence_markers(corpus_evidence),
            *[f"assembly:{macro.macro_id}" for macro in assembly_macros],
            *_compiler_path_evidence(compiled_task, candidate),
        ]
    )
    substitution_explanations = substitution_explanations_from_evidence(
        grounding,
        availability_matrix=availability_matrix,
    )
    missing_ops, family_omitted_ops = _classify_required_ops(
        required_ops,
        available_ops,
        card_index=card_index,
        strict_missing_ops=sampled_unavailable_ops,
    )
    graph = ConceptGraph(
        task=task,
        profile="concept_compiled",
        concepts=candidate.concepts,
        edges=candidate.edges,
        operators=required_ops,
        unresolved=missing_ops,
        evidence=grounding,
        risk_flags=[
            *candidate.risk_flags,
            *[f"missing-op:{op}" for op in missing_ops],
            *[f"family-list-omitted:{op}" for op in family_omitted_ops],
        ],
    )
    missing_facts = [f"missing_op:{op}" for op in missing_ops]
    sampled_missing_ops = sorted(set(missing_ops).intersection(sampled_unavailable_ops or set()))
    missing_facts.extend(f"availability_sample_unavailable:{op}" for op in sampled_missing_ops)
    missing_device_sources = _missing_device_source_facts(candidate, task.constraints)
    missing_facts.extend(missing_device_sources)
    blocked_questions = []
    if missing_ops:
        blocked_questions.append(
            "The current TouchDesigner operator family list does not include every required operator for the compiler-backed candidate graph."
        )
        patch_plan = _empty_patch(task, reason="missing required operators")
    elif missing_device_sources:
        blocked_questions.append(
            "The selected compiler-backed pattern depends on an external device or network source. "
            "Declare the available source in constraints.device_sources before mutation."
        )
        patch_plan = _empty_patch(task, reason="missing device source")
    else:
        patch_plan = _compile_patch_plan(task, graph, existing_names)
        graph, patch_plan = _with_param_semantics_risk_flags(graph, patch_plan)
        param_issues = _blocking_param_issues(patch_plan, require_param_semantics=True)
        if param_issues:
            blocked_questions.append(_param_semantics_block_message(param_issues))
            missing_facts.extend(_param_issue_facts(param_issues))
            graph.risk_flags = _dedupe([*graph.risk_flags, *_param_issue_risk_flags(param_issues)])
            patch_plan = _empty_patch(task, reason="invalid parameter semantics")
        else:
            patch_plan = _with_assembly_operations(
                patch_plan,
                task=task,
                graph=graph,
                candidate=candidate,
                assembly_macros=assembly_macros,
                existing_names=existing_names,
            )
            graph, patch_plan = _with_param_semantics_risk_flags(graph, patch_plan)
            param_issues = _blocking_param_issues(patch_plan, require_param_semantics=True)
            if param_issues:
                blocked_questions.append(_param_semantics_block_message(param_issues))
                missing_facts.extend(_param_issue_facts(param_issues))
                graph.risk_flags = _dedupe([*graph.risk_flags, *_param_issue_risk_flags(param_issues)])
                patch_plan = _empty_patch(task, reason="invalid parameter semantics")

    return BrainPlan(
        task=task,
        concept_graph=graph,
        patch_plan=patch_plan,
        compiled_task=compiled_task,
        candidate_graphs=candidate_graphs,
        availability_matrix=availability_matrix,
        validation_profile=_resolve_validation_profile(validation_profile),
        blocked_questions=blocked_questions,
        missing_facts=missing_facts,
        grounding_evidence=list(graph.evidence),
        corpus_evidence=corpus_evidence,
        substitution_explanations=substitution_explanations,
        risk_flags=list(graph.risk_flags),
    )


def _plan_from_atlas_candidate_graph(
    *,
    task: VisualTaskSpec,
    compiled_task,
    atlas_draft: AtlasDraftResult,
    available_ops: set[str],
    existing_names: set[str],
    card_index,
    validation_profile: str,
) -> BrainPlan:
    candidate = atlas_draft.candidate_graph
    if candidate is None:
        raise ValueError("accepted atlas draft must include a candidate graph")

    ranked_candidates = list(atlas_draft.candidate_graphs or [candidate])
    required_ops = list(candidate.required_ops)
    corpus_evidence = build_corpus_evidence(
        intent=task.intent,
        operators=required_ops,
        card_index=card_index,
    )
    draft_evidence = _param_semantics_draft_evidence(required_ops, card_index)
    grounding = _dedupe(
        [
            "profile:generic",
            "planner:open_prompt_atlas_drafted",
            *candidate.grounding_evidence,
            *corpus_evidence_markers(corpus_evidence),
            *draft_evidence,
        ]
    )
    missing_ops, family_omitted_ops = _classify_required_ops(
        required_ops,
        available_ops,
        card_index=card_index,
    )
    graph = ConceptGraph(
        task=task,
        profile="generic",
        concepts=candidate.concepts,
        edges=candidate.edges,
        operators=required_ops,
        unresolved=missing_ops,
        evidence=grounding,
        risk_flags=[
            *candidate.risk_flags,
            *(["param-semantics-drafts-need-review"] if draft_evidence else []),
            *[f"missing-op:{op}" for op in missing_ops],
            *[f"family-list-omitted:{op}" for op in family_omitted_ops],
        ],
    )
    missing_facts = [f"missing_op:{op}" for op in missing_ops]
    missing_device_sources = _missing_device_source_facts(candidate, task.constraints)
    missing_facts.extend(missing_device_sources)
    blocked_questions = []
    if missing_ops:
        blocked_questions.append(
            "The atlas-grounded draft names operators that are not available in the current TouchDesigner build."
        )
        patch_plan = _empty_patch(task, reason="missing required operators")
    elif missing_device_sources:
        blocked_questions.append(
            "The selected atlas-grounded draft depends on an external device or network source. "
            "Declare the available source in constraints.device_sources before mutation."
        )
        patch_plan = _empty_patch(task, reason="missing device source")
    else:
        patch_plan = _compile_patch_plan(task, graph, existing_names)
        patch_plan = _with_graph_output_capture(task, graph, patch_plan)
        graph, patch_plan = _with_param_semantics_risk_flags(graph, patch_plan)
        param_issues = _blocking_param_issues(patch_plan)
        if param_issues:
            blocked_questions.append(_param_semantics_block_message(param_issues))
            missing_facts.extend(_param_issue_facts(param_issues))
            graph.risk_flags = _dedupe([*graph.risk_flags, *_param_issue_risk_flags(param_issues)])
            patch_plan = _empty_patch(task, reason="invalid parameter semantics")

    return BrainPlan(
        task=task,
        concept_graph=graph,
        patch_plan=patch_plan,
        compiled_task=compiled_task,
        candidate_graphs=ranked_candidates,
        validation_profile=_resolve_validation_profile(validation_profile),
        blocked_questions=blocked_questions,
        missing_facts=missing_facts,
        grounding_evidence=list(graph.evidence),
        corpus_evidence=corpus_evidence,
        risk_flags=list(graph.risk_flags),
    )


async def read_available_operator_types(td_client) -> set[str]:
    """Read the live TD operator family list as canonical op-type names.

    Public bridge for the host-authored draft loop (td_brain_ground /
    td_brain_propose). Returns an empty set when TouchDesigner is not
    reachable — callers must treat an empty set as "availability unknown",
    the same degradation contract ``build_brain_plan`` uses.
    """
    return await _read_available_ops(td_client)


async def build_brain_plan_from_reviewed_candidate(
    td_client,
    *,
    task: VisualTaskSpec,
    compiled_task,
    candidate: CandidateConceptGraph,
    card_index=None,
    validation_profile: str = "auto",
    available_ops: set[str] | None = None,
) -> BrainPlan:
    """Compile a review-gated, host-authored candidate graph into a full BrainPlan.

    Public bridge for ``td_brain_propose``: the candidate MUST come from
    ``review_draft_candidate_graph`` (schema, official docs, availability, and
    param-semantics strip already proven). It reuses the atlas candidate-graph
    compiler so host-authored drafts get the exact same patch compilation,
    output capture, param-semantics gating, and blocked-question behavior as
    planner-authored atlas drafts.
    """
    ops = available_ops if available_ops is not None else await _read_available_ops(td_client)
    existing_names = await _read_existing_names(td_client, task.target_root)
    atlas_draft = AtlasDraftResult(
        accepted=True,
        candidate_graph=candidate,
        candidate_graphs=[candidate],
        grounding_evidence=list(candidate.grounding_evidence),
    )
    plan = _plan_from_atlas_candidate_graph(
        task=task,
        compiled_task=compiled_task,
        atlas_draft=atlas_draft,
        available_ops=ops,
        existing_names=existing_names,
        card_index=card_index,
        validation_profile=validation_profile,
    )
    plan.grounding_evidence = _dedupe(["planner:host_authored_draft", *plan.grounding_evidence])
    plan.concept_graph.evidence = _dedupe(["planner:host_authored_draft", *plan.concept_graph.evidence])
    return plan


_DEVICE_SOURCE_REQUIREMENTS: dict[str, str] = {
    "audio_device_to_analysis_chop": "audio_device",
    "midi_in_to_control_chop": "midi_device",
    "atlas:midi_chop_control_bridge": "midi_device",
    "serial_dat_protocol_bridge": "serial_device",
    "osc_in_dat_protocol_bridge": "osc_source",
    "websocket_dat_protocol_bridge": "websocket_endpoint",
    "atlas:web_client_dat_request_output": "http_endpoint",
    "atlas:web_server_dat_endpoint": "network_listener",
    "mqtt_client_dat_protocol_bridge": "mqtt_broker",
    "udp_in_dat_protocol_bridge": "udp_source",
    "ndi_in_to_post_fx_output": "ndi_source",
}


def _compiler_pattern_registry(*, include_memory: bool):
    from td_mcp.brain.patterns import load_pattern_registry

    patterns = load_pattern_registry()
    if not include_memory:
        return patterns
    try:
        from td_mcp.brain.traces import promoted_patterns_from_traces

        promoted = promoted_patterns_from_traces(limit=50)
    except Exception:
        promoted = []
    return [*patterns, *promoted]


def _missing_device_source_facts(
    candidate: CandidateConceptGraph,
    constraints: dict[str, Any],
) -> list[str]:
    declared = _device_sources_from_constraints(constraints)
    missing = [
        source
        for pattern_id, source in _DEVICE_SOURCE_REQUIREMENTS.items()
        if pattern_id in candidate.pattern_ids and source not in declared
    ]
    return [f"missing_device_source:{source}" for source in missing]


def _operator_has_docs(card_index, op_type: str) -> bool:
    if card_index is None:
        return False
    try:
        return card_index.get_operator(op_type) is not None
    except Exception:
        return False


def _blocking_param_issues(patch_plan: PatchPlan, *, require_param_semantics: bool = False):
    return [
        issue
        for issue in [
            *validate_patch_plan_parameter_contract(
                patch_plan,
                require_semantics_for_set_params=require_param_semantics,
            ),
            *validate_patch_plan_generated_code(patch_plan),
        ]
        if issue.severity in {"error", "critical"}
    ]


def _param_semantics_block_message(issues) -> str:
    first = issues[0]
    return (
        "The generated PatchPlan has unsafe or ungrounded parameter bindings before transaction apply "
        f"({first.code})."
    )


def _param_issue_facts(issues) -> list[str]:
    return _dedupe([f"param_semantics:{issue.code}" for issue in issues])


def _param_issue_risk_flags(issues) -> list[str]:
    return _dedupe([f"param-semantics:{issue.code}" for issue in issues])


def _with_param_semantics_risk_flags(
    graph: ConceptGraph, patch_plan: PatchPlan
) -> tuple[ConceptGraph, PatchPlan]:
    risk_flags = parameter_risk_flags_for_plan(patch_plan)
    if not risk_flags:
        return graph, patch_plan
    graph.risk_flags = _dedupe([*graph.risk_flags, *risk_flags])
    graph.evidence = _dedupe([*graph.evidence, *[f"direct-param-risk:{flag}" for flag in risk_flags]])
    return graph, patch_plan.model_copy(update={"risk_flags": _dedupe([*patch_plan.risk_flags, *risk_flags])})


def _assembly_required_ops(assembly_macros) -> list[str]:
    required_ops: list[str] = []
    if any(macro.macro_id == "make_component_shell" for macro in assembly_macros):
        required_ops.append("baseCOMP")
    if any(macro.macro_id == "annotate_operator_chain" for macro in assembly_macros):
        required_ops.append("annotateCOMP")
    if any(macro.macro_id == "add_debug_panel" for macro in assembly_macros):
        required_ops.extend(["textDAT", "infoCHOP", "errorDAT"])
    return _dedupe(required_ops)


def _with_assembly_operations(
    patch_plan: PatchPlan,
    *,
    task: VisualTaskSpec,
    graph: ConceptGraph,
    candidate: CandidateConceptGraph,
    assembly_macros,
    existing_names: set[str],
) -> PatchPlan:
    if not assembly_macros or not patch_plan.operations:
        return patch_plan

    macro_ids = {macro.macro_id for macro in assembly_macros}
    assembly_task = task
    if "make_component_shell" in macro_ids:
        shell_name = _component_shell_name(existing_names)
        shell_path = _join_path(task.target_root, shell_name)
        shell_op = PatchOperation(
            kind="create_node",
            target=task.target_root,
            args={
                "op_type": "baseCOMP",
                "name": shell_name,
                "x": -360,
                "y": 240,
                "assembly_macro_id": "make_component_shell",
            },
        )
        validation_plan = patch_plan.validation_plan.model_copy(
            update={
                "target_root": shell_path,
                "capture_frames": _rebase_path_values(
                    patch_plan.validation_plan.capture_frames,
                    from_root=task.target_root,
                    to_root=shell_path,
                ),
            }
        )
        patch_plan = patch_plan.model_copy(
            update={
                "operations": [
                    shell_op,
                    *_rebase_operations_to_shell(
                        patch_plan.operations,
                        from_root=task.target_root,
                        to_root=shell_path,
                    ),
                ],
                "validation_plan": validation_plan,
            }
        )
        assembly_task = task.model_copy(
            update={
                "target_root": shell_path,
                "output_top": _rebase_path_value(
                    task.output_top, from_root=task.target_root, to_root=shell_path
                )
                if task.output_top
                else None,
            }
        )

    concept_paths = _concept_paths_from_patch_plan(assembly_task, graph, patch_plan)
    operations = list(patch_plan.operations)

    if "group_by_domain" in macro_ids:
        operations.extend(_domain_layout_ops(graph, concept_paths))
    if "add_named_outputs" in macro_ids:
        operations.extend(_role_layout_ops(graph, concept_paths, role="output", macro_id="add_named_outputs"))
    if "add_debug_panel" in macro_ids:
        operations.extend(_debug_diagnostic_ops(assembly_task, graph, concept_paths))
        operations.extend(
            _matching_layout_ops(
                graph,
                concept_paths,
                macro_id="add_debug_panel",
                predicate=lambda concept: (
                    concept.id == "debug_notes" or "debug" in concept.id or concept.role == "validator"
                ),
            )
        )
    if "add_user_controls" in macro_ids:
        operations.extend(
            _matching_layout_ops(
                graph,
                concept_paths,
                macro_id="add_user_controls",
                predicate=lambda concept: concept.role in {"control", "ui"},
            )
        )
    if "annotate_operator_chain" in macro_ids:
        operations.append(_assembly_annotation_op(assembly_task, candidate, assembly_macros))

    return patch_plan.model_copy(update={"operations": operations})


def _component_shell_name(existing_names: set[str]) -> str:
    base = "tdpilot_concept"
    candidate = base
    counter = 1
    while candidate in existing_names:
        counter += 1
        candidate = f"{base}{counter}"
    return candidate


def _rebase_operations_to_shell(
    operations: list[PatchOperation],
    *,
    from_root: str,
    to_root: str,
) -> list[PatchOperation]:
    return [
        operation.model_copy(
            update={
                "target": _rebase_path_value(operation.target, from_root=from_root, to_root=to_root),
                "args": _rebase_path_value(operation.args, from_root=from_root, to_root=to_root),
            }
        )
        for operation in operations
    ]


def _rebase_path_values(values: list[str], *, from_root: str, to_root: str) -> list[str]:
    return [str(_rebase_path_value(value, from_root=from_root, to_root=to_root)) for value in values]


def _rebase_path_value(value: Any, *, from_root: str, to_root: str) -> Any:
    if isinstance(value, dict):
        return {
            key: _rebase_path_value(item, from_root=from_root, to_root=to_root) for key, item in value.items()
        }
    if isinstance(value, list):
        return [_rebase_path_value(item, from_root=from_root, to_root=to_root) for item in value]
    if isinstance(value, str):
        root = from_root.rstrip("/") or "/"
        if value == root:
            return to_root
        prefix = f"{root}/" if root != "/" else "/"
        if value.startswith(prefix):
            suffix = value[len(prefix) :]
            return _join_path(to_root, suffix)
        if root != "/" and prefix in value:
            return value.replace(prefix, f"{to_root.rstrip('/')}/")
    return value


def _debug_diagnostic_ops(
    task: VisualTaskSpec,
    graph: ConceptGraph,
    concept_paths: dict[str, str],
) -> list[PatchOperation]:
    stable_target = _stable_top_path(graph, concept_paths) or task.output_top or task.target_root
    debug_notes_path = _join_path(task.target_root, "debug_notes")
    debug_info_path = _join_path(task.target_root, "debug_info")
    error_log_path = _join_path(task.target_root, "error_log")
    operations: list[PatchOperation] = []
    if "debug_notes" not in concept_paths:
        operations.extend(
            [
                PatchOperation(
                    kind="create_node",
                    target=task.target_root,
                    args={
                        "op_type": "textDAT",
                        "name": "debug_notes",
                        "x": _DOMAIN_COLUMNS["DAT"],
                        "y": -840,
                        "assembly_macro_id": "add_debug_panel",
                    },
                ),
                PatchOperation(
                    kind="set_dat_content",
                    target=debug_notes_path,
                    args={
                        "text": f"TDPilot debug notes\nstable_target: {stable_target}",
                        "assembly_macro_id": "add_debug_panel",
                    },
                ),
            ]
        )
    operations.extend(
        [
            PatchOperation(
                kind="create_node",
                target=task.target_root,
                args={
                    "op_type": "infoCHOP",
                    "name": "debug_info",
                    "x": _DOMAIN_COLUMNS["CHOP"],
                    "y": -960,
                    "assembly_macro_id": "add_debug_panel",
                },
            ),
            PatchOperation(
                kind="set_params",
                target=debug_info_path,
                args={
                    "params": {
                        "op": stable_target,
                        "passive": True,
                    },
                    "assembly_macro_id": "add_debug_panel",
                },
            ),
            PatchOperation(
                kind="create_node",
                target=task.target_root,
                args={
                    "op_type": "errorDAT",
                    "name": "error_log",
                    "x": _DOMAIN_COLUMNS["DAT"],
                    "y": -960,
                    "assembly_macro_id": "add_debug_panel",
                },
            ),
            PatchOperation(
                kind="set_params",
                target=error_log_path,
                args={
                    "params": {
                        "active": True,
                        "source": f"{task.target_root.rstrip('/')}/*",
                        "clamp": True,
                        "maxlines": 50,
                    },
                    "assembly_macro_id": "add_debug_panel",
                },
            ),
        ]
    )
    return operations


def _stable_top_path(graph: ConceptGraph, concept_paths: dict[str, str]) -> str | None:
    final_output = next(
        (concept for concept in graph.concepts if concept.id == "output" and concept.role == "output"),
        None,
    )
    if final_output is not None:
        if final_output.domain != "TOP":
            return None
        return concept_paths.get(final_output.id)
    for concept in graph.concepts:
        if concept.role == "output" and concept.domain == "TOP":
            path = concept_paths.get(concept.id)
            if path:
                return path
    return None


def _with_graph_output_capture(task: VisualTaskSpec, graph: ConceptGraph, patch_plan: PatchPlan) -> PatchPlan:
    if task.output_top or patch_plan.validation_plan.capture_frames:
        return patch_plan
    concept_paths = _concept_paths_from_patch_plan(task, graph, patch_plan)
    stable_top = _stable_top_path(graph, concept_paths)
    if not stable_top:
        return patch_plan
    validation_plan = patch_plan.validation_plan.model_copy(update={"capture_frames": [stable_top]})
    return patch_plan.model_copy(update={"validation_plan": validation_plan})


def _param_semantics_draft_evidence(required_ops: list[str], card_index) -> list[str]:
    if card_index is None or not required_ops:
        return []
    try:
        report = draft_param_semantics_from_docs(
            card_index,
            required_ops,
            existing_registry=load_param_semantics_registry(),
            max_per_operator=12,
        )
    except Exception:
        return []
    return [
        f"param-semantics-draft:{draft.op_type}.{draft.name}:needs-live-readback" for draft in report.drafts
    ]


def _concept_paths_from_patch_plan(
    task: VisualTaskSpec,
    graph: ConceptGraph,
    patch_plan: PatchPlan,
) -> dict[str, str]:
    create_ops = [operation for operation in patch_plan.operations if operation.kind == "create_node"]
    paths: dict[str, str] = {}
    create_index = 0
    for concept in graph.concepts:
        if not concept.op_type:
            continue
        while (
            create_index < len(create_ops)
            and create_ops[create_index].args.get("assembly_macro_id") == "make_component_shell"
        ):
            create_index += 1
        if create_index >= len(create_ops):
            break
        name = create_ops[create_index].args.get("name")
        parent = create_ops[create_index].target or task.target_root
        if name:
            paths[concept.id] = _join_path(str(parent), str(name))
        create_index += 1
    return paths


_DOMAIN_COLUMNS = {
    "CHOP": 0,
    "TOP": 360,
    "COMP": 720,
    "DAT": 1080,
    "POP": 1440,
    "SOP": 1800,
    "MAT": 2160,
}


def _domain_layout_ops(graph: ConceptGraph, concept_paths: dict[str, str]) -> list[PatchOperation]:
    offsets: dict[str, int] = {}
    operations: list[PatchOperation] = []
    for concept in graph.concepts:
        path = concept_paths.get(concept.id)
        if not path:
            continue
        domain = str(concept.domain)
        x = _DOMAIN_COLUMNS.get(domain, 2520)
        y = offsets.get(domain, 0) * -160
        offsets[domain] = offsets.get(domain, 0) + 1
        operations.append(
            PatchOperation(
                kind="layout",
                target=path,
                args={
                    "x": x,
                    "y": y,
                    "domain": domain,
                    "assembly_macro_id": "group_by_domain",
                },
            )
        )
    return operations


def _role_layout_ops(
    graph: ConceptGraph,
    concept_paths: dict[str, str],
    *,
    role: str,
    macro_id: str,
) -> list[PatchOperation]:
    return _matching_layout_ops(
        graph,
        concept_paths,
        macro_id=macro_id,
        predicate=lambda concept: concept.role == role,
    )


def _matching_layout_ops(
    graph: ConceptGraph,
    concept_paths: dict[str, str],
    *,
    macro_id: str,
    predicate,
) -> list[PatchOperation]:
    operations: list[PatchOperation] = []
    for concept in graph.concepts:
        if not predicate(concept):
            continue
        path = concept_paths.get(concept.id)
        if not path:
            continue
        domain = str(concept.domain)
        operations.append(
            PatchOperation(
                kind="layout",
                target=path,
                args={
                    "x": _DOMAIN_COLUMNS.get(domain, 2520),
                    "y": -720 - (len(operations) * 120),
                    "domain": domain,
                    "assembly_macro_id": macro_id,
                },
            )
        )
    return operations


def _assembly_annotation_op(
    task: VisualTaskSpec, candidate: CandidateConceptGraph, assembly_macros
) -> PatchOperation:
    validation = _dedupe(
        [
            *candidate.validation_needs,
            *[addon for macro in assembly_macros for addon in macro.validation_addons],
        ]
    )
    macro_notes = _dedupe([note for macro in assembly_macros for note in macro.notes])
    text = "\n".join(
        [
            "TDPilot assembled concept graph",
            f"patterns: {', '.join(candidate.pattern_ids)}",
            f"validation: {', '.join(validation)}",
            f"notes: {'; '.join(macro_notes)}",
            f"evidence: {', '.join(candidate.grounding_evidence[:8])}",
        ]
    )
    return PatchOperation(
        kind="annotate",
        target=task.target_root,
        args={
            "name": "assembly_notes",
            "text": text,
            "assembly_macro_id": "annotate_operator_chain",
            "validation_addons": validation,
            "macro_notes": macro_notes,
            "evidence": candidate.grounding_evidence[:8],
        },
    )


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
            resolved_params = _resolve_param_refs(concept.params, concept_names, task.target_root)
            operations.append(
                PatchOperation(
                    kind="set_params",
                    target=_join_path(task.target_root, name),
                    args={"params": resolved_params},
                )
            )
        if concept.content or concept.generated_code:
            args = _resolve_param_refs(concept.content or {}, concept_names, task.target_root)
            if concept.generated_code:
                args["generated_code"] = _resolve_param_refs(
                    concept.generated_code,
                    concept_names,
                    task.target_root,
                )
                if "text" not in args and "code" in args["generated_code"]:
                    args["text"] = args["generated_code"]["code"]
            operations.append(
                PatchOperation(
                    kind="set_dat_content",
                    target=_join_path(task.target_root, name),
                    args=args,
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
    if concept.id == "debug_notes":
        return "debug_notes"
    if concept.role == "output":
        if concept.domain == "POP":
            return "out_pop"
        if concept.domain == "CHOP":
            return "out_chop"
        if concept.domain == "DAT":
            return "out_dat"
        if concept.domain == "SOP":
            return "out_sop"
        if concept.domain == "MAT":
            return "out_mat"
        if concept.domain == "COMP":
            return "out_comp"
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


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _resolve_param_refs(value: Any, concept_names: dict[str, str], target_root: str) -> Any:
    """Resolve small `${path:concept_id}` placeholders inside concept params."""
    if isinstance(value, dict):
        return {key: _resolve_param_refs(item, concept_names, target_root) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_param_refs(item, concept_names, target_root) for item in value]
    if isinstance(value, str):
        return _resolve_path_refs_in_string(value, concept_names, target_root)
    return value


_PATH_REF_PATTERN = re.compile(r"\$\{path:([A-Za-z0-9_]+)\}")


def _resolve_path_refs_in_string(value: str, concept_names: dict[str, str], target_root: str) -> str:
    def replace(match: re.Match[str]) -> str:
        node_name = concept_names.get(match.group(1))
        if not node_name:
            return match.group(0)
        return _join_path(target_root, node_name)

    return _PATH_REF_PATTERN.sub(replace, value)


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
