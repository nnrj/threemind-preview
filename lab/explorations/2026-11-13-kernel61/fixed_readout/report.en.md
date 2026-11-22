# R51k: A fixed reader expresses new learning in 6.1; the tested temporal features fail the stable-expression target

13 November 2026. **All eight independent sources passed fixed expression and connection causality with the 110-ms output-port reader. After the Core learned new correspondences, its existing reader expressed them without further training. Blocking new-relation connections abolished new answers while preserving old answers; restoring those connections restored the answers.** The primary, 250-ms temporal condition passed fixed expression in 4/8 sources and causal attribution in 0/8, below the registered 6/8 threshold.

The experiment therefore supports expression of new Core learning through an existing personal reader. It also rejects the expectation that the particular temporal features and calibration procedure tested here provide stable expression. Subsequent courses should not treat that temporal representation as a validated reading method.

## Purpose and expectation

The experiment distinguishes learning by the Core from learning by its reader. A personal linear reader first learns how to answer from old-relation teaching data and is then frozen. The Core receives new teaching, and the same reader answers. The expected outcome is expression of new relations with preservation of old relations, selective impairment after blocking the corresponding connections, and recovery after restoration.

The author approved temporal readout as the primary condition and the historical 110-ms endpoint as a separate comparison. Both observe the same Core and the same teaching and testing experiences. The [preregistered protocol](protocol.en.md) defines separate targets for fixed expression, Core attribution, reading scope, and further reader calibration. The primary condition is not selected after seeing results.

## Methods

Eight independent birth sources each supplied two opposite new teaching histories and registered causal copies. Ordinary teaching, sampling, and questions proceeded continuously. Saved complete states include the Core, personal readers and their learning state, random state, channel mappings, recent activity, and answer terminal. The independent unit is the source; histories and questions are nested observations.

Old and new courses each contain 16 rounds with increasingly spaced repetition. Readers were calibrated on 12 old-course samples and checked on six development questions. All eight sources passed the registered development check without triggering corrective rounds. With readers frozen, the Core learned XY–A and CD–B, or the opposite relations, while reviewing old relations. New answers could not be used to recalibrate readers before their first new responses.

Temporal readout samples activation, inhibition, direct activation, and associative activation every millisecond from 1 to 250 ms after a stimulus. Means in five consecutive 50-ms intervals form 240 ordered features. A separate endpoint comparison uses 12 activation values at 110 ms from the same trajectory. Each condition has a whole-channel reader and a reader restricted to the declared A/B output ports. A direct sensory reader provides an additional comparison. All are personal linear ridge models with normalization and answer thresholds fixed after initial calibration.

After new teaching, registered copies receive sham operations, blocking of new-relation connections, blocking of old-relation connections, or restoration. Another teaching branch uses the public plasticity-off configuration, a combined intervention. Each connection set contains four directed edges with matched counts and degrees; contemporaneous weight and teaching-activity residuals must satisfy registered limits. Connections are selected from declared teaching interfaces, without final-test answers. After first-response testing, separate copies retain frozen readers or continue calibration and then receive previously unused doses of 0.85 and 0.95.

A source passes a target only if both opposite histories satisfy it; a batch requires at least 6/8 passing sources. Fixed expression requires at least 75% new-question accuracy and a gain of at least 50 percentage points over prelearning, while retaining old performance. The causal target additionally requires gains of at least 50 points over plasticity-off and new-connection blocking, selective preservation of the other relation, and exact recovery.

## Results

The following counts use independent sources and the original thresholds.

| Target | Temporal, all channels | Temporal, output ports | 110 ms, all channels | 110 ms, output ports |
|---|---:|---:|---:|---:|
| New learning expressed after freezing | 0/8, failed | 4/8, failed | 0/8, failed | **8/8, passed** |
| Causal contribution of new learning and its connections | 4/8, failed | 0/8, failed | 4/8, failed | **8/8, passed** |
| Benefit of further calibration at unseen doses | 4/8, failed | 4/8, failed | **8/8, passed** | 0/8, failed |

The registered advantage of output-port over whole-channel reading passed in 4/8 sources in each timing condition, below 6/8. Success on other endpoint targets does not change that result.

First-test single-cue answers are shown below. The denominator of 64 comprises eight sources, two histories, and four cues. It describes answers, not 64 independent samples.

| Condition | Temporal ports, new | Temporal ports, old | Endpoint ports, new | Endpoint ports, old |
|---|---:|---:|---:|---:|
| Full teaching, sham | 44/64 | 48/64 | **56/64** | **64/64** |
| New connections blocked | 28/64 | 48/64 | **0/64** | **64/64** |
| Old connections blocked | 48/64 | 28/64 | **56/64** | **0/64** |
| Connections restored | 44/64 | 48/64 | **56/64** | **64/64** |
| Plasticity off during new teaching | 24/64 | 48/64 | **0/64** | **64/64** |

Restoration reproduces all reference reader scores exactly. Direct sensory reading answers 0/64 new and 64/64 old questions correctly. Joint cues are retained separately under the protocol and do not enter these single-cue denominators. Exact 95% intervals for the source-level passing proportions are 63.06%–100% for 8/8, 15.70%–84.30% for 4/8, and 0–36.94% for 0/8.

## Analysis and scientific conclusion

**The fixed output-port endpoint reader establishes that the changes needed to answer the new relations occurred in the Core.** The reader received no further training, and new test cues contained no answer labels. Normal teaching produced 56/64 correct new answers; plasticity-off or blocking new connections reduced this to 0/64. Blocking old connections instead abolished old answers. The corresponding local connections therefore support the two relations separately, and restoration demonstrates reversibility. Both source-level expression and causality targets passed in 8/8 sources.

**The tested temporal readout did not provide stable expression of new relations.** It recorded four activity types over time, but the combination of five interval means, a linear model, and old-course calibration failed the registered expression and causal criteria. Passing development questions was followed by old-question errors at a new test dose. Adding temporal information did not by itself yield a reliable personal reader. This negative result directly constrains subsequent use of this feature design.

Further calibration identifies the contribution of peripheral learning. At unseen doses, the whole-channel endpoint reader improved from 40/128 to 128/128 correct new answers while retaining 128/128 old answers; all eight sources passed the benefit target. Temporal output-port reading improved from 88/128 to 128/128 new answers and from 96/128 to 128/128 old answers, but only four sources met the required gain. The output-port endpoint reader already answered 128/128 correctly and gained nothing further, so it retained its original 0/8 benefit verdict. First responses and later calibration benefits are scored separately.

For ThreeMind, the conclusion is specific and direct: **6.1 retains the ability to learn correspondences in local connections and express them through a fixed personal reader; the temporal feature design tested here does not provide a stable replacement.** The registered campaign stop applies when both temporal and endpoint conditions lose output-port expression and causality. It was not triggered. After delivery, the campaign proceeds to the author's requested investigation of changed inertial responses.

## Continuity, audit correction, and delivery

The experiment saved 2,024 complete states. The initial host reached its 1-GiB private-memory budget after completing the second source, with all individuals saved and no in-flight unit. The host had retained the previous source's result while computing the next. Each of the remaining six independent sources was completed serially in a fresh host, preserving continuous complete state within the source and the frozen curriculum. Total scientific computation was 3,207.38 seconds, or 53.46 minutes. Pausing added no simulated time. The [host-continuation note](continuation-note.en.md) records the original STOP, verification, and separate entry point.

The original read-only audit stopped because its allowed-field list omitted the active-node index updated by a same-time public configuration operation. The revised audit independently recomputes the index from saved activation and elapsed time and checks internal time, event sequence, and queue. All 32 relevant operations passed. Validation covered 2,024 complete states, 1,824 answers, and 64 connection-mask receipts; maximum weight and activity matching residuals were 0.03107 and 0.00120, within their registered limits. Scientific execution, scoring functions, and criteria remain unchanged; the original failed audit and records are retained. The [audit correction](audit-correction.en.md) explains the omission. Auditing reads files without loading or advancing an experimental Core. Files at analysis occupied 3.255 GiB logically and 3.259 GiB in allocated storage. Initial-host peak private memory was 1,024.70 MiB; system commit, physical memory, and C/E free space retained the required margins.

Originals are in `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/fixed-readout61-v1/`, research record `5fbc563e-3574-52f3-b7f9-9b2eb4233d4d`. `audit.json` and `analysis.json` contain validation, resource, and storage results. `publication/completion.json` records complete archive readback through the research API and zero pending requests. Historical experiments, production kernels, defaults, and the author's manuscript are unchanged.
