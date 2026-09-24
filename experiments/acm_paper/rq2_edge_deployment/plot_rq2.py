"""
plot_rq2.py — ACM Paper RQ2: Figures from benchmark results.csv

Aggregates repeated runs (same architecture + environment_label) into
mean +/- std before plotting, since a single run is not reliable on a
shared/noisy host (see docs/acm_paper/rq2_edge_deployment.md, section on
run-to-run variance).

Figure 1: Inference Time / Peak Memory / CPU Usage across environments (error bars = std).
Figure 2: Model Size vs Runtime.
"""

from __future__ import annotations

import argparse
import csv
import statistics as st
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ENV_ORDER = ["desktop", "vm_a_2c2g", "vm_b_4c4g"]
ENV_LABELS = {
    "desktop": "Desktop",
    "vm_a_2c2g": "VM (2 Core / 2GB)",
    "vm_b_4c4g": "VM (4 Core / 4GB)",
}
MODEL_COLORS = {"unet_mobilenet": "#2E86AB", "unet_resnet": "#C73E1D"}
ARCH_LABELS = {"unet_mobilenet": "U-Net + MobileNetV2", "unet_resnet": "U-Net + ResNet34"}


def load_rows(csv_path: str):
    with open(csv_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def aggregate(rows):
    """Group by (architecture, environment_label) -> {metric: (mean, std, n)}."""
    groups = defaultdict(list)
    for r in rows:
        groups[(r["architecture"], r["environment_label"])].append(r)

    agg = {}
    metrics = ["mean_latency_ms", "peak_rss_mb", "avg_cpu_percent_normalized", "checkpoint_size_mb"]
    for key, group_rows in groups.items():
        agg[key] = {}
        for m in metrics:
            vals = [float(r[m]) for r in group_rows]
            mean = st.mean(vals)
            sd = st.stdev(vals) if len(vals) > 1 else 0.0
            agg[key][m] = (mean, sd, len(vals))
    return agg


def figure1(agg, out_path: Path):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    metrics = [
        ("mean_latency_ms", "Inference Time (ms/image)"),
        ("peak_rss_mb", "Peak Memory (MB)"),
        ("avg_cpu_percent_normalized", "CPU Usage (% of allowed cores)"),
    ]
    archs = ["unet_mobilenet", "unet_resnet"]

    for ax, (key, title) in zip(axes, metrics):
        x = range(len(ENV_ORDER))
        width = 0.35
        for i, arch in enumerate(archs):
            means, stds = [], []
            for env in ENV_ORDER:
                mean, sd, n = agg.get((arch, env), {}).get(key, (0.0, 0.0, 0))
                means.append(mean)
                stds.append(sd)
            ax.bar(
                [xi + i * width for xi in x], means, width, yerr=stds, capsize=4,
                label=ARCH_LABELS[arch], color=MODEL_COLORS[arch],
            )
        ax.set_xticks([xi + width / 2 for xi in x])
        ax.set_xticklabels([ENV_LABELS[e] for e in ENV_ORDER], rotation=15)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.3)

    axes[0].legend(loc="upper right", fontsize=8)
    fig.suptitle("Figure 1 — Runtime Comparison Across Edge Environments (mean +/- std, n=3)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[plot_rq2] Saved {out_path}")


def figure2(agg, out_path: Path):
    fig, ax = plt.subplots(figsize=(6.5, 5))
    archs = ["unet_mobilenet", "unet_resnet"]
    markers = {"desktop": "o", "vm_a_2c2g": "s", "vm_b_4c4g": "^"}

    for arch in archs:
        for env in ENV_ORDER:
            entry = agg.get((arch, env))
            if not entry:
                continue
            size_mean, _, _ = entry["checkpoint_size_mb"]
            lat_mean, lat_sd, _ = entry["mean_latency_ms"]
            ax.errorbar(
                size_mean, lat_mean, yerr=lat_sd, fmt=markers[env], markersize=10,
                color=MODEL_COLORS[arch], capsize=4,
                label=f"{ARCH_LABELS[arch]} — {ENV_LABELS[env]}",
            )

    ax.set_xlabel("Model Size (MB)")
    ax.set_ylabel("Mean Inference Time (ms/image, +/- std over n=3)")
    ax.set_title("Figure 2 — Runtime vs Model Size")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, loc="upper left")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[plot_rq2] Saved {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-csv", default="outputs/acm_paper/rq2/results.csv")
    parser.add_argument("--output-dir", default="outputs/acm_paper/rq2/figures")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = load_rows(args.results_csv)
    agg = aggregate(rows)

    figure1(agg, out_dir / "figure1_runtime_comparison.png")
    figure2(agg, out_dir / "figure2_runtime_vs_model_size.png")


if __name__ == "__main__":
    main()
