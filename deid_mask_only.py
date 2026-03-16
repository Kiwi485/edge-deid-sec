from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np


Meta = Dict[str, Any]


def _odd(v: int) -> int:
    return v if v % 2 == 1 else v + 1


def _normalize_color_image(image: np.ndarray) -> np.ndarray:
    """Ensure image is a valid 3-channel color image in BGR order."""
    if image is None:
        raise ValueError("image is None")
    if not isinstance(image, np.ndarray):
        raise TypeError("image must be a numpy array")
    if image.size == 0:
        raise ValueError("image is empty")

    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    if image.ndim != 3:
        raise ValueError(f"unsupported image ndim: {image.ndim}")

    channels = image.shape[2]
    if channels == 3:
        return image
    if channels == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

    raise ValueError(f"unsupported image channel count: {channels}")


def _normalize_mask(mask: np.ndarray, image_hw: Tuple[int, int]) -> np.ndarray:
    """Convert mask into a boolean mask aligned with image height/width."""
    if mask is None:
        raise ValueError("mask is None")
    if not isinstance(mask, np.ndarray):
        raise TypeError("mask must be a numpy array")
    if mask.size == 0:
        raise ValueError("mask is empty")

    h, w = image_hw
    if mask.ndim == 3:
        channels = mask.shape[2]
        if channels == 1:
            mask_2d = mask[:, :, 0]
        elif channels == 3:
            mask_2d = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        elif channels == 4:
            mask_2d = cv2.cvtColor(mask, cv2.COLOR_BGRA2GRAY)
        else:
            raise ValueError(f"unsupported mask channel count: {channels}")
    elif mask.ndim == 2:
        mask_2d = mask
    else:
        raise ValueError(f"unsupported mask ndim: {mask.ndim}")

    if mask_2d.shape != (h, w):
        raise ValueError(
            f"mask shape {mask_2d.shape} does not match image shape {(h, w)}"
        )

    if mask_2d.dtype == np.bool_:
        mask_bool = mask_2d
    else:
        mask_float = mask_2d.astype(np.float32)
        max_val = float(mask_float.max())
        min_val = float(mask_float.min())
        if max_val == min_val == 0.0:
            raise ValueError("mask is empty (all zeros)")

        # Support bool / 0-1 / 0-255 style masks.
        if max_val <= 1.0:
            threshold = 0.5 if np.issubdtype(mask_2d.dtype, np.floating) else 0.0
        else:
            threshold = 127.0
        mask_bool = mask_float > threshold

    if not np.any(mask_bool):
        raise ValueError("mask has no foreground pixels")

    return mask_bool


def _largest_component(mask_u8: np.ndarray) -> np.ndarray:
    """Keep only the largest foreground connected component."""
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    if num_labels <= 1:
        return np.zeros_like(mask_u8)

    # Ignore background at index 0.
    largest_idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    largest = np.zeros_like(mask_u8)
    largest[labels == largest_idx] = 255
    return largest


def _remove_small_border_components(mask_u8: np.ndarray, min_area: int) -> np.ndarray:
    """Remove tiny components touching image borders to suppress edge leakage."""
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    if num_labels <= 1:
        return mask_u8

    h, w = mask_u8.shape
    out = np.zeros_like(mask_u8)
    for label in range(1, num_labels):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < min_area:
            continue

        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        bw = int(stats[label, cv2.CC_STAT_WIDTH])
        bh = int(stats[label, cv2.CC_STAT_HEIGHT])
        touches_border = x == 0 or y == 0 or (x + bw) >= w or (y + bh) >= h
        if touches_border and area < (min_area * 3):
            continue

        out[labels == label] = 255
    return out


def _strict_tongue_mask(mask_bool: np.ndarray) -> np.ndarray:
    """Post-process mask to keep only a tighter tongue-shaped region."""
    h, w = mask_bool.shape
    min_dim = max(1, min(h, w))

    mask_u8 = (mask_bool.astype(np.uint8) * 255)
    min_area = max(64, int(h * w * 0.0008))

    bridge_k = _odd(max(3, min(15, int(min_dim * 0.01))))
    smooth_k = _odd(max(3, min(11, int(min_dim * 0.006))))

    bridge_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (bridge_k, bridge_k))
    smooth_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (smooth_k, smooth_k))

    # Opening helps break thin links to lips/chin/skin in imperfect masks.
    opened = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, bridge_kernel, iterations=1)
    candidate = opened if np.any(opened) else mask_u8

    candidate = _remove_small_border_components(candidate, min_area=min_area)
    candidate = _largest_component(candidate)
    if not np.any(candidate):
        raise ValueError("mask postprocess failed: no component left")

    refined = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, smooth_kernel, iterations=1)
    refined = cv2.erode(refined, smooth_kernel, iterations=1)

    contours, _ = cv2.findContours(refined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("mask postprocess failed: contour not found")

    tongue_contour = max(contours, key=cv2.contourArea)
    contour_mask = np.zeros_like(refined)
    cv2.drawContours(contour_mask, [tongue_contour], -1, 255, thickness=-1)

    if not np.any(contour_mask):
        raise ValueError("mask postprocess failed: empty contour mask")

    return contour_mask.astype(bool)


def deid_mask_only(image: np.ndarray, mask: np.ndarray) -> Tuple[Optional[np.ndarray], Meta]:
    """
    Keep only the tongue region selected by `mask` and black out everything else.

    Args:
        image: Original color image as a numpy array.
        mask: Tongue mask as a numpy array. Supports single-channel / 3-channel /
              bool / 0-1 / 0-255 masks.

    Returns:
        deid_img: A color image with the same size as `image`, where only mask
                  region keeps original pixels and all other pixels are black.
                  Returns None if processing fails before a valid fallback can be made.
        meta: Dict containing deid_method, deid_ms, status, error.
    """
    start = time.perf_counter()
    meta: Meta = {
        "deid_method": "mask_only",
        "mask_postprocess": "strict_tongue_v1",
        "deid_ms": 0.0,
        "status": "error",
        "error": "",
    }

    try:
        image_bgr = _normalize_color_image(image)
        mask_bool = _normalize_mask(mask, image_bgr.shape[:2])
        mask_bool = _strict_tongue_mask(mask_bool)

        deid_img = np.zeros_like(image_bgr)
        deid_img[mask_bool] = image_bgr[mask_bool]

        meta["status"] = "ok"
        return deid_img, meta

    except Exception as exc:  # noqa: BLE001
        meta["status"] = "error"
        meta["error"] = str(exc)

        # If image is valid enough, return a black fallback image with same size.
        try:
            image_bgr = _normalize_color_image(image)
            fallback = np.zeros_like(image_bgr)
        except Exception:  # noqa: BLE001
            fallback = None

        return fallback, meta

    finally:
        meta["deid_ms"] = round((time.perf_counter() - start) * 1000.0, 3)


def save_deid_result(
    output_dir: str | Path,
    deid_img: Optional[np.ndarray],
    meta: Meta,
    *,
    merge_existing_meta: bool = True,
) -> None:
    """
    Save deid.png and meta.json.

    If meta.json already exists, its content will be loaded and updated with the
    new deid-related fields.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if deid_img is not None:
        out_path = output_dir / "deid.png"
        ok = cv2.imwrite(str(out_path), deid_img)
        if not ok:
            raise IOError(f"failed to write image: {out_path}")

    meta_path = output_dir / "meta.json"
    payload: Meta = {}
    if merge_existing_meta and meta_path.exists():
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}

    payload.update(
        {
            "deid_method": meta.get("deid_method", "mask_only"),
            "mask_postprocess": meta.get("mask_postprocess", "strict_tongue_v1"),
            "deid_ms": meta.get("deid_ms", 0.0),
            "status": meta.get("status", "error"),
            "error": meta.get("error", ""),
        }
    )

    meta_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_from_paths(
    image_path: str | Path,
    mask_path: str | Path,
    output_dir: str | Path,
) -> Meta:
    """Convenience helper for reading files, running deid, and saving outputs."""
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    mask = cv2.imread(str(mask_path), cv2.IMREAD_UNCHANGED)

    deid_img, meta = deid_mask_only(image, mask)
    save_deid_result(output_dir, deid_img, meta)
    return meta


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Mask-only de-identification")
    parser.add_argument("--image", required=True, help="Path to input color image")
    parser.add_argument("--mask", required=True, help="Path to mask image")
    parser.add_argument("--out", required=True, help="Output directory")
    args = parser.parse_args()

    meta = run_from_paths(args.image, args.mask, args.out)
    print(json.dumps(meta, ensure_ascii=False, indent=2))
