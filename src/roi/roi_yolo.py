from pathlib import Path


def load_yolo_bbox(label_path, image_shape):
    """Read a YOLO-format label file and return a pixel bbox.

    YOLO label format (one line per object):
        <class_id> <x_center> <y_center> <width> <height>
    All values are normalized to [0, 1] relative to image dimensions.

    Only the first line is used (tongue ROI produces one bbox per image).

    Args:
        label_path: str or Path pointing to the .txt label file.
        image_shape: tuple (H, W) or (H, W, C) matching image.shape.

    Returns:
        tuple: (bbox, status, error)
            bbox:   [x1, y1, x2, y2] as ints, or [] on failure.
            status: "ok" or "error".
            error:  empty string on success, reason string on failure.
    """
    label_path = Path(label_path)

    if not label_path.exists():
        return [], "error", f"label file not found: {label_path}"

    h_img, w_img = image_shape[:2]
    if h_img <= 0 or w_img <= 0:
        return [], "error", "invalid image_shape"

    try:
        raw = label_path.read_text(encoding="utf-8")
    except Exception as exc:
        return [], "error", f"failed to read label file: {exc}"

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return [], "error", "label file is empty"

    parts = lines[0].split()
    if len(parts) != 5:
        return [], "error", f"expected 5 fields, got {len(parts)}: '{lines[0]}'"

    try:
        _, xc, yc, bw, bh = (float(v) for v in parts)
    except ValueError:
        return [], "error", f"non-numeric value in label: '{lines[0]}'"

    for name, val in [("xc", xc), ("yc", yc), ("bw", bw), ("bh", bh)]:
        if not (0.0 <= val <= 1.0):
            return [], "error", f"{name}={val:.4f} out of [0, 1] range"

    x1 = int((xc - bw / 2) * w_img)
    y1 = int((yc - bh / 2) * h_img)
    x2 = int((xc + bw / 2) * w_img)
    y2 = int((yc + bh / 2) * h_img)

    # Clamp to image bounds.
    x1 = max(0, min(x1, w_img - 1))
    y1 = max(0, min(y1, h_img - 1))
    x2 = max(x1 + 1, min(x2, w_img))
    y2 = max(y1 + 1, min(y2, h_img))

    if x2 <= x1 or y2 <= y1:
        return [], "error", "degenerate bbox after clamp"

    return [x1, y1, x2, y2], "ok", ""
