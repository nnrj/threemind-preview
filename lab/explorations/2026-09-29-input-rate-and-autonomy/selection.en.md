# Environmental selection: execution schedule

Registered after eight integration trials and before selection outcomes. Seed 9293201 mostly circles in one direction; 9293202 mostly moves slowly or stays near its start. Both have mean region occupancy 0.5 across four counterbalanced starts. Preserve these wiring limitations and seeds.

In each block, share four generation-zero parents and two independent newborn evaluations per parent (positions 0.0625 and 0.5625, 60 s). Mean region-1 occupancy determines external selection for region 0 or region 1; a third arm chooses randomly with `Random(seed+generation)`. Select two parents, two offspring each. Ties use candidate index. Goals never enter stimuli, kernel parameters or output wiring.

Run generations 1 and 2 with four offspring per arm, 60 s of experience, rotating the original four starting positions, and two newborn evaluation copies per candidate. Birth retains structure and resets activity. Never write evaluation learning back to parents. Final champions use four held-out starts 0.1875/0.4375/0.6875/0.9375 crossed with normal/swapped regions (48 instances).

For each final champion and held-out starts 0.1875/0.6875, add sensory replay with ineffective actions, recorded normal-layout actions in a swapped layout, and a region swap at 30 s with current activity controlling actions (36 controls). Record proposed and applied controls separately. Fixed -0.5/0/0.5 physical controls use the same eight start/layout combinations without a Core. Remaining still can score 0.5 across symmetric starts; occupancy alone is not agency.

The exact maximum is 252 Core instances including the eight integration trials: 144 later-generation experience/evaluation instances + 8 generation-zero + 16 shared evaluations + 48 final tests + 36 controls. Reserve 308 slots conservatively, but report actual counts. No mutation, direct weight edits, rewards or unrelated mechanism switches. Stop at registered resource limits, three generations and two blocks.
