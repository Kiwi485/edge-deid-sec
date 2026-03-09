# I/O 規格（B 版本，固定不可亂改）
> 本規格是所有模組並行開發的共同契約。任何變更需 PM 宣告版本升級。

## Input
- 影像來源：`data/raw/`
- 支援格式：.jpg / .png
- 建議：先固定原圖輸入為 640×480（或 pipeline 中 resize），再取 ROI。

## Per-image Output（每張一包）
輸出路徑：`data/out/<image_id>/`
- `roi.png`：ROI 影像（可為裁切後 ROI）
- `mask.png`：舌體分割遮罩（0/255 或 0/1）
- `deid.png`：去識別化影像（roi-only 或 mask-only）
- `feature_256.npy`：float32 shape=(256,)
- `meta.json`：該張處理紀錄（固定欄位如下）

## meta.json（最小固定欄位）
```json
{
  "image_id": "xxx",
  "input_file": "xxx.jpg",
  "roi_method_used": "mediapipe|fallback",
  "roi_bbox": [x1, y1, x2, y2],
  "deid_method": "roi_only|mask_only",
  "timing_ms": {
    "roi_ms": 0.0,
    "seg_ms": 0.0,
    "feat_ms": 0.0,
    "deid_ms": 0.0,
    "total_ms": 0.0
  },
  "status": "ok|quality_fail|error",
  "error": ""
}