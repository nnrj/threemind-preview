"""Explicit synthetic capability reports for tests of leases, not probe correctness.

Real-worker and capability-matching tests announce their actual or targeted reports.
This helper does not patch Database or skip any production admission checks.
"""


def claim_as(database, name, *, queue="runtime", **kwargs):
    keys = {
        "runtime": [
            "worker.core",
            "worker.raw_readout_v1",
            "worker.activity_analysis_v2",
            "worker.environment_seed_v1",
            "worker.mujoco",
            "worker.telemetry_host",
            "worker.telemetry_process",
            "worker.telemetry_runtime",
        ],
        "ai": ["worker.ai"],
        "notification": ["worker.notifications", "worker.execution_health_v1"],
    }[queue]
    database.announce_worker(
        name,
        {
            "queue": queue,
            "backend": "native",
            "features": {
                key: {"state": "available", "reason": "Explicit synthetic lease-test fixture"} for key in keys
            },
        },
    )
    return database.claim(name, queue=queue, **kwargs)
