# E34 measured tables / 实测表

Every row retains the complete habitat. Time is seconds after the declared whole-world fork.

| 来源 / focal→counterpart | 操作 / operation | First contact s | Counterpart captured by @ s | Other+target captures | New food | Focal body alive |
| --- | --- | ---: | --- | ---: | ---: | --- |
| g0-e0: 48→47 | intact | — | — | 0 | 1 | True |
| g0-e0: 48→47 | target | — | — | 0 | 1 | True |
| g0-e0: 48→47 | matched | — | — | 0 | 1 | True |
| g0-e0: 48→47 | random | — | — | 0 | 2 | True |
| g0-e0: 48→47 | experienced | — | — | 0 | 1 | True |
| g0-e0: 48→47 | blank | — | — | 0 | 1 | True |
| g0-e0: 48→47 | graft | — | — | 0 | 1 | True |
| g0-e0: 48→47 | graft-matched | — | — | 0 | 0 | True |
| g0-e1: 12→57 | intact | — | — | 0 | 1 | True |
| g0-e1: 12→57 | target | — | — | 0 | 1 | True |
| g0-e1: 12→57 | matched | — | — | 0 | 1 | True |
| g0-e1: 12→57 | random | — | — | 0 | 0 | True |
| g0-e1: 12→57 | experienced | — | — | 0 | 1 | True |
| g0-e1: 12→57 | blank | 2.240 | 12 @ 3.080 | 1 | 1 | True |
| g0-e1: 12→57 | graft | — | — | 0 | 1 | True |
| g0-e1: 12→57 | graft-matched | 2.200 | 12 @ 3.040 | 1 | 1 | True |
| g1-e0: 14→6 | intact | — | — | 0 | 0 | True |
| g1-e0: 14→6 | target | — | — | 0 | 0 | True |
| g1-e0: 14→6 | matched | — | — | 0 | 0 | True |
| g1-e0: 14→6 | random | — | — | 0 | 1 | True |
| g1-e0: 14→6 | experienced | — | — | 0 | 0 | True |
| g1-e0: 14→6 | blank | — | — | 0 | 4 | True |
| g1-e0: 14→6 | graft | — | — | 0 | 1 | True |
| g1-e0: 14→6 | graft-matched | — | — | 0 | 3 | True |
| g1-e1: 36→8 | intact | — | — | 2 | 1 | True |
| g1-e1: 36→8 | target | — | — | 2 | 1 | True |
| g1-e1: 36→8 | matched | — | — | 2 | 1 | True |
| g1-e1: 36→8 | random | — | — | 0 | 0 | True |
| g1-e1: 36→8 | experienced | — | — | 2 | 1 | True |
| g1-e1: 36→8 | blank | — | — | 2 | 1 | True |
| g1-e1: 36→8 | graft | — | — | 2 | 1 | True |
| g1-e1: 36→8 | graft-matched | — | — | 2 | 1 | True |

Activity reduction uses1–10s samples where the target channels have no direct input in the preceding second in either branch. Action MAE uses only common living periods; duration in parentheses.

| Source | Edges | Target activity reduction | Matched activity reduction | Target action difference | Matched action difference | Experienced vs blank | Experienced vs graft | Experienced vs matched graft |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| g0-e0 | 128 | 99.89% | 1.86% | 0.017757 (20.00s) | 0.018300 (20.00s) | 0.011810 (20.00s) | 0.005580 (20.00s) | 0.029571 (20.00s) |
| g0-e1 | 128 | 15.90% | 0.42% | 0.004206 (20.00s) | 0.001551 (20.00s) | 0.030611 (20.00s) | 0.015478 (20.00s) | 0.030955 (20.00s) |
| g1-e0 | 128 | 78.65% | 0.37% | 0.013396 (20.00s) | 0.008241 (20.00s) | 0.062173 (20.00s) | 0.022902 (20.00s) | 0.043492 (20.00s) |
| g1-e1 | 128 | 97.06% | 1.17% | 0.024504 (20.00s) | 0.021344 (20.00s) | 0.053969 (20.00s) | 0.051304 (20.00s) | 0.050408 (20.00s) |
