"""Combine verified R46b counts and a reviewed bilingual scientific interpretation."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
WORK=Path('E:/ThreeMindData/experiments/2026-11-09-decay-mechanisms52/stimulus-v1')
def read(path):return json.loads(path.read_text('utf-8'))
def label(row,lang):
    names={'exponential':('指数','Exponential'),'inverse-logarithmic':('逆对数','Inverse-logarithmic'),'power-law':('幂律','Power-law')}
    i=int(lang=='en');switch=('开' if row['relaxation'] else '关') if lang=='zh' else ('on' if row['relaxation'] else 'off')
    return names[row['curve']][i]+' / '+switch
def table(header,rows):
    return '\n'.join(['|'+'|'.join(header)+'|','|'+'|'.join(['---']*len(header))+'|']+['|'+'|'.join(map(str,row))+'|' for row in rows])
def counts(data,lang):
    names={'strong-gain':('强刺激专门增益','Dedicated strong gain'),'novelty-gain':('连接新颖性增益','Connection novelty gain'),
           'overall-intensity':('等驱动下整体强度','Overall intensity at equal drive')};rows=[]
    for name in names:
        for condition in data['conditions']:
            row=condition['counts'][name]
            rows.append([label(condition,lang),names[name][int(lang=='en')]]+[f'{row[f]}/8' for f in ('immediate','structure','activity')])
    return table(['设置','比较','即时增强','300秒结构收益','300秒活动收益'] if lang=='zh' else
                 ['Setting','Contrast','Immediate gain','300-s structural benefit','300-s activity benefit'],rows)
def retention(data,lang):
    rows=[]
    for c in data['conditions']:
        for arm,name in (('strong-intensity',('强刺激','Strong stimulus')),('arrival-novelty',('连接新颖性','Connection novelty'))):
            row=c['retention'][arm]
            rows.append([label(c,lang),name[int(lang=='en')]]+[f'{row[f]}/8' for f in ('structure','process','finite_fading')])
    return table(['设置','正常增益组','300秒两连接保留','300秒过程保持','30日有限淡忘预测'] if lang=='zh' else
                 ['Setting','Normal-gain arm','Both connections at 300 s','Temporal retention at 300 s','Conditional 30-day fading'],rows)
def costs(inventory,lang):
    rows=[[label(c,lang),c['sequences'],f"{c['operation_wall_seconds']/c['sequences']:.3f}",f"{c['maximum_boundary_private_bytes']/2**30:.3f}"] for c in inventory['cost_by_setting']]
    return table(['设置','序列','平均操作墙秒/序列','边界私有内存最大GiB'] if lang=='zh' else
                 ['Setting','Sequences','Mean operation seconds/sequence','Maximum boundary private GiB'],rows)
def main():
    assert read(WORK/'status.json')==dict(state='awaiting-analysis',sequences_completed=960)
    audit=read(WORK/'independent-audit-v1.json');assert audit['passed']
    data=read(WORK/'analysis-v1.json');inventory=read(WORK/'storage-inventory-v1.json');resources=read(WORK/'resource-summary.json')
    review=read(WORK/'postprocessing/scientific-interpretation.json')
    assert review['reviewer']=='assistant' and review['complete_data_reviewed'] is True
    import hashlib
    assert review['analysis_sha256']==hashlib.sha256((WORK/'analysis-v1.json').read_bytes()).hexdigest()
    resource_text='/'.join(f"{resources['minimum_available_bytes'][key]/2**30:.3f}" for key in ('commit','ram','system_disk','data_disk'))
    storage=inventory['study'];state=inventory['largest_state']
    for lang in ('zh','en'):
        if lang=='zh':
            text=f'''# R46b：强刺激与连接新颖性的增强能否成为持久保持

2026-11-10首版。全部960序列完成、独立复算通过后生成。[English](stimulus-report.en.md) · [运行前协议](stimulus_protocol.zh.md)

## 科学结论

{review['zh']['conclusion']}

## 目的、预期与设计

本批回答两个问题：专门强刺激规则和连接到达窗口的新颖性规则，是否增强新连接；这种增强能否成为300内部秒后的结构和提示活动收益。预期是两个规则在相同输入下分别带来即时增益，并检验该增益能保持到哪一步。R46a原高剂量条件未跨整体强度阈值，本批使用真正跨阈值的输入补齐这一问题。

六设置仍是独立5.2的指数、逆对数、幂律衰减，各配原线性时间尺度回落开或关。八种强刺激条件交叉实际驱动0.4、0.6、0.8、1.0与整体强度2、3；每路幅值除以整体强度，保持实际驱动。强刺激组与同输入的`intensity_gain=0`组定位专门连接增益，强刺激组与整体强度1的组比较全部强刺激效应，疲劳等共同变化单独归于后一种整体比较。

新颖性先配对线索与旧输出，再与新输出配对，交叉旧、新幅值0.4/0.8及50/75毫秒间隔。正常规则与同输入的`local_novelty_gain=0`组比较，其他配置相同。节点首次接触增益两组相同；这里的新颖性指新连接形成后、到达窗口内的已有规则。完整样本保存窗口前后状态、实际联想返回和获得的增益。

八个出生种子各对应一种实际输入条件。每种条件内，曲线、回落和增益组配对；延迟1/300秒及呈现/省略提示分别从出生连续培养，共960条序列、1920完整边界，累计{data['internal_seconds']:,.0f}内部秒。帧、连接、序列是条件内观察，不增加独立条件数。所有配置出生时确定，普通发展中没有换核、逐题回退或重训读取器。

## 测量与判定

本层使用固定输入适配器和完整时序测量工具，测局部机制。1秒窗口保存20帧激活、抑制、直接和联想活动。先计算新输出通道提示后减提示前的过程，再减去同龄同经历的省略提示过程，得到80维提示效应。完整个人Transformer联合任务保留为另层目标。

同输入的增益对照中，即时平均权重差超过1e-8即满足该条件；300秒结构收益要求两条原连接仍在，平均权重较关闭增益高至少10%且差超过1e-6；活动收益要求提示效应均方根超过1e-4，较对照高至少10%且差超过1e-6。每项至少六种条件通过，才判定该设置的相应收益成立。等驱动整体强度比较单独用同一门槛。

{counts(data,lang)}

保持目标单独要求两条原连接在300秒存在；过程均方根超过1e-4、至少保留早期十分之一且余弦相似度至少0.8。有限淡忘从教学末状态按公式推算：无新增强化及结构损伤，30内部日后权重低于0.008。这是条件性解析结果。三项各按六种条件通过判定，不合成意识或能力分数。

{retention(data,lang)}

## 结果解释与对ThreeMind的意义

{review['zh']['analysis']}

{review['zh']['meaning']}

## 成本、图和完整性

{costs(inventory,lang)}

操作墙时包含推进、完整状态捕获和原件写入，目录检查与外层开销另计。宿主累计{resources['wall_seconds']:,.2f}墙秒；每秒守卫采样的峰值私有内存{resources['peak_private_bytes']/2**30:.3f}GiB，提交/RAM/C/E最小余量{resource_text}GiB。原5/4/5/25GiB保护量保持。工程最长300秒探针为10.357墙秒；正式成本以上表及完整守卫回执为准。

三组图分别展示全部比较的通过数量、四字段完整过程及所有条件的300秒权重。过程图使用事前指定的输入条件0、回落关闭，对比三曲线和增益开/关；全数据并未因画图取舍而删减。PNG、SVG、PDF及生成源码随原件归档，路径为`figures/stimulus-gain-outcomes`、`stimulus-temporal-fields`及`stimulus-retained-weights`。

原独立审计的JSON延迟键比较错误在全批结果前发现并记录，冻结原版及失败保留；修订2仅纠正键的类型，重新核对所有原始数值、1920边界和公式，详见[审计更正](stimulus-audit-correction-v2.md)。提示组与省略组在提示前状态一致。工程两次配置身份比较失败、规范编码修订及240份原件精确复用均保存；240短序列、48操纵比较和12长测验不计科学样本。

只读进度观察器曾因读取status.json时的PermissionError退出。随后核对原科学宿主、完整边界和守卫均正常，未重启个体；该工具事件原件随包保留。资源表的边界采样与每秒守卫采样频率不同，因此各自最大值分别报告。

清点时原件{storage['files']:,}个，逻辑大小{storage['logical_bytes']/2**20:.3f}MiB，按文件身份去重的实际分配{storage['allocated_unique_bytes']/2**20:.3f}MiB。最大完整个体压缩{state['compressed_bytes']:,}字节、解压JSON {state['decoded_json_bytes']:,}字节，含{state['nodes']}节点、{state['directed_connections']}条有向连接和{state['contributions']:,}项衰减贡献。该完整个体包含Core、固定适配器映射、随机来源、全部事件和测量状态，没有另存的训练头权重。Windows清点不计目录/MFT/数据库开销。助手审阅和独立算术实现分别署明。

原件：`{WORK.as_posix()}`。科研记录`6e152699-598f-5c40-9ac5-b655b7f9e843`。最终API全文及原包读回、哈希和pending见[交付](stimulus-delivery.md)。
'''
        else:
            text=f'''# R46b: does strong-stimulus or connection-novelty enhancement become durable retention?

First edition, 10 November 2026, generated after all 960 sequences and independent verification. [中文](stimulus-report.zh.md) · [Prospective protocol](stimulus_protocol.en.md)

## Scientific conclusion

{review['en']['conclusion']}

## Purpose, expectation and design

This study asks whether the dedicated strong-stimulus rule and connection-arrival novelty rule strengthen new connections, and whether those increments become structural and cue-activity benefits after 300 internal seconds. The expectation is immediate enhancement under matched input; delayed tests determine how far that enhancement persists. R46a's higher-dose input did not cross the overall-intensity threshold; this follow-up uses input that actually crosses it.

Six genuine 5.2 settings cross exponential, inverse-logarithmic and power-law decay with original linear timescale relaxation enabled or disabled. Eight strong-stimulus profiles cross actual drive 0.4, 0.6, 0.8 and 1.0 with overall intensity 2 and 3, dividing channel amplitude by overall intensity to match drive. Strong versus identical-input `intensity_gain=0` isolates the dedicated connection gain. Strong versus overall intensity 1 measures the complete intensity effect, including fatigue and other accompanying changes.

Novelty first pairs a cue with an old output, then with a new output, crossing old/new amplitudes 0.4/0.8 with 50/75-ms intervals. Normal rules are compared with identical input and only `local_novelty_gain=0`. Node first-contact gain remains shared; novelty here denotes the existing post-formation connection-arrival-window rule. Complete samples preserve states around the window, actual associative re-entry and awarded gains.

Eight birth seeds correspond to eight actual input profiles. Curves, relaxation and gain arms are paired within profiles. Separate continuously developed subjects provide 1/300-second first tests and cue-present/omission controls: 960 sequences, 1,920 complete boundaries and {data['internal_seconds']:,.0f} aggregate internal seconds. Frames, connections and sequences are nested observations. Configurations are selected at birth; ordinary development has no Core replacement, per-question rollback or reader retraining.

## Measurement and decisions

Fixed input adapters and full temporal instruments measure local mechanisms. Each one-second window records 20 frames of activation, inhibition, direct and associative activity. Subtract the pre-cue process from the post-cue process at the new output channel, then subtract the same-age, same-history omission change, producing an 80-dimensional cue effect. The complete personal-Transformer joint task remains a separate objective.

Immediate gain requires a mean connection-weight difference above 1e-8 against the identical-input gain-zero control. At 300 seconds, structural benefit requires both original connections and at least 10% higher mean weight with an absolute difference above 1e-6. Activity benefit requires cue-effect RMS above 1e-4 and a gain of at least 10% and more than 1e-6. At least six of eight profiles must pass each endpoint. The equal-drive overall-intensity contrast uses the same thresholds separately.

{counts(data,lang)}

Retention separately requires both original connections at 300 seconds. Process retention requires RMS above 1e-4, at least one tenth of the early value and cosine similarity of at least 0.8. Finite fading projects teaching-end state without reinforcement or structural damage to weights below 0.008 after 30 internal days; this is conditional analytic evidence. Each endpoint uses a six-profile threshold and is reported separately.

{retention(data,lang)}

## Interpretation and meaning for ThreeMind

{review['en']['analysis']}

{review['en']['meaning']}

## Cost, figures and integrity

{costs(inventory,lang)}

Operation time includes advancement, complete-state capture and original writing, excluding preceding directory checks and outer control overhead. The scientific host used {resources['wall_seconds']:,.2f} wall seconds and {resources['peak_private_bytes']/2**30:.3f}GiB peak private memory sampled by the one-second guard. Minimum commit/RAM/C/E headroom was {resource_text}GiB, retaining 5/4/5/25GiB reserves. The longest engineering 300-second probe took 10.357 wall seconds; the table and guard receipt give actual formal costs.

Three figures show counts for all contrasts, complete four-field processes and all profiles' 300-second weights. The process illustration uses prospectively selected profile 0 with relaxation off, showing all three curves and gain on/zero. Every profile remains in the original data. PNG, SVG, PDF and rendering source accompany the archive under `figures/stimulus-gain-outcomes`, `stimulus-temporal-fields` and `stimulus-retained-weights`.

The original auditor's JSON delay-key mismatch was identified before full outcomes; the frozen original and its failure remain. Revision 2 corrects only the expected key type and verifies raw values, all 1,920 boundaries and direct formulas: [audit correction](stimulus-audit-correction-v2.md). Cue and omission subjects have matching pre-cue states. Two earlier engineering configuration-identity checker failures, the canonical-encoding correction and exact reuse of 240 fixtures remain preserved. The 240 short sequences, 48 manipulation comparisons and 12 long engineering probes are excluded from scientific N.

A read-only progress observer exited after a PermissionError while reading status.json. Subsequent checks confirmed that the original scientific host, complete boundaries and guard remained healthy; no subject was restarted. The tool-event record remains in the package. Boundary memory samples and one-second guard samples have different timing, so their maxima are reported separately.

At inventory, {storage['files']:,} files occupied {storage['logical_bytes']/2**20:.3f}MiB logically and {storage['allocated_unique_bytes']/2**20:.3f}MiB in allocated streams deduplicated by file identity. The largest complete subject occupied {state['compressed_bytes']:,} compressed bytes and {state['decoded_json_bytes']:,} decoded JSON bytes, with {state['nodes']} nodes, {state['directed_connections']} directed connections and {state['contributions']:,} decay contributions. Complete state includes the Core, fixed adapter mapping, random source, event history and measurement state, with no separately stored trained-head weights. Windows inventory excludes directory/MFT/database overhead. Review is attributed to the assistant and separately implemented arithmetic.

Originals: `{WORK.as_posix()}`. Research record: `6e152699-598f-5c40-9ac5-b655b7f9e843`. Full document/archive API readback, hashes and final pending status are recorded in [delivery](stimulus-delivery.md).
'''
        dest=HERE/f'stimulus-report.{lang}.md';assert not dest.exists(),'append a dated revision to an existing report'
        dest.write_text(text,encoding='utf-8')
    print(json.dumps(dict(reports=['zh','en'],sequences=960)))

if __name__=='__main__':main()
