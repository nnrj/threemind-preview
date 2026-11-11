# R46a独立复算工具修正 / Independent audit correction

2026-11-09，科学计算进行中，完整成绩尚未生成。静态复查发现原`audit_assay.py`用`count`累计完整边界，又在条件汇总中将它覆盖成字典；末尾与3840比较必然失败。这是验证脚本错误，不是科学宿主错误。

保留原冻结脚本和其失败日志，另存`audit_assay_v2.py`。唯一计算修正是把条件字典变量改名；原边界计数、所有公式、阈值和逐项比较不变。输出追加修订编号及脚本哈希。科学宿主继续原冻结执行，不加载或推进任何个体来补算。v2对完整数据的实际核验结果将在计算结束后记录。

Static review found a bookkeeping error: the frozen auditor replaced its integer boundary counter with a condition dictionary before the final 3,840-boundary assertion. Revision 2 renames that dictionary and adds explicit auditor provenance. All formulas, thresholds and scientific comparisons remain unchanged. The original auditor and failure log are retained; the scientific run is unaffected.

`independent-audit-v1.json` denotes the first successful result/schema, not the auditor's source revision. It will explicitly contain `auditor_revision: 2` and `auditor_sha256`. Its creation requires actual complete-data verification; this correction note does not claim it has passed. The failed original postprocessing receipt also remains, with a later completion receipt recorded separately.
