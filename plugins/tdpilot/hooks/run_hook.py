"""Bootstrap TDPilot hook checks from a lightweight plugin cache."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    runtime_root = _find_runtime_root(args)
    if runtime_root is None:
        event_name = "PostToolUse" if args[:1] == ["post-tool-use"] else "Stop"
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": event_name,
                        "additionalContext": (
                            "TDPilot hook runner could not locate a Python runtime root. "
                            "Set TD_MCP_REPO_ROOT or refresh the TDPilot plugin cache."
                        ),
                    }
                },
                separators=(",", ":"),
            )
        )
        return 0

    return subprocess.run(
        [
            "uv",
            "run",
            "--directory",
            str(runtime_root),
            "python",
            "-m",
            "td_mcp.brain.hook_check",
            *args,
        ],
        check=False,
    ).returncode


def _find_runtime_root(args: list[str]) -> Path | None:
    for candidate in _candidate_roots(args):
        root = candidate.expanduser().resolve()
        if _is_runtime_root(root):
            return root
    return None


def _candidate_roots(args: list[str]) -> list[Path]:
    roots: list[Path] = []
    for key in ("TD_MCP_REPO_ROOT", "TDPILOT_REPO_ROOT", "CODEX_PROJECT_DIR", "CLAUDE_PROJECT_DIR"):
        if value := os.environ.get(key):
            roots.append(Path(value))
    roots.extend(_root_args(args))
    if value := os.environ.get("PWD"):
        roots.append(Path(value))
    roots.append(Path.cwd())
    roots.append(Path.home() / ".codex" / "vendor_imports" / "TDPilot")
    roots.append(Path(__file__).resolve().parents[1])
    return roots


def _root_args(args: list[str]) -> list[Path]:
    roots: list[Path] = []
    for index, value in enumerate(args):
        if value == "--root" and index + 1 < len(args):
            roots.append(Path(args[index + 1]))
    return roots


def _is_runtime_root(root: Path) -> bool:
    return (root / "pyproject.toml").exists() and (
        root / "src" / "td_mcp" / "brain" / "hook_check.py"
    ).exists()


if __name__ == "__main__":
    raise SystemExit(main())
