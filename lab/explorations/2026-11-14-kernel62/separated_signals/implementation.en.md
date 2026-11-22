# Independent excitatory and inhibitory connection states in 6.2

Implemented on 2026-11-15 with the author's authorization. The Python reference implementation, native Rust implementation, standalone runtime and workbench configuration catalogue expose the same options.

## Configuration

The master switch, `separate_inhibition`, defaults to `false`. Setting it to `true` separates weights, synaptic resources and learning records. Each child switch defaults to `null`, meaning that it inherits the master value. An explicit child value, `true` or `false`, overrides the master.

| Child switch | State controlled |
| --- | --- |
| `separate_inhibition_weights` | The base weight used, reinforced and decayed for each signal type |
| `separate_inhibition_resources` | Available, active and temporarily unavailable resources, and facilitation state |
| `separate_inhibition_learning` | Fast enhancement, eligibility, stability, retention timescale, decay age, usage count and usage times |

For example, `{"separate_inhibition": true}` separates all three. Adding `"separate_inhibition_resources": false` shares resources while separating weights and learning records. `{"separate_inhibition": false, "separate_inhibition_resources": true}` separates resources alone.

Separate learning records require separate weights: two independent decay records would otherwise compete to update one weight. Contradictory configurations are rejected. These choices are fixed at birth. Saved individuals without these fields retain shared-state behavior.

## Dynamics

Each direction remains one connection, which can hold state for the two signal types. Separate weights start equal. Co-stimulation and novelty apply the existing equations to both weights; actual transmission reinforces only the corresponding weight. The whole connection is deleted only when both weights are below the deletion threshold. Connection interventions, topology, spatial position and dormancy remain shared.

Separating weights alone leaves usage and retention records shared. When learning records are also separated, inhibitory transmission no longer refreshes excitatory usage times, stability or fast enhancement. The inhibitory side records its own history using the same equations. Each side follows the selected retention and decay rule; no new decay equation is introduced.

Separate resource pools each retain the original pool capacity and release and recovery equations. This both isolates consumption and increases total capacity; both changes belong in the interpretation of any benefit. Shared mode retains the previous pool and release order.

Complete snapshots preserve all separated state. Offspring inherit both persistent weights and their retention records; fast activity and resources are reinitialized, and decay age follows the existing preserve-or-reset choice. Observation, saving and readout do not advance internal time.

## Validation and defaults

The options are changes in dynamics, disabled by default. Version 6.1 and earlier implementations are unchanged, and the global creation default remains 6.1. The existing 6.2 defaults for resource prechecks and local activity expiry remain enabled.

`tests_v2/test_local62_separated.py` covers Python/Rust parity, complete restoration, inheritance, switch precedence and shared-mode behavior. The bilingual reports in this directory present the performance measurements and prefix results. Existing services were not restarted; long-running services load the new code on a subsequent normal restart.
