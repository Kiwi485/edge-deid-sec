import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/out")


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _clip_bbox(bbox: List[int], w: int, h: int) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = [int(v) for v in bbox]
    x1 = max(0, min(x1, w - 1))
    y1 = max(0, min(y1, h - 1))
    x2 = max(0, min(x2, w))
    y2 = max(0, min(y2, h))
    if x2 <= x1 or y2 <= y1:
        raise ValueError("roi_bbox has no positive area")
    return x1, y1, x2, y2


def _select_tongue_component(mask: np.ndarray, cx: float, cy: float, roi_area: float) -> np.ndarray:
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels <= 1:
        return mask

    best = -1
    best_score = -1.0
    for i in range(1, num_labels):
        x, y, bw, bh, area = stats[i]
        if area <= 0:
            continue

        # Reject tiny noise and over-large blocks.
        area_ratio = float(area) / max(1.0, roi_area)
        if area_ratio < 0.01 or area_ratio > 0.75:
            continue

        ccx, ccy = centroids[i]
        d = ((ccx - cx) ** 2 + (ccy - cy) ** 2) ** 0.5

        # Tongue region tends to be wider than tall in this ROI setup.
        aspect = float(bw) / float(max(1, bh))
        aspect_score = max(0.0, 1.0 - abs(aspect - 1.5) / 1.5)

        comp = np.zeros_like(mask)
        comp[labels == i] = 255
        contours, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        hull = cv2.convexHull(contour)
        hull_area = float(cv2.contourArea(hull))
        contour_area = float(cv2.contourArea(contour))
        solidity = contour_area / hull_area if hull_area > 1.0 else 0.0

        bbox_area = float(max(1, bw * bh))
        extent = contour_area / bbox_area

        # Weighted score: center proximity + proper size + tongue-like shape.
        size_score = min(1.0, area_ratio / 0.25)
        dist_score = max(0.0, 1.0 - d / (max(1.0, (bw + bh))))
        shape_score = 0.5 * solidity + 0.5 * extent
        score = 0.40 * size_score + 0.25 * dist_score + 0.20 * aspect_score + 0.15 * shape_score
        if score > best_score:
            best_score = score
            best = i

    if best < 0:
        # Fallback to largest foreground component when shape cues fail.
        best = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))

    out = np.zeros_like(mask)
    out[labels == best] = 255
    return out


def build_mask(image: np.ndarray, roi_bbox: List[int]) -> np.ndarray:
    h, w = image.shape[:2]
    x1, y1, x2, y2 = _clip_bbox(roi_bbox, w, h)
    rw, rh = x2 - x1, y2 - y1

    # Fast HSV-based tongue candidate inside ROI.
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    m1 = cv2.inRange(hsv, (0, 20, 35), (25, 255, 255))
    m2 = cv2.inRange(hsv, (150, 15, 35), (179, 255, 255))
    tongue_seed = cv2.bitwise_or(m1, m2)

    roi_only = np.zeros((h, w), dtype=np.uint8)
    roi_only[y1:y2, x1:x2] = 255
    tongue_seed = cv2.bitwise_and(tongue_seed, roi_only)

    # Keep lower-major part of ROI to avoid lips/nostril regions.
    lower_prior = np.zeros((h, w), dtype=np.uint8)
    py = y1 + int(0.22 * rh)
    lower_prior[py:y2, x1:x2] = 255
    tongue_seed = cv2.bitwise_and(tongue_seed, lower_prior)

    # Include tongue coating (lower saturation + medium/high value) near tongue seed.
    coat_raw = cv2.inRange(hsv, (0, 0, 80), (179, 120, 255))
    coat_raw = cv2.bitwise_and(coat_raw, lower_prior)
    coat_raw = cv2.bitwise_and(coat_raw, roi_only)

    # Restrict coating to areas adjacent to tongue seed to avoid skin/lip leakage.
    near_k = max(5, int(min(rw, rh) * 0.07))
    if near_k % 2 == 0:
        near_k += 1
    near_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (near_k, near_k))
    seed_dilated = cv2.dilate(tongue_seed, near_kernel, iterations=1)
    coat_near = cv2.bitwise_and(coat_raw, seed_dilated)

    merged = cv2.bitwise_or(tongue_seed, coat_near)

    # Hard suppress the top band inside ROI where lips are more likely.
    suppress_top = np.zeros((h, w), dtype=np.uint8)
    top_cut = y1 + int(0.16 * rh)
    suppress_top[top_cut:y2, x1:x2] = 255
    merged = cv2.bitwise_and(merged, suppress_top)

    if int(np.count_nonzero(merged)) < int(0.01 * rw * rh):
        # Fallback if color segmentation is too weak: keep center-lower ellipse in ROI.
        merged = np.zeros((h, w), dtype=np.uint8)
        cx = x1 + rw // 2
        cy = y1 + int(rh * 0.62)
        ax = max(1, int(rw * 0.23))
        ay = max(1, int(rh * 0.22))
        cv2.ellipse(merged, (cx, cy), (ax, ay), 0, 0, 360, 255, -1)

    kernel = np.ones((5, 5), np.uint8)
    merged = cv2.morphologyEx(merged, cv2.MORPH_OPEN, kernel)
    merged = cv2.morphologyEx(merged, cv2.MORPH_CLOSE, kernel)

    # Slightly relax contour to cover tongue coating while staying compact.
    relax_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    merged = cv2.dilate(merged, relax_kernel, iterations=1)

    cx = x1 + rw / 2.0
    cy = y1 + rh * 0.65
    merged = _select_tongue_component(merged, cx, cy, roi_area=float(rw * rh))

    if int(np.count_nonzero(merged)) < int(0.005 * h * w):
        # Final fallback: keep the ROI rectangle itself.
        merged = roi_only

    return merged


def process_bundle(bundle_dir: Path, raw_dir: Path) -> bool:
    meta_path = bundle_dir / "meta.json"
    mask_path = bundle_dir / "mask.png"

    meta = _load_json(meta_path)
    if not meta:
        return False

    image_id = meta.get("image_id", bundle_dir.name)
    input_file = meta.get("input_file", f"{image_id}.jpg")
    image_path = raw_dir / input_file

    if not image_path.exists():
        return False

    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img is None:
        return False

    roi_bbox = meta.get("roi_bbox")
    if not isinstance(roi_bbox, list) or len(roi_bbox) != 4:
        return False

    mask = build_mask(img, roi_bbox)
    ok = cv2.imwrite(str(mask_path), mask)
    return bool(ok)


def run_batch(out_dir: Path, raw_dir: Path, prefix: str = "") -> Tuple[int, int]:
    ok = 0
    err = 0

    for bundle_dir in sorted([p for p in out_dir.iterdir() if p.is_dir()]):
        if prefix and not bundle_dir.name.startswith(prefix):
            continue
        if process_bundle(bundle_dir, raw_dir=raw_dir):
            ok += 1
        else:
            err += 1
    return ok, err


def main() -> None:
    parser = argparse.ArgumentParser(description="Build tongue mask.png from roi_bbox for each data/out bundle")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--prefix", type=str, default="")
    args = parser.parse_args()

    ok, err = run_batch(args.out_dir, args.raw_dir, prefix=args.prefix)
    print(f"mask_build completed: ok={ok}, error={err}")


if __name__ == "__main__":
    main()
