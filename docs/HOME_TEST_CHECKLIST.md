# 回家測試清單：W6、W7、W8

這份清單使用 **Windows PowerShell + Docker Desktop（Linux containers）**。所有指令都在專案根目錄、同一個 PowerShell 視窗依序執行。Python 在 Docker 內執行，不需要先建立 Windows 虛擬環境。

## 今天要確認什麼

| 項目 | 要確認的事情 | 不是這次要證明的事情 |
| --- | --- | --- |
| W6 | 同一批照片能用 PyTorch 和 TFLite 分割，並比較遮罩與耗時 | Pi 已達到單幀 80 ms |
| W7 | pipeline 自動產生包含 GLCM 的新版 256 維特徵 | 已完成分類，或分類效果變好 |
| W8 | 開啟監控後能看到每張照片的各階段 spans | 已有監控網頁或完整跨服務追蹤 |

順序是：**準備環境 → 不用照片的測試 → PyTorch 基準 → TFLite → 檢查 W7 → 開啟 W8**。三輪都用同一批 5 張照片，期間不要新增、刪除或更換照片。

> 目前程式測試在 Codespace 的 Python 3.11 容器已有 30 個通過。下面要補的是你家裡環境的驗證，以及真實照片的結果。不要先把 W6、W7、W8 寫成「全部驗收完成」。

## 0. 開始前準備

- [ ] 確認 W6、W7、W8 的 PR **已合併**到遠端 `main`，不只是已建立 PR。尚未提交或推送的 Codespace 修改不會出現在家裡。
- [ ] 開啟 Docker Desktop，使用 Linux containers。
- [ ] 在 VS Code 開啟專案，終端機選 PowerShell，工作目錄是 `edge-deid-sec`。
- [ ] 有足夠的網路與磁碟空間下載 Docker 映像和 Python／模型套件；第一次 build 可能較久。
- [ ] 不要刪除原始照片、ROI 標註或模型來「重新測試」。

先在家裡的專案確認工作樹乾淨，才更新 `main`。若 `git status --short` 有輸出，先確認並保存那些修改，不要直接切換分支或強制覆蓋：

```powershell
git status --short
git switch main
git pull --ff-only origin main
git branch --show-current
```

若 PR 只是開啟、尚未合併，這些指令不會取得該 PR 的程式碼；請等合併後再執行本清單。接著檢查環境與 W8 檔案：

```powershell
docker --version
docker compose version
docker info
Test-Path .\src\telemetry.py
Test-Path .\test\test_pipeline_telemetry.py
```

**可以繼續的條件：** 位於最新 `main`、Docker 引擎可連線，兩個 `Test-Path` 都是 `True`。若檔案不存在，先確認 PR 是否真的合併並檢查 `git pull` 是否成功；若 `docker info` 失敗，先處理 Docker Desktop，不要直接跳到照片測試。

## 1. 先備份，不要讓測試覆蓋舊資料

現有 Compose 會清除 `data/out/`，並重建預設 latency CSV。以下建立唯一的備份目錄，放在 Git 已忽略的 `outputs/`，不會被 Compose 的 `--clear-out` 清掉。

```powershell
$EvidenceRoot = Join-Path (Get-Location).Path ("outputs/home_w6_w8_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
New-Item -ItemType Directory -Path $EvidenceRoot | Out-Null
$Before = Join-Path $EvidenceRoot "before_tests"
New-Item -ItemType Directory -Path $Before | Out-Null
if (Test-Path .\data\out) { Copy-Item .\data\out "$Before/out" -Recurse }
if (Test-Path .\logs\pipeline_latency_vm.csv) { Copy-Item .\logs\pipeline_latency_vm.csv "$Before/latency.csv" }
if (Test-Path .\evidence\batch) { Copy-Item .\evidence\batch "$Before/evidence" -Recurse }
Write-Host "本次結果保存位置：$EvidenceRoot"
```

**後面的步驟繼續使用同一個 PowerShell 視窗。** 若關掉終端機，需把 `$EvidenceRoot` 設回上面顯示的路徑。不要把這些照片、metadata、特徵或完整 logs 提交到 Git。

## 2. 建立測試環境，先跑不需要照片的測試

```powershell
$env:INSTALL_TFLITE = "1"
$env:SEG_BACKEND = "torch"
$env:EDGE_DEID_TRACING = "off"
$env:BATCH_LIMIT = "5"
docker compose build extraction
```

**build 成功後**才執行：

```powershell
docker compose run --rm --no-deps extraction python --version
docker compose run --rm --no-deps --volume "${PWD}/test:/app/test:ro" extraction python -m pytest -q -p no:cacheprovider test/test_tflite_inference.py test/test_feature_extractor.py test/test_pipeline_telemetry.py test/test_unix_socket_ipc.py
```

映像檔本身不包含 `test/`，所以測試指令用 `--volume` 將本機測試資料夾唯讀掛載進容器；請保留這個參數。`${PWD}` 是目前專案根目錄。

**通過標準：** Python 顯示 `3.11.x`，目前這組測試應顯示 `30 passed`。若程式後續增加測試，數量可以增加，但不能有 failed／error。

這一步不需要照片，也不需要真正的 TFLite 模型檔；模型部分使用模擬輸出。若測試失敗，先停在這裡，記下第一個錯誤，不要把後面照片測試當作替代。

## 3. 準備真實照片與模型

- [ ] 至少 5 張有權使用的 JPG／JPEG／PNG 照片放在 `data/raw/`。
- [ ] 測試圖片使用不同的主檔名；例如不要同時放 `sample.jpg` 與 `sample.png`，兩者會共用輸出資料夾。
- [ ] `models/seg/best.pth` 存在。
- [ ] `models/seg/model.tflite` 存在，且確定由這次使用的同一份 `best.pth` 匯出。
- [ ] 專案的 MediaPipe／YOLO 模型資產已按原本部署方式準備。

```powershell
Get-ChildItem .\data\raw -File | Where-Object { $_.Extension.ToLower() -in @(".jpg", ".jpeg", ".png") } | Sort-Object Name | Select-Object -First 5 Name
Test-Path .\models\seg\best.pth
Test-Path .\models\seg\model.tflite
```

**注意：`model.tflite` 不會隨 Git 帶回家。** 若不存在，先從已驗證的環境安全複製對應模型，或依 [W6 模型匯出說明](DEPLOY.md#w6tflite-分割模型可選)在相容的 Linux 開發環境重新匯出。不要只把 `.pth` 改副檔名成 `.tflite`，也不要假設 Windows 本機能安裝 Linux runtime。

若資料夾還有 HEIC，pipeline 也可能選到它們；首次測試建議使用另外準備的純 JPG／PNG 測試資料集。不要刪除原本的病患資料。

`BATCH_LIMIT=5` 代表 acquisition 最多送 5 個工作，extraction 等待 5 個工作。照片不足會造成等待；同一批照片在三輪之間不要變動。

## 4. 第一輪：PyTorch 基準，監控關閉

```powershell
$env:SEG_BACKEND = "torch"
$env:EDGE_DEID_TRACING = "off"
docker compose down
docker compose up --build --force-recreate
```

等三個服務完成並回到提示字元。**沒有回到提示字元，不一定是當機**；先查看是否照片不足、模型下載、錯誤或某個容器仍在等工作。

```powershell
docker compose ps -a
```

預期服務正常完成。接著查看每張 metadata：

```powershell
Get-ChildItem .\data\out -Filter meta.json -Recurse | ForEach-Object {
    $Meta = Get-Content $_.FullName -Raw | ConvertFrom-Json
    [PSCustomObject]@{
        Image = $_.Directory.Name
        Status = $Meta.status
        Backend = $Meta.seg_backend
        FeatureVersion = $Meta.feature_version
        PrivacyPass = $Meta.privacy_metrics.privacy_pass
    }
} | Format-Table -AutoSize
```

**通過標準：** 有 5 張結果，每張 `Status=ok`、`Backend=torch`、`FeatureVersion=v2_glcm`、`PrivacyPass=True`。若品質未通過，會看到 `quality_fail`，需要查看原因，不可直接記為通過。

另外在本機開啟每張的 `roi.png`、`mask.png`、`deid.png`：ROI 應包含舌頭，mask 應合理涵蓋舌頭，DeID 圖不應保留臉部或背景。自動隱私檢查無法取代人工確認 mask 是否真的只包含舌頭。

查看 `evidence/batch/validation_summary.csv` 與 `privacy_summary.md`，確認沒有未處理的失敗。照片有成功輸出，不等於三服務與驗證全部成功。

**切換模型之前，保存這一輪：**

```powershell
$RunDir = Join-Path $EvidenceRoot "torch_off"
New-Item -ItemType Directory -Path $RunDir | Out-Null
Copy-Item .\data\out "$RunDir/out" -Recurse
Copy-Item .\logs\pipeline_latency_vm.csv "$RunDir/latency.csv"
Copy-Item .\evidence\batch "$RunDir/evidence" -Recurse
docker compose logs --no-color | Out-File "$RunDir/compose.log" -Encoding utf8
```

## 5. W6：用相同 ROI 比較 PyTorch 與 TFLite

此時 `data/out/` 還是上一輪 PyTorch 產生的 ROI。先比較，不要先清掉它們：

```powershell
docker compose run --rm --no-deps extraction python tools/compare_seg_backends.py --roi-dir data/out --limit 5
```

記下終端機中的結果：

```text
images=
mask_dice_mean=
mask_iou_mean=
torch_forward_ms p50=        p95=
tflite_forward_ms p50=       p95=
```

這不是固定的預期數字，請填實測值並保存在 `$EvidenceRoot` 內。

- `images` 應為 5。
- Dice／IoU 越接近 1，兩個後端的 mask 越一致，但**不是對人工標註的準確率**。
- 兩個模型都輸出空 mask 時，也可能得到一致性 1；所以一定要搭配影像、mask 與隱私檢查。
- 若兩個後端差異明顯，先檢查模型是否對應、前處理與輸出，不要只因程式沒有報錯就視為轉換驗證通過。專案目前沒有訂定正式的一致性驗收門檻。
- 這裡量的是模型 forward，不是整條 pipeline；5 張只適合初步比較，包含冷啟動等變異，不足以宣稱效能達標。

## 6. 第二輪：TFLite，監控關閉

確認第一輪已保存，再執行：

```powershell
$env:SEG_BACKEND = "tflite"
$env:EDGE_DEID_TRACING = "off"
docker compose down
docker compose up --force-recreate
docker compose ps -a
```

重跑第 4 步的 metadata 表格指令。這次的通過條件為 5 張 `Status=ok`、`Backend=tflite`、`FeatureVersion=v2_glcm`、`PrivacyPass=True`。同樣查看 mask、DeID 與驗證報告。

保存這一輪：

```powershell
$RunDir = Join-Path $EvidenceRoot "tflite_off"
New-Item -ItemType Directory -Path $RunDir | Out-Null
Copy-Item .\data\out "$RunDir/out" -Recurse
Copy-Item .\logs\pipeline_latency_vm.csv "$RunDir/latency.csv"
Copy-Item .\evidence\batch "$RunDir/evidence" -Recurse
docker compose logs --no-color | Out-File "$RunDir/compose.log" -Encoding utf8
```

對照 `torch_off/latency.csv` 與 `tflite_off/latency.csv` 的 `seg_forward_ms`、`total_ms`。TFLite 不保證一定比較快；請保留實際結果。

## 7. W7：確認新版 256 維特徵

**不需要再跑另一個 GLCM 程式。** 前兩輪 pipeline 已經包含 W7，現在檢查第二輪的輸出：

```powershell
docker compose run --rm --no-deps extraction python -c "from pathlib import Path; import numpy as np; files=sorted(Path('data/out').glob('*/feature_256.npy')); assert len(files)==5, 'Expected 5 feature files'; arrays=[np.load(path, allow_pickle=False) for path in files]; assert all(features.shape==(256,) and features.dtype==np.float32 and np.isfinite(features).all() for features in arrays), 'Invalid feature shape, dtype or values'; assert all(((features[240:256]>=0) & (features[240:256]<=1)).all() for features in arrays), 'GLCM out of range'; print('PASS: 5 finite float32 vectors, each 256 dimensions; GLCM range OK')"
```

**通過標準：** 指令輸出 `PASS`，且 metadata 的 `feature_version` 是 `v2_glcm`。最後 16 維，即索引 240-255，才是新增 GLCM；前面還有 HSV、RGB、形狀、LBP。

數值範圍合法不代表分類有效，也不能取代前面的 mask 檢查。舊版 256 維資料不可與新版混用；需要從原圖與 mask 重新產生。詳細配置見 [Feature 256 規格](feature_256_spec.md)。

## 8. 第三輪：TFLite + W8 監控

確認第二輪已保存。只改監控開關，模型與照片不變：

```powershell
$env:SEG_BACKEND = "tflite"
$env:EDGE_DEID_TRACING = "console"
docker compose down
docker compose up --force-recreate
docker compose ps -a
```

查看監控紀錄：

```powershell
docker compose logs --no-color --no-log-prefix extraction
```

想先找各階段名稱，可以執行：

```powershell
docker compose logs --no-color --no-log-prefix extraction | Select-String -Pattern '"name": "(total|roi|seg|feat|deid|privacy)"'
```

**通過標準：**

- [ ] 5 張均處理成功且品質、隱私檢查通過。
- [ ] 每張有 `total`、`roi`、`seg`、`feat`、`deid`、`privacy`，正常成功的 5 張合計 30 個 spans。
- [ ] 同一筆處理的六個 spans 有相同 `context.trace_id`；不同影像使用不同 trace ID。
- [ ] 子 span 的 `parent_id` 指向 `total` 的 `context.span_id`。
- [ ] 正常成功時 `status.status_code` 為 `OK`；`ERROR` 要查原因，不可只確認「有 JSON」就打勾。
- [ ] span 的 `attributes` 不包含照片內容、特徵向量、病患檔名或完整路徑。
- [ ] metadata 仍是 `Backend=tflite`、`FeatureVersion=v2_glcm`，並重跑第 7 步特徵檢查。

`start_time` 與 `end_time` 的差是該 span 的耗時。這一版只輸出 JSON，**不會自動開啟監控網頁**。完整欄位說明見 [W8 監控文件](OPENTELEMETRY.md)。

保存這一輪：

```powershell
$RunDir = Join-Path $EvidenceRoot "tflite_console"
New-Item -ItemType Directory -Path $RunDir | Out-Null
Copy-Item .\data\out "$RunDir/out" -Recurse
Copy-Item .\logs\pipeline_latency_vm.csv "$RunDir/latency.csv"
Copy-Item .\evidence\batch "$RunDir/evidence" -Recurse
docker compose logs --no-color | Out-File "$RunDir/compose.log" -Encoding utf8
docker compose logs --no-color --no-log-prefix extraction | Out-File "$RunDir/extraction.log" -Encoding utf8
```

對照 `tflite_off/latency.csv` 與 `tflite_console/latency.csv`，初步觀察監控額外成本。console exporter 同步輸出會增加耗時；不要將開啟與關閉監控的樣本混在一起做效能結論。

**整份 log 不是單一 JSON，也不是完全去識別化資料。** 新增 spans 會避開敏感資訊，但原有 extraction／pipeline 訊息仍可能有檔名或路徑，分享前須審查。

## 9. 結束與回報

確認三輪結果都已保存在 `$EvidenceRoot` 後：

```powershell
$env:EDGE_DEID_TRACING = "off"
$env:SEG_BACKEND = "torch"
docker compose down
Write-Host "結果保存位置：$EvidenceRoot"
```

`docker compose down` 移除本次服務容器，不刪除掛載的原始照片或前面備份。之後新開 PowerShell，環境變數不一定保留；再次測試時需重新設定。

可用以下格式把不含病患資料的摘要補到 PR：

```text
測試日期：
Git commit：
電腦 CPU / RAM：
Docker Desktop 分配的 CPU / RAM：
Python（容器內）：3.11.x
照片數：5（同一批，未公開照片）

自動測試：__ passed / __ failed
W6 PyTorch：__ / 5 成功，privacy pass __ / 5
W6 TFLite：__ / 5 成功，privacy pass __ / 5
模型一致性：Dice __，IoU __；人工查看 mask 結果：__
W7：__ / 5 為 v2_glcm，256 維 float32／有限值／GLCM 範圍檢查 __
W8：__ 筆 traces，__ 個 spans；階層與狀態檢查 __
效能初步觀察（非正式 benchmark）：__
遇到的錯誤與處理：__

尚未驗證：Pi 效能、1,000 次統計、正式分割準確率、分類效益。
```

這份摘要只能寫你實際觀察到的結果。不要提交完整照片、mask、特徵向量、metadata、原始 logs 或敏感的本機路徑。

## 卡住時先看這裡

| 現象 | 先做什麼 |
| --- | --- |
| `docker info` 連不上 | 確認 Docker Desktop 已啟動，且使用 Linux containers |
| build／套件安裝失敗 | 保留第一個錯誤，先確認網路、磁碟與套件相容性；不要繼續跑後面的測試 |
| 找不到 TFLite 模型 | 重新檢查 `model.tflite` 是否在家裡，及是否由同一份 `best.pth` 匯出 |
| extraction 一直等待 | 確認 acquisition 有成功送出 5 個工作，照片至少有 5 張；查看 `docker compose logs acquisition extraction` |
| `quality_fail` | 查看 metadata 的品質原因，確認照片是否模糊、過暗或不符合輸入條件 |
| `privacy_pass=False` | 查看 mask、DeID 與 privacy issues，不能只看 `status=ok` |
| 沒有 GLCM | 確認程式是 W7 版本、metadata 是 `v2_glcm`，並查看最後 16 維；它不是一張圖片 |
| 看不到 spans | 確認第三輪設定 `EDGE_DEID_TRACING=console` 並用 `--force-recreate` 重新建立容器，查看 extraction logs，不是 observability logs |
| 不小心切換下一輪 | 從 `$EvidenceRoot` 找已保存的結果；不要假設 `data/out/` 還保留上一輪 |