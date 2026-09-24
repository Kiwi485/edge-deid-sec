"""
train_yolo.py — ACM Paper RQ1: Train YOLOv8n-seg
=================================================
Trains a YOLOv8n-seg model on the tongue segmentation dataset using
the **same sample split** as the three SMP models.

IMPORTANT: Loss function
------------------------
YOLOv8n-seg uses Ultralytics' **native compound segmentation loss**,
which combines box regression, classification, and mask losses internally.
This is fundamentally different from the BCE + DiceLoss combination used
by the SMP models.  Do NOT claim that all four models use mathematically
identical losses — they do not.

The comparison is fair at the level of:
  - Identical dataset samples and split (same manifest)
  - Identical input resolution (256 × 256)
  - Identical final segmentation metrics (from metrics.py)
  - Same held-out test set

YOLO-specific notes
-------------------
- The random seed is passed to Ultralytics where supported.
- The exact optimizer, scheduler, and augmentation policy are controlled
  by Ultralytics internally.
- Training results are recorded in the output directory.

Usage
-----
::

    python -m experiments.acm_paper.rq1_model_selection.yolo.train_yolo \\
        --data-dir DATASET_PATH \\
        --model yolov8n-seg.pt \\
        --epochs 50 \\
        --img-size 256 \\
        --batch-size 8 \\
        --seed 42 \\
        --split-manifest outputs/acm_paper/rq1/split_manifest.json \\
        --output-dir models/acm_paper/rq1/yolov8n_seg
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from experiments.acm_paper.rq1_model_selection.dataset_split import (
    create_or_load_manifest,
    DEFAULT_MANIFEST_PATH,
)
from experiments.acm_paper.rq1_model_selection.yolo.adapter import prepare_yolo_dataset

# Default YOLO model name
DEFAULT_YOLO_MODEL = "yolov8n-seg.pt"
DEFAULT_YOLO_DATASET_DIR = "outputs/acm_paper/rq1/yolo_dataset"


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train_yolo(
    data_dir: str,
    model_name: str = DEFAULT_YOLO_MODEL,
    epochs: int = 50,
    img_size: int = 256,
    batch_size: int = 8,
    seed: int = 42,
    manifest_path: str = DEFAULT_MANIFEST_PATH,
    output_dir: str = "models/acm_paper/rq1/yolov8n_seg",
    yolo_dataset_dir: str = DEFAULT_YOLO_DATASET_DIR,
    device_str: str = "",
) -> Path:
    """
    Train YOLOv8n-seg on the tongue segmentation dataset.

    Preparation steps:
      1. Load or create the split manifest.
      2. Convert the dataset to YOLO format (via adapter.py).
      3. Launch Ultralytics training.

    Parameters
    ----------
    data_dir : str
        Source dataset root directory.
    model_name : str
        Ultralytics model name or path (default: "yolov8n-seg.pt").
    epochs : int
    img_size : int
    batch_size : int
    seed : int
    manifest_path : str
    output_dir : str
        Where to save YOLO training results.
    yolo_dataset_dir : str
        Where to write the converted YOLO dataset.
    device_str : str
        Device string for Ultralytics ("", "cpu", "0", "cuda:0").

    Returns
    -------
    Path
        Path to the best checkpoint (``best.pt``).

    Raises
    ------
    SystemExit
        If dataset is missing or Ultralytics is not installed.
    """
    try:
        from ultralytics import YOLO
        import ultralytics
        ult_version = ultralytics.__version__
    except ImportError:
        print(
            "[train_yolo] ERROR: ultralytics is not installed.\n"
            "Install it with: pip install ultralytics"
        )
        sys.exit(1)

    data_path = Path(data_dir)
    if not data_path.is_dir():
        print(
            f"[train_yolo] ERROR: Dataset not found: {data_dir}\n"
            "The experiment framework is ready but requires real image data.\n"
            "Upload the dataset and re-run this command."
        )
        sys.exit(1)

    # ── Load or create manifest ──────────────────────────────────────
    manifest = create_or_load_manifest(
        data_dir=data_dir,
        manifest_path=manifest_path,
        seed=seed,
    )

    # ── Prepare YOLO dataset ─────────────────────────────────────────
    data_yaml = prepare_yolo_dataset(
        data_dir=data_dir,
        manifest=manifest,
        output_dir=yolo_dataset_dir,
    )

    # ── Launch Ultralytics training ───────────────────────────────────
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print(
        f"\n[train_yolo] ─────────────────────────────────────────────\n"
        f"  Model          : {model_name}\n"
        f"  Epochs         : {epochs}\n"
        f"  Image size     : {img_size}\n"
        f"  Batch size     : {batch_size}\n"
        f"  Seed           : {seed}\n"
        f"  Data YAML      : {data_yaml}\n"
        f"  Output dir     : {out_path}\n"
        f"  Ultralytics    : {ult_version}\n"
        f"  Loss           : Ultralytics native compound segmentation loss\n"
        f"  NOTE: YOLO loss ≠ BCE + DiceLoss used by SMP models.\n"
        f"[train_yolo] ─────────────────────────────────────────────\n"
    )

    model = YOLO(model_name)

    train_kwargs = {
        "data": str(data_yaml),
        "epochs": epochs,
        "imgsz": img_size,
        "batch": batch_size,
        "project": str(out_path.parent),
        "name": out_path.name,
        "seed": seed,
        "exist_ok": True,
        "verbose": True,
    }
    if device_str:
        train_kwargs["device"] = device_str

    results = model.train(**train_kwargs)

    # ── Locate best checkpoint ────────────────────────────────────────
    # Ultralytics saves weights to <project>/<name>/weights/best.pt
    best_pt = out_path / "weights" / "best.pt"
    if not best_pt.exists():
        # Fallback: search for any best.pt in the output directory
        candidates = list(out_path.rglob("best.pt"))
        best_pt = candidates[0] if candidates else out_path / "best.pt"

    # ── Save training metadata ────────────────────────────────────────
    meta = {
        "model_name": model_name,
        "model_type": "yolov8n-seg",
        "ultralytics_version": ult_version,
        "epochs": epochs,
        "img_size": img_size,
        "batch_size": batch_size,
        "seed": seed,
        "data_yaml": str(data_yaml),
        "output_dir": str(out_path.resolve()),
        "best_checkpoint": str(best_pt),
        "manifest_path": str(Path(manifest_path).resolve()),
        "loss_function": (
            "Ultralytics native compound segmentation loss "
            "(NOT BCE + DiceLoss; different from SMP models)"
        ),
        "optimizer": "auto (controlled by Ultralytics)",
        "scheduler": "auto (controlled by Ultralytics)",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "note": (
            "YOLO training uses Ultralytics' built-in data augmentation, "
            "optimizer selection, and loss function. "
            "Final evaluation metrics are unified across all four models "
            "using experiments/acm_paper/rq1_model_selection/metrics.py."
        ),
    }

    meta_path = out_path / "training_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[train_yolo] Training metadata → {meta_path}")
    print(f"[train_yolo] Best checkpoint   → {best_pt}")

    return best_pt


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Train YOLOv8n-seg on the tongue segmentation dataset (RQ1).\n\n"
            "IMPORTANT: YOLO uses Ultralytics' native compound segmentation loss,\n"
            "not BCE + DiceLoss.  Training procedure differs from SMP models.\n"
            "Final evaluation metrics are unified via metrics.py."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--data-dir", required=True,
        help="Dataset root directory (Roboflow or flat format).",
    )
    parser.add_argument(
        "--model", default=DEFAULT_YOLO_MODEL,
        help="Ultralytics model name or path (default: yolov8n-seg.pt).",
    )
    parser.add_argument("--epochs",     type=int,   default=50)
    parser.add_argument("--img-size",   type=int,   default=256)
    parser.add_argument("--batch-size", type=int,   default=8)
    parser.add_argument("--seed",       type=int,   default=42)
    parser.add_argument(
        "--split-manifest",
        default=DEFAULT_MANIFEST_PATH,
        help="Path to the fixed split manifest JSON.",
    )
    parser.add_argument(
        "--output-dir",
        default="models/acm_paper/rq1/yolov8n_seg",
        help="Directory for YOLO training results.",
    )
    parser.add_argument(
        "--yolo-dataset-dir",
        default=DEFAULT_YOLO_DATASET_DIR,
        help="Directory for the converted YOLO dataset.",
    )
    parser.add_argument("--device", default="",
                        help="Device for Ultralytics ('', 'cpu', '0', 'cuda:0').")

    args = parser.parse_args()

    train_yolo(
        data_dir=args.data_dir,
        model_name=args.model,
        epochs=args.epochs,
        img_size=args.img_size,
        batch_size=args.batch_size,
        seed=args.seed,
        manifest_path=args.split_manifest,
        output_dir=args.output_dir,
        yolo_dataset_dir=args.yolo_dataset_dir,
        device_str=args.device,
    )


if __name__ == "__main__":
    main()
