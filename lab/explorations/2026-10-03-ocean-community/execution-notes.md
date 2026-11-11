# E32 execution notes

## 2026-10-03: registration and apparatus checks

Account usage start17%; available memory about10.8GiB, C9GiB/E82GiB. One simulation worker. Local study project `0b662685-7484-4c20-b1cb-064b53a582e4`; design stored before simulation. Ten focused apparatus/contact tests passed. The blank/experienced/graft births use matched **current** Core reserve, leaving body age and reserve untouched. No Core changes.

The analysis window definitions were written while the first world was still running and before its 120-second result existed. Raw streams and whole-habitat states are retained; no old data scanned or changed.

Full-habitat visual inspection caught a renderer-only periodic-seam bug: independently wrapping capsule endpoints could draw a spurious line across the world. Renderer3 unwraps each capsule around its center and draws boundary copies. It also provides a full-world view with an optional additional focal inset and population/nutrient counts. No simulation state or trajectory was altered. An early preview and initial video remain as development exports; the final catalog identifies the accepted files.

## Orchestration naming correction, before causal forks

Code review found that the single-focal random controller and the whole-population random world both used `gN-random`. The completed-case check would skip the focal case, not overwrite or rerun the whole-population case. The focal key is now `gN-focal-random`; the already loaded initial batch will skip it, so the corrected `forks` command will run these two missing planned cases after that batch. There is no new experimental arm or data conversion. Runner revisions preserve both scripts. Analysis distinguishes the two controls explicitly.

## Whole-habitat finding: capture can follow a birth

In world1, the preselected focal2 captures17 at61.16s, then is captured by60 at62.88s. Inspecting the actual lineage shows60 is its own child, born at62.00s. Ocean/3 protects an immature child from its parent, not the reverse. This consequence must be included in the causal interpretation: the sequence involves feeding, reproduction, body contact and asymmetric protection, not simply an unrelated attacker and a failure to escape. The registered rule remains identical across current arms. The user has been asked whether **future** studies should use bilateral parent/immature-child protection; no decision is assumed and no current protocol is silently changed.

### Later decision, 2026-10-03

The user answered: “后续改为双向亲子保护（建议）” (use bilateral parent–child protection in future studies). This approves protection in **both directions until the child matures**, for subsequent experiments. E32 continues its registered Ocean/3 rule, and its evidence is not rewritten. This is an environmental rule, not a Core preference or an alteration of the current contrasts.

## Completion of the registered18 conditions

All18 cases reached their prescribed horizons,including both focal-random controls,with81.760938 simulation process-minutes. Focal-random0 consumed4 rather than intact3,at82.81 versus26.09 motor energy; focal-random2 survived and consumed5 rather than intact2. These favorable random replacements are retained alongside the population-level Core advantage and selective internal-pathway findings. No old evidence or Core dynamics was changed.

After E32 simulation completion,the environmental protection predicate was extracted without changing legacy Ocean/3 behavior. A declared `bilateral-until-maturity/1` research option in the complete-world state implements the approved future rule. It is absent from E32; E33 disables predation altogether. Twelve focused tests passed for legacy contacts,complete-world preservation,resume and the new opt-in rule. The natural-encounter observer also stopped appending stale pre-death activity after physical loss; this observer fix affects no Core state. E32 already had that freshness check.

The final8 videos and the synchronous three-arm local gallery passed actual encoding/playback checks; desktop1440px and mobile390px have no horizontal overflow or browser errors. A sandbox child-process denial was resolved by the approved isolated headless-browser launch; no user service was changed.
