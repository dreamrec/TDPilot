#!/usr/bin/env python3
"""Refresh Derivative release-note HTML pages inside a local docs mirror."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

BASE_URL = "https://docs.derivative.ca"
USER_AGENT = "TDPilot-docs-release-refresh/1.0"
TIMEOUT_SECONDS = 30
BUILD_PATTERN = re.compile(r"\b(20\d{2}\.\d{4,5})\b")

DEFAULT_RELEASE_PAGES = [
    "Release_Notes",
    "Release_Notes/2025.30000",
    "Release_Notes/2025.30000/next",
    "Release_Notes/Experimental",
    "Release_Notes/2025.30000/experimental",
    "Release_Notes/2025.30000/experimental/next",
]


class RefreshResult(NamedTuple):
    page_count: int
    latest_build: str
    pages: list[str]


def local_html_path(mirror_root: Path, page: str) -> Path:
    clean_page = page.strip("/")
    if not clean_page or ".." in clean_page.split("/"):
        raise ValueError(f"unsafe release page path: {page!r}")
    return mirror_root / f"{clean_page}.html"


def fetch_page(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="replace")


def latest_build_from_html(html: str) -> str:
    builds = BUILD_PATTERN.findall(html)
    return max(builds, key=_build_key, default="")


def refresh_release_pages(
    mirror_root: Path,
    *,
    pages: list[str] | None = None,
    fetch: Callable[[str], str] = fetch_page,
) -> RefreshResult:
    mirror_root = Path(mirror_root)
    page_names = list(pages or DEFAULT_RELEASE_PAGES)
    latest_build = ""
    written: list[str] = []
    for page in page_names:
        url = f"{BASE_URL}/{page.strip('/')}"
        html = fetch(url)
        path = local_html_path(mirror_root, page)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        written.append(page)
        build = latest_build_from_html(html)
        if build and (not latest_build or _build_key(build) > _build_key(latest_build)):
            latest_build = build
    return RefreshResult(page_count=len(written), latest_build=latest_build, pages=written)


def _build_key(build: str) -> tuple[int, int]:
    try:
        year, number = build.split(".", 1)
        return int(year), int(number)
    except ValueError:
        return (0, 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mirror_root", type=Path, help="Local docs.derivative.ca mirror root.")
    parser.add_argument(
        "--page",
        action="append",
        default=[],
        help="Release page to refresh, for example Release_Notes/2025.30000. May be repeated.",
    )
    args = parser.parse_args(argv)

    result = refresh_release_pages(args.mirror_root, pages=args.page or None)
    print(
        json.dumps(
            {
                "page_count": result.page_count,
                "latest_build": result.latest_build,
                "pages": result.pages,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
