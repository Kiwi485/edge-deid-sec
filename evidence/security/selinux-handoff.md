## SELinux 驗證交接

- 測試日期／時間範圍：2026-10-25（UTC+8）。最終驗收輪：02:09:52–02:10:13，包含 pytest、三服務回歸與安全探測，全部在同一輪完成。
  - 一般流程（compose up）：02:09:53–02:10:09
  - 安全探測（check_week10_security.py）：02:10:09–02:10:13
- VM 作業系統、虛擬化軟體、vCPU／RAM：Fedora Linux 44 Workstation x86_64（kernel 6.19.10-300.fc44），Oracle VirtualBox，4 vCPU、8 GB RAM（MemTotal 8119008 kB）、/home 68 GB。
  - 註：起初只配置 3.8 GiB，建置映像時 VM 記憶體不足當機。之後在 6.3 GiB 下完成一輪全部通過的測試，最後調為 8 GB 重跑完整一輪；本文件與所有證據皆來自 8 GB 這一輪。
- 實體主機規格：筆電，12th Gen Intel Core i5-1240P、16 GB RAM（VM 分配 4 vCPU／8 GB）。
- Git commit；是否有未提交修改：`c42d0fee00731a9411ab029d97a44103c34cd6f5`（main）。**有未提交修改**：`security/selinux/edge_deid.te`，差異見 `evidence/security/edge_deid-policy.patch`（分支 `w10-1-selinux-vm`；PR：待建立）。
  - `evidence/batch/*` 會被本輪結果覆寫。`.fc`、`.if`、`.pp` 是編譯產物，不需提交。
- 使用模型：TFLite；模型 SHA-256：`647c5b26dee68b2aa75e4f9f5b7a499bb0510ca771dd923eb077852c42de1d81`
- 程式測試：21 passed、0 failed、0 skipped（Docker 已安裝，Compose 設定測試有實際執行）。
- 三服務：acquisition Exited (0)；extraction Exited (0)；observability Exited (0)。
- 圖片處理／輸出驗證：5 / 5 通過。每張 `status=ok`、`seg_backend=tflite`；`acquisition_manifest.json` 中 total=5。
- 隱私：5 / 5 通過，通過率 100%。
- SELinux：Enforcing 是；原圖拒絕 是；IPv4 拒絕 是；IPv6 拒絕 是。
  - extraction context：`system_u:system_r:edge_deid_extraction_t:s0:c192,c359`
  - 原圖標籤：`edge_deid_raw_t`
  - 宿主機外連對照：`connected`
- 安全 JSON：selinux_verified=true；checks_passed=true。`configuration` 與 `runtime.checks` 全為 true，`runtime.uid=10001`，沒有 `error` 欄位。`cis_full_audit=not_run`、`week10_complete=false` 在本階段屬正常。
- AVC 對應證據（`evidence/security/selinux-avc.log`）：
  - 第 7 行：02:10:11，`edge_deid_extraction_t` 被拒絕 `tcp_socket { create }`。這是 runtime 禁網探測（AF_INET 連 1.1.1.1:443）。
  - 第 11、15 行：02:10:12，同一探測容器（pid 5875）先後被拒絕 `tcp_socket { create }`。依時間與順序，分別對應 IPv4 與 IPv6 探測；AF_INET6 的 TCP Socket 在 SELinux 中同樣歸為 `tcp_socket` class。
  - 第 19 行：02:10:12，同一探測容器被拒絕 `dir { read }`，target 為 `edge_deid_raw_t`，`name="raw"`。對應額外唯讀掛載的原圖目錄 `/security-raw`。
  - 一般流程期間（02:09:53–02:10:09）**沒有任何 AVC**。
- 必交檔案的受控下載／備份位置：證據檔隨 PR 提交（不含照片／影像輸出）；原始影像、mask、特徵保留在測試 VM（`/home/i1an/edge-deid-sec/`），收件人需要人工複核時再私下交接。檔案路徑如下：
  - `evidence/security/`：selinux-environment.txt、selinux-tests.txt、week10-selinux.json、selinux-avc.log、selinux-compose.log、selinux-container-status.txt、selinux-handoff.md、edge_deid-policy.patch
  - `evidence/security/batch/`：acquisition_manifest.json、validation_summary.csv、privacy_report.csv、privacy_summary.md、ipc_report.csv、ipc_summary.md、pipeline_latency_vm.csv
    - 本輪輸出原本寫在 `evidence/batch/` 與 `logs/pipeline_latency_vm.csv`。為了不覆蓋 repo 既有的 100 張批次紀錄，複製到此目錄提交，內容未修改。
  - `evidence/security/meta/<image_id>.meta.json`：5 個 `data/out/<image_id>/meta.json` 的複本，只含狀態、指標與 bbox，不含影像
  - 影像、mask、特徵保留在 VM，不放入 Git。
- 本次修改：只修改 SELinux 候選政策 `security/selinux/edge_deid.te`，**沒有增加任何 TCP／UDP／raw IP Socket 權限或原圖權限**。已用 `sesearch` 確認 extraction 對上述 socket class 沒有 `create`，對 `edge_deid_raw_t` 也沒有 open/read。修改內容依發現順序如下：
  1. **extraction 無法啟動**。runc 回報 `write fsmount:fscontext:proc/self/attr/keycreate: invalid argument`。原因是 `edge_deid_extraction_t` 沒有授權給 `system_r` role，context 無效；容器 runtime 也不能轉入這個 domain。修正方式：
     - 加入 `role system_r types edge_deid_extraction_t`
     - 允許 `container_runtime_t` 對它做 `process transition`
     - 加入 `container_runtime_typebounds`（`nnp_transition`），因為 Compose 有設定 no-new-privileges
     - 加入 `mcs_constrained`，與 `container_t` 一樣使用 MCS 類別隔離
     - 沒有採用 `container_domain` attribute，因為它會讓這個 domain 取得所有 file_type（含原圖）的 dir open/search 權限。
  2. **healthcheck 一直 unhealthy**。AVC 為 `edge_deid_extraction_t` 對自身 `unix_stream_socket { connectto }` 被拒絕：healthcheck 在 extraction 內連自己的 Socket。修正方式：自身 unix_stream_socket 加上 `connectto`。
  3. **正常流程中出現兩類 AVC**，雖然沒有讓流程失敗，但屬於正常操作被擋：
     - 對容器內 `/dev/null` 的 `container_file_t:chr_file { read write }` 被拒絕
     - 對自身 cgroup 目錄的 `cgroup_t:dir { search }` 被拒絕
     - 修正方式：允許 container_file_t 字元裝置讀寫，以及唯讀的 `fs_search_cgroup_dirs`、`fs_read_cgroup_files`。沒有加入 cgroup 管理權限。
  - 重測結果：上表最終輪即為修正後的完整重測，正常流程零 AVC，禁止操作全部被拒絕。
- 未解決問題：
  - 政策修改需要提交 PR 供審查（patch 已備）。
- 結論：**通過**（待收件人核對原始證據）。此結論僅適用本 SELinux Issue，不包含 CIS 完整稽核與 1,000 次效能驗收。
