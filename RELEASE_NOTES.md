# Public preview releases

## 2026-11-22

The source snapshot now corresponds to `b1ea13db51efdf5abbdcfad9f948649a9506960e`. It includes kernels 6.0–6.3, the associated historical comparisons, the r3 experimental scripts, and the paused aquatic studies. [Study index](STUDIES.json) · [Source checksums](SOURCE_MANIFEST.json) · [Dataset scope](DATA_AVAILABILITY.md).

## Initial public preview — 2026-11-11

The following paragraphs record the initial extraction; the supplement below updates its scope.

This independent source snapshot was prepared from commit `8f56c7872458f40e9367c7144d74968fa7187a19`. The source repository was already clean after the requested `git add .` and commit check; no empty commit was created. No source Git history is included in this preview.

The export preserves the selected source files byte-for-byte and lists their hashes in `SOURCE_MANIFEST.json`. New preview-only files provide installation, provenance, data indexing, checksum verification and a read-only reanalysis entry point. `.gitattributes` disables newline conversion so frozen source checksums survive checkout on different operating systems.

Excluded material includes manuscript drafts, supplementary manuscript documents, paper-authoring tools, private discussion/history archives, live configuration, credentials, databases, experimental payloads, dependency caches and build outputs. The companion data preview has no manuscript files. Research protocols and scientific reports document the actual experiments and remain included.

Historical scientific reports may refer to internal paths or additional studies outside this selected package. Use `STUDIES.json` and `REPRODUCIBILITY.md` as the public entry points. Original negative results and report revisions are retained. Nothing was uploaded, pushed, or rerun during extraction.

See `VALIDATION.json` for the completed local checks and `PRIVACY_REVIEW.json` for the scan scope. The preserved source repository and the author-supplied manuscript were checked again after packaging.

## 2026-11-11 — Reviewed documentation and history supplement

Added 2,721 source-derived files: 2,635 byte-identical copies, 85 marked public editions and one Git-attribute packaging adjustment, plus separate public-scope and figure-provenance documents. Technical documentation, research histories, protocols, reports, summaries, configurations, replay HTML/templates, two history tools and their tests are included. Six authorized scientific PNGs retain their original paths and bytes. Manuscripts, writing/submission discussions and private conversation locators remain excluded. Author-approved founding recollections remain included.

Each edited Markdown location or JSON record states the omission reason. PUBLIC_OMISSIONS.json indexes source-line spans without copying removed material. SOURCE_MANIFEST.json distinguishes exact copies from edited public editions; tools/verify_preview.py now verifies both and the generated provenance files.

History validation passed for four editions and 135 chapters; five focused history tests passed. The first sandbox test attempt failed because Windows denied access to its temporary fixture directory; the authorized isolated rerun passed. Existing application code is unchanged. The workbench API's pre-existing docs/paper image restriction remains; direct file/Markdown image links are retained. No kernel regression, scientific run, service, push or upload was initiated for this supplement. Source integrity checks found all 6,070 original tracked files unchanged and the original Git worktree clean.

A preview-only Git-attribute override preserves JSON bytes in one historical experiment directory. The first staged-byte audit found one newline-normalized file; original source remains unchanged. Packaging metadata is separated from scientific-document edits in SOURCE_MANIFEST.json.
