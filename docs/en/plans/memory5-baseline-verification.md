# /2 baseline and tool-time verification before /5

> Public edition, 2026-11-11: private conversation locators and manuscript/submission discussions are omitted where present. Scientific records retain their original dates; the complete source remains unchanged.


Date: 2026-10-13. Classification: historical provenance and isolated engineering verification, not a new formal consciousness experiment.

## Conclusion and scope

**Across 24 conditions and 66 complete snapshots per implementation, current Python `/2` exactly matches three historical Python versions. Current Rust makes identical discrete decisions, with floats inside the existing tolerance.** No `/2` change caused by shared `/3` or `/4` implementation work was found in these paths. This bounded check does not prove all configurations or equivalence of `/4` and `/2`.

Only small new anonymous engineering cores were used. No formal individual, database, service, or E67/E68 original was loaded or restored. This work adds an audit script, hash fixture, regression tests and documentation; it changes no Core, Runtime or historical definition. See the [/5 plan](local-events-v5.md) and [kernel change governance](../kernel-change-governance.md) for implementation authority.

## 1. Original user decisions


> **Public-edition edit (2026-11-11; source lines 13-13):** Private conversation IDs and locators are omitted; scientific quotations and records are retained. The complete source remains unchanged.



The original **ThreeMind二期** conversation, ID `[private locator omitted]`, was read. These are original user messages, not retrospective authorization inferred from implementation:

| Original message UTC / local session line | Relevant decision |
|---|---|
| 2026-09-08 07:59:57, 33026 | Transmission must not inspect recipient state; saturation does not undo sending, contact or consolidation; restore ordinary learning, local novelty and long-term forgetting protection |
| 2026-09-08 10:01:38, 33194 | Approved restoration: 100 ms propagation rhythm, per-edge weak threshold, ordinary learning rate 0.055 and local novelty 0.018; preserve consolidation from actual nonzero emission separately, without double charging |
| 2026-09-30 09:07:08, 53045 | Approved `/2`, arrival-window novelty, ordinary input intensity 1 and strong preset 4; preserve propagation threshold, timing architecture, forgetting/inhibition/resource recovery; independent simultaneous sources are not automatically one co-observation |
| 2026-09-30 20:52:19, 58592 | Additional strong-stimulus mechanism configurable, enabled by default |
| 2026-10-01 01:38:05, 60426 | Keep the current strong-stimulus mechanism; defer replacement exploration |


> **Public-edition edit (2026-11-11; source lines 23-23):** Private conversation IDs and locators are omitted; scientific quotations and records are retained. The complete source remains unchanged.



Local original: `private conversation record (locator omitted)`. This document indexes relevant decisions without copying the full conversation or tool logs.

These decisions support preserving `/2` learning and strong-stimulus rules. “Use local events” does not authorize arbitrary additional learning opportunities. See the [delta/decay audit](kernel-delta-decay-audit-20261013.md) for `/4` recipient pairing and other differences. H was historically authorized; the user now questions its cost and necessity. Both facts must remain distinct.

## 2. Historical baselines and results

| Source | Current Git identity | Comparison with current Python |
|---|---|---|
| Earliest `/2` identity | `52e18c3e3d9be89aa2569861e612b977c6911f4b` | Complete state equal in 24/24 conditions when the novelty mode is explicitly matched |
| Before `/3` | `6a9e68a2b261beb6c2d3424662d3e0c6baad102c` | Complete state equal in 24/24; defaults also equal |
| Before `/4` | `f4e7568f29c0f81c9ed2bce022f805279aff4fe7` | Complete state equal in 24/24; defaults also equal |

The only earliest-to-current default change is `novelty_mode: immediate → arrival-window`, the explicitly authorized `/2` calibration in commit `3a4b35547c7281e3fdfd6d55e81e21a4e12f3836`. This audit did not silently revert it.

Each novelty mode covers 12 scenarios: birth/repeated propagation, energy consumption at saturation, weak signals/inhibition/forgetting, waiting/death, identity after disconnect/delete, isolated pruning, nonaligned strong stimuli, temporal links, starvation, spatial neighborhood, the base path with STP/fast/context disabled, and learning disabled. This is not every parameter combination.

Current Rust independently received identical inputs. Identity, topology, time, queues and other discrete values match exactly; floats use `abs(error) ≤ max(1e-14, abs(reference) × 1e-12)`. All 24 conditions and 66 snapshots pass; tolerant numeric agreement is not byte identity.

The new regression has **49 passing checks** (24 historical state hashes, 24 cross-backend comparisons and one default hash). The existing novelty and pre-upgrade native witness suite separately has **21 passes**. The initial new-test invocation failed during setup because of Windows temporary-directory permissions, before assertions; all passed using a new isolated `.work` temporary directory. Hashes freeze sorted JSON of unrounded historical Python states. A cross-platform math-library last-bit difference requires historical comparison and tolerance review, never automatic fixture replacement.

## 3. Tool overhead and simulated time

| Inspected path | Evidence and boundary |
|---|---|
| `Runtime.pace`, CLI and Lab advance loops | Physical time decides waiting. Targets come from current simulated time and declared deadlines. Query duration is not added to simulated time; falling behind removes waiting, not internal events |
| Lab event observers, `ReadoutHost`, output organs | Inspected callbacks record provenance or read state, without injecting, reconfiguring, intervening or extra advancement. Checkpoint copying/waiting does not advance either |
| Observation frequency | Lab `next_observation`, readout/output deadlines and CLI `ReadoutSession` subdivide `advance_to`. Batch invariance must therefore be checked; read-only callback source alone is insufficient proof |
| Fixed-input `/2` witness | Python and Rust each compare direct advancement with 11,357/17,311/19,877 µs nonaligned observation intervals. At 1,001,337 µs complete states match exactly within each backend, with 90 readout events each. Repeated metrics, graph, node/edge reads, spatial projection, forced readout and capture leave state bytes unchanged |
| Mock physical delay | Advancing the mocked host monotonic clock by 100 seconds then invoking pacing changes neither simulated time nor complete state in either backend. This controlled test did not actually wait 100 seconds |

**Live telemetry introduces a separate feedback path.** `src/threemind_lab/telemetry.py` samples by physical time. Enabled host/process/runtime sensors encode actual measurements as inputs delivered at the then-current simulated time plus the declared feedback interval. Observation, saving and other tools may change CPU/memory measurements, scheduling latency, sample count or the simulated position at physical sampling. Runtime measurement in `run_cycle.py` also includes Python observer cost inside `advance_observed`.

The located risk is therefore **explicit external telemetry input affected by tool load**, not evidence that a tool secretly consumes simulated seconds. Authorized live telemetry must not be silently disabled or replaced to demonstrate independence. Fixed prerecorded input can control this factor in an engineering comparison; live-environment experiments must report tool load and obtain the user's decision on separating organism costs from tool costs. These findings do not themselves modify input protocols, sampling rules or old kernels.

## 4. Reproduction

- [Audit script](../../../tools/audit_memory2_preservation.py): reads Git history and writes extracted source/full engineering outputs to a new `.work` child only; refuses existing output directories.
- [Regression tests](../../../tests_v2/test_memory2_preservation.py) and [compact frozen hashes](../../../tests_v2/fixtures/memory2-preservation-hashes.json): configurations, scenario/state hashes only; no formal experiment trajectory.
- Local full results: `.work/memory2-preservation-final-20261013/summary.json` (including tool-time checks); first provenance outputs remain in `.work/memory2-baseline-20261013`. These are reproducible engineering materials, not formal research originals.

```powershell
$env:PYTHONPATH = 'src'
.\.work\kernel-venv\Scripts\python.exe -X utf8 tools/audit_memory2_preservation.py --output .work/memory2-audit-new --native --tool-time
.\.work\kernel-venv\Scripts\python.exe -X utf8 -m pytest tests_v2/test_memory2_preservation.py -q --basetemp=.work/pytest-memory2-new
```

The output directory must not exist. Passing these checks authorizes no change to `/2` and does not replace `/5` acceptance of local semantics, observation frequency, same-time order or complete-state recovery.

## 5. Independent review during /5 development

Separate from implementation self-tests, source review and new anonymous engineering witnesses found the following development defects. Implementers corrected them and added regressions; these are not new conclusions from formal experiments.

| Finding | Original reproduction and post-fix check |
|---|---|
| Zero novelty gain differed between backends | Python created a window while Rust did not, diverging in deadlines after 70ms. Both now omit the inactive window and complete states match within tolerance |
| External input counted as reentry under the unified research option | Rust counted an external accepted amount of0.09 at80ms toward novelty while Python did not. Both now count internal association for this reward |
| Mixed legacy-source + coincident arrivals lost an external impulse | At110ms Rust treated the whole mixed group as nondirect and dropped its external impulse; Python retained it, producing edge weights0.08324401549754097 versus0.081388. They now agree; this combination remains a labeled research option |
| Later same-time input forgot a completed emission phase | Advance to100ms, then inject a valid input at100ms: /2 changes weight0.1085287384 to0.13551908159515785, while the initial /5 produced0.12083166376262104. A new edge incorrectly used a110ms novelty deadline instead of210ms. A recoverable completed-emission-phase marker restores the former tolerance and210ms deadline; both backends agree through continuation. The marker records execution order, not a graph-wide refresh or learning quota |
| Completed novelty windows retained empty Python index keys | Deleting all nodes still left historical IDs mapped to empty sets. Cleanup now removes them. This is derived-memory management, not a reward or simulated-time change |

The latest isolated native extension is in `.work/memory5-validation/native`. Independent reruns of the three option witnesses and the same-time phase check pass; /2 frozen regression against this rebuilt extension again passes49 checks. Scripts/results: `.work/memory5-validation/provenance_review_parity.py`, `provenance_same_boundary.py`, and `provenance-review-parity.json`.

A further /4 comparison uses source commit `db5e3d3113c613fa7799b12db5c46292655f5c75` before shared-branch changes. Two retention modes × two arrival modes × two reception modes × two propagation phases yield16 conditions/80 snapshots, all exactly equal to current Python /4 (`.work/memory5-review-old4/summary.json`). The same16 /5 combinations also match exactly between direct advance and nonaligned readout batching with fixed prequeued inputs (`provenance-review-observation.json`). Later same-time input is a separate ordering case; prequeued-only tests cannot replace it. These finite witnesses do not replace overall performance, installation or formal research acceptance.
