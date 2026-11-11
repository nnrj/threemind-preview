# 独立 Runtime 与部署检查

[English](../en/v2-independent-runtime.md)

Runtime 保留有状态、持续可塑的内核，输入输出总线、适配器、时钟、模型编解码、独立 SQLite 恢复及可选只读观察。Lab 提供 Web、PostgreSQL、研究编排、笔记和报告。运行模型不需要启动 Lab，也不需要连云端。研究观察与显式干预是可选工具，不能冒充内核的自然变化。

## 安装与打包

源码开发安装顺序（使用项目选定的 Python）：

```powershell
python -m pip install -e packages/runtime
python -m pip install -e packages/transformer -e ".[dev]"
```

独立机器只安装 `threemind_runtime-2.1.0-py3-none-any.whl` 及其依赖。Runtime 的基本依赖是 NumPy、Arrow（既有模型格式）、Pydantic 和 psutil；不包含 Web 框架、PostgreSQL、绘图或文档导出。`world`、`media` 为可选安装项。Rust 原生扩展另行安装；未安装时可明确选择 `--backend reference`，不会把参考后端伪装成原生后端。

```powershell
python scripts/build-python-packages.py --out .work/python-wheels
python -m pip install .work/python-wheels/threemind_runtime-2.1.0-py3-none-any.whl
threemind-runtime --model model.tmind --backend reference --clock unbounded --until-us 1000000 --export continued.tmind
```

`until-us` 是本次命令的绝对模拟时刻终点，必须不早于模型已保存时刻；不是意识寿命。输入、器官与环境须通过相应 CLI／宿主显式接入。纯模型包保存 Core 与感官配置；完整具身实验恢复还需要环境、输入总线及观察器上下文，不能把纯模型包称为完整实验快照。

## 研究静默与生产部署

模型会忠实保存静默节点和连接。以下命令只读检查；不会解除静默、改动力学或覆盖模型：

```powershell
threemind-deployment model.tmind
threemind-deployment model.tmind --output declaration.json
threemind-runtime --model model.tmind --deployment-manifest declaration.json --clock unbounded --until-us 1000000
```

如果模型带有静默，生成声明会要求 `--acknowledge-interventions`，或者由研究者在独立副本显式解除静默后重新导出。声明绑定完整模型文件哈希、状态哈希和具体静默列表，文件或列表不匹配会拒绝部署检查。此声明是防误用检查，不是防止有权限的使用者自行改程序的安全边界。历史 CLI 没有被强制加入新检查，以保留研究复现。

## 可选外部沙箱

`deploy/compose.runtime.yaml` 使用独立 Python Runtime 镜像，无网络、无额外设备、只读模型目录、独立输出目录、4 GiB 内存与 2 CPU 限额。Docker 是外壳，不进入 Core。把模型与声明放到 `deploy/runtime-input/`，创建可由容器用户写入的 `deploy/runtime-output/`，确认绝对模拟终点后执行：

```powershell
docker compose -f deploy/compose.runtime.yaml run --rm runtime
```

此命令执行一次有限任务；已有输出文件不会覆盖。部署机器人等有外设或实时要求的环境时，需显式配置设备、网络和实时调度。沙箱默认配置不宣称已经验证真实设备、生产安全或价值对齐。
