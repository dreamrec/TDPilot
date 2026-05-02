#!/usr/bin/env python3
"""Build ``tdpilot.mcpb`` — Claude Desktop one-click install bundle.

The MCPB (MCP Bundle) format is Anthropic's distribution channel for
desktop MCP servers — analogous to ``.crx`` for Chrome extensions or
``.vsix`` for VS Code. Users open the ``.mcpb`` in Claude for macOS or
Windows and the MCP server is installed and configured automatically.

This is DISTINCT from the existing distribution channels:
  - ``tdpilot.plugin`` (Claude Code plugin ZIP, see scripts/build_plugin_zip.py)
  - ``npm/`` (npm distribution invoked via ``npx tdpilot``)
  - ``mcp/manifest.json`` (generic MCP registry manifest)

The ``.mcpb`` we build here ships a snapshot of the Python source so
Claude Desktop's bundled ``uv`` runtime can install dependencies and
launch ``uv run tdpilot`` without the user needing Python installed
separately.

Bundle contents:
  manifest.json              — MCPB manifest (this file generates it)
  pyproject.toml             — copied verbatim
  uv.lock                    — copied if present
  src/td_mcp/                — the Python package, copied recursively
  td_component/tdpilot.tox   — TD-side component (user must drag into TD)
  README.md                  — bundle README explaining post-install steps
  LICENSE                    — license file

Usage:
    uv run python scripts/build_mcpb.py
    uv run python scripts/build_mcpb.py --output /tmp/tdpilot.mcpb
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "tdpilot.mcpb"

# Files/directories copied from repo root into the bundle root.
# Order: manifest first (so `mcpb pack` validates against it), then
# source, then docs/license.
BUNDLE_FILES = (
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
)
BUNDLE_DIRS = (
    "src",
    "td_component",
)
# uv.lock is optional — included if present so installs reproduce
# the exact dep set we tested against.
OPTIONAL_FILES = ("uv.lock",)


def _read_version() -> str:
    """Pull the canonical version string from src/td_mcp/__init__.py."""
    init_py = (ROOT / "src" / "td_mcp" / "__init__.py").read_text(encoding="utf-8")
    for line in init_py.splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("Could not find __version__ in src/td_mcp/__init__.py")


def _build_manifest(version: str) -> dict:
    """Construct the MCPB manifest dict.

    See https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md
    for the schema. We use:
      - server.type = "python" so Claude Desktop's uv runtime picks up
        the bundled pyproject.toml and installs tdpilot's dependencies
        on first run.
      - mcp_config.command = "uv" with "--directory ${__dirname}" so uv
        runs against the bundled source.
    """
    return {
        "$schema": "https://raw.githubusercontent.com/modelcontextprotocol/mcpb/refs/heads/main/MANIFEST.schema.json",
        "manifest_version": "0.2",
        "name": "tdpilot",
        "display_name": "TDPilot",
        "version": version,
        "description": "AI copilot for TouchDesigner — 102 MCP tools for live node graph control, parameter management, diagnostics, safety, streaming, technique memory, knowledge corpus, focus + locations, hint injection, and typed patch sessions.",
        "long_description": (
            "TDPilot is a production-grade MCP server for TouchDesigner. "
            "It exposes 102 tools that let an AI agent inspect, build, wire, "
            "optimize, and stabilize live TD networks via real tool calls. "
            "Includes a typed patch-session API (plan/preview/apply/validate/"
            "variations) with sentinel-guarded undo blocks, knowledge-corpus "
            "lookups, vision diagnostics, project-lifecycle control, snapshot "
            "safety, and a technique-memory system for reusable subnet patterns. "
            "After install, drag the bundled td_component/tdpilot.tox into "
            "your TouchDesigner /local container — see README for details."
        ),
        "author": {
            "name": "silviu",
            "email": "dreamrec@users.noreply.github.com",
            "url": "https://github.com/dreamrec",
        },
        "homepage": "https://github.com/dreamrec/TDPilot",
        "documentation": "https://github.com/dreamrec/TDPilot/blob/main/README.md",
        "support": "https://github.com/dreamrec/TDPilot/issues",
        "license": "MIT",
        "repository": {
            "type": "git",
            "url": "https://github.com/dreamrec/TDPilot.git",
        },
        "keywords": [
            "touchdesigner",
            "td",
            "mcp",
            "creative-coding",
            "visual-programming",
            "popx",
            "particles",
            "simulations",
            "patch-sessions",
        ],
        "server": {
            "type": "python",
            "entry_point": "src/td_mcp/server.py",
            "mcp_config": {
                "command": "uv",
                "args": [
                    "run",
                    "--directory",
                    "${__dirname}",
                    "tdpilot",
                ],
                "env": {
                    "TD_MCP_HOST": "127.0.0.1",
                    "TD_MCP_PORT": "9981",
                    "TD_MCP_WS_PORT": "9982",
                    "TD_MCP_EXEC_MODE": "restricted",
                    "TD_MCP_REQUIRE_AUTH": "1",
                    "TD_MCP_AUTOGENERATE_SECRET": "1",
                },
            },
        },
        "tools_generated": True,
        "compatibility": {
            "claude_desktop": ">=0.10.0",
            "platforms": ["darwin", "win32", "linux"],
            "runtimes": {"python": ">=3.10"},
        },
    }


def _copy_into(staging: Path) -> None:
    """Copy bundled files + dirs from repo root into staging."""
    for fname in BUNDLE_FILES:
        src = ROOT / fname
        if not src.exists():
            print(f"  WARN: missing required file {fname}", file=sys.stderr)
            continue
        shutil.copy2(src, staging / fname)
        print(f"  + {fname}")
    for fname in OPTIONAL_FILES:
        src = ROOT / fname
        if src.exists():
            shutil.copy2(src, staging / fname)
            print(f"  + {fname} (optional)")
    for dname in BUNDLE_DIRS:
        src = ROOT / dname
        if not src.is_dir():
            print(f"  WARN: missing required dir {dname}/", file=sys.stderr)
            continue
        # Exclude __pycache__ + .venv + tests when copying.
        shutil.copytree(
            src,
            staging / dname,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".venv", "tests"),
        )
        print(f"  + {dname}/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output .mcpb path (default: tdpilot.mcpb at repo root)",
    )
    args = parser.parse_args()

    version = _read_version()
    print(f"[mcpb] Building tdpilot.mcpb v{version}")

    with tempfile.TemporaryDirectory(prefix="tdpilot-mcpb-") as td:
        staging = Path(td)
        manifest = _build_manifest(version)
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"  + manifest.json ({len(json.dumps(manifest))} bytes)")
        _copy_into(staging)

        # Validate the manifest before packing. Inherit os.environ so
        # node/uv/etc. are reachable; prepend the npm-global bin in case
        # mcpb was installed there but not on the user's default PATH.
        import os

        env = dict(os.environ)
        npm_global_bin = str(Path.home() / ".npm-global" / "bin")
        env["PATH"] = f"{npm_global_bin}{os.pathsep}{env.get('PATH', '')}"

        try:
            subprocess.run(
                ["mcpb", "validate", str(staging / "manifest.json")],
                check=True,
                env=env,
            )
        except FileNotFoundError:
            print("  WARN: mcpb CLI not on PATH; skipping validate step", file=sys.stderr)
            print(f"        (tried {npm_global_bin})", file=sys.stderr)
        except subprocess.CalledProcessError as exc:
            print(f"  ERROR: manifest validation failed: {exc}", file=sys.stderr)
            return 1

        # Pack the staging dir into the .mcpb file.
        try:
            subprocess.run(
                ["mcpb", "pack", str(staging), str(args.output)],
                check=True,
                env=env,
            )
        except FileNotFoundError:
            print("  ERROR: mcpb CLI not on PATH; install via:", file=sys.stderr)
            print("    npm install -g @anthropic-ai/mcpb", file=sys.stderr)
            return 1
        except subprocess.CalledProcessError as exc:
            print(f"  ERROR: mcpb pack failed: {exc}", file=sys.stderr)
            return 1

    print(f"\n[mcpb] Wrote {args.output}")
    print(f"  size:    {args.output.stat().st_size:,} bytes")
    print(f"  version: {version}")
    print("\nInstall: open the .mcpb in Claude Desktop (macOS/Windows) for one-click install.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
