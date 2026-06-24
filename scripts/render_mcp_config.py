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


def _shared_secret_path() -> Path:
    """Canonical shared-secret file — the SAME one the TD-side WebServer and the
    MCP server read (auth_bootstrap.default_env_file). Honours TDPILOT_ENV_FILE."""
    override = (os.environ.get("TDPILOT_ENV_FILE") or "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".tdpilot" / ".tdpilot.env"


def _read_existing_secret(env_path: Path) -> str | None:
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("TD_MCP_SHARED_SECRET="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                return value or None
    except OSError:
        return None
    return None


def _resolve_shared_secret(explicit: str | None) -> str:
    """Resolve ONE shared secret so the rendered client config and the TD-side
    agree (no 401 drift): an explicit --secret wins; else reuse the secret in
    ~/.tdpilot/.tdpilot.env; else generate one (token_urlsafe, matching
    auth_bootstrap) and persist it there so both halves read the same value."""
    if explicit:
        return explicit
    env_path = _shared_secret_path()
    existing = _read_existing_secret(env_path)
    if existing:
        return existing
    secret = secrets.token_urlsafe(32)
    try:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        kept = []
        if env_path.exists():
            kept = [
                ln
                for ln in env_path.read_text(encoding="utf-8").splitlines()
                if not ln.strip().startswith("TD_MCP_SHARED_SECRET=")
            ]
        kept.append(f"TD_MCP_SHARED_SECRET={secret}")
        env_path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        try:
            os.chmod(env_path, 0o600)
        except OSError:
            pass
    except OSError:
        pass
    return secret


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
        "${TDPILOT_SHARED_SECRET}": _resolve_shared_secret(args.secret),
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
