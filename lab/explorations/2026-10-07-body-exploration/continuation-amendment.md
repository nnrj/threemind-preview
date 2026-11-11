# 2026-10-07：完成归因与姿态对照的有界续行

在用户明确允许继续探索、放宽用量后，第二来源的52课实耗697.4秒。按已完成部分估计，原三组×两来源、母亲撤去引导、归因对照及已登记的条件性姿态测试可能接近或超过180分钟。

决定：当前进程仍按180分钟边界运行；之后新启动的收尾进程累计上限为**210分钟**，旧计算全部计入。账户阈值采用`quota-amendment.md`中的12%停止扩展、14%停止新计算。除此以外，单worker、320次创建/恢复、6/8GiB证据限制及内存/磁盘余量完全不变。

追加只用于完成当前明确的比较与`posture-amendment.md`的条件分支，不用来搜索任意参数或无限延长探索。已有案例按结果跳过；有中断的案例保留，不原位重跑。若210分钟仍不足，按案例边界停止并列出未执行项。

English: measured teaching cost makes180minutes tight for attribution and the preregistered posture branch. Under the user's explicit additional authorization, subsequently launched finalization uses210minutes total, including all prior computation. Original registrations and the current180-minute process remain intact. Other physical resource limits do not change. This extension completes specific comparisons, not an open parameter search.
