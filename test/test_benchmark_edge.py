import pytest

from src.benchmark_edge import summarize_latencies


def test_summarize_latencies_reports_mean_spread_percentiles_and_fps():
    result = summarize_latencies([10.0, 20.0, 30.0])

    assert result["n"] == 3
    assert result["mean_ms"] == pytest.approx(20.0)
    assert result["stddev_ms"] == pytest.approx(8.1649658)
    assert result["median_ms"] == pytest.approx(20.0)
    assert result["p95_ms"] == pytest.approx(29.0)
    assert result["fps_from_mean"] == pytest.approx(50.0)


def test_summarize_latencies_rejects_empty_input():
    with pytest.raises(ValueError, match="empty"):
        summarize_latencies([])
