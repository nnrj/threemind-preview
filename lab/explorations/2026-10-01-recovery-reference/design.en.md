# Sensory state, maintenance timing and shared references: preregistration

[中文](design.zh.md)

2026-10-01, E22 follows E21. The user requested continued planned experimentation. Keep continuous-memory/2, product defaults and intensity_gain=0.075; do not search for replacements, alter Core dynamics or old evidence, or recertify autonomy-criteria/1. Use a separate database project.

## A Sensory reversal: persistent fields versus ongoing state

Use 16 E21 pre-probe images: blocks 930101–930104, full/no_imu, learning competition on, learning depletion off/on. All images are one second after teaching, already reconfigured through the original public interface to expression depletion and competition on. Preserve hot-switch semantics; this is not equivalent to being enabled since birth. Sources are test11/sign1/physical1 pre-probe images. Reuse E18/E21 physical inputs, intensity 0.3 and 5.6-second observation.

Images contain in-flight events and traversed edges. Retain strict state_exchange/1 unchanged. New research-state-exchange-cut/1 exchanges only W (edge weights), S (edge stability, eligibility and touch history), N (node support, stability, plasticity and touch history). Align anonymous channels and directed pairs. Retain all receiver identities, activity, inhibition, short-term resources, fast traces, in-flight signals, traversed sets, clocks and counters exactly. Never withdraw sent signals or redirect them to new identities. Require equal configurations, time, lifecycle, channel sets and topology and no pending novelty; otherwise stop rather than fabricate compatibility.

Exchange all eight W/S/N subsets with opposite-learning-depletion donors, in both recipient directions. Probe each state with both physical directions and their matched no-physical controls: 512 cases. Sham interventions must exactly reproduce E21. These are artificial research interventions, not natural learning or inheritance. Failure of all persistent fields to transfer direction does not identify any single fast mechanism; it establishes insufficiency of this bundle in that state.

From the same 16 images, also advance naturally for another 9/29/59 seconds: 10/30/60 seconds after teaching. Preserve maintenance, forgetting, propagation and learning. Each holding state has two physical directions and matched controls: 48 holding plus 192 probe cases, total 240. Time changes forgetting and repropagation as well as resources, so waiting alone cannot isolate resource recovery.

## B Separate teaching phase from maintenance phase

Blocks 100121–100124; 12 AX/BX pairs, 50 ms within pairs, 2.5-second pair period, intensity 0.4, AB/BA. Cross teaching offsets 0/40/60 ms with training-maintenance offsets 0/40/60 ms and facilitation 0/1 s. The first K=0.2 is always at zero; subsequent K starts at 0.5 s plus the offset, recurring every 0.5 s, with equal counts. Common Y=0.2 at32.2 s; thereafter all maintenance returns to the same 0.5-second grid. Probe X=0.5 or none after30 s, observing5 s: 144 teaching plus288 probes =432. Save state before/after teaching and propagation clocks. Maintenance-phase interactions implicate relative input timing; absence of interaction does not by itself isolate the propagation clock. The48 teaching and96 probe cases with K offset0 must reproduce corresponding E21 cases exactly.

Dense jitter control: 12 pairs at550 ms periods, fixed40 ms offset versus per-pair jitter drawn before execution using seed22001, integer milliseconds from-40 to+40, added to40 ms. Both frames of each pair move together, retaining50 ms separation. Four blocks, two orders, facilitation off, normal K; common Y at7 s, probe after30 s. 16 teaching plus32 probes =48. Never select a jitter schedule from its response.

## C Match individual channel exposures as well as total dose

Four blocks, facilitation off. Twelve rounds of four intact groups. Shared: AX,BX,CZ,DZ. Separate: AX,BZ,CZ,DX. Each round exposes A/B/C/D once and X/Z twice; all frames contain two elements at0.4. Thus channel counts and doses match exactly. AB/BA reverses the first two object presentations, keeping references attached to their object rule; C/D order fixed. Frame slots match.

Dense rounds:1.1 s, slots0/50/550/600 ms; sparse rounds:5 s, slots0/50/2500/2550 ms. Common final Y=0.2 at13.2/60 s respectively; K=0.2 every0.5 s. After1/30 s probe none, X=0.5, Z=0.5 or X/Z each0.25 (same total0.5), observe5 s. 32 teaching plus256 probes =288. C/D are declared balancing inputs, not semantic instructions.

Topology and exact reference timestamps remain treatment differences. X connects both targets in shared teaching but A/D in separate teaching. A single X-induced A-B difference is not order discrimination without bidirectional reversal. The combined equal-dose XZ cue is reported separately since it can alter competition. Do not presuppose that a shared reference is necessary.

## Analysis, verification and bounds

Use E21's process integral minus a matched uncued sibling, then target contrast; order must reverse with AB/BA. Threshold1e-6 activation·s with1e-9 sensitivity. Do not score original sensory direction as inherently better. Store complete node/edge trajectories at20 ms and retain terminal, peak, raw temporal windows and convergence-decision values. Process positives do not rewrite terminal zeros. Four blocks vary anonymous identities, not independent ecological populations.

Registered1520 cases: cut512, recovery240, timing432, jitter48, reference288. Safety ceiling2048, one worker,4 h aggregate case wall time,300 s/case,4 GiB process;6 GiB stop simulations,8 GiB hard including archive; reserve RAM2 GiB,C5 GiB,E15 GiB. Verified account baseline88%;+3 percentage points stop starting later batches,+5 stop new simulations, counting shared usage; refresh within30 min. Deliver partial results if stopped without relaxing checks.

Freeze sources, design and schedules. Audit every input, DB/file state hashes, exact historical cases and observer-disabled replays. Test the new tool in Python/Rust, all subsets, sham and identity exchanges, channel alignment, in-flight preservation and rejection. Publish bilingual reports, notebooks, original readout records and evidence archive to the dedicated project; update history and local Git only.
