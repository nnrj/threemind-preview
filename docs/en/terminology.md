# ThreeMind Terminology (English–Chinese)

[中文](../zh/terminology.md) | [English](terminology.md)

This glossary standardizes ThreeMind writing, translation and code documentation.
Its entries are project working definitions, not final definitions for
biological consciousness, neuroscience or philosophy.

## Writing principle: make the idea understandable before defining it precisely

Added on 2026-09-29 at the researcher's request. Discussion, reports, documentation and interfaces should prefer familiar, established words and preserve existing project terminology. Do not keep inventing names, abbreviations or layers of qualification for a simple phenomenon. Explain what happened and why it matters first; provide parameters, units, equations and scope where reproducibility requires them.

Established words such as energy, memory, association and adaptation may have explicitly defined operational meanings in this project. Their use does not claim every biological or everyday property of the corresponding concept. An imperfect analogy usually calls for a clearer definition, not a new and less understandable label.

Introduce a new term only when existing vocabulary cannot express an important distinction. Explain it in plain language at first use and map it to existing terms and code fields. Conversely, do not give genuinely different mechanisms an indistinguishable name or change a mechanism by renaming it.

### Using “energy”

Earlier documentation already uses energy: see [local inhibition and energy](local-inhibition-energy-and-dynamics.md) and the [model-wide energy account](../zh/v2-energy.md). Continue using that word. When necessary, distinguish energy at a connection from energy for the whole model rather than requiring readers to learn a new phrase for available transmission resources.

| Familiar wording | Exact project meaning and parameter |
| --- | --- |
| Connection energy is finite, consumed and replenished | `depletion_enabled=true` in the continuous-memory research kernel. Each connection's available fraction decreases during transmission and recovers over time; facilitation separately changes utilization. Calling this energy does not identify it with ATP or joules. |
| Remove connection depletion / refill instantly | `depletion_enabled=false`, with `stp_enabled=true`. The available fraction is replenished before every release while facilitation remains active. This is the earlier D=0 intervention, not the researcher's intended unlimited supply. |
| Model-wide energy accounting | The separate `energy_simulation_enabled` and `energy_*` settings govern a whole-model reserve, supply and expenditure; they are not aliases for the connection control. |
| Unlimited or sufficient supply | The external reservoir does not run out; internal capacity and replenishment speed remain finite. Connections still consume and recover energy; inhibition and refractoriness remain. Existing `total_supply_limit=null` removes the external total cap, while `rate_per_s` and `energy_capacity` remain finite. These do not replace local `depletion_enabled=true`. |
| Re-enable energy consumption | Plain wording for the earlier phrase “restore depletion”; it means enabling consumption again, not replenishing energy. |

Whether simulated energy is limited is a research assumption; digital models need not inherit every biological supply constraint. Unlimited simulated supply does not give the host unlimited electricity, memory or compute. Hardware budgets still apply. Energy supply does not itself create sensory input or activation; consciousness death still follows cessation of all activation for the configured interval.

The researcher's analogy is an inexhaustible supply of bread: the person must still eat, and cannot consume unlimited bread when already full. Use unlimited supply in this sense. Earlier reports' D=0 unlimited replenishment means the specific instantaneous-refill control; preserve those records with this clarification, rather than reusing ambiguous wording to remove consumption or recovery.

Local recovery and the whole-model supply are currently separate implementations; increasing the external reserve does not accelerate connection recovery. Continuous self-inhibition and LIF's explicit refractory interval/adaptation current also differ. Familiar language still requires these implementation distinctions to be stated.

## Terms

| English | 中文 | English definition |
| --- | --- | --- |
| artificial consciousness | 人工意识 | ThreeMind's long-term engineering objective; not a currently demonstrated system state. |
| working hypothesis | 工作假设 | A provisional explanatory framework that experiments can support, weaken or revise. |
| continuity | 持续性 | State and environmental contact persist across ticks rather than disappearing after one call. |
| plasticity | 可塑性 | The capacity for node or edge state to change through touch and history. |
| association | 联想 | Activation propagating through existing local connections and reaching neighboring structure with attenuation. |
| direct touch | 直接触达 | A state change at receptor nodes directly caused by an external sensory frame. |
| associative touch | 联想触达 | A usually attenuated state change that reaches a node through local propagation. |
| consolidation | 巩固 | The process by which repeated direct or associative touch makes a connection more resistant to decay. |
| forgetting | 遗忘 | Decline of inadequately maintained edge strength or stability, potentially ending in disconnection. |
| anonymous node | 匿名节点 | A Core node that does not store human-readable input plaintext. |
| literal-character node | 明文字符节点 | A readable experimental baseline using stable character channels; not the standard anonymous mode. |
| node label | 节点标签 | An external display annotation that does not participate in Core dynamics. |
| sensory frame | 感官帧 | An anonymous channel–amplitude pulse collection delivered to the input bus by an adapter. |
| sensory adapter | 感官适配器 | An external module that encodes, filters or projects an external carrier into sensory frames. |
| auditory sensory adapter | 听觉感官适配器 | An adapter that turns uploaded or live physical audio samples into anonymous sensory frames through non-semantic framing and band/waveform encoding. |
| visual sensory adapter | 视觉感官适配器 | An adapter that turns uploaded or live image/video pixels into anonymous sensory frames through deterministic filtering and local retinal patches. |
| ambient sensor adapter | 环境感官适配器 | The adapter that produces a dynamic ambient background field. |
| body adapter | 躯体适配器 | An optional adapter applying sampling, thresholds, adaptation or noise to the ambient field. |
| input bus | 输入总线 | The unified boundary that delivers sensory frames to Core without interpreting carrier semantics. |
| output bus | 输出总线 | The one-way boundary that publishes anonymous activity and topology from Core. |
| passive readout / structural readout adapter | 被动读出器 | An observer that only reads structural output and never writes a signal back into Core. |
| temporal-window convergence readout adapter | 时间区间收敛读出器 | A read-only output adapter anchored to an input envelope that subtracts a pre-stimulus baseline and measures multi-tick duration, integral, inhibition, and convergence. |
| character driver | 字符驱动器 | An output adapter that presents a structural readout as characters using external node labels. |
| acoustic output organ | 声音输出器官 | An output adapter that derives bounded oscillator controls only from anonymous node identity and activation, without reading labels or performing TTS. |
| activation-image projector | 激活图像投影器 | An external experimental output device that deterministically projects anonymous node identity and activation into grayscale pixels. |
| content-addressed media carrier | 内容寻址媒体载体 | An uploaded raw carrier deduplicated by its content checksum, distinct from both anonymous Core frames and ephemeral live raw streams. |
| structural signature | 结构指纹 | An anonymous identifier summarizing node activity, stability, touch counts and internal edges. |
| state signature | 状态指纹 | A quantized single-tick identity for activation, stability and touch state; it is not graph identity. |
| exact structure identity | 精确结构身份 | A structure ID defined by the node-ID set and induced directed-edge set. |
| topology candidate class | 拓扑候选类 | An identity-free grouping candidate that is not a proof of strict graph isomorphism. |
| occurrence identity | 出现身份 | The identity of one observation of a structure at one tick, used to avoid double-counting observation and alert records. |
| repeatable structure | 可重复结构 | A recurring structural activity pattern that meets configured window and threshold criteria. |
| global saturation | 全局饱和 | A state in which most nodes enter one dense connected component, making differentiated new traces difficult to form. |
| local co-activation | 局部共同触达 | The default new-edge policy: form edges only among direct receptors in the same sensory frame. |
| temporal association | 时间关联 | An optional experimental policy that also considers recent shared activity for new-edge formation. |
| spatial embedding | 空间基底 | Internal coordinates, neighborhoods and propagation constraints explicitly enabled by a model package; not ordinary screen layout. |
| spatial neighborhood | 空间邻域 | Local adjacency defined by internal coordinates and a radius. |
| spatial competition | 空间竞争 | An optional local activity inhibition/competition mechanism for spatial-model experiments. |
| topology-local inhibition | 拓扑局部抑制 | Default-on, switchable local negative feedback whose finite potential diffuses over physical adjacency derived from existing directed edges without reversing excitation. |
| inhibitory potential | 抑制势 | An experimental local state generated after activation rise, subject to decay and saturation, that attenuates neighbouring response on a later tick. |
| refractory interval | 不应期 | A short reduction in a recently activated node's responsiveness, currently expressed through retained local inhibition. |
| energy accounting | 能量记账 | A default-off experimental finite-resource scalar that can increase only through initial conditions and external supply; it is not identified with physical energy. |
| host physical telemetry sensor | 宿主物理遥测感官 | A default-on adapter encoding reliably measured host CPU, memory, disk, aggregate network, and power state as anonymous external stimuli; never a Core energy source. |
| process telemetry sensor | 进程遥测感官 | A default-off adapter encoding whole-service CPU, memory, I/O, scheduling and runtime timing as anonymous stimuli; it cannot be attributed to one consciousness in a multi-instance process. |
| per-consciousness runtime physical feedback | 实例物理自反馈 | A default-off adapter that encodes one instance's measured thread CPU time, epoch wall time, and scheduling latency as anonymous input in a later sampling cycle; it never echoes output semantics. |
| dynamics trace | 动力学追踪 | An explicitly enabled, non-feedback per-tick record of node activation, inhibition, support, touch, and topology changes. |
| attention/competition gate | 注意/竞争门 | An optional input-side environmental selection layer; transparent by default and not a built-in survival or reward preference. |
| environmental selector | 环境选择器 | A more precise experimental name for the attention/competition gate, emphasizing external pressure rather than intrinsic cognitive preference. |
| model package | 模型包 | A `.tmind` ZIP package containing a declarative manifest, state, snapshots, portraits and logs, but no executable model code. |
| snapshot | 快照 | A restorable capture of a running consciousness state. |
| portrait | 遗照 | A saved record near death or stopping. |
| instance | 实例 | One independently running consciousness runtime. |
| sensory seed | 感官随机种子 | A recordable random source determining adapter projection or spatial initialization. |
| ablation experiment | 消融实验 | Disabling or replacing one mechanism to measure its causal contribution. |
| temporary functional silencing | 临时功能沉默 | A reversible runtime-boundary intervention on an isolated clone that prevents selected nodes or edges from activation and propagation without becoming model state. |
| structural lesion | 结构移除 | An explicitly audited, irreversible removal of selected nodes or edges, permitted only in an isolated experiment clone. |
| paired control | 配对对照 | A causal design in which control and intervention clones share one captured starting state and receive matched inputs. |
| history dependence | 历史依赖 | Different state or response to the same current input because prior touch order differed. |
| stimulus–structure–output mapping | 刺激—结构—输出映射 | A testable correspondence among external stimulus, internal structural response and external readout. |
| falsifiability | 可证伪性 | The property of stating which observation could weaken or refute a hypothesis. |

## Stimulus carriers and physical references

An element is a value on one anonymous channel. A group is an explicitly declared joint observation. A stimulus carrier contains an element or group; an event stream records their sampling and delivery order. Body senses are peripherals, not Core primitives. Units, coordinates, source identities and observer labels are evidence, not implicit semantic input.
