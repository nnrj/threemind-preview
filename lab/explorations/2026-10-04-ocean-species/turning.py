"""Archive observed turning/feeding candidates, retaining full-world source states."""
import json
from collections import defaultdict
from pathlib import Path

from experiment import ROOT, HERE, WORK
from lab.tools.ocean_cli import read_json, write_json
from lab.tools.ocean_turning import screen
from lab.tools.ocean_species import save_candidate
from threemind_lab.config import Settings
from threemind_lab.database import Database, LOCAL_USER
from threemind_lab.species_library import put


def main():
    project=read_json(WORK/'platform.json')['project_id']
    db=Database(Settings.from_env().database_url)
    receipts=[]
    try:
        roots=[('E37',ROOT/'.work/ocean-enclosure-20261004'),('E38',WORK)]
        for study,base in roots:
            for case in sorted((base/'cases').glob('*')):
                if not (case/'result.json').exists():continue
                cache=WORK/('turning-e37-'+case.name+'.json' if study=='E37' else 'turning-'+case.name+'.json')
                if not cache.exists():write_json(cache,screen(case))
                s=read_json(cache);grouped=defaultdict(list)
                for event in s['passing_events']:grouped[event['individual']].append(event)
                states=[]
                for folder in [case/'final',*sorted((case/'checkpoints').glob('*'))]:
                    if not (folder/'manifest.json').exists():continue
                    context=read_json(folder/'manifest.json')['context']
                    if context['schema']=='threemind.ocean-enclosure-state/2':context=context['enclosure']
                    w=context['group']['community']['world']
                    states.append((w['time_us'],folder,{b['id']:b for b in w['bodies']}))
                for i,events in sorted(grouped.items()):
                    # Preserve a living post-observation state, never label a
                    # later dead state as the original successful organism.
                    suitable=sorted((t,f,b) for t,f,b in states if t>=events[-1]['time_us'] and i in b and b[i]['physical'])
                    if not suitable:
                        receipts.append({'study':study,'case':case.name,'individual':i,'saved':False,
                                         'reason':'no living post-observation checkpoint','events':events})
                        continue
                    t,folder,bodies=suitable[0];b=bodies[i]
                    out=WORK/'turning-species'/f'{study}-{case.name}-{i}-{t}.tmspecies'
                    receipt=out.with_suffix('.receipt.json')
                    if receipt.exists():receipts.append(read_json(receipt));continue
                    name=f'{study} #{i} 转弯摄食候选 · {case.name}'
                    evidence=[{'summary':f'{len(events)}次转弯后摄入营养；观察筛查，尚未证明稳定觅食习惯。',
                               'kind':'motor-turn-and-feeding/1','criteria':s['criteria'],'events':events,
                               'recording':str(case),'snapshot_time_us':t,
                               'scope':'posthoc candidate, no matched sensory or neural ablation yet'}]
                    if b['captured']:
                        evidence.append({'summary':f'同一个体截至保存时累计{b["captured"]}次包裹吞食。',
                                         'kind':'lifetime-enclosure-count','captures':b['captured']})
                    if not out.exists():
                        save_candidate(folder,i,out,name=name,evidence=evidence,
                            description='完整海洋中的转弯摄食候选；保留观察后最近的存活快照，非事件瞬间。')
                    row=put(db,project,LOCAL_USER,out.read_bytes())
                    item={'study':study,'case':case.name,'individual':i,'saved':True,'library_id':str(row['id']),
                          'snapshot_time_us':t,'snapshot':str(folder),'bundle':str(out),'captures_at_save':b['captured'],
                          'events':events}
                    write_json(receipt,item);receipts.append(item)
        # A new rollup per call preserves earlier partial observation receipts.
        out=WORK/f'turning-catalog-{len(receipts):03d}.json'
        if not out.exists():write_json(out,{'schema':'threemind.turning-species-catalog/1','candidates':receipts})
        print(json.dumps({'catalog':str(out),'saved':sum(x['saved'] for x in receipts),
            'both_capabilities':[{'study':x['study'],'case':x['case'],'individual':x['individual']}
                                 for x in receipts if x['saved'] and x['captures_at_save']]}))
    finally:db.close()


if __name__=='__main__':main()
