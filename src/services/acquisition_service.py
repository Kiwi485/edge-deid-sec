from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from random import Random

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
    return parser.parse_args()


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

    print("acquisition completed")
    print(f"total={len(images)}")
    print(f"manifest={args.manifest}")


if __name__ == "__main__":
    main()
