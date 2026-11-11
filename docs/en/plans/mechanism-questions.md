# Open mechanism questions

[中文](../../zh/plans/mechanism-questions.md)

These proposals do not replace the restoration baseline. Confirmed facts, accepted decisions and validated implementations are different statuses.

| Question | Established fact / current decision | Status |
| --- | --- | --- |
| What is a node; should it persist forever? | Do not equate it directly with a biological neuron. Zero activation does not immediately delete a node; old joint pruning is restored | Open |
| Physical basis of decay | Old `_decay_nodes` runs independently of the energy switch. A more specific physical explanation or coupling remains undecided | Fact confirmed; new hypothesis open |
| Isolated nodes and disconnected subnetworks | Both are legal, including with energy disabled; no forced attachment to the main graph | Confirmed, implemented and validated |
| Refractory period | Existing self-inhibition can reduce short-term responsiveness. There is no separate refractory timer | Existing base mechanism; separate timer open |
| Stronger neighbors inhibit weaker ones | Optional spatial competition compares activations. Default topological inhibition does not require the sender to be stronger | New default rule open |
| Inhibition directly accelerates existing activation decay | Default inhibition weakens new responses and propagation. No separate acceleration term was found | Open / unimplemented |
| Excess activation switches to inhibition | No explicit conversion rule was found. Activation rises generating inhibition are a different mechanism | Open / unimplemented |
| Why dispersed structures became less visible | Finite telemetry channels, synthetic disturbances, co-frame birth and display sampling are distinguished below | Local facts confirmed; longitudinal explanation needs experiments |
| Simpler memory rules | Local traces, stability and history can have separate timescales/couplings that yield retention and forgetting; investigate removing explicit traversal exemptions | Candidate only |

Using a node's or edge's own local state in its evolution does not require an external observer. An external module preserving links because of human-assigned importance or expected answers is a different intervention and must not enter default dynamics.

## Withdrawn defaults retained for discussion

- causal/7 summed weak paths into the receiver before using `activation_floor * step_seconds`. The restored default gates each edge. Aggregation remains a possible separate model choice; evidence has not justified replacing ThreeMind's baseline with it.
- causal/7 substituted `min(cap,q)` for `cap*tanh(q/cap)` and bypassed the old response soft curve. Simpler syntax is not sufficient grounds for that change.
- causal/7 independently exponentially decayed node support/stability and edge stability, with `dw/dt = -forgetting_rate*w/(1+4*s)`, removing eligibility and traversal exemption effects. This remains a separate candidate, not an equivalent restoration.

No fixed brain regions, arbitrary random edges, semantic novelty rewards, or importance-based preservation are introduced to force a desired picture.

## Source inspection of dispersed structure

- `telemetry.py::TelemetryEncoder.encode` reuses level/rise/fall receptor identities per metric. CPU changes alter amplitude rather than continually introducing new identities. The accepted input protocol is unchanged.
- `body.py::AmbientField.sample` reuses finite synthetic baseline channels; its separate disturbance frames use incrementing identities and finite lifetimes. This is an explicitly synthetic fixture, not measured host telemetry. Independent subnetworks depend on actual nonzero co-frame channels and learning policy.
- The restored kernel has no forced attachment to the main graph. `test_disconnected_subnetworks_are_not_forced_into_existing_component` verifies two independently stimulated subnetworks and a singleton without inserting arbitrary edges.
- Restored joint pruning changes structural persistence relative to causal/7. `graph.worker.ts` display caps and layout affect observation only; absent pixels do not prove deletion, and screen distance is not causal distance.

These are established contributing mechanisms, not a proven explanation for a particular historical visualization. Its fixed input/configuration evidence is unavailable; no unique cause is invented.
