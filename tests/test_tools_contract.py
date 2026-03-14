import asyncio

import td_mcp.server as server


def test_tool_registry_contains_core_and_v2_surfaces():
    tools = asyncio.run(server.mcp.list_tools())
    names = {tool.name for tool in tools}

    expected = {
        # core
        "td_get_info",
        "td_get_capabilities",
        "td_get_server_metrics",
        "td_get_nodes",
        "td_set_params",
        "td_create_node",
        "td_connect_nodes",
        "td_screenshot",
        "td_geometry_data",
        "td_pop_inspect",
        "td_exec_python",
        "td_custom_parameters",
        "td_project_lifecycle",
        # macros/events/vision
        "td_create_macro",
        "td_list_macros",
        "td_get_macro_params",
        "td_subscribe",
        "td_unsubscribe",
        "td_get_events",
        "td_capture_and_analyze",
        "td_monitor_visual",
        "td_stop_monitor_visual",
        "td_stream_top",
        "td_stop_stream_top",
        "td_optimize_visual",
        "td_describe_dynamics",
        # safety/memory
        "td_set_param_bounds",
        "td_clear_param_bounds",
        "td_detect_instability",
        "td_emergency_stabilize",
        "td_snapshot_scene",
        "td_list_snapshots",
        "td_diff_snapshots",
        "td_restore_snapshot",
        # semantics surfaces
        "td_get_state_vector",
        "td_get_timescale_state",
        # technique memory
        "td_memory_learn",
        "td_memory_save",
        "td_memory_recall",
        "td_memory_replay",
        "td_memory_favorite",
        "td_memory_promote",
        "td_memory_preferences",
        "td_memory_list",
        "td_memory_export",
        "td_memory_import",
        # v1.3.0 knowledge tools
        "td_search_official_docs",
        "td_get_operator_doc",
        "td_get_param_help",
        "td_lookup_snippets",
        "td_lookup_palette_component",
        "td_get_release_delta",
        "td_get_build_compatibility",
        "td_describe_surface",
        # v1.3.1 planning & validation tools
        "td_plan_patch",
        "td_preflight_patch",
        "td_validate_recipe",
        "td_audit_project",
        # v1.3.2 vision diagnostics
        "td_capture_frame",
        "td_analyze_frame",
        # v1.3.2 TD 2025 native system tools
        "td_python_env_status",
        "td_threading_status",
        "td_logger_status",
        "td_tdresources_inspect",
        "td_component_standardize",
        "td_color_pipeline",
        # v1.3.2 official recommendation tools
        "td_recommend_official_component",
        "td_find_official_example",
        "td_explain_better_way",
    }

    missing = expected - names
    assert not missing, f"Missing expected tools: {sorted(missing)}"
    assert len(names) >= 88
