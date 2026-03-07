from td_mcp.models import TemporalAnalysisInput
from td_mcp.tool_registry import _classify_temporal_character


def test_temporal_analysis_input_defaults():
    model = TemporalAnalysisInput()
    assert model.path == "/project1"
    assert model.observation_window == 3.0
    assert model.sample_rate == 10.0


def test_classify_temporal_character_static():
    samples = [
        {"fps": 60.0, "event_rate": 0.0, "issues_count": 0, "heavy_nodes_count": 0},
        {"fps": 60.1, "event_rate": 0.1, "issues_count": 0, "heavy_nodes_count": 0},
        {"fps": 59.9, "event_rate": 0.0, "issues_count": 0, "heavy_nodes_count": 0},
    ]
    result = _classify_temporal_character(samples)
    assert result["overall_character"] in {"static", "slowly_evolving"}


def test_classify_temporal_character_chaotic():
    samples = [
        {"fps": 20.0, "event_rate": 12.0, "issues_count": 2, "heavy_nodes_count": 7},
        {"fps": 18.0, "event_rate": 9.0, "issues_count": 3, "heavy_nodes_count": 8},
        {"fps": 22.0, "event_rate": 11.0, "issues_count": 1, "heavy_nodes_count": 6},
    ]
    result = _classify_temporal_character(samples)
    assert result["overall_character"] == "chaotic"
