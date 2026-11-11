import { can } from "./access";
import { t, locale } from "./i18n";
import { lazy, useEffect, useMemo, useState, useRef, Suspense } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  ArrowRight,
  Activity,
  Play,
  Pause,
  Square,
  Download,
  GitFork,
  Upload,
  Filter,
  ChevronRight,
  ChevronLeft,
  ExternalLink,
  RefreshCw,
  FlaskConical,
  FileArchive,
  Box,
  Settings2,
} from "lucide-react";
import {
  api,
  post,
  projectPath,
  timeLabel,
  numberLabel,
  type Run,
  type Metrics,
} from "./api";
import {
  useWorkspace,
  PageTitle,
  Button,
  Modal,
  Field,
  CodeEditor,
  ErrorBox,
  Empty,
  Loading,
  Metric,
  Badge,
  RunTable,
} from "./ui";
import { EditRunConfiguration, useCatalogue } from "./configuration";
import {
  KernelConfiguration,
  type KernelConfigurationHandle,
} from "./kernelConfiguration";
import "./workbench.css";
const SensoryPage = lazy(() => import("./inputs"));
const ReadoutPage = lazy(() => import("./readouts"));
const Conversation = lazy(() => import("./conversation"));
const Bundles = lazy(() => import("./bundles"));
const SpeciesLibrary = lazy(() => import("./species"));
const Graph = lazy(() => import("./Graph"));
const StateCaptures = lazy(() => import("./stateCaptures"));
const Chart = lazy(() => import("./Chart"));
const ResourcePanel = lazy(() => import("./resourceLimits"));
const EnergyPanel = lazy(() => import("./energy"));
const SpatialPanel = lazy(() => import("./spatial"));
const ModelLibrary = lazy(() => import("./modelLibrary"));
const ModelMetadataDialog = lazy(() =>
  import("./modelLibrary").then((m) => ({ default: m.ModelMetadataDialog })),
);
const VersionLibrary = lazy(() =>
  import("./modelLibrary").then((m) => ({ default: m.VersionLibrary })),
);
const ResearchConsole = lazy(() => import("./researchConsole"));
const AITools = lazy(() => import("./aiTools"));
const SchedulingPanel = lazy(() => import("./scheduling"));
const PhysicalMembranes = lazy(() =>
  import("./Kernels").then((m) => ({ default: m.PhysicalMembranes })),
);

export function useRuns(studyId?: string, enabled = true) {
  const { project } = useWorkspace();
  return useQuery({
    queryKey: ["runs", project?.id, studyId],
    queryFn: () =>
      api<Run[]>(
        `${projectPath(project!.id)}/runs?summary=true${studyId ? `&study_id=${encodeURIComponent(studyId)}&limit=1000` : ""}`,
      ),
    enabled: !!project && enabled,
    refetchInterval: 1500,
  });
}
export function NewRun({
  open,
  onOpenChange,
  worldProtocol,
  robotProtocol,
  onCreated,
  kernelId,
  startImmediately = false,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  worldProtocol?: any;
  robotProtocol?: any;
  onCreated?: (run: Run) => void;
  kernelId?: string;
  startImmediately?: boolean;
}) {
  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      wide
      title={t("创建意识")}
      description={t(
        "先配置新意识，再选择保存归属。默认创建后保持未启动，已有意识的配置不会改变。",
      )}
    >
      {open && (
        <NewRunForm
          onClose={() => onOpenChange(false)}
          worldProtocol={worldProtocol}
          robotProtocol={robotProtocol}
          onCreated={onCreated}
          kernelId={kernelId}
          startImmediately={startImmediately}
        />
      )}
    </Modal>
  );
}
function NewRunForm({
  onClose,
  worldProtocol,
  robotProtocol,
  onCreated,
  kernelId,
  startImmediately,
}: {
  onClose: () => void;
  worldProtocol?: any;
  robotProtocol?: any;
  onCreated?: (run: Run) => void;
  kernelId?: string;
  startImmediately: boolean;
}) {
  const workspace = useWorkspace(),
    catalogue = useCatalogue(),
    client = useQueryClient(),
    navigate = useNavigate();
  const [name, setName] = useState(() => t("新的意识"));
  const [destination, setDestination] = useState(() =>
    workspace.project?.role !== "viewer" ? workspace.project?.id || "" : "",
  );
  const [createdProjects, setCreatedProjects] = useState<any[]>([]);
  const choices = [
    ...workspace.projects,
    ...createdProjects.filter(
      (p) => !workspace.projects.some((q) => q.id === p.id),
    ),
  ].filter((p) => p.role !== "viewer");
  const [projectName, setProjectName] = useState("");
  const [inlineProject, setInlineProject] = useState(false);
  const [immediate, setImmediate] = useState(startImmediately);
  const editor = useRef<KernelConfigurationHandle>(null);
  const addProject = useMutation({
    mutationFn: () => post("/projects", { name: projectName.trim() }),
    onSuccess: (p) => {
      setCreatedProjects((old) => [...old, { ...p, role: p.role || "owner" }]);
      setDestination(p.id);
      setInlineProject(false);
      setProjectName("");
      client.invalidateQueries({ queryKey: ["projects"] });
    },
  });
  const create = useMutation({
    mutationFn: async () => {
      if (!destination) throw new Error(t("请选择归属项目，或新建一个项目。"));
      const draft = await editor.current?.validate();
      if (!draft) return null;
      return post<Run>(`${projectPath(destination)}/runs`, {
        name,
        spec: draft.spec,
        start_immediately: immediate,
        creation_source: draft.creationSource,
        ...(draft.execution ? { execution: draft.execution } : {}),
      });
    },
    onSuccess: (run) => {
      if (!run) return;
      client.invalidateQueries({ queryKey: ["runs"] });
      client.invalidateQueries({ queryKey: ["browse-resources"] });
      onClose();
      if (onCreated) onCreated(run);
      else
        navigate(
          `/runs/${run.id}?project=${encodeURIComponent(destination)}&view=network`,
        );
    },
  });
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      <Field label={t("意识名称")}>
        <input
          required
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </Field>
      <ErrorBox error={catalogue.error} />
      {catalogue.isPending ? (
        <Loading />
      ) : (
        catalogue.data && (
          <KernelConfiguration
            ref={editor}
            catalogue={catalogue.data}
            initialKernel={kernelId}
            project={destination || undefined}
            readOnly={create.isPending}
            worldProtocol={worldProtocol}
            robotProtocol={robotProtocol}
          />
        )
      )}
      <section className="new-run-destination">
        <Field label={t("所属项目")}>
          <select
            aria-label={t("所属项目")}
            value={destination}
            disabled={
              create.isPending ||
              ((!!worldProtocol || !!robotProtocol) && !!workspace.project)
            }
            onChange={(e) => setDestination(e.target.value)}
          >
            <option value="">{t("请选择归属项目")}</option>
            {choices.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </Field>
        <p className="footnote">
          {t("项目只决定保存位置和访问权限，不改变当前配置草稿。")}
        </p>
        {!worldProtocol && !robotProtocol && (
          <Button type="button" onClick={() => setInlineProject((v) => !v)}>
            {t("新建归属项目")}
          </Button>
        )}
        {inlineProject && (
          <div className="query-controls">
            <Field label={t("项目名称")}>
              <input
                value={projectName}
                maxLength={120}
                onChange={(e) => setProjectName(e.target.value)}
              />
            </Field>
            <Button
              type="button"
              disabled={
                !projectName.trim() ||
                addProject.isPending ||
                !can(workspace.user, "projects.create")
              }
              onClick={() => addProject.mutate()}
            >
              {t("创建项目并选用")}
            </Button>
          </div>
        )}
        <label className="settings-switch">
          <input
            type="checkbox"
            checked={immediate}
            disabled={!can(workspace.user, "runs.resume")}
            onChange={(e) => setImmediate(e.target.checked)}
          />
          {t("创建后立即启动")}
        </label>
      </section>
      <ErrorBox error={create.error ?? catalogue.error ?? addProject.error} />
      <div className="form-actions config-sticky-actions">
        <Button type="button" onClick={onClose}>
          {t("取消")}
        </Button>
        <Button
          variant="primary"
          disabled={
            create.isPending ||
            !catalogue.data ||
            !destination ||
            !name.trim() ||
            !can(workspace.user, "runs.create")
          }
        >
          {immediate ? <Play size={16} /> : <Plus size={16} />}
          {create.isPending
            ? t("正在创建…")
            : immediate
              ? t("创建并开始")
              : t("创建并准备")}
        </Button>
      </div>
    </form>
  );
}

export function Overview({ onNew }: { onNew: () => void }) {
  const runs = useRuns(),
    [filter, setFilter] = useState("all"),
    [search, setSearch] = useState("");
  const { project } = useWorkspace();
  const studies = useQuery({
    queryKey: ["studies", project?.id],
    queryFn: () => api<any[]>(`${projectPath(project!.id)}/studies`),
  });
  const data = runs.data ?? [];
  const shown = data.filter(
    (r) =>
      (filter === "all" || r.status === filter) &&
      r.name.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <PageTitle
        eyebrow="RESEARCH OVERVIEW"
        title={t("研究概览")}
        description={t("从持续运行的网络，到可比较、可复现的研究证据。")}
        actions={
          <Link className="text-link" to="/docs">
            {t("阅读研究指南 ")}
            <ArrowRight size={15} />
          </Link>
        }
      />
      <div className="metrics-grid">
        <Metric
          label={t("全部运行")}
          value={data.length}
          detail={t("项目中的独立意识实例")}
        />
        <Metric
          label={t("正在演化")}
          value={data.filter((r) => r.status === "running").length}
          detail={t("接受环境刺激与持续塑造")}
        />
        <Metric
          label={t("实验协议")}
          value={studies.data?.length ?? 0}
          detail={t("冻结的条件、种子与采集方案")}
        />
        <Metric
          label={t("已保存的运行")}
          value={data.filter((r) => r.revision > 0).length}
          detail={t("可查询、恢复或导出")}
        />
      </div>
      <div className="overview-band">
        <div className="band-icon">
          <FlaskConical size={24} />
        </div>
        <div>
          <h3>{t("把一个观察，变成一个可验证的问题。")}</h3>
          <p>
            {t("从相同状态分叉，用独立环境种子检验可塑性、保持与结构消融。")}
          </p>
        </div>
        <Link to="/studies" className="button">
          {t("设计实验 ")}
          <ArrowRight size={16} />
        </Link>
      </div>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>
              {t("运行记录 ")}
              <span className="count">{data.length}</span>
            </h2>
            <p>{t("观察状态、进入网络，或继续已有研究。")}</p>
          </div>
          <Button onClick={onNew}>
            <Plus size={16} />
            {t("新建意识")}
          </Button>
        </div>
        <div className="table-tools">
          <div className="tabs">
            {[
              ["all", "全部"],
              ["running", "运行中"],
              ["completed", "已完成"],
              ["paused", "已暂停"],
            ].map(([value, label]) => (
              <button
                key={value}
                className={filter === value ? "active" : ""}
                onClick={() => setFilter(value)}
              >
                {t(label)}
              </button>
            ))}
          </div>
          <input
            className="search-input"
            placeholder={t("搜索意识名称…")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <ErrorBox error={runs.error} />
        {runs.isPending ? (
          <Loading />
        ) : shown.length ? (
          <RunTable runs={shown} />
        ) : (
          <Empty
            title={data.length ? t("没有匹配的运行") : t("开始第一次环境接触")}
            detail={t("选择感官环境和时间模式，观察连接如何在刺激中形成。")}
            action={
              <Button variant="primary" onClick={onNew}>
                <Play size={15} />
                {t("创建意识")}
              </Button>
            }
          />
        )}
      </section>
      <div className="footnote">
        {t(
          "生命状态与执行状态分别记录。暂停、任务完成或资源故障不会被自动判定为意识死亡。",
        )}
      </div>
    </>
  );
}

export function RunPage() {
  const [newConsciousness, setNewConsciousness] = useState(false);
  const [showScheduling, setShowScheduling] = useState(false);
  const [playerPane, setPlayerPane] = useState("network");
  const { id } = useParams(),
    { project, user } = useWorkspace(),
    client = useQueryClient(),
    navigate = useNavigate();
  const base = `${projectPath(project!.id)}/runs/${id}`;
  const run = useQuery({
    queryKey: ["run", project?.id, id],
    queryFn: () => api<Run>(base),
    refetchInterval: (q) =>
      ["completed", "dead", "cancelled", "failed"].includes(
        q.state.data?.status ?? "",
      )
        ? false
        : 1000,
  });
  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState(
    [
      "network",
      "inputs",
      "readouts",
      "dynamics",
      "conversation",
      "events",
      "checkpoints",
      "protocol",
      "research",
      "ai",
    ].includes(searchParams.get("view") ?? "")
      ? searchParams.get("view")!
      : "network",
  );
  const [dynamicsTab, setDynamicsTab] = useState(
    searchParams.get("tool") === "energy" ? "energy" : "activity",
  );
  const requestedView = searchParams.get("view"),
    requestedTool = searchParams.get("tool");
  useEffect(() => {
    if (
      requestedView &&
      [
        "network",
        "inputs",
        "readouts",
        "dynamics",
        "conversation",
        "events",
        "checkpoints",
        "protocol",
        "research",
        "ai",
      ].includes(requestedView)
    )
      setTab(requestedView);
    if (requestedView === "dynamics" && requestedTool === "energy")
      setDynamicsTab("energy");
  }, [requestedView, requestedTool]);
  const configureOpen = searchParams.get("configure") === "1";
  const observations = useQuery({
    queryKey: ["observations", project?.id, id, run.data?.revision],
    queryFn: () => api(`${base}/observations?limit=10000`),
    enabled:
      tab === "dynamics" && dynamicsTab === "activity" && !!run.data?.revision,
    gcTime: 0,
    staleTime: Infinity,
  });
  const checkpoints = useQuery({
    queryKey: ["checkpoints", id, run.data?.revision],
    queryFn: () => api<any[]>(`${base}/checkpoints`),
    gcTime: 0,
    staleTime: Infinity,
  });
  const [node, setNode] = useState<string | number | null>(null),
    [format, setFormat] = useState("tmind"),
    [notice, setNotice] = useState("");
  const [forkOpen, setForkOpen] = useState(false),
    [forkName, setForkName] = useState(() => t("新的演化分支")),
    [inherit, setInherit] = useState(false),
    [forkCp, setForkCp] = useState("");
  const [eventKind, setEventKind] = useState("");
  const [templateName, setTemplateName] = useState<string | null>(null);
  const saveParameterTemplate = useMutation({
    mutationFn: () =>
      post(`${base}/configuration-template`, {
        name: templateName?.trim(),
        expected_metadata_revision: run.data?.metadata_revision,
      }),
    onSuccess: () => {
      setTemplateName(null);
      setNotice(t("当前参数已保存为模板，不包含个体状态或学习权重。"));
      client.invalidateQueries({ queryKey: ["configuration-templates"] });
      client.invalidateQueries({ queryKey: ["system-templates"] });
    },
  });
  const events = useQuery({
    queryKey: ["events", id, eventKind, run.data?.revision],
    queryFn: () =>
      api<any[]>(`${base}/events${eventKind ? `?kind=${eventKind}` : ""}`),
    enabled: tab === "events",
    gcTime: 0,
    staleTime: Infinity,
  });
  const inspected = useQuery({
    queryKey: ["node", id, node, run.data?.revision],
    queryFn: () =>
      api(
        `${base}/data/nodes?node_id=${encodeURIComponent(String(node))}&limit=1`,
      ),
    enabled: node != null,
    gcTime: 0,
  });
  const action = useMutation({
    mutationFn: ({ kind, payload = {} }: { kind: string; payload?: unknown }) =>
      post(`${base}/commands`, { kind, payload }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["run"] });
      setNotice(t("指令已提交，将在因果边界执行。"));
    },
  });
  const exportJob = useMutation({
    mutationFn: () => post(`${base}/exports`, { format }),
    onSuccess: () =>
      setNotice(t("导出任务已提交。完成后可在「模型与证据」下载。")),
  });
  const fork = useMutation({
    mutationFn: () =>
      post<Run>(`${base}/forks`, {
        name: forkName,
        inherit: run.data?.ecology ? true : inherit,
        checkpoint_id: forkCp || null,
      }),
    onSuccess: (r) => {
      setForkOpen(false);
      navigate(`/runs/${r.id}`);
      client.invalidateQueries({ queryKey: ["runs"] });
    },
  });
  const r = run.data;
  if (run.isPending) return <Loading />;
  if (!r) return <ErrorBox error={run.error} />;
  const active = ["queued", "running", "blocked"].includes(r.status);
  const isSpiking = r.spec.kernel_id === "threemind.lif/1";
  const environmentLabel = t(
    (
      {
        mujoco: "模拟物理环境",
        world: "可配置物理世界与躯体",
        host: "宿主物理遥测",
        replay: "记录输入重放",
        ambient: "合成环境场（显式实验载体）",
        manual: "手动刺激",
      } as Record<string, string>
    )[r.spec.environment] ?? r.spec.environment,
  );
  const clockLabel =
    r.spec.clock === "unbounded"
      ? t("尽速训练")
      : r.spec.clock === "scaled"
        ? t("{speed} 倍时间", { speed: r.spec.speed })
        : t("实时运行");
  return (
    <>
      <div className="consciousness-workbench-actions">
        <Link className="button" to="/">
          {t("意识工作台")}
        </Link>
        <Link className="button" to="/?open=1">
          {t("打开意识")}
        </Link>
        <Button
          disabled={!can(user, "runs.create")}
          onClick={() => setNewConsciousness(true)}
        >
          <Plus size={15} />
          {t("新建意识")}
        </Button>
        <span>{t("查看不改变运行状态；离开页面也不会暂停意识。")}</span>
      </div>
      <NewRun open={newConsciousness} onOpenChange={setNewConsciousness} />
      <PageTitle
        eyebrow="RUNTIME OBSERVATORY"
        title={r.name}
        description={`${r.spec.kernel_id ?? "threemind.causal/9"} · ${environmentLabel} · ${clockLabel} · seed ${r.spec.seed}`}
        actions={
          <>
            {r.revision === 0 && r.status === "paused" ? (
              <span className="badge paused">
                <i />
                {t("未启动")}
              </span>
            ) : (
              <Badge status={r.status} />
            )}
            <Button
              disabled={!can(user, "runs.configure")}
              onClick={() => setSearchParams({ view: tab, metadata: "1" })}
            >
              {t("编辑档案")}
            </Button>
            <Button onClick={() => setSearchParams({ configure: "1" })}>
              <Settings2 size={15} />
              {t("参数配置")}
            </Button>
            {can(user, "system.write") && (
              <Button onClick={() => setTemplateName(r.name)}>
                {t("从此实例参数创建模板")}
              </Button>
            )}
            {!r.ecology && !r.assessment && active ? (
              <Button
                onClick={() => action.mutate({ kind: "pause" })}
                disabled={action.isPending || !can(user, "runs.pause")}
              >
                <Pause size={15} />
                {t("暂停")}
              </Button>
            ) : !r.ecology && !r.assessment && r.status === "paused" ? (
              <Button
                variant="primary"
                disabled={!can(user, "runs.resume") || action.isPending}
                onClick={() => action.mutate({ kind: "resume" })}
              >
                <Play size={15} />
                {r.revision === 0 ? t("启动") : t("继续")}
              </Button>
            ) : null}
            <Button
              disabled={!r.revision || !can(user, "runs.create")}
              onClick={() => setForkOpen(true)}
            >
              <GitFork size={15} />
              {t("分叉 / 继承")}
            </Button>
          </>
        }
      />
      {r.assessment && (
        <div className="notice">
          {t(
            "该意识属于独立评估，环境、输入和参数已冻结。请在独立评估页面控制，或先分叉。",
          )}{" "}
          <Link to={"/studies?tab=assessment&assessment=" + r.assessment.id}>
            {r.assessment.name}
          </Link>
        </div>
      )}
      {r.ecology && (
        <p className="notice">
          {t(
            "此个体属于生态训练，暂停、继续和物理世界恢复由整个种群统一处理。训练协议已冻结；个体原始输入、读出和模型仍可查看与导出。",
          )}{" "}
          <Link to={"/studies?tab=ecology&campaign=" + r.ecology.campaign_id}>
            {t("管理所属生态训练")}
          </Link>
        </p>
      )}
      {searchParams.get("metadata") === "1" && (
        <ModelMetadataDialog
          base={base}
          close={() => setSearchParams({ view: tab })}
        />
      )}
      {r.archived_at && (
        <p className="notice">
          {t(
            "这份意识已归档。数据、恢复点与来源谱系仍可查询；可在档案编辑中取消归档。",
          )}
        </p>
      )}
      {configureOpen && (
        <EditRunConfiguration
          key={r.id}
          run={r}
          initialGroup={searchParams.get("group") ?? undefined}
          onClose={() => setSearchParams({})}
        />
      )}
      <Modal
        open={templateName !== null}
        onOpenChange={(open) => !open && setTemplateName(null)}
        title={t("从此实例参数创建模板")}
      >
        <p>{t("仅复制已保存的参数，不复制个体状态、学习权重或实验身份。")}</p>
        <Field label={t("模板名称")}>
          <input
            maxLength={120}
            value={templateName || ""}
            onChange={(event) => setTemplateName(event.target.value)}
          />
        </Field>
        <ErrorBox error={saveParameterTemplate.error} />
        <Button type="button" onClick={() => setTemplateName(null)}>
          {t("取消")}
        </Button>
        <Button
          type="button"
          variant="primary"
          disabled={!templateName?.trim() || saveParameterTemplate.isPending}
          onClick={() => saveParameterTemplate.mutate()}
        >
          {t("保存模板")}
        </Button>
      </Modal>
      <ErrorBox error={action.error ?? exportJob.error ?? run.error} />
      {r.status !== "queued" && (
        <div className="run-scheduling-toggle">
          <button
            className="text-link"
            type="button"
            aria-expanded={showScheduling}
            onClick={() => setShowScheduling(!showScheduling)}
          >
            {t("任务调度与执行记录")}
          </button>
        </div>
      )}
      {(r.status === "queued" || showScheduling) && project && (
        <Suspense fallback={<Loading />}>
          <SchedulingPanel key={r.id} projectId={project.id} runId={r.id} />
        </Suspense>
      )}
      {r.error && <ErrorBox error={r.error} />}
      <div className="run-summary">
        <span>
          {t("模拟时间 ")}
          <strong className="mono">{timeLabel(r.time_us)}</strong>
        </span>
        <span>
          {t("节点 ")}
          <strong>{numberLabel(r.metrics.nodes, 0)}</strong>
        </span>
        <span>
          {t("连接 ")}
          <strong>{numberLabel(r.metrics.edges, 0)}</strong>
        </span>
        <span>
          {isSpiking ? t("总归一化去极化 ") : t("总激活 ")}
          <strong>{numberLabel(r.metrics.activation, 4)}</strong>
        </span>
        <span>
          {t("数据库状态 ")}
          <strong className="mono">r{r.revision}</strong>
        </span>
      </div>
      <div className="tabs page-tabs runtime-tabs" aria-label={t("意识工具")}>
        {[
          ["network", "意识网络"],
          ["conversation", "刺激与读出"],
          ["dynamics", "动力学"],
          ["inputs", "感官与输入"],
          ["readouts", "时序与截面读出"],
          ["research", "人工实验"],
          ["ai", "AI 工具"],
          ["events", "因果事件"],
          ["checkpoints", "恢复与版本"],
          ["protocol", "运行协议"],
        ].map(([value, label]) => (
          <button
            className={tab === value ? "active" : ""}
            onClick={() => {
              setTab(value);
              setSearchParams({ view: value });
            }}
            key={value}
          >
            {t(label)}
          </button>
        ))}
      </div>
      {notice && (
        <div className="notice" role="status">
          {t(notice)}
          <button className="text-link" onClick={() => setNotice("")}>
            {t("收起")}
          </button>
        </div>
      )}
      {tab === "research" && (
        <Suspense fallback={<Loading />}>
          <ResearchConsole key={r.id} base={base} run={r} />
        </Suspense>
      )}
      {tab === "ai" && (
        <Suspense fallback={<Loading />}>
          <AITools key={r.id} base={base} run={r} />
        </Suspense>
      )}
      {tab === "network" && (
        <>
          {r.revision === 0 && (
            <p className="notice">
              {t("尚未启动。配置已保存，点击“启动”后才会推进模拟时间。")}
            </p>
          )}
          {isSpiking && (
            <p className="notice">
              {t(
                "此脉冲候选的图形与读出按去极化投影显示。膜电位、电流和发放次数可在动力学中查看。",
              )}
            </p>
          )}
          <div className="player-mobile-tabs tabs" aria-label={t("工作台面板")}>
            <button
              className={playerPane === "network" ? "active" : ""}
              onClick={() => setPlayerPane("network")}
            >
              {t("意识网络")}
            </button>
            <button
              className={playerPane === "inspector" ? "active" : ""}
              onClick={() => setPlayerPane("inspector")}
            >
              {t("属性、刺激与读出")}
            </button>
          </div>
          <div className={`observatory player-pane-${playerPane}`}>
            <Graph
              project={project!.id}
              run={id!}
              onSelect={setNode}
              polling={["queued", "running"].includes(r.status)}
              revision={r.revision}
            />
            <aside className="inspector">
              <Suspense fallback={<Loading />}>
                <Conversation key={r.id} base={base} run={r} compact />
              </Suspense>
              <details className="inspector-section" open={node != null}>
                <summary>{t("观察节点")}</summary>
                {node == null ? (
                  <p>{t("点击图中的节点，查看该节点的已提交状态。")}</p>
                ) : (
                  <>
                    <div className="inspected-id">
                      {t("节点 #")}
                      {node}
                    </div>
                    <dl>
                      {Object.entries(
                        inspected.data?.rows?.[0]?.id === node
                          ? inspected.data.rows[0]
                          : {},
                      ).map(([key, value]) => (
                        <div key={key}>
                          <dt>{key}</dt>
                          <dd>
                            {typeof value === "number"
                              ? numberLabel(value, 5)
                              : String(value)}
                          </dd>
                        </div>
                      ))}
                    </dl>
                    {inspected.data &&
                      inspected.data.rows?.[0]?.id !== node && (
                        <p>{t("该节点已不在当前提交的状态中。")}</p>
                      )}
                  </>
                )}
              </details>
              <div className="inspector-section">
                <h3>{t("记录与导出")}</h3>
                <p>
                  {t("数据版本 r")}
                  {r.revision} · {timeLabel(r.time_us)}
                  <br />
                  {t("图形显示使用数据库已提交的状态。")}
                </p>
                <select
                  aria-label={t("导出格式")}
                  value={format}
                  onChange={(e) => setFormat(e.target.value)}
                >
                  <option value="tmind">{t("标准模型 .tmind")}</option>
                  <option value="json">{t("等价 JSON 模型")}</option>
                  <option value="evidence">{t("完整研究证据 ZIP")}</option>
                </select>
                <Button
                  disabled={
                    !r.revision ||
                    exportJob.isPending ||
                    !can(user, "runs.export")
                  }
                  onClick={() => exportJob.mutate()}
                >
                  <Download size={15} />
                  {t("按需导出")}
                </Button>
                <Link
                  className="text-link"
                  to={`/projects/${encodeURIComponent(project!.id)}/tools/models?view=artifacts`}
                >
                  {t("查看导出任务 ")}
                  <ArrowRight size={13} />
                </Link>
              </div>
              <details className="inspector-section">
                <summary>{t("生命周期操作")}</summary>
                <p>{t("关闭输入后，已有内部活动仍会继续演化。")}</p>
                <Button
                  disabled={
                    !active || !!r.spec.study_id || !can(user, "runs.configure")
                  }
                  onClick={() => action.mutate({ kind: "close_inputs" })}
                >
                  {t("关闭所有输入")}
                </Button>
                <Button
                  variant="danger"
                  disabled={
                    (!active && r.status !== "paused") ||
                    !can(user, "runs.intervene")
                  }
                  onClick={() => action.mutate({ kind: "cancel" })}
                >
                  <Square size={14} />
                  {t("终止执行")}
                </Button>
              </details>
            </aside>
          </div>
        </>
      )}
      {tab === "conversation" && (
        <Conversation key={r.id} base={base} run={r} />
      )}
      {tab === "inputs" && (
        <SensoryPage
          base={base}
          run={r}
          initialTool={searchParams.get("tool") ?? undefined}
          initialInput={searchParams.get("input") ?? undefined}
          configure={(group) =>
            setSearchParams({ configure: "1", ...(group ? { group } : {}) })
          }
        />
      )}
      {tab === "readouts" && (
        <ReadoutPage
          base={base}
          run={r}
          initialRecord={searchParams.get("record") ?? undefined}
          configure={() => setSearchParams({ configure: "1" })}
        />
      )}
      {tab === "dynamics" && (
        <>
          <div className="tabs" aria-label={t("动力学分类")}>
            {[
              ["activity", "活动与结构"],
              ["resources", "容量与预算"],
              ["energy", "能量与供给"],
              ["spatial", "空间基底"],
            ]
              .filter(([value]) => !isSpiking || value === "activity")
              .map(([value, label]) => (
                <button
                  key={value}
                  className={dynamicsTab === value ? "active" : ""}
                  onClick={() => setDynamicsTab(value)}
                >
                  {t(label)}
                </button>
              ))}
          </div>
          {!isSpiking && dynamicsTab === "resources" && (
            <ResourcePanel base={base} run={r} />
          )}
          {!isSpiking && dynamicsTab === "spatial" && (
            <SpatialPanel
              project={project!.id}
              base={base}
              run={r}
              configure={() => setSearchParams({ configure: "1" })}
            />
          )}
          {!isSpiking && dynamicsTab === "energy" && (
            <EnergyPanel
              base={base}
              run={r}
              configure={() => setSearchParams({ configure: "1" })}
            />
          )}
          {isSpiking && (
            <PhysicalMembranes key={r.id} base={base} revision={r.revision} />
          )}
          {!isSpiking && dynamicsTab === "activity" && (
            <div className="chart-grid">
              {[
                "mean_activation",
                "saturated_fraction",
                "activation",
                "edges",
                "inhibition",
                "mean_weight",
                "active_fraction",
                "edge_density",
              ].map((metric) => (
                <section className="panel" key={metric}>
                  <Chart
                    metric={metric}
                    rows={
                      observations.data?.rows?.map((r: any) => r.metrics) ?? []
                    }
                  />
                </section>
              ))}
              {observations.data?.more && (
                <p className="notice">
                  {t(
                    "当前展示前 10,000 个观测点。完整记录可在研究证据包中导出。",
                  )}
                </p>
              )}
            </div>
          )}
        </>
      )}
      {tab === "events" && (
        <section className="panel">
          <div className="panel-heading">
            <h2>{t("因果事件")}</h2>
            <select
              value={eventKind}
              onChange={(e) => setEventKind(e.target.value)}
            >
              <option value="">{t("全部因果事件")}</option>
              <option value="input_delivered">{t("已递送输入")}</option>
              <option value="energy_scheduled">{t("能量供给调度")}</option>
              <option value="energy_delivered">{t("能量供给递送")}</option>
              <option value="structure_interval">{t("结构变化区间")}</option>
              <option value="intervention">{t("干预")}</option>
              <option value="pause">{t("暂停")}</option>
              <option value="phase">{t("实验阶段")}</option>
            </select>
          </div>
          <div className="event-list">
            {events.data?.map((event) => (
              <div className="event-row" key={event.id}>
                <span className="mono">{timeLabel(event.time_us)}</span>
                <strong>{event.kind}</strong>
                <details>
                  <summary>{t("查看数据")}</summary>
                  <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                </details>
              </div>
            ))}
          </div>
          {!events.data?.length && (
            <Empty
              title={t("暂无事件记录")}
              detail={t("输入、干预和结构变化将在提交后显示。")}
            />
          )}
          <div className="footnote">
            {t(
              "此处展示最多 500 条因果事件。器官采样在“感官与输入 → 器官输出”查看，避免此页加载大量图像像素；证据导出仍包含所选检查点之前的完整已记录事件。",
            )}
          </div>
        </section>
      )}
      {tab === "checkpoints" && (
        <>
          <Suspense fallback={<Loading />}>
            <StateCaptures
              key={r.id}
              base={base}
              run={r}
              onFork={(cp) => {
                setForkCp(cp);
                setForkOpen(true);
              }}
            />
          </Suspense>
          <VersionLibrary
            base={base}
            run={r}
            onFork={(cp) => {
              setForkCp(cp);
              setForkOpen(true);
            }}
          />
        </>
      )}
      {tab === "protocol" && (
        <section className="panel protocol">
          <h2>{t("冻结的运行协议")}</h2>
          <p>
            {t("同一输入、内核版本、时间参数与完整恢复状态共同决定重放条件。")}
          </p>
          <pre>{JSON.stringify(r.spec, null, 2)}</pre>
          <p className="mono">
            state_hash: {r.state_hash ?? t("等待首次提交")}
          </p>
          {r.origin_hash && (
            <p className="mono">origin_hash: {r.origin_hash}</p>
          )}
        </section>
      )}
      <Modal
        open={forkOpen}
        onOpenChange={setForkOpen}
        title={t("从状态创建新实例")}
        description={t("保留来源和谱系。原运行继续独立存在。")}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            fork.mutate();
          }}
        >
          <Field label={t("分支名称")}>
            <input
              value={forkName}
              onChange={(e) => setForkName(e.target.value)}
              required
            />
          </Field>
          <Field label={t("起始状态")}>
            <select value={forkCp} onChange={(e) => setForkCp(e.target.value)}>
              <option value="">{t("最新已提交恢复点")}</option>
              {forkCp && !checkpoints.data?.some((cp) => cp.id === forkCp) && (
                <option value={forkCp}>
                  {t("已选历史恢复点 · ")}
                  {forkCp.slice(0, 8)}
                </option>
              )}
              {checkpoints.data?.map((cp) => (
                <option key={cp.id} value={cp.id}>
                  {cp.label ? `${cp.label} · ` : ""}r{cp.revision} ·{" "}
                  {timeLabel(cp.time_us)}
                </option>
              ))}
            </select>
          </Field>
          <label className="check">
            <input
              type="checkbox"
              checked={!!r.ecology || inherit}
              disabled={!!r.ecology}
              onChange={(e) => setInherit(e.target.checked)}
            />
            {t("作为先天模型继承出生，重置激活等快状态")}
          </label>
          <p className="muted">
            {t(
              "未勾选时保留活动、待传播事件与模拟环境状态，创建精确恢复分支。",
            )}
          </p>
          <ErrorBox error={fork.error} />
          <div className="form-actions">
            <Button variant="primary" disabled={fork.isPending}>
              {t("创建分支")}
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

export function DataPage() {
  const runs = useRuns(),
    { project } = useWorkspace();
  const [queryParams] = useSearchParams();
  const [selected, setSelected] = useState(queryParams.get("run") ?? ""),
    [table, setTable] = useState("nodes"),
    [minimum, setMinimum] = useState("0"),
    [source, setSource] = useState(""),
    [checkpoint, setCheckpoint] = useState(queryParams.get("checkpoint") ?? ""),
    [exportFormat, setExportFormat] = useState("csv"),
    [after, setAfter] = useState<number | undefined>(),
    [revision, setRevision] = useState<number | undefined>();
  const runId = selected || runs.data?.[0]?.id;
  const checkpoints = useQuery({
    queryKey: ["query-checkpoints", project?.id, runId],
    queryFn: () =>
      api<any[]>(`${projectPath(project!.id)}/runs/${runId}/checkpoints`),
    enabled: !!runId,
  });
  const query = useQuery({
    queryKey: [
      "data",
      project?.id,
      runId,
      table,
      minimum,
      source,
      after,
      revision,
      checkpoint,
    ],
    queryFn: () =>
      api(
        `${projectPath(project!.id)}/runs/${runId}/data/${table}?limit=100&minimum=${Number(minimum) || 0}${after != null ? `&after=${after}` : ""}${revision != null ? `&revision=${revision}` : ""}${source ? `&source=${encodeURIComponent(source)}` : ""}${checkpoint ? `&checkpoint_id=${checkpoint}` : ""}`,
      ),
    enabled: !!runId,
    retry: false,
  });
  const rows = query.data?.rows ?? [],
    columns = rows.length ? Object.keys(rows[0]) : [];
  const exportQuery = useMutation({
    mutationFn: () =>
      post(`${projectPath(project!.id)}/runs/${runId}/data-exports`, {
        table,
        format: exportFormat,
        minimum: Number(minimum) || 0,
        source: source || null,
        checkpoint_id: checkpoint || null,
        revision: query.data?.revision,
      }),
  });
  function reset() {
    setAfter(undefined);
    setRevision(undefined);
  }
  return (
    <>
      <PageTitle
        eyebrow="DATA EXPLORER"
        title={t("数据查询")}
        description={t("按条件检查连接与节点；分页绑定同一个已提交版本。")}
      />
      <section className="panel">
        <div className="query-filters">
          <Field label={t("运行")}>
            <select
              value={runId ?? ""}
              onChange={(e) => {
                setSelected(e.target.value);
                setCheckpoint("");
                reset();
              }}
            >
              {selected && !runs.data?.some((r) => r.id === selected) && (
                <option value={selected}>
                  {t("指定意识 · ")}
                  {selected}
                </option>
              )}
              {runs.data?.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("数据类型")}>
            <select
              value={table}
              onChange={(e) => {
                setTable(e.target.value);
                reset();
              }}
            >
              <option value="nodes">{t("节点状态")}</option>
              <option value="edges">{t("连接状态")}</option>
              <option value="changes">{t("连接变化")}</option>
            </select>
          </Field>
          <Field label={t("状态版本")}>
            <select
              aria-label={t("状态版本")}
              value={checkpoint}
              onChange={(e) => {
                setCheckpoint(e.target.value);
                reset();
              }}
            >
              <option value="">{t("最新提交")}</option>
              {checkpoint &&
                !checkpoints.data?.some((cp) => cp.id === checkpoint) && (
                  <option value={checkpoint}>{t("指定历史恢复点")}</option>
                )}
              {checkpoints.data?.map((cp) => (
                <option key={cp.id} value={cp.id}>
                  {cp.label ? `${cp.label} · ` : ""}r{cp.revision} ·{" "}
                  {timeLabel(cp.time_us)}
                </option>
              ))}
            </select>
          </Field>
          <Field
            label={
              table === "nodes"
                ? t("最低激活量")
                : table === "changes"
                  ? t("最小权重变化（绝对值）")
                  : t("最低权重")
            }
          >
            <input
              type="number"
              min="0"
              max="1"
              step=".01"
              value={minimum}
              onChange={(e) => {
                setMinimum(e.target.value);
                reset();
              }}
            />
          </Field>
          {table !== "nodes" && (
            <Field label={t("源节点 ID（可选）")}>
              <input
                type="text"
                value={source}
                onChange={(e) => {
                  setSource(e.target.value);
                  reset();
                }}
              />
            </Field>
          )}
          <Button
            onClick={() => {
              reset();
              query.refetch();
            }}
          >
            <RefreshCw size={15} />
            {t("刷新版本")}
          </Button>
        </div>
        <div className="query-export">
          <select
            aria-label={t("筛选导出格式")}
            value={exportFormat}
            onChange={(e) => setExportFormat(e.target.value)}
          >
            <option value="csv">{t("CSV 数据表")}</option>
            <option value="jsonl">{t("JSONL 记录")}</option>
            <option value="parquet">{t("Parquet 列式数据")}</option>
          </select>
          <Button
            disabled={!query.data || exportQuery.isPending}
            onClick={() => exportQuery.mutate()}
          >
            <Download size={15} />
            {t("导出全部匹配结果")}
          </Button>
          {exportQuery.isSuccess && (
            <Link to="/models">{t("导出任务已提交，查看产物 →")}</Link>
          )}
        </div>
        <ErrorBox error={exportQuery.error} />
        <ErrorBox error={query.error} />
        {query.isPending && runId ? (
          <Loading />
        ) : rows.length ? (
          <div className="table-scroll">
            <table className="numeric-table">
              <thead>
                <tr>
                  {columns.map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row: any, i: number) => (
                  <tr key={i}>
                    {columns.map((c) => (
                      <td key={c}>
                        {typeof row[c] === "number"
                          ? numberLabel(row[c], 6)
                          : String(row[c])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title={t("没有匹配的数据")}
            detail={t("创建意识并等待第一次提交，或调整当前筛选条件。")}
          />
        )}
        <div className="pagination">
          <span>
            r{query.data?.revision ?? "—"} · {timeLabel(query.data?.time_us)}
            {t(" · 当前 ")}
            {rows.length}
            {t(" 条")}
          </span>
          <div>
            <Button disabled={after == null} onClick={reset}>
              <ChevronLeft size={15} />
              {t("回到首页")}
            </Button>
            <Button
              disabled={!query.data?.more}
              onClick={() => {
                setRevision(query.data.revision);
                setAfter(query.data.next);
              }}
            >
              {t("下一页")}
              <ChevronRight size={15} />
            </Button>
          </div>
        </div>
      </section>
      <div className="footnote">
        {t(
          "导出包含全部匹配记录及筛选条件、状态哈希。连接变化比较相邻恢复点，时间范围在每条记录中标明。完整可运行模型请从运行页面导出。",
        )}
      </div>
    </>
  );
}

export function ModelsPage() {
  const { project, user } = useWorkspace(),
    client = useQueryClient(),
    navigate = useNavigate();
  const base = projectPath(project!.id);
  const [search, setSearch] = useSearchParams();
  const libraryView =
    search.get("view") === "species"
      ? "species"
      : search.get("view") === "bundles"
        ? "bundles"
        : search.get("view") === "artifacts"
          ? "artifacts"
          : "library";
  const setLibraryView = (view: string) =>
    setSearch(view === "library" ? {} : { view });
  const artifacts = useQuery({
    queryKey: ["artifacts", project?.id],
    enabled: libraryView === "artifacts",
    queryFn: () => api<any[]>(`${base}/artifacts`),
    refetchInterval: 2000,
  });
  const jobs = useQuery({
    queryKey: ["jobs", project?.id],
    enabled: libraryView === "artifacts",
    queryFn: () => api<any[]>(`${base}/jobs`),
    refetchInterval: 1500,
  });
  const [importError, setImportError] = useState<unknown>(),
    [importing, setImporting] = useState(false);
  async function importFile(file: File) {
    setImporting(true);
    setImportError(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const run = await api<Run>(
        `${base}/imports?name=${encodeURIComponent(file.name)}`,
        { method: "POST", body },
      );
      client.invalidateQueries({ queryKey: ["runs"] });
      navigate(`/runs/${run.id}`);
    } catch (e) {
      setImportError(e);
    } finally {
      setImporting(false);
    }
  }
  return (
    <>
      <PageTitle
        eyebrow="MODELS & EVIDENCE"
        title={t("模型与证据")}
        description={t("模型按需导出；日常运行状态与研究证据保存在数据库中。")}
        actions={
          libraryView !== "species" && (
            <label className={`button primary ${importing ? "disabled" : ""}`}>
              <Upload size={16} />
              {importing ? t("正在校验…") : t("导入模型")}
              <input
                type="file"
                hidden
                accept=".tmind,.json"
                disabled={importing || !can(user, "data.import")}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void importFile(file);
                  e.target.value = "";
                }}
              />
            </label>
          )
        }
      />
      <ErrorBox error={importError} />
      <nav
        className="tabs page-tabs view-tabs"
        aria-label={t("模型与证据分类")}
      >
        <button
          className={libraryView === "library" ? "active" : ""}
          onClick={() => setLibraryView("library")}
        >
          {t("意识档案")}
        </button>
        <button
          className={libraryView === "artifacts" ? "active" : ""}
          onClick={() => setLibraryView("artifacts")}
        >
          {t("导出文件与任务")}
        </button>
        <button
          className={libraryView === "bundles" ? "active" : ""}
          onClick={() => setLibraryView("bundles")}
        >
          {t("实验快照")}
        </button>
        <button
          className={libraryView === "species" ? "active" : ""}
          onClick={() => setLibraryView("species")}
        >
          {t("物种库")}
        </button>
      </nav>
      {libraryView === "library" && <ModelLibrary key={project!.id} />}
      {libraryView === "species" && (
        <Suspense fallback={<Loading />}>
          <SpeciesLibrary key={project!.id} />
        </Suspense>
      )}
      {libraryView === "bundles" && (
        <Suspense fallback={<Loading />}>
          <Bundles key={project!.id} />
        </Suspense>
      )}
      {libraryView === "artifacts" && (
        <>
          <div className="model-explanation">
            <div>
              <Box size={21} />
              <h3>{t("标准模型 .tmind")}</h3>
              <p>{t("完整状态、时间相位与待处理事件，用于独立意识和交换。")}</p>
            </div>
            <div>
              <GitFork size={21} />
              <h3>{t("继承与继续学习")}</h3>
              <p>
                {t(
                  "从恢复点创建分支，或继承慢状态，让模型在新环境中持续塑造。",
                )}
              </p>
            </div>
            <div>
              <FileArchive size={21} />
              <h3>{t("研究证据包")}</h3>
              <p>
                {t("协议、输入记录、数据表、模型和 SVG / PNG / PDF 图表。")}
              </p>
            </div>
          </div>
          <section className="panel">
            <div className="panel-heading">
              <h2>{t("已生成的产物")}</h2>
              <span className="muted">
                {artifacts.data?.length ?? 0}
                {t(" 个文件")}
              </span>
            </div>
            {artifacts.data?.length ? (
              <div className="table-scroll">
                <table className="artifact-table">
                  <thead>
                    <tr>
                      <th>{t("文件")}</th>
                      <th>{t("大小")}</th>
                      <th>{t("来源 / 校验")}</th>
                      <th>{t("生成时间")}</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {artifacts.data.map((a) => (
                      <tr key={a.id}>
                        <td>
                          <strong>{a.name}</strong>
                          <small>{a.media_type}</small>
                          {a.metadata?.evidence_boundary && (
                            <small className="artifact-evidence-scope">
                              {t("统计按恢复点的提交版本限定。")}
                              {Number(
                                a.metadata.evidence_boundary.unscoped_counts
                                  ?.observations ?? 0,
                              ) +
                                Number(
                                  a.metadata.evidence_boundary.unscoped_counts
                                    ?.events ?? 0,
                                ) >
                                0 &&
                                `另附 ${numberLabel(Number(a.metadata.evidence_boundary.unscoped_counts?.observations ?? 0), 0)} 条采样、${numberLabel(Number(a.metadata.evidence_boundary.unscoped_counts?.events ?? 0), 0)} 条事件，其提交版本未知，未计入统计。`}
                            </small>
                          )}
                        </td>
                        <td data-label="大小">
                          {numberLabel(a.bytes / 1024)} KB
                        </td>
                        <td className="mono" data-label="来源 / 校验">
                          {a.metadata?.revision
                            ? `r${a.metadata.revision} · `
                            : ""}
                          {a.sha256.slice(0, 12)}…
                        </td>
                        <td data-label="生成时间">
                          {new Date(a.created_at).toLocaleString(locale())}
                        </td>
                        <td>
                          <a
                            className="button small"
                            href={`/api/v2${base}/artifacts/${a.id}`}
                            download
                          >
                            <Download size={14} />
                            {t("下载")}
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty
                title={t("尚未生成导出文件")}
                detail={t(
                  "进入运行页面，选择标准模型、JSON 或完整研究证据包。",
                )}
              />
            )}
          </section>
          <section className="panel">
            <div className="panel-heading">
              <h2>{t("后台任务")}</h2>
            </div>
            <div className="job-list">
              {jobs.data?.map((job) => (
                <div className="job-row" key={job.id}>
                  <span className="job-kind">
                    {(
                      {
                        run: "运行",
                        export: "导出",
                        study: "实验编排",
                        analysis: "统计分析",
                        notification: "邮件通知",
                      } as any
                    )[job.kind] ?? job.kind}
                  </span>
                  <Badge status={job.status} />
                  <span className="mono">{job.id.slice(0, 8)}</span>
                  <span className="muted">
                    {t("尝试 ")}
                    {job.attempts}
                  </span>
                  {job.error && <span className="job-error">{job.error}</span>}
                  {job.result?.artifact_id && (
                    <a
                      className="text-link"
                      href={`/api/v2${base}/artifacts/${job.result.artifact_id}`}
                    >
                      {t("下载结果 ")}
                      <Download size={13} />
                    </a>
                  )}
                </div>
              ))}
            </div>
            {!jobs.data?.length && (
              <Empty
                title={t("暂无任务")}
                detail={t("训练、分析和导出会作为可追踪的后台任务执行。")}
              />
            )}
          </section>
        </>
      )}
    </>
  );
}
