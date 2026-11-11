# M2 timing test: failed approximation and an emission-phase diagnosis

2026-10-16. [Prespecified protocol](pilot-m2-timing.en.md), frozen commit `31b8f3e`. All 288 causal copies from 16 complete parents and eight new origins finished. **Separating cue inputs did not produce the assumed independent arrivals.** Original forecasts, endpoints and every lag remain unchanged; a post-result formula does not replace the failed prediction.

## Prespecified results

S mode; four teaching intensities .25/.35/.45/.55 and two orders each; opposite histories, 15s retention, fixed personal A−B projection. Single cues have dose .5; combined cues have .5 each with 0/1/10/25/50/100ms lag. Normalized/summed configurations are declared causal copies. Parents develop continuously to 32s; children continue to 34s. E69 remains paused.

The primary normalized contrast is `XY-1 at 111ms minus XY-0 at 110ms`, after corresponding same-history/time no-cue subtraction and half the opposite-history difference. Across eight origins the mean is **−.000007926996**, with pointwise source-bootstrap 95% interval [−.000011564061,−.000004389450]. Six origins decrease slightly and two remain zero. This is a .164% decrease relative to the simultaneous mean .004834049, not the predicted near-doubling. It is not a claim of major capability deterioration.

| Lag ms | Normalized mean | Summed mean | Mean origin-level original forecast error |
| ---: | ---: | ---: | ---: |
| 0 | .004834049 | .009668098 | .000000002649 |
| 1 | .004826122 | .009652244 | .002413060927 |
| 10 | .004755939 | .009511877 | .002377969307 |
| 25 | .004643481 | .009286961 | .002321740326 |
| 50 | .003490480 | .008935875 | .002722697694 |
| 100 | .004311723 | .009375308 | .002531792461 |

Each reading remains at the prespecified 110+lag ms. This is the protocol's **nominal second-arrival time, not an established second physical arrival**. Averaging all six XY lags, configurations and histories within origin yields primary MAE .002061210561, interval [.001183964801,.002913395676]. Zero/nonzero classification is 184/192 but amplitude prediction fails substantially; classification does not rescue the primary error. The 192 forecasts are nested, with independent N=8. Separately, 32/288 late-window means are nonzero, without an accuracy or capability-success claim.

![Unchanged prospective forecasts and observed timing effects](E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-timing-v1/figure-v1.png)

## Post-result diagnosis: cue timing is not emission timing

Read-only inspection of `pulse` in `crates/threemind-core/src/local_shared.rs` and saved trajectories shows that the aligned configuration schedules emissions on propagation-period boundaries, constrained by completed_emission. External input can precede same-time emission. Thus X at 32s and Y at 0–100ms later can still emit together at 32.1s and arrive at 32.11s. The approximation incorrectly added input lag to Y's first-arrival time.

Of 192 XY copies, all 144 with nonzero activity first appear at the 110ms grid point; 48 remain zero. For origin o2/history0 at 1ms lag, the 110ms response is .004229602 and the 111ms response .004215730, versus the original forecast .008431460. The forecast added two quantities that actually still underwent joint normalization.

A separate `timing-diagnostic-v1.json` contains an implementation-informed, post-result aligned approximation. Its origin-mean error at 110ms is about 2.80e-9. **This is retrospective interpretation, not prospective validation.** It does not model later pulses or arbitrary phase; no intervention disabling alignment was performed. All timing effects cannot be attributed to a single field from this diagnosis alone.

The next discriminating question is whether a frozen prediction generalizes to unseen absolute input phases and boundary-crossing cues, identifying which arrivals coincide or disappear before transmission/readout. That requires separate new material, not rescoring or rerunning these trials or expanding samples until success.

## Integrity and delivery

All 24 apparatus paths passed whole-state equality across ordinary/frequent observation, restoration and wall-clock pause, plus configuration/definition identity validation. Read-only analysis verified 576 initial/final snapshots, 288 prior forecasts, 144 configuration pairs, all 2,000-frame endpoints and preserved past inputs, mapping, RNG, fixed peripherals and empty body/optimizer. No STOP, new death, orphan in-flight, rollback or original-subject rerun occurred. Review was by the assistant, not external replication.

Parent development totals 512 internal seconds and copies 576s. Host wall time is 123.43s including I/O/API; peak private memory 101.14MiB, not a pure-Core speed measurement. Minimum headroom: commit16.01GiB, RAM13.72GiB, system9.95GiB and data60.86GiB. The 5/4/5/25 guard did not trigger.

Pre-publication: 1,647 files/unique identities, logical and deduplicated logical 23,439,761 bytes, allocated file streams 25,866,832 bytes, no duplicate hard links. Later archives/readback, directory/MFT and database overhead are excluded. Complete final compressed states are 55,004–64,817 bytes, not Core-only RAM.

Originals: [m2-timing-v1](E:/ThreeMindData/experiments/2026-10-16-mechanism-discovery/m2-timing-v1). Project `0477ee18-d906-4ef0-bd59-9e2de76713f4`, record `a2253755-6ea6-5cbc-9d7f-d174441ee56a`. `analysis-v1.json` retains the original failed forecast; the diagnosis is separate. Closure requires full API readback and pending zero, recorded in `publication/final-verification.json`. Recompute with `analyze_timing.py` or run the read-only `diagnose_timing.py`; do not rerun subjects.
