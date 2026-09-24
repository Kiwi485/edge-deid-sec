"""
visualize.py — ACM Paper RQ1: Qualitative Visualisation
========================================================
Generates qualitative segmentation visualisations for paper figures.

PRIVACY WARNING
---------------
Real tongue images of participants are **NOT** committed to this repository.
This module accepts real image paths through CLI and saves outputs under
``outputs/acm_paper/rq1/figures/``.  Never commit source participant images
to git.

Generated figures per image:
  1. Original image
  2. Ground-truth mask
  3. Predicted mask
  4. Overlay (prediction on image)
  5. Error map (false positives and false negatives)
  6. Side-by-side model comparison (all four models)

The module skips gracefully when no input images are provided or when
required checkpoint files are missing.

Usage
-----
::

    # Visualise a single image with one model
    python -m experiments.acm_paper.rq1_model_selection.visualize \\
        --image /path/to/tongue.jpg \\
        --gt-mask /path/to/mask.png \\
        --arch unet_mobilenet \\
        --checkpoint models/acm_paper/rq1/unet_mobilenet/best.pth \\
        --output-dir outputs/acm_paper/rq1/figures \\
        --anonymize-filename

    # Compare all four models on the same image
    python -m experiments.acm_paper.rq1_model_selection.visualize \\
        --image /path/to/tongue.jpg \\
        --gt-mask /path/to/mask.png \\
        --comparison \\
        --unet-mobilenet-ckpt models/acm_paper/rq1/unet_mobilenet/best.pth \\
        --unet-resnet-ckpt    models/acm_paper/rq1/unet_resnet/best.pth \\
        --deeplabv3-ckpt      models/acm_paper/rq1/deeplabv3/best.pth \\
        --yolo-ckpt           models/acm_paper/rq1/yolov8n_seg/best.pt \\
        --output-dir          outputs/acm_paper/rq1/figures
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Allow running as python -m experiments.acm_paper.rq1_model_selection.visualize
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Lazy import helpers (avoid hard crash if optional deps are missing)
# ---------------------------------------------------------------------------

def _require_cv2():
    try:
        import cv2  # noqa: F401
        return cv2
    except ImportError:
        print("[ERROR] opencv-python is required for visualisation.  "
              "Install it with: pip install opencv-python")
        sys.exit(1)


def _require_matplotlib():
    try:
        import matplotlib  # noqa: F401
        import matplotlib.pyplot as plt  # noqa: F401
        return plt
    except ImportError:
        print("[ERROR] matplotlib is required for visualisation.  "
              "Install it with: pip install matplotlib")
        sys.exit(1)


def _require_torch():
    try:
        import torch  # noqa: F401
        return torch
    except ImportError:
        print("[ERROR] torch is required for visualisation.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Image loading
# ---------------------------------------------------------------------------

def load_image(path: Path) -> np.ndarray:
    """Load an image as RGB numpy array (H, W, 3) uint8."""
    cv2 = _require_cv2()
    img = cv2.imread(str(path))
    if img is None:
        raise FileNotFoundError(f"Cannot load image: {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def load_mask(path: Path) -> np.ndarray:
    """Load a binary mask as uint8 (H, W), values 0 or 255."""
    cv2 = _require_cv2()
    mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise FileNotFoundError(f"Cannot load mask: {path}")
    _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    return binary


# ---------------------------------------------------------------------------
# SMP model inference
# ---------------------------------------------------------------------------

def predict_smp(
    image_rgb: np.ndarray,
    arch: str,
    checkpoint_path: Path,
    img_size: int = 256,
    threshold: float = 0.5,
    device_str: Optional[str] = None,
) -> np.ndarray:
    """
    Run SMP model inference on a single image.

    Returns
    -------
    np.ndarray : Binary mask (H, W) uint8 (0 or 255), at original resolution.
    """
    torch = _require_torch()
    import albumentations as A
    from albumentations.pytorch import ToTensorV2
    from src.seg.model import build_model_by_arch

    device = torch.device(device_str or ("cuda" if torch.cuda.is_available() else "cpu"))
    model = build_model_by_arch(arch, encoder_weights=None).to(device)

    raw = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if isinstance(raw, dict) and "model_state_dict" in raw:
        model.load_state_dict(raw["model_state_dict"])
    else:
        model.load_state_dict(raw)
    model.eval()

    original_h, original_w = image_rgb.shape[:2]
    transform = A.Compose([
        A.Resize(img_size, img_size),
        A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ToTensorV2(),
    ])
    tensor = transform(image=image_rgb)["image"].unsqueeze(0).to(device)

    with torch.no_grad():
        logits = model(tensor)
        prob = torch.sigmoid(logits).squeeze().cpu().numpy()

    pred = (prob >= threshold).astype(np.uint8) * 255

    cv2 = _require_cv2()
    pred_resized = cv2.resize(pred, (original_w, original_h), interpolation=cv2.INTER_NEAREST)
    return pred_resized


# ---------------------------------------------------------------------------
# YOLO model inference
# ---------------------------------------------------------------------------

def predict_yolo(
    image_path: Path,
    checkpoint_path: Path,
    img_size: int = 256,
) -> np.ndarray:
    """
    Run YOLO segmentation inference on a single image.

    Returns
    -------
    np.ndarray : Binary mask (H, W) uint8 (0 or 255), at original resolution.
    """
    try:
        from ultralytics import YOLO
        import cv2 as cv2_
    except ImportError:
        print("[ERROR] ultralytics is required for YOLO visualisation.")
        sys.exit(1)

    original_img = cv2_.imread(str(image_path))
    if original_img is None:
        raise FileNotFoundError(f"Cannot load image: {image_path}")
    h, w = original_img.shape[:2]

    model = YOLO(str(checkpoint_path))
    results = model.predict(
        source=str(image_path),
        imgsz=img_size,
        verbose=False,
    )

    combined_mask = np.zeros((h, w), dtype=np.uint8)
    for result in results:
        if result.masks is not None:
            for m in result.masks.data:
                m_np = m.cpu().numpy().astype(np.float32)
                m_resized = cv2_.resize(m_np, (w, h), interpolation=cv2_.INTER_NEAREST)
                combined_mask = np.logical_or(combined_mask, m_resized > 0.5).astype(np.uint8)
    return (combined_mask * 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Visualisation utilities
# ---------------------------------------------------------------------------

def make_overlay(
    image_rgb: np.ndarray,
    mask: np.ndarray,
    alpha: float = 0.4,
    color: Tuple[int, int, int] = (255, 50, 50),
) -> np.ndarray:
    """Return image with coloured mask overlay."""
    overlay = image_rgb.copy()
    binary = mask > 127
    overlay[binary] = (
        (1 - alpha) * overlay[binary]
        + alpha * np.array(color, dtype=np.float32)
    ).astype(np.uint8)
    return overlay


def make_error_map(
    gt_mask: np.ndarray,
    pred_mask: np.ndarray,
) -> np.ndarray:
    """
    Return an RGB error map.
    - Green  (TP): correct positive
    - Red    (FP): predicted positive, actually negative
    - Blue   (FN): predicted negative, actually positive
    - Black  (TN): correct negative
    """
    gt_b = gt_mask > 127
    pr_b = pred_mask > 127
    h, w = gt_b.shape
    error = np.zeros((h, w, 3), dtype=np.uint8)
    error[gt_b & pr_b]   = (50, 200, 50)   # TP green
    error[~gt_b & pr_b]  = (200, 50, 50)   # FP red
    error[gt_b & ~pr_b]  = (50, 50, 200)   # FN blue
    return error


# ---------------------------------------------------------------------------
# Figure savers
# ---------------------------------------------------------------------------

def save_single_model_figure(
    image_rgb: np.ndarray,
    gt_mask: np.ndarray,
    pred_mask: np.ndarray,
    model_name: str,
    output_dir: Path,
    base_filename: str,
) -> Path:
    """
    Save a 5-panel figure: original | GT | pred | overlay | error map.
    """
    plt = _require_matplotlib()
    import matplotlib.gridspec as gridspec

    fig = plt.figure(figsize=(18, 4))
    gs = gridspec.GridSpec(1, 5, figure=fig)

    panels = [
        (image_rgb,                         "Original"),
        (gt_mask,                           "Ground Truth"),
        (pred_mask,                         "Prediction"),
        (make_overlay(image_rgb, pred_mask), "Overlay"),
        (make_error_map(gt_mask, pred_mask),"Error Map"),
    ]

    for idx, (panel, title) in enumerate(panels):
        ax = fig.add_subplot(gs[0, idx])
        if panel.ndim == 2:
            ax.imshow(panel, cmap="gray", vmin=0, vmax=255)
        else:
            ax.imshow(panel)
        ax.set_title(title, fontsize=9)
        ax.axis("off")

    fig.suptitle(model_name, fontsize=11, fontweight="bold")
    plt.tight_layout()

    out_path = output_dir / f"{base_filename}_{model_name.replace(' + ', '_').replace(' ', '_')}.png"
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[visualize] Saved → {out_path}")
    return out_path


def save_model_comparison_figure(
    image_rgb: np.ndarray,
    gt_mask: np.ndarray,
    predictions: Dict[str, np.ndarray],
    output_dir: Path,
    base_filename: str,
) -> Path:
    """
    Save a side-by-side comparison figure across all models.

    Rows: original / GT | one row per model (pred + overlay + error map)
    """
    plt = _require_matplotlib()

    model_names = list(predictions.keys())
    n_models = len(model_names)

    fig, axes = plt.subplots(
        n_models + 1, 4,
        figsize=(16, 4 * (n_models + 1)),
    )
    if n_models + 1 == 1:
        axes = axes[np.newaxis, :]

    # Row 0: original + GT
    axes[0, 0].imshow(image_rgb)
    axes[0, 0].set_title("Original", fontsize=9)
    axes[0, 0].axis("off")

    axes[0, 1].imshow(gt_mask, cmap="gray", vmin=0, vmax=255)
    axes[0, 1].set_title("Ground Truth", fontsize=9)
    axes[0, 1].axis("off")
    for j in (2, 3):
        axes[0, j].axis("off")

    # Rows 1+: each model
    for row, name in enumerate(model_names, start=1):
        pred = predictions[name]
        axes[row, 0].imshow(pred, cmap="gray", vmin=0, vmax=255)
        axes[row, 0].set_title(f"{name} — Pred", fontsize=9)
        axes[row, 0].axis("off")

        axes[row, 1].imshow(make_overlay(image_rgb, pred))
        axes[row, 1].set_title("Overlay", fontsize=9)
        axes[row, 1].axis("off")

        axes[row, 2].imshow(make_error_map(gt_mask, pred))
        axes[row, 2].set_title("Error Map", fontsize=9)
        axes[row, 2].axis("off")

        axes[row, 3].axis("off")

    plt.tight_layout()
    out_path = output_dir / f"{base_filename}_comparison.png"
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[visualize] Comparison figure saved → {out_path}")
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate qualitative segmentation visualisations for ACM paper RQ1.\n"
            "Skips gracefully if input images or checkpoints are missing."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Input
    parser.add_argument("--image",   default=None, help="Path to input tongue image.")
    parser.add_argument("--gt-mask", default=None, help="Path to ground-truth mask PNG.")
    parser.add_argument("--img-size", type=int, default=256)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--device",   default=None)

    # Single model
    parser.add_argument("--arch",       default=None,
                        choices=["unet_mobilenet", "unet_resnet", "deeplabv3"],
                        help="Architecture for single-model visualisation.")
    parser.add_argument("--checkpoint", default=None,
                        help="Checkpoint for single-model visualisation.")

    # Comparison mode
    parser.add_argument("--comparison", action="store_true",
                        help="Generate side-by-side comparison of all four models.")
    parser.add_argument("--unet-mobilenet-ckpt", default=None)
    parser.add_argument("--unet-resnet-ckpt",    default=None)
    parser.add_argument("--deeplabv3-ckpt",      default=None)
    parser.add_argument("--yolo-ckpt",           default=None)

    # Output
    parser.add_argument("--output-dir", default="outputs/acm_paper/rq1/figures")
    parser.add_argument("--anonymize-filename", action="store_true",
                        help="Replace the source filename with an anonymous ID.")

    args = parser.parse_args()

    # ── Validate inputs ───────────────────────────────────────────────
    if args.image is None:
        print(
            "[visualize] No --image provided.  Nothing to do.\n"
            "            Provide real image paths when the dataset is available."
        )
        return

    image_path = Path(args.image)
    if not image_path.exists():
        print(
            f"[visualize] Image not found: {image_path}\n"
            "            Skipping (no real data available)."
        )
        return

    gt_path = Path(args.gt_mask) if args.gt_mask else None
    if gt_path and not gt_path.exists():
        print(f"[visualize] Ground-truth mask not found: {gt_path}  (overlay only).")
        gt_path = None

    # ── Load inputs ────────────────────────────────────────────────────
    image_rgb = load_image(image_path)
    gt_mask = load_mask(gt_path) if gt_path else np.zeros(image_rgb.shape[:2], dtype=np.uint8)

    out_dir = Path(args.output_dir)
    base_name = "anonymous" if args.anonymize_filename else image_path.stem

    # ── Single-model mode ─────────────────────────────────────────────
    if args.arch and args.checkpoint:
        ckpt = Path(args.checkpoint)
        if not ckpt.exists():
            print(f"[visualize] Checkpoint not found: {ckpt}  Skipping.")
        else:
            from experiments.acm_paper.rq1_model_selection.evaluate_smp import ARCH_DISPLAY_NAMES
            pred = predict_smp(image_rgb, args.arch, ckpt, args.img_size, args.threshold, args.device)
            save_single_model_figure(
                image_rgb, gt_mask, pred,
                ARCH_DISPLAY_NAMES.get(args.arch, args.arch),
                out_dir, base_name,
            )

    # ── Comparison mode ───────────────────────────────────────────────
    if args.comparison:
        from experiments.acm_paper.rq1_model_selection.evaluate_smp import ARCH_DISPLAY_NAMES

        checkpoints = {
            "unet_mobilenet": args.unet_mobilenet_ckpt,
            "unet_resnet":    args.unet_resnet_ckpt,
            "deeplabv3":      args.deeplabv3_ckpt,
        }
        predictions: Dict[str, np.ndarray] = {}

        for arch, ckpt_str in checkpoints.items():
            if ckpt_str is None:
                print(f"[visualize] No checkpoint for {arch}, skipping.")
                continue
            ckpt = Path(ckpt_str)
            if not ckpt.exists():
                print(f"[visualize] Checkpoint not found: {ckpt}, skipping.")
                continue
            pred = predict_smp(image_rgb, arch, ckpt, args.img_size, args.threshold, args.device)
            predictions[ARCH_DISPLAY_NAMES[arch]] = pred

        if args.yolo_ckpt:
            yolo_ckpt = Path(args.yolo_ckpt)
            if yolo_ckpt.exists():
                pred_yolo = predict_yolo(image_path, yolo_ckpt, args.img_size)
                predictions["YOLOv8n-seg"] = pred_yolo
            else:
                print(f"[visualize] YOLO checkpoint not found: {yolo_ckpt}, skipping.")

        if predictions:
            save_model_comparison_figure(image_rgb, gt_mask, predictions, out_dir, base_name)
        else:
            print("[visualize] No predictions could be generated.  "
                  "Are all checkpoints available?")


if __name__ == "__main__":
    main()
