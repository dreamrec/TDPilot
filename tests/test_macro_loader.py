import json

from td_mcp.macros.engine import MacroEngine
from td_mcp.macros.loader import load_user_templates


class FakeTDClient:
    async def request(self, endpoint, body=None):
        return {"success": True}


def test_load_user_templates_from_json(tmp_path):
    template = {
        "name": "custom_chain",
        "description": "User template",
        "nodes": [
            {"node_type": "noiseTOP", "name": "noise"},
            {"node_type": "nullTOP", "name": "out", "dx": 220},
        ],
        "connections": [
            {"source": "noise", "target": "out"},
        ],
        "param_schema": {
            "amp": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0},
        },
        "param_targets": {
            "amp": [{"node": "noise", "param": "amplitude", "mode": "value"}],
        },
        "entry_node": "noise",
        "exit_node": "out",
    }

    (tmp_path / "custom.json").write_text(json.dumps(template), encoding="utf-8")

    loaded, warnings = load_user_templates(tmp_path)

    assert warnings == []
    assert "custom_chain" in loaded
    assert loaded["custom_chain"].entry_node == "noise"


def test_macro_engine_includes_user_templates(tmp_path):
    template = {
        "name": "user_post",
        "description": "User post chain",
        "nodes": [
            {"node_type": "levelTOP", "name": "grade"},
            {"node_type": "nullTOP", "name": "out", "dx": 220},
        ],
        "connections": [{"source": "grade", "target": "out"}],
    }
    (tmp_path / "user_post.json").write_text(json.dumps(template), encoding="utf-8")

    engine = MacroEngine(td_client=FakeTDClient(), user_template_dir=str(tmp_path))
    summary = engine.list_macros()

    macros = {item["name"]: item for item in summary["macros"]}
    assert "user_post" in macros
    assert macros["user_post"]["source"] == "user"
