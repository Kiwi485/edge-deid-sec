# VM Benchmark v0

- Source CSV: logs/pipeline_latency_vm.csv
- Total rows: 720
- Status counts: ok=48, quality_fail=672, error=0

## Percentiles (all)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 4.00 | 8.98 | 11.75 |
| seg_ms | 3.91 | 6.99 | 11.27 |
| feat_ms | 0.00 | 1.01 | 1.53 |
| deid_ms | 1.51 | 2.53 | 8.79 |
| total_ms | 22.39 | 32.08 | 38.55 |

## Percentiles (ok)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 3.80 | 5519.76 | 6444.59 |
| seg_ms | 3.55 | 5.27 | 8.11 |
| feat_ms | 0.00 | 1.02 | 1.28 |
| deid_ms | 1.48 | 2.51 | 10.72 |
| total_ms | 24.79 | 5531.81 | 6467.77 |

## Percentiles (quality_fail)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 4.00 | 8.86 | 9.97 |
| seg_ms | 3.91 | 6.99 | 11.35 |
| feat_ms | 0.00 | 1.01 | 1.53 |
| deid_ms | 1.51 | 2.53 | 7.80 |
| total_ms | 22.29 | 31.62 | 34.68 |

## Percentiles (error)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | nan | nan | nan |
| seg_ms | nan | nan | nan |
| feat_ms | nan | nan | nan |
| deid_ms | nan | nan | nan |
| total_ms | nan | nan | nan |

## Bottleneck

Bottleneck observation (status=ok):
- p95 main stage: roi_ms (5519.76 ms, 99.8% of total p95)
- p99 main stage: roi_ms (6444.59 ms, 99.6% of total p99)
