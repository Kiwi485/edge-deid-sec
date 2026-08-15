# edge-deid-sec

Edge AI 影像去識別化 pipeline。系統從 `data/raw/` 讀取影像，執行品質檢查、ROI 擷取、舌頭 segmentation、特徵擷取與去識別化，結果寫入 `data/out/`。

## 快速開始（Windows）

在專案根目錄開啟 PowerShell：

```powershell
python -m venv .venv311
.\.venv311\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果 PowerShell 不允許啟用虛擬環境：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

完整 MediaPipe 設定請看 [docs/SETUP_MEDIAPIPE_WINDOWS.md](docs/SETUP_MEDIAPIPE_WINDOWS.md)。

## 執行主 pipeline

先把要處理的 `.jpg`、`.jpeg` 或 `.png` 放到 `data/raw/`，然後執行：

```powershell
.\.venv311\Scripts\python.exe src\pipeline_local.py
.\.venv311\Scripts\python.exe src\update_roi_eval.py
```

只想先用少量影像測試：

```powershell
.\.venv311\Scripts\python.exe src\pipeline_local.py --limit 5
```

## 重新測試前要清理什麼

如果想從乾淨狀態重新執行，請清理舊的輸出和 latency CSV，但不要刪除 `data/raw/` 的原始影像、同名 `.txt` ROI 標註或 `models/` 裡的模型：

```powershell
Remove-Item .\data\out -Recurse -Force -ErrorAction Ignore
Remove-Item .\logs\pipeline_latency_vm.csv -Force -ErrorAction Ignore
Remove-Item .\docs\roi_eval.md -Force -ErrorAction Ignore
```

接著重新執行：

```powershell
.\.venv311\Scripts\python.exe src\pipeline_local.py
.\.venv311\Scripts\python.exe src\update_roi_eval.py
```

也可以讓 pipeline 自動清理舊的 `data/out/`，並用新 CSV 開始：

```powershell
.\.venv311\Scripts\python.exe src\pipeline_local.py --clear-out --reset-csv
```

不要使用 `--append-csv`，除非你確實要把新批次接到舊的 latency CSV 後面。通常不需要刪除 `data/raw/*.txt`，因為這些檔案是 YOLO ROI fallback 使用的標註。

Linux/macOS：

```bash
./.venv311/bin/python src/pipeline_local.py
./.venv311/bin/python src/update_roi_eval.py
```

## 執行後查看什麼

每張影像會產生 `data/out/<image_id>/`：

| 檔案 | 用途 |
|---|---|
| `roi.png` | ROI 裁切結果 |
| `mask.png` | 舌頭 segmentation mask |
| `deid.png` | 只保留舌頭區域的去識別化影像 |
| `feature_256.npy` | 256 維影像特徵 |
| `meta.json` | ROI 方法、品質結果、狀態與耗時 |

其他輸出：

- `docs/roi_eval.md`：ROI 成功率與 fallback 統計
- `logs/pipeline_latency_vm.csv`：每張影像的處理時間 CSV
- `data/raw/<image_id>.txt`：pipeline 可使用的 YOLO ROI label

`logs/` 是效能記錄，不是 pipeline 啟動的必要輸入；不需要查看效能或研究報告時可以忽略它。

## Pipeline 程式位置

| 功能 | 程式位置 |
|---|---|
| 主流程 | `src/pipeline_local.py` |
| MediaPipe ROI | `src/roi/roi_mediapipe.py` |
| YOLO ROI fallback | `src/roi/roi_yolo.py`, `src/roi/roi_yolo_detect.py` |
| 固定裁切 fallback | `src/roi/roi_fixed_crop.py` |
| 品質檢查 | `src/roi/quality_check.py` |
| 舌頭 mask fallback | `src/deid/build_tongue_mask.py` |
| 去識別化 | `src/deid/deid_mask_only.py` |
| segmentation 推論 | `src/seg/inference.py`, `src/seg/model.py` |
| 特徵擷取 | `src/seg/feature_extractor.py` |
| ROI 報告 | `src/update_roi_eval.py` |

主要模型：

- `face_landmarker.task`：MediaPipe face landmark model
- `hand_landmarker.task`：MediaPipe hand landmark model
- `models/seg/best.pth`：舌頭 segmentation checkpoint（存在時使用）
- `yolov8n-seg.pt`：YOLO 模型檔

如果 `models/seg/best.pth` 不存在，pipeline 會使用 HSV mask fallback；主流程仍可執行，但 segmentation 品質會不同。

## 使用 CVAT 訓練 segmentation 模型

CVAT 標註、COCO 匯出、資料夾整理與訓練指令請看 [docs/CVAT_TRAINING.md](docs/CVAT_TRAINING.md)。

訓練完成後，將最佳 checkpoint 放到：

```text
models/seg/best.pth
```

## Docker

Docker/Compose 目前是部署骨架，詳細指令請看 [docs/DEPLOY.md](docs/DEPLOY.md)。主 pipeline 的本機執行方式仍以上面的 Python 指令為準。

## 專案結構

```text
src/                 主 pipeline 與模型程式
data/raw/            輸入影像與 ROI label
data/out/            每張影像的 pipeline 輸出
models/              模型 checkpoint
docs/                設定、CVAT 與部署說明
tools/               資料準備與 YOLO 訓練工具
test/                手動或自動測試工具（主 pipeline 不依賴）
```

影像、模型 checkpoint、`data/out/` 與效能 log 都屬於執行資料，不需要時不要提交到 Git。
