"""Append E58 delivery findings and synchronize current R35/R36 status."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent


def append(path,body):
    path=ROOT/path;s=path.read_text(encoding='utf-8')
    if body.strip() not in s:path.write_text(s.rstrip()+'\n\n'+body.strip()+'\n',encoding='utf-8')


def main():
    result=json.loads((HERE/'results.json').read_bytes());cases=result['cases']
    a=cases.get('A-fit-activity');b=cases.get('A-fit-incoming')
    azh=(f'完整视野留出题中，最终位置最接近正确对象：Core活动{a["correct"]}/24、直接感官{b["correct"]}/24；实际到达目标0.20米内分别为{a["arrived"]}/24、{b["arrived"]}/24。' if a and b else
         '完整视野未完成全部留出指认，具体中止与边界见报告。')
    aen=(f'Whole-scene held-out trials: the correct object was nearest the final pointer in {a["correct"]}/24 Core-activity and {b["correct"]}/24 direct-input trials; actual arrival within 0.20 m was {a["arrived"]}/24 and {b["arrived"]}/24, respectively.' if a and b else
         'Whole-scene held-out pointing was not fully completed; see the report for the recorded limit.')
    if a and b:
        azh+=f'颜色分别为{a["categories"]["color"]}/8、{b["categories"]["color"]}/8，形状为{a["categories"]["shape"]}/8、{b["categories"]["shape"]}/8；新装置形状瓶颈不能只归给Core，也尚未定位为注意力问题。'
        aen+=f' Color scores are {a["categories"]["color"]}/8 and {b["categories"]["color"]}/8; shape scores are {a["categories"]["shape"]}/8 and {b["categories"]["shape"]}/8. The new apparatus has a shape bottleneck that cannot be assigned solely to Core or yet identified as an attention failure.'
    for lang in ('zh','en'):
        zh=lang=='zh'
        title='相同末段后的记忆：连接的作用与读取不稳定' if zh else 'Memory after identical recent experience: the role of connections and unstable decoding'
        text=('E58把“感官短时痕迹也是记忆”的讨论变为内容与因果检验。第一环境来源相同末段＋6秒后，旧头16/32，重校准24/32；既有边静默16、恢复24且逐题恢复；关结构学习副本重校准16。教师受体激活交换不改答，连接/快状态交换22，未整体随供体。第二环境来源校准32/32、留出14/32；6秒头跨0/6/30秒为15/24/16，故局部因果增益成立而稳定读取仍未完成。新对应外设纠正由0到14/16，但旧例25到20/32；绕核新题也可16/16，不能把外设学习全部归给Core。完整身体和自我视觉反馈均改变活动，本体引发联想；这不是主观动作归属证据。'+azh+
              '新增单眼、实体自身、导轨触觉、共享视网膜读头与CLI，不改Core或旧数据。用户提出中央清晰/周边粗略与注意力，登记R36，当前批不换输入。原输入门关闭而连续局部竞争已开，不能混为一谈。'
              if zh else 'E58 treats short sensory traces as memory and tests their content and causal role. After identical recent experience and a six-second wait, environment seed 223 scores 16/32 with the old reader and 24/32 after recalibration. Silencing existing connections gives 16/32; restoring communication recovers all original choices and the 24/32 score. Recalibrating the learning-off control gives 16/32. Teacher-activation transfer has no effect; edge/fast-state transfer gives 22/32 without systematic following of donor answers. Environment seed 279 fits 32/32 but tests at 14/32. The six-second reader scores 15/32, 24/32 and 16/32 after waits of 0, 6 and 30 seconds. A causal contribution is established in the first environment; robust decoding remains open. Correction improves the new mapping from 0/16 to 14/16, while old examples fall from 25/32 to 20/32. The direct-input bypass also learns new answers at 16/16. Body and self-vision feedback change activity, without establishing subjective agency. '+aen+
              ' New tools add a whole eye, visible self, guide touch, shared retinal reader and CLI without Core/old-data changes. The user proposes sharp-centre/coarse-periphery optics and attention as R36; this batch retains its inputs. Disabled legacy input gating and enabled continuous local competition remain distinct.')
        link=f'[E58 report](../../../lab/explorations/2026-10-07-embodied-memory/report.{lang}.md)'
        for section in ('chronicles/08-embodied-communication.md','themes/03-memory.md'):
            local=f'[E58 report](../../../../lab/explorations/2026-10-07-embodied-memory/report.{lang}.md)'
            append(f'docs/{lang}/history/{section}',f'## 2026-10-07：{title}\n\n{text}\n\n{local}')
        append(f'docs/{lang}/history/milestones.md',f'2026-10-07 — E58: {title}。{link}')
        append(f'docs/{lang}/history/sources/source-register.md',
            f'2026-10-07 — [E58 measured evidence](../../../../lab/explorations/2026-10-07-embodied-memory/report.{lang}.md): separate discussion, trials, tool failures and interpretation.')
        append(f'docs/{lang}/plans/embodied-memory-content.md',
            ('## 2026-10-07交付\n\n' if zh else '## Delivery, 2026-10-07\n\n')+text+'\n\n'+link)
        path=ROOT/f'docs/{lang}/plans/embodied-memory-content.md';s=path.read_text(encoding='utf-8')
        s=s.replace('状态：用户已批准，实施与实验登记中。','状态：本批已交付；结果与未完成范围见文末及报告。')
        s=s.replace('Status: approved, implementation and registration in progress.','Status: batch delivered; findings and remaining scope are recorded below and in the report.')
        path.write_text(s,encoding='utf-8')
        path=ROOT/f'docs/{lang}/plans/research-backlog.md';s=path.read_text(encoding='utf-8')
        top=('**2026-10-07：E58本批已交付。一组实验中，连接静默与恢复使答对数24→16→24；另一组及跨时间读取未稳定复现。外设少量纠正有效，但不能独归Core。R36视野/扫视/注意力留下一轮。**' if zh else
             '**2026-10-07: E58 delivered. The first environment shows a 24→16→24 correct-answer change under connection silence and rescue; the second environment and cross-time decoding remain unstable. External correction helps, with contributions from both Core and the reader. R36 optics, gaze and attention remain a separate next-round discussion.**')
        first,rest=s.split('\n',1)
        if top not in s:
            prior=next((line for line in rest.splitlines() if line.startswith('**2026-10-07') and
                        ('E58已批准并登记' in line or 'E58 approved and registered' in line)),None)
            if prior:s=s.replace(prior,top+' [E58](embodied-memory-content.md)',1)
            else:s=first+'\n\n'+top+' [E58](embodied-memory-content.md)\n'+rest
        lines=s.splitlines()
        for i,line in enumerate(lines):
            if line.startswith('| R35 /'):
                cells=line.split('|');cells[1]=' R35 / P1 E58本批交付，稳定表达未完成 ' if zh else ' R35 / P1 E58 delivered; robust expression open '
                cells[3]=(' 同末段后首源24→16→24；第二来源14/32，跨时间读法不稳；外设纠正0→14/16，旧例25→20/32。'+azh+' ' if zh else
                          ' After identical recent experience: first environment 24→16→24 under connection silence/rescue; second 14/32, with unstable cross-time decoding. Correction improves new examples from 0/16 to 14/16; old examples decline from 25/32 to 20/32. '+aen+' ')
                cells[4]=(' 已有整体眼、自身可见、反馈对照与少量外设纠正；具体概念所在、稳定读取、无意图不动作、闭环自主控制仍需定位。R36分开研究采样与注意，旧待办保留。 ' if zh else
                          ' Whole-eye/self visibility, feedback controls and small-dose correction delivered. Concept location, robust readout, abstention and autonomous closed-loop control remain open. R36 separates sampling/attention; earlier open items retained. ')
                lines[i]='|'.join(cells)
        path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        append(f'docs/{lang}/plans/research-backlog.md',f'## 2026-10-07 · E58 delivery\n\n{text}\n\n{link}')
    append('docs/zh/history/classical/shiji-04.md',
           '## 同末而异忆\n\n乃同二者末段之所历。其一更读器得二十四，塞旧边得十六，复通还二十四，逐答皆复；禁其学者仍十六。然他源未同，读器随时而失准。新名旧器不答，小授器以新例，则十六中十四，旧例亦有损。故忆有其据，译未恒准，不可归尽于一器。又使目见全境与己体，验其受感；边繁，创者议中央明、周边略，留后试之。[实录](../../../../lab/explorations/2026-10-07-embodied-memory/report.zh.md)')
    append('docs/zh/history/classical/tongjian-04.md',
           '### 2026-10-07 · E58交付\n\n同末段而试旧忆，首源更器二十四，塞边十六，复之二十四。教师激活移而答未改，移诸边亦未尽随供体。别源及异时读之未稳。授器新例，新答进而旧答损；旁路亦能学，故不独归功于核。单目与己形具，受感之因已验；扫视与注意另议。[报告](../../../../lab/explorations/2026-10-07-embodied-memory/report.zh.md)')


if __name__=='__main__':main()
