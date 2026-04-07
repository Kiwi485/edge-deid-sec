# VM Benchmark v0

- Source CSV: logs/pipeline_latency_vm.csv
<<<<<<< HEAD
- Total rows: 720
- Status counts: ok=48, quality_fail=672, error=0
=======
- Total rows: 120
- Status counts: ok=8, quality_fail=112, error=0
>>>>>>> 95bd3e132ccd134e630bc8d9aed72d8aa7aee1dd

## Percentiles (all)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
<<<<<<< HEAD
| roi_ms | 4.00 | 8.98 | 11.75 |
| seg_ms | 3.91 | 6.99 | 11.27 |
| feat_ms | 0.00 | 1.01 | 1.53 |
| deid_ms | 1.51 | 2.53 | 8.79 |
| total_ms | 22.39 | 32.08 | 38.55 |
=======
| roi_ms | 6.00 | 31.04 | 52.28 |
| seg_ms | 9.00 | 27.99 | 44.04 |
| feat_ms | 0.00 | 6.00 | 9.62 |
| deid_ms | 0.00 | 10.00 | 14.43 |
| total_ms | 37.49 | 97.08 | 114.26 |
>>>>>>> 95bd3e132ccd134e630bc8d9aed72d8aa7aee1dd

## Percentiles (ok)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
<<<<<<< HEAD
| roi_ms | 3.80 | 5519.76 | 6444.59 |
| seg_ms | 3.55 | 5.27 | 8.11 |
| feat_ms | 0.00 | 1.02 | 1.28 |
| deid_ms | 1.48 | 2.51 | 10.72 |
| total_ms | 24.79 | 5531.81 | 6467.77 |
=======
| roi_ms | 5.50 | 153.56 | 210.66 |
| seg_ms | 8.00 | 27.99 | 27.99 |
| feat_ms | 0.00 | 8.25 | 9.65 |
| deid_ms | 0.00 | 11.30 | 11.86 |
| total_ms | 70.98 | 267.23 | 340.57 |
>>>>>>> 95bd3e132ccd134e630bc8d9aed72d8aa7aee1dd

## Percentiles (quality_fail)

| metric | p50 | p95 | p99 |
|---|---:|---:|---:|
<<<<<<< HEAD
| roi_ms | 4.00 | 8.86 | 9.97 |
| seg_ms | 3.91 | 6.99 | 11.35 |
| feat_ms | 0.00 | 1.01 | 1.53 |
| deid_ms | 1.51 | 2.53 | 7.80 |
| total_ms | 22.29 | 31.62 | 34.68 |
=======
| roi_ms | 6.00 | 29.34 | 44.44 |
| seg_ms | 9.00 | 19.99 | 44.44 |
| feat_ms | 0.00 | 6.00 | 7.89 |
| deid_ms | 0.00 | 10.00 | 14.67 |
| total_ms | 35.99 | 94.43 | 106.86 |
>>>>>>> 95bd3e132ccd134e630bc8d9aed72d8aa7aee1dd

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
<<<<<<< HEAD
- p95 main stage: roi_ms (5519.76 ms, 99.8% of total p95)
- p99 main stage: roi_ms (6444.59 ms, 99.6% of total p99)
=======
- p95 main stage: roi_ms (153.56 ms, 57.5% of total p95)
- p99 main stage: roi_ms (210.66 ms, 61.9% of total p99)
>>>>>>> 95bd3e132ccd134e630bc8d9aed72d8aa7aee1dd
