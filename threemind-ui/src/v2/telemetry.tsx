import { t, locale } from "./i18n";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Settings2, Download, RefreshCw } from "lucide-react";
import { api, type Run } from "./api";
import { Button, Field, ErrorBox, Loading, Empty } from "./ui";

const number = (value: unknown) =>
  typeof value === "number"
    ? value.toLocaleString(locale(), { maximumSignificantDigits: 6 })
    : "—";
export function TelemetryPanel({
  base,
  run,
  configure,
  inspect,
}: {
  base: string;
  run: Run;
  configure: () => void;
  inspect: (id: string) => void;
}) {
  const [scope, setScope] = useState("");
  const [pages, setPages] = useState<(number | null)[]>([null]);
  const [filter, setFilter] = useState("");
  const before = pages.at(-1);
  const query = new URLSearchParams({ limit: "1" });
  if (scope) query.set("scope", scope);
  if (before) query.set("before_id", String(before));
  const samples = useQuery({
    queryKey: ["telemetry", run.id, query.toString()],
    queryFn: () => api(`${base}/telemetry?${query}`),
    gcTime: 0,
    refetchInterval:
      !before && ["running", "queued"].includes(run.status) ? 2000 : false,
  });
  const row = samples.data?.rows[0];
  const payload = row?.payload;
  const enabled = Object.entries(samples.data?.configuration ?? {}).filter(
    ([root, v]) =>
      (v as any).enabled &&
      samples.data?.source_policies?.[root]?.enabled !== false,
  ).length;
  return (
    <section className="panel telemetry-panel">
      <div className="panel-heading">
        <div>
          <h2>{t("物理遥测")}</h2>
          <p>{t("查看真实计数、归一化结果，以及每次采样递送的匿名刺激。")}</p>
        </div>
        <Button onClick={configure}>
          <Settings2 size={15} />
          {t("配置遥测")}
        </Button>
      </div>
      <div className="query-controls">
        <Field label={t("遥测范围")}>
          <select
            value={scope}
            onChange={(e) => {
              setScope(e.target.value);
              setPages([null]);
            }}
          >
            <option value="">{t("全部范围")}</option>
            <option value="host">{t("宿主计算机")}</option>
            <option value="process">{t("工作进程")}</option>
            <option value="runtime">{t("当前意识实例")}</option>
          </select>
        </Field>
        <Field label={t("筛选指标")}>
          <input
            value={filter}
            placeholder={t("指标名称或键")}
            onChange={(e) => setFilter(e.target.value)}
          />
        </Field>
        <Button onClick={() => samples.refetch()}>
          <RefreshCw size={15} />
          {t("刷新采样")}
        </Button>
      </div>
      <p className="footnote">
        {t("已启用 ")}
        {enabled}{" "}
        {t(
          "组遥测。真实时间采样仅在运行中进行；暂停／恢复后重建基线，在途刺激保留。进程资源包含整个 worker；实例计量仅覆盖内核调用。",
        )}
      </p>
      <ErrorBox error={samples.error} />
      {samples.isPending && <Loading />}
      {!samples.isPending && !row && (
        <Empty
          title={t("暂无已提交的遥测采样")}
          detail={t(
            "在参数中启用所需遥测组，使用实时模式运行。首个计数间隔可能尚未建立基线。",
          )}
        />
      )}
      {payload && (
        <>
          <div className="input-queue-summary">
            <span>
              {t("采集时间")}{" "}
              <strong>
                {new Date(payload.captured_at_utc).toLocaleString(locale())}
              </strong>
            </span>
            <span>
              {t("模拟时间 ")}
              <strong>{number(Number(row.time_us) / 1e6)} s</strong>
            </span>
            <span>
              {t("数据库版本 ")}
              <strong>r{row.commit_revision}</strong>
            </span>
          </div>
          <details className="sensory-wiring-details">
            <summary>{t("采样来源与会话")}</summary>
            <dl className="telemetry-context">
              <dt>{t("采集后端")}</dt>
              <dd>{payload.backend}</dd>
              <dt>{t("工作进程")}</dt>
              <dd>{payload.worker_pid}</dd>
              <dt>{t("会话")}</dt>
              <dd className="mono">{payload.session_id}</dd>
              <dt>{t("采样")}</dt>
              <dd className="mono">{payload.sample_id}</dd>
              <dt>{t("单调时间")}</dt>
              <dd>{number(payload.monotonic_s)} s</dd>
            </dl>
          </details>
          {Object.entries(payload.scopes)
            .filter(([s]) => !scope || s === scope)
            .map(([s, entry]) => {
              const value = entry as any;
              const rows = Object.entries(value.measurements).filter(([name]) =>
                `${samples.data.metrics[s]?.[name]} ${t(samples.data.metrics[s]?.[name] ?? "")} ${name}`
                  .toLowerCase()
                  .includes(filter.toLowerCase()),
              );
              return (
                <article className="telemetry-scope" key={s}>
                  <div className="panel-heading">
                    <h3>
                      {t(samples.data.scopes[s])}
                      {t("遥测")}
                    </h3>
                    <Button onClick={() => inspect(value.envelope_id)}>
                      {t("查看递送证据")}
                    </Button>
                  </div>
                  <p className="footnote">
                    {value.channel_count}
                    {t(" 个通道值 ·")}{" "}
                    {value.scheduled_time_us
                      ? t("计划递送 {value0} s", {
                          value0: String(
                            number(Number(value.scheduled_time_us) / 1e6),
                          ),
                        })
                      : t("本次无正幅值刺激")}{" "}
                    {t("· 实测采样迟到 ")}
                    {number(value.sampling_lateness_ms)} ms
                  </p>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>{t("指标")}</th>
                          <th>{t("原始测量")}</th>
                          <th>{t("归一化／平滑")}</th>
                          <th>{t("上升／下降")}</th>
                          <th>{t("可用性与尺度")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map(([name, item]) => {
                          const r = item as any;
                          return (
                            <tr key={name}>
                              <td>
                                {t(samples.data.metrics[s]?.[name] ?? name)}
                                <small className="metric-key">{name}</small>
                              </td>
                              <td>
                                {number(r.raw.raw_value)}{" "}
                                <small>{r.raw.unit ?? ""}</small>
                              </td>
                              <td>
                                {number(r.normalized_level)} /{" "}
                                {number(r.smoothed_level)}
                              </td>
                              <td>
                                {r.baseline_established
                                  ? `${number(r.rise)} / ${number(r.fall)}`
                                  : t("基线未建立")}
                              </td>
                              <td>
                                {!r.raw.available ? (
                                  <span className="telemetry-unavailable">
                                    {t("不可用：")}
                                    {r.raw.unavailable_reason}
                                  </span>
                                ) : (
                                  <>
                                    <span
                                      className={`badge ${r.encoded ? "running" : "paused"}`}
                                    >
                                      {r.encoded ? t("已编码") : t("无刺激")}
                                    </span>
                                    <small className="metric-key">
                                      {number(r.reference)} {r.raw.unit} ·{" "}
                                      {r.reference_source ??
                                        r.raw.unavailable_reason}
                                    </small>
                                  </>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </article>
              );
            })}
        </>
      )}
      <div className="media-input-actions">
        <Button
          disabled={pages.length <= 1}
          onClick={() => setPages((p) => p.slice(0, -1))}
        >
          {t("较新采样")}
        </Button>
        <Button
          disabled={!samples.data?.more}
          onClick={() => setPages((p) => [...p, samples.data.next])}
        >
          {t("较早采样")}
        </Button>
        <Button disabled={pages.length <= 1} onClick={() => setPages([null])}>
          {t("回到最新")}
        </Button>
        {["csv", "jsonl"].map((format) => (
          <a
            className="button"
            key={format}
            href={`/api/v2${base}/telemetry/export?format=${format}${scope ? `&scope=${scope}` : ""}`}
          >
            <Download size={15} />
            {t("导出 ")}
            {format.toUpperCase()}
          </a>
        ))}
      </div>
      <p className="footnote">
        {t(
          "导出包含所选范围的全部已提交采样。缺失测量保留原因；图形筛选仅影响当前展示。",
        )}
      </p>
      <Link className="text-link" to="/docs?doc=docs%2Fzh%2Fv2-telemetry.md">
        {t("遥测原理、时间与计量边界")}
      </Link>
    </section>
  );
}
