# ROI 評估報告

## 範圍
- 資料集：`data/raw`
- 影像數量：120
- 已匹配 meta 數量：120
- 流程：quality gate -> MediaPipe ROI -> fixed-crop fallback
- 批次執行指令：`d:/edge-deid-sec/.venv311/Scripts/python.exe src/pipeline_local.py`
- 報告更新指令：`d:/edge-deid-sec/.venv311/Scripts/python.exe src/update_roi_eval.py`
- 產生時間：2026-03-23 15:59:58

## 驗收檢查
- 批次穩定性（目標 100 張）：目前 120 張統計中無 pipeline hard error。
- quality_fail 行為：失敗樣本會標記 status=quality_fail，並在 meta.json 留下 reason。
- fallback 行為：MediaPipe ROI 失敗時改用 fixed crop，並記錄 roi_method_used=fallback。

## 核心指標（120 張）
- ROI 成功（mediapipe）：8/120 = 6.7%
- ROI 使用 fallback：112/120 = 93.3%
- 品質通過（quality_gate.reason=ok）：8/120 = 6.7%
- 品質失敗（status=quality_fail）：112/120 = 93.3%
- Pipeline hard error（status=error）：0/120 = 0.0%

## 失敗原因分類
- Quality gate reasons（英文鍵值）：
- `blur`（模糊）: 112
- `ok`（通過）: 8
- Fallback trigger reasons（英文鍵值）：
- `no_face_landmarks`（未檢出人臉關鍵點）: 112

## 備註
- 統計方式：以 `data/raw` 檔名對應 `data/out/<image_id>/meta.json`。
- 缺少 meta 數量：0
