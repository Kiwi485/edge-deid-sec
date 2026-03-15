import numpy as np


def extract_roi_fixed(image):
    """Extract a deterministic fallback ROI from a BGR image.

    The crop is tuned for close-up oral images where the mouth tends to
    appear in the lower-center region of the frame.

    Returns:
        tuple: (roi_img, roi_bbox)
            roi_img: np.ndarray ROI image or None when input is invalid
            roi_bbox: [x1, y1, x2, y2] or [] when input is invalid
    """
    if image is None or not isinstance(image, np.ndarray):
        return None, []
    if image.ndim != 3 or image.shape[2] != 3:
        return None, []

    h, w = image.shape[:2]
    if h <= 1 or w <= 1:
        return None, []

    x1 = int(w * 0.20)
    x2 = int(w * 0.80)
    y1 = int(h * 0.35)
    y2 = int(h * 0.95)

    x1 = max(0, min(x1, w - 1))
    y1 = max(0, min(y1, h - 1))
    x2 = max(x1 + 1, min(x2, w))
    y2 = max(y1 + 1, min(y2, h))

    roi_img = image[y1:y2, x1:x2].copy()
    if roi_img.size == 0:
        return None, []

    return roi_img, [x1, y1, x2, y2]
