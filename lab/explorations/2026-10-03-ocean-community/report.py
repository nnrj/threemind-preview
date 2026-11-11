"""Render bilingual reports from the completed, fixed E32 analysis."""
from experiment import HERE,WORK
from lab.tools.ocean_cli import read_json


def build():
    d=read_json(WORK/'findings.json');cases=d['cases']
    if len(cases)!=18 or any(c['status']!='horizon_paused' for c in cases.values()):
        raise ValueError('all 18 registered cases must be complete before final reporting')
    worlds=[]
    for g in (0,1):
        for mode in ('core','random'):
            c=cases[f'g{g}-{mode}']
            worlds.append(f'| {g+1} | {mode} | {c["food"]} | {int(c["captures"])} | {c["births"]} | {c["alive"]} | {c["living_body_s"]:.2f} | {c["food_per_body_s"]:.5f} |')
    world_table='\n'.join(worlds)
    labels={'core':'原意识 / intact','target':'目标静默 / target','matched':'匹配静默 / matched',
        'focal-random':'单体随机 / focal random','experienced':'保留经历 / experienced',
        'blank':'空白 / blank','graft':'目标移植 / target graft','graft-matched':'匹配移植 / matched graft'}
    focal=[]
    for op,label in labels.items():
        values=[]
        for g in (0,1):
            v=cases[f'g{g}-{op}']['focal_outcome']
            values.extend([str(v['food']),str(v['captures']),'是 / yes' if v['alive'] else '否 / no'])
        focal.append('| '+label+' | '+' | '.join(values)+' |')
    focal_table='\n'.join(focal)
    minutes=sum(c['wall_seconds'] for c in cases.values())/60
    usage=read_json(WORK/'usage.json')['used_percent']
    zh=f'''# E32 完整海洋：内部活动的作用，终于放回原环境检验

[English](report.en.md) · [事前设计](design.zh.md) · [指标定义](analysis-registration.md) · [执行记录](execution-notes.md)

2026-10-03登记。本报告依据18个完成的世界/分叉；独立来源是两个世界种子，不能把18个分支称为18个独立种群。

## 先回答本轮真正的问题

**意识驱动与随机驱动有清楚差别，而且本轮两个完整世界都存在摄食优势。**意识组摄入213对197、270对180，分别多8.1%和50.0%；按累计活体时间计算，摄食率分别高27.5%和59.5%。这次保留了其他个体、营养、随机刷新与全部感官环境，E31删减环境的问题已经纠正。

**至少一个完整环境中的摄食收益，确实有局部内部联想活动的贡献。**0号的目标通路被静默后，近期未受直接提示的活动消失，随后动作与轨迹改变，60秒内摄入由3颗降至2颗；静默同等数量、权重/稳定度相近的其他连接，仍为3颗。不是仅凭食量猜测原因：活动、动作、路径与具体营养摄入事件都有记录。

**经历形成的结构能携带动作模式，但“移过去就更会觅食”没有得到普遍支持。**第二个来源2号的目标连接移植，使动作与经历者的差距比空白减少约68%，优于匹配移植；这次捕获和死亡结果却不变。第一个来源中，目标及匹配移植都更像经历者，但摄入都是2颗，空白为3颗。模式转移、作用和收益必须分别回答。

## 完整海洋里的群体结果

1.2米见方海域，53初始个体，97在世上限，360颗初始营养，每模拟秒在随机位置补一颗；每个主世界120模拟秒。有限能量、运动耗能、外壳、变异、持续接触捕获、繁殖、水流、温度、碰撞及本体感官全部保留。没有实时宿主遥测，也没有融合或共享。

| 世界 | 驱动 | 营养摄入 | 捕获个体 | 出生 | 末存活 | 累计活体秒 | 营养/活体秒 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
{world_table}

![完整海洋的摄食、存活与捕获过程](figures/ecology.png)

意识组动作更连续，在有局部营养梯度的采样中更倾向朝浓度较高方向输出。单位方向与梯度的平均对齐值：世界1为0.140对0.013，世界2为0.136对−0.001。平均平移命令幅度也更小：0.433对0.765、0.494对0.763。**这支持它并非与当前随机控制器毫无区别地碰运气，但整体优势仍包含即时感官、身体接线、输出幅度/连续性及网络经历的共同影响。**正常意识的输出没有为对照而限速或限幅；随机基线是原有每秒独立随机指令，不代表所有可能的随机策略。

末存活数量少4个和1个，不能直接解释成意识组生存能力较差：它们同时捕获了更多个体。用户据此批准E33禁止相互吞食的配对补试，单独区分这一环境因素；该补试不改写本报告的数值或本轮规则。

## 0号：内部活动改变了真实的一次摄食机会

在主世界第57–60秒，只按既定活动规则选择目标；第60秒复制**整个海洋**，只改0号意识。它有3个目标节点、75条目标入边；匹配对照同为75条，平均权重/稳定度匹配误差0.00534。

对两边均在此前1秒没有直接通道输入的目标活动，第61–70秒的共同可测积分为：原意识0.79335，目标静默0，匹配静默0.79019。后者保留约99.6%。动作在静默后0.2秒的采样中出现差异，目标静默的60秒平均动作差0.01083，匹配静默0.00485。0.2秒是100毫秒采样下首次观察到的差异，不能当作精确连续时间延迟。

具体经历如下：原意识先在63.835秒取得营养404、78.890秒取得225、108.015秒取得50。目标静默后仍取得404，但改为78.785秒取得269，之后没有取得第三颗。匹配静默仍取得404、225和50，第三次在108.910秒发生。因果差异体现在同一环境中走了不同路线、遇到了不同营养，并非人为把一团食物放到目标前方。

这支持“这部分内部活动对该次觅食有正面作用”。它还没有给出群体额外16/90颗营养中有多少百分比归于内部联想；只有两个预选焦点，也没有把当前所有有益行为定位完。

![0号动作及摄食过程](figures/focal-g0.png)

## 2号：动作模式可转移，遭遇还受繁殖与身体规则左右

第二世界依相同顺序规则选中2号，静默目标和匹配通路各128条，平均匹配误差0.03329。共同无直接提示时的活动积分由原来的0.25188变为目标静默0；匹配为0.25085。共同存活的约2.9秒内，目标静默动作差0.01032，匹配0.00158。内部通路作用再次出现。

原2号在61.16秒捕获17号，随后摄入两颗营养，62.00秒繁殖出60号；60号在62.88秒捕获自己的亲代。当前Ocean/3只阻止亲代吞食未成熟子代，没有阻止反向吞食。该来源各神经对照的终点相同，因此不能把这些结果写成已经证明某条区域决定了主动追猎或逃命。实际身体在62.88秒被捕获，原意识活动在65.62秒才依原生命规则终止；二者不能混为同一时刻。

出生式对照只重置即时神经状态，保持身体年龄、位置、当前有限储备与整个环境。目标连接移植的动作与经历者平均差0.00316，空白0.00981，匹配移植0.01333（共同存活约2.9秒）。**约68%的差距缩小由指定目标连接实现，说明这部分持久结构能搬动具体动作模式。**原规则下该遭遇结局没有改善。

用户随后明确批准：后续实验在子代成熟前采用亲子双向保护。本轮已经登记的对照继续原规则；下一期的环境修订不能混入当前样本。禁止吞食的E33则不触发任一方向的吞食。

![2号动作及摄食过程](figures/focal-g1.png)

## 所有焦点结果，不挑只好看的分支

每项都是原世界60–120秒。原样与静默保持即时状态；经历/空白/移植四项统一重置即时状态，只在这四项内部比较持久经历，不能把出生重置本身误算成记忆效果。空白副本仍可继续学习，并非关闭学习的石头。

| 条件 | 0号摄食 | 0号捕获 | 0号存活 | 2号摄食 | 2号捕获 | 2号存活 |
| --- | ---: | ---: | --- | ---: | ---: | --- |
{focal_table}

局部未提示活动的判定是“该通道此前1秒无直接输入且活动存在”，不等于整个世界停止了输入。目标静默及匹配静默才提供它参与动作的因果证据。匹配覆盖数量、权重和稳定度，没有声称不同区域的拓扑完全等价。实际刺激、动作、完整状态和事件均保留，便于进一步核对。

**单个体随机替换也有明确的有利结果，不能略去。**0号改为随机驱动后摄食4颗（原为3颗），运动耗能82.81（原为26.09，约3.2倍）；2号随机替换后仍存活、摄食5颗，原意识在该遭遇中被捕获且只摄入2颗。总体意识组胜出与这两个焦点随机替换胜出可以同时成立：它们回答的范围不同。当前不能声称每个意识个体都有净收益，或已有经历总是优于其他动作序列。E33还将检验捕食压力拿掉后群体差异如何变化。

## 影片、工具和资源

本轮导出8段MP4：意识/随机全程、摄食、接触捕获、脱离，以及0号同一时段的原样/目标/匹配三联对照。全景保留全部生态，附加近景不替代全景。视频依据实际100毫秒状态记录，10fps；全程片按2倍速，其他片1倍速，不生成额外实验帧或样本。三联片各13秒，可同步播放。脱离影片只证明发生脱离，本轮尚未把其收益定位到指定内部区域。

本地影片目录：`.work/ocean-community-20261003/media/final/`，`gallery.html`可直接打开；完整海洋还可在4个HTML回放中逐时查看。平台独立项目`0b662685-7484-4c20-b1cb-064b53a582e4`保存设计、双语报告及影片记录。

提炼了完整海洋分叉、只改单个意识、出生副本时钟/储备对齐、单个体随机控制的保存恢复与过程记录工具。原Core公式、参数、传播时钟及感官映射均未改。10项相关工具/物理测试通过；全景影片编码、1440/390像素播放/暂停/定位验收通过。纠正了视频中跨周期边界形状画成横线的渲染错误，不改模拟轨迹。

本轮18个完成条件合计{minutes:.2f}模拟进程分钟；登记账户17%，报告生成时{usage}%（共享账户变化一起计入）。保持单模拟worker；证据存储及入库收据另见交付记录。没有清理旧数据、重复运行旧种群或反复全量校验。一次研究调度名称冲突让两个单体随机条件被跳过，已用独立名称补全；原数据没有被覆盖，见执行记录。

## 值得继续的明确问题

本轮最重要的新证据是：**完整复杂环境中，内部活动不仅改变数值，还改变了具体摄食后果；选定连接也能转移动作模式。**未完成的是有益技能的稳定移植、主动追猎/逃命的指定内部机制，以及群体优势的分量归因。E33按用户建议先拆分捕食对种群结果的影响。之后可围绕自然遇食/遇敌前的短窗选择更多焦点，保留整个环境做区域静默、恢复及移植；不再退回孤立小装置替代生态验证。三维及更长演化另行决定。

本轮补足E31的环境缺口，不倒改既定`autonomy-criteria/1`通过结论，也不以新的食量判据重新定义“意识”。
'''
    en=f'''# E32: internal activity tested inside the complete ocean

[中文](report.zh.md) · [Registration](design.en.md) · [Measures](analysis-registration.md) · [Execution](execution-notes.md)

Registered2026-10-03. All18 conditions completed; the independent sources are **two world seeds**, not18 independent populations.

## Main answers

**Core control has a clear feeding advantage over this random baseline in both intact worlds:**213 versus197 and270 versus180 nutrients (+8.1%,+50.0%). Intake per living-body second is27.5% and59.5% higher. Other organisms,food,random replenishment and environmental senses remain throughout,correcting E31's habitat-removal limitation.

**One concrete feeding benefit depends on a selected internal pathway.** Silencing individual0's target pathways removes recently uncued activity,changes subsequent commands/trajectory,and reduces60s intake from3 to2. Silencing75 matched other edges leaves intake at3. Activity,commands and exact nutrient events connect the manipulation to the outcome.

**Persistent structure can transfer an action pattern; transferred foraging benefit is not general.** In source2,target grafting reduces action distance to the experienced birth by about68% compared with blank and outperforms a matched graft,without changing capture/death outcomes. For individual0,both grafts resemble the experienced actions more closely but consume2 nutrients versus3 for blank. Pattern transfer and ecological benefit are distinct observed questions.

## World results

Each world starts with53 bodies and360 nutrients in a1.2m square,allows97 live bodies,and replenishes one nutrient per simulated second at a random position. Observe120s with finite energy,motor costs,mutation,shells,contact capture,reproduction,water,temperature,collision and proprioceptive feedback. No live host telemetry,fusion or sharing.

| World | Control | Nutrients | Captures | Births | Final alive | Living-body seconds | Nutrients/body-second |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
{world_table}

![Complete habitat trajectories](figures/ecology.png)

Core commands are smoother and more aligned with locally measured nutrient gradients: mean angular alignment0.140 versus0.013 in world1 and0.136 versus−0.001 in world2. Mean planar command magnitude is lower:0.433/0.765 and0.494/0.763. Thus its behavior is observably different from this random controller; total advantage still combines immediate sensing,wiring,command scale/continuity and experience. Core cadence/amplitude are unrestricted. The random baseline uses independent commands each second; it does not stand for every possible random strategy.

Final population is smaller by4 and1 while captures are higher. The user approved E33 to disable mutual predation and separate this environmental contribution. E32 numbers and rules remain intact.

## Individual0: a local pathway changes a real feeding opportunity

Selection uses only57–60s activity and fixed identity order. At60s,the **whole ocean** is copied and only the focal engine changes. Three target nodes have75 selected incoming edges;75 matched edges have mean weight/stability matching error0.00534.

For target nodes not directly stimulated in either arm during the preceding1s,the common61–70s activity integral is0.79335 intact,0 under target silence,and0.79019 matched (99.6% retained). First action difference appears at the0.2s sample,with60s command MAE0.01083 target versus0.00485 matched. This is the first observed100ms sample,not exact continuous latency.

Intact0 ingests nutrient404 at63.835s,225 at78.890s,and50 at108.015s. Target silence retains404,but instead reaches269 at78.785s and no third particle. Matched silence retains404/225/50,the third at108.910s. Different routes encounter different existing particles; no target was placed in front of the focal body. This establishes a positive contribution in this encounter,not a full percentage decomposition of the population's16/90 extra nutrients.

![Individual0 process](figures/focal-g0.png)

## Individual2: transferable commands and an offspring encounter

The second source has128 target/matched edges,mean matching error0.03329. Common uncued activity is0.25188 intact,0 target,and0.25085 matched. During approximately2.9s of common physical survival,command MAE is0.01032 target versus0.00158 matched. The internal contribution repeats.

Intact2 captures17 at61.16s,eats two particles,gives birth to60 at62.00s,and is captured by its own newborn at62.88s. Ocean/3 protects immature children from parents but not the reverse. This lineage chain belongs in the explanation; the neural variants retain the same focal endpoints. Physical capture at62.88s and Core activity death at65.62s are separate events. These contrasts do not locate a target region that decides successful pursuit or escape.

Paired births reset immediate neural activity while retaining physical age,position,current finite reserve and the whole habitat. Target graft MAE to the experienced birth is0.00316,blank0.00981,matched graft0.01333 during common survival. The approximately68% reduction supports **specific persistent-structure transfer of a command pattern**,without a better encounter outcome. The user approved bilateral parent–child protection until maturity in future studies; E32 keeps its registered rule. E33 disables all predation,so protection direction is immaterial there.

![Individual2 process](figures/focal-g1.png)

## All focal outcomes

Results cover60–120s. Intact/silenced arms retain immediate state. Experienced/blank/graft births reset it identically and should be compared within that set. Blank births continue normal learning. Both scopes retain every other body and all food.

| Condition | 0 food | 0 captures | 0 alive | 2 food | 2 captures | 2 alive |
| --- | ---: | ---: | --- | ---: | ---: | --- |
{focal_table}

“Uncued” means no direct input on that node's channel during the preceding1s,not that the world is silent. Matched local manipulations supply causal evidence. Matching covers count,weight and stability,not identical topology. Complete inputs,commands,states and events remain available.

**Focal random replacements also have favorable outcomes.** Individual0 consumes4 rather than3 nutrients,but motor expenditure rises to82.81 from26.09 (about3.2×). Randomly controlled2 survives and consumes5,where intact2 is captured after consuming2. Population-level Core advantage and these favorable focal random replacements coexist; they answer different questions. Neither universal individual benefit nor universally superior learned experience is established. E33 tests how population differences change without predation pressure.

## Footage,tools and limits

Eight actual-record MP4s cover Core/random full worlds,feeding,capture,release,and the same-time intact/target/matched feeding comparison. The whole habitat remains visible; focal zoom is additional.100ms state samples are displayed at10fps,full overviews at2× and excerpts at1×. The synchronized comparison clips each last13s. Release footage establishes a physical release,not a localized internal cause of escape.

Open`.work/ocean-community-20261003/media/final/gallery.html`locally; four HTML world replays are also retained. Local Lab project`0b662685-7484-4c20-b1cb-064b53a582e4`contains designs,bilingual reports and video records. Whole-evidence archives stay local.

Reusable tools preserve whole-world forks,focal-only interventions,birth-clock/current-reserve alignment,focal-random restoration and process recording. No Core dynamics,defaults,propagation clocks or sensory mappings changed. Ten relevant apparatus/contact tests passed,as did video encoding and1440/390px playback,pause and seek checks. A renderer-only periodic-seam line artifact was corrected without changing recorded trajectories.

The18 completed cases used{minutes:.2f}simulation process-minutes. Account usage was17% at registration and{usage}% at report generation,including shared use. One simulation worker; storage/publication receipts are separate. A naming collision initially skipped two focal-random cases; distinct names completed both without overwriting prior evidence. No old-data deletion or repetitive full audits.

## What this advances

The new result is **internal activity changing a concrete feeding outcome in an intact complex habitat**,plus transferable action patterns in selected persistent connections. Stable transfer of useful skills,localized pursuit/escape mechanisms and complete population attribution remain open. E33 first separates predation effects. Subsequent natural pre-encounter interventions should retain the whole habitat;3D and longer evolution remain separate decisions. E32 does not revise the prior`autonomy-criteria/1`pass or redefine consciousness through a new intake threshold.
'''
    for lang,body in (('zh',zh),('en',en)):(HERE/f'report.{lang}.md').write_text(body,encoding='utf-8')


if __name__=='__main__':build()
