# Bodily responses depend on persistent connections and current state

14 November 2026, R51s. This E22A replication follows comprehensive revalidation plan v2 with frozen kernel 6.1, transmission threshold 0.0004, deletion threshold 0.008 and inverse-logarithmic decay.

**Connection weights formed during bodily teaching have a causal effect: transferring them moves response magnitude toward the donor. The recipient's retained current state also affects expression. All 12 conditions tested 10, 30 and 60 seconds after teaching retained the taught direction in 4/4 material blocks, with 96/96 cued diagnostics passing. Both preregistered targets were met, and no stopping condition was triggered.**

## Purpose and design

R51r established that depletion during teaching changes later bodily responses. R51s asks how much of that difference is carried by transferable persistent state and how subsequent waiting affects expression. Both teaching conditions taught the same bodily-direction associations; this study examines their differences in response magnitude.

Four anonymous material blocks, 930101–930104, each supplied full sensory and joint-only conditions with teaching depletion disabled or enabled. The 16 complete R51r references were saved at 20.2 internal seconds, one second after teaching. They retain the Core, input bus and observer. Teaching was not repeated. Depletion and local input competition were enabled during all tests.

The two teaching conditions within each material and sensory block served reciprocally as donor and recipient. Three state groups were exchanged in all eight combinations: connection base weights W, connection history S and node history N. S includes decay age, retention scale and connection-use records; N includes node support and history fields. Recipient activation, inhibition, fatigue, synaptic resources, short-term states and in-flight signals were retained. Derived deletion timers were updated by the existing rule and recorded. Production kernels were unchanged.

Each combination received two bodily directions and matched uncued controls, giving 512 diagnostics. The 16 unexchanged references also supplied independent waits to 10, 30 and 60 seconds after teaching, followed by the same direction-and-control tests: 48 holding stages and 192 diagnostics. The total was 752 stages and 704 diagnostics. The replication unit remains the four material blocks.

Each diagnostic contained 0.6 seconds of bodily input followed by five seconds of observation. Activation, inhibition, direct activity and associative activity were recorded every 20 ms. The primary net response margin integrates activation over all 5.6 seconds, subtracts the matched uncued trajectory, and subtracts the other target from the taught target. Positive and negative values denote taught and reversed directions. Post-input integrals, raw trajectories, peaks and final values are retained separately.

The preregistered weight criterion required a same-signed effect exceeding 1e-6 activation-seconds in at least 3/4 blocks for at least one full-sensory recipient condition. Each waiting condition required both directions to favor the taught target in at least 3/4 blocks. Donor–recipient separability, response-distance measures and partial-transfer thresholds were fixed before execution.

## Weights transfer response differences

With full sensory input, W-only exchange increased the mean net margin by 0.008727136 activation-seconds in recipients taught without depletion and reduced it by 0.008787815 in recipients taught with depletion. Both effects had the same direction in 4/4 blocks. The initial mean donor–recipient difference was 0.012420294 activation-seconds and was identifiable in both conditions. The causal weight effect was confirmed.

Each cell below averages four blocks and two bodily directions, in activation-seconds. All 256 cued exchange diagnostics retained the taught direction.

| Exchanged state | Full: teaching depletion off | Full: teaching depletion on | Joint only: off | Joint only: on |
|---|---:|---:|---:|---:|
| Sham | 0.025642311 | 0.038062605 | 0.107355524 | 0.065079291 |
| N | 0.025642303 | 0.038062605 | 0.107355524 | 0.065079291 |
| S | 0.025642592 | 0.038062480 | 0.107355714 | 0.065079459 |
| SN | 0.025642583 | 0.038062480 | 0.107355714 | 0.065079459 |
| W | 0.034369447 | 0.029274790 | 0.105298412 | 0.066519566 |
| WN | 0.034369444 | 0.029274792 | 0.105298412 | 0.066519566 |
| WS | 0.034370017 | 0.029274761 | 0.105298744 | 0.066519660 |
| WSN | 0.034370014 | 0.029274764 | 0.105298744 | 0.066519660 |

All 128 diagnostics in the four W-containing combinations met the preregistered partial-transfer definition: responses moved closer to the donor but remained more than 1e-6 away. N, S and their joint exchange produced changes below that threshold. Together with 32 sham diagnostics, these other 128 diagnostics were classified as not closer to the donor. Field changes and subthreshold raw differences are retained.

Even after W, S and N were exchanged together, mean distances from donor responses were 0.003985052 and 0.003632452 activation-seconds in the two full-sensory recipient conditions, and 0.040219453 and 0.040835864 in joint-only conditions. None reproduced the donor's complete response. Persistent state then came from the donor, while recipient current state and in-flight signals remained. This supports the prespecified interpretation that **persistent connections retain teaching effects, while current internal state helps determine their expression.** The contributions of individual current-state components were not separated in this batch.

## Expression survives waiting

All 12 waiting conditions passed: 4/4 blocks and 8/8 direction diagnostics per condition. Waiting retained the original fixed inputs and existing local-update rules. Earlier tests did not rehearse later cohorts.

| Sensory condition | Teaching depletion | Wait (s) | 6.1 net margin | Historical margin | Passing blocks |
|---|---|---:|---:|---:|---:|
| Full | Off | 10 | 0.013689811 | 0.006063556 | 4/4 |
| Full | Off | 30 | 0.012874215 | 0.006145992 | 4/4 |
| Full | Off | 60 | 0.011886122 | 0.001367486 | 4/4 |
| Full | On | 10 | 0.021462934 | 0.011523773 | 4/4 |
| Full | On | 30 | 0.019372015 | 0.011543701 | 4/4 |
| Full | On | 60 | 0.017421423 | 0.011479027 | 4/4 |
| Joint only | Off | 10 | 0.099865950 | 0.104655165 | 4/4 |
| Joint only | Off | 30 | 0.083754182 | 0.103493885 | 4/4 |
| Joint only | Off | 60 | 0.071767518 | 0.098911418 | 4/4 |
| Joint only | On | 10 | 0.097764842 | 0.104638220 | 4/4 |
| Joint only | On | 30 | 0.081985653 | 0.103387060 | 4/4 |
| Joint only | On | 60 | 0.070311266 | 0.098705624 | 4/4 |

The historical column comes from original E22 evidence, whose 12 cells also retained the taught direction in 8/8 diagnostics. Kernel 6.1 reproduced this retention result. Full-sensory margins were larger than historical margins at the tested times; joint-only margins were smaller while retaining the correct direction. Current margins decreased with longer waits. The retained ability and sensory-dependent magnitude changes are both reported.

## Meaning for ThreeMind

R51s locates part of the teaching effect found in R51r in persistent connection weights: exchanging those weights causes consistent response changes. This is causal support for experience organizing behavior through connections. Partial transfer also shows that expression depends on established connections together with current activity conditions, giving complete-state and in-flight-signal preservation an empirical role. Waiting tests establish continued expression of bodily associations over the tested 10–60-second interval.

Both targets were met. Defaults remain unchanged, and original-scale E12 and subsequent revalidation continue. This routine positive result does not pause the campaign.

## Verification, cost and evidence

The independent apparatus passed same-source identity and native restoration for all eight exchanges. Five observation, restoration and pause modes produced identical final states for four representative references. Formal analysis created and advanced no Core. It verified 2,352 complete states, 128 exchanges, 752 stages and 17,888 inputs. All 64 sham comparisons exactly matched R51r inputs, four-field trajectories and final states. Independent 45-digit decimal integration differed by at most 2.77556e-17.

Scientific execution took 21.60 minutes; peak private memory was 669.57 MiB. Before analysis, originals occupied 376.55 MiB logically and 403.11 MiB of actual allocation, including apparatus and frozen materials. Formal unit allocation was 1.420–1.715 times corresponding historical allocation, below the frozen review threshold.

Workspace: E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/body-recovery61-v1. Research record: 29b91273-2889-53d2-8f36-2334a8e4284b. Protocols, trajectories, exchange details, inputs, lineage and reproducible analyses are delivered as one original package. The API readback receipt is stored in publication/completion.json. Arithmetic verification is a read-only tool calculation; external independent reproduction is recorded separately. Historical originals, conclusions and the author's manuscript remain unchanged.
