import argparse
import csv
import json
import os
import random
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple


VALID_EXT = {".jpg", ".jpeg", ".png"}
REQUIRED_FILES = [
    "roi.png",
    "mask.png",
    "deid.png",
    "feature_256.npy",
    "meta.json",
]
CSV_EXPECTED_HEADER = [
    "image_id",
    "input_file",
    "roi_ms",
    "seg_ms",
    "feat_ms",
    "deid_ms",
    "total_ms",
    "status",
]


@dataclass
class ImageValidationResult:
    image_id: str
    input_file: str
    has_all_files: bool
    files_missing: str
    meta_ok: bool
    meta_issues: str
    csv_ok: bool
    csv_issues: str
    final_result: str


def load_batch_ids(raw_dir: Path) -> Dict[str, str]:
    batch: Dict[str, str] = {}
    if not raw_dir.exists():
        return batch
    for p in raw_dir.iterdir():
        if p.is_file() and p.suffix.lower() in VALID_EXT:
            batch[p.stem] = p.name
    return batch


def load_csv_index(csv_path: Path) -> Tuple[List[str], Dict[str, List[List[str]]]]:
    if not csv_path.exists():
        return [], {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return [], {}
        index: Dict[str, List[List[str]]] = {}
        for row in reader:
            if not row:
                continue
            img_id = row[0]
            index.setdefault(img_id, []).append(row)
        return header, index


def validate_meta(meta: dict, image_id: str, input_file: str) -> Tuple[bool, List[str]]:
    issues: List[str] = []

    required_keys = [
        "image_id",
        "input_file",
        "roi_method_used",
        "roi_bbox",
        "timing_ms",
        "status",
        "error",
    ]
    for k in required_keys:
        if k not in meta:
            issues.append(f"missing_key:{k}")

    if meta.get("image_id") != image_id:
        issues.append("image_id_mismatch")

    if meta.get("input_file") != input_file:
        issues.append("input_file_mismatch")

    status = meta.get("status")
    if status not in {"ok", "quality_fail", "error"}:
        issues.append("status_invalid")

    timing = meta.get("timing_ms")
    if not isinstance(timing, dict):
        issues.append("timing_ms_not_dict")
    else:
        for k in ["roi_ms", "seg_ms", "feat_ms", "deid_ms", "total_ms"]:
            v = timing.get(k)
            if not isinstance(v, (int, float)):
                issues.append(f"timing_ms_{k}_not_number")
            elif v < 0:
                issues.append(f"timing_ms_{k}_negative")

    if status != "error":
        if not meta.get("roi_method_used"):
            issues.append("roi_method_used_empty")
        roi_bbox = meta.get("roi_bbox")
        if not roi_bbox:
            issues.append("roi_bbox_empty")
    else:
        # error 狀態下，error 應該要有內容
        err = meta.get("error")
        if not err:
            issues.append("error_empty_for_error_status")

    return len(issues) == 0, issues


def validate_csv_for_image(
    image_id: str,
    input_file: str,
    status: str,
    csv_header: List[str],
    csv_index: Dict[str, List[List[str]]],
) -> Tuple[bool, List[str]]:
    issues: List[str] = []

    if not csv_header:
        issues.append("csv_missing_or_empty")
        return False, issues

    if csv_header != CSV_EXPECTED_HEADER:
        issues.append("csv_header_mismatch")

    rows = csv_index.get(image_id, [])
    if not rows:
        issues.append("csv_row_missing")
        return False, issues
    if len(rows) > 1:
        issues.append("csv_row_duplicate")

    row = rows[0]
    # 根據 CSV_EXPECTED_HEADER 順序取欄位
    csv_image_id, csv_input_file, *_timings, csv_status = row
    if csv_image_id != image_id:
        issues.append("csv_image_id_mismatch")
    if csv_input_file != input_file:
        issues.append("csv_input_file_mismatch")
    if csv_status != status:
        issues.append("csv_status_mismatch")

    return len(issues) == 0, issues


def build_evidence_pack(
    evidence_root: Path,
    batch_tag: str,
    results: List[ImageValidationResult],
    out_dir: Path,
    csv_path: Path,
    roi_eval_path: Path,
    sample_count: int,
) -> None:
    batch_dir = evidence_root / batch_tag
    samples_dir = batch_dir / "samples_for_review"
    csv_snapshot_dir = batch_dir / "csv_snapshot"

    batch_dir.mkdir(parents=True, exist_ok=True)
    samples_dir.mkdir(parents=True, exist_ok=True)
    csv_snapshot_dir.mkdir(parents=True, exist_ok=True)

    # 寫入 validation_summary.csv
    summary_path = batch_dir / "validation_summary.csv"
    with open(summary_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "image_id",
                "input_file",
                "has_all_files",
                "files_missing",
                "meta_ok",
                "meta_issues",
                "csv_ok",
                "csv_issues",
                "final_result",
            ],
        )
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))

    # 複製 CSV snapshot
    if csv_path.exists():
        shutil.copy2(csv_path, csv_snapshot_dir / csv_path.name)

    # 複製 roi_eval 報告 snapshot（若存在）
    if roi_eval_path.exists():
        shutil.copy2(roi_eval_path, batch_dir / roi_eval_path.name)

    # 準備 samples：優先選 pass 的，其次才是 fail
    pass_ids = [r.image_id for r in results if r.final_result == "pass"]
    fail_ids = [r.image_id for r in results if r.final_result != "pass"]

    chosen: List[str] = []
    for img_id in pass_ids:
        if len(chosen) >= sample_count:
            break
        chosen.append(img_id)
    for img_id in fail_ids:
        if len(chosen) >= sample_count:
            break
        if img_id not in chosen:
            chosen.append(img_id)

    # 為了可預期性，排序
    chosen = sorted(chosen)

    for img_id in chosen:
        src_folder = out_dir / img_id
        if not src_folder.exists():
            continue
        dst_folder = samples_dir / img_id
        dst_folder.mkdir(parents=True, exist_ok=True)
        for name in REQUIRED_FILES:
            src = src_folder / name
            if src.exists():
                shutil.copy2(src, dst_folder / name)


def run_validation(
    raw_dir: Path,
    out_dir: Path,
    csv_path: Path,
    evidence_dir: Path,
    batch_tag: str,
    sample_count: int,
) -> int:
    batch = load_batch_ids(raw_dir)
    csv_header, csv_index = load_csv_index(csv_path)

    if not batch:
        print(f"No input images found in {raw_dir}.")
        return 1

    results: List[ImageValidationResult] = []

    for image_id, input_file in sorted(batch.items()):
        files_missing: List[str] = []
        meta_ok = False
        meta_issues: List[str] = []
        csv_ok = False
        csv_issues: List[str] = []

        out_folder = out_dir / image_id
        if not out_folder.exists():
            files_missing.append("folder_missing")
        else:
            for name in REQUIRED_FILES:
                if not (out_folder / name).exists():
                    files_missing.append(name)

        meta = None
        meta_path = out_folder / "meta.json"
        if not meta_path.exists():
            meta_issues.append("meta_missing")
        else:
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception as e:  # pylint: disable=broad-except
                meta_issues.append(f"meta_json_error:{e}")

        status_for_csv = "unknown"
        if meta is not None:
            meta_ok, meta_issues = validate_meta(meta, image_id, input_file)
            status_for_csv = str(meta.get("status"))

        csv_ok, csv_issues = validate_csv_for_image(
            image_id=image_id,
            input_file=input_file,
            status=status_for_csv,
            csv_header=csv_header,
            csv_index=csv_index,
        )

        has_all_files = len(files_missing) == 0
        final_ok = has_all_files and meta_ok and csv_ok

        result = ImageValidationResult(
            image_id=image_id,
            input_file=input_file,
            has_all_files=has_all_files,
            files_missing=",".join(files_missing),
            meta_ok=meta_ok,
            meta_issues=",".join(meta_issues),
            csv_ok=csv_ok,
            csv_issues=",".join(csv_issues),
            final_result="pass" if final_ok else "fail",
        )
        results.append(result)

    # 簡要列印總結
    total = len(results)
    passed = sum(1 for r in results if r.final_result == "pass")
    failed = total - passed

    print("Validation summary")
    print("==================")
    print(f"Total images: {total}")
    print(f"Pass: {passed}")
    print(f"Fail: {failed}")
    print()

    if failed > 0:
        print("Failed samples (image_id: reasons)")
        for r in results:
            if r.final_result != "pass":
                reasons = [
                    r.files_missing,
                    r.meta_issues,
                    r.csv_issues,
                ]
                reason_str = ";".join(x for x in reasons if x)
                print(f"- {r.image_id}: {reason_str}")

    # 建立 evidence pack
    roi_eval_path = Path("docs") / "roi_eval.md"
    build_evidence_pack(
        evidence_root=evidence_dir,
        batch_tag=batch_tag,
        results=results,
        out_dir=out_dir,
        csv_path=csv_path,
        roi_eval_path=roi_eval_path,
        sample_count=sample_count,
    )

    return 0 if failed == 0 else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate pipeline outputs (contract) and build evidence pack.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw"),
        help="Input raw images directory.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/out"),
        help="Pipeline output directory.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("logs/pipeline_latency_vm.csv"),
        help="Pipeline latency CSV path.",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=Path("evidence"),
        help="Root directory to write evidence packs.",
    )
    parser.add_argument(
        "--batch-tag",
        type=str,
        default="batch",
        help="Tag/name for this batch (used as subfolder name).",
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=10,
        help="Number of samples to copy into samples_for_review.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    exit_code = run_validation(
        raw_dir=args.raw_dir,
        out_dir=args.out_dir,
        csv_path=args.csv,
        evidence_dir=args.evidence_dir,
        batch_tag=args.batch_tag,
        sample_count=args.sample_count,
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
