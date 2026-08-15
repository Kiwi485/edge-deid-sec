"""
adapter.py — YOLO Dataset Adapter for ACM Paper RQ1
=====================================================
Converts the tongue segmentation dataset into YOLO segmentation format
so that YOLOv8n-seg can be trained on the **same samples** as the three
SMP models (U-Net variants and DeepLabV3+).

Conversion rules
----------------
- Source: COCO JSON (Roboflow export) or flat images + PNG masks.
- Target: YOLO polygon segmentation format.
  Each label file line: ``class_id x1_n y1_n x2_n y2_n … xn_n yn_n``
  where coordinates are normalised to [0, 1].
- Class ID is always 0 (tongue is the only class).
- The original dataset is NEVER modified.
- Converted labels and a ``data.yaml`` are written under
  ``outputs/acm_paper/rq1/yolo_dataset/``.
- Conversion metadata is saved as
  ``outputs/acm_paper/rq1/yolo_conversion_meta.json``.

IMPORTANT
---------
- YOLO uses its own native Ultralytics compound segmentation loss.
  Do NOT claim that YOLO uses BCE + Dice loss.
- The Ultralytics training objective differs from the SMP models.
  The comparison is fair at the level of unified test metrics and
  identical dataset splits.

Usage
-----
::

    from experiments.acm_paper.rq1_model_selection.yolo.adapter import (
        prepare_yolo_dataset,
    )
    yaml_path = prepare_yolo_dataset(
        data_dir="path/to/dataset",
        manifest=manifest_dict,
        output_dir="outputs/acm_paper/rq1/yolo_dataset",
    )
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

TONGUE_CLASS_ID = 0
CLASS_NAMES = ["tongue"]


# ---------------------------------------------------------------------------
# Conversion: COCO polygon → YOLO polygon
# ---------------------------------------------------------------------------

def _coco_polygon_to_yolo(
    segmentation: List[List[float]],
    img_width: int,
    img_height: int,
) -> Optional[str]:
    """
    Convert a COCO segmentation polygon list to one YOLO polygon line.

    Parameters
    ----------
    segmentation : list of polygon coordinate lists
        Each polygon is [x1, y1, x2, y2, ..., xn, yn] in pixel coords.
    img_width, img_height : int
        Image dimensions for normalisation.

    Returns
    -------
    str | None
        YOLO label line, or None if the polygon is degenerate (< 3 points).
    """
    if not segmentation:
        return None

    # Merge all polygons of the same annotation into one line per polygon
    lines = []
    for poly in segmentation:
        if len(poly) < 6:
            continue  # Need at least 3 points (6 values)
        coords = []
        for i in range(0, len(poly) - 1, 2):
            x_n = max(0.0, min(1.0, poly[i] / img_width))
            y_n = max(0.0, min(1.0, poly[i + 1] / img_height))
            coords.extend([f"{x_n:.6f}", f"{y_n:.6f}"])
        if coords:
            lines.append(f"{TONGUE_CLASS_ID} " + " ".join(coords))

    return "\n".join(lines) if lines else None


# ---------------------------------------------------------------------------
# Conversion: PNG mask → YOLO polygon (contour-based)
# ---------------------------------------------------------------------------

def _mask_to_yolo_polygon(
    mask_path: Path,
    img_width: int,
    img_height: int,
) -> Optional[str]:
    """
    Extract the largest contour from a binary mask PNG and convert to
    a YOLO polygon label line.
    """
    try:
        import cv2
    except ImportError:
        return None

    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return None
    _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # Use the largest contour
    contour = max(contours, key=cv2.contourArea)
    if len(contour) < 3:
        return None

    coords = []
    for pt in contour.squeeze():
        x_n = max(0.0, min(1.0, float(pt[0]) / img_width))
        y_n = max(0.0, min(1.0, float(pt[1]) / img_height))
        coords.extend([f"{x_n:.6f}", f"{y_n:.6f}"])

    return f"{TONGUE_CLASS_ID} " + " ".join(coords)


# ---------------------------------------------------------------------------
# Build YOLO split from manifest
# ---------------------------------------------------------------------------

def _prepare_split(
    split_name: str,
    manifest: Dict,
    data_dir: Path,
    yolo_dir: Path,
    conversion_log: List[Dict],
) -> int:
    """
    Create YOLO images/ and labels/ for one split.

    Returns the number of successfully converted samples.
    """
    try:
        import cv2
    except ImportError:
        print("[adapter] WARNING: opencv-python not found.  Mask conversion unavailable.")
        cv2 = None  # type: ignore

    images_out = yolo_dir / "images" / split_name
    labels_out = yolo_dir / "labels" / split_name
    images_out.mkdir(parents=True, exist_ok=True)
    labels_out.mkdir(parents=True, exist_ok=True)

    # Locate COCO JSON if available (Roboflow format)
    coco_data: Optional[Dict] = None
    coco_ann_by_img: Dict[str, List] = {}
    coco_img_dims: Dict[str, Tuple[int, int]] = {}

    # Try to load COCO JSON for this split
    source_split_name = split_name if split_name != "val" else "valid"
    for split_candidate in [source_split_name, split_name]:
        coco_candidates = [
            data_dir / split_candidate / "_annotations.coco.json",
            data_dir / split_candidate / "annotations" / "instances_default.json",
            data_dir / split_candidate / "annotations" / f"instances_{split_candidate}.json",
        ]
        for cp in coco_candidates:
            if cp.exists():
                with open(cp, "r", encoding="utf-8") as f:
                    coco_data = json.load(f)
                # Build lookup: filename → annotations + dims
                id2img = {img["id"]: img for img in coco_data.get("images", [])}
                for ann in coco_data.get("annotations", []):
                    img_info = id2img.get(ann["image_id"])
                    if img_info:
                        fname = img_info["file_name"]
                        coco_ann_by_img.setdefault(fname, []).append(ann)
                        coco_img_dims[fname] = (img_info["width"], img_info["height"])
                break
        if coco_data is not None:
            break

    # Filter manifest to this split
    split_samples = [
        s for s in manifest.get("samples", [])
        if s.get("assigned_split") == split_name
    ]

    converted = 0
    for sample in split_samples:
        rel_path = sample["image_path"]
        img_src = data_dir / rel_path
        if not img_src.exists():
            conversion_log.append({"file": rel_path, "status": "image_not_found"})
            continue

        stem = img_src.stem
        img_dst = images_out / img_src.name

        # Get image dimensions
        if cv2 is not None:
            img_cv = cv2.imread(str(img_src))
            if img_cv is None:
                conversion_log.append({"file": rel_path, "status": "cannot_read_image"})
                continue
            img_h, img_w = img_cv.shape[:2]
        elif img_src.name in coco_img_dims:
            img_w, img_h = coco_img_dims[img_src.name]
        else:
            conversion_log.append({"file": rel_path, "status": "cannot_get_dims"})
            continue

        # Generate YOLO label
        label_lines = []

        # Try COCO annotations first
        fname_key = img_src.name
        if fname_key in coco_ann_by_img:
            for ann in coco_ann_by_img[fname_key]:
                segs = ann.get("segmentation", [])
                line = _coco_polygon_to_yolo(segs, img_w, img_h)
                if line:
                    label_lines.append(line)

        # Fall back to mask PNG
        if not label_lines:
            for mask_dir in [
                data_dir / "masks",
                data_dir / (source_split_name + "/masks"),
                data_dir / (split_name + "/masks"),
            ]:
                for ext in [".png", ".jpg"]:
                    mp = mask_dir / f"{stem}{ext}"
                    if mp.exists():
                        line = _mask_to_yolo_polygon(mp, img_w, img_h)
                        if line:
                            label_lines.append(line)
                        break
                if label_lines:
                    break

        if not label_lines:
            conversion_log.append({"file": rel_path, "status": "no_annotations_found"})
            # Still copy image (YOLO can handle images without labels as negatives)
            shutil.copy2(img_src, img_dst)
            # Write empty label file
            (labels_out / f"{stem}.txt").write_text("")
            continue

        # Write YOLO label
        label_text = "\n".join(label_lines)
        (labels_out / f"{stem}.txt").write_text(label_text, encoding="utf-8")

        # Copy image
        shutil.copy2(img_src, img_dst)
        converted += 1
        conversion_log.append({"file": rel_path, "status": "ok"})

    return converted


# ---------------------------------------------------------------------------
# data.yaml creation
# ---------------------------------------------------------------------------

def _write_data_yaml(yolo_dir: Path, class_names: List[str]) -> Path:
    """Write a data.yaml compatible with Ultralytics YOLO."""
    import yaml  # pyyaml

    data = {
        "path": str(yolo_dir.resolve()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "nc": len(class_names),
        "names": class_names,
    }

    yaml_path = yolo_dir / "data.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    return yaml_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def prepare_yolo_dataset(
    data_dir: str,
    manifest: Dict,
    output_dir: str = "outputs/acm_paper/rq1/yolo_dataset",
    force_recreate: bool = False,
) -> Path:
    """
    Convert the tongue dataset into YOLO segmentation format.

    Uses the split manifest to ensure exactly the same samples are used
    as for the SMP models.  The original dataset is never modified.

    Parameters
    ----------
    data_dir : str
        Source dataset root directory.
    manifest : dict
        Loaded split manifest (from dataset_split.create_or_load_manifest).
    output_dir : str
        Where to write the YOLO dataset.
    force_recreate : bool
        If True, delete and recreate the YOLO dataset even if it exists.

    Returns
    -------
    Path
        Absolute path to the ``data.yaml`` file for Ultralytics training.

    Raises
    ------
    SystemExit
        If the source dataset directory does not exist.
    """
    data_path = Path(data_dir)
    yolo_dir = Path(output_dir)
    yaml_path = yolo_dir / "data.yaml"
    meta_path = yolo_dir.parent / "yolo_conversion_meta.json"

    if not data_path.is_dir():
        print(f"[adapter] ERROR: Dataset not found: {data_dir}")
        sys.exit(1)

    if yaml_path.exists() and not force_recreate:
        print(f"[adapter] YOLO dataset already exists at {yolo_dir}.  Loading data.yaml.")
        return yaml_path

    print(f"[adapter] Preparing YOLO dataset at {yolo_dir} …")
    if yolo_dir.exists() and force_recreate:
        shutil.rmtree(yolo_dir)

    conversion_log: List[Dict] = []
    counts: Dict[str, int] = {}

    for split in ("train", "val", "test"):
        n = _prepare_split(split, manifest, data_path, yolo_dir, conversion_log)
        counts[split] = n
        print(f"[adapter]   {split}: {n} samples converted")

    yaml_path = _write_data_yaml(yolo_dir, CLASS_NAMES)
    print(f"[adapter] data.yaml written → {yaml_path}")

    # Save conversion metadata
    meta = {
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "source_data_dir": str(data_path.resolve()),
        "yolo_dataset_dir": str(yolo_dir.resolve()),
        "data_yaml": str(yaml_path),
        "split_counts": counts,
        "conversion_log": conversion_log,
        "total_ok": sum(1 for e in conversion_log if e["status"] == "ok"),
        "total_errors": sum(1 for e in conversion_log if e["status"] != "ok"),
        "note": (
            "YOLO uses its native Ultralytics compound segmentation loss. "
            "This dataset was prepared for training YOLOv8n-seg using the "
            "same samples and split as the SMP models."
        ),
    }
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[adapter] Conversion metadata → {meta_path}")

    return yaml_path
