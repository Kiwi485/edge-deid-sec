
---


# 10 週 Roadmap（從 2026/03/09 起算）

## Milestones
- W1（03/09–03/15）：I/O 固定化
- W2（03/16–03/22）：ROI（MediaPipe + fallback）+ DeID 並行
- W3（03/23–03/29）：整合 pipeline_local + 批次跑真圖（>=50）
- W4（03/30–04/05）：VM benchmark v0（>=100 張）+ 初版報告
- W5（04/06–04/12）：API /process
- W6（04/13–04/19）：Docker
- W7（04/20–04/26）：Docker Compose
- W8（04/27–05/03）：OpenTelemetry 最小可用（roi/seg/feat/total）
- W9（05/04–05/10）：VM 1000 runs（p50/p95/p99 + 95% CI）
- W10（05/11–05/17）：SELinux 禁網證據 + CIS checklist + security v0

## 與計畫書對齊的「最終交付」
- Docker Compose 微服務基礎建置 + 舌體分割提取 256 維特徵 + OTel 監控 + SELinux 隔離，單幀 <80ms。:contentReference[oaicite:7]{index=7}
- CIS Docker Benchmark 合規 >90%，並產出 1000 次循環測試 95% CI 延遲證據。:contentReference[oaicite:8]{index=8} :contentReference[oaicite:9]{index=9}