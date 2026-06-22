"""Phase 4 assembly macro registry for readable compiler-backed plans."""

from __future__ import annotations

from td_mcp.models.brain import AssemblyMacro, BrainPattern, BrainProfile


def load_assembly_macro_registry() -> list[AssemblyMacro]:
    """Load the built-in Phase 4 MVP assembly macros."""
    return [AssemblyMacro(**item) for item in _DEFAULT_ASSEMBLY_MACROS]


def macros_for_profiles(profiles: list[str]) -> list[AssemblyMacro]:
    """Return registry macros applicable to any requested concept profile."""
    requested = set(profiles)
    if not requested:
        return []
    return [
        macro
        for macro in load_assembly_macro_registry()
        if requested.intersection(set(macro.applies_to_profiles))
    ]


def validate_assembly_macro_control_bindings(
    *,
    macros: list[AssemblyMacro] | None = None,
    patterns: list[BrainPattern] | None = None,
) -> list[dict[str, str]]:
    """Return missing macro control bindings against known pattern parameters."""
    from td_mcp.brain.patterns import load_pattern_registry

    pattern_records = patterns if patterns is not None else load_pattern_registry()
    params_by_pattern: dict[str, set[str]] = {}
    for pattern in pattern_records:
        params_by_pattern[pattern.pattern_id] = {
            str(param.get("name"))
            for param in pattern.parameters
            if isinstance(param, dict) and str(param.get("name") or "").strip()
        }

    missing: list[dict[str, str]] = []
    macro_records = macros if macros is not None else load_assembly_macro_registry()
    for macro in macro_records:
        for control in macro.created_controls:
            pattern_id = str(control.get("pattern_id") or "")
            parameter_name = str(control.get("parameter_name") or "")
            if not pattern_id or not parameter_name:
                missing.append(
                    {
                        "macro_id": macro.macro_id,
                        "control": str(control.get("name") or ""),
                        "reason": "missing_pattern_parameter_binding",
                    }
                )
                continue
            if pattern_id not in params_by_pattern:
                missing.append(
                    {
                        "macro_id": macro.macro_id,
                        "control": str(control.get("name") or ""),
                        "pattern_id": pattern_id,
                        "parameter_name": parameter_name,
                        "reason": "unknown_pattern",
                    }
                )
                continue
            if parameter_name not in params_by_pattern[pattern_id]:
                missing.append(
                    {
                        "macro_id": macro.macro_id,
                        "control": str(control.get("name") or ""),
                        "pattern_id": pattern_id,
                        "parameter_name": parameter_name,
                        "reason": "unknown_pattern_parameter",
                    }
                )
    return missing


_COMPONENT_SOURCES = [
    "https://docs.derivative.ca/Component_Editor_Dialog",
    "https://docs.derivative.ca/Palette%3AsceneChanger",
]

_DEFAULT_PROFILES: list[BrainProfile] = ["concept_compiled"]

_DEFAULT_ASSEMBLY_MACROS = [
    {
        "macro_id": "make_component_shell",
        "label": "Make Component Shell",
        "applies_to_profiles": _DEFAULT_PROFILES,
        "layout_strategy": "component_shell",
        "created_controls": [],
        "debug_nodes": [],
        "notes": ["Place the assembled concept graph inside a deterministic Base COMP shell."],
        "output_contract": ["tdpilot_concept"],
        "validation_addons": ["component_shell_present"],
        "official_sources": [
            "https://docs.derivative.ca/Base_COMP",
            "https://docs.derivative.ca/Component",
            *_COMPONENT_SOURCES,
        ],
    },
    {
        "macro_id": "group_by_domain",
        "label": "Group By Domain",
        "applies_to_profiles": _DEFAULT_PROFILES,
        "layout_strategy": "domain_columns",
        "created_controls": [],
        "debug_nodes": [],
        "notes": ["Place CHOP, TOP, COMP, and DAT nodes in deterministic domain bands."],
        "output_contract": ["out1", "out_chop", "out_dat", "out_pop", "debug_notes"],
        "validation_addons": ["output_node_present"],
        "official_sources": [
            "https://docs.derivative.ca/COMP_Layout_Page",
            *_COMPONENT_SOURCES,
        ],
    },
    {
        "macro_id": "add_named_outputs",
        "label": "Add Named Outputs",
        "applies_to_profiles": _DEFAULT_PROFILES,
        "layout_strategy": "stable_output_contract",
        "created_controls": [],
        "debug_nodes": [],
        "notes": ["Make stable output nodes easy to identify and validate."],
        "output_contract": ["out1", "out_chop", "out_dat", "out_pop", "debug_notes"],
        "validation_addons": ["output_node_present", "cheap_visual_metrics"],
        "official_sources": _COMPONENT_SOURCES,
    },
    {
        "macro_id": "add_debug_panel",
        "label": "Add Debug Panel",
        "applies_to_profiles": _DEFAULT_PROFILES,
        "layout_strategy": "diagnostics_band",
        "created_controls": [],
        "debug_nodes": [
            {"name": "debug_notes", "op_type": "textDAT", "domain": "DAT"},
            {"name": "debug_info", "op_type": "infoCHOP", "domain": "CHOP"},
            {"name": "error_log", "op_type": "errorDAT", "domain": "DAT"},
        ],
        "notes": ["Expose lightweight debug notes without changing the primary TOP output."],
        "output_contract": ["debug_notes", "debug_info", "error_log"],
        "validation_addons": ["output_node_present"],
        "official_sources": [
            "https://docs.derivative.ca/Text_DAT",
            "https://docs.derivative.ca/Info_CHOP",
            "https://docs.derivative.ca/Error_DAT",
            *_COMPONENT_SOURCES,
        ],
    },
    {
        "macro_id": "add_user_controls",
        "label": "Add User Controls",
        "applies_to_profiles": _DEFAULT_PROFILES,
        "layout_strategy": "controls_band",
        "created_controls": [
            {
                "name": "feedback_decay",
                "pattern_id": "feedback_decay_top_loop",
                "parameter_name": "feedback_decay",
                "target_node_id": "feedback_decay",
                "target_param": "opacity",
                "control_type": "slider",
            },
            {
                "name": "panel_reader",
                "pattern_id": "panel_controls_to_chop_output",
                "parameter_name": "panel_reader_component",
                "target_node_id": "panel_reader",
                "target_param": "component",
                "control_type": "operator_reference",
            },
        ],
        "debug_nodes": [],
        "notes": ["Keep user-facing control nodes grouped near panel outputs."],
        "output_contract": ["out_chop"],
        "validation_addons": ["panel_state_reader", "control_output"],
        "official_sources": _COMPONENT_SOURCES,
    },
    {
        "macro_id": "annotate_operator_chain",
        "label": "Annotate Operator Chain",
        "applies_to_profiles": _DEFAULT_PROFILES,
        "layout_strategy": "annotation_band",
        "created_controls": [],
        "debug_nodes": [{"name": "assembly_notes", "domain": "COMP"}],
        "notes": ["Annotate selected patterns, docs evidence, and validation expectations."],
        "output_contract": ["assembly_notes"],
        "validation_addons": ["output_node_present"],
        "official_sources": _COMPONENT_SOURCES,
    },
]


__all__ = [
    "load_assembly_macro_registry",
    "macros_for_profiles",
    "validate_assembly_macro_control_bindings",
]
