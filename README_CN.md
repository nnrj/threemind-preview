# ThreeMind 代码预览版

本目录是为 ThreeMind 预印本独立整理的代码预览版，包含 Python 参考内核、Rust 内核与独立运行时、适配器、实验平台 API、工作台、实验脚本和测试。原仓库版本和逐文件 SHA-256 校验值见 [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json)。

预览版使用全新的 Git 历史，已补入经核查的科研史书、讨论节选、协议和报告；排除论文草稿、写作与投稿讨论、私有会话定位、论文生成工具、凭据、本机数据库和原始实验数据。完整项目地址为 <https://github.com/nnrj/threemind>；预览版拟发布到 <https://github.com/nnrj/threemind-preview>。本次本地整理本身不代表已上传。

[公开版范围与删节说明](PUBLIC_EDITION.md) · [中文史书](docs/zh/history/index.md) · [English](README.md) · [安装说明](INSTALL.md) · [实验复现](REPRODUCIBILITY.md) · [数据获取](DATA_AVAILABILITY.md)

新建个体默认使用 `threemind.continuous-memory/6.3`。6.0 起使用固定函数寻址。各实验保留实际使用的内核版本和配置。[实验索引](STUDIES.json)列出 r3 各节对应的研究代码及原件。

先核验数据校验值，再按实验清单复算。重新实验必须使用新的输出目录。恢复完整个体时，还需保留其个人适配器、优化器、随机状态、近期活动、映射和身体状态。仅恢复 Core 不是恢复完整个体。

本次提取不新增软件许可，不改变第三方组件原有许可。论文文件与原始数据分别保存，不随代码仓库发布。

三组中英文科研图片按原路径保留，`docs/paper` 中没有稿件。删节位置逐处说明原因，完整索引见 [PUBLIC_OMISSIONS.json](PUBLIC_OMISSIONS.json)。
