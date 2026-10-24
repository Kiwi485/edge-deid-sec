# W10 安全部署與驗證

## 驗收範圍

- extraction 禁網，僅由 Unix Socket 接收圖片，不能直接讀取宿主機 `data/raw`。
- 非 root、唯讀根目錄、移除所有 capabilities、禁止提權、限制 PID。
- SELinux enforcing 下，以獨立 domain 拒絕網路 Socket 與原圖 type。
- 完整 CIS Docker Benchmark 稽核、適用項目合規率 >90%，保存版本與例外理由。
- 最終安全設定下重新驗證 pipeline 輸出、privacy pass rate 與 W9 效能。

目前的 JSON 證據只表示實際跑過的檢查。`checks_passed` 不等於 W10 完成；設定檢查、SELinux 與完整 CIS 稽核是不同門檻。

## 測試快速開始

以下指令都在專案根目錄執行，使用 Linux Bash、已啟用的 Python 環境與 Docker Compose v2。Windows 建議使用 WSL2 並開啟 Docker Desktop 的 WSL integration；原生 Windows 的 Unix Socket、檔案權限與 SELinux 行為不能視為 Linux 驗收。macOS Docker Desktop 可以檢查容器限制，但 SELinux 需另用適合的 Linux VM。

### 1. 不用照片的程式測試

```bash
python -m pip install pytest
python -m pytest -q test/test_week10_security.py test/test_unix_socket_ipc.py
```

預期全部通過（2026-10-24 的 Ubuntu WSL2 驗證為 21 passed，無略過）。涵蓋圖片內容經 Socket 傳輸、拒絕不合法檔名/Base64/過大圖片、忽略客戶端讀寫路徑、成功與失敗後刪除暫存、Compose 安全設定，以及安全探測指令與錯誤輸出回歸。模型處理使用替身，這不是實際分割品質測試。若未安裝 Docker，兩項 Compose 測試會略過，不能當作設定已驗證。

### 2. 不用模型的設定檢查

啟動 Docker 後執行，不需要先建立專案映像：

```bash
python tools/check_week10_security.py --static-only --output evidence/security/week10-static.json
```

預期 `configuration` 每項為 `true`、`checks_passed` 為 `true`、`scope` 為 `static-only`。這一步不會啟動 extraction 或證明 runtime 限制。`selinux_verified: false` 與 `week10_complete: false` 在此階段是正常的。

### 3. 容器與真實圖片回歸

先備份舊輸出與 CSV，依 [一般 Linux 部署](#一般-linux-部署)準備權限，放入至少 5 張 JPG/PNG 與分割模型；本例使用預設 PyTorch。若先前設定過 TFLite 環境變數或 `.env`，本次指令會明確選擇 torch：

```bash
docker compose build
BATCH_LIMIT=5 SEG_BACKEND=torch docker compose up
python tools/check_week10_security.py --output evidence/security/week10-runtime.json
docker compose ps -a
```

若部署使用 TFLite，可改用以下指令；需先準備 `models/seg/model.tflite`，不必為了 W10 改回 PyTorch：

```bash
BATCH_LIMIT=5 INSTALL_TFLITE=1 SEG_BACKEND=tflite docker compose up --build --force-recreate
python tools/check_week10_security.py --output evidence/security/week10-runtime.json
docker compose ps -a
```

等待流程完成後再執行安全檢查。`BATCH_LIMIT` 不可超過可用照片數；圖片的檔名主體應唯一，避免不同副檔名覆寫同一個輸出 bundle。安全探測會另外建立一次性容器，不會執行模型或取代三服務回歸。

| 查看項目 | 預期結果 |
|---|---|
| pytest | 沒有 failed/error；無 Docker 時略過的設定測試需另補測 |
| runtime JSON | `configuration` 與 `runtime.checks` 全為 `true`，`checks_passed` 為 `true` |
| 宿主機外連對照 | `host_network_control` 為 `connected`；否則不能判定禁網驗證完整 |
| 三服務狀態 | acquisition、extraction、observability 都正常完成，exit code 0 |
| 每張 meta | `status=ok`、`seg_backend` 與選用後端一致（`torch` 或 `tflite`）、`privacy_metrics.privacy_pass=true` |
| 輸出驗證 | `evidence/batch/validation_summary.csv` 中本批次全部通過 |
| 隱私報告 | `evidence/batch/privacy_summary.md` 中本批次 privacy pass rate 為 100% |

若不通過，先查看 JSON 的 `error` 或為 `false` 的項目，再執行 `docker compose logs acquisition extraction observability`。權限錯誤請修正指定目錄權限，不要改成 root/privileged 或 `chmod 777`；缺模型請補齊模型；extraction 一直等待則確認照片數與 `BATCH_LIMIT`。品質或隱私不通過須查看該張 meta，不能只因容器 exit code 0 就判定成功。

完成證據收集後可執行 `docker compose down` 停止與移除容器。JSON 的 `--output` 分開保存設定與 runtime 結果，避免預設證據檔被下一輪覆寫。

### 4. 最後才驗收 SELinux 與 CIS

依 [SELinux 專用宿主機](#selinux-專用宿主機)編譯、安裝政策並使用覆寫設定後，再執行 `--require-selinux`。它不是所有電腦都能直接執行的快速測試。完整 [CIS Checklist](#cis-checklist) 稽核與最終安全配置下的 W9 效能證據仍須另外完成；不要以第 1 到 3 步通過宣稱 W10 全部完成。

## 資料流與限制

acquisition 唯讀掛載原圖，傳送 Base64 圖片內容；單張上限 16 MiB，IPC 請求上限 24 MiB。extraction 不接受客戶端指定讀寫路徑，圖片暫存於自己的 `/tmp` tmpfs，成功或失敗都清除暫存目錄。處理中仍會接觸原始像素，這不是「完全看不到原圖」的架構。

extraction 僅掛載輸出、延遲日誌、唯讀模型與專用 Socket volume；不掛載原圖、Docker Socket 或宿主機 `/tmp`。原圖不會被 COPY 到映像（見 `.dockerignore`）。既有 pipeline 會保存 `roi.png`，ROI 不保證只有舌頭，輸出目錄仍應視為敏感資料。原圖與輸出的保留期限須由部署者明定。

observability 目前仍需唯讀原圖來重算隱私指標，並需寫入輸出 `meta.json`。W10 的原圖隔離目標是 extraction，不是三個服務全部。Unix Socket volume 僅供 acquisition/extraction 共用。

Base64 傳輸會增加資料量與編解碼成本，因此 W4 的舊 IPC 數據不能直接沿用，必須重新量測。暫存資料會在正常完成、例外處理或容器移除時消失；程序被強制終止但容器仍存活時可能留在 tmpfs，應移除容器。不保證 RAM 清零，也不保證宿主機 swap 不含原圖；敏感部署須停用或加密 swap，禁止 core dump，訂定原圖 retention。

## 一般 Linux 部署

先備份原有輸出與 latency CSV。以下具管理權限的命令由部署者在宿主機執行，不是在 Codespace 內執行；只調整此專案的指定目錄，不使用 `chmod 777`：

```bash
mkdir -p data/raw data/out logs evidence docs
sudo chown -R 10001:10001 data/out logs evidence
sudo chgrp -R 10001 data/raw docs
sudo chmod -R g+rX data/raw
sudo chmod -R g+rwX docs
docker compose build
BATCH_LIMIT=5 docker compose up
python tools/check_week10_security.py
```

`BATCH_LIMIT` 不可超過可用照片數，否則 extraction 會等待。這些權限調整會改變宿主機檔案 ownership；有其他共用使用者時請改用精確 ACL。Docker Desktop 的 bind mount 權限行為可能不同。

使用同一批輸入做回歸，先保存舊輸出；Compose 不再自動清除整個输出掛載點，以避免刪除 mount root 失敗。改用不同批次時，先備份並手動整理舊 bundle，避免離線稽核把不同批次混算。

安全檢查工具不需要模型推論，但需要已建立的 extraction 映像與可寫的掛載目錄。探測前先確認映像存在，再以 `--pull never` 執行；不會自動 build，也不會自動修正宿主機權限。無映像、無權限、主機外連對照失敗都會記錄失敗，不會冒充通過。Docker 指令失敗時，JSON 的 `command_stderr` 與 `command_stdout` 會保留錯誤輸出。

```bash
python tools/check_week10_security.py --static-only
python -m pytest -q test/test_week10_security.py test/test_unix_socket_ipc.py
```

預設證據位置：`evidence/security/week10.json`。重跑會覆寫，正式驗收應使用 `--output` 指定不同檔案。`--static-only` 只驗證設定，不能當成容器 runtime 證據。

## SELinux 專用宿主機

在 Fedora/RHEL 類、具 Docker 相容 container-selinux 的測試 VM 上先驗證。Docker Desktop VM、目前的 AppArmor Codespace 或未啟用 SELinux 的樹莓派，不具備相同驗證条件。不要為了讓容器啟動而停用 SELinux、使用 privileged 或 label=disable。

`security/selinux/edge_deid.te` 是待目標宿主機編譯與實測的候選政策，不是已驗證政策。它未繼承 container domain 的網路允許規則；`neverallow` 是編譯期防止意外授權的約束，runtime 拒絕來自沒有相應 allow 規則。reference-policy interface 與檔案 labels 隨宿主機版本不同，可能需要依 AVC 做最小範圍調整。

安裝宿主機的 `selinux-policy-devel`、`policycoreutils-python-utils`、`container-selinux` 與編譯工具後，管理員執行：

```bash
getenforce
make -C security/selinux -f /usr/share/selinux/devel/Makefile edge_deid.pp
sudo semodule -i security/selinux/edge_deid.pp
```

`getenforce` 必須是 `Enforcing`。政策編譯或安裝失敗就停止，不把失敗當證據。完成一般 Linux 的檔案權限準備後，使用絕對路徑設定獨立原圖 type：

```bash
sudo semanage fcontext -a -t edge_deid_raw_t "$PWD/data/raw(/.*)?"
sudo restorecon -Rv data/raw
ls -Zd data/raw
docker compose -f docker-compose.yml -f docker-compose.selinux.yml config --quiet
BATCH_LIMIT=5 docker compose -f docker-compose.yml -f docker-compose.selinux.yml up --build
python tools/check_week10_security.py --require-selinux --output evidence/security/week10-selinux.json
```

若同一路徑已有自訂 fcontext，先確認原規則，再由管理員使用 `-m`，不要盲目覆寫。專案位於原始標籤不可變更的共享儲存上時，改用專用本機目錄。

覆寫檔刻意移除原圖 mount 的 `:z`，避免 Docker 將 `edge_deid_raw_t` 重標成 `container_file_t`。完成自訂標籤後不要再用只有基本 Compose 的 acquisition/observability，否則 `:z` 會改回原圖標籤。其他專案可寫 volume 仍使用 shared container label，IPC 不可用兩個不同 private `:Z` 標籤。

驗證工具會檢查 enforcing、實際 extraction context、原圖標籤，並在一次性 extraction 探測容器中額外唯讀掛載原圖，確認讀取目錄得到 `EACCES/EPERM`；也檢查 IPv4/IPv6 TCP Socket 建立被 SELinux 拒絕。一般禁網探測使用固定 IP 與宿主機連線對照，避免把 DNS 失敗誤認成禁網。

保存對應時間範圍的 AVC 證據，並確認 subject 是 `edge_deid_extraction_t`、target 是 `edge_deid_raw_t` 或網路 Socket：

```bash
sudo ausearch -m AVC,USER_AVC -ts recent > evidence/security/selinux-avc.log
```

不要直接把整份 AVC 丟給 `audit2allow` 套用。政策不得增加 TCP/UDP/raw Socket 或原圖權限。只有拒絕證據也不夠：必須同時保留三服務正常處理、輸出驗證及 privacy pass 的紀錄。移除測試政策之前，先停掉容器、移除原圖自訂 fcontext 並 restorecon，再由管理員移除 module。

## CIS Checklist

以下是專案檢查清單，不是完整 CIS Docker Benchmark，也沒有宣稱已超過 90%。正式稽核需固定所用 CIS 版本、Level/profile、Docker/OS 版本、所有適用控制項與判定證據。

| 範圍 | 檢查 | 目前狀態 |
|---|---|---|
| 容器使用者 | 非 root UID/GID | WSL2 設定檢查通過；runtime 確認非 root、UID 10001；目標 SELinux VM 待驗證 |
| 權限 | drop ALL、no-new-privileges、不使用 privileged | WSL2 runtime 確認有效 capabilities 為 0、禁止提權；不是完整 CIS 驗收 |
| 檔案系統 | rootfs 唯讀、模型唯讀、指定可寫目錄 | WSL2 設定檢查通過；runtime 確認 rootfs 唯讀、輸出及日誌可寫；模型唯讀未另做寫入探測 |
| 網路與掛載 | extraction 禁網、不掛原圖或 Docker Socket | WSL2 設定檢查通過；runtime 確認原圖目錄不存在、外連被阻擋且宿主機對照可連線 |
| 資源 | CPU、RAM、PID limits | 設定已加入；宿主機 enforcement 待實測 |
| LSM | seccomp 保持預設；SELinux enforcing 自訂政策 | SELinux 待編譯與實測 |
| 宿主機 | 專用工作負載、更新、Docker 權限、auditd | 部署者稽核 |
| daemon | logging、TLS/遠端存取、live restore、user namespace 等適用控制 | 部署者稽核 |
| 映像 | 來源信任、digest 固定、掃描、SBOM、套件更新 | 未驗證 |
| 資料 | retention、敏感 ROI、swap/core dump、備份權限 | 部署者制定與驗證 |

使用獲授權的 CIS 稽核方法或經審查且固定版本的 Docker Bench for Security 作輔助，後者不能直接等同完整 CIS 認證。此專案不自動下載或執行高權限稽核腳本。

保存稽核輸出與一份 CSV：`control_id,applicable,status,evidence,exception_reason`。合規率 = 通過的適用控制項 / 全部適用控制項；未檢查項目不可算通過，N/A 必須有理由。目標是嚴格大於 90%。完整報告另行交付；安全工具故意不讓局部探測把 `week10_complete` 設成 true。

## 最終交付

- 目標 VM 的 runtime JSON、SELinux JSON 與對應 AVC 日誌。
- 三服務正常處理、輸出完整與 privacy pass 的報告。
- CIS 固定版本全量清單、證據、適用性理由與合規率。
- 最終安全配置下 W9 的 1,000 次測試；不得用之前未隔離的效能報告替代。

## 階段驗證紀錄（2026-10-24）

環境為 Ubuntu WSL2 + Docker Desktop，專案副本位於 Ubuntu 的 Linux 檔案系統。以下是本次開發驗證結果，不代表目標 SELinux 宿主機驗收或完整 CIS 合規：

| 項目 | 本次結果 |
|---|---|
| 單元與 Compose 設定測試 | 21 passed，無失敗或略過 |
| 靜態設定與 runtime 安全檢查 | 全部通過，`checks_passed=true` |
| 禁網對照 | `host_network_control=connected`，extraction 外連被阻擋 |
| 真實模型與圖片回歸 | TFLite 後端，5 張圖片全部 `status=ok` |
| 三服務狀態 | acquisition、extraction、observability 皆 `Exited (0)` |
| 輸出驗證 | 5 passed、0 failed |
| 隱私驗證 | 5/5 通過，privacy pass rate 100%；僅代表本批次 |
| SELinux | 宿主機不可用，`selinux_verified=false`，待另測 |
| 完整 CIS 稽核 | 未執行 |

本批次 `total_ms`：第一張 344.27 ms，包含 114.99 ms 模型載入；後四張平均 86.56 ms；全部五張平均 138.10 ms。五張皆未達單幀 <80 ms 目標，不能以模型 forward 時間取代 pipeline 總耗時，也不能以五張 smoke test 取代 W9 的 1,000 次測試、百分位數及 95% CI。首次處理與後續處理應分開報告。

證據保存在執行測試的 Ubuntu 專案副本中，不會自動同步至 Windows 原專案。保留 `evidence/security/` 的 JSON、Compose 日誌與容器狀態，`evidence/batch/` 的輸出及隱私報告，以及 `logs/pipeline_latency_vm.csv`；若需保留影像、mask、特徵與每張 meta，另保存 `data/out/`。本機證據需備份並檢查敏感資訊，不應直接整批提交至公開儲存庫。

下一步是 SELinux enforcing 宿主機驗證、完整 CIS 稽核與最終安全配置下的 1,000 次效能驗收。`week10_complete=false` 仍是正確結果。