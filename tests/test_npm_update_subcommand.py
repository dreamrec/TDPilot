"""`npx tdpilot update` smoke tests (audit batch E).

The subcommand was documented (ensureRepo()'s opt-in auto-update comment
pointed users at `npx tdpilot update`) but never implemented — running it
fell through to the default branch and spawned the MCP server with `update`
as a bogus server arg. These tests pin the dispatch and its load-bearing
properties as printed source (same style as tests/test_npm_install_snippet.py)
so a refactor of run.js cannot silently regress the funnel.

No network git is executed here — assertions are on run.js source text only,
plus one offline `node run.js --help` smoke that exits before any git/uv/repo
work (skipped when node is absent).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
RUN_JS = REPO / "npm" / "run.js"


def _source() -> str:
    return RUN_JS.read_text(encoding="utf-8")


def test_update_subcommand_is_dispatched():
    src = _source()
    assert 'subcommand === "update"' in src, "run.js must dispatch the documented update subcommand"
    assert "function updateRepo()" in src


def test_update_dispatch_exits_before_server_spawn():
    """`update` must never fall through to the MCP-server spawn — the
    pre-implementation bug passed `update` to the Python server as an arg."""
    src = _source()
    dispatch = src.find('subcommand === "update"')
    spawn = src.find('spawn("uv"')
    assert dispatch != -1 and spawn != -1
    assert dispatch < spawn
    tail = src[dispatch : src.find("}", dispatch) + 1]
    assert "process.exit(0)" in tail


def test_update_fetches_tags_and_repins_to_latest_tag():
    """Mirrors the install pinning strategy: fetch tags, then re-pin —
    never leave the user on unpinned main HEAD."""
    src = _source()
    body_start = src.find("function updateRepo()")
    body = src[body_start : src.find("function printHelp()")]
    assert "git fetch --tags origin main" in body
    assert "pinToLatestTag(INSTALL_DIR)" in body
    assert "--ff-only" in body, "update must not merge over user edits silently"


def test_update_prints_restart_and_component_reminders():
    src = _source()
    body = src[src.find("function updateRepo()") : src.find("function printHelp()")]
    assert "Restart your MCP client" in body
    assert "td_self_update" in body
    assert "setup_mcp_in_td.py" in body


def test_update_is_windows_safe_no_shellisms():
    """Every git call in updateRepo goes through run() as a single fixed
    command string: no &&, no |, no $(...) — execSync would hand those to a
    shell and break on Windows cmd."""
    src = _source()
    body = src[src.find("function updateRepo()") : src.find("function printHelp()")]
    for line in body.splitlines():
        if 'run("git' in line:
            assert "&&" not in line and "|" not in line and "$(" not in line


def test_help_mentions_update():
    src = _source()
    assert '"--help"' in src
    help_body = src[src.find("function printHelp()") : src.find("// ── Subcommands")]
    assert "update" in help_body
    # Top-of-file usage comment stays in sync too.
    header = src[: src.find("*/")]
    assert "npx tdpilot update" in header


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
def test_help_smoke_runs_offline():
    """--help exits 0 before any uv/git/repo bootstrap — safe to execute."""
    proc = subprocess.run(
        ["node", str(RUN_JS), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0
    assert "update" in proc.stdout
    assert "brains" in proc.stdout
