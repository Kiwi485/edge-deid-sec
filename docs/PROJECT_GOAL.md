# Year-1 專題目標（B 版本）

## 一句話目標
在雲邊協同架構下，建立「舌診影像脫敏與安全基礎」：以 Docker Compose 微服務為基礎，開發 MediaPipe ROI 定位 + 輕量 U-Net（MobileNetV2）舌體分割，輸出舌頭分割遮罩與 256 維特徵向量，並整合 SELinux 隔離與 OpenTelemetry 監控，確保單幀處理延遲穩定 <80ms。:contentReference[oaicite:0]{index=0}

## 目標平台
- x86：Intel NUC
- ARM：Raspberry Pi（最終需在 Pi 上跑 edge benchmark）

## 核心輸入/輸出（B 版本）
- Input：舌頭照片（先用檔案資料集，後續再接相機）
- Output：
  - roi.png（ROI 影像）
  - mask.png（舌體分割遮罩）
  - deid.png（去識別化影像：只保留 ROI 或 mask）
  - feature_256.npy（256 維特徵向量）
  - meta.json（方法、時間、狀態、錯誤）
  - logs/pipeline_latency_vm.csv（批次統計）

## 計畫書技術路線（我們要對齊的點）
- MediaPipe：Face Mesh 取關鍵點並提取口腔 ROI；使用自適應補白因子 δ，並標準化為 256×256。:contentReference[oaicite:1]{index=1}
- 分割模型：MobileNetV2 作為輕量 U-Net 編碼器，參數量壓縮到 8.2M。:contentReference[oaicite:2]{index=2}
- 輸出：舌頭分割遮罩 + 256 維特徵向量。:contentReference[oaicite:3]{index=3}
- 安全與可觀測：SELinux MAC + OpenTelemetry；CIS Docker Benchmark 合規 >90%（vs 預設約 40%）。:contentReference[oaicite:4]{index=4} :contentReference[oaicite:5]{index=5}
- 量測交付：1000 次循環測試的 95% CI 延遲數據，證明穩定度低於 80ms。:contentReference[oaicite:6]{index=6}