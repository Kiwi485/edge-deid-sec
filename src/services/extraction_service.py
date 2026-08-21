from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline_local import run_batch_pipeline  # noqa: E402


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
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.manifest.exists():
        raise FileNotFoundError(f"manifest not found: {args.manifest}")

    with open(args.manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    total = int(manifest.get("total", 0))
    shuffle = bool(manifest.get("shuffle", False))
    seed = int(manifest.get("seed", 42))

    # This service executes the selected batch immediately after acquisition.
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
