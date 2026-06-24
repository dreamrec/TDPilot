from __future__ import annotations

import json

import pytest
from patch.conftest import FakeTDClient

from td_mcp.brain.code_harness import validate_patch_plan_generated_code
from td_mcp.brain.planner import build_brain_plan
from td_mcp.models.brain import BrainPattern


class FakeCardIndex:
    def __init__(self, known: set[str]):
        self.known = known

    def get_operator(self, op_type: str):
        if op_type in self.known:
            return {"op_type": op_type, "summary": f"{op_type} docs"}
        return None


class AtlasCardIndex:
    def __init__(self, cards: list[dict]):
        self.cards = {str(card["op_type"]): card for card in cards}

    def get_operator(self, op_type: str):
        return self.cards.get(op_type)

    def search(
        self,
        query: str,
        card_types: list[str] | None = None,
        family: str | None = None,
        limit: int = 10,
    ):
        tokens = {token for token in query.lower().split() if len(token) > 2}
        hits = []
        for card in self.cards.values():
            text = " ".join(
                str(card.get(key, "")) for key in ("op_type", "display_name", "summary", "key_concepts")
            ).lower()
            if family and str(card.get("family", "")).upper() != family.upper():
                continue
            if not tokens or tokens.intersection(text.split()):
                hits.append(card)
        return hits[:limit]


PHASE_ONE_SEED_OPS = {
    "audiofileinCHOP",
    "analyzeCHOP",
    "mathCHOP",
    "nullCHOP",
    "noiseTOP",
    "feedbackTOP",
    "levelTOP",
    "compositeTOP",
    "nullTOP",
    "baseCOMP",
    "containerCOMP",
    "sliderCOMP",
    "buttonCOMP",
    "panelCHOP",
    "textDAT",
    "annotateCOMP",
    "infoCHOP",
    "errorDAT",
}


@pytest.mark.asyncio
async def test_planner_blocks_complex_ten_project_library_instead_of_generic_collapse():
    client = FakeTDClient()

    plan = await build_brain_plan(
        client,
        intent=(
            "Using TD live, build 10 different complex artistic projects and a final "
            "thumbnail library panel with click to detail, back, next, previous, "
            "visual QA metrics, bug ledger, and 60 fps performance."
        ),
        target_root="/project1/tdpilot_deep_test_suite",
        output_top="/project1/tdpilot_deep_test_suite/final_gallery/out_gallery",
        constraints={"avoid": ["feedbackTOP"]},
    )

    assert plan.blocked_questions
    assert plan.patch_plan.operations == []
    assert "planner:blocked_complex_multi_output" in plan.grounding_evidence
    assert "complex_multi_output_library" in plan.missing_facts
    assert "multi-output-brief" in plan.risk_flags


def _first_created_target(plan, op_type: str) -> str:
    for operation in plan.patch_plan.operations:
        if operation.kind != "create_node" or operation.args.get("op_type") != op_type:
            continue
        return f"{operation.target.rstrip('/')}/{operation.args['name']}"
    raise AssertionError(f"missing created {op_type}")


def _set_params_for(plan, target: str) -> dict:
    for operation in plan.patch_plan.operations:
        if operation.kind == "set_params" and operation.target == target:
            return operation.args["params"]
    raise AssertionError(f"missing set_params for {target}")


def _atlas_card(
    op_type: str,
    family: str,
    summary: str,
    concepts: list[str],
    *,
    params: list[str] | None = None,
) -> dict:
    return {
        "card_type": "operator",
        "op_type": op_type,
        "family": family,
        "display_name": op_type,
        "docs_url": f"https://docs.derivative.ca/{op_type}",
        "summary": summary,
        "key_params": [{"name": param} for param in (params or [])],
        "key_concepts": concepts,
    }


def _promoted_audio_feedback_pattern() -> BrainPattern:
    return BrainPattern(
        pattern_id="trace_audio_feedback_green_audio_feedback_panel",
        title="Promoted Audio Feedback Panel",
        intent_tags=[
            "audio_analysis",
            "feedback_loop",
            "panel_controls",
            "debug_output",
        ],
        profiles=["audio_reactive", "feedback", "panel_ui"],
        required_ops=[
            "audiofileinCHOP",
            "analyzeCHOP",
            "mathCHOP",
            "nullCHOP",
            "noiseTOP",
            "feedbackTOP",
            "levelTOP",
            "compositeTOP",
            "nullTOP",
            "containerCOMP",
            "sliderCOMP",
            "buttonCOMP",
            "panelCHOP",
            "textDAT",
        ],
        concept_nodes=[
            {
                "id": "audio_source",
                "label": "Audio source",
                "role": "source",
                "domain": "CHOP",
                "op_type": "audiofileinCHOP",
            },
            {
                "id": "feedback_visual",
                "label": "Feedback visual",
                "role": "feedback",
                "domain": "TOP",
                "op_type": "feedbackTOP",
            },
            {
                "id": "panel_controls",
                "label": "Panel controls",
                "role": "control",
                "domain": "COMP",
                "op_type": "containerCOMP",
            },
            {
                "id": "debug_notes",
                "label": "Debug notes",
                "role": "validator",
                "domain": "DAT",
                "op_type": "textDAT",
            },
        ],
        concept_edges=[],
        layout={
            "source": "trace_promotion",
            "trace_fingerprint": "tracefp:audio-feedback-panel",
            "operator_fingerprint": "ops:audio-feedback-panel",
            "validation_fingerprint": "validation:audio-feedback-panel",
            "trace_support_count": 1,
            "support_trace_ids": ["trace-audio-feedback-green"],
            "runtime_validation": {
                "required_probe_ids": [
                    "audio_signal_activity",
                    "feedback_output_readback",
                    "panel_state_readback",
                ],
                "passed_probe_ids": [
                    "audio_signal_activity",
                    "feedback_output_readback",
                    "panel_state_readback",
                ],
                "readback_paths": {
                    "audio_signal_activity": "/project1/out_chop",
                    "feedback_output_readback": "/project1/out1",
                    "panel_state_readback": "/project1/out_chop",
                },
            },
        },
        debug_outputs=[{"node": "debug_notes", "domain": "DAT"}],
        validation_profile="structural_visual_safe",
        validation_probes=[
            "audio_signal_activity",
            "feedback_output_readback",
            "panel_state_readback",
        ],
        rollback_risks=["trace-promoted-pattern"],
        official_sources=[
            "https://docs.derivative.ca/Audio_File_In_CHOP",
            "https://docs.derivative.ca/Feedback_TOP",
            "https://docs.derivative.ca/Panel_CHOP",
            "https://docs.derivative.ca/Text_DAT",
        ],
        promoted_from_trace="trace-audio-feedback-green",
    )


MATERIAL_RENDER_OPS = PHASE_ONE_SEED_OPS | {
    "geometryCOMP",
    "cameraCOMP",
    "glslMAT",
    "renderTOP",
}
TERRAIN_MATERIAL_OPS = MATERIAL_RENDER_OPS | {
    "gridSOP",
    "noiseSOP",
    "nullSOP",
}

DAT_EXECUTE_CALLBACK_OPS = {
    "datexecuteDAT",
    "tableDAT",
    "textDAT",
    "nullDAT",
    "baseCOMP",
    "annotateCOMP",
    "infoCHOP",
    "errorDAT",
}

OSC_PROTOCOL_OPS = {
    "oscinDAT",
    "tableDAT",
    "nullDAT",
    "baseCOMP",
    "annotateCOMP",
    "textDAT",
    "infoCHOP",
    "errorDAT",
}

WEBSOCKET_PROTOCOL_OPS = {
    "websocketDAT",
    "tableDAT",
    "nullDAT",
    "baseCOMP",
    "annotateCOMP",
    "textDAT",
    "infoCHOP",
    "errorDAT",
}

MQTT_PROTOCOL_OPS = {
    "mqttclientDAT",
    "tableDAT",
    "nullDAT",
    "baseCOMP",
    "annotateCOMP",
    "textDAT",
    "infoCHOP",
    "errorDAT",
}

UDP_PROTOCOL_OPS = {
    "udpinDAT",
    "tableDAT",
    "nullDAT",
    "baseCOMP",
    "annotateCOMP",
    "textDAT",
    "infoCHOP",
    "errorDAT",
}

DAT_RENDER_SWITCH_OPS = {
    "tableDAT",
    "constantTOP",
    "noiseTOP",
    "switchTOP",
    "nullTOP",
    "baseCOMP",
    "annotateCOMP",
    "textDAT",
    "infoCHOP",
    "errorDAT",
}

NDI_POST_FX_OPS = {
    "ndiinTOP",
    "levelTOP",
    "nullTOP",
    "baseCOMP",
    "annotateCOMP",
    "infoCHOP",
    "errorDAT",
}

POP_PREVIEW_OPS = {
    "circlePOP",
    "noisePOP",
    "mathmixPOP",
    "nullPOP",
    "rendersimpleTOP",
    "nullTOP",
    "textDAT",
    "baseCOMP",
    "annotateCOMP",
    "infoCHOP",
    "errorDAT",
}

GLSL_TOP_SHADER_OPS = {
    "constantTOP",
    "glslTOP",
    "textDAT",
    "nullTOP",
    "baseCOMP",
    "annotateCOMP",
    "infoCHOP",
    "errorDAT",
}

GLSL_ADVANCED_POP_OPS = {
    "circlePOP",
    "glsladvancedPOP",
    "topologyPOP",
    "textDAT",
    "nullPOP",
    "rendersimpleTOP",
    "nullTOP",
    "baseCOMP",
    "annotateCOMP",
    "infoCHOP",
    "errorDAT",
}


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
    assert not any(op.args.get("assembly_macro_id") for op in plan.patch_plan.operations)
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
    assert plan.compiled_task is None
    assert plan.candidate_graphs == []
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
    assert plan.compiled_task is None
    assert plan.candidate_graphs == []
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
    shader_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target == "/project1/glsl"
    ]
    assert shader_params and shader_params[0]["computedat"] == "/project1/text"
    generated_ops = [
        op
        for op in plan.patch_plan.operations
        if op.kind == "set_dat_content" and isinstance(op.args.get("generated_code"), dict)
    ]
    assert generated_ops
    compute_source_op = generated_ops[0]
    assert compute_source_op.target == "/project1/text"
    assert "TDIndex()" in compute_source_op.args["text"]
    assert "TDNumElements()" in compute_source_op.args["text"]
    assert compute_source_op.args["generated_code"]["target_op"] == "/project1/glsl"
    assert compute_source_op.args["generated_code"]["target_param"] == "computedat"
    assert compute_source_op.args["generated_code"]["source_refs"] == ["/project1/text"]
    assert "glsl_pop_bounds_guard" in compute_source_op.args["generated_code"]["static_checks"]
    assert validate_patch_plan_generated_code(plan.patch_plan) == []


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


@pytest.mark.asyncio
async def test_compiler_path_builds_audio_feedback_panel_debug_candidate_graph():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": [
                        "audiofileinCHOP",
                        "analyzeCHOP",
                        "mathCHOP",
                        "nullCHOP",
                        "panelCHOP",
                        "infoCHOP",
                    ],
                    "TOP": ["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
                    "COMP": ["baseCOMP", "containerCOMP", "sliderCOMP", "buttonCOMP", "annotateCOMP"],
                    "DAT": ["textDAT", "errorDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(PHASE_ONE_SEED_OPS),
    )

    assert plan.blocked_questions == []
    assert plan.compiled_task is not None
    assert plan.compiled_task.domains == ["CHOP", "TOP", "COMP", "DAT"]
    assert plan.concept_graph.profile == "concept_compiled"
    assert plan.candidate_graphs
    assert len(plan.candidate_graphs) >= 2
    assert plan.candidate_graphs[0].score >= plan.candidate_graphs[1].score
    assert any("device-source-required" in candidate.risk_flags for candidate in plan.candidate_graphs)
    device_candidate = next(
        candidate
        for candidate in plan.candidate_graphs
        if "audio_device_to_analysis_chop" in candidate.pattern_ids
    )
    assert "missing-op:audiodeviceinCHOP" in device_candidate.risk_flags
    candidate = plan.candidate_graphs[0]
    assert candidate.profiles == ["audio_reactive", "feedback", "panel_ui"]
    assert {
        "audio_analysis_chop_chain",
        "feedback_top_loop",
        "panel_control_output",
        "debug_output_conventions",
    }.issubset(set(candidate.pattern_ids))
    assert "audio_signal_activity" in candidate.validation_needs
    assert "feedback_output_readback" in candidate.validation_needs
    assert "panel_state_readback" in candidate.validation_needs
    assert set(candidate.required_ops).issubset(set(plan.patch_plan.required_ops))
    assert "textDAT" in plan.patch_plan.required_ops
    assert "annotateCOMP" in plan.patch_plan.required_ops
    assert "infoCHOP" in plan.patch_plan.required_ops
    assert "errorDAT" in plan.patch_plan.required_ops
    assert "baseCOMP" in plan.patch_plan.required_ops
    assert any(edge.kind == "control" and edge.source == "audio_out" for edge in plan.concept_graph.edges)
    assert all(f"docs:{op_type}" in plan.grounding_evidence for op_type in candidate.required_ops)
    assert "docs:baseCOMP" in plan.grounding_evidence
    assert "compiler:path:phase1-audio-feedback-panel-debug" in plan.grounding_evidence
    create_names = [op.args["name"] for op in plan.patch_plan.operations if op.kind == "create_node"]
    assert "tdpilot_concept" in create_names
    assert "out1" in create_names
    assert "out_chop" in create_names
    assert "debug_notes" in create_names
    assert "debug_info" in create_names
    assert "error_log" in create_names
    shell_path = "/project1/tdpilot_concept"
    assert plan.patch_plan.validation_plan.capture_frames == [f"{shell_path}/out1"]
    assert plan.patch_plan.operations[0].kind == "create_node"
    assert plan.patch_plan.operations[0].target == "/project1"
    assert plan.patch_plan.operations[0].args["op_type"] == "baseCOMP"
    assert plan.patch_plan.operations[0].args["name"] == "tdpilot_concept"
    assert plan.patch_plan.operations[0].args["assembly_macro_id"] == "make_component_shell"
    child_create_targets = [
        op.target
        for op in plan.patch_plan.operations[1:]
        if op.kind == "create_node" and op.args.get("assembly_macro_id") != "add_debug_panel"
    ]
    assert child_create_targets and set(child_create_targets) == {shell_path}

    panel_reader_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target == f"{shell_path}/panel_reader"
    ]
    assert panel_reader_params and panel_reader_params[0]["component"] == f"{shell_path}/panel_container"

    audio_analyze_params = _set_params_for(plan, _first_created_target(plan, "analyzeCHOP"))
    assert audio_analyze_params == {
        "function": "RMS Power",
        "allowstart": False,
        "allowend": False,
        "valleys": False,
    }
    audio_math_params = _set_params_for(plan, _first_created_target(plan, "mathCHOP"))
    assert audio_math_params == {"fromrange": (0.0, 1.0), "torange": (0.0, 1.0), "interppars": True}
    feedback_decay_params = _set_params_for(plan, _first_created_target(plan, "levelTOP"))
    assert feedback_decay_params == {"opacity": 0.92}

    debug_info_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target == f"{shell_path}/debug_info"
    ]
    assert debug_info_params and debug_info_params[0]["op"] == f"{shell_path}/out1"
    assert debug_info_params[0]["passive"] is True
    error_log_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target == f"{shell_path}/error_log"
    ]
    assert error_log_params and error_log_params[0]["source"] == f"{shell_path}/*"
    assert error_log_params[0]["clamp"] is True
    assert error_log_params[0]["maxlines"] == 50
    connect_paths = [
        value
        for op in plan.patch_plan.operations
        if op.kind == "connect"
        for value in (op.args["from"], op.args["to"])
    ]
    assert not any(path.endswith("/debug_info") or path.endswith("/error_log") for path in connect_paths)
    assert connect_paths and all(path.startswith(f"{shell_path}/") for path in connect_paths)

    assembly_ops = [op for op in plan.patch_plan.operations if op.args.get("assembly_macro_id")]
    assembly_ids = {op.args["assembly_macro_id"] for op in assembly_ops}
    assert {
        "make_component_shell",
        "group_by_domain",
        "add_named_outputs",
        "add_debug_panel",
        "add_user_controls",
        "annotate_operator_chain",
    }.issubset(assembly_ids)
    layout_ops = [op for op in assembly_ops if op.kind == "layout"]
    assert layout_ops
    domain_columns = {op.args["domain"]: op.args["x"] for op in layout_ops if "domain" in op.args}
    assert domain_columns == {"CHOP": 0, "TOP": 360, "COMP": 720, "DAT": 1080}
    annotations = [op for op in assembly_ops if op.kind == "annotate"]
    assert annotations
    annotation = annotations[0]
    assert "audio_analysis_chop_chain" in annotation.args["text"]
    assert "validation:" in annotation.args["text"]
    assert "notes:" in annotation.args["text"]
    assert (
        "Place the assembled concept graph inside a deterministic Base COMP shell."
        in annotation.args["macro_notes"]
    )
    assert "Make stable output nodes easy to identify and validate." in annotation.args["macro_notes"]


@pytest.mark.asyncio
async def test_compiler_path_uses_trace_promoted_patterns_when_memory_is_enabled(monkeypatch, tmp_path):
    promoted = _promoted_audio_feedback_pattern()
    trace_path = tmp_path / "brain_traces.jsonl"
    trace_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "type": "brain_execution",
                "promoted_pattern_candidate": promoted.model_dump(mode="json"),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TDPILOT_BRAIN_TRACE_PATH", str(trace_path))
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": [
                        "audiofileinCHOP",
                        "analyzeCHOP",
                        "mathCHOP",
                        "nullCHOP",
                        "panelCHOP",
                        "infoCHOP",
                    ],
                    "TOP": ["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
                    "COMP": ["baseCOMP", "containerCOMP", "sliderCOMP", "buttonCOMP", "annotateCOMP"],
                    "DAT": ["textDAT", "errorDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(PHASE_ONE_SEED_OPS),
        include_memory=True,
    )

    assert plan.blocked_questions == []
    assert plan.candidate_graphs[0].pattern_ids == ["trace_audio_feedback_green_audio_feedback_panel"]
    assert "trace-promoted:trace-audio-feedback-green" in plan.grounding_evidence
    assert "runtime-validation:trace_audio_feedback_green_audio_feedback_panel:3" in plan.grounding_evidence
    assert "promoted_trace:trace-audio-feedback-green" in plan.candidate_graphs[0].explanation


@pytest.mark.asyncio
async def test_compiler_path_ignores_trace_promoted_patterns_when_memory_is_disabled(monkeypatch, tmp_path):
    promoted = _promoted_audio_feedback_pattern()
    trace_path = tmp_path / "brain_traces.jsonl"
    trace_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "type": "brain_execution",
                "promoted_pattern_candidate": promoted.model_dump(mode="json"),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TDPILOT_BRAIN_TRACE_PATH", str(trace_path))
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": [
                        "audiofileinCHOP",
                        "analyzeCHOP",
                        "mathCHOP",
                        "nullCHOP",
                        "panelCHOP",
                        "infoCHOP",
                    ],
                    "TOP": ["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
                    "COMP": ["baseCOMP", "containerCOMP", "sliderCOMP", "buttonCOMP", "annotateCOMP"],
                    "DAT": ["textDAT", "errorDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(PHASE_ONE_SEED_OPS),
        include_memory=False,
    )

    assert "trace_audio_feedback_green_audio_feedback_panel" not in plan.candidate_graphs[0].pattern_ids
    assert "trace-promoted:trace-audio-feedback-green" not in plan.grounding_evidence


@pytest.mark.asyncio
async def test_compiler_path_uses_device_audio_substitution_when_file_audio_missing():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": [
                        "audiodeviceinCHOP",
                        "analyzeCHOP",
                        "mathCHOP",
                        "nullCHOP",
                        "panelCHOP",
                        "infoCHOP",
                    ],
                    "TOP": ["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
                    "COMP": ["baseCOMP", "containerCOMP", "sliderCOMP", "buttonCOMP", "annotateCOMP"],
                    "DAT": ["textDAT", "errorDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        constraints={"device_sources": ["audio_device"]},
        card_index=FakeCardIndex(PHASE_ONE_SEED_OPS | {"audiodeviceinCHOP"}),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert "audio_device_to_analysis_chop" in plan.candidate_graphs[0].pattern_ids
    assert "audiodeviceinCHOP" in plan.patch_plan.required_ops
    assert "audiofileinCHOP" not in plan.patch_plan.required_ops
    audio_device_params = _set_params_for(plan, _first_created_target(plan, "audiodeviceinCHOP"))
    assert audio_device_params == {"active": True, "errormissing": True, "format": "stereo"}
    assert "substitution:audiofileinCHOP->audio_device_to_analysis_chop" in plan.grounding_evidence
    assert (
        "substitution-rule:audiofileinCHOP->audiodeviceinCHOP:medium:requires-approval"
        in plan.grounding_evidence
    )
    assert "device-source-declared:audio_device" in plan.grounding_evidence
    assert any(item.startswith("availability:td_build:") for item in plan.grounding_evidence)
    assert [item.model_dump(mode="json") for item in plan.substitution_explanations] == [
        {
            "missing_op": "audiofileinCHOP",
            "replacement_target": "audio_device_to_analysis_chop",
            "replacement_ops": ["audiodeviceinCHOP"],
            "confidence": "medium",
            "requires_approval": True,
            "approval_state": "approved",
            "approval_evidence": ["device-source-declared:audio_device"],
            "availability_reason": "missing from live family list",
            "tradeoffs": ["uses a live audio input device instead of a deterministic audio file"],
            "official_sources": [
                "https://docs.derivative.ca/Audio_File_In_CHOP",
                "https://docs.derivative.ca/Audio_Device_In_CHOP",
            ],
            "summary": (
                "audiofileinCHOP is unavailable in this TouchDesigner environment "
                "(missing from live family list), so TDPilot selected audio_device_to_analysis_chop "
                "using audiodeviceinCHOP. Tradeoff: uses a live audio input device instead of a deterministic audio file."
            ),
        }
    ]


@pytest.mark.asyncio
async def test_compiler_path_blocks_unapproved_available_audio_device_substitution():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": [
                        "audiodeviceinCHOP",
                        "analyzeCHOP",
                        "mathCHOP",
                        "nullCHOP",
                        "panelCHOP",
                        "infoCHOP",
                    ],
                    "TOP": ["noiseTOP", "feedbackTOP", "levelTOP", "compositeTOP", "nullTOP"],
                    "COMP": ["baseCOMP", "containerCOMP", "sliderCOMP", "buttonCOMP", "annotateCOMP"],
                    "DAT": ["textDAT", "errorDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        constraints={"device_sources": ["midi_device"]},
        card_index=FakeCardIndex(PHASE_ONE_SEED_OPS | {"audiodeviceinCHOP"}),
    )

    assert plan.blocked_questions
    assert "missing_device_source:audio_device" in plan.missing_facts
    assert "audio_device_to_analysis_chop" in plan.candidate_graphs[0].pattern_ids
    assert "audiodeviceinCHOP" in plan.candidate_graphs[0].required_ops
    assert "audiofileinCHOP" not in plan.candidate_graphs[0].required_ops
    assert (
        "substitution:audiofileinCHOP->audio_device_to_analysis_chop:pending-approval"
        in plan.grounding_evidence
    )
    assert "substitution-rule:audiofileinCHOP->audiodeviceinCHOP:medium:requires-approval" in (
        plan.grounding_evidence
    )
    assert plan.substitution_explanations[0].approval_state == "pending"
    assert plan.substitution_explanations[0].summary.startswith(
        "audiofileinCHOP is unavailable in this TouchDesigner environment"
    )
    assert plan.patch_plan.operations == []


@pytest.mark.asyncio
async def test_compiler_path_builds_audio_reactive_glsl_material_render_candidate_graph():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": ["audiofileinCHOP", "analyzeCHOP", "mathCHOP", "nullCHOP", "infoCHOP"],
                    "TOP": ["renderTOP", "nullTOP"],
                    "COMP": ["baseCOMP", "geometryCOMP", "cameraCOMP", "annotateCOMP"],
                    "MAT": ["glslMAT"],
                    "DAT": ["textDAT", "errorDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build an audio-reactive 3D render with material modulation",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(MATERIAL_RENDER_OPS),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.compiled_task is not None
    assert plan.compiled_task.domains == ["CHOP", "TOP", "COMP", "DAT", "MAT"]
    assert plan.concept_graph.profile == "concept_compiled"
    candidate = plan.candidate_graphs[0]
    assert candidate.profiles == ["audio_reactive", "render_pipeline", "glsl_material"]
    assert {
        "audio_analysis_chop_chain",
        "glsl_material_render_pipeline",
        "debug_output_conventions",
    }.issubset(set(candidate.pattern_ids))
    assert set(candidate.required_ops).issubset(set(plan.patch_plan.required_ops))
    assert "baseCOMP" in plan.patch_plan.required_ops
    assert "glslMAT" in plan.patch_plan.required_ops
    assert "renderTOP" in plan.patch_plan.required_ops
    assert not any(flag.startswith("missing-op:") for flag in candidate.risk_flags)

    shell_path = "/project1/tdpilot_concept"
    create_names = [op.args["name"] for op in plan.patch_plan.operations if op.kind == "create_node"]
    assert "tdpilot_concept" in create_names
    assert "glsl" in create_names
    assert "render" in create_names
    assert "out1" in create_names
    assert plan.patch_plan.validation_plan.capture_frames == [f"{shell_path}/out1"]

    geometry_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target == f"{shell_path}/geometry"
    ]
    assert geometry_params and geometry_params[0]["material"] == f"{shell_path}/glsl"
    material_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target == f"{shell_path}/glsl"
    ]
    assert material_params and material_params[0]["vdat"] == f"{shell_path}/text"
    assert material_params[0]["pdat"] == f"{shell_path}/text2"
    generated_ops = [
        op
        for op in plan.patch_plan.operations
        if op.kind == "set_dat_content" and isinstance(op.args.get("generated_code"), dict)
    ]
    generated_by_target = {
        op.args["generated_code"]["target_param"]: op.args["generated_code"] for op in generated_ops
    }
    assert {"vdat", "pdat"}.issubset(generated_by_target)
    assert generated_by_target["vdat"]["target_op"] == f"{shell_path}/glsl"
    assert generated_by_target["vdat"]["source_refs"] == [f"{shell_path}/text"]
    assert "glsl_mat_vertex_shader" in generated_by_target["vdat"]["static_checks"]
    assert generated_by_target["pdat"]["target_op"] == f"{shell_path}/glsl"
    assert generated_by_target["pdat"]["source_refs"] == [f"{shell_path}/text2"]
    assert "glsl_mat_pixel_shader" in generated_by_target["pdat"]["static_checks"]
    assert validate_patch_plan_generated_code(plan.patch_plan) == []
    render_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target == f"{shell_path}/render"
    ]
    assert render_params and render_params[0]["camera"] == f"{shell_path}/camera"
    assert render_params[0]["geometry"] == f"{shell_path}/geometry"
    debug_info_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target == f"{shell_path}/debug_info"
    ]
    assert debug_info_params and debug_info_params[0]["op"] == f"{shell_path}/out1"


@pytest.mark.asyncio
async def test_compiler_path_builds_audio_reactive_glsl_material_render_with_panel_controls():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": [
                        "audiofileinCHOP",
                        "analyzeCHOP",
                        "mathCHOP",
                        "nullCHOP",
                        "panelCHOP",
                        "infoCHOP",
                    ],
                    "TOP": ["renderTOP", "nullTOP"],
                    "COMP": [
                        "baseCOMP",
                        "geometryCOMP",
                        "cameraCOMP",
                        "containerCOMP",
                        "sliderCOMP",
                        "buttonCOMP",
                        "annotateCOMP",
                    ],
                    "MAT": ["glslMAT"],
                    "DAT": ["textDAT", "errorDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build an audio-reactive GLSL material render with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(MATERIAL_RENDER_OPS),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.compiled_task is not None
    assert plan.compiled_task.domains == ["CHOP", "TOP", "COMP", "DAT", "MAT"]
    assert plan.concept_graph.profile == "concept_compiled"
    candidate = plan.candidate_graphs[0]
    assert candidate.profiles == ["audio_reactive", "render_pipeline", "glsl_material", "panel_ui"]
    expected_path_marker = (
        "compiler:path:phase1-audio-reactive-render-pipeline-glsl-material-panel-ui-debug-output"
    )
    assert "compiler:path:phase1-audio-feedback-panel-debug" not in plan.grounding_evidence
    assert expected_path_marker in plan.grounding_evidence
    assert {
        "audio_analysis_chop_chain",
        "glsl_material_render_pipeline",
        "panel_control_output",
        "debug_output_conventions",
    }.issubset(set(candidate.pattern_ids))
    assert any(
        edge.kind == "control" and edge.source == "panel_out" and edge.target == "material"
        for edge in plan.concept_graph.edges
    )
    assembly_ids = {
        op.args["assembly_macro_id"] for op in plan.patch_plan.operations if op.args.get("assembly_macro_id")
    }
    assert "add_user_controls" in assembly_ids

    shell_path = "/project1/tdpilot_concept"
    create_names = [op.args["name"] for op in plan.patch_plan.operations if op.kind == "create_node"]
    assert "panel_container" in create_names
    assert "panel_slider" in create_names
    assert "panel_button" in create_names
    assert "panel_reader" in create_names
    assert plan.patch_plan.validation_plan.capture_frames == [f"{shell_path}/out1"]

    panel_reader_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target == f"{shell_path}/panel_reader"
    ]
    assert panel_reader_params and panel_reader_params[0]["component"] == f"{shell_path}/panel_container"

    material_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target == f"{shell_path}/glsl"
    ]
    assert material_params and material_params[0]["vdat"] == f"{shell_path}/text"
    assert material_params[0]["pdat"] == f"{shell_path}/text2"


@pytest.mark.asyncio
async def test_compiler_path_builds_audio_reactive_terrain_material_with_controls():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": [
                        "audiofileinCHOP",
                        "analyzeCHOP",
                        "mathCHOP",
                        "nullCHOP",
                        "panelCHOP",
                        "infoCHOP",
                    ],
                    "SOP": ["gridSOP", "noiseSOP", "nullSOP"],
                    "TOP": ["renderTOP", "nullTOP"],
                    "COMP": [
                        "baseCOMP",
                        "geometryCOMP",
                        "cameraCOMP",
                        "containerCOMP",
                        "sliderCOMP",
                        "buttonCOMP",
                        "annotateCOMP",
                    ],
                    "MAT": ["glslMAT"],
                    "DAT": ["textDAT", "errorDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build a melting glass terrain driven by music with UI controls and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(TERRAIN_MATERIAL_OPS),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.compiled_task is not None
    assert plan.compiled_task.domains == ["CHOP", "TOP", "COMP", "DAT", "SOP", "MAT"]
    candidate = plan.candidate_graphs[0]
    assert {
        "audio_analysis_chop_chain",
        "sop_noise_terrain_surface",
        "glsl_material_render_pipeline",
        "panel_control_output",
        "debug_output_conventions",
    }.issubset(set(candidate.pattern_ids))
    assert any(
        edge.kind == "reference" and edge.source == "terrain_out" and edge.target == "geo"
        for edge in plan.concept_graph.edges
    )

    shell_path = "/project1/tdpilot_concept"
    create_names = [op.args["name"] for op in plan.patch_plan.operations if op.kind == "create_node"]
    assert "grid" in create_names
    assert "noise" in create_names
    assert "out_sop" in create_names
    assert "geometry" in create_names
    assert "panel_container" in create_names

    geometry_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target == f"{shell_path}/geometry"
    ]
    assert geometry_params
    assert geometry_params[0]["sop"] == f"{shell_path}/out_sop"
    assert geometry_params[0]["material"] == f"{shell_path}/glsl"
    assert "add_user_controls" in {
        op.args["assembly_macro_id"] for op in plan.patch_plan.operations if op.args.get("assembly_macro_id")
    }
    assert plan.patch_plan.validation_plan.capture_frames == [f"{shell_path}/out1"]


@pytest.mark.asyncio
async def test_compiler_path_builds_dat_execute_callback_with_valid_generated_code_attachment():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["datexecuteDAT", "tableDAT", "textDAT", "nullDAT", "errorDAT"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build a DAT Execute table-change callback with stable DAT diagnostics",
        target_root="/project1",
        card_index=FakeCardIndex(DAT_EXECUTE_CALLBACK_OPS),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.compiled_task is not None
    assert plan.compiled_task.domains == ["DAT"]
    assert plan.concept_graph.profile == "concept_compiled"
    assert plan.candidate_graphs
    candidate = plan.candidate_graphs[0]
    assert candidate.profiles == ["dat_protocol"]
    assert "dat_execute_table_change_callback" in candidate.pattern_ids
    assert {"datexecuteDAT", "tableDAT", "textDAT", "nullDAT"}.issubset(set(candidate.required_ops))
    assert "callback_guard_present" in candidate.validation_needs

    generated_ops = [
        op
        for op in plan.patch_plan.operations
        if op.kind == "set_dat_content" and isinstance(op.args.get("generated_code"), dict)
    ]
    assert generated_ops
    callback_op = generated_ops[0]
    callback_metadata = callback_op.args["generated_code"]
    shell_path = "/project1/tdpilot_concept"

    assert callback_op.target == f"{shell_path}/table_change_exec"
    assert "def onTableChange(dat, prevDAT, info):" in callback_op.args["text"]
    assert "tdpilot_callback_guard" in callback_op.args["text"]
    assert callback_metadata["target_op"] == f"{shell_path}/table_change_exec"
    assert callback_metadata["target_param"] == "text"
    assert callback_metadata["source_refs"] == [f"{shell_path}/table_change_exec"]
    assert "dat_execute_table_change_callback" in callback_metadata["static_checks"]
    assert "diagnostic_output_present" in callback_metadata["runtime_checks"]
    assert callback_metadata["expected_outputs"] == [f"{shell_path}/out_dat"]
    assert f"{shell_path}/out_dat" in callback_op.args["text"]

    exec_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target == f"{shell_path}/table_change_exec"
    ]
    assert exec_params
    assert exec_params[0]["dat"] == f"{shell_path}/table"
    assert "callbacks" not in exec_params[0]
    assert exec_params[0]["tablechange"] is True
    assert exec_params[0]["rowchange"] is False
    assert exec_params[0]["colchange"] is False
    assert exec_params[0]["cellchange"] is False
    assert exec_params[0]["sizechange"] is False

    assert validate_patch_plan_generated_code(plan.patch_plan) == []


@pytest.mark.asyncio
async def test_compiler_path_blocks_dat_execute_when_availability_sample_reports_unavailable():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["datexecuteDAT", "tableDAT", "textDAT", "nullDAT", "errorDAT"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build a DAT Execute table-change callback with stable DAT diagnostics",
        target_root="/project1",
        constraints={
            "availability_report": {
                "results": [
                    {
                        "op_type": "datexecuteDAT",
                        "available": False,
                        "error": "Cannot create operator",
                    }
                ]
            }
        },
        card_index=FakeCardIndex(DAT_EXECUTE_CALLBACK_OPS),
    )

    assert plan.blocked_questions
    assert "missing_op:datexecuteDAT" in plan.missing_facts
    assert "availability_sample_unavailable:datexecuteDAT" in plan.missing_facts
    assert "missing-op:datexecuteDAT" in plan.risk_flags
    assert "availability-sample:unavailable:datexecuteDAT" in plan.grounding_evidence
    assert "availability-sample-reason:datexecuteDAT:Cannot create operator" in plan.grounding_evidence
    assert plan.patch_plan.operations == []
    assert plan.patch_plan.risk_flags == ["missing required operators"]


@pytest.mark.asyncio
async def test_compiler_path_blocks_dat_execute_when_availability_matrix_reports_unavailable():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["datexecuteDAT", "tableDAT", "textDAT", "nullDAT", "errorDAT"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build a DAT Execute table-change callback with stable DAT diagnostics",
        target_root="/project1",
        constraints={
            "availability_matrix": {
                "schema_version": 1,
                "td_build": "2025.32820",
                "platform": "macOS",
                "generated_at": "2026-06-22T00:00:00+00:00",
                "installed_addons": ["POPX"],
                "operators": {
                    "datexecuteDAT": {"family": "DAT", "available": False},
                    "tableDAT": {"family": "DAT", "available": True},
                },
                "family_aliases": {
                    "DAT": ["datexecuteDAT", "tableDAT"],
                },
                "unavailable_reasons": {
                    "datexecuteDAT": "Cannot create operator",
                },
            }
        },
        card_index=FakeCardIndex(DAT_EXECUTE_CALLBACK_OPS),
    )

    assert plan.blocked_questions
    assert "missing_op:datexecuteDAT" in plan.missing_facts
    assert "availability_sample_unavailable:datexecuteDAT" in plan.missing_facts
    assert "missing-op:datexecuteDAT" in plan.risk_flags
    assert "availability-sample:unavailable:datexecuteDAT" in plan.grounding_evidence
    assert "availability-sample-reason:datexecuteDAT:Cannot create operator" in plan.grounding_evidence
    assert "availability:td_build:2025.32820" in plan.grounding_evidence
    assert "availability:platform:macOS" in plan.grounding_evidence
    assert "availability:addon:POPX" in plan.grounding_evidence
    assert plan.availability_matrix is not None
    assert plan.availability_matrix.td_build == "2025.32820"
    assert plan.availability_matrix.platform == "macOS"
    assert plan.availability_matrix.installed_addons == ["POPX"]
    assert plan.availability_matrix.operators["datexecuteDAT"]["available"] is False
    assert plan.availability_matrix.unavailable_reasons["datexecuteDAT"] == "Cannot create operator"
    assert plan.patch_plan.operations == []


@pytest.mark.asyncio
async def test_compiler_path_blocks_dat_execute_from_stored_availability_report(tmp_path):
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["datexecuteDAT", "tableDAT", "textDAT", "nullDAT", "errorDAT"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )
    report_path = tmp_path / "operator_availability.json"
    report_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "ok": True,
                "availability_matrix": {
                    "schema_version": 1,
                    "td_build": "2025.32820",
                    "platform": "macOS",
                    "generated_at": "2026-06-22T00:00:00+00:00",
                    "installed_addons": ["POPX"],
                    "operators": {
                        "datexecuteDAT": {"family": "DAT", "available": False},
                        "tableDAT": {"family": "DAT", "available": True},
                    },
                    "family_aliases": {
                        "DAT": ["datexecuteDAT", "tableDAT"],
                    },
                    "unavailable_reasons": {
                        "datexecuteDAT": "Cannot create operator",
                    },
                },
                "results": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    plan = await build_brain_plan(
        client,
        intent="Build a DAT Execute table-change callback with stable DAT diagnostics",
        target_root="/project1",
        constraints={"availability_report_path": str(report_path)},
        card_index=FakeCardIndex(DAT_EXECUTE_CALLBACK_OPS),
    )

    assert plan.blocked_questions
    assert "missing_op:datexecuteDAT" in plan.missing_facts
    assert "availability_sample_unavailable:datexecuteDAT" in plan.missing_facts
    assert "missing-op:datexecuteDAT" in plan.risk_flags
    assert "availability-sample:unavailable:datexecuteDAT" in plan.grounding_evidence
    assert "availability-sample-reason:datexecuteDAT:Cannot create operator" in plan.grounding_evidence
    assert "availability:td_build:2025.32820" in plan.grounding_evidence
    assert "availability:platform:macOS" in plan.grounding_evidence
    assert "availability:addon:POPX" in plan.grounding_evidence
    assert plan.patch_plan.operations == []


@pytest.mark.asyncio
async def test_compiler_path_blocks_ndi_post_fx_without_declared_network_source():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "TOP": ["ndiinTOP", "levelTOP", "nullTOP"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                    "DAT": ["textDAT", "errorDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build an NDI input with post FX and stable TOP output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(NDI_POST_FX_OPS),
    )

    assert plan.blocked_questions
    assert "missing_device_source:ndi_source" in plan.missing_facts
    assert "device-source-required" in plan.risk_flags
    assert plan.patch_plan.operations == []
    assert plan.patch_plan.risk_flags == ["missing device source"]


@pytest.mark.asyncio
async def test_open_prompt_atlas_ignores_ndi_docs_distractor_for_procedural_top():
    cards = [
        _atlas_card(
            "ndiinTOP",
            "TOP",
            "NDI In TOP receives network video input; distractor device source docs.",
            ["ndi", "network", "video", "source"],
            params=["source"],
        ),
        _atlas_card(
            "noiseTOP",
            "TOP",
            "Procedural noise texture source for a stable texture wash.",
            ["procedural", "texture", "source"],
            params=["period"],
        ),
        _atlas_card(
            "levelTOP",
            "TOP",
            "Level TOP shapes brightness for a texture wash.",
            ["brightness", "level", "process"],
            params=["brightness1"],
        ),
        _atlas_card(
            "nullTOP",
            "TOP",
            "Stable TOP output for final texture.",
            ["stable", "output", "texture"],
        ),
    ]
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "TOP": ["ndiinTOP", "noiseTOP", "levelTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="procedural texture wash with stable TOP output while NDI In TOP docs are present",
        target_root="/project1",
        card_index=AtlasCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.concept_graph.profile == "generic"
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:top_card_chain"]
    assert candidate.required_ops == ["noiseTOP", "levelTOP", "nullTOP"]
    assert "ndiinTOP" not in candidate.required_ops
    assert "missing_device_source:ndi_source" not in plan.missing_facts
    assert "atlas-synthesis:source:noiseTOP" in plan.grounding_evidence


@pytest.mark.asyncio
async def test_open_prompt_atlas_ignores_audio_docs_distractor_for_procedural_top():
    cards = [
        _atlas_card(
            "audiofileinCHOP",
            "CHOP",
            "Audio File In CHOP plays sound files; distractor audio source docs.",
            ["audio", "sound", "source"],
            params=["file"],
        ),
        _atlas_card(
            "analyzeCHOP",
            "CHOP",
            "Analyze CHOP measures amplitude of audio channels.",
            ["audio", "analyze", "amplitude"],
            params=["function"],
        ),
        _atlas_card(
            "mathCHOP",
            "CHOP",
            "Math CHOP normalizes audio control ranges.",
            ["audio", "normalize", "process"],
            params=["fromrange", "torange"],
        ),
        _atlas_card(
            "nullCHOP",
            "CHOP",
            "Stable CHOP output for audio control.",
            ["stable", "output", "audio"],
        ),
        _atlas_card(
            "noiseTOP",
            "TOP",
            "Procedural noise texture source for a stable texture wash.",
            ["procedural", "texture", "source"],
            params=["period"],
        ),
        _atlas_card(
            "levelTOP",
            "TOP",
            "Level TOP shapes brightness for a texture wash.",
            ["brightness", "level", "process"],
            params=["brightness1"],
        ),
        _atlas_card(
            "nullTOP",
            "TOP",
            "Stable TOP output for final texture.",
            ["stable", "output", "texture"],
        ),
    ]
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": ["audiofileinCHOP", "analyzeCHOP", "mathCHOP", "nullCHOP"],
                    "TOP": ["noiseTOP", "levelTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="procedural texture wash with stable TOP output while Audio File In CHOP docs are present",
        target_root="/project1",
        card_index=AtlasCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.concept_graph.profile == "generic"
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:top_card_chain"]
    assert candidate.required_ops == ["noiseTOP", "levelTOP", "nullTOP"]
    assert "audiofileinCHOP" not in candidate.required_ops
    assert "atlas-synthesis:source:noiseTOP" in plan.grounding_evidence
    assert "profile:audio_reactive" not in plan.grounding_evidence


@pytest.mark.asyncio
async def test_compiler_path_blocks_osc_dat_protocol_without_declared_network_source():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["oscinDAT", "tableDAT", "nullDAT", "textDAT", "errorDAT"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build an OSC DAT protocol bridge with table diagnostics",
        target_root="/project1",
        card_index=FakeCardIndex(OSC_PROTOCOL_OPS),
    )

    assert plan.blocked_questions
    assert "missing_device_source:osc_source" in plan.missing_facts
    assert "device-source-required" in plan.risk_flags
    assert plan.patch_plan.operations == []
    assert plan.patch_plan.risk_flags == ["missing device source"]


@pytest.mark.asyncio
async def test_compiler_path_builds_osc_dat_protocol_candidate_graph():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["oscinDAT", "tableDAT", "nullDAT", "textDAT", "errorDAT"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build an OSC DAT protocol bridge with table diagnostics",
        target_root="/project1",
        constraints={"device_sources": ["osc_source"]},
        card_index=FakeCardIndex(OSC_PROTOCOL_OPS),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.compiled_task is not None
    assert plan.compiled_task.domains == ["DAT"]
    assert plan.concept_graph.profile == "concept_compiled"
    assert plan.candidate_graphs
    candidate = plan.candidate_graphs[0]
    assert candidate.profiles == ["dat_protocol"]
    assert "osc_in_dat_protocol_bridge" in candidate.pattern_ids
    assert {"oscinDAT", "tableDAT", "nullDAT"}.issubset(set(candidate.required_ops))
    assert "device-source-required" in candidate.risk_flags
    assert set(candidate.required_ops).issubset(set(plan.patch_plan.required_ops))

    shell_path = "/project1/tdpilot_concept"
    create_names = [op.args["name"] for op in plan.patch_plan.operations if op.kind == "create_node"]
    assert "tdpilot_concept" in create_names
    assert "oscin" in create_names
    assert "table" in create_names
    assert "out_dat" in create_names
    assert "debug_notes" in create_names
    osc_params = _set_params_for(plan, _first_created_target(plan, "oscinDAT"))
    assert osc_params == {"active": True, "protocol": "msging", "clamp": True, "maxlines": 256}
    connect_pairs = [
        (op.args["from"], op.args["to"]) for op in plan.patch_plan.operations if op.kind == "connect"
    ]
    assert (f"{shell_path}/oscin", f"{shell_path}/out_dat") in connect_pairs


@pytest.mark.asyncio
async def test_compiler_path_blocks_websocket_dat_protocol_without_declared_endpoint():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["websocketDAT", "tableDAT", "nullDAT", "textDAT", "errorDAT"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build a WebSocket DAT protocol bridge with table diagnostics",
        target_root="/project1",
        card_index=FakeCardIndex(WEBSOCKET_PROTOCOL_OPS),
    )

    assert plan.blocked_questions
    assert "missing_device_source:websocket_endpoint" in plan.missing_facts
    assert "device-source-required" in plan.risk_flags
    assert plan.patch_plan.operations == []
    assert plan.patch_plan.risk_flags == ["missing device source"]


@pytest.mark.asyncio
async def test_compiler_path_builds_websocket_dat_protocol_candidate_graph():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["websocketDAT", "tableDAT", "nullDAT", "textDAT", "errorDAT"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build a WebSocket DAT protocol bridge with table diagnostics",
        target_root="/project1",
        constraints={"device_sources": ["websocket_endpoint"]},
        card_index=FakeCardIndex(WEBSOCKET_PROTOCOL_OPS),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.compiled_task is not None
    assert plan.compiled_task.domains == ["DAT"]
    assert plan.concept_graph.profile == "concept_compiled"
    assert plan.candidate_graphs
    candidate = plan.candidate_graphs[0]
    assert candidate.profiles == ["dat_protocol"]
    assert "websocket_dat_protocol_bridge" in candidate.pattern_ids
    assert {"websocketDAT", "tableDAT", "nullDAT"}.issubset(set(candidate.required_ops))
    assert "device-source-required" in candidate.risk_flags
    assert set(candidate.required_ops).issubset(set(plan.patch_plan.required_ops))

    shell_path = "/project1/tdpilot_concept"
    create_names = [op.args["name"] for op in plan.patch_plan.operations if op.kind == "create_node"]
    assert "tdpilot_concept" in create_names
    assert "websocket" in create_names
    assert "table" in create_names
    assert "out_dat" in create_names
    assert "debug_notes" in create_names
    websocket_params = _set_params_for(plan, _first_created_target(plan, "websocketDAT"))
    assert websocket_params == {"active": True, "clamp": True, "maxlines": 256}
    connect_pairs = [
        (op.args["from"], op.args["to"]) for op in plan.patch_plan.operations if op.kind == "connect"
    ]
    assert (f"{shell_path}/websocket", f"{shell_path}/out_dat") in connect_pairs


@pytest.mark.asyncio
async def test_compiler_path_blocks_mqtt_dat_protocol_without_declared_broker():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["mqttclientDAT", "tableDAT", "nullDAT", "textDAT", "errorDAT"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build an MQTT DAT protocol bridge with table diagnostics",
        target_root="/project1",
        card_index=FakeCardIndex(MQTT_PROTOCOL_OPS),
    )

    assert plan.blocked_questions
    assert "missing_device_source:mqtt_broker" in plan.missing_facts
    assert "device-source-required" in plan.risk_flags
    assert plan.patch_plan.operations == []
    assert plan.patch_plan.risk_flags == ["missing device source"]


@pytest.mark.asyncio
async def test_compiler_path_builds_mqtt_dat_protocol_candidate_graph():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["mqttclientDAT", "tableDAT", "nullDAT", "textDAT", "errorDAT"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build an MQTT DAT protocol bridge with table diagnostics",
        target_root="/project1",
        constraints={"device_sources": ["mqtt_broker"]},
        card_index=FakeCardIndex(MQTT_PROTOCOL_OPS),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.compiled_task is not None
    assert plan.compiled_task.domains == ["DAT"]
    assert plan.concept_graph.profile == "concept_compiled"
    assert plan.candidate_graphs
    candidate = plan.candidate_graphs[0]
    assert candidate.profiles == ["dat_protocol"]
    assert "mqtt_client_dat_protocol_bridge" in candidate.pattern_ids
    assert {"mqttclientDAT", "tableDAT", "nullDAT"}.issubset(set(candidate.required_ops))
    assert "device-source-required" in candidate.risk_flags
    assert "device-source-declared:mqtt_broker" in plan.grounding_evidence
    assert set(candidate.required_ops).issubset(set(plan.patch_plan.required_ops))

    shell_path = "/project1/tdpilot_concept"
    create_names = [op.args["name"] for op in plan.patch_plan.operations if op.kind == "create_node"]
    assert "tdpilot_concept" in create_names
    assert "mqttclient" in create_names
    assert "table" in create_names
    assert "out_dat" in create_names
    assert "debug_notes" in create_names
    mqtt_params = _set_params_for(plan, _first_created_target(plan, "mqttclientDAT"))
    assert mqtt_params == {"active": True, "reconnect": True, "clamp": True, "maxlines": 256}
    connect_pairs = [
        (op.args["from"], op.args["to"]) for op in plan.patch_plan.operations if op.kind == "connect"
    ]
    assert (f"{shell_path}/mqttclient", f"{shell_path}/out_dat") in connect_pairs


@pytest.mark.asyncio
async def test_compiler_path_blocks_udp_dat_protocol_without_declared_source():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["udpinDAT", "tableDAT", "nullDAT", "textDAT", "errorDAT"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build a UDP DAT protocol bridge with table diagnostics",
        target_root="/project1",
        card_index=FakeCardIndex(UDP_PROTOCOL_OPS),
    )

    assert plan.blocked_questions
    assert "missing_device_source:udp_source" in plan.missing_facts
    assert "device-source-required" in plan.risk_flags
    assert plan.patch_plan.operations == []
    assert plan.patch_plan.risk_flags == ["missing device source"]


@pytest.mark.asyncio
async def test_compiler_path_builds_udp_dat_protocol_candidate_graph():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["udpinDAT", "tableDAT", "nullDAT", "textDAT", "errorDAT"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build a UDP DAT protocol bridge with table diagnostics",
        target_root="/project1",
        constraints={"device_sources": ["udp_source"]},
        card_index=FakeCardIndex(UDP_PROTOCOL_OPS),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.compiled_task is not None
    assert plan.compiled_task.domains == ["DAT"]
    assert plan.concept_graph.profile == "concept_compiled"
    assert plan.candidate_graphs
    candidate = plan.candidate_graphs[0]
    assert candidate.profiles == ["dat_protocol"]
    assert "udp_in_dat_protocol_bridge" in candidate.pattern_ids
    assert {"udpinDAT", "tableDAT", "nullDAT"}.issubset(set(candidate.required_ops))
    assert "device-source-required" in candidate.risk_flags
    assert "device-source-declared:udp_source" in plan.grounding_evidence
    assert set(candidate.required_ops).issubset(set(plan.patch_plan.required_ops))

    shell_path = "/project1/tdpilot_concept"
    create_names = [op.args["name"] for op in plan.patch_plan.operations if op.kind == "create_node"]
    assert "tdpilot_concept" in create_names
    assert "udpin" in create_names
    assert "table" in create_names
    assert "out_dat" in create_names
    assert "debug_notes" in create_names
    udp_params = _set_params_for(plan, _first_created_target(plan, "udpinDAT"))
    assert udp_params == {
        "active": True,
        "protocol": "msging",
        "format": "permessage",
        "clamp": True,
        "maxlines": 256,
    }
    connect_pairs = [
        (op.args["from"], op.args["to"]) for op in plan.patch_plan.operations if op.kind == "connect"
    ]
    assert (f"{shell_path}/udpin", f"{shell_path}/out_dat") in connect_pairs


@pytest.mark.asyncio
async def test_compiler_path_builds_dat_table_render_switch_candidate_graph():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["tableDAT", "textDAT", "errorDAT"],
                    "TOP": ["constantTOP", "noiseTOP", "switchTOP", "nullTOP"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build a DAT table driven render switch with stable TOP output and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(DAT_RENDER_SWITCH_OPS),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.compiled_task is not None
    assert plan.compiled_task.domains == ["TOP", "DAT"]
    assert plan.concept_graph.profile == "concept_compiled"
    assert plan.candidate_graphs
    candidate = plan.candidate_graphs[0]
    assert candidate.profiles == ["dat_protocol"]
    assert "dat_table_render_switch_top" in candidate.pattern_ids
    assert {"tableDAT", "constantTOP", "noiseTOP", "switchTOP", "nullTOP"}.issubset(
        set(candidate.required_ops)
    )
    assert "render_switch_table_present" in candidate.validation_needs
    assert "render_switch_output_present" in candidate.validation_needs
    assert set(candidate.required_ops).issubset(set(plan.patch_plan.required_ops))
    assert all(f"docs:{op_type}" in plan.grounding_evidence for op_type in candidate.required_ops)

    shell_path = "/project1/tdpilot_concept"
    create_names = [op.args["name"] for op in plan.patch_plan.operations if op.kind == "create_node"]
    assert "tdpilot_concept" in create_names
    assert "table" in create_names
    assert "constant" in create_names
    assert "noise" in create_names
    assert "switch" in create_names
    assert "out1" in create_names
    assert "debug_notes" in create_names
    assert plan.patch_plan.validation_plan.capture_frames == [f"{shell_path}/out1"]

    connect_pairs = [
        (op.args["from"], op.args["to"]) for op in plan.patch_plan.operations if op.kind == "connect"
    ]
    assert (f"{shell_path}/constant", f"{shell_path}/switch") in connect_pairs
    assert (f"{shell_path}/noise", f"{shell_path}/switch") in connect_pairs
    assert (f"{shell_path}/switch", f"{shell_path}/out1") in connect_pairs
    assert not any(
        pair[0] == f"{shell_path}/table" or pair[1] == f"{shell_path}/table" for pair in connect_pairs
    )
    assert any(
        edge.kind == "reference" and edge.source == "switch_table" and edge.target == "render_switch"
        for edge in plan.concept_graph.edges
    )

    table_content = [
        op.args
        for op in plan.patch_plan.operations
        if op.kind == "set_dat_content" and op.target == f"{shell_path}/table"
    ]
    assert table_content
    assert "selected_index" in table_content[0]["text"]
    assert "source_a" in table_content[0]["text"]

    switch_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target == f"{shell_path}/switch"
    ]
    assert switch_params == [
        {"index": {"expr": "min(1, max(0, int(op('/project1/tdpilot_concept/table')[1, 'selected_index'])))"}}
    ]


@pytest.mark.asyncio
async def test_compiler_path_builds_ndi_post_fx_output_candidate_graph():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "TOP": ["ndiinTOP", "levelTOP", "nullTOP"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                    "DAT": ["textDAT", "errorDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build an NDI input with post FX and stable TOP output",
        target_root="/project1",
        output_top="/project1/out1",
        constraints={"device_sources": ["ndi_source"]},
        card_index=FakeCardIndex(NDI_POST_FX_OPS),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.compiled_task is not None
    assert plan.compiled_task.domains == ["TOP"]
    assert plan.concept_graph.profile == "concept_compiled"
    assert plan.candidate_graphs
    candidate = plan.candidate_graphs[0]
    assert candidate.profiles == ["video_io"]
    assert "ndi_in_to_post_fx_output" in candidate.pattern_ids
    assert {"ndiinTOP", "levelTOP", "nullTOP"}.issubset(set(candidate.required_ops))
    assert "device-source-required" in candidate.risk_flags
    assert set(candidate.required_ops).issubset(set(plan.patch_plan.required_ops))

    shell_path = "/project1/tdpilot_concept"
    create_names = [op.args["name"] for op in plan.patch_plan.operations if op.kind == "create_node"]
    assert "tdpilot_concept" in create_names
    assert "ndiin" in create_names
    assert "level" in create_names
    assert "out1" in create_names
    assert "debug_notes" in create_names
    debug_notes_ops = [
        op
        for op in plan.patch_plan.operations
        if op.kind == "create_node" and op.args.get("name") == "debug_notes"
    ]
    assert debug_notes_ops and debug_notes_ops[0].args["op_type"] == "textDAT"
    assert debug_notes_ops[0].target == shell_path
    assert debug_notes_ops[0].args["assembly_macro_id"] == "add_debug_panel"
    assert plan.patch_plan.validation_plan.capture_frames == [f"{shell_path}/out1"]
    connect_pairs = [
        (op.args["from"], op.args["to"]) for op in plan.patch_plan.operations if op.kind == "connect"
    ]
    assert (f"{shell_path}/ndiin", f"{shell_path}/level") in connect_pairs
    assert (f"{shell_path}/level", f"{shell_path}/out1") in connect_pairs


@pytest.mark.asyncio
async def test_open_prompt_atlas_synthesizes_typed_sop_render_preview_graph():
    cards = [
        _atlas_card(
            "gridSOP",
            "SOP",
            "SOP mesh source grid for a surface that should become a visual texture output.",
            ["sop", "mesh", "surface", "source"],
            params=["rows", "cols"],
        ),
        _atlas_card(
            "noiseSOP",
            "SOP",
            "Noise SOP shapes and displaces the mesh surface before rendering.",
            ["surface", "noise", "process", "shaping"],
            params=["amp"],
        ),
        _atlas_card(
            "nullSOP",
            "SOP",
            "Stable SOP output for downstream render references.",
            ["stable", "output", "sop"],
        ),
        _atlas_card(
            "geometryCOMP",
            "COMP",
            "Geometry COMP references a SOP output for TOP rendering.",
            ["geometry", "sop", "render"],
            params=["sop"],
        ),
        _atlas_card(
            "cameraCOMP",
            "COMP",
            "Camera COMP frames the render output.",
            ["camera", "render"],
        ),
        _atlas_card(
            "lightCOMP",
            "COMP",
            "Light COMP provides illumination for the rendered SOP surface.",
            ["light", "render"],
        ),
        _atlas_card(
            "renderTOP",
            "TOP",
            "Render TOP creates a visual texture output from geometry, camera, and lights.",
            ["top", "render", "texture", "visual"],
            params=["geometry", "camera", "lights"],
        ),
        _atlas_card(
            "nullTOP",
            "TOP",
            "Stable TOP output for the final visual texture.",
            ["stable", "output", "texture"],
        ),
    ]
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "SOP": ["gridSOP", "noiseSOP", "nullSOP"],
                    "COMP": ["geometryCOMP", "cameraCOMP", "lightCOMP"],
                    "TOP": ["renderTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="SOP mesh surface becomes a visual texture output with noise shaping",
        target_root="/project1",
        card_index=AtlasCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.concept_graph.profile == "generic"
    assert plan.candidate_graphs
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:typed_role_graph_sop_render_preview_top_card_chain"]
    assert {
        "atlas-synthesis:typed-role-graph",
        "atlas-synthesis:role-graph:source->preview->output",
        "atlas-synthesis:multi-domain:sop-to-render-top-preview",
        "atlas-synthesis:family:sop+comp+top",
    }.issubset(set(plan.grounding_evidence))
    assert {
        "gridSOP",
        "noiseSOP",
        "nullSOP",
        "geometryCOMP",
        "cameraCOMP",
        "lightCOMP",
        "renderTOP",
        "nullTOP",
    } == set(candidate.required_ops)
    assert "soptoTOP" not in candidate.required_ops

    geometry_params = _set_params_for(plan, "/project1/geometry")
    render_params = _set_params_for(plan, "/project1/render")
    assert geometry_params == {"sop": "/project1/out_sop"}
    assert render_params == {
        "geometry": "/project1/geometry",
        "camera": "/project1/camera",
        "lights": "/project1/light",
    }
    assert plan.patch_plan.validation_plan.capture_frames == ["/project1/out1"]

    connect_pairs = [
        (op.args["from"], op.args["to"]) for op in plan.patch_plan.operations if op.kind == "connect"
    ]
    assert ("/project1/grid", "/project1/noise") in connect_pairs
    assert ("/project1/noise", "/project1/out_sop") in connect_pairs
    assert ("/project1/render", "/project1/out1") in connect_pairs
    assert ("/project1/out_sop", "/project1/render") not in connect_pairs


@pytest.mark.asyncio
async def test_open_prompt_atlas_synthesizes_chop_export_bound_sop_render_preview():
    cards = [
        _atlas_card(
            "lfoCHOP",
            "CHOP",
            "Oscillator CHOP source for repeating control signals and modulation.",
            ["oscillator", "control", "source"],
            params=["frequency", "amp", "channelname"],
        ),
        _atlas_card(
            "mathCHOP",
            "CHOP",
            "Scales and remaps CHOP channels for terrain displacement ranges.",
            ["scale", "control", "range", "process"],
            params=["fromrange", "torange"],
        ),
        _atlas_card(
            "nullCHOP",
            "CHOP",
            "Stable CHOP output for exported modulation control channels.",
            ["stable", "output", "export"],
            params=["exportmethod", "autoexportroot", "exporttable"],
        ),
        _atlas_card(
            "gridSOP",
            "SOP",
            "SOP mesh source grid for a terrain surface.",
            ["sop", "mesh", "terrain", "source"],
            params=["rows", "cols"],
        ),
        _atlas_card(
            "noiseSOP",
            "SOP",
            "Noise SOP displaces the terrain surface with an amplitude parameter.",
            ["surface", "noise", "displacement", "process"],
            params=["amp"],
        ),
        _atlas_card(
            "nullSOP",
            "SOP",
            "Stable SOP output for downstream render references.",
            ["stable", "output", "sop"],
        ),
        _atlas_card(
            "geometryCOMP",
            "COMP",
            "Geometry COMP references a SOP output for TOP rendering.",
            ["geometry", "sop", "render"],
            params=["sop"],
        ),
        _atlas_card(
            "cameraCOMP",
            "COMP",
            "Camera COMP frames the render output.",
            ["camera", "render"],
        ),
        _atlas_card(
            "lightCOMP",
            "COMP",
            "Light COMP provides illumination for the rendered SOP surface.",
            ["light", "render"],
        ),
        _atlas_card(
            "renderTOP",
            "TOP",
            "Render TOP creates a visual texture output from geometry, camera, and lights.",
            ["top", "render", "texture", "visual"],
            params=["geometry", "camera", "lights"],
        ),
        _atlas_card(
            "nullTOP",
            "TOP",
            "Stable TOP output for the final visual texture.",
            ["stable", "output", "texture"],
        ),
    ]
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": ["lfoCHOP", "mathCHOP", "nullCHOP"],
                    "SOP": ["gridSOP", "noiseSOP", "nullSOP"],
                    "COMP": ["geometryCOMP", "cameraCOMP", "lightCOMP"],
                    "TOP": ["renderTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="LFO export binding drives terrain SOP displacement and renders a visual TOP preview",
        target_root="/project1",
        card_index=AtlasCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.concept_graph.profile == "generic"
    assert plan.candidate_graphs
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:chop_export_bound_sop_render_preview_card_chain"]
    assert {
        "atlas-synthesis:typed-role-graph",
        "atlas-synthesis:typed-role-path-search:v1:CHOP:control->process->output",
        "atlas-synthesis:typed-role-path-search:v1:SOP:source->process->output",
        "atlas-synthesis:role-graph:control->source->preview->output",
        "atlas-synthesis:multi-domain:chop-export-to-sop-render-top-preview",
        "atlas-synthesis:family:chop+sop+comp+top",
        "atlas-synthesis:chop-export-binding:path-parameter",
        "atlas-synthesis:binding:out_chop->noiseSOP.amp",
        "atlas-synthesis:sop-control-target:noiseSOP.amp",
    }.issubset(set(plan.grounding_evidence))
    assert {
        "lfoCHOP",
        "mathCHOP",
        "nullCHOP",
        "gridSOP",
        "noiseSOP",
        "nullSOP",
        "geometryCOMP",
        "cameraCOMP",
        "lightCOMP",
        "renderTOP",
        "nullTOP",
    } == set(candidate.required_ops)
    assert "export-flag-requires-review" in candidate.risk_flags

    assert _set_params_for(plan, "/project1/lfo") == {"channelname": "/project1/noise:amp"}
    assert _set_params_for(plan, "/project1/out_chop") == {"exportmethod": "Channel Name is Path:Parameter"}
    assert _set_params_for(plan, "/project1/geometry") == {"sop": "/project1/out_sop"}
    assert _set_params_for(plan, "/project1/render") == {
        "geometry": "/project1/geometry",
        "camera": "/project1/camera",
        "lights": "/project1/light",
    }

    noise_param_sets = [
        operation.args["params"]
        for operation in plan.patch_plan.operations
        if operation.kind == "set_params" and operation.target == "/project1/noise"
    ]
    assert noise_param_sets == []

    connect_pairs = [
        (op.args["from"], op.args["to"]) for op in plan.patch_plan.operations if op.kind == "connect"
    ]
    assert ("/project1/lfo", "/project1/math") in connect_pairs
    assert ("/project1/math", "/project1/out_chop") in connect_pairs
    assert ("/project1/grid", "/project1/noise") in connect_pairs
    assert ("/project1/noise", "/project1/out_sop") in connect_pairs
    assert ("/project1/render", "/project1/out1") in connect_pairs
    assert ("/project1/out_chop", "/project1/noise") not in connect_pairs


@pytest.mark.asyncio
async def test_open_prompt_atlas_searches_messy_chop_export_sop_binding_candidates():
    cards = [
        _atlas_card(
            "noiseCHOP",
            "CHOP",
            "Noise CHOP random modulation source distractor for control channels.",
            ["random", "control", "source"],
            params=["amp", "period", "channelname"],
        ),
        _atlas_card(
            "lfoCHOP",
            "CHOP",
            "LFO CHOP oscillator source for deliberate export binding modulation.",
            ["lfo", "oscillator", "control", "source"],
            params=["frequency", "amp", "channelname"],
        ),
        _atlas_card(
            "lagCHOP",
            "CHOP",
            "Lag CHOP smoothing detour for control channels.",
            ["smooth", "control", "process"],
            params=["lag1"],
        ),
        _atlas_card(
            "mathCHOP",
            "CHOP",
            "Math CHOP scales exported terrain displacement control ranges.",
            ["scale", "control", "range", "process"],
            params=["fromrange", "torange"],
        ),
        _atlas_card(
            "nullCHOP",
            "CHOP",
            "Stable CHOP output for path-parameter export binding.",
            ["stable", "output", "export"],
            params=["exportmethod", "autoexportroot"],
        ),
        _atlas_card(
            "gridSOP",
            "SOP",
            "SOP mesh source grid for a terrain surface.",
            ["sop", "mesh", "terrain", "source"],
            params=["rows", "cols"],
        ),
        _atlas_card(
            "transformSOP",
            "SOP",
            "Transform SOP layout distractor with translate parameters for camera framing.",
            ["layout", "camera", "transform", "process"],
            params=["tx", "ty", "tz"],
        ),
        _atlas_card(
            "noiseSOP",
            "SOP",
            "Noise SOP adds terrain displacement amplitude before rendering.",
            ["terrain", "noise", "displacement", "process"],
            params=["amp", "height"],
        ),
        _atlas_card(
            "nullSOP",
            "SOP",
            "Stable SOP output for downstream render references.",
            ["stable", "output", "sop"],
        ),
        _atlas_card(
            "geometryCOMP",
            "COMP",
            "Geometry COMP references a SOP output for TOP rendering.",
            ["geometry", "sop", "render"],
            params=["sop"],
        ),
        _atlas_card(
            "cameraCOMP",
            "COMP",
            "Camera COMP frames the render output.",
            ["camera", "render"],
        ),
        _atlas_card(
            "lightCOMP",
            "COMP",
            "Light COMP provides illumination for the rendered SOP surface.",
            ["light", "render"],
        ),
        _atlas_card(
            "renderTOP",
            "TOP",
            "Render TOP creates a visual texture output from geometry, camera, and lights.",
            ["top", "render", "texture", "visual"],
            params=["geometry", "camera", "lights"],
        ),
        _atlas_card(
            "nullTOP",
            "TOP",
            "Stable TOP output for the final visual texture.",
            ["stable", "output", "texture"],
        ),
    ]
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": ["noiseCHOP", "lfoCHOP", "lagCHOP", "mathCHOP", "nullCHOP"],
                    "SOP": ["gridSOP", "transformSOP", "noiseSOP", "nullSOP"],
                    "COMP": ["geometryCOMP", "cameraCOMP", "lightCOMP"],
                    "TOP": ["renderTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent=(
            "LFO export binding drives terrain noise SOP amplitude and renders a "
            "visual TOP preview while random noise and transform layout cards are present"
        ),
        target_root="/project1",
        card_index=AtlasCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.candidate_graphs
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:chop_export_bound_sop_render_preview_card_chain"]
    assert candidate.required_ops == [
        "lfoCHOP",
        "mathCHOP",
        "nullCHOP",
        "gridSOP",
        "noiseSOP",
        "nullSOP",
        "geometryCOMP",
        "cameraCOMP",
        "lightCOMP",
        "renderTOP",
        "nullTOP",
    ]

    evidence = set(plan.grounding_evidence)
    assert "atlas-synthesis:typed-role-graph-search:v1" in evidence
    assert "atlas-synthesis:typed-role-path-search:v1:CHOP:control->process->output" in evidence
    assert "atlas-synthesis:typed-role-path-search:v1:SOP:source->process->output" in evidence
    assert "atlas-synthesis:role-graph-search:CHOP:control->process->output" in evidence
    assert "atlas-synthesis:role-graph-selected:CHOP:1:lfoCHOP>mathCHOP>nullCHOP" in evidence
    assert "atlas-synthesis:control-branch-exportable:true" in evidence
    assert any(
        marker.startswith("atlas-synthesis:role-graph-candidate:CHOP:")
        and ":alternative:noiseCHOP>mathCHOP>nullCHOP:" in marker
        for marker in evidence
    )
    assert "atlas-synthesis:role-node:CHOP:control:lfoCHOP" in evidence
    assert "atlas-synthesis:role-node:CHOP:output:nullCHOP" in evidence
    assert "atlas-synthesis:sop-control-target-selected:noiseSOP.amp" in evidence
    assert "atlas-synthesis:sop-control-target-candidate-count:2" in evidence
    assert any(
        marker.startswith("atlas-synthesis:sop-control-target-candidate:")
        and ":alternative:noiseSOP.height:" in marker
        for marker in evidence
    )

    assert _set_params_for(plan, "/project1/lfo") == {"channelname": "/project1/noise:amp"}
    assert _set_params_for(plan, "/project1/out_chop") == {"exportmethod": "Channel Name is Path:Parameter"}
    assert _set_params_for(plan, "/project1/geometry") == {"sop": "/project1/out_sop"}
    noise_param_sets = [
        operation.args["params"]
        for operation in plan.patch_plan.operations
        if operation.kind == "set_params" and operation.target == "/project1/noise"
    ]
    assert noise_param_sets == []


@pytest.mark.asyncio
async def test_open_prompt_atlas_synthesizes_chop_export_path_parameter_binding():
    cards = [
        _atlas_card(
            "lfoCHOP",
            "CHOP",
            "Oscillator CHOP source for repeating control signals and modulation.",
            ["oscillator", "control", "source"],
            params=["frequency", "amp", "channelname"],
        ),
        _atlas_card(
            "mathCHOP",
            "CHOP",
            "Scales and remaps CHOP channels for brightness control ranges.",
            ["scale", "control", "range", "process"],
            params=["fromrange", "torange"],
        ),
        _atlas_card(
            "nullCHOP",
            "CHOP",
            "Stable CHOP output for exported modulation control channels.",
            ["stable", "output", "export"],
            params=["exportmethod", "autoexportroot", "exporttable"],
        ),
        _atlas_card(
            "noiseTOP",
            "TOP",
            "Procedural texture source for a brightness wash visual.",
            ["procedural", "texture", "source"],
            params=["period", "harmonics"],
        ),
        _atlas_card(
            "levelTOP",
            "TOP",
            "Brightness and level adjustment stage for a procedural texture.",
            ["brightness", "level", "visual", "process"],
            params=["brightness1", "opacity"],
        ),
        _atlas_card(
            "nullTOP",
            "TOP",
            "Stable TOP output for the final controlled texture.",
            ["stable", "output", "texture"],
        ),
    ]
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": ["lfoCHOP", "mathCHOP", "nullCHOP"],
                    "TOP": ["noiseTOP", "levelTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="CHOP export binding overrides level brightness over a procedural texture output",
        target_root="/project1",
        card_index=AtlasCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.concept_graph.profile == "generic"
    assert plan.candidate_graphs
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:chop_export_bound_top_card_chain"]
    assert {
        "atlas-synthesis:chop-export-binding:path-parameter",
        "atlas-synthesis:binding-method:Channel Name is Path:Parameter",
        "atlas-synthesis:binding:out_chop->levelTOP.brightness1",
        "atlas-synthesis:channelname-source:lfoCHOP",
        "atlas-synthesis:exportmethod-output:nullCHOP",
        "atlas-synthesis:typed-role-path-search:v1:CHOP:control->process->output",
        "atlas-synthesis:typed-role-path-search:v1:TOP:source->process->output",
        "atlas-synthesis:role-graph-search:TOP:source->process->output",
        "atlas-synthesis:role-graph-selected:TOP:1:noiseTOP>levelTOP>nullTOP",
    }.issubset(set(plan.grounding_evidence))
    assert candidate.validation_needs == [
        "output_node_present",
        "control_output",
        "chop_export_method_readback",
        "export_flag_review",
        "top_output_present",
        "cheap_visual_metrics",
    ]
    assert "export-flag-requires-review" in candidate.risk_flags

    lfo_params = _set_params_for(plan, "/project1/lfo")
    out_chop_params = _set_params_for(plan, "/project1/out_chop")
    assert lfo_params == {"channelname": "/project1/level:brightness1"}
    assert out_chop_params == {"exportmethod": "Channel Name is Path:Parameter"}

    level_param_sets = [
        operation.args["params"]
        for operation in plan.patch_plan.operations
        if operation.kind == "set_params" and operation.target == "/project1/level"
    ]
    assert level_param_sets == []

    connect_pairs = [
        (op.args["from"], op.args["to"]) for op in plan.patch_plan.operations if op.kind == "connect"
    ]
    assert ("/project1/lfo", "/project1/math") in connect_pairs
    assert ("/project1/math", "/project1/out_chop") in connect_pairs
    assert ("/project1/noise", "/project1/level") in connect_pairs
    assert ("/project1/level", "/project1/out1") in connect_pairs
    assert ("/project1/out_chop", "/project1/level") not in connect_pairs


@pytest.mark.asyncio
async def test_open_prompt_atlas_searches_messy_chop_controlled_top_candidates():
    cards = [
        _atlas_card(
            "waveCHOP",
            "CHOP",
            "Wave CHOP oscillator source distractor for generic control signals.",
            ["wave", "oscillator", "control", "source"],
            params=["wavetype", "period", "amp", "channelname"],
        ),
        _atlas_card(
            "lfoCHOP",
            "CHOP",
            "LFO CHOP source for deliberate brightness modulation control.",
            ["lfo", "oscillator", "control", "source"],
            params=["frequency", "amp", "channelname"],
        ),
        _atlas_card(
            "lagCHOP",
            "CHOP",
            "Lag CHOP smoothing detour for control channels.",
            ["smooth", "control", "process"],
            params=["lag1"],
        ),
        _atlas_card(
            "mathCHOP",
            "CHOP",
            "Math CHOP scales LFO brightness control ranges.",
            ["scale", "brightness", "control", "process"],
            params=["fromrange", "torange"],
        ),
        _atlas_card(
            "nullCHOP",
            "CHOP",
            "Stable CHOP output for modulation control channels.",
            ["stable", "output", "control"],
        ),
        _atlas_card(
            "noiseTOP",
            "TOP",
            "Procedural noise texture source for the brightness wash visual.",
            ["procedural", "noise", "texture", "source"],
            params=["period", "harmonics"],
        ),
        _atlas_card(
            "transformTOP",
            "TOP",
            "Transform TOP layout distractor for texture placement.",
            ["layout", "transform", "process"],
            params=["tx", "ty"],
        ),
        _atlas_card(
            "levelTOP",
            "TOP",
            "Level TOP brightness stage for the procedural texture.",
            ["brightness", "level", "visual", "process"],
            params=["brightness1", "opacity"],
        ),
        _atlas_card(
            "nullTOP",
            "TOP",
            "Stable TOP output for the final controlled texture.",
            ["stable", "output", "texture"],
        ),
    ]
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": ["waveCHOP", "lfoCHOP", "lagCHOP", "mathCHOP", "nullCHOP"],
                    "TOP": ["noiseTOP", "transformTOP", "levelTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent=(
            "LFO controlled brightness wash over a procedural noise texture output "
            "while wave and transform cards are present"
        ),
        target_root="/project1",
        card_index=AtlasCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.candidate_graphs
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:chop_controlled_top_card_chain"]
    assert "operator-intent:chop_controlled_texture" in candidate.grounding_evidence
    assert "atlas_intent:chop_controlled_texture" in candidate.explanation
    assert candidate.required_ops == [
        "lfoCHOP",
        "mathCHOP",
        "nullCHOP",
        "noiseTOP",
        "levelTOP",
        "nullTOP",
    ]

    evidence = set(plan.grounding_evidence)
    assert "atlas-synthesis:typed-role-graph-search:v1" in evidence
    assert "atlas-synthesis:typed-role-path-search:v1:CHOP:control->process->output" in evidence
    assert "atlas-synthesis:typed-role-path-search:v1:TOP:source->process->output" in evidence
    assert "atlas-synthesis:role-graph-search:CHOP:control->process->output" in evidence
    assert "atlas-synthesis:role-graph-selected:CHOP:1:lfoCHOP>mathCHOP>nullCHOP" in evidence
    assert "atlas-synthesis:role-node:CHOP:control:lfoCHOP" in evidence
    assert "atlas-synthesis:role-node:CHOP:output:nullCHOP" in evidence
    assert any(
        marker.startswith("atlas-synthesis:role-graph-candidate:CHOP:")
        and ":alternative:waveCHOP>mathCHOP>nullCHOP:" in marker
        for marker in evidence
    )
    assert "atlas-synthesis:role-graph-search:TOP:source->process->output" in evidence
    assert "atlas-synthesis:role-graph-selected:TOP:1:noiseTOP>levelTOP>nullTOP" in evidence
    assert "atlas-synthesis:role-node:TOP:source:noiseTOP" in evidence
    assert "atlas-synthesis:role-node:TOP:process:levelTOP" in evidence
    assert any(
        marker.startswith("atlas-synthesis:role-graph-candidate:TOP:")
        and ":alternative:noiseTOP>transformTOP>nullTOP:" in marker
        for marker in evidence
    )
    assert "atlas-synthesis:binding:out_chop->levelTOP.brightness1" in evidence

    level_params = _set_params_for(plan, "/project1/level")
    assert level_params == {"brightness1": {"expr": "op('/project1/out_chop')[0]"}}
    connect_pairs = [
        (op.args["from"], op.args["to"]) for op in plan.patch_plan.operations if op.kind == "connect"
    ]
    assert ("/project1/lfo", "/project1/math") in connect_pairs
    assert ("/project1/math", "/project1/out_chop") in connect_pairs
    assert ("/project1/noise", "/project1/level") in connect_pairs
    assert ("/project1/level", "/project1/out1") in connect_pairs
    assert ("/project1/out_chop", "/project1/level") not in connect_pairs


@pytest.mark.asyncio
async def test_open_prompt_atlas_ignores_midi_docs_distractor_for_chop_controlled_top():
    cards = [
        _atlas_card(
            "midiinCHOP",
            "CHOP",
            "MIDI In CHOP receives controller note and CC channels; distractor device source docs.",
            ["midi", "controller", "source"],
            params=["device", "source"],
        ),
        _atlas_card(
            "lfoCHOP",
            "CHOP",
            "LFO CHOP oscillator source for repeating brightness modulation.",
            ["lfo", "oscillator", "control", "source"],
            params=["frequency", "amp"],
        ),
        _atlas_card(
            "mathCHOP",
            "CHOP",
            "Math CHOP scales oscillator channels for brightness control ranges.",
            ["scale", "control", "process"],
            params=["fromrange", "torange"],
        ),
        _atlas_card(
            "nullCHOP",
            "CHOP",
            "Stable CHOP output for modulation control channels.",
            ["stable", "output", "control"],
        ),
        _atlas_card(
            "noiseTOP",
            "TOP",
            "Procedural noise texture source for brightness wash visual.",
            ["procedural", "texture", "source"],
            params=["period"],
        ),
        _atlas_card(
            "levelTOP",
            "TOP",
            "Level TOP brightness stage for procedural texture.",
            ["brightness", "level", "process"],
            params=["brightness1"],
        ),
        _atlas_card(
            "nullTOP",
            "TOP",
            "Stable TOP output for final texture.",
            ["stable", "output", "texture"],
        ),
    ]
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": ["midiinCHOP", "lfoCHOP", "mathCHOP", "nullCHOP"],
                    "TOP": ["noiseTOP", "levelTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent=(
            "oscillator controlled brightness wash over procedural texture with final TOP output "
            "while MIDI In CHOP docs are present"
        ),
        target_root="/project1",
        card_index=AtlasCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.concept_graph.profile == "generic"
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:chop_controlled_top_card_chain"]
    assert candidate.required_ops == [
        "lfoCHOP",
        "mathCHOP",
        "nullCHOP",
        "noiseTOP",
        "levelTOP",
        "nullTOP",
    ]
    assert "midiinCHOP" not in candidate.required_ops
    assert "operator-intent:chop_controlled_texture" in plan.grounding_evidence
    assert "operator-intent:midi_chop_control_bridge" not in plan.grounding_evidence


@pytest.mark.asyncio
async def test_open_prompt_atlas_blocks_midi_control_bridge_without_declared_device():
    cards = [
        _atlas_card(
            "waveCHOP",
            "CHOP",
            "Wave CHOP generic oscillator source distractor for control signals.",
            ["wave", "oscillator", "control", "source"],
            params=["wavetype", "period", "amp"],
        ),
        _atlas_card(
            "noiseCHOP",
            "CHOP",
            "Noise CHOP random modulation source distractor for control signals.",
            ["random", "control", "source"],
            params=["type", "period", "amp"],
        ),
        _atlas_card(
            "midiinCHOP",
            "CHOP",
            "MIDI In CHOP receives MIDI CC controller note and performance channel data.",
            ["midi", "controller", "cc", "performance", "source"],
            params=["source", "device", "simplified", "controlname"],
        ),
        _atlas_card(
            "mathCHOP",
            "CHOP",
            "Math CHOP normalizes and scales incoming MIDI control channels.",
            ["normalize", "scale", "control", "process"],
            params=["fromrange", "torange"],
        ),
        _atlas_card(
            "nullCHOP",
            "CHOP",
            "Stable CHOP output for normalized MIDI controls.",
            ["stable", "output", "control"],
        ),
    ]
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": ["waveCHOP", "noiseCHOP", "midiinCHOP", "mathCHOP", "nullCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="CC performance controller should become a normalized CHOP output while oscillator cards are present",
        target_root="/project1",
        card_index=AtlasCardIndex(cards),
    )

    assert plan.blocked_questions
    assert "missing_device_source:midi_device" in plan.missing_facts
    assert "device-source-required" in plan.risk_flags
    assert plan.patch_plan.operations == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:midi_chop_control_bridge"]
    assert candidate.required_ops == ["midiinCHOP", "mathCHOP", "nullCHOP"]
    assert "waveCHOP" not in candidate.required_ops
    assert "noiseCHOP" not in candidate.required_ops
    assert "operator-intent:midi_chop_control_bridge" in plan.grounding_evidence


@pytest.mark.asyncio
async def test_open_prompt_atlas_builds_declared_midi_control_bridge_over_distractors():
    cards = [
        _atlas_card(
            "waveCHOP",
            "CHOP",
            "Wave CHOP generic oscillator source distractor for control signals.",
            ["wave", "oscillator", "control", "source"],
            params=["wavetype", "period", "amp"],
        ),
        _atlas_card(
            "noiseCHOP",
            "CHOP",
            "Noise CHOP random modulation source distractor for control signals.",
            ["random", "control", "source"],
            params=["type", "period", "amp"],
        ),
        _atlas_card(
            "midiinCHOP",
            "CHOP",
            "MIDI In CHOP receives MIDI CC controller note and performance channel data.",
            ["midi", "controller", "cc", "performance", "source"],
            params=["source", "device", "simplified", "controlname"],
        ),
        _atlas_card(
            "mathCHOP",
            "CHOP",
            "Math CHOP normalizes and scales incoming MIDI control channels.",
            ["normalize", "scale", "control", "process"],
            params=["fromrange", "torange"],
        ),
        _atlas_card(
            "nullCHOP",
            "CHOP",
            "Stable CHOP output for normalized MIDI controls.",
            ["stable", "output", "control"],
        ),
    ]
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "CHOP": ["waveCHOP", "noiseCHOP", "midiinCHOP", "mathCHOP", "nullCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="CC performance controller should become a normalized CHOP output while oscillator cards are present",
        target_root="/project1",
        constraints={"device_sources": ["midi_device"]},
        card_index=AtlasCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.concept_graph.profile == "generic"
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:midi_chop_control_bridge"]
    assert candidate.required_ops == ["midiinCHOP", "mathCHOP", "nullCHOP"]
    assert "waveCHOP" not in candidate.required_ops
    assert "noiseCHOP" not in candidate.required_ops
    assert {
        "operator-intent:midi_chop_control_bridge",
        "docs:midiinCHOP",
        "docs:mathCHOP",
        "docs:nullCHOP",
    }.issubset(set(plan.grounding_evidence))

    create_ops = [
        operation.args["op_type"]
        for operation in plan.patch_plan.operations
        if operation.kind == "create_node"
    ]
    assert create_ops == ["midiinCHOP", "mathCHOP", "nullCHOP"]
    connect_pairs = [
        (operation.args["from"], operation.args["to"])
        for operation in plan.patch_plan.operations
        if operation.kind == "connect"
    ]
    assert ("/project1/midiin", "/project1/math") in connect_pairs
    assert ("/project1/math", "/project1/out_chop") in connect_pairs


@pytest.mark.asyncio
async def test_open_prompt_atlas_dat_pipeline_prefers_requested_protocol_source_over_distractors():
    cards = [
        _atlas_card(
            "serialDAT",
            "DAT",
            "Serial device message source distractor that appends COM port sensor rows to a DAT table.",
            ["serial", "sensor", "message", "source"],
            params=["port", "baudrate", "active", "clamp", "maxlines"],
        ),
        _atlas_card(
            "udpinDAT",
            "DAT",
            "UDP packet source distractor that appends received network packets to a DAT table.",
            ["udp", "packet", "network", "source"],
            params=["protocol", "port", "active", "clamp", "maxlines"],
        ),
        _atlas_card(
            "mqttclientDAT",
            "DAT",
            "MQTT Client DAT subscribes to broker topic payloads and appends messages to a DAT table.",
            ["mqtt", "broker", "topic", "payload", "source"],
            params=["netaddress", "keepalive", "active", "clamp", "maxlines"],
        ),
        _atlas_card(
            "tableDAT",
            "DAT",
            "Table DAT processing stage normalizes MQTT payload rows for diagnostics.",
            ["table", "normalize", "process", "rows"],
            params=["rows", "cols"],
        ),
        _atlas_card(
            "nullDAT",
            "DAT",
            "Stable DAT table output for normalized MQTT message consumers.",
            ["stable", "table", "output"],
        ),
    ]
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["serialDAT", "udpinDAT", "mqttclientDAT", "tableDAT", "nullDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent=(
            "subscribe to mqtt broker topic payload rows and normalize them into a stable "
            "table output while serial and udp source cards are present"
        ),
        target_root="/project1",
        constraints={"device_sources": ["mqtt_broker"]},
        card_index=AtlasCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:typed_role_graph_dat_pipeline_card_chain"]
    assert candidate.required_ops == ["mqttclientDAT", "tableDAT", "nullDAT"]
    assert "serialDAT" not in candidate.required_ops
    assert "udpinDAT" not in candidate.required_ops
    assert "atlas-synthesis:source:mqttclientDAT" in plan.grounding_evidence


@pytest.mark.asyncio
async def test_open_prompt_atlas_blocks_web_client_request_without_declared_endpoint():
    cards = [
        _atlas_card(
            "webDAT",
            "DAT",
            "Deprecated Web DAT HTTP request source; use Web Client DAT for modern requests.",
            ["deprecated", "web", "http", "request"],
            params=["url"],
        ),
        _atlas_card(
            "webclientDAT",
            "DAT",
            "Web Client DAT sends HTTP requests and outputs API responses to a DAT.",
            ["web", "http", "api", "request", "response", "source"],
            params=["url", "reqmethod", "request", "verifycert", "clamp"],
        ),
        _atlas_card(
            "nullDAT",
            "DAT",
            "Stable DAT output for HTTP response rows.",
            ["stable", "output", "dat"],
        ),
    ]
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["webclientDAT", "nullDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="fetch an HTTP API response into a stable DAT output while deprecated Web DAT docs are present",
        target_root="/project1",
        card_index=AtlasCardIndex(cards),
    )

    assert plan.blocked_questions
    assert "missing_device_source:http_endpoint" in plan.missing_facts
    assert "device-source-required" in plan.risk_flags
    assert plan.patch_plan.operations == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:web_client_dat_request_output"]
    assert candidate.required_ops == ["webclientDAT", "nullDAT"]
    assert "webDAT" not in candidate.required_ops


@pytest.mark.asyncio
async def test_open_prompt_atlas_builds_web_client_request_output_over_deprecated_web_dat_card():
    cards = [
        _atlas_card(
            "webDAT",
            "DAT",
            "Deprecated Web DAT HTTP request source; use Web Client DAT for modern requests.",
            ["deprecated", "web", "http", "request"],
            params=["url"],
        ),
        _atlas_card(
            "webclientDAT",
            "DAT",
            "Web Client DAT sends HTTP requests and outputs API responses to a DAT.",
            ["web", "http", "api", "request", "response", "source"],
            params=["url", "reqmethod", "request", "verifycert", "clamp"],
        ),
        _atlas_card(
            "nullDAT",
            "DAT",
            "Stable DAT output for HTTP response rows.",
            ["stable", "output", "dat"],
        ),
    ]
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["webclientDAT", "nullDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="fetch an HTTP API response into a stable DAT output while deprecated Web DAT docs are present",
        target_root="/project1",
        constraints={"device_sources": ["http_endpoint"]},
        card_index=AtlasCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.concept_graph.profile == "generic"
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:web_client_dat_request_output"]
    assert candidate.required_ops == ["webclientDAT", "nullDAT"]
    assert "webDAT" not in candidate.required_ops
    assert {
        "operator-intent:web_client_dat_request_output",
        "docs:webclientDAT",
        "docs:nullDAT",
    }.issubset(set(plan.grounding_evidence))

    create_ops = [
        operation.args["op_type"]
        for operation in plan.patch_plan.operations
        if operation.kind == "create_node"
    ]
    assert create_ops == ["webclientDAT", "nullDAT"]
    connect_pairs = [
        (operation.args["from"], operation.args["to"])
        for operation in plan.patch_plan.operations
        if operation.kind == "connect"
    ]
    assert ("/project1/webclient", "/project1/out_dat") in connect_pairs


@pytest.mark.asyncio
async def test_open_prompt_atlas_blocks_web_server_endpoint_without_declared_listener():
    cards = [
        _atlas_card(
            "webclientDAT",
            "DAT",
            "Web Client DAT sends HTTP requests and outputs API responses to a DAT.",
            ["web", "http", "api", "request", "response", "client"],
            params=["url", "request"],
        ),
        _atlas_card(
            "webserverDAT",
            "DAT",
            "Web Server DAT hosts HTTP and WebSocket endpoints inside TouchDesigner with callbacks.",
            ["web", "http", "websocket", "server", "endpoint", "callbacks"],
            params=["active", "restart", "port", "callbacks"],
        ),
        _atlas_card(
            "nullDAT",
            "DAT",
            "Stable DAT output for server callback rows.",
            ["stable", "output", "dat"],
        ),
    ]
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["webclientDAT", "webserverDAT", "nullDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="host an HTTP server endpoint with callback DAT rows and stable output",
        target_root="/project1",
        card_index=AtlasCardIndex(cards),
    )

    assert plan.blocked_questions
    assert "missing_device_source:network_listener" in plan.missing_facts
    assert "device-source-required" in plan.risk_flags
    assert plan.patch_plan.operations == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:web_server_dat_endpoint"]
    assert candidate.required_ops == ["webserverDAT", "nullDAT"]
    assert "webclientDAT" not in candidate.required_ops


@pytest.mark.asyncio
async def test_open_prompt_atlas_builds_web_server_endpoint_over_web_client_distractor():
    cards = [
        _atlas_card(
            "webclientDAT",
            "DAT",
            "Web Client DAT sends HTTP requests and outputs API responses to a DAT.",
            ["web", "http", "api", "request", "response", "client"],
            params=["url", "request"],
        ),
        _atlas_card(
            "webserverDAT",
            "DAT",
            "Web Server DAT hosts HTTP and WebSocket endpoints inside TouchDesigner with callbacks.",
            ["web", "http", "websocket", "server", "endpoint", "callbacks"],
            params=["active", "restart", "port", "callbacks"],
        ),
        _atlas_card(
            "nullDAT",
            "DAT",
            "Stable DAT output for server callback rows.",
            ["stable", "output", "dat"],
        ),
    ]
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["webclientDAT", "webserverDAT", "nullDAT"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="host an HTTP server endpoint with callback DAT rows and stable output",
        target_root="/project1",
        constraints={"device_sources": ["network_listener"]},
        card_index=AtlasCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.concept_graph.profile == "generic"
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:web_server_dat_endpoint"]
    assert candidate.required_ops == ["webserverDAT", "nullDAT"]
    assert "webclientDAT" not in candidate.required_ops
    assert {
        "operator-intent:web_server_dat_endpoint",
        "docs:webserverDAT",
        "docs:nullDAT",
    }.issubset(set(plan.grounding_evidence))

    create_ops = [
        operation.args["op_type"]
        for operation in plan.patch_plan.operations
        if operation.kind == "create_node"
    ]
    assert create_ops == ["webserverDAT", "nullDAT"]
    connect_pairs = [
        (operation.args["from"], operation.args["to"])
        for operation in plan.patch_plan.operations
        if operation.kind == "connect"
    ]
    assert ("/project1/webserver", "/project1/out_dat") in connect_pairs


@pytest.mark.asyncio
async def test_open_prompt_atlas_typed_bridge_search_explains_selected_path_and_alternatives():
    cards = [
        _atlas_card(
            "gridSOP",
            "SOP",
            "SOP mesh source grid for geometry sampling.",
            ["sop", "mesh", "source"],
            params=["rows", "cols"],
        ),
        _atlas_card(
            "noiseSOP",
            "SOP",
            "Displaces SOP surface before conversion.",
            ["surface", "process", "displacement"],
            params=["amp"],
        ),
        _atlas_card(
            "nullSOP",
            "SOP",
            "Stable SOP output for downstream bridge references.",
            ["stable", "output", "sop"],
        ),
        _atlas_card(
            "soptoCHOP",
            "CHOP",
            "SOP to CHOP bridge samples stable SOP geometry into control channels.",
            ["bridge", "sop", "chop", "channels"],
            params=["sop"],
        ),
        _atlas_card(
            "mathCHOP",
            "CHOP",
            "Range shaping stage for sampled geometry control channels.",
            ["range", "channel", "process"],
            params=["range1", "range2"],
        ),
        _atlas_card(
            "nullCHOP",
            "CHOP",
            "Stable CHOP output for sampled geometry control channels.",
            ["stable", "output", "channels"],
        ),
        _atlas_card(
            "soptoPOP",
            "POP",
            "SOP to POP bridge converts stable SOP geometry into a point field.",
            ["bridge", "sop", "pop", "point"],
            params=["sop"],
        ),
        _atlas_card(
            "noisePOP",
            "POP",
            "Adds point displacement to converted POP fields.",
            ["point", "field", "process"],
            params=["amplitude"],
        ),
        _atlas_card(
            "nullPOP",
            "POP",
            "Stable POP output before TOP preview.",
            ["stable", "output", "pop"],
        ),
        _atlas_card(
            "poptoTOP",
            "TOP",
            "POP to TOP bridge previews stable POP point fields as texture pixels.",
            ["bridge", "pop", "top", "texture"],
            params=["pop"],
        ),
        _atlas_card(
            "levelTOP",
            "TOP",
            "Texture shaping stage for geometry preview pixels.",
            ["texture", "preview", "process"],
            params=["brightness1", "opacity"],
        ),
        _atlas_card(
            "nullTOP",
            "TOP",
            "Stable TOP output for geometry preview texture.",
            ["stable", "output", "top"],
        ),
    ]
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "SOP": ["gridSOP", "noiseSOP", "nullSOP"],
                    "CHOP": ["soptoCHOP", "mathCHOP", "nullCHOP"],
                    "POP": ["soptoPOP", "noisePOP", "nullPOP"],
                    "TOP": ["poptoTOP", "levelTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="SOP mesh surface becomes sampled control channels with stable CHOP output",
        target_root="/project1",
        card_index=AtlasCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert len(plan.candidate_graphs) == 3
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:typed_bridge_graph_sop_to_chop_card_chain"]
    assert candidate.required_ops == [
        "gridSOP",
        "noiseSOP",
        "nullSOP",
        "soptoCHOP",
        "mathCHOP",
        "nullCHOP",
    ]
    evidence = set(plan.grounding_evidence)
    assert "atlas-synthesis:typed-bridge-selected:sop_to_chop:soptoCHOP" in evidence
    assert "atlas-synthesis:typed-bridge-alternative-count:2" in evidence
    assert any(
        marker.startswith("atlas-synthesis:typed-bridge-candidate:") and ":sop_to_pop:soptoPOP:" in marker
        for marker in evidence
    )
    assert any(
        marker.startswith("atlas-synthesis:typed-bridge-candidate:")
        and ":sop_to_pop_to_top:soptoPOP+poptoTOP:" in marker
        for marker in evidence
    )
    assert "candidate_paths:3" in candidate.explanation
    assert "selected_path:sop_to_chop" in candidate.explanation
    assert plan.candidate_graphs[1].pattern_ids == [
        "atlas:synthesized:typed_bridge_graph_sop_to_pop_to_top_card_chain"
    ]
    assert "alternative_path:sop_to_pop_to_top" in plan.candidate_graphs[1].explanation
    assert (
        "atlas-synthesis:typed-bridge-alternative:2:sop_to_pop_to_top:soptoPOP+poptoTOP"
        in plan.candidate_graphs[1].grounding_evidence
    )
    assert {
        "gridSOP",
        "noiseSOP",
        "nullSOP",
        "soptoPOP",
        "nullPOP",
        "poptoTOP",
        "nullTOP",
    } == set(plan.candidate_graphs[1].required_ops)


@pytest.mark.asyncio
async def test_open_prompt_atlas_typed_bridge_uses_requested_protocol_source_before_table_stage():
    cards = [
        _atlas_card(
            "serialDAT",
            "DAT",
            "Serial device source distractor that appends COM port sensor rows to a DAT table.",
            ["serial", "sensor", "source"],
            params=["port", "baudrate"],
        ),
        _atlas_card(
            "udpinDAT",
            "DAT",
            "UDP packet source distractor that appends network packets to a DAT table.",
            ["udp", "packet", "source"],
            params=["port", "protocol"],
        ),
        _atlas_card(
            "mqttclientDAT",
            "DAT",
            "MQTT Client DAT subscribes to broker topic payload rows.",
            ["mqtt", "broker", "topic", "payload", "source"],
            params=["netaddress", "keepalive"],
        ),
        _atlas_card(
            "tableDAT",
            "DAT",
            "Table DAT processing stage that normalizes MQTT payload rows.",
            ["table", "normalize", "process", "rows"],
            params=["rows", "cols"],
        ),
        _atlas_card(
            "dattoCHOP",
            "CHOP",
            "DAT to CHOP bridge converts selected payload rows into control channels.",
            ["bridge", "dat", "chop", "channels"],
            params=["dat"],
        ),
        _atlas_card(
            "mathCHOP",
            "CHOP",
            "Math CHOP range shaping stage for normalized MQTT payload channels.",
            ["range", "channel", "process"],
            params=["range1", "range2"],
        ),
        _atlas_card(
            "nullCHOP",
            "CHOP",
            "Stable CHOP output for normalized MQTT payload channels.",
            ["stable", "output", "channels"],
        ),
        _atlas_card(
            "choptoTOP",
            "TOP",
            "CHOP to TOP bridge converts normalized MQTT channels into texture pixels.",
            ["bridge", "chop", "top", "texture"],
            params=["chop"],
        ),
        _atlas_card(
            "levelTOP",
            "TOP",
            "Texture shaping stage after channel conversion.",
            ["texture", "process", "level"],
            params=["brightness1", "opacity"],
        ),
        _atlas_card(
            "nullTOP",
            "TOP",
            "Stable TOP output for the converted MQTT payload texture.",
            ["stable", "output", "texture"],
        ),
    ]
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "DAT": ["serialDAT", "udpinDAT", "mqttclientDAT", "tableDAT"],
                    "CHOP": ["dattoCHOP", "mathCHOP", "nullCHOP"],
                    "TOP": ["choptoTOP", "levelTOP", "nullTOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent=(
            "mqtt broker payload rows become normalized channels and then a texture output "
            "while serial and udp source cards are present"
        ),
        target_root="/project1",
        card_index=AtlasCardIndex(cards),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    candidate = plan.candidate_graphs[0]
    assert candidate.pattern_ids == ["atlas:synthesized:typed_bridge_graph_dat_to_chop_to_top_card_chain"]
    assert candidate.required_ops == [
        "mqttclientDAT",
        "tableDAT",
        "dattoCHOP",
        "mathCHOP",
        "nullCHOP",
        "choptoTOP",
        "levelTOP",
        "nullTOP",
    ]
    assert "serialDAT" not in candidate.required_ops
    assert "udpinDAT" not in candidate.required_ops
    assert "atlas-synthesis:source:mqttclientDAT" in plan.grounding_evidence
    assert "atlas-synthesis:process:tableDAT" in plan.grounding_evidence


@pytest.mark.asyncio
async def test_compiler_path_builds_pop_particle_preview_candidate_graph():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "POP": ["circlePOP", "noisePOP", "mathmixPOP", "nullPOP"],
                    "TOP": ["rendersimpleTOP", "nullTOP"],
                    "DAT": ["textDAT", "errorDAT"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build a POP particle field preview with stable TOP output and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(POP_PREVIEW_OPS),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.compiled_task is not None
    assert plan.compiled_task.domains == ["TOP", "DAT", "POP"]
    assert plan.compiled_task.candidate_profiles == ["pop"]
    assert plan.concept_graph.profile == "concept_compiled"
    assert plan.candidate_graphs
    candidate = plan.candidate_graphs[0]
    assert candidate.profiles == ["pop"]
    assert {"pop_particle_field_preview", "debug_output_conventions"}.issubset(set(candidate.pattern_ids))
    assert {
        "circlePOP",
        "noisePOP",
        "mathmixPOP",
        "nullPOP",
        "rendersimpleTOP",
        "nullTOP",
        "textDAT",
    }.issubset(set(candidate.required_ops))
    assert "validate-finite-pop-bounds" in plan.risk_flags
    assert "validate-pop-render-preview" in plan.risk_flags
    assert set(candidate.required_ops).issubset(set(plan.patch_plan.required_ops))

    shell_path = "/project1/tdpilot_concept"
    create_names = [op.args["name"] for op in plan.patch_plan.operations if op.kind == "create_node"]
    assert "tdpilot_concept" in create_names
    assert "circle" in create_names
    assert "noise" in create_names
    assert "mathmix" in create_names
    assert "out_pop" in create_names
    assert "rendersimple" in create_names
    assert "out1" in create_names
    assert "debug_notes" in create_names
    assert plan.patch_plan.validation_plan.capture_frames == [f"{shell_path}/out1"]

    render_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target == f"{shell_path}/rendersimple"
    ]
    assert render_params and render_params[0]["pop"] == f"{shell_path}/out_pop"
    connect_pairs = [
        (op.args["from"], op.args["to"]) for op in plan.patch_plan.operations if op.kind == "connect"
    ]
    assert (f"{shell_path}/circle", f"{shell_path}/noise") in connect_pairs
    assert (f"{shell_path}/noise", f"{shell_path}/mathmix") in connect_pairs
    assert (f"{shell_path}/mathmix", f"{shell_path}/out_pop") in connect_pairs
    assert (f"{shell_path}/rendersimple", f"{shell_path}/out1") in connect_pairs
    assert (f"{shell_path}/out_pop", f"{shell_path}/rendersimple") not in connect_pairs


@pytest.mark.asyncio
async def test_compiler_path_builds_glsl_advanced_pop_topology_candidate_graph():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "POP": ["circlePOP", "glsladvancedPOP", "topologyPOP", "nullPOP"],
                    "TOP": ["rendersimpleTOP", "nullTOP"],
                    "DAT": ["textDAT", "errorDAT"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent=(
            "Build a GLSL POP shader that changes point counts and writes topology "
            "with a stable TOP preview and debug output"
        ),
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(GLSL_ADVANCED_POP_OPS),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.compiled_task is not None
    assert plan.compiled_task.domains == ["TOP", "DAT", "POP"]
    assert {"glsl", "pop"}.issubset(set(plan.compiled_task.candidate_profiles))
    assert "glsl_advanced_pop_topology" in plan.compiled_task.required_capabilities
    assert plan.concept_graph.profile == "concept_compiled"
    assert plan.candidate_graphs
    candidate = plan.candidate_graphs[0]
    assert candidate.profiles == ["glsl", "pop"]
    assert {"glsl_advanced_pop_topology_shader", "debug_output_conventions"}.issubset(
        set(candidate.pattern_ids)
    )
    assert {
        "circlePOP",
        "glsladvancedPOP",
        "topologyPOP",
        "textDAT",
        "nullPOP",
        "rendersimpleTOP",
        "nullTOP",
    }.issubset(set(candidate.required_ops))
    assert "glslPOP" not in candidate.required_ops
    assert "topology_capacity" in candidate.validation_needs
    assert "validate-glsl-compile-state" in plan.risk_flags
    assert set(candidate.required_ops).issubset(set(plan.patch_plan.required_ops))

    shell_path = "/project1/tdpilot_concept"
    create_names = [op.args["name"] for op in plan.patch_plan.operations if op.kind == "create_node"]
    assert "tdpilot_concept" in create_names
    assert "circle" in create_names
    assert "glsladvanced" in create_names
    assert "topology" in create_names
    assert "text" in create_names
    assert "out_pop" in create_names
    assert "rendersimple" in create_names
    assert "out1" in create_names
    assert "debug_notes" in create_names
    assert plan.patch_plan.validation_plan.capture_frames == [f"{shell_path}/out1"]

    shader_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target == f"{shell_path}/glsladvanced"
    ]
    assert shader_params and shader_params[0]["computedat"] == f"{shell_path}/text"
    render_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target == f"{shell_path}/rendersimple"
    ]
    assert render_params and render_params[0]["pop"] == f"{shell_path}/out_pop"
    generated_ops = [
        op
        for op in plan.patch_plan.operations
        if op.kind == "set_dat_content" and isinstance(op.args.get("generated_code"), dict)
    ]
    assert generated_ops
    shader_source_op = generated_ops[0]
    assert shader_source_op.target == f"{shell_path}/text"
    assert "TDIndex()" in shader_source_op.args["text"]
    assert "TDNumElements()" in shader_source_op.args["text"]
    assert shader_source_op.args["generated_code"]["target_op"] == f"{shell_path}/glsladvanced"
    assert shader_source_op.args["generated_code"]["target_param"] == "computedat"
    assert shader_source_op.args["generated_code"]["source_refs"] == [f"{shell_path}/text"]
    assert "glsl_pop_bounds_guard" in shader_source_op.args["generated_code"]["static_checks"]
    assert validate_patch_plan_generated_code(plan.patch_plan) == []

    connect_pairs = [
        (op.args["from"], op.args["to"]) for op in plan.patch_plan.operations if op.kind == "connect"
    ]
    assert (f"{shell_path}/circle", f"{shell_path}/glsladvanced") in connect_pairs
    assert (f"{shell_path}/glsladvanced", f"{shell_path}/topology") in connect_pairs
    assert (f"{shell_path}/topology", f"{shell_path}/out_pop") in connect_pairs
    assert (f"{shell_path}/rendersimple", f"{shell_path}/out1") in connect_pairs
    assert (f"{shell_path}/text", f"{shell_path}/glsladvanced") not in connect_pairs
    assert (f"{shell_path}/out_pop", f"{shell_path}/rendersimple") not in connect_pairs


@pytest.mark.asyncio
async def test_compiler_path_uses_glsl_advanced_pop_for_deprecated_glsl_create_prompt():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "POP": ["circlePOP", "glsladvancedPOP", "topologyPOP", "nullPOP"],
                    "TOP": ["rendersimpleTOP", "nullTOP"],
                    "DAT": ["textDAT", "errorDAT"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent=(
            "Build a GLSL Create POP topology shader that changes point counts "
            "with a stable TOP preview and debug output"
        ),
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(GLSL_ADVANCED_POP_OPS | {"glslcreatePOP"}),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.compiled_task is not None
    assert "deprecated-op:glslcreatePOP" in plan.compiled_task.risk_flags
    assert "glslcreatePOP" not in plan.concept_graph.operators
    assert "glslcreatePOP" not in plan.patch_plan.required_ops
    assert {"glsladvancedPOP", "topologyPOP"}.issubset(set(plan.patch_plan.required_ops))
    assert "substitution:glslcreatePOP->glsladvancedPOP+topologyPOP" in plan.grounding_evidence
    assert "substitution-rule:glslcreatePOP->glsladvancedPOP+topologyPOP:high" in plan.grounding_evidence


@pytest.mark.asyncio
async def test_compiler_path_blocks_topology_changing_glsl_pop_when_advanced_ops_unavailable():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "POP": ["circlePOP", "glslPOP", "nullPOP"],
                    "TOP": ["rendersimpleTOP", "nullTOP"],
                    "DAT": ["textDAT", "errorDAT"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent=(
            "Build a GLSL POP shader that changes point counts and writes topology "
            "with a stable TOP preview and debug output"
        ),
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(GLSL_ADVANCED_POP_OPS),
    )

    assert plan.blocked_questions
    assert "missing_op:glsladvancedPOP" in plan.missing_facts
    assert "missing_op:topologyPOP" in plan.missing_facts
    assert "missing-op:glsladvancedPOP" in plan.risk_flags
    assert "missing-op:topologyPOP" in plan.risk_flags
    assert plan.patch_plan.operations == []
    assert plan.patch_plan.risk_flags == ["missing required operators"]


@pytest.mark.asyncio
async def test_compiler_path_builds_glsl_top_shader_candidate_graph():
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "TOP": ["constantTOP", "glslTOP", "nullTOP"],
                    "DAT": ["textDAT", "errorDAT"],
                    "COMP": ["baseCOMP", "annotateCOMP"],
                    "CHOP": ["infoCHOP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await build_brain_plan(
        client,
        intent="Build a GLSL TOP shader with source texture, shader DAT, stable TOP output, and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(GLSL_TOP_SHADER_OPS),
    )

    assert plan.blocked_questions == []
    assert plan.missing_facts == []
    assert plan.compiled_task is not None
    assert plan.compiled_task.domains == ["TOP", "DAT"]
    assert plan.compiled_task.candidate_profiles == ["glsl"]
    assert plan.concept_graph.profile == "concept_compiled"
    assert plan.candidate_graphs
    candidate = plan.candidate_graphs[0]
    assert candidate.profiles == ["glsl"]
    assert {"glsl_top_shader_with_text_dat", "debug_output_conventions"}.issubset(set(candidate.pattern_ids))
    assert {"constantTOP", "glslTOP", "textDAT", "nullTOP"}.issubset(set(candidate.required_ops))
    assert "validate-glsl-compile-state" in plan.risk_flags
    assert set(candidate.required_ops).issubset(set(plan.patch_plan.required_ops))

    shell_path = "/project1/tdpilot_concept"
    create_names = [op.args["name"] for op in plan.patch_plan.operations if op.kind == "create_node"]
    assert "tdpilot_concept" in create_names
    assert "constant" in create_names
    assert "glsl" in create_names
    assert "text" in create_names
    assert "out1" in create_names
    assert "debug_notes" in create_names
    assert plan.patch_plan.validation_plan.capture_frames == [f"{shell_path}/out1"]

    shader_params = [
        op.args["params"]
        for op in plan.patch_plan.operations
        if op.kind == "set_params" and op.target == f"{shell_path}/glsl"
    ]
    assert shader_params and shader_params[0]["pixeldat"] == f"{shell_path}/text"
    generated_ops = [
        op
        for op in plan.patch_plan.operations
        if op.kind == "set_dat_content" and isinstance(op.args.get("generated_code"), dict)
    ]
    assert generated_ops
    shader_source_op = generated_ops[0]
    assert shader_source_op.target == f"{shell_path}/text"
    assert "TDOutputSwizzle" in shader_source_op.args["text"]
    assert shader_source_op.args["generated_code"]["target_op"] == f"{shell_path}/glsl"
    assert shader_source_op.args["generated_code"]["target_param"] == "pixeldat"
    assert shader_source_op.args["generated_code"]["source_refs"] == [f"{shell_path}/text"]
    assert "glsl_top_uses_td_output_swizzle" in shader_source_op.args["generated_code"]["static_checks"]
    assert validate_patch_plan_generated_code(plan.patch_plan) == []

    connect_pairs = [
        (op.args["from"], op.args["to"]) for op in plan.patch_plan.operations if op.kind == "connect"
    ]
    assert (f"{shell_path}/constant", f"{shell_path}/glsl") in connect_pairs
    assert (f"{shell_path}/glsl", f"{shell_path}/out1") in connect_pairs
    assert (f"{shell_path}/text", f"{shell_path}/glsl") not in connect_pairs
