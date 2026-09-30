"""
feature_extractor.py — 256 維舌頭特徵提取

輸入：
  image_bgr : np.ndarray  — 原始 BGR 影像（任意尺寸）
  mask      : np.ndarray  — 二值遮罩（0/255），與 image_bgr 同尺寸

輸出：
  np.ndarray shape (256,) float32

特徵佈局（共 256 維）：
  [  0– 47]  HSV 顏色直方圖（H×16 + S×16 + V×16）
  [ 48– 95]  RGB 顏色統計（各 channel mean/std/p25/p50/p75/skew × 3ch → 18 → pad to 48）
  [ 96–143]  形狀特徵（面積比、長寬比、circularity、solidity、extent、hu_moments×7）→ 12 → pad to 48
    [144–239]  LBP 紋理直方圖（96 維）
    [240–255]  Masked GLCM（4 方向 × 4 指標）
"""

import cv2
import numpy as np
from typing import Optional
from skimage.feature import graycomatrix, graycoprops


FEATURE_VERSION = "v2_glcm"
GLCM_LEVELS = 32
GLCM_ANGLES = (0.0, np.pi / 4, np.pi / 2, 3 * np.pi / 4)
GLCM_PROPERTIES = ("contrast", "dissimilarity", "homogeneity", "energy")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _crop_to_bbox(image_bgr: np.ndarray, mask: np.ndarray):
    """Crop image+mask to the tight bbox of mask>0 to avoid wasting work on background.

    Returns (cropped_bgr, cropped_mask_u8, mask_bool) or (None, None, None) on empty mask.
    """
    mask_u8 = (mask > 0).astype(np.uint8)
    if mask_u8.sum() == 0:
        return None, None, None

    ys, xs = np.where(mask_u8 > 0)
    y0, y1 = ys.min(), ys.max() + 1
    x0, x1 = xs.min(), xs.max() + 1
    crop_img = image_bgr[y0:y1, x0:x1]
    crop_mask = mask_u8[y0:y1, x0:x1]
    return crop_img.copy(), crop_mask, crop_mask.astype(bool)


def _hsv_histogram(crop_bgr: np.ndarray, crop_mask: np.ndarray, bins: int = 16) -> np.ndarray:
    """HSV histogram via cv2.calcHist (C++) — 3 × bins dims."""
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    ranges = [(0, 180), (0, 256), (0, 256)]
    feats = []
    for ch, (lo, hi) in enumerate(ranges):
        hist = cv2.calcHist([hsv], [ch], crop_mask, [bins], [lo, hi])
        hist = hist.flatten().astype(np.float32)
        s = hist.sum()
        if s > 0:
            hist /= s
        feats.append(hist)
    return np.concatenate(feats)  # 48 dims


def _rgb_stats(crop_bgr: np.ndarray, mask_bool: np.ndarray) -> np.ndarray:
    """Per-channel RGB stats: mean, std, p25, p50, p75, skew → 6×3=18, padded to 48."""
    rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    feats = np.zeros(18, dtype=np.float32)
    for ch in range(3):
        vals = rgb[:, :, ch][mask_bool]
        if vals.size == 0:
            continue
        vals = vals.astype(np.float32)
        mean = vals.mean()
        std = vals.std()
        q = np.quantile(vals, [0.25, 0.50, 0.75])
        skew = ((vals - mean) ** 3).mean() / (std ** 3 + 1e-6)
        base = ch * 6
        feats[base:base + 6] = [
            mean / 255.0, std / 255.0,
            q[0] / 255.0, q[1] / 255.0, q[2] / 255.0,
            float(skew),
        ]
    return np.pad(feats, (0, 48 - len(feats)))   # pad to 48


def _shape_features(mask: np.ndarray) -> np.ndarray:
    """Shape features from mask contour — 12 dims, padded to 48."""
    mask_u8 = (mask > 0).astype(np.uint8) * 255
    total_pixels = float(mask_u8.size)
    tongue_pixels = float((mask_u8 > 0).sum())
    area_ratio = tongue_pixels / max(1.0, total_pixels)

    contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return np.zeros(48, dtype=np.float32)

    cnt = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(cnt))
    perimeter = float(cv2.arcLength(cnt, True))
    x, y, bw, bh = cv2.boundingRect(cnt)

    circularity = (4 * np.pi * area / (perimeter ** 2 + 1e-6))
    aspect_ratio = float(bw) / float(max(1, bh))
    extent = area / float(max(1, bw * bh))

    hull = cv2.convexHull(cnt)
    hull_area = float(cv2.contourArea(hull))
    solidity = area / max(1.0, hull_area)

    # Hu moments (7 dims)
    moments = cv2.moments(cnt)
    hu = cv2.HuMoments(moments).flatten()  # (7,)
    # log-scale Hu moments (standard practice)
    hu = np.sign(hu) * np.log10(np.abs(hu) + 1e-10)

    feats = np.array([
        area_ratio,
        aspect_ratio,
        min(circularity, 1.0),
        solidity,
        extent,
        *hu,  # 7 dims
    ], dtype=np.float32)  # 12 dims total

    return np.pad(feats, (0, 48 - len(feats)))  # pad to 48


def _lbp_histogram(crop_bgr: np.ndarray, mask_bool: np.ndarray, bins: int = 96) -> np.ndarray:
    """8-neighbour LBP-like texture histogram over the cropped tongue region."""
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)

    offsets = [(-1, -1), (-1, 0), (-1, 1),
               (0,  -1),          (0,  1),
               (1,  -1), (1,  0), (1,  1)]

    h, w = gray.shape
    lbp = np.zeros((h, w), dtype=np.uint8)
    for bit, (dy, dx) in enumerate(offsets):
        shifted = np.roll(np.roll(gray, dy, axis=0), dx, axis=1)
        lbp |= ((gray >= shifted).astype(np.uint8) << bit)

    vals = lbp[mask_bool]
    hist, _ = np.histogram(vals, bins=bins, range=(0, 256))
    hist = hist.astype(np.float32)
    s = hist.sum()
    if s > 0:
        hist /= s
    return hist


def _glcm_features(crop_bgr: np.ndarray, mask_bool: np.ndarray) -> np.ndarray:
    """Exclude sentinel level zero so both endpoints of every pair are in the mask."""
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    quantized = (gray.astype(np.uint16) * GLCM_LEVELS // 256 + 1).astype(np.uint8)
    quantized[~mask_bool] = 0
    matrices = graycomatrix(
        quantized,
        distances=[1],
        angles=GLCM_ANGLES,
        levels=GLCM_LEVELS + 1,
        symmetric=True,
        normed=False,
    )[1:, 1:, :, :]
    has_pairs = matrices.sum(axis=(0, 1))[0] > 0
    features = np.column_stack([
        graycoprops(matrices, prop)[0] for prop in GLCM_PROPERTIES
    ])
    features[:, 0] /= (GLCM_LEVELS - 1) ** 2
    features[:, 1] /= GLCM_LEVELS - 1
    features[~has_pairs] = 0.0
    return features.ravel().astype(np.float32)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_features(image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Extract 256-dim tongue feature vector.

    Parameters
    ----------
    image_bgr : np.ndarray  BGR image, same size as mask
    mask      : np.ndarray  binary mask (0/255), HxW uint8

    Returns
    -------
    np.ndarray shape (256,) float32
    """
    if image_bgr is None or mask is None:
        return np.zeros(256, dtype=np.float32)

    # Ensure mask matches image size
    if image_bgr.shape[:2] != mask.shape[:2]:
        mask = cv2.resize(mask, (image_bgr.shape[1], image_bgr.shape[0]),
                          interpolation=cv2.INTER_NEAREST)

    # Shape features need the full-image mask (area_ratio is wrt full image).
    shape_feat = _shape_features(mask)                             # 48

    # Color/texture features only need the tight tongue crop.
    crop_bgr, crop_mask, mask_bool = _crop_to_bbox(image_bgr, mask)
    if crop_bgr is None:
        return np.concatenate([np.zeros(48 + 48, dtype=np.float32),
                               shape_feat,
                               np.zeros(112, dtype=np.float32)])

    hsv_feat = _hsv_histogram(crop_bgr, crop_mask, bins=16)        # 48
    rgb_feat = _rgb_stats(crop_bgr, mask_bool)                     # 48
    lbp_feat = _lbp_histogram(crop_bgr, mask_bool, bins=96)
    glcm_feat = _glcm_features(crop_bgr, mask_bool)

    feat = np.concatenate([hsv_feat, rgb_feat, shape_feat, lbp_feat, glcm_feat])
    assert feat.shape == (256,), f"Feature dim mismatch: {feat.shape}"

    # Clip to finite values (safety)
    feat = np.nan_to_num(feat, nan=0.0, posinf=1.0, neginf=-1.0)
    return feat.astype(np.float32)
