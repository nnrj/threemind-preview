# History catalogue and source records

> 2026-11-11 公开节选：稿件整理、投稿讨论或私有会话定位已省略，完整历史原件未改。


[简体中文通史](../zh/history/index.md) · [English history](../en/history/index.md)

[Initial compilation verification / 初编验收](verification.md)

`catalog.json` describes four editions and their Markdown chapters. The Lab API serves it at `GET /api/v2/history`; the `/history` reader follows the same source files. No database migration, simulation or second copy of chapter text is needed.

`source-inventory.json` records the pre-compilation `docs/` and `lab/` Markdown at baseline `e83aedd9aa1f5346341cd78d3c4e9aa7a0df4b2c`. SHA-256 values describe the checked-out file bytes at compilation, including their line endings. The baseline commit supplies an independent Git reference. Later documentation additions do not rewrite this snapshot.


> **Public-edition edit (2026-11-11; source lines 11-11):** Metadata wording is updated to describe this public extract; private conversation locators are not provided. The complete source remains unchanged.



`conversation-excerpts.json` retains only the selected publishable messages quoted in the source chapters, with public source IDs, statement dates and original text hashes; private conversation IDs and locators are omitted. It is not a full conversation export and contains no tool logs or internal reasoning. The author approved inclusion of the personal recollections in the founding statement. Publication editing and submission discussions are outside this public edition. Original Chinese quotations are retained in the English edition with explicitly labeled editorial summaries.

For continuation, follow the [editorial method](../en/history/editorial.md). Validate with:

```powershell
& .work/kernel-venv/Scripts/python.exe tools/validate_history.py
```

Any supported Python 3 environment can run this dependency-free check. Frontend/API changes additionally require their affected tests and a production build. Do not regenerate the source snapshot from future working trees or treat compilation as authorization to change Core.

To read without starting PostgreSQL or any worker, build `threemind-ui`, then use the project's Python environment:

```powershell
& .work/kernel-venv/Scripts/python.exe tools/serve_history.py --port 8911
```

Open `http://127.0.0.1:8911/history`. This optional service binds only loopback and exposes read-only documentation routes. Stop it with Ctrl+C. The normal Lab service also provides the History menu after its next restart; the standalone reader does not replace or stop that service.

Public-edition file hashes and transformations are listed in the repository SOURCE_MANIFEST.json. The historical baseline hashes in source-inventory.json remain historical provenance, not hashes of the edited public copies.
