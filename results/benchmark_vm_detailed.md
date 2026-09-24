# VM Benchmark v0

- Source CSV: logs/pipeline_latency_vm.csv
- Total rows: 100
- Status counts: ok=100, quality_fail=0, error=0

## Percentiles (all)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| image_load_ms | 9.77 | 109.42 | 119.67 |
| resize_ms | 0.52 | 1.25 | 1.64 |
| quality_ms | 0.85 | 1.03 | 1.07 |
| roi_ms | 8.40 | 10.86 | 109.95 |
| model_load_ms | 0.00 | 0.00 | 4.04 |
| seg_preprocess_ms | 0.44 | 0.51 | 0.87 |
| seg_forward_ms | 46.74 | 195.73 | 497.34 |
| seg_postprocess_ms | 0.27 | 0.47 | 1.32 |
| seg_ms | 56.25 | 197.06 | 503.81 |
| feat_ms | 1.87 | 44.50 | 68.03 |
| deid_ms | 1.10 | 1.56 | 1.79 |
| artifact_write_ms | 18.88 | 83.94 | 89.24 |
| privacy_ms | 8.28 | 8.83 | 76.79 |
| unaccounted_ms | 0.02 | 0.03 | 0.03 |
| total_ms | 133.53 | 340.00 | 563.18 |

## Percentiles (ok)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| image_load_ms | 9.77 | 109.42 | 119.67 |
| resize_ms | 0.52 | 1.25 | 1.64 |
| quality_ms | 0.85 | 1.03 | 1.07 |
| roi_ms | 8.40 | 10.86 | 109.95 |
| model_load_ms | 0.00 | 0.00 | 4.04 |
| seg_preprocess_ms | 0.44 | 0.51 | 0.87 |
| seg_forward_ms | 46.74 | 195.73 | 497.34 |
| seg_postprocess_ms | 0.27 | 0.47 | 1.32 |
| seg_ms | 56.25 | 197.06 | 503.81 |
| feat_ms | 1.87 | 44.50 | 68.03 |
| deid_ms | 1.10 | 1.56 | 1.79 |
| artifact_write_ms | 18.88 | 83.94 | 89.24 |
| privacy_ms | 8.28 | 8.83 | 76.79 |
| unaccounted_ms | 0.02 | 0.03 | 0.03 |
| total_ms | 133.53 | 340.00 | 563.18 |

## Percentiles (quality_fail)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| image_load_ms | nan | nan | nan |
| resize_ms | nan | nan | nan |
| quality_ms | nan | nan | nan |
| roi_ms | nan | nan | nan |
| model_load_ms | nan | nan | nan |
| seg_preprocess_ms | nan | nan | nan |
| seg_forward_ms | nan | nan | nan |
| seg_postprocess_ms | nan | nan | nan |
| seg_ms | nan | nan | nan |
| feat_ms | nan | nan | nan |
| deid_ms | nan | nan | nan |
| artifact_write_ms | nan | nan | nan |
| privacy_ms | nan | nan | nan |
| unaccounted_ms | nan | nan | nan |
| total_ms | nan | nan | nan |

## Percentiles (error)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| image_load_ms | nan | nan | nan |
| resize_ms | nan | nan | nan |
| quality_ms | nan | nan | nan |
| roi_ms | nan | nan | nan |
| model_load_ms | nan | nan | nan |
| seg_preprocess_ms | nan | nan | nan |
| seg_forward_ms | nan | nan | nan |
| seg_postprocess_ms | nan | nan | nan |
| seg_ms | nan | nan | nan |
| feat_ms | nan | nan | nan |
| deid_ms | nan | nan | nan |
| artifact_write_ms | nan | nan | nan |
| privacy_ms | nan | nan | nan |
| unaccounted_ms | nan | nan | nan |
| total_ms | nan | nan | nan |

## Bottleneck

Bottleneck observation (status=ok):
- p95 main stage: seg_ms (197.06 ms, 58.0% of total p95)
- p99 main stage: seg_ms (503.81 ms, 89.5% of total p99)
