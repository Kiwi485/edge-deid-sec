from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

try:
    from src.privacy.deid_metrics import PrivacyConfig, evaluate_privacy
except ImportError:
    from deid_metrics import PrivacyConfig, evaluate_privacy

# cv2.imread cannot decode HEIC; fall back to pillow_heif like pipeline_local.
try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    _HEIF_OK = True
except ImportError:
    _HEIF_OK = False


VALID_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".heic")


def _load_raw(path: Path) -> np.ndarray | None:
    if path.suffix.lower() == ".heic":
        if not _HEIF_OK:
            return None
        from PIL import Image

        img = Image.open(path).convert("RGB")
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    return cv2.imread(str(path), cv2.IMREAD_COLOR)


def _read_json(path: Path) -> Dict[str, object]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload: Dict[str, object]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _find_raw_path(raw_dir: Path, image_id: str, input_file: str) -> Path | None:
    if input_file:
        p = raw_dir / input_file
        if p.exists():
            return p

    for ext in VALID_EXT:
        p = raw_dir / f"{image_id}{ext}"
        if p.exists():
            return p
    return None


def _fmt_pct(x: float) -> str:
    return f"{x * 100.0:.2f}%"


def _fmt_num(x: float) -> str:
    return f"{x:.6f}"


def _align_to_deid_size(
    raw: np.ndarray,
    deid: np.ndarray,
    mask: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Align raw/mask to deid spatial size to match pipeline resize behavior."""
    h, w = deid.shape[:2]

    if raw.shape[:2] != (h, w):
        # Must match pipeline_local's cv2.resize default (INTER_LINEAR),
        # otherwise interpolation differences show up as false retention loss.
        raw = cv2.resize(raw, (w, h), interpolation=cv2.INTER_LINEAR)

    if mask.shape[:2] != (h, w):
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)

    return raw, deid, mask


def evaluate_one_bundle(
    bundle_dir: Path,
    raw_dir: Path,
    cfg: PrivacyConfig,
) -> Tuple[Dict[str, object], str]:
    image_id = bundle_dir.name
    meta_path = bundle_dir / "meta.json"
    deid_path = bundle_dir / "deid.png"
    mask_path = bundle_dir / "mask.png"

    base = {
        "image_id": image_id,
        "input_file": "",
        "pipeline_status": "",
        "privacy_ok": False,
        "background_leak_ratio": float("nan"),
        "retention_completeness": float("nan"),
        "privacy_risk_score": float("nan"),
        "privacy_issues": "",
    }

    if not meta_path.exists():
        base["privacy_issues"] = "meta_missing"
        return base, "error"

    meta = _read_json(meta_path)
    input_file = str(meta.get("input_file") or "")
    base["input_file"] = input_file
    base["pipeline_status"] = str(meta.get("status") or "")

    raw_path = _find_raw_path(raw_dir, image_id, input_file)
    if raw_path is None:
        base["privacy_issues"] = "raw_missing"
        return base, "error"
    if not deid_path.exists():
        base["privacy_issues"] = "deid_missing"
        return base, "error"
    if not mask_path.exists():
        base["privacy_issues"] = "mask_missing"
        return base, "error"

    raw = _load_raw(raw_path)
    deid = cv2.imread(str(deid_path), cv2.IMREAD_COLOR)
    mask = cv2.imread(str(mask_path), cv2.IMREAD_UNCHANGED)

    if raw is None or deid is None or mask is None:
        missing = []
        if raw is None:
            missing.append("raw_read_fail")
        if deid is None:
            missing.append("deid_read_fail")
        if mask is None:
            missing.append("mask_read_fail")
        base["privacy_issues"] = ";".join(missing)
        return base, "error"

    raw, deid, mask = _align_to_deid_size(raw, deid, mask)

    try:
        metrics = evaluate_privacy(raw, deid, mask, cfg)
    except Exception as exc:
        base["privacy_issues"] = f"privacy_eval_error:{exc}"
        return base, "error"

    base["privacy_ok"] = bool(metrics["privacy_pass"])
    base["background_leak_ratio"] = float(metrics["background_leak_ratio"])
    base["retention_completeness"] = float(metrics["retention_completeness"])
    base["privacy_risk_score"] = float(metrics["privacy_risk_score"])
    base["privacy_issues"] = ";".join(metrics["privacy_issues"])

    meta["privacy_metrics"] = metrics
    _write_json(meta_path, meta)

    return base, "ok"


def _mean(values: List[float]) -> float:
    if not values:
        return float("nan")
    return float(np.mean(np.array(values, dtype=np.float64)))


def write_report_csv(rows: List[Dict[str, object]], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "image_id",
        "input_file",
        "pipeline_status",
        "privacy_ok",
        "background_leak_ratio",
        "retention_completeness",
        "privacy_risk_score",
        "privacy_issues",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_summary_md(rows: List[Dict[str, object]], md_path: Path) -> None:
    md_path.parent.mkdir(parents=True, exist_ok=True)

    total = len(rows)
    ok_count = sum(1 for r in rows if bool(r["privacy_ok"]))
    fail_count = total - ok_count
    pass_rate = (ok_count / total) if total else 0.0

    leak_vals = [
        float(r["background_leak_ratio"])
        for r in rows
        if isinstance(r.get("background_leak_ratio"), float)
        and np.isfinite(float(r["background_leak_ratio"]))
    ]
    ret_vals = [
        float(r["retention_completeness"])
        for r in rows
        if isinstance(r.get("retention_completeness"), float)
        and np.isfinite(float(r["retention_completeness"]))
    ]
    risk_vals = [
        float(r["privacy_risk_score"])
        for r in rows
        if isinstance(r.get("privacy_risk_score"), float)
        and np.isfinite(float(r["privacy_risk_score"]))
    ]

    issue_counter = Counter()
    for r in rows:
        issues = str(r.get("privacy_issues") or "").strip()
        if not issues:
            continue
        for issue in issues.split(";"):
            if issue:
                issue_counter[issue] += 1

    lines = [
        "# Privacy Summary",
        "",
        f"- Total images: {total}",
        f"- Privacy pass: {ok_count}",
        f"- Privacy fail: {fail_count}",
        f"- Privacy pass rate: {_fmt_pct(pass_rate)}",
        "",
        "## Mean Metrics",
        "",
        f"- Mean background leak ratio: {_fmt_num(_mean(leak_vals))}",
        f"- Mean retention completeness: {_fmt_num(_mean(ret_vals))}",
        f"- Mean privacy risk score: {_fmt_num(_mean(risk_vals))}",
        "",
        "## Top Issues",
    ]

    if not issue_counter:
        lines.append("- none")
    else:
        for k, v in issue_counter.most_common(10):
            lines.append(f"- {k}: {v}")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    base_dir = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Evaluate DeID privacy metrics for data/out bundles.")
    parser.add_argument("--raw-dir", type=Path, default=base_dir / "data/raw")
    parser.add_argument("--out-dir", type=Path, default=base_dir / "data/out")
    parser.add_argument("--report-csv", type=Path, default=base_dir / "evidence/batch/privacy_report.csv")
    parser.add_argument("--summary-md", type=Path, default=base_dir / "evidence/batch/privacy_summary.md")
    parser.add_argument("--black-threshold", type=int, default=8)
    parser.add_argument("--retain-tolerance", type=int, default=8)
    parser.add_argument("--leak-ref", type=float, default=0.02)
    parser.add_argument("--weight-leak", type=float, default=0.70)
    parser.add_argument("--weight-retain", type=float, default=0.30)
    parser.add_argument("--pass-leak-max", type=float, default=0.005)
    parser.add_argument("--pass-retain-min", type=float, default=0.98)
    parser.add_argument("--pass-risk-max", type=float, default=20.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    cfg = PrivacyConfig(
        black_threshold=args.black_threshold,
        retain_tolerance=args.retain_tolerance,
        leak_ref=args.leak_ref,
        weight_leak=args.weight_leak,
        weight_retain=args.weight_retain,
        pass_leak_max=args.pass_leak_max,
        pass_retain_min=args.pass_retain_min,
        pass_risk_max=args.pass_risk_max,
    )

    bundles = sorted([p for p in args.out_dir.iterdir() if p.is_dir()]) if args.out_dir.exists() else []
    rows: List[Dict[str, object]] = []
    status_counter = Counter()

    for bundle in bundles:
        row, status = evaluate_one_bundle(bundle, args.raw_dir, cfg)
        rows.append(row)
        status_counter[status] += 1

    write_report_csv(rows, args.report_csv)
    write_summary_md(rows, args.summary_md)

    print("privacy evaluation completed")
    print(f"bundles={len(rows)} ok={status_counter.get('ok', 0)} error={status_counter.get('error', 0)}")
    print(f"report_csv={args.report_csv}")
    print(f"summary_md={args.summary_md}")


if __name__ == "__main__":
    main()
