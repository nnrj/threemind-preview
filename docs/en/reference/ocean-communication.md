# Ocean communication tools

[中文](../../zh/reference/ocean-communication.md) · [Research plan](../plans/embodied-communication.md)

The existing oscillator mouth transmits through the simulated environment to anonymous binaural frequency bands. No Transformer, dictionary, answer labels or Core change is involved. This creates a testable pathway, not a predetermined language.

## CLI and Python

From the repository root, with the configured Python environment, create a separate demonstration:

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
New-Item -ItemType Directory -Force .work/communication-demo
& $py -m lab.tools.ocean_communication_cli template > .work/communication-demo/protocol.json
# Edit the protocol if needed. init creates blank brains, not E53's historical founders.
& $py -m lab.tools.ocean_communication_cli init .work/communication-demo/protocol.json .work/communication-demo/source
& $py -m lab.tools.ocean_communication_cli run .work/communication-demo/source .work/communication-demo/live --seconds 5
& $py -m lab.tools.ocean_communication_cli run .work/communication-demo/source .work/communication-demo/muted --seconds 5 --hearing muted
& $py -m lab.tools.ocean_communication_view .work/communication-demo/replay.html --case .work/communication-demo/live --case .work/communication-demo/muted
```

Every output directory must be new. Continue from a previous stage's `final`. `--wall-seconds` limits computation; `--seconds` bounds observation, not organism lifespan. Snapshots retain structure, activity, bodies, environment RNG, in-flight sound and input buses. Restoring does not clear current activity.

Python uses `CommunicationOcean`, `CommunicationProtocol`, `load`, and `ocean_communication_cli.run_recorded`, the same execution code as the CLI. Save with `ocean_contact_cli.save`. Protocol/state identities are `threemind.ocean-communication/1` and `threemind.ocean-communication-state/1`.

### Explicit /2 common-body sampling

`template --joint-body-sample` selects `threemind.ocean-communication/2`, `JointCommunicationOcean`, `JointCommunicationProtocol`, and state `/2`. Actual body and arriving auditory measurements from **one body at one physical sample** form one stimulus group. Anonymous channels and values are preserved. Different bodies are never merged; meanings, identities and food answers are not injected. `/1` continues to submit body and ear observations separately, without automatic upgrades.

E53 found no cross-sensory connections between hearing and other body channels under the separate-submission apparatus/configuration. `/2` changes how the environment declares a common observation, not Core edge-birth rules. The apparatus versions must be reported separately.

Equal channel values do not make the groupings dynamically equivalent: joint edge candidates and existing local input competition can both change. A changed outcome cannot be assigned entirely to new cross-sensory connections without an independent connection intervention.

## Configuration and interpretation

| Fields | Meaning |
| --- | --- |
| `sound_interval_us` | Mouth sampling cadence; does not change Core propagation |
| `sound_range_m`, `sound_reference_m`, `sound_speed_m_s` | Range, attenuation scale, propagation speed; arrival rounded up to environment samples |
| `sound_bands`, `hearing_gain` | Frequency bands and fixed sensory conversion |
| `voice_cost_per_s` | Physical emission energy, limited by available storage |
| `self_hearing` | Receive one's own emitted signal |
| `hearing_mode` | `live`; `muted` removes others only; `scrambled` freshly permutes other bands per arrival, preserving that arrival's power |
| `intake_share_fraction`, `association_gap_m`, `association_dwell_us` | Intake sharing between compatible contacting bodies |

Compatibility, in-group consumption protection and contact sharing are declared environmental rules, not evidence of voluntary cooperation. The current mouth sonifies stronger local activity; voluntary speech gating has not been established.

## Replay and evidence

Open the generated HTML in a browser: select a complete-world branch, seek/play, select organisms, inspect ear bands and export PNG. The layout supports wide and narrow screens. Physical states are held between 200 ms observations, with no invented trajectories. Acoustic links are recorded deliveries in that window, not neural connections or semantic labels. Muted branches can still show environmental sound links; ear power reflects the experimental intervention.

`inputs/` contains submitted sensory stimuli; `communication.jsonl.gz` contains emissions, deliveries, auditory components and actions. **For `/1`, reconstruct both body and auditory streams. For `/2`, `inputs/` already includes the combined auditory input: never deliver the logged auditory component twice.** `delivery_group` and `combined_stimulus` identify the grouping. Early E53 logs retain band power; later logs also retain the mouth's raw `voices`. Missing observations are not fabricated retrospectively. `events.json` includes ecological events; `initial`, `checkpoints` and `final` contain complete snapshots.

Both versions support candidate export through `ocean_species save` and explicit `seed_founders` replication into new compatible worlds. Replication retains structure/mapping, resets activity and uses ordinary founder energy. It is not natural reproduction or evidence of learned communication. No automatic historical-data cleanup.

E53 replay and bilingual reports are published together in the research project's records/reports. The HTML is a downloadable artifact. A production graphical world composer is not part of this tool delivery and remains on the research backlog.
