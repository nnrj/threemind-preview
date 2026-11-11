# Storage and scientific state

Added 2026-10-10. PostgreSQL remains the authoritative Lab store for scientific state. External carrier originals, offline research registrations, formal data bundles, explicit migration and manual backups are documented in the [data management guide](data-management.md). Policies affect future writes; changing a setting does not migrate existing data. Migrations 060/061 were tested only in isolation, without upgrading the user's database or performing generic migration.

The existing detailed storage rationale is preserved in the [Chinese storage document](../zh/v2-storage.md); this short entry links the delivered tools without rewriting historical conclusions.
