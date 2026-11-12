"""Opt-in tool surfaces. Full remains the backwards-compatible default.

Registration filtering removes tools from both discovery and dispatch, including
batch calls. Profiles reduce model context; they are not a security sandbox.
"""

import os

from mcp.server.mcpserver import MCPServer
from mcp.server.subscriptions import InMemorySubscriptionBus, ResourceUpdated

INSPECT_TOOLS = frozenset(
    {
        "td_tool_batch",
        "td_get_info",
        "td_get_capabilities",
        "td_sync_status",
        "td_sync_diagnose",
        "td_get_nodes",
        "td_get_node_detail",
        "td_get_params",
        "td_get_connections",
        "td_get_content",
        "td_get_errors",
        "td_get_focus",
        "td_search_nodes",
        "td_list_families",
        "td_chop_data",
        "td_pop_inspect",
        "td_geometry_data",
        "td_cooking_info",
        "td_get_state_vector",
        "td_search_official_docs",
        "td_get_operator_doc",
        "td_get_param_help",
        "td_lookup_snippets",
        "td_get_release_delta",
        "td_get_build_compatibility",
        "td_capture_frame",
        "td_analyze_frame",
        "td_describe_surface",
    }
)
BUILD_TOOLS = INSPECT_TOOLS | frozenset(
    {
        "td_brain_plan",
        "td_brain_ground",
        "td_brain_propose",
        "td_brain_execute",
        "td_transaction_apply",
        "td_create_node",
        "td_set_params",
        "td_set_content",
        "td_connect_nodes",
        "td_delete_node",
        "td_disconnect",
        "td_pulse_param",
        "td_snapshot_scene",
        "td_list_snapshots",
        "td_restore_snapshot",
        "td_detect_instability",
        "td_emergency_stabilize",
        "td_preflight_patch",
        "td_audit_project",
        "td_memory_recall",
        "td_search_popx_docs",
        "td_get_popx_operator",
    }
)
PROFILES = {"full": None, "inspect": INSPECT_TOOLS, "build": BUILD_TOOLS}


class ProfiledMCPServer(MCPServer):
    def __init__(self, *args, tool_profile: str | None = None, **kwargs):
        self.tool_profile = (
            (tool_profile if tool_profile is not None else os.environ.get("TD_MCP_TOOL_PROFILE", "full"))
            .strip()
            .lower()
        )
        if self.tool_profile not in PROFILES:
            raise ValueError("TD_MCP_TOOL_PROFILE must be full, inspect, or build")
        self._td_subscription_bus = InMemorySubscriptionBus()
        super().__init__(*args, subscriptions=self._td_subscription_bus, **kwargs)

    def add_tool(self, fn, name=None, **kwargs):
        allowed = PROFILES[self.tool_profile]
        if allowed is None or (name or fn.__name__) in allowed:
            return super().add_tool(fn, name=name, **kwargs)
        return None

    async def notify_resource_updated(self, uri: str) -> None:
        """Publish TD events to SDK 2 subscription streams."""
        await self._td_subscription_bus.publish(ResourceUpdated(uri=uri))
