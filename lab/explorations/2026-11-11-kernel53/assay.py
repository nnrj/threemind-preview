"""R47a: four-curve retention instrument with continuous independent cohorts.

Only declared stimuli and advance operations move the subject's clock.
The output is a four-field temporal measurement, not a learned adapter.
"""

import copy
import random

from threemind_core import StateImage, Stimulus
from threemind_kernels.decay53 import CURVES
from threemind_kernels.local53 import KERNEL_ID, Local53Config
from threemind_kernels.registry import resolve_kernel

FIELDS = ("activation", "inhibition", "direct", "associative")
SYMBOLS = ("background", "cue", "out0", "out1")
COURSES = ("weak", "ordinary", "high-dose", "strong", "massed", "spaced")
DELAYS = (1, 30, 60, 300)
TIMES = {c: (127.0,) for c in COURSES}
TIMES.update(massed=tuple(range(120, 128)), spaced=(16.0, 17.0, 19.0, 23.0, 31.0, 47.0, 79.0, 127.0))
DOSES = dict(weak=0.08, ordinary=0.4, **{"high-dose": 0.8}, strong=0.4, massed=0.4, spaced=0.4)


def cases(n=8, confirmation=False):
    rows = []
    for origin in range(n):
        seed = (261111480 if confirmation else 261111100) + origin
        rng = random.Random(seed)
        # Profile variation is frozen independently of history and output label.
        profile = dict(
            scale=rng.uniform(0.85, 1.15),
            phase_us=rng.randrange(1, 20_000),
            novelty_offset_us=rng.choice((50_000, 75_000)),
        )
        for curve in CURVES:
            for course in COURSES + ("strong-gain-zero", "novelty", "novelty-gain-zero"):
                for delay in DELAYS:
                    for history in (0, 1):
                        for cue in (False, True):
                            key = f"o{origin}/{curve}/{course}/d{delay}/h{history}/q{int(cue)}"
                            rows.append(
                                dict(
                                    key=key,
                                    origin=origin,
                                    seed=seed,
                                    profile=profile,
                                    curve=curve,
                                    course=course,
                                    delay=delay,
                                    history=history,
                                    cue=cue,
                                )
                            )
    return rows


class Assay:
    def __init__(self, case, backend="native"):
        self.case = copy.deepcopy(case)
        self.mapping = dict(zip(SYMBOLS, random.Random(case["seed"]).sample(range(1, 2**32), len(SYMBOLS))))
        self.next_background = 0
        self.events = []
        self.cursor = "birth"
        config = dict(seed=case["seed"], energy_seed=case["seed"] ^ 0x31E629, decay_curve=case["curve"])
        if case["course"] == "strong-gain-zero":
            config["intensity_gain"] = 0.0
        if case["course"] == "novelty-gain-zero":
            config["local_novelty_gain"] = 0.0
        self.core = resolve_kernel(KERNEL_ID).create(Local53Config(**config), backend=backend)

    def state(self):
        return dict(
            schema="threemind.single-age-assay/1",
            case=copy.deepcopy(self.case),
            mapping=self.mapping.copy(),
            next_background=self.next_background,
            events=copy.deepcopy(self.events),
            cursor=self.cursor,
            core=self.core.capture_state().to_dict(),
            apparatus=dict(
                input="fixed anonymous stimulus adapter",
                output="four-field temporal instrument",
                learned_peripherals=False,
                body="isolated local mechanism preparation",
            ),
        )

    @classmethod
    def restore(cls, value, backend="native"):
        if value["schema"] != "threemind.single-age-assay/1":
            raise ValueError("assay identity")
        s = cls.__new__(cls)
        for k in ("case", "mapping", "next_background", "events", "cursor"):
            setattr(s, k, copy.deepcopy(value[k]))
        s.core = resolve_kernel(KERNEL_ID).create(state=StateImage.from_dict(value["core"]), backend=backend)
        if s.state() != value:
            raise ValueError("whole instrument state differs after restore")
        return s

    def inject(self, t, values, role, intensity=1.0):
        event = Stimulus(t, tuple((self.mapping[k], float(v)) for k, v in values.items()), float(intensity))
        self.core.inject(event)
        self.events.append(
            dict(time_us=t, channels=[list(x) for x in event.channels], intensity=event.intensity, role=role)
        )

    def advance(self, t):
        if t < self.core.time_us:
            raise ValueError("no rollback")
        while self.next_background <= t:
            self.inject(self.next_background, {"background": 0.2}, "background")
            self.next_background += 500_000
        self.core.advance_to(t)
        if self.core.life == "dead":
            raise RuntimeError("new subject death; preserve in-flight")

    def graph(self):
        before = self.core.capture_state()
        graph = self.core.graph()
        names = {v: k for k, v in self.mapping.items()}
        ids = {n["id"]: names[n["channel"]] for n in graph["nodes"]}
        for n in graph["nodes"]:
            n["symbol"] = ids[n["id"]]
        for e in graph["edges"]:
            e.update(source_symbol=ids[e["source"]], target_symbol=ids[e["target"]])
            if "background" in (e["source_symbol"], e["target_symbol"]):
                raise RuntimeError("background acquired task connection")
        if before.digest != self.core.capture_state().digest:
            raise RuntimeError("observation changed subject")
        return graph

    @property
    def teaching_end(self):
        return 1_000_000 if self.case["course"].startswith("novelty") else 128_000_000

    def teach(self):
        if self.cursor != "birth":
            raise ValueError("fresh teaching only")
        c = self.case
        p = c["profile"]
        target = f"out{c['history']}"
        samples = []
        if c["course"].startswith("novelty"):
            t = 100_000 + p["phase_us"]
            self.advance(t)
            self.inject(t, {"cue": 0.4 * p["scale"], f"out{1 - c['history']}": 0.4 * p["scale"]}, "prior-pair")
            t += p["novelty_offset_us"]
            self.advance(t)
            samples.append(self.graph())
            self.inject(t, {"cue": 0.4 * p["scale"], target: 0.4 * p["scale"]}, "new-pair")
            self.advance(t)
            samples.append(self.graph())
            self.advance(400_000)
            samples.append(self.graph())
        else:
            course = "strong" if c["course"] == "strong-gain-zero" else c["course"]
            for second in TIMES[course]:
                t = round(second * 1e6) + p["phase_us"]
                self.advance(t)
                self.inject(
                    t,
                    {"cue": DOSES[course] * p["scale"], target: DOSES[course] * p["scale"]},
                    "teaching",
                    2.0 if course == "strong" else 1.0,
                )
                self.advance(t)
                samples.append(self.graph())
        self.advance(self.teaching_end)
        self.cursor = "taught"
        return dict(teaching_end_us=self.teaching_end, samples=samples, after=self.graph())

    def window(self, values=None):
        start = self.core.time_us
        self.advance(start)
        if values:
            self.inject(start, values, "cue-probe")
        frames = []
        for i in range(20):
            self.advance(start + (i + 1) * 50_000)
            by = {n["channel"]: n for n in self.core.observation_nodes()}
            frames.append(
                {k: {f: by.get(channel, {}).get(f, 0.0) for f in FIELDS} for k, channel in self.mapping.items()}
            )
        return dict(start_us=start, end_us=self.core.time_us, frames=frames)

    def probe(self):
        if self.cursor != "taught":
            raise ValueError("one first probe per continuously taught cohort")
        self.advance(self.teaching_end + (self.case["delay"] - 1) * 1_000_000)
        baseline = self.window()
        before = self.graph()
        response = self.window({"cue": 0.8} if self.case["cue"] else None)
        self.cursor = "completed"
        return dict(before=before, baseline=baseline, response=response, after=self.graph())
