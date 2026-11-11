# E23 execution corrections / 执行更正

2026-10-01. The frozen design, Core and criteria are unchanged.

1. Registration initially failed because notebook Markdown links require the local `/docs` route. Resumed the same project and original registration time after converting links; no simulations had run. The failed registration receipt is preserved.
2. The first minimal-observation probe incorrectly invoked `begin_observation`, which correctly rejects requests when activity V2 is disabled. One training state and one failed probe are preserved under `replication/`. The runner now calls that method only with enabled readers. The entire registered matrix restarts under `replication-v2/`; this is a research runner revision, **not a kernel version**. Two extra saved cases count toward budgets. No inputs, dynamics, thresholds or analysis criteria changed; the failed probe is excluded from scientific comparisons and included in failure accounting.

登记最初被笔记模块的相对链接校验拒绝；转换为已有文档路由后复用同一项目继续。随后首个最小观测探测错误调用了已关闭的活动分析，接口按约定拒绝。保留原训练与失败记录，修正调用条件，以新目录完整重跑登记矩阵；这不是内核改版，也不是根据动力学结果调整判据。

3. The load phase was mistakenly dispatched before the replication process had fully exited. It briefly overlapped the final random-background block (100124), contrary to the single-worker rule. Neither process used live telemetry and all compared Core hashes agreed, but this does not erase the protocol deviation. Preserve both batches; repeat the last 20 replication cases and all 32 load cases serially, comparing full hashes. Add an OS file lock preventing a second simulation worker for this study. The additional 52 cases remain inside the 512 safety cap; total expected saved cases becomes 478 including the two earlier setup cases. No outcome-dependent parameter change is made.

调度时误把尚在运行的最后一个随机背景区组与负载检查短暂重叠，违反单 worker 登记。两边均未启用实时遥测、哈希检查一致，但仍保留并承认偏差；串行复演最后 20 个矩阵案例和全部 32 个负载案例核对，并加入操作系统文件锁阻止重复派工。原数据不删，不以静默重跑掩盖经过。

4. An analysis assertion initially compared raw JSON SHA256 with the platform's canonical full-state digest. The latter deliberately preserves floating-point bit patterns and normalized field order. Corrected the verifier to use the existing `StateImage.digest`, retaining separate raw-file hashes for commitments and archives. No state bytes or simulation were changed or repeated for this analysis fix.

分析校验初次把 JSON 文件哈希与平台的规范化状态哈希混比较；改用既有 `StateImage.digest` 核对状态，封存与归档仍核对原始字节哈希。没有修改证据或重新模拟。

5. Delivery review found that the initial live driver measured total process CPU and included readout in the runtime meter. Production defines that meter as advancement/thread CPU and observes afterward. This is a study-driver measurement error, not a Core fault. Retain the 12 live + 12 replay pilot cases under `live/`; their exact replay result is valid for those actual inputs, but their runtime scope is not a production-equivalent measurement. Before final reporting, repeat all 24 under `live-kernel-meter/` with the production measurement boundary and thread CPU. Host/process probes remain the existing implementations; report their genuine physical load and distinguish runtime kernel time from readout cost. This brings the total to 502, within 512. The earlier analysis/figure is retained as preliminary, not used as the final live comparison. A and C do not consume physical telemetry and are unaffected.

交付复核发现，首批实时研究驱动把全进程 CPU、读出耗时也计入了实例内核计量，与生产边界不同。保留该批及其精确输入重放，作为计量范围不正确的试运行；按生产定义改为推进期间的线程 CPU、读出另计，再完整复验 24 例。最终实时比较使用新批，原图表标为初稿留存。背景矩阵与延后选择均无物理遥测输入，不受此误差影响。累计 502 例，仍在登记硬限以内。
