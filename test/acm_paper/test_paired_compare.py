from __future__ import annotations

import pytest

from experiments.acm_paper.rq1_model_selection.paired_compare import paired_comparison


def _result(name: str, values: list[float], manifest: str = "split.json") -> dict:
    return {
        "model_name": name,
        "split_name": "test",
        "split_manifest_path": manifest,
        "per_image_records": [{"dice": value} for value in values],
    }


def test_paired_difference_and_interval_are_directional():
    report = paired_comparison(
        _result("A", [0.9, 0.8, 0.7]),
        _result("B", [0.8, 0.7, 0.6]),
        bootstrap_repetitions=500,
        seed=7,
    )
    assert report["mean_paired_difference_a_minus_b"] == pytest.approx(0.1)
    assert report["paired_bootstrap_ci_95"]["lower"] == pytest.approx(0.1)
    assert report["paired_bootstrap_ci_95"]["upper"] == pytest.approx(0.1)


def test_mismatched_split_is_rejected():
    with pytest.raises(ValueError, match="split_manifest_path"):
        paired_comparison(_result("A", [0.9], "a.json"), _result("B", [0.8], "b.json"))


def test_identical_records_have_null_result():
    report = paired_comparison(_result("A", [0.7, 0.8]), _result("B", [0.7, 0.8]), bootstrap_repetitions=10)
    assert report["mean_paired_difference_a_minus_b"] == 0.0
    assert report["wilcoxon_signed_rank"]["two_sided_p_value"] == 1.0
