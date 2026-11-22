"""Read recorded sensory/action samples. The observers never advance a world."""

from collections import defaultdict
import math

import numpy as np
import pyarrow.compute as pc
from lab.tools.ocean_turning import WINDOW_US, measure_window


class MealTurns:
    """Continue the same five-second history over file and experimental fork boundaries."""

    def __init__(self, preceding=None):
        self.history = dict(preceding.history) if preceding else {}
        self.last_hit = dict(preceding.last_hit) if preceding else {}
        self.examples = []
        self.meals = self.matched = self.windows = 0
        self.dimension = None

    def consume(self, batch, events):
        period = 20_000
        arrivals = defaultdict(dict)
        for event in events:
            if event["kind"] == "nutrient_contact" and event["energy"] > 0:
                tick = (event["time_us"] + period - 1) // period * period
                arrivals[event["individual"]].setdefault(tick, []).append(event["time_us"])
                self.meals += 1
        nested = batch.column("inputs")
        rows = pc.list_flatten(nested)
        if not len(rows):
            return
        sizes = np.unique(pc.list_value_length(rows.field("raw")).to_numpy())
        if len(sizes) != 1 or sizes[0] not in (13, 26):
            raise ValueError("unknown physical sensory layout")
        self.dimension = int(sizes[0])
        ids = rows.field("individual").to_numpy()
        times = pc.take(batch.column("time_us"), pc.list_parent_indices(nested)).to_numpy()
        physical = pc.list_flatten(rows.field("raw")).to_numpy().reshape(-1, self.dimension)
        actions = pc.list_flatten(rows.field("action")).to_numpy().reshape(-1, 3)
        for i in np.unique(ids):
            i = int(i)
            mask = ids == i
            t, values, commands = times[mask], physical[mask], actions[mask]
            start = t[0]
            if i in self.history:
                ht, hv, ha = self.history[i]
                t, values, commands = (
                    np.concatenate((ht, t)),
                    np.concatenate((hv, values)),
                    np.concatenate((ha, commands)),
                )
            for at in np.flatnonzero((values[:, 10] > 0) & (t >= start)):
                now = int(t[at])
                meal_times = arrivals[i].get(now)
                if not meal_times:
                    continue
                self.matched += len(meal_times)
                if now - self.last_hit.get(i, -WINDOW_US) < WINDOW_US:
                    continue
                first = np.searchsorted(t, now - WINDOW_US)
                raw = values[first:at]
                if self.dimension == 13:
                    # Collision was not measured in E28. Mark it missing rather than invent a zero.
                    raw = np.pad(raw, ((0, 0), (0, 13)), constant_values=np.nan)
                m = measure_window(t[first:at], raw, commands[first:at])
                if m is None:
                    continue
                self.windows += 1
                if self.dimension == 13:
                    m["max_collision"] = None
                    m["passes"] = (
                        m["turn_degrees"] >= 30
                        and m["alignment_after"] >= 0.7
                        and m["alignment_after"] - m["alignment_before"] >= 0.3
                        and m["mean_water_relative_speed_m_s"] >= 0.001
                        and m["mean_absolute_turn_command"] >= 0.01
                        and m["turn_command_angular_velocity_product"] > 0
                    )
                if m["passes"]:
                    self.examples.append(dict(individual=i, sampled_us=now, meal_times_us=meal_times, **m))
                    self.last_hit[i] = now
            keep = t >= t[-1] - WINDOW_US
            self.history[i] = t[keep].copy(), values[keep].copy(), commands[keep].copy()
        self.history = {i: v for i, v in self.history.items() if times[-1] - v[0][-1] <= WINDOW_US}

    def result(self):
        return dict(
            sensor_fields=self.dimension,
            collision_measured=self.dimension == 26,
            grain_events=self.meals,
            matched_grain_events=self.matched,
            windows=self.windows,
            turns=len(self.examples),
            individuals=len({e["individual"] for e in self.examples}),
            evidence=self.examples,
        )


def delta(end, start, side):
    return (np.asarray(end) - start + side / 2) % side - side / 2


def turn_angle(a, b):
    return math.degrees(abs(math.atan2(a[0] * b[1] - a[1] * b[0], float(a @ b))))


def unit_dot(a, b):
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(a @ b / norm) if norm > 1e-12 else 0.0


def capsule_gap(small_pos, angle, small, large_pos, large_angle, large, side):
    from lab.tools.ocean_contact import segment_distance

    def ends(pos, heading, body):
        r, length = body["radius"], body["elongation"]
        cap = r / math.sqrt(1 + 4 * length / math.pi)
        arm = length * cap * np.array([math.cos(heading), math.sin(heading)])
        return pos - arm, pos + arm, cap

    a, b, r = ends(np.zeros(2), angle, small)
    c, d, s = ends(delta(large_pos, small_pos, side), large_angle, large)
    return segment_distance(a, b, c, d) - r - s


class EncounterTurns:
    """Score relative movement of the same two identified bodies in recorded frames."""

    def __init__(self, side, members):
        from collections import deque

        self.side, self.members = side, members
        self.frames = deque(maxlen=31)  # one second before, five seconds after, inclusive
        self.last = {}
        self.approaches = self.exposed = 0
        self.escape, self.pursuit = [], []

    def frame(self, now, items):
        # Each value is [x,y, water-relative vx,vy, body angle, omega sensor, motor turn, collision].
        self.frames.append((now, {int(row[0]): np.asarray(row[1:], dtype=float) for row in items}))
        if len(self.frames) < 31:
            return
        f = list(self.frames)
        if f[-1][0] - f[0][0] != 6_000_000:
            raise ValueError("kinematic sample gap")
        start, bodies = f[5]
        ids = list(bodies)
        if len(ids) < 2:
            return
        xy = np.array([bodies[i][:2] for i in ids])
        radii = np.array([self.members[i]["radius"] for i in ids])
        ds = delta(xy[None, :, :], xy[:, None, :], self.side)
        dist = np.linalg.norm(ds, axis=2)
        reach = np.array([min(0.06, 3 * self.members[i]["sensor_range"]) for i in ids])
        smalls, larges = np.where((radii[:, None] < radii[None, :]) & (dist <= reach[:, None]))
        for ix, jx in zip(smalls, larges):
            small, large = ids[ix], ids[jx]
            if start - self.last.get((small, large), -5_000_000) < 5_000_000:
                continue
            if any(small not in row or large not in row for _, row in f[:6]):
                continue
            s0, l0 = f[0][1][small], f[0][1][large]
            s = bodies[small]
            d0 = dist[ix, jx]
            if np.linalg.norm(delta(l0[:2], s0[:2], self.side)) - d0 < 0.002:
                continue
            self.last[small, large] = start
            self.approaches += 1
            if any(small not in row or large not in row for _, row in f[5:]):
                continue
            self.exposed += 1
            before = np.mean([row[small][2:4] for _, row in f[:6]], axis=0)
            after = np.mean([row[small][2:4] for _, row in f[-6:]], axis=0)
            angle = turn_angle(before, after)
            if angle < 30:
                continue
            animal = np.array([row[small] for _, row in f[5:]])
            if (
                np.mean(abs(animal[:, 6])) < 0.01
                or np.mean(animal[:, 6] * animal[:, 5]) <= 0
                or max(animal[:, 7]) > 0
                or np.linalg.norm(animal[:, 2:4], axis=1).mean() < 0.001
            ):
                continue
            end_s, end_l = animal[-1, :2], f[-1][1][large][:2]
            away = delta(end_s, end_l, self.side)
            if unit_dot(after, away) < 0.7 or np.linalg.norm(away) - d0 < 0.005:
                continue
            velocity = delta(s[:2], s0[:2], self.side)  # preceding one-second ground displacement
            # Keep the larger body's observed path. Extrapolate the smaller one's original course.
            min_gap = min(
                capsule_gap(
                    s[:2] + velocity * ((t - start) / 1e6),
                    s[4],
                    self.members[small],
                    row[large][:2],
                    row[large][4],
                    self.members[large],
                    self.side,
                )
                for t, row in f[5:]
            )
            if min_gap <= 0:
                self.escape.append(
                    dict(
                        time_us=start,
                        small=small,
                        large=large,
                        turn_degrees=angle,
                        initial_distance_m=d0,
                        end_distance_m=float(np.linalg.norm(away)),
                        straight_course_gap_m=min_gap,
                    )
                )

    def kill(self, event):
        h, v = event["predator"], event["individual"]
        f = [(t, body) for t, body in self.frames if event["time_us"] - 5_000_000 <= t < event["time_us"]]
        if len(f) < 25 or any(h not in body or v not in body for _, body in f):
            return
        a = np.array([body[h] for _, body in f])
        prey = np.array([body[v][:2] for _, body in f])
        toward = delta(prey, a[:, :2], self.side)
        align = np.array([unit_dot(x, y) for x, y in zip(a[:, 2:4], toward)])
        angle = turn_angle(a[:5, 2:4].mean(axis=0), a[-5:, 2:4].mean(axis=0))
        if (
            angle >= 30
            and align[-5:].mean() >= 0.7
            and align[-5:].mean() - align[:5].mean() >= 0.3
            and np.linalg.norm(a[:, 2:4], axis=1).mean() >= 0.001
            and abs(a[:, 6]).mean() >= 0.01
            and (a[:, 5] * a[:, 6]).mean() > 0
            and max(a[:, 7]) == 0
            and np.linalg.norm(toward[0]) - np.linalg.norm(toward[-1]) >= 0.005
        ):
            self.pursuit.append(
                dict(
                    time_us=event["time_us"],
                    predator=h,
                    prey=v,
                    turn_degrees=angle,
                    initial_alignment=float(align[:5].mean()),
                    final_alignment=float(align[-5:].mean()),
                )
            )
