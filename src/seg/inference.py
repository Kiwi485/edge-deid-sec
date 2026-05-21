"""
inference.py — 舌頭 segmentation 推論腳本

用法（命令列）：
    python src/seg/inference.py --image path/to/photo.jpg --model models/seg/best.pth

程式匯入用法：
    from src.seg.inference import run_inference
    mask, tongue_only = run_inference("photo.jpg", "models/seg/best.pth")
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

try:
    from seg.model import build_model_by_arch, get_device
except ImportError:
    from src.seg.model import build_model_by_arch, get_device

import albumentations as A
from albumentations.pytorch import ToTensorV2

# Normalisation constants (ImageNet)
_NORMALIZE = A.Compose(
    [
        A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ToTensorV2(),
    ]
)

# Model singleton cache so we don't reload weights for every image.
_CACHED_MODEL = None
_CACHED_MODEL_PATH = None
_CACHED_DEVICE = None


def _get_model(model_path: str, device: torch.device, arch: str = "unet_mobilenet"):
    global _CACHED_MODEL, _CACHED_MODEL_PATH, _CACHED_DEVICE
    if _CACHED_MODEL is not None and _CACHED_MODEL_PATH == model_path:
        return _CACHED_MODEL, _CACHED_DEVICE

    ckpt = torch.load(model_path, map_location=device, weights_only=False)
    saved_arch = ckpt.get("args", {}).get("arch", arch)
    model = build_model_by_arch(arch=saved_arch, encoder_weights=None)
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device).eval()

    _CACHED_MODEL = model
    _CACHED_MODEL_PATH = model_path
    _CACHED_DEVICE = device
    return model, device


def _preprocess(img_rgb: np.ndarray, img_size: int) -> torch.Tensor:
    """Resize, normalize, add batch dim → (1, C, H, W) float tensor."""
    resized = cv2.resize(img_rgb, (img_size, img_size), interpolation=cv2.INTER_LINEAR)
    augmented = _NORMALIZE(image=resized)
    tensor = augmented["image"].unsqueeze(0)  # (1, C, H, W)
    return tensor


@torch.no_grad()
def run_inference(
    image_path: str,
    model_path: str,
    img_size: int = 256,
    threshold: float = 0.5,
    device: torch.device = None,
    arch: str = "unet_mobilenet",
    image_array: np.ndarray = None,
):
    """
    對單張影像執行 tongue segmentation 推論。

    Parameters
    ----------
    image_path  : str  — 輸入影像路徑（當 image_array 為 None 時使用）
    model_path  : str  — checkpoint 路徑（models/seg/best.pth）
    img_size    : int  — 模型輸入邊長（需與訓練時一致）
    threshold   : float — sigmoid 閾值（預設 0.5）
    device      : torch.device | None — None 時自動選擇
    arch        : str  — 模型架構（checkpoint 內未記錄時才使用）
    image_array : np.ndarray | None — 如提供，直接使用此 BGR ndarray，跳過磁碟讀取

    Returns
    -------
    mask_np       : np.ndarray  — binary mask，shape (H, W)，值 0 或 255（原始影像尺寸）
    tongue_only   : np.ndarray  — 套用 mask 後的 RGB 影像（背景歸黑），shape (H, W, 3)
    """
    if device is None:
        device = get_device()

    # Load image (prefer in-memory array to avoid disk I/O)
    if image_array is not None:
        img_bgr = image_array
    else:
        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise FileNotFoundError(f"Cannot load image: {image_path}")
    orig_h, orig_w = img_bgr.shape[:2]
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    # Load model (cached singleton)
    model, device = _get_model(model_path, device, arch)

    # Preprocess
    inp = _preprocess(img_rgb, img_size).to(device)

    # Forward
    logits = model(inp)                              # (1, 1, H, W)
    prob = torch.sigmoid(logits).squeeze().cpu().numpy()  # (H, W) float [0,1]

    # Threshold → binary mask at model resolution
    mask_small = (prob > threshold).astype(np.uint8) * 255

    # Resize mask back to original resolution
    mask_np = cv2.resize(
        mask_small, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST
    )

    # Tongue-only image (background = black)
    tongue_only = img_rgb.copy()
    tongue_only[mask_np == 0] = 0

    return mask_np, tongue_only


def main():
    parser = argparse.ArgumentParser(description="Tongue segmentation inference")
    parser.add_argument("--image", type=str, required=True, help="輸入影像路徑")
    parser.add_argument("--model", type=str, default="models/seg/best.pth",
                        help="checkpoint 路徑")
    parser.add_argument("--arch", type=str, default="unet_mobilenet",
                        help="模型架構（checkpoint 內已記錄時自動讀取，一般不需手動指定）")
    parser.add_argument("--img-size", type=int, default=256,
                        help="模型輸入邊長（需與訓練時相同）")
    parser.add_argument("--threshold", type=float, default=0.5, help="mask 閾値")
    parser.add_argument("--out-dir", type=str, default="outputs",
                        help="輸出目錄（mask + tongue-only 圖片）")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(args.image).stem
    mask_path = out_dir / f"{stem}_mask.png"
    tongue_path = out_dir / f"{stem}_tongue.png"

    print(f"Processing: {args.image}")
    mask_np, tongue_only = run_inference(
        args.image, args.model, args.img_size, args.threshold, arch=args.arch
    )

    cv2.imwrite(str(mask_path), mask_np)
    cv2.imwrite(str(tongue_path), cv2.cvtColor(tongue_only, cv2.COLOR_RGB2BGR))

    tongue_pct = (mask_np > 0).mean() * 100
    print(f"Tongue coverage : {tongue_pct:.1f}% of image")
    print(f"Saved mask      : {mask_path}")
    print(f"Saved tongue    : {tongue_path}")


if __name__ == "__main__":
    main()
