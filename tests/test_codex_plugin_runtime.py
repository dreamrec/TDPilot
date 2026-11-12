from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_PATH = ROOT / "plugins/tdpilot/scripts/launch_runtime.py"
launcher = ModuleType("codex_runtime")
launcher.__file__ = str(LAUNCHER_PATH)
exec(compile(LAUNCHER_PATH.read_text(encoding="utf-8"), "<plugin-launcher-test>", "exec"), launcher.__dict__)


def runtime(tmp_path, *, name="tdpilot", version="2.5.0"):
    root = tmp_path / "managed"
    (root / "src/td_mcp").mkdir(parents=True)
    (root / "src/td_mcp/server.py").write_text("")
    (root / "uv.lock").write_text("")
    (root / "pyproject.toml").write_text(f'[project]\nname="{name}"\nversion="{version}"\n')
    return root


def test_resolves_managed_pointer_without_using_path_executable(tmp_path, monkeypatch):
    root = runtime(tmp_path)
    (tmp_path / ".tdpilot_path").write_text(str(root))
    monkeypatch.setenv("PATH", "/unrelated/bin")
    assert launcher.resolve_runtime(tmp_path, None, "2.5.0") == root


@pytest.mark.parametrize("name,version", [("other", "2.5.0"), ("tdpilot", "2.4.1")])
def test_rejects_foreign_or_older_runtime(tmp_path, name, version):
    root = runtime(tmp_path, name=name, version=version)
    with pytest.raises(RuntimeError):
        launcher.resolve_runtime(tmp_path, str(root), "2.5.0")


def test_incomplete_override_does_not_fall_back_to_other_installation(tmp_path):
    root = runtime(tmp_path)
    (tmp_path / ".tdpilot_path").write_text(str(root))
    with pytest.raises(FileNotFoundError):
        launcher.resolve_runtime(tmp_path, str(tmp_path / "missing"), "2.5.0")
