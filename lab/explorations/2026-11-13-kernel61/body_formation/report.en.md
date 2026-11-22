# Local mechanisms have distinct effects on the formation and expression of bodily experience

14 November 2026, R51r. This E21C replication follows comprehensive revalidation plan v2 using the frozen 6.1 kernel. The signal-transmission threshold remains 0.0004, the deletion threshold 0.008, and inverse-logarithmic decay remains enabled.

**Synaptic-resource depletion and local input competition affect both the state formed during teaching and its expression during testing, but their effects differ between stages. With full sensory input, enabling either mechanism during teaching strengthens the taught-direction response, whereas enabling either during testing weakens it. With joint signals alone, both teaching effects become negative. All 256 cued diagnostics nevertheless express the taught direction.** Both primary targets were met; no scientific stopping condition was triggered.

## Question, design and decision rules

R51m established that raising the transmission threshold restores the historical reversed inertial response in 6.1. R51r retains the default configuration and separates effects during formation from effects during expression. Before execution, we expected the all-on reference to reproduce R51m's taught-direction response and at least one local-mechanism contrast to show a consistent effect across material blocks.

The original four anonymous material blocks, 930101–930104, were retained. Full sensory input or joint signals alone were crossed with depletion and competition during teaching, producing 32 teaching references. Each underwent 32 consecutive bodily-teaching segments of 0.6 seconds, followed by a one-second wait, reaching internal time 20.2 seconds. Bodily signals were replayed from saved physical simulations with their original timing.

Each reference supplied 16 registered diagnostic copies: four test-switch combinations, two physical directions, and a bodily cue or matched uncued condition. The 512 diagnostics comprise 256 cued tests and 256 uncued references. Target A/B labels were absent from testing. The four material blocks are the replication units; teaching references and diagnostic copies are nested conditions.

The depletion switch determines whether release reduces available synaptic resources. When disabled, available resources are reset to one before and after release, while utilization and other implemented states remain. The competition switch controls local competition when signals are received. Test settings were changed through the existing API at the same internal time, including an identical configuration call for unchanged references. The API also settles state at that time and updates relevant timers; all resulting field changes were recorded.

A passive process readout recorded activation, inhibition, direct activity and associative activity every 20 milliseconds. The primary measure integrates activation over the full 5.6-second diagnostic, subtracts the matched uncued integral, then subtracts the other target from the target corresponding to teaching. Units are activation-seconds. Each physical direction was scored separately. A margin above 1e−6 indicates the taught direction and below −1e−6 the reverse. Mechanism effects average the two directions within each block and compare on minus off. Consistent effects require the same sign and magnitude above 1e−6 in at least three of four blocks. The post-input interval, 0.6–5.6 seconds, is reported separately for comparison with R51m. [Preregistered protocol](protocol.en.md)

## Primary findings and conclusions

| Preregistered target | Criterion | Result | Scientific conclusion |
|---|---|---|---|
| Reproduce the default taught-direction reference | Both directions pass in at least 3/4 blocks for each sensory condition | 4/4 in both conditions | Default 6.1 reliably retains the taught direction in this bodily task |
| Locate local-mechanism effects during teaching and testing | At least one of eight primary contrasts has a consistent effect | 8/8, each agreeing across 4/4 blocks | Both mechanisms have causal effects at both stages; their direction depends on stage and sensory input |

The following values are mean on-minus-off changes. Positive values strengthen the taught-direction response; negative values weaken it. Within each cell, the four block differences agree to the displayed precision. Full values are retained in analysis.json.

| Comparison, with the other three switches on | Full sensory input | Joint signals only | Agreement across blocks |
|---|---:|---:|---|
| Depletion during teaching | +0.012420294 | -0.042276234 | 4/4; 4/4 |
| Local input competition during teaching | +0.004898691 | -0.000568630 | 4/4; 4/4 |
| Depletion during testing | -0.078241745 | -0.260982345 | 4/4; 4/4 |
| Local input competition during testing | -0.146794464 | -0.070177632 | 4/4; 4/4 |

With full sensory input, enabling depletion during teaching adds 0.012420294 activation-seconds and enabling competition adds 0.004898691. During testing, enabling depletion or competition instead subtracts 0.078241745 or 0.146794464. **A mechanism's effect during teaching therefore cannot be inferred from its effect during testing.**

With joint signals alone, teaching depletion and teaching competition contribute −0.042276234 and −0.000568630 respectively: both signs reverse relative to full input. Test-stage effects remain negative. **How a local mechanism changes experience-dependent expression depends on when it acts and which bodily signals the individual receives.**

## All conditions and interactions

Each matrix cell is the mean margin over four blocks and two physical directions, after subtracting the corresponding uncued references. Digits denote depletion followed by competition: zero is off, one is on.

Full sensory input:

| Teaching depletion/competition | Test 00 | Test 01 | Test 10 | Test 11 |
|---|---:|---:|---:|---:|
| 00 | 0.302096846 | 0.051452778 | 0.135487758 | 0.025231019 |
| 01 | 0.420691880 | 0.060072239 | 0.171054521 | 0.025642311 |
| 10 | 0.321580422 | 0.086314580 | 0.191288839 | 0.033163914 |
| 11 | 0.375716194 | 0.116304350 | 0.184857069 | 0.038062605 |

Joint signals only:

| Teaching depletion/competition | Test 00 | Test 01 | Test 10 | Test 11 |
|---|---:|---:|---:|---:|
| 00 | 0.575287472 | 0.248980329 | 0.168863861 | 0.089574861 |
| 01 | 0.968774196 | 0.309882144 | 0.213501812 | 0.107355524 |
| 10 | 1.167157972 | 0.323895812 | 0.135667249 | 0.065647921 |
| 11 | 1.229334286 | 0.326061635 | 0.135256923 | 0.065079291 |

All 256 cued diagnostics in the 32 cells expressed the taught direction. All 64 preregistered single-factor contrasts, including the eight primary contrasts, showed consistent effects, as did all 16 interactions. An interaction means that one mechanism's effect depends on the state of the other, measured by a within-block difference of differences. With both test mechanisms enabled, the teaching-stage interaction was +0.004487398 for full input and −0.018349293 activation-seconds for joint signals alone. The two mechanisms do not contribute fixed additive corrections.

All-on teaching and waiting hashes match their R51m references. All four activity measures agree exactly at common sample times. Post-input margins for the two directions were 0.024777941 and 0.025417647 with full input, and 0.040119830 and 0.041040971 with joint signals alone, passing in every block. The prior default reference was reproduced without changing the observation window to obtain a new response direction.

## Meaning for ThreeMind

This experiment supports the claim that local mechanisms organize experience-dependent activity. It separates two causal roles: teaching configuration changes the state left by experience, while testing configuration changes how that state is expressed. Their opposite signs with full sensory input show why a mechanism that suppresses an immediate response need not impair formation of an experience-dependent response. The reversal of teaching effects after inertial inputs are removed also demonstrates that bodily input composition changes the role of those mechanisms.

Both targets are closed. Depletion and competition act during both formation and expression in 6.1, with effects jointly determined by stage and sensory conditions. The planned E22 state-exchange and waiting experiments will locate which saved states carry these differences.

## Evidence, instrument checks and resources

Read-only verification passed for 1,632 complete states, 32,544 inputs, 544 stages and 512 intervention records, checking genuine 6.1 identity, fixed-function addressing, state continuity, input content and timing. Independent 45-digit decimal integration differed from ordinary integration by at most 2.220446049250313e-16. Analysis created and advanced no individuals.

In the independent apparatus check, all eight groups produced identical final Core hashes under normal observation, no observation, lower-frequency observation, complete save/restore and a host pause. An unchanged-configuration API call differed from no call by at most 1.01644e−20 in the measured process. Both uncued enqueue schedules produced identical final states and activity. Formal API settlement had zero same-time projection error.

Before formal execution, full-input trajectory storage exceeded the comparison limit and was reviewed. Lossless XZ level 1 encoding reproduced all 48 apparatus trajectories byte for byte after decompression; original gzip files were retained. Sampling, numerical precision, complete states and curricula were unchanged. [Storage amendment](storage-amendment.en.md)

Scientific execution took 972.37 seconds (16.21 minutes), with peak private memory 650.79 MiB. At analysis, logical storage was 284.53 MiB and actual allocation 300.02 MiB. Unit allocations were 1.235–1.905 times their historical counterparts, below the twofold review limit. All resource reserves were maintained, with no STOP or dead-host in-flight state.

Originals are at E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/body-formation61-v1, research record 2a8234ce-4314-5b5d-8add-8af1df49da62. analysis.json contains every result and R51m comparison; audit.json records verification. originals.zip, manifest.json and publication/completion.json hold the archive, member list and complete API-readback receipt. Closure requires verified coverage and pending=0. This is an internal project replication; historical originals and conclusions are preserved.
