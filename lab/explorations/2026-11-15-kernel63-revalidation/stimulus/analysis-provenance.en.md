# R63a analysis provenance

15 November 2026. Before analyzing formal results, two record corrections were documented. The frozen English protocol retained the old date, 13 November, on its first line. This batch was actually registered, frozen and executed on 15 November 2026; API receipts give the timestamps. The original protocol is preserved.

The initially ported analyze.py used GetCompressedFileSizeW for physical allocation, which can return only file length for uncompressed files. Formal read-only analysis therefore uses analyze_v2.py with the existing R51c FileStandardInfo allocation function. Scientific measures, conditions, windows and criteria are unchanged. The original analyzer was not run and no result was overwritten. No subject or teaching is rerun. Per-state auxiliary allocated_bytes fields retain their original values; the report uses the independent physical-allocation audit.
