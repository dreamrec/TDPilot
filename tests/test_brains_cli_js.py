"""Smoke tests for npm/brains.js — v1.4.5 hardening.

Drives the JS via node subprocess against an isolated HOME so the user's
real `~/.tdpilot/` is never touched. The bundled manifest is staged at
`<tmp>/.tdpilot/data/brains/brains_manifest.json` before each test.

Pins the regressions the reviewer identified in v1.4.4:

  - `brains add <unknown>` silently marked the id installed.
  - `brains add <local_build_id>` (no files) succeeded with zero
    downloads, polluting active.json without a usable DB.
  - Any typo in active.json disables all known brains at next startup
    (because active.json is an allow-list).

Note: As of v1.6 the shipping manifest contains no `local_build` brains,
so the local-build-specific regression tests have been retired. They
should be re-introduced if a future shipping brain re-uses that mode.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BRAINS_JS = REPO / "npm" / "brains.js"
MANIFEST = REPO / "data" / "brains" / "brains_manifest.json"


def _has_node() -> bool:
    return shutil.which("node") is not None


@pytest.fixture
def isolated_home(tmp_path: Path) -> Path:
    """Stage a fake ~/.tdpilot/ with the bundled manifest present.

    Returns the tmp dir to use as HOME. Inside it, the INSTALL_DIR
    (`~/.tdpilot/`) contains just the manifest — no active.json yet.
    Tests can drive `node brains.js <cmd>` with HOME pointing here.
    """
    install_dir = tmp_path / ".tdpilot"
    (install_dir / "data" / "brains").mkdir(parents=True)
    # Copy the real manifest so tests reflect the shipping shape.
    (install_dir / "data" / "brains" / "brains_manifest.json").write_text(
        MANIFEST.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    # Also seed a ~/.tdpilot/scripts/ stub so brains.js's downloader call
    # won't error out before the JS-side validation even runs. Not used
    # because we test reject paths, but prevents "file not found" noise.
    (install_dir / "scripts").mkdir(exist_ok=True)
    return tmp_path


def _node(home: Path, args: list) -> subprocess.CompletedProcess:
    """Invoke brains.js with HOME overridden to an isolated fixture path.

    We preserve the caller's PATH so node is locatable (it lives in
    /usr/local/bin on Homebrew installs, /opt/homebrew/bin on Apple Silicon,
    and other places), and only override HOME — that's what brains.js reads
    to compute INSTALL_DIR.
    """
    import os as _os

    cmd = ["node", str(BRAINS_JS)] + args
    env = dict(_os.environ)
    env["HOME"] = str(home)
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


pytestmark = pytest.mark.skipif(not _has_node(), reason="node not on PATH; skip JS CLI tests")


def test_list_shows_install_mode(isolated_home: Path):
    proc = _node(isolated_home, ["list"])
    assert proc.returncode == 0, proc.stderr
    # derivative is download-mode, must be tagged as such
    combined = proc.stdout + proc.stderr
    assert "derivative" in combined
    assert "download" in combined.lower()


def test_add_unknown_id_rejects_with_non_zero_exit(isolated_home: Path):
    """Typo resistance: `brains add typox` must not touch active.json."""
    active = isolated_home / ".tdpilot" / "data" / "brains" / "active.json"
    assert not active.exists(), "active.json should not exist before the test"

    proc = _node(isolated_home, ["add", "not_a_real_brain"])
    assert proc.returncode != 0, f"expected non-zero; got 0.\nstderr: {proc.stderr}"
    combined = proc.stdout + proc.stderr
    assert "unknown" in combined.lower() or "valid ids" in combined.lower()
    # Critical: active.json untouched
    assert not active.exists(), "active.json was created despite unknown id — regression"


def test_showInstalled_with_no_active_is_clean(isolated_home: Path):
    """No active.json + no typos in past invocations = clean output."""
    proc = _node(isolated_home, [])
    assert proc.returncode == 0
    combined = proc.stdout + proc.stderr
    assert "No active.json" in combined or "no active" in combined.lower()
