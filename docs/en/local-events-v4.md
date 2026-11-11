# continuous-memory/4 execution and state contract

[中文](../zh/local-events-v4.md) · [Implementation plan](plans/local-events-v4.md)

Identity `threemind.continuous-memory/4`, state `/4.1`. Python and Rust execute independently. `/3` remains creatable, restorable and executable. Shared implementation can change without changing its established behavior. No individual is upgraded; the application creation default remains `/3`.

Nodes own activation, trace, inhibition, support S, H, fatigue/salience, time anchors and emission/quiet/reclamation deadlines. Edges own weight, eligibility, stability, H, STP, fast trace and expiry/novelty deadlines. The executor delivers deadlines already requested by their owners. It does not scan the graph to select updates. Idle objects continue to forget and expire without new input.

Activation, trace, inhibition and eligibility decay exponentially. Default H/weight/support use the `/3.1` analytic integral. Edge stability loss now integrates that edge's own eligibility over elapsed time, an explicit `/4` numerical change. `legacy-stability` retains the discrete edge forgetting equation through edge-owned periodic events, rather than a graph scan. This control is not the complete `/3` engine.

Default emission period remains 100 ms, initially aligned to simulated time. Asynchronous phase schedules from the node's own actual activity. The old 10 ms `step_us` is inactive metadata: `/4` performs no 10 ms whole-graph solve. Non-default `step_us`, `association_window_us`, `attention_budget`, and `target_total_activation` are rejected. Global homeostasis, spatial competition, input ranking, temporal whole-graph birth search and learning/propagation quotas are unsupported. Monotonic simulated microseconds and host pacing remain distinct.

Observation, saving/loading validation, explicit paused configuration intervention and structural birth can traverse the graph. Ordinary local events visit their owners and contacts. `scan-control` explicitly enumerates nodes and invokes the same local emission operator. Correction to earlier discussion: `/3.1` already uses local expiry reclamation; the old global prune path cannot explain its observed text retention regression.

Default unified reception processes actual arrivals with the same activation, trace, inhibitory-generation, S/H, fatigue and ordinary-learning rules regardless of source tags. Direct/associative are observational. Messages can carry their sender's own features; external arrivals without these use a zero key. Equal processing rules do not manufacture equal features. `legacy-source` explicitly preserves source-dependent reception/learning as a control.

`coincident` integrates messages actually delivered to one receiver at the same timestamp; `sequential` processes them individually. Saturation, fatigue and context allocation make this scientifically consequential. At equal time reception precedes emissions, which precede expiry. This does not refresh all nodes simultaneously or query their neighbors' live activations.

An external packet or a sender's local fanout packet carries actual contact notifications. Only receivers actually reached by that packet can associate, using their received amounts, without searching all active nodes. Weight/stability reinforcement remains direct. Novelty rewards are never converted into D. Unified novelty records actual local postbirth arrivals; source-dependent novelty records internal arrivals only. Immediate controls use the packet's received amounts or the old associative criterion, respectively. The operator identity declares these differences.

Node H dose comes from its own accepted amount. Edge H dose comes only from actual emission after release/amplitude/energy gates, using a fixed 0.1 s reference. Edges do not inherit endpoint H or read both endpoint activations to grow H. STP may release before a failed post-release floor check; failed transmissions receive no H dose. STP numbers and H gain 0.2 have not been retuned.

Default energy model is `local-field`; energy constraints remain independently disabled by default. Fixed regions are assigned from an independent energy seed and node birth ID. These are explicit resource-contact regions, not simulated fluid or a biological claim. Supply placement ignores graph size, learner RNG, host clock and display layout. Counter hashing and an independent saved 64-bit random stream are replayable alternatives.

Supply enters one region. Members take shares proportional to their own capacity deficits, without traversal-order priority. Defaults: 16 regions, capacity 1 per node. The initial total is capacity-clipped then divided over regions. Subsequent `energy_capacity` limits each region pool; `energy_node_capacity` limits each node. The shared-ledger control instead has a single global pool, so comparisons must declare this capacity difference. Regional uptake visits regional members and is not constant-cost in their count.

Nodes own local maintenance events when starvation damage is enabled. Maintenance/erosion affects the owner and its outgoing contacts, never a graph-size-dependent global erosion. Aggregate accounting is read-only. `global-ledger` uses the same local work and maintenance operators with shared funds; it does not invoke the historical whole-graph starvation transition.

Automatic/manual reclamation and retain-node options follow previous decisions. Dormancy and awakening remain off by default; disabling dormancy disables awakening. Only residual contacts carry real signals from either endpoint; coincident contributions add at the contact. Nodes and edges require their own explicit positive thresholds. Awakening grants no fixed weight or bulk restoration. Weak contacts may promptly sleep again. Deletion/silence cannot be undone, and disabling awakening suppresses in-flight wake effects.

Checkpoints save all local anchors, scheduled emissions/expiry, in-flight packets, STP/fast traces, pending inhibition, isolation timing, local reserves and independent RNG. Identity/definition mismatches, missing required expiry and invalid values are rejected. Old kernels run through their identities; relabeling `/3` as `/4` is not restoration. Explicit structural inheritance is a new birth: projected structure, support/H, stability and historical counts transfer, while dynamic activity, resource history, packets and clocks reset.

Model choices, seeds, region partition and propagation period are fixed at birth. Numeric changes use the existing pause/checkpoint/audit workflow: settle old parameters first, then apply new values, clipping H bounds and resource capacities when reduced. Observation cannot change parameters. API/CLI/UI share the kernel registry and expose executable `/4` options; inactive legacy fields are rejected or hidden.

## Binary interchange and phase evidence (2026-10-09)

JSON retains all object fields. The tmind base Arrow columns remain unchanged; only `/4` adds the explicit `threemind.local-object-columns/1` extension. Nine additional fields per node/edge, including anchors and nested short-term state, follow corresponding rows. Missing fields, row counts or schema mismatches are rejected rather than defaulted. Historical artifact columns are unchanged.

Relevant regressions: 352 passed,11 skipped for unavailable isolated PostgreSQL; six Rust tests and frontend build passed. Local work is independent of unrelated graph size, but the small dense background graph is slower. `/4` stability retains more than H here; full `/3` retains more again. Sampled default H peaks at only30.0035s. [Scope, negative findings and evidence](../../lab/explorations/2026-10-09-local-events-v4/report.en.md).

## 2026-10-13 contract-provenance correction

The statement above about establishing/strengthening contacts between a packet's actual recipients describes the implementation, not a rule independently specified by the user. The user stated that they had not requested internal downstream-recipient pairing; the original pre-approval conversation also contains no such specific decision. Scoring, eligibility, windows and nonlinear inhibition timing changed as well. Retaining ordinary coefficients does not establish unchanged dynamics. `legacy-source` excludes internal packet pairing but does not restore all `/2` behavior. See the [complete delta, authorization and cost inventory](plans/kernel-delta-decay-audit-20261013.md). This correction preserves the earlier implementation record and authorizes no kernel or existing-subject changes.
