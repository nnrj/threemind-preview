# R51d: Stimulus grouping, effects of experience, and weak-connection retention in 6.1

13 November 2026. A new replication batch; the original E17 data, report, and kernel identities remain intact.

**The batch confirms that 6.1 retains the mechanisms by which stimulus grouping forms connections, repeated teaching changes connections, and input order affects internal state. The goal of deleting weak background connections within 120 seconds was not met: all 96 weak connections remained in each of the four configurations.** These are separate scientific outcomes.

## Purpose and preregistered expectations

Following E17, we tested connection formation, the effects of experience on subsequent activity, and deletion of weak background connections under fixed-function addressing and the new emission thresholds. Two original anonymous encoding blocks were each tested with the default configuration and with an optional facilitation time constant of one second, yielding 264 conditions. The independent materials comprise two blocks; configurations, causal copies, and probes are nested observations.

All subjects were newly created with kernel 6.1. Inputs came from frozen schedules, random materials, and fixed replays of historical physical recordings. Passive temporal readouts recorded every node's activation, inhibition, direct activation, and associative activation at 100-ms intervals. There was no trainable adapter, naming task, or embodied actuator. Teaching proceeded continuously. Cued, uncued, and retention conditions used separately registered research copies of complete teaching endpoints.

## Results and interpretation

| Preregistered question | Observed result | Scientific conclusion |
|---|---|---|
| Does grouping determine connection formation? | All four configurations passed. New background channels presented individually left only the two original connections. Paired new channels produced 96 background connections, for 98 in total. No connections linked the background channels to the original pair. Complete cart and pendulum inputs produced 6 and 60 connections; splitting them into individual stimulus elements produced none. | Grouping determines connection formation in these materials. Fixed-function addressing preserves this mechanism. |
| Does repeated teaching leave a different internal state? | Total connection weight was zero without teaching, 0.32833–0.32837 after one intensity-4 presentation, and 0.90946–0.90975 after ten intensity-1 presentations. | The teaching histories leave different connection states. The repeated course also has a larger total input dose; this comparison concerns the two complete courses. |
| Does input order matter at equal dose? | Complete and shuffled courses had identical per-channel doses and timestamps. All eight comparisons had the same connection sets but different weights, with summed absolute differences of 0.13691–1.99879. | Input order affects connection weights. This measures the overall sequence effect; the scheduled event-order studies separately control endpoint fast activity. |
| Are all weak connections deleted within 120 seconds while repeated connections survive? | Each configuration retained 96/96 weak and 2/2 repeated connections. The maintenance channel formed no cross-connections. Weak weights were 0.010716–0.012598, above the deletion threshold of 0.008; repeated weights were approximately 0.15475–0.15481. All subjects reached 125.8 internal seconds. | Repeated connections survived, but the 120-second weak-deletion target failed. Recorded weights had not reached the deletion threshold; there is no indication that local deletion missed an expired connection. |

Channel amplitude 1 × stimulus intensity 1 and amplitude 0.25 × intensity 4 have equal products but yielded total weights of 0.21481 and 0.31991. The implemented rules also use stimulus intensity separately, so these input descriptions produce different effects. Full schedules and per-channel doses accompany the originals.

Of 100 nonzero probes, 48 met the frozen activity-pattern convergence rule: 0/24 background, 20/36 intensity, and 28/40 physical-material probes. Each configuration contributed 24/50. This measures temporal response shape, not answer accuracy. Compared with the corresponding uncued copy, all 24 background probes increased activation integrated over non-cue nodes, by 0.01093–0.01226 activation-unit seconds. Thus associative responses occurred even when the specified convergence pattern was absent.

At their recorded endpoints, 150 conditions remained active, 24 were waiting, and 90 had reached network death. These deaths were recorded network outcomes under the prescribed inputs, not host crashes. Process comparisons use only jointly observed time intervals. No weak-background cue was delivered after the 120-second retention period, so the finding there is structural persistence; behavioral expression at that endpoint has no measurement.

## Meaning for ThreeMind and the next decision

The basic connection-formation and experience-dependent state results support proceeding to selective causal tests of learned responses. The negative weak-deletion result continues the previously identified long tail of inverse-logarithmic decay: these default settings do not clear these transient connections within 120 seconds. Subsequent retention studies will measure both structure and cued responses. This batch retains its negative result without changing thresholds, extending teaching, or rerunning subjects.

## Verification, cost, and evidence

All 528 complete initial/final states, 180 parent-copy correspondences, and fixed addresses passed verification. A separate read-only arithmetic calculation projected weights to the recorded endpoints and agreed with the already recorded native metrics to at most 1.85×10⁻¹³. It did not load or advance an individual. Original weight statistics and the first analysis remain intact; the additional check is stored in `arithmetic-verification.json`.

Condition execution totaled 274.38 seconds; the guard-monitoring interval was 418.50 seconds. Before the additional check, originals occupied 108.65 MiB logically and 112.61 MiB in allocated storage, with archives and readback additional; no hard links were used. Peak private memory was 916.61 MiB. Minimum free commit/RAM/C/E resources were approximately 13.92/13.22/10.54/91.91 GiB. No resource stop occurred.

Data: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/stimulus61-v1`. Research record: `d754fa57-f8c3-5c3a-8c7b-2fc6ce1dd142`. The package includes the protocol, complete states, actual inputs, observer state, four activity trajectories, and analyses. The delivery receipt records complete API readback and zero pending requests. Verification was performed internally by the executing assistant.
