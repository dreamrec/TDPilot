from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from mcp.client import Client
from mcp.server.mcpserver import Context
from mcp_types import CallToolResult, TextContent, ToolAnnotations

from td_mcp.events.event_manager import EventManager
from td_mcp.registry.tools_batch import _dispatch_async, _parse_content_blocks
from td_mcp.tool_profiles import ProfiledMCPServer


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_sdk2_tool_context_batch_errors_resources_and_annotations(mode, monkeypatch):
    @asynccontextmanager
    async def lifespan(server):
        yield {"sentinel": "same-request-services"}

    server = ProfiledMCPServer("sdk2-test", version="2.6.0", lifespan=lifespan)

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False))
    async def inspect_state(ctx: Context) -> dict:
        return {"state": ctx.request_context.lifespan_context["sentinel"]}

    @server.tool()
    async def batch(ctx: Context) -> dict:
        return {
            "results": await _dispatch_async(
                [{"tool": "inspect_state", "args": {}}, {"tool": "missing", "args": {}}], ctx
            )
        }

    @server.resource("test://state")
    def resource() -> str:
        return "cached state"

    monkeypatch.setattr("td_mcp.registry.tools_batch.mcp", server)
    async with Client(server, mode=mode) as client:
        tools = (await client.list_tools()).tools
        assert next(t for t in tools if t.name == "inspect_state").annotations.read_only_hint
        result = await client.call_tool("batch", {})
        assert not result.is_error
        entries = _parse_content_blocks(result)["results"]
        assert entries[0]["result"] == {"state": "same-request-services"}
        assert entries[1]["ok"] is False
        assert "Unknown tool" in entries[1]["error"]
        assert (await client.read_resource("test://state")).contents[0].text == "cached state"


@pytest.mark.asyncio
async def test_td_event_published_to_sdk2_subscription_bus():
    server = ProfiledMCPServer("event-test")
    events = []
    unsubscribe = server._td_subscription_bus.subscribe(events.append)
    manager = EventManager(server)
    await manager.set_state("td://timeline/state", {"frame": 1})
    unsubscribe()
    assert len(events) == 1
    assert events[0].uri == "td://timeline/state"


def test_sdk2_error_flag_is_not_misreported_as_success():
    result = CallToolResult(is_error=True, content=[TextContent(type="text", text='{"ok": true}')])
    assert "error" in _parse_content_blocks(result)


def test_sdk2_string_result_wrapper_is_unwrapped():
    text = '{"success": true, "value": 7}'
    result = CallToolResult(
        content=[TextContent(type="text", text=text)], structured_content={"result": text}
    )
    assert _parse_content_blocks(result) == {"success": True, "value": 7}


@pytest.mark.asyncio
async def test_real_td_resource_template_accepts_operator_paths_but_rejects_traversal():
    import json

    from td_mcp.events.uri import par_uri
    from td_mcp.tool_registry import mcp

    contents = list(await mcp.read_resource(par_uri("/project1/noise1", "period")))
    assert json.loads(contents[0].content)["path"] == "/project1/noise1"
    with pytest.raises(Exception, match="Unknown resource"):
        await mcp.read_resource(par_uri("/../../sys", "period"))
