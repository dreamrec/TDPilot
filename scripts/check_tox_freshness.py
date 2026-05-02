#!/usr/bin/env python3
"""Fail if the committed ``td_component/tdpilot.tox`` is out of sync with source.

The .tox is a binary TD artifact and can only be rebuilt inside TouchDesigner.
That means after any edit to the `.py` files it embeds, the .tox goes stale
silently — users who install the plugin get outdated callback code.

This guard compares the hash of the source files against the hash recorded in
``td_component/.tox-source-hash.json`` at build time. Mismatch = "rebuild
the .tox in TD before pushing".

Runs in CI. Also runnable locally.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Must match _TOX_SOURCE_FILES in td_component/build_export_mcp_tox.py
SOURCE_FILES = (
    "td_component/mcp_webserver_callbacks.py",
    "td_component/event_emitter.py",
    "td_component/ws_callbacks.py",
    "td_component/tdpilot_startup.py",
    # v1.5.6 — installer + panel scaffolding (parent tdpilot COMP children).
    "td_component/installer.py",
    "td_component/installer_exec.py",
    "td_component/autostart.py",
    "td_component/renderer.py",
)
HASH_FILE = ROOT / "td_component" / ".tox-source-hash.json"
TOX_FILE = ROOT / "td_component" / "tdpilot.tox"


def compute_current_hash() -> str:
    h = hashlib.sha256()
    for rel in SOURCE_FILES:
        path = ROOT / rel
        if not path.exists():
            continue
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(path.read_bytes())
        h.update(b"\x00")
    return h.hexdigest()


def main() -> int:
    if not TOX_FILE.exists():
        print("ERROR: " + str(TOX_FILE.relative_to(ROOT)) + " is missing.")
        print("       Rebuild it inside TouchDesigner via setup_mcp_in_td.py in the Textport.")
        return 1

    if not HASH_FILE.exists():
        print("ERROR: " + str(HASH_FILE.relative_to(ROOT)) + " is missing.")
        print("       Rebuild the .tox in TouchDesigner — the rebuild writes this file.")
        return 1

    stored = json.loads(HASH_FILE.read_text())
    stored_hash = stored.get("tox_source_hash")
    current_hash = compute_current_hash()

    if stored_hash != current_hash:
        print("ERROR: .tox is stale relative to td_component source.")
        print("  stored hash:  " + str(stored_hash))
        print("  current hash: " + current_hash)
        print("  built at:     " + str(stored.get("built_at")))
        print("")
        print("Rebuild the .tox in TouchDesigner before pushing:")
        print("  1. Open TD")
        print("  2. In Textport run setup_mcp_in_td.py")
        print("  3. git add td_component/tdpilot.tox td_component/.tox-source-hash.json")
        return 1

    print(".tox is fresh (hash " + current_hash[:16] + "..., built " + str(stored.get("built_at")) + ")")
    return 0


if __name__ == "__main__":
    sys.exit(main())
