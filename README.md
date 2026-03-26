# edge-deid-sec

本專案為團隊協作之 Edge AI / De-identification（去識別化）相關研究與開發專案，  
主要使用 **Python + MediaPipe（Tasks API）** 進行影像處理與實驗。

請所有成員在開始開發前，**務必閱讀並遵守本 README 與相關文件**，  
以確保專案環境一致、Git 流程正確、主分支（`main`）穩定。

---

## 🚀 新成員快速開始（必讀）

### 1️⃣ Clone 專案
```bash
git clone https://github.com/Kiwi485/edge-deid-sec.git
cd edge-deid-sec
````

---

### 2️⃣ 建立並切換自己的開發分支

❗ **禁止直接在 main 分支開發**

bash
git checkout -b feature-你的功能名稱

範例：

bash
git checkout -b feature-roi-detection

---

### 3️⃣ 建立開發環境（Python / MediaPipe）

📄 **完整安裝流程請參考（必讀）：**
👉 SETUP_MEDIAPIPE_WINDOWS.md

此文件包含：

* Python 版本規範（3.11）
* 虛擬環境 .venv311
* VS Code Interpreter 設定
* MediaPipe / OpenCV 安裝
* 攝影機測試與除錯

---

## 🐍 Python / 虛擬環境規範（重要）

* 本專案 **不會將虛擬環境加入 Git**

  * .venv / .venv311 不會被 push
* 每位成員需在 **自己的電腦** 建立虛擬環境
* 套件版本以 requirements.txt 為準（若有提供）

### 環境建立流程（摘要）

bash
python -m venv .venv311
.venv311\Scripts\activate
pip install -r requirements.txt

> ⚠️ 每次「新開 Terminal」時，都需要重新執行 `activate`。

---

## 🌳 Git 分支與協作規範（摘要）

* main

  * 穩定分支
  * ❌ 不可直接開發

* 開發流程

  * 每人只能在 **自己的分支** 上開發
  * 功能完成後透過 **Pull Request (PR)** 合併到 main
  * 未經 review 請勿自行 merge

📘 **完整 GitHub 協作流程與詳細指令說明**
👉 GITHUB_TEAMGUIDE.md

（包含：PR 時機、常見 Q&A、stash / reset / diff、流程圖等）

---

## 📁 專案文件說明

| 文件                           | 說明                  |
| ---------------------------- | ------------------- |
| README.md                  | 專案入口、規範摘要           |
| SETUP_MEDIAPIPE_WINDOWS.md | 開發環境安裝與測試（必讀）       |
| GITHUB_TEAMGUIDE.md        | Git / GitHub 協作完整指南 |
| requirements.txt           | Python 套件版本清單（若有提供） |

---

## ⚠️ 注意事項

* 請勿將以下內容加入 Git：

  * .venv / .venv311
  * __pycache__
  * 編輯器暫存檔
* 不確定 Git 操作時，**先詢問再 merge**
* commit 訊息請清楚描述修改內容，避免使用：

  * update
  * fix

---

## 🧠 快速記憶（團隊共識）

> main 不動
> 功能開分支
> 改完發 PR
> review 才合併

---

## ROI 測試（VM）

可先用 50 張資料快速驗證 MediaPipe ROI 成功率與錯誤容錯：

bash
python src/roi/test_roi_batch.py --input data/raw --limit 50

執行完整批次管線（推薦，一次完成推論與報告更新）：

bash
# macOS / Linux
./.venv311/bin/python src/pipeline_local.py && ./.venv311/bin/python src/update_roi_eval.py

# Windows (PowerShell)
.\.venv311\Scripts\python.exe src\pipeline_local.py; .\.venv311\Scripts\python.exe src\update_roi_eval.py

說明：

- 前半段 `src/pipeline_local.py`：對 data/raw 全部影像執行 ROI/品質檢查並輸出到 `data/out`。
- 後半段 `src/update_roi_eval.py`：依據最新 data/out/*/meta.json 重新產生 `docs/roi_eval.md`。
- 若只執行前半段，`docs/roi_eval.md` 不會自動更新。

檢查輸出：

- data/out/<image_id>/meta.json 是否含 `roi_bbox`、`timing_ms.roi_ms`、`status`、`error`
- 單張失敗時，其它圖片仍持續處理（CSV 筆數不應提前中斷）

## Docker / Compose 部署骨架

為了讓之後 ROI / DeID API 完成後，可以直接接上部署流程，本專案先建立一組 Docker / Docker Compose 骨架（placeholder）：

### 內容摘要

- Dockerfile
  - 基底映像：`python:3.11-slim`
  - 安裝 OpenCV 需要的系統套件（`libglib2.0-0`, `libsm6`, `libxext6`, `libxrender1`, `libxcb1`, `libgl1`）
  - 使用 requirements.txt 安裝 Python 套件
  - 預設工作目錄：`/app`
  - 預留 API port：`EXPOSE 8000`
  - 目前 CMD：`python mp_test.py`（僅作為測試腳本／placeholder，之後會改成真正 API 入口）

- docker-compose.yml
  - service api
    - `build: .`（使用專案根目錄的 Dockerfile）
    - ports: 8000:8000
    - volumes 掛載：
      - ./data → /app/data
      - ./logs → /app/logs
    - 未來可透過 command: 覆蓋 Dockerfile 的 CMD，接上真正 API。
  - service `otel-collector`（placeholder）
    - 映像：`otel/opentelemetry-collector:latest`
    - 僅先建立容器與基本啟動流程，日後再補 config 與相依設定。

- docs/DEPLOY.md
  - 說明：
    - 如何在本機 build 映像：`docker build -t edge-deid-sec-api .`
    - 如何使用 docker compose up / down 啟動與關閉服務
    - volume / port 配置說明
  - 提醒現在的 mp_test.py 只是測試腳本，容器內尚未掛實體攝影機。

### 快速測試步驟（開發用）

在專案根目錄：

```bash
# 建立映像
docker build -t edge-deid-sec-api .

# 單獨啟動容器測試（可看到 MediaPipe / OpenCV log）
docker run --rm -p 8000:8000 edge-deid-sec-api

# 使用 docker compose 啟動整個骨架
docker compose up

# 查看 service 狀態
docker compose ps

# 關閉服務
docker compose down
```
## Output Contract Validator 與 Evidence Pack (輸出契約驗證器與證據包)

這一節說明如何驗證 pipeline 輸出格式（contract），以及如何產生可交付、可抽查的 evidence pack。

### 功能概述

- 檢查每個 data/out/<image_id>/ 是否包含：
  - roi.png
  - mask.png
  - deid.png
  - feature_256.npy
  - meta.json
- 驗證 meta.json 的必填欄位與值域：
  - image_id / input_file 與檔名一致
  - roi_method_used 非空（除非整張 status=error）
  - roi_bbox 非空矩形
  - timing_ms 內含 roi_ms / seg_ms / feat_ms / deid_ms / total_ms，且皆為非負數
  - status ∈ {ok, quality_fail, error}
  - status=error 時，error 必須有具體說明
- 驗證 logs/pipeline_latency_vm.csv：
  - 表頭欄位順序固定：image_id, input_file, roi_ms, seg_ms, feat_ms, deid_ms, total_ms, status
  - 每個本批 data/raw 的 image_id 在 CSV 中恰好出現一次，且 image_id / input_file / status 與 meta.json 一致
- 產生 evidence pack（evidence/<batch-tag>）：
  - validation_summary.csv：每張影像的 pass/fail 清單與原因
  - csv_snapshot/pipeline_latency_vm.csv：本批次 CSV 副本
  - roi_eval.md：對齊 docs/roi_eval.md 結構的 ROI/quality 評估報告快照
  - samples_for_review/：最多 10 張抽樣樣本，每張包含 roi/mask/deid/feature_256/meta.json，可供 PM / 老師人工檢查

### 一次完整驗證與產生 evidence pack 的步驟

1. 啟動虛擬環境（專案根目錄）  
   `.\.venv311\Scripts\Activate.ps1`

2. 清除舊的 latency CSV（避免混入舊批次資料）  
   `Remove-Item .\logs\pipeline_latency_vm.csv`

3. 針對目前 data/raw 這一批影像跑 batch pipeline：  
   `python src/pipeline_local.py`

4. 更新 ROI 評估報告（可選，但建議一起做）：  
   `python src/update_roi_eval.py`

5. 執行輸出驗證器並產生 evidence pack（以 batch tag = w4-issue3 為例）：  
   `python src/validate_outputs.py --batch-tag w4-issue3`

執行後預期終端輸出摘要類似：

- Total images: N  
- Pass: N  
- Fail: 0

### 自我檢查與注意事項

- 在 evidence/w4-issue3 中檢查：
  - validation_summary.csv：所有列的 final_result 應為 pass，若有 fail，files_missing / meta_issues / csv_issues 應能清楚說明原因。
  - csv_snapshot/pipeline_latency_vm.csv：行數約等於本批影像數，無重複 image_id。
  - roi_eval.md：統計數字與目前這一批 data/raw / data/out 對起來。

## W4-1 / W4-2 ROI Fallback 更新（給隊友快速交接）

### 本次解的兩個 issue（decomposition）

1) W4-1: YOLO Label Parser 與 BBox 轉換
- 目標：讀取 YOLO `.txt`（normalized）並轉成 pipeline 使用的 pixel bbox `[x1,y1,x2,y2]`。
- 主要檔案：
  - `src/roi/roi_yolo.py`
  - `test/test_roi_yolo.py`
  - `test/verify_yolo_bbox.py`
- 完成內容：
  - 建立 `load_yolo_bbox(label_path, image_shape)`。
  - 完整錯誤處理（檔案不存在、格式錯誤、非數字、超範圍、退化 bbox）。
  - 單元測試 15 個 case（正常與異常路徑）。

2) W4-2: 將 YOLO 整合為 ROI fallback
- 目標：MediaPipe 失敗時，先嘗試 YOLO label，再退 fixed crop。
- 主要檔案：
  - `src/pipeline_local.py`
  - `src/roi/test_roi_batch.py`
  - `src/update_roi_eval.py`
- 完成內容：
  - ROI 流程改為：`mediapipe -> yolo_fallback -> fixed_fallback`。
  - `meta.json` 的 `roi_method_used` 新增 `yolo_fallback`、`fixed_fallback`。
  - 報告統計支援 YOLO fallback 與 fixed fallback 分開計數。

### 額外補強（避免 bootstrap 死循環）

- 在 `src/pipeline_local.py` 加入「自動寫入 YOLO `.txt`」：
  - 每張圖完成 ROI 後，若 bbox 合法，會在 `data/raw/<image_id>.txt` 寫入一行 YOLO label。
  - 下一次跑 pipeline 可直接使用該 label 進行 `yolo_fallback`。


### 如何測試（隊友可直接執行）

1) 單元測試 YOLO parser

```bash
python -m pytest test/test_roi_yolo.py -q
```

預期：全部通過（15 passed）。

2) 跑 batch pipeline（會自動產生/更新 data/raw/*.txt）

```bash
# Windows PowerShell
.\.venv311\Scripts\python.exe src\pipeline_local.py
```

檢查：
- `data/out/<image_id>/meta.json` 有 `roi_method_used` 與 `roi_bbox`。
- `roi_method_used` 可能是 `mediapipe` / `yolo_fallback` / `fixed_fallback`。
- `data/raw/` 會出現或更新同名 `.txt` label。

3) 更新 ROI 評估報告

```bash
.\.venv311\Scripts\python.exe src\update_roi_eval.py
```

檢查：
- 報告中有 `ROI 使用 YOLO fallback` 與 `ROI 使用 fixed fallback` 指標。

4) 可視化抽查 YOLO bbox（verify_yolo）

先決條件：
- `data/raw` 內要有圖片與同名 `.txt`（例如 `10001.jpg` 與 `10001.txt`）。
- 若 `.txt` 不齊全，先跑一次 `src/pipeline_local.py` 讓系統自動補寫。

執行指令（Windows PowerShell）：

```bash
.venv311/Scripts/python.exe test/verify_yolo_bbox.py --output data/verify_out --limit 20
```

參數說明：
- `--input`：原始圖片與 label 所在目錄。
- `--output`：可視化結果輸出目錄。
- `--limit`：最多處理幾張，先用 10 張快速抽查。

預期終端輸出：
- `[OK]`：成功讀取 label 並畫框。
- `[SKIP] no label`：找不到同名 `.txt`，此張被跳過。
- `[ERR]`：label 內容格式錯誤或圖片讀取失敗。

檢查重點：
- `data/out/yolo_bbox_*.jpg` 的綠框是否包住目標 ROI。
- 框不應超出影像邊界，也不應是退化矩形（寬或高接近 0）。
- 若大量 `[SKIP]`，代表 labels 尚未產生或命名不一致。
  - samples_for_review/：任選幾個 image_id，確認：
    - roi.png 是合理的人臉/上半身區域。
    - mask.png 目前為 placeholder，全黑圖為預期結果。
    - deid.png 尺寸與輸入一致，沒有明顯壞檔。
    - meta.json 的 status / error 能解釋這張是 ok 或 quality_fail（例如 status=quality_fail, error="blur; no_face_landmarks"）。

- 每次要產生新的 evidence pack 建議流程：
  - 先刪除舊的 logs/pipeline_latency_vm.csv。
  - 視需求清空 data/out 或確保 data/raw 只放本次要驗證的影像。
  - 再重跑 `python src/pipeline_local.py` 和 `python src/validate_outputs.py --batch-tag <新的名稱>`。

- evidence/ 資料夾通常不建議 commit 進 Git。  
  在 PR 描述中請註明：
  - 使用的 batch-tag（例如 w4-issue3）。
  --batch-tag 後面那個字串只是「這次驗證／證據包的名字」，不是程式裡固定寫死的東西。
  - reviewer 如需重建 evidence pack，可在 VM 上依照本節步驟重跑一次。