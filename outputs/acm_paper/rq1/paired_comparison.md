# RQ1 Paired Per-Image Comparison

| Model A | Model B | n | Mean Dice A | Mean Dice B | Paired difference (A-B) | 95% paired bootstrap CI | Wilcoxon p |
|---|---|---:|---:|---:|---:|---:|---:|
| U-Net + MobileNetV2 | U-Net + ResNet34 | 15 | 0.8819 | 0.8620 | +0.0198 | [-0.0003, +0.0415] | 0.1205 |

The fixed 15-image split does not measure sensitivity to data splitting or training randomness.
