"""Simple manual YOLO bbox annotator using OpenCV.

Usage (from project root):

    .\.venv311\Scripts\python.exe test\manual_yolo_annotator.py --input data/raw

Controls:
    - 左鍵拖曳：畫出一個 bbox
    - s：存檔目前 bbox 到 YOLO .txt（class 0），跳到下一張
    - n：直接跳到下一張（不存 bbox）
    - q：離開程式

This is a lightweight replacement for LabelImg when it is unstable
on some Windows environments. It writes standard YOLO txt files
compatible with src.roi.roi_yolo.load_yolo_bbox.
"""

import argparse
from pathlib import Path

import cv2


VALID_EXT = {".jpg", ".jpeg", ".png"}


def to_yolo_norm(x1, y1, x2, y2, w_img, h_img):
    """Convert pixel bbox to YOLO normalized (class 0)."""
    x1, y1, x2, y2 = map(float, (x1, y1, x2, y2))

    x1 = max(0.0, min(x1, w_img - 1.0))
    y1 = max(0.0, min(y1, h_img - 1.0))
    x2 = max(x1 + 1.0, min(x2, w_img))
    y2 = max(y1 + 1.0, min(y2, h_img))

    bw = x2 - x1
    bh = y2 - y1
    xc = x1 + bw / 2.0
    yc = y1 + bh / 2.0

    return (
        xc / w_img,
        yc / h_img,
        bw / w_img,
        bh / h_img,
    )


def annotate_folder(in_dir: Path, start_index: int = 0):
    images = sorted(p for p in in_dir.iterdir() if p.suffix.lower() in VALID_EXT)
    if not images:
        print(f"[WARN] no images found in {in_dir}")
        return

    print("Controls: left-drag to draw bbox, 's' save & next, 'n' next, 'q' quit")

    current_bbox = None  # (x1, y1, x2, y2)
    drawing = False
    ix, iy = -1, -1

    def mouse_cb(event, x, y, flags, param):
        nonlocal ix, iy, drawing, current_bbox, vis

        if event == cv2.EVENT_LBUTTONDOWN:
            drawing = True
            ix, iy = x, y
            current_bbox = None
        elif event == cv2.EVENT_MOUSEMOVE and drawing:
            vis = image.copy()
            cv2.rectangle(vis, (ix, iy), (x, y), (0, 255, 0), 2)
        elif event == cv2.EVENT_LBUTTONUP:
            drawing = False
            x1, y1 = min(ix, x), min(iy, y)
            x2, y2 = max(ix, x), max(iy, y)
            current_bbox = (x1, y1, x2, y2)
            vis = image.copy()
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)

    idx = max(0, start_index)
    while idx < len(images):
        img_path = images[idx]
        label_path = img_path.with_suffix(".txt")

        print(f"[IMG ] {idx+1}/{len(images)}  {img_path.name}")

        image = cv2.imread(str(img_path))
        if image is None:
            print(f"[ERR ] cannot read image: {img_path}")
            idx += 1
            continue

        vis = image.copy()
        h_img, w_img = image.shape[:2]

        current_bbox = None
        cv2.namedWindow("annotate", cv2.WINDOW_NORMAL)
        # Use a smaller default window so it doesn't cover the whole screen.
        cv2.resizeWindow("annotate", 800, 600)
        cv2.setMouseCallback("annotate", mouse_cb)

        while True:
            cv2.imshow("annotate", vis)
            key = cv2.waitKey(20) & 0xFF

            if key == ord("q"):
                cv2.destroyAllWindows()
                return
            if key == ord("n"):
                print("[SKIP] next image")
                idx += 1
                break
            if key == ord("s"):
                if not current_bbox:
                    print("[WARN] no bbox drawn, press 'n' to skip or draw one")
                    continue

                x1, y1, x2, y2 = current_bbox
                xc, yc, bw, bh = to_yolo_norm(x1, y1, x2, y2, w_img, h_img)

                line = f"0 {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}\n"
                label_path.write_text(line, encoding="utf-8")
                print(f"[SAVE] {label_path.name}: {line.strip()}")

                idx += 1
                break

    cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="Manual YOLO bbox annotator (OpenCV)")
    parser.add_argument("--input", default="data/raw", help="Folder containing images")
    parser.add_argument("--start-index", type=int, default=0, help="Start from this 0-based index")
    args = parser.parse_args()

    in_dir = Path(args.input)
    if not in_dir.exists():
        raise SystemExit(f"input folder not found: {in_dir}")

    annotate_folder(in_dir, start_index=args.start_index)


if __name__ == "__main__":
    main()
