#!/usr/bin/env python3
"""Fail if the seed release-card corpus drifts more than --max-drift builds
behind docs.derivative.ca/Release_Notes.

This is the external analog of scripts/check_versions.py. Where check_versions
guards TDPilot's own seven version fields, this script guards the *upstream*
version — the TouchDesigner build that the doc atlas tracks. The cards in
src/td_mcp/knowledge/cards/release/<build>.json power td_get_release_delta
and td_get_build_compatibility; whenever the newest seed card lags real
Derivative shipments, those tools start returning
"No release card for build X" on fresh installs running current TD.

Policy:
    - max-drift = 0 (default): the seed corpus must cover the current stable
      build exactly. TDPilot's compatibility tools should not return an
      unknown-build response for Derivative's production release.
    - Maintainers can pass a non-zero --max-drift explicitly for an
      informational or grace-period check.
    - Network failures soft-pass by default (a Derivative outage shouldn't
      redden CI). Use --strict-network in environments where the page must be
      reachable.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = ROOT / "src" / "td_mcp" / "knowledge" / "cards" / "release"
RELEASE_NOTES_URL = "https://docs.derivative.ca/Release_Notes"
DEFAULT_MAX_DRIFT = 0
NETWORK_TIMEOUT_SECONDS = 15
USER_AGENT = "TDPilot-release-freshness-check/1.0"

_OK = 0
_DRIFT_EXCEEDED = 1
_NETWORK_SOFT_PASS = 0

# Matches TD build strings like 2025.32820 / 2026.10000. `\b` boundaries on
# both sides prevent partial matches inside longer digit runs (e.g. a 6-digit
# timestamp) but tolerate the year/build separator and any non-digit suffix.
_BUILD_PATTERN = re.compile(r"\b(20\d{2}\.\d{4,5})\b")


def parse_build_key(build: str) -> tuple[int, int]:
    """Sort key. '2025.32820' -> (2025, 32820)."""
    try:
        year_s, ord_s = build.split(".", 1)
        return int(year_s), int(ord_s)
    except (IndexError, ValueError):
        return (0, 0)


def seed_card_latest_build(cards_dir: Path = CARDS_DIR) -> str | None:
    """Newest build present in the seed cards directory, by build key."""
    if not cards_dir.is_dir():
        return None
    builds: list[str] = []
    for p in cards_dir.glob("*.json"):
        m = _BUILD_PATTERN.search(p.stem)
        if m:
            builds.append(m.group(1))
    if not builds:
        return None
    builds.sort(key=parse_build_key, reverse=True)
    return builds[0]


def extract_derivative_builds(html: str) -> list[str]:
    """Extract build numbers from Release_Notes HTML in page order (newest first).

    The Release_Notes page lists builds newest-at-top in its Recent Builds
    table; later occurrences in body anchors duplicate the same builds, so we
    de-dup while preserving first-seen order.
    """
    seen: set[str] = set()
    builds: list[str] = []
    for m in _BUILD_PATTERN.finditer(html):
        b = m.group(1)
        if b not in seen:
            seen.add(b)
            builds.append(b)
    return builds


def fetch_release_notes_html(url: str = RELEASE_NOTES_URL) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT_SECONDS) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check release-card freshness vs docs.derivative.ca/Release_Notes",
    )
    parser.add_argument(
        "--max-drift",
        type=int,
        default=DEFAULT_MAX_DRIFT,
        help=f"Builds the newest seed card may trail by (default: {DEFAULT_MAX_DRIFT}).",
    )
    parser.add_argument(
        "--offline-fixture",
        type=Path,
        default=None,
        help="Read release-notes HTML from this file instead of the network (tests).",
    )
    parser.add_argument(
        "--strict-network",
        action="store_true",
        help="Fail on network/parse errors instead of soft-passing.",
    )
    parser.add_argument(
        "--cards-dir",
        type=Path,
        default=CARDS_DIR,
        help="Override seed-cards directory (tests).",
    )
    args = parser.parse_args(argv)

    seed_latest = seed_card_latest_build(args.cards_dir)
    if seed_latest is None:
        print(
            f"ERROR: no release cards found in {args.cards_dir}",
            file=sys.stderr,
        )
        return _DRIFT_EXCEEDED

    if args.offline_fixture is not None:
        html = args.offline_fixture.read_text(encoding="utf-8")
    else:
        try:
            html = fetch_release_notes_html()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            msg = f"WARN: could not fetch {RELEASE_NOTES_URL}: {exc}"
            if args.strict_network:
                print(msg, file=sys.stderr)
                return _DRIFT_EXCEEDED
            print(f"{msg} — soft-passing (use --strict-network to fail)")
            return _NETWORK_SOFT_PASS

    derivative_builds = extract_derivative_builds(html)
    if not derivative_builds:
        msg = "WARN: no build numbers parsed from Release_Notes page. Page format may have changed."
        if args.strict_network:
            print(msg, file=sys.stderr)
            return _DRIFT_EXCEEDED
        print(f"{msg} — soft-passing (use --strict-network to fail)")
        return _NETWORK_SOFT_PASS

    derivative_latest = derivative_builds[0]
    seed_key = parse_build_key(seed_latest)
    derivative_key = parse_build_key(derivative_latest)

    if seed_key >= derivative_key:
        print(f"OK: seed card {seed_latest} matches or exceeds Derivative latest {derivative_latest}.")
        return _OK

    # Drift = position of seed_latest in the Derivative list, or total length
    # if the seed predates everything currently shown on the page.
    try:
        drift = derivative_builds.index(seed_latest)
    except ValueError:
        drift = len(derivative_builds)

    if drift <= args.max_drift:
        print(
            f"OK: seed card {seed_latest} is {drift} build(s) behind Derivative "
            f"latest {derivative_latest} (within --max-drift={args.max_drift})."
        )
        return _OK

    rel_card_dir = args.cards_dir.relative_to(ROOT) if args.cards_dir.is_relative_to(ROOT) else args.cards_dir
    print(
        f"ERROR: seed card {seed_latest} is {drift} builds behind Derivative latest "
        f"{derivative_latest} (--max-drift={args.max_drift}).\n"
        f"  Recent Derivative builds: {derivative_builds[:6]}\n"
        f"  Add a card at {rel_card_dir}/{derivative_latest}.json",
        file=sys.stderr,
    )
    return _DRIFT_EXCEEDED


if __name__ == "__main__":
    sys.exit(main())
