"""Summarize existing receipts only; never execute or rank/select a new model."""
import html
from common import *


def main():
    models={p.stem:read_json(p) for p in sorted((WORK/'models').glob('*.json'))}
    cases=[read_json(p) for p in (WORK/'cases').glob('*/result.json')]
    timings={p.stem:read_json(p)['wall_seconds'] for p in (WORK/'timing').glob('*.json')}
    reteaching=read_json(HERE/'reteaching-results.json')['rows'];grouped={}
    for row in reteaching:
        if row['item']<0:continue
        key=f"{row['owner']}/{row['condition']}/{row['seconds']}"
        result=grouped.setdefault(key,{'correct':0,'count':0});result['count']+=1
        result['correct']+=row['target']==row['output']
    result={'models':{name:{k:v for k,v in model.items() if k not in ('projection','rows','training_outputs')} for name,model in models.items()},
        'reteaching':grouped,'new_case_count':len(cases),'expression_models':len(models),
        'timing_seconds':timings,'case_wall_seconds':sum(c.get('wall_seconds',0) for c in cases),
        'local_bytes_before_archive':sum(p.stat().st_size for p in WORK.rglob('*') if p.is_file()),
        'usage':read_json(WORK/'usage.json'),'core_changed':False,'defaults_changed':False,
        'audited_effective_mechanisms':read_json(HERE/'effective-mechanisms.json')}
    new_json(HERE/'results.json',result)
    # Exact text is the evidence. No blanking, no no-cue subtraction or correction.
    sections=[]
    for name,model in models.items():
        rows=[]
        for row in model['rows']:
            target=row.get('target');cue=row['item']>=0
            ok=cue and row['output']==target
            cells=[row.get('seed',model['owner']),row['condition'],row['seconds'],row['item'],target if cue else '未定义 / no assumed answer',row['output'],('✓' if ok else '×') if cue else '—']
            rows.append('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in cells)+'</tr>')
        sections.append(f'<details><summary>{html.escape(name)} · 训练拟合 {model["fit_correct"]}/{model["fit_count"]}</summary><div class="scroll"><table><thead><tr><th>来源</th><th>经历</th><th>模拟秒</th><th>物体</th><th>教学所指</th><th>原始输出</th><th>相符</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div></details>')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>E49 原样表达记录</title><style>body{font:16px/1.65 system-ui;margin:24px auto;padding:0 20px;max-width:1100px;background:#f4f8f6;color:#183b36}h1{font-size:26px}details{background:white;margin:12px 0;padding:14px;border:1px solid #d0dfd8;border-radius:8px}summary{cursor:pointer;font-weight:600}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:6px 12px;text-align:left;white-space:pre-wrap;border-bottom:1px solid #e0e8e4}th{white-space:nowrap}p{max-width:850px}</style><h1>E49 · 原样表达记录</h1><p>每一行都是实际输出，包括错答和无提示时的词语。无提示没有预设正确答案；与无提示相同的回答不会被扣分。物体编号 0–3 是实验者的证据索引，不进入表达器推理。所有模型只读取匿名状态。</p><p>“训练拟合”不是留出题准确率。cycle1 在 correction/joint 模型中已经纳入教学；其他模型未教。共同校准结果不能冒称意识独立完成了推理。</p>'''+''.join(sections)+'</html>'
    (WORK/'outputs.html').write_text(page,encoding='utf-8')
    print({'cases':len(cases),'models':len(models),'case_seconds':result['case_wall_seconds'],'timings':timings,'storage_mib':result['local_bytes_before_archive']/2**20},flush=True)


if __name__=='__main__':main()
