from __future__ import annotations

from td_mcp.brain.validation_probes import (
    load_profile_validation_probes,
    probe_ids_for_profile,
    probe_summaries_for_profile,
    validation_probe_coverage_report,
)
from td_mcp.brain.validators import build_validation_report_v2, checks_for_profile


def test_profile_validation_probe_registry_covers_current_profiles():
    probes = load_profile_validation_probes()
    by_profile: dict[str, list[str]] = {}
    for probe in probes:
        by_profile.setdefault(probe.profile, []).append(probe.probe_id)

    for profile in {
        "generic",
        "feedback",
        "audio_reactive",
        "pop",
        "glsl",
        "glsl_material",
        "glsl_pop",
        "render_pipeline",
        "panel_ui",
        "control_rig",
        "dat_protocol",
        "video_io",
        "concept_compiled",
    }:
        assert by_profile.get(profile), f"missing probes for {profile}"

    assert "feedback_cycle" in by_profile["feedback"]
    assert "feedback_output_readback" in by_profile["feedback"]
    assert "audio_source_present" in by_profile["audio_reactive"]
    assert "audio_signal_activity" in by_profile["audio_reactive"]
    assert "camera_frustum_coverage" in by_profile["render_pipeline"]
    assert "panel_state_reader" in by_profile["panel_ui"]
    assert "panel_state_readback" in by_profile["panel_ui"]
    assert "serial_source_present" in by_profile["dat_protocol"]
    assert "osc_source_present" in by_profile["dat_protocol"]
    assert "websocket_source_present" in by_profile["dat_protocol"]
    assert "mqtt_source_present" in by_profile["dat_protocol"]
    assert "udp_source_present" in by_profile["dat_protocol"]
    assert "dat_execute_callback_present" in by_profile["dat_protocol"]
    assert "callback_guard_present" in by_profile["dat_protocol"]
    assert "render_switch_table_present" in by_profile["dat_protocol"]
    assert "render_switch_index_binding" in by_profile["dat_protocol"]
    assert "render_switch_output_present" in by_profile["dat_protocol"]
    assert "ndi_source_present" in by_profile["video_io"]
    assert "post_fx_stage" in by_profile["video_io"]
    assert "top_output_present" in by_profile["video_io"]
    assert {"audio_source_present", "feedback_cycle", "panel_state_reader"}.issubset(
        set(by_profile["concept_compiled"])
    )
    assert all(probe.official_sources for probe in probes)


def test_validation_probe_coverage_report_covers_master_plan_profiles_and_expensive_controls():
    report = validation_probe_coverage_report()

    assert report["ok"] is True
    assert report["missing_required_profile_count"] == 0
    assert report["invalid_source_count"] == 0
    assert report["uncontrolled_expensive_probe_count"] == 0
    assert report["expensive_probe_count"] >= 1
    assert {
        "feedback",
        "audio_reactive",
        "pop",
        "glsl",
        "glsl_material",
        "render_pipeline",
        "panel_ui",
        "dat_protocol",
    }.issubset(set(report["covered_required_profiles"]))


def test_checks_for_profile_are_backed_by_probe_registry_and_keep_existing_names():
    checks = checks_for_profile("structural_visual_safe", "feedback")

    assert "graph_structure" in checks
    assert "td_errors" in checks
    assert "feedback_cycle" in checks
    assert "decay_control" in checks
    assert checks == list(dict.fromkeys(checks))
    assert set(probe_ids_for_profile("feedback")).issubset(checks)


def test_feedback_probe_summaries_include_runtime_output_readback_contract():
    probes = probe_summaries_for_profile("structural_visual_safe", "feedback")
    readback = next(item for item in probes if item["probe_id"] == "feedback_output_readback")

    assert readback["readback_strategy"] == "top_luminance_runtime"
    assert readback["cost_level"] == "cheap"
    assert readback["required_inputs"] == ["feedbackTOP", "nullTOP"]
    assert "feedback_output_luminance_mean" in readback["metric_names"]
    assert "feedback_output_luminance_max" in readback["metric_names"]
    assert "https://docs.derivative.ca/Feedback_TOP" in readback["official_sources"]
    assert "https://docs.derivative.ca/TOP_Class" in readback["official_sources"]


def test_audio_reactive_probe_summaries_include_runtime_activity_contract():
    probes = probe_summaries_for_profile("structural_visual_safe", "audio_reactive")
    activity = next(item for item in probes if item["probe_id"] == "audio_signal_activity")

    assert activity["readback_strategy"] == "chop_channel_delta_runtime"
    assert activity["cost_level"] == "cheap"
    assert activity["required_inputs"] == [
        "audiofileinCHOP",
        "audiodeviceinCHOP",
        "analyzeCHOP",
        "nullCHOP",
    ]
    assert "audio_analysis_channel_delta" in activity["metric_names"]
    assert "https://docs.derivative.ca/Analyze_CHOP" in activity["official_sources"]


def test_panel_ui_probe_summaries_include_runtime_state_readback_contract():
    probes = probe_summaries_for_profile("structural_visual_safe", "panel_ui")
    readback = next(item for item in probes if item["probe_id"] == "panel_state_readback")

    assert readback["readback_strategy"] == "chop_channel_presence_runtime"
    assert readback["cost_level"] == "cheap"
    assert readback["required_inputs"] == ["panelCHOP", "nullCHOP"]
    assert "panel_state_channel_count" in readback["metric_names"]
    assert "panel_state_sample_count" in readback["metric_names"]
    assert "https://docs.derivative.ca/Panel_CHOP" in readback["official_sources"]
    assert "https://docs.derivative.ca/Null_CHOP" in readback["official_sources"]


def test_pop_probe_summaries_include_runtime_bounds_readback_contract():
    probes = probe_summaries_for_profile("structural_visual_safe", "pop")
    bounds = next(item for item in probes if item["probe_id"] == "finite_pop_bounds")

    assert bounds["readback_strategy"] == "pop_bounds_runtime"
    assert bounds["cost_level"] == "cheap"
    assert bounds["required_inputs"] == ["nullPOP"]
    assert bounds["metric_names"] == ["pop_bounds_finite"]
    assert "https://docs.derivative.ca/POP" in bounds["official_sources"]


def test_pop_attribute_probe_summaries_include_runtime_inspect_contracts():
    expected = {"pop", "glsl_pop"}

    for profile in expected:
        probes = probe_summaries_for_profile("structural_visual_safe", profile)
        attributes = next(item for item in probes if item["probe_id"] == "attribute_sample_available")

        assert attributes["readback_strategy"] == "pop_attribute_metadata_runtime"
        assert attributes["cost_level"] == "cheap"
        assert attributes["required_inputs"] == ["nullPOP"]
        assert attributes["metric_names"] == ["pop_attribute_count_present"]
        assert "https://docs.derivative.ca/POP" in attributes["official_sources"]


def test_render_pipeline_probe_summaries_include_camera_frustum_runtime_contract():
    probes = probe_summaries_for_profile("structural_visual_safe", "render_pipeline")
    coverage = next(item for item in probes if item["probe_id"] == "camera_frustum_coverage")

    assert coverage["readback_strategy"] == "render_camera_frustum_runtime"
    assert coverage["cost_level"] == "cheap"
    assert coverage["required_inputs"] == ["renderTOP", "cameraCOMP", "geometryCOMP"]
    assert coverage["metric_names"] == ["render_camera_ref_bound", "render_geometry_ref_bound"]
    assert "https://docs.derivative.ca/Render_TOP" in coverage["official_sources"]
    assert "https://docs.derivative.ca/Camera_COMP" in coverage["official_sources"]
    assert "https://docs.derivative.ca/Geometry_COMP" in coverage["official_sources"]


def test_glsl_compile_probe_summaries_include_runtime_node_error_contracts():
    expected = {
        "glsl": "shader_compile_clean",
        "glsl_material": "material_compile_clean",
        "glsl_pop": "pop_shader_compile_clean",
    }

    for profile, metric_name in expected.items():
        probes = probe_summaries_for_profile("structural_visual_safe", profile)
        compile_state = next(item for item in probes if item["probe_id"] == "compile_state")

        assert compile_state["readback_strategy"] == "node_errors_runtime"
        assert compile_state["cost_level"] == "cheap"
        assert compile_state["metric_names"] == [metric_name]
        assert any(
            source.startswith("https://docs.derivative.ca/GLSL_")
            for source in compile_state["official_sources"]
        )


def test_dat_callback_guard_probe_summary_includes_runtime_content_readback_contract():
    probes = probe_summaries_for_profile("structural_visual_safe", "dat_protocol")
    guard = next(item for item in probes if item["probe_id"] == "callback_guard_present")

    assert guard["readback_strategy"] == "node_content_runtime"
    assert guard["cost_level"] == "cheap"
    assert guard["required_inputs"] == ["datexecuteDAT"]
    assert guard["metric_names"] == ["modern_table_change_callback_present"]
    assert "https://docs.derivative.ca/DAT_Execute_DAT" in guard["official_sources"]


def test_probe_summaries_exclude_expensive_probes_by_default():
    cheap = probe_summaries_for_profile("structural_visual_safe", "glsl")
    all_probes = probe_summaries_for_profile("structural_visual_safe", "glsl", include_expensive=True)
    opt_in = probe_summaries_for_profile("structural_visual_expensive", "glsl")

    assert cheap
    assert all(item["cost_level"] != "expensive" for item in cheap)
    assert any(item["probe_id"] == "compile_state" for item in cheap)
    assert any(
        item["probe_id"] == "nonblack_output" and item["cost_level"] == "expensive" for item in all_probes
    )
    assert any(item["probe_id"] == "nonblack_output" and item["cost_level"] == "expensive" for item in opt_in)
    assert len(all_probes) > len(cheap)


def test_validation_report_includes_profile_probe_summaries():
    report = build_validation_report_v2(
        target_root="/project1",
        profile="structural_visual_safe",
        concept_profile="glsl",
        patch_result=None,
    )

    profile_probes = report.cheap_metrics["profile_probes"]
    assert any(item["probe_id"] == "compile_state" for item in profile_probes)
    assert all(item["cost_level"] != "expensive" for item in profile_probes)
    assert report.checks == checks_for_profile("structural_visual_safe", "glsl")


def test_expensive_validation_report_includes_optional_top_probe_summaries():
    report = build_validation_report_v2(
        target_root="/project1",
        profile="structural_visual_expensive",
        concept_profile="render_pipeline",
        patch_result=None,
    )

    profile_probes = report.cheap_metrics["profile_probes"]
    assert any(item["probe_id"] == "render_top_output" for item in profile_probes)
    assert any(item["cost_level"] == "expensive" for item in profile_probes)
    assert "graph_structure" in report.checks
    assert "render_top_output" in report.checks


def test_concept_compiled_report_includes_assembly_macro_shell_probe():
    report = build_validation_report_v2(
        target_root="/project1/tdpilot_concept",
        profile="structural_visual_safe",
        concept_profile="concept_compiled",
        patch_result=None,
    )

    profile_probes = report.cheap_metrics["profile_probes"]
    shell_probe = next(item for item in profile_probes if item["probe_id"] == "component_shell_present")

    assert "component_shell_present" in report.checks
    assert shell_probe["required_inputs"] == ["baseCOMP"]
    assert "component_shell_present" in shell_probe["metric_names"]
    assert "https://docs.derivative.ca/Base_COMP" in shell_probe["official_sources"]


def test_concept_compiled_output_probe_covers_all_stable_output_families():
    report = build_validation_report_v2(
        target_root="/project1/tdpilot_concept",
        profile="structural_visual_safe",
        concept_profile="concept_compiled",
        patch_result=None,
    )

    profile_probes = report.cheap_metrics["profile_probes"]
    output_probe = next(item for item in profile_probes if item["probe_id"] == "output_node_present")

    assert {"nullTOP", "nullCHOP", "nullDAT", "nullPOP", "textDAT"}.issubset(
        set(output_probe["required_inputs"])
    )
    assert "https://docs.derivative.ca/Null_DAT" in output_probe["official_sources"]
    assert "https://docs.derivative.ca/Null_POP" in output_probe["official_sources"]
