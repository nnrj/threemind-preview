# R46b独立复算工具修订2 / Independent-audit revision 2

2026-11-10，科学批运行期间静态核对发现：分析文件中的延迟键在JSON保存后是字符串，独立复算却将其与整数键字典直接比较，因此会错误报失败。合成80维数组的JSON往返明确复现了问题。修订2只将预期字典的延迟键转为字符串，再逐项比较原数值；公式、窗口、分数、门槛、全态链和科学输入均未改变。

冻结原审计保留，现有后处理观察器仍记录其首次失败；随后核对失败原因，只运行修订2及尚未执行的清点。不得重跑科学个体。源码哈希和合成核查见同名JSON。正式独立复核结果须等全部960序列完成后另记。

Static inspection while the scientific batch was running found that persisted JSON delay keys are strings, whereas the auditor compares them with integer keys. An 80-dimensional synthetic JSON round trip reproduces the false mismatch. Revision 2 converts only the expected delay keys to strings and preserves every value, formula, window, score, criterion and continuity check. The frozen original audit and its first failure remain; the corrected audit and any still-missing inventory follow only after verifying that failure. Scientific subjects are never rerun for postprocessing repair. Full-data verification remains pending until all 960 sequences finish.
