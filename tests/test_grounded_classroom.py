import numpy as np
from lab.tools.grounded_classroom import GroundedClassroom
from lab.tools.shape_color_world import ShapeColorWorld
from lab.tools.classroom_reviews import classroom_reviews


def test_background_physically_changes_body_and_restores():
    w = GroundedClassroom()
    initial = w.observe()['physical_background']
    for _ in range(40): w.advance_physics()
    after = w.observe()
    assert w.pointer.x != 0 and after['physical_background'] != initial
    restored = GroundedClassroom.restore(w.state())
    assert restored.stimulus(restored.observe()).to_dict() == w.stimulus(after).to_dict()
    w.advance_physics((.2,-.3)); restored.advance_physics((.2,-.3))
    assert w.state() == restored.state()


def test_no_answer_label_or_core_load_in_background():
    a, b = GroundedClassroom(), GroundedClassroom()
    b.set_scene([(3,0),(2,1),(1,2),(0,3)])
    b.marker = [.55,-.55]
    for _ in range(30): a.advance_physics(); b.advance_physics()
    assert a.observe()['physical_background'] == b.observe()['physical_background']
    observation = a.observe(); before = a.stimulus(observation)
    observation['physical_background'] = {'answer': 'arbitrary'}
    observation['items'] = ['arbitrary']
    assert a.stimulus(observation) == before
    assert a.channels[:272] == ShapeColorWorld().channels
    assert len(set(a.channels)) == 292


def test_whole_lesson_spacing_and_equal_dose_control():
    a,b = classroom_reviews(),classroom_reviews(mode='uniform')
    assert len(a) == len(b) == 168
    assert [r['item'] for r in a] == [r['item'] for r in b]
    assert a[:96] == b[:96]
    assert [r['time_us'] for r in a[-8:]] == [r['time_us'] for r in b[-8:]]
    for rows in (a,b):
        assert min(y['time_us']-x['time_us'] for x,y in zip(rows,rows[1:])) >= 1500000
        for item in range(8): assert sum(r['item']==item for r in rows) == 21
    for gap in (12,24,48,96):
        rows=[r for r in a if r['phase']==f'review-{gap}s']
        for item in range(8):
            times=[r['time_us'] for r in rows if r['item']==item]
            assert times[1]-times[0] == gap*1000000
