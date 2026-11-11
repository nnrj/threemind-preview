# Delivery addendum (2026-09-30)

This section was appended after simulation and evidence archival. It does not recompute or replace measurements. Platform reports are saved as revision 2; revision 1 and the original archive remain available.

**The 40.66% novelty increase has specific conditions.** Both settlement modes used a 1-second facilitation time constant, identical inputs and other parameters. The increase compares transient target net-response integrals at training intensity 0.4. New-creation defaults still use facilitation 0 (extra facilitation disabled). Thus 40.66% is not a uniform improvement for default configurations, final convergence rankings or arbitrary tasks. Every instance retains its complete parameters.

New creation defaults to `threemind.continuous-memory/2` with arrival-window novelty settlement. `causal/9`, `continuous/1`, `continuous-memory/1` and `lif/1` remain available; the new version also supports immediate evaluation. Restoration follows saved identity. Historical protocols omitting identity still mean the original baseline; saved project defaults are not overwritten. Strong-input formulas, forgetting defaults and sensory mapping are unchanged.

Temporal activity readouts are connected to UI, CLI, API, exports and report sources. Original activity steady-state detection remains selectable alongside independently enabled response-pattern convergence, amplitude change, periodic activity and response end. Primary ranking uses decision-window-end activation, retaining full trajectories, peaks and integrals. Stable-background rankings and transient-only target responses remain visible as measured.

Delivery verification:

- **153 tests passed** across kernels, configuration, readouts, deployment and related integration.
- **45 tests passed** across five-kernel Python/Rust interoperability, LIF and build validation. The initially opt-in real compilation case was subsequently enabled; its build suite had **2 passes**.
- **27 tests passed** for default-transition API, ecology execution, temporal reports and probes; **5 Rust core tests passed**.
- An isolated Runtime wheel installation without Lab, FastAPI or PostgreSQL client packages passed save/restore/continuation equivalence for all five kernels. A standalone Rust constructor was actually compiled and tested for plasticity and mismatched-kernel rejection.
- Production frontend build passed. Browsers at 1440 and 390 pixels verified readouts, chat deduplication, new defaults and graphical/JSON synchronization without page overflow.
- Optional sandbox Compose configuration passed validation. **The sandbox image was not built or run**; configuration validation is not container execution acceptance.

Runtime and Lab were updated to 2.1.0 on this workstation, with rebuilt native extension and frontend. The old `.venv` references removed Anaconda. The existing independent Python environment works; no Anaconda reinstall is needed. From the project root:

```powershell
.\scripts\start-lab.ps1 -Python .\.work\kernel-venv\Scripts\python.exe
```

Academic consciousness-indicator collection/validation, rich environment evolution and association-region transplantation are later work. This round does not alter the existing `autonomy-criteria/1` criteria or their passing result.
