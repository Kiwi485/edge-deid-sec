# CIS Docker 稽核環境（W10-2）

## 標準與範圍

- Benchmark：CIS Docker Benchmark **v1.9.0**（CIS 官網依授權下載；PDF 只保存在稽核 VM 的 `~/cis-benchmark/`，依授權不上傳、不複製原文）
- Profile：**Level 1 - Docker - Linux** 與 **Level 2 - Docker - Linux**
  - 第 7 節（Docker Swarm Configuration）9 項屬於 Swarm profile，Swarm 未啟用，列為 N/A（理由見 `cis-controls.csv`）
  - 控制項總數 117（第 1–7 節全部列出，沒有刪減）
- 本稽核為團隊內部自我評估，**不是 CIS 官方認證**

## 稽核時間（UTC+8）

- 修正前基準檢查：2026-10-27（`checks/baseline/`，每檔第 2 行有收集時間）
- 修正、重建映像：2026-10-27 至 2026-10-29（10-29 依 PR 程式碼審查修正 acquisition 重啟設定，並因基底更新重建；見 `cis-remediation.md` §I）
- 最終回歸：2026-10-29 17:39:01–17:39:17（`regression/round-window.txt`）
- 最終 CIS 檢查：2026-10-29 17:39:26–17:40:04（`checks/final/`）
- Trivy 掃描：2026-10-29 17:40–17:47（`tool-output/trivy-version.txt` 與各 log；弱點資料庫 2026-10-29 更新版）

## 目標主機（與 W10-1 SELinux 驗證同一台 VM）

| 項目 | 值 |
|---|---|
| 虛擬化 | Oracle VirtualBox，4 vCPU、8 GB RAM |
| 實體主機 | 筆電 12th Gen Intel Core i5-1240P、16 GB RAM |
| OS／核心 | Fedora Linux 44 Workstation，6.19.10-300.fc44.x86_64 |
| SELinux | Enforcing（targeted），自訂模組 `edge_deid`（見 `final-config/selinux-module.txt`） |
| 硬碟 | sda 70 GB（系統、/home）；sdb 80 GB：sdb1 6 GB → `/var/lib/docker`、sdb2 約 74 GB → `/var/lib/containerd`（ext4） |
| auditd | audit-4.1.4，規則見 `final-config/30-docker-cis.rules`、`final-config/auditctl-l.txt` |

不是 WSL；所有主機檢查都在這台 VM 的 Docker daemon 上執行。

## Docker

| 項目 | 值 |
|---|---|
| Docker Engine（client／server） | 29.9.2／29.9.2（rootful，systemd `docker.service`，`dockerd -H fd://`，socket activation） |
| Docker Compose | v5.6.1 |
| context | default（本機 Unix socket `/run/docker.sock`） |
| containerd／runc | v2.4.2（b7a2526）／1.5.2 |
| 儲存 | containerd image store（overlayfs snapshotter），cgroup v2、systemd driver |
| daemon 設定 | `final-config/daemon.json` |

**與 Benchmark 的適用性差異：**

- Docker 29 預設使用 containerd image store，映像實際存放在 `/var/lib/containerd`，不在 `/var/lib/docker`。因此 1.1.1 的獨立分割區同時套用到兩個目錄（見 `cis-remediation.md` §C）。
- Fedora 沒有 `/etc/default/docker`、`/etc/sysconfig/docker`，containerd 2.x 沒有 `containerd-shim`、`containerd-shim-runc-v1`，依 Benchmark 列為 N/A。
- 主機沒有 AppArmor，改用 SELinux（5.2 N/A、5.3 PASS）。
- Docker 29 已移除 `docker trust`，4.11 無法用 Benchmark 原本的 Content Trust 做法（仍列 FAIL，不列 N/A）。
- Benchmark 的 `docker export | tar` 檢查方式（4.7）對 11 GB 映像過慢，改用 `nsenter` 進入容器 mount namespace 執行 `find`，結果等效（見 `checks/final/4.7.txt`）。

## 專案版本

- 分支：`w10-2-cis-audit`。稽核時基於 commit `0383d43e32530336228256477fff31dcc30e0ebf`；W10-1 合併到 main 後，本分支改接在 `5d36358`（PR #78 merge）之上。兩者的程式、Dockerfile、Compose 與 SELinux 政策完全相同，只差 `evidence/security/selinux-handoff.md` 一行文件，所以稽核結果適用。
- 稽核時的未提交修改：`Dockerfile`、`docker-compose.yml`（CIS 修正，見 `cis-remediation.md`）；之後與本目錄一起提交
- Compose：`docker-compose.yml` + `docker-compose.selinux.yml`，環境 `BATCH_LIMIT=5 INSTALL_TFLITE=1 SEG_BACKEND=tflite`；展開結果 `final-config/compose-config.yml`
- 模型後端：TFLite（`models/seg/model.tflite`，SHA-256 `647c5b26dee68b2aa75e4f9f5b7a499bb0510ca771dd923eb077852c42de1d81`，與 W10-1 相同；模型不提交）

## 映像

| 映像 | Image ID |
|---|---|
| edge-deid-sec-acquisition:latest | `sha256:91531e85a6545e2e3f80888c0d0a39a74f1f295f2f87950b5d9a1af678ca1b5d` |
| edge-deid-sec-extraction:latest | `sha256:c45511b8603f3a9cb60aa3cfe9d7bd4ca13407a33fc204560506404078c8c8f5` |
| edge-deid-sec-observability:latest | `sha256:e3f19d623efe0d6816ea04697a6b14acaa4d58fa94495fc150b50b112b88b50a` |
| 基底 | `python:3.11-slim@sha256:673719e071ecf27434fd2635bbd8d00f49f4fdd81f243143438a42ced8bedf60`（2026-10-29 建置當下 registry 最新） |

映像只存在本機，沒有推送到 registry。

## 輔助工具

| 工具 | 版本 | 用途 |
|---|---|---|
| 自寫收集腳本 `scripts/collect_checks.sh` | 本目錄 | 依 Benchmark v1.9.0 各控制項的 Audit 步驟逐項執行，輸出到 `checks/<階段>/<控制項>.txt` |
| `scripts/runtime_window.sh` | 本目錄 | 受控 runtime 期間讓三個容器同時運行，供第 5 節檢查 |
| `scripts/build_controls_csv.py` | 本目錄 | 由判定表產生 `cis-controls.csv` |
| Trivy | 0.76.1（Fedora RPM，來自 GitHub release，已比對官方 checksum；RPM 本身沒有 GPG 簽章） | 4.4 映像弱點掃描，只用 `--scanners vuln`，不需要 root、不掛載 docker.sock 到容器 |

**沒有使用 Docker Bench for Security。** 所有控制項都是依 Benchmark 原文逐項人工判定，腳本只負責收集輸出；判定依據寫在 `judgments-final.tsv` 與 `cis-controls.csv`。
