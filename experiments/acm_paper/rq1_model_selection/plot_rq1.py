"""
RQ1 Figure Generator for ACM Paper
====================================
Generates publication-quality figures from the 4 model evaluation JSONs.

Figures produced:
  1. bar_accuracy.png     — Dice / IoU / Precision / Recall grouped bar chart
  2. bar_complexity.png   — Parameters (M) + Model Size (MB) comparison
  3. scatter_tradeoff.png — Dice vs Latency scatter (accuracy–efficiency frontier)
  4. radar.png            — Radar chart (all 5 metrics, normalized)

Usage
-----
    python -m experiments.acm_paper.rq1_model_selection.plot_rq1 \
        --output-dir outputs/acm_paper/rq1/figures

All 4 result JSONs must already exist under outputs/acm_paper/rq1/.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_ORDER = [
    "unet_mobilenet",
    "unet_resnet",
    "deeplabv3",
    "yolov8n_seg",
]

DISPLAY_NAMES = {
    "unet_mobilenet": "U-Net\n+MobileNetV2",
    "unet_resnet":    "U-Net\n+ResNet34",
    "deeplabv3":      "DeepLabV3+\n+ResNet50",
    "yolov8n_seg":    "YOLOv8n\n-seg",
}

COLORS = {
    "unet_mobilenet": "#4C72B0",
    "unet_resnet":    "#DD8452",
    "deeplabv3":      "#55A868",
    "yolov8n_seg":    "#C44E52",
}

JSON_NAMES = {
    "unet_mobilenet": "unet_mobilenet.json",
    "unet_resnet":    "unet_resnet.json",
    "deeplabv3":      "deeplabv3.json",
    "yolov8n_seg":    "yolov8n_seg.json",
}

RESULT_DIR = Path("outputs/acm_paper/rq1")

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_results(result_dir: Path) -> dict:
    data = {}
    for key, fname in JSON_NAMES.items():
        p = result_dir / fname
        if not p.exists():
            raise FileNotFoundError(
                f"Result file not found: {p}\n"
                "Run evaluation first with evaluate_smp / evaluate_yolo."
            )
        with open(p, encoding="utf-8") as f:
            data[key] = json.load(f)
    return data


# ---------------------------------------------------------------------------
# Figure 1 — Accuracy bar chart (Dice, IoU, Precision, Recall)
# ---------------------------------------------------------------------------

def plot_accuracy_bars(results: dict, out_path: Path) -> None:
    metrics = ["Dice", "IoU", "Precision", "Recall"]
    metric_labels = ["Dice", "IoU", "Precision", "Recall"]

    n_models  = len(MODEL_ORDER)
    n_metrics = len(metrics)
    x = np.arange(n_metrics)
    width = 0.18

    fig, ax = plt.subplots(figsize=(9, 5))

    for i, key in enumerate(MODEL_ORDER):
        vals = [results[key].get(m, 0) for m in metrics]
        bars = ax.bar(
            x + (i - n_models / 2 + 0.5) * width,
            vals,
            width=width * 0.9,
            color=COLORS[key],
            label=DISPLAY_NAMES[key].replace("\n", " "),
            zorder=3,
        )
        for bar, val in zip(bars, vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.004,
                f"{val:.3f}",
                ha="center",
                va="bottom",
                fontsize=7,
                rotation=90,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(metric_labels, fontsize=11)
    ax.set_ylim(0.70, 1.02)
    ax.set_ylabel("Score", fontsize=11)
    ax.set_title("RQ1 — Segmentation Accuracy Comparison", fontsize=12, fontweight="bold")
    ax.legend(loc="lower right", fontsize=9, ncol=2)
    ax.yaxis.grid(True, linestyle="--", alpha=0.6, zorder=0)
    ax.set_axisbelow(True)

    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot_rq1] Saved → {out_path}")


# ---------------------------------------------------------------------------
# Figure 2 — Model complexity (parameters + size)
# ---------------------------------------------------------------------------

def plot_complexity_bars(results: dict, out_path: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5))

    names = [DISPLAY_NAMES[k].replace("\n", " ") for k in MODEL_ORDER]
    colors = [COLORS[k] for k in MODEL_ORDER]

    # Parameters (in Millions)
    params_m = []
    for k in MODEL_ORDER:
        p = results[k].get("trainable_parameter_count") or results[k].get("total_parameter_count", 0)
        params_m.append(p / 1e6)

    bars1 = ax1.bar(names, params_m, color=colors, zorder=3)
    for bar, val in zip(bars1, params_m):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.3,
            f"{val:.1f}M",
            ha="center", va="bottom", fontsize=9,
        )
    ax1.set_ylabel("Parameters (Millions)", fontsize=10)
    ax1.set_title("Model Parameter Count", fontsize=11, fontweight="bold")
    ax1.yaxis.grid(True, linestyle="--", alpha=0.6, zorder=0)
    ax1.set_axisbelow(True)
    ax1.tick_params(axis="x", labelsize=8)

    # Model size (MB) — use state dict size if available, else checkpoint size
    sizes_mb = []
    for k in MODEL_ORDER:
        sd = results[k].get("model_state_dict_size_mb", -1)
        if sd and sd > 0:
            sizes_mb.append(sd)
        else:
            sizes_mb.append(results[k].get("checkpoint_size_mb", 0))

    bars2 = ax2.bar(names, sizes_mb, color=colors, zorder=3)
    for bar, val in zip(bars2, sizes_mb):
        ax2.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            f"{val:.1f} MB",
            ha="center", va="bottom", fontsize=9,
        )
    ax2.set_ylabel("Model Size (MB)", fontsize=10)
    ax2.set_title("Model Checkpoint Size", fontsize=11, fontweight="bold")
    ax2.yaxis.grid(True, linestyle="--", alpha=0.6, zorder=0)
    ax2.set_axisbelow(True)
    ax2.tick_params(axis="x", labelsize=8)

    fig.suptitle("RQ1 — Model Complexity", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot_rq1] Saved → {out_path}")


# ---------------------------------------------------------------------------
# Figure 3 — Accuracy–Efficiency trade-off scatter
# ---------------------------------------------------------------------------

def plot_tradeoff_scatter(results: dict, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 5))

    for key in MODEL_ORDER:
        dice = results[key].get("Dice", 0)
        latency = results[key].get("mean_latency_ms_per_image", 0)
        sd = results[key].get("model_state_dict_size_mb", -1)
        size_mb = sd if (sd and sd > 0) else results[key].get("checkpoint_size_mb", 1)

        # Bubble size proportional to model size
        bubble = max(size_mb * 4, 50)

        ax.scatter(
            latency, dice,
            s=bubble,
            color=COLORS[key],
            alpha=0.85,
            edgecolors="black",
            linewidths=0.8,
            zorder=4,
        )
        ax.annotate(
            DISPLAY_NAMES[key].replace("\n", " "),
            (latency, dice),
            textcoords="offset points",
            xytext=(8, 4),
            fontsize=8.5,
        )

    ax.set_xlabel("Mean Inference Latency (ms / image, CPU)", fontsize=10)
    ax.set_ylabel("Dice Coefficient", fontsize=10)
    ax.set_title(
        "RQ1 — Accuracy vs. Latency Trade-off\n(bubble size ∝ model size)",
        fontsize=11, fontweight="bold",
    )
    ax.yaxis.grid(True, linestyle="--", alpha=0.5, zorder=0)
    ax.xaxis.grid(True, linestyle="--", alpha=0.5, zorder=0)
    ax.set_axisbelow(True)

    # Ideal-direction annotation
    ax.annotate(
        "← faster\n↑ better",
        xy=(0.02, 0.96), xycoords="axes fraction",
        fontsize=8, color="grey",
        ha="left", va="top",
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot_rq1] Saved → {out_path}")


# ---------------------------------------------------------------------------
# Figure 4 — Radar chart (all 5 metrics)
# ---------------------------------------------------------------------------

def plot_radar(results: dict, out_path: Path) -> None:
    metrics = ["Dice", "IoU", "Precision", "Recall", "Pixel Accuracy"]
    N = len(metrics)

    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]  # close the polygon

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))

    for key in MODEL_ORDER:
        vals = [results[key].get(m, 0) for m in metrics]
        vals += vals[:1]
        ax.plot(angles, vals, color=COLORS[key], linewidth=2, label=DISPLAY_NAMES[key].replace("\n", " "))
        ax.fill(angles, vals, color=COLORS[key], alpha=0.10)

    ax.set_thetagrids(np.degrees(angles[:-1]), metrics, fontsize=9)
    ax.set_ylim(0.7, 1.0)
    ax.set_yticks([0.75, 0.80, 0.85, 0.90, 0.95, 1.00])
    ax.set_yticklabels(["0.75", "0.80", "0.85", "0.90", "0.95", "1.00"], fontsize=7)
    ax.set_title("RQ1 — Segmentation Metrics (Radar)", fontsize=11, fontweight="bold", pad=15)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.15), fontsize=8)

    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot_rq1] Saved → {out_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate RQ1 figures for the ACM paper.")
    parser.add_argument(
        "--result-dir",
        default=str(RESULT_DIR),
        help="Directory containing the 4 model result JSONs.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(RESULT_DIR / "figures"),
        help="Directory to save generated figures.",
    )
    args = parser.parse_args()

    result_dir = Path(args.result_dir)
    out_dir    = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[plot_rq1] Loading results from: {result_dir}")
    results = load_results(result_dir)

    plot_accuracy_bars  (results, out_dir / "bar_accuracy.png")
    plot_complexity_bars(results, out_dir / "bar_complexity.png")
    plot_tradeoff_scatter(results, out_dir / "scatter_tradeoff.png")
    plot_radar          (results, out_dir / "radar.png")

    print(f"\n[plot_rq1] All figures saved to: {out_dir}")


if __name__ == "__main__":
    main()
