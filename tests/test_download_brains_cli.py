"""Tests for scripts/download_brains.py — v1.4.5 hardening.

Before v1.4.5 the downloader exited 0 when:
  - unknown brain ids were passed (logged warning, continued with empty list),
  - the resulting download list was empty (for loop never ran, `all_ok` stayed True).

Combined with `npm/brains.js addBrain()` which writes any requested id to
active.json after a zero-exit downloader, a typo could pollute active.json
without downloading anything AND disable all known brains on next startup
(because active.json acts as an allow-list).

v1.4.5 changes:
  - Unknown ids in --brains-file → exit non-zero.
  - Empty `brains_to_download` after filtering → exit non-zero.
  - Manifest entries with `install_mode: "local_build"` are skipped by the
    downloader (can't be downloaded), but signaled to callers via a
    machine-parseable result summary.

Note: As of v1.6 the shipping manifest contains no `local_build` brains,
so the local-build-only test has been retired. It should be re-introduced
if a future shipping brain re-uses that mode.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOWNLOADER = REPO / "scripts" / "download_brains.py"


def _run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Invoke the downloader in a subprocess so we can observe exit codes."""
    cmd = [sys.executable, str(DOWNLOADER)] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=REPO,
        **kwargs,
    )


def _write_selection(tmp_path: Path, ids: list) -> Path:
    sel = tmp_path / "selection.json"
    sel.write_text(json.dumps(ids), encoding="utf-8")
    return sel


def test_list_command_still_works():
    """--list should not network; smoke check that exit 0."""
    proc = _run(["--list"])
    assert proc.returncode == 0, f"stderr:\n{proc.stderr}"
    # Known brains show up
    combined = proc.stdout + proc.stderr
    assert "derivative" in combined


def test_unknown_id_in_brains_file_exits_non_zero(tmp_path):
    """Typing `npx tdpilot brains add typox` (which doesn't exist) must fail.

    Before v1.4.5: the downloader logged a warning, ended with zero brains
    to download, and exited 0. brains.js would then mark `typox` as
    installed in active.json, silently polluting the allow-list.
    """
    sel = _write_selection(tmp_path, ["not_a_real_brain"])
    proc = _run(
        ["--manifest", str(REPO / "data" / "brains" / "brains_manifest.json"), "--brains-file", str(sel)]
    )
    assert proc.returncode != 0, (
        f"expected non-zero exit for unknown brain id; got {proc.returncode}\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    )


def test_empty_brains_file_exits_non_zero(tmp_path):
    """Empty selection list must exit non-zero."""
    sel = _write_selection(tmp_path, [])
    proc = _run(
        ["--manifest", str(REPO / "data" / "brains" / "brains_manifest.json"), "--brains-file", str(sel)]
    )
    assert proc.returncode != 0


def test_mixed_unknown_and_known_ids_exits_non_zero(tmp_path):
    """If any id is unknown, fail the whole run so the user catches the typo."""
    sel = _write_selection(tmp_path, ["derivative", "typox"])
    proc = _run(
        ["--manifest", str(REPO / "data" / "brains" / "brains_manifest.json"), "--brains-file", str(sel)]
    )
    assert proc.returncode != 0


def test_list_command_shows_install_mode(tmp_path):
    """--list must surface install_mode for each brain so users can see
    which ones are downloadable vs local-build."""
    proc = _run(["--list", "--manifest", str(REPO / "data" / "brains" / "brains_manifest.json")])
    assert proc.returncode == 0
    combined = proc.stdout + proc.stderr
    # Either "download" appears near derivative
    assert "derivative" in combined
    assert "download" in combined.lower()
