# Addressing and motor expression: recommendations, not implemented changes

18 November 2026. During AS63-03, the author proposed mapping stimulus parameters to node addresses through an explicit function rather than directly using a parameter value. These recommendations do not constitute implementation authorization. See the [study report](report.en.md) for measured results.

## Separate addressing from output interpretation

Current 6.3 returns the anonymous channel code from `node_address(code)`. The old motor adapter computes `tanh(0.5 × Σ sign(id) × activation)`. Addressing determines where an input arrives; the adapter determines how activity there affects movement. Replacing the address with a more complicated hash does not remove a fixed stimulus-to-motor route if the adapter still hashes that address into a motor coefficient. It changes the table.

A new function can nevertheless separate external codes from internal identity and avoid assigning IDs according to arrival order. That design benefit must be distinguished from evidence that behavior depends on experience and learning.

## Useful constraints

Specify `address = F(stable identity parameters, fixed individual seed, addressing version)`. The same identity in the same individual/version must return the same address regardless of node count, input order or host execution time. A small deterministic integer mixer or permutation can suffice; a large model or expensive cryptography is unnecessary.

First define which parameters represent identity. If intensity means the strength of the same stimulus, it should normally change the input delivered to the node, rather than route every slightly different intensity to another node. Timestamps normally should not define identity. If a varying physical parameter defines a different stimulus, encode it at a justified resolution before addressing. Blindly hashing every floating-point field can prevent repeated experiences from reaching the same location.

For a finite integer identity domain, an invertible permutation can avoid silent collisions. Multiple parameters require canonical encoding and adequate address space. Truncated hashing is not collision-free; collisions require an explicit rule. Preserve the fixed seed, addressing version and encoding rules in complete snapshots and apply declared inheritance rules to offspring.

## Output and experimental controls

Store motor connections or readout rules independently and explicitly instead of deriving direction from arbitrary IDs at every readout. Declared anonymous output channels or activity-pattern readouts can support tests of how experience organizes motor output. Fixed sensory-to-motor pathways may remain as specified baseline responses, but their contribution must be distinguished from learning.

Future learning/inheritance studies should retain same-peripheral blank controls, developed individuals, genuine offspring and direct-sensory controls. When testing internal-connection contributions, preregister selective blockade, restoration or transplant and measure behavior, not occupancy alone. Separate output calibration/learning from Core learning. These are proposed future controls; they were not added to this study.

## Version the change

Current node identity also contributes to local energy-region allocation and, when spatial mechanisms are enabled, positions and neighborhoods. Changing addresses therefore need not be a harmless renaming. Version the addressing mechanism, preserve genuine old 6.3 behavior and saved identities, and check both reference and native implementations.

Minimum checks cover stable addressing, arrival-order independence, explicit collision behavior, complete save/restore, compatible inherited connections, and consistent node relabeling when topology and peripheral attachments are declared fixed. Event-order, spatial and energy-allocation effects must be disclosed separately, not hidden as optimization. The concrete function and its dynamics require author approval before implementation.

Implementation sources: [6.3 addressing and node creation](../../../src/threemind_kernels/local63.py); [historical motor adapter](../2026-09-29-input-rate-and-autonomy/world.py).
