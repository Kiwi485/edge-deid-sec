import cv2
import time
import csv
import os
import psutil
import argparse

# -----------------------------
# Arguments
# -----------------------------
parser = argparse.ArgumentParser()
parser.add_argument("--env", choices=["laptop", "vm"], default="laptop",
                    help="Execution environment: laptop (camera) or vm (static image)")
args = parser.parse_args()

# -----------------------------
# Paths
# -----------------------------
os.makedirs("logs", exist_ok=True)
log_path = os.path.join("logs", f"example_latency_{args.env}.csv")

# -----------------------------
# Process info
# -----------------------------
process = psutil.Process()
MAX_FRAMES = 100

# -----------------------------
# Input source
# -----------------------------
if args.env == "laptop":
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Camera not available on laptop")
else:
    # VM mode: use a fixed image (no camera)
    image_path = os.path.join("data", "sample_tongue.jpg")
    frame = cv2.imread(image_path)
    if frame is None:
        raise RuntimeError(f"Cannot load image: {image_path}")

# -----------------------------
# Logging
# -----------------------------
with open(log_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["frame", "latency_ms", "cpu_percent", "ram_mb"])

    for frame_id in range(MAX_FRAMES):

        if args.env == "laptop":
            ret, frame = cap.read()
            if not ret:
                break

        t0 = time.perf_counter()

        # --- ROI processing (same as original) ---
        h, w, _ = frame.shape
        roi = frame[int(h * 0.4):int(h * 0.7),
                    int(w * 0.3):int(w * 0.7)]
        _ = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000

        cpu = psutil.cpu_percent(interval=None)
        ram_mb = process.memory_info().rss / (1024 * 1024)

        writer.writerow([frame_id, f"{latency_ms:.2f}", cpu, f"{ram_mb:.2f}"])
        print(
            f"[{args.env}] Frame {frame_id}: "
            f"{latency_ms:.2f} ms | CPU {cpu}% | RAM {ram_mb:.2f} MB"
        )

if args.env == "laptop":
    cap.release()

print(f"Saved log to: {log_path}")
