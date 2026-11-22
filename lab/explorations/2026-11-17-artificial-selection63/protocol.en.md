# AS63-01: Artificial selection, inheritance, and accumulation in a fixed ring

17 November 2026. Prospective protocol, authorized by the author in this chat. Only this new experiment is authorized; other paused 6.3 revalidations remain paused. Historical E13 selected parents using newborn assessment offspring. Here, assessment copies retain the candidate's complete current state; birth is used only after selecting the actual candidate.

## Questions and apparatus

Assess separately H1 preservation of an observed parental regional tendency through two transmissions, H2 directional selection versus random selection, H3 improvement across generations, and H4 the causal contribution of inherited persistent Core state. All four are expected, but success or failure is determined separately.

Use genuine threemind.continuous-memory/6.3, native Rust for science and Python for instrument comparison. Keep current default dynamics, enabling only the apparatus energy ledger. An explicit reservoir offers one energy unit every 0.1 internal seconds without a total limit; normal expenditure remains. No kernel edits or result-dependent settings.

Ring circumference is normalized to one. Region 0 is [0,0.5); region 1 is [0.5,1). Locations, sensory patterns, and mappings remain fixed for all generations, cultivation, selection, held-out tests and controls. Each region supplies four fixed anonymous channels at amplitude one and intensity 0.8 every second. Velocity direction and magnitude use the historical ring encoding. A region-independent background channel receives intensity 0.2 every 0.5 seconds. All mappings depend on a population seed and are inherited unchanged. The fixed motor adapter computes tanh of 0.5 times the sum of node activations with fixed hashed signs. Mass=1, force coefficient=0.3, drag=0.8, motor step=0.1 seconds. No reward, semantic target or correct action enters the Core. Stillness and circling receive no extra penalty.

Birth uses threemind.birth/2 with decay_age=preserve: retain current persistent node and connection states, including decay age; initialize fast activity, resources and the internal clock using the existing rule. No mutation or recombination. Matched uninherited controls use the same body, peripheral mappings, settings, starting position and procedure but a blank Core.

## Populations and life histories

Sixteen independent populations use seeds 1117100–1117115, without replacement based on performance. Instrument seed 1117099 is separate. Each population starts with four blank G0 individuals at positions 0.125, 0.375, 0.625 and 0.875, velocity zero. Each cultivation or assessment lasts 60 internal seconds.

A complete individual includes Core state, input queue, passive observer state, energy supplier, body, fixed mappings and future sensing/background/motor times. Assessment copies preserve all components and NEVER invoke birth. The only declared measurement intervention sets the copy's starting position and velocity to zero. Original candidates remain untouched, and assessment experience is not written back.

Selection uses starts 0.0625 and 0.5625, averaging the fraction of time in region 1. Held-out starts are 0.1875, 0.4375, 0.6875 and 0.9375; these scores never determine selection. All generations use identical assessment conditions. Occupancy is computed from 0.1-second intervals with a fixed 60-second denominator. Region-0 target score is one minus region-1 occupancy. Preserve trajectories, speed and travel distance. Record death and actual survival separately, never replacing a failed candidate. In a diagnostic copy, the remaining observation period uses passive body physics and zero control if the Core dies. If a breeding candidate dies, preserve evidence and pause its population rather than silently replacing it or breeding from it.

The same four G0 candidates and selection scores seed three arms: select the lowest two region-1 scores for region0, the highest two for region1, or select two by fixed Random(seed+generation). Ties use candidate indices. Selected candidates—not their assessment copies—each produce two descendants. Four descendants form the next generation, with the four cultivation starts rotated by generation. Apply the same procedure through G1 and G2, stopping after G2 assessment. Record all candidates before selection, including descendants that do not retain the parent's tendency.

Every G1/G2 descendant has a separate uninherited control, cultivated identically and given four held-out assessments. Controls do not breed or influence selection.

Per population: 28 cultivated breeding candidates, each with two selection and four held-out assessments; 24 uninherited controls, each with four held-out assessments. This gives 316 stages per population and 5,056 stages overall. There are 64 G0 founders, 384 formal descendants and 384 uninherited controls. Copies and tests are nested observations; independent N=16 populations.

## Decisions and statistics

Average held-out starts within each candidate, then all four candidates within each population/arm/generation. Give populations equal weight. Random-selection scores are expressed separately for each target region.

H1: a parent exhibits a target tendency if its held-out target score is at least 0.55. For each direction and transmission, include every descendant of such selected parents when calculating retention at the same threshold. A population passes dual-direction two-generation retention only if both directions have at least one qualifying parent at each transmission and at least 75% of their descendants retain the tendency. At least 4/16 populations passing establishes repeatable feasibility in this apparatus; report the exact 95% binomial interval and every population, without claiming universal success. Lack of a qualifying parent is not evidence that retention was tested successfully.

H2: compare G2 directional and random arms within each population, separately for both directions. Each mean gain must be at least 0.01 and its Holm-adjusted one-sided P<=0.05.

H3: compare G1−G0 and G2−G1 for each direction using all candidates before selection. Each adjacent-generation gain must be at least 0.01 and adjusted P<=0.05. Report G2−G0 too. Both directions must pass for the complete accumulation claim.

H4: compare G2 inherited and individually matched uninherited descendants, averaging within populations. Each direction requires mean gain>=0.01 and adjusted P<=0.05; both are required for complete H4.

Use eight one-sided exact sign tests jointly corrected by Holm: two H2, four H3, two H4. Absolute differences<=1e-12 are ties; report effective N, positive/negative counts and all differences. Fixed-seed 20,000-resample population bootstrap intervals describe mean uncertainty. Insufficient precision is not evidence of no effect. H1–H4 close separately, without post-result thresholds or additional generations.

## Verification, budget and delivery

Independent instrument checks precede formal subjects: complete-state copying, frequent observation, host pause and whole-system save/restore equivalence; Python/native short-trajectory agreement; persistent-state birth and fast-state initialization; unchanged parent states; fixed regions; selection rules and independent occupancy arithmetic. Instrument outcomes do not select scientific seeds or tune dynamics.

Freeze protocol, code, genuine native binary and population list through the research API before formal execution. Instrument budget: 30 minutes. Science runs serially, maximum six hours. Originals/archive/readback each have 3 GiB; analysis and figures 0.5 GiB. Private process memory cap 1 GiB. Reserve commit/RAM/C/E space of 5/4/5/25 GiB. Pause at complete-population boundaries; preserve interrupted states and in-flight markers. Valid negative results close normally without adding populations or changing rules.

Store originals in ignored .work/artificial-selection63-20261117. Deliver bilingual reports, population/parent–child/selection tables, generation plots, independently audited originals and complete research API readback. Update research backlog and bilingual/classical histories. Do not rewrite old reports or manuscripts, push Git, change kernels or resume other paused studies.
