"""Bounded, offline Linux acceptance for the optional official task backend."""

import copy
import json
import math
import time

from threemind_runtime.playground_world import PlaygroundWorld
from threemind_runtime.robot_protocol import playground_template
from threemind_runtime.robot_session import RobotSession


def main():
    start = time.monotonic()
    task = playground_template()
    print("loading pinned task", flush=True)
    with PlaygroundWorld(task, 11, environment_seed=7) as a:
        print("reset compiled", flush=True)
        a.sample(0, action=[0.0] * a.model.nu)
        print("step compiled", flush=True)
        before = a.capture()
        a.observation()
        a.scene_protocol()
        a.task_metrics()
        assert a.capture() == before, "observation must not affect state"
        with PlaygroundWorld(task, 11, json.loads(json.dumps(before)), environment_seed=7) as b:
            for now in (20000, 40000, 60000):
                assert a.sample(now, [(2, 0.1)]) == b.sample(now, [(2, 0.1)])
            assert a.capture() == b.capture(), "full official-state continuation differs"
        changed = copy.deepcopy(before)
        changed["versions"]["jax"] = "invalid"
        changed["physical_hash"] = "invalid"
        try:
            PlaygroundWorld(task, 11, changed, environment_seed=7)
        except ValueError:
            pass
        else:
            raise AssertionError("changed backend identity accepted")
        assert all("reward" not in m["id"] for m in a.last_measurements)
        assert a.observation()["stimulus_unit"]["intensity"] == 1
        print("observation and exact restoration passed", flush=True)
        a.steps = 149  # Explicit test fixture for the task's terminal boundary.
        a.sample(80000, action=[0.0] * a.model.nu)
        assert a.terminated
        try:
            a.sample(100000)
        except ValueError:
            pass
        else:
            raise AssertionError("terminal episode advanced")
    with RobotSession(task, seed=11, environment_seed=7) as a:
        a.advance(60000)
        image, context = a.engine.capture_state(), a.context()
        with RobotSession(task, image=image, context=context) as b:
            am, bm = a.advance(100000), b.advance(100000)
            assert a.engine.capture_state().digest == b.engine.capture_state().digest
            for key, value in am.items():
                assert (
                    math.isclose(value, bm[key], rel_tol=1e-14, abs_tol=1e-14)
                    if type(value) is float
                    else value == bm[key]
                ), key
            assert a.context() == b.context()
        print(
            json.dumps(
                {
                    "passed": True,
                    "seconds": time.monotonic() - start,
                    "versions": a.world.versions,
                    "metrics": a.world.task_metrics(),
                    "core_hash": a.engine.capture_state().digest,
                }
            )
        )


if __name__ == "__main__":
    main()
