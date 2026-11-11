"""Database-free closed loop. Its saved state owns both brain and external robot."""

from threemind_kernels.registry import DEFAULT_KERNEL, state_kernel

from .host import create_engine
from .profile import profile_from_spec
from .robot_factory import create_robot_world
from .robot_protocol import parse_robot


class RobotSession:
    def __init__(
        self,
        protocol,
        *,
        seed=20260724,
        environment_seed=None,
        kernel_id=None,
        config=None,
        backend="native",
        image=None,
        context=None,
    ):
        task = parse_robot(protocol)
        if context is not None:
            if context.get("schema") != "threemind.robot-runtime/1" or context["protocol"] != task.model_dump(
                mode="json"
            ):
                raise ValueError("robot runtime protocol differs from stored continuation")
            seed, environment_seed, kernel_id = context["seed"], context["environment_seed"], context["kernel_id"]
        kernel_id = kernel_id or (state_kernel(image).kernel_id if image is not None else DEFAULT_KERNEL)
        self.engine = create_engine(config, state=image, backend=backend, kernel_id=kernel_id)
        self.kernel_id, self.seed, self.environment_seed = kernel_id, seed, environment_seed
        self.profile = profile_from_spec({"seed": seed})
        self.world = create_robot_world(task, seed, context["world"] if context else None, environment_seed=environment_seed)
        self.next_world_us = int(context["next_world_us"]) if context else self.engine.time_us
        if not self.engine.time_us <= self.next_world_us <= self.engine.time_us + self.world.period_us:
            self.close()
            raise ValueError("robot sensory deadline does not match Core clock")

    def advance(self, until_us, *, record=None, action=None):
        if type(until_us) is not int or until_us < self.engine.time_us:
            raise ValueError("advance target precedes current clock")
        while self.engine.time_us < until_us and self.engine.life != "dead":
            if self.engine.time_us == self.next_world_us:
                if getattr(self.world, "terminated", False):
                    break
                frame = self.world.sample(self.engine.time_us, self.engine.activations(), action=action)
                event = self.engine.inject(frame)
                self.next_world_us = frame.time_us
                if record:
                    record(
                        {
                            "kind": "robot_sample",
                            "core_event_id": event,
                            "stimulus": frame.to_dict(),
                            "observation": self.world.observation(),
                        }
                    )
            self.engine.advance_to(min(until_us, self.next_world_us))
        return self.engine.metrics() | self.world.task_metrics()

    def context(self):
        return {
            "schema": "threemind.robot-runtime/1",
            "protocol": self.world.task.model_dump(mode="json"),
            "kernel_id": self.kernel_id,
            "seed": self.seed,
            "environment_seed": self.environment_seed,
            "world": self.world.capture(),
            "next_world_us": str(self.next_world_us),
        }

    def close(self):
        self.world.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
