"""v1.6.7: regression tests for the three build-script bugs that left the
panel showing "Ctn" placeholder on every fresh loadTox from v1.5.6 through
v1.6.6.

The three bugs (all in `td_component/build_*.py`):

1. ``state_cache`` textDAT is never created inside ``mcp_server`` —
   renderer.bootstrap silently returns False on every load, panel never
   gets populated. Fix in v1.6.7: ``_populate_component`` now creates
   it and bakes ``td_component/state_cache.py`` content into it.
2. ``autostart`` executeDAT created with all trigger toggles at default
   False — onStart, onFrameStart, etc. are defined as functions in the
   DAT but TD never calls them because no toggle says "fire this
   callback." Fix in v1.6.7: ``_create_text_dat_with_source`` enables
   the toggles for executeDAT.
3. ``status_text`` textTOP created without ``display=True``, so the
   containerCOMP's panel surface doesn't show it. Fix in v1.6.7:
   ``_create_status_text_top`` sets display + viewer flags.

Why source-text tests rather than runtime tests: the build script can
only execute inside a running TouchDesigner (it calls ``op()``,
``parent.create()``, etc.). A unit test outside TD can't actually run
the build. So we settle for the next-best thing: assert the SOURCE
contains the calls that fix each bug. If someone removes those calls
in a future refactor, this test fails — and CI stops them.

These tests are NOT a substitute for verifying the .tox itself works.
That verification happens via ``check_tox_freshness`` (CI) plus manual
panel inspection on every release.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_TDPILOT = REPO_ROOT / "td_component" / "build_tdpilot_tox.py"
BUILD_LEGACY = REPO_ROOT / "td_component" / "build_export_mcp_tox.py"
STATE_CACHE = REPO_ROOT / "td_component" / "state_cache.py"


class TestStateCacheRestored:
    """Bug 1: state_cache.py was missing from main from v1.5.6 through v1.6.6."""

    def test_state_cache_py_exists_in_source_tree(self):
        """The file itself must be present at ``td_component/state_cache.py``."""
        assert STATE_CACHE.is_file(), (
            "td_component/state_cache.py is missing — without it the panel "
            "renderer's bootstrap silently fails. See v1.6.7 CHANGELOG."
        )

    def test_state_cache_exposes_required_functions(self):
        """Renderer + callbacks call into these functions; their absence
        would surface as runtime AttributeError on every panel tick."""
        text = STATE_CACHE.read_text(encoding="utf-8")
        for fn in ("def update", "def snapshot", "def increment", "def record_request", "def mark_ws_error"):
            assert fn in text, f"state_cache.py missing required function: {fn}"

    def test_state_cache_listed_in_TOX_SOURCE_FILES(self):
        """The file must be in the .tox source list so the freshness gate
        hash-tracks it (CI catches edits that don't trigger a .tox rebuild)."""
        text = BUILD_LEGACY.read_text(encoding="utf-8")
        # Must appear inside _TOX_SOURCE_FILES tuple
        assert '"td_component/state_cache.py"' in text, (
            "state_cache.py must be in _TOX_SOURCE_FILES in build_export_mcp_tox.py"
        )

    def test_state_cache_listed_in_freshness_gate(self):
        """``scripts/check_tox_freshness.py`` must mirror _TOX_SOURCE_FILES.
        Drift between the two would let a state_cache edit ship without a
        .tox rebuild — which would silently break the panel again."""
        freshness = (REPO_ROOT / "scripts" / "check_tox_freshness.py").read_text(encoding="utf-8")
        assert '"td_component/state_cache.py"' in freshness, (
            "state_cache.py must be in SOURCE_FILES in check_tox_freshness.py"
        )

    def test_populate_component_creates_state_cache_dat(self):
        """``_populate_component`` must create the state_cache textDAT
        inside mcp_server. Without this, the freshly-loaded .tox lacks
        the DAT and the renderer falls back to "(state_cache not loaded)"
        forever."""
        text = BUILD_LEGACY.read_text(encoding="utf-8")
        # Must call _create_with_fallback for "state_cache" textDAT
        assert '"state_cache"' in text, "_populate_component must create a textDAT named 'state_cache'"
        # Must accept state_cache_code arg + assign to .text
        assert "state_cache_code" in text, "_populate_component must accept and apply state_cache_code"

    def test_build_tdpilot_passes_state_cache_code(self):
        """The outer builder must read state_cache.py + pass content to
        _populate_component. Otherwise _populate_component would be
        called with empty state_cache_code and the DAT would be empty."""
        text = BUILD_TDPILOT.read_text(encoding="utf-8")
        assert '"td_component/state_cache.py"' in text, (
            "build_tdpilot_tox.py must read state_cache.py from disk"
        )
        assert "state_cache_code" in text, (
            "build_tdpilot_tox.py must pass state_cache_code to _populate_component"
        )


class TestAutostartTriggersEnabled:
    """Bug 2: executeDAT trigger toggles all stayed at default False, so
    autostart's callbacks never fired automatically."""

    def test_create_text_dat_enables_executeDAT_triggers(self):
        """``_create_text_dat_with_source`` must explicitly enable the
        callback toggles autostart.py uses. We test for the presence of
        the toggle names AND the True assignment."""
        text = BUILD_TDPILOT.read_text(encoding="utf-8")

        # Must reference the trigger names autostart.py defines callbacks for
        required_triggers = (
            '"start"',  # onStart — fires _disable_auth + _bootstrap + _tick
            '"framestart"',  # onFrameStart — fires _tick + _refresh_installer
            '"projectpresave"',  # onProjectPreSave (reserved hook)
            '"projectpostsave"',  # onProjectPostSave (reserved hook)
        )
        for trig in required_triggers:
            assert trig in text, f"_create_text_dat_with_source must enable {trig} on executeDAT"

        # Must scope this to executeDAT (not enable triggers on textDAT etc.)
        assert 'op_type == "executeDAT"' in text, "Trigger enabling must be guarded to executeDAT only"


class TestStatusTextDisplayEnabled:
    """Bug 3: status_text.display stayed at default False, so the
    containerCOMP's panel surface never showed it."""

    def test_create_status_text_top_sets_display_True(self):
        """``_create_status_text_top`` must explicitly set top.display = True
        (and viewer = True for safety). Without this, the textTOP renders
        its content but the panel doesn't surface it — user sees TD's
        "Ctn" placeholder instead."""
        text = BUILD_TDPILOT.read_text(encoding="utf-8")
        # Look for the assignments. They're plain attribute assignments on
        # the TOP node (not via _set_first_par because display/viewer aren't
        # custom params), so must appear literally as "top.display = True".
        assert "top.display = True" in text, (
            "_create_status_text_top must set top.display = True for the panel to surface the status_text TOP"
        )
        assert "top.viewer = True" in text, (
            "_create_status_text_top should also set top.viewer = True for the viewer flag (helps debugging)"
        )


class TestStatusTextInsideViewport:
    """v1.6.8: status_text.nodeX/nodeY MUST be inside the panel viewport
    (0..PANEL_W, 0..PANEL_H = 0..520, 0..320). TD's containerCOMP panel
    composition uses each child's network nodeX/nodeY as its position in
    the panel surface. v1.6.7 placed status_text at (600, 0) which is
    past PANEL_W=520 horizontally — so the TOP rendered correctly as a
    standalone TOP but never appeared in the panel. User saw a black
    panel even though status_text.par.text contained correct content.

    The earliest (v1.5.x) build placed it inside the viewport. v1.6.7
    regressed; v1.6.8 restores."""

    def test_status_text_nodeX_inside_panel_width(self):
        """status_text.nodeX must be < PANEL_W (520) so the TOP composites
        into the panel viewport."""
        text = BUILD_TDPILOT.read_text(encoding="utf-8")

        # The build script places status_text at "status_text.nodeX, status_text.nodeY = X, Y"
        # We need to assert X is inside [0, 520) — anything else is offscreen.
        import re

        match = re.search(
            r"status_text\.nodeX,\s*status_text\.nodeY\s*=\s*(-?\d+),\s*(-?\d+)",
            text,
        )
        assert match is not None, (
            "Could not find status_text positioning line in build_tdpilot_tox.py — "
            "the TOP must be positioned via `status_text.nodeX, status_text.nodeY = X, Y`"
        )
        x, y = int(match.group(1)), int(match.group(2))
        assert 0 <= x < 520, (
            f"status_text.nodeX={x} is OUTSIDE the panel viewport (PANEL_W=520). "
            f"The textTOP would render correctly but never composite into the panel "
            f"surface. Place at (0, 0) or another in-viewport position. See v1.6.8 CHANGELOG."
        )
        assert 0 <= y < 320, f"status_text.nodeY={y} is OUTSIDE the panel viewport (PANEL_H=320)."


class TestStatusTextNativeResolution:
    """v1.6.9: status_text resolution must match PANEL_W × PANEL_H so the
    panel-bg TOP renders without horizontal stretching when composited
    into the 520×320 panel viewport. v1.6.8 kept the default 256×256 which
    stretched 1.625:1 in the wider direction."""

    def test_status_text_resolution_matches_panel_size(self):
        text = BUILD_TDPILOT.read_text(encoding="utf-8")
        # The build script's style dict in _create_status_text_top must
        # set resolutionw/h to PANEL_W/H. Look for both literal keys in
        # the style dict (we use string keys, not direct par access).
        assert '"resolutionw": PANEL_W' in text, (
            "status_text resolutionw must match PANEL_W to avoid horizontal stretch when used as panel-bg TOP"
        )
        assert '"resolutionh": PANEL_H' in text, (
            "status_text resolutionh must match PANEL_H to avoid vertical stretch when used as panel-bg TOP"
        )


class TestStatusTextStyling:
    """v1.6.9: visual styling per user feedback — cyan-greenish text on
    90% opaque black bg. Locked into a regression test so future style
    refactors don't accidentally regress to the v1.6.8 grey-on-black look."""

    def test_status_text_font_color_is_cyan_greenish(self):
        text = BUILD_TDPILOT.read_text(encoding="utf-8")
        # Cyan-greenish: roughly (0.45, 0.95, 0.85). Allow flexibility but
        # assert the green channel is the strongest (the visual signature
        # of cyan-green vs grey/white).
        import re

        rx = re.compile(r'"fontcolor([rgb])":\s*([\d.]+)')
        colors = {m.group(1): float(m.group(2)) for m in rx.finditer(text)}
        assert "r" in colors and "g" in colors and "b" in colors, (
            "fontcolorr/g/b must all be set in _create_status_text_top"
        )
        # green > red AND green > blue → cyan/green tint, not grey
        assert colors["g"] > colors["r"], f"fontcolor must be cyan-greenish (g > r); got rgb={colors}"
        # Blue should also be elevated for the cyan note (not pure green)
        assert colors["b"] > 0.5, f"fontcolor blue channel should be elevated for cyan tint; got rgb={colors}"

    def test_status_text_bg_is_90pct_opaque_black(self):
        text = BUILD_TDPILOT.read_text(encoding="utf-8")
        assert '"bgcolorr": 0.0' in text and '"bgcolorg": 0.0' in text and '"bgcolorb": 0.0' in text, (
            "status_text bg must be black (rgb=0,0,0)"
        )
        # 90% opaque = alpha 0.9
        assert '"bgalpha": 0.9' in text, "status_text bg must be 90% opaque (alpha=0.9)"


class TestPanelBackgroundTopWired:
    """v1.6.9: containerCOMP's Look-page `top` parameter is what makes the
    panel render any TOP content. Without `comp.par.top = status_text`, the
    panel surface is just bgcolor — no text appears even when status_text
    is correctly cooking pixels. v1.6.7-v1.6.8 missed this entirely; v1.6.9
    discovered it by probing the live COMP's params and seeing `top=None`
    on the Look page after all other fixes were in place.

    The v1.5.x .tox had `top` wired correctly. The v1.5.6 containerCOMP
    refactor in build_tdpilot_tox.py dropped the wiring. v1.6.9 restores."""

    def test_populate_tdpilot_comp_wires_panel_bg_top(self):
        """``_populate_tdpilot_comp`` MUST set ``comp.par.top = status_text``
        on the outer containerCOMP. This is the single param that makes the
        panel render the textTOP content (vs just showing bgcolor)."""
        text = BUILD_TDPILOT.read_text(encoding="utf-8")
        # The build script must contain this assignment (or a structurally
        # equivalent one). Guard against the literal pattern used in v1.6.9.
        assert "comp.par.top = status_text" in text, (
            "build_tdpilot_tox.py must set `comp.par.top = status_text` "
            "in _populate_tdpilot_comp — this is the containerCOMP Look-"
            "page panel-background TOP. Without it, the panel renders as "
            "just bgcolor, no text content. See v1.6.9 CHANGELOG and "
            "Section 14 of docs/TD_INTRICACIES_AND_PATTERNS.md (local-only)."
        )


class TestOuterCompViewerEnabled:
    """v1.6.8 defense-in-depth: outer tdpilot containerCOMP must have
    ``viewer = True`` explicitly set. TD's default is True (as of TD
    2025.32460), but a future TD release flipping the default would cause
    the panel to show "Ctn" placeholder in the network editor. Explicit >
    implicit."""

    def test_populate_tdpilot_comp_sets_outer_viewer_True(self):
        """``_populate_tdpilot_comp`` must explicitly set ``comp.viewer = True``
        on the outer containerCOMP so the panel surface renders inside the
        COMP node in the network editor (vs showing the default "Ctn")."""
        text = BUILD_TDPILOT.read_text(encoding="utf-8")
        assert "comp.viewer = True" in text, (
            "_populate_tdpilot_comp must explicitly set comp.viewer = True on "
            "the outer containerCOMP — required for the panel to render in "
            "the network editor without depending on TD's default"
        )
