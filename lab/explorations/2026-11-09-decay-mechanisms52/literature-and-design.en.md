# Literature and measurement choices for the decay comparison

9 November 2026. Preparation before the 5.2 implementation, not a completed behavioral experiment. [中文](literature-and-design.zh.md)

Wixted and Ebbesen found that power functions described retention better than five alternatives in word recall, face recognition, and pigeon delayed matching. This motivates including a power-law candidate. Their dependent variable was behavioral performance; it does not directly specify the decay law of an individual connection. [Original study abstract](https://www.psychologicalscience.org/journals/psychological-science/j.1467-9280.1991.tb00175.x/)

Aggregation also matters. Murre and Chessa derived conditions under which averaging exponential processes with different rates produces a power function. We will retain individual connection trajectories and independent-origin scores before computing group means. A mean retention curve cannot by itself identify the decay law of every constituent connection. [Original paper](https://doi.org/10.3758/s13423-011-0076-y)

In a study of more than 1,350 participants, Cepeda and colleagues found that the appropriate review gap varied with the final retention interval. For a given interval, increasing the gap first improved and then impaired retention. We retain initially dense and later spaced teaching, while matching exposure counts, doses, complete curricula, and delays from last exposure to first test across decay conditions. Human interval ratios are not adopted as model constants. [Original paper](https://doi.org/10.1111/j.1467-9280.2008.02209.x)

These findings inform three measurement choices:

1. Measure connection survival, cue-evoked internal activity, and correct answers separately, each with its own objective and denominator.
2. Prefer first questions for retention at each delay. Later questions about the same material count as renewed experience; test-induced review must not be described as passive retention.
3. Match the first half-value time of a new contribution, then compare repetition, strength, novelty, reversal learning, and long tails. Longer retention is not automatically better: the objectives include preserving useful experience and losing irrelevant experience.

These are design decisions for this study. Curricula, effect thresholds, and sample sizes will be frozen after apparatus calibration and before formal execution. The cited findings are not ThreeMind outcomes.
