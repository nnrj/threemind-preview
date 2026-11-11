"""Exact words plus tolerant object/temporal components, all declared in report."""
import html
from experiment import *


def main():
    models={};tables=[]
    for path in sorted((WORK/'models').glob('s*-local.json')):
        model=read_json(path);groups={};body=[]
        for r in model['rows']:
            key=(r['learning'],r['question'],r['mode'],r['held'])
            g=groups.setdefault(key,{'learning':key[0],'question':key[1],'mode':key[2],'held':key[3],
                                    'exact':0,'object_correct':0,'time_word_correct':0,'count':0})
            g['count']+=1;g['exact']+=r['output']==r['target']
            if r['question']!='clock':
                expected=h.WORDS[r['past'] if r['question']=='past' else r['current']]
                g['object_correct']+=expected in r['output'] and not any(w in r['output'] for w in h.WORDS if w!=expected)
                g['time_word_correct']+=r['output'].startswith('刚刚' if r['question']=='past' else '现在')
            body.append('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in
                [r['learning'],r['mode'],r['past'],r['current'],r['question'],r['held'],r['target'],r['output']])+'</tr>')
        models[path.stem]={'fit_correct':model['fit_correct'],'fit_count':model['fit_count'],'metadata':model['metadata'],
                           'summary':list(groups.values()),'rows':model['rows']}
        tables.append('<h2>'+path.stem+'</h2><div><table><tr><th>学习</th><th>时钟</th><th>先</th><th>后</th><th>问</th><th>留出顺序</th><th>教学目标</th><th>原样表达</th></tr>'+''.join(body)+'</table></div>')
    cases=[read_json(p) for p in (WORK/'cases').glob('*/result.json')]
    result={'models':models,'cases':len(cases),'sim_seconds_max':max(r.get('end_seconds',0) for r in cases),
        'wall_seconds':sum(r['wall_seconds'] for r in cases)+sum(read_json(p)['wall_seconds'] for p in (WORK/'timing').glob('*.json')),
        'stopped':read_json(WORK/'stopped.json') if (WORK/'stopped.json').exists() else None,
        'usage':read_json(WORK/'usage.json'),'local_bytes':sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file()),
        'core_changes':False,'input_encoder_changes':False,'language_frame_interval_us':20000}
    new_json(HERE/'results.json',result)
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>E51 时钟与复述原话</title><style>body{font:16px/1.6 system-ui;max-width:1200px;margin:25px auto;padding:0 16px;color:#183b36;background:#f5f8f6}div{overflow:auto}table{border-collapse:collapse;background:white}th,td{padding:7px;border-bottom:1px solid #dae5df;text-align:left;white-space:nowrap}</style><h1>E51 · 时钟、现在与刚刚</h1><p>时间词与物体词分别计分。原始输出不补词，不把部分正确改写成完整复述。当前实验不是小时或昨天的检验。</p>'+''.join(tables)+'</html>'
    (WORK/'outputs.html').write_text(page,encoding='utf-8')
    print(json.dumps({k:{'fit':v['fit_correct'],'summary':v['summary']} for k,v in models.items()},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
