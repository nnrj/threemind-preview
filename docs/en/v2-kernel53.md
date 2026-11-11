# ThreeMind 5.3: implementation, use and results

11 November 2026. [中文](../zh/v2-kernel53.md) · [Approved plan](plans/kernel53.md) · [Engineering verification](../../lab/explorations/2026-11-11-kernel53/engineering-report.en.md)

## Delivered scope

`threemind.continuous-memory/5.3` has independent Python and genuine Rust implementations, using the existing creation, configuration, stimulus, advancement, observation, intervention and persistence interfaces. It implements one weight and one age, four decay curves, internal-clock deletion checks, separate node emission and connection transmission, and common directed transmission and reinforcement for excitation and inhibition.

Version 5.3 is new dynamics. Historical /5.1 and /5.2 subjects retain their genuine identities. The new /5.2 Rust backend preserves its contribution histories, transmission and event rules. The global creation default remains `continuous-memory/3`. Author manuscripts, historical reports and original data were not rewritten.

## One weight and one age

A connection stores its current base weight w and cumulative dimensionless age a. Persistent node support uses the same representation. For Δt internal seconds and fixed timescale H:

\[
a'=a+\Delta t/H,\qquad w'=w\,F(a')/F(a).
\]

H controls decay speed in internal seconds; it is not a checking interval. Its initial value is 30 seconds. Reinforcement increases the current weight and normally retains age. Optional resetting applies only to an accepted positive increase. Observation, saving, damage and reinforcement at the cap do not reset age.

| `decay_curve` | F(a) | Interpretation |
| --- | --- | --- |
| `exponential` | 2⁻ᵃ | Halves every H seconds at fixed H |
| `power-law` | 1/(1+a) | Fractional decay slows with age |
| `inverse-logarithmic` | 1/[1+ln(1+(e−1)a)] | Natural logarithm and a longer tail |
| `power-exponential` | 1/(1+a) for a≤A; exp[−(a−A)/(1+A)]/(1+A) thereafter | A defaults to 10; value and slope are continuous |

Timescale growth and the original linear relaxation have separate switches, `retention_growth_enabled` and `retention_relaxation_enabled`, both initially off. Growth retains the existing formula and triggers. With relaxation, H falls toward its floor and age advances by ∫dt/H(t). Disabling these mechanisms retains weight reinforcement. The existing field `memory_half_life_min_s` supplies the scale floor/initial value; outside exponential decay it describes a timescale rather than a constant half-life.

Persistent representation size no longer grows with reinforcement count, and old contributions are not summed. Contribution histories were the chosen representation and dynamics of /5.2, not a mathematical requirement for nonexponential decay. Because /5.3 applies one rule to the entire current weight, it is not an equivalent optimization of /5.2.

## Clock checks and transmission

Structure is checked every 100,000 microseconds by default. Same-time input, associative emission and reinforcement precede comparisons against the edge deletion threshold 0.008 and node support threshold 0.006. Individual expiration prediction is removed; each check instead scans extant structure. Tool reads, saving and wall-clock delays do not advance internal time.

Nodes offer excitation and inhibition from their own state and pay for attempted emission. Insufficient energy scales both signal types and all outgoing offers equally. Each connection uses its effective weight before reinforcement, offered signal, synaptic resource release and enabled spatial factor:

\[
q_+=w_{\mathrm{eff}}s_+rd,\qquad q_-=w_{\mathrm{eff}}s_-rd.
\]

The two types share one resource release r on that emission. The spatial factor d is one when disabled. Both types follow actual outgoing edges. An incoming edge no longer supplies an automatic reverse inhibitory path, and inhibition is no longer renormalized by neighboring weights. Reinforcement follows transmission. Inhibitory learning is enabled by default and has a separate switch. Failed attempts do not refund spent node energy or released synaptic resources.

The common minimum transmitted amount defaults to 0.0004. It acts on the calculated quantity for either signal type, allowing a weak signal on a strong edge or a strong signal on a weak edge to pass. `signal_threshold_enabled=false` disables it. The independent base-weight gate is off by default; when enabled, `weight_gate` must be at least the deletion threshold. Weak node activation is separately zeroed by `activation_floor=0.004`. The historical inhibitory sender gate applies only when `inhibition_sender_gate_enabled=true`, initially false.

Dormancy and revival remain separately optional and initially disabled. Opposite directions store and update their own states. Diagnostics distinguish offered, delivered and weight/signal/dormancy/energy-blocked quantities.

## Identity, persistence and usable builds

Curve, transition age, reinforcement age policy and structure-check interval are fixed at birth. Complete state retains configuration, ages, queued events and all established fields, with Python/Rust cross-restoration. Restoring a different identity or overriding saved configuration is rejected. Exact full-state copies remain supported; reproduction refuses undefined age-inheritance behavior.

Verified local products are `.work/kernel53-delivery/threemind-runtime.exe` and `_threemind_native.pyd`, containing genuine /5.2 and /5.3. Installed extensions and the running API service were not replaced. Using the new backends in that service requires rebuilding/installing and a normal restart at an appropriate maintenance time.

From the repository root, this command creates only a zero-time engineering example, without teaching or loading a historical individual. Existing export files are not overwritten:

```powershell
.\.work\kernel53-delivery\threemind-runtime.exe `
  --kernel threemind.continuous-memory/5.3 `
  --clock unbounded --until-us 0 --export .work\example-53.tmind
```

The Python reference backend uses the existing API without a new extension:

```python
from threemind_kernels.local53 import Local53Config
from threemind_kernels.registry import resolve_kernel

core = resolve_kernel("threemind.continuous-memory/5.3").create(
    Local53Config(decay_curve="power-law"), backend="reference"
)
```

For the isolated native build, prepend the absolute `.work/kernel53-delivery` path to `sys.path` before importing and request `backend="native"`. Rebuild with `cargo build --offline --release -p threemind-native -p threemind-runtime -j 2`. Missing build dependencies require explicit resolution, not silent fallback to Python. The executable targets the same platform; other platforms need their own builds.

A Windows x64 wheel for CPython≥3.11 is also available at `.work/kernel53-delivery/wheels/threemind_native-2.0.0-cp311-abi3-win_amd64.whl`. It was installed with `pip --target` into an isolated directory and passed 126 backend checks. Package version remains 2.0.0; scientific kernel identities distinguish the dynamics. During maintenance, after normally stopping the workstation, the selected Python can run `-m pip install --no-deps --force-reinstall <wheel path>`, followed by the existing workstation startup procedure. This delivery did not update the active environment.

## What the three experiments established

| Batch | Independent origins and scope | Conclusion |
| --- | --- | --- |
| R47a | 8 origins; four-curve local exploration, 4,608 continuous sequences | Inverse logarithmic: 8/8 for structure and expression in all three 300-second courses; both specific gain mechanisms 8/8; weak forgetting 0/8 for all curves |
| R47b | 48 fresh confirmation origins, 5,376 continuous sequences | Inverse logarithmic wins all three preregistered 300-second paired comparisons; expression 48/37/48; weak forgetting 0/48 for every curve |
| R47c | 8 origins × 4 curves; 32 complete individuals jointly developing personal Transformers | Inverse logarithmic initial/new/return goals each 8/8; reversal 4/8 fails the 6/8 criterion; power law also returns at 8/8 |

All three archives, members and bilingual texts passed full API readback with `completed/verified/pending=0`. See [exploration](../../lab/explorations/2026-11-11-kernel53/report.en.md), [confirmation](../../lab/explorations/2026-11-11-kernel53/confirmation/report.en.md), and [joint development](../../lab/explorations/2026-11-11-kernel53/joint/report.en.md) for originals and denominators. Local retention has independent confirmation; complete-system outcomes are eight-origin exploration. No curve meets every objective, so power law remains the engineering starting default rather than a declared universal winner.

## Assessment of a fifth strategy

The following is retrospective mathematical analysis and a design recommendation. It changes neither completed criteria nor implemented dynamics.

All four normalized curves have F(1)=1/2. A new connection of weight 0.035 at H=30 seconds, without further reinforcement, still has weight 0.0175 after 30 seconds, above the deletion threshold 0.008. Changing the curve shape alone therefore cannot fix this batch's weak-experience objective. Under these simplified conditions, exponential, power-law and inverse-logarithmic threshold times are approximately 63.88, 101.25 and 492.78 seconds. These are analytical calculations, not additional cultivation records; continued associative reinforcement changes actual times.

First use a bounded comparison to separate timescale, initial learned weight and subsequent associative reinforcement. Switching curves by individual stimulus strength adds questions about weak/strong thresholds, previously existing connections and repeated switching. Current weight already reflects repetition, strong stimuli and novelty. A continuous dependence on current weight is therefore worth considering before adding per-stimulus records.

One simple candidate for discussion is:

\[
\frac{dw}{dt}=-w[\lambda_{\min}+\lambda_{\mathrm{extra}}(1-w)],
\quad 0\le w\le1,\quad\lambda_{\min}>0,\quad\lambda_{\mathrm{extra}}\ge0.
\]

Both rates have units of inverse internal seconds. For λextra>0, weak weights decay faster fractionally and strong weights more slowly; λextra=0 gives ordinary exponential decay. A positive minimum rate also forgets a capped weight. Reinforcement still increments the same w. Writing α=λmin+λextra and β=λextra yields a direct constant-parameter update:

\[
w(t+\Delta t)=\frac{\alpha w(t)e^{-\alpha\Delta t}}
{\alpha-\beta w(t)[1-e^{-\alpha\Delta t}]}.
\]

It requires current weight and two global rates, without contribution lists, stimulus classes or numerical integration. Existing edges update as whole weights, without splitting old and new parts. This is an unapproved model candidate, not an established law of human memory. Rates, any remaining role of age, comparisons and authorization must be decided before implementation. Tests should jointly cover new weak connections, weak input on old connections, repeated/strong/novel teaching, long-term decay without reinforcement, reversal and relearning, with separate declared outcomes.

This delivery completes the four-curve implementation and three comparisons. No specific fifth mechanism has been approved or added, and no further parameter search was started.

## 11 November 2026 addendum: the weight-dependent candidate has been tested

The fifth candidate discussed above was subsequently authorized, implemented and tested as the separate R48 research kernel. Its slow setting improved immediate initial learning but failed 300-second retention; no combined default was selected. Python, Rust and the standalone runtime are delivered, while 5.3 and its default remain unchanged. [Scientific conclusions](../../lab/explorations/2026-11-11-weight-dependent-decay/joint/report.en.md) · [Independent candidate](v2-weight-decay.md)
