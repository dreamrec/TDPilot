"""Tests for docs brain normalizer and metadata extraction."""

from __future__ import annotations

from td_mcp.knowledge.docsbrain.metadata import (
    classify_page,
    derive_page_id,
    derive_url,
    extract_operator_family,
    extract_operator_name,
    should_skip_file,
    slugify,
)


class TestClassifyPage:
    def test_operator_top(self):
        assert classify_page("Composite_TOP") == "operator"

    def test_operator_chop(self):
        assert classify_page("Wave_CHOP") == "operator"

    def test_operator_pop(self):
        assert classify_page("Particle_POP") == "operator"

    def test_python_api_class(self):
        assert classify_page("CompositeTOP_Class") == "python_api"

    def test_python_api_bare_class(self):
        assert classify_page("OP_Class") == "python_api"

    def test_release_notes(self):
        assert classify_page("Release_Notes/2025.30000") == "release_notes"

    def test_palette(self):
        assert classify_page("Palette:camSchnappr") == "palette"

    def test_snippet(self):
        assert classify_page("OP_Snippets") == "snippet"

    def test_glossary(self):
        assert classify_page("TouchDesigner_Glossary") == "glossary"

    def test_general(self):
        assert classify_page("3D_Parenting") == "general"

    def test_skip_file_page(self):
        assert classify_page("File:some_image.jpg") is None


class TestDerivePageId:
    def test_simple_operator(self):
        assert derive_page_id("Composite_TOP.html") == "composite_top"

    def test_release_notes_with_path(self):
        assert derive_page_id("Release_Notes/2025.30000.html") == "release_notes__2025_30000"

    def test_palette_colon(self):
        assert derive_page_id("Palette:camSchnappr.html") == "palette:camschnappr"

    def test_no_html_suffix(self):
        assert derive_page_id("Composite_TOP") == "composite_top"


class TestDeriveUrl:
    def test_simple(self):
        assert derive_url("Composite_TOP.html") == "https://docs.derivative.ca/Composite_TOP"

    def test_release_notes(self):
        assert (
            derive_url("Release_Notes/2025.30000.html")
            == "https://docs.derivative.ca/Release_Notes/2025.30000"
        )


class TestShouldSkipFile:
    def test_skip_css(self):
        assert should_skip_file("style.css") is True

    def test_skip_png(self):
        assert should_skip_file("image.png") is True

    def test_skip_loadphp(self):
        assert should_skip_file("load.php?lang=en") is True

    def test_keep_html(self):
        assert should_skip_file("Composite_TOP.html") is False


class TestExtractOperatorFamily:
    def test_top(self):
        assert extract_operator_family("Composite_TOP.html") == "TOP"

    def test_chop(self):
        assert extract_operator_family("Wave_CHOP.html") == "CHOP"

    def test_pop(self):
        assert extract_operator_family("Particle_POP.html") == "POP"

    def test_non_operator(self):
        assert extract_operator_family("3D_Parenting.html") is None


class TestExtractOperatorName:
    def test_operator(self):
        assert extract_operator_name("Composite TOP") == "Composite TOP"

    def test_non_operator(self):
        assert extract_operator_name("3D Parenting") is None


class TestSlugify:
    def test_simple(self):
        assert slugify("Bug Fixes and Improvements") == "bug_fixes_and_improvements"

    def test_special_chars(self):
        assert slugify("Build 2025.32460 Mar 10, 2026") == "build_2025_32460_mar_10_2026"


from pathlib import Path

from td_mcp.knowledge.docsbrain.normalizer import normalize_file

FIXTURES = Path(__file__).parent / "fixtures" / "sample_pages"


class TestNormalizeFile:
    def test_operator_page(self):
        result = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        assert result is not None
        assert result["page_id"] == "composite_top"
        assert result["title"] == "Composite TOP"
        assert result["doc_type"] == "operator"
        assert result["operator_family"] == "TOP"
        assert "Summary" in result["headings"]
        assert "Parameters" in result["headings"]
        assert "text_hash" in result

    def test_boilerplate_stripped(self):
        result = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        assert result is not None
        # Edit links, navigation, footer should be gone
        assert "[edit]" not in result["text"]
        assert "Jump to navigation" not in result["text"]
        assert "Footer here" not in result["text"]
        # But actual content should be present
        assert "Composite TOP" in result["text"]
        assert "Operand" in result["text"]

    def test_lingo_terms_unwrapped(self):
        result = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        assert result is not None
        # Lingo span text should be kept, wrapper removed
        assert "Composite TOP" in result["text"]

    def test_skips_non_html(self):
        result = normalize_file(FIXTURES / "Composite_TOP.html", "style.css")
        assert result is None

    def test_skips_file_pages(self):
        result = normalize_file(FIXTURES / "Composite_TOP.html", "File:some_image.jpg.html")
        assert result is None

    def test_release_notes_page(self):
        result = normalize_file(
            FIXTURES / "Release_Notes" / "2025.30000.html",
            "Release_Notes/2025.30000.html",
        )
        assert result is not None
        assert result["doc_type"] == "release_notes"
        assert result["page_id"] == "release_notes__2025_30000"
        assert "Build 2025.32460" in result["text"] or "New Features" in result["headings"]
