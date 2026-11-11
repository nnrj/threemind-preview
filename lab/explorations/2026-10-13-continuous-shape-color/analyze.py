"""Read-only E68 continuity, score, cost and storage audit. No Core imports."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from threemind_lab.storage_files import atomic_json

ARMS=('2','3.1')
STAGES=['initial-teaching','initial-calibration','initial-fit','development-0']
for r in range(1,4):STAGES.extend([f'correction-{r}',f'calibration-{r}',f'fit-{r}',f'development-{r}'])
STAGES.append('final')
FIELDS=('activation','inhibition','direct','associative')
def read(p):return json.loads(p.read_bytes())
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while chunk:=f.read(1024**2):h.update(chunk)
    return h.hexdigest()
def encoded(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,allow_nan=False,default=str).encode('utf-8')
def bytes_in(p):return sum(x.stat().st_size for x in p.rglob('*') if x.is_file())


def audit_arm(work,arm,verify_all=True):
    base=work/'arms'/arm
    if (base/'in-flight.json').exists():raise ValueError('uncommitted experience remains')
    birth=read(base/'blank-birth.json');assert birth['previous_subject'] is None and not birth['engineering']
    assert all(birth[k]==0 for k in ('time_us','nodes','edges','peripheral_computed_updates','peripheral_committed_updates','recent_history'))
    chain=[read(p) for p in sorted((base/'chain').glob('*.json'))];previous=None;verified=0
    for seq,state in enumerate(chain):
        assert state['sequence']==seq and state['identity']==birth['identity']
        value={k:v for k,v in state.items() if k!='boundary_sha256'}
        assert hashlib.sha256(encoded(value)).hexdigest()==state['boundary_sha256']
        assert state['computed_updates']==state['committed_updates']
        if previous:
            assert state['parent']==previous['boundary_sha256']
            assert state['start_us']==previous['end_us'] and state['end_us']>=state['start_us']
            assert state['committed_updates']>=previous['committed_updates']
        else:assert state['key']=='birth' and state['end_us']==0
        if verify_all or seq in (0,len(chain)-1):
            for name,meta in state['files'].items():
                p=base/state['checkpoint']/name
                assert p.stat().st_size==meta['bytes'] and digest(p)==meta['sha256']
                verified+=1
        previous=state
    assert read(base/'latest.json')==chain[-1]
    stages={};last_us=0;last_seq=0;frame_count=0
    out=work/'analysis';out.mkdir(exist_ok=True)
    with (out/f'activity-{arm}.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.writer(f);writer.writerow(['time_us','stage','clip',*FIELDS])
        for stage in STAGES:
            folder=base/stage;result=read(folder/'result.json');stages[stage]=result
            assert result['start_us']==last_us and result['start_sequence']==last_seq
            if 'fit' in stage:
                assert result['end_us']==result['start_us'] and result['selection'].startswith('last state')
            else:
                for p in sorted((folder/'clips').glob('*.json.gz')):
                    with gzip.open(p,'rt',encoding='utf-8') as stream:record=json.load(stream)
                    rows=record['process'];trial=record['trial']
                    assert trial['identity']==birth['identity'] and trial['start_us']==last_us
                    for row in rows:
                        t=int(row['activity']['time_us'])
                        assert t==last_us+50000, (arm,stage,p.name,t,last_us)
                        assert abs(float(row['observation']['time_s'])-(t-50000)/1e6)<1e-6
                        totals=[sum(float(n[k]) for n in row['activity']['nodes']) for k in FIELDS]
                        writer.writerow([t,stage,p.name,*totals]);last_us=t;frame_count+=1
                    assert trial['end_us']==last_us
                assert result['end_us']==last_us
            last_seq=result['end_sequence']
    assert last_us==chain[-1]['end_us'] and last_seq==chain[-1]['sequence']
    assert chain[-1]['computed_updates']==4800
    cp=base/chain[-1]['checkpoint']
    with gzip.open(cp/'system.json.gz','rt',encoding='utf-8') as f:current=json.load(f)
    assert int(current['session']['core']['time_us'])==last_us
    assert abs(current['session']['world']['time_s']-last_us/1e6)<1e-6
    assert current['identity']==birth['identity'] and current['cursor']==last_seq
    scores={k:{key:stages[k][key] for key in ('correct','n','shape','color','pairs')}
            for k in [f'development-{r}' for r in range(4)]+['final']}
    return dict(identity=birth['identity'],birth= birth,continuous=True,rollback_count=0,
        sim_seconds=last_us/1e6,frames=frame_count,boundaries=len(chain),verified_checkpoint_members=verified,
        scores=scores,stages=stages,timing=chain[-1]['timing'],
        nodes=stages['final']['metrics']['nodes'],edges=stages['final']['metrics']['edges'],
        storage=dict(all_arm_bytes=bytes_in(base),complete_individual_bytes=bytes_in(cp),
            compressed_core_host_bytes=(cp/'system.json.gz').stat().st_size,
            peripheral_bytes=bytes_in(cp/'words'),boundary_snapshots_bytes=bytes_in(base/'boundaries')),
        final_checkpoint=cp.relative_to(work).as_posix(),last_boundary=chain[-1]['boundary_sha256'])


def report(work,data):
    a,b=data['arms']['2'],data['arms']['3.1']
    def scoreline(lang):
        lines=[]
        for key in [f'development-{r}' for r in range(4)]+['final']:
            def value(v):
                s=v['scores'][key]
                return f"{s['correct']}/{s['n']} (shape {s['shape']['correct']}/{s['shape']['n']}; color {s['color']['correct']}/{s['color']['n']}; pairs {s['pairs']['correct']}/{s['pairs']['n']})"
            lines.append(f'| {key} | {value(a)} | {value(b)} |')
        return '\n'.join(lines)
    def winner():
        sa,sb=a['scores']['final']['correct'],b['scores']['final']['correct']
        return '/2' if sa>sb else '/3.1' if sb>sa else 'tie'
    speed=b['timing']['core_ns']/a['timing']['core_ns']
    common=f"""| Stage | /2 | /3.1 |
|---|---|---|
{scoreline('en')}

| Measurement | /2 | /3.1 |
|---|---:|---:|
| Simulated seconds | {a['sim_seconds']:.2f} | {b['sim_seconds']:.2f} |
| Native Core advance seconds | {a['timing']['core_ns']/1e9:.2f} | {b['timing']['core_ns']/1e9:.2f} |
| Full-state save seconds | {a['timing']['checkpoint_save_ns']/1e9:.2f} | {b['timing']['checkpoint_save_ns']/1e9:.2f} |
| Nodes | {a['nodes']} | {b['nodes']} |
| Edges | {a['edges']} | {b['edges']} |
| Complete individual MiB | {a['storage']['complete_individual_bytes']/2**20:.2f} | {b['storage']['complete_individual_bytes']/2**20:.2f} |
| All arm originals GiB | {a['storage']['all_arm_bytes']/2**30:.3f} | {b['storage']['all_arm_bytes']/2**30:.3f} |
"""
    cn=f"""# E68 连续形色实验：待人工核对的结果草稿

两组均从本批独立完整空白个体出生，不使用E67或工程样本。普通阶段回退0次，所有教学、校准采样、题目和纠错经历均连续传递。证据检查覆盖两组全部{a['frames']+b['frames']}帧和{a['boundaries']+b['boundaries']}个完整保存边界；不是只把显示时间改成递增。

本批最终题得分较高者：**{winner()}**；/3.1原生推进耗时为/2的**{speed:.3f}倍**。这是单种子、有限形色词汇、固定眼手与个人学习表达器的完整系统比较，不能据此宣称普遍优劣或Core已单独掌握概念。E67逐题副本与本批连续考试的问题不同，旧分数不能当作同协议前后对照。

{common}

## 证据与边界

每组development-0是初教后，development-1～3是三轮纠错后，final是未用于该个体教学/校准的新位置题。组合列指两次属性提问都正确，不是同一句答案。表达器仅从原始Core活动推理；标签仅用于教师、监督校准和评分。推理冻结学习权重并不冻结Core：试题引起的正常变化全部保留。

校准保持1200步后的当前权重、Adam和RNG，不按最低损失回退；校准时内部时间暂停。两组课表使用错题并集匹配，风、温度及其他物理背景始终接入。未进行消融、移植或任何回退依赖对照，因此本批不能量化Core与表达器的独立因果贡献。

保存每一个单元完整边界是本次连续性审计开销，不是单个意识运行必需占用。完整个体列含Core/宿主/感官世界/当前与近期读出及个人外设/优化器/RNG；全组原件另含全部边界、过程和题目，视频等派生物在最终存储表补列。原生计算、观察、压缩、写入等细分见`analysis/verified-results.json`，嵌套计时不能直接相加。

完整数据：`analysis/activity-2.csv`、`activity-3.1.csv`；各组`chain/`、`blank-birth.json`、逐题/阶段原件；最终完整个体`{a['final_checkpoint']}`和`{b['final_checkpoint']}`。视频下方为四条实测活动曲线，正式交付须先完成渲染与视觉验收。
"""
    en=f"""# E68 continuous shape/color experiment: result draft awaiting review

Both complete individuals were born blank in this batch. Neither E67 nor engineering fixtures were reused. Zero ordinary rollbacks; every teaching, sampling, question and correction experience continues into the next stage. The audit checked all{a['frames']+b['frames']} frames and{a['boundaries']+b['boundaries']} complete boundaries.

Higher final score in this batch: **{winner()}**. /3.1 native advancement took **{speed:.3f} times** /2. These are single-seed, finite-vocabulary, fixed-apparatus whole-system results, not universal kernel superiority or isolated Core concept learning. E67 checkpoint-copy scores answer a different question.

{common}

development-0 precedes correction; development-1 through3 follow each corrective round; final uses held-out positions. Pair success requires both attribute questions; it is not one combined utterance. The reader sees raw Core activity only. Its supervised calibration preserves the last update, Adam and RNG. Simulation pauses during fitting; it never returns to a loss minimum. Test experiences remain in Core and world state. No rollback-dependent causal intervention was performed.

Both arms received the same union-error curriculum and physical background. Complete-individual storage includes Core, host, world, history, peripheral/optimizer/RNG; all-arm originals additionally include every audit boundary and recorded trial. Videos are reported separately after rendering. Nested timings must not be added as independent costs. Evidence: `analysis/verified-results.json`, activity CSVs, each arm's chain and blank-birth witness. The final delivery still requires video QA and reviewed reports.
"""
    for lang,body in [('zh',cn),('en',en)]:
        (work/'analysis'/f'report-draft.{lang}.md').write_text(body,encoding='utf-8')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True)
    args=p.parse_args();work=args.work.resolve()
    if not (work/'computation-complete.json').exists():raise ValueError('both formal arms must finish first')
    data=dict(study='E68',arms={a:audit_arm(work,a) for a in ARMS},protocol='continuous-v1')
    atomic_json(work/'analysis/verified-results.json',data);report(work,data)
    print(json.dumps({a:data['arms'][a]['scores'] for a in ARMS},ensure_ascii=False))


if __name__=='__main__':main()
