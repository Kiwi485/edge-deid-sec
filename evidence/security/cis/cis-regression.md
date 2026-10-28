# CIS 修正後回歸（W10-2）

CIS 修正改到了 daemon（icc、no-new-privileges、ulimit、live-restore、userland-proxy）、主機稽核、Docker 資料分割區、映像（HEALTHCHECK、移除 setuid、基底更新）與 Compose（cpu_shares、healthcheck、restart）。這些都可能影響 SELinux 與功能，所以在**最終映像與最終設定**上完整重跑 W10-1 的回歸。

- 執行腳本：`scripts/run_final_round.sh`（pytest → `compose up --no-build --force-recreate` → `tools/check_week10_security.py --require-selinux` → 收集 AVC → CIS 最終檢查）
- 映像：見 `cis-environment.md`「映像」（三個 Image ID 與 `checks/final/6.1.txt` 相同）
- 設定：`final-config/`，與 `checks/final/` 同一輪、同一組設定

## 時間（2026-10-28，UTC+8）

| 階段 | 時間 |
|---|---|
| 一般流程（compose up，5 張照片） | 01:35:16–01:35:29 |
| SELinux 安全探測 | 01:35:29–01:35:32 |
| CIS 最終檢查（同一份映像／設定） | 01:35:41–01:36:18 |

## 結果

| 項目 | 結果 | 證據 |
|---|---|---|
| 程式與 Compose 設定測試 | 21 passed、0 failed（`test_week10_security.py`、`test_unix_socket_ipc.py`）；`compose config` 通過 | `regression/pytest.txt` |
| 三服務 | acquisition、extraction、observability 全部 Exited (0) | `regression/container-status.txt`、`regression/compose.log` |
| 五張圖片處理 | 5／5 `status=ok`、`seg_backend=tflite`；manifest total=5 | `regression/meta/*.meta.json`、`regression/batch/acquisition_manifest.json`、`regression/batch/pipeline_latency_vm.csv` |
| 輸出驗證 | 5／5 `final_result=pass` | `regression/batch/validation_summary.csv` |
| 隱私 | 5／5 通過，通過率 100%，背景洩漏 0 | `regression/batch/privacy_summary.md`、`privacy_report.csv` |
| Unix socket IPC | 5 jobs，p95 2.445 ms（目標 ≤ 5 ms） | `regression/batch/ipc_summary.md`、`ipc_report.csv` |
| SELinux 設定與 runtime | `selinux_verified=true`、`checks_passed=true`；Enforcing；extraction 以 `edge_deid_extraction_t` 執行、uid 10001；configuration／runtime 檢查全為 true | `regression/week10-selinux.json` |
| SELinux 拒絕探測 | IPv4、IPv6 TCP socket 被拒；掛載的原圖目錄（`edge_deid_raw_t`）讀取被拒 | `regression/week10-selinux.json`、`regression/selinux-avc.log` |
| AVC | 一般流程期間 **0 筆**；探測期間 4 筆，全部是預期的拒絕（3 筆 `tcp_socket create`、1 筆 `edge_deid_raw_t dir read`） | `regression/selinux-avc.log`（以 audit epoch 視窗過濾） |

`week10_complete=false`、`cis_full_audit=not_run` 是 checker 的固定欄位（checker 本身不做 CIS 稽核、也不含效能驗收），不代表失敗。

## 與 W10-1 的比較

結果與 W10-1 最終驗收輪一致（21 passed、5／5、隱私 100%、相同的 4 類預期拒絕、一般流程無 AVC）。CIS 修正沒有破壞功能，也沒有新增任何 SELinux 允許規則；SELinux 政策 `edge_deid.te` 與 W10-1 commit 相同（SHA-256 見 `final-config/config-sha256.txt`）。

## 失敗路徑（5.15 restart on-failure:5）

第一次嘗試回歸時，`evidence/batch/` 權限被 `git restore` 改掉，acquisition／observability 結束碼 1，容器依 `on-failure:5` 重試後停止，沒有無限重啟。原因與 CIS 無關，修正權限後重跑通過（見 `cis-remediation.md` §H）。

## 隱私與敏感資料

- 照片、模型、去識別化輸出圖片都不在本目錄；`regression/` 只有文字結果、CSV 與 meta JSON。
- 證據中出現主機路徑 `/home/i1an/edge-deid-sec`、VM 主機名稱與容器 ID，沒有金鑰、憑證或密碼。
