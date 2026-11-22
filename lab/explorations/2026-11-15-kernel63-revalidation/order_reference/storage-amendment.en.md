# R63n lossless storage specified before formal execution

15 November 2026. This batch adopts the complete-state packing already validated in historical R51q. Successive teaching snapshots share lesson-states.zip, with each member retaining its complete tmind bytes. Teaching endpoints, diagnostic endpoints and pre-cue states remain separate files. Inputs, timing, observation frequency, state contents and criteria remain unchanged.

After registration and independent apparatus validation, packed_snapshots.py prepare will verify the bytes and complete-state hashes of 192 apparatus snapshots and estimate actual allocation using FileStandardInfo. Formal execution requires passing apparatus and budget checks and API registration of the storage proof with pending=0. The formal and analysis entries are packed_snapshots.py run and packed_snapshots.py analyze. Unpacked apparatus files remain intact.

This addresses small-file allocation overhead using a historical tooling correction; it is not a newly measured result. No formal subjects have been created. Courses, sample sizes and the twofold cost stop remain unchanged.
