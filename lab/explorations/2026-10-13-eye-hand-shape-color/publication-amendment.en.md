# E69 original-registration tooling amendment

2026-10-13. This postprocessing defect was identified after the subject was born and continuous teaching had begun. This is a tooling correction, not a protocol, curriculum, Core or peripheral-learning change, and not a behavioral result.

The frozen bulk publisher infers attachment roles and stages again, although some originals were already registered under the same stable request IDs as protocols, results or birth checkpoints. Resubmitting different metadata produces an idempotency conflict. Isolated tests reproduced this defect; it does not affect the running learner or ordinary stage recording.

The independent `publish_resume.py` preserves the frozen `publish.py`, `pipeline.py`, `journal.py` and experiment sources. It verifies file hashes, sizes, scientific identities and locations, reuses committed receipts, retains unsent requests with their original roles/stages, and registers missing files. If the old publisher has already left a conflicting pending resend, removal is allowed only after a server receipt proves the original commit and differences are limited to role/stage. The rejected request's original bytes and verification proof are archived first. Other differences fail for review. The repair audit is additionally registered through the unified research API without overwriting committed facts.

Execution requires verified computation, analysis and video completion, no uncommitted experience, and exclusive pipeline, runner and storage writer locks. The tool does not load a subject, rerun questions, advance simulation, clear in-flight, change scientific originals or finalize reports. If the original pipeline stops at publication, use [HANDOFF](HANDOFF.md) to resume only this postprocessing step and subsequent report review.

Nine isolated tests passed: the actual frozen publication conflict and its repair, idempotent retry, pending metadata preservation, rejection without server proof, rejection of changed originals, refusal while runner/pipeline/in-flight/unfinished computation is present, and rejection of other metadata conflicts. Ruff passed. These tests used synthetic originals and an in-memory API, without advancing the formal subject.

The tool and amendment are separately preserved under `engineering/publication-repair-20261013`; the original frozen manifest remains intact. The repair has not yet been applied to the completed formal experiment because E69 is still being taught. Actual publication success must be established by its future receipts.

[中文](publication-amendment.zh.md)
