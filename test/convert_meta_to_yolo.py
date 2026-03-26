"""Convert meta.json roi_bbox -> YOLO .txt label files in data/raw/.

Reads every data/out/<id>/meta.json, converts the pixel roi_bbox to a
normalized YOLO label, and writes data/raw/<id>.txt alongside the image.

Usage:
    python test/convert_meta_to_yolo.py
    python test/convert_meta_to_yolo.py --deid_out data/out --out_dir data/raw
"""
import argparse
import json
import sys
from pathlib import Path


def bbox_to_yolo(x1, y1, x2, y2, w_img, h_img):
    """Convert pixel [x1,y1,x2,y2] to YOLO normalized (xc, yc, bw, bh)."""
    xc = (x1 + x2) / 2 / w_img
    yc = (y1 + y2) / 2 / h_img
    bw = (x2 - x1) / w_img
    bh = (y2 - y1) / h_img
    return xc, yc, bw, bh


def main():
    parser = argparse.ArgumentParser(description="Convert meta.json roi_bbox to YOLO .txt labels.")
    parser.add_argument("--deid_out", default="data/out", help="Folder containing <id>/meta.json")
    parser.add_argument("--out_dir", default="data/raw", help="Folder to write .txt label files into")
    parser.add_argument("--class_id", type=int, default=0, help="YOLO class id (default: 0 = tongue)")
    args = parser.parse_args()

    deid_out = Path(args.deid_out)
    out_dir = Path(args.out_dir)

    if not deid_out.exists():
        print(f"[ERR] deid_out not found: {deid_out}")
        sys.exit(1)

    meta_files = sorted(deid_out.glob("*/meta.json"))
    if not meta_files:
        print(f"[WARN] no meta.json files found under {deid_out}")
        sys.exit(0)

    ok, skipped, err = 0, 0, 0

    for meta_path in meta_files:
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[ERR ] {meta_path.parent.name}: {exc}")
            err += 1
            continue

        roi_bbox = data.get("roi_bbox")
        metrics = data.get("quality_gate", {}).get("metrics", {})
        w_img = metrics.get("width")
        h_img = metrics.get("height")

        if not roi_bbox or len(roi_bbox) != 4:
            print(f"[SKIP] {meta_path.parent.name}: missing or invalid roi_bbox")
            skipped += 1
            continue
        if not w_img or not h_img:
            print(f"[SKIP] {meta_path.parent.name}: missing width/height in metrics")
            skipped += 1
            continue

        x1, y1, x2, y2 = roi_bbox
        if x2 <= x1 or y2 <= y1:
            print(f"[SKIP] {meta_path.parent.name}: degenerate roi_bbox {roi_bbox}")
            skipped += 1
            continue

        xc, yc, bw, bh = bbox_to_yolo(x1, y1, x2, y2, w_img, h_img)

        input_file = data.get("input_file", meta_path.parent.name + ".jpg")
        stem = Path(input_file).stem
        label_path = out_dir / f"{stem}.txt"

        label_line = f"{args.class_id} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}\n"
        label_path.write_text(label_line, encoding="utf-8")

        roi_method = data.get("roi_method_used", "?")
        print(f"[OK  ] {stem}.txt  bbox={roi_bbox}  size={w_img}x{h_img}  method={roi_method}")
        ok += 1

    print(f"\nDone. written={ok}  skipped={skipped}  error={err}")
    print(f"Label files -> {out_dir.resolve()}")


if __name__ == "__main__":
    main()
