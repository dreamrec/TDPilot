import argparse
import json

import td_mcp.server as server


def test_build_profile_config_uses_npx_tdpilot():
    profile = server._build_profile_config("claude-desktop", "touchdesigner")
    td_cfg = profile["mcpServers"]["touchdesigner"]

    assert td_cfg["command"] == "npx"
    assert td_cfg["args"] == ["-y", "tdpilot"]
    assert td_cfg["env"]["TD_MCP_PORT"] == "9981"


def test_merge_profile_preserves_existing_servers():
    existing = {
        "mcpServers": {
            "foo": {
                "command": "bar",
                "args": [],
            }
        }
    }
    profile = server._build_profile_config("generic", "touchdesigner")

    merged = server._merge_profile(existing, profile)

    assert "foo" in merged["mcpServers"]
    assert "touchdesigner" in merged["mcpServers"]


def test_run_init_command_writes_config(tmp_path):
    out = tmp_path / "config.json"
    args = argparse.Namespace(
        client="generic",
        server_name="touchdesigner",
        output=str(out),
        print_only=False,
        force=False,
    )

    code = server._run_init_command(args)
    payload = json.loads(out.read_text(encoding="utf-8"))

    assert code == 0
    assert "mcpServers" in payload
    assert "touchdesigner" in payload["mcpServers"]


def test_collect_doctor_report_skip_td_check():
    report = server._collect_doctor_report(timeout=0.2, skip_td_check=True, strict=False)

    assert report["schema_version"] == 1
    checks = {item["name"]: item for item in report["checks"]}
    assert checks["td_health"]["status"] == "skip"
    assert checks["transport_config"]["status"] in {"pass", "fail"}


def test_runtime_health_from_payloads():
    health = server._runtime_health_from_payloads(
        cooking={
            "fps": 25.0,
            "nodes": [
                {"path": "/project1/op1", "cookTime": 0.02},
                {"path": "/project1/op2", "cookTime": 0.03},
            ],
        },
        errors={"issues": [{"path": "/project1/op1", "error": "boom"}]},
    )

    assert health["fps"] == 25.0
    assert health["issues_count"] == 1
    assert health["unstable"] is True
