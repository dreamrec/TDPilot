from __future__ import annotations

from td_mcp.brain import assembly_macros
from td_mcp.brain.assembly_macros import load_assembly_macro_registry, macros_for_profiles
from td_mcp.brain.patterns import load_pattern_registry
from td_mcp.brain.validators import checks_for_profile


def test_assembly_macro_registry_loads_phase4_mvp_macros():
    macros = load_assembly_macro_registry()
    ids = [macro.macro_id for macro in macros]

    assert ids == [
        "make_component_shell",
        "group_by_domain",
        "add_named_outputs",
        "add_debug_panel",
        "add_user_controls",
        "annotate_operator_chain",
    ]
    assert all(macro.official_sources for macro in macros)
    assert all("concept_compiled" in macro.applies_to_profiles for macro in macros)
    debug_macro = next(macro for macro in macros if macro.macro_id == "add_debug_panel")
    debug_ops = {node["op_type"] for node in debug_macro.debug_nodes}
    assert {"infoCHOP", "errorDAT"}.issubset(debug_ops)
    assert "https://docs.derivative.ca/Info_CHOP" in debug_macro.official_sources
    assert "https://docs.derivative.ca/Error_DAT" in debug_macro.official_sources
    shell_macro = next(macro for macro in macros if macro.macro_id == "make_component_shell")
    assert "tdpilot_concept" in shell_macro.output_contract
    assert "https://docs.derivative.ca/Base_COMP" in shell_macro.official_sources


def test_macros_for_profiles_filters_deterministically():
    macros = macros_for_profiles(["concept_compiled", "feedback"])

    assert [macro.macro_id for macro in macros] == [
        "make_component_shell",
        "group_by_domain",
        "add_named_outputs",
        "add_debug_panel",
        "add_user_controls",
        "annotate_operator_chain",
    ]
    assert macros_for_profiles(["generic"]) == []


def test_assembly_macro_validation_addons_are_backed_by_concept_compiled_checks():
    macros = load_assembly_macro_registry()
    backed_checks = set(checks_for_profile("structural_visual_safe", "concept_compiled"))
    addons = {addon for macro in macros for addon in macro.validation_addons}

    assert addons
    assert addons.issubset(backed_checks)


def test_named_output_macro_contract_covers_dat_and_pop_outputs():
    macros = load_assembly_macro_registry()
    named_outputs = next(macro for macro in macros if macro.macro_id == "add_named_outputs")

    assert {"out1", "out_chop", "out_dat", "out_pop", "debug_notes"}.issubset(
        set(named_outputs.output_contract)
    )


def test_user_control_macro_controls_map_to_known_pattern_parameters():
    assert hasattr(assembly_macros, "validate_assembly_macro_control_bindings")

    missing = assembly_macros.validate_assembly_macro_control_bindings(
        macros=load_assembly_macro_registry(),
        patterns=load_pattern_registry(),
    )

    assert missing == []
