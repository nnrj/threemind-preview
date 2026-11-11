import { lazy, Suspense, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, post, timeLabel, statuses } from "./api";
import { t } from "./i18n";
import { Button, ErrorBox, Field, Loading, useWorkspace } from "./ui";
import JsonEditor, { parseJson } from "./JsonEditor";
import { ActivitySummary, classes } from "./readouts";
const Chart = lazy(() => import("./Chart"));

const labels: Record<string, string> = {
  enabled: "启用时序读出",
  interval_us: "采样间隔",
  baseline_us: "刺激前基线",
  min_response_us: "递送后最短观察",
  max_response_us: "最长观察窗口",
  settle_us: "稳定判定窗口",
  trigger_manual: "观察人工输入",
  trigger_ai: "观察 AI 输入",
  trigger_ambient: "观察环境输入",
  consider_activation_strength: "综合排序考虑激活强度",
  ranking_mode: "排序方式",
  candidate_scope: "候选范围",
  activation_threshold: "活动阈值",
  excess_activation_min: "超基线阈值",
  baseline_noise_gain: "基线噪声系数",
  comparison_top_k: "收敛比较项数",
  convergence_jaccard_min: "集合相似度下限",
  convergence_drift_max: "分布变化上限",
  convergence_amplitude_drift_max: "幅度变化上限",
  decay_final_ratio_max: "衰减末值比例上限",
  display_limit: "详情默认显示数",
  max_active_windows: "同时观察窗口预算",
  max_node_entries: "累计节点预算",
  max_history_samples: "窗口采样数预算",
};

export default function TemporalProbe({ base }: { base: string }) {
  const { project } = useWorkspace(),
    root = `/projects/${project!.id}`;
  const [cues, setCues] = useState("甲。\n乙。"),
    [doses, setDoses] = useState("1");
  const [route, setRoute] = useState("continuation"),
    [learning, setLearning] = useState("inherit"),
    [blank, setBlank] = useState(0);
  const [maxWall, setMaxWall] = useState(60);
  const [activityOverride, setActivityOverride] = useState<
    Record<string, any> | null | undefined
  >(undefined);
  const [checkpoint, setCheckpoint] = useState(""),
    [override, setOverride] = useState<Record<string, any> | null>(null);
  const [json, setJson] = useState<string | null>(null),
    [selected, setSelected] = useState(""),
    [page, setPage] = useState(0);
  const [caseIndex, setCaseIndex] = useState(0),
    [nodePage, setNodePage] = useState(0),
    [allNodes, setAllNodes] = useState(false);
  const [error, setError] = useState<unknown>();
  const attempt = useRef({ key: "", id: "" });
  const source = useQuery({
    queryKey: ["temporal-probe-source", base],
    queryFn: () => api(base),
    gcTime: 0,
  });
  const history = useQuery({
    queryKey: ["temporal-probes", base, page],
    queryFn: () =>
      api(`${base}/calibrations?mode=temporal&offset=${page * 20}`),
    refetchInterval: (q) =>
      q.state.data?.rows?.some((r: any) =>
        ["pending", "leased"].includes(r.status),
      )
        ? 2000
        : false,
    gcTime: 0,
  });
  const detail = useQuery({
    queryKey: ["temporal-probe", root, selected],
    enabled: !!selected,
    queryFn: () => api(`${root}/calibrations/${selected}`),
    gcTime: 0,
    refetchInterval: (q) =>
      ["pending", "leased"].includes(q.state.data?.status) ? 1500 : false,
  });
  const result = useQuery({
    queryKey: ["temporal-probe-result", root, selected],
    enabled: detail.data?.status === "done",
    queryFn: () => api(`${root}/calibrations/${selected}/result`),
    gcTime: 0,
  });
  const form = () => ({
    mode: "temporal",
    cues: cues.split("\n").filter((v) => v.trim()),
    intensities: doses.split(/[,，]/).map((v) => {
      if (!v.trim() || !Number.isFinite(Number(v)))
        throw Error(t("请输入有效的探针强度"));
      return Number(v);
    }),
    route,
    blank_us: Math.round(blank * 1e6),
    max_wall_seconds: maxWall,
    learning_during_probe: learning === "inherit" ? null : learning === "true",
    ...(override ? { temporal_readout: override } : {}),
    ...(activityOverride !== undefined
      ? { activity_readout: activityOverride }
      : {}),
  });
  const submit = useMutation({
    mutationFn: () => {
      const body = {
        checkpoint_id: checkpoint || null,
        protocol: json === null ? form() : parseJson(json),
      };
      const key = JSON.stringify(body);
      if (attempt.current.key !== key)
        attempt.current = { key, id: crypto.randomUUID() };
      return post(`${base}/calibrations`, {
        ...body,
        operation_id: attempt.current.id,
      });
    },
    onSuccess: (value) => {
      setSelected(value.id);
      setCaseIndex(0);
      setNodePage(0);
      setPage(0);
      void history.refetch();
    },
    onError: setError,
  });
  const sample = result.data?.rows?.[caseIndex],
    window = sample?.temporal;
  const table = window
    ? allNodes
      ? window.nodes
      : window.candidate_ids
          .map((id: number) => window.nodes.find((n: any) => n.node_id === id))
          .filter(Boolean)
    : [];
  return (
    <div className="probe-calibration">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>{t("时序观察实验")}</h2>
            <p>
              {t("观察刺激后的一段活动及其收敛过程；每个探针使用独立副本。")}
            </p>
          </div>
          <button
            type="button"
            className="text-link"
            onClick={async () => {
              try {
                if (json === null) setJson(JSON.stringify(form(), null, 2));
                else {
                  const parsed: any = parseJson(json);
                  await post(`${base}/calibrations/validate`, {
                    protocol: parsed,
                  });
                  if (
                    parsed.mode !== "temporal" ||
                    !Array.isArray(parsed.cues) ||
                    !Array.isArray(parsed.intensities)
                  )
                    throw Error(t("JSON 结构无法转换为图形配置"));
                  const known = [
                    "mode",
                    "cues",
                    "intensities",
                    "route",
                    "blank_us",
                    "max_wall_seconds",
                    "learning_during_probe",
                    "temporal_readout",
                    "activity_readout",
                  ];
                  if (
                    Object.keys(parsed).some((key) => !known.includes(key)) ||
                    parsed.cues.some(
                      (v: any) => typeof v !== "string" || /[\r\n]/.test(v),
                    ) ||
                    parsed.intensities.some(
                      (v: any) => typeof v !== "number" || !Number.isFinite(v),
                    )
                  )
                    throw Error(t("JSON 结构无法转换为图形配置"));
                  setCues(parsed.cues.join("\n"));
                  setDoses(parsed.intensities.join(","));
                  setRoute(parsed.route ?? "continuation");
                  setLearning(
                    parsed.learning_during_probe == null
                      ? "inherit"
                      : String(parsed.learning_during_probe),
                  );
                  setBlank((parsed.blank_us ?? 0) / 1e6);
                  setMaxWall(parsed.max_wall_seconds ?? 60);
                  setOverride(parsed.temporal_readout ?? null);
                  setActivityOverride(parsed.activity_readout);
                  setJson(null);
                }
                setError(undefined);
              } catch (e) {
                setError(e);
              }
            }}
          >
            {t(json === null ? "JSON 编辑" : "图形配置")}
          </button>
        </div>
        <Field label={t("恢复点编号（留空固定到最新已保存点）")}>
          <input
            value={checkpoint}
            onChange={(e) => setCheckpoint(e.target.value)}
          />
        </Field>
        {json !== null ? (
          <JsonEditor
            value={json}
            onChange={setJson}
            label={t("时序实验协议 JSON")}
            rows={20}
          />
        ) : (
          <>
            <div className="form-grid">
              <Field label={t("完整探针句子（每行一句）")}>
                <textarea
                  rows={4}
                  value={cues}
                  onChange={(e) => setCues(e.target.value)}
                />
              </Field>
              <Field label={t("探针强度（逗号分隔）")}>
                <input
                  value={doses}
                  onChange={(e) => setDoses(e.target.value)}
                />
              </Field>
            </div>
            <details>
              <summary>{t("高级观察配置")}</summary>
              <div className="form-grid">
                <Field label={t("主要读出分析")}>
                  <select
                    value={
                      activityOverride === undefined
                        ? "inherit"
                        : activityOverride?.enabled
                          ? "activity"
                          : "steady"
                    }
                    onChange={(e) =>
                      setActivityOverride(
                        e.target.value === "inherit"
                          ? undefined
                          : e.target.value === "activity"
                            ? {
                                ...source.data?.spec.activity_readout,
                                enabled: true,
                              }
                            : { enabled: false },
                      )
                    }
                  >
                    <option value="inherit">{t("继承来源设置")}</option>
                    <option value="activity">
                      {t("响应模式收敛与活动过程")}
                    </option>
                    <option value="steady">
                      {t("仅活动稳态判定（原算法）")}
                    </option>
                  </select>
                </Field>
                <Field label={t("副本起点")}>
                  <select
                    value={route}
                    onChange={(e) => setRoute(e.target.value)}
                  >
                    <option value="continuation">
                      {t("继承完整状态继续")}
                    </option>
                    <option value="birth">{t("重新出生（清空活动）")}</option>
                  </select>
                </Field>
                <Field label={t("测量时学习")}>
                  <select
                    value={learning}
                    onChange={(e) => setLearning(e.target.value)}
                  >
                    <option value="inherit">{t("继承来源设置")}</option>
                    <option value="true">{t("显式开启")}</option>
                    <option value="false">{t("显式关闭")}</option>
                  </select>
                </Field>
                <Field label={t("刺激前等待（模拟秒）")}>
                  <input
                    type="number"
                    min={0}
                    max={10}
                    step="0.001"
                    value={blank}
                    onChange={(e) => setBlank(Number(e.target.value))}
                  />
                </Field>
                <Field label={t("本批实验墙钟预算（秒）")}>
                  <input
                    type="number"
                    min={1}
                    max={300}
                    value={maxWall}
                    onChange={(e) => setMaxWall(Number(e.target.value))}
                  />
                </Field>
              </div>
              <label>
                <input
                  type="checkbox"
                  checked={override != null}
                  onChange={(e) =>
                    setOverride(
                      e.target.checked
                        ? { ...source.data?.spec.temporal_readout }
                        : null,
                    )
                  }
                />
                {t("自定义时序读出参数（默认继承来源）")}
              </label>
              {override && (
                <div className="form-grid">
                  {Object.entries(override).map(([key, value]) => (
                    <Field
                      key={key}
                      label={`${t(labels[key] ?? key)}${key.endsWith("_us") ? " (s)" : ""}`}
                    >
                      {typeof value === "boolean" ? (
                        <input
                          type="checkbox"
                          checked={value}
                          onChange={(e) =>
                            setOverride({
                              ...override,
                              [key]: e.target.checked,
                            })
                          }
                        />
                      ) : typeof value === "number" ? (
                        <input
                          type="number"
                          step="any"
                          value={key.endsWith("_us") ? value / 1e6 : value}
                          onChange={(e) =>
                            setOverride({
                              ...override,
                              [key]: key.endsWith("_us")
                                ? Math.round(Number(e.target.value) * 1e6)
                                : Number(e.target.value),
                            })
                          }
                        />
                      ) : (
                        <select
                          value={value}
                          onChange={(e) =>
                            setOverride({ ...override, [key]: e.target.value })
                          }
                        >
                          {(key === "ranking_mode"
                            ? ["composite", "duration", "activation-integral"]
                            : [
                                "associative-or-persistent",
                                "associative-only",
                                "all-active",
                              ]
                          ).map((v) => (
                            <option key={v}>{v}</option>
                          ))}
                        </select>
                      )}
                    </Field>
                  ))}
                </div>
              )}
            </details>
          </>
        )}
        <ErrorBox error={error ?? submit.error} />
        <Button
          variant="primary"
          disabled={submit.isPending}
          onClick={() => {
            setError(undefined);
            submit.mutate();
          }}
        >
          {t("开始时序观察")}
        </Button>
      </section>
      <section className="panel">
        <h3>{t("时序实验记录")}</h3>
        <select
          aria-label={t("选择时序实验")}
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value);
            setCaseIndex(0);
            setNodePage(0);
          }}
        >
          <option value="">{t("请选择")}</option>
          {history.data?.rows?.map((r: any) => (
            <option key={r.id} value={r.id}>
              {r.id.slice(0, 8)} ·{" "}
              {t(
                statuses[
                  r.id === selected && detail.data
                    ? detail.data.status
                    : r.status
                ] ?? r.status,
              )}
            </option>
          ))}
        </select>
        <button
          className="text-link"
          disabled={!page}
          onClick={() => setPage((v) => v - 1)}
        >
          {t("上一页")}
        </button>
        <button
          className="text-link"
          disabled={!history.data?.more}
          onClick={() => setPage((v) => v + 1)}
        >
          {t("下一页")}
        </button>
        <ErrorBox
          error={
            history.error ?? detail.error ?? result.error ?? detail.data?.error
          }
        />
        {selected && detail.data?.status !== "done" && (
          <p>{t(statuses[detail.data?.status] ?? "加载中")}</p>
        )}
        {result.isLoading && <Loading />}
        {result.data && (
          <>
            <p>
              {t("来源状态")} <code>{result.data.source_hash}</code>
            </p>
            <select
              aria-label={t("选择探针结果")}
              value={caseIndex}
              onChange={(e) => {
                setCaseIndex(Number(e.target.value));
                setNodePage(0);
              }}
            >
              {result.data.rows.map((r: any, i: number) => (
                <option key={r.id} value={i}>
                  {r.cue} · {r.intensity} ·{" "}
                  {t(classes[r.classification] ?? r.classification)}
                </option>
              ))}
            </select>
            <p>
              {t(
                classes[sample?.classification] ?? sample?.classification ?? "",
              )}{" "}
              · {sample?.reason}
            </p>
            {window && (
              <>
                <ActivitySummary value={window} />
                <p>
                  {timeLabel(window.start_us)} – {timeLabel(window.end_us)} ·{" "}
                  {t("实际递送结束")} {timeLabel(window.delivery_end_us)} ·{" "}
                  {t("基线覆盖")}{" "}
                  {timeLabel(window.coverage.baseline_coverage_us)}
                </p>
                <Suspense fallback={<Loading />}>
                  <Chart
                    rows={window.series.map((r: any) => ({
                      time_us: r.time_us,
                      activation: r.total,
                    }))}
                    title={t("时序活动变化（超基线总量）")}
                    step
                  />
                </Suspense>
                <label>
                  <input
                    type="checkbox"
                    checked={allNodes}
                    onChange={(e) => {
                      setAllNodes(e.target.checked);
                      setNodePage(0);
                    }}
                  />
                  {t("显示全部节点（包含非候选及零活动）")}
                </label>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>{t("节点")}</th>
                        <th>{t("标签")}</th>
                        <th>{t("综合得分")}</th>
                        <th>{t("活动时长")}</th>
                        <th>{t("超基线积分")}</th>
                        <th>{t("窗末激活")}</th>
                        {window.analysis_schema && <th>{t("判定时激活")}</th>}
                        <th>{t("窗内峰值")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {table
                        .slice(nodePage * 50, (nodePage + 1) * 50)
                        .map((n: any) => (
                          <tr key={n.node_id}>
                            <td>#{n.node_id}</td>
                            <td>
                              {window.annotations?.[n.node_id]?.join(" · ") ??
                                "—"}
                            </td>
                            <td>{n.score?.toPrecision(5) ?? "—"}</td>
                            <td>{timeLabel(n.active_us)}</td>
                            <td>{n.excess_integral?.toPrecision(5)}</td>
                            <td>{n.last_activation?.toPrecision(5)}</td>
                            {window.analysis_schema && (
                              <td>
                                {n.decision_activation?.toPrecision(5) ?? "—"}
                              </td>
                            )}
                            <td>{n.peak_activation?.toPrecision(5)}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
                <button
                  className="text-link"
                  disabled={!nodePage}
                  onClick={() => setNodePage((v) => v - 1)}
                >
                  {t("上一页")}
                </button>
                <button
                  className="text-link"
                  disabled={(nodePage + 1) * 50 >= table.length}
                  onClick={() => setNodePage((v) => v + 1)}
                >
                  {t("下一页")}
                </button>
              </>
            )}
            <p>
              <a
                className="button"
                href={`/api/v2${root}/artifacts/${detail.data.result.bundle_artifact_id}`}
              >
                {t("导出完整证据 ZIP")}
              </a>
            </p>
            <p>
              <Link
                className="button"
                to={`/reports?temporal_run=${base.split("/").at(-1)}&calibration=${selected}`}
              >
                {t("用此时序实验创建记录")}
              </Link>
            </p>
          </>
        )}
      </section>
    </div>
  );
}
