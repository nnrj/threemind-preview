# LIF candidate lif/1: equations, identity and validation boundaries

[中文](../../zh/plans/lif-candidate.md) · [Implementation record](multi-kernel-implementation.md)

Scientific identity `threemind.lif/1`; recovery schema `threemind.lif-state/1`; hypothesis identity `threemind.hypotheses/lif1`. This is an independent candidate. It neither replaces causal/9 or continuous/1 nor converts existing consciousnesses. Every state binds configuration, trusted operator order and its hash. Python and Rust implementations exist as of 2026-09-28; completion is tracked in the implementation record.

## Local physical model

Each receptor stores membrane voltage V (mV), synaptic current I (nA), adaptation current A (nA), refractory deadline and its own spike history. MΩ × nA = mV. Between event boundaries, analytic evolution solves:

```
τm dV/dt = −(V − Vrest) + R (I − A)
τI dI/dt = −I
τA dA/dt = −A
```

Thresholds are tested only on a fixed simulation lattice, initially 250 μs. At −50 mV the receptor spikes and resets to −65 mV. The default 2 ms refractory interval clamps voltage at reset while currents still arrive and decay. Each spike adds 0.01 nA to A. Defaults are 20 ms membrane, 5 ms current and 100 ms adaptation constants, and 100 MΩ resistance. These are configurable phenomenological examples, not calibrated human-brain parameters. Leak, current decay, adaptation increments, timing plasticity and short-term release can be ablated independently.

Sources: [passive RC, threshold and reset](https://neuronaldynamics.epfl.ch/online/Ch1.S3.html); [leaky models with adaptation](https://neuronaldynamics.epfl.ch/online/Ch6.S1.html). This uses linear leak and spike-triggered adaptation, not a claim to reproduce all ion channels.

## Input, growth and learning

Existing sensory mapping, framing and text normalization remain unchanged. Positive input injects `amplitude × intensity × input_gain_na`. New channels create receptors on demand. Receptors actually contacted by the same input frame may form directed connections with weight `birth_weight × min(1,a×intensity) × min(1,b×intensity)`, initially birth coefficient 0.05. There are no random prewired graphs, semantic labels or prescribed brain regions. Co-input growth is an explicit ThreeMind modeling choice, not a proven biological neurogenesis law.

Each synapse has presynaptic arrival trace p and postsynaptic spike trace q, both initially decaying with 20 ms constants:

```
Actual arrival: w ← max(0, w − A− q); p ← p + 1
Target spike:   w ← min(1, w + A+ p); q ← q + 1
Defaults A+ = 0.01, A− = 0.0105
```

Arrivals precede same-time threshold tests, so zero-lag pairing counts as arrival-before-spike. This discretization convention is versioned and subject to step convergence checks. The [local STDP example](https://brian2.readthedocs.io/en/stable/examples/synapses.STDP.html) informs the traces; its random weights and all-to-all initial topology were not adopted.

At each lattice point all firing nodes are identified, then their postsynaptic updates complete, then emissions occur. Node traversal order therefore does not teach a different ordering. Emitted current is `weight × spike_gain_na × short-term release fraction`, initially gain 0.3 nA. Senders never consult target voltage, saturation or semantic correctness. The [same TM three-pool primitive](candidate-mechanisms.md) is used, here triggered by actual spikes; default delay is 1 ms.

STDP visits arrived connections and the incoming neighbors of firing nodes. Passive evolution visits active receptors. Observation and explicit reconfiguration may inspect full state without making full-graph traversal a default solver step. Co-input growth is quadratic in the contacted frame width, bounded by explicit receptor/edge capacities with rejection counters.

## Differences from the preserved kernel

| Aspect | Explicit lif/1 choice |
| --- | --- |
| Activity | Voltage displacement, synaptic current and adaptation current are physical state; spikes are events, not the only evidence of activity |
| Inhibition | Local spike-triggered adaptation only; no inhibitory cell classes or original topology-based inhibitory diffusion |
| Structure | Receptors and connections do not automatically prune at rest; STDP changes weights, including zero. Explicit deletion and disconnection remain available |
| Long-term retention | No causal/9 stability, support, eligibility protection or forgetting rules are falsely exposed as implemented mechanisms |
| Energy/space | No causal energy ledger, input modulation port or causal spatial embedding. Unsupported requests are rejected; display layout is not physical geometry |
| Randomness | No random growth or spontaneous noise in this version; identity seed is retained |

These differences define another testable hypothesis, not an empirically superior replacement. The system default remains causal/9.

## Life and observation

“No spike this step” is not death: subthreshold currents and voltage evolution are activity. This candidate counts any nonzero voltage displacement, synaptic current or adaptation current above its corresponding tolerance. All three must subside before snapping to rest. Initial tolerances are 10⁻⁶ mV and 10⁻⁸ nA. Zero removes that numerical cutoff and may prevent practical quiescence. Before first activity, state is waiting. Afterwards, all receptors remaining quiet for one simulation second means death. Same-time arrivals and spikes precede that decision; pausing does not advance simulation time. Death preserves structure and does not automatically revive.

This is the `lif1` physical-activity definition. It is not backported to causal/9. In particular, adaptation current is a physical evolving quantity here, not the original kernel's abstract residual inhibition scalar. Changing which physical processes count requires an explicit comparison or version.

Graphics and existing temporal readers may use `clip((V−Vrest)/(Vthreshold−Vrest),0,1)`, labeled `normalized-depolarization`, unit 1. It is neither original activation nor firing rate. Readouts carry the quantity, formula and kernel identity. Models preserve full membranes, synapses, resources and pending traffic. The checkpoint-pinned `/physical-state` endpoint paginates raw voltage, currents and cumulative spike counts. Zero placeholders such as stability in compatibility graph rows are not scientific measurements for this candidate.

The original 100 ms reader interval can miss brief spikes. Lab defaults to `record_spikes=true`, separately retaining actual spike times and firing nodes. Dynamics, the paginated `/spikes` endpoint and raw event export expose them. CLI ReadoutSession also delivers spikes when an event sink is present. Disabling recording leaves state hashes unchanged; observing spikes does not copy every synaptic arrival. See the [guide](../v2-kernels.md) for buffers and budgets. A missing character in a temporal display is not proof of absent physical response.

## Restoration, inheritance and damage

Exact restoration retains all physical quantities, STDP traces, short-term resources, traffic, lattice and quiet timer. Structural inheritance is separate: retain receptor identities and slow weights; reset voltage, currents, spikes, traces, resources, traffic and time. The parent stays unchanged.

Disconnection does not retract sent traffic. A recreated edge has a new generation identity; old traffic can arrive but cannot train it. A recreated channel receptor has a new node identity and cannot receive traffic sent to its predecessor. Temporary silencing clears the selected receptor's activity and blocks new reception until released.

Acceptance includes analytic RC checks, lattice timing error, STDP order, advance partitioning, cross-backend restore, deadline arrivals, damage, artifact and independent Rust runtime interoperability. Engineering equivalence does not establish paired memory, relational composition or AGI.
