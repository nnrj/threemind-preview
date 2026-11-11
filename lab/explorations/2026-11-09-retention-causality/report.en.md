# R44: longer retention preserves connections but does not generally restore joint judgments

2026-11-09, first scientific report. [中文](report.zh.md) · [Preregistered protocol](protocol.en.md) · [Mechanism audit](mechanism-audit.en.md)

## Answer to the experimental question

**The current 30-second retention floor does allow the weak connections formed by this curriculum to disappear too soon. Raising existing connection half-lives to 300 seconds prevents that structural loss and changes subsequent activity and responses. It does not generally restore a joint judgment in which sound, vision, and action are all correct.**

Extending target connections immediately before testing increased new-cue joint accuracy from 40/128 to 54/128, a 10.94-percentage-point gain. Only one of eight origins met the preregistered major-benefit criterion. Extending retention after initial teaching instead brought sound and vision to 128/128 each, while action accuracy was only 28/128 for target connections and 40/128 for all connections, below the baseline 57/128. Thus the expectation that preserving connections would suffice to repair joint judgments was not met. A useful component benefit was nevertheless established: earlier preservation made sensory predictions correct while action choice remained poorly coordinated with them.

This study is a causal follow-up using the R43 curriculum and its eight independent birth origins. The two teaching histories, 112 research sequences, and 2,688 questions are nested observations within those origins. They are neither 112 independent individuals nor a confirmation study with new materials.

## Purpose, expectations, and controls

R43 had failed its joint-judgment target. Read-only review found 256 bidirectional connections between new cues X0/X1 and output ports before final testing. All had a current half-life of 30 internal seconds and actual weights of 0.019613–0.029655; all disappeared by the end of the 72-second test. We separated three explanations: losing connections during testing impairs expression; inadequate retention during earlier teaching prevents accumulation; or other processes constrain joint responses even when structure is preserved.

Late interventions began from complete parents at 786–818 internal seconds and compared baseline, target, matched, and all-connection extension. Early interventions began at 431 seconds after initial teaching and compared baseline, target, and all-connection extension before continuing the original two correction/review rounds with expanding intervals. Target and matched sets each contained 28 directed connections selected by declared channels, not test scores. The structural primary outcome counted the original X0/X1-to-output connections within that set, with node identities used to establish survival.

Each research copy was restored from its parent once and then developed continuously. Its three temporal Transformer output adapters, weights, optimizers, random state, body, mapping, and recent activity were preserved. Each answer observed a one-second process: 20 raw frames were saved, and eight fixed frame positions supplied activation, inhibition, direct, and associative activity to the adapters.

The intervention raised only the current half-life of existing connections, preserving their actual base weights at the intervention time. Source code, learning rules, defaults, and the original half-life relaxation of 0.125 seconds per internal second were unchanged. Early groups received the same teacher schedule and dose; environmental feedback contingent on their actual viewing actions remained active. The frozen protocol contains the full design.

## Closure of the registered targets

Every origin-level acceptance rule required at least six of eight origins. Joint correctness required sound, vision, and action all to be correct in the first response window. New and old cues were scored separately.

|Target|Expectation|Observed result|Scientific conclusion|
|---|---|---|---|
|Q1 Preserve target structure|Late target retains at least 90%, baseline at most 10%, in both histories|8/8 origins; target 256/256, baseline 0/256|**Passed. Longer retention prevents loss of the target structure in this study.**|
|Q2 Major benefit from extending retention during testing|At least 25 points above baseline, at least 12.5 points more than matched extension, old-cue loss at most 12.5 points|1/8; pooled gain 10.94 points; old-cue score unchanged at 39/64|**Failed. Late extension alone did not produce the registered widespread major benefit.**|
|Q3 Earlier extension improves curriculum accumulation|Target and all-connection candidates separately gain at least 25 points, with old-cue loss at most 12.5 points|Target 1/8; all 2/8; pooled new-cue changes −9.38 and 0 points|**Both failed. Earlier extension did not generally improve joint accuracy.**|
|Q4 Restore the original joint ability|New-cue accuracy at least 75% in each history, all three outputs changing jointly with opposite histories on at least 50% of cue pairs|Early target and all each 1/8; every other group 0/8|**Failed. This study did not repair the registered R43 joint-judgment target.**|

Q2–Q4 failed their behavioral expectations; their measurements were valid. Early effects varied substantially between origins, and their intervals still include the planned 25-point benefit. The precision target for the mean effect was therefore not met. This does not alter the clear finding that the observed study failed its preregistered widespread-benefit rule, nor does it imply that no origin could benefit.

## Scores and variation between origins

|Phase and condition|New joint /128|Sound /128|Vision /128|Action /128|Old joint /64|
|---|---:|---:|---:|---:|---:|
|Late baseline|40|100|93|57|39|
|Late target|54|127|110|54|39|
|Late matched|40|100|93|57|46|
|Late all|42|108|106|56|46|
|Early baseline|40|100|93|57|39|
|Early target|28|128|128|28|40|
|Early all|40|128|128|40|52|

The following estimates first pool the two histories within each origin, then resample the eight origins 20,000 times. Intervals are 95% percentile intervals for paired mean differences; all entries are percentage points.

|Change in new-cue joint accuracy relative to the same-phase baseline|Mean|95% interval|
|---|---:|---:|
|Late target|+10.94|0.00 to +24.22|
|Late matched|0.00|0.00 to 0.00|
|Late all|+1.56|−5.47 to +8.59|
|Early target|−9.38|−35.94 to +25.78|
|Early all|0.00|−32.81 to +36.72|

Late target extension had the highest pooled new-cue joint accuracy among the four late conditions, but did not meet the major-benefit rule. Early all-connection extension improved old-cue joint accuracy from 39/64 to 52/64 while new-cue joint accuracy remained 40/128. These are dimension-specific outcomes, not components of an unregistered overall ranking.

Additional behavioral measures were first-window viewing under mixed cues, correct subsequent exit choice, and joint revision of all three outputs after disambiguating evidence on conflict trials.

|Condition|Mixed-cue viewing /192|Correct subsequent exit /192|Conflict revision /64|
|---|---:|---:|---:|
|Late baseline|20|102|62|
|Late target|24|108|64|
|Late matched|20|102|62|
|Late all|24|108|64|
|Early baseline|20|102|62|
|Early target|98|133|64|
|Early all|72|120|64|

## Why preserved connections did not yield better joint judgments

Structural results were consistent. Target and all-connection extension in both phases preserved 256/256 original new-cue connections. Their baselines preserved 0/256, as did late matched extension. Earlier intervention also produced output-port activation in 128/128 new-cue first windows, versus 0/128 at baseline. This was a post-design full-window diagnostic. Baseline windows still contained inhibition, so zero activation did not mean no internal activity. Both early extensions changed 128/128 raw windows, 128/128 output-score sets, and 120/128 categorical response sets. The intervention changed internal processes and behavior.

Correct sound and vision predictions did not ensure correct actions. A post-design action-category audit found that early target extension selected “view” on 83/128 clear new-cue trials that required a direct exit choice; all-connection extension did so on 72/128, compared with 16/128 at baseline. Their viewing rates on mixed-cue trials were 98/192 and 72/192, respectively, lower than their rates on clear new cues. Viewing became more common without becoming selective for an information need. This error pattern explains why joint accuracy did not follow the sensory improvement. It does not assign sole causation to an untested downstream component.

The activity and action diagnostics are explicitly retrospective and leave Q1–Q4 scores and criteria intact. They identify a concrete next question: how extended retention changes the process signals at the action channel, and how the existing personal adapter converts them into viewing or exit choices. R45 first completes the registered relaxation-rate comparison; subsequent pathway and expression controls can then be selected from both studies.

## Implications for the decay mechanism

These results support continued work on retention: useful connections are short-lived under the default conditions, and preserving them earlier improves sound and vision predictions. They also reject treating longer retention as an accomplished repair of joint ability. The authorized six-condition decay comparison must measure retention, correct expression, forgetting of weak stimuli, old interference, and rule reversal rather than simply counting surviving connections.

The immediate structural issue concerns the balance between half-life growth and relaxation. Thirty seconds is a parameter floor. Shared external stimulation can increase base weight, whereas actual local transmission grows a connection's half-life; those are different updates. R45 uses the existing per-instance API to compare the original relaxation rate, one-tenth of that rate, and no relaxation while retaining exponential weight decay. The separate 5.2 candidate will compare exponential, logarithmic, and power-law decay. The naming clarification does not change existing linear relaxation or upgrade old individuals.

Mathematical candidates are stored separately from measured outcomes. At equal 30-second half-value times, inverse-log decay retains the same weak connection longer than exponential decay, but the same formula can imply extremely long deletion times for strong connections. Explicit formulas, ages of learning contributions, and consistency across time partitions are requirements for the new implementation. [Calculations and sources](mechanism-audit.en.md)

## Verification, resources, and evidence

Independent JSON arithmetic verified 112 continuous chains, 112 interventions, 96 teaching stages, and 2,688 trials: 2,896 complete boundaries in total. All 553 source files were checked against the originals, as were hashes for 72 adapter dependency files. Eight hundred baseline boundaries reproduced the full R43 state apart from declared copy identity, cursor, and parent references. Teacher schedules, waits, and doses matched. Target and matched connection counts and degree distributions passed; the largest contemporaneous mean-weight residual was 0.013414, below the registered 0.05 threshold. The largest retrospective activity-matching residual was 0.005556 and is disclosed descriptively.

Scientific computation took 10,724.21 seconds (about 2 hours 59 minutes) and advanced 25,920 internal seconds summed over research copies. Peak host private memory was 1.69 GiB. Minimum available commit memory, RAM, C-drive space, and E-drive space were approximately 11.55, 10.63, 20.29, and 101.68 GiB, above the 5/4/5/25 GiB guard reserves. There was no resource STOP, new rollback, or incomplete final state.

The pre-publication inventory counted 9,521 files, 651,128,833 logical bytes, and 663,850,832 allocated bytes after deduplication by file identity; no duplicate hard links appeared in this inventory. The largest complete snapshot contained 18 nodes and 78 directed connections and occupied 200,783 compressed bytes. Including all personal adapter dependencies, one complete individual occupied 1,025,698 logical bytes and 1,037,416 allocated bytes. Reports added after this measurement, archives, platform database storage, and readback copies are additional; directory and filesystem metadata are excluded.

Originals: `E:/ThreeMindData/experiments/2026-11-09-retention-causality/v1`. Main records: `analysis-v1.json`, `independent-audit-v1.json`, `source-audit-v1.json`, `activity-diagnostic-v1.json`, `action-diagnostic-v1.json`, `storage-inventory-v1.json`, and `figures/behavior.*` / `figures/decay-curves.*`. Research record: `21f12dc8-0681-5b6b-a521-6f83e8c4e96e`. Full archive readback and finalization receipts are listed in the [delivery record](delivery.md). Review and separate arithmetic verification were performed by the executing assistant, not represented as human review or external-laboratory replication.

**The added finding is that inadequate retention can impair the preservation and expression of learned relations. Preserving structure improves sensory predictions here, while joint judgment remains limited by action choice. Retention deserves improvement; repairing the joint ability also requires resolving action selection.**
