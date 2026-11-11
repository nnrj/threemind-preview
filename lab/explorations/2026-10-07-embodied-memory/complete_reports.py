"""Fill the remaining report fields from completed evidence, once."""
import json
from pathlib import Path
import shutil
import time
import psutil

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
WORK=ROOT/'.work/embodied-memory-20261007'


def main():
    result=json.loads((HERE/'results.json').read_bytes());cases=result['cases']
    a=cases['A-fit-activity'];b=cases['A-fit-incoming'];taught=cases['A-teach']
    physical=result['physical_pointing']
    usage=json.loads((WORK/'usage.json').read_bytes())['used_percent']
    measured={'recorded_at_epoch':time.time(),'account_start_percent':76,'account_end_percent':usage,
        'completed_compute_minutes':result['compute_minutes'],
        'compute_including_failed_minutes':result['compute_including_failed_minutes'],
        'created_or_restored':result['created'],'local_evidence_before_archive_bytes':result['local_bytes'],
        'free_memory_gib':psutil.virtual_memory().available/2**30,
        'free_disk_gib':{d:shutil.disk_usage(d+':/').free/2**30 for d in ('C','E')},
        'effective_compute_cap_minutes':140,'original_compute_cap_minutes':120,
        'account_scope':'Shared account change, not exclusively attributable to E58. Final archive and database growth are in delivery.json.'}
    with (WORK/'resource-summary.json').open('x',encoding='utf-8') as f:json.dump(measured,f,indent=2)
    for lang in ('zh','en'):
        zh=lang=='zh'
        headline=(
            '**本轮最明确的发现：相同末段体验之后，过去经历仍能通过内部连接影响回答。** 第一组环境重校准后24/32，静默连接降到16/32，恢复后逐题回到24/32；第二组未复现这一增益。外设少量纠正能学会新对应，但会损失部分旧例。完整视野的实际成绩及全部错误见下表，不能把外设自己的识别算成Core独立完成。'
            if zh else
            '**The clearest finding is that prior experience can still affect answers through internal connections after identical recent experience.** In the first environment, recalibration gives 24/32, connection silence reduces this to 16/32, and rescue restores every original choice and the 24/32 score. The second environment does not reproduce the gain. Small-dose external correction learns new mappings with some loss of old examples. Whole-scene results, including errors, are reported below with a direct-input control.')
        table=(['| 读取的信息 | 颜色：最近／到达 | 形状：最近／到达 | 组合：最近／到达 | 合计：最近／到达 |','|---|---:|---:|---:|---:|'] if zh else
               ['| Reader information | Color: nearest / arrived | Shape: nearest / arrived | Combination: nearest / arrived | Total: nearest / arrived |','|---|---:|---:|---:|---:|'])
        for kind,name,score in [('activity','Core活动' if zh else 'Core activity',a),('incoming','直接感官' if zh else 'Direct input',b)]:
            cells=[]
            for category in ('color','shape','pair'):
                p=physical[kind][category];cells.append(f'{p["nearest_object_correct"]}/{p["n"]} · {p["arrived_within_0_20m"]}/{p["n"]}')
            table.append('| '+name+' | '+' | '.join(cells)+f' | {score["correct"]}/24 · {score["arrived"]}/24 |')
        table='\n'.join(table)
        table+= ('\n\n“最近”是最终指针离正确对象最近；“到达”要求距目标不超过0.20米。两者均依据实际执行终点。训练目标为物体中心的指定像素；Core活动和直接感官头的训练精确像素命中分别为'
                 if zh else '\n\n“Nearest” means the correct object is closest to the final pointer. “Arrived” requires a distance at most 0.20 m. Both use the actual endpoint. Training labels specify a centre pixel; exact training-pixel hits for the activity and direct-input readers are ')
        table+=f'{a["train_exact_pixels"]}/48、{b["train_exact_pixels"]}/48。' if zh else f'{a["train_exact_pixels"]}/48 and {b["train_exact_pixels"]}/48, respectively.'
        table+= (f' 教学结束时为{taught["nodes"]:,}节点、{taught["edges"]:,}条边，共{taught["sim_seconds"]:g}模拟秒。'
                 if zh else f' Teaching ends at {taught["sim_seconds"]:g} simulated seconds with {taught["nodes"]:,} nodes and {taught["edges"]:,} edges.')
        table+= (' 全部24题及终点坐标保存在两组predictions.json中；不能把“最近正确”当成精准动作控制，也不能仅由新装置成绩给旧四视场结果定性。'
                 if zh else ' All 24 questions and endpoints are retained in each predictions.json. Nearest-object correctness is not precise motor control; the new apparatus does not retrospectively redefine the old four-field result.')
        resources=(f'共完成{result["completed_stages"]}个阶段，新建/恢复{result["created"]}次；计入已记录失败的科研计算{result["compute_including_failed_minutes"]:.2f}分钟。最初120分钟上限在A评分前有日期地补充为140分钟，仅完成原题量；其他边界不变。归档前本地证据{result["local_bytes"]/2**30:.3f} GiB。共享账户显示从76%到{usage}%，不能全部归因于本项目。收尾时可用内存{measured["free_memory_gib"]:.2f} GiB，C/E盘余量{measured["free_disk_gib"]["C"]:.2f}/{measured["free_disk_gib"]["E"]:.2f} GiB。最终归档和数据库增量另记delivery.json。'
            if zh else f'Completed {result["completed_stages"]} stages and {result["created"]} Core creations/restores; recorded compute including failed attempts totals {result["compute_including_failed_minutes"]:.2f} minutes. Before any A pointing score, a dated amendment increased the 120-minute compute cap to 140 minutes solely to finish the fixed workload; all other limits remain. Local evidence before archiving is {result["local_bytes"]/2**30:.3f} GiB. Shared account usage changed from 76% to {usage}%, not wholly attributable to E58. At closing, available RAM is {measured["free_memory_gib"]:.2f} GiB and free C/E storage is {measured["free_disk_gib"]["C"]:.2f}/{measured["free_disk_gib"]["E"]:.2f} GiB. Final archive/database growth is separately recorded in delivery.json.')
        path=HERE/f'report.{lang}.md';body=path.read_text(encoding='utf-8')
        for key,value in [('HEADLINE',headline),('EYE_TABLE',table),('RESOURCES',resources)]:
            marker=f'<!-- FINAL_{key} -->'
            if body.count(marker)!=1:raise ValueError('report already filled or missing '+marker)
            body=body.replace(marker,value)
        path.write_text(body,encoding='utf-8')
    print(json.dumps(measured))


if __name__=='__main__':main()
