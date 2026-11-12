"""Parameter names and menus sampled from TouchDesigner 2025.33230.

Nuitrack node construction on macOS does not qualify sensor operation;
the Windows hardware/license requirement is recorded in its operator cards.
"""

from td_mcp.models.brain import ParamSemantics


def release_parameter_semantics() -> list[ParamSemantics]:
    records = [
        ParamSemantics(
            op_type="particlePOP",
            name="targetpop",
            label="Target Feedback Loop POP",
            value_kind="op_ref",
            expected_family="POP",
            default_strategy="explicit_downstream_feedback_state",
            cook_risk="medium",
            validation_rule="created_reference_matches_family",
            official_source="https://docs.derivative.ca/Particle_POP",
        )
    ]
    for op_type, docs, parameters in (
        (
            "timefilterPOP",
            "Time_Filter_POP",
            {
                "active": ("bool", None),
                "alwayscook": ("bool", None),
                "attrs": ("string", None),
                "attrclass": ("enum", ["point", "primitive", "vertex"]),
                "filtertype": ("enum", ["none", "gaussian", "triangle", "box", "oneeuro"]),
                "width": ("float", (0.0, 60.0)),
                "widthunit": ("enum", ["seconds", "frames"]),
                "inc": ("float", (0.001, 60.0)),
                "incunit": ("enum", ["seconds", "frames"]),
                "cutoff": ("float", (0.001, 1000.0)),
                "speedcoeff": ("float", (0.0, 1000.0)),
                "slopecutoff": ("float", (0.001, 1000.0)),
                "filterresetpulse": ("pulse", None),
            },
        ),
        (
            "nuitrackCHOP",
            "Nuitrack_CHOP",
            {
                "active": ("bool", None),
                "positions": ("bool", None),
                "rotations": ("bool", None),
                "maxplayers": ("int", (1.0, 6.0)),
                "restart": ("pulse", None),
            },
        ),
        (
            "nuitrackTOP",
            "Nuitrack_TOP",
            {
                "image": ("enum", ["depth", "color", "playerindex", "pointcloud"]),
                "rawresolution": ("bool", None),
                "restart": ("pulse", None),
            },
        ),
    ):
        for name, (kind, choices) in parameters.items():
            records.append(
                ParamSemantics(
                    op_type=op_type,
                    name=name,
                    label=name,
                    value_kind=kind,
                    enum_values=choices if kind == "enum" else [],
                    valid_range=choices if kind in {"float", "int"} else None,
                    default_strategy="inspect_live_parameters_before_authoring",
                    cook_risk="medium",
                    validation_rule="known_menu_value" if kind == "enum" else "typed_parameter",
                    official_source="https://docs.derivative.ca/" + docs,
                )
            )
    return records
