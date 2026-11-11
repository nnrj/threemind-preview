# R45: disabling retention relaxation did not improve joint judgments

9 November 2026, first scientific report. [中文](report.zh.md) · [Preregistered protocol](protocol.en.md)

## Scientific conclusion

**In this curriculum, slowing half-life relaxation tenfold or disabling it improved neither joint sound–vision–action accuracy nor survival of the new-cue connections formed under natural retention.** All three natural-retention groups answered 40/128 new trials correctly. All three groups whose target half-lives were first raised to 300 seconds answered 28/128. Every origin's paired accuracy difference was zero in all four primary contrasts; all major-benefit targets passed in 0/8 against the preregistered six-of-eight requirement.

The study identified a more specific retention problem: little retention growth was acquired during natural teaching. Even with relaxation disabled, target half-lives after both teaching stages ranged from 30.000 to 30.156 seconds, with median 30.024 seconds; all disappeared by the end of testing. Raising the initial target half-life to 300 seconds preserved every target connection under all three relaxation rates, and both sensory predictions were correct, but actions remained mismatched. Thus the expected repair by slowing or disabling relaxation alone failed. Further work should compare actual decay curves and experience-dependent timescale growth while retaining action selection as a separate behavioral question.

## Purpose and design

The author suggested that relaxation of an extended half-life might be the principal reason for short retention. This study used the existing 5.1 instance-configuration API to compare rates 0.125, 0.0125 and zero, measured in half-life seconds lost per internal second. The parameter affects both nodes and directed connections. Exponential weight decay and all other rules continued; disabling relaxation did not disable forgetting.

Eight independent birth origins from R43, each with two opposite teaching histories, supplied complete post-initial-teaching parents at 431 internal seconds. Natural half-lives or target half-lives raised to at least 300 seconds were crossed with the three rates, producing 96 research sequences. Every copy received the configuration API call, including sham controls, then continuously completed two fixed correction/review stages and 24 trials. The curriculum was fixed from historical errors, with matched teaching and dose; all actual new answers and errors were retained.

Each individual kept its three personal temporal Transformer adapters, weights, optimizer, random states and readout window. Answers used a one-second, 20-frame record, with the original eight frame positions carrying activation, inhibition, direct and associative activity. Core, body, mappings, recent activity and actuators remained continuous. Each research branch was restored once at creation; no question-level restoration occurred thereafter.

The 96 sequences and 2,304 trials are nested within eight origins. Reused materials do not constitute fresh-material confirmation. Production kernels, installed modules, defaults and original evidence were unchanged.

## Registered expectations and outcomes

|Target|Expected result|Measured result|Scientific conclusion|
|---|---|---|---|
|R1 Effective intervention|Current physical error ≤1e-12; clock, queue and peripherals intact; disabled-relaxation H never decreases for the same surviving connection|Passed; no decreases in 52,217 comparisons|**The intervention worked; failed behavioral benefit was not an ineffective switch.**|
|R2 Natural-retention benefit|Slow and disabled rates each improve new joint accuracy by ≥25 percentage points with old loss ≤12.5 points, in at least 6/8 origins|Both 0/8; every paired new-accuracy difference zero|**Neither change improved natural-retention joint answers in this curriculum.**|
|R3 Additional benefit after extension|The same thresholds after target H was raised to 300 seconds|Both 0/8; every paired difference zero|**Preventing relaxation of already extended retention did not repair the behavioral difficulty.**|
|R4 Joint-target restoration|New joint accuracy ≥75% in both histories and all three outputs change with opposite history in ≥50% of matched cues, in at least 6/8 origins|Natural groups 0/8; raised groups each 1/8|**No condition repaired the registered joint-judgment target.**|

All four paired mean new-accuracy differences were zero percentage points, with origin-bootstrap 95% intervals [0,0]. This describes the eight reused origins; it is not a population-wide zero-effect bound for other curricula. Registered goals and denominators were unchanged.

## Scores

|Initial retention / relaxation|New joint /128|Sound /128|Vision /128|Action /128|Old joint /64|
|---|---:|---:|---:|---:|---:|
|Natural / default|40|100|93|57|39|
|Natural / slow|40|100|93|57|39|
|Natural / off|40|100|93|57|39|
|Raised to 300 s / default|28|128|128|28|40|
|Raised to 300 s / slow|28|128|128|28|40|
|Raised to 300 s / off|28|128|128|28|40|

|Initial retention / relaxation|View on mixed cues /192|Correct subsequent exit /192|Joint conflict revision /64|
|---|---:|---:|---:|
|Natural / default, slow, off (each)|20|102|62|
|Raised / default|98|133|64|
|Raised / slow|97|133|64|
|Raised / off|97|133|64|

Default, slow and disabled relaxation tied on the registered new-joint dimension. Natural retention had higher aggregate joint accuracy than raised retention, while raised retention improved sensory prediction, conflict revision and exits after mixed cues. These dimensions remain separate.

## What happened to retention

All 256 original directed new-cue/output connections had H=30 seconds after initial teaching. Natural default and slow groups still had H=30 at the post-teaching measurement boundaries. With relaxation disabled, the median reached only 30.024 seconds and the maximum 30.156 seconds. All three ended with 0/256 surviving target connections. Thus this curriculum acquired too little timescale growth to move those connections out of the approximately 30-second retention range; disabling relaxation supplied no missing growth.

The raised groups all retained 256/256 connections, but their final H and weights differed:

|Raised-group relaxation|Final H minimum / median / maximum, s|Median final base weight|
|---|---|---:|
|Default|246.50 / 251.33 / 263.14|0.24956|
|Slow|296.10 / 301.86 / 314.36|0.26917|
|Off|301.61 / 307.45 / 320.29|0.27113|

The switch therefore changed retention as intended, without improving joint accuracy. A post-run action-category check found 83/128 VIEW choices on clear new trials in each raised group, compared with 16/128 in each natural group. The viewing bias persisted despite perfect sensory predictions. This retrospective diagnosis describes the errors without changing R2–R4.

Compared with the corresponding R44 default-rate controls, all category answers matched in 768 trials. Both raw windows matched exactly in 559 trials; the maximum absolute difference elsewhere was 1.943×10⁻¹⁶. This additional read-only diagnostic identifies floating-point last-bit differences from ordinary lazy-state materialization by the API. The comparison is not described as whole-state bitwise identity.

## Implications for ThreeMind

R44 established a structural benefit from longer retention. R45 rejects changing relaxation rate alone as a successful repair under this curriculum. Natural H remaining close to its lower bound after relaxation is disabled is the specific mechanism fact to investigate next. Candidate decay curves must also be assessed on strong, weak and repeated exposure and eventual forgetting.

No new default rate is adopted. Under the author's authorization, a distinct 5.2 version will add exponential, logarithmic and power-law curves with an independent relaxation switch, preserving 5.1. Its first layer compares local retention and complete cue-driven activity, with the personal-adapter joint task retained separately. Connection count and H are not substituted for behavioral success.

## Verification, cost and evidence

Independent JSON arithmetic verified 96 continuous chains, 96 interventions, 192 teaching stages, 2,304 trials and 2,592 complete boundaries. Hash checks covered 553 source files and 72 personal-adapter dependencies. Trials retained their three-second duration; aggregate advancement across copies was 42,624 internal seconds. Verification did not instantiate or advance Core. The bilingual reports and two scientific figures were reviewed by this execution assistant; independently implemented arithmetic is labeled as such, without claiming a human or external-laboratory review.

Scientific runtime was 8,849.67 wall seconds, approximately 2 h 27 min, with peak private memory 1.652 GiB. Minimum commit/RAM/C/E headroom was 10.914/10.914/20.134/99.906 GiB. There was no resource STOP, new rollback or incomplete final state.

The 20:18 prepublication storage snapshot counted 8,566 files, 602,620,040 logical bytes and 614,460,008 allocated bytes after file-identity deduplication; no duplicate hard links were found. Later analysis, figures and reports are additional. The largest individual snapshot contained 18 nodes and 76 directed connections in 199,841 compressed bytes. With its nine adapter dependencies, one complete individual occupied 1,024,756 logical and 1,033,320 allocated bytes. Directory, platform-database and filesystem-metadata overhead is excluded.

Originals: `E:/ThreeMindData/experiments/2026-11-09-retention-relaxation/v1`. Principal evidence includes `analysis-v1.json`, `independent-audit-v1.json`, `api-control-diagnostic-v1.json`, `storage-inventory-v1.json`, `resource-summary.json` and two figures in PNG/SVG/PDF. Research record: `2856e835-10aa-5efe-a679-b8701337c030`. See [delivery](delivery.md) for full archive readback and finalization.

**Disabling relaxation preserved the timescale already acquired, but this curriculum acquired too little growth. Disabling relaxation alone repaired neither short connection retention nor joint judgment.**
