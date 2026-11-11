# Whole-scene classroom tools

[中文](../../zh/reference/whole-scene-classroom.md) · [E58](../plans/embodied-memory-content.md)

`WholeSceneClassroom` in `lab.tools.whole_scene_classroom` implements `threemind.grounded-classroom/3`. One fixed camera samples all physical objects, teacher marker and colored self-pointer. Support1–8objects at continuous positions; only four-object scenes have default positions. Core receives RGB/range pixels, proprioception, body/weather and guide reaction measurements. Observer names, item lists and answer labels are not Core/selector inference inputs.

This remains a2D sliding pointer, not an articulated arm. Contact represents guide reaction at workspace limits, not arbitrary skin/object friction. Simulated wind/weather remain independent of host CPU load.

The teacher cue is an optically rendered sphere. `teacher_radius_m` defaults to0.12m and is saved with state. The original0.065m cue missed the two far teaching locations on the16×16 retina; visibility was fixed before formal teaching. Early /3 states without this field still restore0.065m. Coordinates place real geometry and are not additional Core sensory ports.

```powershell
& .work/kernel-venv/Scripts/python.exe -m lab.tools.whole_scene_classroom --output .work/my-eye-recording --seconds 3 --force 0.4 -0.2
```

The output directory must not exist. Save physical frames, actual Stimulus records and restorable world state without starting Core or user services. `--state <state.json>` restores. Python provides `observe`, `stimulus`, `advance_physics`, `state` and `restore`, reusable by Agents/UI. History/docs are available in the existing UI; the production world editor is not yet wired to this apparatus.

`RetinalChoice` applies the same temporal reader to every regular retinal neighborhood, without object boxes or identities. Its output is a retinal pixel. Training uses explicit supervision; inference has no answer argument. It is a supervised selector, not automatically a faithful intention translator. Direct-input/Core comparisons use the same architecture. Explicit smaller training batches leave the existing default32 unchanged.

`sensory_replay` is a recorded-input research intervention, replacing vision and/or all motion-dependent body fields from an actual reference tape. It does not modify Core state or become normal default behavior. Preserving background is distinct from preserving movement feedback.
