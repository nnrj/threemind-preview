# ThreeMind project continuity

For consequential hypothesis, mechanism, protocol, default, experiment or research-decision work, preserve the history as part of the task. Follow `docs/zh/history/editorial.md` (English: `docs/en/history/editorial.md`) and `docs/AGENTS.md`.

Keep historical versions and evidence intact. Append dated corrections and source references; distinguish original dialogue, later recollection, measured results and interpretation. Do not silently rewrite older reports or their criteria. Maintain the modern Chinese/English histories and update the two Classical Chinese adaptations for major phases. Small wording fixes do not require artificial milestones.

History maintenance never authorizes changes to Core dynamics, old instances, original experiment data, or running services beyond the user's task.

## Writing and translation (2026-11-21)

Before drafting or substantially revising project documentation, experimental reports,[Public edition: manuscript editing or private locator omitted.] For translation and bilingual synchronization, also follow `docs/zh/translation-guidelines.md` (English counterpart available). These requirements apply throughout the repository, including reports under `lab/`.

Use the author's designated source and approved definitions. Explain actors, methods and statistical units clearly; state each experiment's conclusion before moving on. Preserve established findings and material uncertainty without adding unrelated disclaimers or post-result criteria. Translation must preserve meaning and claim strength in natural English, including figure labels. Respect protected passages and existing authorization for technical corrections; these guidelines do not authorize rewriting historical reports or changing research mechanisms.

## Kernel change authorization and tool-time isolation (2026-10-13)

Outside clearly isolated temporary experiments, any kernel change not already explicitly authorized by the user requires asking the user and obtaining confirmation before implementation. Existing explicit authorization applies to its stated scope; do not ask again for that same scope, and do not expand it by treating an assistant-authored plan or contract as user authorization. Every kernel change must visibly disclose what changes, why, and its expected/observed impact; distinguish implementation optimization, dynamics changes, default changes and unresolved effects. Temporary experiments cannot silently change production kernels, formal subjects or defaults.

Tools, observation, saving, plotting and host delays must not advance or alter internal simulated time, change event ordering, inject input or mutate dynamics as a side effect. A wall-clock pause of any duration may resume the complete current subject; even a tiny unauthorized intervention measured in simulated time is forbidden. Explicit experimental stimulation, interventions and advancement remain declared operations, never hidden instrumentation.

Version selection must route to that version's genuine implementation and saved identity. Preserve historical behavior with frozen witnesses and cross-version regression checks; never silently upgrade, substitute or repair an old individual under its original version name. See `docs/zh/kernel-change-governance.md` and the English counterpart.

Keep the current summary in `docs/{zh,en}/plans/research-backlog.md` synchronized with completed research/tooling work and consequential research decisions. Update status, evidence and remaining questions as well as appending dated history; preserve stable item IDs and distinguish recommendations from approved work.

## Whole-system experimental continuity (2026-10-07)

When testing a developing consciousness plus learned peripherals, the experimental subject is the whole system. Preserve Core, peripheral weights and learning state, recent readout history, body state, mappings and random state across ordinary stages. A Core-only checkpoint is not a whole-system checkpoint.

Continuity is per individual and its own peripheral, not a requirement that all control groups share one model or configuration. Different groups may use different declared architectures and training conditions. An individual's learned internal-pattern mapping must not be assumed interchangeable with another's. Preserve Core dynamics, the applicable version's hypotheses and established system consistency; explicitly authorized interventions are separate experimental copies with an intact reference.

Before replacing/reinitializing a peripheral, changing the control path, resetting development state, or splitting joint learning into independent fitting, explain the change and its effect on the question to the user and obtain agreement. Do not disclose it only as a limitation after a long experiment. Explicitly authorized ablation, transplant, frozen-reader and cold-start comparison branches already have authorization; keep them separate from the unchanged baseline. Read-only instrument calibration must be described as calibration, not organism learning.

See `docs/zh/plans/system-continuity-audit.md` (English counterpart available). Preserve the original E61 evidence and correction; do not repeat its segmented pipeline as a test of continuous joint development.

## Research data and Git boundary (2026-10-10)

Keep generated experiment originals, checkpoints, detailed trajectories and transfer packages in ignored data storage, not Git. Code, protocols, small summaries and explicitly classified frozen fixtures remain tracked. Follow `docs/zh/plans/data-management-and-storage-separation.md` and the artifact manifests in `lab/artifact-index/`.

Before any local commit, run `python scripts/check-git-data.py`; use `--all-tracked` for a complete index audit. Under the user-authorized 2026-11-10 revision, ordinary files follow GitHub's file limits: above 50 MiB warns without blocking, and above 100 MiB blocks. Ordinary manuscripts and documentation no longer require per-file size exceptions. Research originals, checkpoints and complete trajectories remain excluded regardless of size; necessary frozen fixtures and templates retain their reviewed bounded exceptions. Never bypass those data classifications by renaming originals or changing limits without authorization. The tracked `.githooks/pre-commit` enforces the guard when `core.hooksPath=.githooks` is configured; a failure leaves files and staged changes intact. Installing this local hook does not modify remote repositories.

## Training and evaluation protocol (2026-10-08)

Before teaching, peripheral calibration, corrective training or evaluation, follow `docs/zh/training-protocol.md` (English: `docs/en/training-protocol.md`). Identify the complete subject and working reference, compare actual curriculum/readout/calibration/control conditions, and separate development data from final tests. Preserve the distinct E56 and E64 reference procedures and their evidence limits; the protocol does not authorize new experiments, waive existing branch conditions or replace Core hypotheses.

2026-10-12 clarification: ordinary experiments treat the complete individual as a continuously developing artificial consciousness, like a human student. Preserve internal simulated time and complete state across teaching, calibration sampling, questions, correction and review. Do not restore a common checkpoint per question or discard evaluation experiences without the user's explicit permission. Pausing/resuming the complete current state does not break internal continuity. Necessary ablation/transplant control restorations use separate branches and require user-facing notice before and after; they are not ordinary-test reset permission. Historical protocols do not override this rule. See training protocol v3, section14.


## Experimental conclusion contract (2026-10-16)

Follow `docs/zh/plans/experiment-conclusion-contract.md` (English counterpart available). Preregister complete scientific targets, necessary controls, pass/fail rules and scope. Close each target explicitly; do not add a higher required claim after results or substitute a completed component for an unfinished stated goal. Known necessary alternatives belong in the design; genuinely new questions receive new hypotheses without changing old scores. Invalid measurement and failure to meet a precision target are explicit outcomes, not proof of no effect. Preserve statistical uncertainty and historical criteria.

### Report conclusions and historical revisions (2026-10-16)

Scores and PASS/FAIL tables do not complete a scientific report. Apply the conclusion contract's purpose–expectation–result–analysis–scientific-conclusion–meaning chain: explicitly state what is supported or rejected, why, and which ThreeMind claim or research choice benefits or is challenged. State actual comparative winners on the registered dimension, without inventing overall rankings or adding post-result vetoes. Label retrospective interpretation. Revise published reports by appending dated editions; preserve original data, criteria, text and evidence packages. Check both repository and published report entries, and record consequential interpretation changes in the bilingual history and research backlog.
