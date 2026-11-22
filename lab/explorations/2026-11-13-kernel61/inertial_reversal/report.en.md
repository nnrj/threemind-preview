# R51m: Transmission conditions change the inertial response; prompt connection deletion is not required

13 November 2026. **Raising only the transmitted-signal threshold from 0.0004 to 0.004 in version 6.1 restored the historical reversed response in all four material blocks, while retaining inverse-logarithmic decay. Disabling connection deletion in the historical kernel also preserved reversal in all four blocks. These results reject the hypothesis that the old reversal requires prompt deletion of transient connections and establish a selective causal effect of the transmission threshold on response direction.**

Versions /2, /3.1 and /5.1 produced reversed responses; /5.3 and /6.1 produced responses consistent with teaching. The change was already present between 5.1 and 5.3. It did not originate with fixed-function addressing or local deletion in 6.1.

## Purpose, expectations and design

In E18, adding inertial sensory information made bodily cues elicit marker activity opposite to the taught correspondence. In the 6.1 replication R51h, the corresponding activity followed the taught direction. The author proposed that slower decay might prevent transient connections from being deleted promptly. This study tested that explanation alongside stimulus enqueueing, fatigue, inhibition, fast enhancement and signal thresholds. The [preregistered protocol](protocol.en.md) specified five targets and their decision rules.

We retained the four historical anonymous material blocks, seeds 930101–930104, with ordinary and facilitating configurations. Each individual continuously experienced 32 bodily teaching segments over 19.2 internal seconds, followed by a one-second retention interval. Registered research copies of the complete parent then received a 0.4-second bodily cue and were observed until 5.6 seconds after cue onset. Cues contained neither answer marker A nor B. A matched copy received no task cue over the same interval.

A response in the “taught direction” means that the dominant marker corresponds to the cued posture in teaching; a “reversed response” means that the other marker dominates. These were internal process responses to bodily cues; no arm was actuated during measurement. Full sensory input included joint, gravity and inertial information. The joint-only condition tested whether a direction change was selective to the additional sensory information. Dose-matched, shuffled-inertia and untrained conditions supplied further comparisons.

Seventeen version or configuration conditions produced 320 teaching individuals and their diagnostic copies, comprising 1,792 stages. The statistical units were the four material blocks. Postures, facilitation settings, versions and related copies were repeated observations within those blocks.

Activation, inhibition, direct activation and associative activation were recorded every 100 milliseconds. The primary window was 0.6–5.6 seconds. We subtracted the matched no-cue trajectory and compared the activation integrals of A and B. A direction required a peak increment above 1×10⁻⁵ and an integral advantage above 1×10⁻⁶. A block reproduced the historical relationship when at least three of its four full-sensory measurements were reversed and at least three joint-only measurements retained the taught direction. Configuration-level restoration required at least three of four blocks. These rules were frozen before execution.

## Results

### The historical difference replicated across scheduling and measurement conditions

| Genuine kernel | Full sensory: reversed | Full sensory: taught | Joint only: taught | Blocks with the historical relationship |
|---|---:|---:|---:|---:|
| /2 | 16/16 | 0/16 | 16/16 | 4/4 |
| /3.1 | 16/16 | 0/16 | 16/16 | 4/4 |
| /5.1 | 16/16 | 0/16 | 16/16 | 4/4 |
| /5.3 | 0/16 | 16/16 | 16/16 | 0/4 |
| /6.1 | 0/16 | 16/16 | 16/16 | 0/4 |

Each set of 16 comprises four blocks, two facilitation settings and two postures. Versions /2 and 6.1 were tested both with the historical incremental enqueueing schedule and with the stage-start prequeueing used by R51f/h. Direction classifications were identical. Arrival times and stimulus values were held constant between these scheduling conditions.

The 0–0.6-second input window, the shared 0.6–5-second window, the primary window and the primary window without blank subtraction gave the same directions. Dose-matched and shuffled-inertia conditions each yielded 16/16 reversed responses in /2 and 16/16 taught responses in 6.1. Neither version produced a measurable direction in any of its 16 untrained tests. The difference therefore depended on processes formed through teaching and was not explained by the measurement window or blank subtraction.

### Connection deletion is not necessary for the historical reversal

Setting the deletion threshold to zero in /2 preserved 16/16 reversed full-sensory responses and 16/16 taught joint-only responses. All four blocks retained the historical relationship. This directly rejects the proposed necessity of deleting transient connections to produce reversal.

The old rules also provide an independent timing bound. The minimum birth weight in these materials was 0.0325, and the maximum decay fraction per 100 milliseconds was 0.0023. Even under that maximum loss throughout the entire 25.8-second episode, the weight would remain at least 0.0179422, above the deletion threshold of 0.008. The earliest inactivity-based node deletion was 80 seconds. Samples of the historical runs likewise showed no disappearing connections. Thus, reversal occurred before deletion would have been required.

Independent calibration selected a higher threshold of 0.013831055361679393. At three stimulus doses, the old connection deletion times were 62, 65 and 75 seconds; the corresponding 6.1 times were 54, 65 and 138 seconds. All met the preregistered 0.5–2× timing criterion. Formal response answers were not used to select this value. In the bodily task, however, the higher threshold, exponential decay and their combination each retained the taught direction: none restored reversal in any block. Sampled connection weights remained above the raised threshold during the formal episode.

Matching the historical deletion speed therefore did not restore reversal. Within this task interval, the relevant question is how existing connections transmit signals, rather than whether they have been deleted.

### A higher transmitted-signal threshold restored the historical relationship

| 6.1 condition | Full sensory: reversed | Full sensory: taught | Joint only: taught | Blocks restored relative to default 6.1 |
|---|---:|---:|---:|---:|
| Current defaults | 0/16 | 16/16 | 16/16 | 0/4 |
| Exponential decay | 0/16 | 16/16 | 16/16 | 0/4 |
| Higher deletion threshold | 0/16 | 16/16 | 16/16 | 0/4 |
| Exponential decay plus higher deletion threshold | 0/16 | 16/16 | 16/16 | 0/4 |
| Transmitted-signal threshold 0.004 | **16/16** | 0/16 | **16/16** | **4/4** |
| Strong-stimulus fatigue disabled | 0/16 | 16/16 | 16/16 | 0/4 |
| Inhibitory transmission excluded from connection reinforcement | 0/16 | 16/16 | 16/16 | 0/4 |
| Both node send thresholds zero | 0/16 | 16/16 | 16/16 | 0/4 |
| Reception activity matching disabled | 0/16 | 16/16 | 16/16 | 0/4 |

`signal_threshold` applies to the signal amount calculated after connection and synaptic-resource effects. It differs from `activation_send_threshold` and `inhibition_send_threshold`, which determine whether nodes continue scheduling sends. Raising the former excluded more weak signals and restored reversal. Setting the two node thresholds to zero did not change direction. These three thresholds were tested separately.

For full sensory input under default 6.1, the taught-marker integral minus the alternative-marker integral ranged from 0.025124 to 0.028422. Raising the transmitted-signal threshold to 0.004 changed that range to −0.004639 to −0.002791. These differences were well above the registered 1×10⁻⁶ decision margin. All four blocks changed direction while joint-only responses were preserved. **The transmission threshold therefore has a causal role in determining the direction of this learned bodily response.**

### Disabling inhibition before testing changed the old response; disabling fast enhancement did not

| Pretest operation | Full sensory: reversed | Full sensory: taught | Joint only: taught |
|---|---:|---:|---:|
| /2: inhibition disabled | 4/16 | 12/16 | 16/16 |
| /2: fast enhancement disabled | 16/16 | 0/16 | 16/16 |
| 6.1: inhibition disabled | 0/16 | 16/16 | 16/16 |
| 6.1: fast enhancement disabled | 0/16 | 16/16 | 16/16 |

In /2, disabling inhibition changed three of four full-sensory measurements in each block from reversed to taught. All four blocks met the registered selective-change criterion. The intervention used the existing public configuration operation: it disabled subsequent inhibition and cleared existing inhibition and relevant pending events; the interface also settled short-term states at the current time. This was a declared pretest operation, rather than a change to one connection or one inhibitory value. All 192 before/after intervention states and changed fields were retained, with internal time unchanged.

Disabling fast enhancement preserved the historical relationship. Disabling strong-stimulus fatigue from birth in /3.1 also preserved 16/16 reversed responses. These tests identify effective direction changes under the transmission-threshold and pretest inhibition operations, while the other tested single-factor explanations were not supported.

## Scientific conclusions and the next experiment

All five registered targets now have explicit outcomes:

1. **Reproducing the difference: achieved.** Matched bodily materials reproduced both the historical reversal and the newer taught response. The transition occurred between 5.1 and 5.3.
2. **Deletion as a necessary mechanism: rejected.** Preventing deletion preserved reversal, and the task occurred before old connections could reach their deletion threshold.
3. **Restoration by decay or faster deletion: not supported.** Exponential decay, the independently calibrated deletion threshold and their combination all failed to restore reversal.
4. **Alternative causal factor: identified.** Raising only the transmitted-signal threshold restored the historical relationship in 4/4 blocks. The pretest inhibition operation also selectively changed the historical direction.
5. **Implication for revalidation: retain current 6.1 defaults and continue.** The newer kernel preserved the taught bodily correspondence, which better matched this task's teaching target. Neither loss of bodily association nor the campaign's adverse-mechanism or performance stop was observed.

For ThreeMind, the study establishes that experience-shaped connections can remain present while transmission conditions change which response is elicited. The historical reversal should be described as a bodily association under its particular dynamics. Subsequent embodied studies will distinguish taught, reversed and absent responses. There is no reason to raise the production threshold merely to recover the historical direction. All configuration changes here were confined to registered research individuals; Core source and default settings were preserved.

Following the author's requested insertion, delivery of this batch is followed by R51l, the independent 48-source local-transfer confirmation. This decision follows the completed targets and existing stop rules; it does not change any subsequent scoring criterion.

## Evidence, audit and cost

Scientific execution took 2,582.53 seconds, or 43.04 minutes. Peak host private memory was 671.05 MiB. At analysis time, originals occupied 527.95 MiB logically and 560.61 MiB of allocated space; subsequent reports and archives are additional. The largest recorded networks had 12 nodes and 60 connections. Minimum available resources during execution were 12.12 GiB of commit headroom, 12.27 GiB of physical RAM, 9.89 GiB on C and 77.09 GiB on E.

A retrospective comparison of the same 80 stages per version gave recorded execution times of 25.69 seconds for /2, 31.65 for /3.1, 42.83 for /5.1, 45.30 for /5.3 and 46.16 for /6.1. Version 6.1 took 1.078× the 5.1 time, below the 2× stop threshold. These recorded stage intervals include within-stage observation and saving but exclude full initialization before a stage. They do not replace the 43.04-minute campaign time.

The read-only audit checked 3,584 complete initial/final states, 192 post-intervention states and 235,712 delivered inputs. Independent integration with 45-digit decimal arithmetic differed from the primary calculation by at most 5.56×10⁻¹⁷. Analysis did not instantiate a running Core or advance simulation. `report_support.py` was added after results to describe integral margins, timings and changed fields; it does not change registered scores. This work is not recorded as reproduction by an external researcher.

Research record: `16c42855-1d4f-5d15-9484-94ca325a2ded`. Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/inertial-reversal61-v1`. `analysis.json` contains block and condition results; `audit.json` records evidence validation; `report-statistics.json` contains retrospective descriptive tables and changed fields. Delivery is confirmed by `publication/completion.json` after complete research-API readback of the archive and reports with pending=0.
