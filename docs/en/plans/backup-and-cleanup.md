# Backup and project/batch cleanup

[中文](../../zh/plans/backup-and-cleanup.md)

This release neither cleans nor reanalyses historical research data. A clean database is not an upgrade prerequisite. The following operations are for the user to perform, after choosing what to retain.

## Backup

In Navicat, connect to the actual `127.0.0.1:5433` instance and select the dedicated `threemind` database. Use an account with complete administrative read access; the application role is subject to project RLS. Pause tasks, stop capture and shut down the workstation normally. Select Backup, include all objects/data, inspect completion and copy the actual file from Open Containing Folder. Test restoration into a separate new database. Menu wording varies by version. [Navicat Windows manual, chapter 15](https://www.navicat.com/manual/pdf_manual/en/navicat_16/win_manual/navicat_en.pdf)

For complete PostgreSQL definitions, also use a native custom-format archive. It is compressed and supports selective restore. [PostgreSQL 17 backup guide](https://www.postgresql.org/docs/17/backup-dump.html)

```powershell
& 'D:\Program Files\PostgreSQL\17\bin\pg_dump.exe' -h 127.0.0.1 -p 5433 -U postgres -d threemind -F c -f 'D:\Backups\threemind-before-cleanup.dump' -W
& 'D:\Program Files\PostgreSQL\17\bin\pg_restore.exe' --list 'D:\Backups\threemind-before-cleanup.dump'
```

Adjust the executable, directory and account locally. Choose a new filename. Enter passwords at the local prompt. Listing contents is not a substitute for restoring into a separate empty database and checking records, definitions and access controls. [pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html)

Cluster roles are outside a single-database dump. Preserve the ThreeMind owner/app roles and grants for cross-instance restoration. An administrator may use `pg_dumpall --roles-only`, recognizing that it includes other roles on that instance. [pg_dumpall](https://www.postgresql.org/docs/17/app-pg-dumpall.html)

Separately retain `.env`, encryption keys, the code revision and manually exported model/evidence files. Keep sensitive backups outside Git. One model export is not a platform backup.

## Cleanup selection

Choose retention by project or experiment batch, considering protocols, seeds, source models, input carriers, controls, failed outcomes, observations and reports together. Unsupported hypotheses and failed experiments are not automatically worthless.

Disposable trial projects, duplicate test batches and unused temporary exports can be candidates. Run the existing Settings → Experiment storage audit yourself, inspect references and the model library's cleanup preview, then perform any chosen cleanup explicitly.

Do not independently truncate events, checkpoints, artifact chunks or report tables in Navicat. They participate in foreign keys, immutable evidence and document references. Archiving does not reclaim storage; deletion does not necessarily shrink physical files immediately. No bypass script or historical-data migration was added by this release.
