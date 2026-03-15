import cv2
import numpy as np
import os

# 建立 data 資料夾
os.makedirs("data", exist_ok=True)

# 產生一張 640x480 的假影像（中間有一個粉紅色區塊）
img = np.zeros((480, 640, 3), dtype=np.uint8)

# 背景設為深灰
img[:] = (50, 50, 50)

# 畫一個類似舌頭顏色的橢圓（純示意）
cv2.ellipse(
    img,
    center=(320, 240),
    axes=(120, 80),
    angle=0,
    startAngle=0,
    endAngle=360,
    color=(180, 120, 160),  # BGR
    thickness=-1
)

# 存檔
cv2.imwrite("data/sample_tongue.jpg", img)

print("sample_tongue.jpg generated at data/sample_tongue.jpg")


