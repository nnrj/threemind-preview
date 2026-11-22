"""Apply the registered kinematic tests to eligible live encounters at their observed size."""

import numpy as np
from turns import EncounterTurns, capsule_gap, delta, turn_angle, unit_dot


def family_roots(individual, members):
    roots = {individual}
    for _ in range(3):
        individual = members[individual]["parent"]
        if individual is None:
            break
        roots.add(individual)
    return frozenset(roots)


class GrowingEncounters(EncounterTurns):
    def __init__(self, side, members):
        super().__init__(side, {i: dict(m) for i, m in members.items()})
        self.roots = {i: family_roots(i, members) for i in members}

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
        for i in ids:
            self.members[i]["radius"] = float(bodies[i][8])
        radii = np.array([self.members[i]["radius"] for i in ids])
        ds = delta(xy[None, :, :], xy[:, None, :], self.side)
        dist = np.linalg.norm(ds, axis=2)
        reach = np.array([min(0.06, 3 * self.members[i]["sensor_range"]) for i in ids])
        smalls, larges = np.where((radii[:, None] < radii[None, :]) & (dist <= reach[:, None]))
        for ix, jx in zip(smalls, larges):
            small, large = ids[ix], ids[jx]
            if not self.roots[small].isdisjoint(self.roots[large]):
                continue
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
                    {
                        "time_us": start,
                        "small": small,
                        "large": large,
                        "turn_degrees": angle,
                        "initial_distance_m": d0,
                        "end_distance_m": float(np.linalg.norm(away)),
                        "straight_course_gap_m": min_gap,
                    }
                )
