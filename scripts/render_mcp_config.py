#!/usr/bin/env python3
"""Render .mcp.json.template into .mcp.json with user-specific paths and a secret.

Usage:
    python scripts/render_mcp_config.py         # writes .mcp.json next to template
    python scripts/render_mcp_config.py --print # print to stdout, don't write
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# NOTE: three .mcp.json-shaped files live at repo root, each for a different consumer:
#   - .mcp.json                         — Claude Code plugin template (tracked, ${CLAUDE_PLUGIN_ROOT})
#   - .mcp.json.claude-desktop-template — Claude Desktop template     (tracked, ${TDPILOT_ROOT})
#   - .mcp.json.local                   — rendered user config         (gitignored)
TEMPLATE = ROOT / ".mcp.json.claude-desktop-template"
OUTPUT = ROOT / ".mcp.json.local"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print", action="store_true", help="Print to stdout instead of writing .mcp.json")
    parser.add_argument(
        "--secret",
        default=None,
        help="Use a specific secret (default: generate a new 32-byte hex secret)",
    )
    args = parser.parse_args()

    if not TEMPLATE.exists():
        print(f"Template not found: {TEMPLATE}", file=sys.stderr)
        return 1

    text = TEMPLATE.read_text()
    replacements = {
        "${TDPILOT_ROOT}": str(ROOT),
        "${TDPILOT_SHARED_SECRET}": args.secret or secrets.token_hex(32),
    }
    for key, value in replacements.items():
        text = text.replace(key, value)

    if args.print:
        print(text)
        return 0

    if OUTPUT.exists():
        backup = OUTPUT.with_suffix(".json.backup")
        backup.write_text(OUTPUT.read_text())
        print(f"Backed up existing .mcp.json to {backup.name}", file=sys.stderr)

    OUTPUT.write_text(text)
    os.chmod(OUTPUT, 0o600)  # secret inside — owner-only read/write
    print(f"Wrote {OUTPUT.relative_to(ROOT)} (chmod 0600 — contains shared secret)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
