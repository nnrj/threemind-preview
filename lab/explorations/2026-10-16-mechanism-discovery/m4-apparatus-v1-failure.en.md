# M4 v1 formal apparatus: encoding defect prevents scientific launch

17 October2026, frozen66a8b47; record `1ca090fe-d05d-500e-8861-f207a368dc41`. [中文](m4-apparatus-v1-failure.zh.md)

**Conclusion: v1 failed the complete-restoration acceptance required before scientific execution. The failure concerns the new evidence encoder. None of the eight scientific origins started, so this is neither positive nor negative evidence about ThreeMind functional division.**

Purpose and expectation: the formal N=0 apparatus must complete known physical demonstration and whole-state save/restore, then reproduce exactly the complete endpoints and trajectories of sham and immediate-restoration paths. Every requirement must pass before the eight-origin study.

Result: the instrument completed a3-second known demonstration and two personal peripheral updates, then saved parent files. Its first restoration of `system.json.xz` raised `ValueError: unknown packing tag`; the two subsequent acceptance paths did not complete. It used approximately31.50 host seconds and2.54GiB peak private memory without a resource STOP. Scientific units,host and progress files do not exist. Preserve apparatus-in-flight,parent files,samples,resource summary and frozen sources.

Analysis: the earlier isolated encoder first converted state into standard JSON objects, implicitly converting tuples into lists. A later transient-memory optimization removed that full reparsing copy, but the packing logic handled lists without handling native tuples in random state. JSON serialization converted untagged tuples into arrays that the decoder could not identify. Final pure-data checks covered empty lists,objects,floats,mixed keys and corruption but omitted native tuples. Earlier isolated N0 success could not replace formal acceptance of the final frozen implementation. The formal gate prevented the faulty tool from reaching scientific execution.

Disposition: close and archive v1 as failed with full API readback. Do not edit frozen v1,retry its directory,clear its marker or resume computation from its parent. Independent v2 explicitly tags every native tuple as a sequence and adds cases for tag-like text,nested random states and endpoint tuples. Use a new entry point,directory,record and idempotency namespace and repeat isolated plus formal N0 acceptance. The eight scientific seeds,course,G1/G2/G3,personal readers,Core and resource reserves remain unchanged.

Meaning for ThreeMind: this identifies a testable storage-tool defect and demonstrates that final-version acceptance prevented an invalid experiment. It neither overturns previous mechanism findings nor completes the functional-division study. No scientific individual was rolled back,reborn or deprived of experience. Continue within authorization by fixing measurement tools while retaining the scientific criteria.
