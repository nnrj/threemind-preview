import { t, locale } from "./i18n";
import { useState, useEffect, lazy } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { RefreshCw, Settings2, Download } from "lucide-react";
import { api, timeLabel, type Run } from "./api";
import { Button, Field, Empty, ErrorBox, Loading } from "./ui";
import { ProcessSummary, ProcessTools } from "./ProcessObservation";
import { classes } from "./readoutLabels";
export { classes } from "./readoutLabels";

const Chart = lazy(() => import("./Chart"));
const reasons: Record<string, string> = {
  maximum_window: "达到观察时长上限",
  node_entry_budget: "累计节点预算不足",
  active_window_budget: "同时观察窗口已满",
  history_sample_budget: "轨迹采样预算已满",
  run_ended: "运行结束",
  cancelled: "运行被终止",
  configuration_changed: "读出参数变更",
  finite_sample_window_criteria: "集合、分布与幅度均符合配置判据",
  three_repeated_nonconstant_cycles: "等间隔采样中出现三个非恒定重复周期",
  tail_amplitude_decline: "尾段未回升，且终值降至峰值的配置比例以下",
  no_sustained_tail: "判定尾段内无超基线活动",
  below_response_floor_for_settle_window:
    "尾段超基线响应低于配置下限；不等于意识死亡",
  series_value_budget: "完整轨迹数值预算已满",
};
const analysisStates: Record<string, string> = {
  converged: "已收敛",
  detected: "已检测到",
  ended: "已结束",
  stable: "稳定",
  decaying: "下降",
  growing: "上升",
  varying: "波动",
  below_floor: "低于下限",
  not_detected: "窗内未检测到",
  disabled: "未启用",
};

export function ActivitySummary({ value }: { value: any }) {
  if (!value?.analyses) return null;
  return (
    <>
      <ProcessSummary value={value} />
      <dl className="readout-facts activity-analysis-facts">
        {(
          [
            ["pattern", "响应模式收敛"],
            ["amplitude", "幅度变化"],
            ["periodic", "周期活动"],
            ["response_end", "响应结束"],
          ] as const
        ).map(([key, label]) => {
          const item = value.analyses[key];
          return (
            <div key={key}>
              <dt>{t(label)}</dt>
              <dd>
                {t(analysisStates[item?.status] ?? "窗内未检测到")}
                {item?.end_us != null && <> · {seconds(item.end_us)}</>}
                {item?.period_us != null && (
                  <>
                    {" "}
                    · {t("周期")} {seconds(item.period_us)}
                  </>
                )}
              </dd>
            </div>
          );
        })}
      </dl>
    </>
  );
}
const number = (x: any) =>
  typeof x === "number"
    ? x.toLocaleString(locale(), { maximumSignificantDigits: 5 })
    : "—";
const seconds = (x: any) => (x == null ? "—" : `${number(Number(x) / 1e6)} s`);
const proportion = (x: any) => (x == null ? "—" : `${number(x * 100)}%`);

function RecordDetail({
  base,
  recordId,
  run,
}: {
  base: string;
  recordId: number;
  run: Run;
}) {
  const [requestedSection, setSection] = useState("default"),
    [offset, setOffset] = useState(0),
    [seriesOffset, setSeriesOffset] = useState(0);
  const [candidates, setCandidates] = useState(false),
    [order, setOrder] = useState("scientific"),
    [measurement, setMeasurement] = useState("overview");
  const [customLimit, setCustomLimit] = useState<number | null>(null);
  const root = `${base}/readouts/${recordId}`;
  const meta = useQuery({
    queryKey: ["readout", run.id, recordId, "meta"],
    queryFn: () => api(`${root}?limit=1`),
    gcTime: 0,
  });
  const p = meta.data?.record?.payload;
  const temporal = p?.kind === "temporal_readout";
  const section =
    requestedSection === "default"
      ? temporal
        ? "nodes"
        : "raw_nodes"
      : requestedSection;
  const limit = customLimit ?? p?.configuration?.display_limit ?? 20;
  const query = new URLSearchParams({
    section,
    offset: String(offset),
    limit: String(limit),
    candidates_only: String(candidates),
    order,
  });
  const detail = useQuery({
    queryKey: ["readout", run.id, recordId, query.toString()],
    queryFn: () => api(`${root}?${query}`),
    enabled: !!p,
    gcTime: 0,
  });
  const series = useQuery({
    queryKey: ["readout", run.id, recordId, "series", seriesOffset],
    queryFn: () =>
      api(`${root}?section=series&offset=${seriesOffset}&limit=500`),
    enabled: !!temporal,
    gcTime: 0,
  });
  if (meta.isLoading) return <Loading />;
  if (!p) return <ErrorBox error={meta.error} />;
  const rows = detail.data?.rows ?? [];
  const columns: [string, string, (x: any) => string][] = temporal
    ? measurement === "time"
      ? [
          ["active_us", "活动时长", seconds],
          ["tail_active_us", "尾段活动", seconds],
          ["longest_run_us", "最长连续活动", seconds],
          ["first_active_us", "首次活动时间", seconds],
          ["last_active_us", "最近活动时间", seconds],
          ["reentry_count", "再次进入次数", number],
        ]
      : measurement === "traces"
        ? [
            ["direct_trace_integral", "直接痕迹积分", number],
            ["associative_trace_integral", "联想痕迹积分", number],
            ["inhibition_integral", "抑制势积分", number],
            ["peak_inhibition", "抑制势峰值", number],
            ["baseline_mean", "基线均值", number],
            ["baseline_noise", "基线标准差", number],
          ]
        : [
            ...(p.analysis_schema
              ? [
                  ["decision_activation", "判定时激活", number] as [
                    string,
                    string,
                    (x: any) => string,
                  ],
                ]
              : []),
            ["last_activation", "窗末激活", number],
            ["score", "排序分数", number],
            ["excess_integral", "超基线积分", number],
            ["activation_integral", "激活积分", number],
            ["active_ratio", "活动占比", proportion],
            ["tail_active_ratio", "尾段活动占比", proportion],
            ["peak_activation", "激活峰值", number],
          ]
    : section === "edges"
      ? [
          ["source", "起点", number],
          ["target", "终点", number],
          ["weight", "权重", number],
          ["stability", "稳定性", number],
          ["eligibility", "资格痕迹", number],
        ]
      : [
          ["activation", "激活", number],
          ["direct", "直接痕迹", number],
          ["associative", "联想痕迹", number],
          ["inhibition", "抑制势", number],
          ["stability", "稳定性", number],
          ["support", "支持量", number],
        ];
  return (
    <section className="panel readout-detail">
      <div className="panel-heading">
        <div>
          <h2>
            {temporal
              ? t(classes[p.classification] ?? p.classification ?? "")
              : t("匿名活动与结构截面")}
          </h2>
          <p>
            {temporal
              ? `${seconds(p.start_us)} → ${seconds(p.end_us)} · ${p.source}`
              : t("{value0} · 完整源节点 {value1}", {
                  value0: String(seconds(p.time_us)),
                  value1: String(p.source_node_count),
                })}
          </p>
        </div>
        <span className="mono">
          {t("证据 #")}
          {recordId} · r{meta.data.record.commit_revision}
        </span>
      </div>
      <p className="footnote">
        {t(
          "输入编号只标明观察窗口的起点，不证明因果归属。候选、排序与外部注释不会改写原始活动或内核连接。",
        )}
      </p>
      {!temporal && !p.raw_observation?.complete && (
        <p className="notice">
          {t(
            p.raw_observation
              ? "此记录未启用完整截面保存；可查看派生结果，不能据此还原全部活动。"
              : "这条历史记录未保存完整原始截面；派生结果不能代表全部节点活动。",
          )}
        </p>
      )}
      {temporal && (
        <p className="footnote">
          {t(
            "本表默认包含已观察的全部节点统计。积分和聚合曲线来自离散采样，不是各节点的完整连续波形。",
          )}
        </p>
      )}
      {temporal ? (
        <>
          {p.analysis_schema && (
            <>
              <ActivitySummary value={p} />
              <p className="footnote">
                {t(
                  "主要结果按模式判定结束时的激活强度排序；其后继续观察幅度和响应结束。",
                )}
                {p.ranking_time_us != null && (
                  <>
                    {" "}
                    {t("判定时刻")} {seconds(p.ranking_time_us)}
                  </>
                )}
              </p>
            </>
          )}
          <p className={p.censored ? "notice" : "footnote"}>
            {t(reasons[p.reason] ?? p.reason)}。
            {p.partial_start && "本窗口从载体中途开始。"}
            {p.overlapping_envelopes.length > 0 &&
              `有 ${p.overlapping_envelopes.length} 个其他输入载体与观察重叠，不能将全部响应归因于单一输入。`}
          </p>
          <dl className="readout-facts">
            <div>
              <dt>{t("输入最后实际递送")}</dt>
              <dd>{seconds(p.delivery_end_us)}</dd>
            </div>
            <div>
              <dt>{t("已观察 / 尾段时长")}</dt>
              <dd>
                {seconds(p.coverage.observed_us)} /{" "}
                {seconds(p.coverage.tail_observed_us)}
              </dd>
            </div>
            <div>
              <dt>{t("刺激前基线覆盖")}</dt>
              <dd>
                {seconds(p.coverage.baseline_coverage_us)} /{" "}
                {seconds(p.coverage.baseline_requested_us)}
                {!p.coverage.baseline_complete && " · 不足"}
              </dd>
            </div>
            <div>
              <dt>{t("已保存 / 候选节点")}</dt>
              <dd>
                {p.node_count} / {p.candidate_count}
              </dd>
            </div>
            <div>
              <dt>{t("尾段 Jaccard / 分布漂移")}</dt>
              <dd>
                {number(p.convergence.mean_jaccard)} /{" "}
                {number(p.convergence.mean_distribution_drift)}
              </dd>
            </div>
            <div>
              <dt>{t("尾段幅度变化 / 集合周期")}</dt>
              <dd>
                {proportion(p.convergence.amplitude_drift)} /{" "}
                {seconds(p.convergence.period_us)}
              </dd>
            </div>
          </dl>
          <div className="chart-grid readout-charts">
            <Chart
              rows={series.data?.rows.map((r: any) => r.item) ?? []}
              metric="total"
              title={t("超基线活动总量")}
              step
            />
            <Chart
              rows={series.data?.rows.map((r: any) => r.item) ?? []}
              metric="active_node_count"
              title={t("超基线活动节点数")}
              step
            />
          </div>
          <ErrorBox error={series.error} />
          <div className="readout-pagination">
            <span>
              {t("轨迹 ")}
              {seriesOffset + 1}–
              {seriesOffset + (series.data?.rows.length ?? 0)} /{" "}
              {p.series_count}
              {t(" 点；阶梯线表示采样间左值保持估计。")}
            </span>
            <Button
              disabled={!seriesOffset}
              onClick={() => setSeriesOffset(Math.max(0, seriesOffset - 500))}
            >
              {t("前段轨迹")}
            </Button>
            <Button
              disabled={!series.data?.more}
              onClick={() => setSeriesOffset(seriesOffset + 500)}
            >
              {t("后段轨迹")}
            </Button>
          </div>
        </>
      ) : (
        <dl className="readout-facts">
          <div>
            <dt>{t("原始截面 / 源节点")}</dt>
            <dd>
              {p.raw_observation?.complete ? p.raw_observation.node_count : "—"}{" "}
              / {p.source_node_count}
            </dd>
          </div>
          <div>
            <dt>{t("阈值以上 / 活动记录")}</dt>
            <dd>
              {p.threshold_node_count} / {p.node_count}
            </dd>
          </div>
          <div>
            <dt>{t("候选子图")}</dt>
            <dd>
              {p.structure
                ? t("{value0} 节点 · {value1} 有向边", {
                    value0: String(p.structure.node_count),
                    value1: String(p.structure.edge_count),
                  })
                : t("未满足候选标准")}
            </dd>
          </div>
          <div>
            <dt>{t("同身份结构与量化状态复现")}</dt>
            <dd>
              {p.structure
                ? t("{value0} 次 · 跨度 {value1}", {
                    value0: String(p.structure.occurrences),
                    value1: String(seconds(p.structure.span_us)),
                  })
                : "—"}
            </dd>
          </div>
          <div>
            <dt>{t("复现判定 / 本次提示")}</dt>
            <dd>
              {p.structure?.recurrent ? t("达到判据") : t("未达到")} /{" "}
              {p.structure?.recurrence_notice ? t("提示") : t("冷却中或未达到")}
            </dd>
          </div>
        </dl>
      )}
      <details className="readout-provenance">
        <summary>{t("来源、判定参数与覆盖边界")}</summary>
        <p>
          {t(
            "只读测量，不向内核注入读出结论。积分单位为归一化幅度 × 模拟秒；痕迹不代表当前正在触达。外部文字标签不属于模型语义。",
          )}
        </p>
        {temporal && (
          <>
            <p className="mono">
              {t("载体 ")}
              {p.envelope_id}
            </p>
            <p>
              {t("重叠载体：")}
              {p.overlapping_envelopes.join("、") || t("未记录到")}
            </p>
            <p>
              {t("实际采样：")}
              {seconds(p.coverage.first_sample_us)}–
              {seconds(p.coverage.last_sample_us)}；{p.coverage.sample_count}{" "}
              {t("次。")}
            </p>
          </>
        )}
        {p.structure && (
          <p className="mono">
            {t("结构身份 ")}
            {p.structure.structure_id}
            {t(" · 状态")} {p.structure.state_signature}
            <br />
            {t("拓扑分组指纹 ")}
            {p.structure.topology_fingerprint}
            {t("（不保证同构）")}
          </p>
        )}
        <pre>{JSON.stringify(p.configuration, null, 2)}</pre>
      </details>
      {temporal && p.analysis_schema && (
        <ProcessTools
          key={recordId}
          base={base}
          recordId={recordId}
          hasSummary={!!p.process}
        />
      )}
      <div className="query-controls">
        {!temporal && (
          <Field label={t("截面内容")}>
            <select
              value={section}
              onChange={(e) => {
                setSection(e.target.value);
                setOffset(0);
              }}
            >
              <option value="raw_nodes">{t("原始节点活动")}</option>
              <option value="nodes">{t("阈值与痕迹筛选结果")}</option>
              <option value="structure_nodes">{t("候选子图节点")}</option>
              <option value="edges">{t("候选子图连接")}</option>
            </select>
          </Field>
        )}
        {temporal && (
          <>
            <Field label={t("指标分组")}>
              <select
                value={measurement}
                onChange={(e) => setMeasurement(e.target.value)}
              >
                <option value="overview">{t("积分与持续比例")}</option>
                <option value="time">{t("持续与重入")}</option>
                <option value="traces">{t("痕迹、抑制与基线")}</option>
              </select>
            </Field>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={candidates}
                onChange={(e) => {
                  setCandidates(e.target.checked);
                  setOffset(0);
                }}
              />
              {t("只看候选节点")}
            </label>
          </>
        )}
        <Field label={t("读出显示排序")}>
          <select
            value={order}
            onChange={(e) => {
              setOrder(e.target.value);
              setOffset(0);
            }}
          >
            <option value="scientific">{t("记录中的默认排序")}</option>
            <option value="id">{t("节点 ID")}</option>
            <option value="activation">
              {t(temporal ? "窗内峰值优先" : "激活优先")}
            </option>
            {temporal && (
              <>
                {p.analysis_schema && (
                  <option value="decision-activation">{t("判定时激活")}</option>
                )}
                <option value="end-activation">{t("窗末激活")}</option>
                <option value="duration">{t("活动时长")}</option>
                <option value="excess">{t("超基线积分")}</option>
                {p.process && (
                  <>
                    <option value="increase">{t("增强幅度")}</option>
                    <option value="decrease">{t("减弱幅度")}</option>
                    <option value="variation">{t("累计活动变化")}</option>
                    <option value="onset">{t("首次激活顺序")}</option>
                  </>
                )}
              </>
            )}
          </select>
        </Field>
        <Field label={t("每页读出节点")}>
          <input
            type="number"
            min="1"
            max="1000"
            value={limit}
            onChange={(e) => {
              setCustomLimit(
                Math.max(1, Math.min(1000, Number(e.target.value) || 1)),
              );
              setOffset(0);
            }}
          />
        </Field>
      </div>
      <ErrorBox error={detail.error} />
      {detail.isLoading ? (
        <Loading />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {section !== "edges" && <th>{t("匿名节点 / 外部注释")}</th>}
                {columns.map(([key, label]) => (
                  <th key={key}>{t(label)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r: any) => (
                <tr key={r.ordinal}>
                  {section !== "edges" && (
                    <td>
                      <strong className="mono">
                        {r.item.node_id ?? r.item.id}
                      </strong>
                      {temporal && !r.item.candidate && (
                        <small>{t("非候选")}</small>
                      )}
                      {r.annotations?.length > 0 && (
                        <small>{r.annotations.join(" · ")}</small>
                      )}
                    </td>
                  )}
                  {columns.map(([key, , format]) => (
                    <td key={key}>{format(r.item[key])}</td>
                  ))}
                </tr>
              ))}
              {!rows.length && (
                <tr>
                  <td colSpan={columns.length + 1}>
                    {t("当前选择下没有节点或连接。")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      <div className="readout-pagination">
        <span>
          {t("当前 ")}
          {rows.length ? offset + 1 : 0}–{offset + rows.length}
          {detail.data?.total != null && ` / ${detail.data.total}`}
          {t("；显示设置不会重算或裁剪原始记录。")}
        </span>
        <Button
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - limit))}
        >
          {t("上一页节点")}
        </Button>
        <Button
          disabled={!detail.data?.more}
          onClick={() => setOffset(offset + limit)}
        >
          {t("下一页节点")}
        </Button>
      </div>
      <div className="readout-downloads">
        <Download size={15} />
        {["json", "csv"].map((format) => (
          <a
            className="text-link"
            key={format}
            href={`/api/v2${root}/export?format=${format}`}
            download
          >
            {format === "csv"
              ? t(
                  temporal || p.raw_observation?.complete
                    ? "全部节点 CSV"
                    : "派生节点 CSV",
                )
              : t("完整记录 JSON")}
          </a>
        ))}
        {temporal &&
          ["svg", "png", "pdf"].map((format) => (
            <a
              className="text-link"
              key={format}
              href={`/api/v2${root}/export?format=${format}`}
              download
            >
              {t("完整轨迹 ")}
              {format.toUpperCase()}
            </a>
          ))}
      </div>
    </section>
  );
}

export default function ReadoutPage({
  base,
  run,
  configure,
  initialRecord,
}: {
  base: string;
  run: Run;
  configure: () => void;
  initialRecord?: string;
}) {
  const [kind, setKind] = useState("temporal_readout"),
    [classification, setClassification] = useState(""),
    [recurrent, setRecurrent] = useState(false);
  const [pages, setPages] = useState<(number | null)[]>([null]),
    [selected, setSelected] = useState<number | null>(null);
  const observe = useMutation({
    mutationFn: () =>
      api(`${base}/commands`, {
        method: "POST",
        body: JSON.stringify({ kind: "readout_observe", payload: {} }),
      }),
  });
  useEffect(() => {
    const id = Number(initialRecord);
    if (Number.isSafeInteger(id) && id > 0) setSelected(id);
  }, [initialRecord]);
  const before = pages.at(-1),
    query = new URLSearchParams({ kind, limit: "15" });
  if (classification && kind === "temporal_readout")
    query.set("classification", classification);
  if (recurrent && kind === "structural_readout")
    query.set("recurrent", "true");
  if (before) query.set("before_id", String(before));
  const history = useQuery({
    queryKey: ["readout-history", run.id, query.toString()],
    queryFn: () => api(`${base}/readouts?${query}`),
    gcTime: 0,
    refetchInterval:
      !before && ["running", "queued"].includes(run.status) ? 2000 : false,
  });
  useEffect(() => {
    void history.refetch();
  }, [run.revision, history.refetch]);
  useEffect(() => {
    if (selected === null && history.data?.rows[0])
      setSelected(history.data.rows[0].id);
  }, [selected, history.data]);
  const recordId = selected ?? history.data?.rows[0]?.id;
  const reset = () => {
    setPages([null]);
    setSelected(null);
  };
  return (
    <div className="readout-page">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>{t("时序与截面读出")}</h2>
            <p>
              {t("查看结构复现与刺激后的时序测量，保留原始来源和观察范围。")}
            </p>
          </div>
          <Link className="button" to="?view=research&tool=calibration">
            {t("时序观察实验")}
          </Link>
          <Link className="button" to={`/reports?temporal_run=${run.id}`}>
            {t("新建实验记录")}
          </Link>
          <Button onClick={configure}>
            <Settings2 size={15} />
            {t("配置读出器")}
          </Button>
          <Button
            disabled={
              observe.isPending ||
              !["queued", "running", "paused", "blocked"].includes(run.status)
            }
            onClick={() => observe.mutate()}
          >
            {t("无刺激观察")}
          </Button>
        </div>
        <ErrorBox error={observe.error} />
        {observe.isSuccess && (
          <p role="status">
            {t(
              "观察请求已排队；运行中的意识会开始记录，暂停中的意识在继续运行后开始。不会注入刺激。",
            )}
          </p>
        )}
        {!!history.data?.trigger_diagnostics?.untriggered_frames && (
          <p className="footnote">
            {t("未触发新窗口的输入帧")}{" "}
            {history.data.trigger_diagnostics.untriggered_frames} ·{" "}
            {history.data.trigger_diagnostics.last_untriggered?.source}.
            {t(
              "来源触发已关闭，不等于没有活动。可使用无刺激观察覆盖这段过程。",
            )}
          </p>
        )}
        <div className="query-controls">
          <div className="tabs" role="tablist" aria-label={t("读出类型")}>
            {[
              ["temporal_readout", "时序读出"],
              ["structural_readout", "截面被动读出"],
            ].map(([value, label]) => (
              <button
                key={value}
                role="tab"
                aria-selected={kind === value}
                className={kind === value ? "active" : ""}
                onClick={() => {
                  setKind(value);
                  reset();
                }}
              >
                {t(label)}
              </button>
            ))}
          </div>
          {kind === "temporal_readout" ? (
            <Field label={t("响应分类")}>
              <select
                value={classification}
                onChange={(e) => {
                  setClassification(e.target.value);
                  reset();
                }}
              >
                <option value="">{t("全部分类")}</option>
                {Object.entries(classes).map(([key, title]) => (
                  <option value={key} key={key}>
                    {t(title)}
                  </option>
                ))}
              </select>
            </Field>
          ) : (
            <label className="checkbox">
              <input
                type="checkbox"
                checked={recurrent}
                onChange={(e) => {
                  setRecurrent(e.target.checked);
                  reset();
                }}
              />
              {t("只看复现提示")}
            </label>
          )}
          <Button
            onClick={async () => {
              if (before) reset();
              else {
                const refreshed = await history.refetch();
                setSelected(refreshed.data?.rows[0]?.id ?? null);
              }
            }}
          >
            <RefreshCw size={15} />
            {t("刷新读出")}
          </Button>
        </div>
        {history.data?.active?.length > 0 && (
          <details className="readout-provenance">
            <summary>
              {t("正在观察 ")}
              {history.data.active.length}
              {t(" 个窗口")}
              {history.data.active.length === history.data.active_limit &&
                "（达到页面显示上限）"}
            </summary>
            <p>
              {t("当前数据库检查点 r")}
              {history.data.revision}
              {t("；暂停后窗口随模型恢复。")}
            </p>
            {history.data.active.map((w: any) => (
              <p className="mono" key={w.window_id}>
                {w.envelope_id} · {seconds(w.start_us)} →{" "}
                {seconds(w.last_sample_us)} · {w.sample_count}
                {t(" 次采样")}
                {w.delivery_end_us == null ? t(" · 输入尚未结束") : ""}
              </p>
            ))}
          </details>
        )}
        <ErrorBox error={history.error} />
        {history.isLoading ? (
          <Loading />
        ) : history.data?.rows.length ? (
          <div className="table-scroll">
            <table className="readout-history">
              <thead>
                <tr>
                  <th>{t("模拟时间 / 区间")}</th>
                  <th>{t("结果")}</th>
                  <th>{t("记录节点")}</th>
                  <th>{t("完整性")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {history.data.rows.map((row: any) => {
                  const p = row.payload;
                  return (
                    <tr
                      key={row.id}
                      className={recordId === row.id ? "selected" : ""}
                    >
                      <td>
                        {p.kind === "temporal_readout"
                          ? `${seconds(p.start_us)}–${seconds(p.end_us)}`
                          : timeLabel(row.time_us)}
                      </td>
                      <td>
                        {p.kind === "temporal_readout"
                          ? t(
                              classes[p.classification] ??
                                p.classification ??
                                "",
                            )
                          : p.structure?.recurrence_notice
                            ? t("结构复现提示")
                            : t("活动截面")}
                      </td>
                      <td>
                        {p.raw_observation?.complete
                          ? p.raw_observation.node_count
                          : p.node_count}
                      </td>
                      <td>
                        {p.analysis_schema &&
                        p.primary_result &&
                        p.reason === "maximum_window"
                          ? t("模式已判定；观察到上限")
                          : p.censored
                            ? t("删失 / 中断")
                            : p.kind === "temporal_readout"
                              ? p.coverage.baseline_complete
                                ? t("采样窗口已记录")
                                : t("基线不足")
                              : t(
                                  p.raw_observation?.complete
                                    ? "完整原始截面"
                                    : "仅派生结果 · 原始截面缺失",
                                )}
                      </td>
                      <td>
                        <Button onClick={() => setSelected(row.id)}>
                          {t("查看 #")}
                          {row.id}
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title={t("还没有匹配的读出记录")}
            detail={t(
              "读出器在启用后采样；时序记录会在窗口完成或中断时出现。新输入可在感官与输入页发送。",
            )}
          />
        )}
        <div className="readout-pagination">
          <Button
            disabled={pages.length === 1}
            onClick={() => {
              setPages(pages.slice(0, -1));
              setSelected(null);
            }}
          >
            {t("较新记录")}
          </Button>
          <Button
            disabled={!history.data?.more}
            onClick={() => {
              setPages([...pages, history.data.next]);
              setSelected(null);
            }}
          >
            {t("较早记录")}
          </Button>
          <a
            className="text-link"
            href={`/api/v2${base}/readouts/export?kind=${kind}${classification && kind === "temporal_readout" ? `&classification=${classification}` : ""}`}
            download
          >
            {t("导出所选类型 JSONL")}
          </a>
        </div>
      </section>
      {recordId && (
        <RecordDetail
          key={recordId}
          base={base}
          recordId={recordId}
          run={run}
        />
      )}
      <Link className="text-link" to="/docs?doc=docs%2Fzh%2Fv2-readouts.md">
        {t("查看读出算法、公式与测量边界")}
      </Link>
    </div>
  );
}
