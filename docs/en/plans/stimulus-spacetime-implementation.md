# Stimulus and proprioceptive tools: implementation

[中文](../../zh/plans/stimulus-spacetime-implementation.md) · [Decisions](stimulus-intensity-and-spacetime.md)

2026-09-30. No Python/Rust Core or candidate-kernel formula changed. Frozen `6241016` input/state witnesses remain reproducible.

Chat offers normal 1, strong 4 and custom intensity, a 0–4 slider and 0–100 number entry. Presets never alter text normalization, framing or identities; an explicit intensity wins. Creation retains continuous-memory/2, arrival-window novelty 0.018/reference 0.2 and no additional facilitation. The research button explicitly applies ordinary kernel defaults plus 1-second facilitation. New host/process/runtime telemetry intensity is 0.2 independently; historical omission restores 1. New runtime profile /6 and telemetry /3 declare intensity; old versions remain readable.

The existing input page accepts stimulus units, generates reproducible random controls without submitting them, and offers diagnostics on an independent checkpoint clone. Diagnostics distinguish drive, touches, activation increment and consolidation, verify the uninstrumented-clone hash, and do not model the live environment/body filter. They stay in Lab, outside deployed Core. CLI limits are 32 MiB model, 4 MiB carrier, 300 nodes/5000 edges and a one-second horizon; larger requests fail rather than truncate.

```powershell
python -m threemind_lab.cli input-text --project <project-id> --run <run-id> --file carrier.txt --preset strong
python -m threemind_runtime.cli --text-input carrier.txt --text-preset strong --clock unbounded --export result.tmind
python -m threemind_runtime.random_stimuli --mode fresh-group --channels 2 --seed 42 --count 20 --intensity 0.2 --output units.jsonl --save-state source-state.json
python -m threemind_runtime.cli --stimulus-units units.jsonl --clock unbounded --until-us 3000000 --export random-result.tmind
python -m threemind_runtime.world_cli --template gravity-pendulum --write-example pendulum.json
```

In this workspace, Python is `.work/kernel-venv/Scripts/python.exe`. Outputs require new paths. Input API remains `POST /api/v2/projects/{project}/runs/{id}/inputs`, adapter `stimulus-units`, payload `{"units":[...]}`; random controls use `.../input-fixtures/random`, clone diagnostics use `.../runs/{id}/input-diagnostics`. The standalone Runtime needs no Lab database. Stimulus-unit schema is `threemind.stimulus-unit/1`, with anonymous channel values and explicit joint-observation provenance. Independent units at the same timestamp are not merged; changing observer labels cannot change Core input.

World /2 adds sensor-local accelerometers/gyroscopes, retaining existing port identity mapping. Templates: inertial cart and gravity pendulum; 5 ms physics, 20 ms sampling, unchanged Core propagation. Editor exposes mounting position/orientation, scale and enabled status. Desktop configuration/preview are side by side; narrow screens use tabs. Old world drafts require explicit upgrade and a new saved revision. Observation includes raw units, encoded values and joint stimulus groups. Preview is a compiled pose, not browser-generated experiment evidence.

## Background audit

Old V3 `97d8592`, `core/threemind/runtime.py`, defaults to local-coactivation and disabled global homeostasis. `_adapt_edges` uses per-event joint touches unless temporal association is explicitly selected. `_homeostasis` scales excessive total activation, not graph connectivity. Current defaults likewise do not force fresh nodes into an existing network.

The synthetic field repeats 8 slow, 11 fast and 13 drift identities; transients repeat during 0.2–1.4-second lifetimes. Physical telemetry reuses level/rise/fall identities and smoothed history. Neither is independent one-shot noise. Repetition and joint observation can legitimately consolidate connections. Random controls never inspect the network or delete by source label. Default activation clamping and input competition are off; body filtering is explicit; display sampling does not create edges. Reports read actual complete state, not rendered point counts.

## Verification

Two overlapping regression batches passed 54 and 59 tests respectively; these counts must not be summed as unique tests. Coverage includes frozen witnesses, legacy telemetry, API, standalone CLI, Rust/Python artifact interchange, physical recovery and configuration. Browser acceptance ran at 1440/390 pixels against an owned isolated database/API: actual submitted strength, clearing input after success, graphical/JSON worlds, narrow-screen tabs and no horizontal overflow. Frontend build passed with pre-existing large-chunk warnings. Accelerometer support/freefall, uniform translation, gyro rotation, local coordinates and template state recovery passed. A sandbox temporary-directory denial was resolved by rerunning with authorized local permissions, without changing dynamics or old evidence.
