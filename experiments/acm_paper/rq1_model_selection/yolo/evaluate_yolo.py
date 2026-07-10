"""
evaluate_yolo.py — ACM Paper RQ1: Evaluate YOLOv8n-seg
=======================================================
Evaluates a trained YOLOv8n-seg checkpoint on the held-out test split
using the same :class:`SegmentationMetricsAccumulator` as the SMP models.

Prediction pipeline
-------------------
1. Run YOLO inference on each test image.
2. If multiple instance masks are predicted, merge them with logical OR.
3. Resize the combined binary mask to match the ground-truth dimensions
   (nearest-neighbour interpolation).
4. If YOLO predicts no mask, use an all-zero prediction.
5. Feed the final binary mask into the ACM metrics accumulator.

IMPORTANT
---------
- Do NOT rely solely on Ultralytics mAP as the final paper metric.
- Final metrics MUST come from metrics.py to ensure consistent comparison
  with the three SMP models.
- Do NOT use test results to select the checkpoint.

Reported metrics
----------------
Dice, IoU, Precision, Recall, Pixel Accuracy, TP, FP, FN, TN
(same metric definitions as evaluate_smp.py)

Usage
-----
::

    python -m experiments.acm_paper.rq1_model_selection.yolo.evaluate_yolo \\
        --data-dir DATASET_PATH \\
        --checkpoint models/acm_paper/rq1/yolov8n_seg/weights/best.pt \\
        --split test \\
        --img-size 256 \\
        --threshold 0.5 \\
        --split-manifest outputs/acm_paper/rq1/split_manifest.json \\
        --output outputs/acm_paper/rq1/yolov8n_seg.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from experiments.acm_paper.rq1_model_selection.metrics import SegmentationMetricsAccumulator
from experiments.acm_paper.rq1_model_selection.dataset_split import (
    load_manifest,
    get_split_image_paths,
)

WARMUP_ITERATIONS = 10
BENCHMARK_ITERATIONS = 100


# ---------------------------------------------------------------------------
# Ground-truth mask loading
# ---------------------------------------------------------------------------

def _find_gt_mask(
    img_path: Path,
    data_dir: Path,
    manifest_entry: Optional[Dict],
) -> Optional[np.ndarray]:
    """
    Locate and load the ground-truth mask for an image.

    Supports:
      - COCO JSON (loads from COCO annotation → renders polygon)
      - PNG mask file parallel to images

    Returns
    -------
    np.ndarray | None  : Binary mask (H, W) with values 0 or 1.
    """
    try:
        import cv2
    except ImportError:
        print("[evaluate_yolo] ERROR: opencv-python required.")
        return None

    # Try PNG mask in parallel masks/ directory
    stem = img_path.stem
    mask_candidates: List[Path] = []
    for mask_dir in [
        data_dir / "masks",
        img_path.parent.parent / "masks",
        img_path.parent / "masks",
    ]:
        for ext in (".png", ".jpg", ".jpeg"):
            mask_candidates.append(mask_dir / f"{stem}{ext}")

    for mc in mask_candidates:
        if mc.exists():
            mask = cv2.imread(str(mc), cv2.IMREAD_GRAYSCALE)
            if mask is not None:
                _, binary = cv2.threshold(mask, 127, 1, cv2.THRESH_BINARY)
                return binary.astype(np.uint8)

    # Try COCO JSON in the split directory
    split_dir = img_path.parent if img_path.parent != data_dir else data_dir
    coco_candidates = [
        split_dir / "_annotations.coco.json",
        split_dir / "annotations" / "instances_default.json",
        split_dir.parent / "annotations" / "instances_default.json",  # train/annotations/
        split_dir.parent / "_annotations.coco.json",
        data_dir / "train" / "annotations" / "instances_default.json",
        data_dir / "annotations" / "instances_default.json",
        data_dir / "_annotations.coco.json",
    ]
    for coco_path in coco_candidates:
        if not coco_path.exists():
            continue
        try:
            with open(coco_path, "r", encoding="utf-8") as f:
                coco = json.load(f)
            fname = img_path.name
            img_info = next(
                (im for im in coco.get("images", []) if im["file_name"] == fname), None
            )
            if img_info is None:
                continue
            h, w = img_info["height"], img_info["width"]
            mask = np.zeros((h, w), dtype=np.uint8)
            ann_list = [a for a in coco.get("annotations", []) if a["image_id"] == img_info["id"]]
            for ann in ann_list:
                for seg in ann.get("segmentation", []):
                    if len(seg) < 6:
                        continue
                    pts = np.array(seg, dtype=np.float32).reshape(-1, 2).astype(np.int32)
                    import cv2 as _cv2
                    _cv2.fillPoly(mask, [pts], 1)
            return mask
        except Exception:
            continue

    return None


# ---------------------------------------------------------------------------
# YOLO prediction → binary mask
# ---------------------------------------------------------------------------

def _yolo_predict_binary(
    yolo_model,
    img_path: Path,
    img_size: int,
    gt_h: int,
    gt_w: int,
) -> np.ndarray:
    """
    Run YOLO prediction and return a binary mask at gt resolution.

    Merges all instance masks with logical OR.
    Returns all-zero mask if no predictions exist.

    Parameters
    ----------
    yolo_model : YOLO instance
    img_path : Path
    img_size : int
    gt_h, gt_w : int
        Ground-truth mask dimensions (H, W).

    Returns
    -------
    np.ndarray : Binary mask (H, W) uint8 values 0 or 1.
    """
    import cv2

    results = yolo_model.predict(
        source=str(img_path),
        imgsz=img_size,
        verbose=False,
    )

    combined = np.zeros((gt_h, gt_w), dtype=np.uint8)

    for result in results:
        if result.masks is None:
            continue
        for m in result.masks.data:
            m_np = m.cpu().numpy().astype(np.float32)
            m_resized = cv2.resize(m_np, (gt_w, gt_h), interpolation=cv2.INTER_NEAREST)
            combined = np.logical_or(combined, m_resized > 0.5).astype(np.uint8)

    return combined


# ---------------------------------------------------------------------------
# Latency benchmark
# ---------------------------------------------------------------------------

def _benchmark_yolo_latency(
    yolo_model,
    img_path: Path,
    img_size: int,
    warmup: int = WARMUP_ITERATIONS,
    iterations: int = BENCHMARK_ITERATIONS,
) -> Dict:
    """Benchmark YOLO inference latency (forward pass timing only)."""
    import cv2
    import torch

    dummy_img = cv2.imread(str(img_path))
    if dummy_img is None:
        return {
            "mean_latency_ms_per_image": -1.0,
            "median_latency_ms_per_image": -1.0,
            "p95_latency_ms_per_image": -1.0,
            "throughput_fps": -1.0,
        }

    # Warm-up
    for _ in range(warmup):
        yolo_model.predict(source=dummy_img, imgsz=img_size, verbose=False)

    latencies: List[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        yolo_model.predict(source=dummy_img, imgsz=img_size, verbose=False)
        latencies.append((time.perf_counter() - t0) * 1000.0)

    arr = np.array(latencies)
    mean_ms = float(arr.mean())
    return {
        "mean_latency_ms_per_image": round(mean_ms, 3),
        "median_latency_ms_per_image": round(float(np.median(arr)), 3),
        "p95_latency_ms_per_image": round(float(np.percentile(arr, 95)), 3),
        "throughput_fps": round(1000.0 / mean_ms if mean_ms > 0 else 0.0, 2),
    }


# ---------------------------------------------------------------------------
# Helper: environment info
# ---------------------------------------------------------------------------

def _get_ult_version() -> str:
    try:
        import ultralytics
        return ultralytics.__version__
    except Exception:
        return "unknown"


def _get_git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=str(_PROJECT_ROOT),
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _checkpoint_size_mb(path: Path) -> float:
    try:
        return round(path.stat().st_size / (1024 ** 2), 3)
    except Exception:
        return -1.0


def _yolo_param_count(model) -> Tuple[int, int]:
    """Count trainable and total parameters in a YOLO model."""
    try:
        import torch
        total = sum(p.numel() for p in model.model.parameters())
        trainable = sum(p.numel() for p in model.model.parameters() if p.requires_grad)
        return trainable, total
    except Exception:
        return -1, -1


# ---------------------------------------------------------------------------
# Main evaluation function
# ---------------------------------------------------------------------------

def evaluate_yolo_model(
    data_dir: str,
    checkpoint_path: str,
    split: str = "test",
    img_size: int = 256,
    threshold: float = 0.5,
    manifest_path: Optional[str] = None,
    output_path: Optional[str] = None,
    seed: int = 42,
    bootstrap_reps: int = 0,
    device_str: Optional[str] = None,
) -> Dict:
    """
    Evaluate a YOLOv8n-seg checkpoint on the test split.

    Parameters
    ----------
    data_dir : str
    checkpoint_path : str
    split : str
    img_size : int
    threshold : float
        Threshold for binarising combined instance mask probabilities.
    manifest_path : str | None
    output_path : str | None
    seed : int
    bootstrap_reps : int
    device_str : str | None

    Returns
    -------
    dict : Full result dict (same schema as evaluate_smp.py).
    """
    import torch

    try:
        from ultralytics import YOLO
    except ImportError:
        print("[evaluate_yolo] ERROR: ultralytics is not installed.")
        sys.exit(1)

    try:
        import cv2
    except ImportError:
        print("[evaluate_yolo] ERROR: opencv-python is required.")
        sys.exit(1)

    np.random.seed(seed)

    ckpt = Path(checkpoint_path)
    if not ckpt.exists():
        print(f"[evaluate_yolo] ERROR: Checkpoint not found: {checkpoint_path}")
        sys.exit(1)

    data_path = Path(data_dir)
    if not data_path.is_dir():
        print(f"[evaluate_yolo] ERROR: Dataset directory not found: {data_dir}")
        sys.exit(1)

    # ── Load manifest ─────────────────────────────────────────────────
    manifest: Optional[Dict] = None
    if manifest_path and Path(manifest_path).exists():
        manifest = load_manifest(Path(manifest_path))
        print(f"[evaluate_yolo] Loaded manifest: {manifest_path}")
    elif manifest_path:
        print(f"[WARNING] Manifest not found: {manifest_path}")

    # ── Gather test image paths ───────────────────────────────────────
    if manifest is not None:
        test_img_paths = get_split_image_paths(manifest, split, data_dir)
    else:
        # Fall back to scanning split directory
        split_dir = data_path / split
        if not split_dir.is_dir():
            split_dir = data_path
        exts = {".jpg", ".jpeg", ".png", ".bmp"}
        test_img_paths = sorted(p for p in split_dir.rglob("*") if p.suffix.lower() in exts)

    if not test_img_paths:
        print(f"[evaluate_yolo] ERROR: No test images found for split='{split}'.")
        sys.exit(1)

    print(f"[evaluate_yolo] Test samples: {len(test_img_paths)}")

    # ── Load YOLO model ───────────────────────────────────────────────
    yolo = YOLO(str(ckpt))
    if device_str:
        # Ultralytics uses string device specification
        pass  # Device is set per-prediction call if needed

    trainable_params, total_params = _yolo_param_count(yolo)

    # ── Evaluate ──────────────────────────────────────────────────────
    acc = SegmentationMetricsAccumulator(threshold=0.5, track_per_image=True)
    # Note: threshold=0.5 for YOLO binary mask combination; the YOLO
    # instance masks are already probability maps from the model.

    per_image_meta: List[Dict] = []

    for img_path in test_img_paths:
        # Load ground truth
        gt_mask = _find_gt_mask(img_path, data_path, None)
        if gt_mask is None:
            print(f"[evaluate_yolo] WARNING: No GT mask for {img_path.name}, skipping.")
            continue

        gt_h, gt_w = gt_mask.shape

        # YOLO prediction
        pred_binary = _yolo_predict_binary(yolo, img_path, img_size, gt_h, gt_w)

        # Convert to torch tensors (B=1, H, W)
        pred_t = torch.from_numpy(pred_binary).unsqueeze(0).float()
        gt_t = torch.from_numpy(gt_mask).unsqueeze(0).float()

        acc.update_from_binary(pred_t, gt_t)
        per_image_meta.append({"image": img_path.name})

    if acc.n_images == 0:
        print("[evaluate_yolo] ERROR: No images were successfully evaluated.")
        sys.exit(1)

    metrics = acc.result()

    # ── Bootstrap CI ─────────────────────────────────────────────────
    bootstrap_results: Dict = {}
    if bootstrap_reps > 0:
        print(f"[evaluate_yolo] Bootstrap CI ({bootstrap_reps} reps) …")
        bootstrap_results = acc.bootstrap_ci(n_repetitions=bootstrap_reps, seed=seed)

    # ── Latency benchmark ─────────────────────────────────────────────
    print("[evaluate_yolo] Benchmarking latency …")
    # Use first available test image for benchmark
    bench_img = test_img_paths[0]
    latency_info = _benchmark_yolo_latency(yolo, bench_img, img_size)

    # ── Build result dict ─────────────────────────────────────────────
    import datetime as _dt

    result: Dict = {
        "model_name":                "YOLOv8n-seg",
        "architecture":              "yolov8n-seg",
        "encoder":                   "YOLOv8n (CSPDarknet)",
        "checkpoint_path":           str(ckpt.resolve()),
        "dataset_path":              str(data_path.resolve()),
        "split_name":                split,
        "split_manifest_path":       str(Path(manifest_path).resolve()) if manifest_path else None,
        "number_of_test_images":     metrics["n_images"],
        "image_size":                img_size,
        "threshold":                 threshold,
        # Metrics
        "Dice":                      round(metrics["dice"], 6),
        "IoU":                       round(metrics["iou"], 6),
        "Precision":                 round(metrics["precision"], 6),
        "Recall":                    round(metrics["recall"], 6),
        "Pixel Accuracy":            round(metrics["pixel_accuracy"], 6),
        "TP":                        metrics["tp"],
        "FP":                        metrics["fp"],
        "FN":                        metrics["fn"],
        "TN":                        metrics["tn"],
        # Per-image stats
        "per_image_dice_mean":       round(metrics.get("per_image_dice_mean", -1.0), 6),
        "per_image_dice_std":        round(metrics.get("per_image_dice_std", -1.0), 6),
        "per_image_iou_mean":        round(metrics.get("per_image_iou_mean", -1.0), 6),
        "per_image_iou_std":         round(metrics.get("per_image_iou_std", -1.0), 6),
        # Bootstrap CIs
        "bootstrap_ci_95":           bootstrap_results,
        # Model complexity
        "trainable_parameter_count": trainable_params,
        "total_parameter_count":     total_params,
        "checkpoint_size_mb":        _checkpoint_size_mb(ckpt),
        "model_state_dict_size_mb":  -1.0,  # not applicable for .pt YOLO format
        # Latency
        "mean_latency_ms_per_image":   latency_info["mean_latency_ms_per_image"],
        "median_latency_ms_per_image": latency_info["median_latency_ms_per_image"],
        "p95_latency_ms_per_image":    latency_info["p95_latency_ms_per_image"],
        "throughput_fps":              latency_info["throughput_fps"],
        "warmup_iterations":           WARMUP_ITERATIONS,
        "benchmark_iterations":        BENCHMARK_ITERATIONS,
        # Hardware / environment
        "peak_gpu_memory_mb":        -1.0,
        "device_name":               platform.processor(),
        "device_type":               "cpu",
        "PyTorch_version":           __import__("torch").__version__,
        "ultralytics_version":       _get_ult_version(),
        "Python_version":            sys.version,
        "seed":                      seed,
        "timestamp":                 _dt.datetime.now(tz=_dt.timezone.utc).isoformat(),
        "git_commit_sha":            _get_git_sha(),
        # Per-image records
        "per_image_records":         acc.per_image_records,
        "per_image_meta":            per_image_meta,
        # Notes
        "notes": (
            "YOLO uses Ultralytics native compound segmentation loss "
            "(NOT BCE + DiceLoss).  Final metrics use the same "
            "SegmentationMetricsAccumulator as the SMP models."
        ),
    }

    # ── Save JSON ─────────────────────────────────────────────────────
    if output_path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"[evaluate_yolo] Result saved → {out_file}")

    # ── Print summary ─────────────────────────────────────────────────
    print(
        f"\n{'─'*55}\n"
        f"  YOLOv8n-seg\n"
        f"{'─'*55}\n"
        f"  Dice      : {result['Dice']:.4f}\n"
        f"  IoU       : {result['IoU']:.4f}\n"
        f"  Precision : {result['Precision']:.4f}\n"
        f"  Recall    : {result['Recall']:.4f}\n"
        f"  PixelAcc  : {result['Pixel Accuracy']:.4f}\n"
        f"  Params    : {result['trainable_parameter_count']:,} trainable\n"
        f"  Latency   : {result['mean_latency_ms_per_image']:.2f} ms/img  "
        f"({result['throughput_fps']:.1f} FPS)\n"
        f"{'─'*55}"
    )

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate YOLOv8n-seg tongue segmentation checkpoint (RQ1).\n\n"
            "Uses the same SegmentationMetricsAccumulator as evaluate_smp.py\n"
            "so results are directly comparable across all four models."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--data-dir",    required=True, help="Dataset root directory.")
    parser.add_argument("--checkpoint",  required=True, help="Path to YOLO best.pt.")
    parser.add_argument("--split",       default="test")
    parser.add_argument("--img-size",    type=int,   default=256)
    parser.add_argument("--threshold",   type=float, default=0.5)
    parser.add_argument(
        "--split-manifest",
        default="outputs/acm_paper/rq1/split_manifest.json",
    )
    parser.add_argument("--output",      default=None)
    parser.add_argument("--seed",        type=int,   default=42)
    parser.add_argument("--device",      default=None)
    parser.add_argument("--bootstrap-repetitions", type=int, default=0)
    args = parser.parse_args()

    if args.output is None:
        out_dir = Path("outputs/acm_paper/rq1")
        out_dir.mkdir(parents=True, exist_ok=True)
        args.output = str(out_dir / "yolov8n_seg.json")

    evaluate_yolo_model(
        data_dir=args.data_dir,
        checkpoint_path=args.checkpoint,
        split=args.split,
        img_size=args.img_size,
        threshold=args.threshold,
        manifest_path=args.split_manifest,
        output_path=args.output,
        seed=args.seed,
        bootstrap_reps=args.bootstrap_repetitions,
        device_str=args.device,
    )


if __name__ == "__main__":
    main()
