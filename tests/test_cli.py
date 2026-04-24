import argparse
import json

import pytest

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


# ---------------------------------------------------------------------------
# Doctor auth-config gate — regression for v1.4.3 plugin-install auth path.
# ---------------------------------------------------------------------------


def test_doctor_flags_auth_required_without_secret(monkeypatch, capsys):
    """doctor must fail (non-zero exit) when TD_MCP_REQUIRE_AUTH=1 but no secret."""
    monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "1")
    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)

    with pytest.raises(SystemExit) as exc:
        server.main(["doctor", "--skip-td-check"])
    assert exc.value.code != 0

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "auth" in combined.lower() or "SHARED_SECRET" in combined


def test_doctor_passes_auth_check_when_secret_set(monkeypatch, capsys):
    """doctor's auth check must pass when required + secret set."""
    monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "1")
    monkeypatch.setenv("TD_MCP_SHARED_SECRET", "x" * 32)

    with pytest.raises(SystemExit) as exc:
        server.main(["doctor", "--skip-td-check"])
    # Exit code is about overall doctor health (tox etc). The auth line itself
    # must not be a FAIL; grep the output.
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "auth_config" in combined
    # FAIL marker should not be on the auth line.
    auth_line = next((line for line in combined.splitlines() if "auth_config" in line), "")
    assert "FAIL" not in auth_line


def test_doctor_passes_auth_check_when_auth_disabled(monkeypatch, capsys):
    monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "0")
    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)

    with pytest.raises(SystemExit):
        server.main(["doctor", "--skip-td-check"])
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    auth_line = next((line for line in combined.splitlines() if "auth_config" in line), "")
    assert "FAIL" not in auth_line


# ---------------------------------------------------------------------------
# Doctor tool-count drift — regression for v1.4.4 reliability release.
# Compares @mcp.tool() decorator count in tool_registry.py against the
# manifest.surface.tool_count value; emits warn on drift, pass on match.
# ---------------------------------------------------------------------------


def test_doctor_tool_count_drift_check_present():
    """doctor must include a `tool_count_drift` check in its report."""
    report = server._collect_doctor_report(timeout=0.2, skip_td_check=True, strict=False)
    names = [item["name"] for item in report["checks"]]
    assert "tool_count_drift" in names


def test_doctor_tool_count_drift_passes_on_sync():
    """When manifest and registry agree, the drift check emits pass."""
    report = server._collect_doctor_report(timeout=0.2, skip_td_check=True, strict=False)
    drift = next(item for item in report["checks"] if item["name"] == "tool_count_drift")
    # Current repo: manifest and registry match at 92 tools.
    assert drift["status"] == "pass", f"detail: {drift['detail']}"
    # Detail should include both counts so developers can see what's compared.
    assert "registry=" in drift["detail"] or "source=" in drift["detail"]
    assert "manifest=" in drift["detail"]


def test_doctor_tool_count_drift_warns_on_mismatch(monkeypatch, tmp_path):
    """When manifest disagrees with registry, the drift check emits warn."""
    # Stage a manifest with a bogus tool_count and point the doctor's lookup
    # at it. The loader reads mcp/manifest.json relative to repo root, so we
    # temporarily rewrite the file, then the test fixture restores it.
    import json
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent
    manifest_path = repo / "mcp" / "manifest.json"
    original = manifest_path.read_text()
    try:
        data = json.loads(original)
        data["surface"]["tool_count"] = 9999  # intentionally wrong
        manifest_path.write_text(json.dumps(data, indent=2) + "\n")

        report = server._collect_doctor_report(timeout=0.2, skip_td_check=True, strict=False)
        drift = next(item for item in report["checks"] if item["name"] == "tool_count_drift")
        assert drift["status"] == "warn"
        assert "9999" in drift["detail"] or "mismatch" in drift["detail"].lower()
    finally:
        manifest_path.write_text(original)


# ---------------------------------------------------------------------------
# Install-profile unification (v1.4.4): --auth / --generate-secret / --shared-secret
# Lets `tdpilot init` emit the same auth-enabled shape install.sh/ps1 already
# produce, so all five install paths can converge on a single config builder.
# ---------------------------------------------------------------------------


def test_build_profile_no_auth_is_default():
    profile = server._build_profile_config("generic", "td")
    env = profile["mcpServers"]["td"]["env"]
    assert "TD_MCP_REQUIRE_AUTH" not in env
    assert "TD_MCP_SHARED_SECRET" not in env


def test_build_profile_auth_without_secret_embeds_require_only():
    profile = server._build_profile_config("generic", "td", auth_required=True)
    env = profile["mcpServers"]["td"]["env"]
    assert env["TD_MCP_REQUIRE_AUTH"] == "1"
    # Intentionally NO secret — the server startup gate trips loudly.
    assert "TD_MCP_SHARED_SECRET" not in env


def test_build_profile_auth_with_secret_embeds_both():
    profile = server._build_profile_config("generic", "td", auth_required=True, shared_secret="s" * 32)
    env = profile["mcpServers"]["td"]["env"]
    assert env["TD_MCP_REQUIRE_AUTH"] == "1"
    assert env["TD_MCP_SHARED_SECRET"] == "s" * 32


def test_generate_shared_secret_is_urlsafe_and_sufficiently_long():
    sec = server._generate_shared_secret()
    # token_urlsafe(32) produces ~43 chars (base64url of 32 bytes, no padding)
    assert len(sec) >= 32
    # URL-safe charset: letters, digits, -, _
    import re as _re

    assert _re.match(r"^[A-Za-z0-9_-]+$", sec)


def test_generate_shared_secret_is_unique_per_call():
    """Sanity: we're not returning a constant by accident."""
    seen = {server._generate_shared_secret() for _ in range(10)}
    assert len(seen) == 10


def test_init_with_auth_and_generate_writes_secret(tmp_path, capsys):
    out = tmp_path / "config.json"
    args = argparse.Namespace(
        client="generic",
        server_name="td",
        output=str(out),
        print_only=False,
        force=False,
        auth=True,
        generate_secret=True,
        shared_secret="",
    )
    assert server._run_init_command(args) == 0
    data = json.loads(out.read_text())
    env = data["mcpServers"]["td"]["env"]
    assert env["TD_MCP_REQUIRE_AUTH"] == "1"
    assert env["TD_MCP_SHARED_SECRET"]  # non-empty
    # Secret was printed to stdout for the user to save
    printed = capsys.readouterr().out
    assert env["TD_MCP_SHARED_SECRET"] in printed


def test_init_with_auth_and_supplied_secret(tmp_path):
    out = tmp_path / "config.json"
    args = argparse.Namespace(
        client="generic",
        server_name="td",
        output=str(out),
        print_only=False,
        force=False,
        auth=True,
        generate_secret=False,
        shared_secret="pre-provisioned-secret-" + "x" * 32,
    )
    assert server._run_init_command(args) == 0
    data = json.loads(out.read_text())
    env = data["mcpServers"]["td"]["env"]
    assert env["TD_MCP_SHARED_SECRET"] == "pre-provisioned-secret-" + "x" * 32


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
