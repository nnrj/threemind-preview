# 原始状态表达工具

2026-10-05，E48。[English](../../en/reference/raw-state-expression.md) · [研究决定](../plans/temporal-input-and-state-expression.md)

`python -m lab.tools.raw_state_expression --manifest layout.json --input processes.jsonl --output new-output.jsonl`

可加`--checkpoint reader.safetensors --device auto`直接解码。没有GPU时回退CPU。输入逐行`{"id":"sample-1","process":{...}}`，输出采用新文件，不覆盖历史。输入单文件上限256MiB。

两种清单：`threemind.raw-state-expression/1`声明匿名通道、节点字段和采样数；`threemind.raw-graph-state-expression/1`声明匿名通道及是否读连接。前者从完整记录选取明确的时间样本，并返回实际样本时间；没有相减、单样本归一化、裁剪、语义过滤或top-k。未知通道/缺失字段报错，不当成零。可声明排除直接感官用于研究归因，但必须显示该清单，不能冒充全状态表达。

后一种读取五份完整快照中的节点与有向连接：节点激活/抑制/痕迹/支持/稳定度/局部可塑性/直接和联想触达/抑制生成及待处理量/触达计数；边权/稳定度/资格迹/触达计数；短时可用量/活动量/利用率；快状态、存在标识及以秒为单位的局部年龄。保留实际存储值及更新时间意义，不假装已进行所有惰性状态的解析恢复。最大262144列、五个采样时刻。

**这是扩展动力学状态读法，不是整个状态容器逐字进入Transformer。** 完整恢复快照仍保存；种子、配置、标签、实验名称、外部待递送队列不送给模型。内部在途消息及全部全局计数尚未加入表达向量，因此不能声称穷尽所有信息。模型前不改变每个样本的幅度；Transformer自身仍按原架构学习数值变换。

表达器每次从空缓存开始，不读取旧输出或对话。其权重会学习翻译规则；这与把当前题目的答案或对话记忆放在表达器里不同。测试新对应时需冻结权重并改变ThreeMind经历，共同发育则另列教学/留出分割。

线性诊断器`ridge_fit/ridge_predict`使用固定正则和可学习截距，不做样本预处理；正确分类仅表明工具可利用这些状态区别，不能单独证明内核推理。需配合不学习、反转、未见对应及通路控制。

2026-10-05交付补充：实际答对与提示特异评分并列；无提示的空白不是真值，不能据此过滤表达或断言无自主活动。[E48更正](../../../lab/explorations/2026-10-05-temporal-state-expression/scoring-correction.zh.md)
