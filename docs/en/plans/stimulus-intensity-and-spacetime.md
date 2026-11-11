# Stimulus intensity, backgrounds and embodied senses

[中文](../../zh/plans/stimulus-intensity-and-spacetime.md)

2026-09-30. Implementation, engineering acceptance, bounded experiments and subsequent Transformer GPU/CPU acceptance are complete. Baseline: Git `6241016`; old V3 audit: `97d8592`. Evidence and remaining research questions are linked in the delivery section.

## Decisions and boundaries

Ordinary text intensity is 1; the strong preset is 4; the accepted range remains 0–100. Presets do not change normalization, framing or receptor mapping. New consciousnesses retain continuous-memory/2, arrival-window novelty, gain .018 and reference .2. Ordinary facilitation stays off. The explicit research preset only changes `stp_facilitation_tau_s` to 1 second.

Retain forgetting, inhibition, local resource expenditure/recovery, propagation thresholds and simulation timing. Historical identities, states, mappings and evidence remain unchanged; creation defaults do not govern restoration.

Proprioception is a peripheral, like any other sense: environment/body → sensory adapter → input bus → Core → output bus → actuator adapter → environment. Core must not read world state, gravity vectors, semantic labels or device names. It remains independent of MuJoCo, UI and databases. Any necessary Core interface or dynamical change requires discussion first.

Physical measurements, encoded drive, received touch and actual activation increment are distinct. No new plastic receptor layer this period. A callus changing transduction is physically meaningful; the current different consolidation for `1×1` versus `.25×4` despite equal drive is a separate intensity term, not evidence of a callus mechanism. Preserve this baseline for later study.

## Hypotheses and open questions

Forgetting is as important as remembering. Short memory loss and subthreshold retrieval with surviving connections are not automatically defects. Forgetting as a contributor to attention remains a hypothesis. Strong-input and novelty effects might emerge from more elementary local mechanisms; the present formula is not established biology. Meanings belong to relations and processes formed inside an instance, not observer labels. Physical references may support temporal/spatial distinctions, while internal-state timing remains possible. Threshold sensitivity may be normal nonlinearity or an implementation defect; do not tune it to manufacture an outcome.

Independent random controls, correlated synthetic backgrounds and physical telemetry are different sources. The existing synthetic field reuses fixed channels and repeatedly samples transients during their lifetime. It is not independent one-shot noise.

## Implementation and acceptance

Freeze source hashes and small state/sensory witnesses; add shared strength presets, optional read-only diagnostics, an explicit facilitation preset and per-scope telemetry intensity (.2 for creation; 1 for legacy). Audit V3/current background connectivity, clamps, filtering, identity reuse and display separately. Add opt-in restorable random controls without graph access or background-specific deletion.

External protocol `threemind.stimulus-unit/1` defines an element, a declared joint-observation group, a carrier and an event stream. It compiles to existing anonymous Stimulus values. Never merge unrelated sources just because timestamps coincide. Reuse API/CLI/UI queues and provenance.

World/state v2 add body-local accelerometers and gyroscopes plus inertial-cart and gravity-pendulum templates. Preserve v1 compilation and replay. Physics 5 ms and sensing 20 ms do not change Core propagation. Validate physical reference frames, free fall, supported rest, rotation, exact restoration, Python/Rust behavior and desktop/mobile interaction before observations.

Primary readout remains activation ranking at the end of a convergence window; retain trajectories, no-cue and behavioral controls. Do not fabricate a convergence when none occurs. Compare ordinary and 1-second facilitation presets; independent/repeated/synthetic/physical backgrounds; histories and strengths; intact/no-proprioception/split/shuffled/untrained physical observations. Discriminating sensory sequences alone does not establish subjective time.

Limits: 384 new instances, 90 simulation wall-clock minutes, one worker, process RSS ≤4 GiB; evidence soft/hard limits 3/4 GiB; available RAM ≥2 GiB, free C/E storage ≥5/15 GiB. Account usage +3 percentage points stops expansion, +5 stops new simulations, counting shared usage conservatively. Never clean or overwrite old evidence.

Deliver bilingual design/results in an independent research project, then validate existing Transformer GPU tasks and CPU fallback. No Core GPU port in this period. Stage local commits; no push.

## References and original discussion

[Synaptic tagging](https://pubmed.ncbi.nlm.nih.gov/9020359/), [novelty modulation](https://www.nature.com/articles/nature19325/), [state-dependent timing](https://pubmed.ncbi.nlm.nih.gov/17270738/) and [MuJoCo sensor definitions](https://mujoco.readthedocs.io/en/stable/XMLreference.html#sensor-accelerometer) motivate mechanisms; none validates the current ThreeMind formula by itself.

The original Chinese discussion is preserved separately in the Chinese plans directory; its translation accompanies this document. See the implementation/experiment report for verified outcomes rather than treating intentions as results.


## Delivery

Stimulus, background and inertial tools have passed engineering and bounded-experiment verification. See [implementation](stimulus-spacetime-implementation.md), [results](../../../lab/explorations/2026-09-30-stimulus-spacetime/report.en.md) and [database verification](../../../lab/explorations/2026-09-30-stimulus-spacetime/delivery.en.md). [Real Transformer GPU tasks and CPU fallback](transformer-gpu-acceptance.md) also passed acceptance.
