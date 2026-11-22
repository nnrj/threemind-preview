# R63t2: Replicating sustained activity with inhibition and prefix discrimination

Prepared on 16 November 2026. Registration follows verified closure of R63t1. This batch retains R51t2's two exchanged curriculum blocks, 22 additional configurations, and 110 stages. Production Core and defaults remain unchanged.

We test whether existing inhibition-strength, inhibition-decay-time, and synaptic-resource settings can maintain task activity through a 300-second wait at low activation levels, while inhibition remains enabled. We also test whether novelty timing, transmission thresholds, and context settings allow AB and DB to favor their respective learned endings. Historical 6.1 recovered low-amplitude sustained activity when the inhibition time constant was reduced to one quarter, but none of these prefix candidates recovered discrimination. This batch tests those findings in 6.3.

## Experimental organization

Sustained-activity copies inherit the complete 81.2-internal-second teaching endpoints of the two new R63t1 6.3 individuals, while activity is still present. Each copy retains Core, random state, input bus, and readout history. Only registered parameters change, followed by 300 seconds of the original background inputs without task prompts.

Inhibition strengths 0.24, 0.06, and 0.015 are crossed with 1, 1/2, and 1/4 of the original 0.2321354823145728-second inhibition time constant. The default reference has already been run in the new R63t1 batch and is verified before reuse; the other eight conditions run here. At strength 0.06 and half the time constant, three further conditions enable depletion, disable short-term facilitation, or combine both changes. Each of these 11 additional configurations has two blocks, a waiting stage, and a 15-second diagnostic stage: 44 stages in total.

The historical sustained-activity apparatus disables depletion and enables one-second facilitation and connection reinforcement. These are explicit experimental settings, not the complete 6.3 defaults. Unchanged teaching references are retained. Same-time state settlement caused by reconfiguration is recorded field by field.

Prefix conditions begin with blank individuals and continuously follow the original 212.2-second A–B–C/D–B–E curriculum and its C/E-exchanged counterpart. Novelty timing (arrival window or immediate), connection-signal threshold (0.0004 or 0.004), and input-context mixing (1 or 0) form eight conditions. The default and immediate-only conditions come from new R63t1 evidence, while the other six run here. Five further immediate-novelty conditions disable inhibitory reinforcement, set inhibition strength to 0.06 or 0.015, halve the inhibition time constant, or disable short-term enhancement. Two blocks each undergo teaching and separate AB and DB diagnostic copies, totaling 66 stages.

Teaching remains continuous. Diagnostic copies preserve complete state and do not overwrite reference experiences. There is no peripheral requiring training. Backgrounds, review intervals, stimulus strengths, and the one-second wait and cue interval follow the original case table. Two blocks remain two blocks; configurations, copies, and the 110 stages are not additional independent samples.

## Criteria and interpretation

Activation, inhibition, direct activity, and associative activity are recorded as processes. Sustained activity requires maximum task-node activation above 10⁻⁶ at every 10-ms sample of the 15-second window following the 300-second wait. Both blocks must pass for recovery. Last nonzero time and the fraction of recorded task-node observations with activation at least 0.95 are also reported; a fraction above 10% indicates saturation risk. The denominator is node observations, not worlds or the fraction of time for which the whole network is saturated.

Prefix scoring retains the original peak difference from the second cue onward: the taught ending's activation peak minus the other ending's peak. Both AB and DB must exceed 10⁻⁶, in both blocks, for recovery. Areas are independently recalculated with high-precision arithmetic without replacing the peak criterion. Complete states around the shared B stimulus preserve evidence about surviving prefix differences and subsequent ending selection.

If a later functional study needs a candidate, the original selection rule applies. Prefer conditions retaining inhibition, passing persistence, and remaining at or below 10% saturation. Rank by the worse block's saturation fraction, then by fewer changed default fields, then by frozen case order. If none pass, select the longest-lasting condition without saturation risk and explicitly report failure of the persistence target. Prefix candidates rank by passing blocks, worst correct-direction margin, and fewer changes. Candidate selection precedes a separately registered functional study; longer activity is not scored as improved decision performance.

Historical positives falling below 2/2, or previously acceptable saturation exceeding 10%, are new adverse differences requiring preservation and discussion. Repeated prefix negatives are delivered normally before other authorized work continues. The configuration set is bounded, and default changes require a separate decision.

## Apparatus and delivery

Preparation checks compare all 110 definitions and 22 historical configuration scores, with representative sustained and bidirectional-prefix processes recalculated from originals. Apparatus uses different encodings and a separate seed to compare observation, complete save/restore, and a host pause; complete Core endpoints and readout histories must agree. Historical data remain read-only. Current references come from new R63t1 individuals, not substituted historical 6.1 results.

Originals, archive, and API readback each have a 2-GiB allowance, plus 128 MiB analysis and a separate 25-GiB E: reserve; startup needs at least 31.125 GiB free. One-second checks reserve 5/4/5/25 GiB for commit/RAM/C:/E:, with 1-GiB private memory, 300 seconds per stage, and a two-hour host limit. Apparatus calibrates allocation against equivalent historical records. Twice the historical unit allocation, a 50% frozen-budget overrun, or insufficient resources causes a pause at a complete boundary. New orphaned in-flight states are preserved and reported.

Read-only auditing covers 770 complete states, 16,940 inputs, lineage, and all recorded processes. Bilingual reports give distinct conclusions for sustained activity, selectivity, and prefixes, and explain their meaning for ThreeMind. Closure requires full research-API package readback and pending=0. [Public edition: manuscript editing or private locator omitted.]
