# Trivy 輸出

- `trivy-vulns.csv`：三個最終映像的弱點清單，每個弱點一列（套件、版本、CVE、嚴重度、修正版本）。`images=all` 代表三個映像都有；本輪三個映像結果完全相同。
- `trivy-<服務>.log`：每次掃描的執行紀錄；`trivy-version.txt`：Trivy 與弱點資料庫版本。
- 嚴重度統計與判定：`../checks/final/4.4.txt` 最後的 manual addendum。

完整 JSON 原始輸出（每個映像約 3 萬行）因為太大，不放進 Git，以受控方式保存在稽核 VM 的 `~/cis-benchmark/trivy-raw/`：

| 檔案 | SHA-256 |
|---|---|
| `trivy-acquisition.json` | `6d33f48fb701ac15eacdc8741b6c7560b4daf7daa2257fe979ae9b3ae2efde7e` |
| `trivy-extraction.json` | `6846eebfd38ada12a16426271e5a4241ae3ca1bc297e728ba4b34abac8869203` |
| `trivy-observability.json` | `89ad4124d3e79325c9cf6073399a118ce8c39b4c884236e18640edbe525a006f` |

產生指令：`trivy image --image-src docker --scanners vuln --timeout 90m --format json --output trivy-<服務>.json edge-deid-sec-<服務>:latest`
