## Discussion addendum: energy, persistent activity and the next experiment (2026-09-29)

This is post-experiment interpretation and planning, not new experimental evidence. The original report, 598 instances, data, evidence archive and first published revision remain preserved.

### Use “energy” and explain the mechanism plainly

The researcher points out that earlier documents already use energy, while phrases such as short-term resources and restore depletion made the discussion harder to follow. We accept this correction. Prefer **energy consumption, replenishment, finite supply and unlimited supply** in ordinary discussion; define variables precisely in papers and parameter documentation. The policy is now in the [glossary](../../../docs/en/terminology.md).

The D switch controls energy consumption at connections: transmission consumes the available fraction, which subsequently recovers; disabling D replenishes that fraction before each release. Facilitation still determines utilization. This is implemented separately from the earlier whole-model energy account. A shared everyday word must not merge the controls or equations. Whole-model energy accounting was not enabled in this study.

“Restore depletion” therefore means **re-enable connection energy consumption**, not replenish the model's energy. Unlimited supply does not disable inhibition, forgetting or activation decay, and does not mean unlimited activation.

### Why persistent internal activity merits further investigation

Connections formed by training maintained activity after task input stopped, including at 300 simulated seconds. Re-enabling consumption extinguished task activity after approximately 0.65 seconds; disabling facilitation did so after 0.55 seconds; disabling only further consolidation did not. These are observable conditions for formation and maintenance, not a visualization replaying an animation.

The researcher interprets this as approaching autonomous consciousness-like activity and matching the project's predictions. The next discriminating question is: **can this activity retain experience, change with new input, switch between patterns, and influence how the model acts on its environment?** Together these would advance the study from indefinite circulation to persistent, changeable activity that affects the system's own circumstances.

One gap requires an explicit control. Earlier task input stopped, but recorded host-telemetry background continued. Saved endpoint states had no task/background cross-edges; that does not establish absence of influence at every intervening time. A new branch should stop all sensory input, drain already accepted sensory deliveries, and observe ongoing internal transmission. Externally driven and internally maintained activity must remain distinguishable.

### Sufficient supply while consumption and recovery remain

The earlier recommendation to prioritize finite supply remains historical. Discussion briefly proposed D=0 as the next unlimited-supply main condition. **The researcher then clarified that external supply is unlimited while connections still consume and recover energy and nodes retain refractoriness. That proposal is withdrawn; no new experiment used it.** Future conditions must preserve local consumption and recovery. D=0 remains only the earlier depletion-removal / instantaneous-refill control.

An inexhaustible supply of bread does not mean a person can stop eating or digest without limits. Supply rate, internal capacity and local recovery speed remain finite. Continuous self-inhibition and LIF's explicit refractory interval/adaptation current differ; neither was removed by the earlier D=0 setting, and neither is to be modified now.

Finite simulated energy is optional, not a prerequisite for a digital consciousness model. Real host computation still consumes electricity and has memory and processing limits; unlimited simulated supply does not remove experiment budgets. Supply conditions alone neither establish nor rule out consciousness.

Compare goal-consistent and goal-opposing stimulation without assuming that stronger activation means liking, or inhibition/death means dislike. Familiarity, surprise and conflict may also produce different responses. Record which nodes respond, their timing, recovery and switching, actions that change subsequent input, and dependence on training history. Task-subnetwork silence is not whole-consciousness death. Calling a death command when a stimulus opposes the goal would manufacture the proposed finding.

The [next discussion plan](../../../docs/en/plans/autonomous-activity.md) first compares second-scale and millisecond-scale input intervals independently. Results then guide persistence/switching, action feedback and opposite tendencies shaped by environmental selection. It has not been executed. It tests observable autonomous activity without treating a single score as a test of subjective experience.

### First check whether stimuli miss the relevant time window

The researcher proposes that one-second input intervals allow short-lived states to disappear before the next input, potentially explaining earlier membrane-kernel failures. Verified code uses a 20-ms LIF membrane constant, 5-ms input-current constant and 20-ms learning traces. The continuous kernel propagates every 100 ms with a 10-ms numerical step. The earlier one-second value was **external stimulus spacing**, not the kernel's entire update rate. This makes the hypothesis worth testing before further environmental experiments, but does not establish it as the sole cause of earlier failures.

Keep intensity, total input count, curriculum, energy mechanisms and internal clocks fixed; compare 1000, 100, 20, 5 and 1 ms between inputs and verify the candidate result with a held-out seed. More total activation alone is not improved learning. Measure target specificity, retained connections, pattern differentiation, inhibition and refractoriness. Denser input increases dose per second and shorter training gives forgetting less elapsed time; report both and add age/duration-and-dose comparisons if needed. Faster input is not automatically faster internal transmission, so do not change both together.

### Researcher's original Chinese wording

The following verbatim remarks preserve the researcher's interpretation and proposed direction; they are not additional measured results.

> 我理解了，耗竭后内部循环消失，这很符合预期。目前都在我的意识假设的预言范围内。刚刚我误解了恢复耗竭的含义，其实这里不就是说的是模拟能量吗，是否耗竭是说能量有限供应（会耗竭）与无限供应。我的理解没错吧。仅回复。

> 我们在描述的时候尽量用现实中有的概念，能直观理解的，即使不精确，我们可以在之后的论文中去规定能量在论文内的定义，宁可这样（而且理应这样），也不要生造新词去引发理解困难。如果你阅读了以前的docs，会发现你说得“恢复耗竭”一直被称为能量。把我们的讨论追加到报告中。并将术语贴近现实、用已有词汇、尽量不生造新词的原则整理为适当表述后写入docs的适当位置。我认为ThreeMind摸到了自主意识活动的边儿，方向是对的。现在我们来讨论，设计一个怎样的实验，来观察和证明这种活动有点像自主的、有点儿像意识活动。我们永远无法确认模型是否具有自我意识，因为主观体验无法由客观验证，但我们可以设置一些模拟实验来观察，为模型接入模拟环境和虚拟感官适配器（可以是一些刺激模拟，不必完全对应四肢和五官），经过一定时间的刺激、特定的环境（环境本身有目标和倾向）塑造后，它会形成一种模式或倾向，自然而然符合环境设定的目标、倾向。此时施加一些符合目标倾向的，观察是否有某些激烈的激活表现；然后施加一些与目标相反的，看是否有另一种不同的激活或某种抑制乃至死亡出现。上述实验可用无限能量（因为有限能量在计算机世界没有物理依据）。如果需要先指定实验plan的化，可以告诉我，我会切计划模式。

> 补充：此外帧率我认为应该加大，当前1秒不符合人脑的神经信号传播速度，人脑的神经脉冲传播是毫秒级的（这也解释了为何此前的膜电位为何无法形成稳定连接，因为刺激间隔太久）。增减帧率这一点可以先独立验证。也就是先把刺激的帧率增加到模拟毫秒级（尽量贴近生物信号传播速度），如果发现有增益，则后续对上述环境选择、正负向刺激的实验在帧率增加的基础上进行。无增益则帧率保持现状。

> 注意：无限功能不意味着连接不需要消耗能量，也不意味着节点没有不应期（也就是受到刺激后需要时间恢复才能再接受刺激，此前受到的刺激越强烈这个恢复时间越久，这个机制此前本来就有，无需修改，这里只是解释我在说什么），别把能量无限供应误解为关闭连接能量消耗和不应期。以人举例，无限供应馒头的疑似只是这个人不会因为没馒头吃而饿死，不是说他活着不需要吃馒头或者吃撑了还能无限吃。
