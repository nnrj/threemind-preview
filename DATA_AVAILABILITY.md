# Data availability / 数据获取

The companion dataset is named **threemind-data-preview**. The verified 11 November export contained 28,314 evidence files (42.535 GiB), selected against the earlier revision. For r3 study mappings, see [STUDIES.json](STUDIES.json).

**Public download URL / DOI: to be supplied by the author after upload.** This extraction has not uploaded the code or data. The intended source repository is <https://github.com/nnrj/threemind-preview>.

Place the dataset beside this code checkout, or pass its location explicitly to the verification/reanalysis commands in [REPRODUCIBILITY.md](REPRODUCIBILITY.md). Its `MANIFEST.jsonl` and `EXPORT.json` identify every original byte sequence. It includes sealed evidence archives, complete subject states, personal adapter learning states where used, trajectories, analyses and replay media. Some historical packages are stored under content hashes; the dataset's `OBJECTS.jsonl` identifies their formats and experiment memberships.

No paper draft is included. Experiment design records and scientific reports are included to document the criteria, outcomes and historical corrections. Use the version-specific protocol for each study. The public preview does not silently substitute the latest kernel for a historical one.

中文：数据另存，不在代码 Git 仓库中。请在数据托管平台发布后补充永久地址。使用前先按数据包清单核验，实验编号、论文小节、数据位置和代码位置见同一份索引。

The installed data package records its own release date, file count, and SHA-256 hashes in `EXPORT.json` and `MANIFEST.jsonl`. The r3 code preview also identifies later evidence from the two research-data volumes. See `r3_studies` in the study index. Counts for the earlier export should not be used as an r3 total.

数据预览版以自身的 `EXPORT.json` 和 `MANIFEST.jsonl` 标明实际收录的材料。代码索引包含 r3 新增的研究。上列数量指 11 月 11 日已经核验的那一版。
