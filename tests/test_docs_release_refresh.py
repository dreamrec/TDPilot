from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "refresh_docs_release_pages",
    ROOT / "scripts" / "refresh_docs_release_pages.py",
)
assert SPEC is not None and SPEC.loader is not None
refresh_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(refresh_module)

DEFAULT_RELEASE_PAGES = refresh_module.DEFAULT_RELEASE_PAGES
RefreshResult = refresh_module.RefreshResult
local_html_path = refresh_module.local_html_path
refresh_release_pages = refresh_module.refresh_release_pages


def test_local_html_path_maps_derivative_release_urls_to_mirror_paths(tmp_path: Path) -> None:
    assert local_html_path(tmp_path, "Release_Notes") == tmp_path / "Release_Notes.html"
    assert (
        local_html_path(tmp_path, "Release_Notes/2025.30000")
        == tmp_path / "Release_Notes" / "2025.30000.html"
    )
    assert (
        local_html_path(tmp_path, "Release_Notes/2025.30000/experimental")
        == tmp_path / "Release_Notes" / "2025.30000" / "experimental.html"
    )


def test_refresh_release_pages_writes_each_page_and_reports_builds(tmp_path: Path) -> None:
    fetched_urls: list[str] = []

    def fake_fetch(url: str) -> str:
        fetched_urls.append(url)
        return f"<html><body>Build 2025.32820 from {url}</body></html>"

    result = refresh_release_pages(
        tmp_path,
        pages=["Release_Notes", "Release_Notes/2025.30000"],
        fetch=fake_fetch,
    )

    assert result == RefreshResult(
        page_count=2,
        latest_build="2025.32820",
        pages=["Release_Notes", "Release_Notes/2025.30000"],
    )
    assert fetched_urls == [
        "https://docs.derivative.ca/Release_Notes",
        "https://docs.derivative.ca/Release_Notes/2025.30000",
    ]
    assert "2025.32820" in (tmp_path / "Release_Notes.html").read_text(encoding="utf-8")
    assert "2025.32820" in (tmp_path / "Release_Notes" / "2025.30000.html").read_text(encoding="utf-8")


def test_default_release_pages_cover_current_stable_and_next_release_sources() -> None:
    assert "Release_Notes" in DEFAULT_RELEASE_PAGES
    assert "Release_Notes/2025.30000" in DEFAULT_RELEASE_PAGES
    assert "Release_Notes/2025.30000/next" in DEFAULT_RELEASE_PAGES
    assert "Release_Notes/2025.30000/experimental" in DEFAULT_RELEASE_PAGES
