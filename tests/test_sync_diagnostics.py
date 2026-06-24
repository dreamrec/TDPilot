from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import td_mcp.tool_registry as _registry
from td_mcp.registry import tools_meta


class _SkewedClient:
    async def request(self, endpoint, body=None):
        if endpoint == "health":
            return {
                "status": "ok",
                "server_version": "2.0.0",
                "api_version": "2.0.1",
            }
        if endpoint == "info":
            return {
                "mcp_server_version": "2.0.0",
                "mcp_component_version": "2.0.1",
            }
        raise AssertionError(endpoint)


class _TouchDesignerInfoClient:
    async def request(self, endpoint, body=None):
        if endpoint == "health":
            return {"status": "ok", "api_version": "2.0.2"}
        if endpoint == "info":
            return {
                "api_version": "2.0.2",
                "product": "TouchDesigner",
                "version": "099",
            }
        raise AssertionError(endpoint)


def test_sync_diagnose_process_parser_ignores_claude_plugin_manifest_json():
    from td_mcp.sync_diagnostics import _process_root_from_command

    command = (
        "/Applications/Claude.app/Contents/MacOS/claude "
        '--mcp-config \'{"mcpServers":{"tdpilot":{"command":"uv",'
        '"args":["run","--directory","${CODEX_PLUGIN_ROOT}","tdpilot"]}}}\' '
        "--plugin-dir <USER_HOME>/.claude/plugins/cache/dreamrec-TDPilot/tdpilot/2.0.1"
    )

    assert _process_root_from_command(command) is None


def test_sync_diagnose_process_parser_ignores_non_tdpilot_python_process_with_plugin_dir():
    from td_mcp.sync_diagnostics import _process_root_from_command

    command = (
        "<USER_HOME>/Tools/ghidra-mcp/.venv/bin/python "
        "<USER_HOME>/Tools/ghidra-mcp/bridge_mcp_ghidra.py "
        "--plugin-dir <USER_HOME>/.claude/plugins/cache/dreamrec-TDPilot/tdpilot/2.0.2"
    )

    assert _process_root_from_command(command) is None


@pytest.mark.asyncio
async def test_sync_diagnose_reports_version_skew_and_redacts_secret(tmp_path, monkeypatch):
    from td_mcp.sync_diagnostics import diagnose_sync

    env_file = tmp_path / ".tdpilot.env"
    env_file.write_text("TD_MCP_SHARED_SECRET=file-secret\n", encoding="utf-8")
    monkeypatch.setenv("TD_MCP_SHARED_SECRET", "process-secret")
    monkeypatch.setenv("TDPILOT_ENV_FILE", str(env_file))

    report = await diagnose_sync(
        client=_SkewedClient(),
        host="127.0.0.1",
        port=9981,
        include_live=True,
        local_version="2.0.2",
        installed_version="2.0.2",
        plugin_versions={"codex": ["2.0.2"]},
        running_processes=[],
    )
    encoded = json.dumps(report)

    assert report["schema_version"] == 1
    assert report["ok"] is False
    assert report["versions"]["local"] == "2.0.2"
    assert report["versions"]["running_mcp"] == "2.0.0"
    assert report["versions"]["td_component"] == "2.0.1"
    assert report["drift"]["version_mismatch"] is True
    assert report["auth"]["process_secret_fingerprint"].startswith("sha256:")
    assert report["auth"]["env_file_secret_fingerprint"].startswith("sha256:")
    assert report["auth"]["fingerprints_match"] is False
    assert "process-secret" not in encoded
    assert "file-secret" not in encoded


@pytest.mark.asyncio
async def test_sync_diagnose_does_not_treat_touchdesigner_product_version_as_mcp_version(
    tmp_path, monkeypatch
):
    from td_mcp.sync_diagnostics import diagnose_sync

    env_file = tmp_path / ".tdpilot.env"
    env_file.write_text("TD_MCP_SHARED_SECRET=same-secret\n", encoding="utf-8")
    monkeypatch.setenv("TD_MCP_SHARED_SECRET", "same-secret")
    monkeypatch.setenv("TDPILOT_ENV_FILE", str(env_file))

    report = await diagnose_sync(
        client=_TouchDesignerInfoClient(),
        include_live=True,
        local_version="2.0.2",
        installed_version="2.0.2",
        plugin_versions={"codex": ["2.0.2"]},
        install_roots={},
        running_processes=[],
    )

    assert report["live"]["reachable"] is True
    assert report["versions"]["td_component"] == "2.0.2"
    assert report["versions"]["running_mcp"] is None
    assert report["drift"]["version_mismatch"] is False


@pytest.mark.asyncio
async def test_sync_diagnose_reports_same_version_source_hash_drift(tmp_path, monkeypatch):
    from td_mcp.sync_diagnostics import diagnose_sync

    local_root = tmp_path / "local"
    install_root = tmp_path / "installed"
    for root, body in ((local_root, "new hardened body\n"), (install_root, "old stale body\n")):
        callbacks = root / "td_component" / "mcp_webserver_callbacks.py"
        callbacks.parent.mkdir(parents=True)
        callbacks.write_text(body, encoding="utf-8")
        (root / "pyproject.toml").write_text('[project]\nversion = "2.0.2"\n', encoding="utf-8")

    env_file = tmp_path / ".tdpilot.env"
    env_file.write_text("TD_MCP_SHARED_SECRET=same-secret\n", encoding="utf-8")
    monkeypatch.setenv("TD_MCP_SHARED_SECRET", "same-secret")
    monkeypatch.setenv("TDPILOT_ENV_FILE", str(env_file))

    report = await diagnose_sync(
        client=None,
        include_live=False,
        local_version="2.0.2",
        installed_version="2.0.2",
        plugin_versions={"codex": ["2.0.2"]},
        local_root=local_root,
        install_roots={"user": install_root},
        running_processes=[],
    )

    assert report["ok"] is False
    assert report["drift"]["source_hash_mismatch"] is True
    source_hashes = report["source_hashes"]
    assert source_hashes["local"]["present"] is True
    assert source_hashes["install_roots"]["user"]["present"] is True
    assert source_hashes["install_roots"]["user"]["matches_local"] is False
    assert any("source files differ" in item for item in report["recommendations"])


@pytest.mark.asyncio
async def test_sync_diagnose_reports_running_process_started_before_source_update(tmp_path, monkeypatch):
    from td_mcp.sync_diagnostics import diagnose_sync

    local_root = tmp_path / "local"
    callbacks = local_root / "td_component" / "mcp_webserver_callbacks.py"
    callbacks.parent.mkdir(parents=True)
    callbacks.write_text("current body\n", encoding="utf-8")
    (local_root / "pyproject.toml").write_text('[project]\nversion = "2.0.2"\n', encoding="utf-8")

    env_file = tmp_path / ".tdpilot.env"
    env_file.write_text("TD_MCP_SHARED_SECRET=same-secret\n", encoding="utf-8")
    monkeypatch.setenv("TD_MCP_SHARED_SECRET", "same-secret")
    monkeypatch.setenv("TDPILOT_ENV_FILE", str(env_file))

    report = await diagnose_sync(
        client=None,
        include_live=False,
        local_version="2.0.2",
        installed_version="2.0.2",
        plugin_versions={"codex": ["2.0.2"]},
        local_root=local_root,
        install_roots={},
        running_processes=[
            {
                "pid": 123,
                "root": str(local_root),
                "path": str(local_root),
                "version": "2.0.2",
                "stale_source": True,
                "process_secret_fingerprint": None,
            }
        ],
    )

    assert report["ok"] is False
    assert report["drift"]["running_process_mismatch"] is True
    assert report["running_processes"]["mismatches"] == [
        {
            "pid": 123,
            "root": str(local_root),
            "reasons": ["process_started_before_source_update"],
        }
    ]
    assert any("Restart running TDPilot MCP processes" in item for item in report["recommendations"])


@pytest.mark.asyncio
async def test_td_sync_diagnose_tool_is_registered(monkeypatch, tmp_path):
    env_file = tmp_path / ".tdpilot.env"
    env_file.write_text("TD_MCP_SHARED_SECRET=same-secret\n", encoding="utf-8")
    monkeypatch.setenv("TD_MCP_SHARED_SECRET", "same-secret")
    monkeypatch.setenv("TDPILOT_ENV_FILE", str(env_file))
    monkeypatch.setattr(_registry, "_get_client", lambda _ctx: _SkewedClient())
    monkeypatch.setattr(
        "td_mcp.sync_diagnostics._plugin_cache_versions",
        lambda: {"codex": ["2.0.2"]},
    )
    monkeypatch.setattr("td_mcp.sync_diagnostics._running_mcp_process_rows", lambda: [])
    ctx = SimpleNamespace(request_context=SimpleNamespace(lifespan_context={}))

    out = await tools_meta.td_sync_diagnose(ctx, include_live=True, check_remote=False)
    payload = json.loads(out)

    assert hasattr(_registry, "td_sync_diagnose")
    assert payload["success"] is True
    assert payload["diagnostic"]["ok"] is False
    assert payload["diagnostic"]["drift"]["version_mismatch"] is True
