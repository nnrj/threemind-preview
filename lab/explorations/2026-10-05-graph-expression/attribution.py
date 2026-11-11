"""Isolated copied-state pathway controls; frozen local expression model."""
import argparse,copy
from common import *
from dataclasses import replace
from lab.tools.connection_controls import cross_domain_masks
from lab.tools.recorded_background import RecordedBackground
from threemind_core import StateImage
from threemind_transformer.language_session import LanguageSession
from threemind_transformer.graph_expression import load
from teaching import observe
from local_activity import local_process


def transfer(recipient,donor,selected):
    """Replace selected edge state in a COPY, aligning anonymous channels.

    No donor activity, node history, clock, energy or queued input is copied.
    Pending transmissions remain the recipient's, as declared in the record.
    """
    result=copy.deepcopy(recipient)
    rc={int(n['id']):int(n['channel']) for n in recipient['nodes']}
    target={int(n['channel']):int(n['id']) for n in recipient['nodes']}
    dc={int(n['id']):int(n['channel']) for n in donor['nodes']}
    selected={tuple(map(int,e)) for e in selected}
    pairs={(rc[a],rc[b]) for a,b in selected}
    inserted={};removed={}
    for field in ('edges','short_term','fast'):
        receiver=result['edges'] if field=='edges' else result['operator_state'][field]
        original=donor['edges'] if field=='edges' else donor['operator_state'][field]
        keep=[r for r in receiver if (int(r['source']),int(r['target'])) not in selected]
        removed[field]=len(receiver)-len(keep);added=0
        for row in original:
            a,b=dc[int(row['source'])],dc[int(row['target'])]
            if (a,b) not in pairs:continue
            clone=copy.deepcopy(row);clone['source']=target[a];clone['target']=target[b];keep.append(clone);added+=1
        keep.sort(key=lambda r:(int(r['source']),int(r['target'])))
        if field=='edges':result['edges']=keep
        else:result['operator_state'][field]=keep
        inserted[field]=added
    return result,{'selected':len(selected),'removed':removed,'inserted':inserted,
        'retained':'recipient nodes, activity, energy, clock, novelty state and pending transmissions'}


def parent(owner,condition):
    for base in (FIRST,WORK):
        p=base/'cases'/f's{owner}-multi-{condition}'
        if (p/'result.json').exists():return p
    raise FileNotFoundError((owner,condition))


def main():
    p=argparse.ArgumentParser();p.add_argument('--owner',type=int,choices=(223,279),default=223);args=p.parse_args()
    torch.set_num_threads(2);s=study();h=helpers();a=h.adapter();folder=WORK/'models'
    model,meta=load(folder/f'multi-s{args.owner}-local.safetensors','cuda' if torch.cuda.is_available() else 'cpu')
    summary=read_json(folder/f'multi-s{args.owner}-local.json')
    if summary['fit_correct']<.9375*summary['fit_count']:raise RuntimeError('local instrument calibration incomplete')
    domains=read_json(OLD/'projection.json');output=[]
    try:
        for condition in ('continued','reversal'):
            own=parent(args.owner,condition);checkpoint=own/'checkpoint-440'
            donor_parent=parent(args.owner,'reversal' if condition=='continued' else 'continued')
            donor=h.old.e45.previous.restore(donor_parent/'checkpoint-440',71).engine.capture_state().to_dict()
            original=h.old.e45.previous.restore(checkpoint,71).engine.capture_state().to_dict()
            masks=cross_domain_masks(original,domains['vision']['excluded_channels'],domains['words']['excluded_channels'])
            if masks is None:raise RuntimeError('no count-matched pathway control')
            receipt=WORK/f'masks-s{args.owner}-{condition}.json'
            if not receipt.exists():new_json(receipt,masks)
            for intervention in ('silence-target','silence-matched','rescue','transfer-target','transfer-matched'):
                for item in (-1,0,1,2,3):
                    key=f'control-s{args.owner}-{condition}-{intervention}-i{item}';path=WORK/'cases'/key
                    if (path/'result.json').exists():output.append(read_json(path/'result.json'));continue
                    if path.exists():raise RuntimeError('incomplete control preserved')
                    guard(s,True);path.mkdir(parents=True);tick=time.monotonic();s.active_case=SimpleNamespace(born_wall=tick)
                    value=h.old.e45.previous.restore(checkpoint,71);details=None
                    chosen=masks['matched' if intervention.endswith('matched') else 'target']
                    if intervention.startswith('silence') or intervention=='rescue':
                        value.engine.intervene(edges=chosen,action='silence')
                        if intervention=='rescue':value.engine.intervene(edges=chosen,action='unsilence')
                    else:
                        changed,details=transfer(original,donor,chosen)
                        value=LanguageSession(value.protocol.model_dump(),image=StateImage(json.dumps(changed).encode()),context=value.context())
                    if item>=0:
                        frames=[{'stimulus':replace(a.world.frame(a.world.sample(item,9)),intensity=.5),'labels':{}}]
                        value.reader.schedule(frames,source='E50-attribution',adapter_id='language-dose-study/1')
                    cursor=read_json(checkpoint/'summary.json')['cursor']
                    RecordedBackground(E48/'physical-telemetry.jsonl').queue_before(value.reader,cursor,value.engine.time_us+2000000)
                    observed=observe(value,value.engine.time_us+2000000,s,True);write_gzip(path/'process.json.gz',observed)
                    answer=model.decode([local_process(observed)])[0]
                    own_def=read_json(own/'definition.json');donor_def=read_json(donor_parent/'definition.json')
                    result={'kind':'attribution','owner':args.owner,'condition':condition,'intervention':intervention,'item':item,
                        'target':h.old.NAMES[own_def['assignment'].index(item)]+'。' if item>=0 else None,
                        'donor_target':h.old.NAMES[donor_def['assignment'].index(item)]+'。' if item>=0 else None,
                        'output':answer['text'],'transfer':details,'evidence':str(path/'process.json.gz'),
                        'wall_seconds':time.monotonic()-tick}
                    new_json(path/'result.json',result);output.append(result);s.active_case=None
                print({'control':condition,'intervention':intervention},flush=True)
        new_json(WORK/f'attribution-s{args.owner}.json',{'rows':output,'summary':scores(output,('condition','intervention')),
            'limitation':'matched edge counts and approximate weights, not equal topology/function; no independent motor decision measured'})
    finally:s.active_case=None;s.db.close()


if __name__=='__main__':main()
