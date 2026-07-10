from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch


IMAGENET_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
IMAGENET_STD = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)


def _to_numpy_image(image_tensor: torch.Tensor) -> np.ndarray:
    image = image_tensor.detach().cpu()
    if image.ndim == 4:
        image = image[0]
    image = image * IMAGENET_STD + IMAGENET_MEAN
    image = image.clamp(0, 1).permute(1, 2, 0).numpy()
    return image


def _to_numpy_mask(mask_tensor: torch.Tensor) -> np.ndarray:
    mask = mask_tensor.detach().cpu()
    if mask.ndim == 4:
        mask = mask[0]
    if mask.ndim == 3:
        mask = mask[0]
    return mask.numpy()


def save_metric_curves(history: list[dict[str, float]], output_dir: str | Path) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    epochs = [row["epoch"] for row in history]
    curve_specs = [
        ("train_loss", "train_loss_curve.png", "Train Loss"),
        ("val_loss", "val_loss_curve.png", "Validation Loss"),
        ("train_dice", "train_dice_curve.png", "Train Dice"),
        ("val_dice", "val_dice_curve.png", "Validation Dice"),
        ("train_iou", "train_iou_curve.png", "Train IoU"),
        ("val_iou", "val_iou_curve.png", "Validation IoU"),
    ]
    for key, filename, title in curve_specs:
        plt.figure(figsize=(7, 4))
        plt.plot(epochs, [row[key] for row in history], marker="o", linewidth=2)
        plt.title(title)
        plt.xlabel("Epoch")
        plt.ylabel(key.replace("_", " ").title())
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / filename, dpi=160)
        plt.close()


@torch.no_grad()
def save_prediction_visualization(
    model: torch.nn.Module,
    dataset,
    device: torch.device,
    output_path: str | Path,
    threshold: float = 0.5,
    sample_index: int = 0,
) -> None:
    model.eval()
    image, target = dataset[min(sample_index, len(dataset) - 1)]
    logits = model(image.unsqueeze(0).to(device))
    pred = (torch.sigmoid(logits).cpu()[0, 0] >= threshold).float()

    image_np = _to_numpy_image(image)
    gt_np = _to_numpy_mask(target)
    pred_np = pred.numpy()
    overlay = image_np.copy()
    overlay[..., 0] = np.maximum(overlay[..., 0], pred_np * 1.0)
    overlay[..., 1] = overlay[..., 1] * (1.0 - 0.35 * pred_np)
    overlay[..., 2] = overlay[..., 2] * (1.0 - 0.35 * pred_np)

    fig, axes = plt.subplots(1, 4, figsize=(14, 4))
    panels = [
        (image_np, "Input Image", None),
        (gt_np, "Ground Truth Mask", "gray"),
        (pred_np, "Predicted Mask", "gray"),
        (overlay, "Overlay", None),
    ]
    for ax, (arr, title, cmap) in zip(axes, panels):
        ax.imshow(arr, cmap=cmap, vmin=0, vmax=1)
        ax.set_title(title)
        ax.axis("off")
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close(fig)
