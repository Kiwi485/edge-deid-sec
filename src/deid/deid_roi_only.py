import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/out")
VALID_EXT = (".jpg", ".jpeg", ".png")


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _find_input_image(image_id: str, meta: Dict[str, Any], raw_dir: Path) -> Optional[Path]:
    input_file = meta.get("input_file", "")
    if input_file:
        p = raw_dir / input_file
        if p.exists():
            return p

    for ext in VALID_EXT:
        p = raw_dir / f"{image_id}{ext}"
        if p.exists():
            return p
    return None


def _parse_roi_bbox(roi_bbox: Any, width: int, height: int) -> Tuple[int, int, int, int]:
    if not isinstance(roi_bbox, list) or len(roi_bbox) != 4:
        raise ValueError("missing or invalid roi_bbox")

    x1, y1, x2, y2 = [int(v) for v in roi_bbox]
    x1 = max(0, min(x1, width - 1))
    y1 = max(0, min(y1, height - 1))
    x2 = max(0, min(x2, width))
    y2 = max(0, min(y2, height))

    if x2 <= x1 or y2 <= y1:
        raise ValueError("roi_bbox has no positive area")

    return x1, y1, x2, y2


def apply_roi_only(image: np.ndarray, roi_bbox: Sequence[int], transparent: bool = False) -> np.ndarray:
    """Keep only ROI and black out everything outside ROI."""
    if image is None or image.size == 0:
        raise ValueError("input image is empty")

    height, width = image.shape[:2]
    x1, y1, x2, y2 = _parse_roi_bbox(roi_bbox, width, height)

    if transparent:
        out = np.zeros((height, width, 4), dtype=np.uint8)
        out[y1:y2, x1:x2, :3] = image[y1:y2, x1:x2]
        out[y1:y2, x1:x2, 3] = 255
        return out

    out = np.zeros_like(image)
    out[y1:y2, x1:x2] = image[y1:y2, x1:x2]
    return out


def process_bundle(bundle_dir: Path, raw_dir: Path = RAW_DIR, transparent: bool = False) -> Dict[str, Any]:
    image_id = bundle_dir.name
    meta_path = bundle_dir / "meta.json"
    out_path = bundle_dir / "deid.png"

    meta = _load_json(meta_path)
    if not meta:
        meta = {"image_id": image_id, "input_file": ""}

    timing_ms = meta.get("timing_ms")
    if not isinstance(timing_ms, dict):
        timing_ms = {}

    start = time.perf_counter()
    status = "ok"
    error = ""

    try:
        input_img_path = _find_input_image(image_id, meta, raw_dir)
        if input_img_path is None:
            raise FileNotFoundError("input image not found in data/raw")

        image = cv2.imread(str(input_img_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"failed to read image: {input_img_path.name}")

        roi_bbox = meta.get("roi_bbox")
        deid_img = apply_roi_only(image, roi_bbox, transparent=transparent)

        ok = cv2.imwrite(str(out_path), deid_img)
        if not ok:
            raise IOError("failed to write deid.png")

    except Exception as e:
        status = "error"
        error = str(e)

    deid_ms = (time.perf_counter() - start) * 1000.0
    timing_ms["deid_ms"] = round(float(deid_ms), 3)

    meta["deid_method"] = "roi_only"
    meta["timing_ms"] = timing_ms
    meta["status"] = status
    meta["error"] = error

    _save_json(meta_path, meta)
    return meta


def run_batch(out_dir: Path = OUT_DIR, raw_dir: Path = RAW_DIR, transparent: bool = False) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    if not out_dir.exists():
        return results

    for bundle_dir in sorted([p for p in out_dir.iterdir() if p.is_dir()]):
        results.append(process_bundle(bundle_dir, raw_dir=raw_dir, transparent=transparent))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply ROI-only de-identification to data/out bundles.")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--transparent", action="store_true", help="Save ROI as RGBA with transparent background")
    args = parser.parse_args()

    results = run_batch(out_dir=args.out_dir, raw_dir=args.raw_dir, transparent=args.transparent)
    ok = sum(1 for r in results if r.get("status") == "ok")
    err = len(results) - ok
    print(f"roi_only completed: ok={ok}, error={err}")


if __name__ == "__main__":
    main()
