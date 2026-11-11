# Mechanism discovery preparation package

**Report-revision entry, 16 October 2026:** Eleven current-batch groups now include scientific analysis, explicit conclusions and implications for ThreeMind, preserving original scores and evidence. [Latest editions](report-revisions-20261016.en.md) · [Historical audit](../../../docs/en/plans/report-conclusion-audit-20261016.md). Older links retain their historical reports and do not trigger repeated computation.

16 October 2026 closure supplement completed: X1 local experience/two-gate transfer PASS (6/8 origins, donor arrivals 0/48→44/48, unrelated 44/48 unchanged); X2 trace/cue-expression separation PASS in 8/8 at 30/60s and transient/sustained separation PASS in 8/8 at 1/30/60s; relearning savings zero, FAIL. X3 ThreeMind passes all four in 8/8 each; no registered comparator passes all four, so discrimination PASS. All 80 units and 5,568 whole snapshots completed with original-file audit and full API archive readback, verified/pending0. Rules frozen at b574881; old originals, E15 and failures retained; no Core, author-paper or E69 change. [Report](closure-report.en.md) · [Contract](../../../docs/en/plans/experiment-conclusion-contract.md)

First bounded batch delivered, 16 October 2026: seven sub-batches completed and one apparatus batch failed under its original rule; all eight records currently verified/pending0 after full API archive readback. M1 localizes a selective early expression route; M3 shows history dependence also in simple memory controls. M2 preserves the timing forecast failure and then prospectively validates a first-cycle account on new phases/doses/23s retention. Read-only graft audit rules out directly applying the old state/2 equal-topology tool to/5.1. Full M1–M3 questions, confirmation and the wider program remain open. No further overnight M2 expansion; this bounded continuation is PAUSED, and E67/E68/E69 stayed PAUSED. [First-batch report](first-batch-report.en.md) · [Phase report](report-phase.en.md) · [Graft readiness](exchange-readiness.en.md)

**2026-10-16 about 05:03 addendum:** The M2 reception pilot completed eight new origins and 448 causal copies. Six eligible origins have joint/single ratios of 1 under normalization and 2 under summation; two zero origins remain included. Unfitted route/receiver forecasts were saved before probes and classify all 224 nested forecasts, with independent N still eight. This is bounded symmetric simultaneous-input prediction, not a universal memory law. Full API readback verified/pending0. V1 failed only apparatus identity-whitelist acceptance before scientific origins; evidence is preserved. A bounded timing pilot will test the synchrony assumption, without confirmation expansion, Core changes or E69 resumption. [Report](report-fusion.en.md) · [Theory map](m3-theory-map.en.md)

**Update, 16 October 2026, 04:35:** This directory has progressed from preparation to bounded exploration; the original preparation text remains below. M1, the first M2 pilot, the M3 history-dependence component and an independent sampling calibration have verified API archive readback and pending-zero closure. The overall program is not complete. [M1](report-m1.en.md) · [M2 and correction](report-m2.en.md) · [M3-C1](report-m3-c1.en.md) · [Sampling calibration](report-sampling-calibration.en.md) · [Current handoff](HANDOFF.md). E69 remains paused; do not rerun closed batches.

[中文](README.zh.md) · [Program](../../../docs/en/plans/mechanism-discovery-20261016.md) · [Protocols](protocols.en.md) · [Evidence](evidence.en.md) · [Verification](verification.en.md)

16 October 2026. Stage-zero evidence preparation and offline tools are implemented; none of the seven packages has run. There is no subject creation, experiment runner, E69 restoration, schedule activation or publication/closure entrypoint. The pause remains. Real apparatus acceptance, eight-origin pilots and confirmation await execution conditions.

From repository root:

```powershell
$prepPython = '.work/kernel-venv/Scripts/python.exe'
& $prepPython -X utf8 lab/tools/mechanism_preflight.py validate lab/explorations/2026-10-16-mechanism-discovery/program.json
& $prepPython -X utf8 lab/tools/mechanism_preflight.py audit lab/explorations/2026-10-16-mechanism-discovery/evidence-manifest.json
& $prepPython -X utf8 lab/tools/mechanism_preflight.py power --effect 0.5 --family-size 3
& $prepPython -X utf8 lab/tools/mechanism_preflight.py power --kind paired-binary --effect 0.1 --family-size 4 --baseline-success 0.5 --discordance 0.3
& $prepPython -X utf8 -m pytest lab/explorations/2026-10-16-mechanism-discovery/test_preflight.py -q
```

Commands print JSON to stdout only. Detailed audit/power outputs reside in ignored `.work/mechanism-preparation-20261016/`, never force-added with original evidence. No service, network, database or Core access occurs. Four commands exist: `validate`, `audit`, `power`, `compare-witnesses`. A schema pass is not launch readiness; all gates remain pending and outputs always state `execution_authorized=false`.

`audit` streams size/SHA256 without unpacking/loading subjects or scanning disks. The source selection is frozen. Later edits to living documents such as HANDOFF produce mismatches: preserve this manifest and make a new review edition, rather than refreshing hashes silently. Missing, unreadable and mismatched sources are distinct. Existing relocation records remain authoritative; this is a review index, not another storage system.

`power` simulates statistical samples. Continuous outcomes are independent origin-level normal paired differences with a two-sided t test. Binary outcomes are one paired Bernoulli result per origin with exact McNemar testing. Repeated questions cannot become independent origins. Binary planning requires baseline success and discordance assumptions. N ranges48–128 in increments16, using10,000 seeded replications. A conditional N is selected only when the Monte Carlo95% lower power bound reaches0.8. This interval captures simulation error, not uncertainty in real variance estimates. Insufficient power returns redesign, without extending N or changing endpoints. Hierarchical/robust estimators require fresh planning.

`compare-witnesses first.json second.json` requires `threemind.observation-witness/1`: subject_id, kernel, canonicalization, boundary, simulated_time_us, input_sha256, event_order_sha256 and ten component hashes: core, peripheral_weights, optimizer, random_state, body, mappings, recent_activity, actuators, environment, input_cursor. Freeze canonicalization and retain dynamic fields; do not delete differences to force equality. Hash an explicitly empty optimizer where appropriate rather than omitting it. This compares supplied witnesses, not an actual engine acceptance experiment. Existing tools remain responsible for complete saving/restoring.

Next: originals/lineage readback → literature/field verification → real apparatus acceptance → renewed scoped execution permission and eight-origin exploration → actual power/task freeze → confirmation → fresh-origin replication. Register eventual work through the unified research API with separate idempotency and receipts. Do not repurpose historical E69 runners or publication scripts.


Timing-batch addendum, 16 October 2026: eight new origins/288 copies completed; the independent-arrival approximation failed (primary MAE .002061211). A 1ms lag slightly reduced the history contrast by about .164%, without the predicted gain. Source and traces suggest common-cycle emission; the post-result phase diagnosis is not prospective validation. Full API readback verified/pending0; original forecasts/scores remain. Freeze the final overnight M2 extension: eight new origins/672 copies, new phases, teaching doses and 23s retention; not yet run. Then assemble the first-batch report, without confirmation expansion. [Report](report-timing.en.md) · [Next frozen protocol](pilot-m2-phase.en.md)

## M5 — 2026-10-16

16 October 2026: M5 completed and closed on eight independent origins with opposite teaching histories. The fixed port reader answers new associations 64/64; target masking gives 0/64, matched masking 64/64, and restoration 64/64 while old answers survive target masking. Port fixed expression, causal attribution and readout-scope benefit each PASS in 8/8 origins. Fixed all-activity expression and attribution each FAIL in 0/8. Continued all-activity calibration improves held-out-dose answers 0/128 to 128/128, PASS in 8/8; the port reader remains perfect with zero gain, FAIL in 0/8 under the original threshold. Audit covers 1,824 examinations and 2,024 scientific whole snapshots; full API archive readback verified, pending=0. Historical E69 and automations stay paused; Core, earlier reports and the author manuscript are unchanged.

[Report](m5-report.en.md) · [Delivery](m5-delivery.en.md)
