"""Append this completed study without rewriting earlier evidence or decisions."""
import json
from pathlib import Path
import study as s


def append(relative, text):
    path = s.ROOT / relative
    old = path.read_text('utf8')
    if text.splitlines()[0] not in old:
        path.write_text(old.rstrip() + '\n\n' + text.strip() + '\n', encoding='utf8')


def main():
    delivery = s.read(s.HERE / 'delivery.json')
    assert delivery['coverage'] == 'verified' and delivery['pending'] == 0
    index = {'schema': 'threemind.repeat-timing63-artifact-locations/1', 'study': s.TAG,
             'date_beijing': '2026-11-18', 'work': str(s.WORK), 'main_subjects': 24,
             'diagnostic_copies': 120, 'code_blocks': 4, 'production_core_or_defaults_changed': False,
             'archive_member': 'originals.zip', 'manifest_member': 'manifest.json',
             'analysis_member': 'analysis-v1/analysis.json', 'audit_member': 'analysis-v1/audit-details.json',
             **delivery}
    s.save(s.ROOT / 'lab/artifact-index/2026-11-18-repeat-timing63.json', index)
    texts = {
        'zh': '''## 2026-11-18：重复刺激无需更换入口也能留下时间差异

讨论稳定寻址时，作者提出：相同内容的两次出现是否需要加入内部时间才能区分，还是由变化的内部状态和共享刺激建立联系即可。作者明确授权在6.3上简单检验连续/分次呈现、不同间隔，以及激活消退后的连接保持。执行者据此登记RT63-01，采用相同内容、总量和最后200毫秒输入的三种课表；内核与默认不改。

24条主线和120次诊断完成。两档强度、四套匿名编码均区分了连续呈现、0.2秒间隔与1秒间隔。30秒后任务激活全部为零，两档均保留权重差异；强度0.2条件重新表达了这些差异，双向仅权重交换使受体与供体活动曲线的差距缩小99.9866%—99.9927%。强度0.05条件未在固定测试刺激下激活另外两个节点，保持与表达由此得到分别检验。原阴性结果保留，未调参重跑。

四套编码数值一致，支持编码重命名下的一致性，不作为随机个体总体推断。结果支持在稳定输入地址下利用内部动态和局部可塑性区分事件安排，未检验语言报数，也未授权或实施新寻址函数。完整输入、状态、假操作、数值复算及原件包已核验并由本地API完整读回。''',
        'en': '''## 18 November 2026: Temporal differences without changing input addresses

During the addressing discussion, the author asked whether repeated identical content requires time-dependent addresses or can be distinguished through changing internal state and shared input. He authorized a small 6.3 study of continuous/separated presentation, different gaps, and connection retention after activation subsides. RT63-01 registered three schedules with equal content, dose, and final 200 ms of input. The kernel and defaults remained unchanged.

All 24 main runs and 120 diagnostics completed. Both intensities and all four anonymous encodings distinguished continuous presentation from 0.2 s and 1 s gaps. At a 30 s delay, task activation was zero and both intensities retained weight differences. Intensity 0.2 re-expressed these differences; bidirectional weight-only exchange reduced the recipient–donor response-curve gap by 99.9866–99.9927%. Intensity 0.05 failed to activate the other two task nodes under the fixed cue. Retention and expression were therefore assessed separately, without tuning or replacing the negative result.

Identical values across encodings support code-renaming consistency, not population inference from randomly varying individuals. The results support temporal distinction through internal dynamics and local plasticity at stable input addresses. Verbal counting was not tested, and no new addressing function was authorized or implemented. Inputs, complete states, shams, numerical reanalysis, and the full original archive were verified, including complete local API readback.'''}
    for lang, text in texts.items():
        report_link = f'[RT63-01](../../../../lab/explorations/2026-11-18-repeat-timing63/report.{lang}.md)'
        append(f'docs/{lang}/history/chronicles/20-artificial-selection.md', text + '\n\n' + report_link)
        append(f'docs/{lang}/history/themes/03-memory.md', text + '\n\n' + report_link)
        short = text.split('\n\n')[0] + '\n\n' + text.split('\n\n')[2]
        append(f'docs/{lang}/history/milestones.md', short + '\n\n[RT63-01](chronicles/20-artificial-selection.md)')
        append(f'docs/{lang}/history/sources/source-register.md', text.split('\n\n')[0] +
               '\n\n[RT63-01](2026-11-18-repeat-timing.md)')
        path = s.ROOT / f'docs/{lang}/plans/research-backlog.md'
        old = path.read_text('utf8')
        heading = '## 2026-11-18：RT63-01完成，AS63-ADDR保持为设计讨论' if lang == 'zh' else \
                  '## 18 November 2026: RT63-01 completed; AS63-ADDR remains a design discussion'
        summary = ('RT63-TIME：三个时间问题的小规模6.3检验已完成，24条主线、120次诊断及完整原件读回通过。'
                   '连续与分次呈现、0.2秒与1秒间隔，在两档强度均产生不同即时活动；30秒后均保留权重差异。'
                   '强度0.2再次表达且权重交换确认因果作用；0.05未通过固定提示下的再表达。四套编码数值相同，'
                   '不将编码重复当成随机总体样本。\n\nAS63-ADDR（状态更新）：结果支持先保留稳定输入地址，'
                   '利用内部状态及连接变化处理事件时间关系。新寻址函数仍未实施。语言报数、更多间隔及更长保持是'
                   '尚未进行的研究问题，不因本次结项自动获得执行授权。' if lang == 'zh' else
                   'RT63-TIME: The small three-question 6.3 study is complete: 24 main subjects, 120 diagnostics, and '
                   'full evidence readback passed. Continuous/separated presentation and 0.2/1 s gaps differed '
                   'immediately at both intensities, with retained weight differences after 30 s. Intensity 0.2 '
                   're-expressed them and weight exchange established causality; intensity 0.05 did not meet '
                   're-expression under the fixed cue. Four encodings gave identical values, not stochastic '
                   'population replication.\n\nAS63-ADDR status update: Evidence supports retaining stable input '
                   'addresses while using internal state and connection changes for temporal distinctions. No new '
                   'addressing function was implemented. Counting, more gaps, and longer retention remain untested '
                   'questions, not automatically authorized follow-up experiments.')
        if heading not in old:
            first, rest = old.split('\n', 1)
            path.write_text(first + '\n\n' + heading + '\n\n' + summary +
                f'\n\n[RT63-01](../../../lab/explorations/2026-11-18-repeat-timing63/report.{lang}.md)\n' + rest,
                encoding='utf8')
    append('docs/zh/history/classical/shiji-06.md', '''## 十一月十八日：同入口而异其时

作者问，同物再至，何以别其前后，是否须以时定址。乃试六点三，剂量与末段皆同，独异其间。两强度皆异其应；三十秒后激活已息，连接之重仍异。较强者再示则应复异，独移其重，受体之应近于供体；较弱者存其异而未显于此试。遂知入口可同，经历之效不必同；存之与显之各有其验，未改核法。

[今录](../chronicles/20-artificial-selection.md)''')
    append('docs/zh/history/classical/tongjian-05.md', '''## 十一月十八日：验重复与间隔

是日，作者许以六点三小试重复之别。二十四主线、一百二十诊断皆毕。连续与中断、短间与长间，其后活动有别；待激活息，权重仍留其异。较强之习，再示可显，移重亦移其应；较弱之习，此提示未能显之，原数不易。原件尽核，记录双语，稳定寻址之议得此证，而未更内核。

[今录](../chronicles/20-artificial-selection.md)''')
    catpath = s.ROOT / 'docs/history/catalog.json'
    cat = json.loads(catpath.read_text('utf8'))
    for lang, title in (('zh', '2026-11-18：相同刺激的两次出现与时间寻址'),
                        ('en', '18 November 2026: Repeated identical input and time-dependent addressing')):
        key = 'sources/2026-11-18-repeat-timing'
        identity = lang + '-' + key
        if not any(row['id'] == identity for row in cat['chapters']):
            cat['chapters'].append({'id': identity, 'work': 'modern-' + lang, 'key': key, 'group': 'sources',
                'title': title, 'path': f'docs/{lang}/history/{key}.md', 'period': '2026-11-18',
                'tags': ['RT63-01', 'AS63-ADDR', 'temporal-input', 'memory', 'addressing']})
    catpath.write_text(json.dumps(cat, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print('RT63-01 artifact index, bilingual history, source catalog, backlog and Classical notes updated.')


if __name__ == '__main__':
    main()
