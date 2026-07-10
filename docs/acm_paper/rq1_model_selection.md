# RQ1 Model Selection for Edge-Based Tongue Segmentation

## 1. Research Question

**RQ1**: Which segmentation model provides the best balance between segmentation
accuracy and computational complexity for an edge-based de-identification pipeline?

## 2. Experiment Motivation

The production de-identification pipeline (under `src/seg/`) must run on
resource-constrained edge devices.  Before committing to a single architecture
for RQ2–RQ4, this experiment systematically compares four candidate models
across accuracy, model size, and inference latency metrics.

The model selected in RQ1 becomes the primary segmentation backbone for all
subsequent research questions.

## 3. Compared Models

| Model | Architecture | Encoder | Class |
|-------|-------------|---------|-------|
| U-Net + MobileNetV2   | U-Net           | MobileNetV2  | Lightweight |
| U-Net + ResNet34      | U-Net           | ResNet34     | Medium      |
| DeepLabV3+ + ResNet50 | DeepLabV3+      | ResNet50     | Heavy       |
| YOLOv8n-seg           | YOLO v8 nano    | CSPDarknet   | Detector-based |

## 4. Why These Four Models

- **U-Net + MobileNetV2** — Lightweight backbone suitable for edge deployment.
  Already used in the production pipeline.
- **U-Net + ResNet34** — Richer feature extraction than MobileNetV2 while
  maintaining a reasonable parameter count.
- **DeepLabV3+ + ResNet50** — ASPP multi-scale context captures fine-grained
  tongue boundaries; heavier but potentially more accurate.
- **YOLOv8n-seg** — Real-time instance segmentation baseline widely used in
  edge-deployed pipelines; trained via the Ultralytics framework.

## 5. Dataset Requirements

- Tongue segmentation images with corresponding binary masks.
- Supported annotation formats (see §6).
- Minimum recommended dataset size: ≥ 100 labelled images for meaningful
  70/15/15 splits.

> **Privacy warning**: Do NOT commit real participant tongue images, masks
> containing private identifiers, or any personally identifiable biometric data
> to this repository.  All participant images must be stored outside the
> repository.

## 6. Supported Dataset Formats

| Format | Detection condition |
|--------|---------------------|
| **Roboflow COCO** | `data_dir/train/_annotations.coco.json` |
| **CVAT COCO** | `data_dir/train/annotations/instances_default.json` |
| **Flat images + PNG masks** | `data_dir/images/` + `data_dir/masks/` |

## 7. Split Policy

### Predefined splits (Roboflow / CVAT)

If the dataset already contains `train/`, `valid/` (or `val/`), and `test/`
directories, those splits are preserved.  The actual ratios are reported
honestly — they are **not** silently claimed to be 70/15/15 if they differ.

### Flat dataset (no predefined splits)

A deterministic 70% / 15% / 15% split is created using a configurable seed
(default 42).  The split is saved to a manifest JSON and never regenerated
automatically.

### Manifest

The split manifest is stored at:

```
outputs/acm_paper/rq1/split_manifest.json
```

All four models use **exactly the same manifest**.  This file must be
created before training and must not be deleted between model runs.

## 8. Metric Definitions

All final paper metrics are computed by
`experiments/acm_paper/rq1_model_selection/metrics.py` using
**pixel-level micro-averaging** across the full test set.

| Metric | Formula |
|--------|---------|
| Dice (F1) | 2·TP / (2·TP + FP + FN) |
| IoU (Jaccard) | TP / (TP + FP + FN) |
| Precision | TP / (TP + FP) |
| Recall | TP / (TP + FN) |
| Pixel Accuracy | (TP + TN) / (TP + FP + FN + TN) |

A small epsilon (1e-8) is applied to all denominators to prevent
division-by-zero.  Empty masks produce numerically stable values near 0 or 1,
never NaN.

### Confusion counts
- **TP**: foreground pixels correctly predicted as foreground.
- **FP**: background pixels incorrectly predicted as foreground.
- **FN**: foreground pixels incorrectly predicted as background.
- **TN**: background pixels correctly predicted as background.

## 9. Difference Between Training Metrics and Final Test Metrics

| Metric type | Where computed | Purpose |
|-------------|---------------|---------|
| **Epoch Dice/IoU** | `src/seg/train.py` (batch-level avg) | Training monitoring only |
| **Final paper Dice/IoU** | `metrics.py` (micro-avg full test set) | **Official paper results** |

Epoch Dice/IoU are averaged over batches and can overestimate performance on
imbalanced datasets.  They are useful for watching convergence during training
but must **never** be used as the final reported paper metric.

Final paper metrics accumulate TP/FP/FN/TN counts across every test pixel and
compute global ratios.  This is the standard for binary segmentation evaluation
in medical imaging literature.

## 10. YOLO Training-Loss Limitation

YOLOv8n-seg uses Ultralytics' **native compound segmentation loss**:

- Box regression loss
- Classification loss
- Segmentation mask loss (dice-like)

This is fundamentally different from the `BCEWithLogitsLoss + DiceLoss`
used by the SMP models.  **Do not claim that all four models use the same
loss function** — they do not.

The comparison is fair at the level of:
- Identical dataset samples and split
- Identical input resolution (256 × 256)
- Identical final segmentation metrics (from `metrics.py`)
- Same held-out test set

## 11. Training Commands

### SMP models (U-Net variants + DeepLabV3+)

Via the unified RQ1 runner:

```bash
python -m experiments.acm_paper.rq1_model_selection.run_rq1 \
    --data-dir /path/to/dataset \
    --epochs 50 \
    --batch-size 8 \
    --img-size 256 \
    --lr 1e-4 \
    --seed 42 \
    --output-dir outputs/acm_paper/rq1 \
    --model-dir models/acm_paper/rq1
```

Via the existing production trainer (not split-manifest-controlled):

```bash
python src/seg/train.py --data-dir /path/to/dataset --arch unet_mobilenet --epochs 50
python src/seg/train.py --data-dir /path/to/dataset --arch unet_resnet    --epochs 50
python src/seg/train.py --data-dir /path/to/dataset --arch deeplabv3      --epochs 50
```

### YOLO

```bash
python -m experiments.acm_paper.rq1_model_selection.yolo.train_yolo \
    --data-dir /path/to/dataset \
    --model yolov8n-seg.pt \
    --epochs 50 \
    --img-size 256 \
    --batch-size 8 \
    --seed 42 \
    --split-manifest outputs/acm_paper/rq1/split_manifest.json \
    --output-dir models/acm_paper/rq1/yolov8n_seg
```

## 12. Evaluation Commands

### Evaluate one SMP model

```bash
python -m experiments.acm_paper.rq1_model_selection.evaluate_smp \
    --data-dir /path/to/dataset \
    --arch unet_mobilenet \
    --checkpoint models/acm_paper/rq1/unet_mobilenet/best.pth \
    --split test \
    --img-size 256 \
    --threshold 0.5 \
    --split-manifest outputs/acm_paper/rq1/split_manifest.json \
    --output outputs/acm_paper/rq1/unet_mobilenet.json
```

Replace `--arch` and `--checkpoint` for other SMP models.

### Evaluate YOLO

```bash
python -m experiments.acm_paper.rq1_model_selection.yolo.evaluate_yolo \
    --data-dir /path/to/dataset \
    --checkpoint models/acm_paper/rq1/yolov8n_seg/weights/best.pt \
    --split test \
    --img-size 256 \
    --split-manifest outputs/acm_paper/rq1/split_manifest.json \
    --output outputs/acm_paper/rq1/yolov8n_seg.json
```

### Run everything (train + evaluate all four models)

```bash
python -m experiments.acm_paper.rq1_model_selection.run_rq1 \
    --data-dir /path/to/dataset \
    --epochs 50 \
    --batch-size 8 \
    --img-size 256 \
    --seed 42
```

### Evaluate only (models already trained)

```bash
python -m experiments.acm_paper.rq1_model_selection.run_rq1 \
    --data-dir /path/to/dataset \
    --evaluate-only \
    --model-dir models/acm_paper/rq1
```

## 13. Output File Descriptions

| File | Description |
|------|-------------|
| `outputs/acm_paper/rq1/split_manifest.json` | Fixed dataset split (all models must use this) |
| `outputs/acm_paper/rq1/unet_mobilenet.json` | Full evaluation result for U-Net + MobileNetV2 |
| `outputs/acm_paper/rq1/unet_resnet.json` | Full evaluation result for U-Net + ResNet34 |
| `outputs/acm_paper/rq1/deeplabv3.json` | Full evaluation result for DeepLabV3+ + ResNet50 |
| `outputs/acm_paper/rq1/yolov8n_seg.json` | Full evaluation result for YOLOv8n-seg |
| `outputs/acm_paper/rq1/results.csv` | Summary table (all four models) |
| `outputs/acm_paper/rq1/results.json` | Summary table + full results |
| `outputs/acm_paper/rq1/results.md` | Markdown table for paper |
| `outputs/acm_paper/rq1/yolo_dataset/data.yaml` | YOLO dataset config |
| `outputs/acm_paper/rq1/yolo_conversion_meta.json` | YOLO conversion log |
| `outputs/acm_paper/rq1/figures/` | Qualitative visualisations (generated on demand) |

Each model result JSON includes:
- Dice, IoU, Precision, Recall, Pixel Accuracy
- TP, FP, FN, TN (global counts)
- Per-image mean/std for each metric
- Trainable and total parameter count
- Checkpoint size (MB)
- Mean, median, p95 latency (ms/image)
- Throughput (FPS)
- Peak GPU memory (if CUDA was used)
- Hardware and software environment metadata
- Per-image confusion records (for bootstrap CI)

## 14. Reproducibility Controls

| Control | Implementation |
|---------|---------------|
| Fixed split | `split_manifest.json` (identical for all models) |
| Fixed seed | `--seed 42` (default) |
| Same resolution | 256 × 256 (configurable, same across all models) |
| Same test preprocessing | `TongueSegDataset` val transforms (resize + normalize) |
| Same metric formulas | `metrics.py` only |
| Best checkpoint by val Dice | Not test Dice |
| No test set for tuning | Threshold set before test evaluation |

## 15. Missing-Data Behaviour

When the dataset is not yet uploaded:

- `--help` always works for all CLI scripts.
- Importing any module does **not** trigger training.
- All scripts print a clear, actionable error message.
- Exit code is non-zero only when actual execution fails.

Example:

```
[run_rq1] ERROR: Dataset directory not found: /path/to/dataset
          The experiment framework is ready but requires real image data.
          Upload the dataset and re-run with --data-dir.
```

## 16. How to Run After Dataset Upload

1. Organise dataset as Roboflow COCO or flat format.
2. Create split manifest:
   ```bash
   python -m experiments.acm_paper.rq1_model_selection.dataset_split \
       --data-dir /path/to/dataset \
       --manifest outputs/acm_paper/rq1/split_manifest.json \
       --seed 42
   ```
3. Run full experiment:
   ```bash
   python -m experiments.acm_paper.rq1_model_selection.run_rq1 \
       --data-dir /path/to/dataset \
       --epochs 50 \
       --batch-size 8 \
       --seed 42
   ```
4. Review results:
   ```bash
   cat outputs/acm_paper/rq1/results.md
   ```

## 17. How to Add Another Segmentation Model

1. If it uses `segmentation_models_pytorch`:
   - Add the architecture to `src/seg/model.py` under `build_model_by_arch()`.
   - Add the arch key to `ARCH_CHOICES` and `ARCH_DISPLAY_NAMES`.
   - Train via `run_rq1.py` by passing the new `--arch`.
   - Evaluate via `evaluate_smp.py`.

2. If it uses a different framework:
   - Create a new directory under
     `experiments/acm_paper/rq1_model_selection/<framework>/`.
   - Implement `train_<framework>.py` and `evaluate_<framework>.py`
     following the same pattern as `yolo/train_yolo.py` and
     `yolo/evaluate_yolo.py`.
   - Use `SegmentationMetricsAccumulator` from `metrics.py` for evaluation.
   - Add the model to `run_rq1.py` and `aggregate_and_export()`.

## 18. Privacy Warning

**Never commit to this repository:**

- Real participant tongue images
- Tongue segmentation masks that reveal participant identity
- Any personally identifiable biometric data
- Files under `data/private/` or `data/raw/*.jpg`
- Trained model weights (already ignored by `models/`)
- Generated evaluation outputs (already ignored by `outputs/`)

The `.gitignore` is configured to block common image formats in dataset
directories.  However, the repository owner is ultimately responsible for
ensuring no private data is committed.

## 19. Directory Separation

| Directory | Purpose |
|-----------|---------|
| `src/seg/` | **Production** segmentation pipeline (backward compatible) |
| `experiments/acm_paper/rq1_model_selection/` | **ACM paper** RQ1 experiment code |
| `outputs/acm_paper/rq1/` | Generated experiment results (gitignored) |
| `models/acm_paper/rq1/` | Paper-specific checkpoints (gitignored) |
| `docs/acm_paper/` | Experiment documentation |

The production pipeline (`src/seg/`) must remain fully functional and backward
compatible regardless of any changes made to the experiment code.  Do not
rename, replace, or restructure `src/seg/` for paper-specific reasons.

## 20. No Results Available Yet

> **No experiment results are available until the real dataset is uploaded
> and evaluated.**  The `results.csv`, `results.json`, and `results.md`
> files contain only `N/A` placeholders until all four models have been
> trained and evaluated on the actual dataset.
