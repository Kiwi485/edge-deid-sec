"""Convert CVAT COCO polygon annotations to YOLO detection labels.

The output is compatible with tools/prepare_yolo_dataset.py:

    data/raw_yolo/
        images/<image files>
        labels/<image stem>.txt

Usage:
    python tools/convert_coco_to_yolo_detection.py
    python tools/convert_coco_to_yolo_detection.py --overwrite
"""

import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path


DEFAULT_COCO_JSON = Path("foryolo/annotations/instances_default.json")
DEFAULT_IMAGES_DIR = Path("foryolo/images/default")
DEFAULT_OUT_DIR = Path("data/raw_yolo")


def polygon_bbox(segmentation):
    points = []
    if not isinstance(segmentation, list):
        return None

    for polygon in segmentation:
        if not isinstance(polygon, list) or len(polygon) < 6:
            continue
        points.extend(
            (float(polygon[index]), float(polygon[index + 1]))
            for index in range(0, len(polygon) - 1, 2)
        )

    if not points:
        return None

    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def to_yolo_bbox(bbox, width, height):
    x1, y1, x2, y2 = bbox
    x1 = min(max(x1, 0.0), float(width))
    x2 = min(max(x2, 0.0), float(width))
    y1 = min(max(y1, 0.0), float(height))
    y2 = min(max(y2, 0.0), float(height))
    if x2 <= x1 or y2 <= y1:
        return None

    return (
        (x1 + x2) / (2.0 * width),
        (y1 + y2) / (2.0 * height),
        (x2 - x1) / width,
        (y2 - y1) / height,
    )


def convert(coco_json: Path, images_dir: Path, out_dir: Path, overwrite: bool):
    if out_dir.exists():
        if not overwrite:
            raise SystemExit(f"{out_dir} already exists; use --overwrite to replace it")
        shutil.rmtree(out_dir)

    with coco_json.open("r", encoding="utf-8") as file:
        coco = json.load(file)

    images = {image["id"]: image for image in coco.get("images", [])}
    categories = sorted(coco.get("categories", []), key=lambda item: item["id"])
    category_to_class = {
        category["id"]: class_id for class_id, category in enumerate(categories)
    }
    labels_by_image = defaultdict(list)
    skipped_annotations = 0

    for annotation in coco.get("annotations", []):
        image = images.get(annotation.get("image_id"))
        class_id = category_to_class.get(annotation.get("category_id"))
        if image is None or class_id is None:
            skipped_annotations += 1
            continue

        bbox = polygon_bbox(annotation.get("segmentation"))
        yolo_bbox = to_yolo_bbox(bbox, image["width"], image["height"]) if bbox else None
        if yolo_bbox is None:
            skipped_annotations += 1
            continue

        values = " ".join(f"{value:.6f}" for value in yolo_bbox)
        labels_by_image[image["id"]].append(f"{class_id} {values}")

    output_images = out_dir / "images"
    output_labels = out_dir / "labels"
    output_images.mkdir(parents=True)
    output_labels.mkdir(parents=True)

    converted_images = 0
    missing_images = []
    for image_id, label_lines in labels_by_image.items():
        image = images[image_id]
        source = images_dir / image["file_name"]
        if not source.exists():
            missing_images.append(image["file_name"])
            continue

        shutil.copy2(source, output_images / source.name)
        (output_labels / f"{source.stem}.txt").write_text(
            "\n".join(label_lines) + "\n", encoding="utf-8"
        )
        converted_images += 1

    class_names = [category["name"] for category in categories]
    print(f"[ok] classes={class_names}")
    print(f"[ok] converted_images={converted_images}")
    print(f"[ok] skipped_annotations={skipped_annotations}")
    print(f"[ok] missing_images={len(missing_images)}")
    print(f"[ok] output={out_dir}")
    if missing_images:
        print("[warning] first missing images: " + ", ".join(missing_images[:5]))
    if converted_images == 0:
        raise SystemExit("No polygon annotations were converted")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--coco-json", type=Path, default=DEFAULT_COCO_JSON)
    parser.add_argument("--images-dir", type=Path, default=DEFAULT_IMAGES_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if not args.coco_json.exists():
        raise SystemExit(f"COCO JSON not found: {args.coco_json}")
    if not args.images_dir.is_dir():
        raise SystemExit(f"Images directory not found: {args.images_dir}")

    convert(args.coco_json, args.images_dir, args.out_dir, args.overwrite)


if __name__ == "__main__":
    main()