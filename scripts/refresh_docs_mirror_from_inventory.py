#!/usr/bin/env python3
"""Refresh a Derivative docs mirror from its normalizable page inventory."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import shutil
import sys
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from td_mcp.knowledge.docsbrain.metadata import classify_page, should_skip_file  # noqa: E402

BASE_URL = "https://docs.derivative.ca"
USER_AGENT = "TDPilot-docs-mirror-refresh/1.0"
TIMEOUT_SECONDS = 30
DEFAULT_PAGE_ALIASES = {
    "Experimental:Alembic_In_POP": "Alembic_In_POP",
    "Experimental:Array_Attribute": "Array_Attribute",
    "Experimental:Learning_About_POPs": "Learning_About_POPs",
    "Experimental:Movin3D": "Movin3D",
    "Experimental:Phaser_POP": "Phaser_POP",
    "GLSL_Matrix_Functions": "Write_a_GLSL_TOP",
    "index": "Main_Page",
    "Sync_In_CHOP": "index.php?title=Sync_In_CHOP&printable=yes",
}


class InventoryPage(NamedTuple):
    name: str
    source_path: Path


class MirrorRefreshResult(NamedTuple):
    page_count: int
    fetched_count: int
    fallback_count: int
    failed_pages: list[str]
    mapped_pages: dict[str, str]
    promotion_safe: bool


def page_name_from_html_path(path: Path, mirror_root: Path) -> str:
    """Return the Derivative page ID for a mirrored HTML path."""
    relative = Path(path).relative_to(mirror_root).as_posix()
    if not relative.endswith(".html"):
        raise ValueError(f"not an HTML page path: {path}")
    return relative[:-5]


def inventory_pages(source_root: Path) -> list[InventoryPage]:
    """Return normalizable page inventory using DocsBrain's metadata boundaries."""
    source_root = Path(source_root)
    pages: list[InventoryPage] = []
    for path in sorted(source_root.rglob("*.html")):
        relative = path.relative_to(source_root).as_posix()
        if should_skip_file(relative):
            continue
        page_name = page_name_from_html_path(path, source_root)
        if classify_page(page_name) is None:
            continue
        pages.append(InventoryPage(name=page_name, source_path=path))
    return pages


def fetch_page(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="replace")


def refresh_inventory_pages(
    source_root: Path,
    output_root: Path,
    *,
    pages: list[str] | None = None,
    fetch: Callable[[str], str] = fetch_page,
    continue_on_error: bool = True,
    workers: int = 1,
    page_aliases: dict[str, str] | None = None,
) -> MirrorRefreshResult:
    """Fetch current official HTML for inventory pages into a staged mirror."""
    source_root = Path(source_root)
    output_root = Path(output_root)
    if workers < 1:
        raise ValueError("workers must be at least 1")
    inventory = inventory_pages(source_root)
    if pages is not None:
        selected = set(pages)
        inventory = [page for page in inventory if page.name in selected]
    aliases = dict(DEFAULT_PAGE_ALIASES if page_aliases is None else page_aliases)

    def refresh_one(page: InventoryPage) -> tuple[bool, str | None, str | None]:
        fetch_name = aliases.get(page.name, page.name)
        url = _url_for_page(fetch_name)
        output_path = output_root / f"{page.name}.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            html = fetch(url)
            if _looks_like_error_page(html):
                raise OSError("official docs returned an error page")
        except Exception:
            if not continue_on_error:
                raise
            shutil.copyfile(page.source_path, output_path)
            return False, page.name, None
        output_path.write_text(html, encoding="utf-8")
        mapped_to = fetch_name if fetch_name != page.name else None
        return True, None, mapped_to

    fetched_count = 0
    fallback_count = 0
    failed_pages: list[str] = []
    mapped_pages: dict[str, str] = {}

    if workers == 1:
        results = [refresh_one(page) for page in inventory]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(refresh_one, page) for page in inventory]
            results = [future.result() for future in futures]

    for page, (fetched, failed_page, mapped_to) in zip(inventory, results, strict=True):
        if fetched:
            fetched_count += 1
            if mapped_to is not None:
                mapped_pages[page.name] = mapped_to
        else:
            fallback_count += 1
            if failed_page is not None:
                failed_pages.append(failed_page)

    return MirrorRefreshResult(
        page_count=len(inventory),
        fetched_count=fetched_count,
        fallback_count=fallback_count,
        failed_pages=failed_pages,
        mapped_pages=mapped_pages,
        promotion_safe=fallback_count == 0 and bool(inventory),
    )


def _url_for_page(page_name: str) -> str:
    clean_page = page_name.strip("/")
    if not clean_page or ".." in clean_page.split("/"):
        raise ValueError(f"unsafe page path: {page_name!r}")
    if clean_page.startswith("index.php?"):
        return f"{BASE_URL}/{clean_page}"
    quoted = urllib.parse.quote(clean_page, safe="/:%+._-()")
    return f"{BASE_URL}/{quoted}"


def _looks_like_error_page(html: str) -> bool:
    lower = html.lower()
    return (
        "<title>database error - derivative</title>" in lower
        or '<h1 id="firstheading" class="firstheading mw-first-heading">database error</h1>' in lower
        or "wikimedia\\rdbms\\dbqueryerror" in lower
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", required=True, type=Path, help="Existing local docs.derivative.ca mirror root."
    )
    parser.add_argument("--output", required=True, type=Path, help="Staged refreshed mirror output root.")
    parser.add_argument(
        "--page", action="append", default=[], help="Specific page ID to refresh. May be repeated."
    )
    parser.add_argument("--limit", type=int, default=None, help="Refresh only the first N inventory pages.")
    parser.add_argument("--workers", type=int, default=1, help="Number of concurrent fetch workers.")
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Raise on the first fetch failure instead of falling back to source HTML.",
    )
    args = parser.parse_args(argv)

    pages = args.page or None
    if args.limit is not None:
        inventory = [page.name for page in inventory_pages(args.source)]
        limited = inventory[: args.limit]
        pages = [page for page in limited if pages is None or page in pages]

    result = refresh_inventory_pages(
        args.source,
        args.output,
        pages=pages,
        continue_on_error=not args.fail_fast,
        workers=args.workers,
    )
    print(
        json.dumps(
            {
                "page_count": result.page_count,
                "fetched_count": result.fetched_count,
                "fallback_count": result.fallback_count,
                "failed_pages": result.failed_pages,
                "mapped_pages": result.mapped_pages,
                "promotion_safe": result.promotion_safe,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
