import cv2
import numpy as np
import time
import json
import os
import glob
from pathlib import Path
import shutil

def run_deid_mask_only(image_path: str, mask_path: str, output_dir: str) -> dict:
    """
    執行 mask-only 去識別化。
    最終目標：
    1. 只保留舌頭本身的原始彩色像素。
    2. 嘴唇、下巴、皮膚、背景全部黑掉 (0,0,0)。
    3. 不灰階化、不二值化、不畫框線。
    4. 收緊 Mask 以排除沾黏。
    5. 優雅處理異常，不 crash，並紀錄 meta.json。
    """
    start_time = time.time()
    # 依照 IO_SPEC.md 規格建立 meta 欄位
    meta = {
        "deid_method": "mask_only",
        "deid_ms": 0,
        "status": "success",
        "error": None
    }

    try:
        # 1. 檢查檔案是否存在
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")
        if not os.path.exists(mask_path):
            raise FileNotFoundError(f"Mask not found: {mask_path}")

        # 2. 讀取影像與 Mask
        img = cv2.imread(image_path)  # 讀取為彩色 (BGR)
        mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)  # 讀取為灰階

        if img is None:
            raise ValueError(f"Failed to decode image from {image_path}")
        if mask is None:
            raise ValueError(f"Failed to decode mask from {mask_path}")

        # 3. 尺寸一致性檢查 (重要：如果 Mask 與圖片尺寸不同，幫忙縮放對齊以避免報錯)
        if img.shape[:2] != mask.shape[:2]:
            print(f"[Info] Resizing mask for {os.path.basename(image_path)} from {mask.shape[:2]} to {img.shape[:2]}")
            mask = cv2.resize(mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)

        # 4. 收緊 Mask (Erosion)：排除可能沾黏的嘴唇或皮膚
        # 建立 5x5 的 kernel
        kernel = np.ones((5, 5), np.uint8)
        # 執行形態學侵蝕，iterations 次數依實際需求調整，3次通常能有效排除邊緣
        shrunk_mask = cv2.erode(mask, kernel, iterations=3)

        # 確保 Mask 為嚴格的二值化 (0 與 255)
        _, binary_mask = cv2.threshold(shrunk_mask, 127, 255, cv2.THRESH_BINARY)

        # 5. 去識別化核心：建立全黑背景，僅複製 Mask 範圍內的原始彩色像素
        deid_img = np.zeros_like(img)  # 生成一個全黑的畫布，尺寸與原圖一致
        
        # 透過 np.copyto 進行像素複製：
        # 將 img 的像素複製到 deid_img，但只在 binary_mask 的特定維度 (H, W, 1) 為 255 的位置進行
        # 這一步嚴格保留了原始彩色像素，其餘皆為預設的純黑。
        np.copyto(deid_img, img, where=(binary_mask[:, :, None] == 255))

        # 6. 輸出影像 deid.png
        os.makedirs(output_dir, exist_ok=True)
        out_img_path = os.path.join(output_dir, "deid.png")
        cv2.imwrite(out_img_path, deid_img)
        
        # 複製原圖供對照
        shutil.copy(image_path, os.path.join(output_dir, "raw.jpg"))

    except Exception as e:
        # 優雅處理異常，不 crash
        meta["status"] = "error"
        meta["error"] = str(e)
        print(f"[ERROR]   Process failed for {os.path.basename(image_path)}: {str(e)}")

    finally:
        # 7. 計算執行時間並輸出 meta.json
        meta["deid_ms"] = int((time.time() - start_time) * 1000)
        
        try:
            os.makedirs(output_dir, exist_ok=True)
            meta_path = os.path.join(output_dir, "meta.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=4)
        except Exception as e:
            # 確保寫入 JSON 失敗也不會導致主流程中斷
            print(f"[Warning] Failed to write meta.json: {str(e)}")

    return meta

if __name__ == "__main__":
    out_base = "PHOTO2"
    os.makedirs(out_base, exist_ok=True)
    
    # 抓取前10張原圖來進行測試
    raw_images = sorted(glob.glob("data/raw/*.jpg"))[:10]
    out_masks_base = "data/out"
    
    print("Running deid_mask_only on 10 examples (into PHOTO2/)...")
    for i, img_path in enumerate(raw_images):
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        out_dir = os.path.join(out_base, f"{base_name}_mask_only")
        os.makedirs(out_dir, exist_ok=True)
        
        # 從舊有的產出資料夾抓取 mask
        mask_path = os.path.join(out_masks_base, base_name, "mask.png")
        
        # 萬一沒有 mask，就在本地建一個替代的用來完成測試
        if not os.path.exists(mask_path):
            img_temp = cv2.imread(img_path)
            if img_temp is not None:
                mask_path = os.path.join(out_dir, "dummy_mask.png")
                mock_m = np.zeros(img_temp.shape[:2], dtype=np.uint8)
                h, w = img_temp.shape[:2]
                cv2.rectangle(mock_m, (int(w*0.3), int(h*0.3)), (int(w*0.7), int(h*0.7)), 255, -1)
                cv2.imwrite(mask_path, mock_m)
        
        res = run_deid_mask_only(img_path, mask_path, out_dir)
        print(f"[{i+1}/10] {img_path} -> status: {res.get('status')} time={res.get('deid_ms')}ms")
