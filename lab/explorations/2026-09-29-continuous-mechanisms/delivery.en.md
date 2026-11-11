# Continuous-kernel attribution: delivery and resources

[中文](delivery.zh.md) · [Report](report.en.md)

Completed 341 instances: 224 factorial training/probes, 56 test-time switch copies, 12 baseline instances, 32 background instances, 5 observation validations and 12 local diagnostics. No failed or budget-stopped instances.

Project **2026-09-29 连续版机制归因**, `e769cd2d-c636-41b0-a266-6af1cca4b805`:

- Initial Chinese design note: `5b24d3c0-b19a-4035-8c18-9fcfde4fdc86`; English design and prospective diagnostic amendment also saved.
- Chinese report revision 1: `8ee40b06-2440-56d2-8fc2-1025146b093b`.
- English report revision 1: `c73c7fd5-5fe2-5a36-b889-6e3265572a9a`.
- Nine experiment records, two reports, and bilingual results notes.
- Evidence artifact: `4e55d7dc-1e0f-44f0-b17e-d9f4a2543693`, 137,921,395 bytes. All 1997 manifest members were read and SHA-256 checked before upload.
- Archive SHA-256: `fa2bb67d86b8aaceb9bbb386e31b5b5bef4c1fe2c5fdaed48ddc8feb823c0e18`.

Measured after publication: summed instance execution 501.19 seconds (~8.35 minutes); DB growth 888,225,792 bytes (~0.827 GiB); local evidence/analysis/ZIP 425,527,971 bytes (~0.396 GiB); total **1,313,753,763 bytes (~1.224 GiB)**, below the 2-GiB cap. No active compute/publication jobs remain.

Account usage read 39% at the start and 40% after completion, below the 42% stopping point. These are rounded, account-wide readings, not exact task billing. No AI calls were made by the scripts. Tiny delivery files were added after the storage measurement; DB growth can include PostgreSQL allocation overhead.

Runtime guards enforced RSS <=4 GiB, host available RAM >=2 GiB and D/E free space >=15 GiB without triggering a stop. No claim of an exact lifetime peak-memory measurement; no old-data cleanup.

Verification: exact previous training/readout reproduction; observation/sampling neutrality; parent state hashes; 16 exact context-on/off trajectory comparisons; diagnostic default-state parity; gate calculations matching actual resource updates; report readback at revision 1; nine records/two reports and artifact hash/ownership checked. The figure was rendered and visually inspected. Documentation discovery is checked. No UI implementation changed, user services were not restarted, and no new browser-interaction validation is claimed.

Only study orchestration, analysis, reports and documentation indexes changed. Core, defaults, sensory mapping and prior experiments remain untouched. Final audit is `.work/continuous-mechanisms-20260929/delivery-audit.json`. This delivery note was written after ZIP creation and is retained separately, not retroactively claimed as an archive member.
