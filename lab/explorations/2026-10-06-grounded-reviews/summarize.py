"""Read only completed E55 stages; preserve failures and incomplete work."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent;WORK=ROOT/'.work/grounded-reviews-20261006'


def main():
    results={p.parent.name:json.loads(p.read_bytes()) for p in sorted((WORK/'cases').glob('*/result.json'))}
    incomplete=[p.parent.name for p in (WORK/'cases').glob('*/started.json') if not (p.parent/'result.json').exists()]
    summary={'schema':'threemind.grounded-classroom-results/1','project_id':json.loads((WORK/'platform.json').read_bytes())['project_id'],
             'completed_stages':len(results),'completed_compute_minutes':sum(v['wall_seconds'] for v in results.values())/60,
             'instance_creation_attempts':json.loads((WORK/'instances.json').read_bytes())['created'],
             'incomplete_or_failed':incomplete,'results':results}
    (HERE/'results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='results'},ensure_ascii=False))
    for key,value in results.items():
        if value['kind']=='expression':print(json.dumps({'case':key,**value},ensure_ascii=False))


if __name__=='__main__':main()
