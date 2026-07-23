#!/usr/bin/env python3
"""Fail if the committed ``td_component/tdpilot.tox`` is out of sync with source.

The .tox is a binary TD artifact and can only be rebuilt inside TouchDesigner.
That means after any edit to the `.py` files it embeds *or the builders that
shape its operator hierarchy and built-in parameters*, the .tox goes stale
silently — users who install the plugin get outdated behavior.

This guard compares the hash of the source files and the hash/size of the
actual ``td_component/tdpilot.tox`` binary against metadata recorded in
``td_component/.tox-source-hash.json`` at build time. Mismatch = "rebuild the
.tox in TD before pushing".

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
    # Builder behavior is saved into the binary even though the builder
    # source is not embedded as a Text DAT.
    "td_component/build_export_mcp_tox.py",
    "td_component/build_tdpilot_tox.py",
    "td_component/mcp_webserver_callbacks.py",
    "td_component/event_emitter.py",
    "td_component/ws_callbacks.py",
    "td_component/tdpilot_startup.py",
    # v1.5.6 — installer + panel scaffolding (parent tdpilot COMP children).
    "td_component/installer.py",
    "td_component/installer_exec.py",
    "td_component/autostart.py",
    "td_component/renderer.py",
    # v1.6.7 — state_cache module that the renderer reads from. Was missing
    # from main from v1.5.6 through v1.6.6 (see CHANGELOG v1.6.7).
    "td_component/state_cache.py",
)
HASH_REL = Path("td_component") / ".tox-source-hash.json"
TOX_REL = Path("td_component") / "tdpilot.tox"
HASH_FILE = ROOT / HASH_REL
TOX_FILE = ROOT / TOX_REL


def compute_current_hash(root: Path | None = None) -> str:
    repo_root = Path(root or ROOT)
    h = hashlib.sha256()
    for rel in SOURCE_FILES:
        path = repo_root / rel
        if not path.exists():
            continue
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(path.read_bytes())
        h.update(b"\x00")
    return h.hexdigest()


def compute_tox_artifact_metadata(root: Path | None = None) -> dict[str, object]:
    repo_root = Path(root or ROOT)
    tox_file = repo_root / TOX_REL
    digest = hashlib.sha256(tox_file.read_bytes()).hexdigest()
    return {
        "tox_artifact_path": str(TOX_REL),
        "tox_artifact_sha256": digest,
        "tox_artifact_size_bytes": tox_file.stat().st_size,
    }


def check_freshness(root: Path | None = None) -> tuple[bool, list[str]]:
    repo_root = Path(root or ROOT)
    tox_file = repo_root / TOX_REL
    hash_file = repo_root / HASH_REL
    messages: list[str] = []

    if not tox_file.exists():
        messages.append("ERROR: " + str(TOX_REL) + " is missing.")
        messages.extend(_rebuild_instructions(missing_tox=True))
        return False, messages

    if not hash_file.exists():
        messages.append("ERROR: " + str(HASH_REL) + " is missing.")
        messages.append("       Rebuild the .tox in TouchDesigner — the rebuild writes this file.")
        return False, messages

    stored = json.loads(hash_file.read_text(encoding="utf-8"))
    stored_hash = stored.get("tox_source_hash")
    current_hash = compute_current_hash(repo_root)

    if stored_hash != current_hash:
        messages.append("ERROR: .tox is stale relative to td_component source.")
        messages.append("  stored hash:  " + str(stored_hash))
        messages.append("  current hash: " + current_hash)
        messages.append("  built at:     " + str(stored.get("built_at")))
        messages.append("")
        messages.extend(_rebuild_instructions())
        return False, messages

    current_artifact = compute_tox_artifact_metadata(repo_root)
    stored_artifact_hash = stored.get("tox_artifact_sha256")
    stored_artifact_size = stored.get("tox_artifact_size_bytes")
    if not stored_artifact_hash or stored_artifact_size is None:
        messages.append("ERROR: .tox artifact metadata is missing from " + str(HASH_REL) + ".")
        messages.append(
            "       Rebuild the .tox so the sidecar binds source freshness to the binary artifact."
        )
        return False, messages

    if (
        stored_artifact_hash != current_artifact["tox_artifact_sha256"]
        or int(stored_artifact_size) != current_artifact["tox_artifact_size_bytes"]
    ):
        messages.append("ERROR: .tox binary changed after the freshness sidecar was written.")
        messages.append("  stored artifact hash:  " + str(stored_artifact_hash))
        messages.append("  current artifact hash: " + str(current_artifact["tox_artifact_sha256"]))
        messages.append("  stored artifact size:  " + str(stored_artifact_size))
        messages.append("  current artifact size: " + str(current_artifact["tox_artifact_size_bytes"]))
        messages.append("")
        messages.extend(_rebuild_instructions())
        return False, messages

    messages.append(
        ".tox is fresh (source hash "
        + current_hash[:16]
        + "..., artifact hash "
        + str(current_artifact["tox_artifact_sha256"])[:16]
        + "..., built "
        + str(stored.get("built_at"))
        + ")"
    )
    return True, messages


def _rebuild_instructions(*, missing_tox: bool = False) -> list[str]:
    if missing_tox:
        return [
            "       Rebuild it inside TouchDesigner via",
            "       td_component/build_tdpilot_tox.py in the Textport (v1.5.6+),",
            "       or setup_mcp_in_td.py for legacy mcp-server-only builds.",
        ]
    return [
        "Rebuild the .tox in TouchDesigner before pushing (v1.5.6+):",
        "  1. Open TD",
        "  2. In Textport, run td_component/build_tdpilot_tox.py",
        "     (open the file, read its source, compile + exec it).",
        "  3. git add td_component/tdpilot.tox td_component/.tox-source-hash.json",
    ]


def main() -> int:
    ok, messages = check_freshness(ROOT)
    for message in messages:
        print(message)
    if ok:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
