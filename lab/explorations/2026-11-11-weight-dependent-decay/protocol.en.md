# R48a: local tests of weight-dependent decay

2026-11-11, preregistered version 1. [中文](protocol.zh.md) · [Whole-system protocol](joint/protocol.en.md)

The user explicitly authorized testing the proposed rule that stronger weights decay more slowly in relative terms. We test dw/dt=−w[λmin+λextra(1−w)], its implementation, the balance between rapid loss of weak experience and retention of repeated/strong/novel experience, and comparison with exponential decay matched at a weak weight.

The isolated identity is `threemind.experimental-weight-decay/1`, implemented in Python in this research directory. Only persistent connection-weight decay differs between arms. Node support uses /5.3 inverse-logarithmic decay with H=30 internal seconds in every arm. Reception, activation, inhibition, synaptic resources, reinforcement, novelty, transmission, and event order remain /5.3. Retention-scale growth and relaxation are off. Reinforcement retains age and adds to the same current weight. Candidate decay does not use the age retained in the existing state format. Production kernels, defaults, old subjects, evidence and manuscripts are unchanged. Unlike R47, node decay is controlled rather than changed together with edge decay. All arms use the same Python backend.

## Fixed parameters and controls

λmin=ln(2)/86400 internal s⁻¹. The two predefined extra rates are 0.06 (fast) and 0.012 (slow) internal s⁻¹. The one-day quantity calibrates a minimum instantaneous fractional rate, not the lifetime of a connection. No parameters are selected using the new scientific results.

| Arm | Connection rule | Purpose |
| --- | --- | --- |
| inverse-logarithmic | Existing /5.3 rule, H=30 | Retention reference |
| weight-fast | Candidate, extra rate 0.06 | Rapid weak-experience forgetting |
| weight-slow | Candidate, extra rate 0.012 | Retention at 300 s |
| matched-fast | Exponential rate λmin+0.06(1−0.035) | Matched fractional rate at weak weight 0.035 |
| matched-slow | Exponential rate λmin+0.012(1−0.035) | Corresponding slow control |

The matching weight 0.035 comes from the current initial edge weight. With α=λmin+λextra, β=λextra and z=exp(−αΔt), exact update is w'=αwz/[α(1−w)+λmin w+βwz]. This avoids cancellation near w=1 and needs neither contribution histories nor numerical integration. A positive minimum rate ensures decay without reinforcement even at full weight. As weight decreases, its fractional loss accelerates; consequently the desired separation of timescales may fail despite the intended local property. Analytic lifetimes and engineering costs are reported separately from cultivation.

## Independent sources and continuous experience

Eight new sources use seeds 261111810–261111817. Each source has five arms and four courses. Weak experience is probed at 1 and 30 s; spaced, strong and novel experience at 1 and 300 s. Each time has independent continuously raised cohorts, with opposite paired histories and cue/no-cue conditions, all born separately. There are 1280 sequences but independent N=8. There is no per-question checkpoint restoration.

The validated R47 four-channel apparatus is reused: background, cue and two output ports. Background amplitude 0.2 arrives every 0.5 s and must not form task connections. Within each source, randomized mappings, amplitude scale 0.85–1.15, phase and novelty interval are paired and frozen. Weak experience is one amplitude-0.08 pair at 127 s. Spaced experience uses amplitude 0.4 at 16,17,19,23,31,47,79,127 s. Strong experience uses amplitude 0.4 and declared intensity 2 at 127 s. These courses end at 128 s. Novelty presents the other pairing and then the target pairing after 50 or 75 ms; that course ends at 1 s. All actual inputs and complete states are saved.

Each cohort receives only its specified first probe. One second before and after probe contains 20 frames of activation, inhibition, direct and associative activity. Cue amplitude is 0.8; the matched no-cue cohort receives no extra input. Analysis subtracts spontaneous change using the no-cue condition and compares whole response trajectories across opposite histories. Raw data remain unchanged. This is a fixed temporal instrument for mechanism measurement, not a trained action or language system. R48b separately includes personal Transformers, corrective teaching, spaced review and actuator feedback.

## Targets and conclusions

Each target requires at least 6/8 sources; Wilson 95% intervals are reported. W: both directed target edges must have formed during teaching and be absent at 30 s in both histories. S: both directed target edges survive at 300 s in both histories, separately for spaced/strong/novel courses. E: the history-difference RMS is >10⁻⁴ at both 1 and 300 s, late RMS is at least 10% of early RMS, and trajectory cosine is ≥0.8, separately by course. F: analytic projection from the actual 300-s state with no further reinforcement puts all target weights below 0.008 after 30 days, separately by course.

F is a conditional analytic endpoint, not 30-day cultivation. Actual autonomous reinforcement may alter survival and is recorded. All W/S/E/F must pass for the local combined objective. Failure to form edges cannot count as forgetting; undetectable early expression fails E with the precise reason retained, without changing denominators.

Paired weights and history-response RMS compare candidate and matched exponential arms. These are exploratory comparisons, not confirmatory parameter selection. The report states winners and failures by declared dimension. A candidate advantage over its matched exponential without the desired forgetting/retention balance is explicitly a partial benefit and a failed combined target. Negative results end this bounded study without expanding a search until success.

## Verification, resources and delivery

Engineering checks cover exact-flow boundaries, composition, numerical derivatives, relative-rate ordering, exponential reduction, identity isolation, nonperturbing observation, advance partitioning, complete restoration and the next input. The inverse-log control must reproduce original /5.3 reference dynamics field by field. Engineering seeds 987654xx are excluded.

Register and read back both protocols through the existing research API before running. One scientific host at a time; one-second guard preserves 5/4/5/25 GiB of commit/RAM/C/E, with ≥8 GiB startup commit margin. Limits: 3 GiB originals, 1 GiB private memory and two host hours. Pause only at complete operations. New death, orphan in-flight state, broken evidence or answer leakage stops the batch with originals intact. Old paused experiments and automations remain paused.

Independent arithmetic checks every original hash, state chain, time and score. Bilingual reports explicitly answer the scientific questions and their consequences for ThreeMind. Full originals and texts must be read back through the API with pending=0. R48b follows with its unchanged preregistered course regardless of this study's sign. Default changes remain a separate user decision.
