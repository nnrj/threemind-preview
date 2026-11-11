# 网络设备：匿名载体、输出订阅与独立授权

网络设备是 ThreeMind 的外部运行时工具，不是内核的一部分。它把传感器、机器人或模拟器测得的数值递送给指定意识，并可读取已提交的匿名输出。默认物理环境、内核时间机制和可塑规则不被网络协议改变。

在意识详情的 **感官与输入 → 网络设备** 添加绑定。为设备分别选择匿名输入、匿名输出、临时输入调制、外部能量供给权限。默认只启用前两项，能量供给还要求模型本身启用能量记账。高级参数默认折叠，所有参数都有图形控件。权限和凭据属于部署；稳定接线可单独导出，与对应模型一起保存。

## 凭据与数据边界

- 每个绑定只授权一个项目中的一个意识。凭据由随机 256 位材料生成，仅创建和轮换时返回一次；数据库仅保存 SHA-256 摘要。它不能作为平台登录凭据使用。
- 每次数据请求、输出读取和订阅轮询都检查绑定状态、有效期、凭据版本以及签发者当前是否仍启用并有项目写权限。平台查看者不能创建设备授权。
- 编辑绑定会结束其当前会话；轮换还使旧凭据立即失效，新凭据有效期 30 天。绑定标识保持不变，接线不会因换密钥漂移。停用不会删除历史证据。
- HTTP 使用 `Authorization: Bearer <设备凭据>` 请求头；WebSocket 在首条 hello 中携带凭据。WebSocket 不接受查询参数。浏览器来源必须在部署允许列表中。
- 工作站默认只监听环回地址；跨设备访问使用带平台身份认证的 server 部署，并在代理启用 TLS、明确主机与来源。不要为了设备接入把匿名工作站直接暴露到公网。

数据库 schema 11 在现有 PostgreSQL 内增加 `device_bindings`、`device_sessions`、`device_packets` 三张表；它们具有项目行级权限及项目／意识／会话外键。感官原件、编码帧、命令、实际递送继续使用现有证据表，没有新建第二个数据库或 MQ。

## 接线与信号

协议名为 `threemind-network/2`。旧 network/1 的字符串通道、共享主机令牌、tick 超时和绕过过滤字段不直接沿用：新协议把设备身份、原始时钟和端口能力明确化。

输入是 1～256 个按时间排序的帧。远端通道号为无符号 32 位整数，幅值是 `[-1,1]` 内的有限数，强度范围沿用 Core 的 `[0,100]`。重复通道、重复 JSON 键、非有限数、逆序时间及未知字段整包拒绝，不截断或静默纠正。

有符号测量被拆为正／负极性的非负受体。接线字节串为 `threemind-network/2`、零分隔符、4 字节大端感官种子、16 字节稳定接线 UUID、4 字节大端远端通道号和 1 字节极性。BLAKE2s 的 4 字节摘要按大端转为本地通道号。零值不发脉冲；极少数哈希碰撞按首次出现顺序合并幅值并钳制到 1，转换映射和规则都保留在配置证据中。这只是传感接线，不指定节点意义或人为添加连接。

schema 41 为设备绑定增加不可变的 `wiring_id`。旧设备从原绑定 UUID 原样补入，不更换节点映射。新建接线初始使用新绑定的 UUID；之后在其他运行或部署中复用时，绑定和凭据重新生成，`wiring_id` 保持原值。一个意识最多绑定一次同一接线，停用后仍保留该身份，应编辑或轮换已有绑定。所有者和研究者可绑定，项目查看者可读取清单，但不能以清单取得设备权限。

匿名输入通过稳定身份编码；已获单独授权的临时调制与能量端口也以 `remote:{wiring_id}` 标识同一控制来源，防止换凭据后误叠加第二个调制器。原始审计仍保留真实 `device_id`／会话／序号与 `wiring_id`，按凭据绑定查询的历史仍分开。已接收载体冻结编码，已经排入内核的刺激不会因换凭据被重新编码。

## 保存、复用与独立部署接线

设备工具栏的 **导出接线清单** 下载 `network-<UUID>.wiring.json`。在另一运行的添加设备窗口中选择 **从已有模型复用接线**，选取文件并查看校验后的身份与种子，再明确创建独立凭据。编辑界面中的接线编号只读；若要进行重新接线实验，应创建新的感官接线。

清单协议 `threemind.network-wiring/1` 只包含 `schema`、编码 `protocol`、`wiring_id`、`sensory_seed` 和 `sha256`。摘要是前四项按键排序、无多余空白的 UTF-8 JSON 的 SHA-256，用于检测损坏，不是授权签名。未知字段、重复 JSON 键、损坏摘要、不支持的编码及大于 16 KiB 的清单拒绝；创建时还会再次验证，不能依赖网页先点过校验。

先导入／恢复对应模型，再复用清单。模型里的 runtime profile 保存感官种子；接线文件的种子必须一致，系统不会为通过导入偷偷修改它。清单与模型分别导出，普通 `.tmind`／JSON 模型没有被加入密码、地址或运行中的硬件会话，也不会仅因为新增设备就被重写。模型本体依然可以由 Core 独立运行；要恢复某个远程感官的接线，还需持有对应清单。

此清单覆盖已有 `network/2` 数值通道编码，不宣称包含所有模拟世界、身体、相机或机器人校准配置。部署者仍需保存真实设备的单位、校准和采集时钟；仅节点映射一致不等于物理刺激一致。`network/2` 本身不在运行时安装任意插件代码。

平台接口：`GET /api/v2/projects/{project}/runs/{run}/devices/{device}/wiring` 下载清单；`POST .../devices/wiring/validate` 接收原始 JSON 进行校验；创建设备时可在原请求增加 `wiring` 对象。清单不是模型文件，不能投给模型导入接口。

`src/threemind_runtime/network.py` 的 `read_message`、`decode_frames` 不依赖 FastAPI 或数据库。独立部署可以使用同一编码器，再通过本地 InputBus 或 Core 接口递送：

```python
from threemind_core import Stimulus
from threemind_runtime import create_engine
from threemind_runtime.network import decode_frames

engine = create_engine()
frames, proof = decode_frames(
    [{"time_us": "1000", "channels": [[12, -0.7], [15, 0.4]]}],
    seed=20260724,
    wiring_id="7b55b7d2-446c-45b8-b720-d411bb73e9c5",
)
for frame in frames:
    engine.inject(Stimulus.from_dict(frame))
engine.advance_to(2000)
```

这里的 UUID 是示例仪器接线身份。实际独立部署可读取从 Lab 导出的清单，继续使用相同编码器：

```python
from pathlib import Path
from threemind_runtime.network_wiring import read_wiring

wiring = read_wiring(Path("device.wiring.json").read_bytes())
frames, proof = decode_frames(
    [{"time_us": "1000", "channels": [[12, -0.7], [15, 0.4]]}],
    seed=wiring["sensory_seed"], wiring_id=wiring["wiring_id"],
)
```

时间必须相对于实际恢复后的模型状态选择，不能把示例的 1000 μs 倒填到已越过该时刻的脑中。纯 Runtime 编码器和清单读取不依赖 Lab 或数据库；上述用法不提供 Lab 的持久化证据服务，保存何种证据由宿主决定。

## 两种时间声明

所有时间单位为微秒，线上建议使用十进制整数字符串；不能用渲染帧号当时间。`source_clock.description` 可记录仪器计时器及校准说明，不进入 Core。

**simulation**：`frames[].time_us` 是绝对模拟时间，`capture_us` 为 0。适合加速模拟、训练或暂停时预先排入输入。时间不得早于已提交模型时间，且不得超过未来预算；执行到该命令时，Runtime 还会按实际内核时间再次检查。迟到就拒绝，不倒填。

**device**：只用于正在运行的 realtime 意识。采集会话以第一个输入包的 `capture_us=0` 为起点，随后保持原始单调时间。帧时间是包内相对偏移。在第一个输入命令实际处理时，以当前内核时间与绑定提前量建立唯一原点：

$$
t_0=t_{\mathrm{core,first\ processing}}+L,\qquad
t_{\mathrm{delivery}}=t_0+c_{\mathrm{packet}}+\Delta t_{\mathrm{frame}}.
$$

原点与对应 Core 状态在同一个检查点事务保存，也在 Runtime 上下文中恢复；事务失败不会只保存一半。后续数据保持这个原点，不根据网络延迟反复挪动时间。采集间隔和传输延迟不同，提前量也不是硬件同步校准保证。若设备持续落后，应重新建立采集会话或调整提前量，并记录这一变化。

网络断开本身可重连；必须带回原 session_id 和相同 source_clock，使用服务器返回的下一序号。模型暂停、执行完成、失败或 worker 租约接管都会中断物理采集会话。恢复后新建会话，不重新绑定旧时钟。已排入 Core 的刺激仍保留原承诺时间；尚未处理的旧会话包会留下拒绝证据。

调制与能量端口的 `delay_us` 以命令实际处理时的 Core 时间为基准，且遵守 Core 最小延迟；它们不假装与同包传感器硬件同步。实际排入时间和事件标识可查。调制持续期使用模拟微秒，见[输入注意](v2-attention.md)；能量定义见[能量与供给](v2-energy.md)。

## HTTP 与 WebSocket 示例

页面提供具体连接地址。下文 `BASE` 为 `/api/v2/network/{project}/{run}/{device}`。

HTTP `POST BASE/sessions`，在请求头放置设备凭据：

```json
{"protocol":"threemind-network/2","type":"hello","source_clock":{"mode":"simulation","description":"显式模拟器时钟"}}
```

返回 `ready` 和会话 id、下一序号、时间原点及状态。重连在 hello 中增加 `session_id`。HTTP 的 hello 正文不接受 token。

WebSocket 连接 `BASE/ws`，在 5 秒内发送相同 hello，并增加 `token` 字段。成功后可在同一连接发送以下消息；HTTP 则 `POST BASE/sessions/{session}/packets`：

```json
{"protocol":"threemind-network/2","type":"input","sequence":"0","capture_us":"0","frames":[{"time_us":"1000","channels":[[12,-0.7],[15,0.4]],"intensity":1}]}
```

这是模拟时钟示例，模型若已越过 1000 μs 必须选择新的未来时间。物理采集模式的首帧可用 `time_us="0"`，后续包递增 `capture_us`。

```json
{"protocol":"threemind-network/2","type":"modulation","sequence":"1","delay_us":"1000","value":{"gain":0.8,"budget_multiplier":1,"competition_enabled":false,"ttl_us":500000}}
```

```json
{"protocol":"threemind-network/2","type":"energy","sequence":"2","delay_us":"1000","value":{"amount":0.05}}
```

服务端只接受精确的下一序号。相同序号、相同规范 JSON 内容的重试返回原有回执；同序号换内容或跳号则拒绝。回执丢失时重发原包，不换序号。接收事务同时保存数据包、原始载体／端口命令及下一序号；失败不会消耗序号，也不会留下半包。回执中的 `accepted` 只证明数据库已接收，不代表已经影响模型。

WebSocket 支持一次读取和持续订阅：

```json
{"protocol":"threemind-network/2","type":"output","after_revision":"12"}
```

```json
{"protocol":"threemind-network/2","type":"subscribe","interval_ms":1000}
```

```json
{"protocol":"threemind-network/2","type":"unsubscribe"}
```

订阅按宿主时间检查最新已提交版本，版本没有变化时不重复发送；它不改变模型采样节奏。`skipped_revisions` 表明相对于上次推送跳过多少提交版本。输出带 `state_hash`、时间、总节点／连接数与 `complete`。显示容量或 128 KiB 上限可能使投影不完整，完整证据不会因此删除。

HTTP 对应 `GET BASE/sessions/{session}/output?after_revision=12`。WebSocket 的 `close` 消息或 HTTP `POST .../{session}/close` 显式结束会话；直接断开连接保留可重连会话。

## 查看、核对与导出

页面按设备、会话、包序号分页，区分接收、排入内核、全部帧处理及拒绝。点击载体证据可同时看到原始远端包、极性接线映射、编码帧、实际递送时间和输入注意账本。输入记录的完整 CSV／JSONL 导出沿用数据库游标，不把当前页当成全量数据。

设备也能凭当前有效凭据查询自己的证据：

| 设备 HTTP 接口 | 用途 |
| --- | --- |
| `GET .../sessions/{session}/receipts?after=-1&limit=30` | 包回执及当前实际处理结果；序号游标，最多 100 行 |
| `GET .../sessions/{session}/evidence/{envelope}?after=-1&limit=20` | 本设备在此会话提交的原件、配置及实际帧；最多 256 帧 |
| `GET .../sessions/{session}/observations?after_us=0&limit=50` | 已获输出权限的完整历史采样指标；最多 200 行，按返回 next_us 继续 |

历史接口可以核对已结束会话，但凭据本身仍须有效。它们返回当下数据库快照；若要复现实验时刻，平台的检查点输入证据导出可按历史提交版本还原递送状态。观测采样不是连续的完整内核事件流；只有启用详细追踪且覆盖的时间段才有更细事件证据。

## 容量与明确边界

默认每设备每秒 40 次请求、每包 256 个通道条目、提前 500000 μs、未来预算 10000000 μs、输出 256 节点／512 连接。图形配置可调整；每个绑定最多 8 个同时活动会话，每个意识最多保留 256 个绑定。接收还受该意识 InputBus 预算限制，所有设备与手动输入共享预算。

每进程最多 32 条设备 WebSocket；接收 128 KiB，ASGI 队列最多 4 条，输出发送超时 5 秒。订阅间隔可选 100～30000 ms，也消耗设备请求预算。预算冲突会报告并停止该订阅；调整后可重新订阅。慢消费者不积累无限显示历史，断开不会抹掉数据库证据。外部 ASGI 启动器须设置同等 `ws_max_size`／`ws_max_queue`；项目 CLI 已设置。

本批没有把器官声波／像素打包成网络串流，也没有实现分布式硬件时钟校准或无界设备吞吐。原有远端匿名图输出已恢复；连续声画器官仍使用[器官输出服务](v2-continuous-output.md)，真实音画输入使用[连续采集服务](v2-live-capture.md)。通用宿主设备发现、更多专用设备协议和公开部署配额继续按[完整性清单](v2-capability-restoration.md)推进。
