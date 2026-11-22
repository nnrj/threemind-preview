# R51g 四项判据复验工具

先读取总轮次的[最新交接](../../2026-11-13-kernel60-revalidation/HANDOFF.md)及本目录[协议](protocol.zh.md)。本目录已准备，是否已经登记、执行、交付必须查看实际工作区。前一批出现科学停止条件时不得启动本批。

历史测量的对应：`rig.py`取自`closure_rig.py`指定函数，使用真实6.1工厂和独立保存格式；`measurement.py`保留旧X3测量，追加教学资料上的Core匹配有效性核验。`check_port.py`用语法树逐函数核对这些差异。四种基线直接复用冻结`pilot_m3.Controller`。`analyze.py`读取轨迹独立核对积分、状态干预、闭环和重放，不装载Core。

新工作区为`E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/criteria61-v1`。以仓库根目录为当前目录，使用`.work/kernel-venv/Scripts/python.exe -X utf8`运行：

```powershell
.work/kernel-venv/Scripts/python.exe -X utf8 lab/explorations/2026-11-13-kernel61/criteria/check_port.py
.work/kernel-venv/Scripts/python.exe -X utf8 lab/explorations/2026-11-13-kernel61/criteria/study.py register --work E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/criteria61-v1
.work/kernel-venv/Scripts/python.exe -X utf8 lab/explorations/2026-11-13-kernel61/criteria/study.py apparatus --work E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/criteria61-v1
.work/kernel-venv/Scripts/python.exe -X utf8 lab/explorations/2026-11-13-kernel61/criteria/study.py run --work E:/ThreeMindData/experiments/2026-11-13-kernel60-revalidation/criteria61-v1
```

这些步骤依次执行，每个步骤先核查磁盘状态，不可整段盲跑。登记和装置只运行一次。完整运行后单独执行`analyze.py --work ...`。先解释科学结果、撰写两语报告，再调用上级`deliver_science.py`做原包与报告读回；以`publication/completion.json`为交付凭据。`summary.json`只表示计算完成。

活宿主的in-flight是正常状态；死宿主留下的标记不清理。普通资源暂停必须先核对STOP原因及当前完整边界，独立归档精确STOP、锁内再核验后才考虑恢复。不得改变本批已冻结的协议或运行源码来争取通过。
