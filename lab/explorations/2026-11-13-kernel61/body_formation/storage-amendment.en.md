# Lossless trajectory compression before the R51r formal run

14 November 2026. The original protocol, executor and apparatus evidence are retained. This amendment changes only trajectory compression. No formal subjects have been run.

All eight apparatus comparisons produced identical final hashes across five observation/restoration modes. The largest process difference between an unchanged-configuration API call and no call was 1.01644e−20, below 1e−9. Both no-cue enqueue policies produced identical final states and activity. The apparatus is valid.

The conservative allocation estimate for a full-sensory unit was 23,498,792 bytes against 6,504,488 historical bytes, a ratio of 3.613. This exceeded the twofold review threshold, so the original run was not started. Complete observations saved every 20 ms account for most of the volume: one all-enabled probe produces 14,427,249 JSON bytes, compressed to 1,278,055 bytes with gzip. It has 12 nodes at both endpoints. Recorded fields differ between versions; larger files cannot be interpreted directly as node proliferation.

A pure file compression comparison reduced the same JSON to 544,004 bytes with XZ preset 1 in approximately 0.19 s. Decompression recovered identical bytes. Preset 6 produced 422,048 bytes but took approximately 1.86 s. Preset 1 is selected to balance space and compression cost. It changes no numerical precision, fields, observation frequency or state contents.

Before formal execution, all 48 existing apparatus trajectories are saved separately as XZ. Decoded bytes, parsed contents and hashes are checked individually. Original gzip evidence remains intact. Both sensory conditions must have revised conservative allocation estimates below twice their historical values, and the amendment registration must have pending=0, before the formal run is permitted.

The new entry point is `compact_trajectory.py prepare/run/analyze`. Preparation converts existing files without creating or advancing subjects. The run calls the frozen executor and writes the same trajectory JSON as `trajectory.json.xz` instead of `trajectory.json.gz`. Analysis uses the corresponding decoder with the frozen state, input, intervention and arithmetic checks. Complete Core snapshots, inputs, curricula, 32 teaching references, 512 diagnostics, criteria and resource reserves are unchanged. The original `study_formation.py run` and direct `analyze_formation.py` are no longer formal entry points.

The added tool and this note are frozen separately in `storage-amendment/`; `proof.json` records conversion evidence. Actual allocation remains compared against each historical unit and stops at a complete boundary if it reaches twice that value. This amendment does not increase the threshold. Any new dead-host in-flight state must still be preserved and reported.
