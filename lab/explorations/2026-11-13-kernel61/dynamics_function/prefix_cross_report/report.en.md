# Immediate novelty and legacy connection retention jointly restore prefix discrimination

14 November 2026 · R51t5 · Two exchanged-material blocks; 42 new stages and 30 completed stages reused read-only.

## Scientific conclusion

**Prefix discrimination was restored in the genuine 3.1 and 5.1 implementations when immediate novelty enhancement and legacy connection retention were enabled together.** Changing either option alone failed in both material blocks. Combining them restored correct responses to both A-B and D-B in 2/2 blocks in each version. Adding manual node retention left the scores and response margins unchanged.

This identifies a combination missed by the preceding single-option comparisons. Novelty timing and connection retention jointly affect how a prefix changes the later response. Persistent activity and prefix discrimination also have different requirements: legacy retention had already restored persistence, whereas both rules were needed to restore the appropriate endings in this matrix.

## Question, expectation and design

R51t1 had shown that immediate novelty restored the first version's prefix performance in version 2. Legacy connection retention restored persistence in 3.1 and 5.1, but prefix discrimination still failed. R51t2 then found that A and D still produced different activity in 6.1, while the endings retained a common preference. The present experiment therefore crossed the two historical rule changes.

Each genuine implementation was tested with two novelty timings and three retention configurations. Immediate novelty computes enhancement during that version's declared direct-input processing; arrival-window novelty computes it after the scheduled subsequent arrival window. Legacy connection retention uses the existing `legacy-stability` option and changes both connection strengthening and forgetting. The third retention condition also selects the existing manual node-retention option. Conditions apply from birth, with identical teaching materials, doses and timing.

One curriculum teaches A-B-C and D-B-E; the other exchanges C and E. Teaching lasts 212.2 internal seconds with the original fixed background replay. Complete teaching parents provide separate declared AB and DB diagnostic copies. After a one-second wait, the prefix is delivered, followed one second later by the shared B stimulus and a 15-second observation. Core, input bus, random state and observation history are preserved. Activation, inhibition, direct activity and associative activity are recorded throughout.

The historical rule requires the peak activation of the taught ending minus that of the other ending to exceed 1×10⁻⁶. Both AB and DB must pass within a block. The full matrix contains 12 configurations and 72 stages. Five configurations, comprising 30 stages, already had complete evidence and were reused read-only; seven configurations supplied 42 new stages. The two exchanged-material blocks are the experimental material units; stages and copies are not additional independent samples.

## Results

| Retention | Novelty timing | Restored blocks, 3.1 | Restored blocks, 5.1 |
| --- | --- | ---: | ---: |
| Version default | Arrival window | 0/2 | 0/2 |
| Version default | Immediate | 0/2 | 0/2 |
| Legacy connections | Arrival window | 0/2 | 0/2 |
| Legacy connections | Immediate | **2/2** | **2/2** |
| Legacy connections plus manual nodes | Arrival window | 0/2 | 0/2 |
| Legacy connections plus manual nodes | Immediate | **2/2** | **2/2** |

For the successful combination, the correct-direction AB and DB margins were 0.000977870 and 0.002735633 in 3.1, and 0.000978373 and 0.002735434 in 5.1. Exchanging the curriculum preserved preference for the respective taught endings. Manual node retention did not change these values.

With immediate novelty alone, the 3.1 margins were approximately −0.007445 and +0.007444; with legacy connection retention alone, they were approximately +0.000994 and −0.000994. Each single change left one direction wrong. Changing a fixed preference is therefore distinct from restoring choice conditional on the prefix. Version 5.1 showed the same pattern.

## Interpretation and implications for ThreeMind

**The result supports joint restoration by the two rules and rejects restoration by either change alone in this matrix.** Manual node retention is not an additional requirement here. Subsequent work should focus on the interaction of novelty enhancement, connection strengthening and forgetting, rather than attributing this result to input addressing or node count.

Legacy retention changes more than one local process. The next mechanistic question is which parts of its strengthening and forgetting rules carry the useful effect. No legacy mechanism was added to 6.1 in this experiment; its prefix outcome remains the outcome measured in R51t2 and R51t4. A possible 6.2 should specify a concrete, simple rule change and then identify which earlier mechanisms that change affects.

[Public edition: manuscript editing or private locator omitted.] this finding belongs after the historical experiments: replication exposed a change in ability, isolated restorations failed, and the crossed experiment located a successful combination. Historical versions and the new evidence should retain their identities.

## Verification and delivery

Read-only verification covered 256 complete states, 6,370 new inputs and the new and reused trajectories. Maximum independent arithmetic error was 8.67×10⁻¹⁹. Separate calibration in both versions found identical final states and observation histories with observation disabled, complete save/restore, and a host pause. Scientific execution took approximately 4.03 minutes, with peak private memory approximately 637.99 MiB. The 5/4/5/25-GiB resource reserves were maintained.

Originals: `E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/prefix-cross61-v1`. The manifest, configurations, historical hashes and bilingual reports are closed after complete research-API readback and pending=0, recorded in `publication/completion.json`. The comprehensive campaign remains paused. Production Core, defaults and the manuscript are unchanged.

Before archiving, 937 files occupied 64.79 MiB logically and 66.66 MiB of allocated storage, with no additional hard-link paths. This includes historical references copied into the package, without counting them as new scientific stages, and excludes subsequent archive and API-readback copies.
