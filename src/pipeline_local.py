import argparse
import shutil
import time
import json
import csv
import numpy as np
import cv2
try:
    import pillow_heif
    from PIL import Image as PILImage
    pillow_heif.register_heif_opener()
except ImportError:
    PILImage = None
from pathlib import Path
from random import Random

try:
    from roi.roi_mediapipe import extract_roi_mediapipe
    from roi.roi_fixed_crop import extract_roi_fixed
    from roi.roi_yolo import load_yolo_bbox
    from roi.roi_yolo_detect import predict_yolo_bbox
    from roi.quality_check import check_quality
    from deid.build_tongue_mask import build_mask
    from deid.deid_mask_only import deid_mask_only
    from seg.inference import run_inference
    from seg.feature_extractor import extract_features
except ImportError:
    # Fallback when running as module from workspace root.
    from src.roi.roi_mediapipe import extract_roi_mediapipe
    from src.roi.roi_fixed_crop import extract_roi_fixed
    from src.roi.roi_yolo import load_yolo_bbox
    from src.roi.roi_yolo_detect import predict_yolo_bbox
    from src.roi.quality_check import check_quality
    from src.deid.build_tongue_mask import build_mask
    from src.deid.deid_mask_only import deid_mask_only
    from src.seg.inference import run_inference
    from src.seg.feature_extractor import extract_features


RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/out")
LOG_DIR = Path("logs")
CSV_PATH = LOG_DIR / "pipeline_latency_vm.csv"
VALID_EXT = {".jpg", ".jpeg", ".png", ".heic"}
# Set to (width, height) to force resize, or None to keep original
RESIZE_TO = (640, 480)

# U-Net segmentation model settings
SEG_MODEL_PATH = Path("models/seg/best.pth")
SEG_IMG_SIZE = 256
SEG_THRESHOLD = 0.5


def ensure_dirs(raw_dir: Path, out_dir: Path, csv_path: Path):
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)


def _load_image(img_path: Path):
    if img_path.suffix.lower() == ".heic":
        if PILImage is None:
            raise ImportError(
                "HEIC support missing: install pillow_heif to load .heic images"
            )
        pil_img = PILImage.open(str(img_path)).convert("RGB")
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    buf = np.fromfile(str(img_path), dtype=np.uint8)
    image = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Failed to read image {img_path}")
    return image


def write_csv_header_if_needed(csv_path: Path):
    if not csv_path.exists():
        with open(csv_path, mode="w", newline="") as f:
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


def _normalize_mask(mask: np.ndarray) -> np.ndarray:
    if mask is None or mask.size == 0:
        raise ValueError("mask is empty")

    if mask.ndim == 3:
        if mask.shape[2] == 1:
            mask = mask[:, :, 0]
        elif mask.shape[2] == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        else:
            raise ValueError("invalid mask format: unsupported channel count")
    elif mask.ndim != 2:
        raise ValueError("invalid mask format: expected 2D or 3D array")

    return (mask > 0)


def apply_mask_only(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    if image is None or image.size == 0:
        raise ValueError("input image is empty")
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("input image must be a color image (3 channels)")

    mask_bin = _normalize_mask(mask)
    if image.shape[:2] != mask_bin.shape[:2]:
        raise ValueError("mask size does not match input image")

    out = np.zeros_like(image)
    out[mask_bin] = image[mask_bin]
    return out


def run_batch_pipeline(
    raw_dir: Path,
    out_dir: Path,
    csv_path: Path,
    limit: int = 0,
    shuffle: bool = False,
    seed: int = 42,
    reset_csv: bool = False,
    clear_out: bool = False,
    append_csv: bool = False,
):
    if clear_out and out_dir.exists():
        shutil.rmtree(out_dir)

    if reset_csv and csv_path.exists():
        csv_path.unlink()

    # Default to clean benchmark data: start a new CSV unless explicitly appending.
    if (not reset_csv) and (not append_csv) and csv_path.exists():
        csv_path.unlink()

    ensure_dirs(raw_dir, out_dir, csv_path)
    write_csv_header_if_needed(csv_path)

    images = sorted([p for p in raw_dir.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXT])
    if shuffle:
        rng = Random(seed)
        rng.shuffle(images)
    if limit > 0:
        images = images[:limit]

    status_counts = {"ok": 0, "quality_fail": 0, "error": 0}

    for img_path in images:
        image_id = img_path.stem
        output_folder = out_dir / image_id
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
            image = _load_image(img_path)

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
            # ROI: MediaPipe → YOLO detect → YOLO .txt label → fixed fallback
            # ======================
            start = time.time()
            roi_img, roi_bbox, mp_status, mp_error = extract_roi_mediapipe(image)
            combined_error = ""

            if mp_status == "ok":
                roi_method_used = "mediapipe"
            else:
                det_img, det_bbox, det_status, det_error = predict_yolo_bbox(image)
                if det_status == "ok":
                    roi_img, roi_bbox = det_img, det_bbox
                    roi_method_used = "yolo_detect"
                    combined_error = f"mp: {mp_error}"
                else:
                    label_path = raw_dir / img_path.with_suffix(".txt").name
                    yolo_bbox, yolo_status, yolo_error = load_yolo_bbox(
                        label_path, image.shape
                    )
                    if yolo_status == "ok":
                        x1, y1, x2, y2 = yolo_bbox
                        roi_img = image[y1:y2, x1:x2].copy()
                        roi_bbox = yolo_bbox
                        roi_method_used = "yolo_label"
                        combined_error = (
                            f"mp: {mp_error}; yolo_detect: {det_error}"
                        )
                    else:
                        roi_img, roi_bbox = extract_roi_fixed(image)
                        roi_method_used = "fixed_fallback"
                        combined_error = (
                            f"mp: {mp_error}; yolo_detect: {det_error}; "
                            f"label: {yolo_error}"
                        )

            if roi_img is None:
                raise ValueError(f"roi_all_fallbacks_failed: {combined_error}")

            if combined_error and error_msg:
                error_msg = f"{error_msg}; {combined_error}"

            roi_ms = (time.time() - start) * 1000

            cv2.imwrite(str(output_folder / "roi.png"), roi_img)

            # ======================
            # Segmentation（U-Net model on ROI crop）
            # ======================
            start = time.time()
            if SEG_MODEL_PATH.exists():
                # Pass ROI array directly to avoid temp file disk I/O
                roi_mask, _ = run_inference(
                    "",
                    str(SEG_MODEL_PATH),
                    img_size=SEG_IMG_SIZE,
                    threshold=SEG_THRESHOLD,
                    image_array=roi_img,
                )

                # Keep only the largest connected component (removes chin/neck noise)
                if roi_mask.max() > 0:
                    _bin = (roi_mask > 0).astype(np.uint8)
                    _n, _lbl, _stats, _ = cv2.connectedComponentsWithStats(_bin, connectivity=8)
                    if _n > 2:
                        _largest = 1 + int(np.argmax(_stats[1:, cv2.CC_STAT_AREA]))
                        roi_mask = np.where(_lbl == _largest, roi_mask.max(), 0).astype(np.uint8)

                # Paste ROI mask back into full-image coordinates
                x1, y1, x2, y2 = roi_bbox
                roi_mask_resized = cv2.resize(roi_mask, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)
                mask = np.zeros((h, w), dtype=np.uint8)
                mask[y1:y2, x1:x2] = roi_mask_resized
            else:
                # Fallback to HSV method if model checkpoint not found
                m = build_mask(image, roi_bbox)
                if m is not None:
                    mask = (m * 255).astype(np.uint8) if m.dtype == np.bool_ else np.where(m > 0, 255, 0).astype(np.uint8)
                else:
                    mask = np.zeros((h, w), dtype=np.uint8)
            seg_ms = (time.time() - start) * 1000
            cv2.imwrite(str(output_folder / "mask.png"), mask)

            # ======================
            # Feature 256
            # ======================
            start = time.time()
            feature_256 = extract_features(image, mask)
            np.save(output_folder / "feature_256.npy", feature_256)
            feat_ms = (time.time() - start) * 1000

            # ======================
            # DeID: keep only tongue mask pixels; everything else is black.
            # ======================
            start = time.time()
            deid_img, _ = deid_mask_only(image, mask)
            if deid_img is None:
                deid_img = apply_mask_only(image, mask)
            deid_method = "mask_only"
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
        # Auto-write YOLO .txt label alongside image.
        # So the next pipeline run can use yolo_fallback instead of fixed fallback.
        # Only written when roi_bbox is valid; failure must not affect pipeline result.
        # ======================
        if roi_bbox and len(roi_bbox) == 4 and status != "error":
            try:
                x1, y1, x2, y2 = roi_bbox
                h_img, w_img = image.shape[:2]
                if w_img > 0 and h_img > 0 and x2 > x1 and y2 > y1:
                    xc = (x1 + x2) / 2 / w_img
                    yc = (y1 + y2) / 2 / h_img
                    bw = (x2 - x1) / w_img
                    bh = (y2 - y1) / h_img
                    label_path = raw_dir / img_path.with_suffix(".txt").name
                    if not label_path.exists():
                        label_path.write_text(
                            f"0 {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}\n",
                            encoding="utf-8",
                        )
            except Exception:
                pass

        # ======================
        # Append CSV
        # ======================
        with open(csv_path, mode="a", newline="") as f:
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

        status_counts[status] = status_counts.get(status, 0) + 1

    print("Batch processing completed.")
    print(f"CSV: {csv_path}")
    print(f"Processed: {len(images)}")
    print(
        "Status counts: "
        f"ok={status_counts.get('ok', 0)}, "
        f"quality_fail={status_counts.get('quality_fail', 0)}, "
        f"error={status_counts.get('error', 0)}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local batch pipeline for ROI/seg/deid outputs and latency CSV.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=RAW_DIR,
        help="Input raw image folder.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DIR,
        help="Output folder for per-image artifacts.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=CSV_PATH,
        help="Latency CSV output path.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most N images (0 means all).",
    )
    parser.add_argument(
        "--shuffle",
        action="store_true",
        help="Shuffle image order before applying limit.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed used when --shuffle is enabled.",
    )
    parser.add_argument(
        "--reset-csv",
        action="store_true",
        help="Delete target CSV before run to avoid mixing old rows.",
    )
    parser.add_argument(
        "--clear-out",
        action="store_true",
        help="Delete output folder before run.",
    )
    parser.add_argument(
        "--append-csv",
        action="store_true",
        help="Append rows to existing CSV instead of starting a clean file.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_batch_pipeline(
        raw_dir=args.raw_dir,
        out_dir=args.out_dir,
        csv_path=args.csv,
        limit=args.limit,
        shuffle=args.shuffle,
        seed=args.seed,
        reset_csv=args.reset_csv,
        clear_out=args.clear_out,
        append_csv=args.append_csv,
    )