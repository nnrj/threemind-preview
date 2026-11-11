# M4 sustained whole eye–hand apparatus: the 30-second path fits the local budget

16 October 2026. Source/protocol frozen at `3600a16`; [preregistered protocol](m4-capacity-protocol.en.md). Record `50d8b217-9722-57bb-956a-8422d71f6edc`. This is instrument acceptance, **scientific N=0**. Applied torques are declared instrument operations, not autonomous performance.

## Purpose, expectation and conclusion

Can the real eye–hand apparatus, previously verified over three seconds, complete 30 continuous internal seconds with 40 declared personal-peripheral updates, whole-state saves every six seconds and exact restoration at 18 seconds within the local budget? The expectation was completion with all state, clock, update and resource gates satisfied. **Yes: the capacity test PASSES.** M4 can now proceed from short apparatus acceptance to sustained-course design informed by measured costs, without buying compute or changing Core for this path.

## Results and verdicts

| Preregistered target | Observed result | Verdict |
| --- | --- | --- |
| 30 continuous internal seconds, 600 ticks | All five six-second segments completed; both absolute clocks agree at every tick | PASS |
| 40 peripheral updates | Twenty fixed calibrations with two updates each; motor total40, naming updates0 | PASS |
| Whole-state preservation and restoration | Six complete states including birth; all member hashes verified; exact canonical equality at18s | PASS |
| Private memory≤3GiB, host≤600s | Peak2,398,531,584 bytes (2.23GiB);169.179s | PASS |
| Commit/RAM/C/E reserves≥5/4/5/25GiB | Minima9.38/10.75/8.43/36.36GiB | PASS |
| Originals≤512MiB | Pre-publication logical58,233,788 bytes (55.54MiB) | PASS |

| Complete boundary | Nodes / edges | Cumulative motor updates | Segment total(s) | Whole save(s) |
| --- | --- | --- | --- | --- |
| 6s | 312 / 96,438 | 8 | 28.558 | 4.868 |
| 12s | 322 / 102,710 | 16 | 29.479 | 5.518 |
| 18s | 324 / 104,044 | 24 | 44.188 | 5.837 |
| 24s | 324 / 104,100 | 32 | 30.925 | 6.023 |
| 30s | 324 / 104,110 | 40 | 30.782 | 6.199 |

The18s segment includes11.130s for whole restoration. Canonical SHA256 before and after was `44c7fc932b041bb113992da34a7f6199f6847fddad17df4898894f715fbc6d26`. The host exited normally without STOP, stderr output or residual in-flight marker. The separate file audit loaded no Core and advanced no simulation.

## Analysis and meaning for ThreeMind

This is a favorable apparatus result: Core, personal weights/Adam/RNG, body, mappings, recent activity and actuators remain preserved along the path. Saving and restoration retain peripheral learning that has already occurred. The final324 nodes and104,110 edges show that the measured object includes the real visual/motor apparatus rather than a small anonymous substitute.

Whole-state storage is a substantial measured cost: five saves total28.444s and one restoration11.130s; twenty calibrations total0.895s. Host time also includes physics, Core, Python observation, serialization, I/O and synchronization. **Pure-Core computing time was not separately instrumented.** Subtracting a few components would not establish that quantity. The measured169s per30 internal seconds supports next-batch planning, with the same resource guard checking every new course.

Before publication there were118 files:58,233,788 logical bytes, the same hardlink-deduplicated logical total, and58,468,624 actually allocated file-stream bytes; zero duplicate hardlink entries. Each of the six whole states has eight files; sizes range from1,012,852 to7,976,386 bytes, median7,303,261.5. Inventory excludes later publication/readback copies, the inventory itself, directory/MFT and database overhead.

This batch completes its sustained-execution, exact-restoration and affordability target. Formal M4 now requires a separately frozen balanced curriculum, crossed training order, separated development/confirmation material and selective interventions; this fixed operational path produces no scientific specialization score. E69/E67/E68 remain paused, and old evidence and the author's manuscript are unchanged.

Originals: `E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m4-capacity-v1`. Evidence: `analysis-v1.json`, `audit-v1.json`, `storage-inventory-v1.json`, `segments/*/whole/complete.json`, trajectories and calibration records. Review is by the executing assistant and separate file arithmetic, not external replication. Actual API delivery is recorded in a separate delivery note.
