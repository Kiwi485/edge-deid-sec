from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F


class ConvBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class DecoderBlock(nn.Module):
    def __init__(self, in_channels: int, skip_channels: int, out_channels: int) -> None:
        super().__init__()
        self.conv = ConvBlock(in_channels + skip_channels, out_channels)

    def forward(self, x: torch.Tensor, skip: torch.Tensor | None = None) -> torch.Tensor:
        x = F.interpolate(x, scale_factor=2, mode="bilinear", align_corners=False)
        if skip is not None:
            if x.shape[-2:] != skip.shape[-2:]:
                x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
            x = torch.cat([x, skip], dim=1)
        return self.conv(x)


class MobileNetV2Encoder(nn.Module):
    out_channels = [16, 24, 32, 96, 1280]

    def __init__(self, pretrained: bool = False) -> None:
        super().__init__()
        from torchvision.models import MobileNet_V2_Weights, mobilenet_v2

        weights = MobileNet_V2_Weights.DEFAULT if pretrained else None
        features = mobilenet_v2(weights=weights).features
        self.stage1 = nn.Sequential(features[0], features[1])
        self.stage2 = features[2:4]
        self.stage3 = features[4:7]
        self.stage4 = features[7:14]
        self.stage5 = features[14:]

    def forward(self, x: torch.Tensor) -> list[torch.Tensor]:
        s1 = self.stage1(x)
        s2 = self.stage2(s1)
        s3 = self.stage3(s2)
        s4 = self.stage4(s3)
        s5 = self.stage5(s4)
        return [s1, s2, s3, s4, s5]


class ResNetEncoder(nn.Module):
    out_channels = [64, 64, 128, 256, 512]

    def __init__(self, name: str, pretrained: bool = False) -> None:
        super().__init__()
        from torchvision.models import ResNet18_Weights, ResNet34_Weights, resnet18, resnet34

        if name == "resnet18":
            weights = ResNet18_Weights.DEFAULT if pretrained else None
            net = resnet18(weights=weights)
        elif name == "resnet34":
            weights = ResNet34_Weights.DEFAULT if pretrained else None
            net = resnet34(weights=weights)
        else:
            raise ValueError(f"Unsupported ResNet encoder: {name}")

        self.stem = nn.Sequential(net.conv1, net.bn1, net.relu)
        self.pool = net.maxpool
        self.layer1 = net.layer1
        self.layer2 = net.layer2
        self.layer3 = net.layer3
        self.layer4 = net.layer4

    def forward(self, x: torch.Tensor) -> list[torch.Tensor]:
        s1 = self.stem(x)
        x = self.pool(s1)
        s2 = self.layer1(x)
        s3 = self.layer2(s2)
        s4 = self.layer3(s3)
        s5 = self.layer4(s4)
        return [s1, s2, s3, s4, s5]


class UNetWithEncoder(nn.Module):
    def __init__(self, encoder_name: str, pretrained: bool = False) -> None:
        super().__init__()
        self.encoder_name = encoder_name
        if encoder_name == "mobilenet_v2":
            self.encoder = MobileNetV2Encoder(pretrained=pretrained)
        elif encoder_name in {"resnet18", "resnet34"}:
            self.encoder = ResNetEncoder(encoder_name, pretrained=pretrained)
        else:
            raise ValueError("encoder must be one of: mobilenet_v2, resnet18, resnet34")

        c1, c2, c3, c4, c5 = self.encoder.out_channels
        self.decoder4 = DecoderBlock(c5, c4, 256)
        self.decoder3 = DecoderBlock(256, c3, 128)
        self.decoder2 = DecoderBlock(128, c2, 64)
        self.decoder1 = DecoderBlock(64, c1, 32)
        self.decoder0 = DecoderBlock(32, 0, 16)
        self.segmentation_head = nn.Conv2d(16, 1, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        input_size = x.shape[-2:]
        s1, s2, s3, s4, s5 = self.encoder(x)
        x = self.decoder4(s5, s4)
        x = self.decoder3(x, s3)
        x = self.decoder2(x, s2)
        x = self.decoder1(x, s1)
        x = self.decoder0(x, None)
        logits = self.segmentation_head(x)
        if logits.shape[-2:] != input_size:
            logits = F.interpolate(logits, size=input_size, mode="bilinear", align_corners=False)
        return logits


def build_unet(encoder: str = "mobilenet_v2", pretrained: bool = False) -> nn.Module:
    return UNetWithEncoder(encoder_name=encoder, pretrained=pretrained)


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
