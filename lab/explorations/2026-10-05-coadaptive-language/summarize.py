"""Read only the bounded study's receipts; keep every original utterance."""
import html
import gzip
import json
from experiment import WORK, HERE, read_json, new_json


def main():
    records = [read_json(p) for p in sorted((WORK/'cases').glob('*/result.json'))]
    sources = [r for r in records if r['kind'] == 'source']
    dialogues = []
    for source in sources:
        file = WORK/'cases'/f"s{source['seed']}-{source['arm']}-stage{source['stage']}"/'dialogue.jsonl.gz'
        with gzip.open(file, 'rt', encoding='utf-8') as stream:
            rows = [json.loads(line) for line in stream]
        source['live_correct'] = sum(r['answer']['text'] == r['target_external_only'] for r in rows)
        source['live_count'] = len(rows)
        source['uncalibrated_turns'] = sum(bool(r['answer'].get('uncalibrated')) for r in rows)
        dialogues.extend({k: source[k] for k in ('seed', 'arm', 'stage')} | {
            'turn': r['index'], 'question': r['question']['text'], 'output': r['answer']['text'],
            'teacher': r['teacher']['text'], 'self_hearing': r['self_hearing']['enabled'],
            'uncalibrated': bool(r['answer'].get('uncalibrated'))} for r in rows)
    tests = [r for r in records if r['kind'] == 'test']
    grouped = {}
    reference = {}
    for row in tests:
        if row['item'] < 0:
            continue
        key = (row['seed'], row['arm'], row['stage'], row['perspective'])
        group = grouped.setdefault(key, dict(zip(('seed', 'arm', 'stage', 'perspective'), key)) |
            {'correct': 0, 'frozen_correct': 0, 'count': 0})
        group['correct'] += row['output'] == row['target']
        group['frozen_correct'] += row['frozen_output'] == row['target']
        group['count'] += 1
        reference.setdefault((row['seed'], row['arm'], row['stage'], row['item']), []).append(row)
    consistency = []
    for key, values in reference.items():
        consistency.append(dict(zip(('seed', 'arm', 'stage', 'item'), key)) | {
            'all_agree': len({r['output'] for r in values}) == 1,
            'all_correct': all(r['output'] == r['target'] for r in values),
            'outputs': [r['output'] for r in values], 'target': values[0]['target']})
    result = {'sources': sources, 'summary': list(grouped.values()), 'consistency': consistency,
              'live_dialogues': dialogues,
              'tests': tests, 'attribution': [r for r in records if r['kind'] == 'attribution'],
              'transcription': [r for r in records if r['kind'] == 'transcription'],
              'linear_transcription': [r for r in records if r['kind'] == 'linear-transcription'],
              'aligned_calibration': [r for r in records if r['kind'] == 'aligned-calibration'],
              'aligned_tests': [r for r in records if r['kind'] == 'aligned-test'],
              'source_probe_count': sum(r.get('core_copies', 1) for r in records),
              'cases': len(records), 'aggregate_seconds': sum(r['wall_seconds'] for r in records)}
    # Generated summaries are derived, versioned publication follows later.
    (HERE/'results.json').write_text(__import__('json').dumps(result, ensure_ascii=False), encoding='utf-8')
    table = []
    for r in tests:
        cells = [r['seed'], r['arm'], r['stage'], r['item'], r['perspective'],
                 (r['prompt'] or {}).get('text', '无提示'), r['target'], r['output'], r['frozen_output']]
        table.append('<tr>' + ''.join('<td>'+html.escape(str(c))+'</td>' for c in cells) + '</tr>')
    page = '<!doctype html><html lang="zh"><meta charset="utf-8"><title>E52原始回答</title>'
    page += '<style>body{font:16px system-ui;margin:24px;color:#213d39}table{border-collapse:collapse}td,th{border:1px solid #bdceca;padding:9px;text-align:left}tr:nth-child(even){background:#f2f7f5}</style>'
    page += '<h1>E52 实际回答</h1><p>目标是外部评分依据，不是推理输入；空白/乱码照录。</p><table><tr>'
    page += ''.join('<th>'+c+'</th>' for c in ('来源','组别','教学阶段','对象','问法','问题','教学所指','持续学习表达','冻结基础表达'))+'</tr>'
    page += ''.join(table)+'</table></html>'
    extra = '<h2>仅词语转写的外设</h2><p>未用物体名称答案训练；这里保留实际输出，不以目标替换。</p><table><tr><th>来源</th><th>阶段</th><th>对象</th><th>问法</th><th>教学所指</th><th>持续转写器</th><th>冻结转写器</th></tr>'
    for source in result['transcription']:
        for row in source['rows']:
            cells = [str(source['seed'])+'/'+row.get('source_arm', 'feedback'), source['stage'], row['item'], row['perspective'], row['target'],
                     row['adaptive_output'], row['frozen_output']]
            extra += '<tr>' + ''.join('<td>'+html.escape(str(c))+'</td>' for c in cells) + '</tr>'
    extra += '</table><h2>同一快照均衡校准的诊断</h2><p>这一外设仍得到任务答案监督；不要当作纯翻译成功。</p><table><tr><th>来源</th><th>对象</th><th>问法</th><th>问题</th><th>教学所指</th><th>原表达器</th><th>诊断表达器</th></tr>'
    for row in result['aligned_tests']:
        cells = [row['seed'], row['item'], row['perspective'], row['prompt']['text'], row['target'],
                 row['original_output'], row['output']]
        extra += '<tr>'+''.join('<td>'+html.escape(str(c))+'</td>' for c in cells)+'</tr>'
    extra += '</table><h2>线性词语转写器：同资料诊断</h2><table><tr><th>来源/组别/阶段</th><th>对象</th><th>问法</th><th>教学所指</th><th>实际输出</th></tr>'
    for source in result['linear_transcription']:
        for row in source['rows']:
            cells = [f"{source['seed']}/{row['arm']}/{row['stage']}", row['item'], row['perspective'], row['target'], row['output']]
            extra += '<tr>'+''.join('<td>'+html.escape(str(c))+'</td>' for c in cells)+'</tr>'
    extra += '</table><h2>教学现场：给出示范前，它实际说了什么</h2><p>最初尚未校准的轮次为静默；此处不是用训练结束后的模型重新生成。</p><table><tr><th>来源/组别/阶段</th><th>轮次</th><th>提问</th><th>当时回答</th><th>随后教师示范</th><th>自听开关</th></tr>'
    for row in dialogues:
        cells = [f"{row['seed']}/{row['arm']}/{row['stage']}", row['turn'], row['question'],
                 row['output'] or ('尚未校准' if row['uncalibrated'] else '∅'), row['teacher'], row['self_hearing']]
        extra += '<tr>'+''.join('<td>'+html.escape(str(c))+'</td>' for c in cells)+'</tr>'
    page = page.replace('</html>', extra+'</table></html>')
    (WORK/'outputs.html').write_text(page, encoding='utf-8')
    print({'cases': len(records), 'compute_seconds': round(result['aggregate_seconds'], 1), 'summary': result['summary']})


if __name__ == '__main__':
    main()
