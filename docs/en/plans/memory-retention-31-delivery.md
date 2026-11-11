# continuous-memory/3.1: local expiry for zero-response nodes

Date: October 11, 2026. The user authorized a distinct `/3.1`, preserving `/3`, and an audit of `/4`. This is an engineering behavior correction, not a formal teaching or retention experiment.

## Defect and behavior boundary

`/3` creates a node for positive input before energy/response gating. After exhaustion, the node and retention anchor exist but the accepted response is zero; the original path schedules reclamation only for positive response. Capture succeeds, but restoration rejects the missing local expiry. Ordinary idle advancement does not fill the gap.

The original witness uses initial energy0.05, direct cost0.2 and two time0 channels0.7/0.6. The first response is0.25 and the second0. Both backends retain the original state hash `ba7714ed08fbb9283098a36101cbcf57aadc45294ea257e25f82489614d16fd6` and recovery failure. No repair on read, weakened validation or historical-checkpoint rewrite is used.

The correction changes structural evolution on the defective branch: zero-response nodes now undergo the existing local reclamation rule and can be deleted. Later node identity and contact formation may consequently differ. This is a dynamics correction, not solely a persistence fix. Ordinary effective activation, propagation, weight learning, H/D formulas and parameters are unchanged; zero response earns no support, dose or half-life growth.

With default quiet-death grace, the original witness dies at2.26 simulated seconds and stops advancing. It did not run to100 seconds by default. Long-idle engineering copies explicitly extend grace to200 simulated seconds without changing repository defaults or historical subjects.

## Identity and implementation

| Item | Treatment |
|---|---|
| Kernel | Add `threemind.continuous-memory/3.1`; `/3` remains available with its original execution/restoration semantics |
| State | New kernel uses `threemind.continuous-memory-state/3.2`; original `/3` still has state schema `/3.1`. Kernel version and state-format numbers are distinct |
| Definition | Add `threemind.zero-response-local-expiry/1`, bound to the new identity/hash |
| Python | Reuse `/3` parameters, learning, retention and recovery; the new type fixes zero-response expiry on at birth |
| Rust | Share the continuous implementation with behavior fixed by birth identity; native backend and independent Runtime support it without Python dynamics |
| Locality | Schedule only the addressed object's existing expiry, through the existing executor; no graph-wide refresh, scheduling repair, arbitration or reward scan |
| Interfaces | API, CLI/Agent catalog, kernel→matching template→parameters, birth locks and coupled switches recognize the new version |
| Default selection | `/3` remains the global default. Existing templates are unchanged; explicitly select `/3.1` for new corrected individuals |

Existing structural order remains: accepted same-time input precedes reclamation. Effective retouch can cancel expiry. Disabled plasticity or retained-node mode is respected. Rejected repeats earn no effective-touch timestamp or isolation-clock reset in `/3.1`.

Versions cannot silently exchange states. New restoration still rejects missing/inconsistent deadlines. No originals, historical states or research data are migrated or modified; database schema remains68. A historical-checkpoint repair utility and pre-existing structural-inheritance gaps remain separate T12 work outside this authorization.

## /4 audit

Both `/4` backends schedule node timers even when the accepted amount is zero; they do not inherit `/3`'s positive-response condition. Two edge-retention formulas × three reclamation modes × two energy models × two backends produce24 zero-energy birth cases. All contain expiry, restore exactly and reclaim at their deadlines. With no effective activation, support/H do not grow.

This defect was not found in `/4`, so its dynamics, identity, schema and parameters are unchanged. This finding is limited to missing zero-response expiry and recovery; it establishes neither universal correctness nor improved memory performance.

## Acceptance

- All63 targeted cases pass: original `/3` frozen hash; both-backend reclamation/recovery; both retention formulas; three modes; rejected repeats; expiry-boundary retouch; explicit no-reclamation settings; unchanged ordinary learning; cross-backend recovery; observation/batching; corruption rejection; configuration catalog; Lab prepare/start/pause/resume. The24 `/4` cases are included, not additional independent experiments.
- Three independent Rust Runtime cases pass: both model formats, SQLite continuation and declarative definition routing. Original bytes and identity remain intact.
- Increasing unrelated nodes from0 to200 leaves additional retention settlements at1 for one zero-response event. This measures only new retention locality; pre-existing `/3` graph-wide executor loops remain.
- These are initial targeted results; same-day final acceptance follows. Engineering acceptance is not registered as a formal research trial and does not replace teaching or historical findings.

### Final acceptance, October 11, 2026

- All 260 cases across seven backend suites pass in 173.17 seconds. This includes the 63 targeted and three new independent-Runtime cases, rather than adding their counts together. Coverage includes original `/3`, `/4`, legacy causal baseline, kernel registry, creation hierarchy and independent-Runtime interoperability.
- The native Python extension was rebuilt/installed and the independent Rust Runtime rebuilt; they execute separately. The frontend production build passes. All 40 UI cases pass across two batches: initially 39 passed and one skipped for a missing isolated catalog entry; after adding that read-only entry, the skipped case passed separately. Coverage includes version labels, matching configuration sources and narrow-screen pages.
- Ruff, formatting checks for changed Rust files, all four history editions with 99 chapters, and bilingual/link validation pass. Test artifacts remain ignored, outside Git; the full tracked-file data-boundary guard is run before committing.
- The first broad-regression PowerShell wrapper stalled after isolated-database startup without entering pytest. After verification, only that wrapper was stopped; direct pytest reused the same isolated database and passed. The task's port-8898 static preview and port-55439 isolated database were stopped at closeout, without operating the user's application or everyday database.

Engineering logs: `.work/birth-expiry-20261011/regression.log` and `regression.xml`. This acceptance does not measure memory-retention benefit or repeat formal teaching experiments.

[Authorization and later acceptance](../history/sources/2026-10-11-memory31-expiry.md) · [Original upgrade plan](memory-retention-v3.md) · [Current backlog](research-backlog.md)
