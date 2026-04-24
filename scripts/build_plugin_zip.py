#!/usr/bin/env python3
"""Rebuild ``tdpilot.plugin`` ZIP from committed plugin sources.

Since audit hardening, the plugin layout is committed at the repo root:
  - .claude-plugin/plugin.json        (plugin manifest)
  - .mcp.json                         (plugin MCP config template)
  - commands/                         (slash commands)
  - skills/                           (skills, already at root)
  - td_component/tdpilot.tox     (binary TD component — must be built in TD)
  - plugin_README.md                  (goes into ZIP as README.md)

This script just zips those files. If any are missing it fails loudly rather
than synthesizing fallbacks — the committed files are the source of truth.

The legacy ZIP artifact is still produced so that users who don't install via
the Claude Code marketplace can drag-drop `tdpilot.plugin` into their plugin
folder.

Usage:
    uv run python scripts/build_plugin_zip.py
    uv run python scripts/build_plugin_zip.py --output /tmp/tdpilot.plugin
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from td_mcp import __version__  # noqa: E402
from td_mcp.release_gates import EXPECTED_MIN_TOOL_COUNT  # noqa: E402

# Every entry is (source_relative_to_ROOT, arcname_in_zip, required).
# `required=True` means the build fails if the file is missing.
PLUGIN_FILES: list[tuple[str, str, bool]] = [
    # Binary TD component.
    ("td_component/tdpilot.tox", "td_component/tdpilot.tox", True),
    # Plugin README (distinct from the repo's README.md).
    ("plugin_README.md", "README.md", True),
    # Plugin manifests.
    (".claude-plugin/plugin.json", ".claude-plugin/plugin.json", True),
    (".mcp.json", ".mcp.json", True),
    # Slash commands.
    ("commands/td-check.md", "commands/td-check.md", True),
    ("commands/td-snapshot.md", "commands/td-snapshot.md", True),
    # Skills.
    ("skills/tdpilot-core/SKILL.md", "skills/tdpilot-core/SKILL.md", True),
    (
        "skills/tdpilot-core/references/advanced-workflows.md",
        "skills/tdpilot-core/references/advanced-workflows.md",
        True,
    ),
    (
        "skills/tdpilot-core/references/preset-systems-and-ui.md",
        "skills/tdpilot-core/references/preset-systems-and-ui.md",
        False,
    ),
    ("skills/tdpilot-production/SKILL.md", "skills/tdpilot-production/SKILL.md", True),
    ("skills/popx-touchdesigner/SKILL.md", "skills/popx-touchdesigner/SKILL.md", True),
    (
        "skills/popx-touchdesigner/references/.gitignore",
        "skills/popx-touchdesigner/references/.gitignore",
        False,
    ),
    (
        "skills/popx-touchdesigner/references/BUILD.md",
        "skills/popx-touchdesigner/references/BUILD.md",
        False,
    ),
    (
        "skills/popx-touchdesigner/scripts/build_popx_refs.py",
        "skills/popx-touchdesigner/scripts/build_popx_refs.py",
        False,
    ),
    (
        "skills/popx-touchdesigner/scripts/search_popx_refs.py",
        "skills/popx-touchdesigner/scripts/search_popx_refs.py",
        False,
    ),
]


def build(output: Path) -> None:
    missing_required = []
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src_rel, arc, required in PLUGIN_FILES:
            src = ROOT / src_rel
            if not src.exists():
                if required:
                    missing_required.append(src_rel)
                continue
            zf.write(src, arc)

    if missing_required:
        output.unlink(missing_ok=True)
        msg = "Missing required plugin files:\n  " + "\n  ".join(missing_required)
        if "td_component/tdpilot.tox" in missing_required:
            msg += (
                "\n\nThe .tox must be rebuilt inside TouchDesigner. From the Textport:\n"
                '  exec(open("setup_mcp_in_td.py").read(), globals(), globals())'
            )
        raise SystemExit(msg)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "tdpilot.plugin",
        help="Output ZIP path (default: tdpilot.plugin at repo root)",
    )
    args = parser.parse_args()

    build(args.output)
    size = args.output.stat().st_size
    print(f"Wrote {args.output}")
    print(f"  size:       {size:,} bytes")
    print(f"  version:    {__version__}")
    print(f"  tool count: {EXPECTED_MIN_TOOL_COUNT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
