import asyncio

from _constants import EXPECTED_MIN_TOOL_COUNT

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
    assert len(names) >= EXPECTED_MIN_TOOL_COUNT


def test_manifest_surface_matches_registry():
    """mcp/manifest.json surface counts must match what the registry registers.

    Resources with `{param}` segments are templates; the rest are static.
    Regression (v1.4.3): manifest claimed resource_template_count=7, but one of
    the seven decorated resources (td://timeline/state) is static.

    v1.5.0 Phase 2: resources moved to
    ``src/td_mcp/registry/resources.py``; this test now scans the merged
    source across ``tool_registry.py`` + ``registry/*.py``.
    """
    import json
    import re
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent
    manifest = json.loads((repo / "mcp" / "manifest.json").read_text())

    src_root = repo / "src" / "td_mcp"
    sources = [(src_root / "tool_registry.py").read_text()]
    pkg_dir = src_root / "registry"
    if pkg_dir.is_dir():
        for sub in sorted(pkg_dir.glob("*.py")):
            if sub.name == "__init__.py":
                continue
            sources.append(sub.read_text())
    source = "\n".join(sources)

    uris = re.findall(r'@mcp\.resource\("([^"]+)"', source)
    assert uris, "No @mcp.resource decorators found across tool_registry.py + registry/*.py"
    templates = [u for u in uris if "{" in u]
    statics = [u for u in uris if "{" not in u]

    surface = manifest["surface"]
    assert surface["resource_template_count"] == len(templates), (
        f"manifest resource_template_count={surface['resource_template_count']} "
        f"but source has {len(templates)} template(s): {templates}"
    )
    assert surface.get("static_resource_count", 0) == len(statics), (
        f"manifest static_resource_count={surface.get('static_resource_count', 0)} "
        f"but source has {len(statics)} static resource(s): {statics}"
    )


def test_manifest_tool_count_matches_registry():
    """manifest.tool_count must equal the number of @mcp.tool() decorators.

    v1.5.0 Phase 2 module split: decorators are split across
    ``tool_registry.py`` and themed submodules under ``registry/``. This
    test sums across all of them.
    """
    import json
    import re
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent
    manifest = json.loads((repo / "mcp" / "manifest.json").read_text())

    tool_decorators: list[str] = []
    root_src = (repo / "src" / "td_mcp" / "tool_registry.py").read_text()
    tool_decorators.extend(re.findall(r"@mcp\.tool\(", root_src))

    registry_pkg = repo / "src" / "td_mcp" / "registry"
    if registry_pkg.is_dir():
        for submodule in sorted(registry_pkg.glob("tools_*.py")):
            tool_decorators.extend(re.findall(r"@mcp\.tool\(", submodule.read_text()))

    assert manifest["surface"]["tool_count"] == len(tool_decorators), (
        f"manifest tool_count={manifest['surface']['tool_count']} "
        f"but source has {len(tool_decorators)} @mcp.tool decorators "
        f"across tool_registry.py + registry/tools_*.py"
    )
