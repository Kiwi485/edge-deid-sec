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

### W7：HSV / GLCM 特徵

特徵版本為 `v2_glcm`，pipeline 會將版本寫入 `meta.json` 的 `feature_version`。輸出仍是 `(256,) float32`：HSV 48 維、RGB 48 維、形狀 48 維、LBP 96 維、GLCM 16 維（RGB 與形狀區段含預留補零）。GLCM 只計算兩端都在舌頭 mask 內的像素配對。

在 Python 3.11 環境安裝新增依賴並執行測試；Docker 使用前請重新 build：

```bash
python -m pip install "scikit-image>=0.25,<0.26"
python -m pytest -q test/test_feature_extractor.py
```

完整配置、GLCM 參數與真實照片驗證步驟請看 [Feature 256 規格](docs/feature_256_spec.md)。舊版 LBP 是 112 維，不能與新版特徵混用；既有特徵資料需要重新產生，下游分類器也需重新訓練。W7 不改 segmentation 模型，也不代表已驗證分類效益或 Raspberry Pi 效能。

其他輸出：

- `docs/roi_eval.md`：ROI 成功率與 fallback 統計
- `logs/pipeline_latency_vm.csv`：每張影像的處理時間 CSV
- `data/raw/<image_id>.txt`：pipeline 可使用的 YOLO ROI label

`logs/` 是效能記錄，不是 pipeline 啟動的必要輸入；不需要查看效能或研究報告時可以忽略它。

## W8：OpenTelemetry 監控

W8 為每張影像記錄 `total`、`roi`、`seg`、`feat`、`deid`、`privacy` spans，不改模型或特徵。預設關閉，啟用後輸出 JSON 到終端機／Docker logs；目前沒有監控網頁或遠端 Collector。

Windows PowerShell（已安裝專案依賴的 Python 3.11 環境）：

```powershell
.\.venv311\Scripts\python.exe -m pip install "opentelemetry-api>=1.30,<2" "opentelemetry-sdk>=1.30,<2"
.\.venv311\Scripts\python.exe -m pytest -q test/test_pipeline_telemetry.py
```

上面的測試不需要照片或模型。使用照片前，請依 [W8 操作與驗證步驟](docs/OPENTELEMETRY.md)設定 `EDGE_DEID_TRACING=console`；內含 PowerShell、Bash、Compose 指令與如何查看成功／失敗紀錄。

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
- `models/seg/best.pth`：主 pipeline 必要的舌頭 segmentation checkpoint
- `yolov8n-seg.pt`：YOLO 模型檔

如果 `models/seg/best.pth` 不存在，pipeline 會以 `seg_model_missing` 錯誤停止該影像處理；目前沒有 HSV segmentation fallback。請先訓練模型，並將 checkpoint 放到上述路徑。

## 使用 CVAT 訓練 segmentation 模型

CVAT 標註、COCO 匯出、資料夾整理與訓練指令請看 [docs/CVAT_TRAINING.md](docs/CVAT_TRAINING.md)。

訓練完成後，將最佳 checkpoint 放到：

```text
models/seg/best.pth
```

## Docker

Docker/Compose 目前是部署骨架，詳細指令請看 [docs/DEPLOY.md](docs/DEPLOY.md)。主 pipeline 的本機執行方式仍以上面的 Python 指令為準。

要用同一批照片比較 `best.pth` 與 TFLite 的 Docker 執行結果，請依照 [Docker 推論驗證步驟](docs/DEPLOY.md#用同一批照片驗證-docker-推論)操作；預設仍使用 `best.pth`，不會使用 `last.pth`。

### 用 Docker 執行 pipeline（Windows PowerShell）

先開啟 Docker Desktop，把照片放在 `data/raw/`，在專案根目錄執行。`BATCH_LIMIT` 不可超過 `data/raw/` 的照片數，否則 extraction 會一直等待。

| 後端 | 需要的模型 | 適合 |
| --- | --- | --- |
| `torch`（預設） | `models/seg/best.pth` | 一般使用、其他電腦 |
| `tflite` | `models/seg/model.tflite` | 需要較快推論時 |

`model.tflite` 不在 Git 裡，須另外複製或依 [DEPLOY.md](docs/DEPLOY.md#w6tflite-分割模型可選)匯出。

**使用 PyTorch：**

```powershell
$env:BATCH_LIMIT = "5"
$env:SEG_BACKEND = "torch"
docker compose up --build --force-recreate
```

**使用 TFLite：**

```powershell
$env:BATCH_LIMIT = "5"
$env:INSTALL_TFLITE = "1"
$env:SEG_BACKEND = "tflite"
docker compose up --build --force-recreate
```

PowerShell 關閉後環境變數會消失。若想讓自己的電腦固定使用 TFLite，可在專案根目錄建立 `.env`（已被 Git 忽略）：

```text
BATCH_LIMIT=5
INSTALL_TFLITE=1
SEG_BACKEND=tflite
```

之後只要執行 `docker compose up --build --force-recreate`。

檢查每張照片使用的後端與狀態：

```powershell
Get-ChildItem .\data\out -Filter meta.json -Recurse | ForEach-Object {
  $m = Get-Content $_.FullName -Raw | ConvertFrom-Json
  [PSCustomObject]@{ Image=$_.Directory.Name; Status=$m.status; Backend=$m.seg_backend }
} | Format-Table
```

> **注意：** Compose 每次執行都會清空 `data/out/` 並重建 `logs/pipeline_latency_vm.csv`。需要保留的結果請先複製到 `outputs/`。

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
test kiwi