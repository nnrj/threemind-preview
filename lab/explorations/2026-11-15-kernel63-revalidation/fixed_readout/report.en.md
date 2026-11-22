# R63h: fixed readers express new learning in 6.3; the tested temporal readout does not meet the stability criterion

16 November 2026. All eight independent origins pass expression and causal-attribution criteria with the 110-ms output-port reader. After reader training stops, the Core learns and expresses new relations. Blocking the new connections eliminates new answers while preserving old answers; restoration restores expression. The primary 250-ms temporal condition passes fixed expression in 4/8 origins and causal attribution in 0/8, below the preregistered 6/8 threshold. Both readers observe the same Core experiences and retain their original scoring rules.

## Purpose and expectation

The study asks whether changes needed to answer new relations can occur in the Core without further reader training. A personal linear reader is calibrated on old teaching and then frozen while the Core learns new relations. The expected result is new expression with preserved old answers, selective impairment after connection intervention, and recovery after restoration.

The author approved temporal readout as primary and retained the 110-ms endpoint comparison. This replication uses new 6.3 individuals with the eight-origin design, curriculum, features and criteria used for 6.1. The [preregistered protocol](protocol.en.md) specifies four goals and the stopping rule.

## Methods

Each origin supplies two opposite new teaching histories and declared causal copies; independent N is eight. Ordinary teaching, questions, correction and review continue from the current complete state, preserving the Core, personal reader and learning state, channels, random state, recent activity, body and actuator.

Old and new teaching each comprise 16 rounds with progressively spaced intervals. Twelve old-course process samples calibrate personal ridge-regression readers, followed by six development questions. All eight origins pass without corrective rounds. After freezing, the Core learns XY–A and CD–B, or the opposite relations, while reviewing old relations. New labels never recalibrate the readers before first responses.

The temporal features record activation, inhibition, direct activity and associative activity every millisecond from 1 to 250 ms. Means over five ordered 50-ms windows form a 240-dimensional vector. The endpoint comparator uses 12 activations at 110 ms from the same trajectory. Each condition has full-channel and A/B-output-port readers, alongside a current-sensory control. Parameters, normalization scales and answer thresholds are fixed before new teaching.

After new teaching, declared copies receive sham treatment, new-connection blocking, old-connection blocking or restoration; a separate teaching branch disables the API's combined plasticity operations. Each connection set has four edges with matched degrees, mean-weight residual ≤0.05 and teaching-activity residual ≤0.02. After first tests, further copies retain frozen readers or undergo additional calibration, then receive previously unfitted doses of 0.85 and 0.95. Later calibration never changes first-test scores.

Both histories must meet a goal for an origin to pass, and at least six of eight origins must pass. Fixed expression requires ≥75% new-answer accuracy and a ≥50-percentage-point gain from before learning, while old accuracy remains ≥75% with ≤10-point loss. Causal attribution additionally requires ≥50-point advantages over both plasticity-off teaching and new-connection blocking, selective effects on new versus old relations, and exact restoration.

## Results

| Goal | Temporal, full | Temporal, ports | 110 ms, full | 110 ms, ports |
|---|---:|---:|---:|---:|
| Expression after freezing | 0/8 | 4/8 | 0/8 | 8/8 |
| Causal contribution of learning and connections | 4/8 | 0/8 | 4/8 | 8/8 |
| Benefit of further calibration at unseen doses | 4/8 | 4/8 | 8/8 | 0/8 |

The preregistered output-port advantage over full-channel reading passes in 4/8 origins in each condition, below 6/8. The following counts describe first single-cue answers. The denominator 64 is eight origins × two histories × four questions, not 64 independent samples.

| Condition | Temporal ports, new | Temporal ports, old | Endpoint ports, new | Endpoint ports, old |
|---|---:|---:|---:|---:|
| Taught, sham | 44/64 | 48/64 | 56/64 | 64/64 |
| New connections blocked | 28/64 | 48/64 | 0/64 | 64/64 |
| Old connections blocked | 48/64 | 28/64 | 56/64 | 0/64 |
| Connections restored | 44/64 | 48/64 | 56/64 | 64/64 |
| Plasticity off during new teaching | 24/64 | 48/64 | 0/64 | 64/64 |

Restoration reproduces every response score exactly. The current-sensory control answers 0/64 new and 64/64 old questions correctly. Joint cues are reported separately. Exact 95% confidence intervals for origin pass rates are 63.06–100% for 8/8, 15.70–84.30% for 4/8, and 0–36.94% for 0/8.

## Analysis, scientific conclusions and implications

Endpoint output-port results confirm that the Core learns new relations and expresses them through a fixed personal reader. New teaching produces 56/64 correct new answers. Disabling plasticity or blocking new connections reduces this to 0/64 while preserving all 64 old answers. Blocking old connections instead eliminates only old answers. The corresponding local connections separately support new and old relations, and expression returns after restoration.

The tested temporal features and calibration method do not express new relations reliably enough to meet the original goals. Recording time-dependent activity does not by itself establish an effective reader. The tested combination of five-window means, a linear model and old-course calibration falls short; these data do not isolate one of those components as the cause. This limitation remains relevant to subsequent tasks.

Further calibration identifies a peripheral-learning contribution. Endpoint full-channel new-answer accuracy at unseen doses rises from 40/128 to 128/128 while old accuracy remains 128/128; all eight origins pass the benefit criterion. Temporal output-port accuracy rises from 88/128 to 128/128 on new questions and from 96/128 to 128/128 on old questions, but only four origins meet the required gain. Endpoint output-port accuracy is already 128/128, so it retains its original no-additional-benefit verdict.

Across 6,901 scientific numerical fields, the maximum difference from 6.1 is 0, with identical categorical decisions. Thus 6.3 retains connection-based learning expressed through a fixed reader and reproduces the limitations of this temporal-readout design. No new adverse contradiction occurred. [Public edition: manuscript editing or private locator omitted.] Inertial-response investigation remains next when the author resumes the campaign. This scheduling decision does not change the scientific results.

## Integrity, cost and evidence

Independent file audits verify 2,024 complete states, 1,824 answers, 64 mask receipts and 32 same-time configuration operations. Maximum weight and activity matching residuals are 0.03106545 and 0.00119802, within the frozen limits. Audits neither load nor advance experimental Cores.

From the outset, the eight origins run serially in separate hosts while each complete life remains continuous. No resource pause occurs. Computation totals 3075.83 s (51.26 min), compared with 3207.38 s for 6.1, a ratio of 0.959. Peak private memory is 863.49 MiB; allocated originals at analysis occupy 3.259 GiB. Timing includes experimental recording and other host work. Host-release arrangements differ slightly, so the entire difference cannot be attributed to Core speed.

Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/fixed-readout-63-rerun-v1`. Research record: `9ca4dd7c-55fb-59b4-99d9-06705b3e79bf`. Statistics and audits are in `analysis.json`, `audit.json` and `historical-comparison.json`; `publication/completion.json` records complete API archive readback and pending status. Production Core code, defaults, historical individuals, originals and manuscript remain unchanged.
