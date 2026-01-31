# Year 1 Feasibility Summary (Laptop Baseline)

## Setup
- Input: Laptop webcam
- Frames: 100
- Pipeline: Representative ROI crop + basic image processing (grayscale)
- Metrics: per-frame latency (ms), CPU usage (%), RAM usage (MB)

## Observations (from example_latency_laptop.csv)
- Latency range: ~0.04–0.15 ms (mostly ~0.05–0.07 ms)
- CPU usage: typically ~10–30% (with occasional spikes)
- RAM usage: ~87–94 MB, stable over time

## Conclusion
The representative ROI preprocessing pipeline shows ultra-low latency and stable resource usage, supporting feasibility for low-resource environments.
