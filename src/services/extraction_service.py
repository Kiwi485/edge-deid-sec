from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.ipc import DEFAULT_SOCKET_PATH, serve_jobs  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run extraction pipeline from acquisition manifest.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("evidence/batch/acquisition_manifest.json"),
    )
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/out"))
    parser.add_argument("--csv", type=Path, default=Path("logs/pipeline_latency_vm.csv"))
    parser.add_argument("--clear-out", action="store_true")
    parser.add_argument("--reset-csv", action="store_true")
    parser.add_argument("--socket-path", type=str, default=DEFAULT_SOCKET_PATH)
    parser.add_argument("--socket-server", action="store_true", help="Serve a Unix socket and wait for acquisition jobs.")
    parser.add_argument("--max-requests", type=int, default=1)
    return parser.parse_args()


def _handle_job(
    job: dict,
    *,
    reset_csv: bool = False,
    clear_out: bool = False,
) -> dict:
    input_file = str(job.get("input_file", ""))
    job_id = str(job.get("job_id", "unknown"))
    if not input_file or Path(input_file).name != input_file:
        return {"status": "error", "job_id": job_id, "error": "invalid input_file"}

    raw_dir = Path(str(job.get("raw_dir", "data/raw")))
    out_dir = Path(str(job.get("out_dir", "data/out")))
    csv_path = Path(str(job.get("csv", "logs/pipeline_latency_vm.csv")))
    print(f"extraction received job={job_id} input_file={input_file}")

    started = time.perf_counter()
    try:
        from src.pipeline_local import run_batch_pipeline

        run_batch_pipeline(
            raw_dir=raw_dir,
            out_dir=out_dir,
            csv_path=csv_path,
            reset_csv=reset_csv,
            clear_out=clear_out,
            append_csv=not reset_csv,
            image_names={input_file},
        )
        meta_path = out_dir / Path(input_file).stem / "meta.json"
        with open(meta_path, "r", encoding="utf-8") as f:
            pipeline_status = json.load(f).get("status", "error")
    except Exception as exc:
        return {
            "status": "error",
            "job_id": job_id,
            "error": str(exc),
            "processing_ms": (time.perf_counter() - started) * 1000.0,
        }

    return {
        "status": pipeline_status,
        "job_id": job_id,
        "processed": True,
        "processing_ms": (time.perf_counter() - started) * 1000.0,
    }


def main() -> None:
    args = parse_args()

    if args.socket_server:
        first_job = True

        def handle_socket_job(job: dict) -> dict:
            nonlocal first_job
            response = _handle_job(
                job,
                reset_csv=args.reset_csv and first_job,
                clear_out=args.clear_out and first_job,
            )
            first_job = False
            return response

        serve_jobs(args.socket_path, handle_socket_job, max_requests=args.max_requests)
        return

    if not args.manifest.exists():
        raise FileNotFoundError(f"manifest not found: {args.manifest}")

    with open(args.manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    total = int(manifest.get("total", 0))
    shuffle = bool(manifest.get("shuffle", False))
    seed = int(manifest.get("seed", 42))

    # Legacy manifest-based batch processing path.
    from src.pipeline_local import run_batch_pipeline  # noqa: E402

    run_batch_pipeline(
        raw_dir=args.raw_dir,
        out_dir=args.out_dir,
        csv_path=args.csv,
        limit=total,
        shuffle=shuffle,
        seed=seed,
        reset_csv=args.reset_csv,
        clear_out=args.clear_out,
        append_csv=False,
    )

    print("extraction completed")
    print(f"processed={total}")
    print(f"out_dir={args.out_dir}")
    print(f"csv={args.csv}")


if __name__ == "__main__":
    main()
