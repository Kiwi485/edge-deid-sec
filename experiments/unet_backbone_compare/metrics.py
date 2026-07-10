from __future__ import annotations

import torch


def _binary_predictions(logits: torch.Tensor, threshold: float = 0.5) -> torch.Tensor:
    return (torch.sigmoid(logits) >= threshold).float()


def dice_score(logits: torch.Tensor, targets: torch.Tensor, threshold: float = 0.5, eps: float = 1e-7) -> float:
    preds = _binary_predictions(logits, threshold)
    targets = targets.float()
    intersection = (preds * targets).sum(dim=(1, 2, 3))
    denom = preds.sum(dim=(1, 2, 3)) + targets.sum(dim=(1, 2, 3))
    return ((2.0 * intersection + eps) / (denom + eps)).mean().item()


def iou_score(logits: torch.Tensor, targets: torch.Tensor, threshold: float = 0.5, eps: float = 1e-7) -> float:
    preds = _binary_predictions(logits, threshold)
    targets = targets.float()
    intersection = (preds * targets).sum(dim=(1, 2, 3))
    union = preds.sum(dim=(1, 2, 3)) + targets.sum(dim=(1, 2, 3)) - intersection
    return ((intersection + eps) / (union + eps)).mean().item()


def precision_score(logits: torch.Tensor, targets: torch.Tensor, threshold: float = 0.5, eps: float = 1e-7) -> float:
    preds = _binary_predictions(logits, threshold)
    targets = targets.float()
    tp = (preds * targets).sum(dim=(1, 2, 3))
    fp = (preds * (1.0 - targets)).sum(dim=(1, 2, 3))
    return ((tp + eps) / (tp + fp + eps)).mean().item()


def recall_score(logits: torch.Tensor, targets: torch.Tensor, threshold: float = 0.5, eps: float = 1e-7) -> float:
    preds = _binary_predictions(logits, threshold)
    targets = targets.float()
    tp = (preds * targets).sum(dim=(1, 2, 3))
    fn = ((1.0 - preds) * targets).sum(dim=(1, 2, 3))
    return ((tp + eps) / (tp + fn + eps)).mean().item()


def pixel_accuracy(logits: torch.Tensor, targets: torch.Tensor, threshold: float = 0.5) -> float:
    preds = _binary_predictions(logits, threshold)
    targets = targets.float()
    return (preds == targets).float().mean().item()


@torch.no_grad()
def segmentation_metrics(logits: torch.Tensor, targets: torch.Tensor, threshold: float = 0.5) -> dict[str, float]:
    return {
        "dice": dice_score(logits, targets, threshold),
        "iou": iou_score(logits, targets, threshold),
        "precision": precision_score(logits, targets, threshold),
        "recall": recall_score(logits, targets, threshold),
        "pixel_accuracy": pixel_accuracy(logits, targets, threshold),
    }
