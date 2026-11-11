# Source audit before integrating 5.2

9 November 2026. Read-only audit of `local.py`, `local5.py`, `local51.py`, `retention.py`, and `registry.py`. The kernel has not been changed. [中文](integration-audit.zh.md)

## Scope

The separate version will add decay choices for persistent connection weights and node support, retaining each object's local time scale. Activation, inhibition, fatigue, fast enhancement, synaptic resources, and event ordering retain their 5.1 rules. Existing local learning rules determine accepted increments; the selected curve determines their subsequent decay. The relaxation switch controls the decrease of the time scale, not ordinary weight decay.

Historical implementations, defaults, and state identities remain intact. An inspectable reference backend is a feasible first implementation. An unimplemented native backend must reject selection explicitly instead of substituting 5.1. Research records must identify the actual backend and its cost.

## Updates requiring explicit preservation

|Operation|Existing change|Requirement for nonexponential candidates|
|---|---|---|
|`_birth`|Initial node support and minimum H|Record support as a contribution at birth|
|`_touch`|Accepted stimuli increase support and H|Settle old contributions, record the accepted increment, and preserve old ages when H grows|
|`_associate`, new connection|Initial weight, possibly with an immediate novelty bonus|Contributions at the same instant may merge; preserve birth conditions, direction, and cap|
|`_associate`, existing connection|Weight increase based on activation, preceding transmission, and intensity|Record only the increment accepted below the cap; rejected increments must not refresh old memory|
|`_emit`|Actual associative transmission increases weight and H and updates fast states|Preserve the transmission-dependent learning condition and separate fast states|
|Novelty expiry event|A delayed novelty bonus may increase weight|Use the actual event time, not the connection's birth time|
|`_maintenance`|Energy shortage proportionally damages support and outgoing weights|Scale old contributions before subsequent learning; do not combine damage and reinforcement into a single net increment|
|`reconfigure`|Settle old parameters, apply allowed changes, and reschedule expiry|Settle age under old parameters until the intervention; prohibit changing curve identity and silently reinterpreting history|
|Deletion, dormancy, awakening|Threshold-dependent lifecycle changes|Preserve or delete the complete corresponding state; awakening must not reset memory age|

Replacing `decay()` alone is insufficient. Local state, expiry calculations, and restoration validation also require version-specific implementation.

## Time, storage, and interfaces

Node and edge projections are read-only. Queries must not write ages or add contributions. Actual event settlement advances age by `integral(dt/H)` exactly once. Contribution histories belong in complete state images, object chunks, digests, and restoration validation, rather than process-local caches.

Existing timers invert exponential decay analytically. New curves require their own inverse or monotone root calculation. A tail beyond the representable internal-time horizon must be recorded explicitly as not crossing within that horizon, without overflow, premature deletion, or omitted finite deadlines. The original strict threshold semantics must remain clear.

Validation must check contribution amounts, age order, agreement with current values, curve identity, and expiry. Exponential-only validation cannot simply be reused. A new state schema must preserve the old 5.1 restoration path. The registry, runtime object codec, and offspring creation each contain explicit version handling. If offspring inherit connection state, contribution-age inheritance needs a declared rule; unsupported paths must reject operation rather than lose age silently.

## Minimum acceptance checks

1. Exponential decay with original relaxation reproduces the 5.1 trajectory; all historical regression witnesses still pass.
2. All six conditions preserve internal time, event ordering, and lifecycle across split advancement, observation frequency, host pauses, complete restoration, and the next input.
3. Independent calculations cover birth, cap clipping, reinforcement of old contributions, delayed novelty, and starvation damage followed by learning.
4. With relaxation disabled, time alone does not reduce H, while weights still decay. Enabled relaxation follows the original linear rule and stops at the lower bound.
5. Validate dormancy, awakening, long-tail expiry, and rejection of missing contributions, future ages, negative/nonfinite values, wrong versions, and incorrect deadlines.
6. Measure contribution counts, peak memory, storage, and wall time. Do not silently merge unequal-age contributions or truncate tails to reduce cost.

The ten existing mathematical tests cover formula properties only. Each contribution stores its own elapsed age, avoiding cancellation when a recent birth age is subtracted from a very large cumulative age. These integration checks remain to be executed after implementing the genuine 5.2 candidate.
