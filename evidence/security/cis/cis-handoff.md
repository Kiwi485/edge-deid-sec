## CIS Docker 稽核交接

- 稽核日期／時間範圍：2026-10-27 14:24（修正前基準檢查）至 2026-10-28 01:48（UTC+8）。最終回歸 01:35:16–01:35:32、最終 CIS 檢查 01:35:41–01:36:18、Trivy 01:40–01:47，全部使用同一組映像與設定。
- 目標 VM／OS：W10-1 同一台 VM。Oracle VirtualBox，4 vCPU、8 GB RAM（實體主機為 i5-1240P／16 GB 筆電）；Fedora Linux 44 Workstation，kernel 6.19.10-300.fc44，SELinux Enforcing。
- Benchmark 版本及 profile：CIS Docker Benchmark v1.9.0；Level 1 + Level 2 - Docker - Linux（Swarm profile 9 項列 N/A）。本報告為內部自我評估，不是 CIS 官方認證。
- Docker／Compose／輔助工具版本：Docker Engine 29.9.2（rootful，`-H fd://`，containerd image store）、Compose v5.6.1、containerd 2.4.2、runc 1.5.2；Trivy 0.76.1（只用於 4.4 弱點掃描）。沒有使用 Docker Bench for Security，全部控制項依 Benchmark 原文逐項判定。
- Git commit；是否有未提交修改：稽核時基於 `0383d43`，提交時改接在 main `5d36358`（W10-1 已合併；兩者程式與設定相同，只差一行文件）。分支 `w10-2-cis-audit`。稽核時 `Dockerfile`、`docker-compose.yml` 的 CIS 修正尚未提交，之後與本目錄一起提交。
- 最終配置與映像識別：`final-config/`（Compose 展開、daemon.json、稽核規則、docker.service drop-in、fstab、設定 SHA-256、SELinux 模組）。映像 ID：
  - acquisition `sha256:68e407d8…`
  - extraction `sha256:c2ce7947…`
  - observability `sha256:50d2d79c…`
  - 基底 `python:3.11-slim@sha256:ae952e0a…`
  - 完整值見 `final-config/images.txt`
- 控制項總數 117；適用 88；N/A 29。
- PASS 80；FAIL 8；NOT_CHECKED 0。
- 合規率：80 / 88 × 100% = 90.909%（未四捨五入 90.9090…%，嚴格 > 90%）。修正前為 54 / 88 = 61.36%。
- 未解決 FAIL（風險與處理決定詳見 `cis-summary.md`）：
  - **4.4（高）**：pillow 12.1.0 有 5 CRITICAL、36 HIGH 可修正弱點。建議優先升級 pillow 13，需負責人同意。
  - 4.3（中）：映像含 torch、CUDA、pytest 等非必要套件。
  - 4.10（中）：pip 套件沒有 hash 驗證。
  - 4.11（中低）：未驗證基底映像簽章。
  - 2.1（中）：dockerd 以 root 執行；rootless 與 W10-1 SELinux 政策不相容。
  - 2.13（低）：沒有授權外掛。
  - 2.14（低中）：沒有集中日誌。
  - 1.2.1（中）：主機未套用正式強化基準，建議另開 Issue。
  - 目前處理決定：本輪接受風險並列入後續計畫，待負責人確認。
- N/A 理由位置：`cis-controls.csv` 的 `exception_reason` 欄；彙整表在 `cis-summary.md`「N/A 理由」。
- 本次修正：26 項由 FAIL 轉 PASS，詳見 `cis-remediation.md`。
  - 主機 auditd 規則：14 條 `-k docker`，重開機後仍有效。
  - daemon.json：icc=false、no-new-privileges、default-ulimits、live-restore、userland-proxy=false。
  - `/var/lib/docker`、`/var/lib/containerd` 改到獨立硬碟。
  - Dockerfile：HEALTHCHECK、移除 setuid／setgid、以最新基底重建。
  - Compose：cpu_shares、healthcheck、restart on-failure:5。
  - 各項重測結果在 `checks/final/`。
- SELinux 回歸：通過，證據在 `cis-regression.md`、`regression/week10-selinux.json`、`regression/selinux-avc.log`。
  - `selinux_verified=true`、`checks_passed=true`。
  - IPv4／IPv6 TCP 與原圖目錄讀取都被拒。
  - 一般流程 0 筆 AVC。
  - SELinux 政策未修改。
- 五張圖片輸出及隱私回歸：通過，證據在 `regression/`。
  - 21 tests passed；三服務 Exited (0)。
  - 5／5 `status=ok`（tflite）、輸出驗證 5／5 pass。
  - 隱私 5／5、通過率 100%；IPC p95 2.445 ms。
- 完整控制項、原始證據與最終配置的受控位置：`evidence/security/cis/`。
  - `cis-controls.csv`、`checks/baseline/`、`checks/final/`、`tool-output/`、`final-config/`、`regression/`、`scripts/`
  - CIS Benchmark PDF 依授權只保存在稽核 VM，不上傳。
  - Trivy 完整 JSON（每個映像約 3 萬行）只保存在稽核 VM 的 `~/cis-benchmark/trivy-raw/`，Git 只放精簡弱點清單 `tool-output/trivy-vulns.csv` 與 SHA-256（`tool-output/README.md`）。
  - 不含照片、模型、金鑰或憑證。
- 結論：**完整稽核完成且通過**（U=0，合規率 90.909% > 90%）。但仍有 8 項 FAIL，其中 4.4 為高風險，已揭露並交負責人決定。
- 下一步與阻塞：
  1. 負責人決定是否先升級 pillow（4.4）。若升級，需重建映像，重跑回歸、Trivy 與第 4、5、6 節檢查，並更新本目錄。
  2. 合規率餘裕只有 1 項：再多 1 項 FAIL 就會降到 89.77%。
  3. 1,000 次效能驗收要在這組配置下執行：syscall 稽核已開啟、`/var/lib/docker` 有 `-p wa` 監看、cpu_shares 與 ulimit 已設定，都可能影響效能。
  4. 效能 Issue 若修改 daemon、Compose 或映像，受影響的控制項與 SELinux 回歸必須重測。
  5. VM 的第二顆虛擬硬碟（sdb，80 GB）必須隨 VM 一起保留。
