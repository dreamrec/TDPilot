import pytest
from pydantic import ValidationError

from td_mcp.brain.control_bindings import control_expression_source
from td_mcp.brain.intent_coverage import control_binding_operation
from td_mcp.models.brain import ConceptEdge, ControlBindingSpec


def _binding(op_type, parameter, **options):
    return control_binding_operation(
        ConceptEdge(
            source="signal",
            target="target",
            kind="control",
            binding={"target_param": parameter, "source_channel": "amp", **options},
        ),
        source_op_type="nullCHOP",
        target_op_type=op_type,
        source_path="/project1/signal",
        target_path="/project1/target",
        target_params={},
    )[1]["expr"]


@pytest.mark.parametrize(
    "op_type,parameter,low,high",
    [
        ("cameraCOMP", "tx", -1000, 1000),
        ("cameraCOMP", "fov", 1, 179),
        ("phongMAT", "diffr", 0, 1),
        ("particlePOP", "birthrate", 0, 10000),
        ("particlePOP", "life", 0.001, 60),
        ("noisePOP", "amp0", 0, 1000),
    ],
)
def test_control_expression_scales_and_clamps_actual_numeric_signal(op_type, parameter, low, high):
    expression = _binding(op_type, parameter, scale=2, offset=3)

    # Evaluate only the locally generated expression with a controlled fake CHOP.
    def run(value):
        return eval(
            expression, {"__builtins__": {}, "min": min, "max": max, "op": lambda path: {"amp": value}}
        )

    assert run(-1e9) == low
    assert run(1e9) == high
    assert run(0) == min(high, max(low, 3))


def test_requested_range_narrows_target_policy():
    assert _binding("cameraCOMP", "tx", output_range=(-2, 2)).startswith("min(2.0, max(-2.0,")
    with pytest.raises(ValueError, match="exceeds"):
        _binding("phongMAT", "diffr", output_range=(-1, 2))


@pytest.mark.parametrize(
    "op_type,param",
    [
        ("cameraCOMP", "lookat"),
        ("particlePOP", "resetpulse"),
        ("noisePOP", "amp"),
        ("phongMAT", "diffusemap"),
    ],
)
def test_unreviewed_or_nonnumeric_targets_are_rejected(op_type, param):
    with pytest.raises(ValueError, match="reviewed numeric"):
        _binding(op_type, param)


@pytest.mark.parametrize(
    "options",
    [
        {"scale": float("nan")},
        {"offset": float("inf")},
        {"output_range": (2, 1)},
        {"output_range": (0, float("inf"))},
        {"source_channel": "x']; dangerous() #"},
    ],
)
def test_invalid_binding_values_are_rejected(options):
    with pytest.raises(ValidationError):
        ControlBindingSpec(target_param="tx", **options)


@pytest.mark.parametrize(
    "expression",
    [
        "op('/project1/source')[0]",  # camera controls must be clamped
        "min(2000, max(-1000, op('/project1/source')[0]))",
        "min(1, max(2, op('/project1/source')[0]))",
        "min(1, max(0, __import__('os').getcwd()))",
        "min(1, max(0, op('/project1/source')[0] + absTime.seconds))",
        "min(1, max(0, op('/project1/source')[0] * float('inf') + 0))",
        "min(1, max(0, op('/project1/source')[0])) or dangerous()",
    ],
)
def test_expression_preflight_rejects_missing_bounds_and_code_injection(expression):
    with pytest.raises(ValueError):
        control_expression_source(expression, "cameraCOMP", "tx")


def test_new_semantics_match_recorded_live_parameter_names_and_menus():
    import json
    from pathlib import Path

    from td_mcp.brain.param_semantics import semantics_by_op_and_param

    sample = json.loads((Path(__file__).parents[1] / "fixtures/td_2025_33230_parameters.json").read_text())
    registry = semantics_by_op_and_param()
    for op_type, parameters in sample["operators"].items():
        for name, metadata in parameters.items():
            semantic = registry[op_type, name]
            if semantic.value_kind == "enum":
                assert set(semantic.enum_values) == set(metadata["menuNames"])
            elif semantic.value_kind in {"int", "float"}:
                assert isinstance(metadata["default"], (int, float))


def test_live_qualification_plan_preflights_and_checks_every_control_target():
    import importlib.util
    from pathlib import Path

    from td_mcp.brain.param_semantics import validate_patch_plan_parameter_contract

    path = Path(__file__).resolve().parents[2] / "scripts/qualify_control_bindings.py"
    spec = importlib.util.spec_from_file_location("qualify_controls_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plan, contract = module.qualification_plan("/project1/owned_scratch")
    assert validate_patch_plan_parameter_contract(plan, require_semantics_for_set_params=True) == []
    assert len(contract.runtime_assertions) == 4
    assert {a.expected["param"] for a in contract.runtime_assertions} == {"tx", "diffr", "birthrate", "amp0"}
