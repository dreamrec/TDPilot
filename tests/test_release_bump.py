from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_release_bump_dry_run_matches_current_public_surfaces() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "release_bump.py"),
            "--version",
            "99.99.99",
            "--dry-run",
        ],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        check=False,
        # Reproduce the Windows runner's legacy console default; the command
        # must still emit a complete UTF-8 dry-run diff.
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
    )

    assert result.returncode == 0, result.stderr
    for path in (
        "docs/API_REFERENCE.md",
        "td_component/README.md",
        "plugins/tdpilot/skills/tdpilot-core/SKILL.md",
        "plugins/tdpilot/skills/tdpilot-production/SKILL.md",
    ):
        assert path in result.stdout
    assert "(dry-run: no files written)" in result.stdout
