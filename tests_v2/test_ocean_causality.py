from lab.tools.ocean_contact import ContactOcean, ContactProtocol
from lab.tools.ocean_causality import select_pathways, replay, compare, local_persistent_transplant
from lab.tools.ocean_controls import naive_same_receptors
from threemind_runtime.inheritance import birth
from lab.tools.ocean_causality import neutralize_persistent_strength
from threemind_core import Config, Stimulus
from threemind_runtime import create_engine


def test_selective_control_restore_and_matching_inputs():
    w=ContactOcean(ContactProtocol(founders=1,reproduction=False,nutrient_initial=12).model_dump(by_alias=True))
    for _ in range(30):w.step()
    image=w.engines[0].capture_state()
    # Artificial selection fixture; real studies must supply measured recent channels.
    n=image.to_dict()['nodes']
    p=select_pathways(image,{x['channel'] for x in n},maximum=4)
    assert not p['applicable']
    p=select_pathways(image,{x['channel'] for x in n[2:]},maximum=4)
    assert p['applicable']
    rows=[]
    for _ in range(15):w.step(lambda r:rows.extend(r['inputs']))
    sham,_=replay(image,rows)
    restored,_=replay(image,rows,'restore',edges=p['target_edges'])
    assert compare(sham,restored)['motor_peak_absolute']==0
    a,_=replay(image,rows,'target',edges=p['target_edges'])
    assert len(a)==len(sham)
    old=birth(image); blank=naive_same_receptors(image)
    graft=local_persistent_transplant(blank,old,p['target_edges'])
    assert len(graft.to_dict()['edges'])==len(p['target_edges'])
    cut=neutralize_persistent_strength(image).to_dict()
    original=image.to_dict()
    assert cut['energy']==original['energy'] and cut['queue']==original['queue']
    assert [n['activation'] for n in cut['nodes']]==[n['activation'] for n in original['nodes']]
    assert all(e['weight']==0 for e in cut['edges'])


def test_replay_preserves_death_instead_of_injecting_or_reviving():
    e=create_engine(Config(activation_tau=.001),backend='native')
    e.inject(Stimulus(1000,((101,1.),)));e.advance_to(10000)
    e.close_inputs();e.advance_to(1200000)
    assert e.life=='dead'
    image=e.capture_state()
    rows=[{'stimulus':{'time_us':'1300000','channels':[[101,1.]],'intensity':1.},'food':100.}]
    trace,end=replay(image,rows)
    assert len(trace)==1 and trace[0]['input_delivered'] is False
    assert trace[0]['life']=='dead' and end.to_dict()==image.to_dict()
