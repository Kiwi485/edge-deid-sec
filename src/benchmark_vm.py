import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np


METRICS = [
    "image_load_ms",
    "resize_ms",
    "quality_ms",
    "roi_ms",
    "model_load_ms",
    "seg_preprocess_ms",
    "seg_forward_ms",
    "seg_postprocess_ms",
    "seg_ms",
    "feat_ms",
    "deid_ms",
    "artifact_write_ms",
    "privacy_ms",
    "unaccounted_ms",
    "total_ms",
]
VALID_STATUS = {"ok", "quality_fail", "error"}
PERCENTILES = [("p50", 0.50), ("p95", 0.95), ("p99", 0.99)]


@dataclass
class Row:
    image_id: str
    input_file: str
    status: str
    values: Dict[str, float]


def _to_float(x: str) -> float:
    v = float(x)
    if not np.isfinite(v) or v < 0:
        raise ValueError(f"invalid timing value: {x}")
    return v


def load_rows(csv_path: Path) -> List[Row]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    rows: List[Row] = []
    seen_image_ids = set()
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = ["image_id", "input_file", "status", *METRICS]
        missing = [k for k in required if k not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"CSV missing required columns: {','.join(missing)}")

        for idx, r in enumerate(reader, start=2):
            image_id = (r.get("image_id") or "").strip()
            input_file = (r.get("input_file") or "").strip()
            if not image_id:
                raise ValueError(f"invalid image_id at line {idx}")
            if not input_file:
                raise ValueError(f"invalid input_file at line {idx}")
            if image_id in seen_image_ids:
                raise ValueError(
                    f"duplicate image_id '{image_id}' at line {idx}; CSV must contain one row per image"
                )
            seen_image_ids.add(image_id)

            status = (r.get("status") or "").strip()
            if status not in VALID_STATUS:
                continue
            try:
                values = {m: _to_float(str(r.get(m, ""))) for m in METRICS}
            except Exception as exc:
                raise ValueError(f"invalid timing data at line {idx}: {exc}") from exc
            rows.append(
                Row(
                    image_id=image_id,
                    input_file=input_file,
                    status=status,
                    values=values,
                )
            )

    return rows


def compute_percentiles(rows: List[Row]) -> Dict[str, Dict[str, Dict[str, float]]]:
    grouped: Dict[str, List[Row]] = {
        "all": rows,
        "ok": [r for r in rows if r.status == "ok"],
        "quality_fail": [r for r in rows if r.status == "quality_fail"],
        "error": [r for r in rows if r.status == "error"],
    }

    out: Dict[str, Dict[str, Dict[str, float]]] = {}
    for group_name, group_rows in grouped.items():
        out[group_name] = {}
        for metric in METRICS:
            vals = np.array([r.values[metric] for r in group_rows], dtype=np.float64)
            if vals.size == 0:
                out[group_name][metric] = {k: float("nan") for k, _ in PERCENTILES}
                continue
            out[group_name][metric] = {
                label: float(np.quantile(vals, q))
                for label, q in PERCENTILES
            }
    return out


def format_table(title: str, stats: Dict[str, Dict[str, float]]) -> str:
    lines = [title, "metric,p50,p95,p99"]
    for metric in METRICS:
        p = stats[metric]
        lines.append(f"{metric},{p['p50']:.2f},{p['p95']:.2f},{p['p99']:.2f}")
    return "\n".join(lines)


def bottleneck_text(percentiles: Dict[str, Dict[str, Dict[str, float]]]) -> str:
    ok = percentiles["ok"]
    stage_metrics = [
        "image_load_ms",
        "resize_ms",
        "quality_ms",
        "roi_ms",
        "seg_ms",
        "feat_ms",
        "deid_ms",
        "artifact_write_ms",
        "privacy_ms",
        "unaccounted_ms",
    ]

    def _pick(metric_key: str) -> Tuple[str, float]:
        pairs = [(m, ok[m][metric_key]) for m in stage_metrics]
        pairs = [p for p in pairs if np.isfinite(p[1])]
        if not pairs:
            return "n/a", float("nan")
        return max(pairs, key=lambda x: x[1])

    top95_name, top95_val = _pick("p95")
    top99_name, top99_val = _pick("p99")
    total95 = ok["total_ms"]["p95"]
    total99 = ok["total_ms"]["p99"]

    share95 = (top95_val / total95 * 100.0) if np.isfinite(top95_val) and total95 > 0 else float("nan")
    share99 = (top99_val / total99 * 100.0) if np.isfinite(top99_val) and total99 > 0 else float("nan")

    return (
        "Bottleneck observation (status=ok):\n"
        f"- p95 main stage: {top95_name} ({top95_val:.2f} ms, {share95:.1f}% of total p95)\n"
        f"- p99 main stage: {top99_name} ({top99_val:.2f} ms, {share99:.1f}% of total p99)"
    )


def write_markdown_report(
    report_path: Path,
    csv_path: Path,
    total_rows: int,
    status_counts: Dict[str, int],
    percentiles: Dict[str, Dict[str, Dict[str, float]]],
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = []
    lines.append("# VM Benchmark v0")
    lines.append("")
    lines.append(f"- Source CSV: {csv_path.as_posix()}")
    lines.append(f"- Total rows: {total_rows}")
    lines.append(
        "- Status counts: "
        f"ok={status_counts.get('ok', 0)}, "
        f"quality_fail={status_counts.get('quality_fail', 0)}, "
        f"error={status_counts.get('error', 0)}"
    )
    lines.append("")

    for group in ["all", "ok", "quality_fail", "error"]:
        lines.append(f"## Percentiles ({group})")
        lines.append("")
        lines.append("| metric | p50 | p95 | p99 |")
        lines.append("|---|---:|---:|---:|")
        for metric in METRICS:
            p = percentiles[group][metric]
            lines.append(
                f"| {metric} | {p['p50']:.2f} | {p['p95']:.2f} | {p['p99']:.2f} |"
            )
        lines.append("")

    lines.append("## Bottleneck")
    lines.append("")
    for row in bottleneck_text(percentiles).split("\n"):
        lines.append(row)

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute VM benchmark p50/p95/p99 from pipeline latency CSV.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("logs/pipeline_latency_vm.csv"),
        help="Latency CSV path.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("results/benchmark_vm_v0.md"),
        help="Output markdown report path.",
    )
    parser.add_argument(
        "--min-rows",
        type=int,
        default=100,
        help="Minimum rows required for a formal benchmark pass.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    rows = load_rows(args.csv)
    total_rows = len(rows)
    if total_rows == 0:
        raise SystemExit("No valid benchmark rows found in CSV.")

    status_counts = {
        "ok": sum(1 for r in rows if r.status == "ok"),
        "quality_fail": sum(1 for r in rows if r.status == "quality_fail"),
        "error": sum(1 for r in rows if r.status == "error"),
    }

    percentiles = compute_percentiles(rows)

    print(format_table("[all]", percentiles["all"]))
    print()
    print(format_table("[ok]", percentiles["ok"]))
    print()
    print(format_table("[quality_fail]", percentiles["quality_fail"]))
    print()
    print(format_table("[error]", percentiles["error"]))
    print()
    print(bottleneck_text(percentiles))

    write_markdown_report(
        report_path=args.report,
        csv_path=args.csv,
        total_rows=total_rows,
        status_counts=status_counts,
        percentiles=percentiles,
    )

    if total_rows < args.min_rows:
        raise SystemExit(
            f"Benchmark row count {total_rows} is below required min-rows={args.min_rows}."
        )


if __name__ == "__main__":
    main()
