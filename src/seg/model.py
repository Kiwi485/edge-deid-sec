"""
model.py — U-Net + MobileNetV2 模型建立
使用 segmentation_models_pytorch (SMP)。
"""

import torch
import torch.nn as nn

try:
    import segmentation_models_pytorch as smp
except ImportError as e:
    raise ImportError(
        "segmentation-models-pytorch 未安裝，請執行：\n"
        "    pip install segmentation-models-pytorch"
    ) from e


def build_model(
    encoder_name: str = "mobilenet_v2",
    encoder_weights: str = "imagenet",
    in_channels: int = 3,
    classes: int = 1,
) -> nn.Module:
    """
    建立 U-Net + MobileNetV2 segmentation 模型。

    Parameters
    ----------
    encoder_name    : SMP encoder 名稱（預設 mobilenet_v2；可換成 efficientnet-b0 等）
    encoder_weights : 'imagenet' 啟用 pretrained weights；None 則隨機初始化
    in_channels     : 輸入影像通道數（RGB = 3）
    classes         : 輸出類別數（binary segmentation = 1）

    Returns
    -------
    torch.nn.Module
        輸出為 raw logits（未套用 sigmoid），搭配 BCEWithLogitsLoss 使用。
    """
    model = smp.Unet(
        encoder_name=encoder_name,
        encoder_weights=encoder_weights,
        in_channels=in_channels,
        classes=classes,
        activation=None,  # raw logits; 使用 BCEWithLogitsLoss + DiceLoss(from_logits=True)
    )
    return model


def get_device() -> torch.device:
    """回傳可用的 device（CUDA 優先，否則 CPU）。"""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def count_parameters(model: nn.Module) -> int:
    """回傳模型可訓練參數數量。"""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
