#!/usr/bin/env python3
"""
PreToolUse hook for TDPilot — Edit/Write matcher.

Reads the tool input JSON on stdin and detects edits to any of the 7
canonical version files. If detected, emits a non-blocking systemMessage
reminding the agent that ALL 7 must be bumped together.

Exits 0 always (non-blocking) — this is a *reminder*, not a *gate*.
The CI script `scripts/check_versions.py` is the authoritative blocker.

To convert this to a hard gate, change the final `print(json.dumps(...))`
to set `"continue": false` and `"stopReason": "..."` and exit 2.
"""
from __future__ import annotations

import json
import os
import sys

# The 7 files that must stay in lockstep on every release.
# Path matching is suffix-based to handle absolute vs. relative input.
VERSION_FILES = (
    "pyproject.toml",
    "src/td_mcp/__init__.py",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    "npm/package.json",
    "mcp/manifest.json",
    "td_component/mcp_webserver_callbacks.py",
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        # No payload, nothing to check.
        return 0

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if not file_path:
        return 0

    # Normalize: match against suffixes so /Users/.../pyproject.toml hits.
    normalized = os.path.normpath(file_path)
    matched: str | None = None
    for vf in VERSION_FILES:
        if normalized.endswith(vf):
            matched = vf
            break

    if matched is None:
        return 0

    # Emit the structured systemMessage. This is shown to the user in the
    # UI; the model also sees it as additional context.
    output = {
        "systemMessage": (
            f"[version-sync gate] Editing {matched} — this is 1 of 7 "
            "version-locked files. All must be bumped together (CI gate "
            "scripts/check_versions.py enforces drift). Other 6: "
            + ", ".join(v for v in VERSION_FILES if v != matched)
        ),
        "continue": True,
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
