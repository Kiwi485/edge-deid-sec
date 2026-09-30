"""Compare PyTorch and TFLite predictions and forward latency on ROI images."""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.seg.inference import run_inference as torch_inference
from src.seg.tflite_inference import run_inference as tflite_inference


def main():
    parser = argparse.ArgumentParser(description="Compare segmentation backends on ROI images")
    parser.add_argument("--roi-dir", type=Path, default=Path("data/out"))
    parser.add_argument("--torch-model", default="models/seg/best.pth")
    parser.add_argument("--tflite-model", default="models/seg/model.tflite")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    paths = sorted(args.roi_dir.rglob("roi.png"))[:args.limit]
    if not paths:
        parser.error(f"No roi.png images found in {args.roi_dir}")

    dice_values = []
    iou_values = []
    torch_ms = []
    tflite_ms = []
    for path in paths:
        image = cv2.imread(str(path))
        if image is None:
            parser.error(f"Cannot read ROI image: {path}")
        torch_mask, _, torch_timings = torch_inference(
            "", args.torch_model, image_array=image, return_timings=True
        )
        tflite_mask, _, tflite_timings = tflite_inference(
            "", args.tflite_model, image_array=image, return_timings=True
        )
        original = torch_mask > 0
        converted = tflite_mask > 0
        intersection = np.count_nonzero(original & converted)
        total = np.count_nonzero(original) + np.count_nonzero(converted)
        union = np.count_nonzero(original | converted)
        dice_values.append(2 * intersection / total if total else 1.0)
        iou_values.append(intersection / union if union else 1.0)
        torch_ms.append(torch_timings["seg_forward_ms"])
        tflite_ms.append(tflite_timings["seg_forward_ms"])

    print(f"images={len(paths)} mask_dice_mean={np.mean(dice_values):.4f} mask_iou_mean={np.mean(iou_values):.4f}")
    for backend, values in (("torch", torch_ms), ("tflite", tflite_ms)):
        print(f"{backend}_forward_ms p50={np.percentile(values, 50):.2f} p95={np.percentile(values, 95):.2f}")


if __name__ == "__main__":
    main()