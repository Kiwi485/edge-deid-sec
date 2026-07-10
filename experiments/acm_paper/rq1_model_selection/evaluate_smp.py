"""
evaluate_smp.py — ACM Paper RQ1: Evaluate SMP-based Segmentation Models
========================================================================
Evaluates one of the three segmentation_models_pytorch (SMP) models:

  - U-Net + MobileNetV2  (arch: unet_mobilenet)
  - U-Net + ResNet34     (arch: unet_resnet)
  - DeepLabV3+ + ResNet50 (arch: deeplabv3)

Final metrics are computed from the **held-out test set** using the
authoritative :class:`SegmentationMetricsAccumulator` from ``metrics.py``.

IMPORTANT
---------
- Do NOT use test results to select checkpoints.
- Do NOT use test results to tune the decision threshold.
- Checkpoint selection MUST be based on validation Dice only.

Outputs
-------
A JSON file at ``--output`` containing model metadata, hardware info,
metric results, latency statistics, and per-image records.

Usage
-----
::

    python -m experiments.acm_paper.rq1_model_selection.evaluate_smp \\
        --data-dir DATASET_PATH \\
        --arch unet_mobilenet \\
        --checkpoint models/acm_paper/rq1/unet_mobilenet/best.pth \\
        --split test \\
        --img-size 256 \\
        --batch-size 8 \\
        --threshold 0.5 \\
        --split-manifest outputs/acm_paper/rq1/split_manifest.json \\
        --output outputs/acm_paper/rq1/unet_mobilenet.json
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
from typing import Dict, List, Optional

import numpy as np
import torch
from torch.utils.data import DataLoader, Subset

# ---------------------------------------------------------------------------
# Allow running as python -m experiments.acm_paper.rq1_model_selection.evaluate_smp
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from src.seg.dataset import TongueSegDataset
    from src.seg.model import build_model_by_arch, count_parameters, ARCH_CHOICES
except ImportError as e:
    print(f"[ERROR] Cannot import from src.seg: {e}")
    print("Make sure to run from the project root directory.")
    sys.exit(1)

from experiments.acm_paper.rq1_model_selection.metrics import SegmentationMetricsAccumulator
from experiments.acm_paper.rq1_model_selection.dataset_split import (
    load_manifest,
    get_split_indices_for_dataset,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARCH_DISPLAY_NAMES = {
    "unet_mobilenet": "U-Net + MobileNetV2",
    "unet_resnet":    "U-Net + ResNet34",
    "deeplabv3":      "DeepLabV3+ + ResNet50",
}
ARCH_ENCODERS = {
    "unet_mobilenet": "mobilenet_v2",
    "unet_resnet":    "resnet34",
    "deeplabv3":      "resnet50",
}

WARMUP_ITERATIONS = 10
BENCHMARK_ITERATIONS = 100


# ---------------------------------------------------------------------------
# Checkpoint loading
# ---------------------------------------------------------------------------

def load_checkpoint(checkpoint_path: Path, model: torch.nn.Module, device: torch.device) -> Dict:
    """
    Load a checkpoint into model.  Handles both raw state-dict and
    wrapped dicts (produced by run_rq1.py or src/seg/train.py).

    Returns the raw checkpoint dict.
    """
    raw = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if isinstance(raw, dict) and "model_state_dict" in raw:
        model.load_state_dict(raw["model_state_dict"])
        return raw
    else:
        # Assume the file IS the state dict
        model.load_state_dict(raw)
        return {}


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def build_test_dataset(
    data_dir: str,
    split: str,
    img_size: int,
    manifest: Optional[Dict],
) -> TongueSegDataset:
    """
    Build a TongueSegDataset for the specified split.

    If a manifest is provided, only the samples assigned to ``split`` are
    included (ensuring identical test sets across all models).
    Otherwise the split directory is loaded directly.
    """
    data_path = Path(data_dir)

    # If a manifest is provided, use it to filter images — load from whatever
    # source directory actually exists (train/, or flat), then restrict to
    # the manifest's assigned split.  This avoids requiring a physical test/
    # or valid/ directory in the dataset.
    if manifest is not None:
        # Determine which source directory to load all samples from
        if (data_path / "train").is_dir():
            src_split = "train"
        elif (data_path / "valid").is_dir():
            src_split = "valid"
        elif (data_path / "val").is_dir():
            src_split = "val"
        else:
            src_split = ""  # flat

        full_ds = TongueSegDataset(
            data_dir,
            split=src_split,
            img_size=img_size,
            is_train=False,
        )

        indices = get_split_indices_for_dataset(
            manifest,
            full_ds._samples,
            split,
            data_path,
        )
        if not indices:
            print(
                f"[WARNING] Manifest has no entries for split='{split}' in {data_dir}.\n"
                f"          Falling back to loading full source split '{src_split}'."
            )
            return full_ds

        print(f"[evaluate_smp] Manifest filtered: {len(indices)} images for split='{split}'")
        return TongueSegDataset(
            data_dir,
            split=src_split,
            img_size=img_size,
            is_train=False,
            indices=indices,
        )

    # No manifest — determine split directory name and load directly
    if split in ("val", "valid"):
        src_split = "valid" if (data_path / "valid").is_dir() else "val"
    else:
        src_split = split

    full_ds = TongueSegDataset(
        data_dir,
        split=src_split,
        img_size=img_size,
        is_train=False,
    )
    return full_ds


# ---------------------------------------------------------------------------
# Latency benchmark
# ---------------------------------------------------------------------------

def benchmark_latency(
    model: torch.nn.Module,
    device: torch.device,
    img_size: int,
    warmup: int = WARMUP_ITERATIONS,
    iterations: int = BENCHMARK_ITERATIONS,
) -> Dict[str, float]:
    """
    Benchmark model inference latency (image tensor → logits only).

    Does NOT include image decoding, disk I/O, or metric computation.

    Parameters
    ----------
    model : torch.nn.Module
    device : torch.device
    img_size : int
        Spatial resolution (square).
    warmup : int
        Warm-up forward passes (not timed).
    iterations : int
        Number of timed forward passes.

    Returns
    -------
    dict with keys:
        mean_latency_ms, median_latency_ms, p95_latency_ms, throughput_fps,
        device_type, warmup_iterations, benchmark_iterations
    """
    model.eval()
    dummy = torch.randn(1, 3, img_size, img_size, device=device)

    # Warm-up
    with torch.no_grad():
        for _ in range(warmup):
            _ = model(dummy)
            if device.type == "cuda":
                torch.cuda.synchronize()

    # Timed runs
    latencies_ms: List[float] = []
    with torch.no_grad():
        for _ in range(iterations):
            if device.type == "cuda":
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            _ = model(dummy)
            if device.type == "cuda":
                torch.cuda.synchronize()
            latencies_ms.append((time.perf_counter() - t0) * 1000.0)

    arr = np.array(latencies_ms)
    mean_ms = float(arr.mean())
    return {
        "mean_latency_ms_per_image": mean_ms,
        "median_latency_ms_per_image": float(np.median(arr)),
        "p95_latency_ms_per_image": float(np.percentile(arr, 95)),
        "throughput_fps": float(1000.0 / mean_ms) if mean_ms > 0 else 0.0,
        "device_type": device.type,
        "warmup_iterations": warmup,
        "benchmark_iterations": iterations,
    }


# ---------------------------------------------------------------------------
# Environment info helpers
# ---------------------------------------------------------------------------

def _get_smp_version() -> str:
    try:
        import segmentation_models_pytorch as smp
        return smp.__version__
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


def _state_dict_size_mb(model: torch.nn.Module) -> float:
    """Estimate the in-memory size of the model state dict in MB."""
    try:
        total_bytes = sum(
            p.numel() * p.element_size()
            for p in model.state_dict().values()
        )
        return round(total_bytes / (1024 ** 2), 3)
    except Exception:
        return -1.0


# ---------------------------------------------------------------------------
# Main evaluation function
# ---------------------------------------------------------------------------

@torch.no_grad()
def evaluate_model(
    data_dir: str,
    arch: str,
    checkpoint_path: str,
    split: str = "test",
    img_size: int = 256,
    batch_size: int = 8,
    threshold: float = 0.5,
    manifest_path: Optional[str] = None,
    output_path: Optional[str] = None,
    device_str: Optional[str] = None,
    seed: int = 42,
    num_workers: int = 0,
    bootstrap_reps: int = 0,
) -> Dict:
    """
    Evaluate an SMP segmentation model on the test split.

    Parameters
    ----------
    data_dir : str
    arch : str
        "unet_mobilenet" | "unet_resnet" | "deeplabv3"
    checkpoint_path : str
    split : str
        Which split to evaluate on (should be "test" for final results).
    img_size : int
    batch_size : int
    threshold : float
    manifest_path : str | None
    output_path : str | None
        Where to save the JSON result.
    device_str : str | None
    seed : int
    num_workers : int
    bootstrap_reps : int
        Number of bootstrap repetitions for CI (0 = disabled).

    Returns
    -------
    dict : Full result dict.
    """
    import torch

    # Seed
    torch.manual_seed(seed)
    np.random.seed(seed)

    # Device
    if device_str:
        device = torch.device(device_str)
    else:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print(f"[evaluate_smp] Device: {device}")

    # ── Load manifest ─────────────────────────────────────────────────
    manifest: Optional[Dict] = None
    if manifest_path and Path(manifest_path).exists():
        manifest = load_manifest(Path(manifest_path))
        print(f"[evaluate_smp] Loaded manifest: {manifest_path}")
    elif manifest_path:
        print(f"[WARNING] Manifest not found: {manifest_path}  (evaluating full split)")

    # ── Dataset ───────────────────────────────────────────────────────
    ckpt_path = Path(checkpoint_path)
    if not ckpt_path.exists():
        print(f"[ERROR] Checkpoint not found: {checkpoint_path}")
        sys.exit(1)

    data_path = Path(data_dir)
    if not data_path.is_dir():
        print(f"[ERROR] Dataset directory not found: {data_dir}")
        sys.exit(1)

    test_ds = build_test_dataset(data_dir, split, img_size, manifest)
    if len(test_ds) == 0:
        print(f"[ERROR] No images found for split='{split}' in {data_dir}")
        sys.exit(1)

    test_loader = DataLoader(
        test_ds,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=(device.type == "cuda"),
    )
    print(f"[evaluate_smp] Test samples: {len(test_ds)}")

    # ── Model ─────────────────────────────────────────────────────────
    model = build_model_by_arch(arch, encoder_weights=None).to(device)
    ckpt_raw = load_checkpoint(ckpt_path, model, device)
    model.eval()

    trainable_params = count_parameters(model)
    total_params = trainable_params

    # ── Evaluation ────────────────────────────────────────────────────
    acc = SegmentationMetricsAccumulator(threshold=threshold, track_per_image=True)

    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)

    for imgs, masks in test_loader:
        imgs = imgs.to(device)
        logits = model(imgs)
        acc.update_from_logits(logits.cpu(), masks)

    metrics = acc.result()

    # ── Peak GPU memory ───────────────────────────────────────────────
    peak_gpu_mb: float = -1.0
    if device.type == "cuda":
        peak_gpu_mb = round(
            torch.cuda.max_memory_allocated(device) / (1024 ** 2), 2
        )

    # ── Latency benchmark ─────────────────────────────────────────────
    print("[evaluate_smp] Benchmarking latency …")
    latency_info = benchmark_latency(model, device, img_size)

    # ── Bootstrap CI (optional) ───────────────────────────────────────
    bootstrap_results: Dict = {}
    if bootstrap_reps > 0:
        print(f"[evaluate_smp] Bootstrap CI ({bootstrap_reps} reps) …")
        bootstrap_results = acc.bootstrap_ci(n_repetitions=bootstrap_reps, seed=seed)

    # ── Build result dict ─────────────────────────────────────────────
    result: Dict = {
        # Identification
        "model_name":         ARCH_DISPLAY_NAMES.get(arch, arch),
        "architecture":       arch,
        "encoder":            ARCH_ENCODERS.get(arch, "unknown"),
        "checkpoint_path":    str(ckpt_path.resolve()),
        "dataset_path":       str(data_path.resolve()),
        "split_name":         split,
        "split_manifest_path": str(Path(manifest_path).resolve()) if manifest_path else None,
        "number_of_test_images": metrics["n_images"],
        "image_size":         img_size,
        "threshold":          threshold,
        # Metrics (global micro-averaged from full test set)
        "Dice":               round(metrics["dice"], 6),
        "IoU":                round(metrics["iou"], 6),
        "Precision":          round(metrics["precision"], 6),
        "Recall":             round(metrics["recall"], 6),
        "Pixel Accuracy":     round(metrics["pixel_accuracy"], 6),
        "TP":                 metrics["tp"],
        "FP":                 metrics["fp"],
        "FN":                 metrics["fn"],
        "TN":                 metrics["tn"],
        # Per-image stats
        "per_image_dice_mean":         round(metrics.get("per_image_dice_mean", -1.0), 6),
        "per_image_dice_std":          round(metrics.get("per_image_dice_std", -1.0), 6),
        "per_image_iou_mean":          round(metrics.get("per_image_iou_mean", -1.0), 6),
        "per_image_iou_std":           round(metrics.get("per_image_iou_std", -1.0), 6),
        # Bootstrap CIs (empty if not requested)
        "bootstrap_ci_95":    bootstrap_results,
        # Model complexity
        "trainable_parameter_count": trainable_params,
        "total_parameter_count":     total_params,
        "checkpoint_size_mb":        _checkpoint_size_mb(ckpt_path),
        "model_state_dict_size_mb":  _state_dict_size_mb(model),
        # Latency
        "mean_latency_ms_per_image":   round(latency_info["mean_latency_ms_per_image"], 3),
        "median_latency_ms_per_image": round(latency_info["median_latency_ms_per_image"], 3),
        "p95_latency_ms_per_image":    round(latency_info["p95_latency_ms_per_image"], 3),
        "throughput_fps":              round(latency_info["throughput_fps"], 2),
        "warmup_iterations":           latency_info["warmup_iterations"],
        "benchmark_iterations":        latency_info["benchmark_iterations"],
        # Hardware / environment
        "peak_gpu_memory_mb": peak_gpu_mb,
        "device_name":        (
            torch.cuda.get_device_name(device)
            if device.type == "cuda"
            else platform.processor()
        ),
        "device_type": device.type,
        "PyTorch_version":             torch.__version__,
        "segmentation_models_pytorch_version": _get_smp_version(),
        "Python_version":              sys.version,
        "seed":                        seed,
        "timestamp":                   __import__("datetime").datetime.now(
            tz=__import__("datetime").timezone.utc
        ).isoformat(),
        "git_commit_sha":              _get_git_sha(),
        # Per-image records (for external bootstrap / CI tools)
        "per_image_records": acc.per_image_records,
        # Training metadata from checkpoint (if available)
        "checkpoint_epoch":            ckpt_raw.get("epoch", None),
        "checkpoint_val_dice":         ckpt_raw.get("val_dice", None),
    }

    # ── Save JSON ─────────────────────────────────────────────────────
    if output_path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"[evaluate_smp] Result saved → {out_file}")

    # ── Print summary ─────────────────────────────────────────────────
    print(
        f"\n{'─'*55}\n"
        f"  {result['model_name']}\n"
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
        description="Evaluate an SMP tongue segmentation model (RQ1).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--data-dir",      required=True, help="Dataset root directory.")
    parser.add_argument("--arch",          required=True, choices=ARCH_CHOICES,
                        help="Model architecture.")
    parser.add_argument("--checkpoint",    required=True, help="Path to best.pth checkpoint.")
    parser.add_argument("--split",         default="test",
                        help="Dataset split to evaluate on (should be 'test').")
    parser.add_argument("--img-size",      type=int,   default=256)
    parser.add_argument("--batch-size",    type=int,   default=8)
    parser.add_argument("--threshold",     type=float, default=0.5)
    parser.add_argument("--split-manifest",
                        default="outputs/acm_paper/rq1/split_manifest.json",
                        help="Path to the fixed split manifest JSON.")
    parser.add_argument("--output",
                        default=None,
                        help="Path to save JSON result (auto-named if omitted).")
    parser.add_argument("--device",        default=None,
                        help="Device ('cpu', 'cuda', 'cuda:0', …).")
    parser.add_argument("--seed",          type=int,   default=42)
    parser.add_argument("--num-workers",   type=int,   default=0)
    parser.add_argument("--bootstrap-repetitions", type=int, default=0,
                        help="Bootstrap CI repetitions (0 = disabled).")
    args = parser.parse_args()

    if args.output is None:
        out_dir = Path("outputs/acm_paper/rq1")
        out_dir.mkdir(parents=True, exist_ok=True)
        args.output = str(out_dir / f"{args.arch}.json")

    evaluate_model(
        data_dir=args.data_dir,
        arch=args.arch,
        checkpoint_path=args.checkpoint,
        split=args.split,
        img_size=args.img_size,
        batch_size=args.batch_size,
        threshold=args.threshold,
        manifest_path=args.split_manifest,
        output_path=args.output,
        device_str=args.device,
        seed=args.seed,
        num_workers=args.num_workers,
        bootstrap_reps=args.bootstrap_repetitions,
    )


if __name__ == "__main__":
    main()
