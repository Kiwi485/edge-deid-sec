import os
import time
import json
import csv
import numpy as np
import cv2
from pathlib import Path

try:
    from roi.roi_mediapipe import extract_roi_mediapipe
    from roi.roi_fixed_crop import extract_roi_fixed
    from roi.quality_check import check_quality
except ImportError:
    # Fallback when running as module from workspace root.
    from src.roi.roi_mediapipe import extract_roi_mediapipe
    from src.roi.roi_fixed_crop import extract_roi_fixed
    from src.roi.quality_check import check_quality


RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/out")
LOG_DIR = Path("logs")
CSV_PATH = LOG_DIR / "pipeline_latency_vm.csv"
VALID_EXT = {".jpg", ".jpeg", ".png"}
# Set to (width, height) to force resize, or None to keep original
RESIZE_TO = (640, 480)


def ensure_dirs():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def write_csv_header_if_needed():
    if not CSV_PATH.exists():
        with open(CSV_PATH, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "image_id",
                "input_file",
                "roi_ms",
                "seg_ms",
                "feat_ms",
                "deid_ms",
                "total_ms",
                "status"
            ])


def run_batch_pipeline():
    ensure_dirs()
    write_csv_header_if_needed()

    images = [p for p in RAW_DIR.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXT]

    for img_path in images:
        image_id = img_path.stem
        output_folder = OUT_DIR / image_id
        output_folder.mkdir(parents=True, exist_ok=True)

        roi_ms = seg_ms = feat_ms = deid_ms = total_ms = 0.0
        status = "ok"
        error_msg = ""
        roi_method_used = ""
        roi_bbox = []
        deid_method = ""
        quality_result = {"pass": False, "reason": "not_run", "metrics": {}}

        start_total = time.time()

        try:
            image = cv2.imread(str(img_path))
            if image is None:
                raise ValueError("Failed to read image")

            # optional resize
            if RESIZE_TO is not None:
                image = cv2.resize(image, RESIZE_TO)
            h, w = image.shape[:2]

            # ======================
            # Quality gate
            # ======================
            quality_result = check_quality(image)
            if not quality_result["pass"]:
                status = "quality_fail"
                error_msg = quality_result["reason"]

            # ======================
            # ROI (MediaPipe)
            # ======================
            start = time.time()
            roi_img, roi_bbox, roi_status, roi_error = extract_roi_mediapipe(image)

            # MediaPipe failed: continue with deterministic fixed-crop fallback.
            if roi_status != "ok":
                roi_img, roi_bbox = extract_roi_fixed(image)
                roi_method_used = "fallback"
                if roi_img is None:
                    raise ValueError(f"roi_fallback_failed: {roi_error}")
                if error_msg:
                    error_msg = f"{error_msg}; {roi_error}"
                else:
                    error_msg = roi_error
            else:
                roi_method_used = "mediapipe"

            roi_ms = (time.time() - start) * 1000

            cv2.imwrite(str(output_folder / "roi.png"), roi_img)

            # ======================
            # Segmentation (placeholder)
            # ======================
            start = time.time()
            mask = np.zeros((h, w), dtype=np.uint8)  # placeholder: all zeros
            # ensure mask uses 0/255 values as required by spec
            mask = (mask * 255).astype(np.uint8)
            seg_ms = (time.time() - start) * 1000
            cv2.imwrite(str(output_folder / "mask.png"), mask)

            # ======================
            # Feature 256 (placeholder)
            # ======================
            start = time.time()
            feature_256 = np.zeros(256, dtype=np.float32)
            np.save(output_folder / "feature_256.npy", feature_256)
            feat_ms = (time.time() - start) * 1000

            # ======================
            # DeID (placeholder: copy image)
            # ======================
            start = time.time()
            deid_img = image.copy()
            deid_method = "roi_only"
            deid_ms = (time.time() - start) * 1000

            cv2.imwrite(str(output_folder / "deid.png"), deid_img)

        except Exception as e:
            status = "error"
            error_msg = str(e)

        total_ms = (time.time() - start_total) * 1000

        # ======================
        # meta.json
        # ======================
        meta = {
            "image_id": image_id,
            "input_file": img_path.name,
            "roi_method_used": roi_method_used if status != "error" else "",
            "roi_bbox": roi_bbox if status != "error" else [],
            "quality_gate": quality_result,
            "deid_method": deid_method if status != "error" else "",
            "timing_ms": {
                "roi_ms": roi_ms,
                "seg_ms": seg_ms,
                "feat_ms": feat_ms,
                "deid_ms": deid_ms,
                "total_ms": total_ms
            },
            "status": status,
            "error": error_msg
        }

        with open(output_folder / "meta.json", "w") as f:
            json.dump(meta, f, indent=2)

        # ======================
        # Append CSV
        # ======================
        with open(CSV_PATH, mode="a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                image_id,
                img_path.name,
                roi_ms,
                seg_ms,
                feat_ms,
                deid_ms,
                total_ms,
                status
            ])

    print("Batch processing completed.")


if __name__ == "__main__":
    run_batch_pipeline()