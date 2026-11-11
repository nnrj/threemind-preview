"""Independent, CPU-only E67 diagnostic copies; never changes the main host."""
from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from uuid import UUID, uuid5

os.environ['OMP_NUM_THREADS'] = os.environ['MKL_NUM_THREADS'] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = ''
ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'src'))
import numpy as np
import psutil
import torch
from lab.tools.recognition_session import RecognitionSystem
from lab.tools.calibrated_activity import CalibratedActivity
from lab.tools.centered_recognition import WORDS
from threemind_lab.config import load_env
from threemind_lab.operations_client import OperationsClient
from threemind_lab.research_recorder import ResearchRecorder
from threemind_lab.research_storage import ResearchStorage

INDICES = (0, 1, 2, 3, 6, 9, 28, 30, 31, 38, 39, 46)
RESOURCE = 'research:e67-causal-probes-20261012'
KEY = 'causal-probes-20261012'


def read(path): return json.loads(Path(path).read_bytes())


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while block := f.read(1024**2): h.update(block)
    return h.hexdigest()


def write(path, content):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    content = content if isinstance(content, bytes) else encoded(content)
    if path.exists():
        if path.read_bytes() != content: raise ValueError('immutable original conflict: '+str(path))
        return
    temp = path.with_name(path.name+'.partial')
    with temp.open('xb') as f:
        f.write(content); f.flush(); os.fsync(f.fileno())
    temp.rename(path)


def guard(work):
    if (work/'STOP').exists(): raise RuntimeError('diagnostic STOP requested')
    if shutil.disk_usage(work).free < 35*2**30: raise RuntimeError('stop diagnosis: preserve 35 GiB disk for /4')
    if psutil.virtual_memory().available < 4*2**30: raise RuntimeError('stop diagnosis: preserve 4 GiB RAM for /4')


def protect_host():
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    p = psutil.Process()
    if os.name == 'nt': p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    if hasattr(p, 'cpu_affinity'): p.cpu_affinity([p.cpu_affinity()[-1]])


def answer(model, x, label):
    logits = model.predict(x[None])[0]
    prob = torch.as_tensor(logits).softmax(-1).tolist()
    selected = int(logits.argmax())
    return dict(selected=selected, word=WORDS[selected], correct=selected==label,
                probabilities=prob, logits=logits.tolist(), true_probability=prob[label],
                true_margin=float(logits[label]-np.max(np.delete(logits,label))))


def model_hash(model):
    h = hashlib.sha256()
    for k, v in model.state_dict().items():
        h.update(k.encode()); h.update(v.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def io_hash(rows):
    h=hashlib.sha256()
    for row in rows: h.update(encoded(row['stimulus']))
    return h.hexdigest()


def paths(source, arm):
    a=source/'arms'/arm
    return {'birth':a/'initial-teaching/birth/words',
            'initial_fit':a/'initial-fit/system/words', 'final_fit':a/'fit-3/system/words'}


def prepare(source, work):
    if (work/'plan.json').exists(): return read(work/'plan.json')
    expected=ResearchStorage().workspace_path(HERE.name)
    if work!=expected: raise ValueError('diagnosis must use its distinct managed workspace')
    questions={arm:read(source/'arms'/arm/'final/predictions.json') for arm in ('2','3.1')}
    selected=[]
    scientific=('question_id','shape','color','label','attribute','offset','text')
    for index in INDICES:
        a,b=(questions[arm][index] for arm in ('2','3.1'))
        if any(a[k]!=b[k] for k in scientific): raise ValueError('mismatched question')
        selected.append(dict(index=index, task={k:a[k] for k in scientific},
                             original={arm:questions[arm][index]['selected'] for arm in ('2','3.1')}))
    source_files=set()
    for arm in ('2','3.1'):
        source_files.update(p for p in (source/'arms'/arm/'fit-3/system').rglob('*') if p.is_file())
        for folder in paths(source,arm).values(): source_files.update(p for p in folder.rglob('*') if p.is_file())
        source_files.add(source/'arms'/arm/'final/predictions.json')
        for i in INDICES:
            source_files.add(source/'arms'/arm/'final/trials'/f'{i:04d}.npz')
            source_files.add(source/'arms'/arm/'final/clips'/f'{i:06d}.json.gz')
    implementation=read(source/'source-reference-r3/manifest.json')
    if any(sha(ROOT/name)!=digest for name,digest in implementation.items()):
        raise ValueError('frozen source implementation changed')
    import _threemind_native
    plan=dict(schema='threemind.e67-causal-probes/1',created_epoch=time.time(),source=str(source),
              arms=['2','3.1'],questions=selected,conditions=['normal','silence','rescue'],
              source_files={p.relative_to(source).as_posix():sha(p) for p in sorted(source_files)},
              implementation_manifest_sha256=sha(source/'source-reference-r3/manifest.json'),
              native_binary=dict(path=_threemind_native.__file__,sha256=sha(_threemind_native.__file__)),
              own_sources={p.name:sha(p) for p in (HERE/'probe.py',HERE/'design.zh.md',HERE/'design.en.md')},
              no_training=True,no_gpu=True,selection='purposive, fixed before interventions; not population accuracy',
              intervention='once-only silence of existing edges; preserve nodes, in-flight activity and future edges',
              reader_diagnostic='same saved activity; personal birth, initial-fit, final-fit readers; zero-input control')
    work.mkdir(parents=True,exist_ok=True)
    for name in plan['own_sources']: write(work/'source-reference'/name,(HERE/name).read_bytes())
    write(work/'plan.json',plan)
    return plan


def recording(source, work, *, setup=False):
    project=read(source/'platform.json')['project_id']
    identity=read(source/'.research-records/identity.json')
    c=OperationsClient.from_environment(source='ai')
    if setup:
        resources=c.request('GET','/api/v2/storage')['resources']
        existing=next((r for r in resources if r['id']==RESOURCE),None)
        if existing is None:
            c.request('POST','/api/v2/storage/resources',body=dict(resource_id=RESOURCE,
                target_id='managed-research-experiments',relative_path=work.name,writer_mode='cooperative',expected_revision=0))
        c.request('POST','/api/v2/storage/record-evidence-grants',body=dict(project_id=project,resource_id=RESOURCE))
    rec=ResearchRecorder(work,project,client=c)
    write(rec.control/'identity.json',identity)
    rec.resume_recording()
    return c,rec,lambda key:str(uuid5(UUID(project),'e67:'+KEY+':'+key))


def attach(rec,rid,work,path,role):
    name=path.relative_to(work).as_posix()
    rec.attach(dict(logical_id=KEY+':'+name,role=role,label='E67 因果诊断 / '+name,
        format=''.join(path.suffixes).lstrip('.') or 'opaque',byte_count=path.stat().st_size,sha256=sha(path),
        stage_key=KEY,locator=dict(kind='file',resource_id=RESOURCE,member=name)),request_id=rid('file:'+name))


def register(source,work):
    plan=prepare(source,work)
    c,rec,rid=recording(source,work,setup=True)
    try:
        rec.append('condition',KEY,dict(plan=plan,interpretation='post-outcome diagnostic copies; original scores unchanged'),request_id=rid('plan'))
        for lang in ('zh','en'):
            rec.text(dict(request_id=rid('protocol:'+lang),identity=rid('protocol-text:'+lang),kind='protocol',expected_revision=0,
                title='E67 附属因果诊断 / adjunct causal protocol · '+lang,markdown=(HERE/f'design.{lang}.md').read_text(encoding='utf-8')))
        for path in [work/'plan.json',*sorted((work/'source-reference').iterdir())]: attach(rec,rid,work,path,'protocol')
        rec.synchronize(strict=True)
        write(work/'registered.json',dict(plan_sha256=sha(work/'plan.json'),experiment=rec.experiment,resource=RESOURCE))
    finally:c.close()
    print(json.dumps(dict(registered=str(work),questions=len(plan['questions'])),ensure_ascii=False),flush=True)


def verify_sources(source,work,plan):
    for name,digest in plan['source_files'].items():
        if sha(source/name)!=digest:raise ValueError('original source changed: '+name)
    for name,digest in plan['own_sources'].items():
        if sha(HERE/name)!=digest:raise ValueError('diagnostic implementation changed: '+name)
    if sha(plan['native_binary']['path'])!=plan['native_binary']['sha256']:raise ValueError('native binary changed')


def reader_probes(source,work,arm,plan):
    out=work/'arms'/arm/'reader-probes.json'
    if out.exists():return
    results=[]
    for stage,folder in paths(source,arm).items():
        guard(work);model=CalibratedActivity.restore(folder,'cpu');before=model_hash(model)
        for q in plan['questions']:
            with np.load(source/'arms'/arm/'final/trials'/f"{q['index']:04d}.npz",allow_pickle=False) as d:x=d['x']
            result=answer(model,x,q['task']['label'])
            if stage=='final_fit' and result['selected']!=q['original'][arm]:raise ValueError('CPU reader does not reproduce original answer')
            results.append(dict(stage=stage,question_id=q['task']['question_id'],**result))
            if stage=='final_fit':results.append(dict(stage='zero_input',question_id=q['task']['question_id'],**answer(model,np.zeros_like(x),q['task']['label'])))
        if model_hash(model)!=before:raise ValueError('read-only prediction changed weights')
        del model;gc.collect()
    write(out,results)
    print(json.dumps(dict(arm=arm,reader_probe_counts={s:sum(r['correct'] for r in results if r['stage']==s) for s in ('birth','initial_fit','final_fit','zero_input')})),flush=True)


def probe(source,work,arm,q,mode):
    task=q['task'];folder=work/'arms'/arm/task['question_id']/mode
    result_path=folder/'result.json'
    if result_path.exists():return read(result_path)
    if folder.exists():raise ValueError('inspect unfinished probe before rerunning: '+str(folder))
    guard(work);start=time.monotonic()
    a=RecognitionSystem.restore(source/'arms'/arm/'fit-3/system','cpu')
    model_before=model_hash(a.words)
    before=a.session.engine.capture_state().to_dict()
    edges=[(e['source'],e['target']) for e in before['edges']]
    if before['silenced_edges'] or before['silenced_nodes']:raise ValueError('source is not an intact baseline')
    if mode in ('silence','rescue'):
        a.session.engine.intervene(edges=edges,action='silence')
        if mode=='rescue':a.session.engine.intervene(edges=edges,action='unsilence')
    after=a.session.engine.capture_state().to_dict()
    changed=[k for k in before if before[k]!=after[k]]
    if set(changed)-{'silenced_edges','sequence'}:raise ValueError('unexpected intervention change: '+str(changed))
    base_metrics=a.session.engine.metrics()
    a.session.world.present(task['shape'],task['color'],offset=task['offset']);a.session.world.marker=None
    frames=list(a.session.sensor.frames(task['text']))
    if len(frames)>20:raise ValueError('question cannot fit original window')
    rows=[]
    for i in range(20):
        row=a.session.tick(frames[i] if i<len(frames) else None,guard=lambda:guard(work))
        row['teacher_utterance']=task['text'];rows.append(row)
    x=np.stack([a.words.layout.frame(rows[i]['activity']) for i in np.rint(np.linspace(0,19,8)).astype(int)])
    result=answer(a.words,x,task['label'])
    with np.load(source/'arms'/arm/'final/trials'/f"{q['index']:04d}.npz",allow_pickle=False) as data:reference=data['x']
    original=json.loads(gzip.decompress((source/'arms'/arm/'final/clips'/f"{q['index']:06d}.json.gz").read_bytes()))['process']
    same_input=io_hash(rows)==io_hash(original)
    same_features=bool(np.array_equal(x,reference))
    if not same_input:raise ValueError('diagnostic input differs from original')
    if mode in ('normal','rescue') and (not same_features or result['selected']!=q['original'][arm]):
        raise ValueError('normal/rescue did not reproduce original activity and answer')
    if model_hash(a.words)!=model_before:raise ValueError('reader changed during causal probe')
    end=a.session.engine.capture_state().to_dict();end_metrics=a.session.engine.metrics()
    remaining={(e['source'],e['target']) for e in end['edges']};old=set(edges)
    silent={tuple(e) for e in end['silenced_edges']}
    activity=x.reshape(8,-1,4)
    result.update(arm=arm,question=task,condition=mode,branch=KEY+':'+arm+':'+task['question_id']+':'+mode,
        source_identity=a.identity,source=str(source/'arms'/arm/'fit-3/system'),
        same_input=same_input,same_features_as_original=same_features,changed_fields=changed,
        source_edges=len(edges),end_edges=len(remaining),new_edges=len(remaining-old),
        end_silenced=len(silent),old_edges_remaining_unsilenced=len((remaining&old)-silent),
        input_sha256=io_hash(rows),source_time_us=before['time_us'],end_time_us=a.session.engine.time_us,
        activity_sum_by_field=dict(zip(('activation','inhibition','direct','associative'),activity.sum(axis=(0,1)).astype(float).tolist())),
        activity_max_difference=float(np.abs(x-reference).max()),reader_sha256=model_before,
        source_pending_events=len(before['queue']),
        source_event_kinds=sorted(set(str(event.get('kind')) for event in before['queue'])),
        transport_delta={k:float(end_metrics['transport'][k])-float(base_metrics['transport'][k]) for k in ('sent','received','activated','discarded')},
        terminal_state_sha256=hashlib.sha256(encoded(end)).hexdigest(),wall_seconds=time.monotonic()-start)
    write(folder/'process.json.gz',gzip.compress(encoded(dict(task=task,mode=mode,process=rows)),compresslevel=1,mtime=0))
    import io
    buffer=io.BytesIO();np.savez_compressed(buffer,x=x)
    write(folder/'features.npz',buffer.getvalue())
    write(folder/'terminal-observation.json',dict(metrics=end_metrics,world=a.session.world.state(),
        meaning='terminal summary, not a resumable complete-system checkpoint'))
    write(result_path,result)
    print(json.dumps(dict(arm=arm,question=task['question_id'],mode=mode,answer=result['word'],correct=result['correct'],
        same_features=same_features,new_edges=result['new_edges'],seconds=result['wall_seconds']),ensure_ascii=False),flush=True)
    del a,before,after,end,rows,original;gc.collect()
    return result


def run(source,work):
    protect_host();plan=read(work/'plan.json')
    if read(work/'registered.json')['plan_sha256']!=sha(work/'plan.json'):raise ValueError('registered plan differs')
    verify_sources(source,work,plan)
    start=time.monotonic();summaries={}
    with ResearchStorage().writer(RESOURCE):
        for arm in plan['arms']:
            reader_probes(source,work,arm,plan)
            results=[]
            for q in plan['questions']:
                for mode in plan['conditions']:results.append(probe(source,work,arm,q,mode))
            summaries[arm]={mode:dict(n=len(plan['questions']),correct=sum(r['correct'] for r in results if r['condition']==mode)) for mode in plan['conditions']}
        verify_sources(source,work,plan)
        write(work/'complete.json',dict(summary=summaries,sources_unchanged=True,plan_sha256=sha(work/'plan.json'),wall_seconds=time.monotonic()-start))
    print(json.dumps(summaries),flush=True)


def publish(source,work):
    complete=read(work/'complete.json');plan=read(work/'plan.json');verify_sources(source,work,plan)
    c,rec,rid=recording(source,work)
    try:
        rec.append('result',KEY+':result',complete,request_id=rid('result'))
        for path in sorted(work.rglob('*')):
            if path.is_file() and not path.is_relative_to(rec.control) and not path.name.endswith('.partial'):
                attach(rec,rid,work,path,'result' if path.name in ('result.json','complete.json') else 'process')
        for lang in ('zh','en'):
            rec.text(dict(request_id=rid('report:'+lang),identity=rid('report-text:'+lang),kind='report',expected_revision=0,
                title='E67 典型题因果诊断 / typical-case causal diagnosis · '+lang,markdown=(HERE/f'report.{lang}.md').read_text(encoding='utf-8')))
        rec.synchronize(strict=True)
        print(json.dumps(dict(synced=True,experiment=rec.experiment,summary=complete['summary'])),flush=True)
    finally:c.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('register','run','publish'))
    args=parser.parse_args();load_env()
    storage=ResearchStorage();source=storage.workspace_path('2026-10-11-shape-color-kernels');work=storage.workspace_path(HERE.name)
    {'register':register,'run':run,'publish':publish}[args.command](source,work)


if __name__=='__main__':main()
