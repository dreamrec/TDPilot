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
#
# v1.4.5 wired `bootstrap_auth()` to run before all non-init commands,
# including doctor. Without an isolated TDPILOT_ENV_FILE, bootstrap reads
# the developer's real `~/.tdpilot/.tdpilot.env` on any machine that has
# run tdpilot once, silently repopulating TD_MCP_SHARED_SECRET and
# defeating the test's `monkeypatch.delenv(...)`. Every doctor-auth test
# below points TDPILOT_ENV_FILE at a non-existent tmp path so bootstrap
# reads nothing (and, if AUTOGEN=1, writes there instead of the user's
# real file).
# ---------------------------------------------------------------------------


def _isolate_env_file(monkeypatch, tmp_path) -> None:
    """Point bootstrap_auth at a non-existent tmp file so it can't read
    the developer's real ~/.tdpilot/.tdpilot.env during the test."""
    monkeypatch.setenv("TDPILOT_ENV_FILE", str(tmp_path / ".tdpilot.env"))


def test_doctor_flags_auth_required_without_secret(monkeypatch, capsys, tmp_path):
    """doctor must fail (non-zero exit) when TD_MCP_REQUIRE_AUTH=1 but no secret."""
    _isolate_env_file(monkeypatch, tmp_path)
    monkeypatch.setenv("TD_MCP_REQUIRE_AUTH", "1")
    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
    # AUTOGEN must also be off; otherwise bootstrap would mint a secret
    # into the tmp file and the test would no longer see the "no secret"
    # condition it's trying to assert.
    monkeypatch.delenv("TD_MCP_AUTOGENERATE_SECRET", raising=False)

    with pytest.raises(SystemExit) as exc:
        server.main(["doctor", "--skip-td-check"])
    assert exc.value.code != 0

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "auth" in combined.lower() or "SHARED_SECRET" in combined


def test_doctor_passes_auth_check_when_secret_set(monkeypatch, capsys, tmp_path):
    """doctor's auth check must pass when required + secret set."""
    _isolate_env_file(monkeypatch, tmp_path)
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


def test_doctor_passes_auth_check_when_auth_disabled(monkeypatch, capsys, tmp_path):
    _isolate_env_file(monkeypatch, tmp_path)
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
    # Current repo: manifest and registry match at 97 tools.
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
    """--auth + --generate-secret bakes the secret into the config file.

    v1.4.5 tightening: the secret is NOT echoed to stdout anymore (it's a
    security smell). The config file is the source of truth. The stdout
    line just confirms that a secret was generated.
    """
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
    # v1.4.5: stdout confirms a secret was generated but does NOT leak it.
    printed = capsys.readouterr().out
    assert "Generated a shared secret" in printed
    assert env["TD_MCP_SHARED_SECRET"] not in printed, (
        "v1.4.5: secret must not be echoed to stdout — it's only in the config file"
    )


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


# ---------------------------------------------------------------------------
# v1.4.5 Fix 4: init --print-only keeps stdout machine-readable.
# Flag-combination validation, default-generate-with-auth, secret notices
# on stderr under --print-only, and TD_MCP_EXEC_MODE=restricted baked in
# when auth is enabled.
# ---------------------------------------------------------------------------


def _init_main(argv: list[str]):
    """Invoke server.main(['init', ...argv]) and return the SystemExit code."""
    try:
        server.main(["init"] + argv)
    except SystemExit as exc:
        return exc.code
    return 0


def test_init_print_only_stdout_is_pure_json(tmp_path, capsys):
    """--print-only --auth --generate-secret: stdout MUST parse as JSON.

    Pre-v1.4.5 the generated-secret notice was printed to stdout before the
    JSON, so `tdpilot init --print-only --auth --generate-secret | jq .`
    silently broke. Pipe discipline matters.
    """
    code = _init_main(["--print-only", "--auth", "--generate-secret"])
    assert code == 0
    captured = capsys.readouterr()
    # Stdout must parse as JSON, end-to-end
    payload = json.loads(captured.out)
    env = payload["mcpServers"]["touchdesigner"]["env"]
    assert env["TD_MCP_REQUIRE_AUTH"] == "1"
    assert env["TD_MCP_SHARED_SECRET"]
    # Secret notice went to stderr
    assert "Generated" in captured.err or "secret" in captured.err.lower()
    # The secret itself may or may not appear — but it must NOT be on stdout
    # ahead of the JSON
    assert env["TD_MCP_SHARED_SECRET"] not in captured.out.split("\n")[0]


def test_init_generate_secret_without_auth_fails(capsys):
    """--generate-secret without --auth must exit non-zero, not silently ignore."""
    code = _init_main(["--generate-secret"])
    assert code != 0


def test_init_shared_secret_without_auth_fails(capsys):
    """--shared-secret without --auth must exit non-zero."""
    code = _init_main(["--shared-secret", "some-value"])
    assert code != 0


def test_init_generate_and_shared_secret_together_fails(capsys):
    """Passing both --generate-secret and --shared-secret is ambiguous."""
    code = _init_main(["--auth", "--generate-secret", "--shared-secret", "x" * 32])
    assert code != 0


def test_init_auth_alone_generates_secret_by_default(tmp_path, capsys):
    """v1.4.5 ergonomics: `--auth` with no explicit secret flag should
    generate one by default. Pre-v1.4.5 it produced a "require auth + no
    secret" config that would trip the server startup gate."""
    out = tmp_path / "config.json"
    code = _init_main(["--auth", "--output", str(out), "--force"])
    assert code == 0
    data = json.loads(out.read_text())
    env = data["mcpServers"]["touchdesigner"]["env"]
    assert env["TD_MCP_REQUIRE_AUTH"] == "1"
    assert env["TD_MCP_SHARED_SECRET"], "--auth alone should mint a secret now"


def test_init_auth_config_includes_exec_mode_restricted(tmp_path):
    """Plan §4.4: when auth is enabled, default exec mode should be
    `restricted` unless the user overrides. Matches .mcp.json posture."""
    out = tmp_path / "config.json"
    code = _init_main(["--auth", "--output", str(out), "--force"])
    assert code == 0
    data = json.loads(out.read_text())
    env = data["mcpServers"]["touchdesigner"]["env"]
    assert env.get("TD_MCP_EXEC_MODE") == "restricted"


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
