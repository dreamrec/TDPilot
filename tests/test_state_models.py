from td_mcp.models import StateVectorInput, TimescaleStateInput


def test_state_vector_input_defaults():
    model = StateVectorInput()
    assert model.path == "/project1"
    assert model.force_refresh is False


def test_timescale_state_input_defaults():
    model = TimescaleStateInput()
    assert model.bpm_hint is None
    assert model.beats_per_bar == 4


def test_timescale_state_input_validation():
    model = TimescaleStateInput(bpm_hint=128.0, beats_per_bar=3)
    assert model.bpm_hint == 128.0
    assert model.beats_per_bar == 3
