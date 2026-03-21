import os
import glob
from pathlib import Path

try:
    from src.deid.deid_mask_only import run_deid_mask_only
except ImportError:
    from deid_mask_only import run_deid_mask_only


def _find_mask(mask_dir: str, img_name: str) -> str:
    # Support both flat and bundle-style mask layouts.
    cands = [
        os.path.join(mask_dir, f"{img_name}_mask.png"),
        os.path.join(mask_dir, f"{img_name}.png"),
        os.path.join(mask_dir, img_name, "mask.png"),
    ]
    for p in cands:
        if os.path.exists(p):
            return p
    return cands[0]


def run_batch_deid(raw_dir: str, mask_dir: str, out_base_dir: str, limit: int = 10) -> None:
    """
    Batch run mask-only de-identification.

    Acceptance goals:
    1) Process all selected images
    2) Missing masks do not crash the batch
    3) Write deid.png and meta.json to output folders
    """
    supported_exts = ("*.jpg", "*.jpeg", "*.png")
    img_paths = []
    for ext in supported_exts:
        img_paths.extend(glob.glob(os.path.join(raw_dir, ext)))

    img_paths = sorted(img_paths)
    if limit > 0:
        img_paths = img_paths[:limit]

    if not img_paths:
        print(f"在 {raw_dir} 中沒有找到任何圖片。")
        return

    os.makedirs(out_base_dir, exist_ok=True)

    print(f"開始批次處理，共找到 {len(img_paths)} 張圖片...")
    success_count = 0
    error_count = 0

    for img_path in img_paths:
        img_filename = os.path.basename(img_path)
        img_name, _ = os.path.splitext(img_filename)

        mask_path = _find_mask(mask_dir, img_name)
        output_dir = os.path.join(out_base_dir, img_name)

        meta = run_deid_mask_only(img_path, mask_path, output_dir)
        status = str(meta.get("status", "")).lower()

        if status in {"ok", "success"}:
            success_count += 1
            print(f"[SUCCESS] {img_filename} -> 耗時: {meta.get('deid_ms', 0)}ms")
        else:
            error_count += 1
            print(f"[ERROR]   {img_filename} -> 原因: {meta.get('error', '')}")

    print("-" * 40)
    print("批次處理完成！")
    print(f"成功: {success_count} 張")
    print(f"失敗: {error_count} 張 (例如 Mask 缺失等優雅處理)")
    print(f"所有結果已輸出至: {out_base_dir}")


if __name__ == "__main__":
    RAW_IMAGE_DIR = "data/raw"
    MASK_DIR = "data/out"
    OUTPUT_DIR = "PHOTO"

    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    run_batch_deid(RAW_IMAGE_DIR, MASK_DIR, OUTPUT_DIR, limit=10)
