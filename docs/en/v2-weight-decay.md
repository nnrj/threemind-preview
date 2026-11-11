# Weight-dependent decay: the R48 research kernel

11 November 2026. [中文](../zh/v2-weight-decay.md) · [Local experiment](../../lab/explorations/2026-11-11-weight-dependent-decay/report.en.md) · [Whole learners](../../lab/explorations/2026-11-11-weight-dependent-decay/joint/report.en.md) · [Runtime verification](../../lab/explorations/2026-11-11-weight-dependent-decay/engineering-report.en.md)

## Rule and implementation

This candidate tests whether stronger weights can forget more slowly in relative terms. For persistent connection weight w and internal time t in seconds:

\[
\frac{dw}{dt}=-w[\lambda_{\min}+\lambda_{\mathrm{extra}}(1-w)].
\]

The relative decay rate decreases as w increases. Its positive minimum ensures continued decay without reinforcement even when w reaches 1. Actual reinforcement still adds to the current weight.

With a=λmin+λextra and z=exp(−aΔt), the exact update is

\[
w'=\frac{awz}{a(1-w)+\lambda_{\min}w+\lambda_{\mathrm{extra}}wz}.
\]

The calculation uses the current weight, elapsed internal time and two rates. It needs neither a history of reinforcement contributions nor small-step numerical integration, and it does not depend on connection age. The state retains the /5.3 age field for comparisons and diagnostics. Node support continues to use the fixed inverse-logarithmic age curve. Activation, inhibition, transmission, synaptic resources, learning and event order retain /5.3 behavior.

This is a separate dynamics candidate, `threemind.experimental-weight-decay/1`. Python, Rust and the standalone runtime share its identity and state schema. It does not replace /5.3 or change the global `continuous-memory/3` default or the /5.3 power-law default. Historical individuals retain their saved implementation identity.

## Five comparison arms

| `edge_rule` | Connection rule | R48 additional rate λextra |
| --- | --- | --- |
| `inverse-logarithmic` | /5.3 inverse-logarithmic age curve | Unused |
| `weight-fast` | Weight-dependent rule above | 0.06/s |
| `weight-slow` | Weight-dependent rule above | 0.012/s |
| `matched-fast` | Constant exponential rate λmin+λextra(1−0.035) | 0.06/s |
| `matched-slow` | Same matching rule | 0.012/s |

λmin=ln2/86400 per second. The matching weight 0.035 was declared before the run from the existing birth weight; matching tests whether an overall change in decay speed explains a candidate benefit. Every arm uses inverse-logarithmic node support with a 30-second scale. Scale growth and relaxation are disabled. Parameters are fixed at birth.

`configuration(seed, rule)` selects the complete parameters in the table. When supplying raw configuration, specify both `edge_rule` and `extra_rate`: the fast/slow names are labels and do not override explicit numbers. Restoration cannot change the saved rule or configuration.

## Existing interfaces

A minimal reference-backend engineering example:

```python
from threemind_kernels.registry import resolve_kernel
from threemind_kernels.weight_decay import KERNEL_ID, configuration

core = resolve_kernel(KERNEL_ID).create(
    configuration(908780, "weight-slow"), backend="reference"
)
```

Select `backend="native"` for Rust. Verified local products reside in `.work/r48-delivery/`; its absolute path can be added to the front of `sys.path` before importing the native module. An older installed extension that lacks the candidate reports the missing backend rather than silently substituting Python.

The standalone program creates candidates and restores their complete Core states. This command creates only a zero-time engineering example and refuses to overwrite an existing file:

```powershell
.\.work\r48-delivery\threemind-runtime.exe `
  --kernel threemind.experimental-weight-decay/1 `
  --clock unbounded --until-us 0 --export .work\r48-example.tmind
```

The candidate's own initial configuration is the fast arm. Supply complete JSON with `--config` for the slow arm or a control. `--model` accepts JSON or TMIND, `--store` records the runtime database, and `--resume --store` continues that individual. Creation overrides cannot be combined with restoration. An experimental whole learner also includes its personal Transformer, Adam, random state, body and mappings; use the experiment's whole-system checkpoint to restore it.

The Python configuration catalogue includes candidate fields and their birth-only constraints. Exact Core copies retain identity. Structural inheritance of age is not defined for this candidate and is rejected explicitly. Delivery has not replaced the installed extension, restarted services or changed historical experiments.

## Verification and findings

The runtime report contains actual state comparisons, performance measurements and package hashes. R48a and R48b report the scientific findings separately. Successful compilation is not counted as a scientific result. Artifact locations are indexed in `lab/artifact-index/2026-11-11-weight-dependent-decay.json`.
