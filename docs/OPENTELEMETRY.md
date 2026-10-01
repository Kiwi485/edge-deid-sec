# W8：OpenTelemetry 監控

W8 記錄「每張影像在哪些階段花了多少時間、哪個階段失敗」。它不更換 W6 的模型，也不改 W7 的特徵。預設關閉，設定 `EDGE_DEID_TRACING=console` 才會啟用；`off` 為關閉，其他值會報設定錯誤。

## 一筆 trace 代表什麼

每張影像建立一筆 trace，包含一個 `total` 父 span 與實際執行到的階段 spans：

```text
total
  roi
  seg
  feat
  deid
  privacy
```

- `roi`：MediaPipe 與必要的 YOLO／固定裁切 fallback。
- `seg`：選定的 PyTorch 或 TFLite 分割推論與 mask 後處理。
- `feat`：W7 的 256 維特徵計算。
- `deid`：mask-only 去識別化。
- `privacy`：隱私指標計算與通過判定。
- `total`：影像載入、縮放、品質檢查、上述階段及影像／特徵寫入；和既有總計時一樣，不包含最後的 metadata 與 CSV 寫入，也不包含 acquisition、IPC 等待或批次初始化。

正常完成且品質、隱私檢查通過時，六個 spans 都是 `OK`。階段丟出例外時，該 span 與 `total` 是 `ERROR`，尚未執行的階段不會產生 span。品質檢查未通過會將 `total` 標為 `ERROR`；隱私檢查未通過或發生例外，則將 `privacy` 與 `total` 標為 `ERROR`。

既有 pipeline 的 `status` 意義不變：隱私失敗時 metadata 的 `status` 仍可能是 `ok`，所以也要檢查 `privacy_metrics.privacy_pass`。trace 另用 `pipeline.status`、`privacy.pass` 與固定的 `pipeline.failure` 代碼表達這個差異。

## 先跑測試：不需要照片或模型

以下為 Windows PowerShell，請在專案根目錄執行。需要已安裝 Python 3.11，且 `.venv311` 確實使用 3.11；資料夾名稱本身不會指定版本。新環境可用 `py -3.11 -m venv .venv311` 建立，不要用此指令直接覆蓋舊的不同版本環境。

若已安裝專案依賴，只需補裝 OpenTelemetry：

```powershell
.\.venv311\Scripts\python.exe --version
.\.venv311\Scripts\python.exe -m pip install "opentelemetry-api>=1.30,<2" "opentelemetry-sdk>=1.30,<2"
.\.venv311\Scripts\python.exe -m pytest -q test/test_pipeline_telemetry.py
```

若只想在乾淨環境執行 W8 測試，不需要安裝模型框架，改用以下最小依賴再執行同一個測試指令：

```powershell
.\.venv311\Scripts\python.exe -m pip install "opencv-python-headless==4.13.0.90" "scikit-image>=0.25,<0.26" "opentelemetry-sdk>=1.30,<2" pytest
```

最小依賴環境與完整專案環境應分開使用，避免混裝不同 OpenCV 發行套件。正式執行 pipeline 仍需完整專案依賴，可用 `python -m pip install -r requirements.txt` 安裝。

測試使用合成影像，模擬 ROI／品質檢查與兩種模型後端，實際執行特徵、DeID、隱私檢查及輸出。測試涵蓋 spans 階層、每張獨立 trace、JSON exporter、監控開關前後輸出一致，以及各階段錯誤與敏感資訊排除。這不是實際模型推論驗證。

## 用照片執行：Windows PowerShell

準備專案依賴、模型與至少 5 張照片，照片放在 `data/raw/`。下面將測試輸出放到已忽略的 `data/out/w8/`，並用獨立 CSV，避免覆蓋預設批次；重跑同一指令仍會覆蓋本次 W8 結果。

```powershell
$env:EDGE_DEID_TRACING = "console"
.\.venv311\Scripts\python.exe src\pipeline_local.py --limit 5 --out-dir data/out/w8 --csv logs/pipeline_latency_w8.csv
```

預設使用 PyTorch。若已準備 W6 的 TFLite 模型和執行依賴，在 pipeline 指令最後加 `--seg-backend tflite`；W8 不會自動切換模型。

測試完關閉監控：

```powershell
$env:EDGE_DEID_TRACING = "off"
```

Linux/macOS 在已啟用的 Python 3.11 專案環境中：

```bash
EDGE_DEID_TRACING=console python src/pipeline_local.py --limit 5 --out-dir data/out/w8 --csv logs/pipeline_latency_w8.csv
```

## Docker Compose

Compose 把開關傳給 extraction；重建會安裝新增依賴。請先保留要比較的舊輸出與 CSV，因為現有 Compose 啟動參數包含 `--clear-out` 和 `--reset-csv`，會清除預設輸出（包含 `data/out/w8/`）。請準備至少 `BATCH_LIMIT` 張有效副檔名的照片，避免 socket server 等待不足的工作數。

Windows PowerShell：

```powershell
$env:EDGE_DEID_TRACING = "console"
$env:BATCH_LIMIT = "5"
docker compose up --build
docker compose logs --no-color extraction
```

Linux/macOS Bash：

```bash
BATCH_LIMIT=5 EDGE_DEID_TRACING=console docker compose up --build
docker compose logs --no-color extraction
```

Compose 仍依 `SEG_BACKEND` 決定模型，預設為 `torch`；W6 TFLite 的 build 與模型準備請看 [DEPLOY.md](DEPLOY.md)。observability service 仍負責既有報表，這一版不是 OTel Collector；也沒有新增跨 Unix socket 的 trace context 傳遞。

## 怎麼看紀錄

終端機／Docker logs 會出現逐筆、多行 JSON span，並混有既有程式訊息；整份 log 不是單一 JSON 檔。

| 欄位 | 用途 |
| --- | --- |
| `name` | 階段，例如 `seg`、`feat`、`total` |
| `context.trace_id` | 同一張影像的 spans 使用相同 ID；不包含檔名 |
| `parent_id` | 子 span 指向 `total` 的 span ID |
| `start_time`、`end_time` | 相減得到階段耗時 |
| `status.status_code` | `OK` 或 `ERROR` |
| `attributes` | 後端、特徵版本、ROI 方法、通過狀態或固定失敗代碼 |
| `resource.attributes.service.name` | 固定為 `edge-deid-extraction` |

同時檢查輸出 metadata 的 `status`、`seg_backend`、`feature_version` 和 `privacy_metrics.privacy_pass`。第一版不在 trace 記錄檔名，請勿只靠 log 順序配對敏感影像。

## 隱私與效能限制

- spans 不記錄影像、mask、特徵向量、病患檔名、完整路徑、例外訊息或堆疊；只加入上述受控屬性。
- 此限制僅適用於新增 spans。既有 metadata、一般 stdout 與 extraction 訊息仍可能有檔名或路徑，不代表整份 Docker log 已去識別化；分享前仍須審查。
- 使用 console exporter，不透過網路傳送 traces，也不新增 Collector／Jaeger。這不等於容器本身已禁網；那是 W10 的工作。
- 使用同步 `SimpleSpanProcessor`，每個 span 結束即輸出，正常流程不需等候批次 flush。console 寫入會增加耗時；`total` 包含子 span 輸出的額外成本，CSV 與 span 邊界也不完全相同。
- 比較效能時要註明監控開關，不要混合不同設定的樣本。真實照片、Pi 上的監控成本及 W9 的 1,000 次效能證據仍待測量。