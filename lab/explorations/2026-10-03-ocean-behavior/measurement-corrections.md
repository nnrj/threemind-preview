# E31 接触时刻的观察器校正 / Contact-time observation correction

2026-10-03，分析阶段、最终报告之前。原模拟及输入/事件/状态不变，不重跑模拟，也不覆盖 `result.json`。

局部场景观察器的食物 `gap` 使用了等面积圆的半径，但 Ocean/3 躯体是胶囊形。原 `first_contact_s` 还按每20 ms观察的 `gap <= contact_skin_m` 记录近接，不能当作精确摄入时刻；两次采样之间发生的摄入可能直接使食物消失。因此正式接触时刻改从原始物理事件读取：食物以指定目标颗粒的 `nutrient_contact` 为准，捕获接触以指定邻体对的 `capture_started` 为准。内核和海洋原本就正确记录了这些事件，问题只在外围观测量的命名及几何近似。

派生分析同时保留 `sampled_contact_s` 和 `physical_contact_s`，重新计算物理接触前的速度平均。其余固定时间窗、原始实际摄食/捕获/生存、动作和运动向量不变。没有通过这一校正挑选正面结果。胶囊形状和接触本身没有被修改。`natural.py`的几何观察使用真实胶囊间隔，仍区分近接采样与实际摄食/捕获事件；每个事件的原始时间可独立核对。

English: During analysis, before the final report, the isolated food observer was found to use the equivalent-circle radius for its gap, whereas Ocean/3 uses capsules. Its20 ms sampled `first_contact_s` also measured the contact-skin threshold rather than exact ingestion; a particle can disappear between samples. Final contact times therefore use already recorded physical events: target-particle `nutrient_contact`, or the specified pair's `capture_started`. The simulation and original records were correct and are not changed or rerun. Derived analysis retains both sampled and physical contact times and recomputes pre-contact velocity means. Fixed time windows, actual food/capture/survival outcomes and action vectors remain unchanged. This is a measurement correction, not a change to Core, body mechanics, experimental criteria or success-oriented tuning.
# 2026-10-03：输入历史完整性 / Complete recent-input history

最终过程分析排除每次记录开头1秒的“未受近期直接刺激”活动判定，因为此前的输入历史没有全部记录在该局部文件中。保留这些帧作普通动作、位置和活动观察；不能据它们证明过去1秒没有直接输入。发现窗口选区已使用同样的等待边界。此修正只影响派生的活动归因统计，不改任何输入、原始状态、动作或结果。此前中途汇报的32组活动统计是未完成批次的临时数字，以最终完整历史分析为准。

The final process analysis excludes the first second from claims about activity without recent direct input: the preceding input history is incomplete in each fork recording. Those frames remain valid for ordinary activity, action and position observation. Discovery selection already excluded this initial interval. Only derived attribution statistics change; original input, state, action and outcomes remain intact. Earlier interim counts from32 completed comparisons are superseded by the final complete-history analysis.

