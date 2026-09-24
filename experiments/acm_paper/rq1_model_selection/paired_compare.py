"""Paired per-image comparison for RQ1 model result JSON files."""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon


def _load_result(path: Path) -> dict:
    result = json.loads(path.read_text(encoding="utf-8"))
    records = result.get("per_image_records")
    if not isinstance(records, list) or not records:
        raise ValueError(f"{path} has no per_image_records")
    if any("dice" not in record for record in records):
        raise ValueError(f"{path} has a per-image record without Dice")
    result["_source_path"] = str(path)
    return result


def paired_comparison(
    first: dict,
    second: dict,
    bootstrap_repetitions: int = 10_000,
    seed: int = 42,
) -> dict:
    first_records = first["per_image_records"]
    second_records = second["per_image_records"]
    if len(first_records) != len(second_records):
        raise ValueError("paired results must contain the same number of images")
    for field in ("split_name", "split_manifest_path"):
        if first.get(field) != second.get(field):
            raise ValueError(f"paired results do not share the same {field}")

    first_dice = np.asarray([record["dice"] for record in first_records], dtype=float)
    second_dice = np.asarray([record["dice"] for record in second_records], dtype=float)
    differences = first_dice - second_dice
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(differences), size=(bootstrap_repetitions, len(differences)))
    bootstrap_means = differences[indices].mean(axis=1)
    if np.allclose(differences, 0):
        statistic, p_value = 0.0, 1.0
    else:
        test = wilcoxon(first_dice, second_dice, alternative="two-sided", method="auto")
        statistic, p_value = float(test.statistic), float(test.pvalue)

    return {
        "model_a": first.get("model_name", first.get("architecture", "model_a")),
        "model_b": second.get("model_name", second.get("architecture", "model_b")),
        "number_of_paired_images": len(differences),
        "mean_per_image_dice_a": round(float(first_dice.mean()), 6),
        "mean_per_image_dice_b": round(float(second_dice.mean()), 6),
        "mean_paired_difference_a_minus_b": round(float(differences.mean()), 6),
        "paired_bootstrap_ci_95": {
            "lower": round(float(np.quantile(bootstrap_means, 0.025)), 6),
            "upper": round(float(np.quantile(bootstrap_means, 0.975)), 6),
            "repetitions": bootstrap_repetitions,
            "seed": seed,
        },
        "wilcoxon_signed_rank": {
            "statistic": round(statistic, 6),
            "two_sided_p_value": round(p_value, 6),
        },
    }


def compare_files(paths: list[Path], bootstrap_repetitions: int = 10_000, seed: int = 42) -> dict:
    if len(paths) < 2:
        raise ValueError("provide at least two model result files")
    results = [_load_result(path) for path in paths]
    comparisons = [
        paired_comparison(a, b, bootstrap_repetitions, seed)
        for a, b in combinations(results, 2)
    ]
    return {
        "analysis": "paired per-image Dice comparison",
        "caution": "The fixed 15-image split does not measure sensitivity to data splitting or training randomness.",
        "comparisons": comparisons,
    }


def write_markdown(report: dict, path: Path) -> None:
    lines = [
        "# RQ1 Paired Per-Image Comparison",
        "",
        "| Model A | Model B | n | Mean Dice A | Mean Dice B | Paired difference (A-B) | 95% paired bootstrap CI | Wilcoxon p |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for comparison in report["comparisons"]:
        interval = comparison["paired_bootstrap_ci_95"]
        lines.append(
            f"| {comparison['model_a']} | {comparison['model_b']} | {comparison['number_of_paired_images']} | "
            f"{comparison['mean_per_image_dice_a']:.4f} | {comparison['mean_per_image_dice_b']:.4f} | "
            f"{comparison['mean_paired_difference_a_minus_b']:+.4f} | "
            f"[{interval['lower']:+.4f}, {interval['upper']:+.4f}] | "
            f"{comparison['wilcoxon_signed_rank']['two_sided_p_value']:.4f} |"
        )
    lines.extend(["", report["caution"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--bootstrap-repetitions", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args()
    report = compare_files(args.results, args.bootstrap_repetitions, args.seed)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report, args.markdown)


if __name__ == "__main__":
    main()
