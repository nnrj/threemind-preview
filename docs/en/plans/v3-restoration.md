# V3 mechanism restoration record

2026-09-10 correction: the 2026-09-08 chat acceptance below established API, media and organ operation, but did not adequately verify continuous conversation, legacy readable ordering or layout. It cannot establish faithful interaction restoration. See [temporal readout and chat restoration](temporal-chat-restoration.md) for the correction and new acceptance scope. Existing dynamics evidence is retained; the new chat work does not change Core.

[中文](../../zh/plans/v3-restoration.md)

2026-09-08. Restoration, affected regression and browser acceptance are complete. On 2026-09-09 the user approved removing independent energy death; implementation and validation are recorded in the [addendum](energy-lifecycle.md). Dynamics come from the unified V3 runtime at Git `97d8592`; chat and media behavior comes from the preserved interface at `0c5e64a`. V1/V2 presets are excluded.

## Decisions and status

Keep timestamp delivery and simulation time. Propagation has its own 100,000 μs rhythm, independent of the 10,000 μs numerical lattice and display refresh. Keep unbounded duration as the ordinary default. Restore old birth, contact consolidation, local plasticity, novelty, soft inhibition, forgetting and joint pruning. Retain the approved independent consolidation of qualified emitted signals, removing its duplicate candidate-path contribution. Sensory encoding and channel mapping do not change. Optional causal space remains disabled by default and configurable.

| Item | Status | Evidence |
| --- | --- | --- |
| Frozen source and small old-operator witnesses | Implemented; targeted checks pass | `scripts/freeze-v3-restoration.py`, `tests_v2/fixtures/v3-restoration.json` |
| Python/Rust causal/8, state/6 | Implemented; targeted checks pass | `tests_v2/test_v3_restoration.py`, local commit `c42baed`; the causal/9 activity-death follow-up is documented in the addendum |
| Graphical/JSON configuration and immutable fields | Implemented; browser checks pass | `threemind-ui/e2e/configuration.spec.ts`; prominent encoding and bidirectional synchronization pass `v3-restoration.spec.ts` |
| Organ commands and readable chat API | Implemented; API checks pass | `tests_v2/test_organ_controls.py` |
| Inline chat, media, four organ buttons | Implemented; browser acceptance passes | `threemind-ui/e2e/v3-restoration.spec.ts` |
| Full regression, affected reruns and sustained UI operation | Validated within the scope below | Initial full run: 580 pass / 18 fail; all 114 affected latest results pass after fixes; 60-second operation check passes |

## Evidence and scope

The freeze script reads the specified Git objects directly, records SHA-256 hashes, and runs tiny old local operators. It does not read `data/` or substitute later working-copy legacy files for the baseline. Re-running it must produce the same fixture. Witnesses cover birth, repeat contact, local novelty, forgetting, saturated direct contact and two-stage inhibition.

These are local-law comparisons, not claims that the obsolete frame scheduler and timestamp scheduler yield identical trajectories. Old whole-frame execution forgot newly born edges at the end of that frame. The restored kernel forgets on the next explicit propagation boundary. New edges execute only their birth branch, without an immediate second existing-edge update.

## What changes after a stimulus

| Behavior | Old implementation | Restored behavior |
| --- | --- | --- |
| Receptor formation | Anonymous channels identify receptors | Current stable encoding remains; a new admitted channel can leave a zero-support receptor, without attaching it to the main network |
| Contact and saturation | Inhibition weakens response; saturation does not erase contact or cost | Arrival, emitted amount and actual activation increment are separate; no double charge on reception |
| Edge birth | Coactivation, combined consolidation and local novelty determine birth | Old formula restored; no second existing-edge update at birth |
| Repeated learning | Local plasticity, history and remaining weight capacity matter | Event learning rate `.055`, old plasticity and weight-headroom factor restored |
| Novelty | Weak, nonzero associative re-entry in an existing neighborhood | Gain `.018`, without semantic priority or importance scoring |
| Propagation | Each edge passes its own cutoff before fan-in | Cutoff `.004`; rejected weak paths cannot rescue each other after summation; receiver state is handled only at arrival |
| Associative consolidation | Old candidate-path coupling missed some traversals | Approved independent emission-based consolidation retained, without a duplicate associative term |
| Inhibition | Soft saturation, reduced response and finite-potential redistribution | Old nonlinear stages run at model rhythm, rather than every solver substep |
| Activity decay | Natural decay exists independently of energy | Elapsed-time decay retained, zero cutoff restored to `.004`, independent of display thresholds |
| Forgetting and pruning | Stability, eligibility, traversal history, support and untouched time matter | Old local laws restored; zero activation alone never deletes a node |
| Death | Historical input/energy rules were mixed | Ordinary death follows continuous zero activation after birth, default grace 1 second; structure is retained |

Local formulas live in Python `src/threemind_core/restoration.py` and Rust `crates/threemind-core/src/restoration.rs`. Their corresponding `engine.py` and `lib.rs` own scheduling and state. Labels, chat, databases and AI do not enter these formulas.

## Formulas and phases

Let activation be $a$, inhibition $q$, node stability $s_n$, support $u$, local plasticity $p$, edge weight $w$, edge stability $s_e$, and eligibility $e$. Defaults below recover the old V3 reference period of 0.1 seconds.

1. **Contact.** Soft saturation is $S(q)=c\tanh(q/c)$; response is $R(q)=1/(1+g_rS(q))$. Affordable direct arrivals are charged before receiver inhibition/saturation. Contact is $d=arrival\,R(q)$, while actual increment is $\Delta a=\min(1-a,d)$. Counters `received`, `activated` and `sent` distinguish pre-inhibition arrivals, actual increments and emitted excitatory amount. Reception does not charge transmission again. Energy-scaled emissions falling below the gate remain charged and enter `discarded`.
2. **Direct consolidation.** $I=\min(I_{max},drive\cdot affordable\_fraction\cdot p\cdot(g_{first}\mathbf1_{first}+g_{repeat}+g_{intensity}\max(0,intensity-1)))$. After contact, $s_n\leftarrow\min(1,s_n+0.5g_sa)$, $u\leftarrow\min(1,u+g_ud)$ and $p\leftarrow\max(0.12,1-0.72s_n)$. Saturation does not cancel nonzero contact.
3. **Birth.** $C=a_i a_j$ and $I_{ij}=\min(I_{max},I_i+I_j)$. Initial values are $w=\min(1,b(0.5+C)+0.18I_{ij}+N)$, $s_e=\min(1,I_{ij}+N)$, $e=I_{ij}$ and zero edge touches. Novelty is present only for a pre-existing neighborhood with $A=\max(assoc_i,assoc_j)>0$: $N=g_N\max(0,1-\min(1,A/A_{ref}))$, default $g_N=.018$.
4. **Existing-edge co-contact.** $w\leftarrow\min(1,w+\eta Ch(1-w)+.08I_{ij})$, $e\leftarrow\min(1,e+.3C+.25I_{ij})$, and $s_e\leftarrow\min(1,s_e+g_sC(1+\log(1+touches))+I_{ij})$. Here $h=1$ with traversal history, otherwise $.45$, and $\eta=.055$. Increment history afterward. The independent traversal path is not charged again as an old associative stability term.
5. **Emission.** $x_{ij}=a_iR(q_i)w_{ij}g_{prop}\Delta t_{prop}$, multiplied by spatial attenuation only when explicitly enabled. Defaults $g_{prop}=4.2s^{-1}$ and $\Delta t_{prop}=.1s$ recover old per-emission `.42`. Each edge must meet `.004`; target activation/inhibition does not enter the sender calculation. Qualified signals arrive after `delay_us`, default 10,000 μs.
6. **Independent traversal consolidation.** A qualified actual emission $x$ updates $w\leftarrow\min(1,w+g_{assoc}x)$, $s_e\leftarrow\min(1,s_e+g_sx)$, $e\leftarrow\min(1,.7e+x)$ and traversal history. Explicit research budgets or the plasticity switch can constrain this path; defaults do not.
7. **Inhibitory phase.** First apply $S(q+q_{pending})$ to time-decayed old potential and arrived pending potential. Excitatory sending uses this source response. Then apply $S(q+q_{generated})$ for accumulated actual activation rises. Transfer a finite pool, default `.35` per reference cycle, using maximum directed weights across existing incident connections; subtract actual transfer from the source. Aggregate inhibitory packets receive soft saturation before delayed delivery. Default transfer gate is `.002`. Pending and locally generated potential are serialized; elapsed-time decay between arrivals remains explicit.
8. **Time-dependent losses.** Activation follows $a\leftarrow a\exp(-\Delta t/\tau_a)$, likewise node trace and inhibition. Defaults retain `.72/.82/.65` per `.1s`. Edge eligibility retains $\exp(-\Delta t_{prop}/\tau_e)$, default `.78`. Then $s_e\leftarrow\max(0,s_e-\Delta t_{prop}(1-e)/\tau_s)$ and $u\leftarrow\max(0,u-\Delta t(1-s_n)/\tau_u)$, with $\tau_s=\tau_u=.1/.00015$. These are linear loss scales; node stability no longer receives the substituted independent exponential loss.
9. **Weight forgetting.** Without traversal this cycle, $w\leftarrow w[\max(0,1-.1f(1-(.08+.92s_e)))]^{\Delta t_{prop}/.1}$, default $f=.025s^{-1}$, restoring the old `.0025` reference-period coefficient. Eligibility changes before stability, which changes before weight. Traversal exemption is restored as an old rule; simplifying it remains a separate research question.
10. **Pruning.** Edges below `prune_weight` may disappear. Nodes require simultaneous isolation, zero activation, support below `.006` and `time-last_touch > 80,000,000 μs`. Disabling plasticity stops learning, forgetting and this natural pruning.

The numerical lattice remains `step_us=10000`; it controls numerical boundaries such as flooring, not propagation amplitude or per-contact learning. Observation batches do not create new lattice points. Explicit propagation-interval changes start a new phase at the effective time. Empty-system skips and export/restore preserve that phase. Explicit resource budgets use fixed windows of the propagation interval's length; changing the interval resets that window's usage, as stated in the parameter UI.

Existing optional spatial comparison competition retains its `step_us` numerical boundary and prior semantics. It is not replaced by topological inhibition or enabled by default. Regression checks also verify independence from edge traversal order.

## Life, damage and serialized models

Before first nonzero activation, the consciousness is waiting. After birth, continuous quiescence starts the grace period. All same-time arrivals are processed before the death decision. Pending signals, arriving external carriers, enabled interfaces, residual inhibition and edges cannot stand in for actual activation. Pausing consumes no simulation time. Death preserves structure and refuses automatic resurrection of the same consciousness.

Damage operations are `silence`, `unsilence`, `disconnect_edges` and `delete_nodes`. Disconnecting removes edges while retaining emitted packets. Deleting removes the receptor index and incident edges; a later receptor on the same channel receives a fresh ID and blank history, so old in-flight packets cannot target it. Unsilencing does not manufacture activity. The old explicit `lesion` argument remains an API alias; new graphical controls expose the four named operations.

Dynamics are `threemind.causal/8`, state is `threemind.state/6`. New state includes node birth time, local plasticity, pending/generated inhibition, propagation phase, traversal history, transport counters and quiescence timing. Python, Rust, JSON and `.tmind` Arrow binary use the same fields. Equivalent format conversion preserves the state digest. Inheritance clears activity and runtime phases for a new birth.

Older causal/1–7 artifacts remain readable/exportable with their original digest. They cannot be relabeled, resumed or inherited under new laws. Database additions use nullable columns for historical projections; no `data/` scan or mass conversion occurs. Stop services, migrate the schema and rebuild native/UI artifacts before restarting an upgraded application.

## Configuration and chat

The first-level node-labeling selector, advanced text encoding field and JSON share `text_sensor.encoding`. Both validation and save enforce immutability after creation. Zero disables strength/rate effects; six time-loss switches disable corresponding losses while retaining positive time constants. `quiescence_death_us=0` means immediate evaluation after same-time events, not disabled death.

Inline chat presents actual nonzero activity and external labels in recorded node order. Anonymous activity displays IDs and amplitudes. Candidate classification or human judgments of meaningful associations do not crop the raw evidence. Display is bounded to 128 active nodes per record with an overflow notice, and 20 messages per page. Scrolling into history freezes the range, preserves the list and reading position, and stops follow mode. Tall latest messages follow to their beginning instead of an evidence footer.

Input, passive readout, temporal readout and explicitly enabled external AI interpretation retain separate identities. Envelope references are audit links only. Successful sends clear the composer; failures retain drafts. Enter, Shift+Enter and IME composition are handled separately. Existing media decoding/storage, capture and output services back the three media entries and four organ buttons. Runtime commits acknowledge switch time. Stopping capture prevents new input without retracting accepted frames. Browser/device failures are shown explicitly.

## Validation and remaining exception

The initial full suite produced **580 passes and 18 failures**. Each failure was addressed; the latest outcomes for all **114 affected cases pass**, merging a 114-case run with a five-case API rerun by test identity. This is not presented as one all-green full-suite run. Fixes preserve spatial competition's original phase and birth-only gating; lifecycle fixtures explicitly reflect quiescence grace. Migration rollback fixtures reconstruct the actual old schema rather than weakening production migration checks.

Two Rust workspace tests pass. Native extension, independent CLI and UI builds pass, as do Ruff, translation-catalogue and document-resource checks. Re-running the frozen Git oracle preserves its behavioral samples. Browser acceptance covers configuration modes, immutable saves, IME, successful/failed drafts, paging, evidence navigation, media entries, four organ switches, upload/original download, historical audition, WAV/PNG export, mobile layout and bilingual math/diagram pages.

The 60-second operation check kept 20 messages per page. From the 10-second warmup sample to 60 seconds, main-thread heap changed from 16,445,376 to 16,978,912 bytes, approximately **0.51 MiB**, and DOM count from 12,825 to 12,835. [Machine-readable evidence](../../benchmarks/v3-restoration-acceptance.json) includes samples and test identities. This fixed small-model workload and fake browser capture do not establish hours-long capacity or physical-device performance.

The local ThreeMind database on port 5433 is upgraded to schema 48 after confirming stopped services and no pending jobs. Health checks pass. Only schema fields/message types are added; no legacy consciousnesses are converted or automatically resumed.

On 2026-09-09 the user approved and implementation removed the independent starvation countdown and forced-death branch while retaining shortage damage. This uses causal/9 with state/6 and Lab schema 48 unchanged; see the [activity-death addendum](energy-lifecycle.md). The other test counts on this page belong to the 2026-09-08 restoration and are not presented as new incremental results. See [open mechanism questions](mechanism-questions.md).

## Why the old associative path was incomplete

The old propagation operator records traversals, but associative stability updates sit inside the edge-adaptation candidate branch. Default candidates come from direct co-stimulation, so a purely traversed edge may never reach that branch, despite documentation allowing associative consolidation. Git only contains the initial import at `97d8592`; earlier author motivation cannot be established. Reusing candidate handling may have created the coupling, but that is an inference. The retained independent consolidation is an approved change, not a claim of numerical equivalence to the old formula.

## Local commits and UI evidence

Kernel restoration `c42baed`, boundary fixes `5ef9a46`, configuration/API `a741a3b`, chat UI `53342ac`. These are local commits; nothing was pushed.

[Desktop acceptance screenshot](../../images/v3-restoration-desktop.png) · [Mobile acceptance screenshot](../../images/v3-restoration-mobile.png)
