from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run observability reports after extraction.")
    parser.add_argument("--python", type=str, default="python")
    parser.add_argument("--manifest", type=Path, default=None)
    return parser.parse_args()


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, cwd=str(BASE_DIR), check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}")


def main() -> None:
    args = parse_args()

    _run([args.python, "src/update_roi_eval.py"])
    _run([args.python, "src/privacy/evaluate_batch.py"])
    validate_cmd = [args.python, "src/validate_outputs.py"]
    if args.manifest is not None:
        validate_cmd.extend(["--manifest", str(args.manifest)])
    _run(validate_cmd)

    print("observability completed")
    print("updated: docs/roi_eval.md, evidence/batch/privacy_summary.md, evidence/batch/validation_summary.csv")


if __name__ == "__main__":
    main()
