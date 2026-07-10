"""
dataset_split.py — Reproducible Dataset Split for ACM Paper RQ1
================================================================
Creates or loads a **fixed split manifest** that assigns every dataset
sample to exactly one of: train, val, test.

All four models (U-Net + MobileNetV2, U-Net + ResNet34,
DeepLabV3+ + ResNet50, YOLOv8n-seg) MUST use the exact same split.

Split policy
------------
- **Roboflow / predefined structure**: if the dataset already contains
  separate ``train/``, ``valid/`` (or ``val/``), and ``test/`` directories,
  those splits are preserved.  The actual ratios are reported honestly —
  they are NOT silently claimed to be 70/15/15 if they differ.
- **Flat structure**: a deterministic random 70/15/15 split is applied
  using a configurable seed.  Once generated the manifest is never
  re-created automatically (load it instead).

Manifest location
-----------------
Default: ``outputs/acm_paper/rq1/split_manifest.json``

The manifest records for every sample:
  - ``id``             : unique string identifier
  - ``image_path``     : path relative to data_dir (forward slashes)
  - ``source_split``   : original split directory (``"train"``, ``"valid"``,
                          ``"test"``, or ``""`` for flat datasets)
  - ``assigned_split`` : ``"train"`` | ``"val"`` | ``"test"``

Usage
-----
::

    python -m experiments.acm_paper.rq1_model_selection.dataset_split \\
        --data-dir /path/to/dataset \\
        --manifest outputs/acm_paper/rq1/split_manifest.json \\
        --seed 42

    # Validate an existing manifest
    python -m experiments.acm_paper.rq1_model_selection.dataset_split \\
        --data-dir /path/to/dataset \\
        --manifest outputs/acm_paper/rq1/split_manifest.json \\
        --validate-only
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Allow running as python -m experiments.acm_paper.rq1_model_selection.dataset_split
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve()
_PROJECT_ROOT = _HERE.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from src.seg.dataset import TongueSegDataset
except ImportError:
    TongueSegDataset = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MANIFEST_PATH = "outputs/acm_paper/rq1/split_manifest.json"
MANIFEST_VERSION = "1.0"

# Default 70 / 15 / 15 split
DEFAULT_TRAIN_RATIO = 0.70
DEFAULT_VAL_RATIO = 0.15
DEFAULT_TEST_RATIO = 0.15


# ---------------------------------------------------------------------------
# Dataset format detection
# ---------------------------------------------------------------------------

def detect_dataset_format(data_dir: Path) -> str:
    """
    Detect the dataset layout under data_dir.

    Returns
    -------
    "roboflow"  : predefined train/ (+ valid/val/ + optional test/) directories
    "flat"      : flat images/ + masks/ (or images/ only)
    "unknown"   : nothing recognisable found
    """
    if (data_dir / "train").is_dir():
        return "roboflow"
    if (data_dir / "images").is_dir():
        return "flat"
    # Some Roboflow exports put images directly in train/images/
    if any((data_dir / s).is_dir() for s in ("train", "valid", "val", "test")):
        return "roboflow"
    return "unknown"


# ---------------------------------------------------------------------------
# Sample enumeration
# ---------------------------------------------------------------------------

def _load_split_samples(
    data_dir: Path,
    split_name: str,
    assigned_split: str,
) -> List[Dict]:
    """
    Load all samples from one split directory using TongueSegDataset.

    Parameters
    ----------
    data_dir : Path
    split_name : str
        Argument passed to TongueSegDataset (e.g. "train", "valid", "test").
    assigned_split : str
        The canonical split label stored in the manifest ("train"/"val"/"test").
    """
    if TongueSegDataset is None:
        raise ImportError(
            "Cannot import TongueSegDataset from src.seg.dataset.  "
            "Make sure the project root is on sys.path."
        )
    ds = TongueSegDataset(
        str(data_dir),
        split=split_name,
        img_size=256,
        is_train=False,
    )
    samples = []
    for i, raw in enumerate(ds._samples):
        img_path = Path(raw["image_path"])
        try:
            rel = img_path.relative_to(data_dir)
        except ValueError:
            rel = img_path  # fallback: keep as-is
        sample_id = f"{assigned_split}_{i:06d}"
        samples.append(
            {
                "id": sample_id,
                "image_path": str(rel).replace("\\", "/"),
                "source_split": split_name,
                "assigned_split": assigned_split,
            }
        )
    return samples


def _enumerate_all_samples_roboflow(data_dir: Path) -> Tuple[List[Dict], Dict]:
    """
    Enumerate samples for a predefined Roboflow split.

    Returns
    -------
    (samples, split_counts)
    """
    samples: List[Dict] = []

    # Train (required)
    train_samples = _load_split_samples(data_dir, "train", "train")
    samples.extend(train_samples)

    # Validation — Roboflow uses "valid", some exports use "val"
    val_source = "valid"
    if not (data_dir / "valid").is_dir() and (data_dir / "val").is_dir():
        val_source = "val"
    if (data_dir / val_source).is_dir():
        val_samples = _load_split_samples(data_dir, val_source, "val")
        samples.extend(val_samples)
    else:
        val_samples = []

    # Test (optional)
    if (data_dir / "test").is_dir():
        test_samples = _load_split_samples(data_dir, "test", "test")
        samples.extend(test_samples)
    else:
        test_samples = []

    split_counts = {
        "train": len(train_samples),
        "val": len(val_samples),
        "test": len(test_samples),
    }
    return samples, split_counts


def _enumerate_all_samples_flat(data_dir: Path) -> List[Dict]:
    """Enumerate all samples from a flat dataset (no sub-directories)."""
    if TongueSegDataset is None:
        raise ImportError("Cannot import TongueSegDataset from src.seg.dataset.")
    ds = TongueSegDataset(str(data_dir), split="", img_size=256, is_train=False)
    samples = []
    for i, raw in enumerate(ds._samples):
        img_path = Path(raw["image_path"])
        try:
            rel = img_path.relative_to(data_dir)
        except ValueError:
            rel = img_path
        samples.append(
            {
                "id": f"sample_{i:06d}",
                "image_path": str(rel).replace("\\", "/"),
                "source_split": "",
                "assigned_split": None,  # to be filled by splitter
            }
        )
    return samples


# ---------------------------------------------------------------------------
# Random split assignment
# ---------------------------------------------------------------------------

def _assign_random_split(
    samples: List[Dict],
    seed: int,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
    val_ratio: float = DEFAULT_VAL_RATIO,
) -> List[Dict]:
    """
    Deterministically assign train/val/test labels to flat samples.

    Parameters
    ----------
    samples : list
        Samples with ``assigned_split = None``.
    seed : int
        Random seed for reproducibility.
    train_ratio, val_ratio : float
        Proportions; test_ratio = 1 - train_ratio - val_ratio.
    """
    import random as _random
    rng = _random.Random(seed)
    shuffled = list(range(len(samples)))
    rng.shuffle(shuffled)

    n = len(shuffled)
    n_train = max(1, round(n * train_ratio))
    n_val = max(1, round(n * val_ratio))
    n_test = n - n_train - n_val
    if n_test < 1:
        # Give at least one sample to test, take from val
        n_val -= 1
        n_test = 1

    split_labels = (
        ["train"] * n_train + ["val"] * n_val + ["test"] * n_test
    )

    assigned = list(samples)
    for order_i, orig_i in enumerate(shuffled):
        assigned[orig_i] = dict(assigned[orig_i])
        assigned[orig_i]["assigned_split"] = split_labels[order_i]

    return assigned


# ---------------------------------------------------------------------------
# Manifest I/O
# ---------------------------------------------------------------------------

def _compute_actual_ratios(samples: List[Dict]) -> Dict[str, float]:
    total = len(samples)
    if total == 0:
        return {"train": 0.0, "val": 0.0, "test": 0.0}
    counts: Dict[str, int] = {"train": 0, "val": 0, "test": 0}
    for s in samples:
        label = s.get("assigned_split", "")
        if label in counts:
            counts[label] += 1
    return {k: round(v / total, 4) for k, v in counts.items()}


def _validate_no_overlap(samples: List[Dict]) -> None:
    """
    Assert that no image path appears in more than one split.

    Raises
    ------
    ValueError
        If any overlap is detected.
    """
    path_to_splits: Dict[str, List[str]] = {}
    for s in samples:
        path = s["image_path"]
        label = s.get("assigned_split", "?")
        path_to_splits.setdefault(path, []).append(label)

    overlaps = {p: v for p, v in path_to_splits.items() if len(v) > 1}
    if overlaps:
        details = "\n".join(f"  {p}: {v}" for p, v in list(overlaps.items())[:5])
        raise ValueError(
            f"Split overlap detected ({len(overlaps)} images appear in multiple splits):\n"
            f"{details}"
        )


def save_manifest(
    manifest: Dict,
    path: Path,
) -> None:
    """Save the manifest dict to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"[dataset_split] Manifest saved → {path}")


def load_manifest(path: Path) -> Dict:
    """Load and return a manifest JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    return manifest


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def create_or_load_manifest(
    data_dir: str,
    manifest_path: str = DEFAULT_MANIFEST_PATH,
    seed: int = 42,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
    val_ratio: float = DEFAULT_VAL_RATIO,
    force_recreate: bool = False,
) -> Dict:
    """
    Create a new split manifest or load an existing one.

    If ``manifest_path`` already exists and ``force_recreate=False``,
    the existing manifest is loaded without modification.

    Parameters
    ----------
    data_dir : str
        Root directory of the dataset.
    manifest_path : str
        Path where the manifest JSON will be saved/loaded.
    seed : int
        Random seed for the flat-dataset random split.
    train_ratio, val_ratio : float
        Intended proportions for flat-dataset splits.
    force_recreate : bool
        If True, always recreate the manifest (overwrite existing).

    Returns
    -------
    dict : The manifest.

    Raises
    ------
    SystemExit
        If the dataset directory is missing or no images are found.
    """
    manifest_file = Path(manifest_path)
    data_dir_path = Path(data_dir)

    # ── Load existing manifest ────────────────────────────────────────
    if manifest_file.exists() and not force_recreate:
        print(f"[dataset_split] Loading existing manifest from {manifest_file}")
        manifest = load_manifest(manifest_file)
        total = manifest.get("total_samples", 0)
        counts = manifest.get("split_counts", {})
        print(
            f"[dataset_split] Manifest: {total} samples — "
            f"train={counts.get('train', '?')}  "
            f"val={counts.get('val', '?')}  "
            f"test={counts.get('test', '?')}"
        )
        return manifest

    # ── Validate dataset exists ───────────────────────────────────────
    if not data_dir_path.is_dir():
        print(
            f"[ERROR] Dataset directory not found: {data_dir}\n"
            "The experiment framework is ready but requires real image data.\n"
            "Upload the dataset and re-run this script."
        )
        sys.exit(1)

    fmt = detect_dataset_format(data_dir_path)
    if fmt == "unknown":
        print(
            f"[ERROR] Could not detect a supported dataset format in: {data_dir}\n"
            "Supported formats:\n"
            "  - Roboflow COCO: data_dir/train/_annotations.coco.json\n"
            "  - Flat:          data_dir/images/ + data_dir/masks/\n"
        )
        sys.exit(1)

    print(f"[dataset_split] Detected format: {fmt}")

    # ── Build sample list ─────────────────────────────────────────────
    if TongueSegDataset is None:
        print(
            "[ERROR] Cannot import TongueSegDataset.  "
            "Run from the project root or add it to PYTHONPATH."
        )
        sys.exit(1)

    split_policy: str
    samples: List[Dict]
    split_counts: Dict[str, int]

    if fmt == "roboflow":
        samples, split_counts = _enumerate_all_samples_roboflow(data_dir_path)
        split_policy = "predefined"
        
        # Handle missing val and/or test directories
        missing_val = split_counts.get("val", 0) == 0
        missing_test = split_counts.get("test", 0) == 0
        
        if missing_val or missing_test:
            if missing_val and missing_test:
                print(
                    "[WARNING] No valid/ or test/ directories found in Roboflow dataset.\n"
                    "          Creating 70/15/15 split from train directory."
                )
            elif missing_val:
                print(
                    "[WARNING] No valid/ directory found in Roboflow dataset.\n"
                    "          A 15% validation split will be carved out of train."
                )
            else:
                print(
                    "[WARNING] No test/ directory found in Roboflow dataset.\n"
                    "          A 15% test split will be carved out of train."
                )
            
            # Re-assign: create val and/or test from train
            train_samples = [s for s in samples if s["assigned_split"] == "train"]
            other_samples = [s for s in samples if s["assigned_split"] != "train"]
            n_train_total = len(train_samples)
            
            import random as _random
            rng = _random.Random(seed)
            indices = list(range(n_train_total))
            rng.shuffle(indices)
            
            # Calculate split sizes
            if missing_val and missing_test:
                # Create both val and test from train (70/15/15 split)
                n_test = max(1, round(n_train_total * DEFAULT_TEST_RATIO))
                n_val = max(1, round(n_train_total * DEFAULT_VAL_RATIO))
                test_indices = set(indices[:n_test])
                val_indices = set(indices[n_test:n_test + n_val])
            elif missing_val:
                # Create only val from train
                n_val = max(1, round(n_train_total * DEFAULT_VAL_RATIO / (DEFAULT_TRAIN_RATIO + DEFAULT_VAL_RATIO)))
                test_indices = set()
                val_indices = set(indices[:n_val])
            else:
                # Create only test from train
                n_test = max(1, round(n_train_total * DEFAULT_TEST_RATIO / (DEFAULT_TRAIN_RATIO + DEFAULT_TEST_RATIO)))
                test_indices = set(indices[:n_test])
                val_indices = set()
            
            # Reassign splits
            for i, s in enumerate(train_samples):
                if i in test_indices:
                    s["assigned_split"] = "test"
                elif i in val_indices:
                    s["assigned_split"] = "val"
                # else remains "train"
            
            samples = train_samples + other_samples
            split_counts = {
                "train": sum(1 for s in samples if s["assigned_split"] == "train"),
                "val":   sum(1 for s in samples if s["assigned_split"] == "val"),
                "test":  sum(1 for s in samples if s["assigned_split"] == "test"),
            }
    else:
        # Flat
        raw_samples = _enumerate_all_samples_flat(data_dir_path)
        if not raw_samples:
            print(
                f"[ERROR] No images found in {data_dir}.\n"
                "Supported flat format: data_dir/images/*.jpg  +  data_dir/masks/*.png"
            )
            sys.exit(1)
        samples = _assign_random_split(
            raw_samples, seed=seed,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
        )
        split_policy = "random_70_15_15"
        split_counts = {
            "train": sum(1 for s in samples if s["assigned_split"] == "train"),
            "val":   sum(1 for s in samples if s["assigned_split"] == "val"),
            "test":  sum(1 for s in samples if s["assigned_split"] == "test"),
        }

    if not samples:
        print(f"[ERROR] No samples found in {data_dir}.  Cannot create manifest.")
        sys.exit(1)

    # ── Validate no overlap ────────────────────────────────────────────
    _validate_no_overlap(samples)

    # ── Compute actual ratios (honest reporting) ───────────────────────
    actual_ratios = _compute_actual_ratios(samples)
    intended_ratios = {
        "train": train_ratio,
        "val": val_ratio,
        "test": round(1.0 - train_ratio - val_ratio, 4),
    }

    if split_policy == "predefined" and actual_ratios != intended_ratios:
        print(
            f"[dataset_split] NOTE: predefined split ratios differ from 70/15/15:\n"
            f"  Actual   → train={actual_ratios['train']:.2%}  "
            f"val={actual_ratios['val']:.2%}  test={actual_ratios['test']:.2%}\n"
            f"  Intended → train={intended_ratios['train']:.2%}  "
            f"val={intended_ratios['val']:.2%}  test={intended_ratios['test']:.2%}\n"
            f"  The predefined splits are used as-is (not forced to 70/15/15)."
        )

    # ── Build manifest ─────────────────────────────────────────────────
    manifest: Dict = {
        "version": MANIFEST_VERSION,
        "seed": seed,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "dataset_dir": str(data_dir_path.resolve()),
        "dataset_format": fmt,
        "split_policy": split_policy,
        "intended_ratios": intended_ratios,
        "actual_ratios": actual_ratios,
        "total_samples": len(samples),
        "split_counts": split_counts,
        "samples": samples,
    }

    save_manifest(manifest, manifest_file)

    print(
        f"[dataset_split] Created manifest: {len(samples)} samples — "
        f"train={split_counts['train']}  val={split_counts['val']}  "
        f"test={split_counts['test']}"
    )
    return manifest


def get_split_image_paths(
    manifest: Dict,
    split: str,
    data_dir: Optional[str] = None,
) -> List[Path]:
    """
    Return absolute image paths for samples assigned to ``split``.

    Parameters
    ----------
    manifest : dict
        Loaded manifest dict.
    split : str
        "train" | "val" | "test"
    data_dir : str | None
        Override the dataset root directory stored in the manifest.

    Returns
    -------
    list[Path]  — sorted list of absolute image paths
    """
    base = Path(data_dir) if data_dir else Path(manifest.get("dataset_dir", "."))
    paths = []
    for s in manifest.get("samples", []):
        if s.get("assigned_split") == split:
            paths.append(base / s["image_path"])
    return sorted(paths)


def get_split_indices_for_dataset(
    manifest: Dict,
    dataset_samples: List[Dict],
    split: str,
    data_dir: Path,
) -> List[int]:
    """
    Find indices in a TongueSegDataset._samples list that correspond to
    the manifest entries for ``split``.

    Parameters
    ----------
    manifest : dict
        Loaded manifest.
    dataset_samples : list
        The ``_samples`` attribute from a TongueSegDataset instance.
    split : str
        "train" | "val" | "test"
    data_dir : Path
        Dataset root directory.

    Returns
    -------
    list[int]  — indices into dataset_samples
    """
    # Build lookup: relative path → dataset index
    path_to_idx: Dict[str, int] = {}
    for i, raw in enumerate(dataset_samples):
        img_path = Path(raw["image_path"])
        try:
            rel = str(img_path.relative_to(data_dir)).replace("\\", "/")
        except ValueError:
            rel = str(img_path).replace("\\", "/")
        path_to_idx[rel] = i

    indices = []
    for s in manifest.get("samples", []):
        if s.get("assigned_split") == split:
            rel = s["image_path"]
            if rel in path_to_idx:
                indices.append(path_to_idx[rel])
            else:
                # Try to find by filename only (handles path prefix differences)
                fname = Path(rel).name
                for k, v in path_to_idx.items():
                    if Path(k).name == fname:
                        indices.append(v)
                        break

    return sorted(indices)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or validate the RQ1 split manifest.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data-dir", required=True,
        help="Dataset root directory (Roboflow or flat format).",
    )
    parser.add_argument(
        "--manifest",
        default=DEFAULT_MANIFEST_PATH,
        help="Path to save/load the split manifest JSON.",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for flat-dataset 70/15/15 split.",
    )
    parser.add_argument(
        "--force-recreate", action="store_true",
        help="Re-create the manifest even if one already exists.",
    )
    parser.add_argument(
        "--validate-only", action="store_true",
        help="Only validate an existing manifest (no creation).",
    )
    args = parser.parse_args()

    if args.validate_only:
        mp = Path(args.manifest)
        if not mp.exists():
            print(f"[ERROR] Manifest not found: {mp}")
            sys.exit(1)
        manifest = load_manifest(mp)
        try:
            _validate_no_overlap(manifest.get("samples", []))
            print(f"[OK] Manifest is valid: {mp}")
            counts = manifest.get("split_counts", {})
            ratios = manifest.get("actual_ratios", {})
            print(
                f"     train={counts.get('train','?')} ({ratios.get('train',0):.1%})  "
                f"val={counts.get('val','?')} ({ratios.get('val',0):.1%})  "
                f"test={counts.get('test','?')} ({ratios.get('test',0):.1%})"
            )
        except ValueError as e:
            print(f"[FAIL] {e}")
            sys.exit(1)
        return

    create_or_load_manifest(
        data_dir=args.data_dir,
        manifest_path=args.manifest,
        seed=args.seed,
        force_recreate=args.force_recreate,
    )


if __name__ == "__main__":
    main()
