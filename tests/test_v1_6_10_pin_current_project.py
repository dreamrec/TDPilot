"""v1.6.10: regression tests for the pin-this-project feature.

Closes the v1.6.6 gap: that release's `_save_toe_with_externaltox`
mechanism only fired for the canonical `~/.tdpilot/tdpilot_default.toe`
autoload — user .toe files in arbitrary locations had no pin path. The
v1.6.10 fix adds:

1. New `Pinthisproject` pulse + `Bodystatus` Str + `Bodyhdr` Header on
   the Update page (built into the .tox by `build_tdpilot_tox.py`).
2. `pin_current_project()` + `_do_pin_current_project()` in installer.py.
3. `_detect_body_state()` + `body_status_from_state()` helpers that
   probe externaltox + embedded callbacks API_VERSION and produce the
   one-line Body status string the renderer reads.
4. `save_toe_pin_current` action handler in autostart.py's
   `_execute_pending_main_thread_action` (targets the open project, not
   the canonical autoload).
5. `Pinthisproject -> pin_current_project` route in installer_exec.py's
   pulse dispatcher.
6. `_read_body_row()` in renderer.py wired into `render()`.

Why source-text tests rather than runtime tests: same rationale as
test_build_script_panel_fixes.py — the build script + autostart + the
TD parameter API can only execute inside a running TouchDesigner. We
assert the SOURCE contains the wiring; CI's check_tox_freshness gate
catches a build that didn't get rebuilt; manual visual confirmation
catches anything else.

The body_status_from_state() helper IS pure-Python testable (no TD
imports needed when parent() is unbound) — so we exercise it directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_TDPILOT = REPO_ROOT / "td_component" / "build_tdpilot_tox.py"
INSTALLER_PY = REPO_ROOT / "td_component" / "installer.py"
AUTOSTART_PY = REPO_ROOT / "td_component" / "autostart.py"
INSTALLER_EXEC_PY = REPO_ROOT / "td_component" / "installer_exec.py"
RENDERER_PY = REPO_ROOT / "td_component" / "renderer.py"


# ---------------------------------------------------------------------------
# Build script: _UPDATE_PAGE has the new params
# ---------------------------------------------------------------------------


class TestBuildScriptUpdatePageHasNewParams:
    """Verify _UPDATE_PAGE in build_tdpilot_tox.py contains v1.6.10 entries."""

    def test_pinthisproject_pulse_present(self):
        text = BUILD_TDPILOT.read_text()
        assert '("Pinthisproject", "Pulse",' in text, (
            "build_tdpilot_tox.py:_UPDATE_PAGE must declare a Pinthisproject "
            "pulse — it's how users trigger the per-project pin from the "
            "Update page UI."
        )

    def test_bodystatus_string_param_present(self):
        text = BUILD_TDPILOT.read_text()
        assert '("Bodystatus", "Str",' in text, (
            "build_tdpilot_tox.py:_UPDATE_PAGE must declare a Bodystatus "
            "Str param — the renderer reads it to surface the Body row."
        )

    def test_bodyhdr_header_present(self):
        text = BUILD_TDPILOT.read_text()
        assert '("Bodyhdr", "Header", "Body source"' in text, (
            "build_tdpilot_tox.py:_UPDATE_PAGE must include a Bodyhdr "
            "header — separates Body source state from update controls."
        )


# ---------------------------------------------------------------------------
# Installer module: pin_current_project + body_status helpers
# ---------------------------------------------------------------------------


class TestInstallerHasPinCurrentProject:
    """Verify installer.py exports the new public-surface functions."""

    def test_pin_current_project_function_exists(self):
        text = INSTALLER_PY.read_text()
        assert "def pin_current_project(" in text, (
            "installer.py must define pin_current_project() — public API "
            "that the pulse dispatcher routes Pinthisproject to."
        )

    def test_do_pin_current_project_function_exists(self):
        text = INSTALLER_PY.read_text()
        assert "def _do_pin_current_project(" in text, (
            "installer.py must define _do_pin_current_project() — bg-thread "
            "worker that schedules the save_toe_pin_current main-thread action."
        )

    def test_pin_uses_existing_main_thread_bridge(self):
        """pin_current_project must wait on save_toe_pin_current action.

        Reusing the existing _wait_for_main_thread_action bridge keeps the
        threading model aligned with v1.6.6's save_toe pattern. If someone
        refactors this to use a different mechanism, this test catches it.
        """
        text = INSTALLER_PY.read_text()
        assert '_wait_for_main_thread_action("save_toe_pin_current"' in text, (
            "_do_pin_current_project must schedule the save_toe_pin_current "
            "main-thread action via _wait_for_main_thread_action."
        )

    def test_pin_refuses_when_canonical_tox_missing(self):
        """If ~/.tdpilot/td_component/tdpilot.tox is missing, pin must fail.

        Pointing externaltox at a missing file would silently restore an
        empty COMP shell on next .toe open. Better to refuse upfront.
        """
        text = INSTALLER_PY.read_text()
        assert "Cannot pin: canonical .tox missing" in text, (
            "_do_pin_current_project must raise when canonical .tox missing — "
            "pointing externaltox at a missing file leads to an empty COMP "
            "shell on next reload."
        )


class TestBodyStatusFromState:
    """body_status_from_state() is pure Python — exercise it directly."""

    @pytest.fixture
    def installer_module(self):
        """Import installer.py without requiring TD (parent() is unbound)."""
        # The path manipulation is necessary because td_component/ isn't a
        # package. installer.py uses module-level imports (json, os, etc.)
        # but doesn't actually call parent() or op() at import time.
        sys.path.insert(0, str(REPO_ROOT / "td_component"))
        try:
            import installer  # type: ignore[import-not-found]

            return installer
        finally:
            sys.path.pop(0)

    def test_pinned_when_externaltox_matches_canonical(self, installer_module):
        """When pinned_to_canonical=True → '✓ pinned'."""
        state = {
            "pinned_to_canonical": True,
            "externaltox_path": "/tmp/.tdpilot/td_component/tdpilot.tox",
            "externaltox_enabled": True,
            "embedded_api_version": "1.6.10",
            "repo_version": "1.6.10",
        }
        assert installer_module.body_status_from_state(state) == "✓ pinned"

    def test_frozen_when_versions_differ_and_no_externaltox(self, installer_module):
        """No externaltox + embedded != disk → '⚠ frozen at <embedded>'."""
        state = {
            "pinned_to_canonical": False,
            "externaltox_path": "",
            "externaltox_enabled": False,
            "embedded_api_version": "1.6.8",
            "repo_version": "1.6.10",
        }
        result = installer_module.body_status_from_state(state)
        assert result.startswith("⚠ frozen at"), result
        assert "1.6.8" in result, result

    def test_external_when_path_is_non_canonical(self, installer_module):
        """Externaltox set + enabled but not the canonical path → 'external'."""
        state = {
            "pinned_to_canonical": False,
            "externaltox_path": "/some/custom/path/tdpilot.tox",
            "externaltox_enabled": True,
            "embedded_api_version": "1.6.10",
            "repo_version": "1.6.10",
        }
        result = installer_module.body_status_from_state(state)
        assert "external" in result, result

    def test_embedded_no_drift_when_versions_match(self, installer_module):
        """No externaltox but versions match → 'embedded (no auto-update)'."""
        state = {
            "pinned_to_canonical": False,
            "externaltox_path": "",
            "externaltox_enabled": False,
            "embedded_api_version": "1.6.10",
            "repo_version": "1.6.10",
        }
        result = installer_module.body_status_from_state(state)
        assert "embedded" in result, result

    def test_checking_when_no_probe_data(self, installer_module):
        """Empty state (parent() unbound, no probe yet) → '(checking)'."""
        state = {
            "pinned_to_canonical": False,
            "externaltox_path": "",
            "externaltox_enabled": False,
            "embedded_api_version": None,
        }
        assert installer_module.body_status_from_state(state) == "(checking)"


# ---------------------------------------------------------------------------
# Autostart: save_toe_pin_current action handler
# ---------------------------------------------------------------------------


class TestAutostartHasSaveToePinCurrent:
    """Verify autostart.py's _execute_pending_main_thread_action handles
    the new action."""

    def test_save_toe_pin_current_action_branch_exists(self):
        text = AUTOSTART_PY.read_text()
        assert 'action == "save_toe_pin_current"' in text, (
            "autostart.py must handle action == 'save_toe_pin_current' — "
            "the bg-thread bridge that pin_current_project uses to do the "
            "actual project.save on the main thread."
        )

    def test_save_toe_pin_current_targets_open_project(self):
        """The pin-current-project handler must save the OPEN project, not
        the canonical autoload — that's the whole point of the v1.6.10 fix.
        """
        text = AUTOSTART_PY.read_text()
        # The handler must reference project.folder + project.name (= the
        # open .toe path), not autoload_toe() (= the canonical).
        assert "project.folder" in text, (
            "save_toe_pin_current handler must compute the target path from "
            "project.folder + project.name (the open .toe), not from "
            "installer.module.autoload_toe() (the canonical)."
        )

    def test_save_toe_pin_current_refuses_unsaved_project(self):
        """Saving an unsaved project (project.name == 'untitled.toe' or
        similar) doesn't make sense — there's nothing to reopen."""
        text = AUTOSTART_PY.read_text()
        assert "Cannot pin unsaved project" in text, (
            "save_toe_pin_current handler must refuse when the project "
            "hasn't been saved yet — pinning an unsaved file produces a "
            ".toe at an unpredictable location."
        )

    def test_save_toe_pin_current_reuses_externaltox_helper(self):
        """The handler must reuse the v1.6.6 _save_toe_with_externaltox
        helper. Don't duplicate the externaltox + saveExternalToxs=False
        logic — keep it in one place."""
        text = AUTOSTART_PY.read_text()
        # Both the save_toe AND save_toe_pin_current branches should call
        # _save_toe_with_externaltox.
        save_toe_pin_idx = text.index('action == "save_toe_pin_current"')
        # Check the handler body (next ~30 lines after the elif)
        snippet = text[save_toe_pin_idx : save_toe_pin_idx + 1500]
        assert "_save_toe_with_externaltox(installer," in snippet, (
            "save_toe_pin_current handler must reuse "
            "_save_toe_with_externaltox(installer, target) for the actual "
            "save — don't duplicate that logic."
        )


# ---------------------------------------------------------------------------
# Installer exec: Pinthisproject pulse routing
# ---------------------------------------------------------------------------


class TestInstallerExecRoutesPinPulse:
    """Verify installer_exec.py:_PULSE_DISPATCH wires the new pulse."""

    def test_pinthisproject_routed_to_pin_current_project(self):
        text = INSTALLER_EXEC_PY.read_text()
        assert '"Pinthisproject": "pin_current_project"' in text, (
            "installer_exec.py:_PULSE_DISPATCH must map 'Pinthisproject' to "
            "'pin_current_project' so clicking the pulse on the Update page "
            "actually calls the new installer function."
        )


# ---------------------------------------------------------------------------
# Renderer: Body row reads Bodystatus
# ---------------------------------------------------------------------------


class TestRendererReadsBodystatus:
    """Verify renderer.py reads parent.par.Bodystatus and renders a row."""

    def test_read_body_row_function_exists(self):
        text = RENDERER_PY.read_text()
        assert "def _read_body_row(" in text, (
            "renderer.py must define _read_body_row() — reads parent's "
            "Bodystatus param and formats it for the panel."
        )

    def test_render_calls_read_body_row(self):
        """The render() function must actually USE _read_body_row() —
        defining it without wiring it produces a silent no-op."""
        text = RENDERER_PY.read_text()
        # Find the render() function and check it references _read_body_row.
        render_idx = text.index("def render():")
        next_def = text.find("\ndef ", render_idx + 1)
        render_body = text[render_idx:next_def]
        assert "_read_body_row()" in render_body, (
            "renderer.render() must call _read_body_row() and append its "
            "output to the panel — defining the helper without wiring it "
            "produces a silent no-op."
        )

    def test_body_row_surfaces_pin_hint_when_frozen(self):
        """When Bodystatus starts with '⚠', the row must include
        the actionable hint pointing at the new pulse."""
        text = RENDERER_PY.read_text()
        assert "click 'Pin this project'" in text, (
            "_read_body_row must surface 'click Pin this project' as an "
            "actionable hint when the body is frozen — that's the user-"
            "facing antidote to the 'panel says X but param tab says Y' "
            "confusion class."
        )


# ---------------------------------------------------------------------------
# Build script: dynamic version labels (v1.6.10 cleanup)
# ---------------------------------------------------------------------------


class TestBuildScriptUsesDynamicVersion:
    """v1.6.10 cleanup: build_tdpilot_tox.py used to hardcode "v1.5.6" in
    print/comment/info_text strings, which never got bumped during version
    cascades. The user spotted this in the v1.6.10 build and asked "why
    1.5.6?" — fair question. Fix: read __version__ dynamically at build
    time, so labels follow the package version automatically.

    These tests guard against regression to the hardcoded-version style.
    """

    def test_no_hardcoded_v156_in_runtime_strings(self):
        """The build script must not contain hardcoded "v1.5.6" labels.

        Historical references in COMMENTS are fine (e.g. "introduced in
        v1.5.6") — they're documentation. But runtime strings like
        ``comp.comment = "TDPilot v1.5.6 ..."`` or
        ``print("[TDPilot] Built v1.5.6 ...")`` produced the user-visible
        drift bug. Catch any new occurrence in those positions.

        We allow "v1.5.6" inside Python COMMENTS (lines starting with #)
        and inside DOCSTRINGS, but not in:
          - print(...) format strings
          - comp.comment = ... assignments
          - return strings from _build_info_text*
        """
        text = BUILD_TDPILOT.read_text()
        # Forbidden: any of these patterns where the string contains
        # the literal "v1.5.6" (or any other hardcoded version).
        forbidden_patterns = [
            'comp.comment = "TDPilot v1.5.6',
            '"TDPilot v1.5.6 installer + MCP server\\n"',
            'print("[TDPilot] Built v1.5.6',
        ]
        for pattern in forbidden_patterns:
            assert pattern not in text, (
                "build_tdpilot_tox.py contains hardcoded label "
                f"'{pattern}' — this caused the v1.5.6 drift confusion "
                "the user reported in the v1.6.10 session. Use "
                "_read_canonical_version(repo_root) instead so labels "
                "follow the canonical __version__ automatically."
            )

    def test_read_canonical_version_helper_exists(self):
        """The dynamic version helper must be present."""
        text = BUILD_TDPILOT.read_text()
        assert "def _read_canonical_version(" in text, (
            "build_tdpilot_tox.py must define _read_canonical_version() — "
            "the helper that parses src/td_mcp/__init__.py for __version__ "
            "so build labels follow the package version automatically."
        )

    def test_build_print_calls_canonical_version(self):
        """The build's `print('[TDPilot] Built v...')` must use the
        dynamic helper, not a hardcoded version string."""
        text = BUILD_TDPILOT.read_text()
        assert '_read_canonical_version(repo_root) + " tdpilot COMP"' in text, (
            "The build's success print must use _read_canonical_version() "
            "so it announces the actual package version, not a frozen "
            "v1.5.6 / v1.6.X / etc."
        )

    def test_comp_comment_uses_canonical_version(self):
        """The COMP's comment (visible in TD's network editor) must use
        the dynamic version."""
        text = BUILD_TDPILOT.read_text()
        # The line should look like:
        #   comp.comment = "TDPilot v" + version + " installer + MCP server panel"
        assert 'comp.comment = "TDPilot v" + version + " installer + MCP server panel"' in text, (
            "comp.comment assignment must concatenate the dynamic version, not hardcode a version literal."
        )
