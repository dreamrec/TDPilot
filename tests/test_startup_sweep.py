"""Tests for v1.6.5 startup-script comprehensive COMP sweep.

Background — the bug v1.6.5 fixes:
   Pre-v1.6.5 ``td_component/tdpilot_startup.py:_load_tox_fast`` only
   knew about ``/local/mcp_server`` (the legacy v1.3-era name). The
   v1.5.6+ build script saves the COMP as ``tdpilot``, and users
   commonly drag the .tox into the visible network panel which lands
   it at ``/project1/tdpilot``. When ``project.save`` then bakes that
   into the autoload .toe, every TD launch restored the stale
   ``/project1/tdpilot``, and the Startup script's loadTox into
   ``/local`` either silently failed (port-9981 collision with the
   already-bound /project1 instance) or got clobbered by the .toe's
   own /local restore. Net result: ``td_get_capabilities`` reported
   the stale baked .toe's ``API_VERSION`` forever.

The fix has two parts:

1. ``_find_existing_tdpilot_comps()`` returns ALL matches across
   ``/local`` and ``/project1`` for BOTH names (``tdpilot`` and the
   legacy ``mcp_server``). So nothing escapes the sweep regardless of
   how the user installed.

2. ``_load_tox_fast()`` destroys every match found, then loads into
   the SAME parent the previous COMP was at (preserves user UI
   position). Defaults to ``/local`` when nothing was found.

Tests use a fake ``op()`` injected via ``monkeypatch.setattr`` on the
imported startup module — same pattern as test_autopin.py uses for
mocking subprocess. Loading the module is gated by
``TDPILOT_STARTUP_SKIP=1`` (added in v1.6.4) so the bottom-of-file
``_startup()`` call doesn't fire on import.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
STARTUP_PATH = REPO_ROOT / "td_component" / "tdpilot_startup.py"


@pytest.fixture(scope="module")
def startup_module():
    """Load tdpilot_startup.py without firing _startup() at import time.

    Module-scoped because the import is expensive (compiles a 270-line file
    + runs all its module-level code). All tests in this file share the
    same module, but each test installs its own fake_op via monkeypatch
    so cross-test pollution can't happen.
    """
    os.environ["TDPILOT_STARTUP_SKIP"] = "1"
    try:
        spec = importlib.util.spec_from_file_location("tdpilot_startup_sweep_test", STARTUP_PATH)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        os.environ.pop("TDPILOT_STARTUP_SKIP", None)
        sys.modules.pop("tdpilot_startup_sweep_test", None)


# ---------------------------------------------------------------------------
# Fake TD COMP tree
# ---------------------------------------------------------------------------


class FakeCOMP:
    """Minimal stand-in for a TD COMP — enough surface for the sweep functions.

    Tracks ``destroyed`` and ``loadTox_calls`` so tests can assert what
    happened. Returns child COMPs by name via ``.op(name)``, mimicking TD's
    parent-child operator addressing.
    """

    def __init__(self, path: str, children: dict[str, FakeCOMP] | None = None):
        self.path = path
        self.isCOMP = True
        self._children: dict[str, FakeCOMP] = children or {}
        self.destroyed = False
        self.loadTox_calls: list[str] = []

    def op(self, name: str) -> FakeCOMP | None:
        return self._children.get(name)

    def destroy(self) -> None:
        self.destroyed = True
        # Detach from parent's children dict so subsequent op() lookups miss.
        # The actual TD destroy() removes the node from the tree; mirror that.
        # We don't have a back-pointer to parent so we mutate via a closure
        # set up in the fixture builder.
        if hasattr(self, "_on_destroy"):
            self._on_destroy()

    def loadTox(self, tox_path: str) -> FakeCOMP:
        """Mimic TD's loadTox: creates a child COMP whose name comes from
        the saved .tox. Pre-v1.5.6 .tox files saved name "mcp_server";
        v1.5.6+ saves "tdpilot". Tests can override the loaded name by
        setting self._loadtox_name; default is "tdpilot" (the current
        builder's output)."""
        self.loadTox_calls.append(tox_path)
        loaded_name = getattr(self, "_loadtox_name", "tdpilot")
        new_comp = FakeCOMP(f"{self.path}/{loaded_name}", {})
        self._children[loaded_name] = new_comp
        return new_comp


def make_world(layout: dict[str, list[str]]) -> tuple[FakeCOMP, dict[str, FakeCOMP]]:
    """Build a fake project tree from a {parent_path: [child_names]} spec.

    Returns ``(root, all_comps)`` where ``all_comps`` maps full paths to
    FakeCOMP instances so tests can inspect ``.destroyed`` after the sweep.
    """
    all_comps: dict[str, FakeCOMP] = {}

    # Always include the canonical parent paths the sweep looks at.
    for pp in ("/local", "/project1"):
        if pp not in all_comps:
            all_comps[pp] = FakeCOMP(pp, {})

    for parent_path, child_names in layout.items():
        if parent_path not in all_comps:
            all_comps[parent_path] = FakeCOMP(parent_path, {})
        parent = all_comps[parent_path]
        for child_name in child_names:
            child_path = f"{parent_path}/{child_name}"
            child = FakeCOMP(child_path, {})
            # Wire detach-on-destroy so subsequent op(name) lookups miss
            child._on_destroy = lambda p=parent, n=child_name: p._children.pop(n, None)
            parent._children[child_name] = child
            all_comps[child_path] = child

    root = FakeCOMP("/", {})
    return root, all_comps


def install_fake_op(monkeypatch, startup_module, all_comps: dict[str, FakeCOMP]):
    """Replace startup_module.op with a function that resolves paths
    against our fake world.

    ``raising=False`` is required because ``op`` is a TD-injected builtin
    that doesn't exist as a module attribute outside TD — production code
    accesses it via the global lookup chain (locals → globals → builtins).
    Without ``raising=False``, monkeypatch refuses to set an attribute that
    didn't exist before. With it, we inject ``op`` into the module's globals
    where the production functions will find it via normal name resolution.
    """

    def fake_op(path: str):
        return all_comps.get(path)

    monkeypatch.setattr(startup_module, "op", fake_op, raising=False)


# ---------------------------------------------------------------------------
# _find_existing_tdpilot_comps
# ---------------------------------------------------------------------------


class TestFindExisting:
    def test_empty_world_returns_empty(self, startup_module, monkeypatch):
        """No tdpilot/mcp_server anywhere → empty list."""
        _, world = make_world({})
        install_fake_op(monkeypatch, startup_module, world)
        assert startup_module._find_existing_tdpilot_comps() == []

    def test_finds_tdpilot_at_local(self, startup_module, monkeypatch):
        _, world = make_world({"/local": ["tdpilot"]})
        install_fake_op(monkeypatch, startup_module, world)
        result = startup_module._find_existing_tdpilot_comps()
        assert result == [("/local", "/local/tdpilot")]

    def test_finds_tdpilot_at_project1(self, startup_module, monkeypatch):
        """The bug case: user dragged .tox into /project1."""
        _, world = make_world({"/project1": ["tdpilot"]})
        install_fake_op(monkeypatch, startup_module, world)
        result = startup_module._find_existing_tdpilot_comps()
        assert result == [("/project1", "/project1/tdpilot")]

    def test_finds_legacy_mcp_server_name(self, startup_module, monkeypatch):
        """Legacy v1.3-era name still detected."""
        _, world = make_world({"/local": ["mcp_server"]})
        install_fake_op(monkeypatch, startup_module, world)
        result = startup_module._find_existing_tdpilot_comps()
        assert result == [("/local", "/local/mcp_server")]

    def test_finds_all_when_multiple_exist(self, startup_module, monkeypatch):
        """If both /local/tdpilot AND /project1/tdpilot exist (e.g.
        Startup script ran but user-saved .toe also has the COMP),
        both are reported. Order is /local first (per _SCAN_PARENTS)."""
        _, world = make_world({"/local": ["tdpilot"], "/project1": ["tdpilot"]})
        install_fake_op(monkeypatch, startup_module, world)
        result = startup_module._find_existing_tdpilot_comps()
        assert result == [
            ("/local", "/local/tdpilot"),
            ("/project1", "/project1/tdpilot"),
        ]

    def test_finds_both_names_at_same_parent(self, startup_module, monkeypatch):
        """Edge case: very old install with mcp_server AND new install
        with tdpilot side-by-side. Both should be found so the sweep
        cleans up both."""
        _, world = make_world({"/local": ["tdpilot", "mcp_server"]})
        install_fake_op(monkeypatch, startup_module, world)
        result = startup_module._find_existing_tdpilot_comps()
        # _COMP_NAMES order is ("tdpilot", "mcp_server") so tdpilot listed first
        assert result == [
            ("/local", "/local/tdpilot"),
            ("/local", "/local/mcp_server"),
        ]


# ---------------------------------------------------------------------------
# _load_tox_fast — the canonical entry point
# ---------------------------------------------------------------------------


class TestLoadToxFast:
    def test_empty_world_loads_into_local(self, startup_module, monkeypatch, capsys):
        """Fresh install: nothing to destroy, load into /local."""
        _, world = make_world({})
        install_fake_op(monkeypatch, startup_module, world)

        ok = startup_module._load_tox_fast("/path/to/tdpilot.tox")

        assert ok is True
        # /local should have received exactly one loadTox call
        assert world["/local"].loadTox_calls == ["/path/to/tdpilot.tox"]
        # /project1 was not touched
        assert world["/project1"].loadTox_calls == []
        out = capsys.readouterr().out
        assert "loaded into /local/tdpilot" in out

    def test_existing_at_local_destroyed_and_reloaded_at_local(self, startup_module, monkeypatch, capsys):
        """Stale /local/tdpilot → destroy + reload at /local."""
        _, world = make_world({"/local": ["tdpilot"]})
        install_fake_op(monkeypatch, startup_module, world)

        old_comp = world["/local/tdpilot"]
        ok = startup_module._load_tox_fast("/path/to/tdpilot.tox")

        assert ok is True
        assert old_comp.destroyed is True
        assert world["/local"].loadTox_calls == ["/path/to/tdpilot.tox"]
        assert "destroying stale /local/tdpilot" in capsys.readouterr().out

    def test_existing_at_project1_destroyed_and_reloaded_at_project1(
        self, startup_module, monkeypatch, capsys
    ):
        """THE BUG CASE: stale /project1/tdpilot baked in .toe.
        v1.6.5 must destroy it AND reload at /project1 (preserve UI)."""
        _, world = make_world({"/project1": ["tdpilot"]})
        install_fake_op(monkeypatch, startup_module, world)

        stale_baked_comp = world["/project1/tdpilot"]
        ok = startup_module._load_tox_fast("/path/to/tdpilot.tox")

        assert ok is True
        # The stale baked COMP is gone
        assert stale_baked_comp.destroyed is True
        # The new COMP loaded at /project1 (NOT /local) — UI position preserved
        assert world["/project1"].loadTox_calls == ["/path/to/tdpilot.tox"]
        assert world["/local"].loadTox_calls == []
        out = capsys.readouterr().out
        assert "destroying stale /project1/tdpilot" in out
        assert "loaded into /project1/tdpilot" in out

    def test_both_locations_destroyed_local_wins(self, startup_module, monkeypatch, capsys):
        """Both /local/tdpilot AND /project1/tdpilot: both destroyed,
        new load goes to /local (first in _SCAN_PARENTS, the canonical
        location)."""
        _, world = make_world({"/local": ["tdpilot"], "/project1": ["tdpilot"]})
        install_fake_op(monkeypatch, startup_module, world)

        local_old = world["/local/tdpilot"]
        project_old = world["/project1/tdpilot"]
        ok = startup_module._load_tox_fast("/path/to/tdpilot.tox")

        assert ok is True
        assert local_old.destroyed is True
        assert project_old.destroyed is True
        # Loaded into /local (preferred when both existed)
        assert world["/local"].loadTox_calls == ["/path/to/tdpilot.tox"]
        assert world["/project1"].loadTox_calls == []

    def test_legacy_mcp_server_name_at_project1_also_destroyed(self, startup_module, monkeypatch):
        """If a really old install has /project1/mcp_server (legacy
        name), the sweep must destroy it too — NOT just /project1/tdpilot."""
        _, world = make_world({"/project1": ["mcp_server"]})
        install_fake_op(monkeypatch, startup_module, world)

        legacy_comp = world["/project1/mcp_server"]
        ok = startup_module._load_tox_fast("/path/to/tdpilot.tox")

        assert ok is True
        assert legacy_comp.destroyed is True
        # New load goes to /project1 because that's where the legacy was
        assert world["/project1"].loadTox_calls == ["/path/to/tdpilot.tox"]

    def test_loadtox_returns_none_returns_false(self, startup_module, monkeypatch):
        """If TD's loadTox fails (returns None), _load_tox_fast must
        return False so the caller falls back to _rebuild_from_source."""
        _, world = make_world({})
        install_fake_op(monkeypatch, startup_module, world)

        # Sabotage loadTox to simulate failure
        world["/local"].loadTox = lambda _path: None  # type: ignore[method-assign]

        assert startup_module._load_tox_fast("/path/to/tdpilot.tox") is False

    def test_loadtox_raising_returns_false(self, startup_module, monkeypatch, capsys):
        """If TD's loadTox raises, _load_tox_fast must catch it and
        return False (TD startup must never crash)."""
        _, world = make_world({})
        install_fake_op(monkeypatch, startup_module, world)

        def raising_loadtox(_path):
            raise RuntimeError("simulated TD loadTox failure")

        world["/local"].loadTox = raising_loadtox  # type: ignore[method-assign]

        assert startup_module._load_tox_fast("/path/to/tdpilot.tox") is False
        out = capsys.readouterr().out
        assert "loadTox failed" in out
        assert "simulated TD loadTox failure" in out

    def test_destroy_failure_does_not_block_load(self, startup_module, monkeypatch, capsys):
        """If destroy() raises on one stale COMP, the sweep must log it
        and continue with the load — partial cleanup is better than no
        cleanup at all."""
        _, world = make_world({"/local": ["tdpilot"]})
        install_fake_op(monkeypatch, startup_module, world)

        def raising_destroy():
            raise RuntimeError("locked node")

        world["/local/tdpilot"].destroy = raising_destroy  # type: ignore[method-assign]

        ok = startup_module._load_tox_fast("/path/to/tdpilot.tox")

        # Load still attempted — and succeeds because our FakeCOMP.loadTox
        # is permissive about pre-existing children (real TD would auto-rename).
        assert ok is True
        out = capsys.readouterr().out
        assert "failed to destroy /local/tdpilot" in out


# ---------------------------------------------------------------------------
# Backward-compat: _destroy_zombie_mcp_servers shim
# ---------------------------------------------------------------------------


class TestZombieShim:
    def test_zombie_shim_destroys_outside_exclude(self, startup_module, monkeypatch, capsys):
        """The pre-v1.6.5 shim still works: passes exclude_path, sweep
        destroys everything except that path."""
        _, world = make_world({"/local": ["tdpilot"], "/project1": ["tdpilot"]})
        install_fake_op(monkeypatch, startup_module, world)

        # Exclude /local/tdpilot — only /project1/tdpilot should die
        startup_module._destroy_zombie_mcp_servers(exclude_path="/local/tdpilot")

        assert world["/local/tdpilot"].destroyed is False
        assert world["/project1/tdpilot"].destroyed is True
        assert "destroying zombie /project1/tdpilot" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# API_VERSION lockstep — defense-in-depth for the v1.6.4 bug class
# ---------------------------------------------------------------------------


class TestAPIVersionLockstep:
    """v1.6.5 changed the policy: API_VERSION must equal __version__.

    The pre-v1.6.5 stance was that they were intentionally decoupled, but
    in practice (a) the panel renderer reads API_VERSION directly so users
    expect them to match, and (b) v1.6.4 silently shipped with API_VERSION
    still at "1.6.3" because no gate caught the missing Edit. This test +
    the scripts/check_versions.py extension mean any future API_VERSION
    drift fails CI.
    """

    def test_api_version_matches_package_version(self):
        import re

        callbacks = (REPO_ROOT / "td_component" / "mcp_webserver_callbacks.py").read_text(encoding="utf-8")
        api_match = re.search(r'API_VERSION\s*=\s*"([^"]+)"', callbacks)
        assert api_match is not None, "API_VERSION not found in callbacks"
        api_version = api_match.group(1)

        init = (REPO_ROOT / "src" / "td_mcp" / "__init__.py").read_text(encoding="utf-8")
        ver_match = re.search(r'__version__\s*=\s*"([^"]+)"', init)
        assert ver_match is not None, "__version__ not found in __init__.py"
        package_version = ver_match.group(1)

        assert api_version == package_version, (
            f"API_VERSION ({api_version}) must equal "
            f"src/td_mcp/__init__.__version__ ({package_version}). "
            f"Bump both together; see comment in scripts/check_versions.py."
        )
