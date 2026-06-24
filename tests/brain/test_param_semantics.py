from __future__ import annotations

import pytest
from patch.conftest import FakeTDClient

from td_mcp.brain import param_semantics
from td_mcp.brain.param_semantics import (
    load_param_semantics_registry,
    parameter_risk_flags_for_plan,
    semantics_by_op_and_param,
    validate_patch_plan_parameter_contract,
)
from td_mcp.brain.transaction import apply_transaction
from td_mcp.models.brain import ParamSemantics
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan
from td_mcp.patch.undo_sentinel import UndoBlockSentinel


class FakeCardIndex:
    def __init__(self, known: set[str]):
        self.known = known

    def get_operator(self, op_type: str):
        if op_type in self.known:
            return {"op_type": op_type, "summary": f"{op_type} docs"}
        return None


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

_CREATE_TYPE_ALIASES = {
    "glsl": "glslTOP",
    "glsltop": "glslTOP",
    "glslmat": "glslMAT",
    "rendersimple": "rendersimpleTOP",
    "rendersimpletop": "rendersimpleTOP",
}


def _plan_with_ops(operations: list[PatchOperation]) -> PatchPlan:
    return PatchPlan(
        intent="test param semantics",
        target_root="/project1",
        source="operations",
        operations=operations,
        required_ops=[],
        risk_flags=[],
        undo_label="test param semantics",
        validation_plan=ValidationPlan(target_root="/project1", capture_frames=[]),
    )


def _created_types(plan: PatchPlan) -> dict[str, str]:
    created: dict[str, str] = {}
    for operation in plan.operations:
        if operation.kind != "create_node":
            continue
        name = operation.args.get("name")
        op_type = operation.args.get("op_type")
        if name and op_type:
            created[f"{operation.target.rstrip('/')}/{name}"] = _canonical_op_type(str(op_type))
    return created


def _canonical_op_type(op_type: str) -> str:
    return _CREATE_TYPE_ALIASES.get(op_type.strip().lower(), op_type)


def _missing_set_param_semantics(plan: PatchPlan) -> list[str]:
    created = _created_types(plan)
    semantics = semantics_by_op_and_param()
    return sorted(
        {
            f"{created[operation.target]}.{name}"
            for operation in plan.operations
            if operation.kind == "set_params" and operation.target in created
            for name in operation.args.get("params", {})
            if (created[operation.target], str(name)) not in semantics
        }
    )


def test_param_semantics_registry_loads_seed_contracts():
    registry = load_param_semantics_registry()
    keys = {(item.op_type, item.name) for item in registry}

    assert ("levelTOP", "opacity") in keys
    assert ("renderTOP", "bgcolor") in keys
    assert ("renderTOP", "resolution") in keys
    assert ("renderTOP", "lights") in keys
    assert ("geometryCOMP", "sop") in keys
    assert ("geometryCOMP", "material") in keys
    assert ("lightCOMP", "dimmer") in keys
    assert ("lightCOMP", "lighttype") in keys
    assert ("lightCOMP", "projmap") in keys
    assert ("lightCOMP", "shadowcasters") in keys
    assert ("lightCOMP", "shadowmap") in keys
    assert ("cameraCOMP", "lookat") in keys
    assert ("cameraCOMP", "pathsop") in keys
    assert ("cameraCOMP", "projection") in keys
    assert ("cameraCOMP", "fov") in keys
    assert ("cameraCOMP", "near") in keys
    assert ("cameraCOMP", "far") in keys
    assert ("cameraCOMP", "customproj") in keys
    assert ("pbrMAT", "basecolor") in keys
    assert ("pbrMAT", "metallic") in keys
    assert ("pbrMAT", "roughness") in keys
    assert ("pbrMAT", "basecolormap") in keys
    assert ("pbrMAT", "roughnessmap") in keys
    assert ("pbrMAT", "metallicmap") in keys
    assert ("pbrMAT", "normalmap") in keys
    assert ("phongMAT", "diff") in keys
    assert ("phongMAT", "spec") in keys
    assert ("phongMAT", "shininess") in keys
    assert ("phongMAT", "colormap") in keys
    assert ("phongMAT", "diffusemap") in keys
    assert ("phongMAT", "specmap") in keys
    assert ("phongMAT", "normalmap") in keys
    assert ("transformTOP", "xord") in keys
    assert ("transformTOP", "t") in keys
    assert ("transformTOP", "rotate") in keys
    assert ("transformTOP", "s") in keys
    assert ("transformTOP", "p") in keys
    assert ("transformTOP", "bgcolor") in keys
    assert ("transformTOP", "extend") in keys
    assert ("cacheTOP", "active") in keys
    assert ("cacheTOP", "cachesize") in keys
    assert ("cacheTOP", "step") in keys
    assert ("cacheTOP", "outputindex") in keys
    assert ("cacheTOP", "interp") in keys
    assert ("cacheTOP", "reset") in keys
    assert ("switchTOP", "index") in keys
    assert ("glslTOP", "pixeldat") in keys
    assert ("glsladvancedPOP", "computedat") in keys
    assert ("glsladvancedPOP", "maxpoints") in keys
    assert ("glsladvancedPOP", "maxtriangles") in keys
    assert ("glsladvancedPOP", "maxquads") in keys
    assert ("glsladvancedPOP", "maxlines") in keys
    assert ("baseCOMP", "clone") in keys
    assert ("baseCOMP", "opviewer") in keys
    assert ("baseCOMP", "enablecloning") in keys
    assert ("baseCOMP", "loadondemand") in keys
    assert ("containerCOMP", "w") in keys
    assert ("containerCOMP", "h") in keys
    assert ("containerCOMP", "display") in keys
    assert ("containerCOMP", "enable") in keys
    assert ("containerCOMP", "helpdat") in keys
    assert ("containerCOMP", "top") in keys
    assert ("containerCOMP", "opacity") in keys
    assert ("sliderCOMP", "slidertype") in keys
    assert ("sliderCOMP", "value0") in keys
    assert ("sliderCOMP", "value1") in keys
    assert ("sliderCOMP", "clampul") in keys
    assert ("sliderCOMP", "clampuh") in keys
    assert ("sliderCOMP", "w") in keys
    assert ("sliderCOMP", "h") in keys
    assert ("sliderCOMP", "display") in keys
    assert ("sliderCOMP", "enable") in keys
    assert ("sliderCOMP", "opacity") in keys
    assert ("buttonCOMP", "buttontype") in keys
    assert ("buttonCOMP", "value0") in keys
    assert ("buttonCOMP", "buttongroupdat") in keys
    assert ("buttonCOMP", "scaletofit") in keys
    assert ("buttonCOMP", "display") in keys
    assert ("buttonCOMP", "enable") in keys
    assert ("buttonCOMP", "opacity") in keys

    assert ("panelCHOP", "component") in keys
    assert ("panelCHOP", "queue") in keys
    assert ("panelCHOP", "queuesize") in keys
    assert ("panelCHOP", "timeslice") in keys
    assert ("panelCHOP", "exporttable") in keys
    assert ("parameterCOMP", "op") in keys
    assert ("parameterCOMP", "header") in keys
    assert ("parameterCOMP", "builtin") in keys
    assert ("parameterCOMP", "custom") in keys
    assert ("parameterCOMP", "combinescopes") in keys
    assert ("infoCHOP", "op") in keys
    assert ("errorDAT", "active") in keys
    assert ("errorDAT", "callbacks") in keys
    assert ("errorDAT", "executeloc") in keys
    assert ("errorDAT", "fromop") in keys
    assert ("errorDAT", "clamp") in keys
    assert ("errorDAT", "maxlines") in keys
    assert ("analyzeCHOP", "function") in keys
    assert ("mathCHOP", "fromrange") in keys
    assert ("mathCHOP", "torange") in keys
    assert ("filterCHOP", "type") in keys
    assert ("filterCHOP", "effect") in keys
    assert ("filterCHOP", "widthunit") in keys
    assert ("lagCHOP", "lagmethod") in keys
    assert ("lagCHOP", "lag") in keys
    assert ("lagCHOP", "lagunit") in keys
    assert ("lagCHOP", "overshoot") in keys
    assert ("lagCHOP", "overshootunit") in keys
    assert ("lagCHOP", "slope") in keys
    assert ("lagCHOP", "accel") in keys
    assert ("datexecuteDAT", "dat") in keys
    assert ("chopexecuteDAT", "chop") in keys
    assert ("chopexecuteDAT", "executeloc") in keys
    assert ("chopexecuteDAT", "freq") in keys
    assert ("executeDAT", "executeloc") in keys
    assert ("executeDAT", "fromop") in keys
    assert ("serialDAT", "callbacks") in keys
    assert ("midiinCHOP", "simplified") in keys
    assert ("midiinCHOP", "source") in keys
    assert ("oscinDAT", "protocol") in keys
    assert ("oscinDAT", "callbacks") in keys
    assert ("oscinDAT", "executeloc") in keys
    assert ("oscinDAT", "fromop") in keys
    assert ("websocketDAT", "callbacks") in keys
    assert ("websocketDAT", "executeloc") in keys
    assert ("websocketDAT", "fromop") in keys
    assert ("webclientDAT", "request") in keys
    assert ("webclientDAT", "callbacks") in keys
    assert ("mqttclientDAT", "active") in keys
    assert ("mqttclientDAT", "callbacks") in keys
    assert ("udpinDAT", "protocol") in keys
    assert ("udpinDAT", "callbacks") in keys
    assert ("lfoCHOP", "frequency") in keys
    assert ("lfoCHOP", "amp") in keys
    assert ("lfoCHOP", "reset") in keys
    assert ("lfoCHOP", "resetpulse") in keys
    assert all(item.official_source.startswith("https://docs.derivative.ca/") for item in registry)


def test_param_semantics_coverage_report_covers_master_plan_priority_bands():
    assert hasattr(param_semantics, "param_semantics_coverage_report")

    report = param_semantics.param_semantics_coverage_report()

    assert report["ok"] is True
    assert report["missing_operator_count"] == 0
    assert report["invalid_source_count"] == 0
    assert set(report["priority_groups"]) == {
        "render_material",
        "glsl",
        "feedback_top_processing",
        "pop",
        "sop_geometry",
        "audio_control",
        "panel_parameters",
        "dat_callbacks_protocols",
    }
    for group in report["priority_groups"].values():
        assert group["missing_operators"] == []
        assert group["covered_operator_count"] == group["operator_count"]


@pytest.mark.asyncio
async def test_compiler_audio_feedback_debug_set_params_are_covered_by_semantics_registry():
    from td_mcp.brain.planner import build_brain_plan

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
    created = _created_types(plan.patch_plan)
    semantics = semantics_by_op_and_param()

    missing = sorted(
        {
            f"{created[operation.target]}.{name}"
            for operation in plan.patch_plan.operations
            if operation.kind == "set_params" and operation.target in created
            for name in operation.args.get("params", {})
            if (created[operation.target], str(name)) not in semantics
        }
    )

    assert plan.blocked_questions == []
    assert missing == []


def test_switch_top_index_accepts_bounded_integer_and_safe_table_expression():
    expression_plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "tableDAT", "name": "table"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "switchTOP", "name": "switch"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/switch",
                args={
                    "params": {
                        "index": {"expr": "min(1, max(0, int(op('/project1/table')[1, 'selected_index'])))"}
                    }
                },
            ),
        ]
    )
    integer_plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "switchTOP", "name": "switch"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/switch",
                args={"params": {"index": 1}},
            ),
        ]
    )

    assert (
        validate_patch_plan_parameter_contract(expression_plan, require_semantics_for_set_params=True) == []
    )
    assert validate_patch_plan_parameter_contract(integer_plan, require_semantics_for_set_params=True) == []


def test_switch_top_index_blocks_arbitrary_expression_bindings():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "tableDAT", "name": "table"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "switchTOP", "name": "switch"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/switch",
                args={"params": {"index": {"expr": "me.time.frame"}}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan, require_semantics_for_set_params=True)

    assert any(issue.code == "unsafe_param_expression" for issue in issues)


def test_lfo_chop_has_bounded_control_semantics():
    keys = set(semantics_by_op_and_param())
    assert ("lfoCHOP", "frequency") in keys
    assert ("lfoCHOP", "amp") in keys
    assert ("lfoCHOP", "bias") in keys
    assert ("lfoCHOP", "timeslice") in keys

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "lfoCHOP", "name": "lfo"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/lfo",
                args={"params": {"frequency": -1, "amp": -0.5, "reset": "yes please"}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan, require_semantics_for_set_params=True)

    assert {"param_out_of_range", "invalid_bool_param"}.issubset({issue.code for issue in issues})


def test_lfo_wave_and_noise_chop_promote_verified_menu_and_rate_semantics():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}

    assert by_key[("lfoCHOP", "wavetype")].value_kind == "enum"
    assert {"sine", "pulse"}.issubset(
        {value.lower() for value in by_key[("lfoCHOP", "wavetype")].enum_values}
    )
    assert by_key[("lfoCHOP", "resetcondition")].value_kind == "enum"
    assert {"offtoon", "whileon", "ontooff", "whileoff"}.issubset(
        {value.lower() for value in by_key[("lfoCHOP", "resetcondition")].enum_values}
    )
    assert by_key[("lfoCHOP", "rate")].value_kind == "float"
    assert by_key[("waveCHOP", "wavetype")].value_kind == "enum"
    assert {"const", "sin", "normal", "expr"}.issubset(
        {value.lower() for value in by_key[("waveCHOP", "wavetype")].enum_values}
    )
    assert by_key[("waveCHOP", "periodunit")].value_kind == "enum"
    assert {"samples", "frames", "seconds"}.issubset(
        {value.lower() for value in by_key[("waveCHOP", "periodunit")].enum_values}
    )
    assert by_key[("noiseCHOP", "type")].value_kind == "enum"
    assert {"sparse", "brownian", "random"}.issubset(
        {value.lower() for value in by_key[("noiseCHOP", "type")].enum_values}
    )
    assert by_key[("noiseCHOP", "periodunit")].value_kind == "enum"
    assert "fraction" in {value.lower() for value in by_key[("noiseCHOP", "periodunit")].enum_values}

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "lfoCHOP", "name": "lfo"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "waveCHOP", "name": "wave"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "noiseCHOP", "name": "noise"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/lfo",
                args={"params": {"wavetype": "sawtooth", "resetcondition": "surprise", "rate": "fast"}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/wave",
                args={"params": {"wavetype": "sawtooth", "periodunit": "beats"}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/noise",
                args={"params": {"type": "marble", "periodunit": "beats"}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan, require_semantics_for_set_params=True)
    by_path = {}
    for issue in issues:
        by_path.setdefault(issue.path, set()).add(issue.code)

    assert {"invalid_enum_param", "invalid_float_param"}.issubset(by_path["/project1/lfo"])
    assert any(
        issue.code == "invalid_enum_param"
        and issue.path == "/project1/lfo"
        and "resetcondition" in issue.message
        for issue in issues
    )
    assert "invalid_enum_param" in by_path["/project1/wave"]
    assert any(
        issue.code == "invalid_enum_param"
        and issue.path == "/project1/wave"
        and "periodunit" in issue.message
        for issue in issues
    )
    assert "invalid_enum_param" in by_path["/project1/noise"]


def test_wave_and_noise_chop_have_docs_grounded_control_semantics():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected_by_source = {
        "https://docs.derivative.ca/Wave_CHOP": {
            ("waveCHOP", "wavetype"),
            ("waveCHOP", "period"),
            ("waveCHOP", "periodunit"),
            ("waveCHOP", "phase"),
            ("waveCHOP", "bias"),
            ("waveCHOP", "amp"),
            ("waveCHOP", "offset"),
            ("waveCHOP", "decay"),
            ("waveCHOP", "channelname"),
            ("waveCHOP", "rate"),
            ("waveCHOP", "left"),
            ("waveCHOP", "right"),
            ("waveCHOP", "timeslice"),
            ("waveCHOP", "exportmethod"),
            ("waveCHOP", "exporttable"),
        },
        "https://docs.derivative.ca/Noise_CHOP": {
            ("noiseCHOP", "type"),
            ("noiseCHOP", "seed"),
            ("noiseCHOP", "period"),
            ("noiseCHOP", "periodunit"),
            ("noiseCHOP", "harmon"),
            ("noiseCHOP", "spread"),
            ("noiseCHOP", "rough"),
            ("noiseCHOP", "exp"),
            ("noiseCHOP", "numint"),
            ("noiseCHOP", "amp"),
            ("noiseCHOP", "reset"),
            ("noiseCHOP", "resetpulse"),
            ("noiseCHOP", "sustain"),
            ("noiseCHOP", "minsustain"),
            ("noiseCHOP", "channame"),
            ("noiseCHOP", "specifyrate"),
            ("noiseCHOP", "rate"),
            ("noiseCHOP", "timeslice"),
            ("noiseCHOP", "exportmethod"),
            ("noiseCHOP", "exporttable"),
        },
    }

    for official_source, expected in expected_by_source.items():
        assert expected - set(by_key) == set()
        assert all(by_key[key].official_source == official_source for key in expected)

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "waveCHOP", "name": "wave"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "noiseCHOP", "name": "noise"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullCHOP", "name": "not_dat"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/wave",
                args={
                    "params": {
                        "period": "fast",
                        "periodunit": "beats",
                        "amp": -1,
                        "rate": "fast",
                        "left": "yes",
                        "exportmethod": "spreadsheet",
                        "exporttable": "/project1/not_dat",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/noise",
                args={
                    "params": {
                        "type": "marble",
                        "seed": "random",
                        "numint": 1.5,
                        "amp": -0.25,
                        "reset": "please",
                        "specifyrate": "yes",
                        "exportmethod": "spreadsheet",
                        "exporttable": "/project1/not_dat",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan, require_semantics_for_set_params=True)
    codes = {issue.code for issue in issues}

    assert {"invalid_enum_param", "invalid_float_param", "invalid_int_param", "invalid_bool_param"}.issubset(
        codes
    )
    assert "param_out_of_range" in codes
    assert any(
        issue.code == "invalid_enum_param"
        and issue.path == "/project1/wave"
        and "periodunit" in issue.message
        for issue in issues
    )
    assert any(
        issue.code == "param_reference_type_mismatch" and issue.path == "/project1/wave" for issue in issues
    )
    assert any(
        issue.code == "param_reference_type_mismatch" and issue.path == "/project1/noise" for issue in issues
    )


def test_transform_sop_has_docs_grounded_geometry_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected = {
        ("transformSOP", "tx"),
        ("transformSOP", "ty"),
        ("transformSOP", "tz"),
        ("transformSOP", "rx"),
        ("transformSOP", "ry"),
        ("transformSOP", "rz"),
        ("transformSOP", "sx"),
        ("transformSOP", "sy"),
        ("transformSOP", "sz"),
    }

    assert expected - set(by_key) == set()
    assert all(by_key[key].official_source == "https://docs.derivative.ca/Transform_SOP" for key in expected)

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "transformSOP", "name": "transform"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/transform",
                args={"params": {"tx": "left", "sx": 25000, "rz": 45}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(
        plan,
        require_semantics_for_set_params=True,
    )

    assert any(
        issue.code == "invalid_float_param" and issue.path == "/project1/transform" and "tx" in issue.message
        for issue in issues
    )
    assert any(
        issue.code == "param_out_of_range" and issue.path == "/project1/transform" and "sx" in issue.message
        for issue in issues
    )


def test_noise_top_source_params_have_docs_grounded_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected = {
        ("noiseTOP", "type"),
        ("noiseTOP", "seed"),
        ("noiseTOP", "period"),
        ("noiseTOP", "harmon"),
        ("noiseTOP", "spread"),
        ("noiseTOP", "gain"),
        ("noiseTOP", "rough"),
        ("noiseTOP", "exp"),
        ("noiseTOP", "amp"),
        ("noiseTOP", "offset"),
        ("noiseTOP", "mono"),
        ("noiseTOP", "aspectcorrect"),
        ("noiseTOP", "xord"),
        ("noiseTOP", "rord"),
        ("noiseTOP", "t"),
        ("noiseTOP", "r"),
        ("noiseTOP", "s"),
        ("noiseTOP", "p"),
        ("noiseTOP", "t4d"),
        ("noiseTOP", "s4d"),
        ("noiseTOP", "rgb"),
        ("noiseTOP", "inputscale"),
        ("noiseTOP", "noisescale"),
        ("noiseTOP", "alpha"),
        ("noiseTOP", "dither"),
        ("noiseTOP", "gradient"),
        ("noiseTOP", "mode"),
        ("noiseTOP", "outputresolution"),
        ("noiseTOP", "resolution"),
        ("noiseTOP", "resmult"),
        ("noiseTOP", "npasses"),
    }

    assert expected - set(by_key) == set()
    assert all(by_key[key].official_source == "https://docs.derivative.ca/Noise_TOP" for key in expected)

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "noiseTOP", "name": "noise"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/noise",
                args={
                    "params": {
                        "type": "clouds",
                        "seed": "random",
                        "period": -1,
                        "harmon": 0,
                        "amp": -0.25,
                        "mono": "yes",
                        "aspectcorrect": "maybe",
                        "xord": "spin",
                        "t": (0.0, 0.0),
                        "s": (1.0, 1.0, 1.0, 1.0),
                        "outputresolution": "enormous",
                        "resolution": (8192, 8192),
                        "resmult": "yes",
                        "npasses": 0,
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan, require_semantics_for_set_params=True)
    risk_flags = parameter_risk_flags_for_plan(plan)
    codes = {issue.code for issue in issues}

    assert {
        "invalid_enum_param",
        "invalid_int_param",
        "invalid_bool_param",
        "param_tuple_size_mismatch",
        "param_out_of_range",
    }.issubset(codes)
    assert "missing_param_semantics" not in codes
    assert "param-semantics:high-resolution:noiseTOP.resolution" in risk_flags


def test_noise_top_common_aliases_are_rejected_with_canonical_param_guidance():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "noiseTOP", "name": "noise"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/noise",
                args={"params": {"harmonics": 4, "roughness": 0.45, "amplitude": 1.0}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan, require_semantics_for_set_params=True)
    messages = "\n".join(issue.message for issue in issues)

    assert {issue.code for issue in issues} == {"unknown_param_alias"}
    assert "noiseTOP.harmonics" in messages and "use noiseTOP.harmon" in messages
    assert "noiseTOP.roughness" in messages and "use noiseTOP.rough" in messages
    assert "noiseTOP.amplitude" in messages and "use noiseTOP.amp" in messages


def test_edge_and_blur_top_params_have_docs_grounded_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected = {
        ("edgeTOP", "edgecolor"),
        ("edgeTOP", "edgecolorr"),
        ("edgeTOP", "edgecolorg"),
        ("edgeTOP", "edgecolorb"),
        ("edgeTOP", "edgecolora"),
        ("blurTOP", "size"),
    }

    assert expected - set(by_key) == set()
    assert by_key[("edgeTOP", "edgecolor")].official_source == "https://docs.derivative.ca/Edge_TOP"
    assert by_key[("blurTOP", "size")].official_source == "https://docs.derivative.ca/Blur_TOP"

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "edgeTOP", "name": "edge"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "blurTOP", "name": "blur"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/edge",
                args={"params": {"edgecolor": (1.0, 0.5), "edgecolorr": "red", "edgecolora": 1.5}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/blur",
                args={"params": {"size": -2.0}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan, require_semantics_for_set_params=True)
    assert "missing_param_semantics" not in {issue.code for issue in issues}
    assert any(issue.code == "param_tuple_size_mismatch" and "edgecolor" in issue.message for issue in issues)
    assert any(issue.code == "invalid_float_param" and "edgecolorr" in issue.message for issue in issues)
    assert any(issue.code == "param_out_of_range" and "edgecolora" in issue.message for issue in issues)
    assert any(issue.code == "param_out_of_range" and "size" in issue.message for issue in issues)


def test_level_top_accepts_narrow_chop_reference_expression_for_control_binding():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullCHOP", "name": "out_chop"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "levelTOP", "name": "level"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/level",
                args={"params": {"brightness1": {"expr": "op('/project1/out_chop')[0]"}}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan, require_semantics_for_set_params=True)

    assert all(issue.code != "unsupported_param_expression" for issue in issues)


def test_level_top_rejects_non_chop_reference_expression_for_control_binding():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "out1"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "levelTOP", "name": "level"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/level",
                args={"params": {"brightness1": {"expr": "op('/project1/out1')[0]"}}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan, require_semantics_for_set_params=True)

    assert any(issue.code == "param_expression_reference_type_mismatch" for issue in issues)


def test_table_select_dat_and_switch_top_have_cue_switch_semantics():
    keys = set(semantics_by_op_and_param())
    assert ("tableDAT", "rows") in keys
    assert ("tableDAT", "cols") in keys
    assert ("selectDAT", "rowselect") in keys
    assert ("selectDAT", "colselect") in keys
    assert ("switchTOP", "index") in keys

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "tableDAT", "name": "cue_table"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "selectDAT", "name": "cue_select"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "switchTOP", "name": "cue_switch"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/cue_table",
                args={"params": {"rows": 0, "cols": -1}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/cue_switch",
                args={"params": {"index": -1}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan, require_semantics_for_set_params=True)

    assert [issue.code for issue in issues].count("param_out_of_range") == 3


@pytest.mark.asyncio
async def test_dat_table_render_switch_emits_docs_grounded_switch_index_expression():
    from td_mcp.brain.planner import build_brain_plan

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

    switch_params = [
        operation.args["params"]
        for operation in plan.patch_plan.operations
        if operation.kind == "set_params" and operation.target == "/project1/tdpilot_concept/switch"
    ]

    assert plan.blocked_questions == []
    assert switch_params == [
        {"index": {"expr": "min(1, max(0, int(op('/project1/tdpilot_concept/table')[1, 'selected_index'])))"}}
    ]
    assert _missing_set_param_semantics(plan.patch_plan) == []
    assert validate_patch_plan_parameter_contract(plan.patch_plan) == []


@pytest.mark.asyncio
async def test_compiler_path_blocks_unknown_generated_set_param_before_returning_operations(monkeypatch):
    from td_mcp.brain import planner

    original_compile = planner._compile_patch_plan

    def compile_with_ungrounded_param(task, graph, existing_names):
        patch_plan = original_compile(task, graph, existing_names)
        created_target = next(
            f"{operation.target.rstrip('/')}/{operation.args['name']}"
            for operation in patch_plan.operations
            if operation.kind == "create_node" and operation.args.get("name")
        )
        operations = [
            *patch_plan.operations,
            PatchOperation(
                kind="set_params",
                target=created_target,
                args={"params": {"not_a_docs_grounded_param": True}},
            ),
        ]
        return patch_plan.model_copy(update={"operations": operations})

    monkeypatch.setattr(planner, "_compile_patch_plan", compile_with_ungrounded_param)
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

    plan = await planner.build_brain_plan(
        client,
        intent="Build an audio-reactive feedback visual with a control panel and debug output",
        target_root="/project1",
        output_top="/project1/out1",
        card_index=FakeCardIndex(PHASE_ONE_SEED_OPS),
    )

    assert plan.blocked_questions
    assert "param_semantics:missing_param_semantics" in plan.missing_facts
    assert plan.patch_plan.operations == []


@pytest.mark.asyncio
async def test_compiler_routes_only_emit_docs_grounded_set_param_bindings():
    from td_mcp.brain.planner import build_brain_plan

    cases = [
        (
            "audio_glsl_material",
            "Build an audio-reactive 3D render with material modulation",
            MATERIAL_RENDER_OPS,
            {
                "CHOP": ["audiofileinCHOP", "analyzeCHOP", "mathCHOP", "nullCHOP", "infoCHOP"],
                "TOP": ["renderTOP", "nullTOP"],
                "COMP": ["geometryCOMP", "cameraCOMP", "baseCOMP", "annotateCOMP"],
                "MAT": ["glslMAT"],
                "DAT": ["textDAT", "errorDAT"],
            },
            {},
        ),
        (
            "terrain_material_controls",
            "Build a melting glass terrain driven by music with UI controls and debug output",
            TERRAIN_MATERIAL_OPS,
            {
                "CHOP": ["audiofileinCHOP", "analyzeCHOP", "mathCHOP", "nullCHOP", "panelCHOP", "infoCHOP"],
                "TOP": ["renderTOP", "nullTOP"],
                "COMP": [
                    "geometryCOMP",
                    "cameraCOMP",
                    "containerCOMP",
                    "sliderCOMP",
                    "buttonCOMP",
                    "baseCOMP",
                    "annotateCOMP",
                ],
                "MAT": ["glslMAT"],
                "SOP": ["gridSOP", "noiseSOP", "nullSOP"],
                "DAT": ["textDAT", "errorDAT"],
            },
            {},
        ),
        (
            "ndi_post_fx",
            "Build an NDI input with post FX and stable TOP output",
            NDI_POST_FX_OPS,
            {
                "TOP": ["ndiinTOP", "levelTOP", "nullTOP"],
                "COMP": ["baseCOMP", "annotateCOMP"],
                "CHOP": ["infoCHOP"],
                "DAT": ["textDAT", "errorDAT"],
            },
            {"device_sources": ["ndi_source"]},
        ),
        (
            "pop_preview",
            "Build a POP particle field preview with stable TOP output and debug output",
            POP_PREVIEW_OPS,
            {
                "POP": ["circlePOP", "noisePOP", "mathmixPOP", "nullPOP"],
                "TOP": ["rendersimpleTOP", "nullTOP"],
                "DAT": ["textDAT", "errorDAT"],
                "COMP": ["baseCOMP", "annotateCOMP"],
                "CHOP": ["infoCHOP"],
            },
            {},
        ),
        (
            "glsl_top_shader",
            "Build a GLSL TOP shader with source texture, shader DAT, stable TOP output, and debug output",
            GLSL_TOP_SHADER_OPS,
            {
                "TOP": ["constantTOP", "glslTOP", "nullTOP"],
                "DAT": ["textDAT", "errorDAT"],
                "COMP": ["baseCOMP", "annotateCOMP"],
                "CHOP": ["infoCHOP"],
            },
            {},
        ),
    ]

    missing_by_case: dict[str, list[str]] = {}
    for case_id, intent, known_ops, families, constraints in cases:
        client = FakeTDClient(scripted={"families": {"families": families}, "nodes": {"nodes": []}})
        plan = await build_brain_plan(
            client,
            intent=intent,
            target_root="/project1",
            output_top="/project1/out1",
            card_index=FakeCardIndex(known_ops),
            constraints=constraints,
        )

        assert plan.blocked_questions == []
        missing_by_case[case_id] = _missing_set_param_semantics(plan.patch_plan)

    assert missing_by_case == {case_id: [] for case_id, *_ in cases}


def test_param_semantics_flags_high_resolution_top_without_blocking():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "geometryCOMP", "name": "geo"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "cameraCOMP", "name": "camera"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "renderTOP", "name": "render"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/render",
                args={
                    "params": {
                        "camera": "/project1/camera",
                        "geometry": "/project1/geo",
                        "resolution": (7680, 4320),
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)
    risk_flags = parameter_risk_flags_for_plan(plan)

    assert issues == []
    assert "param-semantics:high-resolution:renderTOP.resolution" in risk_flags


def test_param_semantics_blocks_out_of_range_numeric_param():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "levelTOP", "name": "level"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/level",
                args={"params": {"opacity": 1.25}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert any(issue.code == "param_out_of_range" and issue.severity == "error" for issue in issues)


def test_param_semantics_blocks_tuple_size_mismatch():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "renderTOP", "name": "render"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/render",
                args={"params": {"bgcolor": (0.0, 0.0, 0.0)}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert any(issue.code == "param_tuple_size_mismatch" for issue in issues)


def test_param_semantics_blocks_unknown_enum_value_with_custom_contract():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "compositeTOP", "name": "composite"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/composite",
                args={"params": {"operand": "Definitely Not A Blend Mode"}},
            ),
        ]
    )
    registry = [
        ParamSemantics(
            op_type="compositeTOP",
            name="operand",
            label="Composite Operation",
            value_kind="enum",
            enum_values=["Over", "Add", "Multiply"],
            default_strategy="keep_default",
            cook_risk="low",
            validation_rule="known_menu_value",
            official_source="https://docs.derivative.ca/Composite_TOP",
        )
    ]

    issues = validate_patch_plan_parameter_contract(plan, registry=registry)

    assert any(issue.code == "invalid_enum_param" for issue in issues)


@pytest.mark.asyncio
async def test_transaction_preflight_blocks_param_semantics_errors_before_preview():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "compositeTOP", "name": "composite"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/composite",
                args={"params": {"operand": "Definitely Not A Blend Mode"}},
            ),
        ]
    )
    client = FakeTDClient()

    result = await apply_transaction(
        client,
        plan,
        sentinel=UndoBlockSentinel(),
        concept_profile="feedback",
    )

    assert result.status == "blocked"
    assert result.failed_reason
    assert "operand" in result.failed_reason
    assert result.apply_result is None
    assert result.validation_report is not None
    assert result.validation_report.ok is False
    assert result.validation_report.checks == ["param_semantics"]
    assert any(issue.code == "invalid_enum_param" for issue in result.validation_report.issues)
    assert client.calls == []


def test_param_semantics_includes_existing_reference_validator():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "glslTOP", "name": "shader"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullTOP", "name": "not_a_dat"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/shader",
                args={"params": {"pixeldat": "/project1/not_a_dat"}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert any(issue.code == "invalid_reference_param" for issue in issues)


def test_glsl_top_params_have_docs_grounded_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected = {
        ("glslTOP", "glslversion"),
        ("glslTOP", "mode"),
        ("glslTOP", "predat"),
        ("glslTOP", "vertexdat"),
        ("glslTOP", "pixeldat"),
        ("glslTOP", "computedat"),
        ("glslTOP", "compilebehavior"),
        ("glslTOP", "errorbehavior"),
        ("glslTOP", "autodispatchsize"),
        ("glslTOP", "dispatchsizex"),
        ("glslTOP", "dispatchsizey"),
        ("glslTOP", "dispatchsizez"),
        ("glslTOP", "outputaccess"),
        ("glslTOP", "type"),
        ("glslTOP", "depth"),
        ("glslTOP", "customdepth"),
        ("glslTOP", "clearoutputs"),
        ("glslTOP", "clearvalue"),
        ("glslTOP", "inputmapping"),
        ("glslTOP", "nval"),
        ("glslTOP", "inputextenduv"),
        ("glslTOP", "inputextendw"),
        ("glslTOP", "numcolorbufs"),
        ("glslTOP", "simplexnoise"),
        ("glslTOP", "array0chop"),
        ("glslTOP", "array0type"),
        ("glslTOP", "array0arraytype"),
        ("glslTOP", "buffer0pop"),
        ("glslTOP", "buffer0attrclass"),
        ("glslTOP", "buffer0attr"),
        ("glslTOP", "buffer0name"),
        ("glslTOP", "outputresolution"),
        ("glslTOP", "resolution"),
        ("glslTOP", "resmult"),
        ("glslTOP", "npasses"),
    }

    missing = expected - set(by_key)
    assert missing == set()
    assert all(by_key[key].official_source == "https://docs.derivative.ca/GLSL_TOP" for key in expected)

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glslTOP", "name": "shader"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "shader_text"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "constantTOP", "name": "source_top"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "mathCHOP", "name": "control_chop"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullPOP", "name": "pop_source"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "not_a_dat"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/shader",
                args={
                    "params": {
                        "predat": "/project1/not_a_dat",
                        "vertexdat": "/project1/not_a_dat",
                        "pixeldat": "/project1/not_a_dat",
                        "computedat": "/project1/not_a_dat",
                        "mode": "Particle Shader",
                        "compilebehavior": "Never Compile",
                        "errorbehavior": "Explode",
                        "autodispatchsize": "yes",
                        "dispatchsizex": 0,
                        "dispatchsizey": "many",
                        "dispatchsizez": -1,
                        "outputaccess": "Read Everything",
                        "type": "Cube Texture",
                        "depth": "Deep",
                        "customdepth": 0,
                        "clearoutputs": "maybe",
                        "clearvalue": (0.0, 0.0, 0.0),
                        "inputmapping": "One Per Dimension",
                        "nval": 0,
                        "inputextenduv": "Wrap",
                        "inputextendw": "Clamp",
                        "numcolorbufs": "lots",
                        "simplexnoise": "Turbo",
                        "array0chop": "/project1/not_a_dat",
                        "array0type": "vec5",
                        "array0arraytype": "storagebuffer",
                        "buffer0pop": "/project1/not_a_dat",
                        "buffer0attrclass": "edge",
                        "outputresolution": "moon",
                        "resolution": (8192, 8192),
                        "resmult": "sometimes",
                        "npasses": 0,
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)
    risk_flags = parameter_risk_flags_for_plan(plan)

    assert sum(1 for issue in issues if issue.code == "param_reference_type_mismatch") >= 6
    assert sum(1 for issue in issues if issue.code == "invalid_enum_param") >= 10
    assert sum(1 for issue in issues if issue.code == "invalid_bool_param") >= 3
    assert sum(1 for issue in issues if issue.code == "invalid_int_param") >= 2
    assert sum(1 for issue in issues if issue.code == "param_out_of_range") >= 5
    assert any(issue.code == "param_tuple_size_mismatch" for issue in issues)
    assert "param-semantics:high-resolution:glslTOP.resolution" in risk_flags


def test_geometry_comp_sop_param_requires_sop_reference():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "geometryCOMP", "name": "geometry"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullTOP", "name": "not_a_sop"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/geometry",
                args={"params": {"sop": "/project1/not_a_sop"}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert any(issue.code == "param_reference_type_mismatch" for issue in issues)


def test_render_material_and_light_params_require_compatible_created_refs_and_menus():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "renderTOP", "name": "render"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "geometryCOMP", "name": "geo"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "lightCOMP", "name": "key_light"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullTOP", "name": "not_a_light_or_mat"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/render",
                args={"params": {"lights": "/project1/not_a_light_or_mat"}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/geo",
                args={"params": {"material": "/project1/not_a_light_or_mat"}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/key_light",
                args={
                    "params": {
                        "dimmer": "bright",
                        "lighttype": "Laser",
                        "projmap": "/project1/geo",
                        "shadowcasters": "/project1/not_a_light_or_mat",
                        "shadowmap": "/project1/geo",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    ref_issues = [issue for issue in issues if issue.code == "param_reference_type_mismatch"]
    assert len(ref_issues) == 5
    assert any(issue.code == "invalid_enum_param" and issue.path == "/project1/key_light" for issue in issues)
    assert any(
        issue.code == "invalid_float_param" and issue.path == "/project1/key_light" for issue in issues
    )


def test_render_top_output_advanced_and_sampler_params_have_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected = {
        ("renderTOP", "camera"),
        ("renderTOP", "multicamerahint"),
        ("renderTOP", "geometry"),
        ("renderTOP", "lights"),
        ("renderTOP", "antialias"),
        ("renderTOP", "bgcolor"),
        ("renderTOP", "premultrgbbyalpha"),
        ("renderTOP", "rendermode"),
        ("renderTOP", "transparency"),
        ("renderTOP", "depthpeel"),
        ("renderTOP", "transpeellayers"),
        ("renderTOP", "render"),
        ("renderTOP", "dither"),
        ("renderTOP", "coloroutputneeded"),
        ("renderTOP", "drawdepthonly"),
        ("renderTOP", "numcolorbufs"),
        ("renderTOP", "depthformat"),
        ("renderTOP", "cullface"),
        ("renderTOP", "overridemat"),
        ("renderTOP", "polygonoffset"),
        ("renderTOP", "polygonoffsetfactor"),
        ("renderTOP", "polygonoffsetunits"),
        ("renderTOP", "overdraw"),
        ("renderTOP", "overdrawlimit"),
        ("renderTOP", "sampler0top"),
        ("renderTOP", "sampler0extendu"),
        ("renderTOP", "sampler0extendv"),
        ("renderTOP", "sampler0extendw"),
        ("renderTOP", "sampler0filter"),
        ("renderTOP", "sampler0anisotropy"),
        ("renderTOP", "outputresolution"),
        ("renderTOP", "resolution"),
        ("renderTOP", "resmult"),
        ("renderTOP", "npasses"),
    }

    missing = expected - set(by_key)
    assert missing == set()
    assert all(by_key[key].official_source == "https://docs.derivative.ca/Render_TOP" for key in expected)

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "renderTOP", "name": "render"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "cameraCOMP", "name": "camera"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "geometryCOMP", "name": "geo"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "lightCOMP", "name": "key_light"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "phongMAT", "name": "mat"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "source_top"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "not_render_ref"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/render",
                args={
                    "params": {
                        "camera": "/project1/not_render_ref",
                        "geometry": "/project1/not_render_ref",
                        "lights": "/project1/not_render_ref",
                        "overridemat": "/project1/not_render_ref",
                        "sampler0top": "/project1/not_render_ref",
                        "multicamerahint": "All Cameras At Once",
                        "antialias": "128x",
                        "premultrgbbyalpha": "yes",
                        "rendermode": "Hologram",
                        "transparency": "Perfect",
                        "depthpeel": "maybe",
                        "transpeellayers": 0,
                        "render": "go",
                        "dither": "sometimes",
                        "coloroutputneeded": 2,
                        "drawdepthonly": "depth",
                        "numcolorbufs": 0,
                        "depthformat": "16-bit",
                        "cullface": "edges",
                        "polygonoffset": "push",
                        "polygonoffsetfactor": "farther",
                        "polygonoffsetunits": "tiny",
                        "overdraw": "show",
                        "overdrawlimit": 0,
                        "sampler0extendu": "Clamp",
                        "sampler0extendv": "Wrap",
                        "sampler0extendw": "Clamp",
                        "sampler0filter": "Bicubic",
                        "sampler0anisotropy": "64x",
                        "outputresolution": "Huge",
                        "resolution": (8192, 8192),
                        "resmult": "sometimes",
                        "npasses": 0,
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)
    risk_flags = parameter_risk_flags_for_plan(plan)

    assert sum(1 for issue in issues if issue.code == "param_reference_type_mismatch") >= 5
    assert sum(1 for issue in issues if issue.code == "invalid_enum_param") >= 10
    assert sum(1 for issue in issues if issue.code == "invalid_bool_param") >= 8
    assert sum(1 for issue in issues if issue.code == "invalid_int_param") == 0
    assert sum(1 for issue in issues if issue.code == "invalid_float_param") == 2
    assert sum(1 for issue in issues if issue.code == "param_out_of_range") >= 4
    assert "param-semantics:high-resolution:renderTOP.resolution" in risk_flags


def test_glsl_mat_shader_sampler_deform_and_render_params_have_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected = {
        ("glslMAT", "glslversion"),
        ("glslMAT", "predat"),
        ("glslMAT", "vdat"),
        ("glslMAT", "pdat"),
        ("glslMAT", "loaduniformnames"),
        ("glslMAT", "clearuniformnames"),
        ("glslMAT", "gdat"),
        ("glslMAT", "inherit"),
        ("glslMAT", "lightingspace"),
        ("glslMAT", "simplexnoise"),
        ("glslMAT", "inprim"),
        ("glslMAT", "outprim"),
        ("glslMAT", "numout"),
        ("glslMAT", "twocolor"),
        ("glslMAT", "attr0name"),
        ("glslMAT", "attr0type"),
        ("glslMAT", "attr0size"),
        ("glslMAT", "sampler0name"),
        ("glslMAT", "sampler0top"),
        ("glslMAT", "sampler0extendu"),
        ("glslMAT", "sampler0extendv"),
        ("glslMAT", "sampler0extendw"),
        ("glslMAT", "sampler0filter"),
        ("glslMAT", "sampler0anisotropy"),
        ("glslMAT", "vec0name"),
        ("glslMAT", "vec0value"),
        ("glslMAT", "matrix0name"),
        ("glslMAT", "matrix0value"),
        ("glslMAT", "rel0name"),
        ("glslMAT", "rel0from"),
        ("glslMAT", "rel0to"),
        ("glslMAT", "const0name"),
        ("glslMAT", "const0value"),
        ("glslMAT", "dodeform"),
        ("glslMAT", "deformdata"),
        ("glslMAT", "targetsop"),
        ("glslMAT", "pcaptpath"),
        ("glslMAT", "pcaptdata"),
        ("glslMAT", "skelrootpath"),
        ("glslMAT", "mat"),
        ("glslMAT", "blending"),
        ("glslMAT", "blendop"),
        ("glslMAT", "srcblend"),
        ("glslMAT", "destblend"),
        ("glslMAT", "separatealphafunc"),
        ("glslMAT", "blendopa"),
        ("glslMAT", "srcblenda"),
        ("glslMAT", "destblenda"),
        ("glslMAT", "blendconstant"),
        ("glslMAT", "blendconstanta"),
        ("glslMAT", "legacyalphabehavior"),
        ("glslMAT", "postmultalpha"),
        ("glslMAT", "pointcolorpremult"),
        ("glslMAT", "depthtest"),
        ("glslMAT", "depthfunc"),
        ("glslMAT", "depthwriting"),
        ("glslMAT", "alphatest"),
        ("glslMAT", "alphafunc"),
        ("glslMAT", "alphathreshold"),
        ("glslMAT", "wireframe"),
        ("glslMAT", "wirewidth"),
        ("glslMAT", "cullface"),
        ("glslMAT", "polygonoffset"),
        ("glslMAT", "polygonoffsetfactor"),
        ("glslMAT", "polygonoffsetunits"),
    }

    missing = expected - set(by_key)
    assert missing == set()
    assert all(by_key[key].official_source == "https://docs.derivative.ca/GLSL_MAT" for key in expected)

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glslMAT", "name": "mat_shader"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "shader_text"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "not_a_ref"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "source_top"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullSOP", "name": "sop_source"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "baseCOMP", "name": "rig"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "phongMAT", "name": "phong"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/mat_shader",
                args={
                    "params": {
                        "predat": "/project1/not_a_ref",
                        "vdat": "/project1/not_a_ref",
                        "pdat": "/project1/not_a_ref",
                        "gdat": "/project1/not_a_ref",
                        "inherit": "/project1/not_a_ref",
                        "sampler0top": "/project1/shader_text",
                        "targetsop": "/project1/not_a_ref",
                        "skelrootpath": "/project1/not_a_ref",
                        "mat": "/project1/not_a_ref",
                        "rel0from": "/project1/not_a_ref",
                        "rel0to": "/project1/not_a_ref",
                        "glslversion": "glsl999",
                        "lightingspace": "Object Space",
                        "simplexnoise": "Ultra",
                        "inprim": "Quads",
                        "outprim": "Triangle Fan",
                        "attr0type": "vec5",
                        "sampler0extendu": "Clamp",
                        "sampler0extendv": "Wrap",
                        "sampler0extendw": "Clamp",
                        "sampler0filter": "Bicubic",
                        "sampler0anisotropy": "64x",
                        "deformdata": "Bones",
                        "blendop": "Mix",
                        "srcblend": "Source",
                        "destblend": "Destination",
                        "blendopa": "Mix",
                        "srcblenda": "Source",
                        "destblenda": "Destination",
                        "pointcolorpremult": "Auto",
                        "depthfunc": "Nearer",
                        "alphafunc": "Opaque",
                        "wireframe": "Mesh",
                        "cullface": "Edges",
                        "loaduniformnames": "yes",
                        "clearuniformnames": "yes",
                        "twocolor": "maybe",
                        "dodeform": "maybe",
                        "blending": "blend",
                        "separatealphafunc": "separate",
                        "legacyalphabehavior": "legacy",
                        "postmultalpha": "post",
                        "depthtest": "depth",
                        "depthwriting": "write",
                        "alphatest": "alpha",
                        "polygonoffset": "push",
                        "numout": 0,
                        "attr0size": 0,
                        "vec0value": (1.0, 2.0),
                        "matrix0value": (1.0, 0.0),
                        "const0value": "one",
                        "blendconstant": (1.0, 0.5),
                        "blendconstanta": 2.0,
                        "alphathreshold": -0.1,
                        "wirewidth": 0,
                        "polygonoffsetfactor": "far",
                        "polygonoffsetunits": "tiny",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert sum(1 for issue in issues if issue.code == "param_reference_type_mismatch") >= 10
    assert sum(1 for issue in issues if issue.code == "invalid_enum_param") >= 18
    assert sum(1 for issue in issues if issue.code == "invalid_bool_param") >= 10
    assert sum(1 for issue in issues if issue.code == "invalid_int_param") == 0
    assert sum(1 for issue in issues if issue.code == "invalid_float_param") >= 3
    assert sum(1 for issue in issues if issue.code == "param_tuple_size_mismatch") >= 3
    assert sum(1 for issue in issues if issue.code == "param_out_of_range") >= 4


def test_geometry_comp_xform_instancing_and_render_params_have_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected = {
        ("geometryCOMP", "sop"),
        ("geometryCOMP", "xord"),
        ("geometryCOMP", "rord"),
        ("geometryCOMP", "t"),
        ("geometryCOMP", "r"),
        ("geometryCOMP", "s"),
        ("geometryCOMP", "p"),
        ("geometryCOMP", "scale"),
        ("geometryCOMP", "parentxformsrc"),
        ("geometryCOMP", "parentobject"),
        ("geometryCOMP", "lookat"),
        ("geometryCOMP", "forwarddir"),
        ("geometryCOMP", "lookup"),
        ("geometryCOMP", "pathsop"),
        ("geometryCOMP", "roll"),
        ("geometryCOMP", "pos"),
        ("geometryCOMP", "pathorient"),
        ("geometryCOMP", "up"),
        ("geometryCOMP", "bank"),
        ("geometryCOMP", "instancing"),
        ("geometryCOMP", "instancecountmode"),
        ("geometryCOMP", "numinstances"),
        ("geometryCOMP", "instanceop"),
        ("geometryCOMP", "instancefirstrow"),
        ("geometryCOMP", "instxord"),
        ("geometryCOMP", "instrord"),
        ("geometryCOMP", "instancetop"),
        ("geometryCOMP", "instancerop"),
        ("geometryCOMP", "instancesop"),
        ("geometryCOMP", "instancepop"),
        ("geometryCOMP", "material"),
        ("geometryCOMP", "render"),
        ("geometryCOMP", "drawpriority"),
        ("geometryCOMP", "pickpriority"),
        ("geometryCOMP", "wcolor"),
        ("geometryCOMP", "lightmask"),
    }

    missing = expected - set(by_key)
    assert missing == set()
    assert all(by_key[key].official_source == "https://docs.derivative.ca/Geometry_COMP" for key in expected)

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "geometryCOMP", "name": "geo"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "not_a_ref"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullSOP", "name": "surface"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "baseCOMP", "name": "target"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "lightCOMP", "name": "key_light"}
            ),
            PatchOperation(kind="create_node", target="/project1", args={"op_type": "pbrMAT", "name": "mat"}),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "constantCHOP", "name": "instances"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/geo",
                args={
                    "params": {
                        "sop": "/project1/not_a_ref",
                        "parentobject": "/project1/not_a_ref",
                        "lookat": "/project1/not_a_ref",
                        "pathsop": "/project1/not_a_ref",
                        "material": "/project1/not_a_ref",
                        "lightmask": "/project1/not_a_ref",
                        "instanceop": 123,
                        "instancetop": 123,
                        "instancerop": 123,
                        "instancesop": 123,
                        "instancepop": 123,
                        "xord": "Spin Translate Scale",
                        "rord": "xyzzy",
                        "parentxformsrc": "Moon",
                        "forwarddir": "diagonal",
                        "lookup": "Twist",
                        "instancecountmode": "Infinite",
                        "instancefirstrow": "Header",
                        "instxord": "Spin Translate Scale",
                        "instrord": "xyzzy",
                        "instancing": "yes",
                        "pathorient": "yes",
                        "render": "visible",
                        "t": (1.0, 2.0),
                        "r": "spin",
                        "s": (1.0, 0.0, 1.0),
                        "p": (0.0,),
                        "up": (0.0, 1.0),
                        "wcolor": (1.0, 0.5),
                        "scale": "large",
                        "roll": "roll",
                        "pos": -0.5,
                        "bank": "bank",
                        "numinstances": 2_000_000,
                        "drawpriority": "front",
                        "pickpriority": "pick",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)
    risk_flags = parameter_risk_flags_for_plan(plan)

    assert sum(1 for issue in issues if issue.code == "param_reference_type_mismatch") >= 6
    assert sum(1 for issue in issues if issue.code == "missing_reference_param") >= 5
    assert sum(1 for issue in issues if issue.code == "invalid_enum_param") >= 9
    assert sum(1 for issue in issues if issue.code == "invalid_bool_param") >= 3
    assert sum(1 for issue in issues if issue.code == "invalid_float_param") >= 5
    assert sum(1 for issue in issues if issue.code == "param_tuple_size_mismatch") >= 4
    assert sum(1 for issue in issues if issue.code == "param_out_of_range") >= 2
    assert "param-semantics:large-instance-count:geometryCOMP.numinstances" in risk_flags


def test_camera_comp_xform_view_fog_and_render_params_have_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected = {
        ("cameraCOMP", "xord"),
        ("cameraCOMP", "rord"),
        ("cameraCOMP", "t"),
        ("cameraCOMP", "r"),
        ("cameraCOMP", "s"),
        ("cameraCOMP", "p"),
        ("cameraCOMP", "scale"),
        ("cameraCOMP", "parentxformsrc"),
        ("cameraCOMP", "parentobject"),
        ("cameraCOMP", "lookat"),
        ("cameraCOMP", "forwarddir"),
        ("cameraCOMP", "lookup"),
        ("cameraCOMP", "pathsop"),
        ("cameraCOMP", "roll"),
        ("cameraCOMP", "pos"),
        ("cameraCOMP", "pathorient"),
        ("cameraCOMP", "up"),
        ("cameraCOMP", "bank"),
        ("cameraCOMP", "projection"),
        ("cameraCOMP", "projectionblend"),
        ("cameraCOMP", "orthowidth"),
        ("cameraCOMP", "viewanglemethod"),
        ("cameraCOMP", "fov"),
        ("cameraCOMP", "focal"),
        ("cameraCOMP", "aperture"),
        ("cameraCOMP", "near"),
        ("cameraCOMP", "far"),
        ("cameraCOMP", "winrollpivot"),
        ("cameraCOMP", "win"),
        ("cameraCOMP", "winsize"),
        ("cameraCOMP", "winroll"),
        ("cameraCOMP", "ipdshift"),
        ("cameraCOMP", "projmatrixop"),
        ("cameraCOMP", "customproj"),
        ("cameraCOMP", "quadreprojsop"),
        ("cameraCOMP", "quadreprojpts"),
        ("cameraCOMP", "bgcolor"),
        ("cameraCOMP", "premultrgbbyalpha"),
        ("cameraCOMP", "fog"),
        ("cameraCOMP", "fogdensity"),
        ("cameraCOMP", "fognear"),
        ("cameraCOMP", "fogfar"),
        ("cameraCOMP", "fogcolor"),
        ("cameraCOMP", "fogalpha"),
        ("cameraCOMP", "fogmap"),
        ("cameraCOMP", "camlightmask"),
        ("cameraCOMP", "material"),
        ("cameraCOMP", "render"),
        ("cameraCOMP", "drawpriority"),
        ("cameraCOMP", "pickpriority"),
        ("cameraCOMP", "wcolor"),
        ("cameraCOMP", "lightmask"),
    }

    missing = expected - set(by_key)
    assert missing == set()
    assert all(by_key[key].official_source == "https://docs.derivative.ca/Camera_COMP" for key in expected)

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "cameraCOMP", "name": "camera"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "not_a_ref"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "baseCOMP", "name": "target"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullSOP", "name": "path"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "custom_proj"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "lightCOMP", "name": "key_light"}
            ),
            PatchOperation(kind="create_node", target="/project1", args={"op_type": "pbrMAT", "name": "mat"}),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "constantCHOP", "name": "proj_chop"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/camera",
                args={
                    "params": {
                        "parentobject": "/project1/not_a_ref",
                        "lookat": "/project1/not_a_ref",
                        "pathsop": "/project1/not_a_ref",
                        "projmatrixop": 123,
                        "customproj": "/project1/not_a_ref",
                        "quadreprojsop": "/project1/not_a_ref",
                        "fogmap": "/project1/custom_proj",
                        "camlightmask": "/project1/not_a_ref",
                        "material": "/project1/not_a_ref",
                        "lightmask": "/project1/not_a_ref",
                        "xord": "Spin Translate Scale",
                        "rord": "xyzzy",
                        "parentxformsrc": "Moon",
                        "forwarddir": "diagonal",
                        "lookup": "Twist",
                        "projection": "Fisheye",
                        "viewanglemethod": "Throw",
                        "winrollpivot": "Corner",
                        "fog": "Mist",
                        "pathorient": "yes",
                        "premultrgbbyalpha": "yes",
                        "render": "visible",
                        "t": (1.0, 2.0),
                        "r": "spin",
                        "s": (1.0, 0.0, 1.0),
                        "p": (0.0,),
                        "up": (0.0, 1.0),
                        "win": (0.0,),
                        "quadreprojpts": (0, 1, 2),
                        "bgcolor": (1.0, 0.5),
                        "fogcolor": (1.0, 0.5),
                        "wcolor": (1.0, 0.5),
                        "scale": "large",
                        "roll": "roll",
                        "pos": -0.5,
                        "bank": "bank",
                        "projectionblend": 2.0,
                        "orthowidth": 0,
                        "fov": 360,
                        "focal": 0,
                        "aperture": 0,
                        "near": 0,
                        "far": 0,
                        "winsize": 0,
                        "winroll": "tilt",
                        "ipdshift": "wide",
                        "fogdensity": -0.1,
                        "fognear": -1,
                        "fogfar": -1,
                        "fogalpha": 2.0,
                        "drawpriority": "front",
                        "pickpriority": "pick",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert sum(1 for issue in issues if issue.code == "param_reference_type_mismatch") >= 9
    assert sum(1 for issue in issues if issue.code == "missing_reference_param") >= 1
    assert sum(1 for issue in issues if issue.code == "invalid_enum_param") >= 9
    assert sum(1 for issue in issues if issue.code == "invalid_bool_param") >= 3
    assert sum(1 for issue in issues if issue.code == "invalid_float_param") >= 7
    assert sum(1 for issue in issues if issue.code == "param_tuple_size_mismatch") >= 8
    assert sum(1 for issue in issues if issue.code == "param_out_of_range") >= 10


def test_light_comp_xform_light_shadow_view_and_render_params_have_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected = {
        ("lightCOMP", "xord"),
        ("lightCOMP", "rord"),
        ("lightCOMP", "t"),
        ("lightCOMP", "r"),
        ("lightCOMP", "s"),
        ("lightCOMP", "p"),
        ("lightCOMP", "scale"),
        ("lightCOMP", "parentxformsrc"),
        ("lightCOMP", "parentobject"),
        ("lightCOMP", "lookat"),
        ("lightCOMP", "forwarddir"),
        ("lightCOMP", "lookup"),
        ("lightCOMP", "pathsop"),
        ("lightCOMP", "roll"),
        ("lightCOMP", "pos"),
        ("lightCOMP", "pathorient"),
        ("lightCOMP", "up"),
        ("lightCOMP", "bank"),
        ("lightCOMP", "c"),
        ("lightCOMP", "dimmer"),
        ("lightCOMP", "lighttype"),
        ("lightCOMP", "coneangle"),
        ("lightCOMP", "conedelta"),
        ("lightCOMP", "coneroll"),
        ("lightCOMP", "attenuated"),
        ("lightCOMP", "attenuationstart"),
        ("lightCOMP", "attenuationend"),
        ("lightCOMP", "attenuationexp"),
        ("lightCOMP", "projmaptype"),
        ("lightCOMP", "projmap"),
        ("lightCOMP", "projmapextendu"),
        ("lightCOMP", "projmapextendv"),
        ("lightCOMP", "projmapextendw"),
        ("lightCOMP", "projmapfilter"),
        ("lightCOMP", "projmapanisotropy"),
        ("lightCOMP", "projmapmode"),
        ("lightCOMP", "projangle"),
        ("lightCOMP", "frontfacelit"),
        ("lightCOMP", "backfacelit"),
        ("lightCOMP", "shadowtype"),
        ("lightCOMP", "shadowcasters"),
        ("lightCOMP", "lightsize"),
        ("lightCOMP", "maxshadowsoftness"),
        ("lightCOMP", "filtersamples"),
        ("lightCOMP", "searchsteps"),
        ("lightCOMP", "polygonoffsetfactor"),
        ("lightCOMP", "polygonoffsetunits"),
        ("lightCOMP", "shadowresolution"),
        ("lightCOMP", "shadowmap"),
        ("lightCOMP", "projection"),
        ("lightCOMP", "aspectcorrect"),
        ("lightCOMP", "orthowidth"),
        ("lightCOMP", "useconeforfov"),
        ("lightCOMP", "viewanglemethod"),
        ("lightCOMP", "fov"),
        ("lightCOMP", "focal"),
        ("lightCOMP", "aperture"),
        ("lightCOMP", "near"),
        ("lightCOMP", "far"),
        ("lightCOMP", "projmatrixop"),
        ("lightCOMP", "customproj"),
        ("lightCOMP", "bgcolor"),
        ("lightCOMP", "material"),
        ("lightCOMP", "render"),
        ("lightCOMP", "drawpriority"),
        ("lightCOMP", "pickpriority"),
        ("lightCOMP", "wcolor"),
        ("lightCOMP", "lightmask"),
    }

    missing = expected - set(by_key)
    assert missing == set()
    assert all(by_key[key].official_source == "https://docs.derivative.ca/Light_COMP" for key in expected)

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "lightCOMP", "name": "key_light"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "not_a_ref"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "baseCOMP", "name": "target"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullSOP", "name": "path"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "geometryCOMP", "name": "geo"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "custom_proj"}
            ),
            PatchOperation(kind="create_node", target="/project1", args={"op_type": "pbrMAT", "name": "mat"}),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "constantCHOP", "name": "proj_chop"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/key_light",
                args={
                    "params": {
                        "parentobject": "/project1/not_a_ref",
                        "lookat": "/project1/not_a_ref",
                        "pathsop": "/project1/not_a_ref",
                        "projmap": "/project1/custom_proj",
                        "shadowcasters": "/project1/not_a_ref",
                        "shadowmap": "/project1/custom_proj",
                        "projmatrixop": 123,
                        "customproj": "/project1/not_a_ref",
                        "material": "/project1/not_a_ref",
                        "lightmask": "/project1/not_a_ref",
                        "xord": "Spin Translate Scale",
                        "rord": "xyzzy",
                        "parentxformsrc": "Moon",
                        "forwarddir": "diagonal",
                        "lookup": "Twist",
                        "lighttype": "Laser",
                        "projmaptype": "Cube",
                        "projmapextendu": "Clamp",
                        "projmapextendv": "Wrap",
                        "projmapextendw": "Clamp",
                        "projmapfilter": "Bicubic",
                        "projmapanisotropy": "64x",
                        "projmapmode": "Magic",
                        "frontfacelit": "Side Lit",
                        "backfacelit": "Side Lit",
                        "shadowtype": "Raytraced",
                        "projection": "Fisheye",
                        "viewanglemethod": "Throw",
                        "pathorient": "yes",
                        "attenuated": "yes",
                        "aspectcorrect": "yes",
                        "useconeforfov": "yes",
                        "render": "visible",
                        "t": (1.0, 2.0),
                        "r": "spin",
                        "s": (1.0, 0.0, 1.0),
                        "p": (0.0,),
                        "up": (0.0, 1.0),
                        "c": (1.0, 0.5),
                        "lightsize": (-1.0,),
                        "shadowresolution": (8192, 8192),
                        "bgcolor": (1.0, 0.5),
                        "wcolor": (1.0, 0.5),
                        "scale": "large",
                        "roll": "roll",
                        "pos": -0.5,
                        "bank": "bank",
                        "dimmer": -0.1,
                        "coneangle": 360,
                        "conedelta": -1,
                        "coneroll": 11,
                        "attenuationstart": -1,
                        "attenuationend": -1,
                        "attenuationexp": -1,
                        "projangle": 360,
                        "maxshadowsoftness": -1,
                        "filtersamples": "lots",
                        "searchsteps": "many",
                        "polygonoffsetfactor": "far",
                        "polygonoffsetunits": "tiny",
                        "orthowidth": 0,
                        "fov": 360,
                        "focal": 0,
                        "aperture": 0,
                        "near": 0,
                        "far": 0,
                        "drawpriority": "front",
                        "pickpriority": "pick",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)
    risk_flags = parameter_risk_flags_for_plan(plan)

    assert sum(1 for issue in issues if issue.code == "param_reference_type_mismatch") >= 9
    assert sum(1 for issue in issues if issue.code == "missing_reference_param") >= 1
    assert sum(1 for issue in issues if issue.code == "invalid_enum_param") >= 18
    assert sum(1 for issue in issues if issue.code == "invalid_bool_param") >= 5
    assert sum(1 for issue in issues if issue.code == "invalid_float_param") >= 6
    assert sum(1 for issue in issues if issue.code == "invalid_int_param") >= 2
    assert sum(1 for issue in issues if issue.code == "param_tuple_size_mismatch") >= 8
    assert sum(1 for issue in issues if issue.code == "param_out_of_range") >= 15
    assert "param-semantics:high-resolution:lightCOMP.shadowresolution" in risk_flags


def test_pbr_and_phong_material_texture_sampling_and_shader_output_params_have_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    pbr_expected = {
        ("pbrMAT", "basecolor"),
        ("pbrMAT", "alphafront"),
        ("pbrMAT", "specularlevel"),
        ("pbrMAT", "metallic"),
        ("pbrMAT", "roughness"),
        ("pbrMAT", "basecolormap"),
        ("pbrMAT", "basecolormapextendu"),
        ("pbrMAT", "basecolormapextendv"),
        ("pbrMAT", "basecolormapextendw"),
        ("pbrMAT", "basecolormapfilter"),
        ("pbrMAT", "basecolormapanisotropy"),
        ("pbrMAT", "texturesamplingmode"),
        ("pbrMAT", "basecolormapcoord"),
        ("pbrMAT", "basecolormapcoordinterp"),
        ("pbrMAT", "basecolormapcoordattrib"),
        ("pbrMAT", "roughnessmap"),
        ("pbrMAT", "roughnessmapchannelsource"),
        ("pbrMAT", "metallicmap"),
        ("pbrMAT", "metallicmapchannelsource"),
        ("pbrMAT", "normalmap"),
        ("pbrMAT", "heightmapenable"),
        ("pbrMAT", "heightmap"),
        ("pbrMAT", "parallaxscale"),
        ("pbrMAT", "parallaxocclusion"),
        ("pbrMAT", "outputshader"),
    }
    phong_expected = {
        ("phongMAT", "ambdiff"),
        ("phongMAT", "diff"),
        ("phongMAT", "amb"),
        ("phongMAT", "spec"),
        ("phongMAT", "emit"),
        ("phongMAT", "shininess"),
        ("phongMAT", "alphafront"),
        ("phongMAT", "colormap"),
        ("phongMAT", "colormapextendu"),
        ("phongMAT", "colormapextendv"),
        ("phongMAT", "colormapextendw"),
        ("phongMAT", "colormapfilter"),
        ("phongMAT", "colormapanisotropy"),
        ("phongMAT", "texturesamplingmode"),
        ("phongMAT", "colormapcoord"),
        ("phongMAT", "colormapcoordinterp"),
        ("phongMAT", "colormapcoordattrib"),
        ("phongMAT", "normalmap"),
        ("phongMAT", "normalmapsamplingmode"),
        ("phongMAT", "heightmapenable"),
        ("phongMAT", "heightmap"),
        ("phongMAT", "parallaxscale"),
        ("phongMAT", "parallaxocclusion"),
        ("phongMAT", "envmap"),
        ("phongMAT", "outputshader"),
    }

    missing = (pbr_expected | phong_expected) - set(by_key)
    assert missing == set()
    assert all(by_key[key].official_source == "https://docs.derivative.ca/PBR_MAT" for key in pbr_expected)
    assert all(
        by_key[key].official_source == "https://docs.derivative.ca/Phong_MAT" for key in phong_expected
    )

    plan = _plan_with_ops(
        [
            PatchOperation(kind="create_node", target="/project1", args={"op_type": "pbrMAT", "name": "pbr"}),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "phongMAT", "name": "phong"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "texture"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "shader_dat"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "baseCOMP", "name": "not_a_texture"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/pbr",
                args={
                    "params": {
                        "basecolor": (1.0, 0.5),
                        "alphafront": 2.0,
                        "specularlevel": -0.1,
                        "metallic": "metal",
                        "roughness": 2.0,
                        "basecolormap": "/project1/not_a_texture",
                        "roughnessmap": "/project1/not_a_texture",
                        "metallicmap": "/project1/not_a_texture",
                        "normalmap": "/project1/not_a_texture",
                        "heightmapenable": "yes",
                        "heightmap": 123,
                        "parallaxocclusion": "yes",
                        "basecolormapextendu": "Clamp",
                        "basecolormapextendv": "Wrap",
                        "basecolormapextendw": "Clamp",
                        "basecolormapfilter": "Bicubic",
                        "basecolormapanisotropy": "64x",
                        "texturesamplingmode": "Object Space",
                        "basecolormapcoord": "uv9",
                        "basecolormapcoordinterp": "Smooth",
                        "roughnessmapchannelsource": "Value",
                        "metallicmapchannelsource": "Value",
                        "basecolormapcoordattrib": "",
                        "outputshader": "yes",
                        "parallaxscale": "tall",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/phong",
                args={
                    "params": {
                        "ambdiff": "yes",
                        "diff": (1.0, 0.5),
                        "amb": (1.0, 0.5),
                        "spec": (1.0, 0.5, 2.0),
                        "emit": (1.0, 0.5),
                        "shininess": "glossy",
                        "alphafront": -0.1,
                        "colormap": "/project1/not_a_texture",
                        "normalmap": "/project1/not_a_texture",
                        "heightmapenable": "yes",
                        "heightmap": 123,
                        "parallaxocclusion": "yes",
                        "envmap": "/project1/not_a_texture",
                        "colormapextendu": "Clamp",
                        "colormapextendv": "Wrap",
                        "colormapextendw": "Clamp",
                        "colormapfilter": "Bicubic",
                        "colormapanisotropy": "64x",
                        "texturesamplingmode": "Object Space",
                        "colormapcoord": "uv9",
                        "colormapcoordinterp": "Smooth",
                        "normalmapsamplingmode": "Object Space",
                        "colormapcoordattrib": "",
                        "outputshader": "yes",
                        "parallaxscale": "tall",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert sum(1 for issue in issues if issue.code == "param_reference_type_mismatch") >= 7
    assert sum(1 for issue in issues if issue.code == "missing_reference_param") >= 2
    assert sum(1 for issue in issues if issue.code == "invalid_enum_param") >= 18
    assert sum(1 for issue in issues if issue.code == "invalid_bool_param") >= 3
    assert sum(1 for issue in issues if issue.code == "invalid_float_param") >= 4
    assert sum(1 for issue in issues if issue.code == "param_tuple_size_mismatch") >= 4
    assert sum(1 for issue in issues if issue.code == "param_out_of_range") >= 5
    assert sum(1 for issue in issues if issue.code == "empty_path_param") >= 2


def test_camera_pbr_and_phong_params_require_compatible_refs_menus_and_numeric_values():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "cameraCOMP", "name": "camera"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "pbrMAT", "name": "pbr"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "phongMAT", "name": "phong"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullTOP", "name": "not_comp_sop_or_dat"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "textDAT", "name": "not_a_top"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/camera",
                args={
                    "params": {
                        "lookat": "/project1/not_a_top",
                        "pathsop": "/project1/not_comp_sop_or_dat",
                        "projection": "Fisheye",
                        "fov": "wide",
                        "near": "close",
                        "far": "distant",
                        "customproj": "/project1/not_comp_sop_or_dat",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/pbr",
                args={
                    "params": {
                        "basecolor": (1.0, 0.5),
                        "metallic": "metal",
                        "roughness": "rough",
                        "basecolormap": "/project1/not_a_top",
                        "roughnessmap": "/project1/not_a_top",
                        "metallicmap": "/project1/not_a_top",
                        "normalmap": "/project1/not_a_top",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/phong",
                args={
                    "params": {
                        "diff": (1.0, 0.5),
                        "spec": (1.0, 1.0, 2.0),
                        "shininess": "glossy",
                        "colormap": "/project1/not_a_top",
                        "diffusemap": "/project1/not_a_top",
                        "specmap": "/project1/not_a_top",
                        "normalmap": "/project1/not_a_top",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert sum(1 for issue in issues if issue.code == "param_reference_type_mismatch") == 11
    assert any(issue.code == "invalid_enum_param" and issue.path == "/project1/camera" for issue in issues)
    assert sum(1 for issue in issues if issue.code == "invalid_float_param") == 6
    assert sum(1 for issue in issues if issue.code == "param_tuple_size_mismatch") == 2
    assert any(issue.code == "param_out_of_range" and issue.path == "/project1/phong" for issue in issues)


def test_transform_and_cache_top_params_require_known_shapes_and_numeric_values():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "transformTOP", "name": "warp"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "cacheTOP", "name": "history"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/warp",
                args={
                    "params": {
                        "xord": "Spin Translate",
                        "t": (0.1, 0.2, 0.3),
                        "rotate": "fast",
                        "s": (1.0,),
                        "p": "center",
                        "bgcolor": (0.0, 0.0, 0.0),
                        "extend": "Infinite",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/history",
                args={
                    "params": {
                        "active": "yes",
                        "cachesize": 4.5,
                        "step": "every frame-ish",
                        "outputindex": "latest",
                        "interp": "blend",
                        "reset": 2,
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert sum(1 for issue in issues if issue.code == "invalid_enum_param") == 2
    assert sum(1 for issue in issues if issue.code == "param_tuple_size_mismatch") == 4
    assert any(issue.code == "invalid_float_param" and issue.path == "/project1/warp" for issue in issues)
    assert sum(1 for issue in issues if issue.code == "invalid_bool_param") == 3
    assert sum(1 for issue in issues if issue.code == "invalid_int_param") == 2
    assert any(issue.code == "invalid_float_param" and issue.path == "/project1/history" for issue in issues)


def test_feedback_top_processing_params_have_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected_by_source = {
        "https://docs.derivative.ca/Feedback_TOP": {
            ("feedbackTOP", "top"),
            ("feedbackTOP", "reset"),
            ("feedbackTOP", "resetpulse"),
            ("feedbackTOP", "outputresolution"),
            ("feedbackTOP", "resolution"),
            ("feedbackTOP", "resmult"),
            ("feedbackTOP", "npasses"),
        },
        "https://docs.derivative.ca/Level_TOP": {
            ("levelTOP", "clampinput"),
            ("levelTOP", "invert"),
            ("levelTOP", "blacklevel"),
            ("levelTOP", "brightness1"),
            ("levelTOP", "gamma1"),
            ("levelTOP", "contrast"),
            ("levelTOP", "inlow"),
            ("levelTOP", "inhigh"),
            ("levelTOP", "outlow"),
            ("levelTOP", "outhigh"),
            ("levelTOP", "stepping"),
            ("levelTOP", "stepsize"),
            ("levelTOP", "threshold"),
            ("levelTOP", "opacity"),
            ("levelTOP", "clamp"),
            ("levelTOP", "premultrgbbyalpha"),
        },
        "https://docs.derivative.ca/Composite_TOP": {
            ("compositeTOP", "top"),
            ("compositeTOP", "previewgrid"),
            ("compositeTOP", "selectinput"),
            ("compositeTOP", "inputindex"),
            ("compositeTOP", "operand"),
            ("compositeTOP", "swaporder"),
            ("compositeTOP", "size"),
            ("compositeTOP", "prefit"),
            ("compositeTOP", "justifyh"),
            ("compositeTOP", "justifyv"),
            ("compositeTOP", "extend"),
            ("compositeTOP", "r"),
            ("compositeTOP", "t"),
            ("compositeTOP", "s"),
            ("compositeTOP", "p"),
            ("compositeTOP", "legacyxform"),
        },
    }

    for official_source, expected in expected_by_source.items():
        missing = expected - set(by_key)
        assert missing == set()
        assert all(by_key[key].official_source == official_source for key in expected)

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "feedbackTOP", "name": "feedback"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "levelTOP", "name": "level"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "compositeTOP", "name": "composite"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "textDAT", "name": "not_a_top"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/feedback",
                args={
                    "params": {
                        "top": "/project1/not_a_top",
                        "reset": "yes",
                        "outputresolution": "huge",
                        "resolution": (1920,),
                        "resmult": "maybe",
                        "npasses": 0,
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/level",
                args={
                    "params": {
                        "clampinput": "overclamped",
                        "invert": "yes",
                        "blacklevel": "dark",
                        "opacity": 1.25,
                        "stepping": "on",
                        "stepsize": -0.25,
                        "premultrgbbyalpha": "alpha-ish",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/composite",
                args={
                    "params": {
                        "top": "/project1/not_a_top",
                        "previewgrid": "sure",
                        "inputindex": "first",
                        "operand": "teleport",
                        "size": "input3",
                        "prefit": "squish",
                        "justifyh": "middle",
                        "t": (0.0, 0.0, 0.0),
                        "legacyxform": "legacy",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)
    by_path = {}
    for issue in issues:
        by_path.setdefault(issue.path, set()).add(issue.code)

    assert {
        "param_reference_type_mismatch",
        "invalid_bool_param",
        "invalid_enum_param",
        "param_tuple_size_mismatch",
        "param_out_of_range",
    }.issubset(by_path["/project1/feedback"])
    assert {
        "invalid_enum_param",
        "invalid_bool_param",
        "invalid_float_param",
        "param_out_of_range",
    }.issubset(by_path["/project1/level"])
    assert {
        "param_reference_type_mismatch",
        "invalid_bool_param",
        "invalid_int_param",
        "invalid_enum_param",
        "param_tuple_size_mismatch",
    }.issubset(by_path["/project1/composite"])


def test_op_execute_dat_params_have_docs_grounded_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}

    for key in {
        ("opexecuteDAT", "op"),
        ("opexecuteDAT", "executeloc"),
        ("opexecuteDAT", "fromop"),
        ("opexecuteDAT", "precook"),
        ("opexecuteDAT", "postcook"),
        ("opexecuteDAT", "opdelete"),
        ("opexecuteDAT", "flagchange"),
        ("opexecuteDAT", "wirechange"),
        ("opexecuteDAT", "namechange"),
        ("opexecuteDAT", "pathchange"),
        ("opexecuteDAT", "uichange"),
        ("opexecuteDAT", "numchildrenchange"),
        ("opexecuteDAT", "childrename"),
        ("opexecuteDAT", "currentchildchange"),
        ("opexecuteDAT", "extensionchange"),
    }:
        assert key in by_key
        assert by_key[key].official_source == "https://docs.derivative.ca/OP_Execute_DAT"

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "opexecuteDAT", "name": "op_exec"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/op_exec",
                args={
                    "params": {
                        "op": "",
                        "executeloc": "Somewhere Else",
                        "precook": "yes",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert any(
        issue.code == "missing_reference_param" and issue.path == "/project1/op_exec" for issue in issues
    )
    assert any(issue.code == "invalid_enum_param" and issue.path == "/project1/op_exec" for issue in issues)
    assert any(issue.code == "invalid_bool_param" and issue.path == "/project1/op_exec" for issue in issues)


def test_parameter_panel_and_pargroup_execute_dat_params_have_semantics():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected_sources = {
        "parameterexecuteDAT": "https://docs.derivative.ca/Parameter_Execute_DAT",
        "panelexecuteDAT": "https://docs.derivative.ca/Panel_Execute_DAT",
        "pargroupexecuteDAT": "https://docs.derivative.ca/ParGroup_Execute_DAT",
    }

    for key in {
        ("parameterexecuteDAT", "op"),
        ("parameterexecuteDAT", "pars"),
        ("parameterexecuteDAT", "executeloc"),
        ("parameterexecuteDAT", "fromop"),
        ("parameterexecuteDAT", "valuechange"),
        ("parameterexecuteDAT", "valueschanged"),
        ("parameterexecuteDAT", "onpulse"),
        ("parameterexecuteDAT", "expressionchange"),
        ("parameterexecuteDAT", "exportchange"),
        ("parameterexecuteDAT", "enablechange"),
        ("parameterexecuteDAT", "modechange"),
        ("parameterexecuteDAT", "custom"),
        ("parameterexecuteDAT", "builtin"),
        ("panelexecuteDAT", "panels"),
        ("panelexecuteDAT", "panelvalue"),
        ("panelexecuteDAT", "executeloc"),
        ("panelexecuteDAT", "fromop"),
        ("panelexecuteDAT", "offtoon"),
        ("panelexecuteDAT", "whileon"),
        ("panelexecuteDAT", "ontooff"),
        ("panelexecuteDAT", "whileoff"),
        ("panelexecuteDAT", "valuechange"),
        ("pargroupexecuteDAT", "op"),
        ("pargroupexecuteDAT", "pars"),
        ("pargroupexecuteDAT", "callbackmode"),
        ("pargroupexecuteDAT", "valuechange"),
        ("pargroupexecuteDAT", "onpulse"),
        ("pargroupexecuteDAT", "expressionchange"),
        ("pargroupexecuteDAT", "exportchange"),
        ("pargroupexecuteDAT", "enablechange"),
        ("pargroupexecuteDAT", "modechange"),
        ("pargroupexecuteDAT", "custom"),
        ("pargroupexecuteDAT", "builtin"),
    }:
        assert key in by_key
        assert by_key[key].official_source == expected_sources[key[0]]

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "parameterexecuteDAT", "name": "par_exec"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "panelexecuteDAT", "name": "panel_exec"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "pargroupexecuteDAT", "name": "group_exec"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullTOP", "name": "not_a_panel"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/par_exec",
                args={"params": {"op": "", "valuechange": "yes"}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/panel_exec",
                args={"params": {"panels": "/project1/not_a_panel", "whileon": "yes"}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/group_exec",
                args={"params": {"callbackmode": "one at a time", "valuechange": "yes"}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert any(
        issue.code == "missing_reference_param" and issue.path == "/project1/par_exec" for issue in issues
    )
    assert any(
        issue.code == "param_reference_type_mismatch" and issue.path == "/project1/panel_exec"
        for issue in issues
    )
    assert any(
        issue.code == "invalid_enum_param" and issue.path == "/project1/group_exec" for issue in issues
    )
    assert sum(1 for issue in issues if issue.code == "invalid_bool_param") == 3


def test_dat_and_chop_execute_dat_trigger_params_have_semantics():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected_sources = {
        "datexecuteDAT": "https://docs.derivative.ca/DAT_Execute_DAT",
        "chopexecuteDAT": "https://docs.derivative.ca/CHOP_Execute_DAT",
    }

    for key in {
        ("datexecuteDAT", "active"),
        ("datexecuteDAT", "executeloc"),
        ("datexecuteDAT", "fromop"),
        ("datexecuteDAT", "dat"),
        ("datexecuteDAT", "tablechange"),
        ("datexecuteDAT", "rowchange"),
        ("datexecuteDAT", "colchange"),
        ("datexecuteDAT", "cellchange"),
        ("datexecuteDAT", "sizechange"),
        ("datexecuteDAT", "execute"),
        ("chopexecuteDAT", "active"),
        ("chopexecuteDAT", "executeloc"),
        ("chopexecuteDAT", "fromop"),
        ("chopexecuteDAT", "chop"),
        ("chopexecuteDAT", "channel"),
        ("chopexecuteDAT", "offtoon"),
        ("chopexecuteDAT", "whileon"),
        ("chopexecuteDAT", "ontooff"),
        ("chopexecuteDAT", "whileoff"),
        ("chopexecuteDAT", "valuechange"),
        ("chopexecuteDAT", "freq"),
    }:
        assert key in by_key
        assert by_key[key].official_source == expected_sources[key[0]]

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "datexecuteDAT", "name": "dat_exec"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "chopexecuteDAT", "name": "chop_exec"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullTOP", "name": "not_a_dat_or_chop"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/dat_exec",
                args={
                    "params": {
                        "dat": "/project1/not_a_dat_or_chop",
                        "tablechange": "yes",
                        "execute": "middle",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/chop_exec",
                args={
                    "params": {
                        "chop": "/project1/not_a_dat_or_chop",
                        "whileon": "yes",
                        "freq": "sometimes",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert sum(1 for issue in issues if issue.code == "param_reference_type_mismatch") == 2
    assert sum(1 for issue in issues if issue.code == "invalid_bool_param") == 2
    assert sum(1 for issue in issues if issue.code == "invalid_enum_param") == 2


def test_panel_control_params_require_compatible_refs_menus_toggles_and_dimensions():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "baseCOMP", "name": "control_host"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "containerCOMP", "name": "panel"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "sliderCOMP", "name": "amount"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "buttonCOMP", "name": "reset"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "panelCHOP", "name": "panel_reader"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "parameterCOMP", "name": "param_panel"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullTOP", "name": "not_a_comp_or_dat"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "textDAT", "name": "not_a_top"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/control_host",
                args={
                    "params": {
                        "clone": "/project1/not_a_comp_or_dat",
                        "opviewer": "/project1/not_a_comp_or_dat",
                        "enablecloning": "yes",
                        "loadondemand": "sometimes",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/panel",
                args={
                    "params": {
                        "w": "wide",
                        "h": 0,
                        "display": "on",
                        "enable": "enabled",
                        "helpdat": "/project1/not_a_comp_or_dat",
                        "top": "/project1/not_a_top",
                        "opacity": "clear",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/amount",
                args={
                    "params": {
                        "slidertype": "rotary",
                        "value0": "half",
                        "value1": 1.25,
                        "clampul": "yes",
                        "clampuh": 2,
                        "w": "wide",
                        "h": 0,
                        "display": "visible",
                        "enable": "enabled",
                        "opacity": 1.25,
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/reset",
                args={
                    "params": {
                        "buttontype": "sticky",
                        "value0": "pressed",
                        "buttongroupdat": "/project1/not_a_comp_or_dat",
                        "scaletofit": "sometimes",
                        "display": "visible",
                        "enable": "enabled",
                        "opacity": 1.25,
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/panel_reader",
                args={
                    "params": {
                        "component": "/project1/not_a_top",
                        "queue": "maybe",
                        "queuesize": 4.5,
                        "timeslice": "per frame",
                        "exporttable": "/project1/not_a_comp_or_dat",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/param_panel",
                args={
                    "params": {
                        "op": "",
                        "header": "show",
                        "builtin": "include",
                        "custom": "include",
                        "combinescopes": "xor",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert sum(1 for issue in issues if issue.code == "param_reference_type_mismatch") == 6
    assert sum(1 for issue in issues if issue.code == "invalid_enum_param") == 4
    assert sum(1 for issue in issues if issue.code == "invalid_bool_param") >= 14
    assert sum(1 for issue in issues if issue.code == "invalid_int_param") == 3
    assert sum(1 for issue in issues if issue.code == "invalid_float_param") == 2
    assert sum(1 for issue in issues if issue.code == "param_out_of_range") == 5
    assert any(
        issue.code == "missing_reference_param" and issue.path == "/project1/param_panel" for issue in issues
    )


def test_panel_shell_parameter_comp_and_panel_chop_extended_params_have_semantics():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    base_expected = {
        ("baseCOMP", "parentshortcut"),
        ("baseCOMP", "opshortcut"),
        ("baseCOMP", "iop0shortcut"),
        ("baseCOMP", "iop0op"),
        ("baseCOMP", "enablecloningpulse"),
        ("baseCOMP", "enableexternaltox"),
        ("baseCOMP", "enableexternaltoxpulse"),
        ("baseCOMP", "externaltox"),
        ("baseCOMP", "reloadcustom"),
        ("baseCOMP", "reloadbuiltin"),
        ("baseCOMP", "savebackup"),
        ("baseCOMP", "subcompname"),
        ("baseCOMP", "relpath"),
    }
    panel_chop_expected = {
        ("panelCHOP", "select"),
        ("panelCHOP", "rename"),
        ("panelCHOP", "scope"),
        ("panelCHOP", "srselect"),
        ("panelCHOP", "exportmethod"),
        ("panelCHOP", "autoexportroot"),
    }
    parameter_comp_expected = {
        ("parameterCOMP", "pagenames"),
        ("parameterCOMP", "labels"),
        ("parameterCOMP", "separators"),
        ("parameterCOMP", "inputeditor"),
        ("parameterCOMP", "allowexpand"),
        ("parameterCOMP", "pagescope"),
        ("parameterCOMP", "parscope"),
        ("parameterCOMP", "x"),
        ("parameterCOMP", "y"),
        ("parameterCOMP", "w"),
        ("parameterCOMP", "h"),
        ("parameterCOMP", "display"),
        ("parameterCOMP", "enable"),
        ("parameterCOMP", "helpdat"),
        ("parameterCOMP", "top"),
        ("parameterCOMP", "opacity"),
    }

    missing = (base_expected | panel_chop_expected | parameter_comp_expected) - set(by_key)
    assert missing == set()
    assert all(by_key[key].official_source == "https://docs.derivative.ca/Base_COMP" for key in base_expected)
    assert all(
        by_key[key].official_source == "https://docs.derivative.ca/Panel_CHOP" for key in panel_chop_expected
    )
    assert all(
        by_key[key].official_source == "https://docs.derivative.ca/Parameter_COMP"
        for key in parameter_comp_expected
    )

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "baseCOMP", "name": "shell"}
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "parameterCOMP", "name": "parameter_panel"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "panelCHOP", "name": "panel_reader"},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "not_a_dat"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "not_a_top"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/shell",
                args={
                    "params": {
                        "iop0op": "",
                        "enableexternaltox": "yes",
                        "externaltox": "",
                        "reloadcustom": "yes",
                        "reloadbuiltin": "yes",
                        "savebackup": "yes",
                        "relpath": "Moon",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/parameter_panel",
                args={
                    "params": {
                        "pagenames": "yes",
                        "labels": "yes",
                        "separators": "yes",
                        "inputeditor": "yes",
                        "allowexpand": "maybe",
                        "x": "left",
                        "w": 0,
                        "display": "visible",
                        "enable": "enabled",
                        "helpdat": "/project1/not_a_dat",
                        "top": "/project1/not_a_top",
                        "opacity": 1.25,
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/panel_reader",
                args={
                    "params": {
                        "srselect": "Fastest",
                        "exportmethod": "Clipboard",
                        "autoexportroot": "",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)
    by_path = {}
    for issue in issues:
        by_path.setdefault(issue.path, []).append(issue.code)

    assert by_path["/project1/shell"].count("invalid_bool_param") == 4
    assert "invalid_enum_param" in by_path["/project1/shell"]
    assert "empty_path_param" in by_path["/project1/shell"]
    assert "missing_reference_param" in by_path["/project1/shell"]
    assert by_path["/project1/parameter_panel"].count("invalid_bool_param") == 7
    assert by_path["/project1/parameter_panel"].count("invalid_int_param") == 1
    assert by_path["/project1/parameter_panel"].count("param_out_of_range") == 2
    assert by_path["/project1/parameter_panel"].count("param_reference_type_mismatch") == 2
    assert by_path["/project1/panel_reader"].count("invalid_enum_param") == 2
    assert "missing_reference_param" in by_path["/project1/panel_reader"]


def test_glsl_advanced_pop_computedat_requires_dat_reference():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "glsladvancedPOP", "name": "topology_shader"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullPOP", "name": "not_a_dat"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/topology_shader",
                args={"params": {"computedat": "/project1/not_a_dat"}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert any(issue.code == "param_reference_type_mismatch" for issue in issues)


def test_glsl_pop_computedat_and_attribute_class_have_semantics():
    semantics = semantics_by_op_and_param()

    assert ("glslPOP", "computedat") in semantics
    assert ("glslPOP", "attrclass") in semantics

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "glslPOP", "name": "attribute_shader"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullPOP", "name": "not_a_dat"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/attribute_shader",
                args={"params": {"computedat": "/project1/not_a_dat", "attrclass": "edge"}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert any(issue.code == "param_reference_type_mismatch" for issue in issues)
    assert any(issue.code == "invalid_enum_param" for issue in issues)


def test_glsl_pop_thread_dispatch_params_have_semantics_and_preflight_checks():
    semantics = semantics_by_op_and_param()
    expected_params = {
        "numthreadsmode",
        "threadsinput",
        "numelems",
        "numelemspop",
        "numelemsclass",
        "workgroupsizex",
        "workgroupsizey",
        "workgroupsizez",
        "dispatchsizex",
        "dispatchsizey",
        "dispatchsizez",
        "initoutputattrs",
        "prevpassoutput",
        "npasses",
    }

    assert expected_params.issubset({param_name for op_type, param_name in semantics if op_type == "glslPOP"})

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "glslPOP", "name": "attribute_shader"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullTOP", "name": "not_a_pop"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/attribute_shader",
                args={
                    "params": {
                        "numthreadsmode": "telepathy",
                        "threadsinput": True,
                        "numelems": -1,
                        "numelemspop": "/project1/not_a_pop",
                        "numelemsclass": "edge",
                        "workgroupsizex": 0,
                        "workgroupsizey": "wide",
                        "workgroupsizez": -1,
                        "dispatchsizex": 0,
                        "dispatchsizey": "many",
                        "dispatchsizez": -1,
                        "initoutputattrs": "yes",
                        "prevpassoutput": 2,
                        "npasses": 0,
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert sum(1 for issue in issues if issue.code == "invalid_enum_param") == 2
    assert any(issue.code == "param_reference_type_mismatch" for issue in issues)
    assert sum(1 for issue in issues if issue.code == "invalid_int_param") == 3
    assert sum(1 for issue in issues if issue.code == "param_out_of_range") == 6
    assert sum(1 for issue in issues if issue.code == "invalid_bool_param") == 2


def test_glsl_multi_top_params_have_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected = {
        ("glslmultiTOP", "glslversion"),
        ("glslmultiTOP", "mode"),
        ("glslmultiTOP", "predat"),
        ("glslmultiTOP", "vertexdat"),
        ("glslmultiTOP", "pixeldat"),
        ("glslmultiTOP", "computedat"),
        ("glslmultiTOP", "autodispatchsize"),
        ("glslmultiTOP", "dispatchsizex"),
        ("glslmultiTOP", "dispatchsizey"),
        ("glslmultiTOP", "dispatchsizez"),
        ("glslmultiTOP", "outputaccess"),
        ("glslmultiTOP", "type"),
        ("glslmultiTOP", "depth"),
        ("glslmultiTOP", "customdepth"),
        ("glslmultiTOP", "clearoutputs"),
        ("glslmultiTOP", "inputmapping"),
        ("glslmultiTOP", "nval"),
        ("glslmultiTOP", "inputextenduv"),
        ("glslmultiTOP", "inputextendw"),
        ("glslmultiTOP", "numcolorbufs"),
        ("glslmultiTOP", "array0chop"),
        ("glslmultiTOP", "array0type"),
        ("glslmultiTOP", "array0arraytype"),
        ("glslmultiTOP", "ac0chopvalue"),
        ("glslmultiTOP", "ac0initvalue"),
        ("glslmultiTOP", "ac0singlevalue"),
        ("glslmultiTOP", "const0value"),
        ("glslmultiTOP", "resolutionw"),
        ("glslmultiTOP", "resolutionh"),
        ("glslmultiTOP", "resmult"),
        ("glslmultiTOP", "npasses"),
    }

    missing = expected - set(by_key)
    assert missing == set()
    assert all(by_key[key].official_source == "https://docs.derivative.ca/GLSL_Multi_TOP" for key in expected)

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glslmultiTOP", "name": "shader"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "shader_text"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "not_a_dat"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "mathCHOP", "name": "control"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/shader",
                args={
                    "params": {
                        "pixeldat": "/project1/not_a_dat",
                        "array0chop": "/project1/not_a_dat",
                        "mode": "Particle Shader",
                        "outputaccess": "Read Everything",
                        "type": "Cube Texture",
                        "autodispatchsize": "yes",
                        "dispatchsizex": 0,
                        "dispatchsizey": "many",
                        "customdepth": "deep",
                        "nval": 0,
                        "numcolorbufs": "lots",
                        "resmult": "maybe",
                        "npasses": 0,
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert sum(1 for issue in issues if issue.code == "param_reference_type_mismatch") == 2
    assert sum(1 for issue in issues if issue.code == "invalid_enum_param") == 3
    assert sum(1 for issue in issues if issue.code == "invalid_bool_param") == 2
    assert sum(1 for issue in issues if issue.code == "invalid_int_param") == 3
    assert sum(1 for issue in issues if issue.code == "param_out_of_range") == 3


def test_glsl_comp_params_have_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected = {
        ("glslCOMP", "vertexdat"),
        ("glslCOMP", "pixeldat"),
        ("glslCOMP", "sampler0top"),
        ("glslCOMP", "sampler0extendu"),
        ("glslCOMP", "sampler0extendv"),
        ("glslCOMP", "sampler0extendw"),
        ("glslCOMP", "sampler0filter"),
        ("glslCOMP", "sampler0anisotropy"),
        ("glslCOMP", "vec0value"),
        ("glslCOMP", "const0value"),
        ("glslCOMP", "x"),
        ("glslCOMP", "y"),
        ("glslCOMP", "w"),
        ("glslCOMP", "h"),
        ("glslCOMP", "fixedaspect"),
        ("glslCOMP", "aspect"),
        ("glslCOMP", "layer"),
        ("glslCOMP", "hmode"),
        ("glslCOMP", "vmode"),
        ("glslCOMP", "display"),
        ("glslCOMP", "enable"),
        ("glslCOMP", "helpdat"),
        ("glslCOMP", "top"),
        ("glslCOMP", "opacity"),
        ("glslCOMP", "opviewer"),
        ("glslCOMP", "clone"),
        ("glslCOMP", "enablecloning"),
        ("glslCOMP", "loadondemand"),
    }

    missing = expected - set(by_key)
    assert missing == set()
    assert all(by_key[key].official_source == "https://docs.derivative.ca/GLSL_COMP" for key in expected)

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "glslCOMP", "name": "panel_shader"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "shader_text"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "source_top"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "baseCOMP", "name": "panel_shell"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/panel_shader",
                args={
                    "params": {
                        "vertexdat": "/project1/source_top",
                        "sampler0top": "/project1/shader_text",
                        "sampler0extendu": "Wrap Forever",
                        "sampler0filter": "Bicubic",
                        "sampler0anisotropy": "64x",
                        "vec0value": (0.1, 0.2, 0.3),
                        "w": 0,
                        "h": "tall",
                        "fixedaspect": "Golden",
                        "aspect": "wide",
                        "display": "visible",
                        "helpdat": "/project1/source_top",
                        "top": "/project1/shader_text",
                        "opacity": 1.25,
                        "clone": "/project1/source_top",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert sum(1 for issue in issues if issue.code == "param_reference_type_mismatch") == 5
    assert sum(1 for issue in issues if issue.code == "invalid_enum_param") == 4
    assert any(issue.code == "param_tuple_size_mismatch" for issue in issues)
    assert sum(1 for issue in issues if issue.code == "param_out_of_range") == 2
    assert any(issue.code == "invalid_int_param" for issue in issues)
    assert any(issue.code == "invalid_float_param" for issue in issues)
    assert any(issue.code == "invalid_bool_param" for issue in issues)


def test_glsl_advanced_pop_large_topology_capacity_is_flagged_without_blocking():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "glsladvancedPOP", "name": "topology_shader"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "textDAT", "name": "compute_shader"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/topology_shader",
                args={
                    "params": {
                        "computedat": "/project1/compute_shader",
                        "maxpoints": 2_000_000,
                        "maxtriangles": 1_500_000,
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)
    risk_flags = parameter_risk_flags_for_plan(plan)

    assert issues == []
    assert "param-semantics:large-pop-capacity:glsladvancedPOP.maxpoints" in risk_flags
    assert "param-semantics:large-pop-capacity:glsladvancedPOP.maxtriangles" in risk_flags


def test_glsl_advanced_pop_negative_topology_capacity_blocks():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "glsladvancedPOP", "name": "topology_shader"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "textDAT", "name": "compute_shader"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/topology_shader",
                args={"params": {"computedat": "/project1/compute_shader", "maxpoints": -1}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert any(issue.code == "param_out_of_range" for issue in issues)


def test_pop_generator_and_attribute_processing_params_have_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected_by_source = {
        "https://docs.derivative.ca/Circle_POP": {
            ("circlePOP", "connectivity"),
            ("circlePOP", "orient"),
            ("circlePOP", "modifybounds"),
            ("circlePOP", "rad"),
            ("circlePOP", "divs"),
            ("circlePOP", "closed"),
            ("circlePOP", "angle"),
            ("circlePOP", "t"),
            ("circlePOP", "r"),
            ("circlePOP", "scale"),
            ("circlePOP", "normal"),
            ("circlePOP", "tangent"),
            ("circlePOP", "texture"),
            ("circlePOP", "bypass"),
            ("circlePOP", "delinputattrs"),
        },
        "https://docs.derivative.ca/Noise_POP": {
            ("noisePOP", "type"),
            ("noisePOP", "noisesize"),
            ("noisePOP", "harmon"),
            ("noisePOP", "period"),
            ("noisePOP", "spread"),
            ("noisePOP", "gain"),
            ("noisePOP", "amp"),
            ("noisePOP", "exp"),
            ("noisePOP", "attrclass"),
            ("noisePOP", "xord"),
            ("noisePOP", "rord"),
            ("noisePOP", "t"),
            ("noisePOP", "r"),
            ("noisePOP", "s"),
            ("noisePOP", "p"),
            ("noisePOP", "t4d"),
            ("noisePOP", "noise"),
            ("noisePOP", "gradient"),
            ("noisePOP", "curl3d"),
            ("noisePOP", "curl2d"),
            ("noisePOP", "combineop"),
            ("noisePOP", "combineentity"),
            ("noisePOP", "attrnumcomps"),
            ("noisePOP", "computenormals"),
            ("noisePOP", "mode"),
            ("noisePOP", "map0op"),
            ("noisePOP", "map0parm"),
            ("noisePOP", "map0combineop"),
            ("noisePOP", "bypass"),
            ("noisePOP", "delinputattrs"),
        },
        "https://docs.derivative.ca/Math_Mix_POP": {
            ("mathmixPOP", "lengthmismatchnotif"),
            ("mathmixPOP", "input0pop"),
            ("mathmixPOP", "attrclass"),
            ("mathmixPOP", "angleunit"),
            ("mathmixPOP", "vec0type"),
            ("mathmixPOP", "vec0value"),
            ("mathmixPOP", "premultcolor"),
            ("mathmixPOP", "color0rgb"),
            ("mathmixPOP", "color0alpha"),
            ("mathmixPOP", "comb0oper"),
            ("mathmixPOP", "delnewattrs"),
            ("mathmixPOP", "bypass"),
            ("mathmixPOP", "delinputattrs"),
        },
        "https://docs.derivative.ca/Attribute_Combine_POP": {
            ("attributecombinePOP", "attrclass"),
            ("attributecombinePOP", "lengthmismatchnotif"),
            ("attributecombinePOP", "duplicateattrs"),
            ("attributecombinePOP", "input0pop"),
            ("attributecombinePOP", "input0attrs"),
            ("attributecombinePOP", "input0renameto"),
            ("attributecombinePOP", "bypass"),
            ("attributecombinePOP", "delinputattrs"),
        },
    }

    for official_source, expected in expected_by_source.items():
        missing = expected - set(by_key)
        assert missing == set()
        assert all(by_key[key].official_source == official_source for key in expected)

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "circlePOP", "name": "circle"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "noisePOP", "name": "noise"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "mathmixPOP", "name": "mix"}
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "attributecombinePOP", "name": "combine"},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "not_a_pop"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullPOP", "name": "pop_in"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/circle",
                args={
                    "params": {
                        "connectivity": "mesh",
                        "orient": "XYZ",
                        "modifybounds": "yes",
                        "rad": (1.0,),
                        "divs": 0,
                        "closed": "sometimes",
                        "t": (0.0, 0.0),
                        "normal": "edge",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/noise",
                args={
                    "params": {
                        "type": "cloud",
                        "noisesize": "5",
                        "harmon": -1,
                        "period": "wide",
                        "attrclass": "edge",
                        "t": (0.0, 0.0),
                        "noise": "on",
                        "combineop": "blend",
                        "mode": "fast",
                        "map0op": "/project1/not_a_pop",
                        "map0combineop": "blend",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/mix",
                args={
                    "params": {
                        "input0pop": "/project1/not_a_pop",
                        "attrclass": "edge",
                        "angleunit": "turns",
                        "vec0type": "float5",
                        "vec0value": (1.0, 2.0, 3.0),
                        "premultcolor": "yes",
                        "color0rgb": (1.0, 0.5, 2.0),
                        "color0alpha": 2.0,
                        "comb0oper": "teleport",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/combine",
                args={
                    "params": {
                        "attrclass": "edge",
                        "lengthmismatchnotif": "loud",
                        "duplicateattrs": "merge",
                        "input0pop": "/project1/not_a_pop",
                        "bypass": "pass",
                        "delinputattrs": "delete",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)
    by_path = {}
    for issue in issues:
        by_path.setdefault(issue.path, set()).add(issue.code)

    assert {
        "invalid_enum_param",
        "invalid_bool_param",
        "param_tuple_size_mismatch",
        "param_out_of_range",
    }.issubset(by_path["/project1/circle"])
    assert {
        "invalid_enum_param",
        "invalid_bool_param",
        "invalid_float_param",
        "param_tuple_size_mismatch",
    }.issubset(by_path["/project1/noise"])
    assert "param_reference_type_mismatch" in by_path["/project1/noise"]
    assert {"param_reference_type_mismatch", "invalid_enum_param", "param_tuple_size_mismatch"}.issubset(
        by_path["/project1/mix"]
    )
    assert {"param_reference_type_mismatch", "invalid_enum_param", "invalid_bool_param"}.issubset(
        by_path["/project1/combine"]
    )


def test_render_simple_top_params_have_docs_grounded_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected = {
        ("rendersimpleTOP", "ortho"),
        ("rendersimpleTOP", "fov"),
        ("rendersimpleTOP", "orthowidth"),
        ("rendersimpleTOP", "camdistance"),
        ("rendersimpleTOP", "normalizegeo"),
        ("rendersimpleTOP", "bgcolor"),
        ("rendersimpleTOP", "pop"),
        ("rendersimpleTOP", "geotranslate"),
        ("rendersimpleTOP", "georotate"),
        ("rendersimpleTOP", "geoscale"),
        ("rendersimpleTOP", "materialsource"),
        ("rendersimpleTOP", "wireframe"),
        ("rendersimpleTOP", "constant"),
        ("rendersimpleTOP", "diffuse"),
        ("rendersimpleTOP", "colormap"),
        ("rendersimpleTOP", "mat"),
        ("rendersimpleTOP", "outputresolution"),
        ("rendersimpleTOP", "resolution"),
        ("rendersimpleTOP", "resmult"),
        ("rendersimpleTOP", "npasses"),
    }

    missing = expected - set(by_key)
    assert missing == set()
    assert all(
        by_key[key].official_source == "https://docs.derivative.ca/Render_Simple_TOP" for key in expected
    )

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "rendersimpleTOP", "name": "preview"}
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullTOP", "name": "not_a_pop_or_mat"},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "not_a_top"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/preview",
                args={
                    "params": {
                        "pop": "/project1/not_a_pop_or_mat",
                        "ortho": "yes",
                        "fov": "wide",
                        "orthowidth": -1,
                        "camdistance": -2,
                        "normalizegeo": 2,
                        "bgcolor": (1.0, 0.0, 0.0),
                        "geotranslate": (0.0, 0.0),
                        "georotate": "spin",
                        "geoscale": -1,
                        "materialsource": "magic",
                        "wireframe": "maybe",
                        "constant": (1.0, 0.0),
                        "diffuse": (1.2, 0.5, 0.5),
                        "colormap": "/project1/not_a_top",
                        "mat": "/project1/not_a_pop_or_mat",
                        "outputresolution": "enormous",
                        "resolution": (1920,),
                        "resmult": "sometimes",
                        "npasses": 0,
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)
    by_path = {}
    for issue in issues:
        by_path.setdefault(issue.path, set()).add(issue.code)

    assert {
        "param_reference_type_mismatch",
        "invalid_bool_param",
        "invalid_float_param",
        "invalid_enum_param",
        "param_tuple_size_mismatch",
        "param_out_of_range",
    }.issubset(by_path["/project1/preview"])


def test_dat_execute_dat_reference_requires_dat_target():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "datexecuteDAT", "name": "table_change_exec"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullTOP", "name": "not_a_dat"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/table_change_exec",
                args={"params": {"dat": "/project1/not_a_dat"}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert any(issue.code == "invalid_reference_param" for issue in issues)


def test_serial_dat_callbacks_param_requires_dat_reference():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "serialDAT", "name": "serial_in"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullTOP", "name": "not_a_dat"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/serial_in",
                args={"params": {"callbacks": "/project1/not_a_dat"}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert any(issue.code == "param_reference_type_mismatch" for issue in issues)


def test_serial_dat_connection_and_output_params_have_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected = {
        ("serialDAT", "active"),
        ("serialDAT", "format"),
        ("serialDAT", "port"),
        ("serialDAT", "baudrate"),
        ("serialDAT", "databits"),
        ("serialDAT", "parity"),
        ("serialDAT", "stopbits"),
        ("serialDAT", "dtr"),
        ("serialDAT", "rts"),
        ("serialDAT", "callbacks"),
        ("serialDAT", "executeloc"),
        ("serialDAT", "fromop"),
        ("serialDAT", "clamp"),
        ("serialDAT", "maxlines"),
        ("serialDAT", "clear"),
        ("serialDAT", "bytes"),
    }

    missing = expected - set(by_key)
    assert missing == set()
    assert all(by_key[key].official_source == "https://docs.derivative.ca/Serial_DAT" for key in expected)

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "serialDAT", "name": "serial_in"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/serial_in",
                args={
                    "params": {
                        "active": "yes",
                        "format": "paragraph",
                        "baudrate": "fast",
                        "databits": "10",
                        "parity": "maybe",
                        "stopbits": "1.5",
                        "dtr": "auto",
                        "rts": "auto",
                        "executeloc": "Nowhere",
                        "fromop": "",
                        "clamp": "sure",
                        "maxlines": "many",
                        "bytes": "raw",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)
    codes = {issue.code for issue in issues if issue.path == "/project1/serial_in"}

    assert {
        "invalid_bool_param",
        "invalid_enum_param",
        "invalid_int_param",
        "missing_reference_param",
    }.issubset(codes)


def test_chop_execute_dat_params_require_chop_target_and_known_menus():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "chopexecuteDAT", "name": "chop_exec"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullTOP", "name": "not_a_chop"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/chop_exec",
                args={
                    "params": {
                        "chop": "/project1/not_a_chop",
                        "executeloc": "Nowhere",
                        "freq": "Every Century",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    enum_issues = [issue for issue in issues if issue.code == "invalid_enum_param"]
    assert len(enum_issues) == 2
    assert any(
        issue.code == "param_reference_type_mismatch" and issue.path == "/project1/chop_exec"
        for issue in issues
    )


def test_execute_dat_fromop_requires_operator_reference_and_known_execute_location():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "executeDAT", "name": "project_exec"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/project_exec",
                args={"params": {"executeloc": "Nowhere", "fromop": ""}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert any(
        issue.code == "invalid_enum_param" and issue.path == "/project1/project_exec" for issue in issues
    )
    assert any(
        issue.code == "missing_reference_param" and issue.path == "/project1/project_exec" for issue in issues
    )


def test_execute_dat_event_and_file_params_have_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    semantics = {(item.op_type, item.name): item for item in registry}
    expected = {
        ("executeDAT", "active"),
        ("executeDAT", "start"),
        ("executeDAT", "create"),
        ("executeDAT", "exit"),
        ("executeDAT", "framestart"),
        ("executeDAT", "frameend"),
        ("executeDAT", "playstatechange"),
        ("executeDAT", "devicechange"),
        ("executeDAT", "edit"),
        ("executeDAT", "file"),
        ("executeDAT", "syncfile"),
        ("executeDAT", "loadonstart"),
        ("executeDAT", "loadonstartpulse"),
        ("executeDAT", "write"),
        ("executeDAT", "writepulse"),
    }

    assert expected <= semantics.keys()
    assert {semantics[key].official_source for key in expected} == {"https://docs.derivative.ca/Execute_DAT"}

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "executeDAT", "name": "project_exec"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/project_exec",
                args={
                    "params": {
                        "active": "yes",
                        "start": "yes",
                        "create": "yes",
                        "exit": "yes",
                        "framestart": "yes",
                        "frameend": "yes",
                        "playstatechange": "yes",
                        "devicechange": "yes",
                        "file": "",
                        "syncfile": "yes",
                        "loadonstart": "yes",
                        "write": "yes",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert sum(1 for issue in issues if issue.code == "invalid_bool_param") == 11
    assert any(
        issue.code == "empty_path_param" and issue.path == "/project1/project_exec" for issue in issues
    )


def test_network_dat_callbacks_require_dat_reference_and_known_protocol_menus():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "oscinDAT", "name": "osc_in"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "websocketDAT", "name": "websocket_in"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullTOP", "name": "not_a_dat"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/osc_in",
                args={
                    "params": {
                        "callbacks": "/project1/not_a_dat",
                        "protocol": "Carrier Signal",
                        "executeloc": "Nowhere",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/websocket_in",
                args={"params": {"callbacks": "/project1/not_a_dat", "executeloc": "Nowhere"}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    enum_issues = [issue for issue in issues if issue.code == "invalid_enum_param"]
    ref_issues = [issue for issue in issues if issue.code == "param_reference_type_mismatch"]
    assert len(enum_issues) == 3
    assert len(ref_issues) == 2


def test_network_dat_connection_output_params_have_docs_grounded_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    osc_expected = {
        ("oscinDAT", "active"),
        ("oscinDAT", "address"),
        ("oscinDAT", "port"),
        ("oscinDAT", "localaddress"),
        ("oscinDAT", "shared"),
        ("oscinDAT", "addscope"),
        ("oscinDAT", "typetag"),
        ("oscinDAT", "splitbundle"),
        ("oscinDAT", "splitmessage"),
        ("oscinDAT", "bundletimestamp"),
        ("oscinDAT", "clamp"),
        ("oscinDAT", "maxlines"),
        ("oscinDAT", "clear"),
        ("oscinDAT", "bytes"),
    }
    websocket_expected = {
        ("websocketDAT", "active"),
        ("websocketDAT", "netaddress"),
        ("websocketDAT", "port"),
        ("websocketDAT", "timeout"),
        ("websocketDAT", "clamp"),
        ("websocketDAT", "maxlines"),
        ("websocketDAT", "clear"),
        ("websocketDAT", "bytes"),
    }
    webclient_expected = {
        ("webclientDAT", "active"),
        ("webclientDAT", "reqmethod"),
        ("webclientDAT", "url"),
        ("webclientDAT", "uploadfile"),
        ("webclientDAT", "request"),
        ("webclientDAT", "stop"),
        ("webclientDAT", "stream"),
        ("webclientDAT", "verifycert"),
        ("webclientDAT", "timeout"),
        ("webclientDAT", "includeheader"),
        ("webclientDAT", "authtype"),
        ("webclientDAT", "clamp"),
        ("webclientDAT", "callbacks"),
        ("webclientDAT", "maxlines"),
        ("webclientDAT", "clear"),
        ("webclientDAT", "username"),
        ("webclientDAT", "pw"),
        ("webclientDAT", "appkey"),
        ("webclientDAT", "appsecret"),
        ("webclientDAT", "oauthtoken"),
        ("webclientDAT", "oauthsecret"),
        ("webclientDAT", "clientid"),
        ("webclientDAT", "token"),
    }
    webserver_expected = {
        ("webserverDAT", "active"),
        ("webserverDAT", "restart"),
        ("webserverDAT", "port"),
        ("webserverDAT", "secure"),
        ("webserverDAT", "privatekey"),
        ("webserverDAT", "certificate"),
        ("webserverDAT", "password"),
        ("webserverDAT", "callbacks"),
    }

    missing = (osc_expected | websocket_expected | webclient_expected | webserver_expected) - set(by_key)
    assert missing == set()
    assert all(by_key[key].official_source == "https://docs.derivative.ca/OSC_In_DAT" for key in osc_expected)
    assert all(
        by_key[key].official_source == "https://docs.derivative.ca/WebSocket_DAT"
        for key in websocket_expected
    )
    assert all(
        by_key[key].official_source == "https://docs.derivative.ca/Web_Client_DAT"
        for key in webclient_expected
    )
    assert all(
        by_key[key].official_source == "https://docs.derivative.ca/Web_Server_DAT"
        for key in webserver_expected
    )

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "oscinDAT", "name": "osc_in"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "websocketDAT", "name": "websocket_in"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "webclientDAT", "name": "web_client"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "webserverDAT", "name": "web_server"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullTOP", "name": "not_dat"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/osc_in",
                args={
                    "params": {
                        "active": "yes",
                        "port": "9000",
                        "shared": "maybe",
                        "typetag": "yes",
                        "splitbundle": "yes",
                        "splitmessage": "yes",
                        "bundletimestamp": "yes",
                        "clamp": "sure",
                        "maxlines": "many",
                        "bytes": "raw",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/websocket_in",
                args={
                    "params": {
                        "active": "yes",
                        "port": "443",
                        "timeout": "forever",
                        "clamp": "sure",
                        "maxlines": "many",
                        "bytes": "raw",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/web_client",
                args={
                    "params": {
                        "active": "yes",
                        "reqmethod": "CONNECT",
                        "uploadfile": "",
                        "stream": "please",
                        "verifycert": "sometimes",
                        "timeout": "forever",
                        "includeheader": "sure",
                        "authtype": "Bearer",
                        "clamp": "sure",
                        "callbacks": "/project1/not_dat",
                        "maxlines": "many",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/web_server",
                args={
                    "params": {
                        "active": "yes",
                        "port": "443",
                        "secure": "sometimes",
                        "privatekey": "",
                        "certificate": "",
                        "callbacks": "/project1/not_dat",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)
    by_path = {}
    for issue in issues:
        by_path.setdefault(issue.path, []).append(issue.code)

    assert by_path["/project1/osc_in"].count("invalid_bool_param") == 8
    assert by_path["/project1/osc_in"].count("invalid_int_param") == 2
    assert by_path["/project1/websocket_in"].count("invalid_bool_param") == 3
    assert by_path["/project1/websocket_in"].count("invalid_int_param") == 3
    assert by_path["/project1/web_client"].count("invalid_bool_param") == 5
    assert by_path["/project1/web_client"].count("invalid_enum_param") == 2
    assert by_path["/project1/web_client"].count("invalid_int_param") == 2
    assert "empty_path_param" in by_path["/project1/web_client"]
    assert "param_reference_type_mismatch" in by_path["/project1/web_client"]
    assert by_path["/project1/web_server"].count("invalid_bool_param") == 2
    assert by_path["/project1/web_server"].count("invalid_int_param") == 1
    assert by_path["/project1/web_server"].count("empty_path_param") == 2
    assert "param_reference_type_mismatch" in by_path["/project1/web_server"]


def test_web_client_dat_request_pulse_is_ranked_as_direct_live_write_risk():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "webclientDAT", "name": "web_client"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/web_client",
                args={"params": {"request": True}},
            ),
        ]
    )

    assert parameter_risk_flags_for_plan(plan) == ["param-semantics:http-request:webclientDAT.request"]


def test_web_client_dat_active_and_stream_are_ranked_as_direct_live_write_risks():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "webclientDAT", "name": "web_client"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/web_client",
                args={"params": {"active": True, "stream": True}},
            ),
        ]
    )

    assert parameter_risk_flags_for_plan(plan) == [
        "param-semantics:http-client-active:webclientDAT.active",
        "param-semantics:http-streaming-response:webclientDAT.stream",
    ]


def test_web_server_dat_active_and_restart_are_ranked_as_direct_live_write_risks():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "webserverDAT", "name": "web_server"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/web_server",
                args={"params": {"active": True, "restart": True}},
            ),
        ]
    )

    assert parameter_risk_flags_for_plan(plan) == [
        "param-semantics:web-server-listener:webserverDAT.active",
        "param-semantics:web-server-restart:webserverDAT.restart",
    ]


def test_live_source_activation_params_are_ranked_as_direct_live_write_risks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    assert (
        by_key[("kinectazureTOP", "active")].official_source == "https://docs.derivative.ca/Kinect_Azure_TOP"
    )
    assert by_key[("kinectazureTOP", "active")].cook_risk == "high"

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "audiodeviceinCHOP", "name": "audio_in"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "videodeviceinTOP", "name": "video_in"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "kinectazureTOP", "name": "depth_in"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "midiinCHOP", "name": "midi_in"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "serialDAT", "name": "serial_in"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "oscinDAT", "name": "osc_in"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "websocketDAT", "name": "websocket_in"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "mqttclientDAT", "name": "mqtt_in"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "udpinDAT", "name": "udp_in"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/audio_in",
                args={"params": {"active": True}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/video_in",
                args={"params": {"active": True, "capture": True}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/depth_in",
                args={"params": {"active": True}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/midi_in",
                args={"params": {"source": "device"}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/serial_in",
                args={"params": {"active": True}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/osc_in",
                args={"params": {"active": True}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/websocket_in",
                args={"params": {"active": True}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/mqtt_in",
                args={"params": {"active": True}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/udp_in",
                args={"params": {"active": True}},
            ),
        ]
    )

    assert parameter_risk_flags_for_plan(plan) == [
        "param-semantics:live-audio-input:audiodeviceinCHOP.active",
        "param-semantics:live-video-input:videodeviceinTOP.active",
        "param-semantics:live-video-capture:videodeviceinTOP.capture",
        "param-semantics:kinect-azure-sensor-input:kinectazureTOP.active",
        "param-semantics:midi-device-input:midiinCHOP.source",
        "param-semantics:serial-device-listener:serialDAT.active",
        "param-semantics:osc-network-listener:oscinDAT.active",
        "param-semantics:websocket-network-client:websocketDAT.active",
        "param-semantics:mqtt-broker-client:mqttclientDAT.active",
        "param-semantics:udp-network-listener:udpinDAT.active",
    ]


def test_callback_dat_execution_params_are_ranked_as_direct_execution_risks():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "textDAT", "name": "callbacks"}
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "datexecuteDAT", "name": "dat_execute"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "executeDAT", "name": "project_execute"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "mqttclientDAT", "name": "mqtt"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/dat_execute",
                args={
                    "params": {
                        "active": True,
                        "executeloc": "current",
                        "tablechange": True,
                        "execute": "end",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/project_execute",
                args={"params": {"active": True, "framestart": True, "writepulse": True}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/mqtt",
                args={"params": {"callbacks": "/project1/callbacks", "executeloc": "callbacks"}},
            ),
        ]
    )

    assert parameter_risk_flags_for_plan(plan) == [
        "param-semantics:callback-execution-enabled:datexecuteDAT.active",
        "param-semantics:callback-execute-location:datexecuteDAT.executeloc",
        "param-semantics:callback-trigger-enabled:datexecuteDAT.tablechange",
        "param-semantics:callback-execution-timing:datexecuteDAT.execute",
        "param-semantics:callback-execution-enabled:executeDAT.active",
        "param-semantics:callback-trigger-enabled:executeDAT.framestart",
        "param-semantics:script-file-write:executeDAT.writepulse",
        "param-semantics:callback-dat-binding:mqttclientDAT.callbacks",
        "param-semantics:callback-execute-location:mqttclientDAT.executeloc",
    ]


def test_mqtt_credentials_and_tls_params_are_ranked_as_direct_security_risks():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "mqttclientDAT", "name": "mqtt"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/mqtt",
                args={"params": {"username": "user", "password": "secret", "verifycert": False}},
            ),
        ]
    )

    assert parameter_risk_flags_for_plan(plan) == [
        "param-semantics:mqtt-credential-username:mqttclientDAT.username",
        "param-semantics:mqtt-credential-secret:mqttclientDAT.password",
        "param-semantics:mqtt-tls-verification-disabled:mqttclientDAT.verifycert",
    ]


def test_web_client_and_server_credentials_are_ranked_as_direct_security_risks():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "webclientDAT", "name": "web_client"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "webserverDAT", "name": "web_server"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/web_client",
                args={
                    "params": {
                        "username": "user",
                        "pw": "secret",
                        "appsecret": "app-secret",
                        "oauthtoken": "oauth-token",
                        "oauthsecret": "oauth-secret",
                        "token": "bearer-token",
                        "verifycert": False,
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/web_server",
                args={
                    "params": {
                        "privatekey": "/project1/private_key",
                        "certificate": "/project1/certificate",
                        "password": "cert-secret",
                    }
                },
            ),
        ]
    )

    assert parameter_risk_flags_for_plan(plan) == [
        "param-semantics:http-credential-username:webclientDAT.username",
        "param-semantics:http-credential-secret:webclientDAT.pw",
        "param-semantics:http-credential-secret:webclientDAT.appsecret",
        "param-semantics:http-credential-secret:webclientDAT.oauthtoken",
        "param-semantics:http-credential-secret:webclientDAT.oauthsecret",
        "param-semantics:http-credential-secret:webclientDAT.token",
        "param-semantics:http-tls-verification-disabled:webclientDAT.verifycert",
        "param-semantics:web-server-tls-private-key:webserverDAT.privatekey",
        "param-semantics:web-server-tls-certificate:webserverDAT.certificate",
        "param-semantics:web-server-tls-credential-secret:webserverDAT.password",
    ]


def test_high_cook_risk_semantics_audit_maps_direct_risk_and_validation_only_behavior():
    report = param_semantics.audit_high_cook_risk_direct_param_coverage()
    direct = {(item["op_type"], item["name"]): item for item in report["direct_risk_parameters"]}
    validation_only = {(item["op_type"], item["name"]): item for item in report["validation_only_parameters"]}

    assert report["ok"] is True
    assert report["contract"] == "high_cook_risk_direct_param_coverage_v1"
    assert report["unclassified_high_cook_risk_parameters"] == []
    assert ("datexecuteDAT", "active") in direct
    assert ("datexecuteDAT", "executeloc") in direct
    assert ("mqttclientDAT", "password") in direct
    assert ("mqttclientDAT", "verifycert") in direct
    assert ("webclientDAT", "pw") in direct
    assert ("webclientDAT", "token") in direct
    assert ("webserverDAT", "password") in direct
    assert ("mqttclientDAT", "netaddress") in validation_only
    assert direct[("mqttclientDAT", "password")]["behavior"] == "direct-risk"
    assert direct[("webserverDAT", "password")]["behavior"] == "direct-risk"
    assert validation_only[("mqttclientDAT", "netaddress")]["behavior"] == "validation-only"


def test_midi_mqtt_and_udp_source_params_have_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    midi_expected = {
        ("midiinCHOP", "source"),
        ("midiinCHOP", "device"),
        ("midiinCHOP", "file"),
        ("midiinCHOP", "simplified"),
        ("midiinCHOP", "record"),
        ("midiinCHOP", "timer"),
        ("midiinCHOP", "sys"),
        ("midiinCHOP", "start"),
        ("midiinCHOP", "end"),
        ("midiinCHOP", "rate"),
        ("midiinCHOP", "controlname"),
        ("midiinCHOP", "controltype"),
        ("midiinCHOP", "notename"),
        ("midiinCHOP", "chan"),
    }
    mqtt_expected = {
        ("mqttclientDAT", "active"),
        ("mqttclientDAT", "netaddress"),
        ("mqttclientDAT", "keepalive"),
        ("mqttclientDAT", "maxinflight"),
        ("mqttclientDAT", "reconnect"),
        ("mqttclientDAT", "callbacks"),
        ("mqttclientDAT", "executeloc"),
        ("mqttclientDAT", "fromop"),
        ("mqttclientDAT", "clamp"),
        ("mqttclientDAT", "maxlines"),
        ("mqttclientDAT", "clear"),
        ("mqttclientDAT", "bytes"),
    }
    udp_expected = {
        ("udpinDAT", "active"),
        ("udpinDAT", "protocol"),
        ("udpinDAT", "address"),
        ("udpinDAT", "port"),
        ("udpinDAT", "shared"),
        ("udpinDAT", "format"),
        ("udpinDAT", "callbacks"),
        ("udpinDAT", "executeloc"),
        ("udpinDAT", "fromop"),
        ("udpinDAT", "clamp"),
        ("udpinDAT", "maxlines"),
        ("udpinDAT", "clear"),
        ("udpinDAT", "bytes"),
    }

    missing = (midi_expected | mqtt_expected | udp_expected) - set(by_key)
    assert missing == set()
    assert all(
        by_key[key].official_source == "https://docs.derivative.ca/MIDI_In_CHOP" for key in midi_expected
    )
    assert all(
        by_key[key].official_source == "https://docs.derivative.ca/MQTT_Client_DAT" for key in mqtt_expected
    )
    assert all(by_key[key].official_source == "https://docs.derivative.ca/UDP_In_DAT" for key in udp_expected)

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "midiinCHOP", "name": "midi"}
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "mqttclientDAT", "name": "mqtt"},
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "udpinDAT", "name": "udp"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullTOP", "name": "not_dat"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/midi",
                args={"params": {"source": "Smoke Signals", "simplified": "yes", "rate": "fast"}},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/mqtt",
                args={
                    "params": {
                        "active": "yes",
                        "keepalive": "forever",
                        "maxinflight": "many",
                        "callbacks": "/project1/not_dat",
                        "executeloc": "Nowhere",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/udp",
                args={
                    "params": {
                        "active": "yes",
                        "protocol": "Carrier Signal",
                        "format": "paragraph",
                        "port": "9000",
                        "callbacks": "/project1/not_dat",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)
    codes_by_path = {}
    for issue in issues:
        codes_by_path.setdefault(issue.path, set()).add(issue.code)

    assert {"invalid_enum_param", "invalid_bool_param", "invalid_float_param"}.issubset(
        codes_by_path["/project1/midi"]
    )
    assert {
        "invalid_bool_param",
        "invalid_int_param",
        "invalid_enum_param",
        "param_reference_type_mismatch",
    }.issubset(codes_by_path["/project1/mqtt"])
    assert {
        "invalid_bool_param",
        "invalid_enum_param",
        "invalid_int_param",
        "param_reference_type_mismatch",
    }.issubset(codes_by_path["/project1/udp"])


def test_movie_and_video_device_top_source_params_have_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    movie_expected = {
        ("moviefileinTOP", "file"),
        ("moviefileinTOP", "reload"),
        ("moviefileinTOP", "reloadpulse"),
        ("moviefileinTOP", "playmode"),
        ("moviefileinTOP", "play"),
        ("moviefileinTOP", "index"),
        ("moviefileinTOP", "speed"),
        ("moviefileinTOP", "imageindexing"),
        ("moviefileinTOP", "inputcolorspace"),
        ("moviefileinTOP", "decodepixelformat"),
        ("moviefileinTOP", "prereadframes"),
        ("moviefileinTOP", "hwdecode"),
    }
    device_expected = {
        ("videodeviceinTOP", "active"),
        ("videodeviceinTOP", "driver"),
        ("videodeviceinTOP", "device"),
        ("videodeviceinTOP", "specifyip"),
        ("videodeviceinTOP", "ip"),
        ("videodeviceinTOP", "deinterlace"),
        ("videodeviceinTOP", "precedence"),
        ("videodeviceinTOP", "signalformat"),
        ("videodeviceinTOP", "inputpixelformat"),
        ("videodeviceinTOP", "inputcolorspace"),
        ("videodeviceinTOP", "inputreferencewhite"),
        ("videodeviceinTOP", "transfermode"),
        ("videodeviceinTOP", "memorymode"),
        ("videodeviceinTOP", "syncinputs"),
        ("videodeviceinTOP", "capture"),
    }

    missing = (movie_expected | device_expected) - set(by_key)
    assert missing == set()
    assert all(
        by_key[key].official_source == "https://docs.derivative.ca/Movie_File_In_TOP"
        for key in movie_expected
    )
    assert all(
        by_key[key].official_source == "https://docs.derivative.ca/Video_Device_In_TOP"
        for key in device_expected
    )

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "moviefileinTOP", "name": "movie"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "videodeviceinTOP", "name": "camera"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/movie",
                args={
                    "params": {
                        "file": "",
                        "reload": "yes",
                        "playmode": "shuffle",
                        "play": "sometimes",
                        "index": "first",
                        "speed": "fast",
                        "imageindexing": "mystery",
                        "prereadframes": "many",
                        "hwdecode": "gpu-ish",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/camera",
                args={
                    "params": {
                        "active": "yes",
                        "driver": "imaginary",
                        "specifyip": "maybe",
                        "ip": "",
                        "deinterlace": "sometimes",
                        "precedence": "random",
                        "transfermode": "warp",
                        "syncinputs": "yes",
                        "capture": "snapshot",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)
    codes_by_path = {}
    for issue in issues:
        codes_by_path.setdefault(issue.path, set()).add(issue.code)

    assert {"empty_path_param", "invalid_bool_param", "invalid_enum_param", "invalid_float_param"}.issubset(
        codes_by_path["/project1/movie"]
    )
    assert {"invalid_bool_param", "invalid_enum_param", "empty_path_param"}.issubset(
        codes_by_path["/project1/camera"]
    )


def test_info_chop_op_reference_requires_a_target():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "infoCHOP", "name": "debug_info"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/debug_info",
                args={"params": {"op": ""}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert any(
        issue.code == "missing_reference_param" and issue.path == "/project1/debug_info" for issue in issues
    )


def test_error_dat_debug_params_require_typed_callbacks_and_output_limits():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "errorDAT", "name": "error_log"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "nullTOP", "name": "not_a_dat"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/error_log",
                args={
                    "params": {
                        "active": "yes",
                        "callbacks": "/project1/not_a_dat",
                        "executeloc": "Nowhere",
                        "fromop": "",
                        "clamp": "sure",
                        "maxlines": "many",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    bool_issues = [issue for issue in issues if issue.code == "invalid_bool_param"]
    assert len(bool_issues) == 2
    assert any(issue.code == "invalid_int_param" and issue.path == "/project1/error_log" for issue in issues)
    assert any(issue.code == "invalid_enum_param" and issue.path == "/project1/error_log" for issue in issues)
    assert any(
        issue.code == "missing_reference_param" and issue.path == "/project1/error_log" for issue in issues
    )
    assert any(
        issue.code == "param_reference_type_mismatch" and issue.path == "/project1/error_log"
        for issue in issues
    )


def test_audio_source_params_have_docs_grounded_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected_by_source = {
        "https://docs.derivative.ca/Audio_File_In_CHOP": {
            ("audiofileinCHOP", "file"),
            ("audiofileinCHOP", "play"),
            ("audiofileinCHOP", "playmode"),
            ("audiofileinCHOP", "speed"),
            ("audiofileinCHOP", "cue"),
            ("audiofileinCHOP", "cuepulse"),
            ("audiofileinCHOP", "cuepoint"),
            ("audiofileinCHOP", "cuepointunit"),
            ("audiofileinCHOP", "index"),
            ("audiofileinCHOP", "indexunit"),
            ("audiofileinCHOP", "timecodeop"),
            ("audiofileinCHOP", "repeat"),
            ("audiofileinCHOP", "trim"),
            ("audiofileinCHOP", "trimstart"),
            ("audiofileinCHOP", "trimstartunit"),
            ("audiofileinCHOP", "trimend"),
            ("audiofileinCHOP", "trimendunit"),
            ("audiofileinCHOP", "opentimeout"),
            ("audiofileinCHOP", "mono"),
            ("audiofileinCHOP", "volume"),
        },
        "https://docs.derivative.ca/Audio_File_Out_CHOP": {
            ("audiofileoutCHOP", "filetype"),
            ("audiofileoutCHOP", "uniquesuff"),
            ("audiofileoutCHOP", "file"),
            ("audiofileoutCHOP", "codec"),
            ("audiofileoutCHOP", "bitrate"),
            ("audiofileoutCHOP", "record"),
            ("audiofileoutCHOP", "pause"),
            ("audiofileoutCHOP", "headerdat"),
        },
        "https://docs.derivative.ca/Audio_Device_In_CHOP": {
            ("audiodeviceinCHOP", "active"),
            ("audiodeviceinCHOP", "driver"),
            ("audiodeviceinCHOP", "device"),
            ("audiodeviceinCHOP", "errormissing"),
            ("audiodeviceinCHOP", "inputs"),
            ("audiodeviceinCHOP", "format"),
            ("audiodeviceinCHOP", "rate"),
            ("audiodeviceinCHOP", "bufferlength"),
            ("audiodeviceinCHOP", "numchan"),
            ("audiodeviceinCHOP", "frontleft"),
            ("audiodeviceinCHOP", "frontright"),
            ("audiodeviceinCHOP", "sideleft"),
            ("audiodeviceinCHOP", "sideright"),
        },
        "https://docs.derivative.ca/Audio_Device_Out_CHOP": {
            ("audiodeviceoutCHOP", "active"),
            ("audiodeviceoutCHOP", "driver"),
            ("audiodeviceoutCHOP", "device"),
            ("audiodeviceoutCHOP", "outputs"),
            ("audiodeviceoutCHOP", "adjustspeed"),
            ("audiodeviceoutCHOP", "clampoutput"),
        },
    }

    for official_source, expected in expected_by_source.items():
        missing = expected - set(by_key)
        assert missing == set()
        assert all(by_key[key].official_source == official_source for key in expected)

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "audiofileinCHOP", "name": "file_audio"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "audiodeviceinCHOP", "name": "live_audio"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "audiofileoutCHOP", "name": "recorder_audio"},
            ),
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "audiodeviceoutCHOP", "name": "speaker_audio"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/file_audio",
                args={
                    "params": {
                        "play": "yes",
                        "playmode": "shuffle",
                        "speed": "fast",
                        "cuepointunit": "beats",
                        "indexunit": "bars",
                        "timecodeop": "",
                        "repeat": "sometimes",
                        "trim": "maybe",
                        "trimstart": "early",
                        "opentimeout": "forever",
                        "mono": "single",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/recorder_audio",
                args={
                    "params": {
                        "filetype": "telepathy",
                        "uniquesuff": "maybe",
                        "file": "",
                        "bitrate": "fast",
                        "record": "now",
                        "pause": 2,
                        "headerdat": "/project1/live_audio",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/live_audio",
                args={
                    "params": {
                        "active": "yes",
                        "driver": "bluetooth",
                        "errormissing": "maybe",
                        "format": "surroundish",
                        "rate": "fast",
                        "bufferlength": "short",
                        "numchan": 1.5,
                        "frontleft": "on",
                        "sideleft": 2,
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/speaker_audio",
                args={
                    "params": {
                        "active": "yes",
                        "driver": "bluetooth",
                        "adjustspeed": "sometimes",
                        "clampoutput": "loud please",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)
    by_path = {}
    for issue in issues:
        by_path.setdefault(issue.path, set()).add(issue.code)

    assert {
        "invalid_bool_param",
        "invalid_enum_param",
        "invalid_float_param",
        "missing_reference_param",
    }.issubset(by_path["/project1/file_audio"])
    assert {
        "invalid_bool_param",
        "invalid_enum_param",
        "invalid_int_param",
        "empty_path_param",
        "param_reference_type_mismatch",
    }.issubset(by_path["/project1/recorder_audio"])
    assert {"invalid_bool_param", "invalid_enum_param", "invalid_float_param", "invalid_int_param"}.issubset(
        by_path["/project1/live_audio"]
    )
    assert {"invalid_bool_param", "invalid_enum_param"}.issubset(by_path["/project1/speaker_audio"])


def test_analyze_chop_function_rejects_unknown_menu_value():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "analyzeCHOP", "name": "audio_analysis"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/audio_analysis",
                args={"params": {"function": "Definitely Not Analysis"}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert any(
        issue.code == "invalid_enum_param" and issue.path == "/project1/audio_analysis" for issue in issues
    )


def test_math_chop_range_params_require_two_values():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "mathCHOP", "name": "audio_range"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/audio_range",
                args={"params": {"fromrange": (0.0,), "torange": (0.0, 1.0, 2.0)}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    mismatches = [issue for issue in issues if issue.code == "param_tuple_size_mismatch"]
    assert len(mismatches) == 2


def test_filter_chop_type_and_effect_contracts_block_invalid_values():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "filterCHOP", "name": "control_filter"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/control_filter",
                args={"params": {"type": "Definitely Not A Filter", "effect": 1.5, "widthunit": "Centuries"}},
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    enum_issues = [issue for issue in issues if issue.code == "invalid_enum_param"]
    assert len(enum_issues) == 2
    assert any(
        issue.code == "param_out_of_range" and issue.path == "/project1/control_filter" for issue in issues
    )


def test_audio_analysis_math_and_filter_control_params_have_semantics_and_preflight_checks():
    registry = load_param_semantics_registry()
    by_key = {(item.op_type, item.name): item for item in registry}
    expected_by_source = {
        "https://docs.derivative.ca/Analyze_CHOP": {
            ("analyzeCHOP", "function"),
            ("analyzeCHOP", "allowstart"),
            ("analyzeCHOP", "allowend"),
            ("analyzeCHOP", "nopeakvalue"),
            ("analyzeCHOP", "valleys"),
            ("analyzeCHOP", "timeslice"),
            ("analyzeCHOP", "scope"),
            ("analyzeCHOP", "srselect"),
            ("analyzeCHOP", "exportmethod"),
            ("analyzeCHOP", "autoexportroot"),
            ("analyzeCHOP", "exporttable"),
            ("analyzeCHOP", "commonrenamefrom"),
            ("analyzeCHOP", "commonrenameto"),
        },
        "https://docs.derivative.ca/Math_CHOP": {
            ("mathCHOP", "preop"),
            ("mathCHOP", "chanop"),
            ("mathCHOP", "chopop"),
            ("mathCHOP", "postop"),
            ("mathCHOP", "match"),
            ("mathCHOP", "align"),
            ("mathCHOP", "interppars"),
            ("mathCHOP", "integer"),
            ("mathCHOP", "preoff"),
            ("mathCHOP", "gain"),
            ("mathCHOP", "postoff"),
            ("mathCHOP", "fromrange"),
            ("mathCHOP", "torange"),
            ("mathCHOP", "timeslice"),
            ("mathCHOP", "scope"),
            ("mathCHOP", "srselect"),
            ("mathCHOP", "exportmethod"),
            ("mathCHOP", "autoexportroot"),
            ("mathCHOP", "exporttable"),
            ("mathCHOP", "commonrenamefrom"),
            ("mathCHOP", "commonrenameto"),
        },
        "https://docs.derivative.ca/Filter_CHOP": {
            ("filterCHOP", "type"),
            ("filterCHOP", "effect"),
            ("filterCHOP", "width"),
            ("filterCHOP", "widthunit"),
            ("filterCHOP", "spike"),
            ("filterCHOP", "passes"),
            ("filterCHOP", "cutoff"),
            ("filterCHOP", "speedcoeff"),
            ("filterCHOP", "slopecutoff"),
            ("filterCHOP", "slopedownreset"),
            ("filterCHOP", "slopeupreset"),
            ("filterCHOP", "reset"),
            ("filterCHOP", "filterpersample"),
            ("filterCHOP", "timeslice"),
            ("filterCHOP", "scope"),
            ("filterCHOP", "srselect"),
            ("filterCHOP", "exportmethod"),
            ("filterCHOP", "autoexportroot"),
            ("filterCHOP", "exporttable"),
            ("filterCHOP", "commonrenamefrom"),
            ("filterCHOP", "commonrenameto"),
        },
    }

    expected = set().union(*expected_by_source.values())
    assert expected - set(by_key) == set()
    for official_source, keys in expected_by_source.items():
        assert all(by_key[key].official_source == official_source for key in keys)

    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "analyzeCHOP", "name": "analysis"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "mathCHOP", "name": "range"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "filterCHOP", "name": "smooth"}
            ),
            PatchOperation(
                kind="create_node", target="/project1", args={"op_type": "nullCHOP", "name": "not_dat"}
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/analysis",
                args={
                    "params": {
                        "function": "Loudness",
                        "allowstart": "yes",
                        "allowend": 2,
                        "nopeakvalue": "none",
                        "valleys": "maybe",
                        "timeslice": "sometimes",
                        "srselect": "fastest",
                        "exportmethod": "spreadsheet",
                        "autoexportroot": "",
                        "exporttable": "/project1/not_dat",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/range",
                args={
                    "params": {
                        "preop": "cube",
                        "chanop": "median",
                        "chopop": "median",
                        "postop": "log",
                        "match": "time",
                        "align": "sync",
                        "interppars": "yes",
                        "integer": "bankers",
                        "preoff": "zero",
                        "gain": "loud",
                        "postoff": "offset",
                        "fromrange": (0.0,),
                        "torange": (0.0, 1.0, 2.0),
                        "timeslice": "sometimes",
                        "srselect": "fastest",
                        "exportmethod": "spreadsheet",
                        "autoexportroot": "",
                        "exporttable": "/project1/not_dat",
                    }
                },
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/smooth",
                args={
                    "params": {
                        "type": "Kalman",
                        "effect": 1.5,
                        "width": "wide",
                        "widthunit": "Beats",
                        "spike": "spiky",
                        "passes": 0.5,
                        "cutoff": "low",
                        "speedcoeff": "fast",
                        "slopecutoff": "slow",
                        "slopedownreset": "yes",
                        "slopeupreset": 2,
                        "reset": "true",
                        "filterpersample": "sometimes",
                        "timeslice": "sometimes",
                        "srselect": "fastest",
                        "exportmethod": "spreadsheet",
                        "autoexportroot": "",
                        "exporttable": "/project1/not_dat",
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    assert sum(1 for issue in issues if issue.code == "invalid_enum_param") >= 14
    assert sum(1 for issue in issues if issue.code == "invalid_bool_param") >= 10
    assert sum(1 for issue in issues if issue.code == "invalid_float_param") >= 8
    assert sum(1 for issue in issues if issue.code == "invalid_int_param") >= 1
    assert sum(1 for issue in issues if issue.code == "param_tuple_size_mismatch") >= 2
    assert sum(1 for issue in issues if issue.code == "param_out_of_range") >= 2
    assert sum(1 for issue in issues if issue.code == "param_reference_type_mismatch") >= 3
    assert sum(1 for issue in issues if issue.code == "empty_path_param") >= 3


def test_lag_chop_method_and_lag_tuple_contracts_block_invalid_values():
    plan = _plan_with_ops(
        [
            PatchOperation(
                kind="create_node",
                target="/project1",
                args={"op_type": "lagCHOP", "name": "control_lag"},
            ),
            PatchOperation(
                kind="set_params",
                target="/project1/control_lag",
                args={
                    "params": {
                        "lagmethod": "Definitely Not A Lag Method",
                        "lagunit": "Centuries",
                        "overshootunit": "Centuries",
                        "lag": (0.1, 0.2, 0.3),
                        "overshoot": (0.1,),
                        "slope": (1.0, 2.0, 3.0),
                        "accel": 1.0,
                    }
                },
            ),
        ]
    )

    issues = validate_patch_plan_parameter_contract(plan)

    enum_issues = [issue for issue in issues if issue.code == "invalid_enum_param"]
    tuple_issues = [issue for issue in issues if issue.code == "param_tuple_size_mismatch"]
    assert len(enum_issues) == 3
    assert len(tuple_issues) == 4


@pytest.mark.asyncio
async def test_planner_blocks_param_semantics_errors_before_returning_operations(monkeypatch):
    from td_mcp.brain import planner

    original_compile = planner._compile_patch_plan

    def compile_with_bad_param(task, graph, existing_names):
        patch_plan = original_compile(task, graph, existing_names)
        operations = [
            *patch_plan.operations,
            PatchOperation(
                kind="set_params",
                target="/project1/level",
                args={"params": {"opacity": 1.25}},
            ),
        ]
        return patch_plan.model_copy(update={"operations": operations})

    monkeypatch.setattr(planner, "_compile_patch_plan", compile_with_bad_param)
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

    plan = await planner.build_brain_plan(client, intent="build feedback loop", target_root="/project1")

    assert plan.blocked_questions
    assert "param_semantics:param_out_of_range" in plan.missing_facts
    assert plan.patch_plan.operations == []


@pytest.mark.asyncio
async def test_planner_carries_non_blocking_param_semantics_risk_flags(monkeypatch):
    from td_mcp.brain import planner

    original_compile = planner._compile_patch_plan

    def compile_with_high_resolution(task, graph, existing_names):
        patch_plan = original_compile(task, graph, existing_names)
        render_target = next(
            f"{operation.target.rstrip('/')}/{operation.args['name']}"
            for operation in patch_plan.operations
            if operation.kind == "create_node" and operation.args.get("op_type") == "renderTOP"
        )
        operations = [
            *patch_plan.operations,
            PatchOperation(
                kind="set_params",
                target=render_target,
                args={"params": {"resolution": (7680, 4320)}},
            ),
        ]
        return patch_plan.model_copy(update={"operations": operations})

    monkeypatch.setattr(planner, "_compile_patch_plan", compile_with_high_resolution)
    client = FakeTDClient(
        scripted={
            "families": {
                "families": {
                    "TOP": ["renderTOP", "nullTOP"],
                    "COMP": ["geometryCOMP", "cameraCOMP"],
                }
            },
            "nodes": {"nodes": []},
        }
    )

    plan = await planner.build_brain_plan(
        client,
        intent="Build a render pipeline with geometry, camera, render TOP, and stable output.",
        target_root="/project1",
        output_top="/project1/out1",
    )

    assert plan.blocked_questions == []
    assert plan.patch_plan.operations
    assert "param-semantics:high-resolution:renderTOP.resolution" in plan.risk_flags
    assert "param-semantics:high-resolution:renderTOP.resolution" in plan.patch_plan.risk_flags
    assert "direct-param-risk:param-semantics:high-resolution:renderTOP.resolution" in plan.grounding_evidence
    assert (
        "direct-param-risk:param-semantics:high-resolution:renderTOP.resolution"
        in plan.concept_graph.evidence
    )
