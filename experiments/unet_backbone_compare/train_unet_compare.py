from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Subset, random_split

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from dataset_cvat import CvatSegmentationDataset, detect_annotation_format, find_annotations_dir
from losses import BCEDiceLoss
from metrics import segmentation_metrics
from models_unet import build_unet, count_parameters
from visualize import save_metric_curves, save_prediction_visualization


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train U-Net with MobileNetV2 or ResNet encoder on CVAT tongue segmentation data.")
    parser.add_argument("--data-root", default="cvat/train", help="CVAT train folder containing annotations/ and images/.")
    parser.add_argument("--encoder", required=True, choices=["mobilenet_v2", "resnet18", "resnet34"])
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--img-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--exp-name", required=True)
    parser.add_argument("--output-root", default="runs/unet_backbone_compare")
    parser.add_argument("--pretrained", action="store_true", help="Use ImageNet pretrained encoder weights. Requires local cache or internet.")
    return parser.parse_args()


def resolve_data_root(data_root: str) -> Path:
    requested = Path(data_root)
    if requested.exists():
        return requested
    fallback = Path("data/cvat/train")
    if data_root == "cvat/train" and fallback.exists():
        print(f"Using detected dataset path: {fallback}")
        return fallback
    raise FileNotFoundError(f"Dataset root not found: {requested}")


def make_loaders(args: argparse.Namespace) -> tuple[DataLoader, DataLoader, Subset, Subset, str]:
    data_root = resolve_data_root(args.data_root)
    annotation_format = detect_annotation_format(find_annotations_dir(data_root))
    dataset = CvatSegmentationDataset(data_root=data_root, img_size=args.img_size, annotation_format=annotation_format)

    val_len = max(1, int(len(dataset) * args.val_ratio))
    train_len = len(dataset) - val_len
    if train_len < 1:
        raise RuntimeError("Dataset must contain at least two samples for train/validation split.")

    generator = torch.Generator().manual_seed(args.seed)
    train_set, val_set = random_split(dataset, [train_len, val_len], generator=generator)
    train_loader = DataLoader(train_set, batch_size=args.batch_size, shuffle=True, num_workers=args.num_workers, pin_memory=True)
    val_loader = DataLoader(val_set, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers, pin_memory=True)
    return train_loader, val_loader, train_set, val_set, annotation_format


def run_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    criterion: torch.nn.Module,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None = None,
) -> dict[str, float]:
    is_train = optimizer is not None
    model.train(is_train)
    totals = {"loss": 0.0, "dice": 0.0, "iou": 0.0, "precision": 0.0, "recall": 0.0, "pixel_accuracy": 0.0}
    seen = 0

    for images, masks in loader:
        images = images.to(device, non_blocking=True)
        masks = masks.to(device, non_blocking=True)

        if is_train:
            optimizer.zero_grad(set_to_none=True)
        with torch.set_grad_enabled(is_train):
            logits = model(images)
            loss = criterion(logits, masks)
        if is_train:
            loss.backward()
            optimizer.step()

        batch_size = images.size(0)
        batch_metrics = segmentation_metrics(logits.detach(), masks.detach())
        totals["loss"] += loss.item() * batch_size
        for key, value in batch_metrics.items():
            totals[key] += value * batch_size
        seen += batch_size

    return {key: value / max(seen, 1) for key, value in totals.items()}


@torch.no_grad()
def measure_inference_time(model: torch.nn.Module, loader: DataLoader, device: torch.device, max_images: int = 32) -> float:
    model.eval()
    elapsed = 0.0
    seen = 0
    for images, _ in loader:
        images = images.to(device, non_blocking=True)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        start = time.perf_counter()
        _ = model(images)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        elapsed += time.perf_counter() - start
        seen += images.size(0)
        if seen >= max_images:
            break
    return elapsed / max(seen, 1)


def write_metrics_csv(history: list[dict[str, float]], output_path: Path) -> None:
    fieldnames = [
        "epoch",
        "train_loss",
        "val_loss",
        "train_dice",
        "val_dice",
        "train_iou",
        "val_iou",
        "train_precision",
        "val_precision",
        "train_recall",
        "val_recall",
        "train_pixel_accuracy",
        "val_pixel_accuracy",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(history)


def main() -> None:
    args = parse_args()
    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    output_dir = Path(args.output_root) / args.exp_name
    output_dir.mkdir(parents=True, exist_ok=True)

    train_loader, val_loader, train_set, val_set, annotation_format = make_loaders(args)
    model = build_unet(args.encoder, pretrained=args.pretrained).to(device)
    criterion = BCEDiceLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    best_val_dice = -1.0
    best_epoch = 0
    history: list[dict[str, float]] = []
    best_model_path = output_dir / "best_model.pth"

    print(f"Training U-Net with {args.encoder} encoder on {device}. Annotation format: {annotation_format}")
    print(f"Train samples: {len(train_set)} | Validation samples: {len(val_set)}")

    for epoch in range(1, args.epochs + 1):
        train_metrics = run_epoch(model, train_loader, criterion, device, optimizer)
        val_metrics = run_epoch(model, val_loader, criterion, device)
        row = {
            "epoch": epoch,
            "train_loss": train_metrics["loss"],
            "val_loss": val_metrics["loss"],
            "train_dice": train_metrics["dice"],
            "val_dice": val_metrics["dice"],
            "train_iou": train_metrics["iou"],
            "val_iou": val_metrics["iou"],
            "train_precision": train_metrics["precision"],
            "val_precision": val_metrics["precision"],
            "train_recall": train_metrics["recall"],
            "val_recall": val_metrics["recall"],
            "train_pixel_accuracy": train_metrics["pixel_accuracy"],
            "val_pixel_accuracy": val_metrics["pixel_accuracy"],
        }
        history.append(row)
        write_metrics_csv(history, output_dir / "metrics.csv")
        save_metric_curves(history, output_dir)

        if val_metrics["dice"] > best_val_dice:
            best_val_dice = val_metrics["dice"]
            best_epoch = epoch
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "encoder": args.encoder,
                    "epoch": epoch,
                    "best_val_dice": best_val_dice,
                    "args": vars(args),
                },
                best_model_path,
            )

        print(
            f"Epoch {epoch:03d}/{args.epochs:03d} "
            f"train_loss={train_metrics['loss']:.4f} val_loss={val_metrics['loss']:.4f} "
            f"val_dice={val_metrics['dice']:.4f} val_iou={val_metrics['iou']:.4f}"
        )

    checkpoint = torch.load(best_model_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    final_val_metrics = run_epoch(model, val_loader, criterion, device)
    inference_time = measure_inference_time(model, val_loader, device)
    save_prediction_visualization(model, val_set, device, output_dir / "prediction_visualization.png")

    summary = {
        "model_name": "U-Net",
        "encoder_name": args.encoder,
        "best_epoch": best_epoch,
        "best_validation_dice": best_val_dice,
        "best_validation_iou": max(row["val_iou"] for row in history),
        "precision": final_val_metrics["precision"],
        "recall": final_val_metrics["recall"],
        "pixel_accuracy": final_val_metrics["pixel_accuracy"],
        "parameter_count": count_parameters(model),
        "average_inference_time_per_image": inference_time,
        "annotation_format": annotation_format,
        "image_size": args.img_size,
    }
    with (output_dir / "final_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Saved best model and reports to {output_dir}")


if __name__ == "__main__":
    main()
