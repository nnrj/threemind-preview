# ThreeMind 5.3: single-age decay and directed transmission

Discussed and authorized on 2026-11-10; implementation continued on 2026-11-11. [中文](../../zh/plans/kernel53.md)

The author explicitly requested implementation of the approved 5.3 plan. Reinforcement keeps decay age by default, with an optional reset on an actual positive increment. Retention-timescale growth and linear relaxation remain independent options, both off by default. Persistent structure is checked directly on an internal-clock grid. Transmission is deterministic, without added fixed loss. Excitation and inhibition use outgoing directed connections, the same resource release and joint threshold. Inhibitory transmission reinforces connections by default; its learning contribution can be disabled. Nodes pay for emission attempts, including failed delivery.

This is a new dynamics version. Historical kernels, existing individuals, original evidence and the global creation default `continuous-memory/3` are preserved. Author-edited manuscripts are outside scope. Python reference and genuine Rust execution are both required; 5.2 Rust will subsequently preserve its original contribution-history model.

Each connection weight and node support retains one current value and one normalized age. For constant timescale H, elapsed internal time Δt increases age by Δt/H and multiplies the current value by F(a+Δt/H)/F(a). Optional linear timescale relaxation uses the integral of 1/H(t). Reinforcement increases the current value; the reset option acts only on a strictly positive accepted increment. Damage, saturation, observation and saving never reset age.

| Curve | Remaining fraction F(a) |
| --- | --- |
| Exponential | 2⁻ᵃ |
| Power law | 1/(1+a) |
| Inverse logarithmic | 1/[1+ln(1+(e−1)a)] |
| Power law followed by exponential | 1/(1+a) up to A; exp[−(a−A)/(1+A)]/(1+A) thereafter |

Initial engineering settings are H=30 internal seconds, A=10 and power-law default. These are comparison starting values, not biological constants. H controls decay speed, not update frequency. A structure check every 100000 microseconds follows same-time input, novelty and emission. Connection deletion uses 0.008; automatic node reclamation uses support 0.006. Optional dormancy/wake mechanisms remain disabled by default. Reciprocal connections are independently stored, strengthened, decayed and deleted.

Nodes retain existing activation, inhibition-generation and fatigue rules. All outgoing attempts incur the existing per-unit energy costs; insufficient node energy scales all attempts uniformly. Each connection calculates transmitted magnitude from effective weight, offered magnitude, synaptic-resource release and any enabled spatial factor. Simultaneous excitatory and inhibitory offers share one release, are tested separately against pre-reinforcement connection state, then contribute to learning. Failed delivery does not refund energy or already released resources.

The initial joint transmission minimum is 0.0004 and can be disabled. An independent weight gate is off by default and, if enabled, cannot be below the deletion threshold. Node activation zeroing remains 0.004 and is independent. The historical inhibitory sender gate is available only as an explicitly enabled control. Inhibition cannot travel backward along an incoming edge and is no longer normalized by total neighbor weight.

Existing creation, injection, advancement, observation, intervention and complete-save interfaces route explicitly to 5.3. Curve, transition age, reinforcement-age policy and structure-clock interval are immutable after birth. Saved configuration and age are mandatory. Exact complete-state forks are available; structural reproduction is explicitly rejected until an age-inheritance rule is defined.

Engineering acceptance includes independent curve calculations, continuity at the transition, split advancement, numerical stability, reinforcement/damage/saturation, constant persistent state size, directed transport, shared resources, failed-attempt costs, same-time deletion boundaries, Python/Rust event and state agreement, cross-backend restoration, observer isolation and frozen historical witnesses. Float tolerances cannot excuse different event decisions, topology or lifecycle. Test binaries remain isolated from installed modules and running hosts.

After engineering acceptance, run 8 exploratory origins and 48 new confirmation origins, with independent continuous cohorts at each retention delay. Freeze targets, denominators, materials and stopping criteria before formal execution. Compare genuine intensity-triggered strong input, novelty/familiarity, equal-dose massed/spaced teaching, structural retention, four-field temporal expression, weak-experience forgetting, reversal, relearning and old-ability retention. Register mechanistic instruments separately from whole-system learning with a personal temporal Transformer. Report scalar, graph, active/quiet, serialization and full-teaching costs separately for Python and Rust. Select a 5.3 default only after the preregistered capability requirements, using cost as a subsequent criterion.

After the four-curve comparison, assess the proposed intensity-dependent fifth strategy. Strength boundaries, switching existing connections and additional state remain undecided and require discussion if they introduce new rules. Do not delay completed four-curve delivery. The later 5.2 Rust implementation must retain its original contribution histories and transmission semantics.

Scientific runs reserve 5/4/5/25 GiB of commit/RAM/C/E capacity, account for startup peaks and original/archive/API copies, and pause at complete boundaries. Do not resume E69/E67/E68, start old queues, purchase cloud resources or delete originals. Completion requires original-package API readback and pending=0. [Current handoff](../../../lab/explorations/2026-11-11-kernel53/HANDOFF.md) distinguishes implementation, engineering validation and scientific results.

## Delivery, 11 November 2026

The four curves and R47a/b/c are complete. Results, default decisions, faithful /5.2 Rust and the fifth-strategy assessment are in the [delivery documentation](../v2-kernel53.md). Each objective is closed against its original criteria; experiments were not extended indefinitely to obtain a positive result.
