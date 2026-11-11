import numpy as np
from lab.tools.activity_controller import ActivityLayout
from lab.tools.choice_attribution import incoming_frame, paired_scores, raw_window
from lab.tools.choice_interventions import transfer_edges


def test_incoming_reader_ignores_answers_and_core_activity():
    layout = ActivityLayout([17, 8])
    s = {'channels': [[17, .4], [8, .2]], 'intensity': 2.}
    rows = [{'stimulus': s, 'activity': {'answer': 'not read'}, 'target': 3}]
    assert np.allclose(raw_window(layout, rows, kind='incoming', count=1), [[.4,0,0,0,.8,0,0,0]])
    assert np.array_equal(incoming_frame(layout, s), incoming_frame(layout, s | {'label': 'changed'}))


def test_identical_input_cannot_resolve_opposite_history_answers():
    y = [[0,1,2,3], [1,2,3,0]]
    result = paired_scores([y[0], y[0]], y)
    assert result['correct'] == result['history_free_ceiling'] == 4
    assert result['paired_both_correct'] == result['choices_changed'] == 0
    assert paired_scores(y, y)['paired_both_correct'] == 4


def test_transfer_uses_channels_not_donor_node_ids_and_preserves_recipient_history():
    a={'nodes':[{'id':1,'channel':8,'activation':.2},{'id':2,'channel':9,'activation':.7}],
       'edges':[{'source':1,'target':2,'weight':.4}], 'time_us':123,
       'operator_state':{'short_term':[],'fast':[]},'pending':[{'target':2}]}
    b={'nodes':[{'id':11,'channel':8},{'id':12,'channel':9}],
       'edges':[{'source':11,'target':12,'weight':.8}],
       'operator_state':{'short_term':[{'source':11,'target':12,'resource':.3}],'fast':[]}}
    result,receipt=transfer_edges(a,b,[(1,2)])
    assert result['nodes']==a['nodes'] and result['pending']==a['pending'] and result['time_us']==123
    assert result['edges']==[{'source':1,'target':2,'weight':.8}]
    assert a['edges'][0]['weight']==.4 and b['edges'][0]['source']==11
    assert result['operator_state']['short_term'][0]['target']==2
    assert receipt['inserted']['short_term']==1
