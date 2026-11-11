"""Bounded offline view of the actual E45 post-teaching trajectories and words."""
import gzip
import json

from experiment import HERE, WORK, read_json


def main():
    sources=[]
    for path in sorted((WORK/'continuous').glob('*.jsonl.gz')):
        name=path.name.removesuffix('.jsonl.gz')
        definition=read_json(WORK/'cases'/name/'definition.json')
        rows=[]
        with gzip.open(path,'rt',encoding='utf-8') as stream:
            for line in stream:
                r=json.loads(line)
                rows.append({'s':int(r['start_us'])/1e6,'e':int(r['end_us'])/1e6,
                    'words':{k:v['text'] for k,v in r['text'].items()},
                    'activity':{k:v['activity_l1'] for k,v in r['observed'].items()},
                    'patterns':{k:{'prediction':v['prediction'],'scores':v['scores']} for k,v in r['observed'].items()},
                    'transport':r['transport']})
        sources.append({'name':name,'seed':definition['seed'],'stage':definition['stage'],
                        'condition':definition['condition'],'parameter':definition['parameter'],'rows':rows})
    payload=json.dumps({'sources':sources,'results':read_json(HERE/'continuous-results.json')},ensure_ascii=False,separators=(',',':'))
    payload=payload.replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    target=WORK/'language-calibration.html'
    if target.exists():raise RuntimeError('viewer already generated; preserve published revisions')
    target.write_text((HERE/'viewer-template.html').read_text(encoding='utf-8').replace('__DATA__',payload),encoding='utf-8')
    print(json.dumps({'viewer':str(target),'sources':len(sources),'bytes':target.stat().st_size}))


if __name__=='__main__':main()
