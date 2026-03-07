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
    }

    missing = expected - names
    assert not missing, f"Missing expected tools: {sorted(missing)}"
    assert len(names) >= 63
