# Reproducing the reported experiments

[中文简要说明](#中文简要说明) · [Installation](INSTALL.md) · [Study index](STUDIES.json) · [Dataset](DATA_AVAILABILITY.md)

## 1. Verify the source and data

Install the dependencies described in `INSTALL.md`. If the code and data directories are siblings:

```powershell
python tools/verify_preview.py
python ../threemind-data-preview/verify_data.py
```

The first command checks every preserved source file against `SOURCE_MANIFEST.json`. The second reads and hashes every evidence file (42.535 GiB). To check one study, add `--study M1-confirmation`; `--metadata-only` checks paths, sizes and the manifest hash without rehashing all payloads.

## 2. Recompute the confirmation analyses

```powershell
python tools/reanalyse_public.py --data ../threemind-data-preview
```

This command reads the sealed M1, M2, M3 and M5 confirmation ZIPs, extracts only the small per-origin result records into a temporary directory, and invokes the preserved statistical analysis functions. It compares the complete recomputed analyses with the published analyses, including per-origin values and intervals. It creates no Core, teaches no individual and changes no simulation time. It prints the results; an optional `--output` may save them outside the published data directory.

The packaged local validation matched all four analyses: M1 (48 origins), M3 (64 origins), M5 (48 origins) and M2's new-condition prediction (8 origins, 160 tests). This is reanalysis of existing observations, not an independent replication experiment.

## 3. Find the original records

Use `STUDIES.json` to map paper sections to experiment identities, data directories and source scripts. Each `MANIFEST.jsonl` entry has a `study` field. `OBJECTS.jsonl` identifies the extensionless content-addressed archives and media in `originals/objects`.

For example, the M1 confirmation archive is:

```text
experiments/2026-10-16-mechanism-discovery/m1-confirmation-v1/originals-v1.zip
```

Unpack an archive into a **new directory outside the dataset** when a deeper audit needs its full records:

```powershell
python ../threemind-data-preview/extract_archive.py ../threemind-data-preview/experiments/2026-10-16-mechanism-discovery/m1-confirmation-v1/originals-v1.zip --output ../m1-confirmation-inspection
```

Check available space against the expanded archive size first. The extraction helper validates member paths and refuses an existing output directory. It does not resume any subject. The E68 data include the two full continuous trajectories and recorded replay material; historical ocean studies include their original recordings and exported media.

## 4. Read the registered design before a new run

The corresponding `lab/explorations` directory contains the preserved protocol, implementation and scientific reports. Original and dated report revisions remain distinguishable. The main confirmation protocols are:

- `2026-10-16-mechanism-discovery/m1-confirmation-protocol.en.md`
- `2026-10-16-mechanism-discovery/m3-confirmation-v2-protocol.en.md`
- `2026-10-16-mechanism-discovery/m5-confirmation-protocol.en.md`
- `2026-10-16-mechanism-discovery/m2-gain-protocol.en.md`
- `2026-11-01-sat-core-exclusion/protocol.en.md`

Historical design records use `design.en.md` and `design.zh.md`. Preserve independent-origin denominators, branches, original criteria, negative results and complete peripheral state. Run a fresh experiment only after selecting a new output directory and verifying the script's arguments. Some historical drivers retain the author's original absolute default paths and local API registration settings: inspect `--help` and pass an explicit new `--work` where supported. Never execute a historical driver against the published data directory.

The current default for a new individual is `threemind.continuous-memory/6.3`. Select the recorded kernel and configuration when reproducing an earlier study. The public source snapshot includes the historical implementations.

## 5. Software checks

After building the native extension and standalone Rust runtime:

```powershell
$env:THREEMIND_TEST_RUNTIME = (Resolve-Path target/release/threemind-runtime.exe).Path
python -m pytest -q tests_v2/test_kernel_registry.py tests_v2/test_local51_equivalence.py tests_v2/test_local53.py tests_v2/test_weight_decay.py
```

These 343 checks passed on the extracted code using a newly built native extension and runtime. The runtime environment variable is required for artifact roundtrip tests. Other test modules may require an isolated PostgreSQL database, optional dependencies, or external historical datasets. The extraction does not start those services automatically.

## 中文简要说明

先核验源码与数据，再运行只读复算入口。该入口从原始封装包读取每个独立来源的记录，重算 M1、M2、M3、M5 的确认统计，并逐项对照已保存分析；它不推进个体，也不重复训练。论文小节与数据位置见 `STUDIES.json`。

若要重新实验，请先阅读相应中英文协议，使用新输出目录，并保留实验实际使用的内核身份和完整个体状态。旧脚本保留原来的默认路径及平台登记逻辑，运行前须明确参数；不要把公开原件目录直接作为新实验工作目录。

## Inspect the P1 and P2 pause boundaries

A live progress file can predate the last sealed observation. Read the segment chain, the feeding and birth events, and the complete last checkpoint. From the code preview, with the indicated data installed, run the following commands.

```powershell
python tools/read_ocean_checkpoint.py ../threemind-data-preview/experiments/ocean63-p1-20261121/evidence/cases/world-0-reference --last 25
python tools/read_ocean_checkpoint.py ../threemind-data-preview/experiments/ocean63-p2-20261122/evidence/cases/world-0-reference --last 28
```

The command checks the checksums of the records it reads. Use the dataset verifier for all files. P1 stopped at 1520.70 internal seconds. P2 stopped at 1669.06 internal seconds with 311 saved Cores, 57 living individuals, 258 births, 115 live predation events and 121 scavenging meals. The counters apply to the first original-supply aquatic world.

在论文所用的观察边界，P1 对应第 25 个编号分段，P2 对应第 28 个编号分段。命令只读已封存的记录。运行前请按数据包中的文件清单确认对应分段已安装。
