"""Tests for v1.6.6 ``autostart._save_toe_with_externaltox``.

The architectural fix v1.6.6 ships:
   When the user clicks "Update Now" (or anything else that triggers the
   "save_toe" main-thread action), don't just project.save the current
   COMP content into the .toe — first set the COMP's ``externaltox``
   parameter to point at the on-disk .tox file. That way the .toe stores
   only a thin reference to the .tox, and every future TD launch reads
   the latest .tox content fresh from disk instead of restoring a frozen
   embedded copy.

Why this matters: pre-v1.6.6 the .toe baked the entire current COMP
content (with whatever API_VERSION was current at save time). Future
launches restored the frozen content forever, which is why the user
kept seeing "TDPilot 1.5.3" in the panel even after the on-disk .tox
was updated to v1.6.5.

Why we can't rely on the v1.6.5 Startup-script sweep alone: TD scans
~/Documents/Derivative/Startup/ scripts BEFORE opening the default
project file. So when the sweep runs, /project1 doesn't exist yet —
the sweep loads .tox into /local, then the .toe restore wipes /local
and brings back the stale /project1/tdpilot. v1.6.5's sweep is
best-effort only; v1.6.6's externaltox is the canonical fix.

This test file uses the same importlib pattern as test_autopin.py and
test_startup_sweep.py to load autostart.py without firing TD-side
code, then injects fake ``parent``, ``project``, and ``op`` globals
into the loaded module's namespace.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AUTOSTART_PATH = REPO_ROOT / "td_component" / "autostart.py"


@pytest.fixture(scope="module")
def autostart_module():
    """Load autostart.py without firing any TD-side code at import time.

    autostart.py has no module-level function calls — it just defines
    constants + functions — so a plain importlib.exec_module is safe
    even outside TD.
    """
    spec = importlib.util.spec_from_file_location("tdpilot_autostart_under_test", AUTOSTART_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakePar:
    """Stand-in for a TD .par.<paramname> attribute that supports assignment."""

    def __init__(self, value=None):
        self.value = value

    def __eq__(self, other):
        return self.value == other

    def __repr__(self):
        return f"FakePar({self.value!r})"


class FakeParCollection:
    """Stand-in for COMP.par — supports both attribute-style access and the
    ``hasattr(comp.par, 'externaltox')`` checks the production code uses.

    Pass ``has_externaltox=False`` to test the no-externaltox-param fallback
    (e.g., baseCOMP without externaltox support).
    """

    def __init__(self, has_externaltox=True, has_enableexternaltox=True):
        if has_externaltox:
            self.externaltox = FakePar("")
        if has_enableexternaltox:
            self.enableexternaltox = FakePar(False)


class FakeCOMP:
    def __init__(self, has_externaltox=True, has_enableexternaltox=True):
        self.par = FakeParCollection(has_externaltox, has_enableexternaltox)


class FakeProject:
    def __init__(self):
        self.save_calls: list[tuple[str, dict]] = []
        # Some TD builds may not accept saveExternalToxs kwarg → simulate
        # that by setting raises_typeerror=True
        self.raises_typeerror_on_kwarg = False

    def save(self, target, **kwargs):
        if self.raises_typeerror_on_kwarg and "saveExternalToxs" in kwargs:
            raise TypeError("save() got unexpected keyword argument 'saveExternalToxs'")
        self.save_calls.append((target, dict(kwargs)))


def install_globals(autostart_module, monkeypatch, *, comp, fake_project, install_dir):
    """Inject parent(), project, op into the autostart module namespace.

    These are TD-injected builtins that don't exist outside TD; tests
    monkeypatch them onto the loaded module via raising=False (same
    pattern used by tests/test_startup_sweep.py for the Startup script).
    """
    monkeypatch.setattr(autostart_module, "parent", lambda: comp, raising=False)
    monkeypatch.setattr(autostart_module, "project", fake_project, raising=False)
    monkeypatch.setattr(autostart_module, "op", lambda *_a, **_kw: None, raising=False)


def make_installer_mock(install_dir: str):
    """Mimic the installer.module surface that _save_toe_with_externaltox calls."""
    installer = MagicMock()
    installer.module.install_dir.return_value = install_dir
    return installer


# ---------------------------------------------------------------------------
# _save_toe_with_externaltox happy path
# ---------------------------------------------------------------------------


class TestExternaltoxHappyPath:
    def test_sets_externaltox_when_tox_exists(self, autostart_module, monkeypatch, tmp_path):
        """When .tox exists on disk and COMP has externaltox param, set it + save."""
        # Create a fake .tox file on disk so os.path.isfile passes
        td_component_dir = tmp_path / "td_component"
        td_component_dir.mkdir()
        tox_file = td_component_dir / "tdpilot.tox"
        tox_file.write_bytes(b"fake .tox content")

        comp = FakeCOMP(has_externaltox=True, has_enableexternaltox=True)
        fake_project = FakeProject()
        install_globals(
            autostart_module, monkeypatch, comp=comp, fake_project=fake_project, install_dir=str(tmp_path)
        )

        installer = make_installer_mock(str(tmp_path))

        target_toe = str(tmp_path / "tdpilot_default.toe")
        result = autostart_module._save_toe_with_externaltox(installer, target_toe)

        assert result is True
        # Production code assigns comp.par.externaltox = tox_path. Real TD
        # parameters have a descriptor that intercepts and stores into .val,
        # but our FakePar doesn't — direct assignment just replaces it with
        # the raw string. Both behaviors yield equality with the path str.
        assert str(comp.par.externaltox) == str(tox_file)
        # enableexternaltox got assigned True — same replacement semantics
        assert bool(comp.par.enableexternaltox) is True
        # project.save called once with target + saveExternalToxs=False
        assert len(fake_project.save_calls) == 1
        save_target, save_kwargs = fake_project.save_calls[0]
        assert save_target == target_toe
        assert save_kwargs == {"saveExternalToxs": False}


# ---------------------------------------------------------------------------
# Fallbacks — externaltox not set, but project.save still happens
# ---------------------------------------------------------------------------


class TestExternaltoxFallbacks:
    def test_tox_file_missing_skips_externaltox(self, autostart_module, monkeypatch, tmp_path):
        """If .tox doesn't exist on disk, don't set externaltox (would point
        at nothing). project.save still happens — falls back to embedded
        save (the pre-v1.6.6 behavior)."""
        # NOTE: we deliberately don't create the .tox file
        comp = FakeCOMP(has_externaltox=True)
        fake_project = FakeProject()
        install_globals(
            autostart_module, monkeypatch, comp=comp, fake_project=fake_project, install_dir=str(tmp_path)
        )
        installer = make_installer_mock(str(tmp_path))

        result = autostart_module._save_toe_with_externaltox(installer, str(tmp_path / "out.toe"))

        assert result is False
        assert comp.par.externaltox.value == ""  # unchanged
        # project.save still called — degrades to pre-v1.6.6 behavior
        assert len(fake_project.save_calls) == 1
        # Still passes saveExternalToxs=False (harmless when no externaltox set)
        assert fake_project.save_calls[0][1] == {"saveExternalToxs": False}

    def test_no_externaltox_par_skips_set(self, autostart_module, monkeypatch, tmp_path):
        """COMPs without an externaltox parameter (e.g., baseCOMP) — skip
        the param set, still save."""
        td_component_dir = tmp_path / "td_component"
        td_component_dir.mkdir()
        (td_component_dir / "tdpilot.tox").write_bytes(b"fake")

        comp = FakeCOMP(has_externaltox=False, has_enableexternaltox=False)
        fake_project = FakeProject()
        install_globals(
            autostart_module, monkeypatch, comp=comp, fake_project=fake_project, install_dir=str(tmp_path)
        )
        installer = make_installer_mock(str(tmp_path))

        result = autostart_module._save_toe_with_externaltox(installer, str(tmp_path / "out.toe"))

        assert result is False
        assert not hasattr(comp.par, "externaltox")
        assert len(fake_project.save_calls) == 1

    def test_install_dir_failure_skips_externaltox(self, autostart_module, monkeypatch, tmp_path):
        """If installer.install_dir() raises, fall back to plain save."""
        comp = FakeCOMP(has_externaltox=True)
        fake_project = FakeProject()
        install_globals(
            autostart_module, monkeypatch, comp=comp, fake_project=fake_project, install_dir=str(tmp_path)
        )

        installer = MagicMock()
        installer.module.install_dir.side_effect = RuntimeError("install_dir broken")

        result = autostart_module._save_toe_with_externaltox(installer, str(tmp_path / "out.toe"))

        assert result is False
        assert comp.par.externaltox.value == ""  # unchanged
        assert len(fake_project.save_calls) == 1


# ---------------------------------------------------------------------------
# Older TD: project.save doesn't accept saveExternalToxs kwarg
# ---------------------------------------------------------------------------


class TestOlderTDFallback:
    def test_typeerror_on_kwarg_falls_back_to_plain_save(self, autostart_module, monkeypatch, tmp_path):
        """Older TD builds may not support project.save(saveExternalToxs=...).
        We catch TypeError and fall back to save(target) without kwargs."""
        td_component_dir = tmp_path / "td_component"
        td_component_dir.mkdir()
        (td_component_dir / "tdpilot.tox").write_bytes(b"fake")

        comp = FakeCOMP(has_externaltox=True)
        fake_project = FakeProject()
        fake_project.raises_typeerror_on_kwarg = True
        install_globals(
            autostart_module, monkeypatch, comp=comp, fake_project=fake_project, install_dir=str(tmp_path)
        )
        installer = make_installer_mock(str(tmp_path))

        # Should NOT raise — TypeError is caught and fallback save called
        result = autostart_module._save_toe_with_externaltox(installer, str(tmp_path / "out.toe"))

        # externaltox WAS set successfully (param assignment isn't what raised)
        assert result is True
        assert str(comp.par.externaltox) == str(td_component_dir / "tdpilot.tox")
        # save called twice: first with kwargs (failed), then fallback without
        assert len(fake_project.save_calls) == 1  # only the fallback succeeded
        # The fallback call has no kwargs
        assert fake_project.save_calls[0][1] == {}


# ---------------------------------------------------------------------------
# parent() returns None — defensive guard
# ---------------------------------------------------------------------------


class TestNoParent:
    def test_parent_none_falls_back_to_plain_save(self, autostart_module, monkeypatch, tmp_path):
        """If parent() somehow returns None (shouldn't happen — autostart is
        always inside the tdpilot COMP), we fall back to plain save so we
        don't lose the user's data."""
        fake_project = FakeProject()
        # parent() returns None
        monkeypatch.setattr(autostart_module, "parent", lambda: None, raising=False)
        monkeypatch.setattr(autostart_module, "project", fake_project, raising=False)
        installer = make_installer_mock(str(tmp_path))

        result = autostart_module._save_toe_with_externaltox(installer, str(tmp_path / "out.toe"))

        assert result is False
        # Plain save called — no kwargs
        assert len(fake_project.save_calls) == 1
        assert fake_project.save_calls[0][1] == {}
