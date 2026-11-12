import math

import pytest

from td_mcp.brain.live_smoke import _collect_performance_summary


class Samples:
    def __init__(self, rows):
        self.rows = iter(rows)

    async def request(self, endpoint, body):
        assert endpoint == "cooking"
        return next(self.rows)


def payload(frame, cook_abs, cook_local, cook_ms=2.0):
    return {
        "frame": frame,
        "nodes": [
            {"path": "/owned/out", "cookTime": cook_ms, "cookFrame": cook_local, "cookAbsFrame": cook_abs}
        ],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("local_frames", [(590, 20, 50), (20, 20, 20), (590, 100, 70)])
async def test_absolute_cook_clock_survives_wrap_full_loop_and_backward_seek(local_frames):
    rows = [payload(frame, frame, local) for frame, local in zip((1000, 1030, 1060), local_frames)]
    result = await _collect_performance_summary(
        Samples(rows), target_root="/owned", sample_interval_s=0, steady_samples=2
    )
    assert result["ok"] is True
    assert result["steady_samples_with_metrics"] == 2
    assert result["frames_advanced"] == 60


@pytest.mark.asyncio
async def test_stale_absolute_clock_cannot_be_overridden_by_local_frame_changes():
    rows = [payload(frame, 900, local) for frame, local in zip((1000, 1030, 1060), (1, 2, 3))]
    result = await _collect_performance_summary(
        Samples(rows), target_root="/owned", sample_interval_s=0, steady_samples=2
    )
    assert result["ok"] is False
    assert result["status"] == "missing_metrics"


@pytest.mark.asyncio
@pytest.mark.parametrize("cook_abs", [20, 5000, math.nan, math.inf, True, -1])
async def test_absolute_cook_must_belong_to_the_current_sampling_interval(cook_abs):
    rows = [payload(1000, 10, 10), payload(1030, cook_abs, 20)]
    result = await _collect_performance_summary(
        Samples(rows), target_root="/owned", sample_interval_s=0, steady_samples=1
    )
    assert result["ok"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("cook_ms", [math.nan, math.inf, -1, True])
async def test_invalid_cook_duration_is_not_a_passing_measurement(cook_ms):
    rows = [payload(1000, 1000, 10), payload(1030, 1030, 20, cook_ms)]
    result = await _collect_performance_summary(
        Samples(rows), target_root="/owned", sample_interval_s=0, steady_samples=1
    )
    assert result["ok"] is False
    assert result["status"] == "missing_metrics"
