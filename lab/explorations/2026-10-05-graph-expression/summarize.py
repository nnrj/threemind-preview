"""Aggregate saved observations. Do not refit or select a model from outcomes."""
import html
from common import *


def main():
    models={}
    for phase,base in (('initial',FIRST),('revised',WORK)):
        for path in sorted((base/'models').glob('*.json')):
            model=read_json(path)
            if 'fit_correct' in model:models[phase+'/'+path.stem]=model
    controls={p.stem:read_json(p) for p in sorted(WORK.glob('attribution-*.json'))}
    additional=read_json(WORK/'additional-tests.json') if (WORK/'additional-tests.json').exists() else {}
    all_cases=[read_json(p) for base in (FIRST,WORK) for p in (base/'cases').glob('*/result.json')]
    results={'models':{},'controls':{},'additional':additional,
        'cases':len(all_cases),'model_count':len(models),
        'wall_seconds':sum(r.get('wall_seconds',0) for r in all_cases)+sum(read_json(p)['wall_seconds'] for base in (FIRST,WORK) for p in (base/'timing').glob('*.json')),
        'account':read_json(WORK/'usage.json'),'core_changes':False,'input_mapping_changes':False,
        'new_default_core_changes':False,'local_bytes':sum(p.stat().st_size for base in (FIRST,WORK) for p in base.rglob('*') if p.is_file())}
    sections=[]
    def table(name,rows):
        body=[]
        for r in rows:
            target=r.get('target');cue=r['item']>=0
            cells=[r.get('owner',r.get('seed')),r.get('condition'),r.get('seconds','440'),r.get('intervention',r.get('perspective','visual')),
                   r['item'],target if cue else '未定义 / no assumed answer',r['output'],('✓' if r['output']==target else '×') if cue else '—']
            body.append('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in cells)+'</tr>')
        sections.append('<details><summary>'+html.escape(name)+'</summary><div class="scroll"><table><thead><tr><th>来源</th><th>经历</th><th>模拟秒</th><th>观点/干预</th><th>物体</th><th>教学所指</th><th>原话</th><th>相符</th></tr></thead><tbody>'+''.join(body)+'</tbody></table></div></details>')
    for name,m in models.items():
        r={k:v for k,v in m.items() if k not in ('rows','training_cases')}
        r['by_time']=scores(m['rows'],('seconds',));results['models'][name]=r
        table(name+f' · 训练 {m["fit_correct"]}/{m["fit_count"]}',m['rows'])
    for name,value in controls.items():
        outcomes=[]
        for intervention in sorted({r['intervention'] for r in value['rows']}):
            rows=[r for r in value['rows'] if r['intervention']==intervention and r['item']>=0]
            outcomes.append({'intervention':intervention,'own_correct':sum(r['output']==r['target'] for r in rows),
                'donor_correct':sum(r['output']==r['donor_target'] for r in rows),'count':len(rows)})
        results['controls'][name]=outcomes;table(name,value['rows'])
    for name,value in additional.get('evaluations',{}).items():table(name,value['rows'])
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>E50 原样表达与干预</title><style>body{font:16px/1.6 system-ui;margin:24px auto;padding:0 16px;max-width:1100px;background:#f4f8f6;color:#183b36}details{background:white;margin:12px 0;padding:14px;border:1px solid #d0dfd8;border-radius:8px}summary{cursor:pointer;font-weight:600}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:6px 10px;border-bottom:1px solid #e0e8e4;text-align:left}h1{font-size:26px}</style><h1>E50 · 局部过程表达与回答归属</h1><p>包括错答、失败模型和无提示原词。无提示不设语义真值，不从其他回答中扣除。训练拟合与留出检验分开；全图只是离线诊断，local 是主表达。干预只在研究副本实施。</p>'''+''.join(sections)+'</html>'
    (WORK/'outputs.html').write_text(page,encoding='utf-8')
    new_json(HERE/'results.json',results)
    print({'cases':results['cases'],'models':results['model_count'],'wall_seconds':round(results['wall_seconds']),
           'local_MiB':round(results['local_bytes']/2**20,1),'controls':results['controls']},flush=True)


if __name__=='__main__':main()
