"""Reproducible CPU benchmark for the TFLite edge-de-identification pipeline."""

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

try:
    import resource
except ImportError:
    resource = None


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
RAW_FIELDS = (
    "mode",
    "run",
    "image_id",
    "status",
    "latency_ms",
    "segmentation_ms",
    "segmentation_forward_ms",
)
PIPELINE_TIMING_FIELDS = (
    "roi_ms",
    "seg_ms",
    "feat_ms",
    "deid_ms",
    "image_load_ms",
    "resize_ms",
    "quality_ms",
    "model_load_ms",
    "seg_preprocess_ms",
    "seg_forward_ms",
    "seg_postprocess_ms",
    "artifact_write_ms",
    "privacy_ms",
    "unaccounted_ms",
)


def _percentile(values, percentile):
    return float(np.percentile(np.asarray(values, dtype=np.float64), percentile))


def summarize_latencies(values):
    if not values:
        raise ValueError("Cannot summarize an empty set of latency values")
    mean_ms = statistics.fmean(values)
    return {
        "n": len(values),
        "mean_ms": mean_ms,
        "stddev_ms": statistics.pstdev(values),
        "median_ms": statistics.median(values),
        "p95_ms": _percentile(values, 95),
        "fps_from_mean": 1000.0 / mean_ms if mean_ms > 0 else None,
    }


def _read_cpu_info():
    path = Path("/proc/cpuinfo")
    if not path.exists():
        return None
    entries = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            entries.setdefault(key.strip(), value.strip())
    return entries.get("model name") or entries.get("Hardware") or entries.get("Model")


def _read_memory_mib():
    path = Path("/proc/meminfo")
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("MemTotal:"):
            return round(int(line.split()[1]) / 1024, 1)
    return None


def _device_tree_model():
    path = Path("/proc/device-tree/model")
    if path.exists():
        return path.read_bytes().decode("utf-8", errors="replace").strip("\x00\n ")
    return None


def _package_version(*names):
    for name in names:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return None


def peak_process_rss_mib():
    if resource is None:
        raise RuntimeError("Peak RSS measurement requires the Linux resource module")
    peak_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(peak_kib / 1024.0, 2)


def _list_images(directory, limit):
    paths = sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if limit:
        paths = paths[:limit]
    if not paths:
        raise ValueError(f"No supported images found in {directory}")
    return paths


def _pipeline_rows(csv_path, run_number):
    rows = []
    with csv_path.open(newline="", encoding="utf-8") as stream:
        for image_index, source in enumerate(csv.DictReader(stream), start=1):
            row = {
                "mode": "end_to_end",
                "run": run_number,
                "image_id": f"image_{image_index:03d}",
                "status": source["status"],
                "latency_ms": float(source["total_ms"]),
                "segmentation_ms": float(source["seg_ms"]),
                "segmentation_forward_ms": float(source["seg_forward_ms"]),
            }
            row.update({
                key: float(source[key])
                for key in PIPELINE_TIMING_FIELDS
            })
            rows.append(row)
    return rows


def _write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _environment(
    model_path, threads, device_notes, cold_load_ms, mode, warmups, runs
):
    try:
        package_list = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"Unable to capture installed package versions: {exc}") from exc
    packages = [
        f"{package['name']}=={package['version']}"
        for package in json.loads(package_list)
    ]

    model_hash = hashlib.sha256()
    with model_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            model_hash.update(chunk)

    from src.seg.tflite_inference import _load_interpreter

    interpreter, _ = _load_interpreter(str(model_path), threads)
    input_dtype = str(interpreter.get_input_details()[0]["dtype"])
    output_dtype = str(interpreter.get_output_details()[0]["dtype"])
    hardware = {
        "device_model": _device_tree_model() or "Not detected; enter in device_notes.json",
        "cpu_model": _read_cpu_info() or "Not detected; enter in device_notes.json",
        "architecture": platform.machine(),
        "logical_cpu_count": os.cpu_count(),
        "ram_total_mib": _read_memory_mib(),
        "storage_type": "Not recorded",
        "cooling_method": "Not recorded",
        "accelerator": "None requested; CPU inference",
        "power_mode": "Not recorded",
    }
    hardware.update(device_notes)
    return {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "os": platform.platform(),
        "kernel": platform.release(),
        "python": platform.python_version(),
        "runtime": "TensorFlow Lite / LiteRT",
        "runtime_package": (
            _package_version("tflite-runtime", "ai-edge-litert") or "Not detected"
        ),
        "model_format": "TensorFlow Lite FlatBuffer (.tflite)",
        "precision": f"input={input_dtype}; output={output_dtype}",
        "input_tensor_dtype": input_dtype,
        "output_tensor_dtype": output_dtype,
        "inference_threads": threads,
        "device": "CPU-only; no accelerator delegate requested",
        "benchmark": {
            "mode": mode,
            "input_resolution": "256x256",
            "batch_size": 1,
            "gradient_tracking": False,
            "model_mode": "inference",
            "warmup_inferences": warmups,
            "timed_complete_runs": runs,
            "latency_clock": "time.perf_counter (monotonic high-resolution)",
        },
        "hardware": hardware,
        "model": {
            "filename": model_path.name,
            "size_bytes": model_path.stat().st_size,
            "sha256": model_hash.hexdigest(),
            "cold_model_load_ms": cold_load_ms,
            "input_resolution": "256x256",
        },
        "peak_process_rss_mib": peak_process_rss_mib(),
        "peak_memory_definition": "Linux process maximum resident set size (ru_maxrss)",
        "python_packages": packages,
    }


def _load_notes(path):
    if path is None:
        return {}
    with path.open(encoding="utf-8") as stream:
        notes = json.load(stream)
    if not isinstance(notes, dict):
        raise ValueError("Device notes must be a JSON object")
    return notes


def _benchmark_segmentation(paths, model_path, warmups, runs, threads):
    from src.seg.tflite_inference import run_inference

    cold_load_ms = 0.0
    for index in range(warmups):
        _, _, timings = run_inference(
            str(paths[index % len(paths)]),
            str(model_path),
            img_size=256,
            return_timings=True,
            num_threads=threads,
        )
        cold_load_ms = max(cold_load_ms, timings["model_load_ms"])

    rows = []
    for run_number in range(1, runs + 1):
        for image_index, path in enumerate(paths, start=1):
            started = time.perf_counter()
            run_inference(
                str(path),
                str(model_path),
                img_size=256,
                return_timings=False,
                num_threads=threads,
            )
            latency_ms = (time.perf_counter() - started) * 1000.0
            rows.append({
                "mode": "segmentation_only",
                "run": run_number,
                "image_id": f"image_{image_index:03d}",
                "status": "ok",
                "latency_ms": latency_ms,
                "segmentation_ms": latency_ms,
                "segmentation_forward_ms": None,
            })
    return rows, cold_load_ms


def _benchmark_pipeline(paths, raw_dir, model_path, warmups, runs, threads):
    from src.pipeline_local import run_batch_pipeline

    cold_input = cv2.imread(str(paths[0]))
    if cold_input is None:
        raise ValueError(f"Unable to decode warm-up image: {paths[0]}")
    from src.seg.tflite_inference import run_inference

    cold_load_ms = 0.0
    for _ in range(warmups):
        _, _, warmup_timings = run_inference(
            "",
            str(model_path),
            image_array=cold_input,
            img_size=256,
            return_timings=True,
            num_threads=threads,
        )
        cold_load_ms = max(cold_load_ms, warmup_timings["model_load_ms"])

    with tempfile.TemporaryDirectory(prefix="edge_bench_warmup_") as temporary:
        warm_dir = Path(temporary)
        run_batch_pipeline(
            raw_dir=raw_dir,
            out_dir=warm_dir / "out",
            csv_path=warm_dir / "warmup.csv",
            limit=warmups,
            seg_backend="tflite",
            seg_model_path=model_path,
            inference_threads=threads,
        )
        warm_rows = _pipeline_rows(warm_dir / "warmup.csv", 0)
        errors = [row["image_id"] for row in warm_rows if row["status"] == "error"]
        if errors:
            raise RuntimeError(f"Pipeline warm-up failed for: {', '.join(errors)}")

    rows = []
    for run_number in range(1, runs + 1):
        with tempfile.TemporaryDirectory(prefix="edge_bench_timed_") as temporary:
            run_dir = Path(temporary)
            csv_path = run_dir / "pipeline_latency.csv"
            run_batch_pipeline(
                raw_dir=raw_dir,
                out_dir=run_dir / "outputs",
                csv_path=csv_path,
                limit=len(paths),
                seg_backend="tflite",
                seg_model_path=model_path,
                inference_threads=threads,
            )
            run_rows = _pipeline_rows(csv_path, run_number)
        errors = [row["image_id"] for row in run_rows if row["status"] == "error"]
        if errors:
            raise RuntimeError(
                f"Pipeline run {run_number} failed for: {', '.join(errors)}"
            )
        rows.extend(run_rows)
    return rows, cold_load_ms


def _summaries(rows):
    summaries = []
    group_keys = sorted({(row["mode"], row["run"]) for row in rows})
    group_keys.append(("all_runs", 0))
    for mode, run_number in group_keys:
        selected = (
            rows if mode == "all_runs"
            else [row for row in rows if row["mode"] == mode and row["run"] == run_number]
        )
        stats = summarize_latencies([row["latency_ms"] for row in selected])
        statuses = {}
        for row in selected:
            statuses[row["status"]] = statuses.get(row["status"], 0) + 1
        summaries.append({
            "mode": mode,
            "run": run_number or "pooled",
            **stats,
            "status_counts": statuses,
        })
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("segmentation", "pipeline"), required=True)
    parser.add_argument("--input-dir", type=Path, required=True,
                        help="ROI crops for segmentation, raw photos for the full pipeline.")
    parser.add_argument("--model", type=Path, default=Path("models/seg/model.tflite"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--warmups", type=int, default=10)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--device-notes", type=Path)
    args = parser.parse_args()

    if not sys.platform.startswith("linux"):
        parser.error("Run this benchmark on the Raspberry Pi's Linux OS.")
    if args.limit < 1 or args.warmups < 10 or args.runs < 3 or args.threads < 1:
        parser.error("--limit and --threads must be positive; require >=10 warmups and >=3 runs.")
    if not args.input_dir.is_dir():
        parser.error(f"Input directory does not exist: {args.input_dir}")
    if not args.model.is_file():
        parser.error(f"Model file does not exist: {args.model}")

    paths = _list_images(args.input_dir, args.limit)
    if len(paths) < args.warmups:
        parser.error(f"Need at least {args.warmups} input images; found {len(paths)}.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    dataset_hash = hashlib.sha256()
    for path in paths:
        dataset_hash.update(path.stat().st_size.to_bytes(8, "big"))
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                dataset_hash.update(chunk)
    dataset_sha256 = dataset_hash.hexdigest()

    if args.mode == "segmentation":
        rows, cold_load_ms = _benchmark_segmentation(
            paths, args.model, args.warmups, args.runs, args.threads
        )
    else:
        rows, cold_load_ms = _benchmark_pipeline(
            paths, args.input_dir, args.model, args.warmups, args.runs,
            args.threads,
        )

    raw_fields = list(RAW_FIELDS)
    if args.mode == "pipeline":
        raw_fields.extend(PIPELINE_TIMING_FIELDS)
    _write_csv(args.output_dir / "latency_raw.csv", rows, raw_fields)
    summaries = _summaries(rows)
    _write_csv(
        args.output_dir / "latency_summary.csv",
        [
            {
                **summary,
                "status_counts": json.dumps(summary["status_counts"], sort_keys=True),
            }
            for summary in summaries
        ],
        ("mode", "run", "n", "mean_ms", "stddev_ms", "median_ms", "p95_ms",
         "fps_from_mean", "status_counts"),
    )
    environment = _environment(
        args.model,
        args.threads,
        _load_notes(args.device_notes),
        cold_load_ms,
        args.mode,
        args.warmups,
        args.runs,
    )
    environment["dataset"] = {
        "image_count": len(paths),
        "ordered_file_content_sha256": dataset_sha256,
        "order": "lexicographic filename order; image IDs in CSV are positional",
    }
    (args.output_dir / "python_environment.txt").write_text(
        "\n".join(environment.pop("python_packages")) + "\n", encoding="utf-8"
    )
    (args.output_dir / "environment.json").write_text(
        json.dumps(environment, indent=2), encoding="utf-8"
    )
    print(f"Raw per-image timing: {args.output_dir / 'latency_raw.csv'}")
    print(f"Statistics: {args.output_dir / 'latency_summary.csv'}")
    print(f"Environment: {args.output_dir / 'environment.json'}")


if __name__ == "__main__":
    main()
