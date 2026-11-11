"""Bounded bus fidelity and calibration-data diagnostics."""
import gzip,hashlib
from dataclasses import replace
from common import *
from threemind_core import Stimulus
from threemind_runtime.host import create_engine
from threemind_runtime.bus import InputBus
from threemind_runtime.activity_stream import RawActivityStream
from threemind_transformer.language_senses import ProcessFeatures
from threemind_transformer.language_protocol import LanguageProtocol
from lab.tools.recorded_background import RecordedBackground

def run():
    s=study();tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
    checks={};direct=create_engine(backend='native');routed=create_engine(backend='native');bus=InputBus(routed)
    frames=[Stimulus(t,((7,.4),(13,.8)),intensity=i) for t,i in ((0,1.),(1000,.5),(20000,1.))]
    for f in frames:
        direct.inject(f);bus.schedule(f,{'source':'manual-language-adapter','labels':{'7':['observer-only']}})
    checks['input_queue_equal']=direct.capture_state().to_dict()==routed.capture_state().to_dict()
    left,right=[],[]
    for t in (0,1000,20000,100000,200000):
        direct.advance_to(t);routed.advance_to(t)
        left.append(direct.observation_nodes());right.append(routed.observation_nodes())
    checks['input_trajectory_equal']=left==right
    checks['input_final_state_equal']=direct.capture_state().to_dict()==routed.capture_state().to_dict()
    # Explicit counterexamples establish what the old adapter representation loses.
    p=LanguageProtocol();base={'id':'1','channel':7,'activation':.5,'inhibition':.2}
    def legacy(seq):
        observer=ProcessFeatures(p,0,20000)
        for f in seq:observer.bus.publish(f)
        return observer.result()['features']
    same_a=[{'time_us':0,'nodes':[base]},{'time_us':20000,'nodes':[base]}]
    same_b=[{'time_us':0,'nodes':[base|{'inhibition':.9}]},{'time_us':20000,'nodes':[base]}]
    checks['legacy_inhibition_change_invisible']=legacy(same_a)==legacy(same_b)
    a=[{'time_us':0,'nodes':[base|{'activation':x}]} for x in (.2,.8)]
    b=list(reversed(a));checks['legacy_within_bin_order_invisible']=legacy(a)==legacy(b)
    # Representative real probes: bus framing compared to E47's direct measurements.
    e48=old_helpers();adapter=e48.adapter();case_rows=[]
    for seed in (223,279):
        for condition in ('continued','reversal'):
            for item in (0,1):
                guard(s);folder=WORK/'cases'/f'bus-s{seed}-{condition}-item{item}'
                if (folder/'result.json').exists():case_rows.append(read_json(folder/'result.json'));continue
                folder.mkdir(parents=True);started=time.monotonic()
                parent=OLD/'cases'/f's{seed}-{condition}'/'checkpoint-532'
                value=e48.old.e45.previous.restore(parent,71);cursor=read_json(parent/'summary.json')['cursor']
                frame=replace(adapter.world.frame(adapter.world.sample(item,9)),intensity=.5)
                value.reader.schedule([{'stimulus':frame,'labels':{}}],source='E49-bus-probe',adapter_id='raw-state-study/1')
                until=value.engine.time_us+2000000
                RecordedBackground(PREVIOUS/'physical-telemetry.jsonl').queue_before(value.reader,cursor,until)
                stream=RawActivityStream();records=[];stream.subscribe('expression-evidence',records.append)
                while True:
                    stream.sample(value.engine)
                    if value.engine.time_us>=until or value.engine.life=='dead':break
                    value.reader.advance_to(min(until,value.engine.time_us+20000),guard=lambda:guard(s))
                process={'start_us':records[0]['time_us'],'end_us':records[-1]['time_us'],'trajectory':records,'life':value.engine.life}
                write_gzip(folder/'process.json.gz',process)
                previous=OLD/'cases'/f's{seed}-{condition}-t532-words{item}-v9-i0.5-test-none'/'process.json.gz'
                with gzip.open(previous,'rt',encoding='utf-8') as f:old=json.load(f)
                def observation(p):
                    return [(f['time_us'],[{k:n[k] for k in ('id','channel','activation','inhibition','trace','support','stability')} for n in f['nodes']]) for f in p['trajectory']]
                result={'seed':seed,'condition':condition,'item':item,'bus_matches_direct':observation(process)==observation(old),
                    'frames':len(records),'life':value.engine.life,'wall_seconds':time.monotonic()-started}
                new_json(folder/'result.json',result);case_rows.append(result)
    checks['eight_real_bus_probes_equal']=all(r['bus_matches_direct'] for r in case_rows)
    train,_=partitions(223);x=np.asarray([r['values'] for r in train],dtype=np.float64)
    flat=x.reshape(len(x),-1);duplicate_conflicts=[];nearest=[]
    for i,row in enumerate(train):
        distances=np.linalg.norm(flat-flat[i],axis=1)
        opposite=[j for j,r in enumerate(train) if r['target']!=row['target']]
        j=min(opposite,key=lambda j:distances[j]);nearest.append(float(distances[j]))
        if distances[j]==0:duplicate_conflicts.append([i,j])
    field_values=x.reshape(16,17,-1,6)
    stats={name:{'min':float(field_values[:,:,:,i].min()),'max':float(field_values[:,:,:,i].max()),
        'rms':float(np.sqrt(np.mean(field_values[:,:,:,i]**2)))} for i,name in enumerate(('present','activation','inhibition','trace','support','stability'))}
    result={'checks':checks,'probe_cases':case_rows,'raw_shape':list(x.shape),'duplicate_conflicting_pairs':duplicate_conflicts,
        'nearest_other_label_l2':nearest,'field_statistics':stats,'evidence_scope':'eight deterministic probes and synthetic compression counterexamples'}
    new_json(HERE/'audit.json',result);new_json(WORK/'timing'/'audit.json',{'wall_seconds':time.monotonic()-tick})
    print(json.dumps(result,ensure_ascii=False),flush=True);s.active_case=None;s.db.close()
if __name__=='__main__':run()
