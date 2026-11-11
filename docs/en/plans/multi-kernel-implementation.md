# Multi-kernel implementation record

[中文](../../zh/plans/multi-kernel-implementation.md) · [Principles and original statements](../kernel-evolution-principles.md)

Status date: 2026-09-28. Implementation is authorized; status follows validation, not the plan alone.

| Stage | Scope | Status |
| --- | --- | --- |
| 0 | Freeze causal/9 source, behavior and hypotheses | Implemented: fixed source, dual-backend witnesses, original hypothesis hashes |
| 1 | Registry, declarative definitions, state identity, configuration and CLI | All three kernels integrated; artifacts and device recovery verified |
| 2 | Continuous candidate: short-term synapses, fast/slow weights, receiver-local context addressing; Python/Rust | Engineering acceptance complete; research benefit unmeasured |
| 3 | Separate membrane/spiking candidate and standalone packaging | Implemented: analytic RC, firing, refractory period, STDP and tested compiled artifacts |
| 4 | Small local Transformer comparator and optional model adapter | Implemented: local training/probabilities, numeric models, optional HTTP and explicit audited input |
| 5 | Configuration/research UI, wide/narrow-screen acceptance, small comparisons | Implemented: six browser cases and nine bounded anonymous controls; not cognitive validation |

## Preservation boundaries

Initial verification: 55 baseline/related tests passed, 12 database tests skipped because the isolated service was unavailable; 2 Rust Core tests passed. Witnesses check both Python and Rust. Skips are not passes. New functionality is validated separately.

- Preserve Git `b53fba1`, `threemind.causal/9` / `threemind.state/6`. The freeze script executes fixed trusted history, never `data/`. Witnesses cover birth, repeated touch, propagation, inhibition, saturated energy costs, forgetting, death and damage.
- `kernel_id` identifies science; `reference/native` identifies implementation. Missing backends never silently change models. Ablations differ from changes to fundamental dynamics.
- New states bind definitions, mechanism versions and hashes. No automatic cross-kernel conversion. Preserve sensory mapping, unlimited duration and activity-based death.
- Core has no database/UI/network dependency. Retain Lab PostgreSQL and optional standalone SQLite; no MQ or distributed shared-brain solver.
- JSON selects trusted operators. Standalone building leaves networks plastic. Optional remote models must record external contribution.

## Mechanisms and validation

Registry/configuration/CLI foundation: 28 tests passed, 3 database tests were initially skipped. Use `python -m threemind_kernels.cli list`, `inspect threemind.continuous/1`, or `validate definition.json`. Both Python and standalone Rust creation accept `--kernel threemind.continuous/1 --config config.json` or `--definition definition.json`. Restoration dispatches by saved identity and rejects creation-parameter overrides. RunSpec, configuration metadata and worker provenance carry identity. Causal/9 remains default; existing consciousnesses are never automatically upgraded.

Early continuous-candidate acceptance: 159 baseline/configuration/development/probe tests passed, plus 13 independent Rust artifact/SQLite and invalid-model cases. That stage used only the isolated service at `127.0.0.1:55439`. Artifacts retain every operator state. Structural birth preserves slow connections but clears short-term/fast histories, activity and in-flight messages; exact recovery clears none of them. See the [candidate specification](candidate-mechanisms.md). Final acceptance and business deployment follow below.

## Final acceptance and deployment

- **259 affected tests passed**, including Python/Rust, PostgreSQL and a real compiled standalone constructor; a separate three adapter-registry tests passed. Coverage includes preserved V3, complete cross-backend state, spike observation without state changes, inheritance/import/export, project isolation, stable request IDs, explicit probability input, population recovery and documents. Skips are not counted as passes.
- TypeScript/Vite builds and six Edge browser cases passed. Coverage includes basic/advanced/JSON consistency and immutable parameters, kernel switching, unlimited defaults, mixed chat and temporal readouts, cleared input, stable scrolling and bounded visible history, 390/320-pixel layouts, text navigation, Transformer training/query/explicit input and physical state pagination. Desktop 1440-pixel and mobile 390-pixel captures were visually inspected; screenshots remain in ignored `.work/kernel-browser-acceptance`.
- [Nine bounded comparisons](../../../lab/validations/2026-09-28-kernel-candidates/README.md) matched across backends and restored exactly. Raw evidence is about 1.02 MiB. No new long language training or GPU experiments were launched.
- Business database `127.0.0.1:5433/threemind` was upgraded from schema 50 to **51**, after verifying no active workstation/workers or task leases. Migration changes dispatch capability matching only. Existing models, experiments and `data/` were not converted, scanned or cleaned. The subsequent doctor check confirmed database access and the native baseline without starting old consciousnesses.
- System Python 3.13 with `.work/kernel-venv` now provides development/media dependencies and rebuilt native bindings. Optional CPU PyTorch is installed; no pretrained model was downloaded. Anaconda is unnecessary. E-drive free space was about 51.9 GiB after acceptance. Business services remain stopped; use the [guide](../v2-kernels.md) to start them.
- Existing build notices include some chart/editor chunks exceeding 500 kB, still loaded on demand. Tests also emit a Starlette TestClient deprecation warning. Neither failed acceptance, and large-scale runtime performance is not claimed as validated.

This implementation scope is complete. Retention, interference, reversal, ordering, environmental adaptation and relational composition remain future scientific experiments requiring sensory/readout calibration. Engineering tests and external Transformer success cannot substitute for them. The optional remote protocol exists; no public service or distributed shared-brain solver was deployed. Continuous fast traces are local scalars, not full Transformer matrices.

Local stages: `4f39b9a` baseline freeze; `f306d04` registry/identity; `b422040` continuous candidate; `691a499` spiking kernel, standalone build and Transformer backend. UI and final records are committed separately, with no push.

Development uses isolated `.work/kernel-venv` after the previous Anaconda installation was removed. `scripts/start-lab.ps1 -Python .work/kernel-venv/Scripts/python.exe` selects it explicitly; the default remains `.venv`. Dependencies and native bindings were rebuilt, without touching experiments. The new NumPy version exposed removal of `trapz`; statistics now use the already-required SciPy implementation of the same trapezoidal formula, with existing tests passing.

Specify states, units, equations, phases, justified defaults and ablations first. Short-term synapses differ from long-term weights; continuous emissions are not biological spikes. Receiver competition cannot let senders read destination state, erase arrivals or undo transmission costs. Voltage, spikes and growth traces have distinct meanings.

Validate frozen and existing V3 behavior, Python/Rust parity, partition/pause/resume, deadline arrivals/death, independent ablations and rejection of invalid definitions/states. Model bundles retain in-flight messages and histories. No hidden default prediction feedback to improve answers.

Sources: [Tsodyks–Markram 1997 (check erratum)](https://pmc.ncbi.nlm.nih.gov/articles/PMC19580/), [Markram et al. 1998](https://pubmed.ncbi.nlm.nih.gov/9560274/), [Brian2 short-term synapses](https://brian2.readthedocs.io/en/stable/examples/frompapers.Tsodyks_Uziel_Markram_2000.html), [LIF](https://neuronaldynamics.epfl.ch/online/Ch1.S3.html), [Bi–Poo 1998](https://pubmed.ncbi.nlm.nih.gov/9852584/), [linear Transformers and fast weights](https://proceedings.mlr.press/v139/schlag21a.html). Demonstration random wiring and increased background current for visible bursts are not inherited assumptions.

## Resources and UI

Start with primitives/nonsemantic controls, then retention, interference, reversal, order and simple adaptation. Evidence determines relation tests and scaling. Primary continuous readout remains end-of-convergence activation ranking with raw evidence retained. Membrane kernels explicitly name their ranking quantities.

Default one CPU job, target RAM ≤4 GiB, optional GPU VRAM ≤2 GiB, new research evidence ≤4 GiB; monitor E-drive build caches separately. Honor the account-usage budget, without automatic expansion. Resource termination is not death. Existing data is neither cleaned, scanned nor automatically upgraded.

Creation exposes kernel and marking mode. Basic/advanced/JSON share state. Preserve graph/chat/media/organ behavior; narrow screens reduce simultaneous display, not functionality. Test navigation, feedback and saving; a build is not interaction acceptance.
