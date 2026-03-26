"""Visual verification script for load_yolo_bbox().

For each image in data/raw/ that has a matching .txt label file,
draw the predicted bbox and save to data/out/yolo_bbox_<name>.jpg.

Usage:
    python test/verify_yolo_bbox.py
    python test/verify_yolo_bbox.py --input data/raw --limit 10
"""
import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.roi.roi_yolo import load_yolo_bbox

VALID_EXT = {".jpg", ".jpeg", ".png"}


def main():
    parser = argparse.ArgumentParser(description="Visually verify YOLO bbox on raw images.")
    parser.add_argument("--input", default="data/raw", help="Folder containing images and .txt labels")
    parser.add_argument("--output", default="data/out", help="Folder to save annotated images")
    parser.add_argument("--limit", type=int, default=20, help="Max images to process")
    args = parser.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(p for p in in_dir.iterdir() if p.suffix.lower() in VALID_EXT)
    images = images[: args.limit]

    if not images:
        print(f"[WARN] no images found in {in_dir}")
        return

    ok_count = 0
    skip_count = 0
    err_count = 0

    for img_path in images:
        label_path = img_path.with_suffix(".txt")

        if not label_path.exists():
            print(f"[SKIP] no label: {img_path.name}")
            skip_count += 1
            continue

        image = cv2.imread(str(img_path))
        if image is None:
            print(f"[ERR ] cannot read image: {img_path.name}")
            err_count += 1
            continue

        bbox, status, error = load_yolo_bbox(label_path, image.shape)

        if status != "ok":
            print(f"[ERR ] {img_path.name}: {error}")
            err_count += 1
            continue

        x1, y1, x2, y2 = bbox
        vis = image.copy()
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(vis, f"yolo [{x1},{y1},{x2},{y2}]", (x1, max(y1 - 6, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

        out_path = out_dir / f"yolo_bbox_{img_path.name}"
        cv2.imwrite(str(out_path), vis)
        print(f"[OK  ] {img_path.name}  bbox={bbox}  -> {out_path.name}")
        ok_count += 1

    print(f"\nDone. ok={ok_count}  skip(no label)={skip_count}  error={err_count}")


if __name__ == "__main__":
    main()
