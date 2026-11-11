import psycopg
import pytest

from threemind_lab.database import LOCAL_USER, MIGRATIONS, migrate


def test_current_schema_bootstrap_can_repeat_without_recreating_project(database):
    project = database.create_project({"id": LOCAL_USER}, "Migration restart keeps research")
    for _ in range(2):
        migrate(database.test_migration_url)
    with database.tx(project["id"]) as db:
        assert (
            db.execute("SELECT name FROM projects WHERE id=%s", (project["id"],)).fetchone()["name"] == project["name"]
        )
        assert [r["version"] for r in db.execute("SELECT version FROM schema_version ORDER BY version")] == list(
            range(1, len(MIGRATIONS) + 1)
        )


@pytest.mark.parametrize("invalid", ["future", "gap"])
def test_unknown_or_incomplete_schema_history_is_not_silently_repaired(database, invalid):
    with psycopg.connect(database.test_migration_url) as db:
        if invalid == "future":
            db.execute("INSERT INTO tm2.schema_version(version) VALUES(%s)", (len(MIGRATIONS) + 1,))
        else:
            db.execute("DELETE FROM tm2.schema_version WHERE version=2")
        previous = db.execute("SELECT version FROM tm2.schema_version ORDER BY version").fetchall()
    with pytest.raises(ValueError, match="unsupported database schema"):
        migrate(database.test_migration_url)
    with psycopg.connect(database.test_migration_url) as db:
        assert db.execute("SELECT version FROM tm2.schema_version ORDER BY version").fetchall() == previous
