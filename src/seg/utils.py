"""
utils.py — 共用輔助函式
- load_image_rgb : 讀取影像並轉 RGB
- polygon_to_mask: COCO polygon list → binary mask (0/255 uint8)
- yolo_bbox_to_mask: YOLO bbox txt → pseudo-mask (filled rectangle)
"""

import json
from pathlib import Path
from typing import List

import cv2
import numpy as np
from PIL import Image, ImageDraw


# ---------------------------------------------------------------------------
# Image loading
# ---------------------------------------------------------------------------

def load_image_rgb(path: str) -> np.ndarray:
    """讀取影像，回傳 RGB numpy array (H, W, 3) uint8。"""
    img = cv2.imread(str(path))
    if img is None:
        raise FileNotFoundError(f"Cannot load image: {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


# ---------------------------------------------------------------------------
# Mask generation
# ---------------------------------------------------------------------------

def polygon_to_mask(
    segmentation: List[List[float]],
    height: int,
    width: int,
) -> np.ndarray:
    """把 COCO segmentation polygons 轉成 binary mask (0/255, uint8 H×W)。"""
    pil_mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(pil_mask)
    for seg in segmentation:
        if len(seg) >= 6:
            pts = [(seg[i], seg[i + 1]) for i in range(0, len(seg) - 1, 2)]
            draw.polygon(pts, fill=255)
    return np.array(pil_mask, dtype=np.uint8)


def yolo_bbox_to_mask(txt_path: str, height: int, width: int) -> np.ndarray:
    """
    把 YOLO bbox 格式的 .txt 轉成填滿矩形的 pseudo-mask。
    用於尚未有精確 polygon 標註的圖片。
    """
    mask = np.zeros((height, width), dtype=np.uint8)
    with open(txt_path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            cx, cy, bw, bh = (
                float(parts[1]),
                float(parts[2]),
                float(parts[3]),
                float(parts[4]),
            )
            x1 = max(0, int((cx - bw / 2) * width))
            y1 = max(0, int((cy - bh / 2) * height))
            x2 = min(width - 1, int((cx + bw / 2) * width))
            y2 = min(height - 1, int((cy + bh / 2) * height))
            mask[y1:y2, x1:x2] = 255
    return mask


# ---------------------------------------------------------------------------
# COCO JSON helper
# ---------------------------------------------------------------------------

def build_coco_sample_list(split_dir: Path, coco_json: Path) -> list:
    """
    解析 Roboflow 匯出的 _annotations.coco.json，
    回傳 list of dict: {image_path, annotations (list), height, width}
    """
    with open(coco_json, "r", encoding="utf-8") as f:
        coco = json.load(f)

    id2img = {img["id"]: img for img in coco.get("images", [])}

    ann_by_img: dict = {}
    for ann in coco.get("annotations", []):
        ann_by_img.setdefault(ann["image_id"], []).append(ann)

    samples = []
    for img_info in coco.get("images", []):
        # 圖片可能在 split_dir 或 split_dir/images/
        fname = img_info["file_name"]
        img_path = split_dir / fname
        if not img_path.exists():
            img_path = split_dir / "images" / fname
        if not img_path.exists():
            continue

        samples.append(
            {
                "image_path": img_path,
                "annotations": ann_by_img.get(img_info["id"], []),
                "height": img_info["height"],
                "width": img_info["width"],
                "source": "coco",
            }
        )
    return samples
