# VM Benchmark v0

- Source CSV: logs/pipeline_latency_vm.csv
- Total rows: 120
- Status counts: ok=8, quality_fail=112, error=0

## Percentiles (all)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 4.66 | 8.16 | 9.16 |
| seg_ms | 3.47 | 4.47 | 4.98 |
| feat_ms | 0.00 | 1.01 | 1.51 |
| deid_ms | 1.50 | 2.49 | 2.83 |
| total_ms | 25.31 | 30.09 | 32.71 |

## Percentiles (ok)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 4.45 | 3644.19 | 5210.83 |
| seg_ms | 3.69 | 4.27 | 4.41 |
| feat_ms | 0.00 | 0.98 | 0.98 |
| deid_ms | 0.99 | 1.80 | 1.92 |
| total_ms | 26.40 | 3664.05 | 5229.03 |

## Percentiles (quality_fail)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 4.84 | 8.08 | 8.91 |
| seg_ms | 3.47 | 4.47 | 4.98 |
| feat_ms | 0.00 | 1.01 | 1.51 |
| deid_ms | 1.50 | 2.49 | 2.84 |
| total_ms | 25.26 | 29.89 | 30.22 |

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
- p95 main stage: roi_ms (3644.19 ms, 99.5% of total p95)
- p99 main stage: roi_ms (5210.83 ms, 99.7% of total p99)
