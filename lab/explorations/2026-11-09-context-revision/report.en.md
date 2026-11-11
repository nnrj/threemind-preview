# Context judgments, evidence revision, and active observation: first experiment

9 November 2026, R43, first edition. Eight independently initialized individuals, using the genuine native `continuous-memory/5.1` implementation. This report describes completed experiments. [中文](report.zh.md) · [Prospective protocol](protocol.en.md) · [Delivery verification](delivery.md)

**The experiment gives separate, explicit answers. The system can produce a joint answer consistent with the current context after receiving new discriminating evidence. This curriculum did not establish stable joint judgments organized by opposite teaching histories or selective active observation. Silencing the designated forward connections changed internal activity without reducing joint accuracy. G2 passed in 8/8 individuals; G1, G3, and G4 each passed in 0/8.**

## Purpose, apparatus, and expectations

The task uses two discrete contexts. The same cue X0 is associated with category 0 under one teaching history and category 1 under the opposite history. An individual predicts a subsequent sound category and visual category and chooses an exit. All three outputs must be correct for a joint success. Sound and vision are event categories represented by anonymous channels. A later discriminating cue, D0 or D1, can conflict with the earlier cue. For a mixture of X0 and X1, the individual must decide whether to inspect the environment; the environment supplies discriminating information only after an actual inspect action.

The expectations were that experience would organize coherent judgments, new evidence would revise them, inspection would improve choices, and relevant local connections would carry these behavioral effects. Each goal has its own verdict. Each independent individual first develops a complete personal interface and then yields two complete copies with opposite teaching histories. Each history has seven conditions: intact, sham, target silence, matched silence, immediate restoration, blocked inspection feedback, and forced discriminating information. The experiment contains 112 continuous final-test sequences and 2,688 questions. Independent N is eight; copies and questions are nested observations.

## Formal output always used a temporal process

Three personal Transformer output adapters produce sound predictions, visual predictions, and actions. They reuse the existing temporal-adapter implementation: 48 dimensions, one layer, four attention heads, a 96-dimensional feedforward layer, and zero dropout.

Each answer records 20 frames over one second at 50-ms intervals. Every frame contains **activation, inhibition, direct reach, and associative reach** at the declared output ports. The adapters consume frames 0, 3, 5, 8, 11, 14, 16, and 19, with positional encoding preserving their order. Changes in duration and timing are represented by this ordered sequence; exact onset and duration are not separately calculated features. All 20 frames remain in the originals. Formal actions were never chosen from a single activation snapshot or the brightest port.

Core and personal adapters first develop together on old interface materials. Adapter fitting uses AdamW with 1,200 updates per round and preserves parameters, optimizer, random state, and all previous samples. All eight individuals reached 10/10 in their first interface-development test. The three adapters were then fixed under the registered attribution design while Core received new teaching.

Initial teaching has eight dense cycles followed by one review cycle after each additional wait of 2, 6, and 18 internal seconds. These are waits before whole review cycles; actual item intervals also depend on lesson order and the 1.5-second lessons, with every event retained. Both histories completed two corrective rounds and their reviews, giving 48 new-teaching stages. Correction first asks the missed question again, then provides original and altered-dose demonstrations and reviews old materials. Ordinary questions and each final-test sequence preserve the complete continuous state, without per-question restoration.

## Results and scientific conclusions

An individual must satisfy a goal under both histories, and at least 6/8 individuals must qualify for a batch pass. G1 additionally requires all three outputs to change with opposite histories on at least 50% of identical-cue comparisons. Every interface and intervention match passed its preregistered validity checks.

| Goal | Preregistered requirement, abbreviated | Actual result | Scientific conclusion |
| --- | --- | --- | --- |
| G1: history-organized joint judgments | First-window joint accuracy on new single cues ≥75%, plus the history-change requirement | 40/128 joint correct; all three outputs changed in 1/64 paired cues; 0/8 qualify | This curriculum did not establish stable history-dependent joint judgments |
| G2: revision with new evidence | Joint conflict accuracy after evidence ≥75%, with a gain ≥50 percentage points over first-window agreement with the actual context | 4/64→62/64, or 6.25%→96.875%; 8/8 qualify | The system can revise its joint answer to fit the current context after a discriminating cue |
| G3: beneficial active observation | Inspect ≥75% of ambiguous cases, inspect ≤25% of clear cases, final ambiguous exit accuracy ≥75%, and a ≥20-point gain over blocked feedback | Inspection on 20/192 ambiguous questions; final exits 102/192; 0/8 qualify | This curriculum did not establish inspection contingent on cue ambiguity |
| G4: behavioral contribution of designated connections | Target silence reduces G1 by ≥30 points; matched loss ≤10 points; old-task loss ≤10 points; exact sham/restoration | Target and matched silence both retain G1 at 40/128; 0/8 qualify | Silencing this set of forward connections does not suffice to change joint accuracy in this apparatus |

The 95% Wilson intervals for the proportion of qualifying independent individuals are 67.56%–100% for G2 and 0–32.44% for each other goal. This is an eight-individual exploration with its original decision thresholds. Sample size, criteria, and teaching were not changed in response to interim scores.

### Action and output consistency are major difficulties

On new single cues in the first window, sound prediction is 100/128, visual prediction 93/128, exit choice 57/128, and joint accuracy 40/128. First-window joint accuracy on old cues is 39/64. Expression is unstable for both new relations and the final old questions; stronger individual prediction scores do not translate into coherent joint answers. Interface development and final old questions use different dose materials, and their scores remain separate.

G2's 62/64 requires all three outputs to agree with the new context. Compared with the first-window 4/64, the net gain is 58/64, or 90.625 percentage points. Both histories of every independent individual meet the original requirements. Correct revision after new evidence is therefore a successful capability result in this experiment.

### Using supplied information and choosing to obtain it have different outcomes

| Ambiguous-cue condition | Correct final exits |
| --- | ---: |
| Actual autonomous choice of whether to inspect | 102/192 (53.125%) |
| Inspection action provides no discriminating information | 84/192 (43.75%) |
| Apparatus always supplies discriminating information | 184/192 (95.833%) |

Providing the information improves final choices. The apparatus can use discriminating information to choose an exit; the curriculum's principal gap here is deciding when to inspect.

Inspection is concentrated in individual 0: it inspects 20/24 ambiguous questions but also 16/16 clear questions. The other seven individuals inspect neither type. No individual exhibits the required selectivity. The mean autonomous benefit over blocked feedback is 9.375 percentage points and comes entirely from individual 0. A descriptive bootstrap over independent individuals gives a 95% interval of 0–28.125 points; this additional interval does not replace the original individual-level decisions.

### Silencing changes activity without the expected behavioral loss

Targets are existing directed connections from X0/X1/D0/D1 to the declared output ports; matches connect old cues to the same output group. Each set contains 14 connections with identical counts and degree distributions. The largest contemporaneous mean effective-weight difference is 0.013433 and the largest teaching-period source-endpoint activity difference is 0.008748, both below 0.05. Runtime logs record projected base-weight differences; a separate post-run calculation includes contemporaneous fast gain, and all 16 matches remain valid. As implemented before the run, activity matching uses source-endpoint means; target ports are shared by the two sets.

Target silence retains new accuracy at 40/128 and old accuracy at 39/64, equal to the intact condition. Matched silence gives 40/128 new and 38/64 old. Every final raw window in sham and immediate restoration exactly matches the intact reference. Restoration occurs before branch testing, rather than after retraining.

The additional signal audit finds that target silence changes output-port data in 768/768 answer windows while all 768 output category triples remain identical. Matched silence changes 764/768 windows and one category triple. Thus G4 has a concrete negative result: the selected connections affect port activity, but those changes do not produce the expected loss in joint performance.

## Post-result diagnosis, separate from formal temporal output

After inspecting the first four completed individuals, a read-only diagnostic was separately declared: average activation at each output port across the existing 20 frames and select the largest value using the original teacher's port mapping. Ties and all-zero values count as unresolved. The rule and code were hashed before this diagnostic ran, and it was executed only after all eight individuals finished. It never controlled behavior or entered primary scoring.

This simple projection scores 0/128 on first-window new single cues. Further inspection shows that in the recorded frames of all 384 intact first windows, activation, direct reach, and associative reach are zero at all seven output ports, while inhibition is nonzero. The nonzero information supplied to the formal adapters in those windows is therefore in the inhibitory field, whereas mean activation gives an unresolved output. Actual temporal-adapter scores remain 100/128 for sound, 93/128 for vision, and 57/128 for action on new single cues.

The observation does not support replacing the adapters with a maximum-mean-activation rule. It identifies concrete signals for the next investigation: why activation is absent at output ports in the recorded windows, how inhibitory changes participate in answers, and why the action output lacks the required selectivity.

The implementation audit also confirms that /5.1 inhibitory diffusion examines incident incoming and outgoing connections and uses the maximum available connection weight for each neighbor. All 448 reverse connections corresponding to the selected target and matched connections are present and awake. The present forward masks and bidirectional inhibitory routes therefore have distinct scopes. The contribution of a particular surviving route to performance is a question for a separately registered intervention. These are post-result explanatory checks; the original G1–G4 scores are unchanged. [Implementation](../../../crates/threemind-core/src/local_shared.rs)

## Integrity, resources, and reproducibility

Independent apparatus checks passed eleven tests, including complete restoration, identical next optimizer updates, observation-frequency invariance, no simulated advancement during wall-clock waits, answer isolation, and action-dependent feedback. The scientific batch completed in one run without a resource STOP or dead in-flight unit. Eight interface calibrations, 48 new-teaching stages, 112 interventions, and 2,688 final questions produced 2,856 complete boundaries. Audits checked full-state and original hashes, 136 continuous chains, fixed adapters, raw windows, intervention scope, and correction coverage. Separately written count-based arithmetic checked all questions and all four decisions and agreed with the main analysis.

All sixteen test parents have 17 nodes and 74 directed connections at internal ages of 786–818 seconds. Each final branch continues for 72 seconds. The declared copies together advance 19,676 internal seconds; this sum is not one individual's continuous age. Scientific host wall time is 8,881.44 seconds (148.02 minutes, including observation, saving, and I/O), with peak private memory 1.815 GiB. Minimum system headroom for commit/RAM/C/E is 12.35/12.05/16.48/103.42 GiB, above the 5/4/5/25 GiB reserves.

The pre-archive inventory contains 8,889 files: 581,552,288 logical bytes and the same hardlink-deduplicated total. Windows FileStandardInfo measures 591,507,640 allocated file-stream bytes, with zero duplicate hardlinks. Compressed complete snapshots have minimum/median/maximum sizes of 166,072/182,845.5/197,899 bytes. Each test parent plus its three adapter dependencies occupies 995,279–1,021,746 bytes. The inventory includes apparatus and scientific originals; it excludes live API logs, request cache, locks, later report copies/archive/readback, and directory, MFT, and database overhead.

Recalculation tools are `analyze.py`, `audit_integrity.py`, `audit_scores.py`, and `summarize.py`; additional diagnostics are `port_diagnostic.py` and `signal_audit.py`; storage measurement is `inventory.py`. Originals reside at `E:/ThreeMindData/experiments/2026-11-09-context-revision/v1`. Review is by the execution assistant. Independent arithmetic means a separate scoring implementation, not external researcher replication. Full API archive readback and final completion receipts are documented in [delivery verification](delivery.md).

## Meaning for ThreeMind and the next decision

The favorable finding is that new discriminating evidence can bring joint answers into agreement with the current context while three personal temporal output adapters remain fixed. The experiment also identifies specific gaps in this training route: opposite histories do not reliably organize all three outputs, inspection is not selective, and the designated forward connections do not show the expected behavioral necessity. These are three unsuccessful preregistered goals; G2's success does not substitute for them.

Compared with the [M5 fixed-personal-reader confirmation](../2026-10-16-mechanism-discovery/m5-confirmation-report.en.md), this study adds three learned temporal output adapters, joint answers, and action-dependent information acquisition. M5's single-relation expression and causal dissociation results remain intact. This study establishes which requirements the more complex fixed-output apparatus has not met.

The next priority is to separate activation and inhibition information, forward and reverse routes, and the action adapter's expression of new activity sequences, retaining complete references and using a new protocol. The present batch is not expanded directly to 48 individuals, Core is not changed, and body-feedback and sleep-like-recombination studies are not launched first. **The four original questions are closed: joint revision after new evidence succeeds; stable history-organized joint judgment, selective active observation, and the expected behavioral attribution to designated forward connections do not.**
