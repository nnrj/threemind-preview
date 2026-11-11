import { t, locale } from "./i18n";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, projectPath, statuses, type Run } from "./api";
import {
  inspectBrowser,
  type Capability,
  type CapabilityReport,
} from "./browserCapabilities";
import { Button, Empty, ErrorBox, Field, Loading, useWorkspace } from "./ui";
import AdapterContracts, { ContractDetails } from "./AdapterContracts";

const capabilityNames: Record<string, string> = {
  available: "可用",
  partial: "部分可用",
  unavailable: "不可用",
  unknown: "尚未检测",
  permission_required: "尚未授权",
  denied: "权限已拒绝",
};
const directionNames: Record<string, string> = {
  input: "输入",
  output: "输出",
  filter: "过滤",
  duplex: "双向",
};
const scopeNames: Record<string, string> = {
  api: "接口服务",
  worker: "工作进程",
  browser: "当前浏览器",
};
const scopeOf = (key: string) => t(scopeNames[key.split(".")[0]] ?? key);
const featureNames: Record<string, string> = {
  "browser.microphone": "麦克风",
  "browser.camera": "摄像头",
  "browser.audio_output": "声音播放",
  "worker.core": "运行内核",
  "worker.ai": "AI 文本请求",
  "worker.mujoco": "物理环境",
  "worker.world_v1": "可配置世界与躯体",
  "worker.world_rgb_v1": "世界离屏 RGB 感官",
  "worker.world_authoring_v1": "世界与躯体草案",
  "worker.telemetry_host": "宿主遥测",
  "worker.telemetry_process": "进程遥测",
  "worker.telemetry_runtime": "实例反馈",
  "api.media_audio": "音频解码",
  "api.media_image": "图片解码",
  "api.media_video": "视频解码",
  "api.network": "设备连接",
};
const timestamp = (value?: string) =>
  value
    ? new Date(value).toLocaleString(locale(), { hour12: false })
    : "尚无报告";

function Feature({ id, value }: { id: string; value: Capability }) {
  return (
    <div className="capability-item">
      <div>
        <strong>{value.name ? t(value.name) : id}</strong>
        <span className={`capability-state ${value.state}`}>
          {t(capabilityNames[value.state] ?? value.state)}
        </span>
      </div>
      <p>{value.reason}</p>
      {!!value.package && (
        <small>
          {t("版本 ")}
          {String(value.package)}
        </small>
      )}
      {!!value.readings && (
        <details>
          <summary>{t("逐项计数可用性")}</summary>
          <ul>
            {Object.entries(value.readings as Record<string, any>).map(
              ([name, r]) => (
                <li key={name}>
                  <code>{name}</code> ·{" "}
                  {r.available ? t("可读取") : t("当前缺失")}
                  {r.reason ? ` · ${r.reason}` : ""}
                </li>
              ),
            )}
          </ul>
        </details>
      )}
    </div>
  );
}

function HostReport({
  title,
  report,
}: {
  title: string;
  report?: CapabilityReport | null;
}) {
  return (
    <section className="capability-report">
      <h3>{title}</h3>
      <p className="footnote">
        {t("检测时间：")}
        {timestamp(report?.checked_at)}
        {report?.platform ? ` · ${report.platform}` : ""}
      </p>
      {report?.features ? (
        <div className="capability-grid">
          {Object.entries(report.features).map(([key, value]) => (
            <Feature key={key} id={key} value={value} />
          ))}
        </div>
      ) : (
        <p className="notice">
          {t("尚未收到该进程的能力报告。不能用其他宿主的结果代替。")}
        </p>
      )}
    </section>
  );
}

function useBrowserInspection() {
  const [report, setReport] = useState<CapabilityReport | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(null);
  async function inspect() {
    setBusy(true);
    setError(null);
    try {
      setReport(await inspectBrowser());
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return { report, busy, error, inspect };
}

export function AdapterCatalogue({
  base,
  run,
  configure,
}: {
  base?: string;
  run?: Run;
  configure?: (group: string) => void;
}) {
  const [query, setQuery] = useState(""),
    [direction, setDirection] = useState(""),
    [enabledOnly, setEnabledOnly] = useState(false),
    [expanded, setExpanded] = useState<Set<string>>(new Set());
  const browser = useBrowserInspection();
  const catalogue = useQuery<any>({
    queryKey: ["adapter-bindings", base, run?.spec],
    queryFn: () => api(base ? `${base}/adapters` : "/adapters"),
    refetchOnWindowFocus: false,
  });
  const term = query.trim().toLowerCase();
  const allRows: any[] = catalogue.data?.adapters ?? [];
  const rows = allRows.filter(
    (r) =>
      (!direction || r.direction === direction) &&
      (!enabledOnly || r.configured_enabled) &&
      (!term ||
        `${r.id} ${r.name} ${t(r.name)} ${r.description} ${t(r.description)} ${r.configuration_root}`
          .toLowerCase()
          .includes(term) ||
        r.parameters.some((p: any) =>
          `${t(p.label)} ${t(p.label)} ${p.path} ${p.hint} ${t(p.hint)}`
            .toLowerCase()
            .includes(term),
        )),
  );
  const features: Record<string, Capability> = {
    ...catalogue.data?.api?.features,
    ...catalogue.data?.worker?.capabilities?.features,
    ...browser.report?.features,
  };
  const toolUrl = (tool: string) =>
    tool === "language"
      ? "/dialogue"
      : `/runs/${run!.id}?view=${tool === "readouts" ? "readouts" : tool === "energy" ? "dynamics" : "inputs"}&tool=${encodeURIComponent(tool)}`;
  return (
    <section
      className="panel adapter-catalogue"
      role="region"
      aria-label={t("适配器目录")}
    >
      <div className="panel-heading">
        <div>
          <h2>{run ? t("此意识的适配器与接线") : t("已实现的适配器目录")}</h2>
          <p>
            {run
              ? t(
                  "配置来自此意识的实际参数。软件能力、浏览器权限和当前执行状态分别展示。",
                )
              : t(
                  "这里展示实际运行时契约和默认参数；选择意识后可查看绑定与配置。",
                )}
          </p>
        </div>
        <Button onClick={() => catalogue.refetch()}>
          {t("刷新适配器目录")}
        </Button>
      </div>
      {run && (
        <p className="notice">
          {t("执行状态：")}
          {t(statuses[run.status] ?? run.status)}
          {t("；外部来源：")}
          {catalogue.data?.source_enabled === false
            ? t("已关闭")
            : catalogue.data?.source_enabled === true
              ? t("未关闭")
              : t("尚无检查点")}
          {t(
            "。配置启用表示参数选择，实际采集、输入和监听还需在相应工具中开始。",
          )}
        </p>
      )}
      <div className="adapter-filters">
        <Field label={t("搜索适配器或参数")}>
          <input
            aria-label={t("搜索适配器或参数")}
            placeholder={t("例如：听觉、增益、body_filter")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </Field>
        <Field label={t("适配器方向")}>
          <select
            aria-label={t("适配器方向")}
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
          >
            <option value="">{t("全部方向")}</option>
            {Object.entries(directionNames).map(([v, n]) => (
              <option key={v} value={v}>
                {t(n)}
              </option>
            ))}
          </select>
        </Field>
        <label className="check">
          <input
            type="checkbox"
            checked={enabledOnly}
            onChange={(e) => setEnabledOnly(e.target.checked)}
          />
          {t("只看配置启用")}
        </label>
      </div>
      {run && (
        <div className="adapter-browser-check">
          <Button disabled={browser.busy} onClick={browser.inspect}>
            {browser.busy ? t("检测中…") : t("检查当前浏览器能力")}
          </Button>
          <span>{t("检测只查询支持情况和现有权限，不请求设备授权。")}</span>
        </div>
      )}
      <ErrorBox error={catalogue.error ?? browser.error} />
      {catalogue.isPending ? (
        <Loading />
      ) : (
        <>
          <p className="footnote">
            {t("显示 ")}
            {rows.length} / {allRows.length}
            {t(" 个适配器。")}
            {run &&
              `工作进程：${catalogue.data?.worker?.name ?? "尚未分配"}；报告时间 ${timestamp(catalogue.data?.worker?.capabilities?.checked_at)}`}
          </p>
          {!rows.length && (
            <Empty
              title={t("没有匹配的适配器")}
              detail={t("调整搜索词或筛选条件。")}
            />
          )}
          <div className="adapter-grid">
            {rows.map((row) => (
              <article className="adapter-card" key={row.id}>
                <div className="adapter-card-heading">
                  <h3>{t(row.name)}</h3>
                  <span>{t(directionNames[row.direction])}</span>
                </div>
                <p>{t(row.description)}</p>
                <div className="adapter-state-row">
                  <span
                    className={`capability-state ${row.binding_status === "configured" ? "available" : row.binding_status === "inactive" ? "partial" : "unknown"}`}
                  >
                    {row.configured_enabled ? t("配置已启用") : t("配置未启用")}
                  </span>
                  <small>{row.bus}</small>
                </div>
                {row.binding_reasons?.map((reason: string) => (
                  <p className="adapter-dependency" key={reason}>
                    {reason}
                  </p>
                ))}
                {row.capabilities.length > 0 && (
                  <div className="adapter-feature-list">
                    {row.capabilities.map((id: string) => {
                      const value = features[id];
                      return (
                        <div key={id}>
                          <span>
                            {scopeOf(id)} ·{" "}
                            {t(value?.name ?? featureNames[id] ?? id)}
                          </span>
                          <strong>
                            {t(capabilityNames[value?.state ?? "unknown"])}
                          </strong>
                          {value && <small>{value.reason}</small>}
                        </div>
                      );
                    })}
                  </div>
                )}
                <details>
                  <summary>{t("总线端口与契约")}</summary>
                  <p className="mono adapter-identity">
                    {row.id} · {row.version}
                  </p>
                  <p>
                    {t("接收：")}
                    {row.ports.inputs.join("、") || "—"}
                  </p>
                  <p>
                    {t("输出：")}
                    {row.ports.outputs.join("、") || "—"}
                  </p>
                  {row.configuration_root && (
                    <p>
                      {t("配置位置：")}
                      <code>{row.configuration_root}</code>
                    </p>
                  )}
                  <ContractDetails contract={row.contract} />
                </details>
                {!!row.parameters.length && (
                  <details
                    onToggle={(e) => {
                      const open = e.currentTarget.open;
                      setExpanded((old) => {
                        const next = new Set(old);
                        if (open) next.add(row.id);
                        else next.delete(row.id);
                        return next;
                      });
                    }}
                  >
                    <summary>
                      {t("参数与不可变规则（")}
                      {row.parameters.length}
                      {t(" 项）")}
                    </summary>
                    {expanded.has(row.id) && (
                      <div className="table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th>{t("参数")}</th>
                              <th>{t("当前值")}</th>
                              <th>{t("创建后")}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {row.parameters.map((p: any) => {
                              const value = p.path
                                .split(".")
                                .slice(1)
                                .reduce(
                                  (v: any, key: string) => v?.[key],
                                  row.configuration,
                                );
                              return (
                                <tr key={p.path}>
                                  <td>
                                    {t(p.label)}
                                    <small>{p.path}</small>
                                  </td>
                                  <td>
                                    {value == null
                                      ? t("未限定")
                                      : typeof value === "boolean"
                                        ? value
                                          ? t("开启")
                                          : t("关闭")
                                        : String(value)}{" "}
                                    {t(p.unit)}
                                  </td>
                                  <td>
                                    {p.immutable ? t("只读") : t("暂停后可改")}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </details>
                )}
                <div className="adapter-actions">
                  {run && (
                    <>
                      <Link className="button" to={toolUrl(row.tool)}>
                        {t("打开")}
                        {t(row.name)}
                        {t("工具")}
                      </Link>
                      {(row.configuration_root ||
                        ["mujoco-environment", "replay"].includes(row.id)) &&
                        (configure ? (
                          <Button onClick={() => configure(row.group)}>
                            {t("配置")}
                            {t(row.name)}
                          </Button>
                        ) : (
                          <Link
                            className="button"
                            to={`/runs/${run.id}?configure=1&group=${encodeURIComponent(row.group)}&view=inputs`}
                          >
                            {t("配置")}
                            {t(row.name)}
                          </Link>
                        ))}
                    </>
                  )}
                  <Link
                    className="text-link"
                    to={`/docs?doc=docs%2Fzh%2F${encodeURIComponent(row.document)}`}
                  >
                    {t("原理与使用说明")}
                  </Link>
                </div>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

export default function DeviceCapabilities() {
  const { project } = useWorkspace();
  const [tab, setTab] = useState("capabilities"),
    [selected, setSelected] = useState(""),
    [history, setHistory] = useState(false);
  const browser = useBrowserInspection();
  const reports = useQuery<any>({
    queryKey: ["host-capabilities"],
    queryFn: () => api("/capabilities"),
    refetchOnWindowFocus: false,
  });
  const runs = useQuery<Run[]>({
    queryKey: ["adapter-runs", project?.id],
    queryFn: () => api(`${projectPath(project!.id)}/runs`),
    enabled: !!project,
  });
  const run = runs.data?.find((r) => r.id === selected);
  const workers: any[] = (reports.data?.workers ?? []).filter(
    (w: any) => history || w.online,
  );
  return (
    <section
      className="panel capability-settings"
      role="region"
      aria-label={t("设备与适配器")}
    >
      <div className="tabs page-tabs">
        <button
          className={tab === "capabilities" ? "active" : ""}
          onClick={() => setTab("capabilities")}
        >
          {t("能力检测")}
        </button>
        <button
          className={tab === "catalogue" ? "active" : ""}
          onClick={() => setTab("catalogue")}
        >
          {t("适配器目录")}
        </button>
        <button
          className={tab === "contracts" ? "active" : ""}
          onClick={() => setTab("contracts")}
        >
          {t("接入验收")}
        </button>
      </div>
      <ErrorBox error={reports.error ?? runs.error ?? browser.error} />
      {tab === "capabilities" ? (
        <>
          <div className="panel-heading">
            <div>
              <h2>{t("设备与执行环境")}</h2>
              <p>{t("先确认功能在哪个宿主执行，再判断是否具备依赖或权限。")}</p>
            </div>
            <Button onClick={() => reports.refetch()}>
              {t("刷新服务能力")}
            </Button>
          </div>
          {reports.isPending ? (
            <Loading />
          ) : (
            <HostReport
              title={t("接口服务：文件与网络接入")}
              report={reports.data?.api}
            />
          )}
          <div className="adapter-browser-check">
            <Button disabled={browser.busy} onClick={browser.inspect}>
              {browser.busy ? t("检测中…") : t("检查当前浏览器能力")}
            </Button>
            <span>{t("当前浏览器的结果只在本页展示。")}</span>
          </div>
          <HostReport
            title={t("当前浏览器：采集、播放与图形")}
            report={browser.report}
          />
          <div className="panel-heading">
            <h3>{t("工作进程：模型与物理环境")}</h3>
            <label className="check">
              <input
                type="checkbox"
                checked={history}
                onChange={(e) => setHistory(e.target.checked)}
              />
              {t("显示离线进程")}
            </label>
          </div>
          {!reports.data?.all_workers_visible && (
            <p className="notice">
              {t(
                "全局进程目录仅管理员可见。项目成员可在相应意识的适配器目录查看实际执行环境。",
              )}
            </p>
          )}
          {reports.data?.all_workers_visible && !workers.length && (
            <Empty
              title={t("尚无在线工作进程报告")}
              detail={t(
                "启动工作进程后刷新。在线状态依据最近 90 秒的数据库心跳；能力报告在进程启动时生成。",
              )}
            />
          )}
          {workers.map((w) => (
            <details className="worker-capability" key={w.id}>
              <summary>
                {w.name} ·{" "}
                {w.enabled
                  ? w.online
                    ? t("在线")
                    : t("心跳已过期")
                  : t("已停用")}
              </summary>
              <p className="footnote">
                {t("最近心跳 ")}
                {timestamp(w.heartbeat)}
                {t(
                  "。更换依赖后需重启该进程以重新检测；内核不可用时不领取任务，也不自动切换实现。",
                )}
              </p>
              <HostReport
                title={t("该工作进程的能力")}
                report={w.capabilities?.schema ? w.capabilities : null}
              />
            </details>
          ))}
          <p className="footnote">
            {reports.data?.notice}
            {t(
              " 接口服务的检测结果最多缓存 30 秒。单次能力检查通过不等于长期吞吐已达标。",
            )}
          </p>
        </>
      ) : tab === "contracts" ? (
        <AdapterContracts />
      ) : (
        <>
          <Field label={t("查看意识绑定")}>
            <select
              aria-label={t("查看意识绑定")}
              value={run?.id ?? ""}
              onChange={(e) => setSelected(e.target.value)}
            >
              <option value="">{t("查看默认契约")}</option>
              {runs.data?.map((r) => (
                <option value={r.id} key={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </Field>
          <AdapterCatalogue
            key={run?.id ?? "default"}
            run={run}
            base={
              run ? `${projectPath(project!.id)}/runs/${run.id}` : undefined
            }
          />
        </>
      )}
      <Link
        className="text-link"
        to="/docs?doc=docs%2Fzh%2Fv2-adapters-and-capabilities.md"
      >
        {t("适配器、宿主能力与配置边界")}
      </Link>
    </section>
  );
}
