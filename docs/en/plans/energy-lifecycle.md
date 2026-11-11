# Energy-shortage damage and unified activity death

[中文](../../zh/plans/energy-lifecycle.md)

2026-09-09. The user approved retaining shortage damage while removing independent forced death. Continuous inactivity reaching the grace period is now the sole death rule. This closes the implementation conflict identified in the [V3 restoration record](v3-restoration.md).

## Boundaries

- The former `irreversible_energy_death_enabled` controlled maintenance, erosion and a starvation countdown. Expiry cleared activity, inhibition, traces and queued events, closed inputs and forced death. That branch has been removed from Python and Rust.
- The new `energy_starvation_damage_enabled=false` controls only optional maintenance and shortage erosion, jointly with `energy_simulation_enabled`. `energy_starvation_death_us` is removed. New configuration, JSON validation and saving reject both retired fields instead of silently reinterpreting them.
- Maintenance and erosion retain their formulas: unpaid maintenance fraction $d$ multiplies node support, edge weight and stability by $\exp(-\lambda d\Delta t)$. Zero maintenance cost creates no corresponding deficit; zero erosion rate disables erosion. Disabling the damage switch disables both maintenance and erosion. Natural decay, learning and joint pruning retain their own rules.
- A zero reserve cannot erase existing activation. A consciousness with ongoing activation remains alive even through prolonged shortage.
- Before the first activation, life remains waiting. After birth, all nodes must stay inactive for `quiescence_death_us` (default 1,000,000 μs) before death. Supply alone, ineffective external inputs and in-flight signals that have not activated a node do not reset this timer.
- Events at the same timestamp arrive before death is checked. Already-paid in-flight excitation may activate a node at zero reserve, without charging transmission twice. Supply at the deadline without activation does not prevent death.
- Death retains structure and queued evidence and halts further execution. Supply or new inputs cannot resurrect the same consciousness. Explicit inheritance still creates a new individual.

## Versioning, accounting and interface

The dynamics version is `threemind.causal/9`; the state remains `threemind.state/6` because its field structure is unchanged. Configuration and lifecycle semantics changed. A small original causal/8 artifact is frozen in `tests_v2/fixtures/causal8-energy-before-unification.json`, with source commit `304ef25` and its digest. Old artifacts remain read-only; JSON/`.tmind` exchange preserves original fields and hashes and cannot silently resume or inherit under the new rules.

`starved_since_us` records zero reserves without imposing a death deadline. In causal/9, `death_us` records the death timestamp determined by the common activity rule, not an energy-specific cause or control. Ledger conservation and timestamped supply protocols are unchanged.

The energy settings now expose shortage damage and no starvation death duration. The energy panel explains that shortage does not directly force death. Historical evidence retains its historical labeling rather than relabeling old forced deaths as activity deaths. CSV retains retired parameter columns; JSONL retains original records.

No database migration is required; Lab schema stays at 48. No scan or conversion of `data/` is performed. Update native extensions, CLI and frontend while services are stopped, then validate with new consciousnesses.

## Validation

Coverage lives in `tests_v2/test_energy_lifecycle.py`, `test_energy.py`, `test_energy_supply.py`, `test_v3_restoration.py` and `threemind-ui/e2e/energy.spec.ts`. It includes both backends, independent Python/Rust CLI, JSON/binary restoration and supply/experiment workflows in isolated databases.

Completed: all 78 affected regression tests and all 17 follow-up tests passed, covering **83 unique test identities**. Rust workspace: 2 pass. Energy browser scenario: 1 pass. Native extension, standalone Rust Runtime and frontend builds passed, as did Ruff, Rust formatting and UI/source plus energy-parameter translations. Local `doctor` confirmed database connectivity and the native backend. The temporary acceptance service was stopped and only its owned test database and roles were removed.

A two-node, zero-reserve counterexample with natural activity decay explicitly disabled stayed active through 91 simulated seconds, beyond the former 90-second default starvation deadline. Shortage erosion continued, while disabling damage or setting its rate to zero prevented that erosion. Additional checks covered supply without activation, paid excitation at the deadline, ineffective external stimuli, pre-birth waiting, partition/pause/restoration consistency and lossless read-only causal/8 JSON/binary exchange.

See the [acceptance evidence](../../benchmarks/energy-lifecycle-acceptance.json) for test identities and scope. This is affected regression, not a new full-repository run or a long-duration capacity claim. The final restoration conflict is closed; unrelated theoretical questions remain open.
