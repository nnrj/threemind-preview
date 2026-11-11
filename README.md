# ThreeMind public code preview

This is the independently packaged source preview for the ThreeMind preprint. It includes the Python reference kernels, Rust kernels and standalone runtime, adapters, laboratory API, web workbench, experiment tools and tests. The source version and per-file SHA-256 hashes are recorded in [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json).

This repository starts a new Git history. Manuscript drafts, paper-authoring tools, private discussion archives, credentials, local databases and experimental originals are excluded. The complete project remains separate at <https://github.com/nnrj/threemind>. The intended preview repository is <https://github.com/nnrj/threemind-preview>; preparing this directory does not publish it.

[中文说明](README_CN.md) · [Installation](INSTALL.md) · [Reproducing the experiments](REPRODUCIBILITY.md) · [Data availability](DATA_AVAILABILITY.md)

## Components

| Directory | Contents |
| --- | --- |
| `src/threemind_core`, `src/threemind_kernels` | Python reference implementations and genuine version routing |
| `crates` | Rust implementations, Python native binding and independent runtime |
| `src/threemind_runtime`, `src/threemind_transformer`, `adapters` | Runtime, sensory/motor adapters and personal learning components |
| `src/threemind_lab`, `migrations`, `threemind-ui` | Laboratory, research API, database migrations and web workbench |
| `lab` | Experiment drivers, analysis tools and frozen regression fixtures |
| `tests`, `tests_v2` | Software checks; some integration checks require an isolated database or external data |
| `docs/en`, `docs/zh` | Selected technical and operating documentation |

Historical experimental identities are retained. The current `/5.3` implementation is included but is not substituted for the historical kernels used in the paper. The default decay curve within `/5.3` remains power law.

## Scope

Source inspection, replay of recorded observations, reanalysis, and a new experimental run are distinct operations. Start with verification and reanalysis of the supplied data. Run new individuals only in a new output directory; do not overwrite published evidence. Full-system restoration must preserve Core, personal adapters, optimizer and random state, recent activity, mappings and body state.

This extraction does not grant a new software license or change existing third-party licenses. It does not include a manuscript or a replacement for the preprint.
