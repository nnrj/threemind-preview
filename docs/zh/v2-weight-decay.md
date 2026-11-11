# 权重依赖衰减：R48研究内核

2026-11-11。[English](../en/v2-weight-decay.md) · [局部实验](../../lab/explorations/2026-11-11-weight-dependent-decay/report.zh.md) · [完整培养](../../lab/explorations/2026-11-11-weight-dependent-decay/joint/report.zh.md) · [运行时验收](../../lab/explorations/2026-11-11-weight-dependent-decay/engineering-report.zh.md)

## 规则与实现范围

本候选检验“权重越强、相对遗忘越慢”。对基础权重w，内部时间t以秒计：

\[
\frac{dw}{dt}=-w[\lambda_{\min}+\lambda_{\mathrm{extra}}(1-w)].
\]

相对衰减率为\(\lambda_{\min}+\lambda_{\mathrm{extra}}(1-w)\)，随w增大而降低。最低速率大于零，因而即使w达到1，在不再强化时也会继续衰减。实际强化仍直接增加当前权重。

设a=λmin+λextra、z=exp(−aΔt)，一次更新的精确解为：

\[
w'=\frac{awz}{a(1-w)+\lambda_{\min}w+\lambda_{\mathrm{extra}}wz}.
\]

计算只需当前权重、经过的内部时间和两个速率，不记录每次强化的贡献，不进行逐小步数值积分。该规则也不依赖连接年龄。存档保留5.3的年龄字段，用于对照和诊断；节点支持度继续使用固定的逆对数年龄曲线。节点激活、抑制、传导、突触资源、学习和事件次序沿用5.3。

这是一项独立动力学改变，以`threemind.experimental-weight-decay/1`登记。Python、Rust和独立运行程序使用同一身份及状态格式。它没有替换5.3，也没有改变全局`continuous-memory/3`或5.3幂律默认。旧个体继续按保存的真实身份恢复。

## 五个比较组

| `edge_rule` | 连接规则 | R48额外速率λextra |
| --- | --- | --- |
| `inverse-logarithmic` | 5.3的逆对数年龄曲线 | 不使用此参数 |
| `weight-fast` | 上述权重依赖规则 | 0.06/秒 |
| `weight-slow` | 上述权重依赖规则 | 0.012/秒 |
| `matched-fast` | 恒定指数速率λmin+λextra(1−0.035) | 0.06/秒 |
| `matched-slow` | 同上 | 0.012/秒 |

λmin=ln2/86400每秒。匹配指数的0.035取自运行前声明的出生权重，用于检验候选收益能否仅由整体衰减速度解释。所有组的节点支持度固定逆对数、尺度30秒；保持尺度增长和回落关闭。参数在出生时固定。

`configuration(seed, rule)`会设置表中的完整参数。直接填写配置时，应同时明确`edge_rule`与`extra_rate`；快慢名称是组别标签，不会覆盖显式参数。普通实例恢复不得换参或换规则。

## 使用现有接口

参考后端的最小工程示例：

```python
from threemind_kernels.registry import resolve_kernel
from threemind_kernels.weight_decay import KERNEL_ID, configuration

core = resolve_kernel(KERNEL_ID).create(
    configuration(908780, "weight-slow"), backend="reference"
)
```

Rust原生后端使用`backend="native"`。本机验证产物在`.work/r48-delivery/`，导入原生模块前可将该目录的绝对路径加入`sys.path`首位。没有安装新模块的旧环境会明确报缺少候选后端，不会自动换成Python。

独立程序可以新建候选，也可恢复其完整Core存档。以下仅创建零时刻工程示例；文件已存在时拒绝覆盖：

```powershell
.\.work\r48-delivery\threemind-runtime.exe `
  --kernel threemind.experimental-weight-decay/1 `
  --clock unbounded --until-us 0 --export .work\r48-example.tmind
```

默认候选配置为快档。指定慢档或对照时，以`--config`传入完整JSON配置。`--model`读取JSON或TMIND，`--store`保存运行数据库，`--resume --store`续接已有实例；创建覆盖项与恢复不能混用。实验中的完整学生还包含个人Transformer、Adam、随机状态、身体和映射，须用该实验的完整存档恢复，不能只恢复Core冒充完整学生。

Python配置目录同步列出候选参数和出生后锁定项。完整Core副本保留身份；年龄的代际继承没有在本研究定义，相关结构继承操作会明确拒绝。当前安装、运行服务和历史实验没有因本轮交付而重启或替换。

## 验收与研究结论

实际逐状态验证、性能及安装包校验见运行时验收报告。研究结论分别见R48a和R48b，不以编译成功代替实验成功。原件索引为`lab/artifact-index/2026-11-11-weight-dependent-decay.json`。
