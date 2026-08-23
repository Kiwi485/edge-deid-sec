from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from random import Random

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.ipc import DEFAULT_SOCKET_PATH, send_job  # noqa: E402

VALID_EXT = {".jpg", ".jpeg", ".png", ".heic"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build acquisition manifest from raw images.")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("evidence/batch/acquisition_manifest.json"),
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--socket-path", type=str, default=DEFAULT_SOCKET_PATH)
    parser.add_argument("--socket-mode", action="store_true", help="Send each task via Unix socket instead of only writing a manifest.")
    parser.add_argument("--ipc-report", type=Path, default=Path("evidence/batch/ipc_report.csv"))
    parser.add_argument("--ipc-summary", type=Path, default=Path("evidence/batch/ipc_summary.md"))
    return parser.parse_args()


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = round((len(ordered) - 1) * percentile)
    return ordered[index]


def main() -> None:
    args = parse_args()
    args.manifest.parent.mkdir(parents=True, exist_ok=True)

    if not args.raw_dir.exists():
        raise FileNotFoundError(f"raw_dir not found: {args.raw_dir}")

    images = sorted(
        [
            p
            for p in args.raw_dir.iterdir()
            if p.is_file() and p.suffix.lower() in VALID_EXT
        ],
        key=lambda p: p.name,
    )

    if args.shuffle:
        rng = Random(args.seed)
        rng.shuffle(images)

    if args.limit > 0:
        images = images[: args.limit]

    payload = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "raw_dir": str(args.raw_dir),
        "limit": args.limit,
        "shuffle": args.shuffle,
        "seed": args.seed,
        "total": len(images),
        "items": [
            {
                "image_id": p.stem,
                "input_file": p.name,
            }
            for p in images
        ],
    }

    with open(args.manifest, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    if args.socket_mode:
        args.ipc_report.parent.mkdir(parents=True, exist_ok=True)
        ipc_rows = []
        for item in payload["items"]:
            job = {
                "job_id": item["image_id"],
                "image_id": item["image_id"],
                "input_file": item["input_file"],
                "raw_dir": str(args.raw_dir),
                "out_dir": "data/out",
                "csv": "logs/pipeline_latency_vm.csv",
                "manifest": str(args.manifest),
            }
            started = time.perf_counter()
            response = send_job(args.socket_path, job)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            ipc_ms = float(response.get("ipc_ms", elapsed_ms))
            processing_ms = float(response.get("processing_ms", 0.0))
            round_trip_ms = float(response.get("round_trip_ms", elapsed_ms))
            ipc_rows.append(
                {
                    "job_id": job["job_id"],
                    "input_file": job["input_file"],
                    "status": response.get("status", "unknown"),
                    "ipc_ms": ipc_ms,
                    "processing_ms": processing_ms,
                    "round_trip_ms": round_trip_ms,
                }
            )
            print(
                f"job={job['job_id']} "
                f"status={response.get('status', 'unknown')} "
                f"ipc_ms={ipc_ms:.2f} "
                f"processing_ms={processing_ms:.2f} "
                f"round_trip_ms={round_trip_ms:.2f}"
            )

        with open(args.ipc_report, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(ipc_rows[0].keys()) if ipc_rows else ["job_id", "input_file", "status", "ipc_ms", "processing_ms", "round_trip_ms"])
            writer.writeheader()
            writer.writerows(ipc_rows)

        ipc_values = [float(row["ipc_ms"]) for row in ipc_rows]
        mean_ms = sum(ipc_values) / len(ipc_values) if ipc_values else 0.0
        p50_ms = _percentile(ipc_values, 0.50)
        p95_ms = _percentile(ipc_values, 0.95)
        target_met = bool(ipc_values) and p95_ms <= 5.0
        args.ipc_summary.parent.mkdir(parents=True, exist_ok=True)
        args.ipc_summary.write_text(
            "\n".join(
                [
                    "# Unix Socket IPC Summary",
                    "",
                    f"- Jobs: {len(ipc_rows)}",
                    f"- Mean ipc_ms: {mean_ms:.3f}",
                    f"- p50 ipc_ms: {p50_ms:.3f}",
                    f"- p95 ipc_ms: {p95_ms:.3f}",
                    "- Target: 3-5 ms (accepted when p95 <= 5 ms)",
                    f"- Target met: {'yes' if target_met else 'no'}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        print("acquisition socket completed")
        print(f"total={len(images)}")
        print(f"manifest={args.manifest}")
        print(f"ipc_report={args.ipc_report}")
        print(f"ipc_summary={args.ipc_summary}")
        return

    print("acquisition completed")
    print(f"total={len(images)}")
    print(f"manifest={args.manifest}")


if __name__ == "__main__":
    main()
