# Version 5.2: mechanism changes and compatibility

2026-11-09. This describes the new version authorized by the author. The actual integration and verification times are recorded in HANDOFF. This document alone does not indicate completion of the scientific comparison. [中文](version-change.zh.md)

## Changes

Two version-owned settings are added: `decay_curve` selects exponential, logarithmic or power-law decay; `retention_relaxation_enabled` controls relaxation of the timescale extended by experience. The exponential option preserves the 5.1 update order. Enabled relaxation retains the original linear rule. Disabling it stops timescale relaxation while connection weights continue to decay. These are new dynamics options, not merely implementation optimizations.

The logarithmic option uses an inverse-logarithmic function; the power-law exponent is fixed at one. For a reinforcement contribution with effective age \(a=\int dt/H(t)\), the retained fractions are

\[
F_{\rm exp}(a)=2^{-a},\qquad
F_{\rm log}(a)=\frac{1}{1+\ln[1+(e-1)a]},\qquad
F_{\rm power}(a)=\frac{1}{1+a}.
\]

All equal one half at \(a=1\). For exponential decay, \(H\) is the half-life parameter; across curves it is called the decay timescale. If \(H\) relaxes, the actual first half-value time also depends on that process. Existing `memory_half_life_*` field names remain for interface compatibility; 5.2 parameter descriptions use decay timescale.

The new curves apply to both directed connection weights and persistent node support. Non-exponential curves preserve each accepted reinforcement amount and its elapsed age. New reinforcement adds a zero-age contribution without resetting older ages; damage proportionally scales existing contributions. Equal-age entries can be merged exactly; no approximate history deletion is introduced. Fast activation, inhibition, fatigue, synaptic resources, energy rules and event ordering inherit 5.1 behavior. Mathematical, implementation and cost evidence is recorded separately.

## Why a distinct version

A different decay curve changes how experience is retained. Equal current weights can therefore lead to different later responses. Non-exponential curves also need contribution ages to preserve evolution across pauses, observation, saving and restoration. Version 5.2 has separate kernel, hypothesis and state identities and rejects 5.1 states instead of converting them implicitly.

The curve is selected at birth and cannot be hot-switched. The relaxation switch can be changed through an explicit current-state configuration operation that neither advances time nor jumps current physical weights. Ordinary development remains continuous; research branches are separately registered. Old implementations, states, evidence and the installed native module remain intact. Adding 5.2 does not change the project's default version.

## Available capabilities

Version 5.2 initially provides the Python reference backend and explicitly rejects a native-backend request. JSON and binary artifacts preserve contribution ages; exact complete-state restoration is supported. Structural inheritance is not exposed until a rule specifies which contributions and ages offspring inherit. Restoration and inheritance are different operations. Each personal adapter retains its own weights, optimizer, random state and recent activity.

## Scientific evaluation

R46a uses fixed stimulus adapters and a full temporal measurement instrument to compare connection retention, forgetting of weak exposure, cue-driven history-dependent activity, conditional long-term decay and cost. The complete joint task with three personal temporal Transformer adapters will be registered separately. That layer will test whether retention improves sound, visual and action answers and examine rule reversal. Each layer answers its own explicit question.

Non-exponential curves store more history and may increase memory, artifact size and runtime. The inverse-logarithmic tail can also make strong connections decay extremely slowly. These are comparison outcomes, not assumed benefits. A default candidate must be chosen from measured results, not curve shape or connection count alone.
