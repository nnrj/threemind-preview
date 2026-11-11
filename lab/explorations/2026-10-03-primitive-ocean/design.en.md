# E28: nutrient contact, finite energy and a plankton population

Registered 2026-10-03, before formal trials. The user proposed a gradual alternative to the difficult arm task: contact-based feeding, survival, reproduction, then conditional mutation and predation. E27 and all previous evidence remain unchanged.

## Apparatus and boundaries

Use ordinary `continuous-memory/2` with finite energy and starvation damage. Do not change its propagation, forgetting, inhibition, novelty, facilitation or strong-input equations. This is a 0.3 m periodic **planar, neutrally buoyant slice**, not an Earth-ocean reconstruction. Mass and inertia follow spherical radius; linear drag is -6πμrv and rotational drag -8πμr³ω. Constant-force substeps integrate these equations analytically. Uniform water flow and unresolved small-scale mixing move nutrient particles. Neutral buoyancy cancels vertical gravity. Soft envelopes may overlap; phase one has no predation or contact injury. This new external apparatus does not use the arm's rigid-body solver. Mechanical work in joules remains separate from Core's experimental energy units.

Physics advances every 5 ms, sensing every 20 ms. Four body-local chemical concentrations, relative water velocity, angular motion, orientation relative to a physical reference axis, contact and energy stores become anonymous signed channels with fixed scales. There are no object names, global food coordinates, correct-action labels or absolute-time answers. A fixed nonsemantic hash projection maps activity into two planar forces and one torque, as an external wiring assumption, not evidence of emergent motor specialization. No live computer telemetry is used.

Initially 160 particles, capacity160, at most one new particle every5seconds globally regardless of population. Contact awards a particle once, to the closest body; exact ties rotate. Only physics determines acquisition.

## Energy and reproduction

A distinct engineering seed measures per-second Core expenditure r during the last10seconds of a30second calibration. Freeze initial reserve240r, Core/storage capacity960r, nutrient value30r. This supplies roughly four minutes of the calibrated load, not a fixed death age. Food enters a body store and is delivered through the existing energy port to replenish spent initial reserve. After60seconds of age/cooldown, a parent may pay180r to the child and30r reproduction loss while keeping180r stored food. Offspring inherit persistent `birth/1` structure but explicitly start with zero free Core energy, then receive the deducted180r. This initialization extension is `ocean-birth/1`; parent brain state and Core dynamics remain unchanged. Audit the complete energy balance, including waste and archives.

Only existing Core inactivity determines consciousness death. Observational deadlines pause and save living instances. Population16 and32births per world are computing limits that defer reproduction, never deaths. Preserve dead states and residual reserves.

## Comparisons and stage gate

Phase one: three independent world/wiring seeds,8founders each, Core-driven/passive/random-action variants,900simulated seconds or actual extinction:9worlds. Controls retain the same Core, sensing and energy accounting. Random actions are held for1second and do not track food. Record ingestion, descendants, death, energy, displacement and lineage. Stillness/circling is not predefined failure. Worlds, not related individuals, are independent units.

Advance only if at least2/3Core-driven worlds show feeding and reproduction, plus population-level starvation or declining reserves under inadequate supply. This is an ecological feasibility gate, not a learning claim. Phase two uses living-parent births in three fresh worlds (8founders,900seconds); never revive a dead parent. If a world has no survivors, disclose reuse of another surviving source and the reduced independent-lineage count.

Phase two independently mutates radius, maximum thrust and sensory range at birth with unbiased log-normal sigma0.15 within declared physical ranges. No random brain rewiring. Engulfing requires complete geometric enclosure for200ms; mere contact does not count. Transfer60%of stored bodily food, lose the rest, and do not duplicate the prey's Core reserve. Its body disappears while its preserved Core closes inputs and continues until genuine inactivity. This is a soft-envelope approximation, not membrane or digestion chemistry.

If survivors and budgets permit, preregister common-environment comparisons: inherited vs blank brains, equal body and initial energy, three paired worlds of4copies,300seconds. Prefer distinct surviving founder lineages, then stable ID, not best-looking post-hoc cases. Unfinished controls must remain unfinished. Trait differences, reproductive success, adaptation and species formation are distinct claims. Short-lived size clusters do not establish speciation.

## Budgets and evidence

One worker;512total individuals including calibration/evaluation;2hours cumulative simulation wall time;4GiBprocess memory;3GiBnew local+database storage stops expansion,4GiBhard ceiling; retain2GiBfreeRAM,C5GiB,E15GiB. Account starts15%,+6points stop expansion,+10stop new simulation, counting shared usage conservatively. Save full populations every120simulated seconds. Preserve inputs, events, trajectories, errors and censored survivors. Publish bilingual design/report/evidence through platform services. Calibration verifies food exclusivity, energy conservation, no free birth energy, physical drag, restoration and Python/Rust agreement. Pre-registration engineering fixes to 32-bit channel IDs and birth configuration identity are not scientific results.

Reference for low-speed drag: [MuJoCo fluid-force documentation](https://mujoco.readthedocs.io/en/stable/computation/fluid.html). This does not claim full fluid simulation.
