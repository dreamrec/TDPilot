#!/usr/bin/env python3
"""Draft review-needed structured operator cards from the DocsBrain corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from td_mcp.brain.atlas_drafts import (  # noqa: E402
    draft_missing_operator_cards,
    write_operator_card_drafts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of drafts to generate.")
    parser.add_argument(
        "--family",
        action="append",
        default=[],
        help="Restrict drafts to an operator family, for example TOP or POP. May be repeated.",
    )
    parser.add_argument(
        "--op-type",
        action="append",
        default=[],
        help="Draft one specific operator type, for example directdisplayoutTOP. May be repeated.",
    )
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Include operators that already have structured cards.",
    )
    parser.add_argument(
        "--include-deprecated",
        action="store_true",
        help="Include operators that DocsBrain marks as deprecated.",
    )
    parser.add_argument(
        "--write",
        type=Path,
        help="Write *.draft.json files and a manifest to this directory instead of only printing JSON.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    drafts = draft_missing_operator_cards(
        args.root,
        limit=args.limit,
        families=args.family or None,
        op_types=args.op_type or None,
        include_existing=args.include_existing,
        include_deprecated=args.include_deprecated,
    )

    if args.write:
        manifest = write_operator_card_drafts(drafts, args.write)
        payload = {"manifest": manifest, "output_dir": str(args.write), "drafts": drafts}
    else:
        payload = {"draft_count": len(drafts), "drafts": drafts}

    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
