# 2026-10-07: memory interruption / 内存中断

`s223-explore-aligned`自动因`memory reserve`停止，已计算1087.53墙钟秒。随后检查系统可用内存约0.33GiB，一个独立`7zG.exe`进程占约15.8GiB。助手未终止、暂停或改变该压缩进程。用户选择“等压缩任务完成后继续”。模拟恢复的前提是压缩已完成且原内存/存储预算允许。

该分支已完成的原始过程及停止记录保留，不当作正式独立控制成绩。最后一份完整快照仅在30模拟秒的学前结束，后续课程虽有过程记录，但没有足够状态直接接续；不以单独外设文件或重造Core伪造恢复。

工具补正：以后每十课（25模拟秒）及每轮复习保存完整系统，附精确课程游标；恢复到新的执行目录，原失败数据不覆盖。课程顺序、辅助比例、权重/优化器/缓存/随机状态和物理时间全部沿用，保存本身不让模拟时间前进。不回滚外设单独选优。最后存档之后、尚未存档的片段若重走，明确标成中断后重新执行，不能计成两次连续经历。

这次失败的18.13计算分钟继续计入总预算；先前监督时序试运行也计入。资源恢复后优先新的空白`direct`组，先完成必要基础教学/校准。中断探索组不能用来评价学前是否有效；是否另恢复探索，由主目标和剩余预算决定。

---

The aligned exploration run stopped automatically at the registered memory reserve after1087.53 wall seconds. A subsequent check found about0.33GiB available system memory and an independent7zG.exe process using15.8GiB. That process was not modified. The user requested waiting for compression to finish; simulations require both completion and the original resource guards.

Preserve the partial process and stop record. The latest complete snapshot is at30 simulated seconds, after preschool. Later recorded observations cannot reconstruct the complete evolving individual and are not unassisted behavioral results.

Future runs save a complete system plus exact curriculum cursor every ten lessons (25 simulated seconds) and every review round. Resume in a separate output directory, retaining course order, assistance, weights, optimizer, replay, RNG and physical time. Saving does not advance simulation. Any unsaved tail must be explicitly rerun, not represented as two consecutive experiences. Both stopped attempts count against the budget. After resources recover, prioritize the new blank direct-teaching/calibration condition; the interrupted exploration run cannot establish a preschool benefit or harm.
