# 14 November 2026: correction to delivery-record verification

After all 464 scientific stages had completed, analyze_v2.py raised a KeyError on its first delivery record: the actual format has no status field. The original script and failure are retained. That attempt produced no scientific analysis, and no individual was rerun.

The separate analyze_v3.py checks that the actual Core event sequence is positive instead of looking for the nonexistent status field. All existing checks of event identity, input content and source, scheduled versus actual delivery time, absence of answer labels and empty input queues remain. Process integrals, peaks, scientific thresholds, denominators and decision rules are unchanged. The not-yet-executed novelty supplement uses the corresponding analyze_novelty_v2.py; its original auditor is retained.

The failure was at line 51 of analyze_v2.py. Actual records contain core_event_id, core_sequence, scheduled_time_us, delivered_time_us, stimulus and source. This is a verifier's format error, not a missing delivery. The revised verifier checks every actual delivery, and the original script and this correction are included in the evidence package.
