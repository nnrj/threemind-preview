from collections import Counter
import numpy as np
from lab.tools.classroom_motor import motor_reviews,choice_scene,raw_process_window,PAIRS


def test_motor_reviews_keep_initial_repeats_and_expand_per_item():
    rows=motor_reviews()
    assert len(rows)==180 and rows[-1]['time_us']+3000000==684000000
    assert Counter(r['item'] for r in rows)==dict.fromkeys(range(12),15)
    for item in range(12):
        own=[r for r in rows if r['item']==item]
        assert all(r['since_same_item_us']==3000000 for r in own[1:12])
        assert own[13]['since_same_item_us']==72000000
        assert own[14]['since_same_item_us']==144000000
    assert all(b['time_us']-a['time_us']>=3000000 for a,b in zip(rows,rows[1:]))


def test_choices_require_both_colour_and_shape_at_every_position():
    for shape,color in PAIRS:
        for slot in range(4):
            items=choice_scene(shape,color,slot,slot)
            assert items[slot]==(shape,color) and len(set(items))==4
            assert sum(s==shape for s,c in items)==2
            assert sum(c==color for s,c in items)==2


def test_observer_window_retains_real_values_and_request_history():
    class Layout:
        def frame(self,row):return np.array(row,dtype=np.float32)
    rows=[{'activity':[i,-i]} for i in range(30)]
    recent=raw_process_window(Layout(),rows,'recent')
    episode=raw_process_window(Layout(),rows,'episode')
    assert recent.shape==(4,2) and episode.shape==(16,2)
    assert recent[0,0]==26 and episode[0,0]==0
    assert np.array_equal(episode[-1],recent[-1])
    assert np.all(episode[:,1]==-episode[:,0])
