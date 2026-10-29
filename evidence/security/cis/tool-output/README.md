# Trivy 輸出

- `trivy-vulns.csv`：三個最終映像的弱點清單，每個弱點一列（套件、版本、CVE、嚴重度、修正版本）。`images=all` 代表三個映像都有；本輪三個映像結果完全相同。
- `trivy-<服務>.log`：每次掃描的執行紀錄；`trivy-version.txt`：Trivy 與弱點資料庫版本。
- 嚴重度統計與判定：`../checks/final/4.4.txt` 最後的 manual addendum。

完整 JSON 原始輸出（每個映像約 3 萬行）因為太大，不放進 Git，以受控方式保存在稽核 VM 的 `~/cis-benchmark/trivy-raw/`（2026-10-29 以基底 `673719e…` 重建後的掃描；前一版 `ae952e…` 映像的掃描保存在 `~/cis-benchmark/trivy-raw-ae952e/`）：

| 檔案 | SHA-256 |
|---|---|
| `trivy-acquisition.json` | `16689a88c3d1aa125e9f75591dd7beb3d211ceb19c5a00b16adc9e3f3fd1978b` |
| `trivy-extraction.json` | `12ce4bc6c4effc1b2255e346395990fd4835c2663a0a5788ec69d6ed3202756f` |
| `trivy-observability.json` | `43179ca8361d24855685dfcb4f5a7c202f559442f4a3603ae6e01bc223e14941` |

產生指令：`trivy image --image-src docker --scanners vuln --timeout 90m --format json --output trivy-<服務>.json edge-deid-sec-<服務>:latest`
