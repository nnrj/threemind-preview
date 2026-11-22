# Documentation and history maintenance

When a task changes a ThreeMind hypothesis, kernel/protocol behavior, consequential default, research conclusion, or important research decision, follow `zh/history/editorial.md` (English: `en/history/editorial.md`) and extend the history within that authorized task.

- Keep existing sources in place. Append dated corrections; distinguish contemporary sources, later recollection, implementation facts, hypotheses and editorial inference.
- Preserve original version identities and fixed experimental criteria. Never rewrite an old report to fit a newer default or a later interpretation.
- Update corresponding modern Chinese/English chapters, milestones and relevant theme. Extend the two Classical Chinese works for major phases without changing facts for style.
- Register new history chapters in `docs/history/catalog.json` and run `tools/validate_history.py`. The UI reads the same Markdown; do not create a competing database copy.
- Archive only relevant, publishable quotations. Never copy credentials, unrelated private conversation, tool logs, internal reasoning or large experiment data into public docs.
- Minor typo fixes do not require a new historical event. Unknown dates or motives stay unknown until new evidence is available.
- Maintain the current summary in `zh/plans/research-backlog.md` and its English counterpart after research/tooling delivery or consequential research decisions. Update the relevant stable item IDs with status, evidence and remaining work, then append dated history. Keep original entries below intact; recommendations and deferred items do not authorize new experiments.

## Writing and bilingual translation (2026-11-21)

Use `zh/writing-guidelines.md` and `zh/translation-guidelines.md` (English counterparts under `en/`) when drafting, substantially revising or translating documentation, reports, manuscripts, supplementary materials, captions and glossaries. The writing guide contains the author's eleven requirements and examples; the translation guide covers fidelity, natural English, terminology, logical conditions and cross-language review.

Start from the author's designated revision and established definitions, not an outdated English draft or glossary. Preserve factual scope, scientific claims and protected passages. Separate stylistic edits from substantive corrections and apply the authorization already given. Include figures, tables and supplementary materials in consistency checks. Do not add an approval procedure for ordinary copyediting or invent a research milestone for a wording correction.

## Explicit scientific conclusions in reports (2026-10-16)

Follow `zh/plans/experiment-conclusion-contract.md` and its English counterpart. A report must explain its purpose and expectation, interpret the evidence, answer the scientific question and state the implications for ThreeMind. A verdict/score table alone is incomplete. Preserve preregistered scope and statistical honesty; neither move success criteria after results nor turn a failed gate into universal falsification. Mark retrospective interpretation, append published report revisions with provenance, and check the platform entry as well as repository text. The all-history audit is `zh/plans/report-conclusion-audit-20261016.md` (English counterpart available).
