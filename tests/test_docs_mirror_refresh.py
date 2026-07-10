from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# The docs-mirror refresh is a maintainer build tool (fetches from
# docs.derivative.ca and writes one file per Derivative page ID). Derivative
# page IDs legitimately contain ':' (e.g. "Palette:bitwigMain",
# "File:Screenshot", "Experimental:Phaser_POP"), which is an illegal filename
# character on Windows — so these files cannot be created there and the tool
# is not run on Windows. Skip the whole module on win32 rather than pretend a
# macOS/Linux build script is cross-platform.
pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="docs-mirror refresh uses ':'-containing Derivative page IDs as filenames (illegal on Windows); maintainer build tool runs on macOS/Linux only",
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "refresh_docs_mirror_from_inventory",
    ROOT / "scripts" / "refresh_docs_mirror_from_inventory.py",
)
assert SPEC is not None and SPEC.loader is not None
refresh_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(refresh_module)

MirrorRefreshResult = refresh_module.MirrorRefreshResult
inventory_pages = refresh_module.inventory_pages
page_name_from_html_path = refresh_module.page_name_from_html_path
refresh_inventory_pages = refresh_module.refresh_inventory_pages


def test_page_name_from_html_path_preserves_derivative_page_ids(tmp_path: Path) -> None:
    assert page_name_from_html_path(tmp_path / "GLSL_TOP.html", tmp_path) == "GLSL_TOP"
    assert page_name_from_html_path(tmp_path / "tcp%2FipDAT.html", tmp_path) == "tcp%2FipDAT"
    assert (
        page_name_from_html_path(tmp_path / "Release_Notes" / "2025.30000.html", tmp_path)
        == "Release_Notes/2025.30000"
    )
    assert page_name_from_html_path(tmp_path / "Palette:bitwigMain.html", tmp_path) == "Palette:bitwigMain"


def test_inventory_pages_follow_docsbrain_normalizer_boundaries(tmp_path: Path) -> None:
    for rel in [
        "GLSL_TOP.html",
        "Revolve_POP.html",
        "Release_Notes/2025.30000.html",
        "Palette:bitwigMain.html",
        "File:Screenshot.png.html",
    ]:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<html></html>", encoding="utf-8")

    assert [page.name for page in inventory_pages(tmp_path)] == [
        "GLSL_TOP",
        "Palette:bitwigMain",
        "Release_Notes/2025.30000",
        "Revolve_POP",
    ]


def test_refresh_inventory_pages_writes_current_html_and_falls_back_to_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    for rel, body in {
        "GLSL_TOP.html": "old glsl",
        "Release_Notes/2025.30000.html": "old release",
        "Revolve_POP.html": "old pop",
        "Sync_In_CHOP.html": "old sync",
        "tcp%2FipDAT.html": "old tcp",
    }.items():
        path = source / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    fetched_urls: list[str] = []

    def fake_fetch(url: str) -> str:
        fetched_urls.append(url)
        if url.endswith("/Release_Notes/2025.30000") or url.endswith("/Revolve_POP"):
            raise OSError("offline")
        if url.endswith("/Sync_In_CHOP"):
            return "<html><head><title>Database error - Derivative</title></head><body>DBQueryError</body></html>"
        return f"current {url}"

    result = refresh_inventory_pages(source, output, fetch=fake_fetch, workers=2, page_aliases={})

    assert result == MirrorRefreshResult(
        page_count=5,
        fetched_count=2,
        fallback_count=3,
        failed_pages=["Release_Notes/2025.30000", "Revolve_POP", "Sync_In_CHOP"],
        mapped_pages={},
        promotion_safe=False,
    )
    assert sorted(fetched_urls) == [
        "https://docs.derivative.ca/GLSL_TOP",
        "https://docs.derivative.ca/Release_Notes/2025.30000",
        "https://docs.derivative.ca/Revolve_POP",
        "https://docs.derivative.ca/Sync_In_CHOP",
        "https://docs.derivative.ca/tcp%2FipDAT",
    ]
    assert (output / "GLSL_TOP.html").read_text(
        encoding="utf-8"
    ) == "current https://docs.derivative.ca/GLSL_TOP"
    assert (output / "Release_Notes" / "2025.30000.html").read_text(encoding="utf-8") == "old release"
    assert (output / "Revolve_POP.html").read_text(encoding="utf-8") == "old pop"
    assert (output / "Sync_In_CHOP.html").read_text(encoding="utf-8") == "old sync"
    assert (output / "tcp%2FipDAT.html").read_text(
        encoding="utf-8"
    ) == "current https://docs.derivative.ca/tcp%2FipDAT"


def test_refresh_inventory_pages_fetches_current_aliases_without_fallback(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    for rel in [
        "Experimental:Phaser_POP.html",
        "GLSL_Matrix_Functions.html",
        "index.html",
    ]:
        path = source / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"old {rel}", encoding="utf-8")

    fetched_urls: list[str] = []

    def fake_fetch(url: str) -> str:
        fetched_urls.append(url)
        if (
            url.endswith("/Experimental:Phaser_POP")
            or url.endswith("/GLSL_Matrix_Functions")
            or url.endswith("/index")
        ):
            raise OSError("legacy page is gone")
        return f"current {url}"

    result = refresh_inventory_pages(source, output, fetch=fake_fetch, workers=2)

    assert result == MirrorRefreshResult(
        page_count=3,
        fetched_count=3,
        fallback_count=0,
        failed_pages=[],
        mapped_pages={
            "Experimental:Phaser_POP": "Phaser_POP",
            "GLSL_Matrix_Functions": "Write_a_GLSL_TOP",
            "index": "Main_Page",
        },
        promotion_safe=True,
    )
    assert sorted(fetched_urls) == [
        "https://docs.derivative.ca/Main_Page",
        "https://docs.derivative.ca/Phaser_POP",
        "https://docs.derivative.ca/Write_a_GLSL_TOP",
    ]
    assert (output / "Experimental:Phaser_POP.html").read_text(encoding="utf-8") == (
        "current https://docs.derivative.ca/Phaser_POP"
    )
    assert (output / "GLSL_Matrix_Functions.html").read_text(encoding="utf-8") == (
        "current https://docs.derivative.ca/Write_a_GLSL_TOP"
    )
    assert (output / "index.html").read_text(
        encoding="utf-8"
    ) == "current https://docs.derivative.ca/Main_Page"


def test_refresh_inventory_pages_supports_official_query_url_aliases(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source_page = source / "Sync_In_CHOP.html"
    source_page.parent.mkdir(parents=True, exist_ok=True)
    source_page.write_text("old sync", encoding="utf-8")

    fetched_urls: list[str] = []

    def fake_fetch(url: str) -> str:
        fetched_urls.append(url)
        if url == "https://docs.derivative.ca/index.php?title=Sync_In_CHOP&printable=yes":
            return "current printable sync in"
        raise OSError("normal page is broken")

    result = refresh_inventory_pages(source, output, fetch=fake_fetch)

    assert result == MirrorRefreshResult(
        page_count=1,
        fetched_count=1,
        fallback_count=0,
        failed_pages=[],
        mapped_pages={"Sync_In_CHOP": "index.php?title=Sync_In_CHOP&printable=yes"},
        promotion_safe=True,
    )
    assert fetched_urls == ["https://docs.derivative.ca/index.php?title=Sync_In_CHOP&printable=yes"]
    assert (output / "Sync_In_CHOP.html").read_text(encoding="utf-8") == "current printable sync in"
