"""Reviewed scalar modulation targets, verified against TD 2025.33230.

Bounds are TDPilot's conservative authoring policy, not hardware limits.
Unknown parameters (including pulses, allocation counts and references) never
become expression targets merely because TD accepts an expression there.
"""

import ast
import math
import re

from td_mcp.models.brain import ParamSemantics

# op type -> (official documentation, parameter -> (low, high, unit))
CONTROL_TARGETS = {
    "cameraCOMP": (
        "Camera_COMP",
        {
            **{name: (-1000.0, 1000.0, "scene units") for name in ("tx", "ty", "tz")},
            **{name: (-3600.0, 3600.0, "degrees") for name in ("rx", "ry", "rz")},
            "fov": (1.0, 179.0, "degrees"),
        },
    ),
    "phongMAT": (
        "Phong_MAT",
        {
            **{name: (0.0, 1.0, "linear color") for name in ("diffr", "diffg", "diffb")},
            "shininess": (0.0, 128.0, None),
        },
    ),
    "particlePOP": (
        "Particle_POP",
        {
            "birthrate": (0.0, 10000.0, "particles/second"),
            "life": (0.001, 60.0, "seconds"),
            "speed": (0.0, 100.0, "scene units/second"),
        },
    ),
    "noisePOP": (
        "Noise_POP",
        {"amp0": (0.0, 1000.0, None), "period": (0.001, 100000.0, None)},
    ),
}


def control_target_bounds(op_type: str, parameter: str) -> tuple[float, float] | None:
    record = CONTROL_TARGETS.get(op_type)
    spec = record[1].get(parameter) if record else None
    return (spec[0], spec[1]) if spec else None


def control_parameter_semantics() -> list[ParamSemantics]:
    return [
        ParamSemantics(
            op_type=op_type,
            name=name,
            label=name,
            value_kind="float",
            valid_range=(low, high),
            unit=unit,
            default_strategy="bounded_chop_modulation",
            cook_risk="medium",
            validation_rule="bounded_control_parameter",
            official_source="https://docs.derivative.ca/" + docs,
        )
        for op_type, (docs, parameters) in CONTROL_TARGETS.items()
        for name, (low, high, unit) in parameters.items()
    ]


def control_expression_source(expression: str, op_type: str, parameter: str) -> str:
    """Validate the closed binding grammar and return its one CHOP path.

    Accept only a channel reference, optional affine transform, and optional
    min/max clamp. New target families require a clamp within reviewed bounds.
    This parser never evaluates the expression.
    """

    def fail():
        raise ValueError("expected a bounded single-operator CHOP channel reference")

    def number(node):
        sign = 1
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            sign = -1 if isinstance(node.op, ast.USub) else 1
            node = node.operand
        if not isinstance(node, ast.Constant) or type(node.value) not in (int, float):
            fail()
        try:
            value = sign * float(node.value)
        except OverflowError:
            fail()
        if not math.isfinite(value):
            fail()
        return value

    def call(node, name, count):
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
            and len(node.args) == count
            and not node.keywords
        )

    try:
        if len(expression) > 2048:
            fail()
        node = ast.parse(expression.strip(), mode="eval").body
        bounds = control_target_bounds(op_type, parameter)
        if call(node, "min", 2):
            high = number(node.args[0])
            inner = node.args[1]
            if not call(inner, "max", 2):
                fail()
            low = number(inner.args[0])
            if low > high or (bounds and (low < bounds[0] or high > bounds[1])):
                fail()
            node = inner.args[1]
        elif bounds:
            fail()
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            number(node.right)
            node = node.left
            if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Mult):
                fail()
            number(node.right)
            node = node.left
        if not isinstance(node, ast.Subscript) or not call(node.value, "op", 1):
            fail()
        path_node = node.value.args[0]
        if not isinstance(path_node, ast.Constant) or not isinstance(path_node.value, str):
            fail()
        path = path_node.value
        if not re.fullmatch(r"/(?:[A-Za-z0-9_]+/)*[A-Za-z0-9_]+", path):
            fail()
        selector = node.slice
        if not isinstance(selector, ast.Constant):
            fail()
        if type(selector.value) is int:
            if selector.value < 0:
                fail()
        elif isinstance(selector.value, str):
            if not re.fullmatch(r"[A-Za-z0-9_]{1,64}", selector.value):
                fail()
        else:
            fail()
        return path
    except (SyntaxError, RecursionError) as exc:
        raise ValueError("invalid control expression") from exc
