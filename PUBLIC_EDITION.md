# ThreeMind 公开版补全说明 / Public-edition supplement

2026-11-11。来源为完整仓库提交 `8f56c7872458f40e9367c7144d74968fa7187a19`。本说明记录对初始代码预览版的补全；原仓库、实验原件和原始 Git 历史保持不变。

## 本次补回

- 技术文档、实验协议、研究报告及其历史修订、实验配置、小型摘要、科研图表和参考手册。
- 中文、英文通史与列传，以及两套文言史书；公开目录共 135 章。可从[中文史书](docs/zh/history/index.md)、[英文史书](docs/en/history/index.md)进入。
- 作者已明确允许公开的创始陈述及其中的个人生活回忆。私有会话定位信息已去除。
- 史书检查、独立阅读工具及相应测试；补回实验回放 HTML、环境模板和界面配置示例。
- 史书引用的三组科研图片，每组中英文各一张，共六张。图片保持原字节和原路径；`docs/paper` 中只包含这六张 PNG。[技术来源说明](docs/zh/reference/history-figure-sources.md)和[来源清单](docs/history/figure-provenance.json)保留实验、帧号、时间及哈希。

本次从完整仓库增加 2,721 份材料，其中 2,635 份逐字节复制，85 份为标明删节或调整的公开版本，1 份为 Git 换行属性调整；另增公开说明和技术来源清单。代码预览版可读研究范围扩大，不表示配套数据预览版也增加了全部研究原件。原始数据的公开范围仍见[数据说明](DATA_AVAILABILITY.md)。

## 删节标注

论文正文、草稿、论文写作与投稿讨论、私有会话编号和定位信息不予收录。混合段落保留实验事实、数值、技术说明和运行决定；删去的内容在相应位置用“公开版删节／调整”说明原因。表格用表内标记；JSON 用显式 `public_edition` 或 `public_omissions` 字段说明。

[删节索引](PUBLIC_OMISSIONS.json)列出源文件位置和原因，不复制被删内容。行号以来源提交为准。研究原件与旧报告没有被覆盖；历史清单中的原哈希描述其原始版本，公开节选自己的哈希见 [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json)。被整篇排除的论文写作条目不在公开史书目录中，其类别和数量列在删节索引中。

普通技术规范中的论文引用、学术文献题名、“不得改作者论文”等边界说明，以及实验报告自身的修订记录仍保留。这些不是论文正文或投稿讨论。

## 阅读与核验

```powershell
python tools/verify_preview.py
python tools/validate_history.py
```

本次核查通过四套史书的目录、双语覆盖和本地链接检查，以及五项史书读取测试；未启动数据库、实验、训练或常驻服务。初始预览版的内核、Rust、工作台和数据复算检查另存于 [VALIDATION.json](VALIDATION.json)，明确与本次检查区分。

图像原相对链接可供 GitHub 和本地 Markdown 阅读器直接读取。现有工作台资源 API 仅开放指定资源目录，未开放 `docs/paper`；因此在该工作台中这六张图可能不能显示。本次保留应用代码与访问边界，可直接打开原路径的图片。历史交接文件是带日期的档案，不是当前启动授权。

## English

This supplement adds technical documentation, protocols, reports and revisions, configurations, small summaries, reference material, research figures, four history editions, history tools/tests and missing replay/template resources. Of the 2,721 added source-derived files, 2,635 are byte-identical and 85 are explicitly marked public editions, and one is a Git-attribute packaging adjustment. The author's approved founding recollections are included; private conversation locators are omitted.

Manuscripts, draft text, writing/submission discussions and private conversation IDs are excluded. Each edited location states the reason; JSON records carry explicit omission metadata. [PUBLIC_OMISSIONS.json](PUBLIC_OMISSIONS.json) gives source-line locations and reasons without reproducing removed text. Mixed records retain their scientific facts and operational decisions. Historical source hashes remain provenance, while [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) also records the hashes of edited public copies.

The six authorized research PNGs retain their original paths and bytes. Only these images are present under `docs/paper`. Their [technical provenance](docs/en/reference/history-figure-sources.md) is separate from the excluded manuscript-bearing register. Direct GitHub/local Markdown links work; the unchanged workbench resource API does not serve `docs/paper`, so its viewer may not display these six images. No application access boundary was expanded.

All four history editions (135 chapters) passed catalogue, bilingual-coverage and local-link checks, and five history-reading tests passed. The initial snapshot's kernel, build and data checks are identified separately in [VALIDATION.json](VALIDATION.json); they were not repeated for this documentation supplement. No experiment or service was started. The companion data-preview scope is unchanged. Original repository and data remain intact. This is a local preparation, without push or upload.

Git 打包说明：一份预览版 `.gitattributes` 追加 JSON 原字节保留规则，防止再次检出时换行转换使来源哈希失效。该调整单列在来源清单的 `packaging_edits` 中，未修改原仓库或任何程序逻辑。

Git packaging note: one preview `.gitattributes` file disables JSON newline conversion so future checkouts preserve the exported bytes and hashes. This is listed separately under `packaging_edits`; original source and application logic are unchanged.
