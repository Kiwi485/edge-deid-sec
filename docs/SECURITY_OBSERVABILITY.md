# 安全與可觀測（Year-1 交付）

## 安全目標（計畫書對齊）
- SELinux 強制存取控制：對容器實施 OS 層級禁網（neverallow ... tcp_socket connect）。:contentReference[oaicite:10]{index=10}
- 目標：CIS Docker Benchmark 合規度 >90%（vs 預設約 40%）。:contentReference[oaicite:11]{index=11}
- 異常回應鏈（概念交付）：偵測非授權系統調用時，可 docker pause 凍結，docker commit 封存現場。:contentReference[oaicite:12]{index=12}

## 我們 Year-1 最小可交付安全證據（必做）
- 容器禁網證明：
  - 在容器內 `curl https://example.com` 失敗（截圖/輸出）
  - 在主機上同指令成功（對照）
- 最小權限：
  - container 非 root（或以文件方式列出設定）
- 資料不離地（DeID policy）：
  - 原圖不落地或有明確 retention（寫入 docs）

## 可觀測性（OpenTelemetry）目標（必做）
- 至少四段 span：
  - roi / seg / feat / total
- 交付：1,000 次循環測試 95% CI 延遲數據，證明穩定 <80ms。:contentReference[oaicite:13]{index=13}

## 模型/資源限制（計畫書對齊，可選加分）
- MediaPipe 容器 1.5 核心、U-Net 容器 2.0 核心，維持記憶體 <75% 避免效能劣化。:contentReference[oaicite:14]{index=14}