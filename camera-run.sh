#!/usr/bin/env bash
set -eu

cd "$(dirname "$0")"
umask 077

WEB_MODE=0
WAIT_SECONDS=5
if [ "$#" -gt 0 ]; then
    if [ "$#" -ne 3 ] || [ "$1" != "--web" ] || ! [[ "$2" =~ ^[0-9a-f]{32}$ ]] || ! [[ "$3" =~ ^([1-9]|[1-5][0-9]|60)$ ]]; then
        echo "ERROR: Invalid arguments." >&2
        exit 1
    fi
    WEB_MODE=1
    RUN_ID="$2"
    WAIT_SECONDS="$3"
fi

if [ ! -s models/seg/model.tflite ]; then
    echo "ERROR: models/seg/model.tflite is missing or empty." >&2
    exit 1
fi

SUDO=(sudo)
if [ "$WEB_MODE" -eq 1 ]; then
    SUDO=(sudo -n)
fi
"${SUDO[@]}" -v
mkdir -p data/camera-runs
if [ "$WEB_MODE" -eq 1 ]; then
    RUN_DIR="$PWD/data/camera-runs/run-$RUN_ID"
    mkdir "$RUN_DIR"
else
    RUN_DIR="$(mktemp -d "$PWD/data/camera-runs/run-XXXXXXXX")"
fi
mkdir -p "$RUN_DIR/raw"

echo "Results will be saved in: $RUN_DIR"
echo "Preview starts now. The photo will be taken in $WAIT_SECONDS seconds."
rpicam-still --qt-preview -t "$((WAIT_SECONDS * 1000))" --width 640 --height 480 \
    -o "$RUN_DIR/raw/tongue.jpg"

if [ ! -s "$RUN_DIR/raw/tongue.jpg" ]; then
    echo "ERROR: No photo was saved." >&2
    exit 1
fi

"${SUDO[@]}" chgrp 10001 "$RUN_DIR/raw" "$RUN_DIR/raw/tongue.jpg"
chmod 750 "$RUN_DIR/raw"
chmod 640 "$RUN_DIR/raw/tongue.jpg"
"${SUDO[@]}" install -d -m 0775 -o 10001 -g 10001 \
    "$RUN_DIR/out" "$RUN_DIR/logs" "$RUN_DIR/evidence" "$RUN_DIR/docs"

echo "Running Docker pipeline..."
"${SUDO[@]}" env CAMERA_RUN_DIR="$RUN_DIR" BATCH_LIMIT=1 \
    INSTALL_TFLITE=1 SEG_BACKEND=tflite EDGE_DEID_TRACING="${EDGE_DEID_TRACING:-off}" \
    docker compose -f docker-compose.yml -f docker-compose.camera.yml \
    up --no-build --force-recreate

for service in acquisition extraction observability; do
    state="$("${SUDO[@]}" docker inspect --format '{{.State.Status}} {{.State.ExitCode}}' "edge-deid-$service")"
    if [ "$state" != "exited 0" ]; then
        echo "ERROR: $service: $state" >&2
        exit 1
    fi
done

python3 - "$RUN_DIR/out/tongue/meta.json" \
    "$RUN_DIR/evidence/batch/validation_summary.csv" <<'PY'
import csv
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    meta = json.load(f)
with open(sys.argv[2], newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

if (
    meta.get("status") != "ok"
    or meta.get("seg_backend") != "tflite"
    or meta.get("privacy_metrics", {}).get("privacy_pass") is not True
    or len(rows) != 1
    or rows[0].get("image_id") != "tongue"
    or rows[0].get("final_result") != "pass"
):
    print("ERROR: Pipeline or validation did not pass. Check metadata and reports.", file=sys.stderr)
    sys.exit(1)

print("Pipeline and validation passed.")
PY

echo "Result folder: $RUN_DIR/out/tongue"
echo "Privacy report: $RUN_DIR/evidence/batch/privacy_report.csv"
if [ "$WEB_MODE" -eq 0 ]; then
    xdg-open "$RUN_DIR/out/tongue/deid.png"
fi
