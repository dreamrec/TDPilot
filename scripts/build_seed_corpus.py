"""Generate skeleton knowledge cards from TD introspection.

Run inside TouchDesigner Textport or with TD Python to populate cards.

Usage (inside TouchDesigner Textport):
    exec(open('/path/to/build_seed_corpus.py').read())

Or from command line with tdpy:
    tdpy build_seed_corpus.py

This script introspects the running TouchDesigner instance to discover
operators, their parameters, and generates skeleton JSON card files
that can then be manually enriched with summaries, gotchas, and tips.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Cards output directory — adjust if running outside the repo tree
CARDS_DIR = Path(__file__).resolve().parent.parent / "src" / "td_mcp" / "knowledge" / "cards"
OPERATORS_DIR = CARDS_DIR / "operators"

# Families to introspect
FAMILIES = {
    "TOP": "TOP",
    "CHOP": "CHOP",
    "SOP": "SOP",
    "COMP": "COMP",
    "DAT": "DAT",
    "MAT": "MAT",
}


def _make_skeleton(op_type: str, family: str, display_name: str = "") -> dict:
    """Create a minimal skeleton card for an operator."""
    return {
        "card_type": "operator",
        "op_type": op_type,
        "family": family,
        "display_name": display_name or op_type,
        "docs_url": f"https://docs.derivative.ca/{display_name.replace(' ', '_')}",
        "summary": "TODO: Add summary",
        "key_params": [],
        "common_gotchas": [],
        "related_snippets": [],
        "build_relevance": "2020.20000+",
        "last_verified": "",
    }


def introspect_td() -> list[dict]:
    """Introspect TouchDesigner to discover operators.

    Must be run inside a TouchDesigner process where the ``td`` module
    is available.
    """
    try:
        import td  # type: ignore[import-not-found]
    except ImportError:
        print(
            "ERROR: 'td' module not available. Run this script inside TouchDesigner Textport or via tdpy.",
            file=sys.stderr,
        )
        return []

    cards: list[dict] = []
    for family_suffix, family_name in FAMILIES.items():
        # Use td.op to discover operator types for each family
        # This is a placeholder — actual introspection depends on TD API
        print(f"Introspecting {family_name} operators...")

    return cards


def write_skeletons(cards: list[dict]) -> int:
    """Write skeleton cards to disk, skipping existing files."""
    OPERATORS_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for card in cards:
        path = OPERATORS_DIR / f"{card['op_type']}.json"
        if path.exists():
            print(f"  SKIP (exists): {path.name}")
            continue
        path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
        print(f"  WROTE: {path.name}")
        written += 1
    return written


def main() -> None:
    """Main entry point."""
    print("=== TDPilot Seed Corpus Builder ===")
    print(f"Output directory: {OPERATORS_DIR}")

    cards = introspect_td()
    if not cards:
        print(
            "\nNo operators discovered (TD not running or no introspection data).\n"
            "To generate skeletons manually, add operator types to the "
            "MANUAL_OPS list in this script."
        )
        return

    written = write_skeletons(cards)
    print(f"\nDone. Wrote {written} new skeleton cards.")


if __name__ == "__main__":
    main()
