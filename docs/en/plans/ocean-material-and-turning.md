# Digestible body material and turning-to-feed candidates

2026-10-04. Additional decisions during E38; original E37/E38 protocols, criteria and evidence remain unchanged.

## A separate environmental version

At199.62 simulation seconds in E38's shared prefix, body15 completely enclosed68 but received zero energy because prey body reserve was empty, while paying about2.25 shell cost. The old environment transfers reserve only. Scarcity can also empty prey reserves and therefore need not favor predation.

The user approved a separate digestible-material rule. `threemind.ocean-enclosure/2` and `threemind.ocean-enclosure-state/2` retain `/1` as the old baseline. This is external apparatus; Core, sensory mapping, motor commands, containment duration and shell rules do not change.

Existing volume/shell construction cost is split between material and dissipated heat. `body_material_fraction` defaults to0.5, configurable from0 to1. This is an explicit engineering starting point, not a calibrated biological constant. Founders pay construction from their ordinary body endowment; insufficient funds cause an error, not free material. Parents already pay offspring construction, so that payment is partitioned rather than charged twice.

On predation, remaining prey body reserve and material pass through the existing assimilation efficiency and predator storage capacity. Loss and overflow are accounted for. Core energy does not transfer. Dead unconsumed bodies retain their material ledger; there is no automatic nutrient regeneration or scavenging. Material is not freely usable self-fuel.

A future causal comparison should pair fractions0 and0.5 within `/2`, holding complete habitats, construction costs, seed and endowments constant. Comparing `/1` directly with `/2` also changes founder construction charging. Long ecological benefit remains untested; mechanical unit calibration is not that experiment.

```powershell
& .work/kernel-venv/Scripts/python.exe -m lab.tools.ocean_material init protocol-v2.json new-world --candidate candidate.tmspecies --candidate-founders 0 1 2
& .work/kernel-venv/Scripts/python.exe -m lab.tools.ocean_material run new-world new-recording --seconds 60
```

The protocol must explicitly identify `/2`. Species bundles retain material accounts; new founders pay construction under the target environment instead of copying stored energy. General graphical habitat deployment remains open.

[Full-habitat protocol template](../../../lab/templates/ocean-material-full-habitat.json) · [Engineering validation record](../../../lab/explorations/2026-10-04-ocean-species/tooling-addendum.md).

## Turning and feeding

The user requested saving individuals that turn to feed, ideally also capable of enclosure consumption. The original quotation is preserved in the [Chinese decision](../../zh/plans/ocean-material-and-turning.md).

`lab.tools.ocean_turning` screens recorded inputs and provides a live passive `TurningObserver`. Its candidate criterion uses the five seconds before an actual nutrient intake: at least30 degrees of water-relative heading change, final alignment with measured local nutrient gradient at least0.7 and improvement at least0.3, actual turn commands with angular velocity of the same sign, relative speed at least1mm/s, and no recorded collision in the window. These are observer thresholds, not neural control limits or an exhaustive definition of feeding. Failure to pass does not establish inability.

Archive the complete habitat, time window, commands, movement and nutrient events as turning-and-feeding candidates. Coincidental circling is not excluded by this observation alone. Reliable ability needs reuse in new environments, sensory controls and internal-mechanism interventions. A single interesting event can be archived without claiming stability. Combined turning/enclosure evidence is attached only when present for the same individual.

Historical records receive derived analysis only. A nearest subsequent living checkpoint is explicitly distinguished from the exact event state. Without such a checkpoint, preserve evidence rather than fabricate a live organism. Future runs can save immediately after a live observer detects an event.

```powershell
& .work/kernel-venv/Scripts/python.exe -m lab.tools.ocean_turning COMPLETED_RECORDING --output NEW_SCREEN_JSON
```

[Library](species-library.md) · [E38 registration](../../../lab/explorations/2026-10-04-ocean-species/design.en.md) · [Research backlog](research-backlog.md)


## 2026-10-04 closeout addition

E38 reached its extension budget boundary. Fourteen turning/feeding snapshots from ten source identities are archived; two repeat episodes hundreds of seconds apart, none also consumes bodies. The new material environment passed full53-founder template initialization/restoration with initial ledger error about5.6e-11. No long selection trial of that version was started. [Complete closeout](../../../lab/explorations/2026-10-04-ocean-species/turning-and-closeout.md).


### 2026-10-04 continuation: three sources together and a proximity-sharing trial

After E38 closed, the user requested joint culture of the two latest repeating turning candidates and a consumer, with improved descendants archived, then added sharing of newly ingested energy among close neighbors. E39–E40 uses17 copies each of E38/44 and59 at900s and15 immediately after consumption, under the approved paid-material rule. A shared300s prefix precedes0/25% sharing forks. Proximity is an environmental transfer condition, with no seeking, attraction or following command and no claim that aggregation is fusion. E38 remains closed; the new budget is independently recorded. The new trial is now running; outcomes are not anticipated here.

[Request, rules and budget](../../../lab/explorations/2026-10-04-ocean-culture/design.en.md).
