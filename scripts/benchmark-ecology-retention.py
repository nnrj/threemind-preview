"""Bounded retention probe, independent of Lab and existing user data.

Run from the repository root, with --cold to archive dead brains in a dedicated
SQLite fixture. Both modes write metrics and final model hashes under .work/.
The fixture is solely a benchmark host; Lab uses PostgreSQL state references.
"""

import argparse
import gc
import json
import sqlite3
import time
from pathlib import Path

import psutil

from threemind_core import Config, StateImage, Stimulus
from threemind_runtime import create_engine
from threemind_runtime.cold_state import FrozenCore, StateReference
from threemind_runtime.ecology import EcologyCoordinator, EcologySettings
from threemind_runtime.ecology_rules import Hazard
from threemind_runtime.world_schema import default_world

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--cold", action="store_true", help="Archive confirmed dead brains after durable storage")
parser.add_argument("--background-load", default="not recorded", help="Describe concurrent load for interpretation")
arguments = parser.parse_args()
source = create_engine(Config(activation_tau=0.001))
Path(".work").mkdir(exist_ok=True)
source.inject(Stimulus(1000, tuple((i + 2000, 0.5) for i in range(48))))
source.advance_to(20000)
image = source.capture_state()
settings = EcologySettings()
settings.rules.patches[0].radius = 10
settings.rules.patches[0].capacity = 10000
settings.rules.patches[0].initial = 10000
settings.rules.uptake_per_s = 100
settings.rules.maintenance_per_s = 0

settings.rules.hazards = [Hazard(id="turnover", radius=10, damage_per_s=10)]
settings.rules.fatal_damage = 0.5
reproduction = settings.rules.reproduction
reproduction.interval_us = 20000
reproduction.minimum_age_us = 20000
reproduction.cooldown_us = 20000
reproduction.threshold = 4
reproduction.offspring_reserve = 1
reproduction.population_limit = 8
reproduction.offspring_limit = 64
process = psutil.Process()
started = time.monotonic()
samples = []
cold = arguments.cold
archive = sqlite3.connect(".work/ecology-retention-cold.sqlite") if cold else None
if archive:
    archive.execute("CREATE TABLE IF NOT EXISTS images(hash TEXT PRIMARY KEY, payload BLOB NOT NULL)")
with EcologyCoordinator(default_world(), settings, founders=[image]) as runtime:
    previous = {}
    for end in range(20000, 1000001, 20000):
        runtime.advance_to(end)
        if len(runtime.participants) != len(previous) or end == 1000000:
            _, images = runtime.checkpoint()
            # Match the current Lab host's materialized delta comparison baseline.
            if archive:
                for key, agent in runtime.participants.items():
                    if (
                        not agent.body_enabled
                        and agent.engine.life == "dead"
                        and agent.dead_recorded
                        and not isinstance(agent.engine, FrozenCore)
                    ):
                        frozen_image = images[key]
                        archive.execute(
                            "INSERT OR IGNORE INTO images VALUES(?,?)", (frozen_image.digest, frozen_image.payload)
                        )
                        archive.commit()
                        agent.archive_engine(
                            StateReference(
                                frozen_image.digest,
                                lambda digest=frozen_image.digest: StateImage(
                                    archive.execute("SELECT payload FROM images WHERE hash=?", (digest,)).fetchone()[0]
                                ),
                            )
                        )
                _, images = runtime.checkpoint()
            previous = {
                key: None if isinstance(runtime.participants[key].engine, FrozenCore) else value.to_dict()
                for key, value in images.items()
            }
            gc.collect()
            samples.append(
                {
                    "time_us": end,
                    "historical_individuals": len(previous),
                    "living_bodies": len(runtime.world.members),
                    "dead_cores": sum(a.engine.life == "dead" for a in runtime.participants.values()),
                    "rss_bytes": process.memory_info().rss,
                    "model_payload_bytes": sum(len(value.payload) for value in images.values()),
                }
            )
            print(json.dumps(samples[-1]), flush=True)
result = {
    "schema": "threemind.performance-probe/1",
    "implementation": "EcologyCoordinator, CoreParticipant and FrozenCore; see the checkout's source revision",
    "purpose": "Synthetic turnover retention, not an evolution or consciousness result",
    "background_load": arguments.background_load,
    "seconds": time.monotonic() - started,
    "seed_model": source.metrics(),
    "samples": samples,
    "final_state_hashes": {key: value.digest for key, value in images.items()},
}
Path(".work/ecology-retention-" + ("cold" if cold else "baseline") + ".json").write_text(
    json.dumps(result, indent=2), encoding="utf-8"
)
if archive:
    archive.close()
