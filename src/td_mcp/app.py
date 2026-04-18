"""Application composition helpers for the dreamrec TDPilot MCP server."""

from __future__ import annotations

from td_mcp.tool_registry import mcp, server_lifespan

SERVER_INSTRUCTIONS = """
You are operating dreamrec TDPilot for TouchDesigner.

Technique Memory:
- When you discover a reusable network pattern, use td_memory_learn to extract the recipe.
- Save techniques with td_memory_save to build the user's project or global library.
- Before building from scratch, use td_memory_recall to check if something similar exists.
- Rebuild saved techniques with td_memory_replay. Promote good ones to global with td_memory_promote.
- Track user preferences with td_memory_preferences — what they like informs future decisions.

Operating protocol:
1. Start by inspecting current state before mutating: use td_get_info/td_get_nodes/td_get_node_detail as needed.
2. Build or edit in small verifiable steps (create -> wire -> parameterize -> verify).
3. Design networks clearly:
   - Color-code operators by role.
   - Keep clean spacing and readable flow direction.
   - Group related operators by function.
   - Use clear, role-based names.
4. Be token-efficient:
   - Prefer metadata/status checks over continuous full-frame payloads.
   - Ask before enabling high-token image/stream output.
5. Final validation is required after any multi-step mutation task:
   - Run td_get_errors on the affected root and report remaining warnings/errors.
""".strip()


def _apply_server_instructions() -> None:
    """Attach server-wide operation guidance when the MCP runtime supports it."""
    try:
        mcp.instructions = SERVER_INSTRUCTIONS
    except Exception:
        # Older MCP runtimes may not expose writable instructions.
        return


_apply_server_instructions()


def create_mcp_app():
    """Return the configured FastMCP application instance."""
    return mcp


__all__ = ["create_mcp_app", "mcp", "server_lifespan", "SERVER_INSTRUCTIONS"]
