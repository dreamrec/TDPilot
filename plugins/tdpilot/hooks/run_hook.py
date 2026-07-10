"""Bootstrap TDPilot hook checks from a trusted TDPilot runtime root."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 is still supported.
    tomllib = None  # type: ignore[assignment]


_RUNTIME_ROOT_ENV_VARS = (
    "TDPILOT_RUNTIME_ROOT",
    "TDPILOT_REPO_ROOT",
    "TD_MCP_REPO_ROOT",
    "CLAUDE_PLUGIN_ROOT",
    "CODEX_PLUGIN_ROOT",
)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    runtime_root = _find_runtime_root()
    if runtime_root is None:
        # Hooks are safety aids, not a reason to break an unrelated host
        # session. Missing or malformed runtimes therefore fail open.
        return 0

    try:
        subprocess.run(
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
        )
    except OSError:
        pass
    return 0


def _find_runtime_root() -> Path | None:
    """Find code only in roots controlled by the plugin or its installer.

    Project cwd variables and ``--root`` name the project being audited; they
    must never select executable Python code.
    """
    for candidate in _candidate_roots():
        try:
            root = candidate.expanduser().resolve()
        except OSError:
            continue
        if _is_runtime_root(root):
            return root
    return None


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    for key in _RUNTIME_ROOT_ENV_VARS:
        if value := os.environ.get(key):
            roots.append(Path(value))
    # The runner's containing package is trusted because this file is already
    # executing from it. The vendor import is Codex's known installation root.
    roots.append(Path(__file__).resolve().parents[1])
    try:
        home = Path.home()
    except (OSError, RuntimeError):
        # Minimal hook environments on Windows may omit USERPROFILE,
        # HOMEDRIVE, and HOMEPATH. The packaged runner root above remains a
        # trusted candidate; an unavailable optional vendor root must fail open.
        home = None
    if home is not None:
        roots.append(home / ".codex" / "vendor_imports" / "TDPilot")
    return roots


def _is_runtime_root(root: Path) -> bool:
    pyproject_path = root / "pyproject.toml"
    hook_module_path = root / "src" / "td_mcp" / "brain" / "hook_check.py"
    if not pyproject_path.is_file() or not hook_module_path.is_file():
        return False
    try:
        text = pyproject_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    if tomllib is not None:
        try:
            project = tomllib.loads(text).get("project")
        except tomllib.TOMLDecodeError:
            return False
        return isinstance(project, dict) and project.get("name") == "tdpilot"
    project_section = re.search(r"(?ms)^\[project\]\s*(.*?)(?=^\[|\Z)", text)
    return bool(
        project_section and re.search(r'(?m)^name\s*=\s*["\']tdpilot["\']\s*$', project_section.group(1))
    )


if __name__ == "__main__":
    raise SystemExit(main())
