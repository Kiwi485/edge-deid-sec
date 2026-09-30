# Docker / Compose 部署指引（W3 三服務）

## 先決條件

- 已安裝 Docker Desktop（或相容 Docker 環境）
- 已在專案根目錄 `edge-deid-sec/`
- `models/seg/best.pth` 必須存在（pipeline 已移除 HSV fallback）

## W6：TFLite 分割模型（可選）

預設仍使用 PyTorch 的 `models/seg/best.pth`。在有 PyTorch、segmentation-models-pytorch 的開發環境安裝 `litert-torch`，再將 checkpoint 匯出成 float32 TFLite 模型：

```bash
python -m pip install litert-torch
python tools/export_seg_tflite.py --checkpoint models/seg/best.pth --output models/seg/model.tflite
```

推論環境需另安裝 LiteRT runtime。Python 3.11 的 Linux x86_64／aarch64 可使用 `ai-edge-litert==1.4.0`；轉檔工具不需安裝在 Pi 上。本機指定 TFLite backend：

```bash
python -m pip install ai-edge-litert==1.4.0
python src/pipeline_local.py --seg-backend tflite --limit 5
```

Compose 的 extraction 容器可選擇安裝 runtime 並載入掛載在 `models/seg/` 下的模型：

```bash
INSTALL_TFLITE=1 SEG_BACKEND=tflite docker compose up --build
```

先以原本的 PyTorch pipeline 產生 `data/out/<id>/roi.png`，再比較同一批 ROI 的兩個 backend：

```bash
python tools/compare_seg_backends.py --roi-dir data/out --limit 20
```

報告中的 Dice／IoU 是**兩個 backend 遮罩的一致性**，不是對人工標註的分割準確率。模型在 x86 Python 3.11 的 LiteRT 1.4.0 已通過載入與執行；Raspberry Pi 上的 ARM64 套件安裝、真實資料精度、記憶體與延遲仍須實測。切換 backend 前請保存原始 benchmark：本機 pipeline 預設重建 CSV，Compose 的 extraction 還會清除舊輸出。產生的 `model.tflite` 留在本機且不納入 Git，部署到另一台機器時須重新匯出或安全地複製。TFLite 不保證達到單幀 80 ms。

### 用同一批照片驗證 Docker 推論

在專案根目錄執行以下 Bash 指令。先放入至少 5 張 JPG／PNG 照片至 `data/raw/`，確認 `models/seg/best.pth` 和 `models/seg/model.tflite` 都存在；兩輪皆用 `BATCH_LIMIT=5` 處理排序後的前 5 張。`last.pth` 不參與這次比較。

1. 先用預設的 `best.pth` 跑完整流程：

	```bash
	BATCH_LIMIT=5 docker compose up --build
	```

	檢查 `data/out/<image_id>/meta.json` 的 `status` 是否為 `ok`，`seg_backend` 是否為 `torch`；每張應有 `roi.png`、`mask.png`、`feature_256.npy`、`deid.png`。查看 `evidence/batch/validation_summary.csv`、`evidence/batch/privacy_summary.md` 和 `logs/pipeline_latency_vm.csv`。

2. 在切換 backend **之前**，保留 PyTorch 延遲紀錄，並利用它產生的 ROI 比較兩個模型：

	```bash
	cp logs/pipeline_latency_vm.csv logs/latency_torch_reference.csv
	INSTALL_TFLITE=1 docker compose build extraction
	INSTALL_TFLITE=1 docker compose run --rm --no-deps extraction python tools/compare_seg_backends.py --roi-dir data/out --limit 20
	```

	輸出的 `mask_dice_mean`、`mask_iou_mean` 越接近 1，兩個模型的分割越一致；`torch_forward_ms` 和 `tflite_forward_ms` 只比較模型推論，不是整條 pipeline 的時間。這一步不需要先跑第二次 Compose，因此不會清掉 PyTorch 的 ROI。

3. 再改用 `model.tflite` 跑同一批原始照片：

	```bash
	BATCH_LIMIT=5 INSTALL_TFLITE=1 SEG_BACKEND=tflite docker compose up --build
	```

	檢查新的 `data/out/<image_id>/meta.json`：`seg_backend` 應為 `tflite`，`status` 應為 `ok`；並查看新的驗證、隱私報表及 `logs/pipeline_latency_vm.csv`。要比較整條 pipeline 的時間，請用兩輪 CSV 的 `total_ms` 和 `seg_forward_ms`；第二輪會覆蓋第一輪的輸出與原本的 CSV，所以先保留紀錄。若測試失敗，先看該影像 `meta.json` 的 `error` 和容器輸出。

這個比較只驗證轉換前後是否一致。真正的分割準確率仍需有人工標註的舌頭 mask，Raspberry Pi 效能也必須在 Pi 上另行量測。

## 服務角色

- `acquisition`：掃描 `data/raw`，產生批次清單 `evidence/batch/acquisition_manifest.json`
- `extraction`：執行主 pipeline，產生 `data/out` 與 `logs/pipeline_latency_vm.csv`
- `observability`：更新 `docs/roi_eval.md`、`privacy_summary`、`validation_summary`

## 建立映像檔（build）

```bash
docker build -t edge-deid-sec .
```

## 啟動完整流程

```bash
docker compose up --build
```

流程順序：

1. acquisition
2. extraction（依賴 acquisition 成功）
3. observability（依賴 extraction 成功）

## 檢查輸出

- 批次清單：`evidence/batch/acquisition_manifest.json`
- pipeline latency：`logs/pipeline_latency_vm.csv`
- 隱私摘要：`evidence/batch/privacy_summary.md`
- 驗證摘要：`evidence/batch/validation_summary.csv`

## 停止與清除

```bash
docker compose down
```

## 自訂批次數量

預設 acquisition 會送出 100 張工作，extraction 也等待 100 張。若輸入照片少於 100 張，請明確設定兩邊共用的 `BATCH_LIMIT`，其值不可超過可用照片數，否則 extraction 會持續等待：

```bash
BATCH_LIMIT=5 docker compose up --build
```