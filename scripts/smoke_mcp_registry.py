#!/usr/bin/env python3
"""Smoke-check MCP registry surfaces (tools/resources) without TouchDesigner runtime."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

import td_mcp.server as server

REQUIRED_TOOLS = {
    "td_get_info",
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
    "td_create_macro",
    "td_list_macros",
    "td_get_macro_params",
    "td_get_capabilities",
    "td_get_server_metrics",
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
    "td_set_param_bounds",
    "td_clear_param_bounds",
    "td_detect_instability",
    "td_emergency_stabilize",
    "td_snapshot_scene",
    "td_list_snapshots",
    "td_diff_snapshots",
    "td_restore_snapshot",
    "td_get_state_vector",
    "td_get_timescale_state",
    "td_memory_learn",
    "td_memory_save",
    "td_memory_recall",
    "td_memory_replay",
    "td_memory_favorite",
    "td_memory_promote",
    "td_memory_preferences",
    "td_memory_list",
}


async def run_smoke(min_tools: int) -> dict[str, Any]:
    tools = await server.mcp.list_tools()
    tool_names = {tool.name for tool in tools}

    resources = await server.mcp.list_resources()
    resource_templates = await server.mcp.list_resource_templates()

    missing_tools = sorted(REQUIRED_TOOLS - tool_names)

    return {
        "schema_version": 1,
        "tool_count": len(tool_names),
        "resource_count": len(resources),
        "resource_template_count": len(resource_templates),
        "missing_required_tools": missing_tools,
        "ok": len(tool_names) >= min_tools and not missing_tools,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-check TDPilot MCP registry")
    parser.add_argument("--min-tools", type=int, default=86)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = asyncio.run(run_smoke(min_tools=args.min_tools))
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
