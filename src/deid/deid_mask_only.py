import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def _load_mask(mask_path: Path) -> np.ndarray:
    if not mask_path.exists():
        raise FileNotFoundError("missing mask.png")

    mask = cv2.imread(str(mask_path), cv2.IMREAD_UNCHANGED)
    if mask is None:
        raise ValueError("failed to read mask.png")

    if mask.ndim == 3:
        # Allow 3-channel masks by collapsing to single channel.
        mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
    elif mask.ndim != 2:
        raise ValueError("invalid mask format: expected single-channel image")

    # Support both 0/1 and 0/255 conventions by treating all non-zero values as foreground.
    return (mask > 0)


def _normalize_mask(mask: np.ndarray) -> np.ndarray:
    if mask is None or mask.size == 0:
        raise ValueError("mask is empty")

    if mask.ndim == 3:
        if mask.shape[2] == 1:
            mask = mask[:, :, 0]
        elif mask.shape[2] == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        else:
            raise ValueError("invalid mask format: unsupported channel count")
    elif mask.ndim != 2:
        raise ValueError("invalid mask format: expected 2D or 3D array")

    # Accept bool / uint8(0/1/255) / numeric masks.
    return (mask > 0)


def apply_mask_only(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    if image is None or image.size == 0:
        raise ValueError("input image is empty")
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("input image must be a color image (3 channels)")

    mask_bin = _normalize_mask(mask)
    if image.shape[:2] != mask_bin.shape[:2]:
        raise ValueError("mask size does not match input image")

    out = np.zeros_like(image)
    out[mask_bin] = image[mask_bin]
    return out


def _ensure_timing_ms(meta: Dict[str, Any]) -> Dict[str, float]:
    existing = meta.get("timing_ms")
    timing_ms: Dict[str, float] = {
        "roi_ms": 0.0,
        "seg_ms": 0.0,
        "feat_ms": 0.0,
        "deid_ms": 0.0,
        "total_ms": 0.0,
    }
    if isinstance(existing, dict):
        for k in timing_ms:
            v = existing.get(k)
            if isinstance(v, (int, float)):
                timing_ms[k] = float(v)
    return timing_ms


def process_bundle(bundle_dir: Path, raw_dir: Path = RAW_DIR) -> Dict[str, Any]:
    image_id = bundle_dir.name
    meta_path = bundle_dir / "meta.json"
    mask_path = bundle_dir / "mask.png"
    roi_path = bundle_dir / "roi.png"
    out_path = bundle_dir / "deid.png"

    meta = _load_json(meta_path)
    if not meta:
        meta = {"image_id": image_id, "input_file": ""}

    timing_ms = _ensure_timing_ms(meta)

    start = time.perf_counter()
    status = "ok"
    error = ""

    try:
        input_img_path = _find_input_image(image_id, meta, raw_dir)
        image = None

        if input_img_path is not None:
            image = cv2.imread(str(input_img_path), cv2.IMREAD_COLOR)

        # Fallback to roi.png if raw input is unavailable.
        if image is None and roi_path.exists():
            image = cv2.imread(str(roi_path), cv2.IMREAD_COLOR)

        if image is None:
            raise FileNotFoundError("input image not found in data/raw and roi.png is unavailable")

        mask = _load_mask(mask_path)
        deid_img = apply_mask_only(image, mask)

        ok = cv2.imwrite(str(out_path), deid_img)
        if not ok:
            raise IOError("failed to write deid.png")

    except Exception as e:
        status = "error"
        error = str(e)

    deid_ms = (time.perf_counter() - start) * 1000.0
    timing_ms["deid_ms"] = round(float(deid_ms), 3)

    meta["deid_method"] = "mask_only"
    meta["timing_ms"] = timing_ms
    meta["status"] = status
    meta["error"] = error

    _save_json(meta_path, meta)
    return meta


def run_batch(out_dir: Path = OUT_DIR, raw_dir: Path = RAW_DIR) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    if not out_dir.exists():
        return results

    for bundle_dir in sorted([p for p in out_dir.iterdir() if p.is_dir()]):
        results.append(process_bundle(bundle_dir, raw_dir=raw_dir))
    return results


def process_single(image_path: Path, mask_path: Path, output_path: Path) -> None:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"failed to read image: {image_path}")

    mask = _load_mask(mask_path)
    deid_img = apply_mask_only(image, mask)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(output_path), deid_img)
    if not ok:
        raise IOError(f"failed to write output: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply mask-only de-identification (tongue pixels only, outside set to black)."
    )
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--image", type=Path, default=None, help="Input color image path for single-image mode")
    parser.add_argument("--mask", type=Path, default=None, help="Binary/single-channel mask path for single-image mode")
    parser.add_argument("--output", type=Path, default=None, help="Output deid image path for single-image mode")
    args = parser.parse_args()

    single_mode = args.image is not None or args.mask is not None or args.output is not None
    if single_mode:
        if args.image is None or args.mask is None or args.output is None:
            parser.error("single-image mode requires --image, --mask, and --output together")

        process_single(args.image, args.mask, args.output)
        print(f"mask_only single completed: output={args.output}")
        return

    results = run_batch(out_dir=args.out_dir, raw_dir=args.raw_dir)
    ok = sum(1 for r in results if r.get("status") == "ok")
    err = len(results) - ok
    print(f"mask_only completed: ok={ok}, error={err}")


if __name__ == "__main__":
    main()
