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
    saved = module.handle_project_lifecycle(
        {"action": "save", "path": "/tmp/show.toe", "save_external_toxs": True}
    )

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


# ─────────────────────────────────────────────────────────────
# handle_analyze_frame structural and functional tests
# ─────────────────────────────────────────────────────────────

import inspect
import sys as _sys

import numpy as _np


class _FakeTOP:
    isTOP = True
    isCHOP = False
    isSOP = False
    isDAT = False
    isCOMP = False
    isMAT = False

    def __init__(self, w=16, h=16, channels=3, fill=0.5):
        self.path = "/project1/null1"
        self.type = "nullTOP"
        self.width = w
        self.height = h
        self._channels = channels
        self._fill = fill

    def numpyArray(self):
        return _np.full((self.height, self.width, self._channels), self._fill, dtype=_np.float32)


class _FakeNotTOP:
    isTOP = False
    isCHOP = True
    type = "waveCHOP"
    path = "/project1/wave1"


def test_handle_analyze_frame_function_exists():
    """handle_analyze_frame must exist and accept a body dict."""
    module = _load_callbacks_module()
    assert hasattr(module, "handle_analyze_frame"), "handle_analyze_frame not found in callbacks module"
    sig = inspect.signature(module.handle_analyze_frame)
    params = list(sig.parameters.keys())
    assert "body" in params, "handle_analyze_frame must accept 'body' parameter"


def test_handle_analyze_frame_registered_in_route_table():
    """'/api/analyze_frame' must appear in the route table source."""
    source = MODULE_PATH.read_text()
    assert "'/api/analyze_frame'" in source or '"/api/analyze_frame"' in source, (
        "'/api/analyze_frame' not found in route table"
    )
    assert "handle_analyze_frame" in source


def test_handle_analyze_frame_missing_path():
    module = _load_callbacks_module()
    result = module.handle_analyze_frame({})
    assert "error" in result
    assert "path" in result["error"].lower()


def test_handle_analyze_frame_node_not_found():
    module = _load_callbacks_module()
    module.op = lambda path: None
    result = module.handle_analyze_frame({"path": "/does/not/exist"})
    assert "error" in result
    assert "not found" in result["error"].lower()


def test_handle_analyze_frame_non_top_node():
    module = _load_callbacks_module()
    fake = _FakeNotTOP()
    module.op = lambda path: fake if path == fake.path else None
    result = module.handle_analyze_frame({"path": fake.path})
    assert "error" in result
    assert "TOP" in result["error"]


def test_handle_analyze_frame_luminance_mode():
    module = _load_callbacks_module()
    # Inject numpy so the guard finds it
    module.sys = _sys
    top = _FakeTOP(w=8, h=8, channels=3, fill=0.5)
    module.op = lambda path: top if path == top.path else None
    result = module.handle_analyze_frame({"path": top.path, "modes": ["luminance"]})
    assert "error" not in result, "Got error: {}".format(result.get("error"))
    assert result["resolution"] == [8, 8]
    assert "luminance" in result["modes"]
    lum = result["modes"]["luminance"]
    assert "mean" in lum
    # Fill=0.5 across all channels: luminance ≈ 0.5
    assert abs(lum["mean"] - 0.5) < 0.01


def test_handle_analyze_frame_histogram_mode():
    module = _load_callbacks_module()
    module.sys = _sys
    top = _FakeTOP(w=4, h=4, channels=3, fill=0.75)
    module.op = lambda path: top if path == top.path else None
    result = module.handle_analyze_frame({"path": top.path, "modes": ["histogram"]})
    assert "error" not in result, "Got error: {}".format(result.get("error"))
    hist = result["modes"]["histogram"]
    assert hist["bins"] == 16
    assert "r" in hist["channels"]
    assert "g" in hist["channels"]
    assert "b" in hist["channels"]


def test_handle_analyze_frame_alpha_coverage_with_rgba():
    module = _load_callbacks_module()
    module.sys = _sys
    top = _FakeTOP(w=4, h=4, channels=4, fill=1.0)
    module.op = lambda path: top if path == top.path else None
    result = module.handle_analyze_frame({"path": top.path, "modes": ["alpha_coverage"]})
    assert "error" not in result
    ac = result["modes"]["alpha_coverage"]
    assert "mean_alpha" in ac
    assert abs(ac["mean_alpha"] - 1.0) < 0.01
    assert abs(ac["opaque_fraction"] - 1.0) < 0.01


def test_handle_analyze_frame_alpha_coverage_no_alpha_channel():
    module = _load_callbacks_module()
    module.sys = _sys
    top = _FakeTOP(w=4, h=4, channels=3, fill=0.5)
    module.op = lambda path: top if path == top.path else None
    result = module.handle_analyze_frame({"path": top.path, "modes": ["alpha_coverage"]})
    assert "error" not in result
    ac = result["modes"]["alpha_coverage"]
    assert "error" in ac


def test_handle_analyze_frame_roi_diff_missing_params():
    module = _load_callbacks_module()
    module.sys = _sys
    top = _FakeTOP(w=8, h=8, channels=3, fill=0.5)
    module.op = lambda path: top if path == top.path else None
    result = module.handle_analyze_frame({"path": top.path, "modes": ["roi_diff"]})
    assert "error" not in result
    rd = result["modes"]["roi_diff"]
    assert "error" in rd


def test_handle_analyze_frame_unknown_mode_returns_error_in_modes():
    module = _load_callbacks_module()
    module.sys = _sys
    top = _FakeTOP(w=4, h=4, channels=3, fill=0.5)
    module.op = lambda path: top if path == top.path else None
    result = module.handle_analyze_frame({"path": top.path, "modes": ["totally_unknown_mode"]})
    assert "error" not in result
    assert "error" in result["modes"]["totally_unknown_mode"]
