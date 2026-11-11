# Installation

Use Python 3.11 or newer, a stable Rust toolchain, and Node.js 24 for the web workbench. Native builds on Windows need the MSVC C++ Build Tools. PostgreSQL 17 is required for the laboratory service, but not for the standalone Rust runtime or database-free kernel analysis.

From this repository root, create your own environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e packages/runtime -e packages/transformer -e ".[dev,media,transformer]"
python -m maturin develop --release --manifest-path crates/threemind-native/Cargo.toml
```

For the web workbench:

```powershell
Set-Location threemind-ui
npm ci
npm run build
Set-Location ..
```

On a **new installation**, copy `.env.example` to `.env`, enter your own PostgreSQL settings, and run `python -m threemind_lab.cli setup-local`. Do not copy another machine's database credentials or initialize over an existing research database.

Browse documentation and saved results with the API service only:

```powershell
python -m threemind_lab.cli serve --host 127.0.0.1 --port 8877
```

Open <http://127.0.0.1:8877> and complete first-account setup. To run the full workstation, including workers that may claim queued jobs, use `scripts/start-lab.ps1` with your environment's Python. That is a separate, deliberate operation.

The standalone Rust runtime does not require Python, PostgreSQL or Lab:

```powershell
cargo build --release -p threemind-runtime
.\target\release\threemind-runtime.exe --help
```

Keep the exact kernel identity in each model and experiment protocol. Source code is provided for historical versions; changing a saved identity is not a version conversion. See `docs/en/v2-independent-runtime.md` and `docs/en/v2-kernels.md`.

## 中文简要说明

请自行创建虚拟环境；本仓库不提供作者电脑的 `.work/kernel-venv`、账号或数据库。上面的安装命令同时安装本地 Runtime、Transformer 组件和实验平台。仅查看文档时用 `serve`；`start-lab.ps1` 会启动作业工作进程。Rust 独立运行时可直接构建，不依赖实验平台数据库。
