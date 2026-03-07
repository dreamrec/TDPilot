from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "td_component" / "mcp_webserver_callbacks.py"


def _load_callbacks_module():
    spec = importlib.util.spec_from_file_location("td_cb_ext_test", str(MODULE_PATH))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeVec:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z


class _FakeBounds:
    def __init__(self):
        self.min = _FakeVec(-1.0, -2.0, -3.0)
        self.max = _FakeVec(4.0, 5.0, 6.0)
        self.center = _FakeVec(1.5, 1.5, 1.5)
        self.size = _FakeVec(5.0, 7.0, 9.0)


class _FakePOP:
    isPOP = True

    def __init__(self):
        self.path = "/project1/particles1"
        self.pointAttributes = ["P: 3 <class 'float'>", "PartAge: 1 <class 'float'>"]
        self.pointAttributesChanged = ["P: 3 <class 'float'>"]
        self.primAttributes = []
        self.primAttributesChanged = []
        self.vertAttributes = []
        self.vertAttributesChanged = []
        self.dimension = "[128]"
        self.maxVertsPerLineStrip = 0

    def numPoints(self, delayed=False, max=False):
        return 128 if max else 96

    def numPrims(self, delayed=False, max=False, primType=None):
        return 128 if max else 96

    def numVerts(self, delayed=False, max=False, lineStrips=False):
        return 128 if max else 96

    def computeBounds(self, display=False, render=False, delayed=False):
        return _FakeBounds()

    def points(self, attributeName, startIndex=0, count=-1, delayed=False):
        if attributeName == "P":
            return [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
        if attributeName == "PartAge":
            return [0.1, 0.2]
        return []


class _FakeUndo:
    def __init__(self):
        self.state = True
        self.globalState = True
        self.undoStack = ["initial"]
        self.redoStack = []
        self.calls = []

    def undo(self):
        self.calls.append("undo")

    def redo(self):
        self.calls.append("redo")

    def startBlock(self, name, enable=True):
        self.calls.append(("startBlock", name, enable))

    def endBlock(self):
        self.calls.append("endBlock")

    def clear(self):
        self.calls.append("clear")


class _FakeUI:
    def __init__(self):
        self.undo = _FakeUndo()


class _FakeProject:
    def __init__(self):
        self.name = "demo.toe"
        self.folder = "/tmp"
        self.saveVersion = "2025"
        self.saveBuild = "32280"
        self.modified = []
        self.saved = None
        self.loaded = None

    def save(self, path=None, saveExternalToxs=False):
        self.saved = (path, saveExternalToxs)
        return True

    def load(self, path):
        self.loaded = path


class _FakePar:
    def __init__(self, name):
        self.name = name
        self.default = None
        self.val = None
        self.min = None
        self.max = None
        self.normMin = None
        self.normMax = None
        self.clampMin = None
        self.clampMax = None
        self.menuNames = []
        self.menuLabels = []

    def __str__(self):
        return self.name


class _FakePage:
    def __init__(self, name):
        self.name = name

    def appendFloat(self, name, **kwargs):
        size = kwargs.get("size", 1)
        return [_FakePar(f"{name}{index + 1}") for index in range(size)]

    def appendRGB(self, name, **kwargs):
        return [_FakePar(f"{name}{suffix}") for suffix in ("r", "g", "b")]


class _FakeCOMP:
    isCOMP = True

    def __init__(self):
        self.customPages = []
        self.pages = []

    def appendCustomPage(self, name):
        page = _FakePage(name)
        self.customPages.append(page)
        self.pages.append(page)
        return page


def test_serialize_exec_result_preserves_structure():
    module = _load_callbacks_module()
    payload = module._serialize_exec_result({"points": [(1, 2, 3)], "ok": True})

    assert payload["result"]["points"] == [[1, 2, 3]]
    assert payload["result"]["ok"] is True
    assert payload["result_is_structured"] is True


def test_handle_project_lifecycle_status_and_save():
    module = _load_callbacks_module()
    module.project = _FakeProject()
    module.ui = _FakeUI()

    status = module.handle_project_lifecycle({"action": "status"})
    saved = module.handle_project_lifecycle({"action": "save", "path": "/tmp/show.toe", "save_external_toxs": True})

    assert status["success"] is True
    assert status["project"]["name"] == "demo.toe"
    assert saved["success"] is True
    assert saved["path"] == "/tmp/show.toe"
    assert module.project.saved == ("/tmp/show.toe", True)


def test_handle_custom_parameters_creates_page_and_defaults():
    module = _load_callbacks_module()
    comp = _FakeCOMP()
    module.op = lambda path: comp if path == "/project1/base1" else None

    payload = module.handle_custom_parameters(
        {
            "path": "/project1/base1",
            "page": "Controls",
            "params": [
                {"kind": "float", "name": "gain", "size": 2, "default": [0.25, 0.5], "min": 0.0, "max": 1.0},
                {"kind": "rgb", "name": "tint", "default": [1.0, 0.5, 0.25]},
            ],
        }
    )

    assert payload["success"] is True
    assert payload["page_created"] is True
    assert payload["count"] == 2
    assert payload["parameters"][0]["member_count"] == 2
    assert payload["parameters"][1]["member_count"] == 3


def test_handle_pop_inspect_returns_summary_and_samples():
    module = _load_callbacks_module()
    pop = _FakePOP()
    module.op = lambda path: pop if path == pop.path else None

    payload = module.handle_pop_inspect({"path": pop.path, "count": 4})

    assert payload["family"] == "POP"
    assert payload["summary"]["numPoints"] == 96
    assert payload["attributes"]["point"][0]["name"] == "P"
    assert "P" in payload["samples"]["points"]
    assert payload["samples"]["points"]["P"]["values"][0] == [1.0, 2.0, 3.0]
