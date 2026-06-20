from __future__ import annotations

import pytest
from patch.conftest import FakeTDClient

from td_mcp.brain.planner import build_brain_plan


class FakeCardIndex:
    def __init__(self, known: set[str]):
        self.known = known

    def get_operator(self, op_type: str):
        if op_type in self.known:
            return {"op_type": op_type, "summary": f"{op_type} docs"}
        return None


@pytest.mark.asyncio
async def test_feedback_intent_builds_grounded_concept_graph_and_patch_plan():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "TOP": ["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="build a clean feedback displacement loop",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex({"noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"}),
    )

    assert plan.blocked_questions == []
    assert plan.concept_graph.profile == "feedback"
    assert "feedbackTOP" in plan.concept_graph.operators
    assert "feedbackTOP" in plan.patch_plan.required_ops
    assert plan.patch_plan.validation_plan.capture_frames == ["/project1/out1"]
    assert any(op.kind == "connect" for op in plan.patch_plan.operations)
    assert any("hint:" in item for item in plan.grounding_evidence)


@pytest.mark.asyncio
async def test_vague_intent_returns_blocked_question_instead_of_empty_guess():
    client = FakeTDClient(scripted={"families": {"families": {"TOP": ["nullTOP"]}}, "nodes": {"nodes": []}})

    plan = await build_brain_plan(client, intent="make it better", target_root="/project1")

    assert plan.blocked_questions
    assert plan.patch_plan.operations == []
    assert "under-specified" in plan.missing_facts[0]


@pytest.mark.asyncio
async def test_missing_required_operator_blocks_execution_plan():
    client = FakeTDClient(
        scripted={"families": {"families": {"TOP": ["noiseTOP", "nullTOP"]}}, "nodes": {"nodes": []}}
    )

    plan = await build_brain_plan(client, intent="build feedback loop", target_root="/project1")

    assert "missing_op:feedbackTOP" in plan.missing_facts
    assert plan.blocked_questions
    assert plan.patch_plan.operations == []


@pytest.mark.asyncio
async def test_pop_intent_builds_particle_concept_graph():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "POP": ["circlePOP", "noisePOP", "mathmixPOP", "nullPOP"],
                    "TOP": ["rendersimpleTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(client, intent="make a POP particle field", target_root="/project1")

    assert plan.blocked_questions == []
    assert plan.concept_graph.profile == "pop"
    assert {"circlePOP", "noisePOP", "mathmixPOP", "nullPOP", "rendersimpleTOP", "nullTOP"}.issubset(
        set(plan.concept_graph.operators)
    )
    assert any(edge.kind == "data" for edge in plan.concept_graph.edges)
    render_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target.endswith("/rendersimple")
    ]
    assert render_params and render_params[0]["pop"] == "/project1/out_pop"
    assert any(op.kind == "connect" for op in plan.patch_plan.operations)


@pytest.mark.asyncio
async def test_glsl_uses_docs_operator_but_short_create_type():
    client = FakeTDClient(
        scripted={
            "families": {"families": {"TOP": ["constantTOP", "glslTOP", "nullTOP"], "DAT": ["textDAT"]}},
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(client, intent="create a GLSL shader TOP", target_root="/project1")

    assert plan.blocked_questions == []
    assert plan.concept_graph.profile == "glsl"
    assert "glslTOP" in plan.concept_graph.operators
    create_ops = [op for op in plan.patch_plan.operations if op.kind == "create_node"]
    assert any(op.args["op_type"] == "glsl" for op in create_ops)
    shader_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target.endswith("/glsl")
    ]
    assert shader_params and shader_params[0]["pixeldat"] == "/project1/text"
    assert any(edge.kind == "reference" for edge in plan.concept_graph.edges)


@pytest.mark.asyncio
async def test_glsl_material_intent_builds_rendered_material_graph():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "COMP": ["geometryCOMP", "cameraCOMP"],
                    "MAT": ["glslMAT"],
                    "TOP": ["renderTOP", "nullTOP"],
                    "DAT": ["textDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client, intent="create a GLSL material with vertex shader", target_root="/project1"
    )

    assert plan.blocked_questions == []
    assert plan.concept_graph.profile == "glsl_material"
    assert {"geometryCOMP", "glslMAT", "cameraCOMP", "renderTOP", "textDAT", "nullTOP"}.issubset(
        set(plan.concept_graph.operators)
    )
    material_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and "vdat" in op.args["params"]
    ]
    assert material_params
    assert material_params[0]["vdat"] == "/project1/text"
    assert material_params[0]["pdat"] == "/project1/text2"


@pytest.mark.asyncio
async def test_glsl_pop_intent_builds_attribute_shader_graph():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "POP": ["circlePOP", "glslPOP", "nullPOP"],
                    "TOP": ["rendersimpleTOP", "nullTOP"],
                    "DAT": ["textDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client, intent="create a GLSL POP attribute shader", target_root="/project1"
    )

    assert plan.blocked_questions == []
    assert plan.concept_graph.profile == "glsl_pop"
    assert {"circlePOP", "glslPOP", "textDAT", "nullPOP", "rendersimpleTOP", "nullTOP"}.issubset(
        set(plan.concept_graph.operators)
    )


@pytest.mark.asyncio
async def test_panel_ui_reference_edges_do_not_compile_to_fake_wires():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "COMP": ["containerCOMP", "buttonCOMP", "sliderCOMP"],
                    "CHOP": ["panelCHOP", "nullCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client, intent="build a panel UI with a slider and button", target_root="/project1"
    )

    assert plan.blocked_questions == []
    assert plan.concept_graph.profile == "panel_ui"
    assert any(edge.kind == "reference" for edge in plan.concept_graph.edges)
    data_edges = [edge for edge in plan.concept_graph.edges if edge.kind in {"data", "feedback"}]
    connect_ops = [op for op in plan.patch_plan.operations if op.kind == "connect"]
    assert len(connect_ops) == len(data_edges)


@pytest.mark.asyncio
async def test_control_rig_plan_marks_custom_parameters_as_risk_to_validate():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {"COMP": ["baseCOMP"], "CHOP": ["constantCHOP", "mathCHOP", "nullCHOP"]}
            },
            "nodes": {"nodes": [{"name": "ctrl"}]},
        }
    )

    plan = await build_brain_plan(
        client, intent="make a custom parameter control rig", target_root="/project1"
    )

    assert plan.blocked_questions == []
    assert plan.concept_graph.profile == "control_rig"
    assert "custom-parameters-required" in plan.risk_flags
    create_names = [op.args["name"] for op in plan.patch_plan.operations if op.kind == "create_node"]
    assert "ctrl2" in create_names


@pytest.mark.asyncio
async def test_live_family_short_names_satisfy_doc_style_required_ops():
    client = FakeTDClient(
        scripted={
            "families": {"families": {"COMP": ["geo", "cam"], "TOP": ["render", "null"]}},
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(client, intent="build a render pipeline", target_root="/project1")

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert {"geometryCOMP", "cameraCOMP", "renderTOP", "nullTOP"}.issubset(set(plan.concept_graph.operators))


@pytest.mark.asyncio
async def test_docs_evidence_softens_incomplete_live_family_list():
    client = FakeTDClient(
        scripted={
            "families": {"families": {"TOP": ["level", "null"]}},
            "nodes": {"nodes": []},
        }
    )
    card_index = FakeCardIndex({"noiseTOP", "feedbackTOP", "compositeTOP", "levelTOP", "nullTOP"})

    plan = await build_brain_plan(
        client,
        intent="build a clean feedback loop",
        target_root="/project1",
        card_index=card_index,
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert "family-list-omitted:feedbackTOP" in plan.risk_flags
    assert any(item == "docs:feedbackTOP" for item in plan.grounding_evidence)
