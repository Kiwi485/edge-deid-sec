# VM Benchmark v0

- Source CSV: logs/pipeline_latency_vm.csv
- Total rows: 120
- Status counts: ok=8, quality_fail=112, error=0

## Percentiles (all)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 6.00 | 31.04 | 52.28 |
| seg_ms | 9.00 | 27.99 | 44.04 |
| feat_ms | 0.00 | 6.00 | 9.62 |
| deid_ms | 0.00 | 10.00 | 14.43 |
| total_ms | 37.49 | 97.08 | 114.26 |

## Percentiles (ok)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 5.50 | 153.56 | 210.66 |
| seg_ms | 8.00 | 27.99 | 27.99 |
| feat_ms | 0.00 | 8.25 | 9.65 |
| deid_ms | 0.00 | 11.30 | 11.86 |
| total_ms | 70.98 | 267.23 | 340.57 |

## Percentiles (quality_fail)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 6.00 | 29.34 | 44.44 |
| seg_ms | 9.00 | 19.99 | 44.44 |
| feat_ms | 0.00 | 6.00 | 7.89 |
| deid_ms | 0.00 | 10.00 | 14.67 |
| total_ms | 35.99 | 94.43 | 106.86 |

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
- p95 main stage: roi_ms (153.56 ms, 57.5% of total p95)
- p99 main stage: roi_ms (210.66 ms, 61.9% of total p99)
