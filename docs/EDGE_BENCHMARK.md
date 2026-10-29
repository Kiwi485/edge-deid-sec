# Raspberry Pi 4 Model B 實體裝置效能測試

本指南使用專案的 TFLite 模型與推論流程，在實際裝置上測量 256×256
U-Net + MobileNetV2 模型。請在 Raspberry Pi 上執行測試，並保留產生的
CSV 與環境資訊檔；這些數據不能以推測或模擬值取代。除非以相同的計時
範圍與執行環境重新測量，否則現有 VM 數據不能直接與本測試比較。

**本測試直接在 Raspberry Pi OS 的 Python 環境中執行，不需要 Docker。**
Issue 2 要驗證的是模型能否在實體 Pi 上執行及其實際效能；使用 Docker
不是必要條件，也不應以桌上型電腦或 VM 的 Docker 測試取代 Pi 實測。

## 準備 Raspberry Pi

記錄確切的主機板版本與 RAM 容量、作業系統映像、散熱方式、儲存裝置、
電源供應器及電源模式。重新開機後，讓 Pi 閒置數分鐘，關閉不必要的程式，
並使用穩定的電源。記錄測試開始時裝置是閒置狀態還是已經升溫。測試期間
不要同時執行模型訓練或其他高負載工作。

將專案儲存庫和 `models/seg/model.tflite` 複製到 Pi。TFLite 模型檔案被
Git 忽略，必須另外複製，或依照 [DEPLOY.md](DEPLOY.md) 的說明，從
`models/seg/best.pth` 匯出。確認它是所選用的 U-Net + MobileNetV2 模型，
並從產生的 `environment.json` 記錄模型的 SHA-256 雜湊值。

若系統支援，請在 64 位元 Raspberry Pi OS 上使用 Python 3.11：

```bash
python3.11 -m venv .venv-edge
source .venv-edge/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-edge.txt
```

`requirements-edge.txt` 列出額外需要的 LiteRT 執行環境。基準測試腳本也會
以 `pip freeze` 擷取已安裝的套件資訊；實際在 Pi 上安裝的環境才是相容性
判斷依據。開始測試前，請確認以下指令能成功執行：
`python -c 'import ai_edge_litert'`。

將固定順序的 93 張基準影像放在私人資料夾中。分割模型單項測試請使用
ROI 裁切影像；端到端測試則使用相對應的原始照片。腳本會依檔名字典順序
排序影像，先執行 10 次暖機推論，再對每張影像進行三輪完整測試。兩種模式
必須使用相同的影像集合及順序。

本次使用 93 張影像，而不是 Issue 2 建議的 100 張；請在論文中明確記錄
此差異及採用 93 張的原因。每輪都要處理全部 93 張，三輪測試會在每種模式
產生 279 筆計時紀錄（不包含暖機）。重複測量不代表有 279 張不同影像。
若要與桌機或 VM 比較，請在各環境使用同一批 93 張影像重新測量。

建立 `device-notes.json` 檔案（未知資訊請勿自行猜填）：

```json
{
  "device_model": "Raspberry Pi 4 Model B",
  "board_revision": "FILL IN",
  "ram_capacity": "FILL IN",
  "storage_type": "FILL IN",
  "cooling_method": "FILL IN",
  "power_mode": "FILL IN"
}
```

若 Linux 有提供資訊，腳本會自動偵測裝置樹中的型號、CPU／架構、邏輯核心
數及 RAM。請將未偵測到的確切硬體資料補入上述備註檔。`--threads 1` 會將
LiteRT 解譯器的執行緒數固定為 1。測試只使用 CPU，不會啟用任何加速器
delegate。

## 執行基準測試

請在 Pi 上的專案根目錄執行。若資料集包含個人或臨床影像，請將資料集放在
版本控制目錄之外。

**僅分割模型**的延遲包含影像解碼、RGB 色彩轉換、縮放與正規化、模型推論、
閾值處理，以及遮罩／輸出準備；不包含 ROI 偵測、其餘去識別化流程及輸出
檔案寫入。請提供 ROI 裁切影像作為輸入：

```bash
python src/benchmark_edge.py \
  --mode segmentation \
  --input-dir /path/to/benchmark-roi \
  --model models/seg/model.tflite \
  --output-dir results/physical_edge/segmentation \
  --limit 93 --warmups 10 --runs 3 --threads 1 \
  --device-notes /path/to/device-notes.json
```

**端到端模式**會使用原始影像，依序執行影像載入、品質檢查、ROI 偵測／
備援、裁切、分割、遮罩後處理、特徵擷取、去識別化、隱私檢查及輸出寫入。
每張影像的 `latency_ms` 對應 pipeline 的 `total_ms`。正式計時前會先暖機
模型，並另外記錄模型載入時間。此模式包含影像產物寫入（ROI、遮罩、特徵
陣列及去識別化影像），但不包含後續 `meta.json` 和基準測試 CSV 的管理
寫入時間：

```bash
python src/benchmark_edge.py \
  --mode pipeline \
  --input-dir /path/to/benchmark-originals \
  --model models/seg/model.tflite \
  --output-dir results/physical_edge/end_to_end \
  --limit 93 --warmups 10 --runs 3 --threads 1 \
  --device-notes /path/to/device-notes.json
```

完整 pipeline 除了分割模型，也需要 ROI 模型及專案相依套件。若某筆 pipeline
資料的狀態為 `quality_fail`，仍會納入端到端延遲統計，並計入摘要中的狀態
數量；請檢查 `status_counts`。只要有任何 `error`，基準測試就會中止，不會
回報不完整的結果。

## 輸出檔案與指標定義

每個輸出資料夾包含：

- `latency_raw.csv`：每輪測試中每張影像各有一筆紀錄；pipeline 模式也會記錄
  各處理階段的耗時。
- `latency_summary.csv`：各輪測試的統計值，以及合併所有計時結果後的統計值。
- `environment.json`：偵測到的硬體／軟體資訊、模型檔案大小與 SHA-256、
  排序後資料集的內容雜湊值、模型冷啟動載入時間、執行緒設定及程序峰值 RSS。
- `python_environment.txt`：基準測試環境中已安裝套件的名稱與版本。
- 端到端模式的每輪 pipeline 輸出產物及中間 CSV 會寫入暫存資料夾，納入
  延遲統計後即刪除。`latency_raw.csv` 使用位置編號而非影像檔名，以避免
  記錄可能含敏感資訊的檔名。

標準差採用所有影像延遲的母體標準差。p95 使用 NumPy 預設的線性百分位數
計算法。FPS 依 `1000 / 平均延遲` 計算，並非獨立量測的連續串流影格率。
峰值 RAM 是 Linux 上程序的最大常駐記憶體大小（`ru_maxrss`），涵蓋基準
測試程序、模型及已載入的函式庫；它不是整體系統記憶體用量變化。模型大小
為 TFLite 模型檔案的實際位元組數。

請將每張影像的原始 CSV、`environment.json`、`python_environment.txt` 和
裝置備註與論文的最終測量結果一併保存。只有在實體裝置上完成兩種基準測試
後，才能根據這些檔案宣稱已驗證 edge 部署可行性。

## 結果表

只有在產生的檔案中找到實際測量值後，才可將 TBD 替換為數據。除非以相同的
256×256 模型、TFLite 執行環境、執行緒數、93 張影像及其順序、暖機次數
與計時範圍重新測量，否則不要沿用舊 VM 數據。

| 環境／階段 | 架構 | 執行環境 | 延遲（毫秒／影像） | 中位數 | p95 | FPS | 峰值 RSS | 模型大小 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Raspberry Pi 4 Model B — 僅分割模型 | ARM64（待確認） | LiteRT（記錄版本） | TBD | TBD | TBD | TBD | TBD | 取自 environment.json |
| Raspberry Pi 4 Model B — 端到端 | ARM64（待確認） | LiteRT（記錄版本） | TBD | TBD | TBD | TBD | TBD | 同一模型 |

成功完成測量後，可採用以下審慎表述：

> 實體裝置基準測試顯示，所選 pipeline 可在受測的 Raspberry Pi 4 Model B
> 上本機執行，每張影像耗時 **[實測延遲]**，程序峰值記憶體為
> **[實測峰值 RSS]**。此結果支持該 pipeline 在受測硬體上的技術可行性，
> 但不能據此推定其在其他 edge 裝置上有相同效能。

完成測試之前，請明確說明實體裝置效能尚未測量；不要移除論文中的相關限制，
也不要將佔位值當作研究結果回報。
