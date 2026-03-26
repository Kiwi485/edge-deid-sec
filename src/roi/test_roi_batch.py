import argparse
from pathlib import Path

import cv2

try:
    from roi_mediapipe import extract_roi_mediapipe
    from roi_fixed_crop import extract_roi_fixed
    from roi_yolo import load_yolo_bbox
    from quality_check import check_quality
except ImportError:
    from src.roi.roi_mediapipe import extract_roi_mediapipe
    from src.roi.roi_fixed_crop import extract_roi_fixed
    from src.roi.roi_yolo import load_yolo_bbox
    from src.roi.quality_check import check_quality


VALID_EXT = {".jpg", ".jpeg", ".png"}


def main():
    parser = argparse.ArgumentParser(description="Run MediaPipe ROI test on a folder of images.")
    parser.add_argument("--input", default="data/raw", help="Input image folder")
    parser.add_argument("--limit", type=int, default=50, help="Max images to test")
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.exists():
        raise FileNotFoundError(f"Input dir not found: {input_dir}")

    images = [p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXT]
    images = images[: args.limit]

    total = len(images)
    ok_count = 0
    yolo_count = 0
    fixed_count = 0
    quality_fail_count = 0
    err_count = 0

    for img_path in images:
        image = cv2.imread(str(img_path))
        quality_result = check_quality(image)
        roi_img, roi_bbox, roi_status, roi_error = extract_roi_mediapipe(image)

        if roi_status == "ok":
            method = "mediapipe"
        else:
            mp_error = roi_error
            label_path = img_path.with_suffix(".txt")
            yolo_bbox, yolo_status, _ = load_yolo_bbox(label_path, image.shape)

            if yolo_status == "ok":
                x1, y1, x2, y2 = yolo_bbox
                roi_img = image[y1:y2, x1:x2].copy()
                roi_bbox = yolo_bbox
                roi_status = "ok"
                roi_error = mp_error
                method = "yolo_fallback"
            else:
                roi_img, roi_bbox = extract_roi_fixed(image)
                roi_status = "ok" if roi_img is not None else "error"
                roi_error = mp_error
                method = "fixed_fallback"

        if roi_status == "ok" and method == "mediapipe":
            ok_count += 1
            if not quality_result["pass"]:
                quality_fail_count += 1
            print(f"[MP ] {img_path.name} bbox={roi_bbox} shape={roi_img.shape}")
        elif roi_status == "ok" and method == "yolo_fallback":
            yolo_count += 1
            if not quality_result["pass"]:
                quality_fail_count += 1
            print(f"[YL ] {img_path.name} bbox={roi_bbox} shape={roi_img.shape} mp_err={roi_error}")
        elif roi_status == "ok" and method == "fixed_fallback":
            fixed_count += 1
            if not quality_result["pass"]:
                quality_fail_count += 1
            print(f"[FX ] {img_path.name} bbox={roi_bbox} reason={roi_error}")
        else:
            err_count += 1
            print(f"[ERR] {img_path.name} error={roi_error}")

    print("\n=== ROI Test Summary ===")
    print(f"total={total}")
    print(f"mediapipe={ok_count}")
    print(f"yolo_fallback={yolo_count}")
    print(f"fixed_fallback={fixed_count}")
    print(f"quality_fail={quality_fail_count}")
    print(f"error={err_count}")
    if total > 0:
        print(f"mediapipe_rate={ok_count / total:.2%}")
        print(f"yolo_fallback_rate={yolo_count / total:.2%}")
        print(f"fixed_fallback_rate={fixed_count / total:.2%}")


if __name__ == "__main__":
    main()
