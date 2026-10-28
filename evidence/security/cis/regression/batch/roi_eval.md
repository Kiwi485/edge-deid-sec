# ROI 評估報告

## 範圍
- 資料集：`data/raw`
- 影像數量：5
- 已匹配 meta 數量：5
- 流程：quality gate -> MediaPipe ROI -> YOLO fallback -> fixed-crop fallback
- 批次執行指令：`python src/pipeline_local.py`
- 報告更新指令：`python src/update_roi_eval.py`
- 產生時間：2026-10-27 17:35:28

## 驗收檢查
- 批次穩定性（目標 100 張）：目前 5 張統計中無 pipeline hard error。
- quality_fail 行為：失敗樣本會標記 status=quality_fail，並在 meta.json 留下 reason。
- fallback 行為：MediaPipe ROI 失敗時依序嘗試 YOLO fallback，最後才用 fixed crop。

## 核心指標（5 張）
- ROI 成功（mediapipe）：5/5 = 100.0%
- ROI 使用 YOLO fallback：0/5 = 0.0%
- ROI 使用 fixed fallback：0/5 = 0.0%
- ROI fallback 總計：0/5 = 0.0%
- 品質通過（quality_gate.reason=ok）：5/5 = 100.0%
- 品質失敗（status=quality_fail）：0/5 = 0.0%
- Pipeline hard error（status=error）：0/5 = 0.0%

## 失敗原因分類
- Quality gate reasons（英文鍵值）：
- `ok`（通過）: 5
- Fallback trigger reasons（英文鍵值）：
- 無

## 備註
- 統計方式：以 `data/raw` 檔名對應 `data/out/<image_id>/meta.json`。
- 缺少 meta 數量：0
