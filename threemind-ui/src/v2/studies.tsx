import { t } from "./i18n";
import { can } from "./access";
import { lazy, Suspense, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import {
  Plus,
  FlaskConical,
  GitCompareArrows,
  ArrowRight,
  Download,
} from "lucide-react";
import { api, post, projectPath, numberLabel } from "./api";
import {
  useWorkspace,
  PageTitle,
  Button,
  Field,
  ErrorBox,
  Empty,
  Badge,
  RunTable,
  Loading,
} from "./ui";
import { useRuns } from "./research";
import { StudyDesigner } from "./studyDesigner";
const Chart = lazy(() => import("./Chart"));
const Development = lazy(() => import("./development"));
const Evolution = lazy(() => import("./evolution"));
const Assessments = lazy(() => import("./assessments"));
const Ecology = lazy(() => import("./ecology"));
const metricNames: Record<string, string> = {
  nodes: "节点数",
  edges: "有向边数",
  activation: "总激活量",
  inhibition: "总抑制势",
  mean_weight: "平均连接权重",
  mean_activation: "节点平均激活",
  active_fraction: "活动节点比例",
  saturated_fraction: "饱和节点比例",
  edge_density: "连接密度",
  activation_auc: "总激活时间积分",
  samples: "观测点数",
  energy_reserve: "能量储备（实验单位）",
  energy_consumed: "累计能量消耗（自记账起点）",
  energy_supplied: "累计接受供给（自记账起点）",
  energy_unserved: "累计未满足需求（自记账起点）",
};
function metricName(key: string): string {
  if (key.startsWith("phase.")) {
    const [, phase, endpoint] = key.split(".");
    return `${phase} · ${t(metricNames[endpoint.replace("_time_mean", "")] ?? endpoint)} ${t("（时间均值）")}`;
  }
  return t(metricNames[key] ?? key);
}

export default function Studies({ compare = false }: { compare?: boolean }) {
  const [params, setParams] = useSearchParams();
  const developmental = params.get("tab") === "development";
  const evolving = params.get("tab") === "evolution";
  const ecological = params.get("tab") === "ecology";
  const assessing = params.get("tab") === "assessment";
  if (compare) return <PairedStudies compare />;
  return (
    <>
      <div
        className="tabs page-tabs"
        role="tablist"
        aria-label={t("实验与训练页面")}
      >
        <button
          role="tab"
          aria-selected={
            !developmental && !evolving && !ecological && !assessing
          }
          className={
            !developmental && !evolving && !ecological && !assessing
              ? "active"
              : ""
          }
          onClick={() => setParams({})}
        >
          {t("配对实验")}
        </button>
        <button
          role="tab"
          aria-selected={developmental}
          className={developmental ? "active" : ""}
          onClick={() => setParams({ tab: "development" })}
        >
          {t("发育与先天模型")}
        </button>
        <button
          role="tab"
          aria-selected={evolving}
          className={evolving ? "active" : ""}
          onClick={() => setParams({ tab: "evolution" })}
        >
          {t("多代定向训练")}
        </button>
        <button
          role="tab"
          aria-selected={ecological}
          className={ecological ? "active" : ""}
          onClick={() => setParams({ tab: "ecology" })}
        >
          {t("生态演化")}
        </button>
        <button
          role="tab"
          aria-selected={assessing}
          className={assessing ? "active" : ""}
          onClick={() => setParams({ tab: "assessment" })}
        >
          {t("独立评估")}
        </button>
      </div>
      {assessing ? (
        <Suspense fallback={<Loading />}>
          <Assessments />
        </Suspense>
      ) : ecological ? (
        <Suspense fallback={<Loading />}>
          <Ecology />
        </Suspense>
      ) : evolving ? (
        <Suspense fallback={<Loading />}>
          <Evolution />
        </Suspense>
      ) : developmental ? (
        <Suspense fallback={<Loading />}>
          <Development />
        </Suspense>
      ) : (
        <PairedStudies />
      )}
    </>
  );
}

function PairedStudies({ compare = false }: { compare?: boolean }) {
  const [params] = useSearchParams();
  const { project, user } = useWorkspace(),
    client = useQueryClient(),
    base = projectPath(project!.id);
  const [offset, setOffset] = useState(0),
    [search, setSearch] = useState("");
  const studies = useQuery({
    queryKey: ["studies", project?.id, search, offset],
    queryFn: () =>
      api<{ rows: any[]; more: boolean }>(
        `${base}/study-library?q=${encodeURIComponent(search)}&offset=${offset}`,
      ),
    staleTime: 30000,
  });
  const jobs = useQuery({
    queryKey: ["jobs", project?.id],
    queryFn: () => api<any[]>(`${base}/jobs`),
    refetchInterval: 2000,
  });
  const [open, setOpen] = useState(false),
    [draft, setDraft] = useState<any>();
  const [selected, setSelected] = useState(params.get("study") || ""),
    [control, setControl] = useState(""),
    [treatment, setTreatment] = useState("");
  const [metric, setMetric] = useState("mean_activation"),
    [metricGroup, setMetricGroup] = useState("overall");
  const studyId = selected || studies.data?.rows[0]?.id;
  const detail = useQuery({
    queryKey: ["study", project?.id, studyId],
    queryFn: () => api<any>(`${base}/studies/${studyId}`),
    enabled: !!studyId,
    staleTime: Infinity,
    gcTime: 0,
  });
  const study = detail.data;
  const runs = useRuns(studyId, !!studyId);
  const studyRuns = (runs.data ?? []).filter(
    (r) => r.spec.study_id === study?.id,
  );
  const conditions = study?.protocol.arms?.map((a: any) => a.name) ?? [];
  const selectedControl = conditions.includes(control)
      ? control
      : conditions[0],
    selectedTreatment = conditions.includes(treatment)
      ? treatment
      : conditions[1];
  const trajectory = useQuery({
    queryKey: [
      "study-trajectory",
      project?.id,
      study?.id,
      metric,
      studyRuns.map((r) => r.revision).join(","),
    ],
    queryFn: () =>
      api<any>(
        `${base}/studies/${study.id}/trajectories?metric=${metric}&buckets=200`,
      ),
    enabled: !!study && studyRuns.length > 0,
    gcTime: 0,
  });
  const analysis = useMutation({
    mutationFn: () =>
      post(`${base}/analyses`, {
        study_id: study.id,
        control: selectedControl,
        treatment: selectedTreatment,
        seed: 71423,
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["jobs"] }),
  });
  const analysisJobs =
    jobs.data?.filter(
      (j) =>
        j.kind === "analysis" &&
        j.params.study_id === study?.id &&
        j.params.control === selectedControl &&
        j.params.treatment === selectedTreatment,
    ) ?? [];
  const result = analysisJobs.find(
    (j) =>
      j.status === "done" &&
      (!study?.protocol.base.phases?.length ||
        j.result?.analysis?.phase_method === "half-open-microsecond/2"),
  )?.result;
  return (
    <>
      <PageTitle
        eyebrow={compare ? "COMPARISON & ABLATION" : "EXPERIMENT DESIGN"}
        title={compare ? t("比较与消融") : t("实验与训练")}
        description={
          compare
            ? t("在相同起点和匹配环境下，比较机制变化带来的效应。")
            : t("冻结协议、准备条件组，并行执行可复现的研究。")
        }
        actions={
          <Button
            variant="primary"
            disabled={!can(user, "experiments.create")}
            onClick={() => {
              setDraft(undefined);
              setOpen(true);
            }}
          >
            <Plus size={16} />
            {t("设计新实验")}
          </Button>
        }
      />
      <div className="method-strip">
        <span>
          <i>1</i>
          {t("共享发育状态")}
        </span>
        <ArrowRight size={16} />
        <span>
          <i>2</i>
          {t("条件分叉")}
        </span>
        <ArrowRight size={16} />
        <span>
          <i>3</i>
          {t("独立环境区组")}
        </span>
        <ArrowRight size={16} />
        <span>
          <i>4</i>
          {t("效应与证据")}
        </span>
      </div>
      <div className="study-search">
        <Field label={t("检索已有实验")}>
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setOffset(0);
              setSelected("");
            }}
          />
        </Field>
        <Button
          disabled={offset === 0}
          onClick={() => {
            setOffset(offset - 30);
            setSelected("");
          }}
        >
          {t("上一页实验")}
        </Button>
        <span>{t("第 {page} 页", { page: Math.floor(offset / 30) + 1 })}</span>
        <Button
          disabled={!studies.data?.more}
          onClick={() => {
            setOffset(offset + 30);
            setSelected("");
          }}
        >
          {t("下一页实验")}
        </Button>
      </div>
      <ErrorBox error={studies.error ?? detail.error ?? analysis.error} />
      {!study ? (
        <section className="panel">
          <Empty
            title={t("从一个明确的对照开始")}
            detail={t(
              "默认协议比较完整可塑性、关闭可塑性与关闭局部抑制；你可以修改条件参数和结构干预。",
            )}
            action={
              <Button
                variant="primary"
                onClick={() => {
                  setDraft(undefined);
                  setOpen(true);
                }}
              >
                <FlaskConical size={16} />
                {t("设计实验")}
              </Button>
            }
          />
        </section>
      ) : (
        <>
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>{t("实验协议")}</h2>
                <p>{t("协议一经创建即冻结。改变设计时创建新的实验。")}</p>
                <button
                  type="button"
                  className="text-link"
                  onClick={() => {
                    setDraft(study.protocol);
                    setOpen(true);
                  }}
                >
                  {t("以此协议再设计")}
                </button>
              </div>
              <select
                aria-label={t("选择实验")}
                value={study.id}
                onChange={(e) => setSelected(e.target.value)}
              >
                {!studies.data?.rows.some((s) => s.id === study.id) && (
                  <option value={study.id}>{study.name}</option>
                )}
                {studies.data?.rows.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="study-summary">
              <div>
                <span>{t("独立环境种子")}</span>
                <strong>{study.protocol.seeds.join(" · ")}</strong>
              </div>
              <div>
                <span>{t("条件组")}</span>
                <strong>
                  {conditions.length}
                  {t(" 组")}
                </strong>
              </div>
              <div>
                <span>{t("发育阶段")}</span>
                <strong>{study.protocol.warmup_s} s</strong>
              </div>
              <div>
                <span>{t("每组运行")}</span>
                <strong>{study.protocol.base.duration_s} s</strong>
              </div>
            </div>
            <div className="condition-grid">
              {study.protocol.arms.map((arm: any, i: number) => (
                <div key={arm.name}>
                  <span className="condition-number">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <h3>{arm.name}</h3>
                  <code>
                    {Object.keys(arm.config_patch).length
                      ? JSON.stringify(arm.config_patch)
                      : t("默认完整机制")}
                  </code>
                  {Object.keys(arm.runtime_patch ?? {}).length > 0 && (
                    <p>
                      {t("工具覆盖：")}
                      {JSON.stringify(arm.runtime_patch)}
                    </p>
                  )}
                  {arm.intervention && (
                    <p>
                      {t("结构干预：")}
                      {JSON.stringify(arm.intervention)}
                    </p>
                  )}
                  {arm.max_channels != null && (
                    <p>
                      {t("每次最多 ")}
                      {arm.max_channels}
                      {t(" 个物理感官通道")}
                    </p>
                  )}
                  {arm.actuator_feedback === false && (
                    <p>{t("动作反馈关闭；外生物理力保持运行")}</p>
                  )}
                  {arm.phases && (
                    <p>
                      {arm.phases
                        .map(
                          (p: any) =>
                            `${p.name} ${p.input_enabled ? "输入开启" : "输入关闭"}`,
                        )
                        .join(" · ")}
                    </p>
                  )}
                </div>
              ))}
            </div>
            <details className="protocol-details">
              <summary>{t("完整协议与校验")}</summary>
              <pre>{JSON.stringify(study.protocol, null, 2)}</pre>
              <code>{study.protocol_hash}</code>
            </details>
          </section>
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>{t("条件动力学")}</h2>
                <p>
                  {t(
                    "覆盖全部已提交历史；先在各运行内按时间分箱，再对独立运行等权平均。",
                  )}
                </p>
              </div>
              <select
                aria-label={t("比较曲线指标")}
                value={metric}
                onChange={(e) => setMetric(e.target.value)}
              >
                <option value="mean_activation">{t("节点平均激活")}</option>
                <option value="saturated_fraction">{t("饱和节点比例")}</option>
                <option value="active_fraction">{t("活动节点比例")}</option>
                <option value="edge_density">{t("连接密度")}</option>
                <option value="mean_weight">{t("平均连接权重")}</option>
                <option value="activation">{t("总激活量")}</option>
                {[
                  "energy_reserve",
                  "energy_consumed",
                  "energy_supplied",
                  "energy_unserved",
                ].map((key) => (
                  <option key={key} value={key}>
                    {t(metricNames[key])}
                  </option>
                ))}
              </select>
            </div>
            <ErrorBox error={trajectory.error} />
            {trajectory.data ? (
              <Suspense fallback={<p>{t("正在准备图表…")}</p>}>
                <Chart
                  rows={[]}
                  metric={metric}
                  height={330}
                  series={trajectory.data.series.filter((s: any) =>
                    [selectedControl, selectedTreatment].includes(s.name),
                  )}
                  phases={trajectory.data.phases}
                />
              </Suspense>
            ) : (
              <p className="muted">{t("首次检查点提交后显示条件曲线。")}</p>
            )}
            <p className="footnote">
              {t(
                "横轴从条件分叉开始。曲线用于观察趋势，统计检验使用每个独立运行的完整记录；空时间箱保留缺口，未完成的运行可能造成样本覆盖不齐。",
              )}
            </p>
          </section>
          <section className="panel">
            <div className="panel-heading">
              <h2>{t("配对运行")}</h2>
              <span className="muted">
                {
                  studyRuns.filter((r) =>
                    ["completed", "dead"].includes(r.status),
                  ).length
                }{" "}
                / {study.protocol.seeds.length * conditions.length}
                {t(" 已完成")}
              </span>
            </div>
            {studyRuns.length ? (
              <RunTable runs={studyRuns} />
            ) : (
              <Empty
                title={t("正在准备发育状态")}
                detail={t(
                  "训练器将为每个环境种子生成共同起点，再创建条件分支。",
                )}
              />
            )}
          </section>
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>{t("统计分析")}</h2>
                <p>
                  {t(
                    "实验单位是独立运行／环境对，不把逐时刻样本当作独立重复。",
                  )}
                </p>
              </div>
              <Button
                variant="primary"
                disabled={
                  analysis.isPending ||
                  !studyRuns.length ||
                  studyRuns.length !==
                    study.protocol.seeds.length * conditions.length ||
                  studyRuns.some(
                    (r) => !["completed", "dead"].includes(r.status),
                  ) ||
                  selectedControl === selectedTreatment
                }
                onClick={() => analysis.mutate()}
              >
                <GitCompareArrows size={16} />
                {t("执行配对分析")}
              </Button>
            </div>
            <div className="analysis-controls">
              <Field label={t("对照条件")}>
                <select
                  value={selectedControl ?? ""}
                  onChange={(e) => setControl(e.target.value)}
                >
                  {conditions.map((c: string) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </Field>
              <Field label={t("干预条件")}>
                <select
                  value={selectedTreatment ?? ""}
                  onChange={(e) => setTreatment(e.target.value)}
                >
                  {conditions.map((c: string) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </Field>
              <span className="muted">
                {t("Bootstrap 95% CI · 符号翻转检验 · Holm 校正")}
              </span>
            </div>
            {analysisJobs[0] && analysisJobs[0].status !== "done" && (
              <div className="notice">
                <Badge status={analysisJobs[0].status} />
                {analysisJobs[0].error ?? t("统计任务已提交。")}
              </div>
            )}
            {result?.analysis ? (
              <>
                <div className="panel-heading">
                  <p>
                    {t(
                      "平均差值＝干预条件－对照条件；界面筛选不会重新计算或缩小 Holm 校正范围。",
                    )}
                  </p>
                  <select
                    aria-label={t("统计指标范围")}
                    value={metricGroup}
                    onChange={(e) => setMetricGroup(e.target.value)}
                  >
                    <option value="overall">{t("整体终点")}</option>
                    <option value="phases">{t("阶段终点")}</option>
                    <option value="all">{t("全部指标")}</option>
                  </select>
                </div>
                <div className="table-scroll">
                  <table className="numeric-table">
                    <thead>
                      <tr>
                        <th>{t("指标")}</th>
                        <th>{t("有效配对")}</th>
                        <th>{t("缺失")}</th>
                        <th>{t("对照均值")}</th>
                        <th>{t("干预均值")}</th>
                        <th>{t("平均差值")}</th>
                        <th>95% CI</th>
                        <th>{t("配对效应 dz")}</th>
                        <th>{t("校正 p")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.analysis.metrics
                        .filter(
                          (m: any) =>
                            metricGroup === "all" ||
                            m.metric.startsWith("phase.") ===
                              (metricGroup === "phases"),
                        )
                        .map((m: any) => (
                          <tr key={m.metric}>
                            <td title={m.metric}>{metricName(m.metric)}</td>
                            <td>{m.n}</td>
                            <td>{m.missing_pairs}</td>
                            <td>{numberLabel(m.control_mean, 5)}</td>
                            <td>{numberLabel(m.treatment_mean, 5)}</td>
                            <td>{numberLabel(m.difference, 5)}</td>
                            <td>
                              {m.ci95
                                ? m.ci95
                                    .map((v: number) => numberLabel(v, 5))
                                    .join(" ~ ")
                                : "—"}
                            </td>
                            <td>{numberLabel(m.paired_dz, 4)}</td>
                            <td>{numberLabel(m.p_holm, 5)}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
                <div className="panel-footer">
                  <span>
                    {t("结果来自冻结数据快照 ·")}{" "}
                    {result.analysis.data_hash.slice(0, 16)}…
                  </span>
                  <a
                    className="text-link"
                    href={`/api/v2${base}/artifacts/${result.artifact_id}`}
                  >
                    <Download size={14} />
                    {t("下载完整分析与配对数据")}
                  </a>
                  {result.csv_artifact_id && (
                    <a
                      className="text-link"
                      href={`/api/v2${base}/artifacts/${result.csv_artifact_id}`}
                    >
                      <Download size={14} />
                      {t("下载统计表 CSV")}
                    </a>
                  )}
                </div>
                {result.analysis.pairs.some(
                  (p: any) => p.phase_evidence?.treatment?.length,
                ) && (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>{t("环境种子")}</th>
                          <th>{t("条件")}</th>
                          <th>{t("撤除阶段")}</th>
                          <th>{t("覆盖")}</th>
                          <th>{t("观察到的稳定衰减")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.analysis.pairs.flatMap((p: any) =>
                          ["control", "treatment"].flatMap((side) =>
                            (p.phase_evidence?.[side] ?? [])
                              .filter((phase: any) => phase.settling)
                              .map((phase: any) => (
                                <tr key={`${p.seed}:${side}:${phase.name}`}>
                                  <td>{p.seed}</td>
                                  <td>
                                    {side === "control"
                                      ? selectedControl
                                      : selectedTreatment}
                                  </td>
                                  <td>{phase.name}</td>
                                  <td>
                                    {phase.complete ? t("完整") : t("不完整")}
                                  </td>
                                  <td>
                                    {phase.settling.right_censored
                                      ? t(
                                          "未观察到 · 随访 {value0} s（右删失）",
                                          {
                                            value0: String(
                                              numberLabel(
                                                phase.settling.followup_s,
                                              ),
                                            ),
                                          },
                                        )
                                      : `${numberLabel(phase.settling.time_s)} s`}
                                  </td>
                                </tr>
                              )),
                          ),
                        )}
                      </tbody>
                    </table>
                    <p className="footnote">
                      {t(
                        "稳定衰减：节点平均激活 ≤ 0.0001，连续保持至少 0.5 s 且持续至窗口结束。右删失表示观察窗口内没有确认满足此条件；不代表无限持续，也不作为已测得时长参与均值检验。",
                      )}
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div className="analysis-empty">
                {t(
                  "运行完成后，在这里查看效应量、置信区间、缺失数据和校正后的检验结果。",
                )}
              </div>
            )}
          </section>
        </>
      )}
      {open && (
        <StudyDesigner
          project={project!.id}
          initial={draft}
          close={() => setOpen(false)}
          created={(id) => {
            setOpen(false);
            setSelected(id);
            client.invalidateQueries({ queryKey: ["studies"] });
            client.invalidateQueries({ queryKey: ["jobs"] });
          }}
        />
      )}
    </>
  );
}
