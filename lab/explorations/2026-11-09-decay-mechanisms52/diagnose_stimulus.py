"""Read saved R46b JSON to explain connection survival and temporal fields."""
import gzip
import hashlib
import json
import math
from pathlib import Path

WORK=Path('E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/stimulus-v1')
FIELDS=('activation','inhibition','direct','associative')
def read(path):
    raw=path.read_bytes();return json.loads(gzip.decompress(raw) if path.suffix=='.gz' else raw)
def rms(xs):return math.sqrt(math.fsum(x*x for x in xs)/len(xs))
def main():
    assert read(WORK/'status.json')==dict(state='awaiting-analysis',sequences_completed=960)
    assert read(WORK/'independent-audit-v1.json')['passed']
    assert not any((WORK/n).exists() for n in ('STOP','in-flight.json','secondary-diagnostics-v1.json'))
    data=read(WORK/'analysis-v1.json');origin={(r['origin'],r['curve'],r['relaxation']):r for r in data['origins']}
    results=[]
    for row in data['rows']:
        c=row['case']
        if not c['cue'] or c['delay']!=300:continue
        folder=WORK/'subjects'/c['key'];taught=read(folder/'teaching/result.json.gz')
        saved=read(folder/'teaching/whole.json.gz');probe=read(folder/'probe/result.json.gz')
        absent_folder=folder.parent/'q0';omitted=read(absent_folder/'probe/result.json.gz')
        effects=[probe['response']['raw'][i]['out0'][f]-probe['baseline']['raw'][i]['out0'][f]
                 -(omitted['response']['raw'][i]['out0'][f]-omitted['baseline']['raw'][i]['out0'][f])
                 for i in range(20) for f in FIELDS]
        own=origin[c['origin'],c['curve'],c['relaxation']]['arms'][c['arm']]
        assert effects==own['effect']['300']
        fields={f:rms(effects[i::4]) for i,f in enumerate(FIELDS)}
        assert fields==own['late_fields_rms']
        nodes={r['id'] for r in probe['before']['nodes']}
        raw_edges={(r['source'],r['target']):r for r in saved['core']['edges']}
        taught_edges={(r['source'],r['target']):r for r in taught['taught']['edges']}
        current={(r['source'],r['target']) for r in probe['before']['edges']}
        edges=[]
        for edge in row['initial_connections']:
            key=edge['source'],edge['target'];stored=raw_edges.get(key);physical=taught_edges.get(key)
            edges.append(dict(source=key[0],target=key[1],survives=key in current,
                endpoints_present=[key[0] in nodes,key[1] in nodes],
                taught_projected_timescale=physical['half_life'] if physical else None,
                stored_last_successful_send_us=stored['last_pass_us'] if stored else None))
        novelty=[]
        if c['family']=='novelty':
            target={(r['source'],r['target']) for r in row['initial_connections']}
            pending=[r for r in taught['samples']['pending']['core']['edges'] if (r['source'],r['target']) in target]
            closed=[r for r in taught['samples']['after_window']['core']['edges'] if (r['source'],r['target']) in target]
            assert len(pending)==len(closed)==2
            enabled=c['arm']=='arrival-novelty'
            assert all((r['novelty_deadline_us'] is not None)==enabled for r in pending)
            cfg=saved['core']['config']
            for edge in closed:
                reentry=max(edge['novelty_source'],edge['novelty_target'])
                assert edge['novelty_deadline_us'] is None
                if enabled:assert reentry>0
                novelty.append(dict(window_enabled=enabled,reentry=reentry,rule_increment=cfg['local_novelty_gain']*max(0.,1-reentry/cfg['novelty_touch_reference'])))
        results.append(dict(case=c,target_edges=edges,fields_rms=fields,novelty=novelty))
    assert len(results)==240
    out=dict(scope='Prespecified read-only endpoint, timescale, novelty-window and temporal-field diagnosis; original criteria unchanged.',
             records=results,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with (WORK/'secondary-diagnostics-v1.json').open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
    print(json.dumps(dict(records=len(results),raw_field_reconstruction_exact=True)))

if __name__=='__main__':main()
