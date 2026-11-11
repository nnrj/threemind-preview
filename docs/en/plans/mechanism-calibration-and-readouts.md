# Mechanism calibration, temporal activity readouts, and runtime boundaries

Status: implementation and calibration completed, 2026-09-30. Frozen baseline: `c57bb1d`, 2026-09-29. Existing studies, evidence, instances, and kernel definitions remain unchanged. Optional sandbox configuration is supplied; container execution acceptance remains unperformed.

## Agreement

Complete runtime and observation tools before calibrating strong stimulation, novelty, and long-term retention. Introduce mechanisms under separate kernel/state versions; switch the default for new instances only after acceptance. Old kernels remain explicitly selectable. Preserve timestamp delivery, sensory mapping, plasticity, inhibition, refractory responses, forgetting, and energy consumption. Unlimited external supply does not disable local depletion.

The umbrella name is **Temporal activity readout**. Name the original algorithm **Activity steady-state detection**. New analyses separately report **Response-pattern convergence**, **Amplitude change**, **Periodic activity**, and **Response end**. Avoid V1/V2 as the main UI distinction. Keep historical `residual_decay` identifiers but label them “Amplitude decay”. Stable proportions and declining amplitude may coexist. Do not normalize zero activity into a meaningful pattern. Finite observations do not prove a global attractor; response end is distinct from consciousness death. Rank primarily by activation at the end of the decision window, retaining peaks, integrals, and original composite ranks.

Observers have independent switches and termination, sharing read-only node observations. Early termination of the original observer must not stop the new observer. Preserve historical classifications; version new analysis evidence. UI, CLI, API, and exports use the same results.

## Implementation and acceptance

1. Freeze source, definitions, and reference behavior. Baseline tests: 84 passed, 1 skipped; retain the skip reason.
2. Separate independently installable Runtime from Lab dependencies. Verify snapshots, declared interventions, and an optional external deployment sandbox. Research tools must not alter Core evolution.
3. Test the observer against proportionally decaying activity, rotating membership with constant total activity, cycles, low amplitudes, zero activity, overlapping windows, restoration, and Core equivalence with observation on/off.
4. Strong stimulation: 0.4, 1, 1.5, 2, 4; single 4 versus ten 0.4 inputs, massed/spaced repetition, and no training. Independently probe at 1/30/300 simulated seconds. Measure received drive, consumption, and consolidation rather than judging only behavioral appearance.
5. Novelty: compare immediate evaluation, the frozen historical operator order, and a delayed-arrival candidate before selecting a default. Record local neighborhoods, actual reentry, and bonus timing. No semantic novelty labels. Retain current default if benefit is inconclusive.
6. Retention: branch the same trained state into ordinary forgetting, no weight forgetting, and no slow structural decay. Keep activation/inhibition decay, learning, and local resources. Use independent clones at 1/10/30/100/300 seconds with no cue, cue 0.5, and cue 1. Distinguish structural loss, pruning, thresholds, and retrieval. Separately test adaptation and saturation.
7. Publish bilingual evidence and validation. Commit locally by stage; do not push.

## Facts and open questions before implementation (original record retained)

- Extra strong-input consolidation still contains a factor `max(0, intensity - 1)`. The preceding “strong” input of 1 did not engage it. Its effectiveness remains to be calibrated.
- Both implementations retain the local novelty formula. Historical direct-input→propagation→association ordering differs from immediate association before delayed arrivals. Formula presence does not establish natural triggering.
- All four existing `autonomy-criteria/1` operational criteria passed. Preserve that result and those criteria. They are not an academically validated subjective-consciousness detector. Prior interventions comprised ablation, restoration, and birth clones, not association-region transplantation.
- Failure to retrieve a new pairing at 300 seconds alone does not distinguish forgetting from readout thresholds.

## Resources and stopping

At most 1,000 new instances; 120 cumulative simulation wall-clock minutes; 4 GiB per process; at least 2 GiB free RAM, 5 GiB free on C, and 15 GiB on E. Total new local/database/archive evidence budget: 4 GiB. Stop expansion at 3 GiB, retaining sealing margin. Record account usage at experiment start; +5 percentage points stops expansion, +8 stops new simulation. Shared-account usage is not task attribution. Scripts enforce time, RAM, and disk budgets. Never delete or overwrite old evidence; use a separate study and directory.

## First-stage acceptance (2026-09-29)

The independent Runtime package, intervention declaration, optional deployment sandbox configuration, activity readers, and API/UI integration are implemented. In a clean Python process without Lab, Web, or database packages, all four existing kernels passed save/restore/continuation equality. Related core/tool tests: 92 passed and one database test skipped; that database case passed separately in a 22-test database suite. Production UI build and browser interaction at 1440/390 pixels passed. Chat shows one primary readout while preserving the comparison record. Compose configuration validation passed; the sandbox image has not been built or executed. No kernel dynamics changed in this stage.

## Final acceptance and default selection (2026-09-30)

Completed 786 valid instances and 12 small historical-order witnesses. Full evidence, four experiment records and bilingual reports reside in separate project `d27d28d0-55f1-4783-99fd-e3a503ec1573`; the empty failed startup is preserved separately. Simulation wall time was 15.83 minutes; new local/database evidence including archive occupied approximately 1.407 GiB, without resource stops. All 786 final snapshots match local evidence; six historical parent states remain unchanged.

- Extra strong-input consolidation works. An intensity of 1 cannot engage its above-1 term; calibration and parameter guidance were completed without changing the formula.
- Arrival-window novelty increased transient target net-response integral by 40.66% at intensity 0.4 and 2.26% at 0.8 in the tested configuration, not final convergence hits or universal performance. Both modes used 1-second facilitation; extra facilitation remains disabled by default.
- New creation selects memory/2 with arrival-window settlement. Four old kernels and immediate settlement remain selectable; historical protocols, state restoration and saved project defaults retain their meaning.
- At 300 seconds, ordinary forgetting pruned the new connection. Disabling weight forgetting preserved it, but cue 0.5 could still fail while cue 1 elicited a transient response. Structural loss and cue thresholds both explain earlier zeros.
- With forgetting disabled, new responses were learned while older responses persisted more strongly. No saturation was observed in this bounded study; coexistence alone is not evidence of impaired adaptation.

Final verification groups: 153 kernel/configuration/readout/deployment integration tests; 45 interoperability/LIF/build tests; then 2 explicitly enabled standalone-constructor build tests; 27 API/ecology/report/probe tests; 5 Rust core tests; 3 study-tool tests. These group counts overlap and should not be summed as unique tests. Production frontend build and 1440/390-pixel browser interactions passed. Isolated Runtime wheel verification covered five kernels without Lab, Web or database clients; a compiled Rust constructor retained plasticity. Workstation doctor confirmed database connectivity and the installed new native backend.

See the [English report](../../../lab/explorations/2026-09-29-mechanism-calibration/report.en.md), [Chinese report](../../../lab/explorations/2026-09-29-mechanism-calibration/report.zh.md) and [delivery verification](../../../lab/explorations/2026-09-29-mechanism-calibration/delivery.en.md) for results, parameter-specific percentages and startup instructions. Platform report revision 2 appends delivery details; revision 1 and its archive remain unchanged. No simulations were rerun to change the default.

## Later work, excluded from this round

Preregister falsifiable software-applicable academic consciousness indicators, reporting them separately from project criteria. The user's priority capability checks are multiplication within ten and language-like communication; other tests follow separately. Rich environments, population evolution, region transplantation, alignment, and external-model assistance follow calibration. Snapshots and external sandboxes must preserve the plastic runtime. A single capability does not establish comprehensive child-level intelligence or subjective experience.
