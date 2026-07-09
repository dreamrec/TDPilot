"""npm installer Textport-snippet smoke test.

``npx tdpilot install`` prints a Textport snippet the user must paste into
TouchDesigner for one-time setup. Before v2.1.0 the printed snippet called
``compile(c, "setup", "exec")`` WITHOUT ``exec()`` — it compiled the setup
script and threw the code object away, so the npx / Claude Desktop
first-install funnel dead-ended with nothing installed. It also created an
empty ``tdpilot_autostart`` executeDAT that nothing reads, and interpolated
OS-native paths into Python string literals (backslash escapes break the
snippet on Windows).

These tests pin the snippet's load-bearing properties as printed source so a
refactor of install.js cannot silently regress the funnel again.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INSTALL_JS = REPO / "npm" / "install.js"


def _source() -> str:
    return INSTALL_JS.read_text(encoding="utf-8")


def test_snippet_actually_executes_the_setup_script():
    src = _source()
    assert "exec(compile(" in src, (
        "install.js must print an exec(compile(...)) Textport snippet — "
        "compile() alone discards the code object and installs nothing"
    )
    # The historical broken form must not come back.
    assert 'compile(c, "setup", "exec")' not in src


def test_snippet_reads_with_utf8_encoding():
    # TD's Textport open() defaults to the system locale (ASCII on macOS);
    # setup files contain non-ASCII (em-dashes) and fail without this.
    assert 'encoding="utf-8"' in _source()


def test_snippet_has_no_dead_autostart_dat():
    # The empty tdpilot_autostart executeDAT was ritual: nothing reads it.
    # Autostart comes from /local/mcp_server installed by setup_mcp_in_td.py.
    assert "tdpilot_autostart" not in _source()


def test_snippet_paths_are_forward_slashed_for_python_literals():
    # Windows: join() produces backslashes, which are escape sequences inside
    # the printed Python string literals. install.js must normalize.
    assert 'replace(/\\\\/g, "/")' in _source()
