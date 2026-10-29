# CIS Docker Benchmark 稽核摘要（W10-2）

- Benchmark：CIS Docker Benchmark v1.9.0；Profile：Level 1 + Level 2 - Docker - Linux（Swarm 9 項列 N/A）
- 目標：W10-1 的 Fedora 44 SELinux Enforcing VM（見 `cis-environment.md`）
- 最終檢查：2026-10-29 17:39:26–17:40:04（UTC+8），`checks/final/`；完整表格 `cis-controls.csv`
- 本報告為團隊內部自我評估，不是 CIS 官方認證

## 合規率計算

| 符號 | 意義 | 修正前（`cis-controls-baseline.csv`） | **修正後（`cis-controls.csv`）** |
|---|---|---|---|
| T | 選定範圍控制項總數 | 117 | **117** |
| N | 不適用 N/A | 29 | **29** |
| A = T − N | 適用控制項 | 88 | **88** |
| P | PASS | 54 | **80** |
| F | FAIL | 34 | **8** |
| U | NOT_CHECKED | 0 | **0** |
| 核對 A = P + F + U | | 88 = 54 + 34 + 0 | **88 = 80 + 8 + 0** |
| 合規率 P / A × 100% | | 61.3636…% | **90.9090…%** |

**80 / 88 × 100% = 90.909090…%，未四捨五入即嚴格大於 90%；U = 0。**

可用以下指令從 CSV 重算：

```bash
python3 -c "import csv,collections; r=list(csv.DictReader(open('cis-controls.csv'))); c=collections.Counter(x['status'] for x in r); A=len(r)-c['N/A']; print(len(r), dict(c), A, c['PASS']/A*100)"
```

分 profile：Level 1 - Docker - Linux 78 項（PASS 63、FAIL 5、N/A 10）；Level 2 - Docker - Linux 30 項（PASS 17、FAIL 3、N/A 10）；Level 1 - Docker Swarm 9 項（全部 N/A）。

**注意：餘裕很小。** 只要再多 1 項 FAIL（79/88 = 89.77%）就不合格。之後效能 Issue 若改動 daemon、Compose 或映像，必須重測受影響控制項。

## 本輪修正（26 項由 FAIL 轉 PASS）

1.1.1、1.1.3–1.1.9、1.1.11、1.1.12、1.1.14、1.1.17、1.1.18、2.2、2.9、2.15、2.16、2.17、4.5、4.7、5.12、5.15、5.23、5.24、5.27、5.28。細節、修改前後與回復方式見 `cis-remediation.md`；功能與 SELinux 回歸全部通過，見 `cis-regression.md`。

## 剩餘 FAIL（8 項，全部揭露，未當成 PASS）

負責人：W10-2 稽核執行者提出建議，**處理決定由專案負責人確認**（目前狀態：本輪接受風險、列入後續計畫）。

| ID | Level | 風險 | 現況與緩解 | 建議處理 |
|---|---|---|---|---|
| **4.4** 映像掃描與修補 | L1 | **高**。pillow 12.1.0 有 5 CRITICAL、36 HIGH 可修正弱點（影像解碼，本系統正是處理照片）；基底內建 pip／setuptools／wheel 也有可修正弱點。Debian 層 234 筆目前都沒有修補版本 | 已掃描並以最新基底重建；extraction 在 SELinux `edge_deid_extraction_t`、`network_mode: none`、非 root、唯讀根目錄、cap_drop ALL 下執行，降低被利用後的影響 | **優先處理**：requirements 升級 `pillow>=13.0.0`、`pillow-heif>=1.3.0`，Dockerfile 升級 pip／setuptools／wheel，重建後重跑回歸與 Trivy。因 pillow 升主版本、影響樹莓派部署，需負責人同意 |
| 4.3 只安裝必要套件 | L1 | 中。TFLite 映像仍含 torch、CUDA、ultralytics、pytest，映像 11 GB，攻擊面與弱點數變大 | 未修正 | 拆分 runtime／dev requirements，建立最小 TFLite 映像（同時改善 4.4 與樹莓派部署） |
| 4.10 安裝套件的驗證 | L1 | 中。pip 套件沒有 hash 驗證，供應鏈被竄改時無法發現 | apt 有 Debian keyring 驗證；pip 版本大多固定 | `pip-compile --generate-hashes` + `pip install --require-hashes` |
| 4.11 映像簽章驗證 | L2 | 中低。未驗證基底映像簽章 | 以 digest 記錄並固定（`cis-environment.md`）；Docker 29 已移除 `docker trust` | 評估 cosign 驗證 Docker Official Images，或 Dockerfile `FROM` 固定 digest |
| 2.1 rootless 模式 | L1 | 中。dockerd 以 root 執行，daemon 被攻破即取得 root | SELinux Enforcing、容器非 root、no-new-privileges、cap_drop ALL | rootless 與 W10-1 自訂 SELinux 政策（`container_runtime_t` 轉換）不相容，改用需重做政策與驗證；建議維持現況，由負責人決定 |
| 2.13 授權外掛 | L2 | 低。能使用 docker.sock 的人等同 root | 單機 VM，docker 群組只有管理者；`/run/docker.sock` 660 root:docker；`-k docker` 稽核規則可追查 | 維持現況；多人共用主機時再評估 |
| 2.14 集中／遠端日誌 | L2 | 低中。日誌只在本機 json-file，主機被入侵時可能被刪除 | 本機 json-file + auditd | 團隊有集中日誌服務後設定 syslog/journald 轉送 |
| 1.2.1 主機強化基準 | L1 | 中。主機作業系統沒有依正式強化基準驗證 | SELinux Enforcing、auditd、firewalld | 超出 Docker Benchmark 範圍；建議另開 Issue 套用 CIS Fedora／RHEL 主機基準 |

## N/A 理由（29 項）

每項理由寫在 `cis-controls.csv` 的 `exception_reason` 欄，證據在 `checks/final/<ID>.txt`。

| 控制項 | 理由 |
|---|---|
| 1.1.10、3.19、3.20 | `/etc/default/docker` 不存在（Fedora 不使用） |
| 1.1.13、3.21、3.22 | `/etc/sysconfig/docker` 不存在 |
| 1.1.15、1.1.16 | containerd 2.x 只有 `containerd-shim-runc-v2`，這兩個檔案不存在 |
| 2.8、3.9–3.14 | dockerd 只用 `-H fd://`（Unix socket），沒有監聽 TCP，也沒有 TLS 憑證檔 |
| 2.10 | 三個映像都以非 root `USER 10001:10001` 執行，依 Benchmark 說明可不啟用 userns-remap |
| 2.18 | 使用 Docker 內建 seccomp profile，沒有需要自訂的系統呼叫 |
| 3.7、3.8 | `/etc/docker/certs.d` 不存在，沒有 registry 憑證 |
| 5.2 | 主機沒有 AppArmor，改由 SELinux 限制（5.3 PASS） |
| 7.1–7.9 | Swarm 未啟用（`LocalNodeState=inactive`），不在選定 profile 內 |

這些 N/A 都是「條件不存在」，不是「工具不支援」或「不方便檢查」。

## 「配置存在」與「runtime 有效」

- 第 5 節在受控 runtime 期間檢查實際運行中的容器（`scripts/runtime_window.sh`），不是只看 Compose。
- 稽核規則：`auditctl -l` 為 runtime 載入結果，並以 `ausearch -k docker` 確認有事件；重開機後仍自動恢復 14 條規則。
- daemon 設定：同時檢查 `daemon.json` 與 `docker info`／網路 inspect 的 runtime 值。

## 結論

**完整稽核已完成並達標**：117 項全部列出，NOT_CHECKED = 0，N/A 都有理由，合規率 80 / 88 = 90.909%（> 90%）；修正後 SELinux、五張圖片、輸出驗證與隱私回歸全部通過。

但 **4.4 的 pillow CRITICAL 弱點屬於高風險**，雖然不影響合規率是否過 90%，仍建議在效能 Issue 之前由負責人決定是否先升級並重測。若升級，4.4 可轉為 PASS（81/88 = 92.05%），且需重做本報告的映像識別、回歸與第 4、5、6 節檢查。
