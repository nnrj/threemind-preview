"""Complete, bounded M4 course and declared causal copies; no Core changes."""
import gc,hashlib,json,os,time
from pathlib import Path
import torch
import pilot_m2 as m
import m4_balanced_course as course
import m4_regional_metrics as metrics
from m4_compact_subject import Subject
import m4_compact_evidence as codec
from m4_instrument import digest

SEEDS=tuple(range(1123100,1123108))
APPARATUS_SEED=1123002
ARMS=('sham','eye','hand','matched-eye','matched-hand','restored-eye','restored-hand')


class BoundaryPause(Exception):pass


def equivalent_sha(a):
    c=a.canonical();c['branch']=None
    return digest(c)


def mask(a,edges,restore=False):
    before=a.session.engine.capture_state().to_dict();sha=digest(before)
    assert not before['silenced_nodes'] and not before['silenced_edges']
    a.session.engine.intervene(edges=[tuple(e) for e in edges],action='silence')
    expected=dict(before);expected['silenced_edges']=sorted(edges)
    assert a.session.engine.capture_state().to_dict()==expected
    if restore:
        a.session.engine.intervene(edges=[tuple(e) for e in edges],action='restore')
        assert a.session.engine.capture_state().to_dict()==before
    return {'edges':edges,'action':'silence_then_immediate_restore' if restore else 'silence',
            'before_sha256':sha,'after_sha256':digest(a.session.engine.capture_state().to_dict()),
            'only_declared_mask_changed':True,'restoration_exact':not restore or a.session.engine.capture_state().to_dict()==before}


def observe_graph(a):
    before=digest(a.canonical());graph=a.session.engine.graph()
    assert digest(a.canonical())==before
    return graph


class Unit:
    def __init__(self,work,origin,guard,record):
        self.work=work;self.origin=origin;self.guard=guard;self.record=record
        self.folder=work/'units'/f'o{origin}';self.folder.mkdir(parents=True,exist_ok=False)
        self.bank=course.bank(origin);m.original(self.folder/'cases.json',self.bank)
        self.a=None;self.results={};self.features={};self.stage_receipts=[]

    def begin(self,label):
        if (self.work/'STOP').exists():raise BoundaryPause('resource stop at complete boundary')
        if not self.guard.thread.is_alive():raise RuntimeError('resource guard absent')
        m.original(self.work/'in-flight.json',{'unit':self.origin,'stage':label,'pid':os.getpid(),'epoch':time.time()})

    def end(self,label,extra=None):
        path=self.folder/'states'/label;start=time.perf_counter();self.a.save(path)
        receipt=m.read(path/'complete.json')
        result={'origin':self.origin,'stage':label,'path':path.relative_to(self.work).as_posix(),
                'time_us':self.a.session.engine.time_us,'canonical_sha256':receipt['canonical_sha256'],
                'motor_updates':self.a.motor.committed_updates,'word_updates':self.a.words.committed_updates,
                'save_wall_seconds':time.perf_counter()-start,'extra':extra}
        m.original(self.folder/'boundaries'/(label+'.json'),result);self.stage_receipts.append(result)
        m.atomic_json(self.work/'current-boundary.json',result)
        (self.work/'in-flight.json').unlink()
        self.record(result)
        if sum(p.stat().st_size for p in self.work.rglob('*') if p.is_file())>4*2**30 and not (self.work/'STOP').exists():
            m.original(self.work/'STOP',{'reason':'registered 4GiB original cap','epoch':time.time()})
        if (self.work/'STOP').exists():raise BoundaryPause('resource stop after complete boundary')

    def trials(self,label,tasks,*,teaching=False,calibrate=False):
        self.begin(label);self.a.phase=label;out=[];features=[];trajectory_hashes=[]
        for task in tasks:
            rows,values,result,samples=course.trial(self.a,task,teaching=teaching)
            path=self.folder/'trials'/label/task['id']
            codec.write(path/'trajectory.json.xz',rows)
            m.original(path/'result.json',result);m.original(path/'teaching-samples.json',samples)
            trajectory_hashes.append(digest(rows))
            if teaching:
                self.a.add_samples(task['id'],values,metadata={'stage':label,'task':task,'source':'declared balanced demonstration'})
            else:features.append(metrics.reduce_trial(task,rows,self.classes))
            out.append(result);del rows,values;gc.collect()
        calibration=None
        if calibrate:
            arrays=self.a.training_arrays();before=self.a.session.engine.time_us
            calibration=self.a.motor.continue_calibration(arrays['x'],arrays['eye'],arrays['hand'],arrays['move'],steps=120,batch_size=32)
            assert self.a.session.engine.time_us==before;del arrays;gc.collect()
        m.original(self.folder/'stages'/(label+'.json'),{'results':out,'trajectory_hashes':trajectory_hashes,'calibration':calibration})
        if features:codec.write(self.folder/'features'/(label+'.json.xz'),features)
        self.results[label]=out;self.features[label]=features
        self.end(label,{'calibration':calibration,'trajectory_hashes':trajectory_hashes})
        return out,trajectory_hashes

    def run(self):
        self.begin('birth');self.a=Subject(SEEDS[self.origin],identity=f'm4-balanced-v1-o{self.origin}',data_root=self.folder)
        self.classes=metrics.channel_classes(self.a.session.world.channels,self.a.session.world.vision_width)
        m.original(self.folder/'channel-classes.json',self.classes);self.end('birth')
        self.begin('warmup');self.a.phase='warmup'
        rows=[]
        for _ in range(60):rows.append(self.a.session.tick());self.a.cursor+=1
        codec.write(self.folder/'warmup.json.xz',rows);del rows;self.end('warmup')
        self.trials('pre',self.bank['pre'])
        for i,cycle in enumerate(self.bank['teaching_rounds']):
            for j,block in enumerate(cycle):self.trials(f'teach-{i}-{j}',block,teaching=True,calibrate=True)
        assert self.a.motor.committed_updates==1920 and sum(x['examples'] for x in self.a.corpus)==288
        self.trials('development',self.bank['development'])
        self.begin('selection')
        selection=metrics.fit_groups(self.features['pre'],self.features['development'],self.classes)
        graph=observe_graph(self.a);core=self.a.session.engine.capture_state().to_dict()
        table=metrics.edge_table(graph,core['config'],self.a.session.engine.time_us,selection)
        chosen=metrics.select_edges(table,selection)
        m.original(self.folder/'development-graph.json.gz',graph,compressed=True)
        m.original(self.folder/'group-selection.json',selection);m.original(self.folder/'edge-selection.json',chosen)
        del graph,core,table;gc.collect()
        # A read-only selection adds no subject state or new whole checkpoint.
        assert digest(self.a.canonical())==self.stage_receipts[-1]['canonical_sha256']
        (self.work/'in-flight.json').unlink()
        self.trials('confirmation',self.bank['confirmation'])
        g1=metrics.behavior(self.results['confirmation']);g2=metrics.confirm_groups(selection,self.features['confirmation'])
        self.begin('causal-preparation')
        graph=observe_graph(self.a);core=self.a.session.engine.capture_state().to_dict()
        table=metrics.edge_table(graph,core['config'],self.a.session.engine.time_us,selection)
        matching=metrics.recheck_edges(chosen,table)
        m.original(self.folder/'confirmation-graph.json.gz',graph,compressed=True)
        m.original(self.folder/'matching-recheck.json',matching);del graph,core,table;gc.collect()
        parent=self.folder/'states'/'confirmation';parent_manifest=m.read(parent/'complete.json')
        parent_sha=parent_manifest['canonical_sha256'];assert self.a.session.engine.time_us==255000000
        eligible=g1['qualified'] and g2['qualified'] and matching['valid']
        m.original(self.folder/'pre-causal-decision.json',{'G1':g1,'G2':g2,'matching':matching,'eligible':eligible,
                   'parent':str(parent),'parent_sha256':parent_sha,'selection_before_confirmation':True})
        (self.work/'in-flight.json').unlink()
        arms={};hashes={};states={};interventions={}
        if eligible:
            del self.a;self.a=None;gc.collect()
            for arm in ARMS:
                self.begin(arm+'-initial');self.a=Subject.restore(parent,data_root=self.folder)
                assert digest(self.a.canonical())==parent_sha
                self.a.branch={'name':arm,'parent_sha256':parent_sha,'parent_time_us':255000000,'explicit_research_copy':True}
                self.a.phase='causal'
                if arm=='sham':operation={'action':'sham','edges':[],'only_declared_mask_changed':True}
                else:
                    group='eye' if 'eye' in arm else 'hand'
                    kind='control' if arm.startswith('matched') else 'target'
                    edges=[p[kind]['key'] for p in chosen['groups'][group]]
                    operation=mask(self.a,edges,restore=arm.startswith('restored'))
                interventions[arm]=operation;m.original(self.folder/'interventions'/(arm+'.json'),operation)
                self.end(arm+'-initial')
                # Same phase/cases in every arm: metadata must not alter dynamics.
                self.begin(arm+'-final');self.a.phase='causal';out=[];hs=[]
                for task in self.bank['confirmation']:
                    rows,_,result,_=course.trial(self.a,task)
                    codec.write(self.folder/'causal'/arm/task['id']/'trajectory.json.xz',rows)
                    m.original(self.folder/'causal'/arm/task['id']/'result.json',result)
                    out.append(result);hs.append(digest(rows));del rows;gc.collect()
                assert self.a.motor.committed_updates==1920 and self.a.session.engine.time_us==291000000
                arms[arm]=out;hashes[arm]=hs;states[arm]=equivalent_sha(self.a)
                self.end(arm+'-final',{'trajectory_hashes':hs,'without_lineage_sha256':states[arm]})
                del self.a;self.a=None;gc.collect()
            exact={g:states['restored-'+g]==states['sham'] and hashes['restored-'+g]==hashes['sham'] for g in ('eye','hand')}
            g3=metrics.causal(arms,exact)
        else:g3={'qualified':False,'measurable':False,'reason':'G1/G2 or frozen matching gate not met; no uninterpretable lesion'}
        assert m.read(parent/'complete.json')==parent_manifest
        return {'origin':self.origin,'seed':SEEDS[self.origin],'valid':True,'G1':g1,'G2':g2,'G3':g3,
                'causal_eligible':eligible,'ordinary_seconds':255,'causal_seconds':252 if eligible else 0,
                'whole_states':len(self.stage_receipts),'boundaries':self.stage_receipts,'interventions':interventions,
                'parent_sha256':parent_sha,'reference_preserved':True,'motor_updates':1920,'scientific_origins':1}


def instrument(folder,seed=APPARATUS_SEED):
    """Known physical teacher path and exact edge-mask/restoration, N=0."""
    torch.set_num_threads(1);folder=Path(folder)
    a=Subject(seed,identity='m4-balanced-instrument',data_root=folder)
    task=course.task('known-joint','joint',course.POSITIONS[1],0)
    rows,values,result,samples=course.trial(a,task,teaching=True)
    assert result['joint_success'] and len(samples)==6
    a.add_samples('known',values,metadata={'source':'N0 instrument'})
    data=a.training_arrays();a.motor.continue_calibration(data['x'],data['eye'],data['hand'],data['move'],steps=2,batch_size=6)
    del data,rows,values;gc.collect();a.save(folder/'parent');parent_sha=digest(a.canonical())
    graph=observe_graph(a);edges=[[e['source'],e['target']] for e in graph['edges'][:16]]
    assert len(edges)==16;del graph,a;gc.collect();hashes={};trajectories={};operations={}
    for mode in ('sham','restored'):
        a=Subject.restore(folder/'parent',data_root=folder);assert digest(a.canonical())==parent_sha
        if mode=='restored':operations[mode]=mask(a,edges,True);assert digest(a.canonical())==parent_sha
        rows,_,_,_=course.trial(a,task)
        hashes[mode]=digest(a.canonical());trajectories[mode]=digest(rows)
        a.save(folder/mode);codec.write(folder/(mode+'-trajectory.json.xz'),rows)
        del a,rows;gc.collect()
    return {'passed':len(set(hashes.values()))==len(set(trajectories.values()))==1,
            'parent_sha256':parent_sha,'whole_hashes':hashes,'trajectory_hashes':trajectories,
            'operations':operations,'teacher_physics_passed':result['joint_success'],'scientific_origins':0,
            'seed':seed,'scientific_course_executed':False}
