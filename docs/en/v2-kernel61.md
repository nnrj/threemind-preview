# 6.1: local deletion and separate sender thresholds

13 November 2026. The author approved local deletion, an optional whole-graph scan, separate activation and inhibition sender thresholds, and emission implementation optimizations. The identity is `threemind.continuous-memory/6.1`. New instances default to 6.1; saved individuals retain their own identities. Implementations of 6.0 and earlier kernels remain unchanged.

## Object-local deletion

Each connection computes its next check directly from its current weight, decay age, retention timescale and deletion threshold. Creation, reinforcement and declared parameter interventions replace that connection's deadline. The indexed queue holds at most one deletion deadline per connection and does not accumulate stale entries.

At the deadline, the engine settles that connection and compares its actual weight with the threshold. It deletes only when the weight is lower. A reinforced connection receives a new deadline. Deletion notifies only the two endpoints. An inactive node with no effective connections is deleted when its support falls below the existing threshold; otherwise it receives its own support deadline.

Checks remain on the original internal-time grid, spaced 0.1 seconds by default. Arrivals, local novelty and emission run before deletion at the same time. If removal of the last connection leaves an already eligible node, that node is removed in the same deletion phase. Advancing internal time triggers due events. Observation, saving and host delays do not advance the simulation.

`deletion_strategy` accepts `local` (default) or `global-scan`. The latter checks the graph at every grid point. A declared paused reconfiguration may switch strategies, settle objects once and rebuild their deadlines. This intervention is distinct from passive observation. Other options, including the explicit `scan-control` propagation control, remain separate.

All four single-age curves have direct inverses. There is no reinforcement-history sum, binary search or periodic check of every edge. For inverse-logarithmic decay, with current weight (w), threshold (q>0), age (a), and (k=e-1), the age increment to threshold is

\[
\Delta a=(a+1/k)\operatorname{expm1}[(w/q-1)(1+\ln(1+ka))].
\]

For a constant timescale, elapsed internal time is (H\Delta a). When the existing timescale relaxation is enabled, its age integral is inverted analytically. The result is rounded upward to the existing grid. Actual deletion still requires a strict less-than comparison. Extremely distant or unrepresentable deadlines are capped at (10^{12}) internal seconds before rechecking that object alone. This numerical safeguard is not a graph scan. A zero deletion threshold schedules no weight-based deletion.

## Separate activation and inhibition offers

| Parameter | Default | Source state compared |
| --- | ---: | --- |
| `activation_send_threshold` | 0.004 | Activation |
| `inhibition_send_threshold` | 0.002 | Inhibition |

Below its threshold, the node offers no signal of that type. When neither activity supports emission and no incoming input remains to be processed, recurring emission stops. New stimuli or arriving signals may restart it. Zero disables the corresponding threshold, but positive activity is still required.

These controls are separate from node activation zeroing and the connection-level signal threshold. The existing `propagation_activation_min` remains effective, defaulting to zero. The existing `inhibition_sender_gate_enabled` remains off by default; enabling it additionally gates the offered inhibitory signal amount. Short-term resources, transmission, learning and energy rules are unchanged. Sender thresholds reduce weak emission, associated expenditure and learning opportunities; this is an explicitly versioned dynamics change.

## Equivalent implementation changes and compatibility

Rust parses frequently used options into typed fields at construction and explicit reconfiguration. Short-term resource and enhancement states use numeric runtime timestamps. Serialization retains string timestamps and accepted leading zeroes. Emission avoids redundant state lookups and copies, and allocates a feature vector only for an actual excitatory packet, using values captured at the original point in the transition.

Python and Rust implement the same version contract. Tests compare 6.1 with global deletion and zero new sender thresholds against complete historical 6.0 trajectories. This setting does not disable existing connection-level thresholds or node zeroing. Local and global deletion have different audit work and lazy-settlement anchors; each retains its real state rather than claiming byte equality between strategies.

6.1 retains `threemind.birth/2`: persistent state and decay age are inherited by default, with an explicit age-reset alternative; offspring fast state and internal time are initialized afresh.

See the [engineering protocol](../../lab/explorations/2026-11-13-kernel61/protocol.md). Scientific courses require explicitly registered 6.1 protocols; earlier 6.0 plans and historical results are not relabelled as 6.1 evidence.
