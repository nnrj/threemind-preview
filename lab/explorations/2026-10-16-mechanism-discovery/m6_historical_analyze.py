"""Read-only primary analysis and explicit bilingual scientific conclusions."""
import math
from pathlib import Path
import pilot_m2 as m
import m6_historical_evidence as ev
import m6_historical_metrics as metrics
import m6_historical_audit as audit


def ecological_change(initial, final):
    """World totals, never offspring-as-independent-replicate statistics."""
    cumulative = ('food_consumed', 'births', 'predations', 'capture_starts', 'voice_energy')
    totals = {name: final['totals'][name] - initial['totals'][name]
              for name in cumulative if name in initial['totals'] and name in final['totals']}
    if 'communication' in initial and 'communication' in final:
        totals['voice_energy'] = final['communication']['voice_energy'] - initial['communication']['voice_energy']
    def alive(value):
        return sum(bool(body['physical']) and body['life'] != 'dead' for body in value['members'])
    def spent(value):
        keys = ('consumed_direct', 'consumed_associative', 'consumed_inhibition', 'consumed_maintenance', 'discarded_total')
        return math.fsum(body['core_energy'][key] for body in value['members'] for key in keys)
    return {'world_total_deltas': totals, 'physical_alive_initial': alive(initial),
            'physical_alive_final': alive(final), 'Core_energy_spent': spent(final) - spent(initial),
            'window_us': final['time_us'] - initial['time_us'], 'secondary_descriptive_only': True}


def analyze(work):
    work = Path(work)
    independent = audit.check(work)
    plan = m.read(work / 'selection.json')
    scores, ecology = [], []
    for index in range(2):
        selection = plan['worlds'][index]
        eligible = sorted(row['body'] for row in selection['rows'] if row['valid'])
        arms, results = {}, {}
        for case in (case for case in ev.cases() if case['world'] == index):
            folder = work / 'branches' / case['id']
            result = m.read(folder / 'result.json')
            chain = ev.verify_chain(folder, result['final']['segments'], 20_000_000, 30_000_000)
            name = f'{case["mode"]}-{case["operation"]}'
            arms[name], results[name] = chain['primary'], result
            ecology.append({'world': index, 'arm': name, **ecological_change(result['initial']['metrics'], result['final']['metrics'])})
        restoration = independent['worlds'][index]['restoration_exact']
        score = metrics.world_result(arms, eligible, restoration)
        other = independent['worlds'][index]
        if (score['verdict'], score['measurement_valid']) != (other['verdict'], other['measurement_valid']):
            raise ValueError('independent scientific classification differs')
        for key in ev.OPERATIONS:
            if not math.isclose(score['partner_action_rms'][key], other['partner_action_rms'][key], rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError('independent action arithmetic differs')
        for key in ('target', 'matched', 'restored'):
            a, b = score['attenuation'][key], other['attenuation'][key]
            if (a is None) != (b is None) or a is not None and not math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError('independent attenuation arithmetic differs')
        scores.append(score | {'world': index, 'eligible_ids': eligible,
                               'maximum_normalized_matching_residual': selection['maximum_selected_normalized_residual']})
    result = metrics.overall(scores)
    result.update(ecology=ecology, independent_audit=independent,
                  scientific_question='Do the specified cross-sensory edges have a selective and recoverable causal contribution to partner-dependent motor differences in both historical worlds?')
    return result


def scientific_conclusion(result, lang):
    """No extra post-result hurdle; answer the registered causal question."""
    verdict = result['verdict']
    if lang == 'zh':
        return {
            'PASS': ('本批证实：事前选定的跨听觉—非听觉连接，在两个历史世界中均承担了达到预定强度、强于匹配连接且可完全恢复的伙伴声音依赖动作作用。'
                     '目标静默相较同规模、同状态匹配干预产生了更大的声音相关动作衰减，解除静默恢复同一完整状态与全部轨迹，因此支持该特定跨感官通路的因果解释。'
                     '这是对ThreeMind内部跨感官通路组织外部交互行为的有利证据，补齐了E53此前缺少的静音与连接干预交叉对照。'),
            'FAIL': ('本批否定了“所选跨感官连接子集在两个历史世界中均达到预定特异贡献强度”的预测。'
                     '测量与恢复有效，但至少一个环境的目标衰减或相对匹配选择性未达到预设值，不能将该子集认定为两环境共有的强因果承担者。'
                     '这对当前选边规则和该通路的强贡献解释是不利结果；实际方向、强度和环境差异须按表中数值保留。'),
            'MEASUREMENT_NOT_QUALIFIED': ('本批没有完成该因果命题的有效测量：至少一个世界不满足预先要求的匹配分母、声音动作基线或完整恢复条件。'
                     '明确结论是本装置条件不合格，不能据本批给跨感官通路判阳性或阴性。对ThreeMind而言，下一步先修复表中定位的测量问题，再另立新批检验原命题。')
        }[verdict]
    return {
        'PASS': ('The specified cross-auditory edge subsets make a selective, fully recoverable causal contribution of the preregistered magnitude to partner-dependent motor differences in both historical worlds. '
                 'Target masking attenuates the sound-dependent difference more than matched masking, and unmasking restores the entire state and trajectory. '
                 'This supports the proposed pathway explanation and provides favorable evidence that ThreeMind internal pathways organize external interaction; it closes the missing E53 sound-by-intervention control.'),
        'FAIL': ('The prediction that this selected cross-sensory subset reaches the preregistered selective contribution in both historical environments is rejected. '
                 'Measurement and restoration are valid, but at least one environment misses the target attenuation or selectivity criterion. '
                 'This is unfavorable to the present selection rule and strong-pathway-contribution account. The observed direction, magnitude and environmental differences remain reported.'),
        'MEASUREMENT_NOT_QUALIFIED': ('The registered causal question was not validly measured: at least one world fails the required matching denominator, sound-dependent baseline or complete restoration check. '
                 'The explicit outcome is an unqualified measurement apparatus, not a positive or negative pathway finding. The identified measurement condition must be repaired and tested in a new batch.')
    }[verdict]


def report(result, lang):
    zh = lang == 'zh'
    title = 'M6：历史交流通路的特异因果作用' if zh else 'M6: Selective causal contribution of historical communication pathways'
    purpose = ('本批检验E53两个历史共同采样海洋中，事前选定的跨听觉—非听觉连接是否特异承担他者声音引起的运动差异。预期目标静默使动作差异衰减至少25%，相较严格匹配连接的衰减多至少20个百分点，且恢复全态和十秒原始轨迹精确一致。'
               if zh else 'This batch tests whether preregistered cross-auditory edge subsets selectively contribute to partner-dependent motor differences in two historical E53 common-sample oceans. The expectation is at least 25% target attenuation, at least 20 percentage points more attenuation than matched edges, and exact whole-state and ten-second trajectory restoration.')
    scope = ('两个历史环境共享三个E38创始谱系；新增独立出生来源0。真实Core为/2。每支从完整20秒父体连续推进至30秒，主要动作窗口为首1秒，分母固定为事前合格个体的50步×3动作分量。身体、帧和子代不作为独立重复。'
             if zh else 'The two historical environments share three E38 founder lineages and add zero independent birth sources. The genuine Core is /2. Each branch develops continuously from its complete 20-second parent to 30 seconds. The primary window is the first second, with a fixed denominator of 50 steps by three action components for every preselected eligible body. Bodies, frames and offspring are not independent replicates.')
    header = '| 环境 | 合格个体 | 声音基线RMS | 目标衰减 | 匹配衰减 | 选择性 | 恢复精确 | 结论 |' if zh else '| World | Eligible bodies | Baseline RMS | Target attenuation | Matched attenuation | Selectivity | Exact restoration | Verdict |'
    def number(value):
        return 'NA' if value is None else f'{value:.6f}'
    lines = [f'# {title}', '', purpose, '', scope, '', header, '|---|---:|---:|---:|---:|---:|---|---|']
    for row in result['worlds']:
        lines.append(f'| {row["world"]} | {row["eligible_bodies"]} | {number(row["partner_action_rms"]["sham"])} | {number(row["attenuation"]["target"])} | {number(row["attenuation"]["matched"])} | {number(row["selectivity"])} | {row["restoration_exact"]} | {row["verdict"]} |')
    lines += ['', scientific_conclusion(result, lang), '',
              ('判定直接采用运行前冻结的门槛。目标与匹配边同时控制慢权重、有效权重、两端入出度及激活；其残差和个体排除清单见原件selection.json。恢复对照检查初态、1秒末态、10秒末态与所有原始输入输出，不凭动作分数相同就宣布状态恢复。主分析与独立逐项算术一致。'
               if zh else 'Verdicts use the thresholds frozen before execution. Target and matched edges control slow and effective weight, both endpoint degrees and activation; pair residuals and exclusions are in selection.json. Restoration checks initial, one-second and ten-second states and all raw input/output, not just equal scores. Primary and independent arithmetic agree.'), '',
              ('十秒生态变化另列为描述性结果，不用于改判主命题。食物摄入、Core能耗、存活、出生和捕获的分支值保存于analysis-v1.json的ecology；不将伙伴动作作用等同于已检验的有用信息传递或生态收益。'
               if zh else 'Ten-second ecological changes are separate descriptive endpoints and cannot override the primary verdict. Per-branch food intake, Core energy expenditure, survival, births and captures are in analysis-v1.json/ecology. Useful information transfer and ecological advantage are distinct planned questions, outside this causal motor endpoint.'), '',
              ('本批最终结论：' if zh else 'Final scientific conclusion: ') + scientific_conclusion(result, lang), '']
    return '\n'.join(lines)


def export(work):
    """Derived files only, with no automatic scientific-record finalization."""
    from m6_historical_driver import frozen_inputs
    work = Path(work)
    m.frozen_check(work)
    frozen_inputs(work)
    if (work / 'publication/final-verification.json').exists():
        raise RuntimeError('completed batch; do not repeat analysis')
    if m.read(work / 'status.json')['state'] != 'awaiting-analysis':
        raise RuntimeError('all sixteen branches must finish first')
    result = analyze(work)
    m.original(work / 'analysis-v1.json', result)
    m.original(work / 'audit-v1.json', result['independent_audit'])
    for lang in ('zh', 'en'):
        path = work / f'report.{lang}.md'
        body = report(result, lang).encode('utf-8')
        if path.exists():
            if path.read_bytes() != body:
                raise RuntimeError('existing report differs; append a revision instead')
        else:
            with path.open('xb') as stream:
                stream.write(body)
    return {'verdict': result['verdict'], 'independent_integrity': True, 'publication_required': True}


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    with m.worker_lock(args.work):
        print(json.dumps(export(args.work.resolve())))
