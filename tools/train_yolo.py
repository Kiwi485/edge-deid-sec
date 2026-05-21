"""Train a YOLOv8n detector for tongue ROI.

Reads data/yolo/dataset.yaml (built by prepare_yolo_dataset.py).
Best weights copied to models/yolo/best.pt for the pipeline to use.

Usage:
    python tools/train_yolo.py
    python tools/train_yolo.py --epochs 80 --imgsz 640 --batch 16
"""
import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO


DATA_YAML = Path("data/yolo/dataset.yaml")
OUT_WEIGHTS = Path("models/yolo/best.pt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=DATA_YAML)
    ap.add_argument("--model", type=str, default="yolov8n.pt",
                    help="base model (downloaded if missing)")
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", type=str, default="cpu",
                    help="'cpu' or '0' for first GPU")
    ap.add_argument("--project", type=str, default="runs/yolo")
    ap.add_argument("--name", type=str, default="tongue_roi")
    args = ap.parse_args()

    if not args.data.exists():
        raise SystemExit(
            f"{args.data} not found. Run: python tools/prepare_yolo_dataset.py"
        )

    model = YOLO(args.model)
    model.train(
        data=str(args.data),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        exist_ok=True,
        patience=20,
    )

    best_src = Path(args.project) / args.name / "weights" / "best.pt"
    if not best_src.exists():
        raise SystemExit(f"best.pt not found at {best_src}")

    OUT_WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best_src, OUT_WEIGHTS)
    print(f"[ok] best weights copied to {OUT_WEIGHTS}")


if __name__ == "__main__":
    main()
