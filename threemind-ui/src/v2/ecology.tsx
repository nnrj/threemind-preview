import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import { api, post, projectPath, timeLabel, numberLabel } from "./api";
import { t, messageKeys } from "./i18n";
import {
  Badge,
  Button,
  CodeEditor,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Modal,
  PageTitle,
  useWorkspace,
} from "./ui";
import { useCatalogue } from "./configuration";
import { EcologyEditor, type EcologyEditorHandle } from "./EcologyEditor";
import EcologyLedger from "./EcologyLedger";
import EcologyObserver from "./EcologyObserver";
import "./ecology.css";
const EcologyScene = lazy(() => import("./EcologyScene"));
const Chart = lazy(() => import("./Chart"));
const eventNames = messageKeys({
  founder_born: "初始个体出生",
  individual_born: "后代出生",
  body_failed: "躯体失效",
  resource_transfer: "资源摄取",
  birth_deferred: "繁殖暂缓",
});
const summaryNames = messageKeys({
  individuals: "累计个体",
  living_bodies: "存活躯体",
  viable_cores: "尚未死亡的内核",
  births: "后代出生数",
  body_failures: "失效躯体数",
  maximum_generation: "最高后代代数",
  deferred_population: "因种群容量暂缓",
  deferred_budget: "因后代预算暂缓",
});

function Paging({ offset, more, change }: any) {
  return (
    <div className="development-pagination">
      <Button
        disabled={!offset}
        onClick={() => change(Math.max(0, offset - 30))}
      >
        {t("上一页")}
      </Button>
      <span>{t("第 {page} 页", { page: offset / 30 + 1 })}</span>
      <Button disabled={!more} onClick={() => change(offset + 30)}>
        {t("下一页")}
      </Button>
    </div>
  );
}

function NewEcology({ project, catalogue, configuration, close, done }: any) {
  const editor = useRef<EcologyEditorHandle>(null);
  const [name, setName] = useState(t("新的生态训练")),
    [objective, setObjective] = useState(
      t("观察环境、身体感知与网络继承对种群形成过程的影响。"),
    );
  const [initial, setInitial] = useState(catalogue.defaults),
    [editorKey, setEditorKey] = useState(0);
  const [sourceQuery, setSourceQuery] = useState(""),
    [sourcePage, setSourcePage] = useState(0),
    [sourceTitle, setSourceTitle] = useState("");
  const [nonce, setNonce] = useState(() => crypto.randomUUID()),
    [sourceError, setSourceError] = useState<unknown>(null);
  const [sourceBusy, setSourceBusy] = useState(false);
  const sources = useQuery({
    queryKey: ["ecology-sources", project, sourceQuery, sourcePage],
    queryFn: () =>
      api<any>(
        projectPath(project) +
          "/innate-versions?q=" +
          encodeURIComponent(sourceQuery) +
          "&offset=" +
          sourcePage,
      ),
  });
  const mutation = useMutation({
    mutationFn: async () => {
      const protocol = await editor.current?.validate();
      if (!protocol) return null;
      return post<any>(projectPath(project) + "/ecologies", {
        name,
        objective,
        operation_id: nonce,
        protocol,
      });
    },
    onSuccess: (result) => {
      if (result) done(result.id);
    },
  });
  function dirty() {
    setNonce(crypto.randomUUID());
    mutation.reset();
  }
  async function choose(id: string) {
    setSourceBusy(true);
    setSourceError(null);
    try {
      const current = await editor.current?.validate();
      if (!current) return;
      const source = id
        ? await api<any>(projectPath(project) + "/innate-versions/" + id)
        : null;
      const next = { ...current, initial_version_id: source?.id ?? null };
      if (source)
        next.base = {
          ...source.protocol,
          environment: "world",
          world_protocol:
            source.protocol.world_protocol ?? current.base.world_protocol,
          duration_s: current.base.duration_s,
          phases: [],
          intervention: null,
        };
      setSourceTitle(source?.name ?? "");
      setInitial(next);
      setEditorKey((k) => k + 1);
      dirty();
    } catch (e) {
      setSourceError(e);
    } finally {
      setSourceBusy(false);
    }
  }
  const busy = mutation.isPending || sourceBusy;
  return (
    <Modal
      open
      wide
      title={t("新建生态训练")}
      onOpenChange={(open) => {
        if (!open && !busy) close();
      }}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate();
        }}
      >
        <Field label={t("训练名称")}>
          <input
            required
            maxLength={120}
            value={name}
            disabled={busy}
            onChange={(e) => {
              setName(e.target.value);
              dirty();
            }}
          />
        </Field>
        <Field label={t("研究目标与环境说明")}>
          <textarea
            required
            maxLength={8000}
            value={objective}
            disabled={busy}
            onChange={(e) => {
              setObjective(e.target.value);
              dirty();
            }}
          />
        </Field>
        <details className="ecology-group">
          <summary>
            {t("初始先天模型")} · {sourceTitle || t("从空白网络出生")}
          </summary>
          <Field label={t("搜索先天版本")}>
            <input
              value={sourceQuery}
              onChange={(e) => {
                setSourceQuery(e.target.value);
                setSourcePage(0);
              }}
            />
          </Field>
          <select
            aria-label={t("初始先天模型")}
            value={initial.initial_version_id ?? ""}
            disabled={busy}
            onChange={(e) => choose(e.target.value)}
          >
            <option value="">{t("从空白网络出生")}</option>
            {initial.initial_version_id &&
              !sources.data?.rows.some(
                (r: any) => r.id === initial.initial_version_id,
              ) && (
                <option value={initial.initial_version_id}>
                  {sourceTitle}
                </option>
              )}
            {sources.data?.rows.map((r: any) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
          <Paging
            offset={sourcePage}
            more={sources.data?.more}
            change={setSourcePage}
          />
        </details>
        <EcologyEditor
          key={editorKey}
          ref={editor}
          project={project}
          initial={initial}
          catalogue={catalogue}
          configuration={configuration}
          onDirty={dirty}
        />
        <ErrorBox error={mutation.error || sourceError || sources.error} />
        <div className="modal-actions">
          <Button type="button" disabled={busy} onClick={close}>
            {t("取消")}
          </Button>
          <Button type="submit" variant="primary" disabled={busy}>
            {t("创建并开始训练")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function EcologyDetail({ project, id, catalogue, configuration, write }: any) {
  const client = useQueryClient(),
    root = projectPath(project) + "/ecologies/" + id;
  const [checkpoint, setCheckpoint] = useState(""),
    [offset, setOffset] = useState(0),
    [life, setLife] = useState("all"),
    [protocolOpen, setProtocolOpen] = useState(false);
  const [after, setAfter] = useState(0),
    [eventKind, setEventKind] = useState(""),
    [individual, setIndividual] = useState("");
  const [before, setBefore] = useState<number | null>(null),
    [trajectoryAfter, setTrajectoryAfter] = useState(0);
  const protocol = useQuery({
    queryKey: ["ecology-protocol", project, id],
    queryFn: () => api<any>(root + "/protocol"),
    staleTime: Infinity,
  });
  const detail = useQuery({
    queryKey: ["ecology-detail", project, id, checkpoint, offset, life],
    queryFn: () =>
      api<any>(
        root +
          "?offset=" +
          offset +
          "&life=" +
          life +
          (checkpoint ? "&checkpoint_id=" + checkpoint : ""),
      ),
    refetchInterval: checkpoint ? false : 3000,
  });
  const selected = detail.data?.checkpoint?.id;
  const [includeModels, setIncludeModels] = useState(false);
  const exports = useQuery({
    queryKey: ["ecology-exports", project, id],
    queryFn: () => api<any[]>(root + "/exports"),
    refetchInterval: 3000,
  });
  const exporter = useMutation({
    mutationFn: () =>
      post(root + "/exports", {
        operation_id: crypto.randomUUID(),
        checkpoint_id: selected,
        include_models: includeModels,
      }),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ["ecology-exports", project, id] }),
  });
  const snapshots = useQuery({
    queryKey: ["ecology-checkpoints", project, id, before, selected],
    queryFn: () =>
      api<any>(root + "/checkpoints" + (before ? "?before=" + before : "")),
  });
  const events = useQuery({
    queryKey: [
      "ecology-events",
      project,
      id,
      selected,
      after,
      eventKind,
      individual,
    ],
    queryFn: () =>
      api<any>(
        root +
          "/events?checkpoint_id=" +
          selected +
          "&after=" +
          after +
          (eventKind ? "&kind=" + eventKind : "") +
          (individual ? "&individual=" + individual : ""),
      ),
    enabled: !!selected,
  });
  const trajectory = useQuery({
    queryKey: ["ecology-trajectory", project, id, selected, trajectoryAfter],
    queryFn: () =>
      api<any>(
        root +
          "/trajectory?checkpoint_id=" +
          selected +
          "&after=" +
          trajectoryAfter,
      ),
    enabled: !!selected,
  });
  const action = useMutation({
    mutationFn: (action: string) =>
      post(root + "/controls", {
        action,
        expected_revision: detail.data?.campaign.control_revision,
      }),
    onSuccess: () =>
      client.invalidateQueries({
        predicate: (q) =>
          q.queryKey[0]?.toString().startsWith("ecolog") ?? false,
      }),
  });
  if (!detail.data)
    return (
      <>
        <ErrorBox error={detail.error} />
        <Loading />
      </>
    );
  const row = detail.data.campaign,
    cp = detail.data.checkpoint,
    stats = cp?.observation.population ?? row.summary;
  const controls =
    row.status === "active"
      ? ["pause", "cancel"]
      : row.status === "paused"
        ? ["resume", "cancel"]
        : row.status === "blocked"
          ? ["retry", "cancel"]
          : [];
  const controlLabels: Record<string, string> = {
    pause: "暂停",
    cancel: "取消训练",
    resume: "继续",
    retry: "重试",
  };
  return (
    <section className="panel ecology-detail">
      <PageTitle
        eyebrow="POPULATION & EVIDENCE"
        title={row.name}
        description={row.objective}
      />
      <div className="query-controls">
        <Badge status={row.status === "active" ? "running" : row.status} />
        {controls.map((kind) => (
          <Button
            key={kind}
            disabled={!write || action.isPending || !!row.requested_action}
            onClick={() => action.mutate(kind)}
          >
            {t(controlLabels[kind])}
          </Button>
        ))}
        <Button disabled={!protocol.data} onClick={() => setProtocolOpen(true)}>
          {t("查看冻结协议")}
        </Button>
      </div>
      {row.requested_action && (
        <p role="status">{t("正在等待整个种群提交恢复点。")}</p>
      )}
      <ErrorBox error={action.error || detail.error || row.error} />
      <details className="ecology-group">
        <summary>{t("导出种群证据")}</summary>
        <label className="check">
          <input
            type="checkbox"
            checked={includeModels}
            onChange={(e) => setIncludeModels(e.target.checked)}
          />
          {t("包含所有个体的模型本体")}
        </label>
        <p className="footnote">
          {t(
            "证据包包含冻结协议、完整生态事件、个体表、资源状态、CSV 和 SVG／PNG 图表。模型可选，个体完整输入与读出可从各自档案导出。",
          )}
        </p>
        <Button
          disabled={!write || !selected || exporter.isPending}
          onClick={() => exporter.mutate()}
        >
          {t("导出当前种群恢复点")}
        </Button>
        <ErrorBox error={exporter.error || exports.error} />
        {exports.data?.map((job) => (
          <div className="query-controls" key={job.id}>
            <Badge status={job.status} />
            {job.result?.artifact_id && (
              <a
                href={
                  "/api/v2/projects/" +
                  project +
                  "/artifacts/" +
                  job.result.artifact_id
                }
              >
                {t("下载证据包")}
              </a>
            )}
            <ErrorBox error={job.error} />
          </div>
        ))}
      </details>
      <div className="ecology-summary">
        {Object.entries(summaryNames).map(([key, label]) => (
          <div key={key}>
            <span>{t(label)}</span>
            <strong>{numberLabel(stats[key] ?? 0)}</strong>
          </div>
        ))}
      </div>
      <Field
        label={t("种群恢复点")}
        hint={t(
          "个体、资源账本与物理世界来自同一次提交；历史选择不会追随最新状态。",
        )}
      >
        <select
          aria-label={t("种群恢复点")}
          value={checkpoint}
          onChange={(e) => {
            setCheckpoint(e.target.value);
            setOffset(0);
            setAfter(0);
            setTrajectoryAfter(0);
          }}
        >
          <option value="">{t("跟随最新提交")}</option>
          {checkpoint &&
            !snapshots.data?.rows.some((r: any) => r.id === checkpoint) && (
              <option value={checkpoint}>r{cp?.revision}</option>
            )}
          {snapshots.data?.rows.map((r: any) => (
            <option key={r.id} value={r.id}>
              r{r.revision} · {timeLabel(r.time_us)}
            </option>
          ))}
        </select>
      </Field>
      <div className="query-controls">
        <Button disabled={!before} onClick={() => setBefore(null)}>
          {t("最新恢复点")}
        </Button>
        <Button
          disabled={!snapshots.data?.more}
          onClick={() => setBefore(snapshots.data.rows.at(-1).revision)}
        >
          {t("更早恢复点")}
        </Button>
      </div>
      <EcologyObserver
        key={root}
        root={root}
        checkpoint={cp?.id}
        write={write}
      />
      {cp && (
        <>
          {write && (
            <Link
              className="button"
              to={`/reports?ecology=${id}&checkpoint=${cp.id}`}
            >
              {t("用此恢复点创建记录")}
            </Link>
          )}
          <p>
            {t("意识全局时间：{model}；物理结算时间：{physical}。", {
              model: timeLabel(cp.time_us),
              physical: timeLabel(cp.ledger.time_us),
            })}
          </p>
          {cp.pending_end_us !== null && (
            <p className="notice">
              {t(
                "当前处于一个尚未完全递送的物理采样区间；身体数据领先意识时间，待递送刺激已保存在恢复点中。",
              )}
            </p>
          )}
          {protocol.data && (
            <Suspense fallback={<Loading />}>
              <EcologyScene
                protocol={protocol.data.protocol}
                observation={cp.observation}
                onSelect={(key: string) => {
                  setIndividual(key);
                  setAfter(0);
                }}
              />
            </Suspense>
          )}
          <EcologyLedger root={root} checkpoint={cp} />
          <p className="footnote">
            {t(
              "身体生存、Core 生命状态和繁殖是不同观测。共享环境中的个体相互影响，不能把个体数当作独立重复实验数。",
            )}
          </p>
          <Suspense fallback={<Loading />}>
            <Chart
              rows={[]}
              metric="living_bodies"
              title={t("存活躯体（提交时采样）")}
              step
              series={[
                {
                  name: t("存活躯体"),
                  rows: (trajectory.data?.rows ?? []).map((r: any) => ({
                    ...r.metrics,
                    time_us: r.time_us,
                  })),
                },
              ]}
            />
          </Suspense>
          <div className="query-controls">
            <Button
              disabled={!trajectoryAfter}
              onClick={() => setTrajectoryAfter(0)}
            >
              {t("首段轨迹")}
            </Button>
            <Button
              disabled={!trajectory.data?.more}
              onClick={() => setTrajectoryAfter(trajectory.data.next)}
            >
              {t("后续轨迹")}
            </Button>
            <span>{t("每段最多显示 1000 个提交点；完整数据可导出。")}</span>
          </div>
          <Field label={t("个体状态筛选")}>
            <select
              value={life}
              onChange={(e) => {
                setLife(e.target.value);
                setOffset(0);
              }}
            >
              <option value="all">{t("全部个体")}</option>
              <option value="body_alive">{t("存活躯体")}</option>
              <option value="body_failed">{t("躯体失效")}</option>
              <option value="core_dead">{t("Core 已死亡")}</option>
            </select>
          </Field>
          <div className="table-scroll ecology-members">
            <table>
              <thead>
                <tr>
                  {[
                    "个体",
                    "父本",
                    "代数",
                    "出生时间",
                    "身体储备",
                    "累计损伤",
                    "Core 状态",
                    "档案",
                  ].map((label) => (
                    <th key={label}>{t(label)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {detail.data.members.map((m: any) => (
                  <tr key={m.individual}>
                    <td data-label={t("个体")}>{m.individual}</td>
                    <td data-label={t("父本")}>{m.parent ?? "—"}</td>
                    <td data-label={t("代数")}>{m.generation}</td>
                    <td data-label={t("出生时间")}>{timeLabel(m.birth_us)}</td>
                    <td data-label={t("身体储备")}>
                      {numberLabel(m.outcome.reserve)}
                    </td>
                    <td data-label={t("累计损伤")}>
                      {numberLabel(m.outcome.damage)}
                    </td>
                    <td data-label={t("Core 状态")}>
                      <span className={"badge " + m.outcome.core_life}>
                        {t(
                          (
                            {
                              active: "已激活",
                              waiting: "等待刺激",
                              dead: "已死亡",
                            } as Record<string, string>
                          )[m.outcome.core_life] ?? m.outcome.core_life,
                        )}
                      </span>
                    </td>
                    <td data-label={t("档案")}>
                      <Link to={"/runs/" + m.run_id}>
                        {t("查看意识与完整数据")}
                      </Link>
                      <details>
                        <summary>{t("来源与状态")}</summary>
                        <CodeEditor
                          readOnly
                          value={JSON.stringify(m, null, 2)}
                          onChange={() => {}}
                          rows={8}
                        />
                      </details>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Paging offset={offset} more={detail.data.more} change={setOffset} />
          <h3>{t("生态事件记录")}</h3>
          <div className="query-controls">
            <Field label={t("事件类型")}>
              <select
                value={eventKind}
                onChange={(e) => {
                  setEventKind(e.target.value);
                  setAfter(0);
                }}
              >
                <option value="">{t("全部")}</option>
                {Object.entries(eventNames).map(([k, v]) => (
                  <option key={k} value={k}>
                    {t(v)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("个体编号")}>
              <input
                value={individual}
                pattern="n[0-9]+"
                placeholder="n0"
                onChange={(e) => {
                  if (!e.target.value || /^n[0-9]*$/.test(e.target.value)) {
                    setIndividual(e.target.value);
                    setAfter(0);
                  }
                }}
              />
            </Field>
            <Button
              onClick={() => {
                setIndividual("");
                setEventKind("");
                setAfter(0);
              }}
            >
              {t("清除筛选")}
            </Button>
          </div>
          {(events.data?.rows ?? []).map((e: any) => (
            <details className="ecology-event" key={e.id}>
              <summary>
                {timeLabel(e.time_us)} ·{" "}
                {e.individual ?? e.payload?.parent ?? "—"} ·{" "}
                {t(eventNames[e.kind as keyof typeof eventNames] ?? e.kind)}
              </summary>
              <CodeEditor
                readOnly
                value={JSON.stringify(e.payload, null, 2)}
                onChange={() => {}}
              />
            </details>
          ))}
          <div className="query-controls">
            <Button disabled={!after} onClick={() => setAfter(0)}>
              {t("首批事件")}
            </Button>
            <Button
              disabled={!events.data?.more}
              onClick={() => setAfter(events.data.next)}
            >
              {t("后续事件")}
            </Button>
          </div>
        </>
      )}
      <ErrorBox
        error={
          events.error || protocol.error || trajectory.error || snapshots.error
        }
      />
      <Modal
        open={protocolOpen}
        onOpenChange={setProtocolOpen}
        wide
        title={t("冻结的生态训练协议")}
      >
        {protocolOpen && protocol.data && (
          <EcologyEditor
            project={project}
            initial={protocol.data.protocol}
            catalogue={catalogue}
            configuration={configuration}
            readOnly
          />
        )}
      </Modal>
    </section>
  );
}

export default function Ecology() {
  const { project } = useWorkspace(),
    client = useQueryClient(),
    configuration = useCatalogue(),
    root = projectPath(project!.id) + "/ecologies";
  const [query, setQuery] = useState(""),
    [offset, setOffset] = useState(0),
    [creating, setCreating] = useState(false);
  const [params, setParams] = useSearchParams();
  const selected = params.get("campaign") ?? "";
  const setSelected = (id: string) =>
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      if (id) next.set("campaign", id);
      else next.delete("campaign");
      return next;
    });
  const lastProject = useRef(project!.id);
  useEffect(() => {
    if (lastProject.current !== project!.id) setSelected("");
    lastProject.current = project!.id;
    setOffset(0);
    setQuery("");
    setCreating(false);
  }, [project!.id]);
  const catalogue = useQuery({
    queryKey: ["ecology-catalogue", project!.id],
    queryFn: () => api<any>(root + "/catalogue"),
    staleTime: Infinity,
  });
  const list = useQuery({
    queryKey: ["ecologies", project!.id, query, offset],
    queryFn: () =>
      api<any>(root + "?q=" + encodeURIComponent(query) + "&offset=" + offset),
    refetchInterval: 5000,
  });
  const write = project!.role !== "viewer";
  if (selected && catalogue.data && configuration.data)
    return (
      <>
        <Button variant="quiet" onClick={() => setSelected("")}>
          {t("返回列表")}
        </Button>
        <EcologyDetail
          key={project!.id + selected}
          project={project!.id}
          id={selected}
          catalogue={catalogue.data}
          configuration={configuration.data}
          write={write}
        />
      </>
    );
  return (
    <>
      <PageTitle
        eyebrow="ECOLOGICAL EVOLUTION"
        title={t("生态演化")}
        description={t(
          "让身体与环境相互作用，通过声明的资源、生存和繁殖规则产生后代。",
        )}
      />
      <div className="evolution-search-controls">
        <Field label={t("搜索生态训练")}>
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOffset(0);
            }}
          />
        </Field>
        <Button
          disabled={!write || !catalogue.data || !configuration.data}
          onClick={() => setCreating(true)}
        >
          {t("新建生态训练")}
        </Button>
      </div>
      <ErrorBox error={list.error || catalogue.error || configuration.error} />
      {list.isPending ? (
        <Loading />
      ) : list.data?.rows.length ? (
        <section className="panel">
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {["训练名称", "状态", "模拟时间", "累计个体", "操作"].map(
                    (label) => (
                      <th key={label}>{t(label)}</th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {list.data.rows.map((r: any) => (
                  <tr key={r.id}>
                    <td>{r.name}</td>
                    <td>
                      <Badge
                        status={r.status === "active" ? "running" : r.status}
                      />
                    </td>
                    <td>{timeLabel(r.time_us)}</td>
                    <td>{numberLabel(r.summary.individuals ?? 0)}</td>
                    <td>
                      <Button onClick={() => setSelected(r.id)}>
                        {t("查看")}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Paging offset={offset} more={list.data.more} change={setOffset} />
        </section>
      ) : (
        <Empty
          title={t("还没有生态训练")}
          detail={t(
            "先配置物理世界、身体感官与资源规则；生态选择不会自动证明意识质量或价值倾向。",
          )}
        />
      )}
      {creating && catalogue.data && configuration.data && (
        <NewEcology
          project={project!.id}
          catalogue={catalogue.data}
          configuration={configuration.data}
          close={() => setCreating(false)}
          done={(id: string) => {
            setCreating(false);
            setSelected(id);
            client.invalidateQueries({ queryKey: ["ecologies"] });
          }}
        />
      )}
    </>
  );
}
