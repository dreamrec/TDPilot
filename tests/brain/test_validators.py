from __future__ import annotations

from td_mcp.brain.validators import checks_for_profile, classify_intent_profile


def test_checks_for_profile_combines_structural_and_concept_checks():
    checks = checks_for_profile("structural_visual_safe", "glsl")

    assert "graph_structure" in checks
    assert "td_errors" in checks
    assert "shader_source_present" in checks
    assert "compile_state" in checks


def test_profile_classifier_does_not_match_ui_inside_build():
    profile = classify_intent_profile("Build a custom parameter control rig with default values")

    assert profile == "control_rig"
