# Local Transformer GPU and CPU fallback acceptance

[中文](../../zh/plans/transformer-gpu-acceptance.md) · [Delivery](stimulus-intensity-and-spacetime.md)

2026-09-30. **The existing small Transformer completed real GPU training, model saving and inference. Training falls back to CPU when CUDA is unavailable; the GPU-trained model also runs directly on CPU.** This does not port the consciousness kernel to GPU or automatically feed Transformer output into Core.

## Environment and results

Windows; NVIDIA GeForce GTX 1650 with approximately 4 GiB VRAM; driver 617.14; project Python 3.13; PyTorch 2.14.0+cu130 and CUDA runtime 13.0. No global Python, driver or system environment changes.

The existing isolated computation service trained numeric sequences `[1,2,3]` and `[4,5,6]`: vocabulary 8, width 16, 2 heads, 1 layer, 3696 parameters, 30 steps, batch size 8. Each training task had a 60-second limit, 2 GiB GPU allocation budget and 512 MiB headroom. Tasks ran sequentially.

| Request | Actual training / inference | Result |
|---|---|---|
| CPU | CPU / CPU | 30 steps; training next-token accuracy 1.0 |
| CUDA | CUDA / CUDA | 30 steps; training next-token accuracy 1.0 |
| Auto | CPU / CPU | Completed without assuming GPU is faster |
| CUDA with the device hidden from child processes | CPU / CPU | Same request completed all 30 steps on CPU |
| Previously GPU-trained model, device hidden | No retraining / CPU | Same model file hash; successful CPU inference |

CPU and CUDA loss fell from approximately 2.056 to 0.0441. After `[1,2]`, token 3 had probability approximately 0.95549. Accuracy is measured on the training material: this is device acceptance, not a generalization or consciousness experiment.

CUDA peak allocated VRAM was approximately 22 MiB; peak process RSS approximately 1.25 GiB. Allocation does not include all driver context or other applications. The same GPU-trained model's CPU/GPU probability vectors differed by at most approximately `1.17e-6`; cross-device floating-point paths are not required to be bitwise identical.

## Why auto selected CPU

Three paired inference samples took approximately 6.72 / 2.52 / 2.67 ms on CPU and 187.03 / 6.79 / 6.96 ms on GPU, including placement, transfer and synchronization. GPU overhead dominates this tiny workload. The auto-training benchmark reached its own time budget (`benchmark_budget`) and fell back to CPU; that is not a measured training speed conclusion. The current general `reason` field also covers unsuccessful benchmarking, so inspect `benchmark.status`.

Whole explicit CPU and CUDA child-process training took approximately 19.66 and 8.82 seconds, respectively. Their order, loading and warm-up differ: **this does not establish a twofold GPU speedup**. Acceptance establishes functionality; suitable larger matrix workloads still require measurement.

## Failures, boundaries and fixes

The first hiding attempt set `CUDA_VISIBLE_DEVICES` to an empty string. The test children still discovered the GPU and the assertion failed; those files are retained. Setting it to `-1`, only for this command's children, produced `cuda_unavailable` and completed real CPU training and inference. No driver removal, service interruption or evidence overwrite occurred.

Recovery from a mid-task device failure into a new CPU process starting from frozen initial conditions is tested through fault injection, not an intentionally broken real driver. A failure-attempt summary could report zero steps despite correct nested evidence; its summary extraction and regression assertions are corrected without changing training. The random-input API now returns the existing 422 validation response for unknown configuration fields or missing recovery positions instead of 500; this does not change Core input.

In the last 28-test batch, 27 passed initially. The new API test incorrectly expected 400; after correcting it to the existing 422 contract, its isolated rerun passed. Earlier 54- and 59-test batches remain separately recorded; overlapping counts are not added.

## Reproduction and evidence

```powershell
$py = (Resolve-Path .work/kernel-venv/Scripts/python.exe).Path
& $py scripts/validate-transformer-device.py .work/new-device-validation
& $py scripts/validate-transformer-device.py .work/new-portability-validation --case gpu-hidden --predict-existing .work/new-device-validation/cuda.tmt
```

The script refuses existing output directories/models. Inputs, training histories, device reports and numeric models are preserved in `.work/transformer-device-20260930`, `.work/transformer-device-fallback-20260930` and `.work/transformer-portability-20260930`, and separately archived in this study's research project. The initial hiding failure remains distinct from valid acceptance.

The shared account moved from 64% at experiment start to 66% including final acceptance; not all usage can be attributed to ThreeMind. New simulation is finished. The consciousness study still contains 295 new instances and does not modify older experiments.
