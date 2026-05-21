"""Prepare YOLO dataset from data/raw/*.jpg + *.txt.

Splits images into train/val (default 80/20) and produces:

    data/yolo/
        images/train/*.jpg
        images/val/*.jpg
        labels/train/*.txt
        labels/val/*.txt
        dataset.yaml

Usage:
    python tools/prepare_yolo_dataset.py
    python tools/prepare_yolo_dataset.py --val-ratio 0.2 --seed 42
"""
import argparse
import random
import shutil
from pathlib import Path

import yaml


RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/yolo")
CLASS_NAMES = ["tongue_roi"]


def collect_pairs(raw_dir: Path):
    pairs = []
    for img in sorted(raw_dir.iterdir()):
        if img.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        lbl = img.with_suffix(".txt")
        if lbl.exists() and lbl.stat().st_size > 0:
            pairs.append((img, lbl))
    return pairs


def reset_out(out_dir: Path):
    if out_dir.exists():
        shutil.rmtree(out_dir)
    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        (out_dir / sub).mkdir(parents=True, exist_ok=True)


def copy_split(pairs, split: str, out_dir: Path):
    for img, lbl in pairs:
        shutil.copy2(img, out_dir / "images" / split / img.name)
        shutil.copy2(lbl, out_dir / "labels" / split / lbl.name)


def write_yaml(out_dir: Path):
    cfg = {
        "path": str(out_dir.resolve()).replace("\\", "/"),
        "train": "images/train",
        "val": "images/val",
        "names": {i: n for i, n in enumerate(CLASS_NAMES)},
    }
    (out_dir / "dataset.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--val-ratio", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    pairs = collect_pairs(args.raw_dir)
    if not pairs:
        raise SystemExit(f"No (image, label) pairs found in {args.raw_dir}")

    random.Random(args.seed).shuffle(pairs)
    n_val = max(1, int(len(pairs) * args.val_ratio))
    val_pairs = pairs[:n_val]
    train_pairs = pairs[n_val:]

    reset_out(args.out_dir)
    copy_split(train_pairs, "train", args.out_dir)
    copy_split(val_pairs, "val", args.out_dir)
    write_yaml(args.out_dir)

    print(f"[ok] total={len(pairs)} train={len(train_pairs)} val={len(val_pairs)}")
    print(f"[ok] dataset.yaml: {args.out_dir / 'dataset.yaml'}")


if __name__ == "__main__":
    main()
