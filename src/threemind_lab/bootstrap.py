from __future__ import annotations

import getpass
import json
import os
import secrets
from urllib.parse import quote

import psycopg
from psycopg import sql

from .config import ROOT, load_env
from .database import migrate


def provision(
    admin_parameters: dict,
    *,
    database="threemind",
    owner="threemind_migrator",
    app="threemind_app",
    app_password=None,
    owner_password=None,
):
    """Create only dedicated named resources. Existing resources require explicit migration.

    Credentials never appear in log output or command-line arguments.
    """
    app_password = app_password or secrets.token_urlsafe(32)
    owner_password = owner_password or secrets.token_urlsafe(32)
    with psycopg.connect(**admin_parameters, autocommit=True) as db:
        present = db.execute("SELECT datname FROM pg_database WHERE datname=%s", (database,)).fetchone()
        roles = db.execute("SELECT rolname FROM pg_roles WHERE rolname=ANY(%s)", ([owner, app],)).fetchall()
        if present or roles:
            expected = db.execute(
                "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=%s", (database,)
            ).fetchone()
            if not present or {r[0] for r in roles} != {owner, app} or expected[0] != owner:
                raise ValueError(
                    "Dedicated resource names already exist with a different owner; no existing credentials were changed"
                )
        else:
            db.execute(
                sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD {}").format(
                    sql.Identifier(owner), sql.Literal(owner_password)
                )
            )
            db.execute(
                sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD {}").format(
                    sql.Identifier(app), sql.Literal(app_password)
                )
            )
            db.execute(
                sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8'").format(
                    sql.Identifier(database), sql.Identifier(owner)
                )
            )
    host = admin_parameters.get("host", "127.0.0.1")
    port = admin_parameters.get("port", 5433)

    def url(user, password):
        return f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/{database}"

    owner_url, app_url = url(owner, owner_password), url(app, app_password)
    migrate(owner_url)
    with psycopg.connect(owner_url) as db:
        db.execute(sql.SQL("GRANT USAGE ON SCHEMA tm2 TO {}").format(sql.Identifier(app)))
        db.execute(
            sql.SQL("GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA tm2 TO {}").format(sql.Identifier(app))
        )
        db.execute(sql.SQL("GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA tm2 TO {}").format(sql.Identifier(app)))
        db.execute(
            sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA tm2 GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO {}").format(
                sql.Identifier(app)
            )
        )
        db.execute(
            sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA tm2 GRANT USAGE,SELECT ON SEQUENCES TO {}").format(
                sql.Identifier(app)
            )
        )
    return owner_url, app_url


def setup_existing(*, interactive=True):
    load_env()
    password = os.getenv("THREEMIND_PG_ADMIN_PASSWORD")
    if not password and interactive:
        password = getpass.getpass("PostgreSQL administrator password: ")
    if not password:
        raise ValueError("Fill THREEMIND_PG_ADMIN_PASSWORD in the local .env")
    params = {
        "host": os.getenv("THREEMIND_PG_ADMIN_HOST", "127.0.0.1"),
        "port": int(os.getenv("THREEMIND_PG_ADMIN_PORT", "5433")),
        "dbname": os.getenv("THREEMIND_PG_ADMIN_DATABASE", "postgres"),
        "user": os.getenv("THREEMIND_PG_ADMIN_USER", "postgres"),
        "password": password,
        "connect_timeout": 5,
    }
    # Persist generated credentials before DDL so an interrupted setup can retry.
    pending = ROOT / ".work/bootstrap.json"
    pending.parent.mkdir(parents=True, exist_ok=True)
    if pending.exists():
        keys = json.loads(pending.read_text(encoding="utf-8"))
    else:
        keys = {"app_password": secrets.token_urlsafe(32), "owner_password": secrets.token_urlsafe(32)}
        pending.write_text(json.dumps(keys), encoding="utf-8")
    owner_url, app_url = provision(params, **keys)
    path = ROOT / ".env"
    lines = path.read_text(encoding="utf-8-sig").splitlines() if path.exists() else []
    remove = ("THREEMIND_PG_ADMIN_PASSWORD=", "THREEMIND_DATABASE_URL=", "THREEMIND_MIGRATION_DATABASE_URL=")
    lines = [line for line in lines if not line.startswith(remove)]
    lines.extend(["THREEMIND_DATABASE_URL=" + app_url, "THREEMIND_MIGRATION_DATABASE_URL=" + owner_url])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    pending.unlink()
    return {
        "database": "threemind",
        "port": params["port"],
        "application_role": "threemind_app",
        "administrator_password_removed": True,
    }
