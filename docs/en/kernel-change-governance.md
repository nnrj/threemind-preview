# Kernel authorization, version fidelity, and tool-time isolation

Effective 2026-10-13 under the user's explicit instruction. [中文](../zh/kernel-change-governance.md)

Outside isolated temporary experiments, every kernel change not already explicitly authorized by the user must be discussed and confirmed before implementation. Every change must disclose its content, rationale and impact. Tools' wall-clock cost or pauses must not add even a small unauthorized amount of simulated time. Selecting version2 must execute the genuine version2.

## Working rules

1. Before implementation, record the version, prior/new behavior, reason, authorization source and expected effects. Complete already authorized scope without asking repeatedly; ask before new mechanisms, defaults or out-of-scope repairs. An assistant-authored statement of approval is not independent authorization.
2. Separate dynamics changes, numerical semantics, implementation optimizations and read-only tools. Learning opportunities, thresholds, ordering, clipping, integration and signal grouping can change dynamics even when function names or coefficients remain unchanged.
3. Temporary experiments use explicitly isolated fresh engineering fixtures or authorized control copies. They do not authorize changing formal subjects, defaults, released kernels or original evidence.
4. Delivery must disclose actual changes, reasons, validation, unverified effects and remaining issues. Core-only equivalence does not establish whole-individual equivalence when readers, checkpoints or inheritance consume the affected values.
5. Historical kernels retain their own creation, execution and restoration identities. Shared code must preserve historical paths and frozen witnesses. Do not silently fix, upgrade or substitute a historical individual under its original name.

## Tools and internal time

Observation, statistics, plotting, saving, export, profiling, authentication and host waiting are not internal experiences. They must not implicitly stimulate, restore, learn, reconfigure or advance the subject; wall-clock delays must not directly add simulated time, discard internal events or reorder them.

Simulation advancement follows declared inputs/protocols and explicit simulation targets. Real-time/scaled/paused host control follows its declared clock semantics. A blocked experimental tool or an explicit pause must resume from the complete current internal state. Actual external input and authorized advancement are recorded operations, not hidden observational side effects.

Acceptance includes observation/no observation, different observation frequencies and advancement batches, host waits or simulated wall-clock jumps, complete restoration, and coincident input/expiry boundaries. Compare internal time, ordering, complete state and the next response, not only graphs or counts. This does not remove the simulation clock or required forgetting/expiry events; it separates instrument cost from model experience.
