# Data availability / 数据获取

The companion **threemind-data-preview** release for the r3 v6 main manuscripts contains **44,635 evidence files (89.146 GiB)** for **81 experiment IDs**. Look up an experiment in [STUDIES.json](STUDIES.json) for its code and data paths. The data package records its release date and totals in `EXPORT.json`. `MANIFEST.jsonl` lists individual files, sizes and SHA-256 checksums.

The r3 release adds the 6.1 and 6.3 replications, the reported E69 gaze-learning course, and the aquatic studies through the observations used in the main text. The registered AS63-01, AS63-02, AS63-03 and RT63-01 archives were verified against their original checksums. The E69 records end at subject boundary 000865. Sealed water-world checkpoints place P1 at 1520.70 internal seconds and P2 at 1669.06 internal seconds.

This is a local release. A public dataset URL or DOI can be added after the author deposits the package.

本版按 r3 v6 定稿的正文、图注和表 4-1 收录数据。只在补充方法目录中列名的实验不属于这份数据包。读者可从[实验索引](STUDIES.json)查到对应的科研代码和原件。两份预览放在同一父目录后，可按[复算说明](REPRODUCIBILITY.md)检查封存文件和实验结果。

```powershell
python ../threemind-data-preview/verify_data.py --metadata-only
python ../threemind-data-preview/verify_data.py
python ../threemind-data-preview/recheck_main_results.py
```

SHA-256 of the evidence manifest / 逐文件清单的 SHA-256 为 `1dee7a51723693e45132fd2664a297783bc4e65e5fe8b75494fe56a33aa8a512`。
