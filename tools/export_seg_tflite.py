"""Export the trained SMP segmentation checkpoint to a float32 TFLite model."""

import argparse
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.seg.model import build_model_by_arch


def main():
    parser = argparse.ArgumentParser(description="Export segmentation checkpoint to TFLite")
    parser.add_argument("--checkpoint", type=Path, default=Path("models/seg/best.pth"))
    parser.add_argument("--output", type=Path, default=Path("models/seg/model.tflite"))
    parser.add_argument("--img-size", type=int, default=256)
    args = parser.parse_args()

    if args.img_size <= 0:
        parser.error("--img-size must be positive")
    try:
        import litert_torch
    except ImportError as exc:
        raise SystemExit("Install litert-torch in the export environment first") from exc

    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    arch = checkpoint.get("args", {}).get("arch", "unet_mobilenet")
    model = build_model_by_arch(arch=arch, encoder_weights=None)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    sample = (torch.zeros(1, 3, args.img_size, args.img_size),)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    litert_torch.convert(model, sample).export(str(args.output))
    print(f"Exported {arch} to {args.output}")


if __name__ == "__main__":
    main()