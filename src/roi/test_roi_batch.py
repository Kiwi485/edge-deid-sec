import argparse
from pathlib import Path

import cv2

try:
    from roi_mediapipe import extract_roi_mediapipe
except ImportError:
    from src.roi.roi_mediapipe import extract_roi_mediapipe


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
    usable_count = 0
    err_count = 0

    for img_path in images:
        image = cv2.imread(str(img_path))
        roi_img, roi_bbox, status, error = extract_roi_mediapipe(image)

        if status == "ok":
            ok_count += 1
            usable_count += 1
            print(f"[OK] {img_path.name} bbox={roi_bbox} roi_shape={roi_img.shape}")
        elif status == "quality_fail":
            usable_count += 1
            print(f"[QF] {img_path.name} bbox={roi_bbox} warn={error}")
        else:
            err_count += 1
            print(f"[ERR] {img_path.name} error={error}")

    print("\n=== ROI Test Summary ===")
    print(f"total={total}")
    print(f"ok={ok_count}")
    print(f"usable_roi={usable_count}")
    print(f"error={err_count}")
    if total > 0:
        print(f"ok_rate={ok_count / total:.2%}")
        print(f"usable_rate={usable_count / total:.2%}")


if __name__ == "__main__":
    main()
