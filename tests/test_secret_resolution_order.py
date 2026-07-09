"""Secret unification tests (audit batch E) — the recurring-401 root cause.

Canonical resolution order, unified across ALL readers:

    1. Explicit process env var ``TD_MCP_SHARED_SECRET`` (never overwritten)
    2. The canonical env file ``~/.tdpilot/.tdpilot.env``
       (``TDPILOT_ENV_FILE`` overrides for isolated tests / custom installs)

Pre-unification, ``td_component/tdpilot_startup.py`` scanned a repo-local
``<repo>/.tdpilot.env`` FIRST — a second secret file written by the shell
installers that different readers preferred differently, which is exactly
the drift class behind the recurring 401s. These tests pin:

  * the startup script now reads ONLY the canonical file (env still wins),
  * ``TDClient`` resolves env > canonical file > explicit constructor arg,
  * ``diagnose_sync``'s new ``secret_chain`` report fingerprints every file
    in the chain, names the winner, and flags divergent legacy/client-config
    sources — fingerprints only, never secret material.

Startup-module loading uses the importlib + ``TDPILOT_STARTUP_SKIP=1``
pattern from tests/test_startup_sweep.py; HOME isolation uses the fake-HOME
tmp_path pattern from tests/test_plugin_install_smoke.py /
test_save_path_validation.py (both HOME and USERPROFILE for Windows).
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
STARTUP_PATH = REPO_ROOT / "td_component" / "tdpilot_startup.py"


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # windows expanduser
    monkeypatch.delenv("TDPILOT_ENV_FILE", raising=False)
    # _load_env_file writes straight into os.environ (that's its job), and
    # monkeypatch.delenv on an ABSENT key records nothing to restore — so we
    # save/pop manually to guarantee no cross-test leakage.
    original_secret = os.environ.pop("TD_MCP_SHARED_SECRET", None)
    yield home
    os.environ.pop("TD_MCP_SHARED_SECRET", None)
    if original_secret is not None:
        os.environ["TD_MCP_SHARED_SECRET"] = original_secret


@pytest.fixture(scope="module")
def startup_module():
    """Load tdpilot_startup.py without firing _startup() at import time."""
    os.environ["TDPILOT_STARTUP_SKIP"] = "1"
    try:
        spec = importlib.util.spec_from_file_location("tdpilot_startup_secret_test", STARTUP_PATH)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        os.environ.pop("TDPILOT_STARTUP_SKIP", None)


# ---------------------------------------------------------------------------
# TD-side startup script (a _TOX_SOURCE_FILES member)
# ---------------------------------------------------------------------------


def test_startup_reads_canonical_home_env_file(startup_module, fake_home, tmp_path, monkeypatch):
    canonical = fake_home / ".tdpilot" / ".tdpilot.env"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("TD_MCP_SHARED_SECRET=home-secret\n", encoding="utf-8")

    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    startup_module._load_env_file(str(repo_root))
    assert os.environ.get("TD_MCP_SHARED_SECRET") == "home-secret"


def test_startup_ignores_repo_local_env_file(startup_module, fake_home, tmp_path, monkeypatch):
    """The repo-local-first scan is dead: a legacy <repo>/.tdpilot.env must
    NOT be loaded, even when the canonical file is absent."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".tdpilot.env").write_text("TD_MCP_SHARED_SECRET=legacy-repo-secret\n", encoding="utf-8")

    startup_module._load_env_file(str(repo_root))
    assert os.environ.get("TD_MCP_SHARED_SECRET") is None


def test_startup_env_var_wins_over_canonical_file(startup_module, fake_home, tmp_path, monkeypatch):
    canonical = fake_home / ".tdpilot" / ".tdpilot.env"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("TD_MCP_SHARED_SECRET=file-secret\n", encoding="utf-8")
    monkeypatch.setenv("TD_MCP_SHARED_SECRET", "process-secret")

    startup_module._load_env_file(str(tmp_path))
    assert os.environ["TD_MCP_SHARED_SECRET"] == "process-secret"


def test_startup_honors_tdpilot_env_file_override(startup_module, fake_home, tmp_path, monkeypatch):
    override = tmp_path / "override.env"
    override.write_text("TD_MCP_SHARED_SECRET=override-secret\n", encoding="utf-8")
    monkeypatch.setenv("TDPILOT_ENV_FILE", str(override))

    startup_module._load_env_file(str(tmp_path))
    assert os.environ.get("TD_MCP_SHARED_SECRET") == "override-secret"


def test_startup_source_has_no_repo_local_env_scan():
    """Regression pin as printed source: the divergent second secret file
    must not quietly come back in a refactor."""
    src = STARTUP_PATH.read_text(encoding="utf-8")
    assert "os.path.join(repo_root, _ENV_FILE_NAME)" not in src
    assert "_canonical_env_file" in src


# ---------------------------------------------------------------------------
# MCP-server-side reader (td_client) — same order
# ---------------------------------------------------------------------------


def test_td_client_env_var_beats_file_and_constructor(fake_home, monkeypatch):
    from td_mcp.td_client import TDClient

    canonical = fake_home / ".tdpilot" / ".tdpilot.env"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("TD_MCP_SHARED_SECRET=file-secret\n", encoding="utf-8")
    monkeypatch.setenv("TD_MCP_SHARED_SECRET", "process-secret")

    client = TDClient(shared_secret="constructor-secret")
    assert client._resolve_secret_uncached() == "process-secret"


def test_td_client_file_beats_constructor_when_env_absent(fake_home):
    from td_mcp.td_client import TDClient

    canonical = fake_home / ".tdpilot" / ".tdpilot.env"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("TD_MCP_SHARED_SECRET=file-secret\n", encoding="utf-8")

    client = TDClient(shared_secret="constructor-secret")
    assert client._resolve_secret_uncached() == "file-secret"


def test_td_client_never_reads_repo_local_env(fake_home, tmp_path, monkeypatch):
    from td_mcp.td_client import TDClient

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".tdpilot.env").write_text("TD_MCP_SHARED_SECRET=cwd-secret\n", encoding="utf-8")
    client = TDClient()
    assert client._resolve_secret_uncached() == ""


# ---------------------------------------------------------------------------
# td_sync_diagnose secret-chain fingerprints
# ---------------------------------------------------------------------------


def _chain(**kwargs):
    from td_mcp.sync_diagnostics import _secret_chain_report

    return _secret_chain_report(**kwargs)


def test_secret_chain_env_var_wins(tmp_path, monkeypatch):
    env_file = tmp_path / ".tdpilot.env"
    env_file.write_text("TD_MCP_SHARED_SECRET=file-secret\n", encoding="utf-8")
    monkeypatch.setenv("TD_MCP_SHARED_SECRET", "process-secret")

    chain = _chain(
        env_path=env_file,
        local_root=tmp_path,
        client_config_paths=[],
        legacy_env_paths=[],
    )
    assert chain["winner"] == "process_env"
    assert chain["winner_fingerprint"].startswith("sha256:")
    # file diverges from the env-var winner
    assert "canonical_env_file" in chain["divergent_sources"]
    assert chain["ok"] is False


def test_secret_chain_file_wins_when_env_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
    env_file = tmp_path / ".tdpilot.env"
    env_file.write_text("TD_MCP_SHARED_SECRET=file-secret\n", encoding="utf-8")

    chain = _chain(
        env_path=env_file,
        local_root=tmp_path,
        client_config_paths=[],
        legacy_env_paths=[],
    )
    assert chain["winner"] == "canonical_env_file"
    assert chain["divergent_sources"] == []
    assert chain["ok"] is True


def test_secret_chain_flags_divergent_legacy_file_without_leaking(tmp_path, monkeypatch):
    import json as jsonlib

    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
    env_file = tmp_path / ".tdpilot.env"
    env_file.write_text("TD_MCP_SHARED_SECRET=canonical-secret\n", encoding="utf-8")
    legacy = tmp_path / "repo" / ".tdpilot.env"
    legacy.parent.mkdir()
    legacy.write_text("TD_MCP_SHARED_SECRET=stale-legacy-secret\n", encoding="utf-8")

    chain = _chain(
        env_path=env_file,
        local_root=tmp_path / "repo",
        client_config_paths=[],
        legacy_env_paths=[legacy],
    )
    encoded = jsonlib.dumps(chain)
    assert chain["winner"] == "canonical_env_file"
    assert [s for s in chain["divergent_sources"] if "legacy_env_file" in s]
    assert "stale-legacy-secret" not in encoded
    assert "canonical-secret" not in encoded


def test_secret_chain_flags_literal_secret_in_client_config(tmp_path, monkeypatch):
    import json as jsonlib

    monkeypatch.delenv("TD_MCP_SHARED_SECRET", raising=False)
    env_file = tmp_path / ".tdpilot.env"
    env_file.write_text("TD_MCP_SHARED_SECRET=canonical-secret\n", encoding="utf-8")
    config = tmp_path / "claude_desktop_config.json"
    config.write_text(
        jsonlib.dumps(
            {
                "mcpServers": {
                    "touchdesigner": {
                        "command": "uv",
                        "env": {"TD_MCP_SHARED_SECRET": "x" * 32},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    chain = _chain(
        env_path=env_file,
        local_root=tmp_path,
        client_config_paths=[config],
        legacy_env_paths=[],
    )
    assert "client_config:claude_desktop_config.json" in chain["non_canonical_secret_sources"]
    assert "client_config:claude_desktop_config.json" in chain["divergent_sources"]
    assert "x" * 32 not in jsonlib.dumps(chain)


def test_secret_chain_matching_sources_are_not_divergent(tmp_path, monkeypatch):
    monkeypatch.setenv("TD_MCP_SHARED_SECRET", "same-secret")
    env_file = tmp_path / ".tdpilot.env"
    env_file.write_text("TD_MCP_SHARED_SECRET=same-secret\n", encoding="utf-8")
    legacy = tmp_path / "legacy.env"
    legacy.write_text("TD_MCP_SHARED_SECRET=same-secret\n", encoding="utf-8")

    chain = _chain(
        env_path=env_file,
        local_root=tmp_path,
        client_config_paths=[],
        legacy_env_paths=[legacy],
    )
    assert chain["ok"] is True
    assert chain["divergent_sources"] == []
    # legacy source is still surfaced (fingerprinted), just not divergent
    assert any(s["kind"] == "legacy_env_file" and s["secret_present"] for s in chain["sources"])


@pytest.mark.asyncio
async def test_diagnose_sync_carries_secret_chain_and_divergence_drift(tmp_path, monkeypatch):
    from td_mcp.sync_diagnostics import diagnose_sync

    env_file = tmp_path / ".tdpilot.env"
    env_file.write_text("TD_MCP_SHARED_SECRET=canonical-secret\n", encoding="utf-8")
    monkeypatch.setenv("TD_MCP_SHARED_SECRET", "canonical-secret")
    monkeypatch.setenv("TDPILOT_ENV_FILE", str(env_file))
    legacy = tmp_path / "legacy.env"
    legacy.write_text("TD_MCP_SHARED_SECRET=other-secret\n", encoding="utf-8")

    report = await diagnose_sync(
        client=None,
        include_live=False,
        local_version="2.0.3",
        installed_version="2.0.3",
        plugin_versions={"codex": ["2.0.3"]},
        install_roots={},
        running_processes=[],
        client_config_paths=[],
        legacy_env_paths=[legacy],
    )
    chain = report["auth"]["secret_chain"]
    assert chain["winner"] == "process_env"
    assert report["drift"]["secret_chain_divergence"] is True
    assert report["ok"] is False
    assert any("Legacy secret file" in item for item in report["recommendations"])
    assert "other-secret" not in str(report)


# ---------------------------------------------------------------------------
# Windows: ps(1)-based process probes must say so, not go silently empty
# ---------------------------------------------------------------------------


def test_running_process_report_unsupported_platform(monkeypatch):
    from td_mcp import sync_diagnostics

    monkeypatch.setattr(sync_diagnostics, "_ps_available", lambda: False)
    report = sync_diagnostics._running_process_report(
        local_hash=None,
        local_version="2.0.3",
        env_file_secret_fingerprint=None,
        process_rows=None,
    )
    assert report["status"] == "unsupported_platform"
    assert report["ok"] is True
    assert report["processes"] == []


def test_running_process_report_checked_status_with_rows():
    from td_mcp.sync_diagnostics import _running_process_report

    report = _running_process_report(
        local_hash=None,
        local_version="2.0.3",
        env_file_secret_fingerprint=None,
        process_rows=[],
    )
    assert report["status"] == "checked"
