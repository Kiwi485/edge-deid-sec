"""
train.py — U-Net + MobileNetV2 舌頭 segmentation 訓練腳本

支援三種資料格式：
  1. Roboflow COCO-seg：data_dir/train/_annotations.coco.json + 圖片
  2. Flat：             data_dir/images/ + data_dir/masks/
  3. YOLO fallback：    data_dir/images/ + data_dir/labels/*.txt（pseudo-mask）

快速啟動（Roboflow 格式）：
    python src/seg/train.py --data-dir path/to/roboflow_export --epochs 50

快速啟動（flat 格式）：
    python src/seg/train.py --data-dir data --epochs 50

測試用（50-100 張，確認程式能跑通）：
    python src/seg/train.py --data-dir path/to/small_set --epochs 3 --batch-size 4
"""

import argparse
import random
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

# Allow running from project root: python src/seg/train.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

try:
    from segmentation_models_pytorch.losses import DiceLoss
except ImportError:
    print("[ERROR] segmentation-models-pytorch 未安裝，請執行：pip install segmentation-models-pytorch")
    sys.exit(1)

try:
    from seg.dataset import TongueSegDataset, get_transforms
    from seg.model import build_model_by_arch, get_device, count_parameters, ARCH_CHOICES
except ImportError:
    from src.seg.dataset import TongueSegDataset, get_transforms
    from src.seg.model import build_model_by_arch, get_device, count_parameters, ARCH_CHOICES


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def dice_score(logits: torch.Tensor, targets: torch.Tensor, threshold: float = 0.5) -> float:
    preds = (torch.sigmoid(logits) > threshold).float()
    smooth = 1e-6
    inter = (preds * targets).sum().item()
    union = preds.sum().item() + targets.sum().item()
    return (2 * inter + smooth) / (union + smooth)


def iou_score(logits: torch.Tensor, targets: torch.Tensor, threshold: float = 0.5) -> float:
    preds = (torch.sigmoid(logits) > threshold).float()
    smooth = 1e-6
    inter = (preds * targets).sum().item()
    union = (preds + targets).clamp(0, 1).sum().item()
    return (inter + smooth) / (union + smooth)


# ---------------------------------------------------------------------------
# Train / Validate one epoch
# ---------------------------------------------------------------------------

def train_epoch(model, loader, optimizer, bce_fn, dice_fn, device):
    model.train()
    total_loss = total_dice = total_iou = 0.0

    for imgs, masks in loader:
        imgs = imgs.to(device, non_blocking=True)
        masks = masks.to(device, non_blocking=True)

        optimizer.zero_grad()
        logits = model(imgs)
        loss = bce_fn(logits, masks) + dice_fn(logits, masks)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        with torch.no_grad():
            total_dice += dice_score(logits, masks)
            total_iou += iou_score(logits, masks)

    n = max(len(loader), 1)
    return total_loss / n, total_dice / n, total_iou / n


@torch.no_grad()
def val_epoch(model, loader, bce_fn, dice_fn, device):
    model.eval()
    total_loss = total_dice = total_iou = 0.0

    for imgs, masks in loader:
        imgs = imgs.to(device)
        masks = masks.to(device)
        logits = model(imgs)
        loss = bce_fn(logits, masks) + dice_fn(logits, masks)
        total_loss += loss.item()
        total_dice += dice_score(logits, masks)
        total_iou += iou_score(logits, masks)

    n = max(len(loader), 1)
    return total_loss / n, total_dice / n, total_iou / n


# ---------------------------------------------------------------------------
# Dataset builder (handles both Roboflow split structure & flat)
# ---------------------------------------------------------------------------

def build_datasets(args):
    data_dir = Path(args.data_dir)
    img_size = args.img_size
    val_frac = args.val_split

    train_dir = data_dir / "train"
    valid_dir_exists = (data_dir / "valid").exists() or (data_dir / "val").exists()

    if train_dir.exists():
        # ── Roboflow split structure ────────────────────────────────
        train_ds = TongueSegDataset(
            args.data_dir, split="train", img_size=img_size, is_train=True
        )
        if valid_dir_exists:
            val_ds = TongueSegDataset(
                args.data_dir, split="valid", img_size=img_size, is_train=False
            )
            print(f"Loaded Roboflow split: {len(train_ds)} train / {len(val_ds)} val")
        else:
            # Auto-split train set
            all_idx = list(range(len(train_ds)))
            random.shuffle(all_idx)
            n_val = max(1, int(len(all_idx) * val_frac))
            val_idx = all_idx[:n_val]
            train_idx = all_idx[n_val:]
            train_ds = TongueSegDataset(
                args.data_dir, split="train", img_size=img_size, is_train=True, indices=train_idx
            )
            val_ds = TongueSegDataset(
                args.data_dir, split="train", img_size=img_size, is_train=False, indices=val_idx
            )
            print(
                f"Auto-split (no valid/): {len(train_ds)} train / {len(val_ds)} val"
                f" ({val_frac*100:.0f}% val)"
            )
    else:
        # ── Flat structure ──────────────────────────────────────────
        all_ds_tmp = TongueSegDataset(
            args.data_dir, split="", img_size=img_size, is_train=True
        )
        if len(all_ds_tmp) == 0:
            print("[ERROR] 找不到任何影像，請確認 --data-dir 是否正確。")
            print("  支援格式：")
            print("    Roboflow: data_dir/train/_annotations.coco.json")
            print("    Flat:     data_dir/images/ + data_dir/masks/")
            sys.exit(1)

        all_idx = list(range(len(all_ds_tmp)))
        random.shuffle(all_idx)
        n_val = max(1, int(len(all_idx) * val_frac))
        val_idx = all_idx[:n_val]
        train_idx = all_idx[n_val:]

        train_ds = TongueSegDataset(
            args.data_dir, split="", img_size=img_size, is_train=True, indices=train_idx
        )
        val_ds = TongueSegDataset(
            args.data_dir, split="", img_size=img_size, is_train=False, indices=val_idx
        )
        print(
            f"Flat mode auto-split: {len(train_ds)} train / {len(val_ds)} val"
            f" ({val_frac*100:.0f}% val)"
        )

    return train_ds, val_ds


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Train tongue segmentation（支援 unet_mobilenet / unet_resnet / deeplabv3）"
    )
    parser.add_argument("--data-dir", type=str, required=True,
                        help="資料集根目錄（Roboflow 或 flat 格式）")
    parser.add_argument("--arch", type=str, default="unet_mobilenet",
                        choices=ARCH_CHOICES,
                        help="模型架構：unet_mobilenet | unet_resnet | deeplabv3")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--img-size", type=int, default=256,
                        help="輸入影像 resize 邊長（正方形），預設 256")
    parser.add_argument("--lr", type=float, default=1e-4, help="初始學習率")
    parser.add_argument("--val-split", type=float, default=0.2,
                        help="無 valid/ 時，從 train 切出的 val 比例")
    parser.add_argument("--device", type=str, default=None,
                        help="cpu 或 cuda（不指定則自動選擇）")
    parser.add_argument("--out-dir", type=str, default="models/seg",
                        help="checkpoint 儲存目錄（會在此目錄下建立 arch 子目錄）")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-workers", type=int, default=0,
                        help="DataLoader workers（Windows 建議設 0）")
    parser.add_argument("--no-pretrain", action="store_true",
                        help="不使用 ImageNet pretrained weights")
    args = parser.parse_args()

    # ── Reproducibility ──────────────────────────────────────────────
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    # ── Device ───────────────────────────────────────────────────────
    device = torch.device(args.device) if args.device else get_device()
    print(f"Device: {device}")

    # ── Dataset / DataLoader ─────────────────────────────────────────
    train_ds, val_ds = build_datasets(args)

    if len(train_ds) == 0:
        print("[ERROR] train set 為空。")
        sys.exit(1)

    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=(device.type == "cuda"),
        drop_last=(len(train_ds) >= args.batch_size),
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
    )

    # ── Model ────────────────────────────────────────────────────────
    encoder_weights = None if args.no_pretrain else "imagenet"
    model = build_model_by_arch(
        arch=args.arch,
        encoder_weights=encoder_weights,
    ).to(device)
    arch_label = {
        "unet_mobilenet": "U-Net + MobileNetV2",
        "unet_resnet":    "U-Net + ResNet34",
        "deeplabv3":      "DeepLabV3+ + ResNet50",
    }.get(args.arch, args.arch)
    print(f"Model: {arch_label} | encoder_weights={encoder_weights}")
    print(f"Trainable params: {count_parameters(model):,}")

    # ── Loss ─────────────────────────────────────────────────────────
    bce_fn = nn.BCEWithLogitsLoss()
    dice_fn = DiceLoss(mode="binary", from_logits=True)

    # ── Optimizer + Scheduler ────────────────────────────────────────
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs, eta_min=1e-6
    )

    # ── Output ───────────────────────────────────────────────────────
    # 每個 arch 儲存到獨立子目錄，方便比較
    out_dir = Path(args.out_dir) / args.arch
    out_dir.mkdir(parents=True, exist_ok=True)
    best_ckpt = out_dir / "best.pth"
    last_ckpt = out_dir / "last.pth"

    # ── Training loop ────────────────────────────────────────────────
    best_val_dice = 0.0

    header = f"{'Epoch':>6} {'TrLoss':>8} {'TrDice':>8} {'TrIoU':>7} | {'VaLoss':>8} {'VaDice':>8} {'VaIoU':>7}  {'LR':>8}"
    print(f"\n{header}")
    print("─" * len(header))

    for epoch in range(1, args.epochs + 1):
        tr_loss, tr_dice, tr_iou = train_epoch(
            model, train_loader, optimizer, bce_fn, dice_fn, device
        )
        va_loss, va_dice, va_iou = val_epoch(model, val_loader, bce_fn, dice_fn, device)
        scheduler.step()

        lr = optimizer.param_groups[0]["lr"]
        star = " ★" if va_dice > best_val_dice else ""

        print(
            f"{epoch:>6} {tr_loss:>8.4f} {tr_dice:>8.4f} {tr_iou:>7.4f} |"
            f" {va_loss:>8.4f} {va_dice:>8.4f} {va_iou:>7.4f}  {lr:>8.2e}{star}"
        )

        # Save best checkpoint
        if va_dice > best_val_dice:
            best_val_dice = va_dice
            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "val_dice": va_dice,
                    "val_iou": va_iou,
                    "args": vars(args),
                },
                best_ckpt,
            )

    # Save last checkpoint
    torch.save(
        {
            "epoch": args.epochs,
            "model_state_dict": model.state_dict(),
            "val_dice": va_dice,
            "args": vars(args),
        },
        last_ckpt,
    )

    print(f"\n{'─'*50}")
    print(f"Best val Dice : {best_val_dice:.4f}")
    print(f"Saved best    : {best_ckpt}")
    print(f"Saved last    : {last_ckpt}")


if __name__ == "__main__":
    main()
