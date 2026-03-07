from td_mcp.tool_registry import _compute_timescale_from_timeline


def test_compute_timescale_contains_multi_scale_fields():
    timescale = _compute_timescale_from_timeline(
        {"seconds": 16.0, "fps": 60.0, "frame": 960},
        bpm=120.0,
        beats_per_bar=4,
    )

    assert "section_phase_32bar" in timescale
    assert "arc_phase_128bar" in timescale
    assert "seconds_to_next_phrase_8bar" in timescale
    assert "arc_stage" in timescale


def test_compute_timescale_default_bpm():
    """Should work with explicit BPM values."""
    timescale = _compute_timescale_from_timeline(
        {"seconds": 8.0, "fps": 30.0, "frame": 240},
        bpm=120.0,
        beats_per_bar=4,
    )
    assert "beat_phase" in timescale
    assert "bar_phase" in timescale
