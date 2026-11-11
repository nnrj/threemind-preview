# 可持续学习的语言中枢适配器

[English](../../en/reference/adaptive-expression.md) · [研究边界](../plans/coadaptive-language-center.md)

`threemind.adaptive-expression/1` 是独立外设。它读取 `graph-expression/2` 接受的原始局部过程；外部教师示范仅用于更新表达器，不成为推理输入。它不是新意识内核，也不替换旧表达器。

## Python

```python
from threemind_transformer.adaptive_expression import AdaptiveExpression, return_utterance
from threemind_transformer.local_activity import local_process

head = AdaptiveExpression(capacity=64, device="cpu")
head.teach(local_process(observation_a), "甲。", receipt="teacher-example-a")
head.teach(local_process(observation_b), "乙。", receipt="teacher-example-b")
head.adapt("new-checkpoint-1", steps=500)
answer = head.decode([local_process(new_observation)])[0]["text"]

# 明确开启后，实际说出的原话通过原有编码、输入队列送回。
# encode 必须是该实例已声明的感官编码，不能按正确答案重写。
return_utterance(reader, answer, encode, enabled=True)

restored = AdaptiveExpression.restore("new-checkpoint-1", device="cpu")
restored.teach(local_process(next_observation), "丁。", receipt="teacher-example-c")
restored.adapt("new-checkpoint-2", steps=500)
```

更新从已有参数继续，优化器每批重建；教学回放容量2～128，默认64，先进先出。回放淘汰只发生在外设的学习缓存，调用方的原始证据不删除。每次更新写新目录，已有/失败目录都不覆盖。模型、回放、父版本和训练记录可恢复；尚不提供跨窗口事实记忆，也未声称实现快权重算法。

## CLI

```powershell
$py = '.work/kernel-venv/Scripts/python.exe'
& $py -m threemind_transformer.adaptive_expression_cli teach --input teaching.jsonl --output revision-1 --steps 500
& $py -m threemind_transformer.adaptive_expression_cli teach --parent revision-1 --input more-teaching.jsonl --output revision-2
& $py -m threemind_transformer.adaptive_expression_cli decode --parent revision-2 --input observations.jsonl --output utterances.jsonl
```

教学JSONL每行只有`process`、`text`、`receipt`；推理每行只有`process`，拒绝答案、对象标记及历史身份字段。`process`与[局部表达CLI](graph-expression.md)的准备格式相同。`--device auto`有CUDA用CUDA，无则CPU，也可明确`--device cpu`。已有输出拒绝覆盖；每次最多128条、输入128MiB，默认计算30分钟，RSS4GiB、GPU3GiB及可用RAM2GiB保护。

自听API默认关闭，避免悄悄改变旧实验。启用时不修饰、过滤或替换错误词语；空输出即无文本输入。教师监督、实际自听以及观察者的分析分别保存。持续学习成功不能单独证明语义来自Core，仍需固定外设的内部干预及反向教学检验。

## 有限词表转写工具

`lab.tools.local_word_transcriber.LocalWordTranscriber` 用于检验原始局部过程是否可区分实际听到的词。它是研究工具，可与 Transformer 读取同一资料，不替换生产表达器。

```python
from lab.tools.local_word_transcriber import LocalWordTranscriber

reader = LocalWordTranscriber(ridge=0.0001).fit([
    {"process": local_process(observation_a), "text": "甲。"},
    {"process": local_process(observation_b), "text": "乙。"},
])
utterance = reader.decode(local_process(new_observation))
reader.save("new-transcriber-checkpoint")
restored_reader = LocalWordTranscriber.restore("new-transcriber-checkpoint")
```

相同相对采样时刻的通道与六字段作为特征，线性岭回归学习权重。包含截距；不居中、不减无提示副本、不逐样本归一化，也不按语义挑节点。只支持节点过程、2～128条示范、2～32个词；不生成任意句子。未在训练中出现的特征权重为零，其数量返回给调用方。词分数不是概率，必须另外检验新经历；一次拟合不等于随Core变化自动适配。

教学词是外设监督，不是推理输入。只教直接听词，仍不能保证能读懂回忆或对外表达；[E52](../../../lab/explorations/2026-10-05-coadaptive-language/report.zh.md)已将这几项分别测试。
