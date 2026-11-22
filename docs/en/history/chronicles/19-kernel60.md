# Chapter 19: a fixed function from stimulus to node

[中文](../../../zh/history/chronicles/19-kernel60.md)

## 12 November 2026: separating addressing from learned connections

While revising the manuscript's channel definitions, the author returned to a basic question: how does a later stimulus find the corresponding node? Existing implementations looked up a stimulus code to obtain a node identifier assigned in birth order. The author's intended receiving function instead resolved the same code to the same location by fixed rules, without a separate allocation relation.

The discussion concerned entry into the network. Connections subsequently shaped by experience constitute a different level of mapping. The author chose to establish 6.0 while preserving older kernels and evidence, and to test the new implementation separately.

The authorization was explicit: implement fixed-function addressing first and retain the other 5.3 mechanisms. Version 6.0 was to own its implementation and run without the 5.3 kernel code. Eligibility and stability could be removed only if unused. The author subsequently clarified that a virtual kernel address, rather than a physical memory address, was acceptable.

## Implementation and initial checks

Existing stimulus codes are unsigned 32-bit integers. Version 6.0 takes `F(c)=c`, so first-arrival order no longer assigns different identifiers to a code. The node container holds only nodes that exist, without allocating a continuous array up to the largest code. A deleted node may be recreated at the same address.

Python and Rust received independent transitions, parameter definitions and checkpoint identities. Elementary numerical mechanisms, timestamps and energy accounting remain shared infrastructure. Eligibility still contributes to stability updates, and node stability affects plasticity, so these fields were retained. The inverse-logarithmic default and other 5.3 mechanisms were preserved; the global creation default remains 5.3.

The initial 92 dedicated checks, 458 historical/runtime regressions and 20 Rust foundation tests passed. Thirty-six conditions with matching identifiers produced exactly matching complete states across versions. Different addresses can affect particular positions, energy regions and simultaneous ordering through the existing identifier-based rules; this effect is disclosed with the version.

One address-reuse boundary still requires the author's decision: should a recreated node receive or discard signals sent before its predecessor was deleted? This question was raised explicitly rather than settled through engineering scores. No new mechanism, shape–color or embodied study was started, and no manuscript or original evidence was changed.

Sources: [version description](../../v2-kernel60.md), [engineering report](../../../../lab/explorations/2026-11-12-kernel60/engineering-report.en.md), and the author's authorization and virtual-address clarification in this task. Engineering fixtures are not additional research sources.

## 13 November 2026 addendum: delivery after recreation

The author reaffirmed that both policies should remain available if straightforward to implement, with address delivery as the default. In the author's interpretation, recreation at an address means that the relevant stimulus has returned, making reception of earlier in-flight signals reasonable. This is an explicit model choice, separate from engineering scores.

Each node records a birth ordinal. When discarding old signals is selected, events also record the cumulative birth count at emission; no deleted-node table is needed. Default delivery still follows the address. Both policies cover excitation, inhibition and wake events, are selected at creation, and survive complete-state saving.

Final verification passed 134 dedicated checks and 461 regression/configuration checks, with 2 database-dependent skips; 20 Rust foundation checks and the frontend build passed. Both packages were accepted in isolation, then the native package was installed in the project environment without restarting services. Fixed-function addressing engineering is complete. The global default remains 5.3; mechanism and embodied reruns require separate protocols. This decision follows the initial pending record, preserving earlier reports and evidence. [Final engineering record](../../../../lab/explorations/2026-11-12-kernel60/engineering-report.en.md)

## 13 November 2026 addendum: the benefit and cost of 0.018

The author approved a quick validation of 0.018, conditional on suitability before adoption. The candidate originated in a retrospective R47b weight comparison. Five courses and acceptance rules were frozen before testing eight new origins in 640 continuous sequences under 0.008 and 0.018. Older origins were not recounted and no historical subject was restored.

Weak residual connection clearance at 30 seconds improved from 0/8 to 8/8; 300-second responses after massed repetition, spaced review and strong stimulation were exactly unchanged. Four novelty-course origins lost their new target connections and responses. Four others retained the new target, but other old connections were removed and responses grew and changed; these were not absent responses. Weak-course behavior was already silent under the baseline, so the gain concerned residual structure rather than newly achieved behavioral forgetting.

The candidate failed the original rules and the 6.0 default remains 0.008. This corrects a recommendation based only on three retention courses: relatively weak connections can still carry expressible novelty-related experience. Boundaries, arithmetic and curricula verified; the complete archive was read back through the research API with zero pending operations. An audit timestamp-type error was corrected in a separate version without changing execution or scoring. Production Core, earlier evidence and manuscripts were unchanged. [Protocol and conclusions](../../../../lab/explorations/2026-11-13-kernel60-pruning/report.en.md)


## 13 November 2026 addendum: reproduction first, then the cost stopping rule

The author approved comprehensive revalidation plan v2, correcting the previous extension of eight-origin exploration and 48-origin confirmation to every task. Each batch should normally retain its historical size, begin only when the whole batch fits, and avoid mandatory migration. The author then explicitly prioritized the reproduction rule needed by aquatic experiments. Both decisions preceded implementation; old evidence, paused subjects and manuscripts remained intact.

New rule `threemind.birth/2` applies only to 6.0. Persistent connection state and decay age are inherited by default; `reset` changes only inherited age. Offspring clocks, fast activity, resource-use state and in-flight queues are initialized anew. Exact continuation still preserves complete state. Python and Rust now allow inherited age to exceed an offspring's own lifetime. Decay and transmission formulas, the global default and deletion threshold were unchanged. Fourteen historical birth hashes matched. Backend, multigeneration ecology and standalone Rust recovery checks passed; relevant regression passed 416 with 15 database-dependent skips, followed by a 49-check reproduction suite including added mid-delivery cases. Overlapping checks are not summed.

The cost gate found a concrete obstacle. The first attempt incorrectly assumed historical node identifiers began at one. Its failed alignment check and evidence were preserved, and a separately named correction matched IDs 0–1023, size and input. Five initial and five confirmation comparisons showed a substantial slowdown relative to 5.1. Confirmation medians were 0.0525683 and 0.4474190 seconds, a ratio of 8.51, with matching CPU-time evidence. Memory and disk were ample; allocated state storage increased only 1.12-fold. The author's preregistered twofold threshold therefore paused formal mechanism, visual and aquatic revalidation.

A separately frozen, bounded diagnostic found similar costs and identical scan counts in 5.3 and 6.0, placing the main difference before fixed-function addressing. Structural checks every 0.1 internal seconds traverse all nodes and connections. This is a specific path to profile, supported by code and counters rather than a measured decomposition of CPU time. No optimization was implemented automatically. Completed reproduction engineering and paused scientific revalidation remain separate outcomes. [Approved plan](../../plans/kernel60-revalidation-v2.md) · [Methods, correction and results](../../../../lab/explorations/2026-11-13-kernel60-revalidation/report.en.md)


Same-day storage correction: the first instrument measured ordinary file length. Windows allocation information gives a final-state ratio of 1.1192. Original records remain intact; bilingual report revision 2 was read back through the API. The complete 725-member archive verified with zero pending operations. Engineering completion and the paused full campaign remain distinct. [Delivery receipts](../../../../lab/explorations/2026-11-13-kernel60-revalidation/delivery.md)


## 13 November 2026 addendum: repeated emission dominates advancement cost

The author requested cost diagnosis. R51b added timers only to isolated source and retained production originals and complete states. Thirty-one production-module and 21 instrumented-copy trials found 6.0 still 8.57 times slower than 5.1 on the 1024-node fixture. Emission occupied 76.66% of coarse-profile time and structural checks 17.67%. Ninety-five percent of transmission attempts transmitted nothing. All 92,160 attempts during internal seconds 1–10 had zero output while that interval consumed 87.15% of elapsed time.

Code and saved states explain the pattern: tiny inhibition keeps nodes scheduling emission, while the connection threshold blocks the resulting signals. Settlement and resource updates still execute. Reducing structural-check frequency saved 14.06%; exponential decay saved 8.59%. This revises the earlier scan-first investigation priority to emission implementation. Zero output still involves internal changes, so simply removing these attempts is inappropriate. The recommendation is to reduce copying, time conversion and repeated configuration access while preserving rules.

All 104 complete states verified; 21 instrumented final states matched production exactly. The 255-member archive and bilingual reports completed API readback with pending=0. Production sources, installed modules and formal subjects were unchanged. Engineering diagnosis is complete; comprehensive revalidation remains paused. [Protocol, results and recommendations](../../../../lab/explorations/2026-11-13-kernel60-revalidation/cost-profile/report.en.md)


## 13 November 2026 addendum: 6.1 passes optimization checks; revalidation is authorized to continue

The author approved local deletion by default with optional global scans, separate activation and inhibition sender thresholds, and fewer copies, time conversions and repeated lookups. He then explicitly authorized continuing comprehensive revalidation plan v2 on 6.1 once optimization checks passed. Historical 6.0 implementations and batches remain intact.

Version 6.1 retains fixed-function addressing, inverse-logarithmic decay and the 0.008 deletion threshold. Local deadlines replace default whole-graph deletion scans. Activation/inhibition sender thresholds are 0.004/0.002. Their effects on weak emission are declared dynamics changes; typed configuration, numeric timestamps and reduced copying preserve calculation rules. The two kinds of change are evaluated separately.

R51c completed 48 engineering trials at two sizes. Default 6.1 takes 0.8073 and 0.8234 times the 5.1 time, approximately 90% less than 6.0. Allocated artifacts are about 1.10 times the 5.1 size. All 96 complete states passed independent verification; eight global-deletion/zero-threshold pairs reproduce complete 6.0 results. An isolated-node deletion that initially lagged by one grid point was corrected before timing was frozen. The engineering target is met and the performance stop is lifted.

The original scientific questions, historical scales, whole-system continuity and resource stopping rules remain in force. New batches register 6.1 explicitly, beginning with stimulus units and connection formation. Engineering completion and old scientific scores are not relabelled as 6.1 findings. [Public edition: manuscript editing or private locator omitted.] [Report](../../../../lab/explorations/2026-11-13-kernel61/report.en.md) · [Continuation decision](../../plans/kernel61-revalidation-addendum.md)


## 13 November 2026 addendum: scientific revalidation begins; selective connection causality reproduces

R51d retained E17's two encoding blocks and two configurations, completing 264 conditions and verification of 528 full states. Grouped inputs formed connections; splitting them into individual elements did not. Repeated histories and equal-dose changes of order altered connection states. All 96 weak background connections remained in each configuration after 120 seconds, so the weak-deletion target failed. This continues the known inverse-logarithmic tail; defaults were not changed. Structural persistence, temporal response and convergence were reported separately.

The small R51e causal study then preceded the longer bodily-process study. Eight origins, 16 opposite teaching lines and 80 research copies completed. Target silencing eliminated 100% of the experience effect; matched silencing eliminated 0%; immediate restoration reproduced complete reference states and trajectories exactly. All eight origins met the predefined selective-effect target. Experience-related connection causality therefore persists under the new addressing and emission rules.

Both batches delivered bilingual reports, separate read-only arithmetic checks and full API archive readback with zero pending requests: 1,893 members for R51d and 306 for R51e. Historical originals remain intact. [Public edition: manuscript editing or private locator omitted.] [Coverage](../../../../lab/explorations/2026-11-13-kernel61/coverage.en.md) · [Stimulus report](../../../../lab/explorations/2026-11-13-kernel61/stimulus/report.en.md) · [Causal report](../../../../lab/explorations/2026-11-13-kernel61/causal/report.en.md)


## 13 November 2026 addendum: bodily association retention and cued expression reproduce on 6.1

R51f retained E18's four encoding blocks and separate calibration material: 16 calibration and 616 formal conditions, with 1,264 initial/final states verified. All 192 trained probes were directionally correct at 1, 60 and 300 internal seconds; untrained controls passed 0/48. Blocking outgoing cue connections reduced all 32 target increment integrals to zero. Matched blocking retained 32 correct directions, with integrals unchanged or at most 0.273% higher. Removing the block restored 32 complete Core states and four activity trajectories exactly. Task activity had subsided by convergence, leaving the original primary convergence score at 0/240. Process retention and stable final output received separate conclusions.

The result confirms that 6.1 stores bodily associations and expresses them after 300 seconds, with outgoing cue connections necessary for expression. Task activation was zero before the cue, while the cued-minus-blank trajectory recovered the correct direction. Associative observation records retained residual values; the report does not claim all recent state had vanished. Formal execution took 37.16 minutes; pre-analysis originals were 246.36 MiB logical and 255.91 MiB allocated, with at most 12 nodes and 60 edges. No scientific stopping condition was triggered.

The 4,470-member package and bilingual reports passed complete API readback with pending=0, record facdd50e-2c7f-5399-8237-7ac26537913e. R51g then registered the original eight-source five-system comparison, retaining four baselines and historical criteria. All 20 instrument paths produced identical whole states, and formal execution began. R51g has no final scientific result yet; 64-source confirmation and remaining mechanisms, embodiment and shape/color studies are pending. A preparatory bodily-transfer protocol adds 40 full-window blank controls to repair a historical missing tail without enlarging source N. [Report](../../../../lab/explorations/2026-11-13-kernel61/body_memory/report.en.md) · [Coverage](../../../../lab/explorations/2026-11-13-kernel61/coverage.en.md)


## 13 November 2026 addendum: eight-source comparison delivered; independent confirmation started

R51g completed. ThreeMind 6.1 scored 8/8 on experience dependence, selective causality, temporal interaction and feedback adaptation, with 8/8 sources satisfying all four together. Every comparator had 0/8 joint passes. Criterion counts were 0/0/0/0 for the reactive controller, 8/8/0/0 for the finite-state controller, 8/8/0/8 for Hebbian learning and 8/0/5/8 for the fixed recurrent network with personal readout. The recurrent network's temporal count of 5/8 missed the original 6/8 threshold. ThreeMind won the registered conjunction, reproducing the earlier discrimination on 6.1.

Independent verification passed for 4,240 scientific whole states, 2,560 probes and 160 closed-loop replay groups. Matching was valid and scientific_stop=false. The 4,903-member archive and reports passed full API readback with zero pending requests, record 84cc0d63-6ec4-5cb1-a527-5f002881f9b6. Formal execution took 419.17 seconds. R51i then registered the original 64-source confirmation, seeds 1096100–1096163. All 20 apparatus paths produced identical whole endpoints and serial formal execution began. Criteria and historical statistics are unchanged; safe pauses now occur at complete-system boundaries. Confirmation has no result yet; the eight-group result is not a 64-group finding.

[R51g](../../../../lab/explorations/2026-11-13-kernel61/criteria/report.en.md) · [R51i](../../../../lab/explorations/2026-11-13-kernel61/criteria_confirmation/protocol.en.md)


## 13 November 2026: temporal M5 readout with a separate historical endpoint

The author approved temporal readout as primary and the old endpoint as a separate control. New M5 calibration will use activation, inhibition, direct activation and associative activation over a fixed window, retaining the 110-millisecond activation endpoint separately. Eight-origin exploration and 48-origin confirmation remain distinct. Previous subjects, readouts and reports are preserved. This is a design decision; the new M5 batch has no scientific result yet.

R51i's independent 64-group confirmation is still running. Following a brief network interruption, host 22356 and its creation time matched the running record; completed disk boundaries continued advancing without STOP. Offline checks passed for R51h's 280-case bodily-transfer table and full measurement window, and AST comparison confirmed the historical R51j transfer functions. Neither new batch is registered or has created scientific subjects. The archive publisher now supports explicit preregistered batch caps and streaming hashes; a synthetic archive check passed. Frozen scientific execution code is unchanged.

[M5](../../../../lab/explorations/2026-11-13-kernel61/fixed_readout/decision.en.md) · [R51h](../../../../lab/explorations/2026-11-13-kernel61/body_transfer/protocol.en.md) · [R51j](../../../../lab/explorations/2026-11-13-kernel61/transfer/protocol.en.md)


## 13 November 2026: M5 temporal measurement and curriculum prepared

Following the author's approval, R51k represents four activity fields over 1–250 ms with five consecutive 50-ms means and retains complete millisecond trajectories. Full anonymous-channel and declared-port readouts are separate, alongside the same-experience 110-ms endpoint. Numerical checks distinguish two sequences with equal total activity and equal 110-ms endpoints but different timing, and verify readout restoration and continued learning.

The curriculum retains sixteen rounds and eighteen seconds, replacing uniform gaps with five each of 0.8, 1.0 and 1.2 seconds to provide increasing spacing. Old-task development errors permit at most two targeted correction rounds, retaining previous calibration samples and statistics. Readouts remain frozen before first answers to new relations; further calibration is scored separately. These changes from historical M5 were disclosed before execution. Scale remains eight origins. Protocol and tools are prepared but unregistered, with no scientific individuals created; native apparatus and complete-original audits remain execution requirements.

[R51k](../../../../lab/explorations/2026-11-13-kernel61/fixed_readout/protocol.en.md)


## 13 November 2026: pre-execution transfer apparatus checks

Inspection of the 6.1 implementation identified node-visit and edge-visit increments from declared same-time materialization. R51j records those increments separately and requires the post-continuation differences to equal them exactly. All other fields and response trajectories retain their original tolerance; observation and restoration paths still require identical whole-state hashes. Four pure numerical cases passed. No formal subjects were created and Core was unchanged.

Preparation began for R51l's 48-source confirmation, retaining the six historical M1 strata and decision criteria with new 6.1 encoding sources 1116100–1116147. Offline checks passed for the cases, cue doses and historical probe/measurement functions. The runner and full audit remain unfinished; this batch is neither registered nor executed.

[R51j](../../../../lab/explorations/2026-11-13-kernel61/transfer/protocol.en.md) · [R51l](../../../../lab/explorations/2026-11-13-kernel61/transfer_confirmation/protocol.en.md)


## 13 November 2026: 64-group confirmation delivered; bodily transfer begins at the original scale

R51i completed 320 system units across 64 independent groups and five implementations. Version 6.1 passed every criterion and their conjunction in 64/64 sources; each comparator had 0/64 joint passes. The fixed recurrent network passed temporal interaction in 49/64 sources, exceeding the original 48/64 threshold. Each paired joint-pass advantage was 100 percentage points, with Holm-adjusted P=4.3368×10⁻¹⁹. The exact 95% interval for ThreeMind's proportion was 94.40%–100%. This completes the registered confirmation target: 6.1 consistently develops experience dependence, selective internal causality, temporal interaction and feedback adaptation, and wins their conjunction among these five implementations.

Verification passed for 33,920 whole states, 20,480 probes, 1,280 replay groups and 128 numerical reconstructions of recurrent-network teaching. Computation took 98.33 minutes, peak private memory was 654.05 MiB, and file cost remained within budget. Record 51a6fe79-aa3c-5b3a-b934-4ae4cd0db085 has complete API readback of its 38,852-member archive and zero pending requests. Archive SHA256: 469b97e0505bfae2924c0342071816ab8a14ff423a314675bd40514c4c7d5f8a. No stopping condition was triggered.

The author asked whether verification had displaced the approved campaign. The scope, source counts and stopping rules still follow plan v2 on 6.1. The five-system comparison was advanced in the sequence; E12, E15, event order, spaced review and X2 remain pending. Verification read committed originals without rerunning students. Preparation checks also fixed a same-name module import before the next batch. Prepared tools are not counted as scientific outcomes; completed checks are not repeated without a concrete reason.

R51h was then registered, passed its independent apparatus checks and began. It uses 40 complete R51f parents to create 240 physical-cue copies and 40 equal-duration blank copies across the original four material blocks, without new teaching. Parents remain intact. Local transfer, temporal readout and transfer confirmation remain prepared or awaiting registration. [Public edition: manuscript editing or private locator omitted.] [R51i report](../../../../lab/explorations/2026-11-13-kernel61/criteria_confirmation/report.en.md) · [Coverage](../../../../lab/explorations/2026-11-13-kernel61/coverage.en.md)


## 13 November 2026: bodily transfer passed; local transplantation begins

R51h completed 280 conditions with four material blocks unchanged. Bodily–marker correspondences survived the new angle and gravity: trained responses were in the original direction in 192/192 tests, versus 0/48 untrained. All 144 tests with inertial input also responded in the original direction; the historical reverse effect did not recur. Converged marker expression remained 0/240, with process and endpoint scored separately. Read-only checks passed for 560 new states, 40 parents and paired curves. Full API readback verified 2,305 archive members, pending0, with no scientific stop. R51j eight-source local transfer was then registered, apparatus-verified and started. Observation, restoration and host-pause endpoints matched; continuation after same-time preparation preserved trajectories and state.

[R51h](../../../../lab/explorations/2026-11-13-kernel61/body_transfer/report.en.md)


## 13 November 2026: local transfer delivered; temporal readout study running

All eight R51j sources met the transfer target. Target local connections changed 48/48 door choices to the donor direction while preserving 48/48 unrelated choices. Persistent transfer had the same effect; sham and restored states matched intact references exactly. The 16 target packages differed only in edge destinations and corresponding timer endpoints, locating the effect in connection destinations in this batch. Fast fields were identical between parents, so fast exchange was a zero-change condition and did not transfer choices. Read-only verification passed for 816 whole states and 672 probes. Full API readback verified 1,016 archive members, pending0. No stop was triggered. Authorized R51k then began: four-field temporal readout is primary and the 110-ms endpoint is separate. Its eight-source continuous curriculum calibrates personal readers before freezing them and teaching new Core relationships. Independent apparatus passed; no formal outcome is yet available. [R51j](../../../../lab/explorations/2026-11-13-kernel61/transfer/report.en.md)


13 November 2026 — The author requested R51m immediately after current R51k and before R51l or other batches. It will locate the changed inertial response by comparing genuine memory/2 with 6.1, aligning stimuli, process windows and blanks, and testing decay, deletion speed and other supported candidates. Higher deletion thresholds are research configurations only; defaults and Core remain unchanged. Preparation is not a result. [R51m](../../../../lab/explorations/2026-11-13-kernel61/inertial_reversal/decision.en.md)

## 2026-11-13：R51k fixed expression delivered

R51k completed eight sources: the 110-ms output-port reader passed fixed expression and connection causality in 8/8; the primary temporal condition passed in 4/8 and 0/8, below 6/8. Blocking new connections reduced endpoint new answers from 56/64 to 0/64 while preserving 64/64 old answers, with exact restoration. Version 6.1 retains expression of new learning through a fixed personal reader; the tested temporal features failed the stable-expression target.

The original host reached its private-memory budget after two complete sources. After preserving the exact STOP, each remaining source used a fresh serial host, retaining continuous state within the source, curriculum and 1-GiB budget. Scientific computation totalled 3,207.38 seconds. A separate read-only audit revision recomputed the active index in 32 same-time configuration operations while preserving time and event queues. The original audit and failure records remain. This corrects an audit tool, not scientific execution or Core dynamics.

All 2,024 complete states and 1,824 answers passed audit. The 2,149-member archive and bilingual reports were read back through the API with pending=0, record 5fbc563e-3574-52f3-b7f9-9b2eb4233d4d. No campaign stop was triggered. R51m inertial investigation is next, before R51l; neither has created formal individuals at this point.

[Report](../../../../lab/explorations/2026-11-13-kernel61/fixed_readout/report.en.md)

## 2026-11-13：R51m completed: the transmission threshold controls inertial reversal

The author proposed that slower decay might prevent prompt deletion of transient connections and requested an explanation before later replications. R51m completed 1,792 stages across four historical material blocks, five genuine versions and 17 configurations. Versions /2, /3.1 and /5.1 were reversed in 16/16 full-sensory tests; /5.3 and /6.1 followed teaching in 16/16. Disabling deletion preserved reversal in all four historical blocks. Exponential decay, an independently calibrated higher deletion threshold, and their combination failed to restore reversal in 6.1. Raising only the transmitted-signal threshold from 0.0004 to 0.004 restored 16/16 reversed full-sensory responses and preserved 16/16 taught joint-only responses, meeting the target in 4/4 blocks. Thus prompt deletion was rejected as a necessary explanation, while causal control by the transmission threshold was established. The public pretest operation disabling inhibition also changed 12/16 historical responses to the taught direction; it includes clearing inhibitory state and is reported at that intervention scope.

The audit verified 3,584 initial/final states, 192 intervention states and 235,712 inputs. The 15,540-member archive was read back through the API, pending=0, record 16c42855-1d4f-5d15-9484-94ca325a2ded. Scientific execution took 43.04 minutes, with peak private memory of 671.05 MiB; matched 80-stage execution in 6.1 took 1.078 times that in 5.1. Bodily association was retained and no campaign stop was triggered. R51l, the 48-source transfer confirmation, follows. Defaults, production Core, historical originals and the author manuscript are preserved.

[Report](../../../../lab/explorations/2026-11-13-kernel61/inertial_reversal/report.en.md)


On 13 November 2026, the author requested an assessment of whether the default 6.1 transmission threshold should increase to preserve inertial reversal. R51m established restoration at 0.004 versus 0.0004; the default review must also consider weak cues, order expression, frozen readouts and resource costs. Frozen batches retain their configurations. No default-value comparison or default change has been made; the recommendation will be submitted to the author. [R51m default review](../../../../lab/explorations/2026-11-13-kernel61/inertial_reversal/default-review.en.md)


## 2026-11-13：R51l 48-source local-transfer confirmation delivered

All 48 independent R51l sources passed, including 8/8 in each of six strata. Target whole and persistent bundles transferred 480/480 first and final target choices to the donor direction while preserving 480/480 unrelated responses; untaught mixtures passed in 192/192 trials. Sham and restoration were exact, while matched transplantation changed the other relationship. The actual changes were the target endpoints of 192 connections and corresponding timers; all 96 fast-bundle exchanges made no changes. Every source had a minimum gain of 100 percentage points, exact two-sided P=7.1054e-15. Read-only checks verified 7,680 states and 10,080,000 frames, and the 8,664-member archive was fully read back through the API, pending=0 and scientific_stop=false. The result confirms selective transfer of responses and closed-loop choices through experience-formed local connections in 6.1. Defaults remain unchanged; E20 event order follows with its original four material blocks.

[Report](../../../../lab/explorations/2026-11-13-kernel61/transfer_confirmation/report.en.md)


2026-11-13 — R51n event-order revalidation was registered and started once, record `f2a0b318-840d-51de-b58e-cba8843721a1`. Four material blocks comprise 96 teaching parents and 576 registered diagnostic copies, with separate 1/30/300-second retention conditions. Five apparatus modes produced identical final state hashes. A pre-run storage amendment losslessly compressed files: all ZIP member bytes and complete-state hashes matched in 65 apparatus states, reducing state files from 1,291,463 to 349,237 bytes while retaining originals. The first formal unit occupied about 0.95 times its historical counterpart. Production Core, defaults, curriculum, scoring and sample size are unchanged. Scientific results await analysis after the full batch. [R51n](../../../../lab/explorations/2026-11-13-kernel61/order_recall/storage-amendment.en.md)


## 2026-11-14：Order expression retained for 300 seconds in kernel6.1

R51n computation completed on 13 November and was analyzed and delivered on 14 November. Four anonymous material blocks provided 96 teaching references and 576 single-test diagnostic copies. Under default facilitation and a 50-ms event interval, order expression passed in 4/4 blocks at both 1 and 30 seconds and in 4/4 at 300 seconds, versus historical 0/4 at 300 seconds. Task activation was zero before the 30- and 300-second cues. All positive conditions showed recency; 32 of 144 paired comparisons passed. The 0.5-second course expressed order at 30 seconds, while historical 1-second primacy under the facilitated 2-second course was not reproduced. Kernel6.1 retains order expression and extends expressible retention of the short-interval course, with course/time differences preserved. Checks verified 6,528 states and 138,752 inputs; the 12,159-member archive was read back through the API with pending=0. No frozen stop was triggered. E21 state exchange remains in preparation, not registered or executed; the default threshold remains 0.0004.

[Report](../../../../lab/explorations/2026-11-13-kernel61/order_recall/report.en.md)


## 2026-11-14：Connection weights causally carry the order response

R51o state exchange is complete. Four material blocks supplied 16 teaching references and 512 diagnostics. Weights alone transferred direction in 16/16; all 128 combinations including weights followed the donor, while all 128 excluding weights retained the recipient direction. This confirms experience-formed connection weights as the causal carrier of the order response after 30 seconds, reproducing E21. Read-only checks verified 1,856 states, 6,336 inputs and 256 exchanges; all 6,896 archive members were read back through the API, pending=0. Execution took 6.81 minutes with peak private memory of 575.32 MiB, without a stop. Next, R51p retains historical scale to examine repetition, teaching timing and reference arrangement; it is currently prepared only. The default threshold remains 0.0004.

[Report](../../../../lab/explorations/2026-11-13-kernel61/order_exchange/report.en.md)


## 2026-11-14：Repetition preserves order expression and extends effective conditions

R51p timing revalidation is complete. Four material blocks supplied 352 teaching references and 1,472 diagnostics: dense order expression passed 80/80, sparse expression 160/240, and separate references 0/64. All 148 historical sparse positives retained the bidirectional criterion, with 12 additional positives; 40 historical primacy effects became recency effects, explicitly retained as directional differences. Read-only checks verified 5,120 states, 88,720 inputs and 384 matched historical comparisons. The first audit incorrectly required a newborn waiting state to be active; its script and failure were preserved, and a separate v2 completed verification without rerunning subjects or changing scores. Runtime was 32.32 minutes with peak private memory of 605.42 MiB and no stop. Full archive API readback is complete, pending=0. R51q is prepared to continue original-scale E22 jitter and dose-matched references. Production Core and defaults remain unchanged.

[Report](../../../../lab/explorations/2026-11-13-kernel61/order_timing/report.en.md)


## 2026-11-14：Timing perturbations and matched doses confirm order expression

R51q timing perturbation and dose-matched reference revalidation is complete. Four material blocks supplied 192 teaching references and 576 diagnostics. Order expression passed 72/72 teaching/K-timing comparisons, 8/8 perturbation comparisons and 16/96 reference comparisons. All historical positives were retained, with 28 added positives. Target integrals were identical across K timings in all 48 comparisons. Shared-reference X cues passed 16/16; target activation was zero in the other 80 reference comparisons. Order expression tolerates the tested timing perturbations, and reference effects are not explained solely by counts or doses. Read-only checks verified 12,864 states and 50,752 inputs. Runtime was 20.16 minutes, peak private memory 598.01 MiB. Losslessly packed complete snapshots brought actual unit allocation to 1.616–1.779 times historical allocation. Full archive API readback is complete, pending=0, with no scientific stop. E21C bodily formation R51r is prepared but not registered or run, retaining four material blocks. Core and defaults remain unchanged.

[Report](../../../../lab/explorations/2026-11-13-kernel61/order_reference/report.en.md)


## 2026-11-14：Distinct local effects during formation and expression

R51r bodily formation and expression revalidation is complete. Four material blocks supplied 32 teaching references and 512 diagnostics. All-on references retained the taught direction in 4/4 blocks for both sensory conditions; all eight primary mechanism contrasts had consistent effects. With full sensory input, teaching depletion and competition strengthened responses, while test-stage depletion and competition weakened them. With joint signals alone, teaching effects also became negative. All 256 cued diagnostics retained the taught direction. The results establish distinct local-mechanism effects during formation and expression, depending on bodily input composition. Read-only verification passed for 1,632 states and 32,544 inputs; the 7,768-member archive was read back through the API, pending=0. Runtime was 16.21 minutes, peak private memory 650.79 MiB, and unit allocation 1.235–1.905 times historical allocation, with no scientific stop. E22 bodily state exchange and waiting, R51s, is being prepared but has not been registered or run. Defaults remain unchanged.

[Report](../../../../lab/explorations/2026-11-13-kernel61/body_formation/report.en.md)


## 2026-11-14：Persistent connections and current state determine bodily responses

R51s bodily state exchange and waiting is complete. Four material blocks supplied 16 complete references, 704 diagnostics and 48 holding stages. Weight exchange had consistent effects in 4/4 blocks for both full-sensory teaching conditions; all 128 weight-containing diagnostics moved partway toward the donor. Current state continued to affect expression. All 12 conditions at 10, 30 and 60 seconds retained the taught direction in 4/4 blocks, with 96/96 cued diagnostics passing. Both primary targets were met. Read-only verification covered 2,352 states, 128 exchanges and 17,888 inputs. The 12,558-member archive was read back through the API, pending=0. Execution took 21.60 minutes, peak private memory was 669.57 MiB, and unit allocation was 1.420–1.715 times historical allocation. No scientific stop occurred; original-scale E12/R51t proceeds with defaults unchanged.

[Report](../../../../lab/explorations/2026-11-13-kernel61/body_recovery/report.en.md)


## 2026-11-14: R51t

The R51t/E12 formal batch has started with two original material blocks and 592 stages. The independent apparatus exposed record-storage costs and a private-memory peak. Failed apparatus originals were retained. Comparable records were separated from additional audits; projections are now losslessly buffered and JSON streamed. Six calibration stages exactly matched complete state, observer, process and projection bytes, with peak private memory 756.20 MiB. Under the existing authorization to increase budgets when space permits, originals, archive and readback each reserve 8 GiB; the conservative full estimate is 7.062 GiB. The twice-historical comparable-record check, 1-GiB private cap and 5/4/5/25-GiB reserves remain unchanged. After exact STOP archival and verification under lock, execution started once. Core and scientific rules are unchanged. This records tooling qualification and startup, not a scientific result. [Protocol](../../../../lab/explorations/2026-11-13-kernel61/memory_timescales/protocol.en.md)

## 2026-11-14：R51t completed; scientific pause triggered

R51t/E12 completed 592 stages in two material blocks. The default combination passed all four pairing-effect comparisons at both 30 and 300 seconds. At 300 seconds the mean effect was 0.033404676, versus 0.008914914 in the original kernel-/2 batch, about 3.75 times the historical value. Disabling existing-connection strengthening only before testing retained 99.9710%–99.9712% of the target margin. However, under the historical persistent-activity condition, task activation remained at one second but was zero at 30 and 300 seconds; all five subsequent 15-second intervention windows were zero throughout. Neither block distinguished both prefixes of the shared-B sequences at any of the one-, three- or 20-second waits (0/2 at each wait), versus 2/2 historically at one second. These two adverse dynamical differences trigger the preregistered scientific stopping rule. Comprehensive revalidation pauses pending the author's decision on causal diagnosis. Read-only verification covered 4,746 complete states, 41,248 inputs and four observation controls. All 10,190 archive members were read back through the research API, pending=0. Execution took 114.29 minutes, with peak private memory 872.29 MiB. Two audit-tool format/scope errors were corrected in separate retained versions, without replaying individuals or changing scores. E15 and later batches remain prepared; Core, defaults and the author's manuscript are unchanged.

[Report](../../../../lab/explorations/2026-11-13-kernel61/memory_timescales/report.en.md)


### 2026-11-14：R51t1原因定位 / Cause investigation

On 2026-11-14 the author authorized a cause investigation after the R51t scientific pause, including comparison with the inertial-reversal findings. R51t1 retains two material blocks and has 384 bounded stages across five authentic versions and declared configuration contrasts. Independent apparatus checks of observation, pause and full restoration passed before the formal run. No scientific conclusion is yet available. Other campaign batches remain paused; defaults and historical reports remain unchanged. Research record: 703d9ec6-df98-5364-85cf-5b9b9febc888; registration pending=0.

## 2026-11-14：R51t1: causal investigation completed

R51t1 completed 476 scientific stages using two exchanged-material blocks. Genuine /1 and /2 reproduced 300-second persistence. Selecting existing legacy connection retention restored 2/2 blocks in /3.1 and /5.1. Default 6.1 had zero activity by 30 seconds but retained four task connections at 300 seconds. Disabling inhibition after unchanged teaching, while activity remained, sustained both blocks through 300 seconds and the subsequent 15-second observation. Enabling depletion or disabling facilitation then terminated activity. The results locate contributions from connection retention, inhibition and short-term resources.

The 0.004 transmitted-signal threshold that restored inertial reversal scored 0/2 here, and the version transitions differ; that common-threshold explanation is rejected. Immediate novelty enhancement in /2 exactly restored historical /1 prefix discrimination in 2/2 blocks. The same change in 6.1 remained at 0/2, so that restoration target was not achieved. All 592 historical E12 results identify /1. R51t's /2 mislabel has a separate erratum and appended correction in the original research record; original reports and artifacts remain intact.

Audits passed for 2248 complete states and 44652 inputs; twenty 6.1 final states exactly match R51t. All 6792 archive members were downloaded through the research API and individually verified, pending=0. Scientific execution took 58.57 minutes, with peak private memory 747.67 MiB. Before archiving, logical content was 1.095 GiB and allocated storage 1.108 GiB. Follow-up protocols were bounded explorations registered after initial observations; stages and copies are not independent samples. Production Core, defaults and manuscripts are unchanged. Diagnosis is complete, while comprehensive revalidation remains paused under R51t's scientific stopping rule pending the author's decision. E15 and later work are unfinished; neither the campaign nor this batch should restart automatically.

[Report](../../../../lab/explorations/2026-11-13-kernel61/persistent_cause/report.en.md)

## 2026-11-14：Three dynamical questions take priority over the replication campaign

The author authorized closed-loop tests of inertial reversal, the relation between persistent-activity duration and decisions, and recovery of prefix discrimination. The comprehensive campaign remains paused. Activity in 6.1 is shortened, not absent. Inhibition is retained while existing gains, decay times and synaptic resources are compared. R51t2 prepares 110 new stages in two material blocks and reuses completed references read-only. Four-block body tasks and delayed choices in four new sources follow under separate freezes. This records authorization and protocol, not new results. A possible 6.2, changed defaults and selective reruns will be discussed after the evidence. r3 retains version-specific historical findings and adds replication and causal investigations, citing research at the points where it motivated the work.

[Source](../sources/2026-11-14-dynamics-function.md)

## 2026-11-14: Dynamical studies delivered; joint rule effects identified

R51t2–t5 are fully delivered. Changing only the test threshold after identical complete teaching states reversed inertial responses in 4/4 encoding blocks; closed-loop posture benefit failed. Retaining inhibition with faster decay restored 300-second low-amplitude activity. Under the new continuous curriculum, both this profile and the reference scored 32/32 on short-delay, long-delay and distractor pairing questions, reaching a ceiling without an additional gain. Removing inhibition made both output integrals exactly equal and nonzero on all 96 cued questions, preventing selection. Prefix recovery still failed in 6.1. In genuine 3.1 and 5.1, immediate novelty plus legacy connection retention restored 2/2 exchanged-material blocks; either alone failed, and manual node retention added no effect. The campaign remains paused; 6.2 and default changes await the author.

[Report](../../../../lab/explorations/2026-11-13-kernel61/dynamics_function/report.en.md)

## 2026-11-14: R51t6 locates reinforcement and forgetting effects on prefix relations

R51t6 completed 70 stages in two exchanged curriculum blocks using an isolated 5.1 research derivative. Reinforcement of base weights by actual associative transmission and stability-dependent slowing of weight forgetting were individually necessary: removing either changed success from 2/2 to 0/2. Removing period-specific decay exemption or recent-transmission protection separately retained 2/2. Disabling all or either component of immediate novelty produced 18 exact scientific-state and 18 exact process matches; the extra immediate bonus was unnecessary. Window-trained weights transferred failure into successful recipients, and reference weights restored window recipients. Disabling reinforcement during testing preserved success. Learned weight differences therefore carried the switch in performance.

The original dialogue establishes that the assistant proposed arrival-window novelty and the author said “开始实施” (begin implementation) after the complete plan at 22:29:02 Beijing time on 29 September, before implementation. The author explicitly confirmed the configuration again on 30 September. 6.1 inherited that rule. Earlier calibration omitted prefix discrimination: a validation-coverage gap, not an unauthorized novelty change during 6.1 development. This is a retrospective audit of primary sources.

The recommendations prioritize immediate novelty as a candidate default for 6.2 and legacy stability retention as an optional candidate. Stability growth/decline must not be relabeled as H time-scale growth/relaxation. The inertial preset changes the connection signal-amount threshold signal_threshold from 0.0004 to 0.004 for both activation and inhibitory signals; source-node sending thresholds are unchanged. Closed-loop benefit failed, so the preset is recommended as optional and disabled by default. These remain recommendations: production kernels, defaults and the manuscript are unchanged, and the campaign remains paused.

Verification passed for 332 complete states, 8462 inputs and independently calculated metrics. The 1131-member archive was downloaded and checked through the API, pending=0. Scientific runtime was 21.38 minutes and peak host private memory 112.96 MiB. Two material blocks are the units; stages and copies do not increase independent N. This is not a production 6.1 or 6.2 result. The initial storage calibration failed before any input or time advancement; its separate v1 evidence and marker remain intact. No formal v2 individual was rerun or rolled back.

[Report](../../../../lab/explorations/2026-11-13-kernel61/prefix_components/report.en.md) · [Authorization](../../../../lab/explorations/2026-11-13-kernel61/prefix_components/novelty-authorization.en.md) · [Evaluation](../../../../lab/explorations/2026-11-13-kernel61/prefix_components/evaluation.en.md)


## 2026-11-14: 6.2 options implemented; prefix recovery failed

The author approved 6.2 based on 6.1. The former legacy connection-retention rule is named stability-based retention, with independent growth and relaxation controls; actual-transmission weight reinforcement is retained. Activation and inhibitory connection signal thresholds can independently override the common value. Each null override falls back separately, and explicit zero disables that type's cutoff. Inertial-reversal and short-inhibition-decay presets expose their parameters and remain disabled by default. Python, Rust, the independent runtime, API, commands and frontend support the new version. All 338 engineering tests passed; the six historical 6.1 implementation hashes are unchanged.

The functional check retained two exchanged-material blocks and crossed single-age inverse-logarithmic/stability retention with arrival-window/immediate novelty. All four configurations scored 0/2 in both Python and Rust. Independent checks verified 48 states and 32 processes; the maximum difference across the four activity variables was 2.1684×10⁻¹⁹. The expectation that restoring these two candidates alone would recover prefix discrimination in 6.2 failed for these materials. The positive 5.1 evidence is preserved. Further comparison must locate the remaining divergences in formation and expression.

Under the preregistered default-selection condition, 6.2 retains arrival-window novelty, single-age inverse-logarithmic decay and the original thresholds. Candidates remain selectable, and the global default for new individuals remains 6.1. The campaign stays paused. Completed 6.1 batches need not all be repeated merely to change the version label; adopting a changed configuration requires evidence for affected claims. Historical research originals and the author's manuscript are unchanged.

[Report](../../../../lab/explorations/2026-11-14-kernel62/report.en.md)


## 2026-11-15: R51t7 restores prefix discrimination in a 6.2 research derivative

The two authorized base-weight reinforcement switches are implemented and enabled by default. Disabling inhibitory weight reinforcement and the other initial switch combinations did not restore discrimination. Across 94 isolated stages, stability retention, immediate novelty and complete emission replacement restored both exchanged curriculum blocks while retaining 6.2 fixed-function addressing. Inhibitory replacement alone, the higher excitatory threshold alone, and their combination each scored 0/2. Replacing a successful parent's eight task weights or its test-transmission configuration with the failed counterpart abolished discrimination. The reverse single exchanges did not rescue failed parents. Formation and expression must work together; fixed-function addressing is compatible with this ability.

The first recorded task difference between successful full replacement and the failed higher-threshold combination occurred in short-term resources at 3.9 internal seconds, before weight or activity differences. Weak-signal handling before resource release is the next single-component candidate, not a production change. Production 6.2 received only the authorized reinforcement switches; other transmission rules and defaults remain intact. The campaign remains paused for the author's decision.

Verification covered 188 execution initial/final states, 16 pre-intervention states and 68 processes, with maximum independent arithmetic error 3.91×10⁻¹⁸. All 542 archive members were downloaded and checked through the API, pending=0. Scientific stage time totaled 35.25 minutes. The first full-graph observation buffer triggered a complete-boundary memory pause; streaming resumed from that state without rerunning teaching or rolling back simulated time.

[Report](../../../../lab/explorations/2026-11-14-kernel62/prefix_recovery/report.en.md)

## 2026-11-15: R51t8 establishes the causal role of pre-release screening

After R51t7, the author requested further localization. Holding stability retention and immediate novelty fixed, this study added five isolated conditions across two exchanged curricula, totaling 30 stages. Five completed controls were reused from verified originals. Adding only pre-release screening to the failed historical-inhibition/0.004 condition changed 0/2 to 2/2. Removing only that check from successful complete historical emission changed 2/2 to 0/2. Forward and reverse interventions establish a causal role for this ordering.

Recovery requires accompanying conditions. With 6.2 inhibition, neither 0.0004 nor 0.004 restored discrimination; historical inhibition at 0.0004 also failed. The successful candidate matches all 4,246 teaching records of task-node and connection states from the complete historical-emission reference. At the first recorded divergence, 3.9 internal seconds, same-time available resources were 0.215375 with screening and 0.107688 without it, while weights and node activity still agreed. Resource consumption by ineffective transmission changes later propagation and learning; this is a dynamical effect rather than merely a performance optimization.

The study establishes a specific recovery combination while retaining fixed-function addressing. Production 6.2, defaults, the paused comprehensive replication and the manuscript were unchanged. Separately decomposing resource use, allocation and learning in modern inhibition is a recommendation, not an implemented change. New computation totaled 22.95 minutes with 95.37 MiB peak private memory and no resource pause or simulation rollback. Read-only verification covered 120 initial/final states and 40 process records, with maximum arithmetic discrepancy 3.91e-18. All 402 archive members were read back through the API; pending=0. The unit remains two curriculum blocks.

[Report](../../../../lab/explorations/2026-11-14-kernel62/prefix_precheck/report.en.md)

## 2026-11-15: R51t9 resource and sending-threshold comparisons completed

The author requested that resource release remain before signal checking, asking whether lower thresholds or greater availability could replace pre-release screening, and then raised node sending thresholds and inverse-logarithmic tails. R51t9 initially registered 24 current-propagation conditions and three conditional historical-inhibition conditions; four high-threshold supply conditions were separately registered prospectively during execution. In total, 186 teaching and diagnostic stages and eight stimulus-free copies were completed. The two exchanged curricula remain two material blocks; 24 stages from four completed references were reused without rerunning them.

All 31 new conditions passed 0/2 curricula. No replacement for pre-release screening restored discrimination. Greater resources increased transmission and weights but failed to preserve the correct prefix difference. The tested expectation that threshold and supply adjustments suffice is rejected. Signal-dependent resource consumption is the next recommendation, not an implemented change.

Stimulus-free observation revealed a separate lifecycle-label defect: original references had zero activation at the one-second sample and no further transmission, yet the default condition remained labeled active at 300 seconds. Two sub-floor entries remained in its active set without expiry or sending timers; the corresponding local-maintenance path exists in both Python and Rust. The label is invalid as a measure of actual activity duration; node-process scores are retained. The combined zero-threshold/faster-recovery conditions still had activity at one second and zero activation at the final 2.6- or 2.9-second samples. Local lifecycle maintenance should be corrected before using survival durations, and label persistence must not be treated as sustained activity or directly attributed to inverse-logarithmic tails.

Read-only verification covered 436 initial/final states, 140 diagnostic processes and 140 independently derived answer checks. All 1049 archive members were read back through the API; pending=0. Production 6.2, defaults, historical evidence and the manuscript are unchanged. Comprehensive replication remains paused.

[Report](../../../../lab/explorations/2026-11-14-kernel62/prefix_resources/report.en.md)

## 2026-11-15: 6.2 pre-release and activity-expiry repairs; R51t10 interrupted

The author approved a default-on pre-release threshold check and required reassessment of persistence after lifecycle repair. Python and Rust 6.2 now expose `resource_precheck_enabled` and `subthreshold_expiry_enabled`, enabled for new individuals. The first checks the applicable excitatory/inhibitory connection thresholds before resource release. The second schedules sub-floor positive activation for local settlement at the next microsecond, preserving same-time summation and the existing one-second quiescence interval. It affects death and acceptance of later input and is recorded as a behavioral repair. Historical 6.2 artifacts missing the fields restore with both disabled. The global new-individual version remains 6.1.

Engineering regression passed 478 tests; eleven database integration checks were skipped because the independent test database was not running. Native, standalone Rust and frontend builds passed. The new wheel is installed; running services were not restarted. Six 6.1 implementation files are unchanged. Read-only historical verification confirmed positive task activation throughout 1,502 samples in each of two curriculum blocks for kernels 1 and 2 and the short-inhibition 6.1 condition. The ranges were 0.0171540–0.0230551 and 0.0604104–0.0811919, with no records reaching 0.95. Those persistence findings remain supported.

Only the first 81.2-second teaching stage of the 92-stage R51t10 plan completed. Repeated full-state hashing caused excessive recording overhead; the next waiting stage then hit a 300-second wall-time assertion without complete final-state preservation. This was an instrument error, not a scientific negative or a complete-state pause. STOP, in-flight, failed-branch evidence and the complete teaching state remain intact. The corrected recorder produced identical complete states and records in both backends across four configurations and passed a forced wall-budget test that finishes the stage before pausing. Recovery awaits the author's confirmation under the standing dead-host rule and has not occurred.

Research record `1047029e-d54a-5f2f-8f56-5db7a0503731` is explicitly interrupted. Its 499-member evidence package passed complete API readback with pending=0. This verifies preserved evidence, not completion of the 92-stage scientific targets. The main campaign remains paused and manuscripts are unchanged.

[Report](../../../../lab/explorations/2026-11-14-kernel62/release_lifecycle/report.en.md)

## 2026-11-15: R51t10 completed; genuine persistence and prefix findings retained

The author explicitly authorized a new copy. The complete 81.2-second teaching state was reused and the remaining 91 stages completed. The interrupted wait, STOP, in-flight marker and 499-member interruption originals remain intact. Waiting retained 300 fixed background inputs. The earlier phrase “dead host” meant a recording-timeout process exit, not an individual dying from absent input. The recovery restriction appears in earlier automated continuation prompts; this does not establish a verbatim personal instruction from the author, and the attribution is corrected here.

Configuration calls in the original 20 tails settled nodes and masked stale activity. Eight additional tails were prospectively registered from teaching states whose flags were set at birth, with no reconfiguration or repeated teaching. With the repair disabled, activation was zero at the one-second sample but life remained active at 300 seconds. With it enabled, death occurred at about 1.996 seconds under the original one-second quiescence rule, with an empty active set. No further transmission occurred after the first zero sample in any condition. This comparison confirms the local expiry repair.

With background input retained and inhibition decay time divided by four, all four switch combinations maintained task activity for the 15-second window after 300 seconds in both curriculum blocks. Pointwise maximum activation was 0.0604104–0.0811919, with no 0.95 saturation. Original inhibition passed 0/2 throughout. The successful research configuration retained 2/2 prefix discrimination with repair off or on; all production-default combinations remained 0/2. Across 20 paired processes, the largest difference in four activity fields was 4.34e-19, preserving all prior functional judgments. The repair corrects false survival labels while preserving genuine persistence and successful prefix discrimination; the two switches alone do not restore default prefix capability.

Verification covered 348 main and 60 supplementary complete states, 40 new processes and six historical processes. All 1206 archive members passed complete local research-API readback, pending=0. Research identity 1047029e-d54a-5f2f-8f56-5db7a0503731 and its interruption history are retained. Scientific execution has ended; the comprehensive campaign and manuscripts remain paused. No additional production-kernel or default changes occurred during continuation.

[Report](../../../../lab/explorations/2026-11-14-kernel62/release_lifecycle/completion/report.en.md)


## 2026-11-15: R51t11 restores prefixes and isolates an inhibitory retention effect

The author requested a solution. The batch completed 192 stages. All sixteen four-factor conditions failed, whereas four separate-inhibition routing/weight combinations each passed 2/2 blocks, including current outgoing routing and effective weights. Source inspection then found that inhibition still wrote the connection usage time when explicit inhibitory learning was disabled. That record affects same-time decay exemption and later co-stimulation reinforcement. A prospectively registered comparison changed only that record under normalized inhibition, resource bypass, disabled explicit learning and a zero inhibitory connection threshold: prefix performance changed from 0/2 to 2/2. New codes and birth seeds also passed 2/2. Removing the record alone in the unnormalized current pathway remained 0/2; attribution retains the tested combination.

Persistence with the identical successful configuration was 0/2. None of four earlier complete resource/inhibition-time configurations jointly passed both tasks: 101 with the original time constant recovered prefixes; both 011 settings sustained activity. The study supplies a concrete recovery while separating duration from relational performance. Verification covered 576 states and 118 processes with zero scoring discrepancy. All 1826 members passed complete local API readback, pending=0. Production kernels, defaults, historical evidence and manuscripts are unchanged. The solution is recommended as an optional mechanism; production decisions remain with the author, and comprehensive replication stays paused.

[Report](../../../../lab/explorations/2026-11-14-kernel62/prefix_solution/report.en.md)

## 2026-11-15: R51t12 separates connection states without restoring prefixes

The author requested separate excitatory and inhibitory weights and resources, approved a learning-record comparison and a master switch, and required performance measurements. Explicit child values override the master; unspecified children inherit it. Defaults remain shared, and separate learning records require separate weights. Python, Rust, the standalone runtime, configuration fields, complete snapshots and inheritance support the new states. Historical 6.1 implementations and the global default remain unchanged.

Six preregistered groups were compared under default retention and stability-based retention, with inhibitory learning enabled throughout. Each of two exchanged curriculum blocks received 212.2 seconds of continuous teaching before separate AB and DB diagnostic copies, totaling 72 stages and 48 complete processes. Every configuration passed 0/2 blocks: an ending preference remained instead of correct switching with the prefix. The result rejects the expectation that these separations alone restore this capability. R51t11's successful research configuration remains supported by its original evidence; the conditional fresh-encoding batch was not triggered.

On identical 32-node inputs, the new shared implementation was about 4.6% slower than the previous binary, with identical numerical state and events. Relative to new shared mode, full separation was about 49.3% slower, with 67.1% larger snapshots and 17.0% higher peak process commit. The additional cost is measurable, while this batch found no prefix benefit. Separation is therefore not recommended as a default on this evidence. Optimization in 6.3 remains a proposal, not implemented work.

Independent verification of 144 complete states and 48 processes found zero scoring discrepancy. Engineering validation passed 706 tests; 11 isolated database checks were skipped. Subsequent standalone tests exposed missing optional fields in the tmind decoder, repaired and recorded separately without altering execution-time sources or JSON scientific originals. All 930 archive members were read back through the local research API, with pending=0 and record b6725bdc-406d-5ae8-9981-67e071bc7424 finalized. Historical experiments and manuscripts are unchanged; the main campaign remains paused.

[Report](../../../../lab/explorations/2026-11-14-kernel62/separated_signals/report.en.md)

## 2026-11-15: R51t13 delivers simpler 6.3; prefix recovery was not achieved

The author requested a default-off inhibitory usage-time update switch in 6.2, a new 6.3 without the unsuccessful separation features, and optional weight-proportional inhibitory allocation with per-connection transmission retained as default. Earlier 6.2 artifacts preserve their behavior. 6.3 has independent Python/Rust transitions while sharing generic mathematics and storage. The new switch changes only last transmission time, not inhibitory learning.

R51t13 preregistered two profiles, two allocation rules and usage updates off/on, retaining resources and learning. Continuous teaching preceded diagnostic copies; matching configurations also tested sustained activity. All 72 stages completed. Each of eight prefix conditions passed 0/2 blocks, as did each of four sustained-activity conditions. No fresh-encoding follow-up was triggered. Read-only verification of 144 complete states and 40 processes found zero scoring discrepancy. Prefix capability has therefore not recovered: these changes are insufficient under the tested conditions. R51t11's 2/2 result for its complete combination remains intact and cannot be reassigned to the current defaults.

On identical 32-node inputs and equal numerical states/events, 6.3 was about 5.4% faster than new 6.2. Proportional allocation was about 46.0% slower than default 6.3 without a corresponding capability gain. The recommendation is to retain per-connection transmission and keep proportional allocation optional. The author's no-usage-update default is implemented. Engineering checks passed 631 cases with seven conditional skips; the native wheel is installed, services were not restarted and checked historical 6.0/6.1 files are unchanged. All 929 archive members were read back through the research API, pending=0, and record fd63e416-7e13-5833-ad74-e8681525323b was closed. Broad revalidation remain paused. [Public edition: manuscript editing or private locator omitted.]

[Report](../../../../lab/explorations/2026-11-15-kernel63/report.en.md)

## 2026-11-15: R51t14 implements independent resources without restoring prefix discrimination

The author requested a shared/independent resource option in 6.3 and a prefix test. Only resources were separated: excitation and inhibition have their own available resources, release and recovery state under identical parameters. Weights, retention and learning records remain shared, and inhibitory learning remains enabled. Shared mode remains the default and the interpretation of older 6.3 artifacts without the field. Python, native Rust, the standalone runtime, complete artifacts and the configuration UI support the option.

R51t14 retained R51t13's materials and criteria. Default and stability-retention profiles each compared two inhibitory allocation methods, paired with shared/independent resources. All eight groups passed 0/2 blocks after 48 stages. Independent pools changed transmission and ending preference without restoring the correct response to each prefix. The registered trigger for new-encoding tests was not met, so the batch ended normally without expanding the search. This rejects the expectation that resource separation alone would restore prefixes. The historical 2/2 and current 0/2 results retain their actual configurations.

All 96 complete states and 32 processes were verified with zero scoring difference; 48 shared boundaries matched the previous batch numerically. In the 32-node benchmark, the added option increased shared-mode median time by about 1.2%; independent and new shared modes differed by less than 0.2%. Independent resources increased state size by about 20.1% and peak commit by about 5%. Shared operation therefore remains the default. There were 692 passing checks and seven environment-dependent skips. All 790 archive members were read back through the local API with zero pending requests; record f954be8d-6e00-56e1-bb72-ef86d4502e94 was finalized. The broader campaign and manuscripts remain paused, and previous data are unchanged.

[Report](../../../../lab/explorations/2026-11-15-kernel63/resources/report.en.md)

## 2026-11-15: R51t15 reproduces prefixes and separates resource and inhibitory-learning effects

The author said, “I never said shared resources were the sole cause” (translation), and requested a comparison combining independent resources with disabled inhibitory usage-time updates, together with an explanation of the earlier 6.2 recovery. Assigning the sole-cause claim to the author was inaccurate. Separate bilingual corrections were attached to R51t14 and read back from its original record; historical text, scores and originals remain intact.

R51t15 first reproduced the historical emitter on a 6.3 base, then used the current emitter with equivalent interventions. Both passed the two exchanged-ending blocks, with AB and DB process scores exactly matching R51t11. Restoring only inhibitory transmission-time updates produced 0/2, reproducing the earlier conditional causal result. The historical success was real and the criterion did not change.

The complete comparison shows that the old positive condition bypassed inhibitory resource constraints and disabled explicit inhibitory learning. Independent pools retain their own release, depletion and recovery. In the 12 resource × learning × threshold conditions, all shared and independent groups passed 0/2. Resource bypass with learning disabled passed 2/2 at thresholds 0 and 0.0004; restoring learning produced 0/2 at both thresholds. A zero threshold was therefore unnecessary here, and explicit learning has effects beyond transmission time.

Starting from the successful combination, individual inhibitory contributions were restored. Shared base weight, stability, and touch-count/latest-touch records each produced 0/2. Short-term enhancement and eligibility each retained 2/2. Retention-timescale growth was disabled in the base configuration and served only as a consistency check. Code identifies distinct paths: inhibitory reinforcement of a shared weight also strengthens later excitation; stability reduces decay of that shared connection; touch counts participate in later co-stimulation-driven stability growth. These interventions locate contributions sufficient to disrupt the working combination. Assigning the full benefit of disabled explicit learning to the usage-time field was incomplete.

The successful condition retaining threshold 0.0004 and its control restoring only explicit learning reproduced at 2/2 and 0/2 with new codes and birth seeds. Independent recalculation of 264 complete states and 88 processes found zero scoring discrepancy. Twelve boundaries each were compared against the historical and recent controls. Projecting differently stored lazy short-term traces to the same internal time left a maximum numerical discrepancy of 5.69e-14. All 1293 archive members passed API readback, pending=0, and record f5f5c28c-bcbd-590b-8a4a-8be49e30e6b7 was finalized. The study used an isolated 6.3 derivative, without changing production Python/Rust or defaults; production choices remain with the author.

[Report](../../../../lab/explorations/2026-11-15-kernel63/prefix_causes/report.en.md)

## 2026-11-15: R51t16 implements inhibitory bypass and tests prefixes and sustained activity

The author explicitly requested default-on inhibitory resource bypass in 6.3 and removal of optional independent resources only if retaining the disabled option materially reduced performance. Bypass takes precedence over independent resources; excitation, allocation, energy, thresholds and learning retain their separate settings. Other defaults remain unchanged. Earlier 6.3 snapshots lacking the field retain resource-limited inhibition. Hashes of 19 implementation files for 6.0–6.2 were unchanged; running services were not restarted.

The study retained two exchanged teaching blocks and the historical process criteria. Actual defaults P, the earlier prefix profile S101, and an alternate resource profile S011 each compared bypass on/off on both tasks. S101 with bypass produced AB/DB margins of 0.000974463734 and 0.002693525721; all four scores exactly matched the originals. Without bypass, both prefixes favored one ending and both blocks failed. P with bypass still scored 0/2, distinct from success under the complete profile.

S011 jointly disables depletion and enables 1-second facilitation relative to S101. With bypass either on or off, sustained activity after 300 seconds passed 2/2, while prefixes remained 0/2. With bypass on, maximum task activation stayed between 0.017154 and 0.023055 in the subsequent 15-second window, with no saturated node samples. All 3001 waiting samples at 100 ms intervals retained task activity. The original 300 background inputs remained; the condition was not described as having no external input. These results establish the tested configuration tradeoff; the two jointly changed resource settings were not assigned separate causal contributions.

Matched-state benchmarks compared the pre-independent-resource implementation plus identical bypass against the current implementation with independent resources disabled. Across eight conditions, numerical states and event counts matched; elapsed-time differences ranged from −0.3% to +2.5%, peak commit differed by at most about 1.2%, and snapshots added 76 bytes of configuration metadata. No condition met the 20% repeat threshold, so independent resources remain optional. Separately, enabling bypass changed per-connection runtime from 0.898 to 12.126 seconds in a dense benchmark with 128 nodes and 16,256 connections. Subsequent large-task budgets must account for this measured cost; bypass remains default on as authorized.

All 72 stages completed normally. Verification covered 144 states and 36 processes with zero score discrepancy; 263 engineering checks passed. All 946 archive members were read back and record 8f0bca42-147f-54d5-a0fe-0fc9299ce0c0 closed with pending=0. Completed stages will not be rerun; broad revalidation and manuscript changes remain paused.

[Report](../../../../lab/explorations/2026-11-15-kernel63/resource_bypass/report.en.md)

## 2026-11-15: 6.3 restores three 6.1 defaults and retains local expiry

The author requested the 6.1 resource and usage-record behavior in 6.3, then explicitly retained local subthreshold expiry. Delivered defaults disable resource prechecking and inhibitory resource bypass, and enable inhibitory transmission-time updates; independent resources remain off and expiry remains on. Under the final expiry setting, prechecking reduced time by 8.40%, below the preregistered 20% threshold. Final 6.3 defaults changed time relative to 6.1 by −1.78% to +7.10% across four materials. The expiry-disabled compatibility configuration passed 72 boundary comparisons and all 24 paired benchmark final states. Actual defaults retain the behavioral difference in timely active-set settlement; the original zeroing floor and one-second quiet period remain. There were 654 distinct passing engineering tests; two database checks were skipped because the isolated test database was not running. Ten pre-edit 6.3 states and 19 historical implementation files remain unchanged. Python/Rust, standalone runtime and configuration catalogue are synchronized; the native module is installed, services were not restarted, and the application default remains 6.1. Historical scientific scores are preserved; broad revalidation remain paused. [Public edition: manuscript editing or private locator omitted.]

[Report](../../../../lab/explorations/2026-11-15-kernel63/default_alignment/report.en.md)

## 2026-11-15: performance audit locates weak-input maintenance costs

The author requested a brief 6.3–6.1 performance comparison and investigation of material slowdowns. Actual birth defaults were tested against a preregistered 10% time-increase scale. Ordinary Rust workloads increased 2.97%–3.18% and Python 6.15%. Weak-input Rust increased 33.49% in pooled measurements but lacked separate-phase confirmation precision; both Python phases confirmed an increase, pooled at 78.77%. Additional switch controls attributed costs to timely settlement and node recreation after deletion. Rust weak-input final nodes fell from 129 to one, reducing snapshot size 86.28%. The fix therefore adds work while enabling existing cleanup. Retaining the fix and optimizing local maintenance without changing behavior was recommended, not implemented. All 235 final states were verified; kernels and defaults are unchanged and the main campaign remains paused.

[Report](../../../../lab/explorations/2026-11-15-kernel63/performance_comparison/report.en.md)

## 2026-11-15: continuation on 6.3 authorized; targeted revalidation scope awaits a decision

The author now authorizes continuing the original campaign on 6.3, but requests a decision before repeating completed 6.1 experiments. Review recommends targeted checks because timely settlement has changed weak-input node cleanup; compatibility-state equality alone does not establish every scientific result under actual defaults. Proposed checks retain original small scales: stimulus formation, connection causation and transfer, eight-group criteria, and key delay/order conditions; the eight-source fixed-readout check precedes M5 confirmation. The 64-group criteria confirmation, 48-source transfer confirmation and historical diagnoses are not repeated wholesale. This records a proposal and authorization boundary, not an approved rerun; no new scientific subject has started.

[Review](../../../../lab/explorations/2026-11-15-kernel63/revalidation-resume-review.en.md)

## 2026-11-15: endpoint reclamation can remove dormant edges before their own expiry

Source inspection confirms explicit dormancy is off by default in 6.1/6.3 and ordinary/dormant edge thresholds remain 0.008/1e−8. When dormancy is enabled, endpoint reclamation can remove edges above their dormant threshold; this is an existing rule, with frequency not yet measured. The 129-to-one-node stress workload had no connections and is not dormant-lifetime evidence. Separating edge expiry from endpoint reclamation is recommended for the pending checks; no experiment or mechanism change was made.

[Review](../../../../lab/explorations/2026-11-15-kernel63/revalidation-resume-review.en.md)

## 2026-11-15: Author approved a complete 6.3 rerun; R63a started

The author explicitly requested every experiment in plan v2 and the additional mechanism studies from revalidation. This replaces the pending selective-rerun proposal; historical proposals, reports and originals remain intact. New 6.3 subjects retain the original sample sizes, controls and criteria. Common defaults match 6.1, with timely weak-activation settlement retained; no production dynamics or global version default changed. The 135 engineering tests and 12 addressing/in-flight checks passed. R63a was registered through the API and launched once; its 264 conditions are still running, with no scientific outcome declared. Initial E-drive free space was 58.85 GiB. Each batch requires a complete budget; new adverse contradictions or serious slowdowns trigger preservation and discussion.

[Coverage](../../../../lab/explorations/2026-11-15-kernel63-revalidation/coverage.en.md)

## 2026-11-15: R63a completed; proceeding to R63b connection causality

All 264 conditions, 528 initial/final states and 180 parent–copy links passed verification. Grouped connection formation passed 4/4 combinations, order affected weights in 8/8 comparisons, and repetition increased weights. All 96 weak edges per combination survived 120 seconds, so the short-term deletion target remains unmet as in 6.1. Seventy-four old active labels became dead; old actual activation after those death times was zero, and shared-time activation was identical. All 318 direct-history differences concern removed nodes. Convergence remains 48/100 in the same conditions; four untrained cart conditions are explicitly censored by death. All 1923 archive members were read back through the API, pending=0. Recorded scientific time was 182.33 seconds and guarded host time 324.58 seconds. No new adverse contradiction or major slowdown occurred.

R63b retains 8 origins, 16 teaching references and 80 causal copies. Do not rerun R63a. E18 bodily-experience tools are prepared and await completion of the preceding batch. All original and additional studies remain in scope; the paper is unchanged.

## 2026-11-15: R63b completed; R63c bodily experience is running

R63b created 8 independent 6.3 origins, 16 opposite-teaching histories and 80 causal research copies. All 8 origins passed: target blockade removed 100% of the history-dependent response difference; matched blockade removed 0%. Sham and immediately restored conditions exactly matched the intact state and recorded process. Audits verified 192 complete states, parent continuity and independent arithmetic for 80 trajectories. Primary and auxiliary measurements match R51e. Runtime was 49.61 s, peak private memory 79.02 MiB and allocated originals 22.23 MiB. All 343 archive members were read back through the research API, with pending=0 and no new adverse contradiction or performance stop.

R63c was independently registered. Sixteen calibration conditions selected intensity 0.3 by the frozen rule. Its 616 formal stages across 4 material blocks are running serially, measuring bodily-experience responses after 1, 60 and 300 s and their connection dependence. No R63c conclusion is declared yet. R63d eight-group comparison tools are prepared but have not started. Historical evidence, Core and the paper remain unchanged.

Evidence: [R63b report](../../../../lab/explorations/2026-11-15-kernel63-revalidation/causal/report.en.md), [API receipt](../../../../lab/explorations/2026-11-15-kernel63-revalidation/causal/delivery.json), [campaign coverage](../../../../lab/explorations/2026-11-15-kernel63-revalidation/coverage.en.md).


## 2026-11-15: R63c bodily-experience replication completed; R63d registered

R63c completed 616 formal stages across 4 material blocks, with 16 separate calibration conditions. Trained process responses passed 192/192 and untrained references 0/48. After 300 s, target blockade retained 0/32 responses, versus 32/32 after matched blockade and immediate restoration. Restored complete states and processes equal the intact references. Native convergence-time readout remains 0/240, reported separately. Audits verified 1,264 complete states and independently recomputed 336 probes. All 632 conditions match 6.1 in classification, sampling and lifecycle; the largest four-field trajectory difference is 2.78e-17. Formal host time was 34.82 min, peak private memory 947.29 MiB and allocated originals 258.91 MiB. All 4,497 archive members passed API readback, pending=0, with no new adverse contradiction or performance stop.

R63d is independently registered: 8 origins, 5 implementations and 40 system units. Apparatus validation precedes formal computation. The 64-origin confirmation and all remaining original and additional studies remain in scope. Only R63a through R63c are closed; the complete campaign is not finished.

Evidence: [R63c report](../../../../lab/explorations/2026-11-15-kernel63-revalidation/body_memory/report.en.md), [API receipt](../../../../lab/explorations/2026-11-15-kernel63-revalidation/body_memory/delivery.json), [coverage](../../../../lab/explorations/2026-11-15-kernel63-revalidation/coverage.en.md).


## 2026-11-16: R63d eight-group joint-criteria replication completed

After interruption, inspection confirmed that all 40 systems had finished the preceding day, with no STOP or orphaned in-flight state. Read-only verification resumed without recomputing subjects. ThreeMind passed each criterion and their conjunction in 8/8 origins; every control had 0/8 joint passes. Recurrent-network temporal interaction passed 5/8. All 750 numerical scientific-summary fields match historical 6.1 exactly. Audits verified 4,240 complete states, 2,560 probes, 160 feedback-replay groups and 16 numerical recurrent-network teaching replays. Computation took 406.38 s, peak private memory was 565.51 MiB and allocated originals 175.68 MiB. All 4,933 archive members passed API readback, pending=0. No new adverse contradiction or marked slowdown occurred. R63e proceeds with 64 new confirmation origins.

Evidence: [R63d report](../../../../lab/explorations/2026-11-15-kernel63-revalidation/criteria/report.en.md), [API receipt](../../../../lab/explorations/2026-11-15-kernel63-revalidation/criteria/delivery.json), [complete coverage](../../../../lab/explorations/2026-11-15-kernel63-revalidation/coverage.en.md).



Preparation note, 16 November 2026: R63e computation continued while the full R63t1 protocol and tools were prepared. All 476 historical stages, two curriculum blocks and 26 configurations are retained; historical decisions and 22 stored processes passed recalculation. This batch has not been registered or instantiated. A separate read-only input audit corrected comparison of an omitted default-false field, without changing stimuli or Core. See the [preparation record](../../../../lab/explorations/2026-11-15-kernel63-revalidation/persistent_cause/preparation.en.md).


Method correction, 16 November 2026: frozen code and delivered R51t3 inputs confirm that online dose matching retains all sensory components and scales their total to the joint-only total. The revised report instead described removing inertial components and increasing the remainder. A [dated correction](../../../../lab/explorations/2026-11-13-kernel61/dynamics_function/body_report/errata-20261116.en.md) was appended to the original research record in both languages and read back, pending=0. Historical directories, reports and the original package were neither written nor replaced; numerical findings and conclusions remain unchanged. The original-scale 110-stage R63t2 protocol is separately prepared, not registered or executed.


2026-11-16: The 296-stage R63t3 body tools are also prepared; posture errors from six historical trajectories reproduce exactly. Neither batch is registered or executed.


Preparation update, 16 November 2026: R63t4 delayed choice retains four material blocks, 64 systems and 1,536 phases. All historical curricula and scores pass verification; independent integration of 42 saved questions differs by at most 6.94×10⁻¹⁸. Protocol and tools are prepared, without registration or new subject creation.


2026-11-16: R63t5 prefix-factor tools are also prepared. The genuine 3.1/5.1 matrices remain, with four corresponding 6.3 conditions using existing retention and novelty options. There are still two blocks and only 12 additional 6.3 execution stages; manual node retention is not reintroduced. Historical condition and positive-process scores pass verification. Registration and execution remain pending.


## 2026-11-16: R63e 64-group autonomous-activity confirmation completed

All 64 ThreeMind 6.3 origins satisfy the four autonomous-activity criteria; each control has 0/64 joint passes. Recurrent-network temporal interaction passes in 49/64 origins, above the original 48/64 criterion threshold. Each paired joint-rate advantage is 100 percentage points, with Holm-adjusted P=4.3368×10⁻¹⁹. Verification covers 33,920 complete states, 20,480 probes, 1,280 feedback-replay groups and 128 recurrent-network teaching histories. All 9,097 scientific summary values match 6.1 exactly. Computation took 92.19 min and peaked at 650.55 MiB private memory, without marked slowdown. All 38,854 archive members passed complete research-API readback, pending=0. The batch confirms that 6.3 retains the joint capacity for experience-organized autonomous activity. No new scientific stop was triggered; R63f bodily transfer follows. [Public edition: manuscript editing instructions omitted.]

[R63e report](../../../../lab/explorations/2026-11-15-kernel63-revalidation/criteria_confirmation/report.en.md) · [API](../../../../lab/explorations/2026-11-15-kernel63-revalidation/criteria_confirmation/delivery.json) · [coverage](../../../../lab/explorations/2026-11-15-kernel63-revalidation/coverage.en.md)


## 2026-11-16: R63f bodily-transfer replication completed

All 192 taught process tests retain the taught direction; all 48 untaught tests are undirected, across original angle, changed angle and changed gravity. Target readout at native convergence remains 0/240 and historical inertial reversal remains absent, both matching 6.1. Verification covers 560 new states, 40 complete parents and 240 trajectory pairs. Independent integral error is at most 6.94×10⁻¹⁸; 9,120 numerical fields differ from 6.1 by at most 4.34×10⁻¹⁹, with identical classifications. Computation took 307.14 s, peak private memory was 626.93 MiB and allocated originals occupied 66.63 MiB. Expression of bodily experience across physical settings is replicated, without a new adverse contradiction. The eight-origin connection-transfer study follows. All 2,307 archive members passed complete API readback, pending=0.

[R63f](../../../../lab/explorations/2026-11-15-kernel63-revalidation/body_transfer/report.en.md) · [API](../../../../lab/explorations/2026-11-15-kernel63-revalidation/body_transfer/delivery.json) · [coverage](../../../../lab/explorations/2026-11-15-kernel63-revalidation/coverage.en.md)


## 2026-11-16: R63g eight-origin connection transfer completed

All eight origins pass the primary transfer criteria. Complete and persistent target packages transfer all 48 target choices to the donor relation while preserving all 48 unrelated responses. Matched transplantation changes the other relation, and immediate restoration restores complete state and responses. All 16 fast-state exchanges are zero-change controls, reported as 0/8 passes. Actual edge-content changes affect only destinations, further localizing transfer to connectivity. Independent verification covers 816 states and 672 probes; all 157 scientific summary values match 6.1 exactly. Computation took 149.83 s, peak private memory was 550.75 MiB and allocated originals occupied 14.72 MiB. No new stop was triggered; fixed process-readout testing follows. All 1,018 archive members passed complete API readback, pending=0.

[R63g](../../../../lab/explorations/2026-11-15-kernel63-revalidation/transfer/report.en.md) · [API](../../../../lab/explorations/2026-11-15-kernel63-revalidation/transfer/delivery.json) · [coverage](../../../../lab/explorations/2026-11-15-kernel63-revalidation/coverage.en.md)


## 2026-11-16: R63u retention, retrieval and relearning measurement prepared

Read-only arithmetic checks of the original X2 study cover 32 origins and 256 diagnostic processes, reproducing the original cue-dependence and transient-expression decisions. Taught and untaught individuals all reached the minimum two rounds, so those results cannot resolve savings in teaching. The new protocol retains the retention tests and pairs two existing 6.3 retention configurations. Independent materials calibrate a process-response criterion before formal relearning, with a 16-round limit; failed calibration is reported as unavailable measurement. Stored, sleeping and graph-visible connections are counted separately. Only protocol and tools are prepared: no registration or subject creation, pending R63q. Core, old originals and old criteria remain unchanged.

[R63u](../../../../lab/explorations/2026-11-15-kernel63-revalidation/retention_relearning/preparation.en.md) · [protocol](../../../../lab/explorations/2026-11-15-kernel63-revalidation/retention_relearning/protocol.en.md)


## 2026-11-16: read-only development of the 6.3 first-response formula

A calculation derived from existing 6.3 rules agrees with all 64 first-response directions in the completed R63g records; maximum amplitude error is 1.7347×10⁻¹⁸. This is retrospective development, not a new prospective prediction result. The tool neither creates a Core nor changes state. M2 still needs a complete intervention and independent-material protocol before registration and execution.

[development](../../../../lab/explorations/2026-11-15-kernel63-revalidation/resource_prediction/development.en.md)


## 2026-11-16: R63h fixed-readout replication completed; continuation paused at author request

All eight origins pass fixed expression and causal attribution with the 110-ms output-port reader. The primary temporal condition passes 4/8 and 0/8 respectively, below the registered 6/8 threshold. Endpoint new answers score 56/64; plasticity-off teaching or new-connection blocking gives 0/64 while preserving all 64 old answers. Restoration is exact. Audits verify 2,024 complete states and 1,824 answers. Scientific categories match 6.1, with maximum numerical difference 0. Computation took 3075.83 s and peak private memory was 863.49 MiB. No new adverse contradiction occurred. Core learning expressed through a fixed reader is replicated, along with the known limitation of this temporal-readout design. At the author's request, the campaign pauses after delivery . [Public edition: manuscript editing or private locator omitted.] R63i and subsequent studies have not started. All 2,131 archive members passed complete API readback, pending=0.

[R63h](../../../../lab/explorations/2026-11-15-kernel63-revalidation/fixed_readout/report.en.md) · [API](../../../../lab/explorations/2026-11-15-kernel63-revalidation/fixed_readout/delivery.json) · [coverage](../../../../lab/explorations/2026-11-15-kernel63-revalidation/coverage.en.md)
