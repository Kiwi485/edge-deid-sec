# Docker / Compose 部署指引（W3 三服務）

## 先決條件

- 已安裝 Docker Desktop（或相容 Docker 環境）
- 已在專案根目錄 `edge-deid-sec/`
- `models/seg/best.pth` 必須存在（pipeline 已移除 HSV fallback）

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

預設 acquisition 會跑 50 張。可在 `docker-compose.yml` 調整：

- `acquisition` command 的 `--limit 50`

例如改成 100：

- `--limit "100"`