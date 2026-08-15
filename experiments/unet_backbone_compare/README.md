# U-Net Backbone Comparison for Tongue Segmentation

This experiment trains and compares binary tongue segmentation models using the same segmentation architecture with different encoders:

- U-Net + MobileNetV2 encoder
- U-Net + ResNet encoder (`resnet18` or `resnet34`)

U-Net is the segmentation architecture. MobileNetV2 and ResNet are encoder backbones inside U-Net; they are not treated as independent segmentation models.

## Dataset

Expected CVAT layout:

```text
cvat/train/
  annotations/
  images/
```

This repository currently contains the inspected dataset at:

```text
data/cvat/train/
  annotations/instances_default_merged.json
  images/
```

The annotation file is COCO-style JSON with polygon `segmentation` entries for category `tongue`, which is suitable for binary segmentation. The dataset loader also supports CVAT XML polygons/masks and existing mask PNG files.

Mask convention:

- tongue = `1`
- background = `0`

## Requirements

Install PyTorch and torchvision for your CUDA/CPU environment. The scripts also use Pillow, NumPy, pandas-compatible CSV output, and matplotlib.

Compressed COCO RLE masks require `pycocotools`, but polygon COCO annotations like the current dataset do not.

## Train U-Net + MobileNetV2

```bash
python experiments/unet_backbone_compare/train_unet_compare.py --data-root data/cvat/train --encoder mobilenet_v2 --epochs 50 --batch-size 8 --img-size 256 --exp-name unet_mobilenetv2
```

## Train U-Net + ResNet

```bash
python experiments/unet_backbone_compare/train_unet_compare.py --data-root data/cvat/train --encoder resnet34 --epochs 50 --batch-size 8 --img-size 256 --exp-name unet_resnet34
```

You can also use `--encoder resnet18`.

By default the models start without pretrained weights to avoid requiring internet access. Add `--pretrained` if ImageNet weights are already cached or your environment can download them.

## Outputs

Each run saves outputs to:

```text
runs/unet_backbone_compare/{exp_name}/
  best_model.pth
  metrics.csv
  final_summary.json
  train_loss_curve.png
  val_loss_curve.png
  train_dice_curve.png
  val_dice_curve.png
  train_iou_curve.png
  val_iou_curve.png
  prediction_visualization.png
```

`final_summary.json` includes the model name, encoder name, best validation Dice/IoU, precision, recall, pixel accuracy, parameter count, and average inference time per image.

## Compare Runs

After training both models:

```bash
python experiments/unet_backbone_compare/compare_results.py
```

Default inputs:

```text
runs/unet_backbone_compare/unet_mobilenetv2/final_summary.json
runs/unet_backbone_compare/unet_resnet34/final_summary.json
```

Comparison outputs:

```text
runs/unet_backbone_compare/comparison_table.csv
runs/unet_backbone_compare/comparison_bar_chart.png
```
