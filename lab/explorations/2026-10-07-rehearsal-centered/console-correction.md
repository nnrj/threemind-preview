# 2026-10-07：第一组摘要打印异常

`rehearsal-recent`已保存完整`system`、`calibration.json`与`result.json`，随后打印终端摘要时，`initial_correct`中的NumPy整数不能被默认JSON编码器序列化，进程返回1。保留原`stopped.json`和结果；此异常发生在保存后，不重跑模拟，不重写原证据。后续将正确数转为普通整数，摘要采用已有编码函数。第一组原结果中的该字段由既有落盘编码器存成字符串，分析按整数读取；数字内容不变。预算只计算该组一次。

The first case completed and saved its entire system and result before console JSON serialization failed on a NumPy integer. Preserve the failure and saved files, do not rerun or rewrite evidence. Future summaries cast the count to an ordinary integer. Analysis parses the original count string; compute time is counted once.
