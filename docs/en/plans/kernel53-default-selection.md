# 11 November 2026: inverse-logarithmic decay becomes the /5.3 creation default

[中文](../../zh/plans/kernel53-default-selection.md)

## Decision and evidence

After comparing power-law and inverse-logarithmic retention and performance, the user explicitly selected inverse-logarithmic decay as the /5.3 default, retained the other choices, and requested visible /5.2 and /5.3 options with /5.3 selected by default for new individuals. This is a contextual paraphrase of a message containing typing errors, not a reconstructed quotation.

The decision prioritizes the curve with demonstrated retention advantages. Across 48 independent origins, R47b confirmed better experience expression at 300 internal seconds than the other three curves. In the R47c whole-individual exploration, inverse logarithmic decay passed initial retention, new learning with preservation of prior learning, and relearning in 8/8 origins each; power law scored 1/8, 3/8, and 8/8. Inverse-logarithmic reversal scored 4/8 against a registered 6/8 target. All four curves failed the weak-experience deletion target at 30 seconds. This selection preserves the original targets, scores, and conclusions.

Longer retention may increase the number of connections retained during extended operation; total memory use remains a measurement for larger tasks. The existing inverse-logarithmic formula is used unchanged. No new parameters or changes to transmission, reinforcement, deletion, retention growth, or relaxation are introduced.

Evidence: [R47b confirmation](../../../lab/explorations/2026-11-11-kernel53/confirmation/report.en.md), [R47c continuous joint learning](../../../lab/explorations/2026-11-11-kernel53/joint/report.en.md), and [R48 whole-individual comparison](../../../lab/explorations/2026-11-11-weight-dependent-decay/joint/report.en.md).

## Scope

| Entry point | New-individual default | Retained choices |
| --- | --- | --- |
| Python registry, research API, workbench | `threemind.continuous-memory/5.3` | All historical versions, including genuine /5.2 |
| /5.3 configuration and Rust constructor | `inverse-logarithmic` | `exponential`, `power-law`, `power-exponential` |
| Standalone Rust runtime without a kernel selection | /5.3 with inverse-logarithmic decay | Explicit `--kernel`, configuration, and compiled definitions |
| New language-experiment dialog | Default identity supplied by the API | Explicit selection; copies retain the source individual's identity |

/5.2 retains its exponential default. In /5.3, reinforcement preserves age and retention-scale growth and relaxation remain disabled by default. Saved user templates, explicit configurations, and complete snapshots take precedence over factory defaults. Restoration uses the saved identity and full configuration, without migrating historical individuals. R48 remains a separate research kernel.

The interface gains bilingual descriptions and includes /5.2 and /5.3 in existing dormancy-control behavior. Checkpoint energy display now recognizes /5.3 local fields; this reads saved state without advancing simulated time.

## Verification and delivery

Checks cover creation defaults, every selectable curve, API configuration catalogues, frontend creation, Python/Rust agreement, and restored trajectories under historical identities and curves. Engineering specimens are isolated from research individuals. Original evidence packages, frozen research binaries, reports, and author manuscripts remain intact.

- Targeted regression: 332 checks passed after correcting a missing standalone-runtime environment variable and one test using old-version configuration fields. All 16 initial failures passed on rerun; the initial batch skipped 13 database-dependent checks.
- A subsequent isolated database batch passed 26 API checks for creation, templates, configuration and persistence. The test cluster started for this batch was then stopped.
- Twenty Rust unit checks passed. After installing the wheel in the project environment, 25 checks passed. These sets overlap with the earlier regression and are not summed as independent experiments.
- Four browser checks passed for the /5.3 default, /5.2 and /5.3 curve choices, explicit alternatives and historical-version creation; the production frontend build passed. Initial static-server connection refusals were resolved with a threaded test server. The real workbench was unaffected.
- History catalogue, bilingual links, Git data boundaries and diff checks passed.

New artifacts and engineering manifests are in `.work/kernel53-default-20261111/`; the previous installation is backed up under `installed-before/`. The new wheel is installed in `.work/kernel-venv`, where default construction was verified. Workbench/API processes were not restarted; a normal restart loads the new defaults. This delivery does not resume any existing experiment.
