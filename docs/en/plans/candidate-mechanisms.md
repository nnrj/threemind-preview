# Candidate mechanism primitives and calibration

[中文](../../zh/plans/candidate-mechanisms.md) · [Implementation record](multi-kernel-implementation.md)

2026-09-28: these are isolated primitives. Passing them does not establish complete kernel integration or improved pairing, reasoning or AGI. Causal/9 does not call them. All time is simulated; UI frames and host speed are absent from equations.

## Short-term resources: threemind.tm-synapse/1

Each edge stores available fraction x, active fraction y, utilization u and last-update time; inactive fraction z=1−x−y conserves total resources. Between events:

```text
dy/dt = −y/τI
dz/dt = y/τI − z/τR
x = 1−y−z
du/dt = −u/τF             (when facilitation is enabled)
```

Recover to event time, update u←u+U(1−u) (or u=U without facilitation), release r=ux, then x←x−r and y←y+r. U=0 stops release; τF=0 disables facilitation. Disabling the whole operator bypasses it: U=0 is not neutral. Exact exponentials include the equal-time-constant limit.

This follows a [published synaptic model](https://brian2.readthedocs.io/en/stable/examples/frompapers.Tsodyks_Uziel_Markram_2000.html). Calibration U=0.5, τI=0.003s, τR=0.8s without facilitation belongs to one example class, not all biology. Facilitation calibration uses U=0.04, τR=0.1s, τF=1s. Demonstration topology, population ratios and increased background input are not inherited.

Applying a presynaptic update to an eligible continuous emission attempt is a ThreeMind abstraction, not replicated biological spikes. The integrated order is specified below.

## Fast trace: threemind.leaky-fast-trace/1

Each edge has f∈[0,1] and last time. Between events f(t+Δ)=f(t)exp(−Δ/τf). Actual transmission q updates:

```text
f ← f + (1−exp(−ηq))(1−f)
effective_weight = min(1, slow_weight + g*f)
```

The primitive never modifies slow weight or reads instantaneous destination state, answers or rewards. η=0 disables accumulation; g=0 disables transmission influence. τf=2s, η=0.1, g=0.1 are explicit candidate scales, neither biologically fitted nor language-tuned. This bounded local leaky integrator has a circuit interpretation; a particular biological correspondence is unconfirmed.

[Fast-weight research](https://proceedings.mlr.press/v139/schlag21a.html) motivates separating time scales. This scalar trace is not that paper's matrix memory, learned controller or delta rule, and is not Transformer equivalence. A complete small Transformer comparator is separate work.

## Receiver-local addressing: threemind.local-context-attention/1

For already delivered messages at one receiver, local query q, keys kᵢ and raw amounts aᵢ:

```text
sᵢ = dot(q,kᵢ)/(sqrt(d)*T)
pᵢ = exp(sᵢ−max(s))/sum(exp(sⱼ−max(s)))
response = sum(aᵢ*((1−m)+m*pᵢ))
```

m∈[0,1]; m=0 neutrally preserves the sum. T>0 defaults to 1; m=1 is primitive calibration. Dimension is bounded. A single arrival retains its amplitude; multiple arrivals undergo explicit allocation, not unprocessed readout. Preserve raw messages, allocation coefficients and sent energy.

The primitive does not invent, train or globally find queries/keys. Callers must bind local sources, update order and recovery state. It is not a semantic/causal relevance detector. The continuous candidate's binding follows.

## Integrated continuous execution order

`threemind.continuous/1` owns `threemind.continuous-state/1`, without replacing causal/9. Each new operator has a switch; disabling all preserves baseline transitions. Enabled candidates retain V3 birth, co-touch learning, inhibition, forgetting and life rules.

1. Source activation, source inhibitory response, slow weight plus fast trace, and optional spatial attenuation determine attempted amplitude. Apply the original per-edge threshold first.
2. A propagation-budget rejection does not release resources. Otherwise, recover/update short-term state and multiply by released fraction.
3. Settle optional energy once, recording actual sent amount. A now-subthreshold amount is recorded as discarded, not queued or rescued by aggregation.
4. Queue qualified amounts with the existing delay and consolidate slow edges by the preserved rules. Fast traces update from actual qualified sent amount only when plasticity is enabled. Destination state is never consulted by sending. Short-term depletion is transmission state and may continue when long-term plasticity is off.
5. Allocate only on arrival. A source's snapshot key contains `[activation, touch trace, inhibition/(1+inhibition), exp(−time since last touch/τcontext)]`; the query contains the same receiver-local quantities. Dimension is four. Names, semantics, answers and rewards are absent. This explicit local state-similarity hypothesis is neither a validated best feature set nor a fitted neuron model.
6. Competition involves messages from one emission batch arriving at one receiver, not global normalization across batches. Preserve raw messages, coefficients and response. The receipt ledger counts raw arrivals; allocated response then encounters receiver inhibition/saturation. Observers do not discard raw activity through semantic filtering.

Recovery includes the complete definition/hash, per-edge short-term/fast histories, clocks and in-flight source keys. Disconnecting removes edge history without recalling emitted traffic; a deleted target cannot redirect messages to a later identity. Reconfiguration first settles histories using old parameters, then changes parameters. These lazy clocks are independent of the baseline integration lattice. All switches and scales are explicit; no language-outcome tuning has occurred.

## Passive membrane: threemind.rc-membrane/1

The separate membrane kernel uses an [RC/LIF model basis](https://neuronaldynamics.epfl.ch/online/Ch1.S3.html):

```text
τm*dV/dt = −(V−Vrest) + R*I
dI/dt = −I/τs
```

Units: mV, nA, MΩ, seconds; MΩ·nA=mV. Exact passive evolution retains subthreshold activity and returns to rest without input. Equal/near-equal time constants use a stable analytic limit. Calibration Vrest=−65mV, R=100MΩ, τm=20ms, τs=5ms is explicit and does not claim a fitted cell.

The primitive does not hide thresholds, resets, refractory periods or plasticity. A complete LIF kernel must separately specify those rules and spike-timing error, and prevent false death between spikes while subthreshold activity remains. Voltage cannot simply replace legacy activation under a compatibility claim.

## Verification and remaining work

Seventy-five primitive, continuous and frozen-baseline tests pass, covering Python/Rust primitives and full state, resource conservation, depletion/recovery/facilitation, time-constant limits, partitions and cross-backend recovery, operator ablations, raw receipt/cost accounting, target-independent sending, disconnection/deletion and corrupt-state rejection. Cross-backend comparisons retain the baseline libm tolerance; same-backend restoration preserves hashes exactly.

Subsequent acceptance covers artifacts, Lab creation/restoration/import/export, temporal readouts and a small engineering comparison; see the [implementation record](multi-kernel-implementation.md). The full independent [lif/1 candidate](lif-candidate.md) now exists. The RC primitive described here still covers passive numerical evolution only, not the full spike mechanism. Engineering acceptance does not establish research gains.
