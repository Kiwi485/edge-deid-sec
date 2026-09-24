"""
benchmark_edge_deployment.py — ACM Paper RQ2: Edge Deployment Performance
==========================================================================
Measures real deployment cost of a trained SMP segmentation checkpoint
(U-Net + MobileNetV2 or U-Net + ResNet34) by running CPU-only inference
over real dataset images and recording:

  - Per-image inference latency (mean / median / min / max / std / p95)
  - Throughput (FPS, images/minute)
  - Peak process memory (RSS, via psutil; ru_maxrss via resource on POSIX)
  - Average process CPU usage (%, normalised to the cores actually
    available to this process)
  - Model checkpoint size on disk
  - Model load time
  - Total wall-clock runtime

This script does NOT compute segmentation accuracy (Dice/IoU) — that is
handled by ``evaluate_smp.py`` (RQ1) on the same checkpoints. Accuracy and
deployment-cost measurement are kept separate so each script has one job.

CPU/RAM constraints for "Environment A / B" are enforced *externally*
(e.g. ``systemd-run --scope -p CPUQuota=200% -p MemoryMax=2048M`` inside
WSL2, or plain execution for the unconstrained Desktop baseline). This
script only *records* what it can see about its own runtime environment
(``--environment-label``, detected CPU affinity, torch thread count).

Usage
-----
::

    python -m experiments.acm_paper.rq2_edge_deployment.benchmark_edge_deployment \\
        --data-dir acmpaper_data \\
        --arch unet_mobilenet \\
        --checkpoint models/acm_paper/rq1/unet_mobilenet/best.pth \\
        --split-manifest outputs/acm_paper/rq1/split_manifest.json \\
        --image-split all \\
        --img-size 256 \\
        --torch-threads 2 \\
        --environment-label vm_a_2c2g \\
        --output outputs/acm_paper/rq2/unet_mobilenet_vm_a.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import psutil

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

ARCH_DISPLAY_NAMES = {
    "unet_mobilenet": "U-Net + MobileNetV2",
    "unet_resnet": "U-Net + ResNet34",
    "deeplabv3": "DeepLabV3+ + ResNet50",
}

DEFAULT_RESULTS_CSV = "outputs/acm_paper/rq2/results.csv"
CSV_FIELDS = [
    "model_name", "architecture", "environment_label",
    "n_images", "mean_latency_ms", "median_latency_ms", "min_latency_ms",
    "max_latency_ms", "std_latency_ms", "p95_latency_ms",
    "throughput_fps", "images_per_minute",
    "peak_rss_mb", "peak_rss_mb_rusage", "avg_cpu_percent_normalized",
    "avg_cpu_percent_raw", "checkpoint_size_mb", "model_load_time_ms",
    "total_runtime_s", "cpu_affinity_count", "torch_threads", "repeat_index",
    "timestamp", "git_commit_sha",
]


def _get_git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=str(_PROJECT_ROOT),
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _checkpoint_size_mb(path: Path) -> float:
    try:
        return round(path.stat().st_size / (1024 ** 2), 3)
    except Exception:
        return -1.0


def _peak_rss_rusage_mb() -> float:
    """Kernel-reported peak RSS via getrusage (POSIX only, e.g. WSL)."""
    try:
        import resource
        ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux reports KB; macOS reports bytes.
        return round(ru / 1024.0, 2) if platform.system() == "Linux" else round(ru / (1024.0 ** 2), 2)
    except Exception:
        return -1.0


def _allowed_cpu_count(proc: psutil.Process) -> int:
    try:
        aff = proc.cpu_affinity()
        if aff:
            return len(aff)
    except Exception:
        pass
    return os.cpu_count() or 1


def load_checkpoint(checkpoint_path: Path, model, device) -> Dict:
    import torch
    raw = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if isinstance(raw, dict) and "model_state_dict" in raw:
        model.load_state_dict(raw["model_state_dict"])
        return raw
    model.load_state_dict(raw)
    return {}


def build_image_list(
    data_dir: str,
    arch: str,
    img_size: int,
    manifest_path: Optional[str],
    image_split: str,
    max_images: Optional[int],
):
    from src.seg.dataset import TongueSegDataset
    from experiments.acm_paper.rq1_model_selection.dataset_split import (
        load_manifest, get_split_indices_for_dataset,
    )

    data_path = Path(data_dir)
    if (data_path / "train").is_dir():
        src_split = "train"
    elif (data_path / "valid").is_dir():
        src_split = "valid"
    elif (data_path / "val").is_dir():
        src_split = "val"
    else:
        src_split = ""

    full_ds = TongueSegDataset(data_dir, split=src_split, img_size=img_size, is_train=False)

    if image_split == "all" or not manifest_path or not Path(manifest_path).exists():
        indices = list(range(len(full_ds)))
    else:
        manifest = load_manifest(Path(manifest_path))
        indices = get_split_indices_for_dataset(manifest, full_ds._samples, image_split, data_path)
        if not indices:
            print(f"[WARNING] No images for image-split='{image_split}'; falling back to all images.")
            indices = list(range(len(full_ds)))

    if max_images is not None:
        indices = indices[:max_images]

    return full_ds, indices


def run_benchmark(
    data_dir: str,
    arch: str,
    checkpoint_path: str,
    environment_label: str,
    img_size: int = 256,
    image_split: str = "all",
    max_images: Optional[int] = None,
    warmup_images: int = 10,
    manifest_path: Optional[str] = "outputs/acm_paper/rq1/split_manifest.json",
    torch_threads: Optional[int] = None,
    output_path: Optional[str] = None,
    results_csv: str = DEFAULT_RESULTS_CSV,
    seed: int = 42,
    repeat_index: int = 1,
) -> Dict:
    total_start = time.perf_counter()

    import torch
    torch.manual_seed(seed)
    np.random.seed(seed)

    if torch_threads:
        torch.set_num_threads(torch_threads)

    device = torch.device("cpu")
    proc = psutil.Process()
    cpu_count_allowed = _allowed_cpu_count(proc)

    from src.seg.model import build_model_by_arch, count_parameters

    ckpt_path = Path(checkpoint_path)
    if not ckpt_path.exists():
        print(f"[ERROR] Checkpoint not found: {checkpoint_path}")
        sys.exit(1)

    data_path = Path(data_dir)
    if not data_path.is_dir():
        print(f"[ERROR] Dataset directory not found: {data_dir}")
        sys.exit(1)

    # ── Model load (timed) ──────────────────────────────────────────────
    load_start = time.perf_counter()
    model = build_model_by_arch(arch, encoder_weights=None).to(device)
    ckpt_raw = load_checkpoint(ckpt_path, model, device)
    model.eval()
    load_time_ms = (time.perf_counter() - load_start) * 1000.0

    trainable_params = count_parameters(model)

    # ── Build image list ────────────────────────────────────────────────
    full_ds, indices = build_image_list(
        data_dir, arch, img_size, manifest_path, image_split, max_images
    )
    if not indices:
        print(f"[ERROR] No images available for benchmarking.")
        sys.exit(1)
    print(f"[benchmark] {ARCH_DISPLAY_NAMES.get(arch, arch)} | env={environment_label} | "
          f"images={len(indices)} (split='{image_split}') | torch_threads={torch.get_num_threads()} | "
          f"cpu_affinity={cpu_count_allowed}")

    # ── Warm-up (not timed) ─────────────────────────────────────────────
    n_warmup = min(warmup_images, len(indices))
    with torch.no_grad():
        for i in range(n_warmup):
            img, _ = full_ds[indices[i % len(indices)]]
            _ = model(img.unsqueeze(0).to(device))

    # ── Timed inference loop ────────────────────────────────────────────
    proc.cpu_percent(interval=None)  # prime the internal counter (first call is meaningless)
    latencies_ms: List[float] = []
    cpu_samples: List[float] = []
    rss_samples_mb: List[float] = [proc.memory_info().rss / (1024 ** 2)]

    with torch.no_grad():
        for idx in indices:
            img, _ = full_ds[idx]
            img = img.unsqueeze(0).to(device)

            t0 = time.perf_counter()
            _ = model(img)
            t1 = time.perf_counter()

            latencies_ms.append((t1 - t0) * 1000.0)
            cpu_samples.append(proc.cpu_percent(interval=None))
            rss_samples_mb.append(proc.memory_info().rss / (1024 ** 2))

    total_runtime_s = time.perf_counter() - total_start

    arr = np.array(latencies_ms)
    mean_ms = float(arr.mean())
    peak_rss_mb = float(max(rss_samples_mb))
    peak_rss_rusage_mb = _peak_rss_rusage_mb()
    avg_cpu_raw = float(np.mean(cpu_samples)) if cpu_samples else 0.0
    avg_cpu_normalized = avg_cpu_raw / cpu_count_allowed if cpu_count_allowed else avg_cpu_raw

    result: Dict = {
        "model_name": ARCH_DISPLAY_NAMES.get(arch, arch),
        "architecture": arch,
        "environment_label": environment_label,
        "checkpoint_path": str(ckpt_path.resolve()),
        "dataset_path": str(data_path.resolve()),
        "image_split": image_split,
        "n_images": len(indices),
        "img_size": img_size,
        "warmup_images": n_warmup,
        "repeat_index": repeat_index,

        "mean_latency_ms": round(mean_ms, 3),
        "median_latency_ms": round(float(np.median(arr)), 3),
        "min_latency_ms": round(float(arr.min()), 3),
        "max_latency_ms": round(float(arr.max()), 3),
        "std_latency_ms": round(float(arr.std()), 3),
        "p95_latency_ms": round(float(np.percentile(arr, 95)), 3),

        "throughput_fps": round(1000.0 / mean_ms, 2) if mean_ms > 0 else 0.0,
        "images_per_minute": round(60000.0 / mean_ms, 1) if mean_ms > 0 else 0.0,

        "peak_rss_mb": round(peak_rss_mb, 2),
        "peak_rss_mb_rusage": peak_rss_rusage_mb,
        "avg_cpu_percent_raw": round(avg_cpu_raw, 2),
        "avg_cpu_percent_normalized": round(avg_cpu_normalized, 2),
        "cpu_affinity_count": cpu_count_allowed,
        "torch_threads": torch.get_num_threads(),

        "trainable_parameter_count": trainable_params,
        "checkpoint_size_mb": _checkpoint_size_mb(ckpt_path),
        "model_load_time_ms": round(load_time_ms, 3),
        "total_runtime_s": round(total_runtime_s, 3),

        "checkpoint_epoch": ckpt_raw.get("epoch", None),
        "checkpoint_val_dice": ckpt_raw.get("val_dice", None),

        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "torch_version": torch.__version__,
        "timestamp": __import__("datetime").datetime.now(
            tz=__import__("datetime").timezone.utc
        ).isoformat(),
        "git_commit_sha": _get_git_sha(),

        "per_image_latency_ms": latencies_ms,
    }

    print(
        f"\n{'─'*60}\n"
        f"  {result['model_name']}  [{environment_label}]\n"
        f"{'─'*60}\n"
        f"  Mean latency : {result['mean_latency_ms']:.2f} ms/img "
        f"({result['throughput_fps']:.2f} FPS)\n"
        f"  Peak RSS     : {result['peak_rss_mb']:.1f} MB\n"
        f"  Avg CPU      : {result['avg_cpu_percent_normalized']:.1f}% "
        f"(of {cpu_count_allowed} allowed cores)\n"
        f"  Model size   : {result['checkpoint_size_mb']:.2f} MB\n"
        f"  Load time    : {result['model_load_time_ms']:.1f} ms\n"
        f"{'─'*60}"
    )

    if output_path:
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"[benchmark] Result saved -> {out_file}")

    _append_csv_row(results_csv, result)

    return result


def _append_csv_row(csv_path: str, result: Dict) -> None:
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow({k: result.get(k) for k in CSV_FIELDS})
    print(f"[benchmark] Row appended -> {path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RQ2: Benchmark edge-deployment cost of a trained SMP model.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--arch", required=True, choices=list(ARCH_DISPLAY_NAMES.keys()))
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--environment-label", required=True,
                         help="e.g. desktop | vm_a_2c2g | vm_b_4c4g")
    parser.add_argument("--img-size", type=int, default=256)
    parser.add_argument("--image-split", default="all", choices=["all", "train", "val", "test"],
                         help="'all' = every image (100), used for pure runtime/memory/CPU "
                              "measurement (no accuracy leakage concern). Use 'test' to restrict "
                              "to the held-out split.")
    parser.add_argument("--max-images", type=int, default=None)
    parser.add_argument("--warmup-images", type=int, default=10)
    parser.add_argument("--split-manifest", default="outputs/acm_paper/rq1/split_manifest.json")
    parser.add_argument("--torch-threads", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--repeat-index", type=int, default=1,
                         help="Which repetition this run is (metadata only, for mean/std across "
                              "repeated runs of the same config).")
    parser.add_argument("--output", default=None)
    parser.add_argument("--results-csv", default=DEFAULT_RESULTS_CSV)
    args = parser.parse_args()

    if args.output is None:
        out_dir = Path("outputs/acm_paper/rq2")
        out_dir.mkdir(parents=True, exist_ok=True)
        args.output = str(out_dir / f"{args.arch}_{args.environment_label}_r{args.repeat_index}.json")

    run_benchmark(
        data_dir=args.data_dir,
        arch=args.arch,
        checkpoint_path=args.checkpoint,
        environment_label=args.environment_label,
        img_size=args.img_size,
        image_split=args.image_split,
        max_images=args.max_images,
        warmup_images=args.warmup_images,
        manifest_path=args.split_manifest,
        torch_threads=args.torch_threads,
        output_path=args.output,
        results_csv=args.results_csv,
        seed=args.seed,
        repeat_index=args.repeat_index,
    )


if __name__ == "__main__":
    main()
