# Raspberry Pi 相機與 Docker

此流程在 Pi 宿主機預覽及拍照，透過 Docker acquisition 和 Unix Socket 將照片送到 extraction，以 MediaPipe ROI、TFLite 分割和既有 pipeline 產生結果；observability 再檢查輸出。它不是分類器，也不會自動啟用 SELinux。

## 先決條件

- Raspberry Pi 4B、64 位元系統（`uname -m` 為 `aarch64`）、已連接相機與可用的圖形桌面。TigerVNC 預覽使用 `--qt-preview`。
- 安裝 Docker Engine、Compose plugin、Python 3 和 `rpicam-still`；確認 `rpicam-hello --list-cameras` 偵測到相機。
- 從可信來源準備 `models/seg/model.tflite` 和 `face_landmarker.task`。這些模型不一定隨 Git 取得；請在建置映像**之前**放好。extraction 禁網，無法在處理時下載 MediaPipe 模型。
- 以專案根目錄執行以下指令，並準備足夠磁碟空間。建置映像及下載 AI 依賴可能非常耗時；本機 Python 虛擬環境不會被容器共用。

Pi 上曾使用 OV5647、Debian 13 ARM64、Python 3.11、LiteRT 1.4.0 和舊版 MediaPipe 執行單張真實影像。此紀錄不是對所有硬體、資料、版本或 SELinux 的驗證；請在目標 Pi 上重新測試。

## 建立 Pi 專用映像

`docker-compose.pi.yml` 為三個服務啟用 `PI_ARM64` build argument。它使用 `requirements-pi-overrides.txt`，不改變其他平台預設的依賴安裝；`INSTALL_TFLITE=1` 會在 extraction 映像安裝 LiteRT。

```bash
ls -lh models/seg/model.tflite face_landmarker.task
sudo env INSTALL_TFLITE=1 SEG_BACKEND=tflite docker compose -f docker-compose.yml -f docker-compose.pi.yml build
```

建置失敗就停止並檢查錯誤，不要以安裝依賴完成或部分映像存在當作成功。模型或程式碼更新後需重新建置；相機執行指令使用 `--no-build`。

## 一鍵拍照

Pi 桌面或 VNC 終端機中執行：

```bash
cd ~/edge-deid-sec
bash camera-run.sh
```

指令需要 `sudo`；輸入密碼後預覽 5 秒並拍攝 640 × 480。程式建立獨立執行目錄，以 UID/GID `10001` 建立容器輸出目錄；不要同時執行另一個使用相同 Compose 服務名稱的批次。完成後會檢查三服務退出狀態、metadata 與 validation CSV，並開啟 `deid.png`。

- 路徑印在終端機：`data/camera-runs/run-.../`。
- `raw/tongue.jpg` 是**原始照片**；`out/tongue/` 包含 ROI、mask、`deid.png`、`feature_256.npy` 與 `meta.json`。
- 隱私與輸出報告在 `evidence/batch/`，ROI 報告在該次 `docs/`。舊資料和原本 `docs/roi_eval.md` 不會被本流程覆寫。
- 這些資料可能包含臉部、ROI 或可辨識特徵，已在 `.gitignore` 排除；請設定存取權、保留期限與備份政策。
- 預測遮罩與隱私數字不足以證明完全匿名；仍須檢查分割是否誤留嘴唇或牙齒。

若預覽或拍照失敗，Docker 不會啟動。若容器、品質、隱私或輸出驗證失敗，程式會回報錯誤並保留本次資料供檢查。若只開啟圖片失敗，可手動查看印出的結果路徑。

## Pi 網頁一鍵拍照

先完成上述模型準備、映像建置與相機測試。使用包含網頁檔案的版本；更新容器內程式碼或模型後，請先重新執行上述映像建置指令。此網頁由 Pi 宿主機執行，不需 Pi 上的 Python 虛擬環境。

在 Pi 桌面或 TigerVNC 的終端機執行（請切換到實際使用的專案目錄）：

```bash
cd ~/edge-deid-sec-new
sudo -v
python3 tools/web_camera_demo.py --pi
```

`sudo -v` 需要輸入 Pi 密碼；只有成功後才執行下一行。請在**同一個終端機**保持伺服器執行，在 Pi 桌面瀏覽器開啟 `http://127.0.0.1:8765/`。設定拍照倒數（1–60 秒，預設 5 秒），按「拍照並處理」，Pi 的 Qt 相機預覽會在桌面**另一個視窗**顯示設定的時間，不會嵌入網頁；接著執行原本的 Docker acquisition、Unix Socket extraction（TFLite）及 observability 流程。三個服務、品質、隱私和輸出驗證通過後，網頁才顯示結果。停止伺服器請回到該終端機按 Ctrl+C。

如需記錄 OpenTelemetry spans，在執行 `sudo -v` 後改用以下指令啟動網頁（不設定時預設關閉）：

```bash
EDGE_DEID_TRACING=console python3 tools/web_camera_demo.py --pi
```

拍照完成後，在另一個 Pi 終端機執行 `sudo docker logs edge-deid-extraction` 查看最新一次 extraction 的 spans；它們不會顯示在網頁上。下一次拍照會重新建立容器，舊容器日誌不會保留，請先保存需要的紀錄。`total` span 不包含相機、Docker 啟動或驗證等待；詳細說明請看 [OpenTelemetry](OPENTELEMETRY.md)。容器映像本身必須已包含 OpenTelemetry 的程式碼與依賴。

此模式使用 `sudo -n`，不會在網頁等待密碼。若授權過期或流程失敗，請檢查終端機訊息；可停止伺服器，重新在同一終端機執行 `sudo -v` 和啟動命令。如果流程逾時，Docker 容器可能仍在執行，請先檢查容器狀態再重試。勿同時執行另一個使用相同 Compose 服務名稱的批次。

網頁只綁定 Pi 的 `127.0.0.1`，不可直接從 Windows 瀏覽器連接，也沒有設計供公開網路使用。每次的原始照片和輸出仍保存在 `data/camera-runs/`，須按敏感資料保護。此功能尚需在目標 Pi 的相機、桌面和 Docker 環境中實際驗證；不會啟用 SELinux。

## 記憶體限制與 SELinux

Pi 的 `cgroup.controllers` 必須包含 `memory`，Docker 記憶體上限才可生效；若 Docker 警告限制被忽略，先檢查核心及開機參數，再依目標系統安全調整。不要將設定的數值當作實際限制已生效的證據。

SELinux 是另一項獨立驗證。某次 Pi 的核心設定為 `CONFIG_SECURITY_SELINUX is not set`，該核心無法啟用 SELinux；更換系統或核心及套用候選政策前，應備份並確認相機與 Docker 相容。完整限制與驗證步驟請參考 [W10 安全隔離](WEEK10_SECURITY.md)。
