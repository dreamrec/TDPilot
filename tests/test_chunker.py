"""Tests for the docs brain chunker."""

from __future__ import annotations

from pathlib import Path

from td_mcp.knowledge.docsbrain.chunker import chunk_page
from td_mcp.knowledge.docsbrain.normalizer import normalize_file

FIXTURES = Path(__file__).parent / "fixtures" / "sample_pages"


class TestChunkPage:
    def test_operator_produces_chunks(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        assert page is not None
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        assert len(chunks) >= 2  # At least summary + parameters

    def test_chunk_has_required_fields(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        required = {
            "chunk_id",
            "page_id",
            "doc_type",
            "section_title",
            "operator_family",
            "operator_name",
            "mentioned_operators",
            "parameter_names",
            "python_symbols",
            "build_number",
            "build_date",
            "change_category",
            "token_estimate",
            "content",
        }
        for chunk in chunks:
            assert required.issubset(chunk.keys()), f"Missing: {required - chunk.keys()}"

    def test_chunk_ids_are_unique(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        ids = [c["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_chunk_ids_contain_page_id(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        for chunk in chunks:
            assert chunk["chunk_id"].startswith("composite_top__")

    def test_operator_name_propagated(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        for chunk in chunks:
            assert chunk["operator_name"] == "Composite TOP"

    def test_token_estimate_reasonable(self):
        page = normalize_file(FIXTURES / "Composite_TOP.html", "Composite_TOP.html")
        chunks = chunk_page(page, FIXTURES / "Composite_TOP.html")
        for chunk in chunks:
            assert chunk["token_estimate"] > 0
            # No chunk should be absurdly large for this small fixture
            assert chunk["token_estimate"] < 5000

    def test_operator_parameter_names_ignore_bullet_menu_choices(self, tmp_path: Path):
        html_path = tmp_path / "Anti_Alias_TOP.html"
        html_path.write_text(
            """<!DOCTYPE html>
<html>
<body>
<div id="mw-content-text">
  <h1 id="firstHeading"><span class="mw-page-title-main">Anti Alias TOP</span></h1>
  <h2><span class="mw-headline" id="Summary">Summary</span></h2>
  <p>The Anti Alias TOP applies screen-space antialiasing.</p>
  <h2><span class="mw-headline" id="Parameters_-_Anti_Alias_Page">Parameters - Anti Alias Page</span></h2>
  <p>Quality <code>quality</code> - &#8862; - Controls the quality of the anti-alias process.</p>
  <ul>
    <li>Low <code>low</code> -</li>
    <li>Medium <code>medium</code> -</li>
    <li>High <code>high</code> -</li>
  </ul>
  <p>Edge Detect Source <code>edgedetectsource</code> - &#8862; - Controls how edges are detected.</p>
  <ul>
    <li>Luminance <code>lum</code> - Uses luminance.</li>
    <li>RGB <code>rgb</code> - Uses RGB channels.</li>
  </ul>
  <p>Edge Threshold <code>edgethreshold</code> - Controls the sensitivity of edge detection.</p>
</div>
</body>
</html>
""",
            encoding="utf-8",
        )
        page = normalize_file(html_path, "Anti_Alias_TOP.html")
        assert page is not None

        chunks = chunk_page(page, html_path)
        params_chunk = next(
            chunk for chunk in chunks if chunk["section_title"] == "Parameters - Anti Alias Page"
        )

        assert params_chunk["parameter_names"] == [
            "Quality\nquality",
            "Edge Detect Source\nedgedetectsource",
            "Edge Threshold\nedgethreshold",
        ]

    def test_operator_parameter_names_ignore_nested_collapsible_menu_choices(self, tmp_path: Path):
        html_path = tmp_path / "Anti_Alias_TOP.html"
        html_path.write_text(
            """<!DOCTYPE html>
<html>
<body>
<div id="mw-content-text">
  <h1 id="firstHeading"><span class="mw-page-title-main">Anti Alias TOP</span></h1>
  <h2><span class="mw-headline" id="Summary">Summary</span></h2>
  <p>The Anti Alias TOP applies screen-space antialiasing.</p>
  <h2><span class="mw-headline" id="Parameters_-_Anti_Alias_Page"><div class="sectionBarTOP">Parameters - Anti Alias Page</div></span></h2>
  <div id="quality">
    <span class="parNameTOP">Quality</span> <code>quality</code> - <span class="mw-customtoggle-quality">⊞</span> - Controls quality.
    <div class="mw-collapsible mw-collapsed" id="mw-customcollapsible-quality">
      <ul><li><span class="parNameTOP">Low</span> <code>low</code> -</li></ul>
      <ul><li><span class="parNameTOP">Medium</span> <code>medium</code> -</li></ul>
      <ul><li><span class="parNameTOP">High</span> <code>high</code> -</li></ul>
    </div>
  </div>
  <div id="edgedetectsource">
    <span class="parNameTOP">Edge Detect Source</span> <code>edgedetectsource</code> - <span class="mw-customtoggle-edgedetectsource">⊞</span> - Controls edge detection.
    <div class="mw-collapsible mw-collapsed" id="mw-customcollapsible-edgedetectsource">
      <ul><li><span class="parNameTOP">Luminance</span> <code>lum</code> - Uses luminance.</li></ul>
      <ul><li><span class="parNameTOP">RGB</span> <code>rgb</code> - Uses RGB channels.</li></ul>
    </div>
  </div>
  <div id="edgethreshold"><span class="parNameTOP">Edge Threshold</span> <code>edgethreshold</code> - Controls threshold.</div>
</div>
</body>
</html>
""",
            encoding="utf-8",
        )
        page = normalize_file(html_path, "Anti_Alias_TOP.html")
        assert page is not None

        chunks = chunk_page(page, html_path)
        params_chunk = next(
            chunk for chunk in chunks if chunk["section_title"] == "Parameters - Anti Alias Page"
        )

        assert params_chunk["parameter_names"] == [
            "Quality\nquality",
            "Edge Detect Source\nedgedetectsource",
            "Edge Threshold\nedgethreshold",
        ]


class TestReleaseNoteChunks:
    def test_release_notes_produce_chunks(self):
        page = normalize_file(
            FIXTURES / "Release_Notes" / "2025.30000.html",
            "Release_Notes/2025.30000.html",
        )
        assert page is not None
        chunks = chunk_page(page, FIXTURES / "Release_Notes" / "2025.30000.html")
        assert len(chunks) >= 2

    def test_release_chunks_have_build_numbers(self):
        page = normalize_file(
            FIXTURES / "Release_Notes" / "2025.30000.html",
            "Release_Notes/2025.30000.html",
        )
        chunks = chunk_page(page, FIXTURES / "Release_Notes" / "2025.30000.html")
        # At least some chunks should have build numbers
        build_chunks = [c for c in chunks if c["build_number"]]
        assert len(build_chunks) >= 1

    def test_release_chunks_have_mentioned_operators(self):
        page = normalize_file(
            FIXTURES / "Release_Notes" / "2025.30000.html",
            "Release_Notes/2025.30000.html",
        )
        chunks = chunk_page(page, FIXTURES / "Release_Notes" / "2025.30000.html")
        # At least one chunk should mention operators
        op_chunks = [c for c in chunks if c["mentioned_operators"]]
        assert len(op_chunks) >= 1

    def test_release_chunks_have_change_category(self):
        page = normalize_file(
            FIXTURES / "Release_Notes" / "2025.30000.html",
            "Release_Notes/2025.30000.html",
        )
        chunks = chunk_page(page, FIXTURES / "Release_Notes" / "2025.30000.html")
        cats = {c["change_category"] for c in chunks if c["change_category"]}
        # Should detect at least new_feature and bug_fix
        assert "new_feature" in cats or "bug_fix" in cats
