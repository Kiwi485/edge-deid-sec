import cv2
import numpy as np
import time
import json
import os
import glob

def run_deid_roi_only(image_path: str, roi: list, output_dir: str) -> dict:
    """
    執行 roi-only 去識別化。
    傳入 roi = [x, y, w, h]，將該矩形以外的區域全部填黑 (0,0,0)。
    """
    start_time = time.time()
    meta = {
        "deid_method": "roi_only",
        "deid_ms": 0,
        "status": "success",
        "error": None
    }

    try:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")
            
        if not roi or len(roi) != 4:
            raise ValueError(f"Invalid ROI format. Expected [x, y, w, h], got: {roi}")

        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Failed to decode image from {image_path}")

        x, y, w, h = [int(v) for v in roi]
        img_h, img_w = img.shape[:2]

        # 邊界保護 (避免 ROI 溢出影像範圍)
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(img_w, x + w)
        y2 = min(img_h, y + h)

        if x1 >= x2 or y1 >= y2:
            raise ValueError("ROI coordinates are entirely out of image bounds.")

        # 去識別化處理：建立全黑背景，貼上 ROI 內的原始影像
        deid_img = np.zeros_like(img)
        deid_img[y1:y2, x1:x2] = img[y1:y2, x1:x2]

        # 輸出影像 deid.png
        os.makedirs(output_dir, exist_ok=True)
        out_img_path = os.path.join(output_dir, "deid.png")
        cv2.imwrite(out_img_path, deid_img)

    except Exception as e:
        meta["status"] = "error"
        meta["error"] = str(e)

    finally:
        meta["deid_ms"] = int((time.time() - start_time) * 1000)
        try:
            os.makedirs(output_dir, exist_ok=True)
            meta_path = os.path.join(output_dir, "meta.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[Warning] Failed to write meta.json: {str(e)}")

    return meta

if __name__ == "__main__":
    raw_images = sorted(glob.glob("data/raw/*.jpg"))[:10]
    out_base = "PHOTO"
    
    print("Running deid_roi_only on 10 examples...")
    import shutil
    for i, img_path in enumerate(raw_images):
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        out_dir = os.path.join(out_base, f"{base_name}_roi_only")
        os.makedirs(out_dir, exist_ok=True)
        
        # 複製原圖供對比
        shutil.copy(img_path, os.path.join(out_dir, "raw.jpg"))
        
        # 示範填入一個預設 roi: [x, y, w, h] (在實務上將從前處理階段接收)
        roi_mock = [100, 100, 300, 300]
        
        res = run_deid_roi_only(img_path, roi_mock, out_dir)
        print(f"[{i+1}/10] {img_path} -> status: {res.get('status')} time={res.get('deid_ms')}ms")
