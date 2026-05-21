"""YOLOv8 tongue-ROI detector for real-time pipeline use.

Loads trained weights once (lazy singleton) and provides a function with
the same return contract as the other ROI extractors:

    img, bbox, status, error = predict_yolo_bbox(image)
"""
from pathlib import Path
from typing import Optional

import numpy as np


_MODEL = None
_WEIGHTS_PATH = Path("models/yolo/best.pt")
_DEFAULT_CONF = 0.25
_DEFAULT_IOU = 0.45


def _load_model(weights: Optional[Path] = None):
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    from ultralytics import YOLO

    path = Path(weights) if weights else _WEIGHTS_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"YOLO weights not found at {path}. "
            "Train first: python tools/train_yolo.py"
        )
    _MODEL = YOLO(str(path))
    return _MODEL


def predict_yolo_bbox(
    image: np.ndarray,
    conf: float = _DEFAULT_CONF,
    iou: float = _DEFAULT_IOU,
    weights: Optional[Path] = None,
):
    """Detect tongue ROI in an image using the trained YOLO model.

    Args:
        image: BGR uint8 ndarray (H, W, 3).
        conf: confidence threshold.
        iou: NMS IoU threshold.
        weights: optional override path to .pt weights.

    Returns:
        roi_img: cropped ROI ndarray, or None on failure.
        bbox:    [x1, y1, x2, y2] pixel ints, or [] on failure.
        status:  "ok" or "error".
        error:   reason string on failure, otherwise "".
    """
    if image is None or image.size == 0:
        return None, [], "error", "empty image"

    try:
        model = _load_model(weights)
    except FileNotFoundError as exc:
        return None, [], "error", str(exc)
    except Exception as exc:
        return None, [], "error", f"load_failed: {exc}"

    try:
        results = model.predict(
            image, conf=conf, iou=iou, verbose=False, device="cpu"
        )
    except Exception as exc:
        return None, [], "error", f"predict_failed: {exc}"

    if not results:
        return None, [], "error", "no result"

    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return None, [], "error", "no detection"

    confs = boxes.conf.cpu().numpy()
    best_idx = int(np.argmax(confs))
    xyxy = boxes.xyxy.cpu().numpy()[best_idx]
    h_img, w_img = image.shape[:2]
    x1 = max(0, int(xyxy[0]))
    y1 = max(0, int(xyxy[1]))
    x2 = min(w_img - 1, int(xyxy[2]))
    y2 = min(h_img - 1, int(xyxy[3]))

    if x2 <= x1 or y2 <= y1:
        return None, [], "error", "invalid bbox"

    roi_img = image[y1:y2, x1:x2].copy()
    return roi_img, [x1, y1, x2, y2], "ok", ""
