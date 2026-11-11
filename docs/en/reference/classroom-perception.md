# Classroom vision and pointing tools

These research peripherals use the existing input and output buses without changing Core dynamics. See the [E56 plan](../plans/vision-correction.md). Available tools do not imply mastery of the classroom tasks.

## Optical sampling

`DetailedClassroom` in `lab/tools/classroom_eye.py` uses `threemind.grounded-classroom/2`. Each of four fixed visual fields can sample a 4,6,8,12 or16 square grid, carrying MuJoCo ray depth and RGB. All four objects remain present. The viewer's schematic icons are not Core's visual input.

The 4×4 configuration preserves legacy ports and values. Denser grids use distinct anonymous ports and per-channel gain `0.03 × 16 / resolution²`, preserving total angular gain. Sampling locations, receptor count and local incident amounts still change; this is not identical input. Body position, velocity, contact, wind, temperature, humidity, inertia and gravity-support channels and physics remain unchanged.

`state()` and `restore()` retain resolution and physical state. Legacy `/1` is not upgraded. Observer labels do not affect stimuli. Estimate graph and storage cost before increasing resolution.

## Selection and movement

Both external readers consume raw activation, inhibition, direct and associative touch over time. Neither subtracts an unprompted copy nor rescales each trial. Teacher labels are allowed during fitting. Inference accepts no query text, object name or correct coordinate.

- `ActivityController` jointly reads registered ports and scores four endpoints.
- `SpatialChoice` applies the **same reading function** to each physical visual field, alongside the same nonvisual activity. It uses the eye's existing physical layout, without assigning Core brain regions or adding semantic tags. Its protocol is `threemind.spatial-choice-reader/1`.

The shared layout is an external architectural choice, not emergent Core organization. A supervised reader can itself learn part of the task; improved accuracy still requires separate tests of dependence on Core experience and connections.

A servo executes the decoded endpoint using body position and velocity. It never receives the scoring target. Record object-selection correctness, arrival at the selected endpoint, and arrival at the requested target separately. This distinguishes selection failure from execution failure; servo skill is not newly learned Core ability.

## Operations and evidence

See [E56 commands](../../../lab/explorations/2026-10-06-vision-correction/README.md) for bounded teaching, calibration, correction, confirmation and recorded replay. Sources, branches and resolutions are stored separately. Replay labels actuation provenance so wind or teacher forces are not mistaken for autonomous commands.

E56's new reader was proposed after inspecting earlier formal scores. Re-reading those records gives development results; disjoint confirmation is required. Multiple questions restored from one consciousness are not independent consciousness samples.
