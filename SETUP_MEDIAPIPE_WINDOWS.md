# MediaPipe 開發環境安裝指南（Windows + VS Code）

> 本文件適用於：
> - Windows 10 / 11
> - Python + MediaPipe（新版 Tasks API）
> - VS Code / VS Code Insider
>
> 目標：  
> **讓任何隊友依照本文件操作，即可成功執行 MediaPipe 攝影機測試。**

---

## 一、安裝 Python（指定版本）

### 為什麼要指定版本？
MediaPipe **目前穩定支援 Python 3.10 / 3.11**。  
Python 3.12 以上版本（3.12 / 3.13 / 3.14）可能會出現相容性問題，**請勿使用**。

### 請安裝版本
👉 **Python 3.11.6（64-bit）**

### 安裝步驟
1. 前往官方下載頁  
   https://www.python.org/downloads/

2. 找到 **Python 3.11.x**
3. 下載：
```

Download Windows installer (64-bit)

```

### 安裝時請務必勾選
- ☑ **Add Python to PATH**
- 點選 **Install Now**

---

## 二、安裝 VS Code 與 Python Extension

### 1️⃣ 安裝 VS Code
https://code.visualstudio.com/  
（或使用 VS Code Insider）

---

### 2️⃣ 安裝 Python Extension（正式版）
在 VS Code Extensions（左側四個方塊）搜尋：

```

Python (by Microsoft)

````

⚠️ 請使用 **正式版（stable）**，不要使用 pre-release。  
若已安裝 pre-release，請解除安裝後改為正式版。

安裝完成後請 **Reload VS Code**。

---

## 三、建立專案與虛擬環境（venv）

### 1️⃣ 開啟專案資料夾
```powershell
cd path\to\your\project
````

---

### 2️⃣ 建立虛擬環境（Python 3.11）

```powershell
python -m venv .venv311
```

建立完成後，專案結構應如下：

```
project/
├─ .venv311/
├─ README.md
```

---

### 3️⃣ 啟用虛擬環境

```powershell
.venv311\Scripts\activate
```

成功後，Terminal 前面會顯示：

```
(.venv311)
```

---

### 4️⃣ 確認 Python 版本

```powershell
python --version
```

應顯示：

```
Python 3.11.x
```

---

## 四、在 VS Code 指定使用 `.venv311`（非常重要）

即使已在 Terminal 啟用 `.venv311`，
**仍需在 VS Code 明確指定 Interpreter**，避免 Run / Debug 使用錯誤的 Python。

### Step A：選擇 Python Interpreter

1. 在 VS Code 按：

   ```
   Ctrl + Shift + P
   ```
2. 輸入並選擇：

   ```
   Python: Select Interpreter
   ```
3. 選擇：

   ```
   .venv311\Scripts\python.exe
   ```
4. VS Code 右下角應顯示：

   ```
   Python 3.11.x (.venv311)
   ```

### 若右下角未顯示

* 請確認 Status Bar 已開啟（View → Appearance → Status Bar）
* 或重新啟動 VS Code
* **最終仍以 Terminal 判斷為準**

---

## 五、安裝 MediaPipe 與必要套件

本專案提供兩種套件安裝方式，**請優先使用方式一**。

---

### ✅ 方式一（推薦）：使用 requirements.txt

若專案中已提供 `requirements.txt`，請在 **(.venv311)** 狀態下執行：

```powershell
pip install -r requirements.txt
```

此方式可確保所有成員使用**完全相同的套件與版本**。
使用此方式時，**不需要**再手動安裝 mediapipe 或 opencv。

---

### 🟡 方式二（備用）：手動安裝

若尚未提供 `requirements.txt`，請執行：

```powershell
pip install --upgrade pip
pip install mediapipe opencv-python
```

環境穩定後，建議產生套件清單供團隊使用：

```powershell
pip freeze > requirements.txt
```

---

## 六、確認套件安裝位置

```powershell
pip show mediapipe
```

應看到：

```
Location: ...\.venv311\Lib\site-packages
```

---

## 七、下載 MediaPipe 官方模型（必要）

新版 MediaPipe（Tasks API）**必須使用模型檔**。

### Hand Landmark 模型

* 檔名：`hand_landmarker.task`
* 官方下載：

```
https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
```

下載後請放在專案根目錄：

```
project/
├─ mp_test.py
├─ hand_landmarker.task
├─ .venv311/
```

---

## 八、環境確認測試（check_env.py）

執行：

```powershell
python check_env.py
```

範例輸出：

```
Python executable:
...\.venv311\Scripts\python.exe

Python version:
3.11.6 ...

MediaPipe version:
0.10.x
```

---

## 九、MediaPipe 攝影機測試

執行：

```powershell
python mp_test.py
```

---

## 成功畫面

* 攝影機視窗開啟
* 手部顯示綠色關節點
* 按 **ESC** 關閉

---

## 十、常見問題排查

### Camera not found

請嘗試將程式中的：

```python
cv2.VideoCapture(0)
```

改為：

```python
cv2.VideoCapture(1)
```

---

### module 'mediapipe' has no attribute 'solutions'

代表使用的是 **新版 MediaPipe**，
請使用本文件中的 **Tasks API 寫法**。

---

## 十一、Git 與虛擬環境說明（重要）

本專案 **不會將 `.venv311` 上傳至 GitHub**。
每位成員需在自己的電腦建立虛擬環境。

Git 中僅包含：

* 原始碼
* Setup 文件
* `requirements.txt`

---
好，下面這一段是**「可直接貼進你的 `SETUP_MEDIAPIPE_WINDOWS.md`」**的完整版內容，
標題我已經幫你寫好是 **「十二」**，語氣也已經調成「給隊友看、不會誤解」的版本。

你只要整段複製貼上即可 ✅

---

## 十二、關於虛擬環境啟用（.venv311）的重要說明

在使用本專案進行開發或執行程式前，**請務必確認已啟用虛擬環境 `.venv311`**。

---

### 為什麼需要啟用虛擬環境？

虛擬環境（venv）是用來確保：
- 使用正確的 Python 版本（3.11）
- 使用正確的套件版本（MediaPipe、OpenCV 等）
- 避免與系統或其他專案的 Python 環境衝突

---

### 什麼時候需要執行 `activate`？

👉 **每一次「新開 Terminal」時，都需要重新執行一次啟用指令**。

以下情況都屬於「需要重新啟用」：
- 關閉並重新開啟 VS Code
- 關閉並重新開啟 Terminal
- 開啟新的 Terminal 分頁
- 重新開機後第一次使用專案

---

### 啟用指令（Windows）

在專案根目錄執行：

```powershell
.venv311\Scripts\activate
````

成功後，Terminal 前面會出現：

```
(.venv311)
```

這代表目前已進入正確的虛擬環境。

---

### 如何判斷目前是否已啟用？

請觀察 Terminal 提示字首：

* 若看到：

  ```
  (.venv311)
  ```

  → 代表已啟用，**不需要再執行 activate**

* 若看到：

  ```
  PS C:\path\to\project>
  ```

  → 代表尚未啟用，**請先執行 activate**

---

### 補充說明（常見誤解）

* 在 VS Code 選擇 Python Interpreter
  👉 是讓 VS Code 知道「要用哪個 Python」

* 執行 `.venv311\Scripts\activate`
  👉 是讓 **Terminal** 使用該虛擬環境

這兩者是不同層級的設定，**建議兩者都完成**，以避免執行時使用到錯誤的 Python 環境。

---

### 建議的每日使用流程

每次開始使用本專案時，建議依序執行：

```powershell
cd path\to\project
.venv311\Scripts\activate
```

確認 Terminal 顯示 `(.venv311)` 後，再執行任何 Python 程式。






