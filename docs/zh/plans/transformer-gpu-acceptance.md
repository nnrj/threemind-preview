# 本机 Transformer GPU 与 CPU 回退验收

[English](../../en/plans/transformer-gpu-acceptance.md) · [本期交付](stimulus-intensity-and-spacetime.md)

2026-09-30。结论：**现有小型 Transformer 已在本机 GPU 上完成实际训练、保存和推理；GPU 不可见时能在 CPU 训练，GPU 训练出的同一模型也能直接在 CPU 推理。** 本次不涉及意识内核的 GPU 移植，也未将 Transformer 输出自动反馈给意识。

## 实际环境和结果

Windows；NVIDIA GeForce GTX 1650，约 4 GiB 显存；驱动 617.14；项目 Python 3.13；PyTorch 2.14.0+cu130、CUDA runtime 13.0。没有修改全局 Python、显卡驱动或系统环境变量。

使用现有隔离计算进程，训练两个数值序列 `[1,2,3]`、`[4,5,6]`。词表 8、宽度 16、2 个注意力头、1 层，共 3696 个参数，30 步，批量 8。每项训练限 60 秒、GPU 预算 2 GiB，保留 512 MiB 显存余量；单项顺序执行。

| 请求 | 实际训练／推理设备 | 结果 |
|---|---|---|
| CPU | CPU／CPU | 30 步完成；训练序列下一项准确率 1.0 |
| CUDA | CUDA／CUDA | 30 步完成；训练序列下一项准确率 1.0 |
| 自动 | CPU／CPU | 正常完成；没有盲目选择 GPU |
| CUDA，但子进程看不到显卡 | CPU／CPU | 原请求不变，回退后 30 步完成 |
| GPU 已训练模型，子进程看不到显卡 | 无需再训练／CPU | 模型文件哈希不变，直接加载推理成功 |

CPU 与 CUDA 的训练损失都从约 2.056 降到 0.0441。输入 `[1,2]` 后，下一项为 3 的概率约 0.95549。这里的准确率来自训练材料，是设备功能验收，不是泛化实验或 ThreeMind 意识实验。

CUDA 训练峰值分配显存约 22 MiB，进程峰值常驻内存约 1.25 GiB；前者不包含完整驱动上下文和其他程序的显存。GPU 训练模型在 CPU 与 GPU 推理的概率最大绝对差约 `1.17e-6`，符合两种浮点执行路径存在数值差异的情况，不要求逐位相同。

## 为什么自动模式用了 CPU

自动推理的三组成对小任务，CPU 约为 6.72／2.52／2.67 毫秒，GPU 约为 187.03／6.79／6.96 毫秒，含放置、传输和同步。这个任务太小，GPU 的固定开销超过计算收益。训练时的自动试测达到试测时间预算，记录为 `benchmark_budget`，因此退回 CPU；不能把这一项说成已经测得训练的速度结论。现有通用 `reason` 字段同时涵盖试测未通过，解释时应看 `benchmark.status`。

显式 CPU 与 CUDA 整个子进程耗时分别约 19.66 和 8.82 秒，但先后顺序、加载与预热不同，**不据此宣称 GPU 快两倍**。本次证明可用性；更大、适合矩阵计算的任务是否有增益，仍由自动模式实测。

## 失败记录、回退边界与修复

最初用空字符串设置 `CUDA_VISIBLE_DEVICES`，本机测试子进程仍发现显卡，所以隐藏 GPU 的断言失败；该次文件完整保留。改用仅作用于本命令及子进程的 `-1` 后，真实训练和推理均记录 `cuda_unavailable`，实际设备为 CPU。没有卸载驱动、停止用户服务或覆盖此前结果。

中途设备故障后从初始条件重新启动 CPU 子进程，由故障注入回归验证；本次没有人为破坏真实驱动。验收时发现失败尝试的步数在嵌套证据里正确、外层摘要却可能为零，已修复摘要取值并加入断言；不改训练过程。随机输入 API 对未知字段或缺失恢复位置现返回统一的 422 校验错误，避免 500；同样不改变内核输入。

最后一组 28 项回归中，27 项首次通过；新增 API 测试误写为期待 400，按项目既有 422 规范纠正后，单独重跑通过。前面的两组 54／59 项仍保持原验收记录，不将有重叠的测试数相加。

## 重现和证据

```powershell
$py = (Resolve-Path .work/kernel-venv/Scripts/python.exe).Path
& $py scripts/validate-transformer-device.py .work/new-device-validation
& $py scripts/validate-transformer-device.py .work/new-portability-validation --case gpu-hidden --predict-existing .work/new-device-validation/cuda.tmt
```

脚本拒绝覆盖输出目录和模型。完整输入、训练历史、设备报告与数值模型保留在 `.work/transformer-device-20260930`、`.work/transformer-device-fallback-20260930`、`.work/transformer-portability-20260930`，另归档到本期研究项目。初始隐藏失败与修正后的有效验收分开保存。

包含最终验收时，共享账户使用读数从实验开始的 64% 到 66%；不能将其全部归因于 ThreeMind。本期已结束新模拟，意识实验仍为 295 个新实例，旧实验没有被改写。
