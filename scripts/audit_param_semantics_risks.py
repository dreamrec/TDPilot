#!/usr/bin/env python3
"""Audit high cook-risk parameter semantics against direct-risk behavior."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from td_mcp.brain.param_semantics import audit_high_cook_risk_direct_param_coverage


def audit_param_semantics_risks() -> dict[str, Any]:
    """Return high cook-risk params mapped to direct-risk or validation-only behavior."""
    return audit_high_cook_risk_direct_param_coverage()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()
    report = audit_param_semantics_risks()
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
