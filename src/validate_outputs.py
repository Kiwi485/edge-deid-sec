import argparse
import csv
import json
from pathlib import Path


VALID_EXT = {".jpg", ".jpeg", ".png", ".heic"}
REQUIRED_OUTPUT_FILES = ["roi.png", "mask.png", "deid.png", "feature_256.npy", "meta.json"]

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data/raw"
OUT_DIR = BASE_DIR / "data/out"
CSV_PATH = BASE_DIR / "logs/pipeline_latency_vm.csv"
SUMMARY_PATH = BASE_DIR / "evidence/batch/validation_summary.csv"

SUMMARY_FIELDS = [
    "image_id",
    "input_file",
    "has_all_files",
    "files_missing",
    "meta_ok",
    "meta_issues",
    "privacy_ok",
    "privacy_issues",
    "csv_ok",
    "csv_issues",
    "final_result",
]


def _list_raw_images(manifest_path=None):
    if not RAW_DIR.exists():
        return []
    images = [p for p in RAW_DIR.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXT]
    if manifest_path is not None:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        selected_names = {
            str(item.get("input_file", ""))
            for item in manifest.get("items", [])
            if item.get("input_file")
        }
        images = [p for p in images if p.name in selected_names]
    return sorted(images, key=lambda p: p.name)


def _load_latency_rows_by_id():
    rows_by_id = {}
    if not CSV_PATH.exists():
        return rows_by_id

    with open(CSV_PATH, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            image_id = row.get("image_id", "")
            rows_by_id.setdefault(image_id, []).append(row)
    return rows_by_id


def _check_output_files(image_id):
    bundle_dir = OUT_DIR / image_id
    missing = [name for name in REQUIRED_OUTPUT_FILES if not (bundle_dir / name).exists()]
    return len(missing) == 0, missing


def _check_meta(image_id, input_file):
    meta_path = OUT_DIR / image_id / "meta.json"
    issues = []

    if not meta_path.exists():
        return False, ["meta_missing"]

    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception:
        return False, ["meta_invalid_json"]

    if meta.get("image_id") != image_id:
        issues.append("meta_image_id_mismatch")
    if meta.get("input_file") != input_file:
        issues.append("meta_input_file_mismatch")

    if meta.get("status") == "error":
        error = str(meta.get("error") or "unknown_error")
        issues.append(f"pipeline_error:{error}")

    timing = meta.get("timing_ms")
    if not isinstance(timing, dict):
        issues.append("meta_timing_missing")

    return len(issues) == 0, issues


def _check_csv(image_id, input_file, rows_by_id):
    rows = rows_by_id.get(image_id, [])
    issues = []

    if not rows:
        issues.append("csv_row_missing")
        return False, issues

    if len(rows) > 1:
        issues.append("csv_row_duplicate")

    row = rows[0]
    if row.get("input_file") != input_file:
        issues.append("csv_input_file_mismatch")

    return len(issues) == 0, issues


def _check_privacy(meta):
    issues = []
    pm = meta.get("privacy_metrics")
    if not isinstance(pm, dict):
        return False, ["privacy_metrics_missing"]

    if "privacy_pass" not in pm:
        issues.append("privacy_pass_missing")
    elif not isinstance(pm.get("privacy_pass"), bool):
        issues.append("privacy_pass_not_bool")

    metric_keys = [
        "background_leak_ratio",
        "retention_completeness",
        "privacy_risk_score",
    ]
    for k in metric_keys:
        v = pm.get(k)
        if not isinstance(v, (int, float)):
            issues.append(f"{k}_missing_or_not_number")

    p_issues = pm.get("privacy_issues")
    if not isinstance(p_issues, list):
        issues.append("privacy_issues_not_list")

    privacy_ok = (len(issues) == 0) and bool(pm.get("privacy_pass"))

    if isinstance(p_issues, list) and p_issues:
        issues.extend([f"privacy:{str(x)}" for x in p_issues])

    return privacy_ok, issues


def build_validation_rows(manifest_path=None):
    raw_images = _list_raw_images(manifest_path)
    rows_by_id = _load_latency_rows_by_id()

    validation_rows = []
    for image in raw_images:
        image_id = image.stem
        input_file = image.name

        has_all_files, missing_files = _check_output_files(image_id)
        meta_ok, meta_issues = _check_meta(image_id, input_file)
        meta = {}
        meta_path = OUT_DIR / image_id / "meta.json"
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                meta = {}
        privacy_ok, privacy_issues = _check_privacy(meta)
        csv_ok, csv_issues = _check_csv(image_id, input_file, rows_by_id)

        final_result = "pass" if has_all_files and meta_ok and privacy_ok and csv_ok else "fail"

        validation_rows.append(
            {
                "image_id": image_id,
                "input_file": input_file,
                "has_all_files": str(has_all_files),
                "files_missing": ";".join(missing_files),
                "meta_ok": str(meta_ok),
                "meta_issues": ";".join(meta_issues),
                "privacy_ok": str(privacy_ok),
                "privacy_issues": ";".join(privacy_issues),
                "csv_ok": str(csv_ok),
                "csv_issues": ";".join(csv_issues),
                "final_result": final_result,
            }
        )

    return validation_rows


def write_summary(rows):
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows):
    total = len(rows)
    passed = sum(1 for r in rows if r["final_result"] == "pass")
    failed = total - passed

    print("Validation summary")
    print("==================")
    print(f"Total images: {total}")
    print(f"Pass: {passed}")
    print(f"Fail: {failed}")
    print(f"Output CSV: {SUMMARY_PATH}")


def parse_args():
    parser = argparse.ArgumentParser(description="Validate pipeline output bundles.")
    parser.add_argument("--manifest", type=Path, default=None)
    return parser.parse_args()


def main():
    args = parse_args()
    rows = build_validation_rows(args.manifest)
    write_summary(rows)
    print_summary(rows)


if __name__ == "__main__":
    main()
