# Kernel 6.2 configuration and mechanisms

This document describes the 6.2 implementation. Kernels 5.1, 6.0 and 6.1, and existing research copies, retain their own saved rules.

## Stability-based retention

`consolidation_mode="stability"` selects stability-based retention. Each connection stores its base weight w, stability s and recent-transmission trace e. Both s and e range from 0 to 1. Actual transmission continues to reinforce w under the existing rule. Co-stimulation, actual transmission and applicable novelty enhancement can increase s. Setting `stability_growth_enabled=False` stops increases in connection stability without disabling weight reinforcement.

Each connection updates through its own local events. For a propagation period Δt in seconds, the recent-transmission trace decays as `e ← e exp(−Δt/eligibility_tau)`. With stability relaxation enabled, `s ← max(0, s−Δt/stability_tau×(1−e))`. Setting `stability_relaxation_enabled=False` stops this relaxation; the existing `stability_decay_enabled=False` also disables stability decay.

If the connection has not transmitted during the current period, its base weight changes as follows:

`w ← w × max(0, 1−0.1×forgetting_rate×[1−(0.08+0.92s)])^(Δt/0.1)`.

With the default propagation period of 0.1 seconds and forgetting_rate of 0.025, this becomes `w ← w×[1−0.0023×(1−s)]`. Actual transmission exempts the connection from this decay step for that period. This exemption and protection of stability by the recent-transmission trace are both retained. Previous single-component ablations did not establish that both could be removed together.

Stability-based retention does not use the H time scale to determine connection weight decay. H growth and relaxation belong to the single-age decay option. Kernel 6.2 rejects a combination of these mechanisms for which no joint formula has been defined. Nodes retain the automatic retention rule of 6.1; manual node retention is not restored.

Local events do not traverse the entire graph. However, stability-based retention continues to update stability and weights after connections become silent. It therefore requires more events than single-age decay, which can directly calculate a silent connection's expiration time. These are different dynamical rules, and their costs are reported separately.

## Separate connection signal thresholds

`signal_threshold` is the common value. Activation signals use a non-null `activation_signal_threshold`, falling back to the common value otherwise. Inhibitory signals independently use `inhibition_signal_threshold` or the common value. An explicit zero removes the signal-amount cutoff for that signal type. Setting `signal_threshold_enabled=False` disables both connection signal-amount cutoffs.

Both signal types use the same transmission procedure, with their own effective value at the threshold comparison. Explicit equal values remain stored as two overrides; they are not rewritten as a common value. This preserves both the numerical behavior and the configuration the author selected.

The comparison concerns signal amount after the connection's transmission calculation. Source-node sending thresholds, the base-weight transmission gate and the weight deletion threshold remain separate conditions with separate fields and meanings.

## Research presets

The inertial-reversal preset sets the common connection threshold to 0.004, clears both type-specific overrides and enables the threshold switch. The short-inhibition-decay preset keeps inhibition enabled and sets its time constant to 0.0580338705786432 seconds. The stability-retention preset selects stability-based retention, enables its own growth and relaxation, and disables H growth and relaxation.

These presets expand into visible parameter values. In the 6.2 interface, applying a preset changes only its listed fields, so presets can be combined. The complete configuration is saved with the individual. Inertial-reversal and short-inhibition-decay presets are not enabled unless selected by the user.
## 14 November 2026 addendum: weight reinforcement by each signal type

At the author's request, 6.2 adds `activation_weight_reinforcement_enabled` and `inhibition_weight_reinforcement_enabled`, both defaulting to `True`. Python, Rust, API, commands and frontend use the same fields.

Let p and n be the amounts of excitation and inhibition successfully transmitted, A and I their weight-reinforcement switches, and L the existing inhibitory-learning master switch. When plasticity and connection reinforcement are enabled, `w ← min(1, w + associative_gain × (A·p + L·I·n))`. Disabling one switch removes only that signal type's contribution to this weight increment. Co-stimulation reinforcement retains its original rule.

Fast enhancement, recent-transmission state, stability and time-scale growth still use the original learning amount `p + L·n`. The new switches therefore isolate base-weight reinforcement. The older `inhibitory_learning_enabled` switch has a broader scope across learning states.

Earlier 6.2 snapshots lack these two fields. Restoration verifies their original definition and checksum before supplying the enabled defaults, preserving the former behavior without rewriting the originals. Historical kernel implementations and identities remain unchanged.
