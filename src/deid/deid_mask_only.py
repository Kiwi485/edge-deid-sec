from __future__ import annotations
import cv2
import numpy as np
import time
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

Meta = Dict[str, Any]

def deid_mask_only(image: np.ndarray, mask: np.ndarray) -> Tuple[Optional[np.ndarray], dict]:
    start_time = time.time()
    meta = {'deid_method': 'mask_only', 'deid_ms': 0, 'status': 'success', 'error': None}
    try:
        if image is None or mask is None: raise ValueError('Image or mask is None')
        if image.shape[:2] != mask.shape[:2]: raise ValueError('Shape mismatch')
        if mask.ndim == 3:
            if mask.shape[2] in (3, 4): mask_gray = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY if mask.shape[2]==3 else cv2.COLOR_BGRA2GRAY)
            else: mask_gray = mask[:, :, 0]
        else: mask_gray = mask
        if mask_gray.dtype == np.bool_: mask_gray = (mask_gray.astype(np.uint8) * 255)
        elif np.issubdtype(mask_gray.dtype, np.floating) and mask_gray.max() <= 1.0: mask_gray = (mask_gray * 255).astype(np.uint8)
        _, binary_mask = cv2.threshold(mask_gray.astype(np.uint8), 127, 255, cv2.THRESH_BINARY)
        deid_img = np.zeros_like(image)
        np.copyto(deid_img, image, where=(binary_mask[:, :, None] == 255))
        meta['status'] = 'ok'
        return deid_img, meta
    except Exception as e:
        meta['status'] = 'error'
        meta['error'] = str(e)
        return np.zeros_like(image) if image is not None else None, meta
    finally:
        meta['deid_ms'] = int((time.time() - start_time) * 1000)

def save_deid_result(output_dir: str | Path, deid_img: Optional[np.ndarray], meta: Meta, *, merge_existing_meta: bool = True) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if deid_img is not None: cv2.imwrite(str(output_dir / 'deid.png'), deid_img)
    meta_path = output_dir / 'meta.json'
    payload = {}
    if merge_existing_meta and meta_path.exists():
        try: payload = json.loads(meta_path.read_text(encoding='utf-8'))
        except: pass
    payload.update(meta)
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
