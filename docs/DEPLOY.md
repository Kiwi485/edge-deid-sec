# Docker / Compose 部署指引

## 先決條件

- 已安裝 Docker Desktop（或相容的 Docker 環境）
- 已在專案根目錄 `edge-deid-sec/`

> 注意：目前容器內沒有直接掛實體攝影機，`mp_test.py` 僅作為 placeholder 測試腳本。

## 建立映像檔（build）

```bash
docker build -t edge-deid-sec-api .
```

- 成功後可以用 `docker images` 看到 `edge-deid-sec-api`。

## 使用 docker compose 啟動

```bash
docker compose up
```

- `api` service 會根據 Dockerfile build 映像並啟動。
- 預設對外 port：`8000`（對應容器內 `8000`）。
- `data/`、`logs/` 會以 volume 方式掛載到容器內 `/app/data`、`/app/logs`。

要停止服務時：

```bash
docker compose down
```

## 之後要調整的項目

- 將 Dockerfile / docker-compose.yml 的啟動指令（CMD / command）改成真正的 API 入口點。
- 視需求補上 `otel-collector` 的設定檔與與 `api` 的相依關係。
- 如需在容器內使用攝影機，需額外設定裝置映射（例如在 Linux 上使用 `--device=/dev/video0`），目前版本僅確認容器可啟動並執行 placeholder 程式。