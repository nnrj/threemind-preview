"""Complete-stage M4 continuation; delegates all science to frozen v2 methods.

This new host adapter never edits the frozen curriculum, criteria or Core. A
fresh process receives the complete latest ordinary state, or an explicitly
registered causal parent, and performs exactly one previously unexecuted stage.
"""
import gc,json
from pathlib import Path
import pilot_m2 as m
import m4_balanced_rig_v2 as rig

from m4_continuation_plan import ORDINARY,CAUSAL,decide,inspect_origin,next_stage


def attach_unit(work,origin,guard,record):
    folder=work/'units'/f'o{origin}'
    if not folder.exists():return rig.Unit(work,origin,guard,record)
    u=rig.Unit.__new__(rig.Unit)
    u.work=work;u.origin=origin;u.guard=guard;u.record=record;u.folder=folder
    u.bank=rig.course.bank(origin);u.a=None;u.results={};u.features={};u.stage_receipts=[]
    u.classes={int(k):v for k,v in m.read(folder/'channel-classes.json').items()}
    for label in ORDINARY+CAUSAL:
        p=folder/'boundaries'/(label+'.json')
        if p.exists():u.stage_receipts.append(m.read(p))
    for label in ORDINARY:
        p=folder/'stages'/(label+'.json')
        if p.exists():u.results[label]=m.read(p)['results']
    for label in ('pre','development','confirmation'):
        p=folder/'features'/(label+'.json.xz')
        if p.exists():u.features[label]=rig.codec.read(p)
    return u


def selection(u):
    u.begin('selection')
    chosen_groups=rig.metrics.fit_groups(u.features['pre'],u.features['development'],u.classes)
    graph=rig.observe_graph(u.a);core=u.a.session.engine.capture_state().to_dict()
    table=rig.metrics.edge_table(graph,core['config'],u.a.session.engine.time_us,chosen_groups)
    chosen=rig.metrics.select_edges(table,chosen_groups)
    m.original(u.folder/'development-graph.json.gz',graph,compressed=True)
    m.original(u.folder/'group-selection.json',chosen_groups);m.original(u.folder/'edge-selection.json',chosen)
    del graph,core,table;gc.collect()
    expected=m.read(u.folder/'states/development/complete.json')['canonical_sha256']
    assert rig.digest(u.a.canonical())==expected
    (u.work/'in-flight.json').unlink()


def causal_preparation(u):
    u.begin('causal-preparation')
    groups=m.read(u.folder/'group-selection.json');chosen=m.read(u.folder/'edge-selection.json')
    g1=rig.metrics.behavior(u.results['confirmation']);g2=rig.metrics.confirm_groups(groups,u.features['confirmation'])
    graph=rig.observe_graph(u.a);core=u.a.session.engine.capture_state().to_dict()
    table=rig.metrics.edge_table(graph,core['config'],u.a.session.engine.time_us,groups)
    matching=rig.metrics.recheck_edges(chosen,table)
    m.original(u.folder/'confirmation-graph.json.gz',graph,compressed=True)
    m.original(u.folder/'matching-recheck.json',matching);del graph,core,table;gc.collect()
    parent=u.folder/'states/confirmation';r=m.read(parent/'complete.json')
    assert u.a.session.engine.time_us==255000000 and rig.digest(u.a.canonical())==r['canonical_sha256']
    m.original(u.folder/'pre-causal-decision.json',{'G1':g1,'G2':g2,'matching':matching,
               'eligible':g1['qualified'] and g2['qualified'] and matching['valid'],
               'parent':str(parent),'parent_sha256':r['canonical_sha256'],'selection_before_confirmation':True})
    (u.work/'in-flight.json').unlink()


def causal_initial(u,arm):
    u.begin(arm+'-initial')
    parent=u.folder/'states/confirmation';sha=m.read(parent/'complete.json')['canonical_sha256']
    assert rig.digest(u.a.canonical())==sha and u.a.branch is None
    u.a.branch={'name':arm,'parent_sha256':sha,'parent_time_us':255000000,'explicit_research_copy':True}
    u.a.phase='causal'
    if arm=='sham':op={'action':'sham','edges':[],'only_declared_mask_changed':True}
    else:
        group='eye' if 'eye' in arm else 'hand';kind='control' if arm.startswith('matched') else 'target'
        chosen=m.read(u.folder/'edge-selection.json')
        edges=[p[kind]['key'] for p in chosen['groups'][group]]
        op=rig.mask(u.a,edges,restore=arm.startswith('restored'))
    m.original(u.folder/'interventions'/(arm+'.json'),op);u.end(arm+'-initial')


def causal_final(u,arm):
    u.begin(arm+'-final');u.a.phase='causal';hs=[]
    assert u.a.branch['name']==arm and u.a.session.engine.time_us==255000000
    for task in u.bank['confirmation']:
        rows,_,result,_=rig.course.trial(u.a,task)
        rig.codec.write(u.folder/'causal'/arm/task['id']/'trajectory.json.xz',rows)
        m.original(u.folder/'causal'/arm/task['id']/'result.json',result)
        hs.append(rig.digest(rows));del rows;gc.collect()
    assert u.a.motor.committed_updates==1920 and u.a.session.engine.time_us==291000000
    u.end(arm+'-final',{'trajectory_hashes':hs,'without_lineage_sha256':rig.equivalent_sha(u.a)})


def finish(u):
    u.begin('finish-result')
    d=m.read(u.folder/'pre-causal-decision.json');arms={};hs={};states={};ops={}
    if d['eligible']:
        for arm in rig.ARMS:
            arms[arm]=[m.read(u.folder/'causal'/arm/task['id']/'result.json') for task in u.bank['confirmation']]
            final=m.read(u.folder/'boundaries'/(arm+'-final.json'))['extra']
            hs[arm]=final['trajectory_hashes'];states[arm]=final['without_lineage_sha256']
            ops[arm]=m.read(u.folder/'interventions'/(arm+'.json'))
        exact={g:states['restored-'+g]==states['sham'] and hs['restored-'+g]==hs['sham'] for g in ('eye','hand')}
        g3=rig.metrics.causal(arms,exact)
    else:g3={'qualified':False,'measurable':False,'reason':'G1/G2 or frozen matching gate not met; no uninterpretable lesion'}
    result={'origin':u.origin,'seed':rig.SEEDS[u.origin],'valid':True,'G1':d['G1'],'G2':d['G2'],'G3':g3,
            'causal_eligible':d['eligible'],'ordinary_seconds':255,'causal_seconds':252 if d['eligible'] else 0,
            'whole_states':len(u.stage_receipts),'boundaries':u.stage_receipts,'interventions':ops,
            'parent_sha256':d['parent_sha256'],'reference_preserved':True,'motor_updates':1920,'scientific_origins':1}
    assert result['whole_states']==(35 if d['eligible'] else 21)
    m.original(u.folder/'result.json',result);(u.work/'in-flight.json').unlink()
    return result


def execute(work,step,guard,record):
    if next_stage(work)!=step:raise RuntimeError('next stage changed; do not dispatch stale work')
    u=attach_unit(work,step['origin'],guard,record);label=step['stage']
    if step['parent'] is not None:
        parent=u.folder/'states'/step['parent'];u.a=rig.Subject.restore(parent,data_root=u.folder)
        if label not in {arm+'-initial' for arm in rig.ARMS}:
            current=m.read(work/'current-boundary.json')
            assert current['path']==parent.relative_to(work).as_posix()
            assert current['canonical_sha256']==rig.digest(u.a.canonical())
        if label not in CAUSAL:
            assert u.a.branch is None
        m.original(guard.evidence/'loaded-state.json',{'source':str(parent),
                   'canonical_sha256':rig.digest(u.a.canonical()),'time_us':u.a.session.engine.time_us,
                   'exact_complete_state_restore':True,'simulation_advanced_by_load':False})
    if label=='birth':
        u.begin('birth');u.a=rig.Subject(rig.SEEDS[u.origin],identity=f'm4-balanced-v2-o{u.origin}',data_root=u.folder)
        u.classes=rig.metrics.channel_classes(u.a.session.world.channels,u.a.session.world.vision_width)
        m.original(u.folder/'channel-classes.json',u.classes);u.end('birth')
    elif label=='warmup':
        u.begin(label);u.a.phase=label;rows=[]
        for _ in range(60):rows.append(u.a.session.tick());u.a.cursor+=1
        rig.codec.write(u.folder/'warmup.json.xz',rows);del rows;u.end(label)
    elif label.startswith('teach-'):
        _,i,j=label.split('-');u.trials(label,u.bank['teaching_rounds'][int(i)][int(j)],teaching=True,calibrate=True)
    elif label in ('pre','development','confirmation'):
        if label=='development':
            assert u.a.motor.committed_updates==1920 and sum(x['examples'] for x in u.a.corpus)==288
        u.trials(label,u.bank[label])
    elif label=='selection':selection(u)
    elif label=='causal-preparation':causal_preparation(u)
    elif label=='finish':return finish(u)
    elif label in CAUSAL:
        arm,part=label.rsplit('-',1)
        (causal_initial if part=='initial' else causal_final)(u,arm)
    else:raise ValueError('unregistered action')
    return None
