# October 13, 2026: why local computation became slower

> Public edition, 2026-11-11: private conversation locators and manuscript/submission discussions are omitted where present. Scientific records retain their original dates; the complete source remains unchanged.


Sources: the current project conversation, existing E67/E68 originals and implementation code. This entry separates the user's question, source facts and existing timings. Engineering profiling is ongoing; no optimization is claimed as implemented. No formal subject was rerun, restored or altered, and no original experiment report was rewritten.

The opening describes the initial inspection. The dated completion addendum below records the subsequent isolated engineering measurements; production kernels remain unchanged.

## User question and audit scope

The following is an editorial translation of the excerpt preserved verbatim in the [Chinese source](../../../zh/history/sources/2026-10-13-kernel-performance-audit.md), not an original English quotation: Liu suspected that global versus local processing might explain the slowdown. If earlier whole-graph work had become naturally interacting local operations, why were /3.1 and /4 slower, and did the actual local operations differ from his intent? He explicitly did not restrict the investigation to that hypothesis.

The request is a multi-cause analysis and actionable remedy. Criticism of the assistant's recent quality is contemporary feedback; suspicion of malicious third-party involvement is not an investigative finding. The audit relies on reproducible code, execution records and cost separation. Existing evidence does not establish intentional external interference.

## Existing measurements: a matched teaching phase remains much slower

All four E67 `arms/<arm>/correction-1/result.json` receipts record 165 lessons, 292.5 simulated seconds and 23,400 native advancement calls. Originals remain under `E:\ThreeMindData\experiments\2026-10-11-shape-color-kernels`, without another large-file copy.

| Kernel and retention mode | Summed native advancement call time, seconds | End-stage nodes | End-stage edges |
| --- | ---: | ---: | ---: |
| `/2` | 649.719 | 400 | 144774 |
| `/3.1` | 1190.025 | 398 | 143996 |
| `/4 adaptive-half-life` | 6171.915 | 398 | 140062 |
| `/4 legacy-stability` | 7405.446 | 398 | 141978 |

These are historical timings of the same corrective teaching phase, not continuous final-examination scores or a new dedicated-hardware benchmark. Native advancement is measured separately from saving, observation and media encoding. Similar end-stage edge counts do not simply explain the approximately 1.83, 9.50 and 11.40 times longer timings. End-stage scale does not establish identical structural trajectories, and call wall time does not remove host scheduling effects. [E67 handoff and evidence entry](../../../../lab/explorations/2026-10-11-shape-color-kernels/HANDOFF.md)

E68's fully continuous final scores remain 66/72 for /2 and 71/72 for /3.1, with a 1.896 native-time ratio. This audit neither retracts nor rewrites that single-individual/single-seed result. [E68 report](../../../../lab/explorations/2026-10-13-continuous-shape-color/report.en.md)

## Confirmed source facts and saved counters

/3.1 retains the whole-graph execution framework. Local retention and expiry replace their earlier counterparts, but advancement still performs whole-node relaxation, baseline construction and inhibition calculations. Periodic propagation still traverses nodes/adjacency, followed by whole-edge eligibility/stability updates. It is incorrect to say that all whole-graph work has disappeared. [Executor](../../../../crates/threemind-core/src/lib.rs) · [Propagation](../../../../crates/threemind-core/src/continuous.rs) · [Retention](../../../../crates/threemind-core/src/retention.rs)

The saved E68 /3.1 counters contain 3,357,181,044 edge settlements, 13,586,125 node settlements and 564,604 expiry checks. Surviving edges carry 2,445,808,123 total touches. Their ordinary-strengthening paths reschedule expiry each time; actual emissions also schedule after H growth and again after ordinary strengthening. The timer removes and reinserts two tree entries even if the deadline is unchanged. The default adaptive mode's legacy-forgetting guard first queries each edge's traversed membership and only then excludes that mode, making that query irrelevant to the result. These counters are existing execution evidence, not a measured attribution of runtime percentages.

/4 emits per node, but its receiver groups contacts by the originating packet serial and associates pairs within each packet's reached-target cohort. Under unified reception, internal propagation creates these learning opportunities as well. `receive` and `associate` in `local.rs` imply work proportional to the sum of squared cohort sizes, `sum(k²)`. If N emitting nodes each reach O(N) targets in a dense graph, candidate pairing can reach O(N³). This is a conditional worst-case derivation, not a claim that every experiment precisely attains cubic work, and it does not relabel internal propagation as fresh external stimulation. [Local reception and association](../../../../crates/threemind-core/src/local.rs)

The packet-based common-target association changes learning opportunities. It is not merely an equivalent decomposition of /2. Treating external and internal signals consistently does not by itself require repeated pairwise association across every packet's targets. Node-local rules, scheduling implementation and task sparsity must be audited separately.

## Recommendations, open evidence and authorization

Proposed equivalent optimizations include avoiding unchanged-deadline rewrites, coalescing a same-edge reservation immediately overwritten within the same operation, rejecting inapplicable branches first, caching constants and reducing repeated lookup/allocation. Preserve event ordering, thresholds, floating-point operations and restoration semantics. Counts/profiles and state-by-state comparisons must establish their benefit; these fixes are not yet implemented.

The learning meaning of /4 internal cohorts, whether pairwise common-target association is needed, and how each object should use its own actual received experience require a separate mechanism decision. Speed is not permission to silently remove learning, change time or allow rollback. Any dynamics change must preserve existing identities and follow the agreed versioning rules. Remedies await user confirmation; no new scientific experiment is launched, and E67, /4 and their automation remain stopped.

See the [performance audit](../../plans/kernel-performance-audit-20261013.md) for the current investigation and subsequent engineering evidence. Existing reports, raw timings, the E67 continuity correction and E68 outcomes remain intact; future profiling and proposed optimizations are not recorded as completed measurements here.

## Same-day engineering completion addendum

Fresh synthetic Core fixtures with 16/32/64 channels were measured in an ignored source-copy workspace, without restoring any formal individual. Doubling channels from 32 to 64 roughly quadrupled edges; /4 H pair-loop iterations grew from 307291 to 2390245 and advancement time roughly eightfold, versus roughly fourfold for the older kernels. Instrumented and uninstrumented final complete-state hashes matched for all four conditions at all three sizes. A separate copy tested unchanged-deadline early returns and an earlier applicability check: all three paired 64-channel runs retained identical final hashes; /4 stability improved by 11.9%–18.2%, /4 H had no consistent gain, and /3.1 improved with substantial short-run variability. This supports concrete engineering improvements while refuting the claim that two indexing changes solve the whole slowdown. Production Core remains unmodified; mechanism changes await a decision. See the linked full report for measurements and limits.

## Same-day addendum: authorization of pairing and the cost of decay

The [Chinese source](../../../zh/history/sources/2026-10-13-kernel-performance-audit.md) preserves Liu's exact statement that he had never requested the internal packet's receivers to associate with one another, that this changed dynamics, and that the assistant should trace its basis, find similar changes and enumerate /4's differences from /2. He also questioned adaptive half-life complexity and proposed that retention should require energy while decay should occur naturally. These are attributed questions and design ideas, not an established biological finding or permission to remove decay.


> **Public-edition edit (2026-11-11; source lines 54-54):** Private conversation IDs and locators are omitted; scientific quotations and records are retained. The complete source remains unchanged.



The original conversation file `private conversation record (locator omitted)` was reread. Line6243 contains the assistant's October8 15:05:01.719 UTC recommendation to first preserve reception semantics and separately unify source-dependent rules. Line6253 records the user's approval of /4 the next day; line6306 repeats the promise of preserving established reception semantics. No separate explanation or confirmation of common-sender downstream pairing was found in user-facing messages through delivery at line7440. Current Git commit `728cde9` introduced implementation, plan, contract and tests together. An assistant-authored contract is not independent evidence that the user specified its detailed rule.

The resulting correction distinguishes approved direction from implementation interpretation: unified reception was authorized, but inferring B/C/D mutual contacts because A reached all three was an assistant-selected semantic expansion. Old default co-stimulus already pairs only the current external touched set; searching recent activity across the graph belongs to a separate optional policy. Removing that search did not require adding internal pairing. `legacy-source` does prevent internal packets entering this pairing; it is incorrect to claim otherwise. It still retains /4 scoring, window and timing differences, so it does not restore the complete /2 model.

The follow-up also identifies changes in pair scores, recent-traversal criteria, novelty initialization/deadlines/eligibility order, inhibition saturation placement and some nondefault gates. See the [mechanism, provenance and decay audit](../../plans/kernel-delta-decay-audit-20261013.md) for conditions and references. Object-owned H/D had explicit authorization in the user's later complete /3 repair plan; questioning it now does not erase that approval, nor does broad approval establish permission for every new learning opportunity.

Three issues remain separate. Removing adaptive H can retain ordinary strengthening and simpler forgetting. Removing all structural weakening leaves no ordinary long-idle structural forgetting under default energy-off conditions without intervention. Lazy evaluation and necessary expiry events can avoid continuous idle refresh, but exact digital simulation is not literally free; model energy is also different from host compute. The waste inventory separates potentially equivalent scheduling, settlement, allocation and encoding improvements from dynamics-changing simplifications. No new research subject, kernel, parameter, service or /4 rerun was changed or started; proposals await a decision, and E68 findings and original evidence remain intact.

## Same-day decision: /5 and explicit authority for kernel changes

At 2026-10-13 03:54:55.230 UTC, original conversation line35088, Liu expressly authorized a new kernel5: revert unexplained or unjustified /4 learning expansions to /2, check the original second-phase conversation for authority, and remove demonstrably redundant kernel work. He required tools to leave internal simulated progression unchanged: even a six-billion-year physical pause is acceptable if the current internal state continues, whereas an unauthorized 0.0001 simulated second is not. The [Chinese source](../../../zh/history/sources/2026-10-13-kernel-performance-audit.md) preserves the wording verbatim.

He also required every non-temporary kernel change lacking explicit authorization to be discussed before implementation, and every change to disclose its content, reason and effect. He requested evidence that selecting /2 still executes the real historical /2 and expressed concern about deliberate tampering. The audit uses original decisions, source versions and independent engineering witnesses; the concern is not recorded as a proven human attack.


> **Public-edition edit (2026-11-11; source lines 68-68):** Private conversation IDs and locators are omitted; scientific quotations and records are retained. The complete source remains unchanged.



At 04:01:29.146 UTC, line35157, he selected /2 reception and learning as the default, retaining already authorized local execution, H and reclamation, with unified reception and asynchronous propagation separately labeled research options. The original belongs to conversation `[private locator omitted]`, already indexed above. This creates /5, without renaming /4 or altering historical individuals. H remains authorized; earlier cost questions are not permission to remove it or all decay. See [governance](../../kernel-change-governance.md) and the [implementation plan](../../plans/local-events-v5.md).

Rereading the original **ThreeMind二期** conversation retains actual-emission strengthening, ordinary co-stimulus learning, arrival-window novelty and strong-input decisions. Restoring old rules must not remove other mechanisms the user approved. The [baseline verification](../../plans/memory5-baseline-verification.md) reports historical /2 comparisons and tool-time checks with their limits.

This entry records authorized development and isolated validation in progress. Review exposed cross-backend option differences, a missing completed-emission phase for later same-time input, and derived-index residue; these are development defects being corrected with witnesses. Overall compatibility, performance and installation remain for a later delivery record. No /5 research-score improvement or completed deployment is claimed; no new shape/color experiment or manuscript edit is authorized by this entry.

## Same-day engineering acceptance: /5 completed, research gains still untested

This addendum follows and preserves the earlier development-stage record. The distinct /5 implementation and isolated engineering acceptance are complete: /2 reception/learning defaults, no internal downstream pairing, restored co-stimulus scoring, novelty eligibility/windows, actual-transmission strengthening and inhibition ordering. Authorized local execution, H, reclamation and optional mechanisms remain. `legacy-stability` replaces connection forgetting only; automatic node support still has its own H and is not the complete /2 model. Version, state format and effects are recorded in the [delivery](../../plans/local-events-v5-delivery.md).

Equivalent fast paths cover W23 fast-trace projection reuse, W24 validated internal short-term resource paths/configuration reuse, W25 singleton context, and partial W04 same-time copy/writeback removal. All 112 complete Python states and 56 complete native states match their pre-optimization witnesses exactly, including queues and audit counters; these particular comparisons do not substitute floating-point tolerance for exact equality. Historical /4 frozen witnesses remain exact. Independent /2 comparisons against three historical sources, 24 conditions and 66 snapshots per implementation, and the latest fixed regressions still pass. The focused suite has 74 passes, Rust Core 13 and isolated Lab 54; overlapping batches must not be added as independent experiments. Final standalone Runtime builds/interoperability and the full acceptance inventory are tracked in the delivery table.

Isolated small-graph measurements show /5 substantially faster than /4 but still slower than /2. Both corrected rules and implementation savings contribute; no single fast path is credited with the whole gain, and no shape/color or long-term retention improvement is inferred. Final repeated timings and separated costs belong in the delivery report; this source does not prefill ratios still being remeasured. The UI's gray default hint was also corrected where it displayed /4 defaults; actual /5 reception defaults were already correct, so this presentation fix does not alter dynamics.

The `coincident` research combination retains a separately disclosed mixed external/internal source-attribution limitation, with its treatment awaiting the user. Backend agreement does not establish that research rule's validity. The existing service has not installed the new extension or restarted; no database migration or new formal shape/color experiment occurred. E67/E68 originals, existing individuals and the author's manuscript remain intact. Engineering completion, research benefit and deployment status are separate. [Baseline evidence](../../plans/memory5-baseline-verification.md) · [Delivery and pending decision](../../plans/local-events-v5-delivery.md)

## Same-day user response and installation closure

The user explicitly retained coincident, disabled by default, conditional on its presence not affecting5 while off. They clarified that the8877 service was assistant residue rather than user-started, authorizing its closure if unnecessary or restart if useful. The [Chinese source](../../../zh/history/sources/2026-10-13-kernel-performance-audit.md) preserves both exact replies.

New isolation checks found no mixed-reception contamination of sequential defaults. The option and its enabled-mode limitation remain, with no kernel rule change. Queue inspection found no pending/active/expired jobs or experiment workers, so the idle service was closed and the verified module installed in the everyday environment without starting another resident service. Doctor and fresh-fixture restoration passed; installed old2 fidelity plus isolation checks passed58 tests. The two pending decisions are resolved, without restarting E67/E68 or rerunning formal individuals. [Installation and evidence](../../plans/local-events-v5-delivery.md)

## Same-day follow-up: version comparison and temporary H-off test

The user requested performance comparisons of5 against3.1 and2, then explicitly authorized a temporary test with5's half-life disabled. The [Chinese source](../../../zh/history/sources/2026-10-13-kernel-performance-audit.md) preserves both statements verbatim. This authorized fresh engineering fixtures, not production-kernel, default or historical-subject changes. Before testing, the assistant disclosed that existing stability/manual options disable runtime edge/node H computation while substituting other forgetting/support rules. It is not a pure arithmetic removal on an unchanged trajectory. Each fresh fixture advanced continuously without restoring a formal student.

Six batches comprise352 runs including44 warmups, with within-group hash/time/size checks; raw receipts remain ignored. On dense16–128-node native-release fixtures, default5 costs1.78–1.91 times3.1 and3.28–3.72 times2; a64-node10-second continuation also remains slower. With1024 nodes/1024 edges and rotating two-channel inputs over100 simulated seconds,5 H takes0.479 physical seconds, reducing3.1/2 time by37.82%/38.65%. This is a large, low-degree, locally touched workload benefit, not general speed or learning superiority.

In the temporary2×2 test, full H-off with existing replacement rules changes dense time from1.047 to1.039 seconds (about0.7%, within observed variation), but large sparse time from0.477 to2.735 seconds (5.74 times). Stability schedules edge maintenance every100ms rather than H's predicted expiry. These results do not support disabling H as a sufficient performance fix; they neither prove zero H arithmetic cost nor assign CPU percentages. Core, installed binaries and defaults remain unchanged; only benchmark inputs/sampling were extended. [Report and raw indexes](../../plans/memory5-performance-comparison-20261013.md)

## Same-day root-cause follow-up: architecture labels are not evidence

The user's direct statement in the current conversation asked for continued investigation of potentially multiple causes of5 being slower than2, and an assessment of whether5's local architecture was inferior to2's global architecture. The [Chinese source](../../../zh/history/sources/2026-10-13-kernel-performance-audit.md) preserves the exact wording; no precise message timestamp or line is recorded for this follow-up.

The assistant instrumented53 functions in an isolated source copy with call counts and nested wall timing, paired with an uninstrumented binary. All12 configuration/workload final-state hashes match; production Core source hashes remain unchanged. These are fixed-fixture witnesses, not proof for every trajectory. Instrumentation adds wall overhead and neither creates simulation events nor replaces repeated uninstrumented performance measurements.

On the64-node dense H fixture, self times are0.28135s for`settle_edge`,0.15434s for`edge_value`, and0.15930s for`timer`; external pairing and per-node emission are also hotspots. H growth/decay/crossing total0.02360s self time within1.13948s instrumented advancement, not a claim of exactly2% production CPU. All three H functions have zero calls in both dense and sparse complete-no-H fixtures, confirming the disable configuration; this does not authorize deleting forgetting or default H.

The1024-node sparse fixture isolates S periodic maintenance:897382 expiry checks against3942 for default H, with S self times0.87182s in`expiry` and0.34273s in`timer`. Whole-round and per-node emission calls are different units, and event totals are not effective signal counts. Combined with default H's measured low-degree large-graph advantage, the finding is expensive dense object/scheduling representation and S periodic maintenance eroding locality benefits—not inherent inferiority of local principles.

Constant caching and avoiding complete-edge clones for current read-only weights remain under temporary-copy validation, without a benefit or production-integration claim. Typed messages, compact slots, and exact lazy stability settlement are recommendations only. Formal changes still require disclosed reasons, contents, effects, and applicable authorization. Historical versions, formal students, services, manuscript, and defaults are unchanged. [Root causes and limits](../../plans/memory5-root-cause-20261013.md)

### Same-day candidate results: partial savings, no production integration

The three uninstrumented binaries—baseline, eligibility-constant cache A, and A plus one current read-only weight path B—subsequently completed 66 isolated runs with matching within-case complete final-state hashes. Each main workload has one warmup and seven alternating-order repetitions; six additional version/option controls are single-state witnesses, not timing conclusions. Combined A+B lowers the dense median by 5.54%, but ranges overlap and three of seven rounds are slower. The large-sparse median falls by 10.58%, with every combined sample below the fastest baseline. B was not measured separately; the combined gain is not attributed to B alone.

This identifies some reducible representation cost without resolving the earlier greater-than-threefold dense gap. Intermediate trajectories, complete restoration, configuration changes, and broader conditions still require checks. Matching 66 final states is not proof of all dynamics, and temporary executables were not installed or integrated into production Core/defaults. Earlier pending-stage statements remain historical; this addendum and the [candidate results](../../plans/memory5-root-cause-20261013.md) record the latest status.

## Same-day optimization request: planning only

The user's original wording after the reports was:

> 根据现有分析，给出优化方案

Translation: provide an optimization proposal based on the current analysis. The assistant appended it to the [existing version-5 plan](../../plans/local-events-v5.md), preserving earlier implementation records. Proposed P0–P4 optimize equivalent execution representation; lazy stability S initially requires a feasibility proof. Architecture labels, deleting H or relaxed thresholds are not performance evidence. Mutations invalidate same-time caches, and real learning cannot be skipped. Equivalent changes would retain version 5, while numerical, ordering or rule changes return to the user first. These are assistant recommendations, not user approval. No kernel, default, formal subject or service changed this turn.

## Same-day approval: name the optimized kernel 5.1

Original user statement:

> 同意你的建议，按照此思路优化，命名为 5.1

Translation: agree with the recommendations, optimize along this approach, and name it 5.1. This approves equivalent engineering optimization and explicitly overrides the earlier recommendation to retain version 5 identity. Historical 5 remains independently creatable/restorable, the application default is unchanged, and S initially receives feasibility work only. Implementation, validation and gains are pending, not established by approval. [Plan update](../../plans/local-events-v5.md)


## October 13, 2026: `/5.1` delivery and naming follow-up

After the minor-version host-routing bug was disclosed, the user permitted a feasibility/necessity assessment of unified naming but explicitly required no renaming this release. Original Chinese wording is retained in the Chinese source. The release fixes faulty parsing without replacing scientific IDs; explicit future catalog fields/display aliases are assistant recommendations, not implemented decisions.

Implementation and measurement: 5.1 retains 5 and older kernels and default 3. Typed internal signals, numeric local clocks, scalar reads and compact slots pass 189 isolated consistency checks; 8 frozen-executable full-state cases, 20 Rust tests and 40 Runtime/world recovery checks pass. Corrected host capability names allow ordinary prepared/start/worker claim for 3, 3.1 and 5.1. Main matrix 432 runs, phase 64 andfrozen 8 showH49.58–60.38% lower cost than 5 and S51.27–58.11% lower. These are engineering costs, not shape/color or consciousness evidence; dense/small sparse still trail 2, while large sparse improves substantially. Native installation and UI/Runtime builds are complete; no service or research individual was changed. [Delivery, failures and limits](../../plans/local-events-v51-delivery.md).

The S feasibility study finds a numerical boundary where repeated floating products and a power formula disagree at strict pruning; periodic S therefore remains unchanged. No unproved P4 expiry skip is added. This is an engineering feasibility finding, not cancellation of forgetting or a new formal scientific observation.
