import asyncio
import json
import os
import subprocess
import sys

import pytest

from td_mcp.tool_profiles import BUILD_TOOLS, INSPECT_TOOLS, ProfiledMCPServer


@pytest.mark.parametrize("profile,names", [("inspect", INSPECT_TOOLS), ("build", BUILD_TOOLS)])
def test_real_profile_discovery_is_complete_and_disabled_dispatch_is_blocked(profile, names):
    script = """
import asyncio, json
from td_mcp.tool_registry import mcp
from td_mcp.registry.tools_batch import _dispatch_async
async def main():
    tools = await mcp.list_tools()
    print(json.dumps([t.name for t in tools]))
    try:
        await mcp.call_tool("td_exec_python", {"code": "raise RuntimeError('must not execute')"})
    except Exception as exc:
        assert "Unknown tool" in str(exc), str(exc)
    else:
        raise AssertionError("excluded tool remained callable")
    results = await _dispatch_async([{"tool": "td_exec_python", "args": {"code": "pass"}}])
    assert results[0]["ok"] is False
    assert "Unknown tool" in results[0]["error"]
asyncio.run(main())
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "TD_MCP_TOOL_PROFILE": profile},
        text=True,
        capture_output=True,
        check=True,
    )
    assert set(json.loads(result.stdout)) == names


def test_profile_default_and_invalid_configuration():
    server = ProfiledMCPServer("test", tool_profile="full")
    server.add_tool(lambda: "ok", name="custom_tool")
    assert [t.name for t in asyncio.run(server.list_tools())] == ["custom_tool"]
    with pytest.raises(ValueError, match="full, inspect, or build"):
        ProfiledMCPServer("test", tool_profile="typo")
