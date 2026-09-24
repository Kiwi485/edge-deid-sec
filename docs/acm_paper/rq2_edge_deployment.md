# RQ2 — Edge Deployment Performance Evaluation

**Research question**: Can the selected lightweight segmentation model (U-Net + MobileNetV2)
satisfy the computational constraints of edge devices while maintaining practical inference
performance, compared against a heavier baseline (U-Net + ResNet34)?

**Status**: ✅ Real experiment executed end-to-end on 2026-07-11. All numbers below come from
actual training + inference runs on this repository's code and dataset — see
[§7 Reproducibility](#7-reproducibility--raw-outputs) for exact commands and file locations.

---

## 1. What changed from the earlier draft

The previous version of this document (originally `data/123.md`) contained numbers that could
not be traced to any script or output file in this repository — no RQ2 benchmark code, no raw
result files, and no ResNet34 checkpoint existed anywhere on disk. That draft has been fully
replaced. Along the way, two pre-existing bugs in the RQ1 training pipeline were found and fixed
(this is why `outputs/acm_paper/rq1/` previously only contained `split_manifest.json` — the
pipeline had never successfully completed a training run):

1. **`experiments/acm_paper/rq1_model_selection/run_rq1.py`** — `count_parameters()` returns a
   single `int`, but `train_smp_model()` unpacked it as a 2-tuple (`trainable, total = ...`),
   raising `TypeError` immediately after model construction.
2. Same file — the validation split loader picked the wrong source directory (`"valid"` /
   `""`) instead of reusing the single `"train"` directory that this dataset actually stores all
   samples under, so `val_ds` always loaded 0 images.

Both are fixed in place (see git diff of `run_rq1.py`).

## 2. Models & checkpoints

| Model | Encoder | Trainable Params | Checkpoint |
|---|---|---:|---|
| U-Net + MobileNetV2 | mobilenet_v2 | 6,628,945 | `models/acm_paper/rq1/unet_mobilenet/best.pth` |
| U-Net + ResNet34 | resnet34 | 24,436,369 | `models/acm_paper/rq1/unet_resnet/best.pth` |

Both trained from scratch via `run_rq1.py` (50 epochs, batch size 8, img size 256, lr 1e-4,
seed 42, Adam + CosineAnnealingLR, BCEWithLogitsLoss + DiceLoss), using the **same fixed split
manifest** (`outputs/acm_paper/rq1/split_manifest.json`: 100 images → train=70 / val=15 / test=15,
carved out of the single 100-image dataset since no separate valid/test directories exist).
Best checkpoint selected by validation Dice, never test Dice.

## 3. Segmentation accuracy (held-out test split, n=15)

| Model | Dice | IoU | Precision | Recall | Pixel Acc |
|---|---:|---:|---:|---:|---:|
| U-Net + MobileNetV2 | **0.8907** | **0.8029** | 0.8251 | 0.9677 | 0.9952 |
| U-Net + ResNet34 | 0.8723 | 0.7736 | 0.7970 | 0.9634 | 0.9942 |

MobileNetV2 is *not* less accurate than ResNet34 on this dataset — it's marginally better on
every metric. This is plausible given the very small training set (70 images): the 24.4M-param
ResNet34 encoder has more capacity to overfit than the 6.6M-param MobileNetV2 encoder. This
result should be treated as preliminary given n=15 test images, not a general claim about the
two architectures.

Full per-model JSON: `outputs/acm_paper/rq1/unet_mobilenet.json`, `outputs/acm_paper/rq1/unet_resnet.json`.

## 4. Environments

| Environment | Mechanism used | Verified |
|---|---|---|
| **Desktop** | Native Windows, `.venv`, no constraints, torch auto-selected 12 threads (16 logical cores) | — |
| **Environment A** (2 Core / 2GB) | WSL2 Ubuntu 24.04, `taskset -c 0,1` (CPU affinity) + `ulimit -v 2097152` (2GB virtual-memory ceiling) + `--torch-threads 2` | Affinity confirmed exactly 2 cores visible (`os.sched_getaffinity`); `ulimit -v` confirmed to raise `MemoryError` when exceeded |
| **Environment B** (4 Core / 4GB) | Same WSL2 instance, `taskset -c 0,1,2,3` + `ulimit -v 4194304` + `--torch-threads 4` | Same mechanism as A, 4 cores / 4GB |

**Why not Docker or systemd/cgroups?** This machine has no Docker installed. WSL2's cgroup v2
`MemoryMax` was tested first and found **not to be reliably enforced** here (a 700MB allocation
under a 300MB `MemoryMax` scope completed without being killed) — likely a delegation quirk of
WSL2's systemd shim. `taskset` (CPU affinity) and `ulimit -v` (POSIX `RLIMIT_AS`) were tested
directly and both verified to work correctly, so they were used instead. This is documented here
so the constraint mechanism is auditable rather than assumed.

## 5. Table 2 — Edge Deployment Performance

100 images per run (the full dataset; this is a pure runtime/memory/CPU measurement with no
accuracy computation involved, so using all 100 images — not only the 15-image held-out test
split — does not introduce any evaluation leakage). **Each configuration was run 3 times**
(`--repeat-index 1/2/3`, independent process invocations) after an initial single-run pass showed
the numbers were noisier than they looked — see §5.2 below. Table 2 reports mean ± std over the 3
runs.

| Model | Environment | Time/Image (ms) | FPS (from mean) | Peak Memory (MB) | CPU Usage (%)* | Model Size (MB) |
|---|---|---:|---:|---:|---:|---:|
| MobileNetV2 U-Net | Desktop | 71.9 ± 5.7 | 13.9 | 512.6 ± 3.1 | 68.1 ± 1.9 | 76.23 |
| MobileNetV2 U-Net | VM (2 Core / 2GB) | 85.4 ± 12.1 | 11.7 | 572.1 ± 13.8 | 62.0 ± 3.2 | 76.23 |
| MobileNetV2 U-Net | VM (4 Core / 4GB) | 99.2 ± 23.5 | 10.1 | 565.2 ± 12.7 | 58.4 ± 1.2 | 76.23 |
| ResNet34 U-Net | Desktop | 127.4 ± 14.4 | 7.8 | 785.6 ± 1.0 | 67.1 ± 3.0 | 279.89 |
| ResNet34 U-Net | VM (2 Core / 2GB) | 179.7 ± 62.2 | 5.6 | 844.5 ± 1.5 | 67.8 ± 8.1 | 279.89 |
| ResNet34 U-Net | VM (4 Core / 4GB) | 142.1 ± 63.3 | 7.0 | 848.2 ± 7.1 | 61.2 ± 9.2 | 279.89 |

\* CPU Usage is process CPU time normalized to the cores actually available in that environment
(e.g. 100% in Environment A means both allowed cores fully saturated), not raw multi-core percent.

### 5.1 Read this table carefully: latency numbers are noisy, memory/CPU numbers are not

The std columns are large relative to the mean for **latency**, especially for ResNet34
(±35–44% of the mean in the VM environments). **Peak Memory and CPU Usage are stable** (std
typically <5% of the mean) — those conclusions (§8, Q2) can be trusted. Latency differences
between Desktop / VM A / VM B in this table are **not clearly separable from run-to-run noise**
on this particular test machine, for the reasons in §5.2. Do not read small latency deltas
between environments in this table as causal.

### 5.2 What the first (single-run) pass got wrong

The first pass of this experiment (n=1 per config) reported MobileNetV2 as 97.46ms on Desktop vs
64.28ms / 50.02ms on VM A / VM B, and concluded this was caused by PyTorch's default thread count
(12, unconstrained) oversubscribing relative to the workload, hurting Desktop latency. **That
conclusion does not survive repetition.** With n=3:

- Desktop with its *default* 12 threads averaged **71.9ms** — faster than every other Desktop
  thread setting tested (threads=2: 88.9ms, threads=4: 85.8ms) and faster than both VM
  environments (85.4ms / 99.2ms). This is the opposite of what the single run suggested.
- A dedicated thread-count control was added specifically to test the oversubscription hypothesis
  (Desktop, unconstrained cores, `torch.set_num_threads(2)` and `(4)` — i.e. same thread budget as
  the VMs but without the affinity/memory constraint):

  | Model | Desktop (default ~12t) | Desktop (2t) | Desktop (4t) |
  |---|---:|---:|---:|
  | MobileNetV2 | 71.9 ± 5.7 ms | 88.9 ± 10.9 ms | 85.8 ± 11.6 ms |
  | ResNet34 | 127.4 ± 14.4 ms | 161.2 ± 13.8 ms | 140.1 ± 1.1 ms |

  If the oversubscription hypothesis were correct, the thread-limited columns should be *faster*
  than default. They are consistently *slower* instead. The original finding was an artifact of
  comparing two single measurements that happened to fall on opposite sides of this machine's
  natural run-to-run variance, not a reproducible property of thread count or environment.

**Likely source of the variance**: this is a shared laptop/desktop host running WSL2 and Windows
on the same physical CPU, with background processes, OS scheduling, and (on a laptop) power/
thermal management all able to shift a ~10-second, single-threaded-per-image CPU benchmark by
tens of milliseconds. None of that is controlled for here. Getting latency numbers precise enough
to make causal claims about "Environment A vs B" would need a dedicated idle machine, more
repeats (n≈10–20+), and ideally paired statistical testing (e.g. a t-test on the per-run means) —
out of scope for this pass, but noted here so the paper doesn't overclaim.

### 5.3 Supplementary detail (latency distribution within a single representative run, load time)

| Model | Env | Median (ms) | P95 (ms) | Min–Max (ms) | Load Time (ms) |
|---|---|---:|---:|---:|---:|
| MobileNetV2 | Desktop (run 1) | 63.76 | 189.43 | 48.5–281.3 | 334.8 |
| MobileNetV2 | VM A (run 1) | 62.95 | 69.37 | 59.4–106.9 | 1611.1 |
| MobileNetV2 | VM B (run 1) | 46.19 | 72.81 | 34.7–106.3 | 1491.8 |
| ResNet34 | Desktop (run 1) | 85.16 | 210.51 | 65.3–325.1 | 387.2 |
| ResNet34 | VM A (run 1) | 115.29 | 168.28 | 101.7–180.9 | 3418.6 |
| ResNet34 | VM B (run 1) | 66.40 | 95.79 | 61.6–120.3 | 4300.2 |

These per-image distribution stats (median/P95/min/max) are from a single representative run
each (within-run variation across the 100 images in that run), separate from the across-run
variation discussed in §5.2. Both sources of noise exist; the across-run one is what invalidated
the original single-pass conclusion.

**Model load time caveat**: the WSL runs' load times (1.5–4.3s) are much higher than Desktop's
(0.33–0.39s). This is almost certainly an artifact of the checkpoint file living on the
Windows-mounted drive (`/mnt/d/...`) accessed through WSL2's 9p filesystem bridge, which is known
to be slow for file I/O — not a property of a genuinely resource-constrained edge device. Treat
the load-time column as a testing-environment artifact, not a deployment-relevant number, unless
re-measured with the checkpoint copied onto native WSL storage.

Raw JSON per run: `outputs/acm_paper/rq2/{arch}_{environment_label}_r{1,2,3}.json`. Combined CSV
(30 rows — 5 configs × 3 repeats × 2 models): `outputs/acm_paper/rq2/results.csv`.

## 6. Figures

- `outputs/acm_paper/rq2/figures/figure1_runtime_comparison.png` — Inference Time / Peak Memory /
  CPU Usage grouped bar charts across the three environments.
- `outputs/acm_paper/rq2/figures/figure2_runtime_vs_model_size.png` — scatter of model size vs
  mean latency, one point per (model, environment) pair.

Regenerate with:
```bash
python -m experiments.acm_paper.rq2_edge_deployment.plot_rq2
```

## 7. Reproducibility — raw outputs

```
models/acm_paper/rq1/unet_mobilenet/{best,last}.pth
models/acm_paper/rq1/unet_resnet/{best,last}.pth
outputs/acm_paper/rq1/unet_mobilenet.json          # accuracy + latency (RQ1 evaluate_smp.py)
outputs/acm_paper/rq1/unet_resnet.json
outputs/acm_paper/rq2/{arch}_{desktop,desktop_threads2,desktop_threads4,vm_a_2c2g,vm_b_4c4g}_r{1,2,3}.json
outputs/acm_paper/rq2/results.csv                  # 30 rows: 5 configs x 3 repeats x 2 models
outputs/acm_paper/rq2/figures/*.png
```

Commands to reproduce (Desktop, one repeat shown — loop `--repeat-index 1..3`):
```bash
python -m experiments.acm_paper.rq1_model_selection.run_rq1 \
    --data-dir acmpaper_data --epochs 50 --batch-size 8 --img-size 256 --lr 1e-4 --seed 42 \
    --device cpu --skip-yolo \
    --output-dir outputs/acm_paper/rq1 --model-dir models/acm_paper/rq1

python -m experiments.acm_paper.rq1_model_selection.evaluate_smp \
    --data-dir acmpaper_data --arch unet_mobilenet \
    --checkpoint models/acm_paper/rq1/unet_mobilenet/best.pth --split test \
    --output outputs/acm_paper/rq1/unet_mobilenet.json
# (repeat --arch unet_resnet)

python -m experiments.acm_paper.rq2_edge_deployment.benchmark_edge_deployment \
    --data-dir acmpaper_data --arch unet_mobilenet \
    --checkpoint models/acm_paper/rq1/unet_mobilenet/best.pth \
    --environment-label desktop --image-split all --repeat-index 1
# (repeat --repeat-index 2, 3; repeat for unet_resnet; repeat with --torch-threads 2 / 4
#  and --environment-label desktop_threads2 / desktop_threads4 for the thread-count control)
```

Commands to reproduce (Environment A / B, inside WSL2, one repeat shown):
```bash
# Environment A: 2 core / 2GB
taskset -c 0,1 bash -c 'ulimit -v 2097152; exec python3 -m \
    experiments.acm_paper.rq2_edge_deployment.benchmark_edge_deployment \
    --data-dir acmpaper_data --arch unet_mobilenet \
    --checkpoint models/acm_paper/rq1/unet_mobilenet/best.pth \
    --environment-label vm_a_2c2g --image-split all --torch-threads 2 --repeat-index 1'

# Environment B: 4 core / 4GB
taskset -c 0,1,2,3 bash -c 'ulimit -v 4194304; exec python3 -m \
    experiments.acm_paper.rq2_edge_deployment.benchmark_edge_deployment \
    --data-dir acmpaper_data --arch unet_mobilenet \
    --checkpoint models/acm_paper/rq1/unet_mobilenet/best.pth \
    --environment-label vm_b_4c4g --image-split all --torch-threads 4 --repeat-index 1'
```

---

## 8. Analysis

### Q1 — Does the edge environment affect inference speed?

**Inconclusive at n=3 — cannot be separated from run-to-run noise on this test machine.**
The single-run pass suggested a clean "more cores → faster" story; §5.2 shows that story does not
survive repetition (in fact ResNet34's mean latency in VM A, 179.7ms, has a 62ms std — the 2-core
vs 4-core means, 179.7ms vs 142.1ms, overlap heavily once that spread is accounted for).
MobileNetV2's trend (Desktop 71.9 → VM A 85.4 → VM B 99.2ms) is *also* not the expected direction
(more cores getting *slower*), reinforcing that these deltas are noise-dominated rather than
signal. **Answer as tested: no reliable evidence either way.** A real answer needs a quieter
measurement setup (§5.2) — this is flagged as follow-up work, not glossed over.

### Q2 — Is memory a bottleneck?

**No.** Peak RSS ranges 513–848 MB (mean ± std, stable across repeats) across every
model/environment combination — well under both the 2GB and 4GB ceilings (26–42% of the 2GB
budget in Environment A). Unlike latency, this metric was consistent across all 3 repeats
(std typically <5% of mean), so this conclusion is on solid footing.

### Q3 — Can CPU-only inference still be real-time?

**Yes, for both models, in every environment tested, even at the noisy upper end.** Against a
300–500ms/image clinical target: MobileNetV2's slowest mean (99.2ms, VM B) is still 3×+ inside
budget; ResNet34's slowest single run across all 30 runs was 244ms (VM A, run 2) — still comfortably
under 300ms. Because the target has this much headroom, the answer to Q3 holds regardless of the
Q1 uncertainty about *which* environment is fastest.

### Q4 — Does MobileNetV2 keep comparable accuracy while cutting runtime/memory?

| Dimension | MobileNetV2 vs ResNet34 |
|---|---|
| Accuracy (Dice) | **+2.1%** (0.8907 vs 0.8723) — not worse, slightly better here |
| Runtime (Desktop, mean) | **-44%** (71.9ms vs 127.4ms) |
| Peak Memory (Desktop, mean) | **-35%** (512.6MB vs 785.6MB) |
| Model Size | **-73%** (76.2MB vs 279.9MB) |

Memory and model size differences are large enough to trust despite the latency noise (peak RSS
std is small; MobileNetV2 vs ResNet34 differ by 35–39%, far outside the ~1–3% run-to-run spread).
The runtime gap is directionally consistent across every environment and every repeat (MobileNetV2
was faster than ResNet34 in all 30/30 runs, even though the *size* of the gap varies with noise) —
so "MobileNetV2 is faster" is solid; "MobileNetV2 is exactly 44% faster" is not, and the paper
should quote a range rather than a single point estimate. Accuracy gap (n=15 test images) remains
the weakest claim here, as noted in §3.

### Q5 — Does the selected model meet clinic-deployment requirements?

**Yes**, on the dimensions this experiment could measure reliably:

- Speed: ✅ MobileNetV2's slowest observed mean is 99.2ms (VM B), ResNet34's is 179.7ms (VM A) —
  both comfortably under the 300–500ms target in every environment and every repeat.
- Memory: ✅ both models stay under 850MB mean peak, far below the 2GB floor tested, consistently.
- Storage: ✅ MobileNetV2 checkpoint is 76MB, ResNet34 is 280MB — both reasonable for app bundling.
- CPU-only: ✅ confirmed, no GPU/NPU required for either model.

The one thing this experiment does *not* let us answer confidently is *which specific edge
environment* (2-core vs 4-core) is better for latency — see Q1. That question doesn't change the
overall Q5 verdict since both models clear the target with wide margin in every environment tested.

## 9. Conclusion

U-Net + MobileNetV2 is the better edge-deployment choice on the dimensions measured reliably here:
it is consistently faster than ResNet34 (30/30 runs), meaningfully lighter on memory (35% less
peak RSS) and disk (73% smaller checkpoint), and — on this small test set — at least as accurate.

Caveats to carry into the paper write-up, in order of how much they should temper the claims:

1. **Latency numbers have real run-to-run variance** (§5.2) large enough that "Environment A vs
   B" cannot be confidently ranked at n=3 on this shared, non-dedicated test machine. Report
   latency as a range or mean±std, not a single number, and flag Q1 as unresolved rather than
   forcing an answer.
2. **The 15-image held-out test set** limits how strongly the accuracy comparison (§3) can be
   claimed to generalize.
3. **The WSL2 "VM" environments are a taskset+ulimit simulation**, not a physical Raspberry Pi /
   Intel NUC — the CPU-affinity and memory-ceiling mechanisms were directly verified to work, but
   real device I/O, thermal throttling, and OS scheduler behavior will differ.
4. **Model load time in the WSL runs is inflated** by cross-filesystem I/O (checkpoint read over
   the `/mnt/d` 9p bridge) and should not be quoted as a device-representative number without
   re-measurement on native storage.

None of these caveats change the headline recommendation (MobileNetV2 over ResNet34 for this
deployment target) — they narrow how precisely the *margins* can be stated.
