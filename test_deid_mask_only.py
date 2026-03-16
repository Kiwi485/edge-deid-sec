from pathlib import Path

from deid_mask_only import run_from_paths

# 改成你自己的路徑
IMAGE_PATH = "data/in/A (358).jpg"
MASK_PATH = "data/in/A (358)_mask.png"
OUTPUT_DIR = "data/out/A_358"


def main() -> None:
    meta = run_from_paths(IMAGE_PATH, MASK_PATH, OUTPUT_DIR)
    print("done")
    print(meta)
    print(f"check: {Path(OUTPUT_DIR) / 'deid.png'}")
    print(f"check: {Path(OUTPUT_DIR) / 'meta.json'}")


if __name__ == "__main__":
    main()
