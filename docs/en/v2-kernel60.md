# 6.0: fixed-function addressing

[中文](../zh/v2-kernel60.md)

Implemented under the author's authorization of 12 November 2026: change stimulus-to-node addressing first, retain the other 5.3 mechanisms, and give 6.0 its own implementation. An address here is a **virtual node identifier** in the network, not an operating-system memory address.

## From stimulus to node

The existing stimulus interface accepts unsigned 32-bit codes. Version 6.0 uses the fixed function

\[
F(c)=c,\qquad c\in\{0,\ldots,2^{32}-1\}.
\]

Input adapters encode external signals into values accepted by the interface. The Core computes the address and looks for a node there. If the node exists, it receives the stimulus; otherwise the Core creates it under the existing birth and capacity rules. A code always produces the same address, independently of the order in which codes first arrive. Zero-amplitude inputs and capacity exhaustion retain their 5.3 behavior.

The Core no longer maintains a `receptors[stimulus code] = sequentially assigned node ID` table. Its node container holds live node objects under their fixed addresses. The container's storage index locates objects; it does not assign a separate set of node identities to stimulus codes. Storage is proportional to the number of nodes created, not the size of the code range.

Node rows retain `channel` for existing observations and peripherals. In 6.0 it must equal `id`, and restoration rejects inconsistent rows. `birth_count` counts births and does not participate in addressing. The historical `next_node` counter is absent from 6.0 checkpoints.

After deletion, the same code can create a node at the same address. Support, fatigue, decay age and connections are initialized under the birth rules rather than recovered from the deleted object.

## In-flight signals after node recreation

On 12 November 2026, the author reaffirmed that both policies should be available, with option 2, delivery to the address, as the default. Select `inflight_delivery` when creating a 6.0 individual:

| Option | Configuration value | Behavior |
| --- | --- | --- |
| 1: discard signals sent before recreation | `same-birth` | The receiver must have existed when the signal was sent and must not have been deleted and recreated since |
| 2: deliver to the address (default) | `address` | Deliver to the node that exists at that address on arrival, including a recreated node |

Neither policy creates nodes from in-flight signals. If no node exists at the address on arrival, the signal is not received. Deleting the sender does not recall excitation or inhibition already sent to a surviving receiver. A wake event concerns a connection: option 1 requires both endpoints to retain their original lifetimes; option 2 applies the existing awakening rules at the endpoint addresses.

The implementation adds a node birth ordinal, `birth_serial`. Under option 1, each internal event also stores the cumulative birth count at emission as `birth_limit`. A replacement node has a higher ordinal, so old signals can be excluded without retaining deleted-node histories or restoring an allocation table. These ordinals identify lifetimes only; addresses still follow `F(c)=c`. Ordinals, event limits and the selected policy are saved in complete checkpoints. The policy is fixed at creation.

## Preserved rules and consequences of addressing

Parameters shared with 5.3 retain their task-start defaults: inverse-logarithmic decay, continued age on reinforcement, and retention-scale growth and relaxation disabled. Exponential, power-law and power-then-exponential decay remain available. Activation, inhibition, fatigue, refractoriness, connection formation and reinforcement, fast traces, synaptic resources, energy accounting, structural checks, dormancy and awakening retain the baseline rules.

Eligibility traces still contribute to connection-stability updates. Node stability still affects local plasticity, and these states also form part of observation and persistence. They were therefore retained.

Changing node identity has concrete consequences. Spatial positions and energy regions still use the original identifier-based functions, and simultaneous operations retain identifier ordering. Replacing birth-order identifiers with stimulus codes can therefore change particular positions, regions and simultaneous ordering for a historical course. Stable addressing does not promise identical trajectories for arbitrary old courses. Engineering comparisons use inputs for which the two versions have matching node identifiers to test the remaining rules directly.

## Independent implementation and version boundaries

- Python: `src/threemind_kernels/local60.py`, `local60_config.py` and `decay60.py` own the transitions, validation and decay calculations. They neither inherit nor import the 5.3 kernel.
- Rust: `crates/threemind-core/src/local60.rs`, `local60_transitions.rs` and `local60-defaults.json` execute the rules independently, with native bindings and a standalone runtime.
- Shared components are protocol types, timestamps, object containers, elementary numerical mechanisms and energy accounting. Observation, saving and host delays do not advance internal time.
- Identity: `threemind.continuous-memory/6.0`; checkpoint schema: `threemind.continuous-memory-state/6.0`. Relabeling a 5.3 checkpoint is not valid restoration, in either direction.
- The API, CLI and workbench allow explicit selection of 6.0. The global creation default remains 5.3; existing individuals retain their saved versions and configurations.

The initial implementation on 12 November 2026 did not define inheritance of decay age and explicitly rejected structural birth; complete-state saving, restoration and research copies remained available. On 13 November, the author's approved revalidation plan v2 supplied the rule described below.

## 13 November 2026: reproduction in 6.0

The new rule is `threemind.birth/2`. Offspring inherit persistent node and connection state at the parent's saved observation time: weights, support, stability, local plasticity, use counts, retention scales, energy regions, dormancy and accumulated decay age. Age is preserved by default. The `reset` control sets inherited decay age to zero while keeping the other persistent values identical.

The child's internal clock starts at zero. Activation, inhibition, fatigue, recent traces, short-term enhancement, synaptic resource-use state and pending events are initialized anew. Parental intervention masks are cleared. Virtual addresses remain unchanged; birth ordinals are assigned anew. Core energy follows newborn configuration, while the ecological ledger continues accounting for bodily reproductive costs. Ordinary pause/resume and exact research copies retain full state and do not call birth.

The Python interface is `birth(image)` or `birth(image, decay_age="reset")`. A 6.0 ecology protocol uses `inheritance_rule="threemind.birth/2"`; `inheritance_decay_age` selects `preserve` (default) or `reset`. The run API accepts the same option with `inherit=true`. Protocols, birth events and branch records identify the actual rule. Historical `birth/1` behavior remains unchanged.

Python and Rust restoration for 6.0 now permit inherited decay age to exceed the child's own lifetime: age comes from the parent while the child starts at time zero. Age must still be finite and nonnegative. This supports the authorized initial condition without changing decay formulas, addressing, transmission or defaults. Undefined births for 5.2 and 5.3 remain rejected.

See the [engineering and cost report](../../lab/explorations/2026-11-13-kernel60-revalidation/report.en.md) and [revalidation plan v2](plans/kernel60-revalidation-v2.md).

## Verification and subsequent research

Engineering tests cover fixed addresses, arrival order, 32-bit boundaries, deletion and recreation, address validation, cross-version rejection, Python/Rust restoration, complete queues, observation invariance and state-by-state comparisons with 5.3. Standalone-runtime checks also cover JSON, `.tmind` and SQLite interoperability.

These are implementation fixtures, not independent research subjects. Mechanism, shape–color and embodied experiments on 6.0 require separately registered protocols. This task starts none of them and does not change manuscripts or original evidence. See the [engineering report](../../lab/explorations/2026-11-12-kernel60/engineering-report.en.md).
