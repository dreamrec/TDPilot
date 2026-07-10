from __future__ import annotations

import pytest
from pydantic import ValidationError

from td_mcp.brain.intent_coverage import compute_intent_coverage, semantic_edge_issues
from td_mcp.brain.planner import _compile_patch_plan, build_brain_plan
from td_mcp.models.brain import (
    ConceptEdge,
    ConceptGraph,
    ConceptNode,
    CoverageEvidence,
    IntentCoverage,
    IntentRequirement,
    VisualTaskSpec,
)


class _TDClient:
    async def request(self, endpoint: str, body: dict):
        if endpoint == "families":
            return {
                "families": {
                    "CHOP": ["audiofileinCHOP", "analyzeCHOP", "mathCHOP", "nullCHOP"],
                    "POP": ["circlePOP", "noisePOP", "mathmixPOP", "nullPOP"],
                    "TOP": ["rendersimpleTOP", "renderTOP", "nullTOP"],
                    "COMP": ["geometryCOMP", "cameraCOMP"],
                }
            }
        if endpoint == "nodes":
            return {"nodes": []}
        return {}


def test_intent_coverage_recomputes_complete_and_uncovered_fields():
    requirement = IntentRequirement(id="req:capability:audio", kind="capability", label="audio")
    coverage = IntentCoverage(
        requirements=[requirement],
        evidence=[],
        complete=True,
        uncovered_requirement_ids=[],
    )

    assert coverage.complete is False
    assert coverage.uncovered_requirement_ids == [requirement.id]

    covered = IntentCoverage(
        requirements=[requirement],
        evidence=[
            CoverageEvidence(
                requirement_id=requirement.id,
                provider_kind="concept",
                provider_ids=["audio_source"],
            )
        ],
    )
    assert covered.complete is True


def test_concept_edge_only_accepts_binding_on_control_edges():
    with pytest.raises(ValidationError):
        ConceptEdge(
            source="a",
            target="b",
            kind="data",
            binding={
                "mode": "chop_reference_expression",
                "source_channel": 0,
                "target_param": "brightness1",
            },
        )


def test_control_edge_lowers_to_explicit_level_top_expression():
    task = VisualTaskSpec(intent="bind a CHOP control to Level TOP brightness")
    graph = ConceptGraph(
        task=task,
        concepts=[
            ConceptNode(id="control", label="Control", role="control", domain="CHOP", op_type="nullCHOP"),
            ConceptNode(id="source", label="Visual", role="source", domain="TOP", op_type="noiseTOP"),
            ConceptNode(id="level", label="Level", role="process", domain="TOP", op_type="levelTOP"),
            ConceptNode(id="output", label="Output", role="output", domain="TOP", op_type="nullTOP"),
        ],
        edges=[
            ConceptEdge(source="source", target="level", kind="data"),
            ConceptEdge(
                source="control",
                target="level",
                kind="control",
                binding={
                    "mode": "chop_reference_expression",
                    "source_channel": "amp",
                    "target_param": "brightness1",
                },
            ),
            ConceptEdge(source="level", target="output", kind="data"),
        ],
    )

    patch = _compile_patch_plan(task, graph, set())

    binding_ops = [
        operation
        for operation in patch.operations
        if operation.kind == "set_params" and operation.target == "/project1/level"
    ]
    assert binding_ops[-1].args["params"] == {"brightness1": {"expr": "op('/project1/control')['amp']"}}
    assert semantic_edge_issues(graph, patch) == []


def test_unsupported_control_target_stays_unresolved_and_is_not_lowered():
    task = VisualTaskSpec(intent="bind audio directly to a material")
    graph = ConceptGraph(
        task=task,
        concepts=[
            ConceptNode(id="control", label="Control", role="control", domain="CHOP", op_type="nullCHOP"),
            ConceptNode(id="material", label="Material", role="material", domain="MAT", op_type="glslMAT"),
        ],
        edges=[
            ConceptEdge(
                source="control",
                target="material",
                kind="control",
                binding={
                    "mode": "chop_reference_expression",
                    "source_channel": 0,
                    "target_param": "brightness1",
                },
            )
        ],
    )

    patch = _compile_patch_plan(task, graph, set())

    assert not any(operation.kind == "set_params" for operation in patch.operations)
    assert any("leveltop_targets_only" in issue for issue in semantic_edge_issues(graph, patch))


@pytest.mark.asyncio
async def test_multidomain_particle_tunnel_fog_cannot_fall_back_to_audio_only_plan():
    plan = await build_brain_plan(
        _TDClient(),
        intent="Build an audio-reactive 3D particle tunnel with fog and stable TOP output",
        target_root="/project1",
        output_top="/project1/out1",
    )

    assert plan.compiled_task is not None
    assert {"audio_analysis", "render_pipeline", "pop_particle_field_preview"}.issubset(
        set(plan.compiled_task.required_capabilities)
    )
    assert plan.route == "host_authored"
    assert plan.blocked_questions
    assert plan.patch_plan.operations == []
    assert plan.intent_coverage is not None and not plan.intent_coverage.complete
    labels = {item.label for item in plan.intent_coverage.requirements}
    assert {"particles", "tunnel_depth", "fog_atmosphere", "three_dimensional"}.issubset(labels)
    assert any("tunnel-depth" in item for item in plan.intent_coverage.uncovered_requirement_ids)


def test_requirement_evidence_is_derived_from_actual_patch_operations():
    task = VisualTaskSpec(intent="audio reactive feedback", output_top="/project1/out1")
    from td_mcp.brain.concept_compiler import compile_visual_task

    compiled = compile_visual_task(task.intent, output_top=task.output_top)
    graph = ConceptGraph(task=task, concepts=[], edges=[])
    patch = _compile_patch_plan(task, graph, set())

    coverage = compute_intent_coverage(compiled, graph, patch)

    assert coverage.complete is False
    assert "req:capability:audio-analysis" in coverage.uncovered_requirement_ids
    assert "req:binding:audio-to-visual-control" in coverage.uncovered_requirement_ids
