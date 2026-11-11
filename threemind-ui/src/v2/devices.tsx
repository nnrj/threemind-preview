import { t, locale } from "./i18n";
import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, post, type Run, timeLabel } from "./api";
import {
  Button,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Modal,
  useWorkspace,
} from "./ui";

const permissions = {
  input: ["匿名刺激输入", "设备只能递送数值载体，不能指定连接或语义。"],
  output: ["读取意识输出", "允许读取此意识的匿名活动、连接投影和历史观测。"],
  modulation: ["临时输入调制", "允许请求有期限的增益、通道预算与竞争开关。"],
  energy: ["外部能量供给", "需要意识同时启用能量记账；供给逐次留下证据。"],
} as const;
const numbers = {
  packets_per_second: [
    "每秒请求预算",
    1,
    1000,
    "同一设备的所有连接共享此预算，包含输出查询。",
  ],
  maximum_channels: [
    "单包通道条目上限",
    1,
    4096,
    "累计所有帧中的通道条目；超出时整包不接收。",
  ],
  lead_us: [
    "采集提前量（μs）",
    1000,
    10000000,
    "首包处理时建立时间原点，为传输和调度留出余量。",
  ],
  lookahead_us: [
    "未来时间预算（μs）",
    1000,
    100000000,
    "最多允许提前排入的模拟时间，不能小于采集提前量。",
  ],
  output_nodes: [
    "输出节点上限",
    0,
    4096,
    "仅影响设备收到的显示投影，不删除内核节点或证据。",
  ],
  output_edges: [
    "输出连接上限",
    0,
    8192,
    "输出还受 128 KiB 传输上限约束，并明确报告是否完整。",
  ],
} as const;
type Config = Record<keyof typeof permissions, boolean> &
  Record<keyof typeof numbers, number>;
type Device = {
  id: string;
  wiring_id: string;
  name: string;
  enabled: boolean;
  configuration: Config;
  expires_at: string;
  token_generation: number;
};
type Wiring = {
  schema: "threemind.network-wiring/1";
  protocol: "threemind-network/2";
  wiring_id: string;
  sensory_seed: number;
  sha256: string;
};
const defaults: Config = {
  input: true,
  output: true,
  modulation: false,
  energy: false,
  packets_per_second: 40,
  maximum_channels: 256,
  lead_us: 500000,
  lookahead_us: 10000000,
  output_nodes: 256,
  output_edges: 512,
};
const statusName: Record<string, string> = {
  active: "可重连",
  closed: "设备已关闭",
  interrupted: "采集中断",
  revoked: "授权已更新",
};
const deliveryName: Record<string, string> = {
  accepted: "等待排入内核",
  scheduled: "已排入内核",
  completed: "全部帧已处理",
  rejected: "未递送",
};
const reasons: Record<string, string> = {
  credential_rotated: "凭据已轮换",
  binding_edited: "设备绑定已修改",
  device_closed: "设备主动关闭",
  worker_replaced: "工作进程接管了执行",
  worker_failed: "工作进程执行失败",
  paused: "意识已暂停",
  completed: "执行时段已完成",
  cancelled: "意识已终止",
  dead: "内部活动已耗尽",
};

function DeviceForm({
  device,
  base,
  finish,
  close,
}: {
  device: Device | null;
  base: string;
  finish: (result: { device: Device; token?: string }) => void;
  close: () => void;
}) {
  const [name, setName] = useState(device?.name ?? "外部感知设备"),
    [config, setConfig] = useState<Config>({
      ...(device?.configuration ?? defaults),
    }),
    [enabled, setEnabled] = useState(device?.enabled ?? true),
    [days, setDays] = useState(30),
    [wiringMode, setWiringMode] = useState("new"),
    [wiring, setWiring] = useState<Wiring | null>(null),
    [reading, setReading] = useState(false),
    [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false);
  const readGeneration = useRef(0);
  return (
    <form
      className="device-form"
      onSubmit={async (e) => {
        e.preventDefault();
        setError(null);
        if (!device && wiringMode === "reuse" && (!wiring || reading)) {
          setError(t("请先选择并校验对应模型的接线清单。"));
          return;
        }
        if (config.lead_us > config.lookahead_us) {
          setError(t("采集提前量不能大于未来时间预算。"));
          return;
        }
        setBusy(true);
        try {
          const result = await api(
            `${base}/devices${device ? `/${device.id}` : ""}`,
            {
              method: device ? "PUT" : "POST",
              body: JSON.stringify({
                name,
                configuration: config,
                ...(device
                  ? { enabled }
                  : {
                      lifetime_days: days,
                      ...(wiringMode === "reuse" ? { wiring } : {}),
                    }),
              }),
            },
          );
          finish(result);
        } catch (e) {
          setError(e);
        } finally {
          setBusy(false);
        }
      }}
    >
      <Field label={t("设备名称")}>
        <input
          aria-label={t("设备名称")}
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          maxLength={120}
        />
      </Field>
      {device ? (
        <Field label={t("稳定接线编号")}>
          <input
            aria-label={t("稳定接线编号")}
            readOnly
            value={device.wiring_id}
          />
          <small>{t("创建后固定。修改权限、名称或凭据会保留原有接线。")}</small>
        </Field>
      ) : (
        <fieldset className="device-wiring">
          <legend>{t("感官接线")}</legend>
          <Field label={t("接线方式")}>
            <select
              aria-label={t("接线方式")}
              value={wiringMode}
              onChange={(event) => {
                readGeneration.current += 1;
                setWiringMode(event.target.value);
                setWiring(null);
                setReading(false);
                setError(null);
              }}
            >
              <option value="new">{t("创建新的感官接线")}</option>
              <option value="reuse">{t("从已有模型复用接线")}</option>
            </select>
          </Field>
          {wiringMode === "reuse" ? (
            <>
              <Field label={t("接线清单文件")}>
                <input
                  aria-label={t("接线清单文件")}
                  type="file"
                  accept=".json,application/json"
                  disabled={busy}
                  onChange={async (event) => {
                    const file = event.target.files?.[0];
                    const generation = ++readGeneration.current;
                    setWiring(null);
                    setError(null);
                    setReading(!!file);
                    if (!file) return;
                    try {
                      if (file.size > 16384)
                        throw new Error(t("接线清单不能超过 16 KiB。"));
                      const result = await api<{
                        valid: boolean;
                        wiring: Wiring;
                      }>(`${base}/devices/wiring/validate`, {
                        method: "POST",
                        body: await file.text(),
                      });
                      if (generation === readGeneration.current)
                        setWiring(result.wiring);
                    } catch (error) {
                      if (generation === readGeneration.current)
                        setError(error);
                    } finally {
                      if (generation === readGeneration.current)
                        setReading(false);
                    }
                  }}
                />
              </Field>
              {reading && <p role="status">{t("正在校验接线…")}</p>}
              {wiring && (
                <>
                  <Field label={t("稳定接线编号")}>
                    <input
                      aria-label={t("稳定接线编号")}
                      readOnly
                      value={wiring.wiring_id}
                    />
                  </Field>
                  <p role="status">
                    {t("接线校验通过，感官种子为 {seed}。", {
                      seed: wiring.sensory_seed,
                    })}
                  </p>
                </>
              )}
              <small>
                {t(
                  "先导入或恢复对应模型，再复用其接线清单。系统会校验感官种子；同一意识不能重复绑定同一接线。",
                )}
              </small>
            </>
          ) : (
            <small>
              {t(
                "新接线分配新的感官身份。部署已经学会的感官时，请复用原接线。",
              )}
            </small>
          )}
        </fieldset>
      )}
      <fieldset className="device-permissions">
        <legend>{t("设备权限")}</legend>
        {(
          Object.entries(permissions) as [
            keyof typeof permissions,
            readonly [string, string],
          ][]
        ).map(([key, [label, hint]]) => (
          <label key={key}>
            <input
              type="checkbox"
              checked={config[key]}
              onChange={(e) =>
                setConfig({ ...config, [key]: e.target.checked })
              }
            />
            <span>
              {t(label)}
              <small>{t(hint)}</small>
            </span>
          </label>
        ))}
      </fieldset>
      {device ? (
        <label className="check">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
          />
          {t("启用此设备绑定")}
        </label>
      ) : (
        <Field label={t("凭据有效期（天）")}>
          <input
            aria-label={t("凭据有效期（天）")}
            type="number"
            min={1}
            max={365}
            step={1}
            required
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          />
        </Field>
      )}
      <details className="device-limits">
        <summary>{t("高级参数：时间、输入预算与输出容量")}</summary>
        <div className="form-grid">
          {(
            Object.entries(numbers) as [
              keyof typeof numbers,
              readonly [string, number, number, string],
            ][]
          ).map(([key, [label, min, max, hint]]) => (
            <Field key={key} label={t(label)}>
              <input
                aria-label={t(label)}
                type="number"
                min={min}
                max={max}
                step={1}
                required
                value={config[key]}
                onChange={(e) =>
                  setConfig({ ...config, [key]: Number(e.target.value) })
                }
              />
              <small>{t(hint)}</small>
            </Field>
          ))}
        </div>
      </details>
      {device && (
        <p className="notice">
          {t(
            "保存后，已有会话结束。设备使用当前凭据重新连接；尚未处理的包可能被拒绝，已排入内核的刺激继续遵守原时间戳。",
          )}
        </p>
      )}
      <ErrorBox error={error} />
      <div className="dialog-actions">
        <Button type="button" onClick={close}>
          {t("取消")}
        </Button>
        <Button variant="primary" disabled={busy || reading}>
          {busy ? t("保存中…") : device ? t("保存设备配置") : t("创建设备绑定")}
        </Button>
      </div>
    </form>
  );
}

export default function DevicePanel({
  base,
  run,
  inspect,
}: {
  base: string;
  run: Run;
  inspect: (id: string) => void;
}) {
  const cache = useQueryClient(),
    { project } = useWorkspace();
  const canWrite = project?.role === "owner" || project?.role === "researcher";
  const [chosen, setChosen] = useState(""),
    [session, setSession] = useState(""),
    [sessionPages, setSessionPages] = useState<(string | null)[]>([null]),
    [pages, setPages] = useState(["-1"]),
    [form, setForm] = useState<Device | "new" | null>(null),
    [secret, setSecret] = useState<{ device: Device; token: string } | null>(
      null,
    ),
    [rotate, setRotate] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(null),
    [copied, setCopied] = useState(false);
  const listing = useQuery<Device[]>({
    queryKey: ["devices", base],
    queryFn: () => api(`${base}/devices`),
    refetchOnWindowFocus: false,
  });
  const device =
    listing.data?.find((d) => d.id === chosen) ?? listing.data?.[0];
  const sessions = useQuery<any>({
    queryKey: ["device-sessions", base, device?.id, sessionPages.at(-1)],
    queryFn: () =>
      api(
        `${base}/devices/${device!.id}/sessions${sessionPages.at(-1) ? `?before=${sessionPages.at(-1)}` : ""}`,
      ),
    enabled: !!device,
    refetchInterval: run.status === "running" ? 5000 : false,
    refetchOnWindowFocus: false,
  });
  const current =
    sessions.data?.rows.find((s: any) => s.id === session) ??
    sessions.data?.rows[0];
  const packets = useQuery<any>({
    queryKey: ["device-packets", base, device?.id, current?.id, pages.at(-1)],
    queryFn: () =>
      api(
        `${base}/devices/${device!.id}/packets?session_id=${current.id}&after=${pages.at(-1)}`,
      ),
    enabled: !!current,
    refetchInterval: run.status === "running" ? 5000 : false,
    refetchOnWindowFocus: false,
  });
  const network = device
    ? `${location.origin}/api/v2/network/${project?.id}/${run.id}/${device.id}`
    : "";
  async function refresh() {
    await listing.refetch();
    await sessions.refetch();
    if (current) await packets.refetch();
  }
  async function completed(result: { device: Device; token?: string }) {
    setForm(null);
    setChosen(result.device.id);
    setSession("");
    setSessionPages([null]);
    setPages(["-1"]);
    setCopied(false);
    if (result.token) setSecret({ device: result.device, token: result.token });
    await cache.invalidateQueries({ queryKey: ["devices", base] });
    await cache.invalidateQueries({ queryKey: ["device-sessions", base] });
    await cache.invalidateQueries({ queryKey: ["sensory", run.id] });
    await cache.invalidateQueries({ queryKey: ["adapter-bindings", base] });
  }
  return (
    <section
      className="panel resource-panel device-panel"
      role="region"
      aria-label={t("网络设备")}
    >
      <div className="panel-heading">
        <div>
          <h2>{t("网络设备")}</h2>
          <p>
            {t(
              "把外部传感器、模拟器或机器人接入此意识，并核对每一包的接收与递送结果。",
            )}
          </p>
        </div>
        <div className="button-row">
          <Button onClick={refresh}>{t("刷新设备记录")}</Button>
          <Button
            variant="primary"
            disabled={!canWrite}
            onClick={() => setForm("new")}
          >
            {t("添加网络设备")}
          </Button>
        </div>
      </div>
      <ErrorBox
        error={error ?? listing.error ?? sessions.error ?? packets.error}
      />
      {listing.isPending ? (
        <Loading />
      ) : !device ? (
        <Empty
          title={t("尚未绑定网络设备")}
          detail={t(
            "为每台设备选择需要的权限并生成独立凭据，再由设备主动连接。",
          )}
        />
      ) : (
        <>
          <div className="device-toolbar">
            <Field label={t("已绑定设备")}>
              <select
                aria-label={t("已绑定设备")}
                value={device.id}
                onChange={(e) => {
                  setChosen(e.target.value);
                  setSession("");
                  setSessionPages([null]);
                  setPages(["-1"]);
                }}
              >
                {listing.data?.map((d) => (
                  <option value={d.id} key={d.id}>
                    {d.name}
                    {d.enabled ? "" : t(" · 已停用")}
                  </option>
                ))}
              </select>
            </Field>
            <Button disabled={!canWrite} onClick={() => setForm(device)}>
              {t("编辑设备配置")}
            </Button>
            <Button disabled={!canWrite} onClick={() => setRotate(true)}>
              {t("轮换凭据")}
            </Button>
            <a
              className="button"
              href={`/api/v2${base}/devices/${device.id}/wiring`}
            >
              {t("导出接线清单")}
            </a>
          </div>
          <div className="device-summary">
            <span className={`badge ${device.enabled ? "running" : "paused"}`}>
              {device.enabled ? t("绑定启用") : t("绑定停用")}
            </span>
            <span>
              {t("凭据版本 ")}
              {device.token_generation}
            </span>
            <span>
              {t("到期")}{" "}
              {new Date(device.expires_at).toLocaleString(locale(), {
                hour12: false,
              })}
            </span>
          </div>
          <div className="device-scopes">
            {Object.entries(permissions).map(([k, [label]]) => (
              <span
                className={
                  device.configuration[k as keyof typeof permissions]
                    ? "enabled"
                    : ""
                }
                key={k}
              >
                {t(label)}：
                {device.configuration[k as keyof typeof permissions]
                  ? t("允许")
                  : t("未授权")}
              </span>
            ))}
          </div>
          <details className="device-connection">
            <summary>{t("连接地址与协议")}</summary>
            <Field label={t("稳定接线编号")}>
              <input
                aria-label={t("稳定接线编号")}
                readOnly
                value={device.wiring_id}
              />
              <small>
                {t(
                  "清单保存匿名接线与感官种子，不包含设备凭据、连接地址或脑状态。请与对应模型一同保存。",
                )}
              </small>
            </Field>
            <Field label={t("设备 HTTP 地址")}>
              <input
                aria-label={t("设备 HTTP 地址")}
                readOnly
                value={network}
              />
            </Field>
            <Field label={t("设备 WebSocket 地址")}>
              <input
                aria-label={t("设备 WebSocket 地址")}
                readOnly
                value={network.replace(/^http/, "ws") + "/ws"}
              />
            </Field>
            <p>
              {t(
                "HTTP 使用 Authorization 请求头；WebSocket 首条 hello 消息携带凭据。不要把凭据拼到地址中。",
              )}
            </p>
            <p>
              {t(
                "物理设备使用从零开始的单调采集时间，仅连接正在运行的实时意识；模拟器可以使用绝对模拟时间。断线重连保留会话与序号，暂停后的物理采集须新建会话。",
              )}
            </p>
            <Link
              className="text-link"
              to="/docs?doc=docs%2Fzh%2Fv2-network-devices.md"
            >
              {t("接入示例、时间规则与错误处理")}
            </Link>
          </details>
          <div
            className="device-toolbar device-exports"
            aria-label={t("设备完整证据导出")}
          >
            <a
              className="button"
              href={`/api/v2${base}/inputs/export?records=envelopes&format=jsonl&source=remote%3A${device.id}`}
            >
              {t("此设备全部载体 JSONL")}
            </a>
            <a
              className="button"
              href={`/api/v2${base}/inputs/export?records=frames&format=csv&source=remote%3A${device.id}`}
            >
              {t("此设备全部递送 CSV")}
            </a>
          </div>
          <div className="device-toolbar">
            <Field label={t("设备会话")}>
              <select
                aria-label={t("设备会话")}
                value={current?.id ?? ""}
                onChange={(e) => {
                  setSession(e.target.value);
                  setPages(["-1"]);
                }}
              >
                {!sessions.data?.rows.length && (
                  <option value="">{t("尚无连接")}</option>
                )}
                {sessions.data?.rows.map((s: any) => (
                  <option key={s.id} value={s.id}>
                    {new Date(s.created_at).toLocaleString(locale(), {
                      hour12: false,
                    })}{" "}
                    ·{" "}
                    {s.clock_mode === "device" ? t("物理采集") : t("模拟时钟")}{" "}
                    · {t(statusName[s.status])}
                  </option>
                ))}
              </select>
            </Field>
            <Button
              disabled={sessionPages.length === 1}
              onClick={() => {
                setSessionPages(sessionPages.slice(0, -1));
                setSession("");
                setPages(["-1"]);
              }}
            >
              {t("上一组会话")}
            </Button>
            <Button
              disabled={!sessions.data?.more}
              onClick={() => {
                setSessionPages([...sessionPages, sessions.data.next]);
                setSession("");
                setPages(["-1"]);
              }}
            >
              {t("更早会话")}
            </Button>
          </div>
          {current ? (
            <>
              <div className="device-summary">
                <span>
                  {t("会话 ")}
                  <code>{current.id}</code>
                </span>
                <span>{t(statusName[current.status])}</span>
                <span>
                  {t("下一包序号 ")}
                  {String(current.next_sequence)}
                </span>
                <span>
                  {t("原点")}{" "}
                  {current.origin_sim_us == null
                    ? t("尚未绑定 / 不适用")
                    : timeLabel(current.origin_sim_us)}
                </span>
              </div>
              {current.reason && (
                <p className="notice">
                  {t("会话结束原因：")}
                  {t(reasons[current.reason] ?? current.reason)}
                </p>
              )}
              <p className="footnote">
                {t(
                  "“已接收”表示数据库已保存，实际递送须查看检查点提交的结果。输出流提供有容量限制的最新投影，完整输入证据可在下方逐包查看并从输入记录导出。",
                )}
              </p>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>{t("包序号")}</th>
                      <th>{t("类型")}</th>
                      <th>{t("处理状态")}</th>
                      <th>{t("递送 / 过滤 / 总帧")}</th>
                      <th>{t("最近递送")}</th>
                      <th>{t("证据")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {packets.data?.rows.map((p: any) => (
                      <tr key={p.sequence}>
                        <td className="mono">{p.sequence}</td>
                        <td>
                          {t(
                            {
                              input: "匿名输入",
                              modulation: "临时调制",
                              energy: "能量供给",
                            }[p.kind as string] ?? p.kind,
                          )}
                        </td>
                        <td>
                          {t(
                            deliveryName[p.delivery_status] ??
                              (p.port_outcome?.status === "scheduled"
                                ? "端口已排入"
                                : p.port_outcome?.status === "rejected"
                                  ? "端口未执行"
                                  : "等待处理"),
                          )}
                          <small>{p.error ?? p.port_outcome?.reason}</small>
                        </td>
                        <td>
                          {p.frame_count == null
                            ? "—"
                            : `${p.delivered_count} / ${p.filtered_count} / ${p.frame_count}`}
                        </td>
                        <td>{timeLabel(p.last_delivery_us)}</td>
                        <td>
                          {p.envelope_id ? (
                            <Button onClick={() => inspect(p.envelope_id)}>
                              {t("查看载体证据")}
                            </Button>
                          ) : (
                            <details>
                              <summary>{t("端口证据")}</summary>
                              <pre>
                                {JSON.stringify(
                                  p.port_outcome ?? p.receipt,
                                  null,
                                  2,
                                )}
                              </pre>
                            </details>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!packets.data?.rows.length && (
                <Empty
                  title={t("会话尚未接收数据包")}
                  detail={t(
                    "设备连接后，按连续序号发送输入或已授权的端口请求。",
                  )}
                />
              )}
              <div className="device-toolbar">
                <Button
                  disabled={pages.length === 1}
                  onClick={() => setPages(pages.slice(0, -1))}
                >
                  {t("上一页数据包")}
                </Button>
                <span>{t("第 {page} 页", { page: pages.length })}</span>
                <Button
                  disabled={!packets.data?.more}
                  onClick={() => setPages([...pages, packets.data.next])}
                >
                  {t("下一页数据包")}
                </Button>
              </div>
            </>
          ) : (
            <p className="notice">
              {t("设备主动连接后，这里会出现会话。页面不会自动连接外部硬件。")}
            </p>
          )}
        </>
      )}
      <Modal
        open={form !== null}
        onOpenChange={(v) => {
          if (!v) setForm(null);
        }}
        title={form === "new" ? t("添加网络设备") : t("编辑设备配置")}
        description={t("绑定只授权当前意识，不改变内核参数或连接结构。")}
      >
        {form && (
          <DeviceForm
            key={form === "new" ? "new" : form.id}
            device={form === "new" ? null : form}
            base={base}
            finish={completed}
            close={() => setForm(null)}
          />
        )}
      </Modal>
      <Modal
        open={!!secret}
        onOpenChange={(v) => {
          if (!v) setSecret(null);
        }}
        title={t("设备凭据已生成")}
        description={t("凭据只在此显示一次。关闭后可轮换生成新凭据。")}
      >
        {secret && (
          <>
            <p>{secret.device.name}</p>
            <Field label={t("设备独立凭据")}>
              <textarea
                aria-label={t("设备独立凭据")}
                readOnly
                value={secret.token}
                rows={3}
                spellCheck={false}
              />
            </Field>
            <div className="dialog-actions">
              <Button
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(secret.token);
                    setCopied(true);
                  } catch {
                    setError(t("无法访问剪贴板，请手动复制设备凭据。"));
                  }
                }}
              >
                {copied ? t("已复制") : t("复制凭据")}
              </Button>
              <Button variant="primary" onClick={() => setSecret(null)}>
                {t("已保存凭据")}
              </Button>
            </div>
          </>
        )}
      </Modal>
      <Modal
        open={rotate}
        onOpenChange={setRotate}
        title={t("轮换设备凭据")}
        description={t(
          "旧凭据立即失效，当前会话结束；新凭据有效期为 30 天。设备通道接线保持不变。",
        )}
      >
        <ErrorBox error={error} />
        <div className="dialog-actions">
          <Button onClick={() => setRotate(false)}>{t("取消")}</Button>
          <Button
            variant="primary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError(null);
              try {
                const result = await post(
                  `${base}/devices/${device!.id}/rotate`,
                  {},
                );
                setRotate(false);
                await completed(result);
              } catch (e) {
                setError(e);
              } finally {
                setBusy(false);
              }
            }}
          >
            {t("生成新凭据")}
          </Button>
        </div>
      </Modal>
    </section>
  );
}
