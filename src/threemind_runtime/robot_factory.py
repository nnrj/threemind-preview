"""Select an external robot backend without importing JAX on ordinary hosts."""

from .robot_protocol import PlaygroundRobotTask, parse_robot


def create_robot_world(protocol, seed=0, state=None, *, environment_seed=None):
    task = parse_robot(protocol)
    if isinstance(task, PlaygroundRobotTask):
        from .playground_world import PlaygroundWorld

        return PlaygroundWorld(task, seed, state, environment_seed=environment_seed)
    from .robot import RobotWorld

    return RobotWorld(task, seed, state, environment_seed=environment_seed)
