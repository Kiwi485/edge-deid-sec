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
<<<<<<< HEAD






好的！您可以親自在終端機執行以下流程，來確認所有問題都已經被解決並且資料完美：

### 第一步：進入專案環境
請打開一個新的 Mac 終端機，並確保進入正確的專案資料夾與啟動虛擬環境：
```bash
cd /Users/chenguanjie/Desktop/脫敏輸出/edge-deid-sec
source .venv311/bin/activate
```

---

### 第二步：故意製造破壞（驗證覆寫機制）
既然我們要驗證「修復是否有效」，我們要故意執行兩次 pipeline，確認它真的**不會**把資料疊加上去（變成兩倍）：
```bash
python src/pipeline_local.py
python src/pipeline_local.py
```
> *(執行過程中，如果您有 120 張圖片，它應該只會花幾十秒跑完。)*

---

### 第三步：檢查 CSV 檔案行數
跑完兩次後，我們來檢查最新產生的 pipeline_latency_vm.csv 的行數。因為您有 120 張相片加上 1 行標題列，行數必須精準卡在 121行。
輸入這行：
```bash
wc -l logs/pipeline_latency_vm.csv
```
✅ **預期結果：** 會印出 `121 logs/pipeline_latency_vm.csv`。

---

### 第四步：確保沒有任何重複的 `image_id`
使用 `awk` 指令將 CSV 的第一欄抓出來，並檢查有沒有重複的項目：
```bash
awk -F',' 'NR>1 {print $1}' logs/pipeline_latency_vm.csv | sort | uniq -d
```
✅ **預期結果：** 終端機什麼字都不應該印出來。如果有殘留的舊資料，這裡會跑出一堆重複的檔名；如果一個字都沒跳出來，代表所有的檔名都只出現了一次！

---

### 第五步：產出您要的 Final Validation 報表
如果上面的資料都很完美，這個步驟就能順利通過，把假性的 fail 完全消除：
```bash

python src/pipeline_local.py
python src/update_roi_eval.py
python src/validate_outputs.py
```
✅ **預期結果：** 會看到：

Validation summary
==================
Total images: 120
Pass: 120
Fail: 0

然後您可以打開 `validation_summary.csv` 看一下，確認 `csv_row_duplicate` 欄位全都變成了 `0`。`

---

經過這樣親自操作與驗收一次，您就可以 100% 放心把這個專案打包作為 W4 evidence 提交了！如果在途中還有遇到什麼問題可以隨時提出！重複驗證前需先刪除暫存：
find data/out -type f -name "deid.png" -delete
find data/out -type f -name "mask.png" -delete
find data/out -type f -name "roi.png" -delete
find data/out -type f -name "feature_256.npy" -delete
find data/out -type f -name "meta.json" -delete
rm -f logs/pipeline_latency_vm.csv
rm -f evidence/batch/validation_summary.csv
rm -f evidence/batch/csv_snapshot/pipeline_latency_vm.csv

再輸入：
python src/pipeline_local.py
python src/update_roi_eval.py
python src/validate_outputs.py
=======

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

## W4-issue2: YOLO ROI 人工標註摘要（舌頭 ROI）

### 這次實際做了什麼

- 新增簡易 YOLO 標註工具：`test/manual_yolo_annotator.py`
  - 使用 OpenCV 顯示 `data/raw` 影像。
  - 滑鼠左鍵拖曳畫出單一 bbox，按 `s` 直接寫入對應的 YOLO `.txt`（class 固定為 0）。
- 以該工具對 `data/raw` 內 **120 張影像全部重標** 舌頭 ROI：
  - 框選原則：以舌頭本體為主，保留少量邊界，避免整張臉/頭都包進去。
  - 每張圖只標註 1 個 bbox（pipeline 目前只讀取第一行 YOLO label）。
  - 完成後，專案中已完全找不到原本的固定 bootstrap 值 `0 0.500000 0.650000 0.600000 0.600000`。
- 使用 `test/verify_yolo_bbox.py` 抽查 YOLO bbox：
  - 在 `data/verify_out/` 產生 `yolo_bbox_<image_id>.jpg`，綠框位置與舌頭 ROI 對齊且彼此不同。
- 以新的 YOLO labels 重跑 W4 pipeline 與 ROI 報告：
  - `src/pipeline_local.py` + `src/update_roi_eval.py`。
  - `docs/roi_eval.md` 更新後顯示：
    - ROI 成功（mediapipe）：8/120 = 6.7%
    - ROI 使用 YOLO fallback：112/120 = 93.3%
    - ROI 使用 fixed fallback：0/120 = 0.0%
  - 代表所有 fallback case 都使用人工標註的 YOLO bbox，fixed fallback 不再被觸發。
- 以 batch tag = `w4-issue2` 產生 evidence pack：
  - `evidence/w4-issue2/validation_summary.csv`
  - `evidence/w4-issue2/csv_snapshot/pipeline_latency_vm.csv`
  - `evidence/w4-issue2/roi_eval.md`（報表快照）
  - `evidence/w4-issue2/samples_for_review/<image_id>/roi.png` 等，用於人工抽查。

### 簡單重跑步驟（需要重新驗證時）

> 前提：`data/raw/*.txt` 已有人工作為舌頭 ROI 標註（可透過 `test/manual_yolo_annotator.py` 產生）。

1. 啟動虛擬環境（專案根目錄）

```bash
cd d:/edge-deid-sec
.\.venv311\Scripts\Activate.ps1
```

2. 以現有 YOLO labels 重跑 W4 ROI pipeline

```bash
Remove-Item .\logs\pipeline_latency_vm.csv -ErrorAction Ignore
.\.venv311\Scripts\python.exe src\pipeline_local.py
.\.venv311\Scripts\python.exe src\update_roi_eval.py
```

3. 抽查 YOLO bbox（選擇性，但建議執行）

```bash
.\.venv311\Scripts\python.exe test\verify_yolo_bbox.py --input data/raw --output data/verify_out --limit 20
```

檢查：`data/verify_out/yolo_bbox_<image_id>.jpg` 的綠框應包住舌頭 ROI，且不同影像 bbox 不應全部相同。

4. 產生或重建 evidence pack（以 w4-issue2 為例）

```bash
.\.venv311\Scripts\python.exe src\validate_outputs.py --batch-tag w4-issue2
```

檢查重點：

- `docs/roi_eval.md` 中：
  - `ROI 使用 YOLO fallback` 為主要 fallback 來源。
  - `ROI 使用 fixed fallback` 理想上為 0%。
- `evidence/w4-issue2/samples_for_review/<image_id>/roi.png`：
  - ROI 裁切集中在舌頭附近，相較早期 fixed 中心裁切有明顯改善。

## Week 4: VM Smoke Test 與 Benchmark v0

目標是先做小批次 smoke test，確認 VM 環境可跑，再做正式 benchmark 取得可比較 baseline。

### 1) VM smoke test（5 到 10 張）

以 VS Code「執行按鈕」為主流程：

1. 開啟 `src/pipeline_local.py`，按右上角執行按鈕（Run Python File）。
2. 開啟 `src/validate_outputs.py`，按執行按鈕。

> 若只用執行按鈕（不帶參數），`pipeline_local.py` 會使用預設設定；若你要嚴格限制為 5 到 10 張，需改用參數模式（或暫時調整 `--limit` 預設值）。

用途：

- 快速確認 model 檔與依賴可正常載入（含 roi_mediapipe 初始化）
- 提前暴露 VM 路徑、套件、模型資源等環境問題

### 2) 正式 benchmark v0（至少 100 張）

以 VS Code「執行按鈕」依序執行：

1. `src/pipeline_local.py`
2. `src/validate_outputs.py`
3. `src/benchmark_vm.py`

正式 benchmark 前的資料清理原則：

- `logs/pipeline_latency_vm.csv` 預設會在執行 `src/pipeline_local.py` 時自動重建（除非你刻意使用 append 模式），通常不需要手動刪除。
- `data/out` 依需求決定是否清空；若要做完全可追溯的乾淨批次，建議清空或改用新的輸出資料夾。

### 3) 交付物

- 乾淨 latency CSV（不混入本機或舊測試資料）
- benchmark 報告：`results/benchmark_vm_v0.md`
- 指標涵蓋：roi_ms / seg_ms / feat_ms / deid_ms / total_ms
- 統計涵蓋：p50 / p95 / p99，並依 status 分群（ok / quality_fail / error）

---

## Tongue Segmentation — U-Net + MobileNetV2（`src/seg/`）

本段說明如何安裝相依套件、準備 CVAT 標註資料，以及如何訓練與推論舌頭 segmentation 模型。

### 架構概覽

```
input image
  └─ MediaPipe ROI (src/roi/)
       └─ U-Net + MobileNetV2 (src/seg/)   ← 本段
            ├─ tongue mask (binary PNG)
            └─ tongue-only image
                 └─ classifier / de-id (src/deid/)
```

### 1️⃣ 安裝相依套件（只需執行一次）

```powershell
# 啟動虛擬環境
.venv311\Scripts\activate

# 安裝 PyTorch（CPU 版本）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 安裝 segmentation + augmentation 套件
pip install segmentation-models-pytorch albumentations
```

驗證安裝：

```powershell
.venv311\Scripts\python.exe -c "import torch, segmentation_models_pytorch as smp, albumentations; print('torch', torch.__version__); print('smp', smp.__version__); print('albu', albumentations.__version__)"
```

---

### 2️⃣ CVAT 標註工作流程

#### Step 1 — 在 CVAT 標註舌頭 polygon

1. 前往 [app.cvat.ai](https://app.cvat.ai) 並登入
2. 建立新 Task，上傳影像（建議每次 50–100 張）
3. 選擇標註類型：**Polygon**，類別名稱設定為 `tongue`
4. 逐張用 polygon 圍出舌頭輪廓（至少標 30–50 張，建議 100+ 張）

#### Step 2 — 匯出 COCO 格式

1. Task 頁面 → **Export dataset**
2. 選擇格式：**COCO 1.0**（Instance Segmentation）
3. 下載並解壓 zip

#### Step 3 — 整理到 repo 資料夾

解壓後的資料夾通常長這樣（`images/` 與 `annotations/` 分開）：

```
桌面/
  images/default/     ← 圖片
  annotations/        ← instances_default.json
```

執行以下指令整理到 repo（**把路徑換成你實際的資料夾名稱**）：

```powershell
cd "C:\Users\kiwib\OneDrive\桌面\edge-deid-sec"

# 建立目標目錄
New-Item -ItemType Directory -Path "data\cvat\train\images" -Force
New-Item -ItemType Directory -Path "data\cvat\train\annotations" -Force

# 複製圖片
Copy-Item "C:\Users\kiwib\OneDrive\桌面\images\default\*" -Destination "data\cvat\train\images\"  

# 複製 annotations
Copy-Item "C:\Users\kiwib\OneDrive\桌面\annotations\*" -Destination "data\cvat\train\annotations\"
```

整理後的資料夾結構：

```
data/
  cvat/
    train/
      images/
        001.jpg
        002.jpg
        ...
      annotations/
        instances_default.json   ← CVAT 匯出的 COCO JSON
```

> **注意：** `data/cvat/` 內的圖片**不要 commit 到 Git**（影像檔案太大）。
> 在 `.gitignore` 加入 `data/cvat/` 或只 commit `instances_default.json`。

---

### 3️⃣ 訓練模型

#### 第一次測試（確認流程正確，不在意結果）

```powershell
.venv311\Scripts\python.exe src\seg\train.py --data-dir data\cvat --epochs 3 --batch-size 2 --no-pretrain
```

#### 正式訓練（有 ImageNet pretrained weights）

```powershell
.venv311\Scripts\python.exe src\seg\train.py --data-dir data\cvat --epochs 50 --batch-size 4
```

#### 常用參數說明

| 參數 | 預設值 | 說明 |
|---|---|---|
| `--data-dir` | 必填 | 資料集根目錄（含 `train/` 子目錄） |
| `--epochs` | 50 | 訓練週期數 |
| `--batch-size` | 8 | 每批次影像數（CPU 建議 4） |
| `--img-size` | 256 | 輸入影像邊長（正方形） |
| `--lr` | 1e-4 | 初始學習率 |
| `--no-pretrain` | — | 不使用 ImageNet weights（測試用） |
| `--out-dir` | `models/seg` | checkpoint 儲存目錄 |

訓練完成後，checkpoint 儲存於：

- `models/seg/best.pth`（val Dice 最高）
- `models/seg/last.pth`（最後一個 epoch）

---

### 4️⃣ 推論（對新圖片預測）

```powershell
.venv311\Scripts\python.exe src\seg\inference.py --image path/to/photo.jpg --model models\seg\best.pth --out-dir outputs
```

輸出：

- `outputs/<name>_mask.png` — 二值 mask（白=舌頭，黑=背景）
- `outputs/<name>_tongue.png` — 舌頭區域影像（背景歸黑）

---

### 5️⃣ 資料量建議

| 標註數量 | 預期 val Dice | 建議行動 |
|---|---|---|
| < 20 張 | < 0.1 | 繼續補標，先當 dry-run |
| 30–50 張 | 0.3–0.5 | 可看到基本形狀，繼續補標 |
| 100+ 張 | 0.6–0.8 | 實用等級 |
| 500+ 張 | > 0.85 | 高品質，可接 classifier |

> **目標：** val Dice > 0.7 才算達到可用水準。

---

### 6️⃣ 注意事項

- `data/cvat/` 內的原始影像建議不要 commit 到 Git（請加入 `.gitignore`）
- `models/seg/` 的 checkpoint 也不要 commit（檔案太大）
- 每次從 CVAT 重新匯出後，覆蓋 `data\cvat\train\annotations\instances_default.json` 並重跑訓練
- Windows 上 `--num-workers` 請保持預設值 `0`（避免 DataLoader deadlock）

---

## CVAT 安裝與基本使用紀錄

### 1. 目的

這份文件整理完成的工作，包含：

- 在 Windows 上使用 Docker Desktop + WSL2 架設 CVAT
- 讓 CVAT 可以從區網 IP 開啟
- 建立 Project / Task
- 上傳舌頭圖片
- 使用 Polygon 進行 segmentation 標註
- 匯出 COCO 格式資料集

這份文件可作為之後自己重做，或給隊友參考的操作紀錄。

---

### 2. 環境需求

**作業系統：** Windows

**已安裝工具：**
- Docker Desktop
- WSL2
- Ubuntu on WSL

**確認方式：** 在 Windows CMD / PowerShell：

```bash
wsl -l -v
```

如果看到類似：

```
NAME              STATE           VERSION
* Ubuntu          Running         2
  docker-desktop  Running         2
```

代表 Ubuntu 已安裝、WSL2 正常、Docker Desktop 正常使用 WSL2 backend。

---

### 3. 打開 Ubuntu

在 Windows CMD / PowerShell 輸入：

```bash
wsl -d Ubuntu
```

進去後會看到類似：

```
username@PCNAME:~$
```

---

### 4. 安裝基本工具

先更新套件並安裝 Git：

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y git
```

確認 Git：

```bash
git --version
```

---

### 5. 確認 Docker 可用

在 Ubuntu 中輸入：

```bash
docker --version
docker compose version
docker ps
```

如果有正常輸出，代表 Ubuntu 可以使用 Docker Desktop。

---

### 6. 下載 CVAT

在 Ubuntu 中輸入：

```bash
git clone https://github.com/cvat-ai/cvat.git
cd cvat
```

---

### 7. 啟動 CVAT

在 `~/cvat` 裡執行：

```bash
docker compose up -d
```

檢查狀態：

```bash
docker compose ps
```

如果 container 都是 `Up`，代表 CVAT 已啟動。

---

### 8. 建立管理員帳號

在 `~/cvat` 裡執行：

```bash
docker exec -it cvat_server bash -ic 'python3 manage.py createsuperuser'
```

然後依序輸入：username、email、password。

備註（常見流程與替代作法）：

- 如果你想在 container 內建立多個使用者或要用程式建立，可以進 `python3 manage.py shell`，再貼入 `create_user` 程式碼。貼入多行程式碼後，務必在結尾按一次 Enter 再按一次 Enter（也就是留一個空白行），否則像在 `for` 迴圈未結束的情況下直接輸入 `exit()` 會收到 `SyntaxError: invalid syntax`。

- 範例（可直接整段貼入 shell）：

```python
from django.contrib.auth import get_user_model
User = get_user_model()

users = [
  {"username":"teammate2","email":"teammate2@example.com","password":"Teammate2Pass123"},
  {"username":"teammate3","email":"teammate3@example.com","password":"Teammate3Pass123"}
]

for u in users:
  if not User.objects.filter(username=u["username"]).exists():
    User.objects.create_user(username=u["username"], email=u["email"], password=u["password"])
    print(f'Created user: {u["username"]}')
  else:
    print(f'User already exists: {u["username"]}')

```

- 更簡單／保險的做法是每次在 shell 裡只建立一個 user：

```python
User.objects.create_user(username="teammate2", email="teammate2@example.com", password="Teammate2Pass123")
```

按完並看到結果後再輸入 `exit()` 退出 container。

---

### 9. 解決 localhost / IP 存取問題

**問題：** 使用 `http://localhost:8080` 可開啟，但無法透過區網 IP 存取，改用 Wi-Fi IPv4（如 `192.168.68.92`）會出現 `404 page not found`。

**解法：**

```bash
export CVAT_HOST=192.168.68.92
docker compose down
docker compose up -d
```

之後使用 `http://192.168.68.92:8080` 登入。

**注意：** 設定 `CVAT_HOST` 後，`localhost:8080` 可能無法開啟，這是正常的，統一使用 IP。

若要永久保存設定，在 `~/cvat` 建立 `.env`：

```env
CVAT_HOST=192.168.68.92
```

然後重啟：

```bash
docker compose down
docker compose up -d --force-recreate
```

---

### 10. 建立 Project

1. 登入 CVAT → 點上方 **Projects** → 建立新 project
2. 名稱：`tongue-seg-v1`
3. 建立 label：`tongue`

> **注意：** 建立 project 時，label 不能只打在欄位裡，必須按 **Continue** 讓 label 真正加入，再按 **Submit & Continue**，否則可能出現建立失敗。

---

### 11. 建立 Task

1. 進入 project `tongue-seg-v1` → 建立 task
2. Task 名稱：`tongue-seg-test-01`
3. 上傳 jpg 圖片（第一次建議先測 3～5 張）

---

### 12. 進入 Job 進行標註

Task 建立後，CVAT 會自動切出 Job。

1. 點進 `Job #1`
2. 右側確認 label 為 `tongue`
3. 左側工具選 **Polygon** + **Shape**

> **Shape vs Track：** `Shape` 為單張圖片標註；`Track` 為影片或連續幀追蹤。因為是單張 jpg，所以選 **Polygon + Shape**。

---

### 13. 標註規則

目前的舌頭 segmentation 原則：

- 只標舌體
- 不含嘴唇、牙齒、下巴皮膚
- 上方黑色口腔陰影不算舌體
- 邊界模糊時，以可見舌頭外緣為準

---



## 推論（Inference）工作流程

### 概念說明

訓練完成後，`best.pth` 就是一個通用的舌頭偵測器。  
**不需要標註過的圖片也可以直接推論**，這些圖就是推論的目標。

```
[CVAT 標 150 張] → 訓練 → best.pth
                                 ↓
              [剩下所有圖片，例如 data/raw/] → inference.py → mask + tongue 圖
```

---

### 圖片放置位置

推論用圖片可以放在任意位置，建議使用現有的 `data/raw/`：

```
data/
├─ raw/          ← 幾千張未標註圖片，推論目標放這裡
├─ cvat/         ← 訓練用（有標註）
└─ infer/        ← 可選：另建資料夾放純推論圖
```

---

### 單張推論

```powershell
.venv311\Scripts\python.exe src\seg\inference.py `
    --image data\raw\10000_A_358.jpg `
    --model models\seg\best.pth
```

輸出自動存到 `outputs/`：

```
outputs/
├─ 10000_A_358_mask.png     ← binary mask（白=舌頭，黑=背景）
└─ 10000_A_358_tongue.png   ← 切出舌頭的 RGB 圖（背景歸黑）
```

---

### 批次推論（整個資料夾）

```powershell
Get-ChildItem data\raw -Filter *.jpg | ForEach-Object {
    .venv311\Scripts\python.exe src\seg\inference.py `
        --image $_.FullName `
        --model models\seg\best.pth
}
```

---

### 推論參數說明

| 參數 | 預設值 | 說明 |
|---|---|---|
| `--image` | （必填）| 輸入影像路徑 |
| `--model` | `models/seg/best.pth` | checkpoint 路徑 |
| `--img-size` | `256` | 需與訓練時一致 |
| `--threshold` | `0.5` | sigmoid 閾值，調高 → mask 更保守 |
| `--out-dir` | `outputs` | 輸出目錄 |

---

### 何時開始推論

| 條件 | 建議行動 |
|---|---|
| val Dice < 0.5 | 繼續補標，模型還不夠準 |
| val Dice 0.5–0.7 | 可試推論，但 mask 邊緣會不精確 |
| val Dice > 0.7 | 推論結果可用，開始批次處理 |
