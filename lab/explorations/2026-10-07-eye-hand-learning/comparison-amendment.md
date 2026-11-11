# E60：留出比较的共同环境 / Common-world confirmation

2026-10-07，在补课和最终留出比较之前登记。

比较“补课前/后Core×原/新外设”时，不能直接把两份完整快照各自的身体位置、眼位及天气阶段都带入比较，否则经历作用会和初始姿态、背景混在一起。最终confirmation四格、输出切断、既有边静默/恢复、入射旁路，统一采用B-teach结束时的**外部世界状态**作为每题初始条件，再按同一留出题布置四物体和教师标记。每份Core的内部时间、状态、连接、历史和读出器状态保持其原值；世界采样时钟作为明确重放的外部环境，不改Core模拟时钟。两种时钟的初始偏移及世界替换来源写入证据。之后动作导致的环境差异正常保留，不能把闭环输入强行写成相同。

原B-teach原型test均从同一快照开始，无需更改；它们不是最终留出比较。鼻子另作配对世界条件，不套用无鼻世界而抹除鼻子。不得依据confirmation成绩再挑检查点。

English: before the correction/confirmation comparisons, register a common physical start state for the four Core/reader combinations and all fixed-reader controls. Otherwise post-teaching pose and weather would confound history. Restore the external world from B-teach, then install the identical held-out scene and marker. Retain each Core's own time, connections and state. Record the replayed world/Core clock offset; subsequent action-dependent feedback remains closed-loop. Existing prototype tests need no rewriting. Nose/no-nose remain deliberately distinct paired optical conditions. Confirmation results cannot select checkpoints.

补课后还需在独立副本上取得12次新教师验证示范。最终新外设的检查点由补课前、补课后两套验证示范合并选择，防止只用早期意识状态选择外设而忽略当前状态。两套均不用于梯度训练，不含confirmation题目。仅按旧验证集拟合的版本另留；合并验证版本标记`val2`。此项在补课尚未完成、最终题尚未开启时登记。新增验证Core副本不会写回补课完成的学生。

After correction, obtain12new validation demonstrations on a separate clone. Select the final updated reader using both old and post-correction validation sets, neither used for gradient fitting and neither containing confirmation questions. This avoids calibrating solely against an obsolete Core state. Preserve the old-validation fit; mark combined-validation fits `val2`. Registered before correction completes and before final tests. The validation clone never writes back into the student.
