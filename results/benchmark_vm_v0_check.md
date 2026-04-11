# VM Benchmark v0

- Source CSV: logs/pipeline_latency_vm.csv
- Total rows: 600
- Status counts: ok=40, quality_fail=560, error=0

## Percentiles (all)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 4.07 | 9.03 | 11.90 |
| seg_ms | 3.97 | 7.39 | 11.42 |
| feat_ms | 0.00 | 1.03 | 1.53 |
| deid_ms | 1.51 | 2.56 | 9.02 |
| total_ms | 24.08 | 32.59 | 39.07 |

## Percentiles (ok)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 3.99 | 5597.68 | 6464.26 |
| seg_ms | 3.55 | 5.50 | 8.26 |
| feat_ms | 0.00 | 1.03 | 1.32 |
| deid_ms | 1.50 | 2.89 | 10.83 |
| total_ms | 25.52 | 5608.12 | 6487.84 |

## Percentiles (quality_fail)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 4.08 | 8.98 | 10.05 |
| seg_ms | 3.98 | 7.76 | 11.62 |
| feat_ms | 0.00 | 1.02 | 1.73 |
| deid_ms | 1.51 | 2.56 | 8.72 |
| total_ms | 24.01 | 32.07 | 34.94 |

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
- p95 main stage: roi_ms (5597.68 ms, 99.8% of total p95)
- p99 main stage: roi_ms (6464.26 ms, 99.6% of total p99)
