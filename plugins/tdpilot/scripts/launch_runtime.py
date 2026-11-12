"""Launch the verified managed TDPilot runtime, never an ambient PATH command."""

from __future__ import annotations

import json
import os
import re
import sys
import tomllib
from pathlib import Path


def version_tuple(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise RuntimeError(f"Unsupported TDPilot version: {value!r}")
    return tuple(int(part) for part in match.groups())


def resolve_runtime(home: Path, override: str | None, minimum: str) -> Path:
    if override:
        root = Path(override).expanduser()
    else:
        pointer = home / ".tdpilot_path"
        root = (
            Path(pointer.read_text(encoding="utf-8").strip()).expanduser()
            if pointer.is_file()
            else home / ".tdpilot"
        )
    if not root.is_absolute():
        raise RuntimeError("TDPilot runtime path must be absolute")
    root = root.resolve()
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = metadata.get("project", {})
    if project.get("name") != "tdpilot":
        raise RuntimeError("Configured runtime is not a TDPilot project")
    if version_tuple(str(project.get("version", ""))) < version_tuple(minimum):
        raise RuntimeError(f"TDPilot runtime {minimum}+ is required; update the managed installation")
    if not (root / "src/td_mcp/server.py").is_file() or not (root / "uv.lock").is_file():
        raise RuntimeError("TDPilot runtime is incomplete")
    return root


def main() -> int:
    try:
        manifest = Path(__file__).resolve().parents[1] / ".codex-plugin/plugin.json"
        minimum = json.loads(manifest.read_text(encoding="utf-8"))["version"]
        root = resolve_runtime(Path.home(), os.environ.get("TDPILOT_INSTALL_DIR"), minimum)
        env = dict(os.environ)
        env.pop("VIRTUAL_ENV", None)
        os.execvpe("uv", ["uv", "run", "--directory", str(root), "tdpilot"], env)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(
            f"TDPilot could not start: {exc}. Use the TD component's Install/Update action, "
            "or set TDPILOT_INSTALL_DIR to a verified TDPilot checkout.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
