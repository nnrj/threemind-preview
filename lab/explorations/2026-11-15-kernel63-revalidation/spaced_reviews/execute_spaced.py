"""Declared E43 teaching and diagnostic stages on complete 6.3 subjects.

Importing this module creates no Core. A registered host must qualify this
apparatus before calling execute for formal materials.
"""
from dataclasses import replace
import io
import json
import lzma
from pathlib import Path
import sys
import time
from uuid import UUID,uuid5

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import materials_spaced as mat
sys.path.insert(0,str(HERE.parent/'autonomy_original'))
import execute_original as support
base=support.base;storage=support.storage;packed=support.packed;unpacked=support.unpacked
from threemind_transformer.language_session import LanguageSession
from threemind_transformer.language_senses import ProcessFeatures,embedding_frame
from lab.tools.language_observation import embedding_basis_peaks,trace_summary

KERNEL='threemind.continuous-memory/6.3'
NS=UUID('5391705f-9479-5094-8d79-9ab6728d1dcf')
FIELDS=('id','channel','activation','inhibition','direct','associative')


def stages(inventory):
    rows=[]
    for source in inventory['sources']:
        previous=None;begin=0
        for end in mat.CHECKPOINTS:
            key=source['key']+'/teach/'+str(end)
            rows.append({'key':key,'source':source['key'],'seed':source['seed'],'condition':source['condition'],
                'kind':'teach','begin_us':begin,'end_us':end*1000000,'parent':previous})
            previous=key;begin=end*1000000
        for probe in inventory['diagnostics']:
            if probe['source']!=source['key']:continue
            rows.append({**probe,'key':source['key']+'/probe/'+probe['key'],
                'kind':'probe','historical_kind':probe['kind'],'begin_us':probe['checkpoint']*1000000,
                'end_us':(probe['checkpoint']+2)*1000000,'parent':source['key']+'/teach/'+str(probe['checkpoint'])})
    assert len(rows)==580 and sum(v['kind']=='teach' for v in rows)==90
    seen=set()
    for row in rows:
        assert row['parent'] is None or row['parent'] in seen
        assert row['key'] not in seen
        seen.add(row['key'])
    return rows


def create(case,source,parent,whole,calibration):
    protocol=mat.protocol(73 if calibration else case['seed'])
    if parent is None:
        context={'schema':'threemind.language-runtime/1','kernel_id':KERNEL,'seed':protocol.seed,
            'protocol':protocol.model_dump(),'text_sensor':{},'readout_config':source['readouts'],
            'readouts':{'schema':'threemind.cli-readouts/1','session_id':str(uuid5(NS,case['source']))}}
        config={'seed':20260725 if calibration else mat.CORE_SEED,'plasticity':case['condition']!='frozen'}
        value=LanguageSession(protocol.model_dump(),kernel_id=KERNEL,config=config,context=context)
    else:
        assert whole is not None and whole['language']['protocol']==protocol.model_dump()
        value=LanguageSession(protocol.model_dump(),image=parent,context=whole['language'])
    assert value.kernel_id==KERNEL
    return value


def execute(case,source,folder,assets,background,parent=None,whole=None,*,calibration=False,mode='observed'):
    started=time.monotonic();value=create(case,source,parent,whole,calibration)
    initial=value.engine.capture_state();assert value.engine.time_us==case['begin_us']
    if parent is not None:assert initial.digest==parent.digest
    folder.mkdir(parents=True,exist_ok=False)
    if parent is None:storage.save(folder/'initial.tmind',initial)
    else:base.s.base.original(folder/'initial-reference.json',{'parent':case['parent'],'sha256':initial.digest})
    cursor=whole['background_cursor'] if whole else 0
    lesson=whole['lesson_cursor'] if whole else 0
    initial_context={'language':value.context(),'background_cursor':cursor,'lesson_cursor':lesson}
    packed(folder/'initial-whole.json.xz',initial_context)
    supplied=[];delivered=[];windows=[];restored=False
    initial_metrics=value.engine.metrics()
    def sink(event,entry):
        if entry:delivered.append(entry)
    value.reader.event_sink=sink

    def guard():
        if time.monotonic()-started>300:raise RuntimeError('registered stage wall cap; preserve current in-flight')

    def enqueue(stimulus,source_name,adapter,when,identity):
        relative=replace(base.Stimulus.from_dict(stimulus),time_us=0)
        receipts=value.reader.schedule([{'stimulus':relative,'labels':{}}],source=source_name,
            adapter_id=adapter,at=when,envelope_id=uuid5(NS,case['key']+':'+identity))
        supplied.extend({'enqueue_us':value.engine.time_us,'receipt':r} for r in receipts)

    def queue_background(end):
        nonlocal cursor
        while cursor<len(background) and int(background[cursor]['time_us'])<end:
            row=background[cursor];when=int(row['time_us'])
            assert when>=value.engine.time_us
            if row['stimulus']:
                enqueue(row['stimulus'],'recorded-physical-'+row['scope'],row['scope']+'-telemetry',when,'bg:'+str(cursor))
            cursor+=1

    def pause_or_restore():
        nonlocal value,restored
        if mode not in ('restored','paused') or restored:return
        image=value.engine.capture_state();context=value.context()
        if mode=='restored':
            value=LanguageSession(value.protocol.model_dump(),image=base.ArtifactCodec.decode(base.ArtifactCodec.encode(image)),context=context)
            value.reader.event_sink=sink
        else:time.sleep(.01)
        assert value.engine.capture_state().digest==image.digest and value.context()==context
        restored=True

    with lzma.open(folder/'trajectory.jsonl.xz','xb',preset=1) as compressed, \
            lzma.open(folder/'four-field.jsonl.xz','xb',preset=1) as extra:
        with io.TextIOWrapper(compressed,encoding='utf-8',newline='') as output, \
                io.TextIOWrapper(extra,encoding='utf-8',newline='') as additional:
            def write(row):
                json.dump(row,output,ensure_ascii=False,sort_keys=True,separators=(',',':'));output.write('\n')
            def write_extra(row):
                json.dump(row,additional,ensure_ascii=False,sort_keys=True,separators=(',',':'));additional.write('\n')
            if case['kind']=='teach':
                lessons=source['lessons']
                while value.engine.time_us<case['end_us']:
                    until=min(case['end_us'],value.engine.time_us+1000000)
                    value.records.clear();queue_background(until)
                    while lesson<len(lessons) and lessons[lesson]['time_us']<until:
                        item=lessons[lesson]
                        frame=embedding_frame(assets['vectors'][item['text']],value.protocol,1.)
                        enqueue(frame.to_dict(),'ordinary-spaced-language','language-transformer',item['time_us'],'lesson:'+str(lesson))
                        lesson+=1
                    value.reader.advance_to(until,guard=guard)
                    assert value.engine.life!='dead','unexpected death; retain complete evidence and in-flight'
                    if mode!='plain' and (mode!='sparse' or until%5000000==0):
                        write({'kind':'teaching','time_us':until,'metrics':value.engine.metrics(),
                            'readouts':value.records,'background_cursor':cursor,'lesson_cursor':lesson})
                        write_extra({'time_us':until,'nodes':[{k:n[k] for k in FIELDS} for n in value.engine.observation_nodes()]})
                    pause_or_restore()
            else:
                for index in range(4):
                    value.records.clear();begin=value.engine.time_us;until=begin+500000
                    queue_background(until)
                    if index==0 and case['probe'] is not None:
                        frame=embedding_frame(assets['vectors'][case['probe']],value.protocol,case['probe_intensity'])
                        enqueue(frame.to_dict(),'manual-language-adapter','language-transformer',begin,'cue')
                    observer=ProcessFeatures(value.protocol,begin,until);full=[]
                    def sample():
                        nodes=value.engine.observation_nodes()
                        observer.bus.publish({'time_us':value.engine.time_us,'nodes':nodes},owned=True)
                        if mode!='plain' and (mode!='sparse' or value.engine.time_us%100000==0):
                            full.append({'time_us':value.engine.time_us,'nodes':[{k:n[k] for k in FIELDS} for n in nodes]})
                    sample()
                    while value.engine.time_us<until:
                        value.reader.advance_to(min(until,value.engine.time_us+value.protocol.sample_us),guard=guard)
                        assert value.engine.life!='dead','unexpected death; retain complete evidence and in-flight'
                        sample()
                        assert observer.node_samples<=250000,'historical process-observation budget exceeded'
                    process=observer.result()
                    row={'window':index,'features':process['features'],'basis':embedding_basis_peaks(process,value.protocol),
                         'summary':trace_summary(process)}
                    windows.append(row)
                    write(row|{'kind':'probe','process':process,'readouts':value.records})
                    write_extra({'window':index,'points':full})
                    pause_or_restore()
    assert value.engine.time_us==case['end_us'] and value.reader.bus.pending_count()==0
    assert len(supplied)==len(delivered)
    final=value.engine.capture_state();storage.save(folder/'final.tmind',final)
    state={'language':value.context(),'background_cursor':cursor,'lesson_cursor':lesson}
    packed(folder/'whole.json.xz',state)
    packed(folder/'scheduled.json.xz',supplied);packed(folder/'delivered.json.xz',delivered)
    if case['kind']=='teach':
        graph=value.engine.graph();native=final.to_dict()
        assert not native['config']['dormant_traces_enabled']
        assert len(graph['nodes'])==len(native['nodes']) and len(graph['edges'])==len(native['edges'])
        packed(folder/'projection.json.xz',graph)
    assert value.engine.capture_state().digest==final.digest
    result={'key':case['key'],'source':case['source'],'kind':case['kind'],'kernel':KERNEL,
        'condition':case['condition'],'seed':case['seed'],'calibration':calibration,'mode':mode,
        'begin_us':case['begin_us'],'end_us':value.engine.time_us,'initial_sha256':initial.digest,
        'final_sha256':final.digest,'parent_sha256':parent.digest if parent else None,
        'initial_metrics':initial_metrics,'metrics':value.engine.metrics(),'life':value.engine.life,
        'inputs':len(delivered),'background_cursor':cursor,'lesson_cursor':lesson,'windows':windows,
        'wall_seconds':time.monotonic()-started,'status':'complete'}
    base.s.base.original(folder/'result.json',result)
    return result,final,state
