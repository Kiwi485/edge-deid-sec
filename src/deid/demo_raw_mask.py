import cv2
import numpy as np
import os
import glob
import time
import json
import shutil
from build_tongue_mask import build_mask

def run_deid_mask_only(img: np.ndarray, mask: np.ndarray, output_dir: str) -> dict:
    meta = {
        "deid_method": "mask_only",
        "deid_ms": 0,
        "status": "success",
        "error": None
    }
    try:
        # 收緊 Mask (Erosion) - 降低 iterations 以保留更完整的舌頭邊緣
        kernel = np.ones((5, 5), np.uint8)
        shrunk_mask = cv2.erode(mask, kernel, iterations=0) # 設為 0 代表不向內壓縮，或可改為 1 微調
        _, binary_mask = cv2.threshold(shrunk_mask, 127, 255, cv2.THRESH_BINARY)

        # 去識別化處理
        deid_img = np.zeros_like(img)
        np.copyto(deid_img, img, where=(binary_mask[:, :, None] == 255))

        # 輸出
        os.makedirs(output_dir, exist_ok=True)
        cv2.imwrite(os.path.join(output_dir, "deid.png"), deid_img)
        
        # 也可以輸出對應的 tight_mask 以供檢查
        cv2.imwrite(os.path.join(output_dir, "tight_mask.png"), binary_mask)

    except Exception as e:
        meta["status"] = "error"
        meta["error"] = str(e)
    return meta

if __name__ == "__main__":
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    raw_images = sorted(glob.glob("data/raw/*.jpg"))[:10]
    out_base = "PHOTO3"
    os.makedirs(out_base, exist_ok=True)
    
    print("Running Native Resolution Mask-Only Deid into PHOTO3/ ...")
    
    for i, img_path in enumerate(raw_images):
        img = cv2.imread(img_path)
        if img is None: continue
        
        h, w = img.shape[:2]
        # Since we don't have MediaPipe ROI here easily without running the whole pipeline,
        # We can approximate ROI using the bottom half center, or just pass full image.
        # However, build_mask assumes the ROI bounds exactly. Let's pass the whole image as ROI:
        roi_bbox = [0, 0, w, h] 
        
        # Build mask AT NATIVE RESOLUTION
        m = build_mask(img, roi_bbox)
        
        if m is not None:
            if m.dtype == np.bool_:
                m = (m * 255).astype(np.uint8)
            else:
                m = np.where(m > 0, 255, 0).astype(np.uint8)
        else:
            m = np.zeros((h, w), dtype=np.uint8)
            
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        out_dir = os.path.join(out_base, f"{base_name}_mask_only")
        os.makedirs(out_dir, exist_ok=True)
        
        shutil.copy(img_path, os.path.join(out_dir, "raw.jpg"))
        res = run_deid_mask_only(img, m, out_dir)
        print(f"[{i+1}/10] {img_path} -> status: {res.get('status')}")

