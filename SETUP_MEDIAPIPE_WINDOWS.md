s```markdown
# MediaPipe 開發環境安裝指南（Windows + VS Code）

> 本文件適用於：
> - Windows 10 / 11
> - Python + MediaPipe（新版 Tasks API）
> - VS Code / VS Code Insider
>
> 目標：  
> **讓任何隊友照做即可成功跑起 MediaPipe（攝影機測試）**

---

## 一、安裝 Python（指定版本）

### ✅ 為什麼指定版本？
MediaPipe **目前穩定支援 Python 3.10 / 3.11**  
❌ Python 3.12 / 3.13 / 3.14 可能會出現相容性問題

### 👉 請安裝：**Python 3.11.x（64-bit）**

1. 前往官方下載頁  
   https://www.python.org/downloads/

2. 找到 **Python 3.11.x**
3. 點選：
```

Download Windows installer (64-bit)

```

### ⚠️ 安裝時「一定要勾選」
- ☑ **Add Python to PATH**
- 點 **Install Now**

---

## 二、安裝 VS Code + Python Extension

### 1️⃣ 安裝 VS Code
https://code.visualstudio.com/

（或使用 VS Code Insider）

---

### 2️⃣ 安裝 Python Extension（正式版）
在 VS Code Extensions 搜尋：

```

Python (by Microsoft)

````

- ❌ 不要使用 pre-release
- ✅ 使用正式版（stable）

安裝完成後 **Reload VS Code**

---

## 三、建立專案與虛擬環境（venv）

### 1️⃣ 開啟專案資料夾
```powershell
cd path\to\your\project
````

---

### 2️⃣ 使用 Python 3.11 建立虛擬環境

```powershell
python -m venv .venv311
```

專案結構應該會變成：

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

看到提示字首：

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

## 四、安裝 MediaPipe（新版）與 OpenCV

在 **(.venv311)** 狀態下執行：

```powershell
pip install --upgrade pip
pip install mediapipe opencv-python
```

---

## 五、確認套件安裝在正確環境

```powershell
pip show mediapipe
```

應看到類似路徑：

```
Location: ...\.venv311\Lib\site-packages
```

---

## 六、下載 MediaPipe 官方模型（必要）

新版 MediaPipe（Tasks API）**必須使用模型檔**

### 👉 下載 Hand Landmark 模型：

```
hand_landmarker.task
```

官方連結：

```
https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
```

下載後放在專案根目錄：

```
project/
├─ mp_test.py
├─ hand_landmarker.task
├─ .venv311/
```

---

## 七、MediaPipe 攝影機測試（新版 API）

建立檔案 **`mp_test.py`**：

```python
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

MODEL_PATH = "hand_landmarker.task"

base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.HandLandmarkerOptions(
    base_options=base_options,
    num_hands=2
)
detector = vision.HandLandmarker.create_from_options(options)

cap = cv2.VideoCapture(0)
print("Camera opened, press ESC to quit")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=rgb
    )

    result = detector.detect(mp_image)

    if result.hand_landmarks:
        h, w, _ = frame.shape
        for hand_landmarks in result.hand_landmarks:
            for lm in hand_landmarks:
                cx, cy = int(lm.x * w), int(lm.y * h)
                cv2.circle(frame, (cx, cy), 5, (0, 255, 0), -1)

    cv2.imshow("MediaPipe Hands (New API)", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
```

執行：

```powershell
python mp_test.py
```

---

## ✅ 成功畫面

* 攝影機視窗開啟
* 手上顯示綠色關節點
* 按 **ESC** 關閉

---

## 八、常見問題排查

### ❌ Camera not found

嘗試改成：

```python
cv2.VideoCapture(1)
```

---

### ❌ module 'mediapipe' has no attribute 'solutions'

代表你使用的是 **新版 MediaPipe**
👉 **請使用本文件的 Tasks API 寫法**

---

## 九、環境正確性的最終判斷方式（最可靠）

```powershell
python --version
where python
pip show mediapipe
```

* Python 版本為 **3.11.x**
* python 路徑在 `.venv311`
* mediapipe 安裝位置在 `.venv311`

---

## 🎯 結論

只要：

* 使用 Python 3.11
* 使用 `.venv311`
* 使用 MediaPipe Tasks API

👉 **MediaPipe 在 Windows + VS Code 一定可以穩定運作**

