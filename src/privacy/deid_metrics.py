from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import cv2
import numpy as np


@dataclass(frozen=True)
class PrivacyConfig:
    black_threshold: int = 8
    retain_tolerance: int = 8
    leak_ref: float = 0.02
    weight_leak: float = 0.70
    weight_retain: float = 0.30
    pass_leak_max: float = 0.005
    pass_retain_min: float = 0.98
    pass_risk_max: float = 20.0


def _to_mask_bool(mask: np.ndarray) -> np.ndarray:
    if mask.ndim == 3:
        mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
    return mask > 0


def _safe_ratio(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return float(num) / float(den)


def evaluate_privacy(
    raw_image: np.ndarray,
    deid_image: np.ndarray,
    mask: np.ndarray,
    cfg: PrivacyConfig | None = None,
) -> Dict[str, object]:
    """Compute privacy metrics for one image bundle."""
    cfg = cfg or PrivacyConfig()

    if raw_image is None or deid_image is None or mask is None:
        raise ValueError("raw_image/deid_image/mask must not be None")

    if raw_image.shape[:2] != deid_image.shape[:2]:
        raise ValueError("raw_image and deid_image shape mismatch")
    if raw_image.shape[:2] != mask.shape[:2]:
        raise ValueError("raw_image and mask shape mismatch")

    m = _to_mask_bool(mask)
    bg = ~m

    fg_total = int(np.count_nonzero(m))
    bg_total = int(np.count_nonzero(bg))

    if deid_image.ndim == 2:
        deid_nz = deid_image > cfg.black_threshold
    else:
        deid_nz = np.any(deid_image > cfg.black_threshold, axis=2)

    bg_leak_count = int(np.count_nonzero(deid_nz & bg))
    background_leak_ratio = _safe_ratio(bg_leak_count, bg_total)

    if raw_image.ndim == 2:
        diff = np.abs(raw_image.astype(np.int16) - deid_image.astype(np.int16))
        retain_ok = diff <= cfg.retain_tolerance
    else:
        diff = np.abs(raw_image.astype(np.int16) - deid_image.astype(np.int16))
        retain_ok = np.max(diff, axis=2) <= cfg.retain_tolerance

    fg_retain_count = int(np.count_nonzero(retain_ok & m))
    retention_completeness = _safe_ratio(fg_retain_count, fg_total)

    leak_norm = min(1.0, background_leak_ratio / max(cfg.leak_ref, 1e-9))
    retain_loss = 1.0 - retention_completeness
    privacy_risk_score = 100.0 * (
        cfg.weight_leak * leak_norm + cfg.weight_retain * retain_loss
    )

    issues: List[str] = []
    if fg_total == 0:
        issues.append("mask_empty")
    if background_leak_ratio > cfg.pass_leak_max:
        issues.append("leak_too_high")
    if retention_completeness < cfg.pass_retain_min:
        issues.append("retention_too_low")
    if privacy_risk_score > cfg.pass_risk_max:
        issues.append("risk_too_high")

    privacy_pass = len(issues) == 0

    return {
        "privacy_pass": privacy_pass,
        "background_leak_ratio": float(background_leak_ratio),
        "retention_completeness": float(retention_completeness),
        "privacy_risk_score": float(privacy_risk_score),
        "privacy_issues": issues,
        "pixels": {
            "foreground_total": fg_total,
            "background_total": bg_total,
            "background_leak_count": bg_leak_count,
            "foreground_retained_count": fg_retain_count,
        },
        "thresholds": {
            "black_threshold": cfg.black_threshold,
            "retain_tolerance": cfg.retain_tolerance,
            "pass_leak_max": cfg.pass_leak_max,
            "pass_retain_min": cfg.pass_retain_min,
            "pass_risk_max": cfg.pass_risk_max,
            "leak_ref": cfg.leak_ref,
        },
    }
