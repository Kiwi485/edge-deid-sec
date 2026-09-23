"""Save Issue 1 dataset examples with full-frame and ROI mask overlays."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


def overlay(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    result = image.copy()
    foreground = mask > 0
    tint = np.zeros_like(result)
    tint[:, :, 2] = 255
    result[foreground] = cv2.addWeighted(result[foreground], 0.55, tint[foreground], 0.45, 0)
    return result


def fit_width(image: np.ndarray, width: int) -> np.ndarray:
    if image.shape[1] == width:
        return image
    scale = width / image.shape[1]
    return cv2.resize(image, (width, max(1, int(image.shape[0] * scale))), interpolation=cv2.INTER_NEAREST)


def visualize(args: argparse.Namespace) -> int:
    root = Path(args.root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with (root / "metadata" / "manifest.csv").open("r", newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    selected = rows if args.image_id is None else [row for row in rows if row["image_id"] == args.image_id]
    if not selected:
        raise ValueError("no matching image_id in manifest")

    for row in selected[: args.limit if args.limit > 0 else None]:
        original_name = Path(row["original_filename"]).name
        stem = Path(original_name).stem
        image = cv2.imread(str(root / "dataset_full" / "images" / original_name))
        mask = cv2.imread(str(root / "dataset_full" / "masks" / f"{stem}.png"), cv2.IMREAD_GRAYSCALE)
        roi_image = cv2.imread(str(root / "dataset_roi" / "images" / original_name))
        roi_mask = cv2.imread(str(root / "dataset_roi" / "masks" / f"{stem}.png"), cv2.IMREAD_GRAYSCALE)
        if any(value is None for value in (image, mask, roi_image, roi_mask)):
            raise FileNotFoundError(f"missing dataset files for image_id={row['image_id']}")

        full_panel = overlay(image, mask)
        roi_panel = overlay(roi_image, roi_mask)
        target_width = max(full_panel.shape[1], roi_panel.shape[1])
        full_panel = fit_width(full_panel, target_width)
        roi_panel = fit_width(roi_panel, target_width)
        label = np.zeros((45, target_width, 3), dtype=np.uint8)
        cv2.putText(label, f"image_id={row['image_id']} split={row['split']} roi={row['roi_method']}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        result = np.vstack([label, full_panel, roi_panel])
        output_path = output_dir / f"{stem}_overlay.jpg"
        if not cv2.imwrite(str(output_path), result):
            raise IOError(f"failed to write {output_path}")
        print(output_path)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Issue 1 dataset output root")
    parser.add_argument("--output-dir", required=True, help="Directory for visualization images")
    parser.add_argument("--image-id", default=None)
    parser.add_argument("--limit", type=int, default=10)
    return visualize(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
