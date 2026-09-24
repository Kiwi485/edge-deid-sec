"""Test the trained YOLO ROI detector on a folder of images.

Usage:
    python tools/test_yolo_data_test.py --input data_test --output data_test/yolo_roi --limit 50
"""
import argparse
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.roi.roi_yolo_detect import predict_yolo_bbox

VALID_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".JPG", ".JPEG", ".PNG", ".BMP"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run YOLO ROI detection on a folder of images.")
    parser.add_argument("--input", default="data_test", help="Folder containing test images")
    parser.add_argument("--output", default="data_test/yolo_roi", help="Folder to save ROI crops and annotated images")
    parser.add_argument("--limit", type=int, default=100, help="Maximum number of images to process")
    parser.add_argument("--conf", type=float, default=0.25, help="YOLO confidence threshold")
    parser.add_argument("--iou", type=float, default=0.45, help="YOLO NMS IOU threshold")
    args = parser.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(p for p in in_dir.iterdir() if p.suffix.lower() in VALID_EXT)
    if not images:
        print(f"[ERROR] no images found in {in_dir}")
        return 1

    images = images[: args.limit]
    print(f"Processing {len(images)} images from {in_dir}")

    for img_path in images:
        image = cv2.imread(str(img_path))
        if image is None:
            print(f"{img_path.name}\tERROR\tread_error")
            continue

        roi_img, bbox, status, error = predict_yolo_bbox(image, conf=args.conf, iou=args.iou)
        if status != "ok":
            print(f"{img_path.name}\tERROR\t{error}")
            continue

        x1, y1, x2, y2 = bbox
        vis = image.copy()
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(vis, f"YOLO [{x1},{y1},{x2},{y2}]", (x1, max(y1 - 8, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

        out_vis = out_dir / f"yolo_box_{img_path.name}"
        out_roi = out_dir / f"roi_{img_path.name}"
        cv2.imwrite(str(out_vis), vis)
        cv2.imwrite(str(out_roi), roi_img)
        print(f"{img_path.name}\tOK\t{bbox}\t{out_vis.name}\t{out_roi.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
