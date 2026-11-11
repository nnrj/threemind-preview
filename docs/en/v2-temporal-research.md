# Temporal readouts, continuous chat and research records

[中文](../zh/v2-temporal-research.md) · [Implementation and acceptance](plans/temporal-chat-restoration.md)

This release connects existing temporal observations to everyday operation and research records. Core dynamics, sensory mapping, sampling equations, candidate selection and convergence criteria are unchanged. A temporal observation describes an interval, rather than a single peak or an automatically inferred verbal answer.

## Conversation

The network sidebar and conversation page share one continuous bubble stream. Inputs appear on the right; passive and temporal readouts and enabled external interpretations appear on the left. Readable external annotations appear directly in the body. Anonymous observations retain their anonymous identity; AI does not invent a response.

Passive labels use legacy activation ordering, with contact traces, stability and identity as tie breakers; disabling this display option uses identity order. Temporal bodies show seven candidates in **recorded scientific order** by default. The display count can be changed; zero permits paging through all candidates. It does not change the scientific `comparison_top_k`. Text deduplication never removes nodes. Auxiliary identity previews show seven IDs with the full count; complete data remains expandable.

Expand a message to inspect all nodes, including non-candidates and zeros. Window-end activation, window peak and composite score are distinct columns. Evidence links open complete measurements and exports. Envelope identity supplies provenance, not proof that every overlapping activity was caused by that input.

The media plus menu and four organ controls precede the textarea; intensity and send follow it. Upload dialogs initially inherit the composer intensity. Enter sends by default, Shift+Enter inserts a newline, existing preferences persist, and IME composition cannot trigger a send. Accepted sends clear the draft; failures retain it. Organ changes still require Runtime acknowledgement.

New messages follow the bottom, while long messages start at their beginning. Scrolling upward preserves the reading position. History loads in batches of 40 with at most eight cached pages and a variable-height virtual viewport. Evicted pages remain cursor-accessible. Similar samples are not silently merged or discarded. Delivery status refreshes independently. Hiding passive readouts does not hide temporal results or alter collection.

## Temporal experiment

Open a consciousness → Temporal and snapshot readouts → Temporal observation experiment, or Manual experiments → Sensory and probe calibration. Temporal observation is the default tab; the earlier fixed-window calibration remains separate.

Choose a checkpoint, or leave it blank to pin the latest saved checkpoint at submission. Enter complete probe sentences and doses. Each probe independently continues the source's full state, with activity and queued events retained; recoverable observation context is inherited where available. Defaults are zero pre-stimulus wait and inherited learning. Birth, a learning override, waiting and reader overrides require explicit configuration. Graphical and JSON forms synchronize and validate at conversion and submission.

The existing temporal defaults remain: 100 ms sampling, at least 1.2 s after actual final delivery, an 0.8 s settling segment and at most 12 s from first delivery. Existing classifications can finish a window earlier. Death, disabled observation and interrupted budgets remain explicitly distinguishable. The source consciousness is never stopped or advanced by the probe.

Budgets: at most eight cues by six doses, a 2,000-node/100,000-edge/64 MiB source, 60 seconds wall time by default (explicitly configurable to 300 seconds), 2 GiB Lab process RSS and a 64 MiB evidence bundle. Unstarted cases remain `not_observed`; unfinished observations remain censored/interrupted. Exceeding the final hard archive limit fails explicitly rather than publishing incomplete evidence as complete.

## Records and reports

| Source | Row unit | Main evidence |
| --- | --- | --- |
| Temporal windows | One window or explicitly unobserved probe | Timing, coverage, classification/reason, convergence time, complete window payload |
| Temporal nodes and ranks | One node within a window | Rank, score, duration, integrals, final/peak values, raw metrics and external labels |
| Temporal activity series | One sample within one selected window | Excess activity total and active-node count |

Ongoing observations are fixed to a checkpoint revision and time interval. Independent experiment sources are fixed to a completed artifact hash. A curve selects exactly one window, preventing unrelated probes from being joined into an invented trajectory. Sources can be combined into records/reports and exported as Markdown, HTML, Word, PDF and a complete evidence ZIP.

`convergence_seconds` is missing unless convergence criteria were met. Peak and final values are not interchangeable. Node integrals summarize discrete samples, not continuous per-node trajectories. Nodes, samples and copies sharing a source are not automatically independent replicates. No historical results are backfilled or reanalysed.

## Standalone Runtime

The Python Runtime host supports the Rust native and Python reference backends without a Lab database:

```powershell
.\.venv\Scripts\python.exe -m threemind_runtime.cli --model source.tmind --text-input cue.txt --clock unbounded --until-us 15000000 --readouts readouts.jsonl --export after.tmind
```

The whole UTF-8 file is one carrier using the model's existing sensory profile. `--readouts` must name a new JSONL file. `--until-us` is this CLI job's absolute simulation deadline, not a default consciousness lifespan. Unfinished windows at a finite cutoff are censored. An optional `--readout-config reader.json` specifies `structural_readout` and `temporal_readout`.

For resumable observation, add `--store recovery.sqlite`; resume with `--resume --store recovery.sqlite --readouts part2.jsonl` and a later absolute deadline. The store includes Core, input-bus and reader context. Pauses do not advance simulation time. This extends the Python host CLI, not the separate minimal Rust executable's flags.

The database-free calibration CLI accepts `{"mode":"temporal","cues":["甲。"],"intensities":[1]}`:

```powershell
.\.venv\Scripts\python.exe -m threemind_runtime.calibration_cli --model source.tmind --protocol temporal.json --output temporal-evidence.zip
```

Protocols lacking `mode` retain their older fixed-window interpretation. An exported model without Lab observation context cannot reconstruct previous baselines or labels; actual coverage is recorded.
