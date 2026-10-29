# CIS Docker Benchmark v1.9.0 改善紀錄（W10-2）

- 修正前證據：`checks/baseline/`、`cis-controls-baseline.csv`（PASS 54 / 適用 88 = 61.36%）
- 修正後證據：`checks/final/`、`cis-controls.csv`（PASS 80 / 適用 88 = 90.909%）
- 功能／SELinux 回歸：`cis-regression.md`、`regression/`
- 修改前設定備份：VM 上 `~/cis-benchmark/backup-20261027-141625/`（`/etc/docker`、`/etc/audit`、`/etc/containerd`、`docker.service`、`docker.socket`、`/etc/fstab`、Dockerfile、Compose、requirements.txt）
- 專案檔差異：`git diff` 於分支 `w10-2-cis-audit`（Dockerfile、docker-compose.yml），主機設定複本見 `final-config/`

每一項改善依「控制項 → 風險 → 原始證據 → 變更 → 回復方式 → 重測」記錄。重測證據檔名與控制項 ID 相同。

## A. 主機稽核（1.1.3–1.1.9、1.1.11、1.1.12、1.1.14、1.1.17、1.1.18、5.23、5.24）

- 風險：Docker daemon、設定檔、socket 與 runtime 二進位檔被修改或濫用時沒有稽核紀錄；`docker exec --privileged`／`--user=root` 無法追查。
- 原始證據：`checks/baseline/1.1.3.txt` 等，`auditctl -l` 只有 `-a never,task`。Fedora 預設 `/etc/audit/rules.d/audit.rules` 以 `-a task,never` **停用所有 syscall 稽核**，因此即使新增規則也不會產生事件（只存在設定、runtime 無效）。
- 變更：
  1. 依該檔註解的官方做法，刪除 `rules.d/audit.rules`，改安裝 Fedora 提供的 `/usr/share/audit-rules/10-base-config.rules`（`-D`、`-b 8192`、`--backlog_wait_time 60000`、`-f 1`）。
  2. 新增 `/etc/audit/rules.d/30-docker-cis.rules`（複本：`final-config/30-docker-cis.rules`），對 dockerd、/run/containerd、/var/lib/docker、/etc/docker、docker.service、docker.socket、containerd.sock、/run/docker.sock、daemon.json、/etc/containerd/config.toml、containerd、containerd-shim-runc-v2、runc 加入 `-k docker` 監看；並對 `/usr/bin/docker` 加 `-p x`，讓 docker CLI 的執行參數（EXECVE）可供 5.23／5.24 查核。
  3. `augenrules --load` 載入。
  4. **重開機後發現的問題與修正**：開機時 audit-rules.service 比 containerd 早執行，`/run/containerd` 尚不存在，`containerd.sock` 規則載入失敗並中止其後所有規則，重開機後只剩 6 條規則（`journalctl -u audit-rules`：`Error sending add rule data request (No such file or directory)`）。修正方式：把 `containerd.sock` 規則移到檔案最後，並新增 `/etc/systemd/system/docker.service.d/10-cis-audit.conf`（`ExecStartPost=-/usr/sbin/augenrules --load`），在 Docker 啟動、相關路徑已存在後重新載入。重啟 docker 後 `auditctl -l` 恢復 14 條 `-k docker` 規則，且沒有 AVC。開機時 audit-rules.service 仍會因最後一條規則回報失敗，但其餘規則已載入，Docker 啟動後即補齊。
- 有效性驗證：執行 `docker version` 與讀取 daemon.json 後，`ausearch -k docker` 出現 EXECVE（含 `docker version` 參數）與 daemon.json 的 PATH／SYSCALL 事件，證明規則在 runtime 生效。
- 回復：刪除 `30-docker-cis.rules`、`10-base-config.rules` 與 `docker.service.d/10-cis-audit.conf`，從備份還原 `rules.d/audit.rules`，`systemctl daemon-reload`、`augenrules --load`。
- 影響：syscall 稽核開啟後有額外 CPU／磁碟負擔，`/var/lib/docker -p wa` 會記錄容器資料寫入。auditd 設定為 `max_log_file=8`、`num_logs=5`、`ROTATE`。**下一個 1,000 次效能 Issue 必須在此設定下量測。**

## B. Docker daemon（2.2、2.9、2.15、2.16、2.17）

- 風險：預設 bridge 容器可互連（2.2）、未限制開檔數（2.9）、容器可取得新權限（2.15，僅依賴 Compose 逐容器設定）、daemon 重啟會中斷容器（2.16）、userland-proxy 擴大攻擊面（2.17）。
- 原始證據：`checks/baseline/2.2.txt`（enable_icc:true）、`2.9.txt`、`2.15.txt`、`2.16.txt`（false）、`2.17.txt`。
- 變更：`/etc/docker/daemon.json`（複本：`final-config/daemon.json`）

  ```json
  {
    "selinux-enabled": true,
    "icc": false,
    "live-restore": true,
    "userland-proxy": false,
    "no-new-privileges": true,
    "default-ulimits": { "nofile": { "Name": "nofile", "Soft": 4096, "Hard": 8192 } }
  }
  ```

  套用前以 `dockerd --validate --config-file` 驗證，之後 `systemctl restart docker`。
- 影響判斷：專案三服務不使用預設 bridge（acquisition／observability 在 Compose 自訂網路，extraction 為 `network_mode: none`），也沒有發布任何 port，因此 icc 與 userland-proxy 不影響功能；Compose 本來就逐容器設定 no-new-privileges。
- 回復：從備份還原 daemon.json（只含 `"selinux-enabled": true`），`systemctl restart docker`。

## C. Docker 資料獨立分割區（1.1.1）

- 風險：容器、映像或日誌塞滿根分割區，造成系統與稽核紀錄無法寫入。
- 原始證據：`checks/baseline/1.1.1.txt`，/var/lib/docker 位於根目錄 btrfs 子卷。
- 發現：Docker 29 使用 containerd image store，映像與 snapshot（約 18 GB）實際在 **/var/lib/containerd**，/var/lib/docker 只有約 820 KB。只搬 /var/lib/docker 雖可通過檢查指令，但無法達成控制項目的。
- 變更：VirtualBox 新增 40 GB 虛擬硬碟 `/dev/sdb`，GPT 分割：
  - `sdb1` 6 GB ext4（label `docker-root`）→ `/var/lib/docker`
  - `sdb2` 34 GB ext4（label `containerd-root`）→ `/var/lib/containerd`
  - 以 UUID 寫入 `/etc/fstab`（`findmnt --verify` 無錯誤），權限維持原本 710／700 root:root，`restorecon` 後標籤為 `container_var_lib_t`。
  - 舊資料改名保留於根分割區：`/var/lib/docker.pre-cis`、`/var/lib/containerd.pre-cis`。
  - 新硬碟上重新建置映像（見 E）。
  - **容量調整**：三服務映像同時解壓 torch／CUDA 層時，34 GB 的 sdb2 寫滿（`no space left on device`）。使用者把虛擬硬碟加大到 80 GB；先以 `sfdisk -d` 備份分割表（`~/cis-benchmark/backup-20261027-141625/sdb-partition-table-before-grow.sfdisk`），再以 `sfdisk -N 2` 把 sdb2 延伸到磁碟結尾（約 74 GB）、`resize2fs` 線上擴充。UUID、標籤與 SELinux 標籤不變，fstab 不需修改。映像改為逐一服務建置以降低尖峰用量。
- 回復：停止 docker／containerd → 卸載並移除 fstab 兩行 → 把 `.pre-cis` 目錄改回原名 → 啟動服務。
- 注意：新硬碟需隨 VM 一起保存；交接給效能 Issue 時，`/var/lib/docker` 與 `/var/lib/containerd` 都在 sdb。

## D. 映像（4.5、4.7）

- 4.7 風險：映像內 su、mount、passwd、chsh 等 11 個 setuid／setgid 檔可被用於提權。
  - 原始證據：`checks/baseline/4.7.txt`。
  - 變更：Dockerfile 最後一個 RUN 加入 `find / -xdev -perm /6000 -type f -exec chmod a-s {} +`。
  - 重測：`checks/final/4.7.txt` 在每個容器的 mount namespace 以 root 執行 find（不改用 `docker exec --user root`，避免觸犯 5.24），setuid／setgid 數量為 0，且 su、passwd、mount 仍存在但已無 s 位元。原 Benchmark 的 `docker export | tar -tv` 對 11 GB 容器過慢（實測超過 1 小時），改用等效方法並保留於腳本註解。
- 4.5 風險：映像沒有健康檢查。
  - 變更：Dockerfile 新增 `HEALTHCHECK`（Python 可執行且唯讀根目錄下的 /tmp tmpfs 可寫入）。
- 回復：`git checkout <base> -- Dockerfile` 後重新建置。

## E. 映像更新與基底版本（5.28、4.4）

- 風險：使用舊快取基底映像，未包含已發布的安全修補。
- 原始證據：`checks/baseline/5.28.txt`，映像以 `python:3.11-slim@sha256:b7a9e5…` 建置，registry 已有新版本。
- 變更：以 `docker compose build --pull` 重新建置。建置期間 registry 又發布新版本（`0a19f6…` → `ae952e…`），因此重建到驗證當下的最新 digest。2026-10-29 重跑時 registry 再更新為 `673719e…`，再次以 `--pull` 重建（§I）。
- 建置可靠性：VM 網路下載約 6 GB Python 套件時兩次失敗（read timeout、broken pipe），Dockerfile 的 pip 加上 `--default-timeout=300 --retries 10`，並改用 BuildKit cache mount（`--mount=type=cache,target=/tmp/.cache/pip`），讓已下載套件可在重試時沿用；cache 不寫入映像層。
- 5.28 重測：`checks/final/5.28.txt`，建置 log 的基底 digest `673719e…` 等於 registry 最新 → PASS。
- 4.4：以 Trivy 0.76.1 掃描三個最終映像（`tool-output/trivy-vulns.csv`；完整 JSON 保存在 VM，見 `tool-output/README.md`，摘要附在 `checks/final/4.4.txt` 最後）。Debian 層 234 筆弱點目前都沒有修補版本，表示基底已是最新修補；但 Python 套件 71 筆可修正弱點未修補（pillow 12.1.0 含 5 CRITICAL，修正於 13.0.0），**4.4 仍判 FAIL，本輪無修正**。pillow 需升主版本、影響共用 requirements 與樹莓派部署，交負責人決定，計畫見 `cis-summary.md`。

## F. 容器 runtime（5.12、5.15、5.27）

- 5.12 風險：沒有 CPU 優先權，資源競爭時 extraction 可能被其他容器擠壓。變更：`cpu_shares` extraction 768、acquisition／observability 512（原本的 `cpus` 上限保留）。
- 5.15 風險：無限重啟可能造成主機 DoS，也會掩蓋容器失敗的原因。Benchmark 建議需要自動重啟時用 on-failure 且最多 5 次；只有 `always` 判為不符合，`no` 原文說明「可能是安全的選項」。
  - 變更：extraction、observability 改為 `restart: on-failure:5`；acquisition 維持 `restart: "no"`。
  - acquisition 不自動重啟的原因（PR 程式碼審查發現）：acquisition 是一次性批次，重啟會從第一張重送，而 extraction 用 `--max-requests` 限制只處理 `BATCH_LIMIT` 筆。若 acquisition 在送出部分或全部工作後才失敗（例如第一次回歸時寫報告沒有權限），重啟會耗盡 extraction 額度，使結果重複或不完整。因此最初「三服務都 on-failure:5」的修改已改回，並重跑完整回歸。
  - 修正前基準把 `RestartPolicyName=no` 判為 FAIL，比 Benchmark 原文嚴格；基準紀錄保留原判定，不追溯修改。
  - 正常流程結束碼為 0，不會重啟。
- 5.27 風險：acquisition、observability 沒有 runtime health。變更：Compose 為 acquisition 加上「可連到 extraction Unix Socket」的健康檢查，observability 加上「輸出目錄可寫入」的健康檢查；extraction 維持原本 socket readiness 檢查。
- 回復：還原 docker-compose.yml。

## G. 評估後不修正、維持 FAIL 的項目

1.2.1、2.1、2.13、2.14、4.3、4.4、4.10、4.11 共 8 項，本輪無修正。逐項風險、理由與處理決定見 `cis-summary.md`「剩餘 FAIL」一節。

## H. 稽核過程中的非安全性問題

- `evidence/batch/` 的既有 CSV 在 W10-1 以 `git restore` 還原後，擁有者變成 `i1an:i1an 644`，容器使用者 10001 無法寫入，導致第一次回歸 acquisition／observability 結束碼 1。依 W10-1 權限規劃（群組 10001 可寫）修正後重跑通過。這不是 CIS 修改造成的，但 `git restore` 後需重設群組權限。

## I. PR 程式碼審查後的修正（2026-10-29）

PR 的自動程式碼審查提出 4 項問題，經確認都成立，已修正並重跑完整回歸與 CIS 檢查。

| 問題 | 修正 | 影響 |
|---|---|---|
| acquisition 自動重啟會耗盡 extraction 的處理額度 | acquisition 改回 `restart: "no"`（見 §F 5.15） | 系統設定變更 → 重跑回歸 |
| 5.24 用 `grep user` 抓不到 `docker exec -u 0`、`-u0`、`-itu root` | `scripts/collect_checks.sh` 的 5.23／5.24 除 Benchmark 原本的 grep 外，再以 `ausearch -m EXECVE -i` 解碼 docker CLI 參數，比對 `--privileged`、`--user`、`-u` 及合併短參數；有符合就人工檢視 | 只改稽核腳本 |
| 回歸腳本失敗後仍繼續收集 CIS 證據，結束碼為 0 | `scripts/run_final_round.sh` 每一步失敗即停止並回傳非 0；`compose up` 加 `--abort-on-container-failure`，並確認每個服務結束碼為 0 | 只改稽核腳本 |
| extraction 一直沒有 healthy 時，runtime window 仍繼續 | `scripts/runtime_window.sh` 等候 60 秒仍非 healthy 即失敗 | 只改稽核腳本 |

重跑時發現 registry 的 `python:3.11-slim` 又發布新版，為維持 5.28，使用 `--pull` 以新基底重建三個映像，並重做 Trivy 掃描（見 §E 與 `cis-environment.md`）。
