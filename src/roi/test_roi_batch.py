import argparse
from pathlib import Path

import cv2

try:
    from roi_mediapipe import extract_roi_mediapipe
    from roi_fixed_crop import extract_roi_fixed
    from quality_check import check_quality
except ImportError:
    from src.roi.roi_mediapipe import extract_roi_mediapipe
    from src.roi.roi_fixed_crop import extract_roi_fixed
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
    fallback_count = 0
    quality_fail_count = 0
    err_count = 0

    for img_path in images:
        image = cv2.imread(str(img_path))
        quality_result = check_quality(image)
        roi_img, roi_bbox, status, error = extract_roi_mediapipe(image)

        if status != "ok":
            roi_img, roi_bbox = extract_roi_fixed(image)
            status = "fallback" if roi_img is not None else "error"

        if status == "ok":
            ok_count += 1
            print(f"[OK] {img_path.name} bbox={roi_bbox} roi_shape={roi_img.shape}")
            if not quality_result["pass"]:
                quality_fail_count += 1
        elif status == "fallback":
            fallback_count += 1
            if not quality_result["pass"]:
                quality_fail_count += 1
            print(f"[FB] {img_path.name} bbox={roi_bbox} reason={error} quality={quality_result['reason']}")
        else:
            err_count += 1
            print(f"[ERR] {img_path.name} error={error}")

    print("\n=== ROI Test Summary ===")
    print(f"total={total}")
    print(f"ok={ok_count}")
    print(f"fallback={fallback_count}")
    print(f"quality_fail={quality_fail_count}")
    print(f"error={err_count}")
    if total > 0:
        print(f"ok_rate={ok_count / total:.2%}")
        print(f"fallback_rate={fallback_count / total:.2%}")
        print(f"quality_fail_rate={quality_fail_count / total:.2%}")


if __name__ == "__main__":
    main()
