"""
run_rq1.py — ACM Paper RQ1: Unified Experiment Runner
======================================================
Orchestrates the full RQ1 "Model Selection for Edge-Based Tongue
Segmentation" experiment.

Models compared
---------------
1. U-Net + MobileNetV2   (arch: unet_mobilenet)
2. U-Net + ResNet34      (arch: unet_resnet)
3. DeepLabV3+ + ResNet50 (arch: deeplabv3)
4. YOLOv8n-seg           (Ultralytics, separate training pipeline)

Experiment steps
----------------
1. Validate dataset structure.
2. Create or load the fixed split manifest (all models use the same split).
3. Train U-Net + MobileNetV2.
4. Train U-Net + ResNet34.
5. Train DeepLabV3+ + ResNet50.
6. Train YOLOv8n-seg.
7. Select best checkpoint per model using validation Dice.
8. Evaluate every model on the same held-out test set.
9. Aggregate all results.
10. Export result tables (CSV / JSON / Markdown).

Fair-comparison controls
------------------------
- Same training samples (train split from manifest)
- Same validation samples (val split from manifest)
- Same test samples (test split from manifest) — used ONLY for evaluation
- Same input resolution: 256 × 256
- Same final metric formulas (metrics.py)
- Same held-out test set — NOT used for checkpoint selection
- Same threshold unless validation-based tuning is explicitly requested
- Best checkpoint selected by validation Dice (never test Dice)
- No threshold tuning on test set

YOLO training differs from SMP models:
  - YOLO uses Ultralytics native compound segmentation loss
  - SMP models use BCEWithLogitsLoss + DiceLoss + Adam + CosineAnnealingLR
  - Both use the same dataset split and unified final evaluation metrics

Missing dataset behaviour
-------------------------
If ``--data-dir`` is not a valid directory:
  - ``--help`` always works
  - Importing this module does NOT trigger training
  - Validation fails gracefully with a clear message
  - Exit status is non-zero only when execution is actually attempted

Usage
-----
::

    # Full experiment (train + evaluate all four models)
    python -m experiments.acm_paper.rq1_model_selection.run_rq1 \\
        --data-dir DATASET_PATH \\
        --epochs 50 \\
        --batch-size 8 \\
        --img-size 256 \\
        --seed 42 \\
        --output-dir outputs/acm_paper/rq1 \\
        --model-dir models/acm_paper/rq1

    # Evaluate only (models already trained)
    python -m experiments.acm_paper.rq1_model_selection.run_rq1 \\
        --data-dir DATASET_PATH \\
        --evaluate-only \\
        --model-dir models/acm_paper/rq1

    # Skip YOLO
    python -m experiments.acm_paper.rq1_model_selection.run_rq1 \\
        --data-dir DATASET_PATH \\
        --skip-yolo
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

# ---------------------------------------------------------------------------
# Allow running as python -m experiments.acm_paper.rq1_model_selection.run_rq1
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR = "outputs/acm_paper/rq1"
DEFAULT_MODEL_DIR  = "models/acm_paper/rq1"
DEFAULT_MANIFEST   = "outputs/acm_paper/rq1/split_manifest.json"
DEFAULT_YOLO_DATASET_DIR = "outputs/acm_paper/rq1/yolo_dataset"

SMP_ARCHS = ["unet_mobilenet", "unet_resnet", "deeplabv3"]
ARCH_DISPLAY = {
    "unet_mobilenet": "U-Net + MobileNetV2",
    "unet_resnet":    "U-Net + ResNet34",
    "deeplabv3":      "DeepLabV3+ + ResNet50",
    "yolov8n_seg":    "YOLOv8n-seg",
}
RESULT_COLUMNS = [
    "Model", "Dice", "IoU", "Precision", "Recall", "Pixel Accuracy",
    "Trainable Params", "Model Size MB", "Latency ms/image", "FPS",
]


# ---------------------------------------------------------------------------
# Training loop for SMP models
# ---------------------------------------------------------------------------

def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def train_smp_model(
    arch: str,
    data_dir: str,
    model_dir: str,
    manifest: Dict,
    epochs: int = 50,
    batch_size: int = 8,
    img_size: int = 256,
    lr: float = 1e-4,
    seed: int = 42,
    device_str: Optional[str] = None,
    num_workers: int = 0,
) -> Path:
    """
    Train one SMP segmentation model using the manifest-controlled split.

    Uses:
      - build_model_by_arch() from src/seg/model.py
      - TongueSegDataset from src/seg/dataset.py
      - BCEWithLogitsLoss + DiceLoss (same as production src/seg/train.py)
      - Adam + CosineAnnealingLR

    Best checkpoint is selected by validation Dice.

    Parameters
    ----------
    arch : str
        Architecture key ("unet_mobilenet" | "unet_resnet" | "deeplabv3").
    data_dir : str
        Dataset root directory.
    model_dir : str
        Parent directory for checkpoints.
    manifest : dict
        Loaded split manifest.
    epochs, batch_size, img_size, lr, seed : training hyperparameters
    device_str : str | None
    num_workers : int

    Returns
    -------
    Path
        Path to the best checkpoint (``best.pth``).
    """
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader

    try:
        from segmentation_models_pytorch.losses import DiceLoss
    except ImportError:
        print(
            "[run_rq1] ERROR: segmentation-models-pytorch not installed.\n"
            "    pip install segmentation-models-pytorch"
        )
        sys.exit(1)

    from src.seg.model import build_model_by_arch, get_device, count_parameters
    from src.seg.dataset import TongueSegDataset
    from experiments.acm_paper.rq1_model_selection.dataset_split import (
        get_split_indices_for_dataset,
    )

    _set_seed(seed)
    device = torch.device(device_str) if device_str else get_device()
    data_path = Path(data_dir)

    arch_label = ARCH_DISPLAY.get(arch, arch)
    print(f"\n[run_rq1] ── Training {arch_label} ──────────────────────")

    # ── Build datasets using manifest split ───────────────────────────
    # Strategy: load full dataset for each source split, then filter by manifest
    def _build_split_ds(split_name: str, is_train: bool):
        """Build TongueSegDataset for one manifest split."""
        # For Roboflow: use predefined split dir; for flat: use ""
        src = split_name if split_name != "val" else "valid"
        if not (data_path / src).is_dir() and not (data_path / split_name).is_dir():
            src = ""  # flat mode

        full_ds = TongueSegDataset(data_dir, split=src, img_size=img_size, is_train=is_train)

        indices = get_split_indices_for_dataset(
            manifest, full_ds._samples, split_name, data_path
        )
        if not indices:
            # Fallback: use the full split
            return full_ds

        return TongueSegDataset(
            data_dir, split=src, img_size=img_size, is_train=is_train, indices=indices
        )

    train_ds = _build_split_ds("train", is_train=True)
    val_ds   = _build_split_ds("val",   is_train=False)

    if len(train_ds) == 0:
        print(f"[run_rq1] ERROR: Empty training set for {arch}.")
        sys.exit(1)

    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=(device.type == "cuda"),
        drop_last=(len(train_ds) >= batch_size),
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
    )

    print(f"[run_rq1]   Train: {len(train_ds)}  Val: {len(val_ds)}  Device: {device}")

    # ── Build model ───────────────────────────────────────────────────
    model = build_model_by_arch(arch, encoder_weights="imagenet").to(device)
    trainable, total = count_parameters(model)
    print(f"[run_rq1]   Trainable params: {trainable:,}")

    # ── Loss + Optimiser + Scheduler ──────────────────────────────────
    bce_fn  = nn.BCEWithLogitsLoss()
    dice_fn = DiceLoss(mode="binary", from_logits=True)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=epochs, eta_min=1e-6
    )

    # ── Checkpoint paths ──────────────────────────────────────────────
    ckpt_dir = Path(model_dir) / arch
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    best_ckpt = ckpt_dir / "best.pth"
    last_ckpt = ckpt_dir / "last.pth"

    # ── Training loop ─────────────────────────────────────────────────
    best_val_dice = 0.0

    def _dice_monitor(logits, masks):
        """Quick dice for monitoring (batch-level, NOT final paper metric)."""
        preds = (torch.sigmoid(logits) > 0.5).float()
        s = 1e-6
        i = (preds * masks).sum().item()
        u = preds.sum().item() + masks.sum().item()
        return (2 * i + s) / (u + s)

    header = (
        f"{'Epoch':>6} {'TrLoss':>8} {'TrDice':>8} | "
        f"{'VaLoss':>8} {'VaDice':>8}  {'LR':>8}"
    )
    print(header)
    print("─" * len(header))

    for epoch in range(1, epochs + 1):
        # Train
        model.train()
        tr_loss = tr_dice = 0.0
        for imgs, masks in train_loader:
            imgs, masks = imgs.to(device), masks.to(device)
            optimizer.zero_grad()
            logits = model(imgs)
            loss = bce_fn(logits, masks) + dice_fn(logits, masks)
            loss.backward()
            optimizer.step()
            with torch.no_grad():
                tr_loss += loss.item()
                tr_dice += _dice_monitor(logits, masks)
        n_tr = max(len(train_loader), 1)
        tr_loss /= n_tr
        tr_dice /= n_tr

        # Validate
        model.eval()
        va_loss = va_dice = 0.0
        with torch.no_grad():
            for imgs, masks in val_loader:
                imgs, masks = imgs.to(device), masks.to(device)
                logits = model(imgs)
                loss = bce_fn(logits, masks) + dice_fn(logits, masks)
                va_loss += loss.item()
                va_dice += _dice_monitor(logits, masks)
        n_va = max(len(val_loader), 1)
        va_loss /= n_va
        va_dice /= n_va

        scheduler.step()
        lr_now = optimizer.param_groups[0]["lr"]
        star = " ★" if va_dice > best_val_dice else ""

        print(
            f"{epoch:>6} {tr_loss:>8.4f} {tr_dice:>8.4f} | "
            f"{va_loss:>8.4f} {va_dice:>8.4f}  {lr_now:>8.2e}{star}"
        )

        if va_dice > best_val_dice:
            best_val_dice = va_dice
            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "val_dice": va_dice,
                    "arch": arch,
                    "img_size": img_size,
                    "seed": seed,
                },
                best_ckpt,
            )

    # Save last checkpoint
    torch.save(
        {"epoch": epochs, "model_state_dict": model.state_dict(), "arch": arch},
        last_ckpt,
    )

    print(
        f"\n[run_rq1]   Best val Dice: {best_val_dice:.4f} → {best_ckpt}"
    )
    return best_ckpt


# ---------------------------------------------------------------------------
# Result aggregation and export
# ---------------------------------------------------------------------------

def _load_result_json(path: Path) -> Optional[Dict]:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def aggregate_and_export(
    result_files: Dict[str, Path],
    output_dir: Path,
) -> Dict:
    """
    Load individual result JSONs, build a summary table, and export
    CSV / JSON / Markdown files.

    Parameters
    ----------
    result_files : dict
        Mapping of model display name → result JSON path.
    output_dir : Path
        Where to write results.csv, results.json, results.md.

    Returns
    -------
    dict : Aggregated results.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict] = []
    all_results: Dict = {}

    for model_name, json_path in result_files.items():
        result = _load_result_json(json_path)
        if result is None:
            print(f"[run_rq1] WARNING: Result not found for {model_name}: {json_path}")
            rows.append({
                "Model": model_name,
                "Dice": "N/A",
                "IoU": "N/A",
                "Precision": "N/A",
                "Recall": "N/A",
                "Pixel Accuracy": "N/A",
                "Trainable Params": "N/A",
                "Model Size MB": "N/A",
                "Latency ms/image": "N/A",
                "FPS": "N/A",
            })
            continue

        row = {
            "Model": model_name,
            "Dice": result.get("Dice", "N/A"),
            "IoU": result.get("IoU", "N/A"),
            "Precision": result.get("Precision", "N/A"),
            "Recall": result.get("Recall", "N/A"),
            "Pixel Accuracy": result.get("Pixel Accuracy", "N/A"),
            "Trainable Params": result.get("trainable_parameter_count", "N/A"),
            "Model Size MB": result.get("checkpoint_size_mb", "N/A"),
            "Latency ms/image": result.get("mean_latency_ms_per_image", "N/A"),
            "FPS": result.get("throughput_fps", "N/A"),
        }
        rows.append(row)
        all_results[model_name] = result

    # ── CSV ───────────────────────────────────────────────────────────
    csv_path = output_dir / "results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[run_rq1] Results CSV → {csv_path}")

    # ── JSON ──────────────────────────────────────────────────────────
    summary = {
        "experiment": "RQ1 Model Selection for Edge-Based Tongue Segmentation",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "note": (
            "No results are available until the real dataset is uploaded and "
            "all models are trained and evaluated.  N/A entries indicate "
            "missing result files."
        ),
        "columns": RESULT_COLUMNS,
        "rows": rows,
        "full_results": all_results,
    }

    json_path = output_dir / "results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"[run_rq1] Results JSON → {json_path}")

    # ── Markdown ──────────────────────────────────────────────────────
    md_lines = [
        "# RQ1 Model Selection — Results",
        "",
        "> **NOTE:** Results below are placeholders (N/A) until the real",
        "> dataset is uploaded and the experiment is executed.",
        "",
        "| " + " | ".join(RESULT_COLUMNS) + " |",
        "| " + " | ".join("---" for _ in RESULT_COLUMNS) + " |",
    ]
    for row in rows:
        values = []
        for col in RESULT_COLUMNS:
            v = row.get(col, "N/A")
            if isinstance(v, float):
                v = f"{v:.4f}"
            values.append(str(v))
        md_lines.append("| " + " | ".join(values) + " |")

    md_lines += [
        "",
        "## Methodological Notes",
        "",
        "- All metrics are computed on the **held-out test set** only.",
        "- Checkpoint selection used **validation Dice** (not test Dice).",
        "- YOLO uses Ultralytics native compound segmentation loss.",
        "- SMP models use BCEWithLogitsLoss + DiceLoss + Adam.",
        "- Final metrics use `experiments/acm_paper/rq1_model_selection/metrics.py`.",
        "",
        f"*Generated: {datetime.now(tz=timezone.utc).isoformat()}*",
    ]

    md_path = output_dir / "results.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"[run_rq1] Results MD → {md_path}")

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "RQ1 Model Selection — Train and evaluate all four tongue\n"
            "segmentation models on the same dataset split.\n\n"
            "If the dataset is not yet available, this script will print\n"
            "a clear message and exit without generating fake results."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Dataset
    parser.add_argument(
        "--data-dir", default=None,
        help="Dataset root directory (required for training/evaluation).",
    )

    # Output paths
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model-dir",  default=DEFAULT_MODEL_DIR)
    parser.add_argument(
        "--split-manifest", default=DEFAULT_MANIFEST,
        help="Path to fixed split manifest JSON.",
    )

    # Training hyperparameters
    parser.add_argument("--epochs",      type=int,   default=50)
    parser.add_argument("--batch-size",  type=int,   default=8)
    parser.add_argument("--img-size",    type=int,   default=256)
    parser.add_argument("--lr",          type=float, default=1e-4)
    parser.add_argument("--seed",        type=int,   default=42)
    parser.add_argument("--device",      default=None)
    parser.add_argument("--threshold",   type=float, default=0.5)
    parser.add_argument("--num-workers", type=int,   default=0)

    # YOLO
    parser.add_argument(
        "--yolo-model", default="yolov8n-seg.pt",
        help="Ultralytics YOLO model name or path.",
    )
    parser.add_argument("--skip-yolo", action="store_true",
                        help="Skip YOLOv8n-seg training and evaluation.")

    # Execution mode
    parser.add_argument("--evaluate-only", action="store_true",
                        help="Only run evaluation (models must be pre-trained).")
    parser.add_argument("--train-only",    action="store_true",
                        help="Only run training (skip evaluation).")

    # Bootstrap
    parser.add_argument(
        "--bootstrap-repetitions", type=int, default=0,
        help="Bootstrap CI repetitions (0 = disabled, 1000+ recommended).",
    )

    args = parser.parse_args()

    # ── Guard: data-dir required for actual execution ─────────────────
    if args.data_dir is None:
        print(
            "[run_rq1] INFO: No --data-dir provided.\n"
            "          The RQ1 experiment framework is implemented and ready.\n"
            "          To run the experiment, provide the dataset path:\n\n"
            "    python -m experiments.acm_paper.rq1_model_selection.run_rq1 \\\n"
            "        --data-dir /path/to/tongue_dataset \\\n"
            "        --epochs 50 --batch-size 8 --seed 42\n"
        )
        return  # Exit 0 — no actual execution was requested

    data_path = Path(args.data_dir)
    if not data_path.is_dir():
        print(
            f"[run_rq1] ERROR: Dataset directory not found: {args.data_dir}\n"
            "          The experiment framework is ready but requires real image data.\n"
            "          Upload the dataset and re-run with --data-dir."
        )
        sys.exit(1)

    output_dir = Path(args.output_dir)
    model_dir  = Path(args.model_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    # ── Load imports lazily (only when dataset is available) ──────────
    from experiments.acm_paper.rq1_model_selection.dataset_split import (
        create_or_load_manifest,
    )
    from experiments.acm_paper.rq1_model_selection.evaluate_smp import evaluate_model
    from experiments.acm_paper.rq1_model_selection.yolo.train_yolo import train_yolo
    from experiments.acm_paper.rq1_model_selection.yolo.evaluate_yolo import evaluate_yolo_model

    # ── Step 1: Create / load manifest ───────────────────────────────
    print("\n[run_rq1] ── Step 1: Dataset split ──────────────────────")
    manifest = create_or_load_manifest(
        data_dir=args.data_dir,
        manifest_path=args.split_manifest,
        seed=args.seed,
    )

    # ── Collect result file paths ─────────────────────────────────────
    result_files = {
        "U-Net + MobileNetV2":    output_dir / "unet_mobilenet.json",
        "U-Net + ResNet34":       output_dir / "unet_resnet.json",
        "DeepLabV3+ + ResNet50":  output_dir / "deeplabv3.json",
        "YOLOv8n-seg":            output_dir / "yolov8n_seg.json",
    }

    checkpoints = {
        "unet_mobilenet": Path(args.model_dir) / "unet_mobilenet" / "best.pth",
        "unet_resnet":    Path(args.model_dir) / "unet_resnet"    / "best.pth",
        "deeplabv3":      Path(args.model_dir) / "deeplabv3"      / "best.pth",
        "yolov8n_seg":    Path(args.model_dir) / "yolov8n_seg"    / "weights" / "best.pt",
    }

    # ── Steps 2-6: Training ───────────────────────────────────────────
    if not args.evaluate_only:
        for arch in SMP_ARCHS:
            print(f"\n[run_rq1] ── Training {ARCH_DISPLAY[arch]} ──")
            train_smp_model(
                arch=arch,
                data_dir=args.data_dir,
                model_dir=args.model_dir,
                manifest=manifest,
                epochs=args.epochs,
                batch_size=args.batch_size,
                img_size=args.img_size,
                lr=args.lr,
                seed=args.seed,
                device_str=args.device,
                num_workers=args.num_workers,
            )

        if not args.skip_yolo:
            print("\n[run_rq1] ── Training YOLOv8n-seg ────────────────")
            train_yolo(
                data_dir=args.data_dir,
                model_name=args.yolo_model,
                epochs=args.epochs,
                img_size=args.img_size,
                batch_size=args.batch_size,
                seed=args.seed,
                manifest_path=args.split_manifest,
                output_dir=str(Path(args.model_dir) / "yolov8n_seg"),
                yolo_dataset_dir=DEFAULT_YOLO_DATASET_DIR,
                device_str=args.device or "",
            )

    # ── Steps 7-8: Evaluation ─────────────────────────────────────────
    if not args.train_only:
        print("\n[run_rq1] ── Evaluating all models ──────────────────")

        for arch in SMP_ARCHS:
            ckpt = checkpoints[arch]
            if not ckpt.exists():
                print(f"[run_rq1] WARNING: Checkpoint not found: {ckpt}  Skipping {arch}.")
                continue
            print(f"\n[run_rq1] Evaluating {ARCH_DISPLAY[arch]} …")
            evaluate_model(
                data_dir=args.data_dir,
                arch=arch,
                checkpoint_path=str(ckpt),
                split="test",
                img_size=args.img_size,
                batch_size=args.batch_size,
                threshold=args.threshold,
                manifest_path=args.split_manifest,
                output_path=str(result_files[ARCH_DISPLAY[arch]]),
                device_str=args.device,
                seed=args.seed,
                num_workers=args.num_workers,
                bootstrap_reps=args.bootstrap_repetitions,
            )

        if not args.skip_yolo:
            yolo_ckpt = checkpoints["yolov8n_seg"]
            if not yolo_ckpt.exists():
                print(f"[run_rq1] WARNING: YOLO checkpoint not found: {yolo_ckpt}")
            else:
                print("\n[run_rq1] Evaluating YOLOv8n-seg …")
                evaluate_yolo_model(
                    data_dir=args.data_dir,
                    checkpoint_path=str(yolo_ckpt),
                    split="test",
                    img_size=args.img_size,
                    threshold=args.threshold,
                    manifest_path=args.split_manifest,
                    output_path=str(result_files["YOLOv8n-seg"]),
                    seed=args.seed,
                    bootstrap_reps=args.bootstrap_repetitions,
                    device_str=args.device,
                )

    # ── Step 9-10: Aggregate and export ───────────────────────────────
    print("\n[run_rq1] ── Aggregating results ────────────────────────")
    aggregate_and_export(result_files, output_dir)

    print(
        f"\n[run_rq1] ══ Experiment complete ══════════════════════════\n"
        f"  Results → {output_dir}\n"
        f"  Split manifest → {args.split_manifest}\n"
    )


if __name__ == "__main__":
    main()
