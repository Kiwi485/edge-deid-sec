"""
model.py — Segmentation 模型建立
支援三種架構（均透過 segmentation_models_pytorch / SMP）：
  - unet_mobilenet : U-Net + MobileNetV2  (輕量，預設)
  - unet_resnet    : U-Net + ResNet34     (中量，特徵更豐富)
  - deeplabv3      : DeepLabV3+ + ResNet50 (重量，多尺度 ASPP)

所有模型輸出 raw logits，搭配 BCEWithLogitsLoss + DiceLoss 使用。
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

# 支援的架構清單（供 train.py / inference.py 做 choices 驗證）
ARCH_CHOICES = ["unet_mobilenet", "unet_resnet", "deeplabv3"]


# ---------------------------------------------------------------------------
# Individual builders
# ---------------------------------------------------------------------------

def build_model(
    encoder_name: str = "mobilenet_v2",
    encoder_weights: str = "imagenet",
    in_channels: int = 3,
    classes: int = 1,
) -> nn.Module:
    """U-Net + MobileNetV2（保留原始介面，向下相容）。"""
    return smp.Unet(
        encoder_name=encoder_name,
        encoder_weights=encoder_weights,
        in_channels=in_channels,
        classes=classes,
        activation=None,
    )


def build_model_unet_resnet(
    encoder_name: str = "resnet34",
    encoder_weights: str = "imagenet",
    in_channels: int = 3,
    classes: int = 1,
) -> nn.Module:
    """
    U-Net + ResNet34 backbone。
    ResNet34 skip connections 比 MobileNetV2 更豐富，
    在有限資料下通常有更好的 Dice / IoU。
    """
    return smp.Unet(
        encoder_name=encoder_name,
        encoder_weights=encoder_weights,
        in_channels=in_channels,
        classes=classes,
        activation=None,
    )


def build_model_deeplabv3(
    encoder_name: str = "resnet50",
    encoder_weights: str = "imagenet",
    in_channels: int = 3,
    classes: int = 1,
) -> nn.Module:
    """
    DeepLabV3+ + ResNet50 backbone。
    ASPP 多尺度上下文對邊界細節較敏感，
    但參數量與記憶體消耗高於 U-Net 系列。
    輸出格式與 U-Net 完全相同（raw logits），train.py 無需修改。
    """
    return smp.DeepLabV3Plus(
        encoder_name=encoder_name,
        encoder_weights=encoder_weights,
        in_channels=in_channels,
        classes=classes,
        activation=None,
    )


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def build_model_by_arch(
    arch: str = "unet_mobilenet",
    encoder_weights: str = "imagenet",
    in_channels: int = 3,
    classes: int = 1,
) -> nn.Module:
    """
    依 arch 名稱建立對應模型。

    Parameters
    ----------
    arch : str
        'unet_mobilenet' | 'unet_resnet' | 'deeplabv3'
    encoder_weights : str
        'imagenet' 或 None（不使用預訓練）
    in_channels : int
    classes     : int

    Returns
    -------
    torch.nn.Module  — raw logits 輸出
    """
    arch = arch.lower()
    if arch == "unet_mobilenet":
        return build_model(
            encoder_name="mobilenet_v2",
            encoder_weights=encoder_weights,
            in_channels=in_channels,
            classes=classes,
        )
    elif arch == "unet_resnet":
        return build_model_unet_resnet(
            encoder_name="resnet34",
            encoder_weights=encoder_weights,
            in_channels=in_channels,
            classes=classes,
        )
    elif arch == "deeplabv3":
        return build_model_deeplabv3(
            encoder_name="resnet50",
            encoder_weights=encoder_weights,
            in_channels=in_channels,
            classes=classes,
        )
    else:
        raise ValueError(
            f"不支援的 arch='{arch}'，請選擇：{ARCH_CHOICES}"
        )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def get_device() -> torch.device:
    """回傳可用的 device（CUDA 優先，否則 CPU）。"""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def count_parameters(model: nn.Module) -> int:
    """回傳模型可訓練參數數量。"""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
