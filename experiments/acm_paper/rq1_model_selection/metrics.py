"""
metrics.py — ACM Paper RQ1: Authoritative Binary Segmentation Metrics
======================================================================
This module is the **single source of truth** for all final RQ1 paper metrics.

IMPORTANT
---------
- Training epoch Dice/IoU in ``src/seg/train.py`` are monitoring metrics only.
  They use batch-level averaging and must NOT be used as final paper results.
- Final paper results MUST come from evaluating on the held-out test set
  using :class:`SegmentationMetricsAccumulator` in this module.
- Do NOT use test-set results to select checkpoints or tune thresholds.
- Do NOT duplicate these metric formulas in other files.

Metrics
-------
Global (micro-averaged across the full test set):
  - Dice Coefficient (F1 Score)
  - Intersection over Union (Jaccard Index)
  - Precision
  - Recall
  - Pixel Accuracy
  - TP, FP, FN, TN  (raw pixel-level confusion counts)

Optional per-image statistics:
  - Mean ± Std of each metric across individual test images

Optional statistical inference:
  - 95% paired bootstrap confidence intervals (bootstrapping over per-image
    confusion counts, same images used for all models)

Usage Example
-------------
::

    from experiments.acm_paper.rq1_model_selection.metrics import (
        SegmentationMetricsAccumulator,
    )

    acc = SegmentationMetricsAccumulator(threshold=0.5)
    for images, masks in test_loader:
        with torch.no_grad():
            logits = model(images.to(device))
        acc.update_from_logits(logits.cpu(), masks.cpu())

    results = acc.result()
    print(f"Dice: {results['dice']:.4f}  IoU: {results['iou']:.4f}")

    # Optional: 95% bootstrap CI (requires track_per_image=True, default)
    ci = acc.bootstrap_ci(n_repetitions=1000, seed=42)
    print(f"Dice 95% CI: [{ci['dice']['lower']:.4f}, {ci['dice']['upper']:.4f}]")
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _confusion_counts(
    pred: torch.Tensor,
    gt: torch.Tensor,
) -> Tuple[float, float, float, float]:
    """
    Compute pixel-level TP, FP, FN, TN for a single prediction / GT pair.

    Parameters
    ----------
    pred : torch.Tensor
        Binary prediction (values 0.0 or 1.0), any shape.
    gt : torch.Tensor
        Binary ground truth (values 0.0 or 1.0), same shape as pred.

    Returns
    -------
    (tp, fp, fn, tn) : Tuple[float, float, float, float]
    """
    pred = pred.float().reshape(-1)
    gt = gt.float().reshape(-1)
    tp = float((pred * gt).sum().item())
    fp = float((pred * (1.0 - gt)).sum().item())
    fn = float(((1.0 - pred) * gt).sum().item())
    tn = float(((1.0 - pred) * (1.0 - gt)).sum().item())
    return tp, fp, fn, tn


def _metrics_from_counts(
    tp: float,
    fp: float,
    fn: float,
    tn: float,
    eps: float = 1e-8,
) -> Dict[str, float]:
    """
    Derive Dice, IoU, Precision, Recall, and Pixel Accuracy from raw counts.

    Formulas
    --------
    Dice = 2·TP / (2·TP + FP + FN)
    IoU  = TP  / (TP + FP + FN)
    Precision = TP / (TP + FP)
    Recall    = TP / (TP + FN)
    PixelAcc  = (TP + TN) / (TP + FP + FN + TN)

    The ``eps`` term prevents division-by-zero; it is applied uniformly so
    that empty masks give numerically stable (near-zero or near-one) values
    rather than NaN.

    Parameters
    ----------
    tp, fp, fn, tn : float
        Pixel-level confusion counts.
    eps : float
        Small constant for numerical stability.

    Returns
    -------
    dict with keys: dice, iou, precision, recall, pixel_accuracy
    """
    dice = (2.0 * tp + eps) / (2.0 * tp + fp + fn + eps)
    iou = (tp + eps) / (tp + fp + fn + eps)
    precision = (tp + eps) / (tp + fp + eps)
    recall = (tp + eps) / (tp + fn + eps)
    total = tp + fp + fn + tn
    pixel_accuracy = (tp + tn + eps) / (total + eps)
    return {
        "dice": float(dice),
        "iou": float(iou),
        "precision": float(precision),
        "recall": float(recall),
        "pixel_accuracy": float(pixel_accuracy),
    }


# ---------------------------------------------------------------------------
# Public standalone helper
# ---------------------------------------------------------------------------

def compute_single_image_metrics(
    pred: torch.Tensor,
    gt: torch.Tensor,
    threshold: float = 0.5,
    logits: bool = False,
    eps: float = 1e-8,
) -> Dict[str, float]:
    """
    Compute all metrics for a single image prediction.

    Parameters
    ----------
    pred : torch.Tensor
        Prediction tensor.  If ``logits=True``, raw logits are accepted and
        sigmoid + threshold is applied.  Otherwise must be binary (0/1).
    gt : torch.Tensor
        Binary ground-truth mask (0 or 1), same shape as pred.
    threshold : float
        Decision threshold (default 0.5).
    logits : bool
        If True, apply sigmoid before thresholding.
    eps : float
        Numerical stability constant.

    Returns
    -------
    dict with keys: dice, iou, precision, recall, pixel_accuracy, tp, fp, fn, tn
    """
    with torch.no_grad():
        if logits:
            binary_pred = (torch.sigmoid(pred) >= threshold).float()
        else:
            binary_pred = pred.float()
        tp, fp, fn, tn = _confusion_counts(binary_pred, gt)
    metrics = _metrics_from_counts(tp, fp, fn, tn, eps=eps)
    metrics.update({"tp": tp, "fp": fp, "fn": fn, "tn": tn})
    return metrics


# ---------------------------------------------------------------------------
# Main accumulator
# ---------------------------------------------------------------------------

class SegmentationMetricsAccumulator:
    """
    Accumulates pixel-level confusion counts across an entire dataset and
    computes global (micro-averaged) segmentation metrics.

    Parameters
    ----------
    threshold : float
        Decision threshold applied to sigmoid probabilities (default 0.5).
    track_per_image : bool
        When True (default), record per-image confusion counts.  Required for
        :meth:`bootstrap_ci` and per-image mean/std in :meth:`result`.

    Notes
    -----
    - Global metrics are **micro-averaged**: all pixels are treated equally,
      so larger images contribute more than smaller ones.
    - Use :meth:`update_from_logits` for raw model outputs (e.g. SMP models
      that return raw logits).
    - Use :meth:`update_from_binary` for already-thresholded predictions
      (e.g. after processing YOLO instance masks).
    - Call :meth:`reset` to reuse the same accumulator across multiple runs.

    Examples
    --------
    ::

        acc = SegmentationMetricsAccumulator(threshold=0.5)

        for logits_batch, mask_batch in loader:
            acc.update_from_logits(logits_batch, mask_batch)

        results = acc.result()
    """

    def __init__(
        self,
        threshold: float = 0.5,
        track_per_image: bool = True,
    ) -> None:
        self.threshold = threshold
        self.track_per_image = track_per_image
        self.reset()

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset all accumulated counts and per-image records."""
        self._tp: float = 0.0
        self._fp: float = 0.0
        self._fn: float = 0.0
        self._tn: float = 0.0
        self._n_images: int = 0
        self._per_image_records: List[Dict[str, float]] = []

    # ------------------------------------------------------------------
    # Update methods
    # ------------------------------------------------------------------

    def update_from_logits(
        self,
        logits: torch.Tensor,
        gt: torch.Tensor,
    ) -> None:
        """
        Accept raw model logits and internally apply sigmoid + threshold.

        Parameters
        ----------
        logits : torch.Tensor
            Raw logits, shape (B, 1, H, W) or (B, H, W).  A single image
            without batch dimension is also accepted.
        gt : torch.Tensor
            Ground-truth binary masks (0 or 1 values), same spatial shape.
        """
        with torch.no_grad():
            probs = torch.sigmoid(logits)
            preds = (probs >= self.threshold).float()
        self._update_batch(preds, gt.float())

    def update_from_binary(
        self,
        preds: torch.Tensor,
        gt: torch.Tensor,
    ) -> None:
        """
        Accept already-binarised predictions (values 0 or 1).

        Parameters
        ----------
        preds : torch.Tensor
            Binary predictions (0.0 or 1.0), shape (B, 1, H, W) or (B, H, W).
        gt : torch.Tensor
            Ground-truth binary masks (0 or 1), same shape as preds.
        """
        self._update_batch(preds.float(), gt.float())

    def _update_batch(self, preds: torch.Tensor, gt: torch.Tensor) -> None:
        """Internal: iterate over a batch and accumulate counts per image."""
        # Normalise to 3-D (B, H, W) for uniform processing
        if preds.dim() == 4:
            preds = preds.squeeze(1)  # (B, 1, H, W) → (B, H, W)
        if gt.dim() == 4:
            gt = gt.squeeze(1)

        if preds.dim() == 2:
            preds = preds.unsqueeze(0)
            gt = gt.unsqueeze(0)

        b = preds.shape[0]
        for i in range(b):
            tp, fp, fn, tn = _confusion_counts(preds[i], gt[i])
            self._tp += tp
            self._fp += fp
            self._fn += fn
            self._tn += tn
            self._n_images += 1

            if self.track_per_image:
                img_m = _metrics_from_counts(tp, fp, fn, tn)
                img_m.update({"tp": tp, "fp": fp, "fn": fn, "tn": tn})
                self._per_image_records.append(img_m)

    # ------------------------------------------------------------------
    # Result computation
    # ------------------------------------------------------------------

    def result(self, eps: float = 1e-8) -> Dict[str, float]:
        """
        Compute global micro-averaged metrics from accumulated counts.

        Returns
        -------
        dict
            Keys: ``dice``, ``iou``, ``precision``, ``recall``,
            ``pixel_accuracy``, ``tp``, ``fp``, ``fn``, ``tn``,
            ``n_images``, and (when ``track_per_image=True``) per-image
            mean/std for each metric.
        """
        global_m = _metrics_from_counts(
            self._tp, self._fp, self._fn, self._tn, eps=eps
        )
        out: Dict[str, float] = {
            **global_m,
            "tp": int(self._tp),
            "fp": int(self._fp),
            "fn": int(self._fn),
            "tn": int(self._tn),
            "n_images": self._n_images,
        }

        if self.track_per_image and self._per_image_records:
            for key in ("dice", "iou", "precision", "recall", "pixel_accuracy"):
                vals = [r[key] for r in self._per_image_records]
                arr = np.array(vals, dtype=np.float64)
                out[f"per_image_{key}_mean"] = float(arr.mean())
                out[f"per_image_{key}_std"] = (
                    float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
                )

        return out

    @property
    def per_image_records(self) -> List[Dict[str, float]]:
        """Return a copy of per-image metric records (requires track_per_image=True)."""
        return list(self._per_image_records)

    @property
    def n_images(self) -> int:
        """Number of images processed so far."""
        return self._n_images

    # ------------------------------------------------------------------
    # Bootstrap confidence intervals
    # ------------------------------------------------------------------

    def bootstrap_ci(
        self,
        n_repetitions: int = 1000,
        seed: int = 42,
        confidence: float = 0.95,
        metrics: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """
        Compute bootstrap confidence intervals by resampling per-image counts.

        This is a **paired bootstrap**: each resample draws ``n_images``
        images (with replacement) from the same set, which allows fair
        pairwise comparison across models evaluated on identical test images.

        Parameters
        ----------
        n_repetitions : int
            Number of bootstrap resamples (default 1000).  Use ≥ 1000 for
            reliable 95% CIs; 10 000 for publication-quality results.
        seed : int
            Random seed for reproducibility.
        confidence : float
            Confidence level (default 0.95 → 95% CI).
        metrics : list[str] | None
            Metrics to compute CIs for.  None = all five standard metrics.

        Returns
        -------
        dict mapping metric_name → {"lower": float, "upper": float, "mean": float}

        Raises
        ------
        RuntimeError
            If ``track_per_image`` is False or no images have been processed.

        Notes
        -----
        Statistical significance is NOT claimed unless the method is
        explicitly documented in the paper.
        """
        if not self.track_per_image:
            raise RuntimeError(
                "bootstrap_ci() requires track_per_image=True.  "
                "Re-create the accumulator with track_per_image=True."
            )
        if self._n_images == 0:
            raise RuntimeError(
                "No images have been processed.  Call update_from_logits() or "
                "update_from_binary() first."
            )
        if n_repetitions < 100:
            raise ValueError(
                "n_repetitions should be at least 100 for meaningful CIs."
            )

        if metrics is None:
            metrics = ["dice", "iou", "precision", "recall", "pixel_accuracy"]

        records = self._per_image_records
        n = len(records)
        rng = random.Random(seed)

        alpha = 1.0 - confidence
        lower_pct = alpha / 2.0 * 100.0
        upper_pct = (1.0 - alpha / 2.0) * 100.0

        bootstrap_values: Dict[str, List[float]] = {m: [] for m in metrics}

        for _ in range(n_repetitions):
            indices = [rng.randrange(n) for _ in range(n)]
            tp = sum(records[i]["tp"] for i in indices)
            fp = sum(records[i]["fp"] for i in indices)
            fn = sum(records[i]["fn"] for i in indices)
            tn = sum(records[i]["tn"] for i in indices)
            sample_m = _metrics_from_counts(tp, fp, fn, tn)
            for m in metrics:
                bootstrap_values[m].append(sample_m[m])

        result: Dict[str, Dict[str, float]] = {}
        for m in metrics:
            vals = np.array(bootstrap_values[m])
            result[m] = {
                "lower": float(np.percentile(vals, lower_pct)),
                "upper": float(np.percentile(vals, upper_pct)),
                "mean": float(vals.mean()),
            }

        return result
