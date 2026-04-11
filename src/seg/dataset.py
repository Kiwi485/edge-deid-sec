"""
dataset.py — TongueSegDataset
自動偵測三種格式：
  1. Roboflow COCO-seg:  data_dir/train/_annotations.coco.json + 圖片
  2. Flat:               data_dir/images/ + data_dir/masks/
  3. YOLO fallback:      data_dir/images/ + data_dir/labels/*.txt (pseudo-mask)
"""

import random
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw
import torch
from torch.utils.data import Dataset

import albumentations as A
from albumentations.pytorch import ToTensorV2

try:
    from seg.utils import polygon_to_mask, yolo_bbox_to_mask, build_coco_sample_list
except ImportError:
    from src.seg.utils import polygon_to_mask, yolo_bbox_to_mask, build_coco_sample_list

IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


# ---------------------------------------------------------------------------
# Transform builders
# ---------------------------------------------------------------------------

def get_transforms(img_size: int, is_train: bool) -> A.Compose:
    mean = [0.485, 0.456, 0.406]
    std = [0.229, 0.224, 0.225]
    if is_train:
        return A.Compose(
            [
                A.Resize(img_size, img_size),
                A.HorizontalFlip(p=0.5),
                A.RandomRotate90(p=0.3),
                A.Affine(translate_percent=0.05, scale=(0.9, 1.1), rotate=(-15, 15), p=0.4),
                A.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.05, p=0.5),
                A.GaussNoise(p=0.2),
                A.Normalize(mean=mean, std=std),
                ToTensorV2(),
            ]
        )
    else:
        return A.Compose(
            [
                A.Resize(img_size, img_size),
                A.Normalize(mean=mean, std=std),
                ToTensorV2(),
            ]
        )


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class TongueSegDataset(Dataset):
    """
    舌頭 segmentation dataset。

    Parameters
    ----------
    data_dir : str
        資料集根目錄。
    split : str
        'train' | 'valid' | 'val' | 'test' | '' (空字串 = 不用 split 子目錄)
    img_size : int
        Resize 後的正方形邊長。
    is_train : bool
        是否套用訓練增強。若 transform 已指定則此參數無效。
    transform : albumentations.Compose | None
        自訂 transform，None 時自動選擇。
    indices : list[int] | None
        若指定，只使用 sample list 中對應的子集（用於手動 train/val 切分）。
    """

    def __init__(
        self,
        data_dir: str,
        split: str = "train",
        img_size: int = 256,
        is_train: bool = True,
        transform=None,
        indices: Optional[List[int]] = None,
    ):
        self.data_dir = Path(data_dir)
        self.split = split
        self.img_size = img_size
        self.is_train = is_train
        self.transform = transform if transform is not None else get_transforms(img_size, is_train)

        self._samples: list = []  # list of dict (see _detect_and_load)
        self._detect_and_load()

        if indices is not None:
            self._samples = [self._samples[i] for i in indices if i < len(self._samples)]

        if len(self._samples) == 0:
            print(f"[Warning] No images found in '{self.data_dir}' (split='{self.split}')")

    # ------------------------------------------------------------------
    # Format detection
    # ------------------------------------------------------------------

    def _detect_and_load(self):
        data_dir = self.data_dir
        split = self.split

        # ── Format 1: Roboflow / CVAT COCO ──────────────────────────────
        # Roboflow: split_dir/_annotations.coco.json
        # CVAT:     split_dir/annotations/instances_default.json
        #           split_dir/annotations/instances_train.json  (CVAT per-split)
        if split:
            for candidate_split in [split, "val" if split == "valid" else split]:
                split_dir = data_dir / candidate_split
                coco_candidates = [
                    split_dir / "_annotations.coco.json",                          # Roboflow
                    split_dir / "annotations" / "instances_default.json",           # CVAT default
                    split_dir / "annotations" / f"instances_{candidate_split}.json",# CVAT per-split
                    split_dir / "annotations" / "result.json",                      # CVAT result export
                ]
                for coco_json in coco_candidates:
                    if coco_json.exists():
                        self._samples = build_coco_sample_list(split_dir, coco_json)
                        return

        # ── Format 2 & 3: Flat images/ + masks/ or labels/ ─────────────
        # Determine images folder
        candidates = []
        if split:
            candidates.append(data_dir / split / "images")
            candidates.append(data_dir / split)
        candidates.append(data_dir / "images")
        candidates.append(data_dir)

        images_dir = next((p for p in candidates if p.is_dir()), None)
        if images_dir is None:
            return

        masks_dir_candidates = [
            data_dir / "masks",
            data_dir / split / "masks" if split else None,
        ]
        masks_dir = next(
            (p for p in masks_dir_candidates if p and p.is_dir()), None
        )

        labels_dir_candidates = [
            data_dir / "labels",
            data_dir / split / "labels" if split else None,
            data_dir / "raw",
        ]
        labels_dir = next(
            (p for p in labels_dir_candidates if p and p.is_dir()), None
        )

        img_paths = sorted(
            p for p in images_dir.iterdir() if p.suffix.lower() in IMG_EXTENSIONS
        )

        for img_path in img_paths:
            stem = img_path.stem

            # Look for mask PNG
            mask_path = None
            if masks_dir:
                for ext in [".png", ".jpg", ".jpeg"]:
                    cand = masks_dir / f"{stem}{ext}"
                    if cand.exists():
                        mask_path = cand
                        break

            # YOLO bbox fallback
            yolo_path = None
            if mask_path is None and labels_dir:
                cand = labels_dir / f"{stem}.txt"
                if cand.exists():
                    yolo_path = cand

            self._samples.append(
                {
                    "image_path": img_path,
                    "mask_path": mask_path,
                    "yolo_path": yolo_path,
                    "annotations": None,  # not COCO
                    "source": "flat",
                }
            )

    # ------------------------------------------------------------------
    # Dataset interface
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._samples)

    def __getitem__(self, idx: int):
        s = self._samples[idx]

        # ── Load image ────────────────────────────────────────────────
        img = cv2.imread(str(s["image_path"]))
        if img is None:
            raise FileNotFoundError(f"Cannot read: {s['image_path']}")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = img.shape[:2]

        # ── Load / generate mask ─────────────────────────────────────
        if s.get("source") == "coco" and s.get("annotations") is not None:
            # Render polygon mask on the fly
            pil_mask = Image.new("L", (w, h), 0)
            draw = ImageDraw.Draw(pil_mask)
            for ann in s["annotations"]:
                for seg in ann.get("segmentation", []):
                    if len(seg) >= 6:
                        pts = [(seg[i], seg[i + 1]) for i in range(0, len(seg) - 1, 2)]
                        draw.polygon(pts, fill=255)
            mask = np.array(pil_mask, dtype=np.uint8)

        elif s.get("mask_path") is not None:
            mask = cv2.imread(str(s["mask_path"]), cv2.IMREAD_GRAYSCALE)
            if mask is None:
                mask = np.zeros((h, w), dtype=np.uint8)

        elif s.get("yolo_path") is not None:
            mask = yolo_bbox_to_mask(str(s["yolo_path"]), h, w)

        else:
            # No annotation: all-zero mask
            mask = np.zeros((h, w), dtype=np.uint8)

        # Binarize: 0.0 (background) / 1.0 (tongue)
        mask = (mask > 127).astype(np.float32)

        # ── Augment ───────────────────────────────────────────────────
        augmented = self.transform(image=img, mask=mask)
        img_t = augmented["image"]          # (C, H, W) float tensor
        mask_t = augmented["mask"]          # (H, W) float tensor
        mask_t = mask_t.unsqueeze(0)        # (1, H, W)

        return img_t, mask_t

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    def summary(self) -> str:
        n_coco = sum(1 for s in self._samples if s.get("source") == "coco")
        n_mask = sum(1 for s in self._samples if s.get("mask_path"))
        n_yolo = sum(1 for s in self._samples if s.get("yolo_path") and not s.get("mask_path"))
        n_none = len(self._samples) - n_coco - n_mask - n_yolo
        return (
            f"TongueSegDataset | split='{self.split}' | total={len(self._samples)} | "
            f"coco={n_coco} mask_png={n_mask} yolo_pseudo={n_yolo} no_ann={n_none}"
        )
