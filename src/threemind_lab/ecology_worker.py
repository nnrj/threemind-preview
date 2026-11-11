"""A single fenced worker owns each interacting population's physical clock."""

import time

from threemind_runtime.cold_state import StateReference
from threemind_runtime.ecology import EcologyCoordinator

from . import development
from .ecology_participant import LabParticipant
from .ecology_protocol import EcologyProtocol
from .ecology_store import PopulationWriter, campaign, run_id


def open_population(worker, row, writer):
    protocol = EcologyProtocol(**row["protocol"])
    spec = protocol.base
    checkpoint = writer.load()
    founders = None
    if checkpoint is None and protocol.initial_version_id:
        with worker.db.tx(row["project_id"]) as db:
            source = development._version(db, protocol.initial_version_id)
        _, image = worker.db.load_checkpoint(row["project_id"], source["run_id"], source["checkpoint_id"])
        if image.digest != source["state_hash"]:
            raise ValueError("registered founder state checksum mismatch")
        founders = [image]

    def factory(identity, image, state):
        reference = image if isinstance(image, StateReference) else None
        if reference is not None:
            image = reference.materialize()
        agent = LabParticipant(
            identity,
            image,
            state,
            database=worker.db,
            project=row["project_id"],
            run_id=run_id(row["id"], identity),
            spec=spec,
            backend=worker.backend,
            record=lambda event: writer.member_record(identity, event),
        )
        if reference is not None:
            agent.archive_engine(reference)
        return agent

    return EcologyCoordinator(
        spec.world_protocol,
        protocol.ecology,
        sensory_seed=spec.seed,
        environment_seed=spec.environment_seed if spec.environment_seed is not None else spec.seed,
        founders=founders,
        core_config=spec.config if checkpoint is None and founders is None else None,
        kernel_id=spec.kernel_id,
        backend=worker.backend,
        participant_factory=factory,
        record=writer.record,
        checkpoint=checkpoint,
    )


def execute(worker, job):
    project = job["project_id"]
    with worker.db.tx(project) as db:
        worker.db.fence(db, job)
        row = campaign(db, job["params"]["campaign_id"])
    if row["status"] != "active":
        return {
            "campaign_id": str(row["id"]),
            "status": row["status"],
            "checkpoint_id": str(row["checkpoint_id"]) if row["checkpoint_id"] else None,
        }
    writer = PopulationWriter(worker.db, project, row, job=job, implementation=worker.implementation)
    spec = EcologyProtocol(**row["protocol"]).base
    end = spec.deadline_us(0)
    with open_population(worker, row, writer) as runtime:
        if row["checkpoint_id"] is None:
            writer.commit(runtime)  # Register real, untouched births before any experience.
        anchor_host, anchor_sim = time.monotonic(), runtime.time_us
        last_host, last_sim, last_poll = anchor_host, runtime.time_us, -float("inf")
        requested, status = None, "active"
        while (end is None or runtime.time_us < end) and not worker.stopping:
            if time.monotonic() - last_poll >= 0.1:
                with worker.db.tx(project) as db:
                    worker.db.fence(db, job)
                    requested = campaign(db, row["id"])["requested_action"]
                last_poll = time.monotonic()
            if requested:
                break
            target = min(
                runtime.pending_end_us or runtime.time_us + spec.world_protocol.physics.sample_us,
                last_sim + spec.checkpoint_us,
            )
            if end is not None:
                target = min(target, end)
            if spec.trace:
                for key, agent in runtime.participants.items():
                    if agent.engine.life != "dead":
                        boundary = (
                            agent.engine.time_us // agent.engine.config.step_us + 1
                        ) * agent.engine.config.step_us
                        target = min(target, runtime.ledger.accounts[key].birth_us + boundary)
            if spec.clock != "unbounded":
                speed = spec.speed if spec.clock == "scaled" else 1
                while not worker.stopping:
                    remaining = (target - anchor_sim) / 1e6 / speed - (time.monotonic() - anchor_host)
                    if remaining <= 0:
                        break
                    time.sleep(min(0.05, remaining))
            if worker.stopping:
                break
            before = len(runtime.participants)
            runtime.advance_to(target)
            force = len(runtime.participants) != before or spec.trace or writer.spike_bytes >= 4 * 1024**2
            force |= any(
                agent.force_checkpoint or agent.readouts.bytes >= 8 * 1024**2 for agent in runtime.participants.values()
            )
            if force or runtime.time_us - last_sim >= spec.checkpoint_us or time.monotonic() - last_host >= 2:
                writer.commit(runtime)
                last_host, last_sim = time.monotonic(), runtime.time_us
        with worker.db.tx(project) as db:
            worker.db.fence(db, job)
            requested = campaign(db, row["id"])["requested_action"]
        status = (
            "cancelled"
            if requested == "cancel"
            else "paused"
            if requested == "pause" or worker.stopping
            else "completed"
        )
        result = writer.commit(runtime, status=status, finish=True)
        return {
            "campaign_id": str(row["id"]),
            "status": result["status"],
            "checkpoint_id": str(result["checkpoint_id"]),
            "time_us": str(runtime.time_us),
        }
