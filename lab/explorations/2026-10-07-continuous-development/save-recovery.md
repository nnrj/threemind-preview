# 2026-10-07: completed evaluation saved after a Windows rename error

The visible-cue control completed all twelve trials and wrote the complete system and peripheral under `system.partial`. Windows rejected the final directory rename with `WinError 5`. The process records were closed successfully. The original `stopped.json` and tool revision remain intact.

After checking that source and destination stayed inside this study and that the destination did not exist, the completed directory was renamed with authorized local filesystem access. `recover_visible_cue.py` recovered the twelve scores from the original process records and the original wall time. No simulation, learning, input or response was repeated or changed. `recovery.json` explicitly identifies this recovery. Computation accounting counts this completed case once rather than adding its preserved error record a second time.

New saves retry only a transient permission error, at most three short waits; they still refuse overwrites and retain the partial directory on persistent failure. Future evaluations save the small scores file before attempting the final snapshot. This changes evidence handling only.

中文摘要：持续提示对照已完成全部十二题，完整快照写出后在目录改名时遇到 Windows 权限错误。核对目标限定在本研究目录且不存在后完成改名，由原过程记录恢复成绩。未重跑、未改变任何输入、学习或响应；原错误记录保留，耗时只计一次。后续存档只增加短暂权限错误重试，并先保存小型成绩文件。
