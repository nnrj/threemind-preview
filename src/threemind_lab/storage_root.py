"""Recoverable host root-change orchestration over existing migration services."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID, uuid5

from psycopg import Error as DatabaseError

from .blob_store import CATEGORIES
from .storage_files import StorageConflict, checked_path, file_lock, read_json, relative_key
from .storage_journal import SelectionJournal
from .storage_migration import MigrationService

EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="storage-root")


class RootChanges:
    def __init__(self, database):
        self.database = database
        self.storage = database.blobs.storage
        self.migrations = MigrationService(self.storage)
        self._cancel_cache = None
        self.journal = SelectionJournal(
            self.storage.control_dir, "root-changes", ("resources", "payloads", "projects", "retained_resources")
        )

    def _path(self, identity):
        return self.storage.control_dir / "root-changes" / (str(UUID(str(identity))) + ".json")

    def _tracked(self):
        result = subprocess.run(
            ["git", "ls-files", "-z"], cwd=self.storage.repository_root, capture_output=True, check=False
        )
        if result.returncode:
            raise StorageConflict("cannot establish the source/fixture boundary; root change stopped")
        return {str(self.storage.repository_root / p) for p in result.stdout.decode().split("\0") if p}

    def preview(self, destination, actor):
        destination = checked_path(destination)
        self.storage._outside_control(destination / "originals")
        tracked = self._tracked()
        selected, excluded = defaultdict(dict), []
        registered = {r["id"]: r for r in self.storage.resources()}
        bases = {r: self.storage.resolve_locator(row["locator"]) for r, row in registered.items()}
        projects = self.database.projects(actor)
        payloads = []
        for project in projects:
            with self.database.tx(project["id"], read_only=True) as db:
                db.execute("SELECT set_config('tm.note_user_id',%s,true)", (str(actor["id"]),))
                records = db.execute(
                    "SELECT locator->>'resource_id' resource,locator->>'member' member,"
                    "max(byte_count)::bigint bytes,max(sha256) sha256,"
                    "count(DISTINCT (byte_count,sha256)) versions FROM research_record_evidence "
                    "WHERE project_id=%s AND locator->>'kind' IN ('file','package') AND locator ? 'resource_id' "
                    "GROUP BY locator->>'resource_id',locator->>'member'",
                    (project["id"],),
                ).fetchall()
                active = db.execute(
                    "SELECT count(*) n FROM jobs WHERE project_id=%s AND status IN ('pending','leased')",
                    (project["id"],),
                ).fetchone()["n"]
                if active:
                    excluded.append(
                        {"project_id": str(project["id"]), "reason": "active project writers", "count": active}
                    )
                    continue
            for evidence in records:
                resource, member = evidence["resource"], evidence["member"]
                if resource not in registered or evidence["versions"] != 1:
                    excluded.append(
                        {
                            "resource_id": resource,
                            "member": member,
                            "reason": "missing resource or conflicting evidence identity",
                        }
                    )
                    continue
                row = registered[resource]
                base = bases[resource]
                path = base / relative_key(member) if member else base
                if str(path) in tracked:
                    continue
                if not member:
                    excluded.append({"resource_id": resource, "reason": "unclassified whole-resource reference"})
                    continue
                selected[resource][member] = {"bytes": int(evidence["bytes"]), "sha256": evidence["sha256"]}
            if project.get("role") in ("owner", "researcher") or actor.get("admin"):
                payloads.extend(self.database.payloads.inventory(project["id"], actor=actor["id"]))
        # P1 exact-file manifests remain authoritative even if not in an experiment index.
        from .data_api import registered_artifacts

        resources = self.storage.resources()
        for original in registered_artifacts(self.storage):
            archive = self.storage.repository_root / original["archive_path"]
            for row in resources:
                base = bases[row["id"]]
                if archive.is_relative_to(base) and archive != base and str(archive) not in tracked:
                    selected[row["id"]][archive.relative_to(base).as_posix()] = {
                        k: original[k] for k in ("bytes", "sha256")
                    }
                    break
        files = []
        for resource, members in selected.items():
            row = self.storage.resource(resource)
            if row["writer_mode"] == "unknown" or row.get("migration_id"):
                excluded.append({"resource_id": resource, "reason": "writer undeclared or migration already reserved"})
                continue
            files.append(
                {
                    "resource_id": resource,
                    "revision": row["revision"],
                    "members": members,
                    "bytes": sum(r["bytes"] for r in members.values()),
                }
            )
        files.sort(
            key=lambda r: (
                not any(
                    word in str(self.storage.resolve_resource(r["resource_id"]))
                    for word in (
                        "centered-restart",
                        "centered-learning",
                        "centered-correction",
                        "retention",
                        "local-v4",
                    )
                ),
                r["resource_id"],
            )
        )
        required = sum(r["bytes"] for r in files) + sum(r["bytes"] for r in payloads)
        existing = destination
        while not existing.exists():
            existing = existing.parent
        free = shutil.disk_usage(existing).free
        return {
            "schema": "threemind.root-change-preview/1",
            "destination": str(destination),
            "root_before": self.storage.root_info(),
            "resources": files,
            "payloads": payloads,
            "projects": [str(p["id"]) for p in projects],
            "excluded": excluded,
            "retained_resources": [
                {"resource_id": row["id"], "reason": "not in fixed file selection; retain and classify separately"}
                for row in registered.values()
                if row["id"] not in selected
            ],
            "resource_count": len(files),
            "files": sum(len(r["members"]) for r in files),
            "payload_count": len(payloads),
            "bytes": required,
            "free_bytes": free,
            "reserve_bytes": self.migrations.min_free_bytes,
            "space_sufficient": free >= required + self.migrations.min_free_bytes,
            "source_copies_retained": True,
            "checkpoint_backend": self.database.checkpoint_backend,
            "checkpoint_rule": "only explicitly sealed, unchanged completed subjects; all other checkpoints remain in database",
        }

    def plan(self, destination, actor, *, operation_id, expected_revision):
        operation_id = str(UUID(str(operation_id)))
        path = self._path(operation_id)
        arguments = {
            "destination": str(checked_path(destination)),
            "actor": str(actor["id"]),
            "expected_revision": expected_revision,
        }
        with file_lock(path.with_suffix(".lock")):
            if path.exists():
                previous = self.status(operation_id)
                if previous["arguments"] != arguments:
                    raise StorageConflict("root-change request ID has different arguments")
                return previous
            preview = self.preview(destination, actor)
            if preview["root_before"]["revision"] != expected_revision:
                raise StorageConflict("data root revision changed")
            plan = preview | {
                "id": operation_id,
                "actor_id": str(actor["id"]),
                "arguments": arguments,
                "state": "planned",
                "cancel_requested": False,
                "resource_receipts": {},
                "payload_receipts": {},
                "failures": {},
                "policy_before": self.database.blobs.policies(),
                "checkpoint_backend": self.database.checkpoint_backend,
            }
            self.journal.write(path, plan)
            return plan

    def status(self, identity):
        row = self.journal.read(self._path(identity))
        if row["id"] != str(UUID(str(identity))):
            raise StorageConflict("root journal belongs to another request")
        return row

    def start(self, identity, *, resume=False):
        # A restart never replays a queued task automatically. Resume is explicit.
        EXECUTOR.submit(self.execute, identity, resume=resume)
        return self.status(identity) | {"dispatch": "submitted"}

    def _save(self, plan):
        with file_lock(self.storage.control_dir / "root-journal.lock"):
            current = read_json(self._path(plan["id"]))
            plan["cancel_requested"] = current.get("cancel_requested", False)
            self.journal.write(self._path(plan["id"]), plan)

    def _cancelled(self, plan):
        path = self._path(plan["id"])
        stat = path.stat()
        signature = (str(path), stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        if self._cancel_cache is None or self._cancel_cache[0] != signature:
            self._cancel_cache = (signature, read_json(path).get("cancel_requested", False))
        return self._cancel_cache[1]

    def _check_writers(self, plan):
        from .browsing import read_scope

        # Host-tool metadata only. One authorized query checks the frozen scope
        # rather than opening every project's transaction before every file.
        projects = [UUID(str(project)) for project in plan["projects"]]
        actor = {"id": UUID(plan["actor_id"])}
        with read_scope(self.database, actor) as db:
            count = db.execute(
                "SELECT count(*) n FROM members m JOIN users u ON u.id=m.user_id "
                "WHERE m.user_id=%s AND u.enabled AND m.project_id=ANY(%s)",
                (actor["id"], projects),
            ).fetchone()["n"]
            if count != len(projects):
                raise StorageConflict("project access changed since planning")
            if db.execute(
                "SELECT 1 FROM jobs WHERE project_id=ANY(%s) AND status IN ('pending','leased') LIMIT 1", (projects,)
            ).fetchone():
                raise StorageConflict("a project writer became active; pause it before resuming this migration")
        if self.database.checkpoint_backend != plan["checkpoint_backend"]:
            raise StorageConflict("checkpoint storage configuration changed during migration")

    def execute(self, identity, *, resume=False):
        path = self._path(identity)
        with file_lock(path.with_suffix(".lock")), file_lock(self.storage.control_dir / "root-execution.lock"):
            plan = self.status(identity)
            if plan["state"] == "complete":
                return plan
            root = self.storage.root_info()
            if (
                root.get("operation_id") == plan["id"]
                and root["path"] == plan["destination"]
                and root["revision"] == plan["arguments"]["expected_revision"] + 1
            ):
                if self.verify(plan["id"])["incomplete"]:
                    raise StorageConflict("activated root lacks its complete recovery receipts")
                if self.database.blobs.policies() != plan.get("policy_after"):
                    raise StorageConflict("activated root policy differs from its saved publication intent")
                plan.update(state="complete", root_revision=root["revision"])
                self._save(plan)
                return plan
            if plan["state"] in ("cancelled", "rolled_back") and not resume:
                raise StorageConflict("explicit resume is required")
            if resume:
                plan["cancel_requested"] = False
                self.journal.write(path, plan)
            remaining = (
                plan["bytes"]
                - sum(r.get("bytes", 0) for r in plan["resource_receipts"].values())
                - sum(r.get("bytes", 0) for r in plan["payload_receipts"].values())
            )
            try:
                self.migrations._space(Path(plan["destination"]), max(0, remaining))
                self._check_writers(plan)
                root = self.storage.root_info()
                if root["revision"] != plan["arguments"]["expected_revision"]:
                    raise StorageConflict("data root changed since planning")
                target_id = "root-" + str(UUID(plan["id"]))
                try:
                    self.storage.target(target_id)
                except ValueError:
                    self.storage.register_target(
                        Path(plan["destination"]) / "originals", "Research originals", target_id=target_id
                    )
                plan.update(state="running", error=None)
                self._save(plan)
                for resource in plan["resources"]:
                    key = resource["resource_id"]
                    if self._cancelled(plan):
                        break
                    if key in plan["resource_receipts"]:
                        continue
                    try:
                        self._check_writers(plan)
                        child_id = uuid5(UUID(plan["id"]), "resource:" + key)
                        relative = "research/" + hashlib.sha256(key.encode()).hexdigest()[:24]
                        child = self.migrations.plan(
                            key,
                            target_id,
                            relative,
                            expected_revision=resource["revision"],
                            request_id=child_id,
                            members=sorted(resource["members"]),
                        )
                        # Verify against fixed scientific evidence, not merely a new copy hash.
                        for entry in child["entries"]:
                            expected = resource["members"].get(entry["path"])
                            if expected and (
                                entry["bytes"] != expected["bytes"] or entry["sha256"] != expected["sha256"]
                            ):
                                raise StorageConflict("historical original differs from its registered size/hash")
                        if child["state"] == "activated":
                            pass  # Recover a completed child whose parent receipt was interrupted.
                        elif resume:
                            self.migrations.resume(child["id"])
                        else:
                            self.migrations.execute(child["id"])
                        self.migrations.verify(child["id"])
                        receipt = self.migrations.activate(child["id"])
                        plan["resource_receipts"][key] = {k: receipt[k] for k in ("id", "state", "bytes")}
                        plan["failures"].pop(key, None)
                    except (ValueError, OSError, DatabaseError) as error:
                        plan["failures"][key] = {
                            "type": type(error).__name__,
                            "reason": "database transaction failed" if isinstance(error, DatabaseError) else str(error),
                        }
                    self._save(plan)
                for payload in plan["payloads"]:
                    key = payload["project_id"] + ":" + payload["kind"] + ":" + payload["id"]
                    if self._cancelled(plan):
                        break
                    if key in plan["payload_receipts"]:
                        continue
                    try:
                        self._check_writers(plan)
                        receipt = self.database.payloads.migrate(
                            payload["project_id"],
                            payload["kind"],
                            payload["id"],
                            target_id,
                            operation_id=uuid5(UUID(plan["id"]), "payload:" + key),
                            actor=plan["actor_id"],
                            cancelled=lambda: self._cancelled(plan),
                        )
                        plan["payload_receipts"][key] = {k: receipt[k] for k in ("id", "state", "bytes")}
                        plan["failures"].pop(key, None)
                    except (ValueError, OSError, DatabaseError) as error:
                        plan["failures"][key] = {
                            "type": type(error).__name__,
                            "reason": "database transaction failed" if isinstance(error, DatabaseError) else str(error),
                        }
                    self._save(plan)
                if self._cancelled(plan):
                    plan["state"] = "cancelled"
                elif plan["failures"] or plan["excluded"]:
                    plan["state"] = "partial"
                else:
                    if self.verify(plan["id"])["incomplete"]:
                        raise StorageConflict("not all planned originals were verified")
                    self._check_writers(plan)
                    # Root+future policies are fenced; no in-flight operation is
                    # silently refrozen. Running checkpoints still default to DB.
                    with file_lock(self.storage.control_dir / "blob-policies.lock"), self.storage._edit() as registry:
                        policy = self.database.blobs.policies()
                        if policy != plan["policy_before"]:
                            raise StorageConflict("future-write policy changed during migration")
                        target = self.storage.target(target_id)
                        for category in CATEGORIES:
                            # The host backend still defaults to database. This
                            # also defines the destination for a later explicit
                            # filesystem choice without retaining an old root.
                            policy["categories"][category] = {
                                "target_id": target_id,
                                "config_revision": target["config_revision"],
                            }
                        policy["revision"] += 1
                        plan["policy_after"] = policy
                        # A durable intent makes a crash after root publication
                        # distinguishable from an unrelated policy change.
                        self._save(plan)
                        registry["blob_policies"] = policy
                        registry["data_root"] = {
                            "path": plan["destination"],
                            "revision": root["revision"] + 1,
                            "operation_id": plan["id"],
                        }
                    plan["state"] = "complete"
                    plan["root_revision"] = root["revision"] + 1
                self._save(plan)
                return plan
            except (ValueError, OSError, DatabaseError) as error:
                plan.update(
                    state="blocked",
                    error="database transaction failed" if isinstance(error, DatabaseError) else str(error),
                )
                self._save(plan)
                return plan

    def cancel(self, identity):
        with file_lock(self.storage.control_dir / "root-journal.lock"):
            plan = self.status(identity)
            if plan["state"] in ("complete", "rolled_back"):
                raise StorageConflict("activated root requires rollback")
            plan["cancel_requested"] = True
            if plan["state"] == "planned":
                plan["state"] = "cancelled"
            self.journal.write(self._path(identity), plan)
        for resource in plan["resources"]:
            # Child identities use the host namespace. Cancel only an existing task.
            child_id = uuid5(
                UUID(self.storage.host_info()["host_id"]),
                "storage-plan:" + str(uuid5(UUID(plan["id"]), "resource:" + resource["resource_id"])),
            )
            if self.migrations._path(child_id).exists() and self.migrations.status(child_id)["state"] != "activated":
                self.migrations.cancel(child_id)
        return self.status(identity)

    def verify(self, identity):
        plan = self.status(identity)
        checked = 0
        for receipt in plan["resource_receipts"].values():
            self.migrations.verify(receipt["id"])
            checked += 1
        for receipt in plan["payload_receipts"].values():
            self.database.payloads.verify(read_json(self.database.payloads._path(receipt["id"])))
            checked += 1
        return {
            "id": plan["id"],
            "state": "verified",
            "checked": checked,
            "old_source_fallback": False,
            "incomplete": bool(plan["failures"] or plan["excluded"])
            or checked != len(plan["resources"]) + len(plan["payloads"]),
        }

    def rollback(self, identity):
        with (
            file_lock(self._path(identity).with_suffix(".lock")),
            file_lock(self.storage.control_dir / "root-execution.lock"),
        ):
            plan = self.status(identity)
            if plan["state"] == "rolled_back":
                return plan
            root = self.storage.root_info()
            if plan["state"] == "complete" and root.get("operation_id") != plan["id"]:
                raise StorageConflict("another root change has occurred")
            if plan.get("policy_after") and self.database.blobs.policies() != plan["policy_after"]:
                raise StorageConflict("future-write policy changed after activation; review a reverse migration")
            # Child rollback fences resource writes; payloads are immutable. Keep
            # new objects at their exact locations even after future root rollback.
            for receipt in reversed(list(plan["payload_receipts"].values())):
                self.database.payloads.rollback(read_json(self.database.payloads._path(receipt["id"])))
            for receipt in reversed(list(plan["resource_receipts"].values())):
                self.migrations.rollback(receipt["id"])
            with file_lock(self.storage.control_dir / "blob-policies.lock"), self.storage._edit() as registry:
                current = self.database.blobs.policies()
                previous = plan["policy_before"] | {"revision": current["revision"] + 1}
                registry["blob_policies"] = previous
                registry["data_root"] = {
                    "path": plan["root_before"]["path"],
                    "revision": root["revision"] + 1,
                    "operation_id": plan["id"],
                }
            plan["state"] = "rolled_back"
            self._save(plan)
            return plan


def summary(row):
    return {
        key: value
        for key, value in row.items()
        if key
        not in ("resources", "payloads", "resource_receipts", "payload_receipts", "projects", "retained_resources")
    } | {
        "resources_completed": len(row.get("resource_receipts", {})),
        "payloads_completed": len(row.get("payload_receipts", {})),
        "retained_resource_count": len(row.get("retained_resources", [])),
    }
