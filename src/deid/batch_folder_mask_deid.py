import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

VALID_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def _largest_component(mask: np.ndarray) -> np.ndarray:
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels <= 1:
        return mask

    best_idx = 1
    best_area = int(stats[1, cv2.CC_STAT_AREA])
    for i in range(2, num_labels):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area > best_area:
            best_idx = i
            best_area = area

    out = np.zeros_like(mask)
    out[labels == best_idx] = 255
    return out


def estimate_tongue_mask(image: np.ndarray) -> np.ndarray:
    """Estimate a tongue mask from a color image using HSV and spatial priors."""
    if image is None or image.size == 0:
        raise ValueError("image is empty")

    h, w = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Broad red/pink ranges for tongue-like regions.
    m1 = cv2.inRange(hsv, (0, 15, 25), (28, 255, 255))
    m2 = cv2.inRange(hsv, (150, 10, 25), (179, 255, 255))
    mask = cv2.bitwise_or(m1, m2)

    # Keep lower-middle region to suppress background and upper-face noise.
    prior = np.zeros((h, w), dtype=np.uint8)
    y1 = int(h * 0.28)
    x1 = int(w * 0.10)
    x2 = int(w * 0.90)
    prior[y1:h, x1:x2] = 255
    mask = cv2.bitwise_and(mask, prior)

    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = _largest_component(mask)

    if int(np.count_nonzero(mask)) < int(0.003 * h * w):
        # Conservative fallback: center-lower ellipse.
        fallback = np.zeros((h, w), dtype=np.uint8)
        center = (w // 2, int(h * 0.63))
        axes = (max(1, int(w * 0.18)), max(1, int(h * 0.16)))
        cv2.ellipse(fallback, center, axes, 0, 0, 360, 255, -1)
        return fallback

    return mask


def apply_mask_only(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    if image.shape[:2] != mask.shape[:2]:
        raise ValueError("mask shape does not match image shape")

    if mask.ndim == 3:
        mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)

    mask_bin = mask > 0
    out = np.zeros_like(image)
    out[mask_bin] = image[mask_bin]
    return out


def _find_mask_for_image(mask_dir: Optional[Path], image_path: Path) -> Optional[Path]:
    if mask_dir is None:
        return None

    stem = image_path.stem
    candidates = [
        mask_dir / f"{stem}.png",
        mask_dir / f"{stem}.jpg",
        mask_dir / f"{stem}.jpeg",
        mask_dir / f"{stem}_mask.png",
        mask_dir / f"{stem}_mask.jpg",
        mask_dir / f"{stem}_mask.jpeg",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _iter_images(image_dir: Path) -> List[Path]:
    paths = [p for p in sorted(image_dir.iterdir()) if p.is_file() and p.suffix.lower() in VALID_EXTS]
    return paths


def run_batch(image_dir: Path, output_dir: Path, mask_dir: Optional[Path], auto_mask: bool) -> Dict[str, int]:
    masks_out = output_dir / "masks"
    deid_out = output_dir / "deid"
    masks_out.mkdir(parents=True, exist_ok=True)
    deid_out.mkdir(parents=True, exist_ok=True)

    images = _iter_images(image_dir)
    ok, err = 0, 0
    rows: List[Dict[str, str]] = []

    for img_path in images:
        status = "ok"
        detail = ""
        try:
            image = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("failed to read image")

            src_mask_path = _find_mask_for_image(mask_dir, img_path)
            if src_mask_path is not None:
                mask = cv2.imread(str(src_mask_path), cv2.IMREAD_UNCHANGED)
                if mask is None:
                    raise ValueError(f"failed to read mask: {src_mask_path.name}")
                if mask.ndim == 3:
                    mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
            else:
                if not auto_mask:
                    raise FileNotFoundError("mask not found and auto-mask disabled")
                mask = estimate_tongue_mask(image)

            deid = apply_mask_only(image, mask)

            out_mask = masks_out / f"{img_path.stem}.png"
            out_deid = deid_out / f"{img_path.stem}.png"
            if not cv2.imwrite(str(out_mask), mask):
                raise IOError("failed to write output mask")
            if not cv2.imwrite(str(out_deid), deid):
                raise IOError("failed to write output deid")

            ok += 1
            rows.append({
                "image": img_path.name,
                "mask": out_mask.name,
                "deid": out_deid.name,
                "status": "ok",
                "detail": "",
            })
        except Exception as e:
            err += 1
            status = "error"
            detail = str(e)
            rows.append({
                "image": img_path.name,
                "mask": "",
                "deid": "",
                "status": status,
                "detail": detail,
            })

    summary = {
        "image_dir": str(image_dir),
        "mask_dir": str(mask_dir) if mask_dir else "",
        "output_dir": str(output_dir),
        "total": len(images),
        "ok": ok,
        "error": err,
    }

    with open(output_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "items": rows}, f, ensure_ascii=False, indent=2)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch generate tongue mask and deid images (mask-only: outside black)."
    )
    parser.add_argument("--image-dir", type=Path, required=True, help="Input image folder")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output folder")
    parser.add_argument("--mask-dir", type=Path, default=None, help="Optional mask folder")
    parser.add_argument(
        "--auto-mask",
        action="store_true",
        help="If set, auto-estimate mask when mask file is missing",
    )
    args = parser.parse_args()

    summary = run_batch(
        image_dir=args.image_dir,
        output_dir=args.output_dir,
        mask_dir=args.mask_dir,
        auto_mask=args.auto_mask,
    )
    print(
        f"batch_folder_mask_deid completed: total={summary['total']}, ok={summary['ok']}, error={summary['error']}"
    )


if __name__ == "__main__":
    main()
