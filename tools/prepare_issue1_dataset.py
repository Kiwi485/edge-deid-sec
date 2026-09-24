"""Build reproducible full-frame and ROI datasets for ACM RACS Issue 1.

The input annotation format is the CVAT COCO 1.0 polygon export supported by
src.seg.dataset. No segmentation model output is used as ground truth.

Example:
    python tools/prepare_issue1_dataset.py \
        --images-dir data/raw \
        --annotations data/cvat \
        --output-root data/issue1

Outputs:
    <output-root>/dataset_full/images/
    <output-root>/dataset_full/masks/
    <output-root>/dataset_roi/images/
    <output-root>/dataset_roi/masks/
    <output-root>/metadata/manifest.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any

import cv2
import numpy as np

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".heic"}
MANIFEST_FIELDS = [
    "image_id",
    "original_filename",
    "image_width",
    "image_height",
    "roi_x1",
    "roi_y1",
    "roi_x2",
    "roi_y2",
    "roi_method",
    "split",
]


def load_image(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"cannot read image: {path}")
    return image


def find_image(images_dir: Path, file_name: str) -> Path | None:
    direct = images_dir / file_name
    if direct.is_file():
        return direct
    basename_matches = sorted(
        path for path in images_dir.rglob(Path(file_name).name) if path.is_file()
    )
    return basename_matches[0] if basename_matches else None


def infer_split(annotation_path: Path) -> str:
    parts = {part.lower() for part in annotation_path.parts}
    if "test" in parts:
        return "test"
    if "valid" in parts or "val" in parts or "validation" in parts:
        return "validation"
    if "train" in parts:
        return "train"
    return "unspecified"


def load_split_manifest(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    if not path.exists():
        raise FileNotFoundError(f"split manifest not found: {path}")

    result: dict[str, str] = {}
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("samples", payload) if isinstance(payload, dict) else payload
        for row in rows:
            key = str(row.get("image_id", row.get("original_filename", "")))
            split = row.get("split", row.get("assigned_split"))
            if key and split:
                result[key] = normalize_split(str(split))
        return result

    with path.open("r", newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            key = row.get("image_id") or row.get("original_filename") or ""
            split = row.get("split") or row.get("assigned_split") or ""
            if key and split:
                result[key] = normalize_split(split)
    return result


def normalize_split(value: str) -> str:
    value = value.strip().lower()
    return {"val": "validation", "valid": "validation", "dev": "validation"}.get(value, value)


def annotation_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    files = sorted(path.rglob("*.json"))
    if not files:
        raise FileNotFoundError(f"no COCO JSON files found under: {path}")
    return files


def load_coco_records(annotation_path: Path, images_dir: Path) -> list[dict[str, Any]]:
    payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not {"images", "annotations"}.issubset(payload):
        raise ValueError(f"not a supported COCO annotation file: {annotation_path}")

    annotations_by_image: dict[Any, list[dict[str, Any]]] = {}
    for annotation in payload.get("annotations", []):
        annotations_by_image.setdefault(annotation.get("image_id"), []).append(annotation)

    records = []
    for image_info in payload.get("images", []):
        image_id = str(image_info.get("id", ""))
        file_name = str(image_info.get("file_name", ""))
        image_path = find_image(images_dir, file_name)
        records.append(
            {
                "image_id": image_id,
                "file_name": file_name,
                "image_path": image_path,
                "annotations": annotations_by_image.get(image_info.get("id"), []),
                "split": infer_split(annotation_path),
            }
        )
    return records


def polygon_mask(annotations: list[dict[str, Any]], height: int, width: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    polygon_count = 0
    for annotation in annotations:
        segmentation = annotation.get("segmentation", [])
        if not isinstance(segmentation, list):
            continue
        for polygon in segmentation:
            if not isinstance(polygon, list) or len(polygon) < 6:
                continue
            points = np.asarray(polygon, dtype=np.float32).reshape(-1, 2)
            points[:, 0] = np.clip(points[:, 0], 0, width - 1)
            points[:, 1] = np.clip(points[:, 1], 0, height - 1)
            cv2.fillPoly(mask, [np.round(points).astype(np.int32)], 255)
            polygon_count += 1
    if polygon_count == 0 or not np.any(mask):
        raise ValueError("annotation has no non-empty polygon segmentation")
    return mask


def extract_roi(image: np.ndarray) -> tuple[np.ndarray, list[int], str]:
    try:
        from src.roi.roi_mediapipe import extract_roi_mediapipe
        roi, bbox, status, _ = extract_roi_mediapipe(image)
        if status == "ok":
            return roi, bbox, "mediapipe"
    except Exception:
        pass

    try:
        from src.roi.roi_yolo_detect import predict_yolo_bbox
        roi, bbox, status, _ = predict_yolo_bbox(image)
        if status == "ok":
            return roi, bbox, "yolo_detect"
    except Exception:
        pass

    from src.roi.roi_fixed_crop import extract_roi_fixed
    roi, bbox = extract_roi_fixed(image)
    if roi is None or len(bbox) != 4:
        raise ValueError("all ROI extraction methods failed")
    return roi, bbox, "fixed_fallback"


def validate_bbox(bbox: list[int], width: int, height: int) -> None:
    if len(bbox) != 4:
        raise ValueError(f"invalid ROI bbox: {bbox}")
    x1, y1, x2, y2 = bbox
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError(f"ROI bbox outside image bounds: {bbox} for {width}x{height}")


def prepare(args: argparse.Namespace) -> int:
    images_dir = Path(args.images_dir)
    annotations_path = Path(args.annotations)
    output_root = Path(args.output_root)
    if not images_dir.is_dir():
        raise FileNotFoundError(f"images directory not found: {images_dir}")

    split_map = load_split_manifest(Path(args.split_manifest) if args.split_manifest else None)
    records: dict[str, dict[str, Any]] = {}
    for file_path in annotation_files(annotations_path):
        for record in load_coco_records(file_path, images_dir):
            if record["image_id"] in records:
                raise ValueError(f"duplicate image_id in annotations: {record['image_id']}")
            records[record["image_id"]] = record

    if not records:
        raise ValueError("no COCO image records found")

    full_images = output_root / "dataset_full" / "images"
    full_masks = output_root / "dataset_full" / "masks"
    roi_images = output_root / "dataset_roi" / "images"
    roi_masks = output_root / "dataset_roi" / "masks"
    metadata_dir = output_root / "metadata"
    if output_root.exists() and not args.overwrite:
        existing = [path for path in (full_images, full_masks, roi_images, roi_masks) if path.exists()]
        if existing:
            raise FileExistsError(f"output already exists; use --overwrite: {output_root}")
    if args.overwrite and output_root.exists():
        shutil.rmtree(output_root)
    for directory in (full_images, full_masks, roi_images, roi_masks, metadata_dir):
        directory.mkdir(parents=True, exist_ok=True)

    rows = []
    for image_id in sorted(records):
        record = records[image_id]
        image_path = record["image_path"]
        if image_path is None:
            raise FileNotFoundError(f"missing image for {record['file_name']}")
        if not record["annotations"]:
            raise ValueError(f"missing annotation for image_id={image_id}")

        image = load_image(image_path)
        height, width = image.shape[:2]
        mask = polygon_mask(record["annotations"], height, width)
        roi_image, bbox, roi_method = extract_roi(image)
        validate_bbox(bbox, width, height)
        x1, y1, x2, y2 = bbox
        roi_mask = mask[y1:y2, x1:x2].copy()
        if roi_image.shape[:2] != roi_mask.shape[:2]:
            raise ValueError(f"ROI image/mask shape mismatch for image_id={image_id}")

        output_name = Path(record["file_name"]).name
        full_image_path = full_images / output_name
        full_mask_path = full_masks / f"{Path(output_name).stem}.png"
        roi_image_path = roi_images / output_name
        roi_mask_path = roi_masks / f"{Path(output_name).stem}.png"
        if not cv2.imwrite(str(full_image_path), image):
            raise IOError(f"failed to write {full_image_path}")
        if not cv2.imwrite(str(full_mask_path), mask):
            raise IOError(f"failed to write {full_mask_path}")
        if not cv2.imwrite(str(roi_image_path), roi_image):
            raise IOError(f"failed to write {roi_image_path}")
        if not cv2.imwrite(str(roi_mask_path), roi_mask):
            raise IOError(f"failed to write {roi_mask_path}")

        split = split_map.get(image_id, split_map.get(record["file_name"], record["split"]))
        rows.append(
            {
                "image_id": image_id,
                "original_filename": record["file_name"],
                "image_width": width,
                "image_height": height,
                "roi_x1": x1,
                "roi_y1": y1,
                "roi_x2": x2,
                "roi_y2": y2,
                "roi_method": roi_method,
                "split": split,
            }
        )

    manifest_path = metadata_dir / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"created {len(rows)} samples")
    print(f"manifest: {manifest_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-dir", required=True, help="Original full-frame image directory")
    parser.add_argument("--annotations", required=True, help="COCO JSON file or directory containing COCO JSON files")
    parser.add_argument("--output-root", default=".", help="Root receiving dataset_full, dataset_roi, and metadata")
    parser.add_argument("--split-manifest", default=None, help="Optional CSV/JSON mapping image_id or filename to split")
    parser.add_argument("--overwrite", action="store_true")
    return prepare(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
