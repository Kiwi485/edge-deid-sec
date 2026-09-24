"""
test_metrics.py — Unit Tests for ACM Paper RQ1 Metrics Module
==============================================================
Tests for:
    experiments/acm_paper/rq1_model_selection/metrics.py

Covers all required test cases from the issue specification:
  1.  Perfect prediction
  2.  Complete mismatch
  3.  Empty ground truth AND empty prediction
  4.  Empty ground truth with non-empty prediction (false positive only)
  5.  Mixed batch
  6.  Logits input
  7.  Binary-mask input
  8.  Multi-image accumulation
  9.  Reset behaviour
  10. Bootstrap CI smoke test

Run with:
    pytest test/acm_paper/test_metrics.py -v
    # or from project root:
    python -m pytest test/acm_paper/test_metrics.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import torch

# ---------------------------------------------------------------------------
# Make sure project root is on sys.path so imports work from any CWD
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from experiments.acm_paper.rq1_model_selection.metrics import (
    SegmentationMetricsAccumulator,
    _confusion_counts,
    _metrics_from_counts,
    compute_single_image_metrics,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_binary(h: int = 4, w: int = 4, fill: float = 1.0) -> torch.Tensor:
    """Create a (1, 1, H, W) binary mask filled with `fill`."""
    return torch.full((1, 1, h, w), fill_value=fill)


def _make_logits(h: int = 4, w: int = 4, value: float = 10.0) -> torch.Tensor:
    """Create a (1, 1, H, W) logit tensor.  Large positive → sigmoid ≈ 1."""
    return torch.full((1, 1, h, w), fill_value=value)


# ---------------------------------------------------------------------------
# _confusion_counts
# ---------------------------------------------------------------------------

class TestConfusionCounts:
    def test_all_true_positives(self):
        pred = torch.ones(4, 4)
        gt   = torch.ones(4, 4)
        tp, fp, fn, tn = _confusion_counts(pred, gt)
        assert tp == 16
        assert fp == 0
        assert fn == 0
        assert tn == 0

    def test_all_true_negatives(self):
        pred = torch.zeros(4, 4)
        gt   = torch.zeros(4, 4)
        tp, fp, fn, tn = _confusion_counts(pred, gt)
        assert tp == 0
        assert fp == 0
        assert fn == 0
        assert tn == 16

    def test_all_false_positives(self):
        pred = torch.ones(4, 4)
        gt   = torch.zeros(4, 4)
        tp, fp, fn, tn = _confusion_counts(pred, gt)
        assert tp == 0
        assert fp == 16
        assert fn == 0
        assert tn == 0

    def test_all_false_negatives(self):
        pred = torch.zeros(4, 4)
        gt   = torch.ones(4, 4)
        tp, fp, fn, tn = _confusion_counts(pred, gt)
        assert tp == 0
        assert fp == 0
        assert fn == 16
        assert tn == 0


# ---------------------------------------------------------------------------
# _metrics_from_counts
# ---------------------------------------------------------------------------

class TestMetricsFromCounts:
    def test_perfect(self):
        m = _metrics_from_counts(tp=100, fp=0, fn=0, tn=100)
        assert m["dice"]          == pytest.approx(1.0, abs=1e-5)
        assert m["iou"]           == pytest.approx(1.0, abs=1e-5)
        assert m["precision"]     == pytest.approx(1.0, abs=1e-5)
        assert m["recall"]        == pytest.approx(1.0, abs=1e-5)
        assert m["pixel_accuracy"] == pytest.approx(1.0, abs=1e-5)

    def test_zero_counts_no_nan(self):
        """Empty masks should not produce NaN."""
        m = _metrics_from_counts(tp=0, fp=0, fn=0, tn=0)
        for v in m.values():
            assert not (v != v), f"NaN detected: {m}"  # NaN != NaN

    def test_empty_gt_fp_only(self):
        """FP only: precision=0, recall=1 (numerically), dice≈0."""
        m = _metrics_from_counts(tp=0, fp=50, fn=0, tn=50)
        assert m["recall"]    == pytest.approx(1.0, abs=1e-3)   # TP/(TP+FN) with eps
        assert m["precision"] < 0.1                               # TP/(TP+FP) ≈ 0


# ---------------------------------------------------------------------------
# Test case 1: Perfect prediction
# ---------------------------------------------------------------------------

class TestPerfectPrediction:
    """SegmentationMetricsAccumulator: perfect binary masks."""

    def test_perfect_binary(self):
        acc = SegmentationMetricsAccumulator(threshold=0.5)
        pred = _make_binary(fill=1.0)
        gt   = _make_binary(fill=1.0)
        acc.update_from_binary(pred, gt)
        r = acc.result()
        assert r["dice"]          == pytest.approx(1.0, abs=1e-5)
        assert r["iou"]           == pytest.approx(1.0, abs=1e-5)
        assert r["precision"]     == pytest.approx(1.0, abs=1e-5)
        assert r["recall"]        == pytest.approx(1.0, abs=1e-5)
        assert r["pixel_accuracy"] == pytest.approx(1.0, abs=1e-5)
        assert r["n_images"] == 1


# ---------------------------------------------------------------------------
# Test case 2: Complete mismatch
# ---------------------------------------------------------------------------

class TestCompleteMismatch:
    """Prediction is the complement of ground truth."""

    def test_complete_mismatch(self):
        acc = SegmentationMetricsAccumulator(threshold=0.5)
        pred = _make_binary(fill=1.0)   # all foreground
        gt   = _make_binary(fill=0.0)   # all background
        acc.update_from_binary(pred, gt)
        r = acc.result()

        # TP=0, FP=16, FN=0, TN=0 → dice≈0
        assert r["tp"] == 0
        assert r["fp"] > 0
        assert r["dice"] < 0.1
        assert r["iou"]  < 0.1


# ---------------------------------------------------------------------------
# Test case 3: Empty ground truth AND empty prediction
# ---------------------------------------------------------------------------

class TestBothEmpty:
    """All-zero GT and all-zero prediction: TN only, no NaN."""

    def test_both_empty(self):
        acc = SegmentationMetricsAccumulator(threshold=0.5)
        pred = _make_binary(fill=0.0)
        gt   = _make_binary(fill=0.0)
        acc.update_from_binary(pred, gt)
        r = acc.result()

        # Should not produce NaN
        for key in ("dice", "iou", "precision", "recall", "pixel_accuracy"):
            assert not np.isnan(r[key]), f"NaN in {key}"
        assert r["tp"] == 0
        assert r["fp"] == 0
        assert r["fn"] == 0
        assert r["tn"] == pytest.approx(16, rel=1e-3)
        assert r["pixel_accuracy"] == pytest.approx(1.0, abs=1e-4)


# ---------------------------------------------------------------------------
# Test case 4: Empty GT with non-empty prediction (FP only)
# ---------------------------------------------------------------------------

class TestEmptyGtNonEmptyPred:
    """GT is all zeros, prediction is all ones — pure false positive."""

    def test_fp_only(self):
        acc = SegmentationMetricsAccumulator(threshold=0.5)
        pred = _make_binary(fill=1.0)
        gt   = _make_binary(fill=0.0)
        acc.update_from_binary(pred, gt)
        r = acc.result()

        assert r["tp"] == 0
        assert r["fp"] == 16
        assert r["fn"] == 0
        assert r["tn"] == 0
        assert not np.isnan(r["dice"])
        assert r["dice"] < 0.05       # near zero
        assert r["pixel_accuracy"] < 0.05  # all wrong


# ---------------------------------------------------------------------------
# Test case 5: Mixed batch
# ---------------------------------------------------------------------------

class TestMixedBatch:
    """Batch of 2: one perfect, one complete mismatch."""

    def test_mixed_batch(self):
        acc = SegmentationMetricsAccumulator(threshold=0.5)

        # Image 1: perfect match
        pred1 = _make_binary(fill=1.0)
        gt1   = _make_binary(fill=1.0)
        acc.update_from_binary(pred1, gt1)

        # Image 2: all FP (pred=1, gt=0)
        pred2 = _make_binary(fill=1.0)
        gt2   = _make_binary(fill=0.0)
        acc.update_from_binary(pred2, gt2)

        r = acc.result()
        assert r["n_images"] == 2

        # Global: TP=16, FP=16, FN=0, TN=0
        assert r["tp"] == 16
        assert r["fp"] == 16
        assert r["fn"] == 0

        # Dice = 2*16 / (2*16 + 16 + 0) ≈ 0.667
        assert 0.5 < r["dice"] < 0.75

        # Per-image mean Dice: avg(1.0, ~0) ≈ 0.5
        assert 0.4 < r["per_image_dice_mean"] < 0.6


# ---------------------------------------------------------------------------
# Test case 6: Logits input
# ---------------------------------------------------------------------------

class TestLogitsInput:
    """update_from_logits applies sigmoid + threshold internally."""

    def test_high_positive_logits_map_to_positive(self):
        acc = SegmentationMetricsAccumulator(threshold=0.5)
        logits = _make_logits(value=10.0)   # sigmoid(10) ≈ 1.0
        gt     = _make_binary(fill=1.0)
        acc.update_from_logits(logits, gt)
        r = acc.result()
        assert r["dice"] == pytest.approx(1.0, abs=1e-4)

    def test_high_negative_logits_map_to_negative(self):
        acc = SegmentationMetricsAccumulator(threshold=0.5)
        logits = _make_logits(value=-10.0)  # sigmoid(-10) ≈ 0.0
        gt     = _make_binary(fill=0.0)
        acc.update_from_logits(logits, gt)
        r = acc.result()
        # All TN
        assert r["tp"] == 0
        assert r["tn"] > 0
        assert r["pixel_accuracy"] == pytest.approx(1.0, abs=1e-4)

    def test_logits_versus_binary_equivalent(self):
        """High-logit and binary-1 predictions should give identical results."""
        acc_logits = SegmentationMetricsAccumulator(threshold=0.5)
        acc_binary = SegmentationMetricsAccumulator(threshold=0.5)
        gt = _make_binary(fill=1.0)

        acc_logits.update_from_logits(_make_logits(value=10.0), gt)
        acc_binary.update_from_binary(_make_binary(fill=1.0),   gt)

        r_l = acc_logits.result()
        r_b = acc_binary.result()
        assert r_l["dice"] == pytest.approx(r_b["dice"], abs=1e-4)


# ---------------------------------------------------------------------------
# Test case 7: Binary-mask input
# ---------------------------------------------------------------------------

class TestBinaryMaskInput:
    """update_from_binary accepts already-thresholded masks."""

    def test_partial_overlap(self):
        """Half of pixels match: known TP, FP, FN, TN counts."""
        acc = SegmentationMetricsAccumulator(threshold=0.5)
        pred = torch.zeros(1, 1, 4, 4)
        gt   = torch.zeros(1, 1, 4, 4)
        # Left half of pred = 1, right half of gt = 1 → no overlap
        pred[0, 0, :, :2] = 1.0   # 8 pixels positive in pred
        gt[0, 0, :, 2:]   = 1.0   # 8 pixels positive in gt
        acc.update_from_binary(pred, gt)
        r = acc.result()
        assert r["tp"] == 0
        assert r["fp"] == 8
        assert r["fn"] == 8
        assert r["tn"] == 0
        assert r["dice"] < 0.05

    def test_exact_half_overlap(self):
        """8 pixels overlap, 4 FP, 4 FN, 0 TN."""
        acc = SegmentationMetricsAccumulator(threshold=0.5)
        pred = torch.zeros(1, 1, 4, 4)
        gt   = torch.zeros(1, 1, 4, 4)
        # pred covers left 3/4; gt covers right 3/4 → overlap = middle 2/4
        pred[0, 0, :, :3] = 1.0   # 12 positive
        gt[0, 0, :, 1:]   = 1.0   # 12 positive; overlap = cols 1,2 = 8 pixels
        acc.update_from_binary(pred, gt)
        r = acc.result()
        assert r["tp"] == pytest.approx(8, rel=1e-3)
        assert r["fp"] == pytest.approx(4, rel=1e-3)  # col 0 in pred but not gt
        assert r["fn"] == pytest.approx(4, rel=1e-3)  # col 3 in gt but not pred


# ---------------------------------------------------------------------------
# Test case 8: Multi-image accumulation
# ---------------------------------------------------------------------------

class TestMultiImageAccumulation:
    def test_counts_add_up(self):
        acc = SegmentationMetricsAccumulator(threshold=0.5)
        for _ in range(5):
            pred = _make_binary(fill=1.0)
            gt   = _make_binary(fill=1.0)
            acc.update_from_binary(pred, gt)
        r = acc.result()
        assert r["n_images"] == 5
        assert r["tp"] == 5 * 16

    def test_per_image_records_length(self):
        acc = SegmentationMetricsAccumulator(threshold=0.5, track_per_image=True)
        for i in range(3):
            acc.update_from_binary(_make_binary(fill=1.0), _make_binary(fill=1.0))
        assert len(acc.per_image_records) == 3

    def test_per_image_mean_std(self):
        """All-perfect images should give mean=1.0, std≈0."""
        acc = SegmentationMetricsAccumulator(threshold=0.5)
        for _ in range(4):
            acc.update_from_binary(_make_binary(fill=1.0), _make_binary(fill=1.0))
        r = acc.result()
        assert r["per_image_dice_mean"] == pytest.approx(1.0, abs=1e-4)
        assert r["per_image_dice_std"]  == pytest.approx(0.0, abs=1e-4)


# ---------------------------------------------------------------------------
# Test case 9: Reset behaviour
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_clears_counts(self):
        acc = SegmentationMetricsAccumulator(threshold=0.5)
        acc.update_from_binary(_make_binary(fill=1.0), _make_binary(fill=1.0))
        assert acc.n_images == 1
        acc.reset()
        assert acc.n_images == 0
        assert acc.per_image_records == []

    def test_result_after_reset_is_safe(self):
        """result() on empty accumulator should not crash."""
        acc = SegmentationMetricsAccumulator(threshold=0.5)
        r = acc.result()
        assert r["n_images"] == 0
        for key in ("dice", "iou", "precision", "recall", "pixel_accuracy"):
            assert not np.isnan(r[key])


# ---------------------------------------------------------------------------
# Test case 10: Bootstrap CI smoke test
# ---------------------------------------------------------------------------

class TestBootstrapCI:
    def test_bootstrap_returns_bounds(self):
        acc = SegmentationMetricsAccumulator(threshold=0.5, track_per_image=True)
        # Feed 20 mixed images
        for i in range(20):
            fill = 1.0 if i % 2 == 0 else 0.0
            acc.update_from_binary(
                _make_binary(fill=fill),
                _make_binary(fill=1.0),
            )
        ci = acc.bootstrap_ci(n_repetitions=200, seed=42)
        for metric in ("dice", "iou", "precision", "recall", "pixel_accuracy"):
            assert metric in ci
            assert ci[metric]["lower"] <= ci[metric]["mean"] <= ci[metric]["upper"]
            assert 0.0 <= ci[metric]["lower"] <= 1.0
            assert 0.0 <= ci[metric]["upper"] <= 1.0

    def test_bootstrap_requires_track_per_image(self):
        acc = SegmentationMetricsAccumulator(threshold=0.5, track_per_image=False)
        acc.update_from_binary(_make_binary(fill=1.0), _make_binary(fill=1.0))
        with pytest.raises(RuntimeError, match="track_per_image"):
            acc.bootstrap_ci(n_repetitions=100)

    def test_bootstrap_requires_images_processed(self):
        acc = SegmentationMetricsAccumulator(threshold=0.5, track_per_image=True)
        with pytest.raises(RuntimeError, match="No images"):
            acc.bootstrap_ci(n_repetitions=100)


# ---------------------------------------------------------------------------
# compute_single_image_metrics standalone function
# ---------------------------------------------------------------------------

class TestComputeSingleImageMetrics:
    def test_logits_path(self):
        logits = torch.full((1, 1, 4, 4), 10.0)  # sigmoid → 1.0
        gt     = torch.ones(1, 1, 4, 4)
        r = compute_single_image_metrics(logits, gt, logits=True)
        assert r["dice"] == pytest.approx(1.0, abs=1e-4)
        assert "tp" in r and r["tp"] == pytest.approx(16, rel=1e-3)

    def test_binary_path(self):
        pred = torch.ones(1, 1, 4, 4)
        gt   = torch.ones(1, 1, 4, 4)
        r = compute_single_image_metrics(pred, gt, logits=False)
        assert r["iou"] == pytest.approx(1.0, abs=1e-4)

    def test_no_nan_on_zero_inputs(self):
        pred = torch.zeros(1, 1, 4, 4)
        gt   = torch.zeros(1, 1, 4, 4)
        r = compute_single_image_metrics(pred, gt, logits=False)
        for v in r.values():
            assert not np.isnan(float(v))


# ---------------------------------------------------------------------------
# Batch shape handling
# ---------------------------------------------------------------------------

class TestBatchShapes:
    """Accumulator handles various input shapes gracefully."""

    def test_bchw_input(self):
        acc = SegmentationMetricsAccumulator()
        acc.update_from_binary(
            torch.ones(2, 1, 8, 8),
            torch.ones(2, 1, 8, 8),
        )
        assert acc.n_images == 2

    def test_bhw_input(self):
        acc = SegmentationMetricsAccumulator()
        acc.update_from_binary(
            torch.ones(2, 8, 8),
            torch.ones(2, 8, 8),
        )
        assert acc.n_images == 2

    def test_hw_input(self):
        """Single image without batch dimension."""
        acc = SegmentationMetricsAccumulator()
        acc.update_from_binary(
            torch.ones(8, 8),
            torch.ones(8, 8),
        )
        assert acc.n_images == 1
