"""Validate an Issue 1 full-frame/ROI dataset and its manifest."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2

REQUIRED_FIELDS = {
    "image_id", "original_filename", "image_width", "image_height",
    "roi_x1", "roi_y1", "roi_x2", "roi_y2", "roi_method", "split",
}


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        fields = set(reader.fieldnames or [])
        missing = REQUIRED_FIELDS - fields
        if missing:
            raise ValueError(f"manifest missing fields: {sorted(missing)}")
        return list(reader)


def check(args: argparse.Namespace) -> int:
    root = Path(args.root)
    manifest_path = root / "metadata" / "manifest.csv"
    full_images = root / "dataset_full" / "images"
    full_masks = root / "dataset_full" / "masks"
    roi_images = root / "dataset_roi" / "images"
    roi_masks = root / "dataset_roi" / "masks"
    rows = read_manifest(manifest_path)
    errors: list[str] = []
    seen_ids: set[str] = set()
    expected_names = {Path(row["original_filename"]).name for row in rows}
    expected_mask_names = {f"{Path(name).stem}.png" for name in expected_names}

    for directory, expected in (
        (full_images, expected_names),
        (roi_images, expected_names),
        (full_masks, expected_mask_names),
        (roi_masks, expected_mask_names),
    ):
        if not directory.is_dir():
            errors.append(f"missing dataset directory: {directory}")
            continue
        actual = {path.name for path in directory.iterdir() if path.is_file()}
        for name in sorted(expected - actual):
            errors.append(f"missing file in {directory}: {name}")
        for name in sorted(actual - expected):
            errors.append(f"unmatched file in {directory}: {name}")

    for row in rows:
        image_id = row["image_id"]
        if image_id in seen_ids:
            errors.append(f"duplicate image_id: {image_id}")
        seen_ids.add(image_id)
        original_name = Path(row["original_filename"]).name
        stem = Path(original_name).stem
        full_image_path = full_images / original_name
        full_mask_path = full_masks / f"{stem}.png"
        roi_image_path = roi_images / original_name
        roi_mask_path = roi_masks / f"{stem}.png"

        for path in (full_image_path, full_mask_path, roi_image_path, roi_mask_path):
            if not path.is_file():
                errors.append(f"missing file for {image_id}: {path}")

        if not all(path.is_file() for path in (full_image_path, full_mask_path, roi_image_path, roi_mask_path)):
            continue

        full_image = cv2.imread(str(full_image_path), cv2.IMREAD_COLOR)
        full_mask = cv2.imread(str(full_mask_path), cv2.IMREAD_GRAYSCALE)
        roi_image = cv2.imread(str(roi_image_path), cv2.IMREAD_COLOR)
        roi_mask = cv2.imread(str(roi_mask_path), cv2.IMREAD_GRAYSCALE)
        if any(value is None for value in (full_image, full_mask, roi_image, roi_mask)):
            errors.append(f"unreadable file for {image_id}")
            continue

        height, width = full_image.shape[:2]
        if full_mask.shape[:2] != (height, width):
            errors.append(f"full image/mask size mismatch for {image_id}")
        if not full_mask.any():
            errors.append(f"empty full-frame mask for {image_id}")
        if not roi_mask.any():
            errors.append(f"empty ROI mask for {image_id}")
        if roi_image.shape[:2] != roi_mask.shape[:2]:
            errors.append(f"ROI image/mask size mismatch for {image_id}")

        try:
            coordinates = [int(row[key]) for key in ("roi_x1", "roi_y1", "roi_x2", "roi_y2")]
        except ValueError:
            errors.append(f"non-integer ROI bbox for {image_id}")
            continue
        x1, y1, x2, y2 = coordinates
        if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            errors.append(f"invalid ROI bbox for {image_id}: {coordinates}")
        elif roi_image.shape[:2] != (y2 - y1, x2 - x1):
            errors.append(f"ROI dimensions do not match bbox for {image_id}")

    if errors:
        print(f"FAILED: {len(errors)} issue(s)")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"OK: validated {len(rows)} sample(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Issue 1 dataset output root")
    return check(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
