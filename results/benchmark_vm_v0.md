# VM Benchmark v0

- Source CSV: logs/pipeline_latency_vm.csv
- Total rows: 120
- Status counts: ok=8, quality_fail=112, error=0

## Percentiles (all)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 3.15 | 6.16 | 7.95 |
| seg_ms | 3.48 | 4.45 | 4.52 |
| feat_ms | 0.00 | 1.04 | 1.52 |
| deid_ms | 1.50 | 1.98 | 2.49 |
| total_ms | 22.71 | 26.83 | 29.43 |

## Percentiles (ok)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 3.10 | 3551.55 | 5079.18 |
| seg_ms | 2.93 | 3.98 | 4.02 |
| feat_ms | 0.00 | 1.17 | 1.46 |
| deid_ms | 1.51 | 1.98 | 2.00 |
| total_ms | 23.97 | 3572.18 | 5098.89 |

## Percentiles (quality_fail)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 3.15 | 6.04 | 7.88 |
| seg_ms | 3.49 | 4.45 | 4.53 |
| feat_ms | 0.00 | 1.01 | 1.51 |
| deid_ms | 1.50 | 1.98 | 2.50 |
| total_ms | 22.53 | 26.78 | 28.09 |

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
- p95 main stage: roi_ms (3551.55 ms, 99.4% of total p95)
- p99 main stage: roi_ms (5079.18 ms, 99.6% of total p99)
