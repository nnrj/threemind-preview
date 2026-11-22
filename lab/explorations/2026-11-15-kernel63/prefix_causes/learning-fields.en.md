# Inhibitory learning contributions distinguished in this study

Source inspection on 15 November 2026, before the component-comparison results. Sources are `_emit`, co-stimulation updates and local expiry handling in `src/threemind_kernels/local63.py`. This table identifies actual controlled fields; code inspection alone does not establish their experimental effect.

| Quantity or record | Possible update after successful inhibitory transmission | Subsequent use |
| --- | --- | --- |
| Most recent transmission time, `last_pass_us` | Controlled by `inhibition_updates_usage`; successful excitation still updates it | The current weight-decay step under stability-based retention and the co-stimulation reinforcement coefficient |
| Base weight, `weight` | Increased with transmitted inhibitory amount when explicit inhibitory learning and weight reinforcement are enabled, subject to a cap | Signal transmission and the allocation fraction under weight-proportional inhibition |
| Short-term enhancement, `fast` | Increased with the learning signal and subsequently decayed | Combined with base weight to determine effective transmission weight |
| Eligibility, `eligibility` | Updated as `min(1, 0.7 × previous value + learning signal)` | Stability decay; this update does not necessarily increase the value |
| Stability, `stability` | Increased with the learning signal when growth is enabled | Weight-decay speed under stability-based retention |
| Retention timescale, `half_life` | Updated only when timescale growth is enabled | Growth is disabled in the study configuration, so this component serves as an unchanged control |
| Touch count and latest touch time, `touches` and `last_touch_us` | A transmission with a learning contribution increments the count and updates the time | The count also affects stability growth during later co-stimulation; these records differ from the most recent transmission time |

Disabling explicit inhibitory learning removes inhibitory contributions to all rows except the first while retaining excitatory contributions. Disabling inhibitory transmission-time updates controls only the first row. The complete-configuration, resource, threshold and component comparisons test whether these distinct interventions determine prefix discrimination.
