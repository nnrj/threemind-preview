# Read brief responses separately from sustained stability

Decision: 2026-10-02. New tool: `threemind.response-readout/1`. The meaning of `target-observation/1`, activity-monitor records and Core identities is preserved.

## Reason

The user's requested notion of convergence is a clear response, however brief. Here **response convergence** names an observed response result; it does not require a lasting steady state. Responses may be short, tied or followed by another response. Detection is not a claim of semantic correctness or proof of the mechanism responsible for competition.

The 800 ms requirement was an engineering choice, not a user hypothesis or an established physiological bound. The trace is `settle_ticks: 8` in `97d8592:adapters/threemind_adapters/temporal.py`, `settle_us=800000` in `4e43349`, and reuse of that default with uninterrupted local activity in `ce311d6`. Why the original eight cycles were chosen remains unverified. Requiring that window to acknowledge a brief response does not serve this research question.

## Fixed rules

- Read complete saved activation vectors; all nodes by default, explicit targets optionally. Unknown IDs are errors, never silent zero responses.
- No minimum duration. Record entry, observed total-activation crests (earliest point of a plateau), changes of leaders/ties, and at least the maximum sample of each episode. A single sampled point is retained.
- Rank actual activation at **one common sample time**. Zero nodes are implicit; never combine each node's independent maximum into a fictitious simultaneous output. Leader margin is descriptive, not an expected-answer gate.
- The default detail is the response with greatest total activation in the window, earliest on a tie. All other detected responses remain available. This is a display rule, not semantic scoring.
- Default numerical tolerance is `1e-12`, configurable down to zero; raw measurements remain intact. Empty sampling, no activity, gaps and window boundaries are distinct.
- A single point has unknown actual duration. Gaps break continuity. Observed rise/fall does not by itself identify a competitive causal mechanism.
- The old tool retains its 800 ms and distribution/amplitude conditions and remains independently callable. No historical verdict is overwritten. The new analysis never feeds back into Core, buses, sampling schedules or dynamics.

The complete-record view in “Stimuli and outputs” opens Response readout by default; Sustained stability (legacy) remains selectable. The `/readouts/{record_id}/response` API, `python -m threemind_runtime.observation_cli response` CLI and batch `response` operation share one implementation. Live sampling windows and stored chat classifications are not silently replaced.

## Acceptance and archived-data analysis

Test isolated points, brief pulses, multiple peaks, leader changes at constant total activation, ties, zero activity, gaps, censoring and annotation independence. Then reread existing E23/E24 trajectories without training again or selecting favorable windows. Targets use the original anonymous A/B channel identities. Publish old/new criteria side by side and source-file hashes; originals remain read-only.

Budget: zero new simulations, at most 400 existing record files, one offline process with a 10-minute limit and 512 MiB new evidence limit. Keep at least 2 GiB free RAM, 5 GiB on C and 15 GiB on E. Missing samples cannot be recovered by a new algorithm; request new sampling only if necessary.

Implementation status and evidence belong in the delivery report.

## Implemented 2026-10-02

UI, API, CLI, operation catalog and batch integration are complete; the legacy stability tool is preserved. 57 affected checks and desktop/mobile browser tests passed. Reanalysis of 188 windows reads 94 brief target responses with no target detections in uncued controls. Bilingual designs, reports and evidence are saved in the separate E25 project. [Report](../../../lab/explorations/2026-10-02-response-readout/report.en.md) · [Delivery](../../../lab/explorations/2026-10-02-response-readout/delivery.en.md)
