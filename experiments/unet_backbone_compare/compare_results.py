from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt


METRICS = [
    ("best_validation_dice", "Dice"),
    ("best_validation_iou", "IoU"),
    ("precision", "Precision"),
    ("recall", "Recall"),
    ("parameter_count", "Parameters"),
    ("average_inference_time_per_image", "Inference Time"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare U-Net backbone experiment summaries.")
    parser.add_argument(
        "summaries",
        nargs="*",
        default=[
            "runs/unet_backbone_compare/unet_mobilenetv2/final_summary.json",
            "runs/unet_backbone_compare/unet_resnet34/final_summary.json",
        ],
        help="Path(s) to final_summary.json files.",
    )
    parser.add_argument("--output-dir", default="runs/unet_backbone_compare", help="Where to save comparison outputs.")
    return parser.parse_args()


def load_summary(path: str | Path) -> dict:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        summary = json.load(f)
    summary["_path"] = str(path)
    return summary


def write_table(summaries: list[dict], output_path: Path) -> None:
    fieldnames = ["model_name", "encoder_name"] + [key for key, _ in METRICS] + ["summary_path"]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for summary in summaries:
            row = {
                "model_name": summary.get("model_name", "U-Net"),
                "encoder_name": summary.get("encoder_name", "unknown"),
                "summary_path": summary.get("_path", ""),
            }
            for key, _ in METRICS:
                row[key] = summary.get(key, "")
            writer.writerow(row)


def save_bar_chart(summaries: list[dict], output_path: Path) -> None:
    labels = [summary.get("encoder_name", f"run_{idx}") for idx, summary in enumerate(summaries)]
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    axes = axes.ravel()
    for ax, (key, title) in zip(axes, METRICS):
        values = [summary.get(key, 0.0) for summary in summaries]
        ax.bar(labels, values, color=["#2f6f9f", "#c06b3e", "#5b8c5a", "#8a6fb0"][: len(labels)])
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=20)
        if key in {"best_validation_dice", "best_validation_iou", "precision", "recall"}:
            ax.set_ylim(0, 1)
        ax.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries = [load_summary(path) for path in args.summaries]
    write_table(summaries, output_dir / "comparison_table.csv")
    save_bar_chart(summaries, output_dir / "comparison_bar_chart.png")
    print(f"Saved comparison outputs to {output_dir}")


if __name__ == "__main__":
    main()
