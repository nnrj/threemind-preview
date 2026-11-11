import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Plus, Cpu } from "lucide-react";
import { t } from "./i18n";
import { api, post, projectPath } from "./api";
import { ProjectDestination } from "./ResourceBrowser";
import {
  Button,
  ErrorBox,
  Field,
  Loading,
  PageTitle,
  useWorkspace,
} from "./ui";
import { useCatalogue } from "./configuration";
import { NewRun } from "./research";
import { preferences } from "./preferences";

function download(value: unknown, name: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function Kernels() {
  const catalog = useCatalogue();
  const { project } = useWorkspace();
  const [search, setSearch] = useSearchParams();
  const tab = search.get("view") === "transformer" ? "transformer" : "kernels";
  const setTab = (view: string) => setSearch({ view });
  const [create, setCreate] = useState<string | null>(null);
  const notes: Record<string, [string, string]> = {
    "threemind.causal/9": [
      "保留的 V3 基线",
      "原有激活、抑制、可塑性和生命周期；既有模型继续使用原身份。",
    ],
    "threemind.continuous/1": [
      "连续增强候选",
      "增加逐连接短时资源、快迹及接收端局部上下文。三个新机制可分别关闭。",
    ],
    "threemind.continuous-memory/1": [
      "记忆机制研究候选",
      "分别控制耗竭、易化和既有连接巩固；关闭巩固仍保留遗忘与抑制。",
    ],
    "threemind.continuous-memory/2": [
      "记忆机制校准版本",
      "新连接等待真实联想触达后结算局部新颖性，保留立即计算对照。已有意识不会自动切换版本。",
    ],
    "threemind.continuous-memory/3": [
      "活动调节保持版本",
      "实际活动延长连接和节点支持度的半衰期，闲置后逐渐回落；休眠与唤醒默认关闭。",
    ],
    "threemind.continuous-memory/3.1": [
      "局部回收修正版",
      "沿用 /3 的学习与保持公式；零响应节点也登记局部回收期限。已有 /3 意识保持原版本。",
    ],
    "threemind.continuous-memory/4": [
      "局部事件执行版本",
      "节点与连接自行结算衰减、安排传播和失效。默认统一接收；可对照独立相位、逐条到达及局部资源场。旧内核继续可用。",
    ],
    "threemind.continuous-memory/5": [
      "局部事件与学习规则修订",
      "默认采用 /2 的接收与学习规则，保留局部执行、半衰期和回收；统一接收、同刻整合与异步传播是注明差异的研究选项。旧版不自动升级。",
    ],
    "threemind.continuous-memory/5.1": [
      "局部执行性能修订",
      "保持 /5 的动力学、参数默认值和研究选项，减少对象复制和内部消息开销。已有意识继续使用其原版本，不自动升级。",
    ],
    "threemind.lif/1": [
      "独立脉冲候选",
      "使用膜电位、电流、发放和局部时序学习。图中显示去极化投影，不与原核激活混作同一指标。",
    ],
  };
  return (
    <>
      <PageTitle
        eyebrow="KERNELS & LOCAL TOOLS"
        title={t("内核与对照工具")}
        description={t(
          "先选择研究假设，再配置意识。外部 Transformer 工具单独记录贡献。",
        )}
      />
      <div className="tabs page-tabs" aria-label={t("内核工具")}>
        <button
          className={tab === "kernels" ? "active" : ""}
          onClick={() => setTab("kernels")}
        >
          {t("内核版本")}
        </button>
        <button
          className={tab === "transformer" ? "active" : ""}
          onClick={() => setTab("transformer")}
        >
          {t("本地 Transformer")}
        </button>
      </div>
      {tab === "kernels" ? (
        <>
          <ErrorBox error={catalog.error} />
          {catalog.isPending ? (
            <Loading />
          ) : (
            <div className="kernel-cards">
              {catalog.data?.kernels?.map((kernel: any) => (
                <article className="panel kernel-card" key={kernel.kernel_id}>
                  <div className="kernel-card-title">
                    <Cpu size={23} />
                    <span>
                      {kernel.default
                        ? t("新建默认 · 研究版本")
                        : kernel.baseline
                          ? t("保留基线")
                          : t("实验候选")}
                    </span>
                  </div>
                  <h2>{t(notes[kernel.kernel_id]?.[0] ?? kernel.title)}</h2>
                  <p>{t(notes[kernel.kernel_id]?.[1] ?? "")}</p>
                  <dl>
                    <dt>{t("版本")}</dt>
                    <dd>{kernel.kernel_id}</dd>
                    <dt>{t("观测量")}</dt>
                    <dd>{kernel.observation_quantity}</dd>
                  </dl>
                  <details>
                    <summary>{t("机制与协议")}</summary>
                    <p>
                      {kernel.hypothesis_id}
                      <br />
                      {kernel.state_schema}
                    </p>
                    <ul>
                      {kernel.mechanisms.map((m: any) => (
                        <li key={m.id}>{m.id}</li>
                      ))}
                    </ul>
                  </details>
                  <div className="kernel-actions">
                    <Button
                      variant="primary"
                      onClick={() => setCreate(kernel.kernel_id)}
                    >
                      <Plus size={16} />
                      {t("创建意识")}
                    </Button>
                    <Button
                      onClick={() =>
                        download(
                          {
                            schema: "threemind.kernel-definition/1",
                            kernel_id: kernel.kernel_id,
                            state_schema: kernel.state_schema,
                            hypothesis_id: kernel.hypothesis_id,
                            operators: kernel.mechanisms,
                            config:
                              catalog.data?.kernel_defaults?.[kernel.kernel_id],
                          },
                          kernel.kernel_id.replaceAll("/", "-") + ".json",
                        )
                      }
                    >
                      <Download size={16} />
                      {t("导出定义")}
                    </Button>
                  </div>
                </article>
              ))}
            </div>
          )}
          <div className="panel kernel-help">
            <h3>{t("如何比较")}</h3>
            <p>
              {t(
                "同一内核的机制消融可在「比较与消融」配置；不同内核请创建独立意识，使用同源刺激，并分别注明观测量与资源预算。候选通过工程验证，不代表已证实研究收益。",
              )}
            </p>
            <Link to="/compare">{t("比较与消融")}</Link> ·{" "}
            <Link to="/docs?doc=docs%2Fzh%2Fplans%2Fmulti-kernel-implementation.md">
              {t("机制规范与实施记录")}
            </Link>
          </div>
          <NewRun
            open={!!create}
            kernelId={create ?? undefined}
            onOpenChange={(open) => !open && setCreate(null)}
          />
        </>
      ) : (
        <ProjectDestination>
          <TransformerTool key={project?.id} />
        </ProjectDestination>
      )}
    </>
  );
}

function TransformerTool() {
  const { project } = useWorkspace(),
    client = useQueryClient(),
    base = `${projectPath(project!.id)}/transformer`;
  const status = useQuery<any>({
    queryKey: ["transformer", project?.id],
    queryFn: () => api(base),
    refetchInterval: 3000,
  });
  const [corpus, setCorpus] = useState("1 2 3\n4 5 6"),
    [evaluation, setEvaluation] = useState(""),
    [vocabulary, setVocabulary] = useState(8),
    [steps, setSteps] = useState(200),
    [seconds, setSeconds] = useState(30),
    [width, setWidth] = useState(32),
    [layers, setLayers] = useState(2),
    [computeDevice, setComputeDevice] = useState<string>(
      () => preferences().toolComputeDevice,
    ),
    [gpuMemory, setGpuMemory] = useState(() => preferences().toolGpuMemory),
    [gpuHeadroom, setGpuHeadroom] = useState(
      () => preferences().toolGpuHeadroom,
    ),
    [selected, setSelected] = useState(""),
    [tokens, setTokens] = useState("1 2"),
    [notice, setNotice] = useState("");
  const requests = useRef<Record<string, { body: string; id: string }>>({});
  function requestId(kind: string, body: unknown) {
    const text = JSON.stringify(body),
      prior = requests.current[kind];
    if (prior?.body === text) return prior.id;
    const id = crypto.randomUUID();
    requests.current[kind] = { body: text, id };
    return id;
  }
  function rows(text: string) {
    return text.trim()
      ? text
          .trim()
          .split(/\r?\n/)
          .filter(Boolean)
          .map((line) =>
            line
              .trim()
              .split(/[\s,]+/)
              .map((v) => {
                if (!/^\d+$/.test(v))
                  throw new Error(
                    t("请使用非负整数类别编号，每行一个完整序列。"),
                  );
                return Number(v);
              }),
          )
      : [];
  }
  const train = useMutation({
    mutationFn: async () => {
      const protocol = {
        architecture: {
          vocabulary,
          context: 64,
          width,
          heads: 4,
          layers,
          seed: 17,
        },
        sequences: rows(corpus),
        evaluation: rows(evaluation),
        steps,
        wall_seconds: seconds,
        compute_device: computeDevice,
        gpu_memory_mib: gpuMemory,
        gpu_headroom_mib: gpuHeadroom,
      };
      return post(base + "/training", {
        request_id: requestId("train", protocol),
        protocol,
      });
    },
    onSuccess: () => {
      delete requests.current.train;
      setNotice(
        t("训练已排队。结果和数值模型将保存为项目证据，不改动现有意识。"),
      );
      client.invalidateQueries({ queryKey: ["transformer"] });
    },
  });
  const predict = useMutation({
    mutationFn: async () => {
      const parsed = rows(tokens);
      if (parsed.length !== 1) throw new Error(t("请提供一个完整的查询序列。"));
      const query = {
          tokens: parsed[0],
          compute_device: computeDevice,
          gpu_memory_mib: gpuMemory,
          gpu_headroom_mib: gpuHeadroom,
        },
        model = selected || status.data?.models?.[0]?.id;
      return post(base + `/models/${model}/predictions`, {
        request_id: requestId("predict", { model, query }),
        query,
      });
    },
    onSuccess: () => {
      delete requests.current.predict;
      client.invalidateQueries({ queryKey: ["transformer"] });
    },
  });
  const latestJob = status.data?.jobs?.find(
    (j: any) => j.operation === "predict" && j.status === "done",
  );
  const latest = latestJob?.result?.summary;
  const [feedbackRun, setFeedbackRun] = useState(""),
    [firstChannel, setFirstChannel] = useState(1000000000),
    [intensity, setIntensity] = useState(0.1);
  const runs = useQuery<any[]>({
    queryKey: ["transformer-targets", project?.id],
    queryFn: () => api(`${projectPath(project!.id)}/runs`),
    enabled: !!latest,
    refetchInterval: 5000,
  });
  const feedback = useMutation({
    mutationFn: () => {
      const body = {
        run_id: feedbackRun,
        channel_ids: latest.probabilities.map(
          (_: number, i: number) => firstChannel + i,
        ),
        intensity,
      };
      return post(base + `/predictions/${latestJob.id}/inputs`, {
        ...body,
        request_id: requestId("feedback", { job: latestJob.id, ...body }),
      });
    },
    onSuccess: () => {
      delete requests.current.feedback;
      setNotice(t("外部概率刺激已接收，来源、模型和通道映射已记录。"));
    },
  });
  return (
    <>
      <p className="notice">
        {t(
          "本地小模型，只输出下一事件概率；可选 GPU，不可用时回退 CPU。数字是对照类别编号，不是意识节点 ID。不会自动回灌或调用云端。",
        )}
      </p>
      <ErrorBox
        error={status.error ?? train.error ?? predict.error ?? feedback.error}
      />
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      <section className="panel kernel-help">
        <h2>{t("计算设备")}</h2>
        <div className="form-grid">
          <Field label={t("本次训练与查询使用")}>
            <select
              aria-label={t("本次训练与查询使用")}
              value={computeDevice}
              onChange={(e) => setComputeDevice(e.target.value)}
            >
              <option value="auto">{t("自动（测量收益后选择）")}</option>
              <option value="cpu">CPU</option>
              <option value="cuda">{t("GPU 优先（失败回退 CPU）")}</option>
            </select>
          </Field>
          <Field label={t("显存预算（MiB）")}>
            <input
              type="number"
              min={128}
              max={131072}
              value={gpuMemory}
              onChange={(e) => setGpuMemory(Number(e.target.value))}
            />
          </Field>
          <Field label={t("显存预留（MiB）")}>
            <input
              type="number"
              min={128}
              max={32768}
              value={gpuHeadroom}
              onChange={(e) => setGpuHeadroom(Number(e.target.value))}
            />
          </Field>
        </div>
        <p>
          {t(
            "意识内核仍使用 CPU。自动模式须测得稳定加速；真实执行设备和回退原因保存在任务证据中。",
          )}
        </p>
      </section>
      <div className="transformer-layout">
        <section className="panel kernel-help">
          <h2>{t("训练对照模型")}</h2>
          <Field label={t("训练序列（每行一条）")}>
            <textarea
              rows={6}
              value={corpus}
              onChange={(e) => setCorpus(e.target.value)}
            />
          </Field>
          <details>
            <summary>{t("独立检验与模型参数")}</summary>
            <Field label={t("保留检验序列（可选）")}>
              <textarea
                rows={3}
                value={evaluation}
                onChange={(e) => setEvaluation(e.target.value)}
              />
            </Field>
            <div className="form-grid">
              <Field label={t("类别数量")}>
                <input
                  type="number"
                  min={2}
                  max={4096}
                  value={vocabulary}
                  onChange={(e) => setVocabulary(Number(e.target.value))}
                />
              </Field>
              <Field label={t("特征宽度")}>
                <select
                  value={width}
                  onChange={(e) => setWidth(Number(e.target.value))}
                >
                  {[16, 32, 64, 128].map((n) => (
                    <option key={n}>{n}</option>
                  ))}
                </select>
              </Field>
              <Field label={t("注意力层数")}>
                <select
                  value={layers}
                  onChange={(e) => setLayers(Number(e.target.value))}
                >
                  {[1, 2, 3].map((n) => (
                    <option key={n}>{n}</option>
                  ))}
                </select>
              </Field>
            </div>
          </details>
          <div className="form-grid">
            <Field label={t("训练步数上限")}>
              <input
                type="number"
                min={1}
                max={5000}
                value={steps}
                onChange={(e) => setSteps(Number(e.target.value))}
              />
            </Field>
            <Field label={t("实际用时上限（秒）")}>
              <input
                type="number"
                min={1}
                max={300}
                value={seconds}
                onChange={(e) => setSeconds(Number(e.target.value))}
              />
            </Field>
          </div>
          <p>
            {t(
              "默认 2 个 CPU 线程、2 GiB 进程内存预算。达到预算会明确记录中止；已有结果保留。",
            )}
          </p>
          <Button
            variant="primary"
            disabled={train.isPending || !corpus.trim()}
            onClick={() => train.mutate()}
          >
            {t("开始本地训练")}
          </Button>
        </section>
        <section className="panel kernel-help">
          <h2>{t("查询概率")}</h2>
          <Field label={t("对照模型")}>
            <select
              value={selected || status.data?.models?.[0]?.id || ""}
              onChange={(e) => setSelected(e.target.value)}
            >
              {!status.data?.models?.length && (
                <option value="">{t("先完成一次训练")}</option>
              )}
              {status.data?.models?.map((m: any) => (
                <option key={m.id} value={m.id}>
                  {m.name} · {m.sha256.slice(0, 8)}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("查询序列")}>
            <input value={tokens} onChange={(e) => setTokens(e.target.value)} />
          </Field>
          <Button
            disabled={predict.isPending || !status.data?.models?.length}
            onClick={() => predict.mutate()}
          >
            {t("计算下一事件概率")}
          </Button>
          {latest && (
            <div className="probability-result">
              <p className="mono">{latest.model_sha256.slice(0, 16)}</p>
              <p>
                {t("输入")}: {latest.tokens.join(" → ")}
              </p>
              <ol>
                {latest.probabilities
                  .map((p: number, i: number) => ({ p, i }))
                  .sort((a: any, b: any) => b.p - a.p)
                  .slice(0, 16)
                  .map(({ p, i }: any) => (
                    <li key={i}>
                      <span>#{i}</span>
                      <meter min={0} max={1} value={p} />
                      <strong>{(p * 100).toFixed(2)}%</strong>
                    </li>
                  ))}
              </ol>
              <Button onClick={() => download(latest, "probabilities.json")}>
                <Download size={15} />
                {t("导出完整概率")}
              </Button>
              <details className="probability-feedback">
                <summary>{t("可选：作为外部刺激接入")}</summary>
                <p>
                  {t(
                    "这会真实改变所选意识。类别按声明的连续通道逐项映射，不能当作内核自行学到的能力；原文本映射不变。",
                  )}
                </p>
                <Field label={t("接收意识")}>
                  <select
                    value={feedbackRun}
                    onChange={(e) => setFeedbackRun(e.target.value)}
                  >
                    <option value="">{t("请选择")}</option>
                    {runs.data
                      ?.filter(
                        (r) =>
                          ["queued", "running", "paused", "blocked"].includes(
                            r.status,
                          ) && r.life !== "dead",
                      )
                      .map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name}
                        </option>
                      ))}
                  </select>
                </Field>
                <div className="form-grid">
                  <Field label={t("起始通道编号")}>
                    <input
                      type="number"
                      min={0}
                      max={4294967295 - latest.probabilities.length + 1}
                      value={firstChannel}
                      onChange={(e) => setFirstChannel(Number(e.target.value))}
                    />
                  </Field>
                  <Field label={t("外部刺激强度")}>
                    <input
                      type="number"
                      min={0}
                      max={1}
                      step={0.05}
                      value={intensity}
                      onChange={(e) => setIntensity(Number(e.target.value))}
                    />
                  </Field>
                </div>
                <Button
                  disabled={!feedbackRun || feedback.isPending}
                  onClick={() => feedback.mutate()}
                >
                  {t("发送一次外部概率刺激")}
                </Button>
              </details>
            </div>
          )}
        </section>
      </div>
      <section className="panel kernel-help">
        <h2>{t("任务与证据")}</h2>
        {!status.data?.jobs?.length && (
          <p>{t("尚无任务。所有结果均与意识模型分开保存。")}</p>
        )}
        <div className="transformer-jobs">
          {status.data?.jobs?.map((j: any) => (
            <article key={j.id}>
              <div>
                <strong>
                  {j.operation === "train" ? t("本地训练") : t("概率查询")}
                </strong>
                <span>{j.status}</span>
              </div>
              {j.error && <p role="alert">{j.error}</p>}
              {j.result?.summary?.compute && (
                <p>
                  {t("执行设备")}:{" "}
                  {j.result.summary.compute.resolved.toUpperCase()} ·{" "}
                  {j.result.summary.compute.reason}
                  {j.result.summary.fallback_from_initial_conditions && (
                    <> · {t("已从初始条件在 CPU 重试")}</>
                  )}
                </p>
              )}
              {j.result?.summary?.steps_completed != null && (
                <p>
                  {t("完成步数")}: {j.result.summary.steps_completed} ·{" "}
                  {j.result.summary.status} ·{" "}
                  {Number(j.result.summary.wall_seconds).toFixed(2)} s
                </p>
              )}
              {j.result?.result_artifact_id && (
                <a
                  href={`/api/v2${projectPath(project!.id)}/artifacts/${j.result.result_artifact_id}`}
                  download
                >
                  {t("下载结果 JSON")}
                </a>
              )}
              {j.result?.summary?.model_artifact_id && (
                <>
                  {" "}
                  ·{" "}
                  <a
                    href={`/api/v2${projectPath(project!.id)}/artifacts/${j.result.summary.model_artifact_id}`}
                    download
                  >
                    {t("下载数值模型")}
                  </a>
                </>
              )}
            </article>
          ))}
        </div>
      </section>
    </>
  );
}

export function PhysicalMembranes({
  base,
  revision,
}: {
  base: string;
  revision: number;
}) {
  const [after, setAfter] = useState(0),
    [history, setHistory] = useState<number[]>([]),
    [before, setBefore] = useState<number | null>(null);
  const state = useQuery<any>({
    queryKey: ["membranes", base, revision, after],
    queryFn: () => api(`${base}/physical-state?after_id=${after}&limit=100`),
    enabled: revision > 0,
  });
  const spikes = useQuery<any>({
    queryKey: ["spikes", base, revision, before],
    queryFn: () =>
      api(`${base}/spikes?limit=100${before ? `&before_id=${before}` : ""}`),
    enabled: revision > 0,
  });
  if (!revision) return <p>{t("首个检查点保存后可查看物理状态。")}</p>;
  return (
    <section className="panel kernel-help">
      <h2>{t("膜电位与电流")}</h2>
      <p>
        {t(
          "图形和聊天排序使用归一化去极化，不是放电率。下表是当前检查点的原始物理状态。",
        )}
      </p>
      <ErrorBox error={state.error ?? spikes.error} />
      {state.data && (
        <>
          <p className="mono">
            r{state.data.revision} · {state.data.state_time_us} μs
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {[
                    "节点",
                    "通道",
                    "膜电位 (mV)",
                    "电流 (nA)",
                    "适应电流 (nA)",
                    "累计发放",
                  ].map((s) => (
                    <th key={s}>{t(s)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {state.data.nodes.map((n: any) => (
                  <tr key={n.id}>
                    <td>{n.id}</td>
                    <td>{n.channel}</td>
                    <td>{n.voltage_mv.toFixed(6)}</td>
                    <td>{n.current_na.toPrecision(6)}</td>
                    <td>{n.adaptation_na.toPrecision(6)}</td>
                    <td>{n.spikes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="kernel-actions">
            <Button
              disabled={!history.length}
              onClick={() => {
                setAfter(history.at(-1)!);
                setHistory(history.slice(0, -1));
              }}
            >
              {t("上一页")}
            </Button>
            <Button
              disabled={state.data.next_after_id == null}
              onClick={() => {
                setHistory([...history, after]);
                setAfter(state.data.next_after_id);
              }}
            >
              {t("下一页")}
            </Button>
            <Button
              onClick={() =>
                download(
                  state.data,
                  `membranes-r${state.data.revision}-after${after}.json`,
                )
              }
            >
              {t("导出本页原始数据")}
            </Button>
          </div>
        </>
      )}
      <h3>{t("发放事件")}</h3>
      <p>
        {t(
          "按真实模拟时间记录的脉冲，与图形采样分开。设置中可关闭记录，关闭不改变发放本身。",
        )}
      </p>
      {spikes.data && (
        <>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t("模拟时间（μs）")}</th>
                  <th>{t("发放节点")}</th>
                </tr>
              </thead>
              <tbody>
                {spikes.data.items.map((e: any) => (
                  <tr key={e.id}>
                    <td>{e.time_us}</td>
                    <td className="spike-node-list">
                      {e.payload.nodes.join(", ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!spikes.data.items.length && (
            <p>{t("本页没有已记录的脉冲。无脉冲不等于无膜电位活动。")}</p>
          )}
          <div className="kernel-actions">
            <Button disabled={!before} onClick={() => setBefore(null)}>
              {t("最新记录")}
            </Button>
            <Button
              disabled={!spikes.data.next_before_id}
              onClick={() => setBefore(spikes.data.next_before_id)}
            >
              {t("更早记录")}
            </Button>
            <Button onClick={() => download(spikes.data, "spikes.json")}>
              {t("导出本页原始数据")}
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
