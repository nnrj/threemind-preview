# R51t14: Can independent synaptic resources restore prefix discrimination in 6.3?

Preregistered on 2026-11-15, before formal computation. The user authorized separate excitatory and inhibitory resource pools as an option in 6.3 and a prefix test. Shared resources remain the default. The broader revalidation programme remains paused.

## Scientific target

We test whether separate resources restore prefix discrimination while both excitatory and inhibitory transmission continue to reinforce connection weights. The expected beneficial result is a C advantage after AB and an E advantage after DB, with the advantages reversing when the taught endings are exchanged. Increasing only one ending does not meet this target.

The shared condition retains one resource state per directed connection. The independent condition maintains two states, each with available, active and temporarily unavailable resources and its own release fraction. They recover independently under identical parameters, each starting with an available amount of 1. This comparison therefore removes competition between signal types and increases their combined resource capacity. It tests the proposed mechanism as a whole; it does not isolate the contributions of competition and capacity. Inhibition still depletes its own pool.

## Materials and conditions

We retain R51t13's anonymous teaching materials, intensities, timing, process measurement and criteria. There are two material blocks with exchanged endings. Each teaching individual develops continuously for 212.2 internal seconds. Its complete final state is retained as a reference, with registered AB and DB diagnostic copies containing all Core state, random state and pending events. There are no trainable peripherals. These are declared causal diagnostic branches.

Profile P uses 6.3's default inverse-log decay and arrival-window novelty, with excitatory and inhibitory connection thresholds of 0.0004. Profile S uses stability retention, immediate novelty and an excitatory threshold of 0.004; its inhibitory threshold remains 0.0004. Both enable resource checks before release, node sending thresholds of 0.004/0.002, depletion and weight reinforcement by both signal types; facilitation is disabled, and inhibition does not update last transmission time. All remaining birth, teaching and background settings are copied from the frozen materials.

For each profile, we compare per-connection inhibitory transmission and proportional allocation by effective outgoing weight. Each is paired with shared and independent resources. This gives 8 conditions × 2 blocks × training and two diagnostic branches = 48 stages. Within each pair, only `separate_inhibition_resources` differs. Weights, short-term enhancement, retention and learning records remain shared. We neither disable inhibitory learning nor alter thresholds.

Each diagnostic presents A or D, then the same B one second later. Activation, inhibition, direct and associative activity are recorded every 10 ms for 15 seconds, including a pre-presentation point: 1502 observations. A fixed passive rule reads the response. Input codes and scoring answers are kept separate.

## Criteria and bounded follow-up

The original criterion is unchanged: after B, the correct ending's peak activation must exceed the alternative peak by more than 1e-6. Both AB and DB must pass for a material block to pass; both blocks must pass to declare restoration in that configuration. C/E peaks, margins and direction are reported. The primary comparison is independent versus shared resources in P with per-connection transmission. Results under S or proportional allocation are labelled separately.

If an independent-resource condition passes, we select one in the fixed order P before S and per-connection before proportional allocation. It and its matched shared condition then receive two new encodings and birth seeds, adding 12 stages. The codes are XORed with 0x02000000/0x01000000 and seeds are 9291251/9291252. Original-material and new-encoding outcomes are reported separately. If none passes, the batch ends without further parameter search. The maximum is 60 stages, and negative findings complete the batch normally. No default changes are automatic.

R51t11's archived positive result is a read-only historical reference. That configuration also bypassed resources for inhibition and disabled explicit inhibitory learning and the inhibitory connection threshold. It is neither this independent-resource condition nor the 6.3 default. New shared-condition numerical states must agree with the corresponding R51t13 states, excluding new configuration metadata. Historical originals are neither changed nor rerun.

## Engineering, resources and delivery

Independent apparatus materials must give identical full states with observation, save/restore, partitioned advancement and wall-clock pauses. Python, native Rust and the standalone runtime must agree. Shared operation is checked against the prechange 6.3 binary. Earlier artifacts lacking the new option retain shared behavior. Resource mode is selected at birth.

The performance benchmark uses the same 32-node, 60-internal-second course, one warm-up and five measured repetitions per condition. It compares old shared 6.3, new shared 6.3 and independent resources, reporting time, peak memory, complete-state size and event count. Implementation overhead under identical dynamics is distinguished from a change in scientific workload.

Originals are capped at 512 MiB; originals, archive, research API readback and analysis together at 2 GiB. Scientific hosts run serially, with a two-hour boundary limit and a 300-second per-stage boundary stop. A one-second guard reserves 5/4/5/25 GiB of commit/RAM/C/E capacity. Incomplete states, disturbed observation, unverifiable originals or insufficient resources cause preservation and a stop, without unauthorized recovery.

After independent rescoring and complete-state-chain verification, deliver Chinese and English reports with explicit conclusions. Close only after full API readback and zero pending requests. Update the research backlog and history and commit locally without pushing. Historical data, manuscripts and other kernel versions remain unchanged.
