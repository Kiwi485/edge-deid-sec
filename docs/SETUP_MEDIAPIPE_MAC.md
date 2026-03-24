下面是**已經改成 macOS 版本**的完整段落，你可以直接放成
`SETUP_MEDIAPIPE_MAC.md` 或加在 Windows 文件後面。
我把 **Mac + VS Code + venv + MediaPipe** 的流程全部改成正確的指令。

（Mac 和 Windows 最大差別主要是：`activate` 路徑與 Python 安裝方式）

---

# MediaPipe 開發環境安裝指南（macOS + VS Code）

> 本文件適用於：
>
> * macOS（Intel / Apple Silicon）
> * Python + MediaPipe（新版 Tasks API）
> * VS Code / VS Code Insider
>
> 目標：
> **讓任何隊友依照本文件操作，即可成功執行 MediaPipe 測試。**

---

# 一、安裝 Python（指定版本）

## 為什麼要指定版本？

MediaPipe **目前穩定支援 Python 3.10 / 3.11**

Python 3.12 以上版本
可能出現相容性問題，因此 **請勿使用**。

---

## 建議安裝版本

👉 **Python 3.11.6**

---

## 安裝方式（推薦 Homebrew）

如果沒有 Homebrew：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

安裝 Python 3.11：

```bash
brew install python@3.11
```

確認版本：

```bash
python3.11 --version
```

應顯示：

```
Python 3.11.x
```

---

# 二、安裝 VS Code 與 Python Extension

## 安裝 VS Code

下載：

[https://code.visualstudio.com/](https://code.visualstudio.com/)

或使用 **VS Code Insider**

---

## 安裝 Python Extension

打開 VS Code → Extensions
搜尋：

```
Python (by Microsoft)
```

⚠️ 請使用 **正式版 stable**

安裝後 **Reload VS Code**

---

# 三、建立專案與虛擬環境（venv）

## 1️⃣ 進入專案資料夾

```bash
cd path/to/your/project
```

---

## 2️⃣ 建立虛擬環境

```bash
python3.11 -m venv .venv311
```

完成後結構：

```
project/
├─ .venv311
├─ README.md
```

---

## 3️⃣ 啟用虛擬環境

Mac / Linux 使用：

```bash
source .venv311/bin/activate
```

成功後 Terminal 會顯示：

```
(.venv311)
```

---

## 4️⃣ 確認 Python 版本

```bash
python --version
```

應顯示：

```
Python 3.11.x
```

---


---

## Step A：選擇 Interpreter

按：

```
Cmd + Shift + P
```

搜尋：

```
Python: Select Interpreter
```

選擇：

```
.venv311/bin/python
```

右下角應顯示：

```
Python 3.11.x (.venv311)
```

---

# 五、安裝 MediaPipe 與必要套件

## 方法一（推薦）

如果專案已有：

```
requirements.txt
```

執行：

```bash
pip install -r requirements.txt
```

---

## 方法二（手動安裝）

```bash
pip install --upgrade pip
pip install mediapipe opencv-python
```

之後可產生：

```bash
pip freeze > requirements.txt
```

---

# 六、確認套件安裝位置

```bash
pip show mediapipe
```

應看到：

```
Location: .../.venv311/lib/python3.11/site-packages
```

---

# 七、下載 MediaPipe 模型

Tasks API 需要模型檔。

下載：

```
https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
```

放入：

```
project/
├─ mp_test.py
├─ hand_landmarker.task
├─ .venv311
```

---

# 八、環境確認測試

執行：

```bash
python check_env.py
```

範例輸出：

```
Python executable:
/Users/xxx/project/.venv311/bin/python

Python version:
3.11.6

MediaPipe version:
0.10.x
```

---

# 九、MediaPipe 測試

執行：

```bash
python mp_test.py
```

成功畫面：

* 開啟攝影機
* 手部顯示綠色關節點
* ESC 關閉

---

# 十、常見問題

## Camera not found

將：

```python
cv2.VideoCapture(0)
```

改為：

```python
cv2.VideoCapture(1)
```

---

## ModuleNotFoundError: mediapipe

代表你沒有在 `.venv311` 裡安裝套件。

請確認：

```
(.venv311)
```

並重新安裝：

```bash
pip install mediapipe
```

---

# 十一、Git 與虛擬環境說明

`.venv311` **不會上傳 GitHub**

每位成員需自行建立。

Git 只會包含：

```
source code
requirements.txt
setup files
```

---

# 十二、關於虛擬環境啟用的重要說明

在使用本專案前，**請務必確認 `.venv311` 已啟用**。

---

## 什麼時候需要重新 activate？

以下情況都需要：

* 重新開 VS Code
* 開新 Terminal
* 重新開機

---

## 啟用指令（macOS）

```bash
source .venv311/bin/activate
```

---

## 如何判斷是否啟用？

Terminal 出現：

```
(.venv311)
```

代表成功。

---

## 建議每日流程

```bash
cd path/to/project
source .venv311/bin/activate
```

確認顯示：

```
(.venv311)
```

再執行任何 Python 程式。

---

💡 **給你一個重要建議（專案管理角度）**

你的 repo 其實可以放 **兩個 setup 文件**：

```
SETUP_MEDIAPIPE_WINDOWS.md
SETUP_MEDIAPIPE_MAC.md
```

這樣 Windows / Mac 的隊友就不會互相搞混。

---

如果你願意，我可以幫你 **再升級一版成「真正專業專案等級的 setup」**，例如幫你補上：

* `.gitignore`（避免 venv 被 commit）
* `requirements.txt` 標準版本
* `check_env.py`
* `mp_test.py`
* `Makefile` / `setup.sh`

那個會變成 **ICPC / research lab 等級的 repo 結構**，隊友基本不可能裝壞環境。
