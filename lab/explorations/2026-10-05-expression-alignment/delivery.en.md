# E47 delivery and reproduction

2026-10-05. [Report](report.en.md) · [简体中文](delivery.zh.md)

Platform project: **E47 表达延迟与新经历**, ID `4e645e2b-1408-4e6b-a651-a8e12acf765c`. Designs, interim findings, final bilingual reports and full evidence are published through ThreeMind services to this separate project. Select it in experiment notes / records and reports. The document menu also opens reports by path. Exact publication IDs are recorded in `delivery.json`, resource growth in `publication-resources.json`.

## Open the evidence

- [Interactive item/time viewer](../../../.work/expression-alignment-20261005/expression-alignment.html): source, history, scope, training regime and direction; preserves incorrect words, blank output and sampled intervals. Includes normal/target/control intervention counts.
- [Main figure](findings.png), [original-unit process figure](process-patterns.png), [results JSON](results.json), [post-result familiar-answer description](interpretation-checks.json).
- [Reusable tools and CLI](../../../docs/en/reference/expression-observation-tools.md). CPU works; unavailable CUDA falls back to CPU. Docker is unnecessary.

Viewer option/table/time/overflow/script checks passed at1440 and390px; screenshots are in working `viewer-qa/`. Figures were visually inspected. Production pages were unchanged; this offline viewer check does not establish live-chat integration.

## Evidence and execution order

Working evidence `.work/expression-alignment-20261005` contains1458 source/probe records, processes, model/observation manifests, physical telemetry tape, timing, calibration, interventions and platform receipts. `dependencies.json` identifies old E46 project/archive dependencies without duplicating its whole archive. Required frozen input weights/background are separately copied. Old states were not trained further or rewritten.

Use the project Python. This batch is already complete: **do not blindly rerun into the same output directory**. Outputs use new-file semantics and resume completed cases; a new reproduction needs a new study ID/directory and pinned old dependencies.

1. `experiment.py prepare` registers; `calibration` adds B probes; `latency.py` compares processing of actual windows.
2. `features.py` compares B readers; `new_experience.py` creates C sources/probes.
3. `expression.py features/train`, then the same operations with `--scope all`; mappings, splits and24 model manifests are preserved.
4. `mediation.py` performs the preregistered60 naming interventions.
5. `results.py` builds tables/figures/viewer; `diagnostics.py` describes familiar-answer reuse; `viewer-check.mjs` validates the viewer.
6. `publish.py` uses services for reports, records, notes, artifacts and a single archive pass. It verifies this project's document hashes, without rehashing all historical evidence.

Budget:6GiB working-evidence expansion stop,10GiB hard total including archive and database. The batch stayed well below these. Recorded compute57.72min; account readings43% at start and44% at compute completion include shared-account use and are not exact task attribution.

## Not delivered

New-assignment prerequisites failed, so composition and larger vocabulary were not started. No Core/default/input/death changes were made. No unprompted contrast was used to declare dreams absent. Production real-time chat, twin-free expression, voluntary speech and general language understanding remain open. Recommendations and their rationale are in the report and backlogR17/T07. Tools are reusable without a new parallel bus or database per experiment.
