"""Opt-in reproducible random controls; never inspect or prune the graph."""

import hashlib
import random
from dataclasses import asdict, dataclass

from .stimulus_units import VERSION


@dataclass(frozen=True)
class RandomStimulusConfig:
    seed: int = 1
    mode: str = "fresh-single"
    channels: int = 4
    interval_us: int = 100000
    intensity: float = 0.2

    def __post_init__(self):
        if type(self.seed) is not int or not 0 <= self.seed < 2**32:
            raise ValueError("invalid random stimulus seed")
        if self.mode not in ("fresh-single", "fresh-group", "fixed-amplitude"):
            raise ValueError("invalid random stimulus mode")
        if type(self.channels) is not int or not 1 <= self.channels <= 256:
            raise ValueError("channels must be in 1..256")
        if type(self.interval_us) is not int or not 1 <= self.interval_us <= 10**9:
            raise ValueError("invalid random interval")
        from .stimulus_presets import resolve_intensity

        resolve_intensity(self.intensity)


class RandomStimuli:
    VERSION = "threemind.random-stimuli/1"

    def __init__(self, config=None, state=None):
        config = config or RandomStimulusConfig()
        self.config, self.index = config, 0
        if state is not None:
            if state.get("schema") != self.VERSION or state.get("config") != asdict(config):
                raise ValueError("random fixture state/config mismatch")
            self.index = state["index"]
            if type(self.index) is not int or self.index < 0:
                raise ValueError("invalid random fixture index")
        self.mask = int.from_bytes(hashlib.sha256(f"random-v1:{config.seed}".encode()).digest()[:4], "little")

    def capture(self):
        return {"schema": self.VERSION, "config": asdict(self.config), "index": self.index}

    def sample(self):
        cfg, n = self.config, self.index
        count = 1 if cfg.mode == "fresh-single" else cfg.channels
        first = 0 if cfg.mode == "fixed-amplitude" else n * count
        if first + count > 2**32:
            raise ValueError("random fixture channel space exhausted; refusing identity reuse")
        rng = random.Random(f"random-v1:{cfg.seed}:{n}")
        result = {
            "schema_id": VERSION,
            "kind": "element" if count == 1 else "group",
            "source": "independent-random-control",
            "mapping_version": self.VERSION,
            "time_us": str(n * cfg.interval_us),
            "frame_id": str(n),
            "intensity": cfg.intensity,
            "grouping_basis": "explicit synthetic joint sample",
            "elements": [{"channel": (first + i) ^ self.mask, "value": rng.random()} for i in range(count)],
        }
        self.index += 1
        return result


def main():
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fresh-single", "fresh-group", "fixed-amplitude"), default="fresh-single")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--channels", type=int, default=4)
    parser.add_argument("--interval-us", type=int, default=100000)
    parser.add_argument("--intensity", type=float, default=0.2)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--restore", type=Path)
    parser.add_argument("--save-state", type=Path)
    args = parser.parse_args()
    if not 1 <= args.count <= 10000:
        parser.error("count must be 1..10000")
    state = json.loads(args.restore.read_bytes()) if args.restore else None
    config = (
        RandomStimulusConfig(**state["config"])
        if state
        else RandomStimulusConfig(args.seed, args.mode, args.channels, args.interval_us, args.intensity)
    )
    fixture = RandomStimuli(config, state)
    with args.output.open("x", encoding="utf-8") as stream:
        for _ in range(args.count):
            stream.write(json.dumps(fixture.sample()) + "\n")
    if args.save_state:
        with args.save_state.open("x", encoding="utf-8") as stream:
            json.dump(fixture.capture(), stream)


if __name__ == "__main__":
    main()
