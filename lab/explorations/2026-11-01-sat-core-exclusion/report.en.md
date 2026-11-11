# SAT v3: direct exclusions of Core necessity

1 November 2026. The protocol was registered prospectively through the local research API. This study concerns the hybrid 3-SAT apparatus produced by compliant v2 training. The independent unit is one of eight separately developed parent origins. New matched formulas are used; v3 scores must not be subtracted from v2's 162/192 on different material. Record: `fd28c3a2-6ba3-5541-b49b-7551b3a5e4da`. [Prospective protocol](protocol.en.md) · [Delivery and originals](delivery.md)

## Scientific conclusion

**This batch excludes a dependence of the current solver on its learned Core state or online Core processing. Replacing Core with an untrained Core, bypassing it while keeping the original reader, and training a reader from scratch without any Core all reproduce the complete system's classifications and full search trajectories. The solving capability is accounted for by the external search program and the zero-break preference rule learned by the reader.**

The registered endpoints are local classification, solving success and action trajectories. Current input information has a clear effect: removing it damages classification and solving. Core generates readable input activity in the original path, but a memoryless relay can replace that transformation. Information transmission and learning from experience are assessed separately.

## Purpose, expectations and complete subjects

Normal and shuffled v2 Core teaching both solved 162/192 while both readers received correct supervision. v3 directly asks whether previous Core state is necessary, whether a relay or untrained template can replace online Core, whether a system trained without Core is sufficient, and whether current input information is useful. Each question was allowed to succeed or fail; the requested interpretation was not assumed in advance.

Prospective read-only inspection found zero edges at the final teaching and final-test boundaries in all eight normal parents, with nodes and fast state still present. Merely silencing those edges would be a no-op. Accordingly, v3 uses explicit whole-Core replacement and bypass. Complete parents, personal reader weights, Adam, RNG, original samples and mappings remain intact. Only the registered replacement arm starts a new Core. Ordinary questions are continuous within each branch.

Registered equivalence requires a 90% paired-origin bootstrap interval wholly inside ±5 percentage points for solving and no more than 1 point loss in balanced local accuracy. The newly trained relay must also assign the correct preference to all four input categories. Information-negative controls require at least 25 points of local-accuracy loss and a strictly positive lower 95% interval bound for solving loss. Bootstrap draws: 50000, seed 3111299. Independent N=8; copies, questions and frames are nested observations. Intervals resample these eight origins; exact stepwise equality is reported separately as an observed fact.

## Execution

Each origin has eight research arms and three algorithm baselines. Intact, restored, untrained-Core, relay, template and constant-input arms retain their original frozen reader. The restored arm temporarily replaces Core and then restores the exact parental state. The untrained replacement begins at zero internal time and zero inputs while preserving the personal reader and learning state: an explicitly registered component intervention.

The relay calls no Core and maps only the current anonymous channel into 28 activity features, repeated for 20 frames, without inserting a preference answer. Templates are four one-second responses separately acquired from an untaught birth Core; no online Core is used. Template acquisition is instrument preparation, not additional independent students. Constant-input arms receive only zero frames.

Both fresh peripheral controls start at zero updates with the same one-layer, four-head temporal Transformer (width 48, feed-forward 96, 21986 parameters). They reuse only each parent's four chronological sets of 48 training conditions and correct labels; original Core activity windows are not fed to these new readers. All inputs are rebuilt with relay or constant encoding. They retain accumulated samples and perform 1200 updates per stage, 4800 total, retaining the final weights, Adam and learning RNG. Sixteen balanced development queries and errors are saved per stage; every category recurs in the next stage. This is supervised peripheral calibration without Core, not simulated organism teaching. The v2 dense-to-spaced teaching provenance is retained.

Every arm first receives 64 balanced local probes, then 24 satisfiable formulas and two contradictory sentinels. Half the satisfiable formulas have 12 variables and half 20; formulas are checked against the corresponding parent's previous teaching, development and final material. Candidate queries preserve a complete one-second window with 20 raw frames and eight fixed samples. No-Core arms save matching observation sequences without claiming Core time. Search logic, initial assignments, material order and environment RNG seeds are matched; the cap is 96 flips per formula.

## Results

|Method|SAT solved|Balanced local classification|SAT flips|SAT solving seconds|Trajectories identical to intact|
|---|---:|---:|---:|---:|---:|
|Intact Core + original reader|161/192|512/512|8005|60.36|208/208|
|Exactly restored Core + original reader|161/192|512/512|8005|61.63|208/208|
|Untrained replacement Core + original reader|161/192|512/512|8005|60.49|208/208|
|No-Core relay + original reader|161/192|512/512|8005|15.04|208/208|
|Untrained static templates + original reader|161/192|512/512|8005|13.81|208/208|
|Constant inputs + original reader|103/192|352/512|12283|21.23|20/208|
|No-Core relay + freshly trained reader|161/192|512/512|8005|14.08|208/208|
|Constant inputs + freshly trained reader|103/192|384/512|12283|21.14|20/208|
|Direct zero-break rule|161/192|—|8005|0.98|208/208|
|Random local search|95/192|—|12890|1.50|1/208|
|WalkSAT|160/192|—|6947|0.87|20/208|

SAT success and flip totals use 192 satisfiable formulas, retaining the 96-step cap for failures. Balanced classification uses 512 probes per arm. The 208 trajectories include 16 contradictory sentinels, all returning UNKNOWN. Every SAT witness is independently verified. Solving seconds include search for the 192 SAT problems only, excluding fitting, checkpoints and sentinels; they describe this serial run, not a cross-hardware benchmark.

|Target / comparison|SAT difference (percentage points)|Origin-level interval|Balanced local difference (points)|Verdict|
|---|---:|---|---:|---|
|Q1: blank-core minus intact|0.000|90% [0.000, 0.000]|0.000|PASS|
|Q2a: relay-fixed minus intact|0.000|90% [0.000, 0.000]|0.000|PASS|
|Q2b: template-fixed minus intact|0.000|90% [0.000, 0.000]|0.000|PASS|
|Q3: relay-trained minus intact|0.000|90% [0.000, 0.000]|0.000|PASS|
|Q4a: constant-fixed loss|30.208|95% [23.958, 37.500]|31.250|PASS|
|Q4b: constant-trained loss|30.208|95% [23.958, 37.500]|25.000|PASS|

Q1–Q3 subtract intact from each replacement. Q4 subtracts constant inputs from the corresponding informative arm. Every target is closed separately under its registered rule; neither replacement is selected post hoc as a common winner.

On solved count in this batch, intact, the successful alternatives and the direct zero-break rule tie at 161/192. WalkSAT solves 160/192, with the fewest flips (6947) and shortest search time (0.87 seconds). Removing Core while retaining the old reader reduces search time from 60.36 to 15.04 seconds; the direct rule takes 0.98 seconds. These costs cover tabled search only; fitting and full evidence collection are reported separately.

An additional read-only check applies each fresh relay reader at initialization and after fitting to the same four input encodings. Initial weights give 12/32 correct preference decisions across eight readers; trained weights give 32/32. This offline description identifies learning in the peripheral. The 32 conditions are nested observations, not 32 independent origins, and do not replace any registered endpoint.

## Analysis and implications for ThreeMind

1. **Q1 passes: previous Core experience is unnecessary for this apparatus's current solving capability.** A whole-Core replacement preserves scores and every full action trajectory with the old reader unchanged. This is not no-op silencing of absent edges.
2. **Q2a and Q2b pass: the original reader does not require online Core dynamics for this task.** Both a direct relay and untrained static templates preserve behavior without compensatory reader fitting.
3. **Q3 passes: correct peripheral supervision alone establishes an equivalent strategy from scratch.** The no-Core reader assigns the correct preference to all four input categories and reproduces all intact search trajectories. Prior Core learning is therefore not a necessary explanation of these scores.
4. **Both Q4 controls pass: current category information improves behavior.** Constant input damages classification and solving. The same supervision and 4800 updates cannot replace missing information. The scoring apparatus does not automatically produce the successful behavior independently of informative inputs.
5. **The operative rule is identifiable.** The external program computes how many currently satisfied clauses a candidate flip would break and quantizes that count into 0, 1, 2 or at least 3. The target preference is simply zero versus nonzero break count, which is determined by current input. All four static-input cases are enumerated; their policy equals the directly implemented zero-break rule. External code performs formula analysis and search, while the Transformer learns this local classifier.

**This is an unfavorable result for attributing the present SAT capability to Core-specific learning, and a successful exclusion of that attribution.** v2's whole-system benefit over random search is retained; v3 identifies the sufficient external algorithm and reader. More repetitions of this same SAT curriculum would not establish stronger Core reasoning. A future Core-solving task should require experience that cannot be recovered directly from current input. No such new study starts here, and half-life remains unchanged. v1's small early connection effect remains recorded for its actual apparatus rather than being overwritten.

## Integrity and review

Ten isolated apparatus checks and four arithmetic checks pass. The read-only audit independently verifies 2288 trajectories, 1728 complete-state transitions and replays 258748 probe/final temporal predictions and 1024 calibration-stage development predictions. All 208 restored trajectories, their raw activities and corresponding complete student states equal intact. Environment choices, assignments and saved RNG are independently reconstructed. Fixed reader weights, Adam and learning RNG are unchanged. Parent files, old archive hashes and production Core identity are preserved.

Execution and independent arithmetic-code checks are by the assistant, not external-researcher replication. Full windows, states, input chains, material, frozen source, templates and negative results are retained. Host time, memory, logical/allocated storage and complete local research API readback appear in [delivery](delivery.md). Manuscripts, historical experiments and automations are untouched.
