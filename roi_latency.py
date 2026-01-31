import cv2
import time
import csv
import os
import psutil

os.makedirs("logs", exist_ok=True)
log_path = os.path.join("logs", "latency.csv")

cap = cv2.VideoCapture(0)
process = psutil.Process()

with open(log_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["frame", "latency_ms", "cpu_percent", "ram_mb"])

    frame_id = 0
    MAX_FRAMES = 100

    while cap.isOpened() and frame_id < MAX_FRAMES:
        ret, frame = cap.read()
        if not ret:
            break

        t0 = time.perf_counter()

        # TODO: 下一步再加 ROI 偵測（先確認最小版能跑）
        h, w, _ = frame.shape
        roi = frame[int(h*0.4):int(h*0.7), int(w*0.3):int(w*0.7)]
        _ = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000

        cpu = psutil.cpu_percent(interval=None)
        ram_mb = process.memory_info().rss / (1024 * 1024)

        writer.writerow([frame_id, f"{latency_ms:.2f}", cpu, f"{ram_mb:.2f}"])
        print(f"Frame {frame_id}: {latency_ms:.2f} ms | CPU {cpu}% | RAM {ram_mb:.2f} MB")

        frame_id += 1

cap.release()
print(f"Saved log to: {log_path}")
