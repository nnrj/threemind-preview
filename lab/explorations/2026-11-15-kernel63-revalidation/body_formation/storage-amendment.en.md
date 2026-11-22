# R63o lossless trajectory storage specified before formal execution

15 November 2026. This batch uses XZ preset 1, already validated in historical R51r, to retain all four activity fields and other observations at 20-ms intervals. Only file encoding changes; fields, precision and sampling are preserved. Complete states, inputs, courses, 32 teaching references, 512 diagnostics and criteria remain unchanged.

Following registration and independent apparatus validation, compact_trajectory.py prepare will encode 48 apparatus trajectories as XZ and verify decompressed bytes, parsed contents and hashes. It will also estimate conservative actual allocation. Passing checks and supplementary API registration with pending=0 are required before compact_trajectory.py run. Analysis uses compact_trajectory.py analyze. Original gzip apparatus files remain intact. The ordinary study_formation.py run is not the formal entry for this batch.

The storage method is specified before computation. Historical disk measurements are not presented as new 6.3 findings. Unit-cost limits, resource reserves and complete-boundary pauses remain unchanged.
