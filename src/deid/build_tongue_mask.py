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


def _largest_component(mask: np.ndarray, cx: float, cy: float) -> np.ndarray:
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels <= 1:
        return mask

    best = 0
    best_score = -1.0
    for i in range(1, num_labels):
        x, y, w, h, area = stats[i]
        if area <= 0:
            continue
        ccx, ccy = centroids[i]
        d = ((ccx - cx) ** 2 + (ccy - cy) ** 2) ** 0.5
        # Prefer bigger region and region close to tongue center.
        score = float(area) - 2.0 * d
        if score > best_score:
            best_score = score
            best = i

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
    color_mask = cv2.bitwise_or(m1, m2)

    roi_only = np.zeros((h, w), dtype=np.uint8)
    roi_only[y1:y2, x1:x2] = 255
    color_mask = cv2.bitwise_and(color_mask, roi_only)

    # Keep the lower-major part of ROI to avoid lips/nostril regions.
    lower_prior = np.zeros((h, w), dtype=np.uint8)
    py = y1 + int(0.15 * rh)
    lower_prior[py:y2, x1:x2] = 255
    merged = cv2.bitwise_and(color_mask, lower_prior)

    if int(np.count_nonzero(merged)) < int(0.01 * rw * rh):
        # Fallback if color segmentation is too weak.
        merged = lower_prior

    kernel = np.ones((5, 5), np.uint8)
    merged = cv2.morphologyEx(merged, cv2.MORPH_OPEN, kernel)
    merged = cv2.morphologyEx(merged, cv2.MORPH_CLOSE, kernel)

    cx = x1 + rw / 2.0
    cy = y1 + rh * 0.65
    merged = _largest_component(merged, cx, cy)

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
