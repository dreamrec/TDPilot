"""Docs-truth gate for hint-corpus count claims.

The tdpilot-core skill shipped "20 packs / 73 hints" while the real corpus
had grown to 23/92 — hardcoded counts in prose go stale silently on every
pack addition. Policy (kill-list item from the 2026-07 audit): prose does
NOT carry corpus counts. If someone re-adds a "N packs / M hints" claim, it
must at least be TRUE at commit time; the cheaper move is to not write one.

Historical changelog lines ("11 → 20 packs, 41 → 73 hints") use arrow/comma
phrasing and are intentionally exempt — only the slash-form current-truth
claim is gated.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACKS_DIR = REPO / "src" / "td_mcp" / "hints" / "packs"

# Prose surfaces where a current-truth count claim could mislead an agent.
DOC_SURFACES = [
    REPO / "skills",
    REPO / "plugins" / "tdpilot" / "skills",
    REPO / "docs",
    REPO / "README.md",
    REPO / "plugin_README.md",
]

CLAIM_RE = re.compile(r"\*{0,2}(\d+)\s+packs?\s*/\s*(\d+)\s+hints?\*{0,2}", re.IGNORECASE)


def _actual_counts() -> tuple[int, int]:
    pack_files = sorted(PACKS_DIR.rglob("*.yaml"))
    assert pack_files, f"no hint packs found under {PACKS_DIR}"
    hints = 0
    for pack in pack_files:
        hints += len(re.findall(r"^  - id:", pack.read_text(encoding="utf-8"), re.MULTILINE))
    return len(pack_files), hints


def _doc_files():
    for surface in DOC_SURFACES:
        if surface.is_file():
            yield surface
        elif surface.is_dir():
            yield from surface.rglob("*.md")


def test_no_stale_pack_hint_count_claims_in_docs():
    actual_packs, actual_hints = _actual_counts()
    offenders: list[str] = []
    for doc in _doc_files():
        text = doc.read_text(encoding="utf-8")
        for match in CLAIM_RE.finditer(text):
            claimed_packs, claimed_hints = int(match.group(1)), int(match.group(2))
            if (claimed_packs, claimed_hints) != (actual_packs, actual_hints):
                offenders.append(
                    f"{doc.relative_to(REPO)}: claims '{match.group(0)}', "
                    f"actual corpus is {actual_packs} packs / {actual_hints} hints"
                )
    assert not offenders, (
        "Stale hint-corpus count claims found (prefer removing the count "
        "entirely — see this test's docstring):\n" + "\n".join(offenders)
    )
