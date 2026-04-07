# VM Benchmark v0

- Source CSV: logs/pipeline_latency_vm.csv
- Total rows: 480
- Status counts: ok=32, quality_fail=448, error=0

## Percentiles (all)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 3.35 | 8.81 | 11.98 |
| seg_ms | 4.00 | 8.66 | 11.99 |
| feat_ms | 0.00 | 1.04 | 2.09 |
| deid_ms | 1.52 | 2.93 | 9.75 |
| total_ms | 22.33 | 31.56 | 38.30 |

## Percentiles (ok)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 3.26 | 5496.79 | 6250.11 |
| seg_ms | 3.71 | 6.18 | 8.41 |
| feat_ms | 0.00 | 1.01 | 1.03 |
| deid_ms | 1.50 | 5.88 | 10.94 |
| total_ms | 24.79 | 5510.07 | 6270.76 |

## Percentiles (quality_fail)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
| roi_ms | 3.35 | 8.51 | 10.28 |
| seg_ms | 4.00 | 8.72 | 12.10 |
| feat_ms | 0.00 | 1.19 | 2.19 |
| deid_ms | 1.79 | 2.93 | 8.93 |
| total_ms | 22.26 | 31.11 | 34.33 |

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
- p95 main stage: roi_ms (5496.79 ms, 99.8% of total p95)
- p99 main stage: roi_ms (6250.11 ms, 99.7% of total p99)
