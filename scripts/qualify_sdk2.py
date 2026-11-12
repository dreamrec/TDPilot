#!/usr/bin/env python3
"""Real stdio SDK 2/legacy qualification, including live TD transaction recovery."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
import traceback
import uuid
from pathlib import Path

from mcp.client import Client

from mcp import StdioServerParameters
from td_mcp.events.uri import par_uri
from td_mcp.models.patch import PatchOperation, PatchPlan, ValidationPlan
from td_mcp.registry.tools_batch import _parse_content_blocks
from td_mcp.td_client import TDClient


async def qualify(mode, *, url=None):
    env = {**os.environ, "TD_MCP_WS_PORT": "0", "TD_MCP_TOOL_PROFILE": "full", "TD_MCP_TRANSPORT": "stdio"}
    server = StdioServerParameters(
        command=sys.executable, args=["-m", "td_mcp"], cwd=str(Path(__file__).resolve().parents[1]), env=env
    )
    if url is not None:
        server = url
    root = None
    td = TDClient()
    report = {"mode": mode, "transport": "streamable-http" if url else "stdio", "ok": False}
    try:
        async with Client(server, mode=mode, read_timeout_seconds=60) as client:
            report["protocol"] = client.protocol_version
            report["server"] = client.server_info.model_dump(mode="json")
            tools = (await client.list_tools()).tools
            report["tools"] = len(tools)
            assert len(tools) == 114
            assert next(t for t in tools if t.name == "td_get_info").annotations.read_only_hint
            batch = _parse_content_blocks(
                await client.call_tool(
                    "td_tool_batch",
                    {
                        "calls": [
                            {"tool": "td_get_info", "args": {}},
                            {"tool": "td_get_release_delta", "args": {"build": "2025.33230"}},
                        ]
                    },
                )
            )
            assert all(r["ok"] for r in batch["results"]), batch
            report["batch_ok"] = True
            for uri in ["td://project/state", "ui://tdpilot/cockpit.html", par_uri("/project1/tdpilot", "w")]:
                resource = await client.read_resource(uri)
                assert resource.contents, uri
            report["resources_ok"] = True
            root = (
                await td.request(
                    "node/create",
                    {
                        "parent_path": "/project1",
                        "node_type": "baseCOMP",
                        "name": "tdpilot_sdk2_" + uuid.uuid4().hex[:8],
                    },
                )
            )["node"]["path"]
            plan = PatchPlan(
                target_root=root,
                source="operations",
                undo_label="SDK2 rollback qualification",
                validation_plan=ValidationPlan(target_root=root),
                operations=[
                    PatchOperation(
                        kind="create_node", target=root, args={"op_type": "constantCHOP", "name": "created"}
                    ),
                    PatchOperation(
                        kind="create_node", target=root, args={"op_type": "notARealTOP", "name": "fail"}
                    ),
                ],
            )
            result = _parse_content_blocks(
                await client.call_tool(
                    "td_transaction_apply",
                    {
                        "plan": plan.model_dump(mode="json"),
                        "options": {"preflight": False, "snapshot_before": False},
                    },
                )
            )
            transaction = result["result"]
            report["transaction"] = {
                k: transaction[k]
                for k in ["status", "rollback_performed", "rollback_verification", "needs_manual_recovery"]
            }
            assert transaction["status"] == "rolled_back" and not transaction["needs_manual_recovery"], (
                transaction
            )
            assert not (await td.request("nodes", {"path": root}))["nodes"]
            report["ok"] = True
    except Exception as exc:
        report["failure"] = traceback.format_exc()
    finally:
        if root:
            report["cleanup"] = await td.request("node/delete", {"path": root})
        await td.close()
    return report


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports = []
    for mode in ["auto", "legacy"]:
        reports.append(await qualify(mode))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = {
        **os.environ,
        "TD_MCP_WS_PORT": "0",
        "TD_MCP_TOOL_PROFILE": "full",
        "TD_MCP_TRANSPORT": "streamable-http",
        "TD_MCP_HTTP_HOST": "127.0.0.1",
        "TD_MCP_HTTP_PORT": str(port),
    }
    with args.output.with_suffix(".http.log").open("w") as log:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "td_mcp", env=env, stdout=log, stderr=log
        )
        try:
            for attempt in range(100):
                if process.returncode is not None:
                    raise RuntimeError("HTTP server exited during startup")
                try:
                    reader, writer = await asyncio.open_connection("127.0.0.1", port)
                    writer.close()
                    await writer.wait_closed()
                    break
                except OSError:
                    await asyncio.sleep(0.1)
            else:
                raise RuntimeError("HTTP server startup timed out")
            for mode in ["auto", "legacy"]:
                reports.append(await qualify(mode, url=f"http://127.0.0.1:{port}/mcp"))
        finally:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=10)
            except TimeoutError:
                process.kill()
                await process.wait()
    args.output.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(json.dumps(reports, indent=2))
    if not all(r["ok"] for r in reports):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
