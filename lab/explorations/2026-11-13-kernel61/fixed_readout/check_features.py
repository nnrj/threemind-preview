"""Numerical checks of the temporal measurement; creates no Core or scientific subject."""
from decimal import Decimal
import inspect
import json
import math

import readout_rig as g


def check():
    trajectory = [{'dt_us': i * 1000,
                   **{field: [float(i + 1000 * f + j) for j in range(12)] for f, field in enumerate(g.FIELDS)}}
                  for i in range(1, 251)]
    vector = g.process_features(trajectory)
    expected = []
    for block in range(5):
        for field in range(4):
            for channel in range(12):
                value = sum(Decimal(i + 1000 * field + channel) for i in range(1 + 50 * block, 51 + 50 * block)) / 50
                expected.append(float(value))
    assert vector == expected and len(vector) == 240
    rejected = 0
    for invalid in (trajectory[:-1], trajectory[::-1], trajectory[1:] + trajectory[:1]):
        try: g.process_features(invalid)
        except ValueError: rejected += 1
    assert rejected == 3
    zeros = [{'dt_us': i * 1000, **{field: [0.] * 12 for field in g.FIELDS}} for i in range(1, 251)]
    import copy
    early, late = copy.deepcopy(zeros), copy.deepcopy(zeros)
    for row in early[:50]: row['activation'][0] = 1.
    for row in late[-50:]: row['activation'][0] = 1.
    assert sum(r['activation'][0] for r in early) == sum(r['activation'][0] for r in late)
    assert early[109]['activation'] == late[109]['activation']
    assert g.process_features(early) != g.process_features(late)
    # A view suffices for testing the declared output mask; no constructor runs.
    view = type('ChannelView', (), {'channels': dict(zip(g.SYMBOLS, range(12, 0, -1)))})()
    masked = g.Subject.port_features(view, [1.] * 240)
    assert sum(masked) == 40 and all(masked[b * 12 + j] == (j in (10, 11)) for b in range(20) for j in range(12))
    reader = g.Reader(dimension=240)
    a = g.process_features(early); b = g.process_features(late)
    reader.learn([{'features': a, 'label': 1}, {'features': b, 'label': -1}])
    assert reader.infer(a)['answer'] == 1 and reader.infer(b)['answer'] == -1
    assert math.isclose(reader.infer(a)['score'], 1 / 1.001, abs_tol=1e-12)
    restored = g.Reader(reader.save())
    assert restored.save() == reader.save()
    more = [{'features': a, 'label': 1}]
    restored.learn(more); reader.learn(more)
    assert restored.save() == reader.save() and reader.updates == 3
    from audit_readout import reader_check, temporal_features, projected_weight
    audit_reader = g.Reader(dimension=240)
    training = [{'features': a if i % 2 == 0 else b, 'label': 1 if i % 2 == 0 else -1} for i in range(12)]
    audit_reader.learn(training)
    reader_check(audit_reader.save())
    audit_reader.learn(training[:6]); reader_check(audit_reader.save())
    audit_reader.learn(training[:6]); reader_check(audit_reader.save())
    assert temporal_features(trajectory) == expected
    from types import SimpleNamespace
    cfg = SimpleNamespace(decay_curve='inverse-logarithmic', retention_relaxation_enabled=False)
    assert math.isclose(projected_weight({'decay_age': 0., 'state_us': '0', 'half_life': 30., 'weight': .5}, 30000000, cfg), .25, abs_tol=1e-15)
    from analyze import endpoint_view
    transformed = endpoint_view({'histories': [{'response': {'answer': 1}, 'endpoint_response': {'answer': -1},
                                               'features': [1.] * 240, 'endpoint_features': [2.] * 12}]})
    assert transformed['histories'][0]['response']['answer'] == -1
    assert transformed['histories'][0]['features'] == [2.] * 12
    assert list(inspect.signature(g.Reader.infer).parameters) == ['self', 'features']
    class TeachingView:
        seed = 1056100
        time = 0
        channels = dict(zip(g.SYMBOLS, range(12)))
        def __init__(self): self.seen = {}
        def advance(self, end, events, observed=False):
            self.seen.update({t: v for t, v in events.items() if self.time < t <= end})
            self.time = end
        def features(self): return [0.] * 12
    lessons = []
    for history, groups in ((None, 2), (0, 4), (1, 4)):
        teacher_view = TeachingView(); record = g.teach(teacher_view, history)
        times = sorted(teacher_view.seen)
        onsets = times[::groups]
        gaps = [b - a for a, b in zip(onsets, onsets[1:])]
        assert teacher_view.time == 18000000 and len(times) == 16 * groups
        assert gaps == record['round_gaps_us'] == [800000] * 5 + [1000000] * 5 + [1200000] * 5
        assert all(b - a == 250000 for i in range(16) for a, b in zip(times[i*groups:(i+1)*groups-1], times[i*groups+1:(i+1)*groups]))
        lessons.append({'history': history, 'groups': groups, 'duration_us': teacher_view.time, 'repetitions': 16})
    return {'passed': True, 'dimensions': 240, 'fields': list(g.FIELDS), 'bins': 5,
            'order_distinguishable_with_equal_total_and_endpoint': True, 'missing_window_rejected': rejected,
            'personal_readout_restore_and_continue_equal': True, 'lessons': lessons, 'Core_engines_created': 0}


if __name__ == '__main__': print(json.dumps(check()))
