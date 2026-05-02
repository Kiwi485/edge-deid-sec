import argparse
from pathlib import Path
import cv2
import numpy as np

try:
    from src.seg.inference import run_inference
except Exception:
    from src.seg.inference import run_inference


def compute_metrics(pred_mask, gt_mask):
    p = (pred_mask > 0).astype(np.uint8)
    g = (gt_mask > 0).astype(np.uint8)
    inter = (p & g).sum()
    union = (p | g).sum()
    dice = (2 * inter) / (p.sum() + g.sum() + 1e-6)
    iou = inter / (union + 1e-6)
    return dice, iou


def overlay_mask_on_image(img_rgb, mask, color=(255, 0, 0), alpha=0.45):
    colored = np.zeros_like(img_rgb, dtype=np.uint8)
    colored[mask > 0] = color
    overlay = cv2.addWeighted(img_rgb, 1 - alpha, colored, alpha, 0)
    return overlay


def draw_contours(img_rgb, mask, color=(0, 255, 0), thickness=2):
    cnt_img = img_rgb.copy()
    mask_bin = (mask > 0).astype(np.uint8)
    contours, _ = cv2.findContours(mask_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(cnt_img, contours, -1, color, thickness)
    return cnt_img


def main():
    parser = argparse.ArgumentParser(description="Visualize segmentation prediction")
    parser.add_argument("--image", type=str, required=True, help="Input image path")
    parser.add_argument("--model", type=str, required=True, help="Checkpoint path (best.pth)")
    parser.add_argument("--gt", type=str, default=None, help="Ground-truth mask path (optional)")
    parser.add_argument("--out-dir", type=str, default="viz_out", help="Output directory")
    parser.add_argument("--img-size", type=int, default=256, help="Model input size")
    parser.add_argument("--threshold", type=float, default=0.5, help="Binarization threshold")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Run inference (returns mask in original image size and tongue-only RGB)
    mask_np, tongue_only = run_inference(args.image, args.model, args.img_size, args.threshold)

    # Read original image
    img_bgr = cv2.imread(args.image)
    if img_bgr is None:
        raise FileNotFoundError(f"Cannot load image: {args.image}")
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    # Visualizations
    overlay = overlay_mask_on_image(img_rgb, mask_np, color=(255, 0, 0), alpha=0.4)
    contours_img = draw_contours(img_rgb, mask_np, color=(0, 255, 0), thickness=2)

    stem = Path(args.image).stem
    cv2.imwrite(str(out_dir / f"{stem}_overlay.png"), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
    cv2.imwrite(str(out_dir / f"{stem}_contours.png"), cv2.cvtColor(contours_img, cv2.COLOR_RGB2BGR))
    cv2.imwrite(str(out_dir / f"{stem}_tongue.png"), cv2.cvtColor(tongue_only, cv2.COLOR_RGB2BGR))

    print(f"Saved overlay: {out_dir / (stem + '_overlay.png')}")
    print(f"Saved contours: {out_dir / (stem + '_contours.png')}")
    print(f"Saved tongue-only: {out_dir / (stem + '_tongue.png')}")

    # If GT provided, compute metrics and diff heatmap
    if args.gt:
        gt = cv2.imread(args.gt, 0)
        if gt is None:
            raise FileNotFoundError(f"Cannot load GT mask: {args.gt}")
        # Ensure same size as mask_np
        if gt.shape != mask_np.shape:
            gt = cv2.resize(gt, (mask_np.shape[1], mask_np.shape[0]), interpolation=cv2.INTER_NEAREST)

        dice, iou = compute_metrics(mask_np, gt)
        print(f"Dice: {dice:.4f}, IoU: {iou:.4f}")

        fp = np.logical_and(mask_np > 0, gt == 0).astype(np.uint8) * 255
        fn = np.logical_and(mask_np == 0, gt > 0).astype(np.uint8) * 255
        diff = np.zeros_like(img_rgb)
        diff[fp > 0] = (255, 0, 0)
        diff[fn > 0] = (0, 0, 255)
        blend = cv2.addWeighted(img_rgb, 0.6, diff, 0.4, 0)
        cv2.imwrite(str(out_dir / f"{stem}_diff.png"), cv2.cvtColor(blend, cv2.COLOR_RGB2BGR))
        print(f"Saved diff: {out_dir / (stem + '_diff.png')}")


if __name__ == "__main__":
    main()
