# R51t12: separating excitatory and inhibitory connection states

Preregistered on 15 November 2026. The author requested optional separate weights and synaptic resources in 6.2, subsequently approved a separate-learning-record control, and requested a master switch and performance measurements.

The question is whether sharing weights, resources or learning records prevents prefix discrimination, and whether separation restores it while inhibitory learning and both weight-reinforcement switches remain enabled. R51t11 evidence and criteria remain intact.

Each direction remains one connection. Birth/contact rules, source emission, spatial factors, inhibitory amounts, energy, reception and delay retain their equations. Separate weights start equally; co-stimulation and novelty update each by the existing equation, while successful transmission reinforces only its corresponding weight. Weight-only separation retains shared fast enhancement, eligibility, stability, retention scale, decay age, usage count and usage timestamps. The learning-record option separates these states and retains their equations. A connection is deleted only after both weights fall below the applicable threshold; dormancy, awakening and explicit whole-connection interventions remain shared.

Separate resource pools have the original capacity and identical release/recovery constants. Each is consumed only by its own offered signal. Total capacity therefore increases: any benefit supports this specified intervention, without separately assigning it to capacity or consumption isolation.

The master switch `separate_inhibition` defaults to false. Nullable child switches `separate_inhibition_weights/resources/learning` inherit it; explicit child booleans override it. Separate learning requires separate weights; contradictory configurations are rejected. These choices are fixed at birth. Historical artifacts missing the switches retain shared behavior.

## Conditions and materials

Six groups: shared; resources only; weights only; weights plus resources; weights plus learning records; all three. Run each under P (current default inverse-logarithmic single-age retention, arrival-window novelty, connection threshold0.0004) and S (stability retention, immediate novelty, excitatory connection threshold0.004). The inhibitory connection threshold remains0.0004. Source gates remain0.004/0.002. Pre-release checking, local activity expiry, depletion and consolidation remain enabled; facilitation is disabled. Comparisons stay within each profile.

Use the same two exchanged-ending curriculum blocks. Each complete parent receives212.2 internal seconds of continuous teaching, followed by separately registered AB and DB diagnostic copies. The common B follows the prefix by1 second; observe15 seconds at10-ms intervals, including the before/after input boundary, for1502 points. There are72 stages. Branches are nested diagnostic copies, not additional independent subjects. This passive mechanism test has no trainable peripheral, additional correction or altered curriculum.

## Decision and performance

Retain the historical score: after B, the correct ending's activation peak minus the alternative ending's peak must exceed1e-6 for both AB and DB in each block; both blocks must pass to claim recovery. Preserve activation, inhibition, direct and associative activity, traffic, connections and saturation. Answers enter only the scorer.

If any group passes, select the fewest separated components; ties follow the listed group order, with P before S. Test that group and its shared control using code masks0x02000000/0x01000000 and seeds9291251/9291252, adding12 stages. Report the fresh-encoding result separately. If none passes, stop without expanding the parameter search. Maximum84 stages.

Use identical32-node engineering inputs to benchmark the previously installed native6.2, new shared code and six configurations. After warm-up, measure five trials: wall/CPU time, median/range, peak process memory, snapshot bytes and event counts. Shared old/new numerical states and events must agree, apart from declared configuration metadata. Report per-event cost because different dynamics can alter workload. Validate Python/Rust parity, complete restoration, observation frequency, advance partitioning, host waiting and inheritance with separate engineering materials before scientific execution.

## Resources and delivery

Originals cap512 MiB; total incremental storage including archive/readback2 GiB; one scientific host, two-hour limit. A one-second guard reserves5/4/5/25 GiB for commit/RAM/C/E, stopping only at complete stages. Preserve and report incomplete states or invalid originals; do not rerun failed stages or edit frozen running sources. Valid negative outcomes complete the study.

Deliver independently recomputed scores, bilingual scientific conclusions, complete states and ancestry, frozen sources/configurations and performance results. Verify the entire archive through the existing localhost research API with pending=0 before closure. Update bilingual backlog/history and both Classical Chinese adaptations, then perform the Git data check and commit locally without pushing. The broader revalidation and manuscripts remain paused; results do not automatically change defaults.
