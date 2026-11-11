from contextlib import contextmanager
from unittest.mock import patch
from uuid import uuid4

import pytest
from test_ecology_runtime import configuration

from threemind_lab.database import LOCAL_USER, Conflict
from threemind_lab.ecology_protocol import EcologyProtocol, EcologyRequest
from threemind_lab.ecology_store import PopulationWriter, campaign, create
from threemind_lab.ecology_worker import open_population
from threemind_lab.protocols import RunSpec
from threemind_lab.worker import Worker
from threemind_runtime.inheritance import birth
from threemind_runtime.world_schema import default_world


def setup(database, *, habitat="shared", external_inputs=False, ecology=None, duration_s=0.1, **base):
    project = database.create_project({"id": LOCAL_USER}, "Ecological fixtures")["id"]
    request = EcologyRequest(
        operation_id=uuid4(),
        name="Ecological fixture",
        objective="Engineering validation; no consciousness claim",
        protocol=EcologyProtocol(
            base=RunSpec(
                environment="world", world_protocol=default_world(), clock="unbounded", duration_s=duration_s, **base
            ),
            ecology=ecology or configuration(habitat),
            external_inputs=external_inputs,
        ),
    )
    row = create(database, project, LOCAL_USER, request, 86400)
    return project, row, Worker(database)


@pytest.mark.parametrize("habitat", ["shared", "independent"])
def test_worker_actual_inheritance_all_member_evidence_and_frozen_source(database, habitat):
    project, row, worker = setup(database, habitat=habitat)
    assert worker.once()
    with database.tx(project) as db:
        done = campaign(db, row["id"])
        assert done["status"] == "completed", done["error"]
        assert done["time_us"] == "100000"
        members = db.execute("SELECT * FROM ecology_members ORDER BY individual").fetchall()
        assert len(members) == 6
        births = db.execute("SELECT payload FROM ecology_events WHERE kind='individual_born'").fetchall()
        assert len(births) == 4
        assert db.execute("SELECT 1 FROM input_frames WHERE status='delivered'").fetchone()
        for member in members:
            cps = db.execute(
                "SELECT id,time_us,state_hash FROM checkpoints WHERE run_id=%s ORDER BY revision", (member["run_id"],)
            ).fetchall()
            assert cps[0]["time_us"] == "0" and cps[0]["state_hash"] == member["birth_hash"]
            if member["parent"]:
                parent = next(m for m in members if m["individual"] == member["parent"])
                _, image = database.load_checkpoint(project, parent["run_id"], member["source_checkpoint_id"])
                assert image.digest == member["source_hash"] and birth(image).digest == member["birth_hash"]
    loaded = PopulationWriter(database, project, done).load()
    assert len(loaded[1]) == 6
    with database.tx(project) as db:
        assert (
            db.execute(
                "SELECT count(*) AS n FROM ecology_checkpoint_members WHERE population_checkpoint_id=%s",
                (done["checkpoint_id"],),
            ).fetchone()["n"]
            == 6
        )


def test_group_rollback_recovery_and_exact_retry_keep_births_and_input_audit_atomic(database):
    project, row, worker = setup(database)
    writer = PopulationWriter(database, project, row)
    with open_population(worker, row, writer) as runtime:
        writer.commit(runtime)
        runtime.advance_to(17000)
        writer.commit(runtime)
        checkpoint = writer.row
        runtime.advance_to(20000)
        operation = uuid4()
        original = database.save_checkpoint
        calls = []

        def fault(*args, **kwargs):
            result = original(*args, **kwargs)
            calls.append(result)
            if len(calls) == 3:
                raise RuntimeError("after newborn insert")
            return result

        with patch.object(database, "save_checkpoint", fault), pytest.raises(RuntimeError, match="newborn"):
            writer.commit(runtime, operation_id=operation)
        with database.tx(project) as db:
            assert campaign(db, row["id"])["checkpoint_id"] == checkpoint["checkpoint_id"]
            assert db.execute("SELECT count(*) AS n FROM ecology_members").fetchone()["n"] == 2
            assert db.execute("SELECT count(*) AS n FROM input_frames WHERE status='delivered'").fetchone()["n"] == 0
        assert writer.events and writer.member_events
        writer.commit(runtime, operation_id=operation)
        restored_writer = PopulationWriter(database, project, writer.row)
        with open_population(worker, writer.row, restored_writer) as restored:
            assert {k: v.engine.capture_state().digest for k, v in restored.participants.items()} == {
                k: v.engine.capture_state().digest for k, v in runtime.participants.items()
            }
            runtime.advance_to(40000)
            restored.advance_to(40000)
            assert runtime.checkpoint() == restored.checkpoint()
        # A reused nonce with different (now drained) evidence must be rejected.
        with pytest.raises(Conflict, match="retry"):
            writer.commit(runtime, operation_id=operation)


def test_committed_population_survives_lost_response_without_duplicate_evidence(database):
    project, row, worker = setup(database)
    writer = PopulationWriter(database, project, row)
    with open_population(worker, row, writer) as runtime:
        writer.commit(runtime)
        runtime.advance_to(20000)
        operation = uuid4()
        original = database.tx

        @contextmanager
        def response_lost(*args, **kwargs):
            with original(*args, **kwargs) as db:
                yield db
            raise ConnectionError("commit acknowledgement lost")

        with patch.object(database, "tx", response_lost), pytest.raises(ConnectionError, match="acknowledgement"):
            writer.commit(runtime, operation_id=operation)
        with database.tx(project) as db:
            committed = campaign(db, row["id"])
            counts = db.execute(
                "SELECT (SELECT count(*) FROM ecology_events) AS events,(SELECT count(*) FROM input_frames) AS inputs"
            ).fetchone()
        retried = writer.commit(runtime, operation_id=operation)
        assert retried["checkpoint_id"] == committed["checkpoint_id"]
        with database.tx(project) as db:
            assert (
                counts
                == db.execute(
                    "SELECT (SELECT count(*) FROM ecology_events) AS events,(SELECT count(*) FROM input_frames) AS inputs"
                ).fetchone()
            )


def test_lease_takeover_and_late_pause_preserve_complete_population(database):
    from threemind_lab.ecology_store import control
    from threemind_runtime.capabilities import probe_worker

    project, row, worker = setup(database)
    capabilities = probe_worker(worker.backend)
    capabilities["features"]["worker.ecology_v1"] = {"state": "available"}

    def claim_as(database, name):
        database.announce_worker(name, capabilities)
        return database.claim(name, capabilities=capabilities)

    stale = claim_as(database, "ecology-old")
    assert stale is not None and stale["id"] == row["job_id"]
    writer = PopulationWriter(database, project, row, job=stale)
    with open_population(worker, row, writer) as runtime:
        writer.commit(runtime)
        runtime.advance_to(20000)
        with database.tx(project) as db:
            db.execute("UPDATE jobs SET lease_until=clock_timestamp()-interval '1 second' WHERE id=%s", (stale["id"],))
        fresh = claim_as(database, "ecology-new")
        assert fresh["generation"] > stale["generation"]
        with pytest.raises(Conflict):
            writer.commit(runtime)
        with database.tx(project) as db:
            row = campaign(db, row["id"])
            assert row["time_us"] == "0"
            assert db.execute("SELECT count(*) AS n FROM ecology_members").fetchone()["n"] == 2
        recovery = PopulationWriter(database, project, row, job=fresh)
        with open_population(worker, row, recovery) as restored:
            restored.advance_to(20000)
            assert runtime.checkpoint() == restored.checkpoint()
            # A pause accepted just before final commit wins over stale intent
            # to finish, and the entire group retains resumable readout windows.
            control(database, project, row["id"], LOCAL_USER, "pause", row["control_revision"])
            final = recovery.commit(restored, status="completed", finish=True)
            assert final["status"] == "paused"
            assert len(PopulationWriter(database, project, final).load()[1]) == 4


def test_retired_brains_are_durable_and_do_not_load_or_copy_on_later_commits(database):
    from threemind_runtime.cold_state import FrozenCore
    from threemind_runtime.population_participant import CoreParticipant

    settings = configuration()
    settings.rules.patches = []
    settings.rules.founder_reserve = 0.01
    settings.rules.maintenance_per_s = 1
    project, row, worker = setup(
        database,
        ecology=settings,
        config={"activation_tau": 0.001, "quiescence_death_us": 20000},
        structural_readout={"enabled": True},
        temporal_readout={"enabled": True},
    )
    writer = PopulationWriter(database, project, row)
    with open_population(worker, row, writer) as runtime:
        writer.commit(runtime)
        for end in range(20000, 300001, 20000):
            runtime.advance_to(end)
            writer.commit(runtime)
        assert all(isinstance(a.engine, FrozenCore) for a in runtime.participants.values())
        assert all(value[1] is None for value in writer.previous.values())
        old_brain_cps = {key: value[0]["id"] for key, value in writer.previous.items()}
        with patch.object(database, "load_checkpoint", side_effect=AssertionError("unexpected archived brain load")):
            runtime.advance_to(320000)
            writer.commit(runtime)
        assert old_brain_cps == {key: value[0]["id"] for key, value in writer.previous.items()}
        restored_writer = PopulationWriter(database, project, writer.row)
        with open_population(worker, writer.row, restored_writer) as restored:
            assert runtime.checkpoint() == restored.checkpoint()
            assert all(isinstance(a.engine, FrozenCore) for a in restored.participants.values())
        # The identical restored tools around a materialized Core give the same
        # final raw observations; archival does not change their output windows.
        reference_writer = PopulationWriter(database, project, writer.row)
        with (
            patch.object(CoreParticipant, "archive_engine"),
            open_population(worker, writer.row, reference_writer) as reference,
        ):
            for key in runtime.participants:
                left, right = runtime.participants[key], reference.participants[key]
                left.readouts.observe(left.engine, force=True)
                right.readouts.observe(right.engine, force=True)
                left.readouts.close(left.engine.time_us, "run_ended")
                right.readouts.close(right.engine.time_us, "run_ended")
            assert writer.member_events == reference_writer.member_events
            assert runtime.checkpoint() == reference.checkpoint()
        final = writer.commit(runtime, status="completed", finish=True)
        with database.tx(project) as db:
            assert db.execute("SELECT count(*) AS n FROM ecology_members").fetchone()["n"] == 2
            assert db.execute("SELECT 1 FROM events WHERE kind='structural_readout'").fetchone()
        assert len(PopulationWriter(database, project, final).load()[1]) == 2
