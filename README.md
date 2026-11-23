# ThreeMind public code preview

This is the independently packaged source preview for the ThreeMind preprint. It includes the Python reference kernels, Rust kernels and standalone runtime, adapters, laboratory API, web workbench, experiment tools and tests. The source version and per-file SHA-256 hashes are recorded in [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json).

This repository starts a new Git history. Reviewed research histories, discussion extracts, protocols and reports are included. Manuscript drafts, writing/submission discussions, private conversation locators, paper-authoring tools, credentials, local databases and experimental originals are excluded. The complete project remains separate at <https://github.com/nnrj/threemind>.

[Public-edition scope and omissions](PUBLIC_EDITION.md) · [Research history](docs/en/history/index.md) · [中文说明](README_CN.md) · [Installation](INSTALL.md) · [Reproducing the experiments](REPRODUCIBILITY.md) · [Data availability](DATA_AVAILABILITY.md)

## Preprint and contact

Dongxu Liu published the ThreeMind preprint on Zenodo. [*Mapping Before Meaning: An Artificial Consciousness Model Shaped by Experience*](https://zenodo.org/records/24481998) · [DOI 10.5281/zenodo.24481998](https://doi.org/10.5281/zenodo.24481998)

[Public code preview on GitHub](https://github.com/nnrj/threemind-preview) · [Author’s ORCID 0009-0009-5898-5029](https://orcid.org/0009-0009-5898-5029) · [tianhehechu2017@gmail.com](mailto:tianhehechu2017@gmail.com)

## Components

| Directory | Contents |
| --- | --- |
| `src/threemind_core`, `src/threemind_kernels` | Python reference implementations and genuine version routing |
| `crates` | Rust implementations, Python native binding and independent runtime |
| `src/threemind_runtime`, `src/threemind_transformer`, `adapters` | Runtime, sensory/motor adapters and personal learning components |
| `src/threemind_lab`, `migrations`, `threemind-ui` | Laboratory, research API, database migrations and web workbench |
| `lab` | Experiment drivers, protocols, reports, analysis tools, replay resources and frozen regression fixtures |
| `tests`, `tests_v2` | Software checks; some integration checks require an isolated database or external data |
| `docs/en`, `docs/zh` | Technical and operating documentation, research plans and curated histories |

New individuals use `threemind.continuous-memory/6.3`. The preview includes genuine historical kernels, with fixed-function addressing from 6.0. Use the kernel and configuration recorded for each study. The [study index](STUDIES.json) maps the r3 results to research code and evidence.

## Scope

Source inspection, replay of recorded observations, reanalysis, and a new experimental run are distinct operations. Start with verification and reanalysis of the supplied data. Run new individuals only in a new output directory; do not overwrite published evidence. Full-system restoration must preserve Core, personal adapters, optimizer and random state, recent activity, mappings and body state.

The manuscript is available separately on Zenodo.

Three bilingual research-figure groups retain their original paths; `docs/paper` contains these six images only. Edited documents mark each omission and its reason. See [PUBLIC_OMISSIONS.json](PUBLIC_OMISSIONS.json).

## Software license and trademark

The project’s original software and accompanying software documentation are available under the [MIT License](LICENSE). Third-party components retain their own licenses. For the paper, supplementary materials, research figures and data, consult the terms published with the relevant work or dataset. The [ThreeMind trademark policy](TRADEMARK.md) covers use of the project name and official logos.
