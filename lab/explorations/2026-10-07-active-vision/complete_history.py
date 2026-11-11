"""Append E59 measured findings; preserve registrations and older evidence."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]


def append(path,text):
    p=ROOT/path;old=p.read_text(encoding='utf-8')
    if text.strip() not in old:p.write_text(old.rstrip()+'\n\n'+text.strip()+'\n',encoding='utf-8')


for language in ('zh','en'):
    zh=language=='zh'
    title='眼睛成本下降，辨识与教学仍待补全' if zh else 'Lower eye cost, recognition and teaching still incomplete'
    body=('E59完成工程与有界对照：10模拟秒，完整均匀眼1,080,548边/100.5秒，新扫描眼87,888边/11.5秒，接近旧四视场成本。旧核、默认与证据不改。中央光学可区分形状，但扫描目标仅约14%时间落在清晰中心；固定/扫描Core读取最近正确8/24、5/24，未达扩展门槛。完整60帧读取未改善新留出结果。闭环正常/静默/空动作最近正确4/12、5/12、4/12，实际到达均0；静默改变12个终点及4个选择，恢复重现原终点，内部连接影响存在而正确性收益未确立。两组各104课，教师没有被省略；复核发现轮间加等待不等于每个概念严格先密后疏，尚未针对错题补课。后续优先逐概念复习、教师示范注视与错误纠正，再验证基础辨识；变形、多指、否定仍待前置能力。工具、CUDA拟合、完整教学/对照回放已交付；生产世界编辑器及全局Core注意力未实现。'
          if zh else 'E59 engineering and bounded controls completed: after ten simulated seconds, uniform whole vision used 1,080,548 edges/100.5 seconds, the new scanning eye 87,888/11.5, approaching old four-field cost. Core, defaults and evidence remain unchanged. Central shapes are optically distinguishable, but targets spend only about 14% of scanning time in the sharp center; fixed/scanning Core readers score 8/24 and 5/24 nearest, below the expansion gate. Reading all sixty samples does not improve fresh holdout performance. Closed-loop normal/silenced/empty-command scores are 4/12, 5/12 and 4/12 with zero arrivals. Silencing changes all twelve endpoints and four choices; rescue restores endpoints. Internal influence exists without an established correctness benefit. Each group receives 104 lessons. Teachers were not omitted, but increasing round delays does not ensure expanding per-concept review, and error-specific correction is still missing. Next priorities are per-concept review, demonstrated fixation and teacher correction before deformation/plural/negative pointing. Reusable tools, CUDA fitting and complete teaching/control replay are delivered; production editor controls and global Core attention are not implemented.')
    report=f'../../../../lab/explorations/2026-10-07-active-vision/report.{language}.md'
    for tail in ('chronicles/08-embodied-communication.md','themes/03-memory.md'):
        append(f'docs/{language}/history/{tail}',f'## 2026-10-07：{title}\n\n{body}\n\n[Evidence]({report}) · [Source](../sources/2026-10-07-active-vision.md)')
    append(f'docs/{language}/history/sources/2026-10-07-active-vision.md',f'## 2026-10-07：{title}\n\n{body}\n\n[Measured report]({report})\n\n'+(
        '史料区分：最初的“先密后疏”是教学意图与轮次安排的概括；后来的逐项时间核查才确认每概念并非严格扩展间隔。保留登记与原数据，追加此更正。无充分教学、无可靠读头与无内核能力不是等价命题。18/24只决定是否扩大本批工作量，未改动此前意识活动的判定标准。'
        if zh else 'Source distinction: “dense-to-sparse” initially summarized intent and round scheduling; later item-level timing exposed non-expanding first-review intervals. Preserve registration/data and append the correction. Insufficient teaching, unreliable reading and absent Core ability are different claims. The 18/24 gate limits this batch workload; it does not redefine earlier consciousness/activity criteria.'))
    append(f'docs/{language}/history/milestones.md',f'2026-10-07 — E59: {title}。[Report](../../../lab/explorations/2026-10-07-active-vision/report.{language}.md)')
    append(f'docs/{language}/history/sources/source-register.md',f'2026-10-07 — E59 measured completion and teaching correction: [report]({report}).')
    p=ROOT/f'docs/{language}/plans/active-vision.md';text=p.read_text(encoding='utf-8')
    text=text.replace('状态：已批准，先登记后实验。','状态：工程与首批有界对照完成；辨识、纠正教学及扩展任务待续。')
    text=text.replace('Status: approved; register before testing.','Status: engineering and bounded controls completed; teaching repair, reliable recognition and extensions remain open.')
    p.write_text(text,encoding='utf-8')
    append(f'docs/{language}/plans/active-vision.md',f'## 2026-10-07 · Measured update\n\n{body}\n\n[Report](../../../lab/explorations/2026-10-07-active-vision/report.{language}.md)')
    p=ROOT/f'docs/{language}/plans/research-backlog.md';text=p.read_text(encoding='utf-8');lines=text.splitlines()
    summary=('**2026-10-07：E59有界试验交付。新眼10秒连接108万→8.8万、耗时100.5→11.5秒；辨识未改善。既有连接静默/恢复确实改变/恢复动作，但正常/静默最近正确4/12、5/12且到达均0，尚无正确性收益。教学104课/组；逐概念复习与错后纠正待补，先教会有效注视，再做变形、多指与否定。Core不改。**'
             if zh else '**2026-10-07: E59 bounded study delivered. New eye edges 1.08M→88K and elapsed 100.5→11.5 seconds; recognition has not improved. Existing-edge silence/rescue changes/restores movement, but normal/silenced nearest scores are 4/12 and 5/12 with zero arrivals. Each group received 104 lessons; repair per-concept reviews, correction and useful gaze before deformation/plural/negative tasks. Core unchanged.**')
    for i,line in enumerate(lines):
        if line.startswith('**2026-10-07：E59已批准') or line.startswith('**2026-10-07: E59 approved'):lines[i]=summary+' [E59](active-vision.md)'
        if line.startswith('| R36 /'):
            lines[i]=('| R36 / P1 E59工程与有界试验完成，辨识待续 | 视觉焦点、扫视与注意力 | 全场景新眼约少92%连接；固定/扫描最近8/24、5/24；闭环正常/静默4/12、5/12，均未到达。静默/恢复改变/恢复终点 | 优先修逐概念复习、教师示范注视/错后纠正、移动视网膜读取；变形、多指、否定等待基础能力；全局Core注意力另议 | [E59](active-vision.md) |'
                      if zh else '| R36 / P1 E59 engineering/bounded study complete; recognition open | Foveation, saccades and attention | About 92% fewer edges; fixed/scan nearest 8/24, 5/24; closed normal/silenced 4/12, 5/12, no arrivals; silence/rescue changes/restores endpoints | Repair per-concept review, demonstrated gaze/correction and moving-retina reading; deformation/plural/negation gated; global Core attention separate | [E59](active-vision.md) |')
    p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    append(f'docs/{language}/plans/research-backlog.md',f'## 2026-10-07 · E59 measured completion\n\n{body}\n\n[Report](../../../lab/explorations/2026-10-07-active-vision/report.{language}.md)')

append('docs/zh/history/classical/shiji-04.md','## 目成而视学未成\n\n五十九试，十模拟秒间，旧全目联结百八万，新转目八万八千，所费百秒减为十一秒有余。其省可纪，而识物未工。两例各受百四课，师未废也；然按轮增隔，未必各物皆先密后疏，因实录而更正之。闭环十二问，常态近者四，默联结近者五，皆未至；默则诸终点异，复则诸终点还。是内部有所与，未足称择物得益。乃留全课与误例，俟修复习、教注视与纠错，再验变形、多指；不因所欲而书所无。\n\n[实录](../../../../lab/explorations/2026-10-07-active-vision/report.zh.md)')
append('docs/zh/history/classical/tongjian-04.md','### 2026-10-07 · E59省费与教学之辨\n\n可转之目既成，中央详而周围略，同境十秒之联结减约九成二，核律无改。识色辨形仍未成，尽读六十帧亦未救之。用户问师教与检查点，核实师课俱在；检查点者，外部读器之权重也，非删意识所历。复核课时，见轮间渐疏非各物渐疏，遂记其失，未敢言教已足。禁联结则动作改，复则还，然选正无益。后试当先修教与转视，变形多指俟之。\n\n[实录](../../../../lab/explorations/2026-10-07-active-vision/report.zh.md)')
