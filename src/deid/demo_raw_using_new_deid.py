import cv2
import numpy as np
import os
import glob
import json
import shutil
import sys

# Ensure imports work regardless of execution context
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from build_tongue_mask import build_mask
from deid_mask_only import deid_mask_only, save_deid_result

if __name__ == '__main__':
    raw_images = sorted(glob.glob('data/raw/*.jpg'))[:10]
    out_base = 'PHOTO_NEW'
    os.makedirs(out_base, exist_ok=True)
    
    print('Running Native Resolution with New Deid Script into PHOTO_NEW/ ...')
    
    for i, img_path in enumerate(raw_images):
        img = cv2.imread(img_path)
        if img is None: continue
        
        h, w = img.shape[:2]
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
        out_dir = os.path.join(out_base, f'{base_name}_mask_only')
        os.makedirs(out_dir, exist_ok=True)
        
        shutil.copy(img_path, os.path.join(out_dir, 'raw.jpg'))
        
        # we can provide the raw mask to deid_mask_only
        deid_img, meta = deid_mask_only(img, m)
        save_deid_result(out_dir, deid_img, meta)
        
        print(f'[{i+1}/10] {img_path} -> status: {meta.get("status")}')