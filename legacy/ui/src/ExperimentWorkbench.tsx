import { FormEvent, lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Locale } from "./i18n";

const GraphViewport = lazy(() => import("./GraphViewport"));

const API = (import.meta.env.VITE_THREEMIND_API as string | undefined)?.replace(/\/$/, "") ?? "";
const WS_API = API ? API.replace(/^http/, "ws") : `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}`;

type Provider = { id: string; name: string; model?: string; kind?: string };
type GraphNode = { id: number; activation: number; stability: number; touch_count: number; direct: number; associative: number; position?: number[] | null; cluster?: number | null };
type GraphEdge = { source: number; target: number; weight: number; stability: number; touched: boolean };
type Graph = { nodes: GraphNode[]; edges: GraphEdge[]; neighbors?: GraphEdge[]; metrics?: { tick?: number; node_count?: number; edge_count?: number; active_nodes?: number } };
type Command = { op: string; mutating: boolean; description: string; args: Record<string, unknown> };
type Template = { id: string; title: string; description: string };
type ExperimentMetadata = { commands: Command[]; templates: Template[]; bridge?: { enabled?: boolean; auto_run_default?: boolean; limits?: Record<string, number> } };
type PlanStep = { id: string; op: string; args: Record<string, unknown>; rationale?: string; mutating?: boolean; status?: string; result?: unknown; duration_ms?: number };
type StreamEvent = { event: string; data: Record<string, unknown> };
type ExperimentOperation = { kind: "create" | "planning"; state: "active" | "success" | "error" | "cancelled"; stage: string; message: string };
type ExperimentRun = {
  id: string;
  title: string;
  created_at?: number;
  updated_at?: number;
  mode: "manual" | "approval" | "auto";
  provider_id?: string;
  goal?: string;
  template_id?: string;
  status: string;
  target: { runtime_id: string; runtime_name?: string; source_consciousness_id?: string; sandbox?: boolean; background_mode?: string };
  plan: PlanStep[];
  steps: PlanStep[];
  analysis?: Array<{ id: string; created_at: number; analysis: Record<string, unknown> }>;
  report?: { path?: string; review_status?: string } | null;
  artifacts?: Array<{ kind: string; path?: string; state?: string }>;
  limits?: Record<string, number>;
};

type WorkbenchDraft = {
  tab: "manual" | "ai";
  title: string;
  goal: string;
  templateId: string;
  mode: "manual" | "approval" | "auto";
  sandbox: boolean;
  pauseBackground: boolean;
  plannerProviderId: string;
  analysisProviderId: string;
  carrier: string;
  intensity: number;
  waitTicks: number;
  manualOp: string;
  snapshotLabel: string;
  historyKind: string;
  historyLimit: number;
  graphLimit: number;
  noteText: string;
  draftPlan: PlanStep[];
  aiPrompt: string;
  analysisPrompt: string;
};

const WORKBENCH_DRAFT_KEY = "threemind.experiment-workbench.draft.v1";
const WORKBENCH_SELECTED_RUN_KEY = "threemind.experiment-workbench.selected-run.v1";

export function rememberExperimentRun(runId: string): void {
  writeStorage(WORKBENCH_SELECTED_RUN_KEY, runId);
}

function readStorage(key: string): string {
  if (typeof window === "undefined") return "";
  try { return window.localStorage.getItem(key) ?? ""; } catch { return ""; }
}

function writeStorage(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    if (value) window.localStorage.setItem(key, value);
    else window.localStorage.removeItem(key);
  } catch {
    // The workbench remains fully functional when browser storage is disabled.
  }
}

function readWorkbenchDraft(): Partial<WorkbenchDraft> {
  const raw = readStorage(WORKBENCH_DRAFT_KEY);
  if (!raw) return {};
  try {
    const value = JSON.parse(raw);
    return value && typeof value === "object" && !Array.isArray(value) ? value as Partial<WorkbenchDraft> : {};
  } catch {
    return {};
  }
}

const copy = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

function labels(locale: Locale) {
  const zh = locale !== "en";
  return {
    title: zh ? "实验与调试" : "Experiments & Debugging",
    subtitle: zh ? "人工与 AI 共用同一套受限、可审计的实验命令；实验层不会直接改写意识网络。" : "Manual and AI workflows share one constrained, auditable command set; the experiment layer never rewrites the associative network.",
    manual: zh ? "人工协议" : "Manual protocol",
    ai: zh ? "AI 计划" : "AI plan",
    evidence: zh ? "证据与报告" : "Evidence & report",
    create: zh ? "创建隔离实验" : "Create isolated run",
    target: zh ? "目标意识" : "Target consciousness",
    titleField: zh ? "实验名称" : "Experiment title",
    goal: zh ? "研究问题 / 假设" : "Research question / hypothesis",
    template: zh ? "协议模板" : "Protocol template",
    mode: zh ? "执行模式" : "Execution mode",
    sandbox: zh ? "克隆为隔离沙箱（推荐）" : "Clone into isolated sandbox (recommended)",
    background: zh ? "暂停沙箱背景刺激，便于控制变量" : "Pause ambient stimulus in sandbox for control",
    planned: zh ? "待执行计划" : "Planned commands",
    buildTemplate: zh ? "生成模板计划" : "Build template plan",
    addCommand: zh ? "加入此命令" : "Add this command",
    command: zh ? "受限实验命令" : "Restricted experiment command",
    addStimulus: zh ? "加入文本刺激" : "Add text stimulus",
    addWait: zh ? "加入等待" : "Add wait",
    addObserve: zh ? "加入输出观测" : "Add output observation",
    savePlan: zh ? "保存人工计划" : "Save manual plan",
    execute: zh ? "执行此步" : "Execute step",
    run: zh ? "执行整个计划" : "Run whole plan",
    stop: zh ? "停止实验" : "Stop experiment",
    carrier: zh ? "实验载体文本" : "Carrier text",
    intensity: zh ? "强度" : "Intensity",
    wait: zh ? "等待 tick" : "Wait ticks",
    snapshotLabel: zh ? "快照名称" : "Snapshot label",
    historyKind: zh ? "历史种类" : "History kind",
    historyLimit: zh ? "历史条数" : "History rows",
    graphLimit: zh ? "图像节点上限" : "Graph node limit",
    note: zh ? "研究者注记" : "Researcher note",
    aiPrompt: zh ? "让 AI 设计一个可证伪、受控的实验计划" : "Ask AI for a falsifiable, controlled experiment plan",
    analysisPrompt: zh ? "分析重点（可选）" : "Analysis focus (optional)",
    generate: zh ? "生成并校验 AI 计划" : "Generate & validate AI plan",
    noProvider: zh ? "请选择已配置的 AI 供应商；AI 只能提交命令草案，不能直接访问 Core。" : "Choose a configured AI provider. AI can only submit command drafts and never gets direct Core access.",
    analyze: zh ? "生成分析" : "Generate analysis",
    export: zh ? "导出实验报告到 lab" : "Export report to lab",
    graph: zh ? "实验目标图像" : "Experiment target graph",
    trace: zh ? "执行轨迹" : "Execution trace",
    noRun: zh ? "先创建一个实验运行。默认会从当前意识克隆出隔离沙箱。" : "Create an experiment run first. By default, it clones the current consciousness into an isolated sandbox.",
    approval: zh ? "需确认" : "Approval",
    auto: zh ? "受限自动" : "Bounded auto",
    autoHelp: zh ? "仅限隔离沙箱：AI 计划通过注册表校验后，才会自动执行。" : "Sandbox only: an AI plan runs automatically only after registry validation.",
    manualMode: zh ? "人工逐步" : "Manual steps",
    view: zh ? "当前实验" : "Experiment run",
    selectRun: zh ? "选择实验运行" : "Select an experiment run",
    runRecovery: zh ? "运行状态保存在后端；离开本页后可在这里恢复。" : "Run state is stored by the backend and can be resumed here after leaving this page.",
    refresh: zh ? "刷新" : "Refresh",
    aiAnalysis: zh ? "AI / 外部分析" : "AI / external analysis",
    reportNote: zh ? "报告会标记为“自动生成，未审核”，不等同于意识结论。" : "Reports are marked generated/unreviewed and are not conclusions about consciousness.",
    commandBoundary: zh ? "允许命令" : "Allowed commands",
    noPlan: zh ? "尚未建立计划。" : "No plan yet.",
    planningProvider: zh ? "AI 规划供应商（可选）" : "AI planning provider (optional)",
    planningProviderHelp: zh ? "创建后会自动作为本实验的默认规划供应商；可在 AI 计划中继续更换。" : "This becomes the run's default planning provider and can still be changed in AI plan.",
    refreshProviders: zh ? "刷新供应商" : "Refresh providers",
    providerUnavailable: zh ? "尚未发现已保存的 AI 供应商。请先在设置中保存供应商配置，再刷新此处列表。" : "No saved AI providers were found. Save a provider in Settings, then refresh this list.",
    bridgeUnavailable: zh ? "AI 实验／调试桥当前未启用。请在“适配器管理”中启用它后再创建实验。" : "The AI experiment/debug bridge is disabled. Enable it in Adapter management before creating an experiment.",
    creating: zh ? "正在创建隔离实验…" : "Creating isolated experiment…",
    planning: zh ? "AI 正在生成计划…" : "AI is generating a plan…",
    waitingOutput: zh ? "正在等待供应商开始输出…" : "Waiting for provider output…",
    plannerOutput: zh ? "AI 规划输出（尚未执行）" : "AI planning output (not executed)",
  };
}

const experimentTemplateTitle = (locale: Locale, template: Template): string => {
  const localized: Record<string, [string, string]> = {
    repeatability: ["重复载体 / 结构响应", "Repeated carrier / structure response"],
    association: ["联想与迁移", "Association and transfer"],
    forgetting: ["遗忘与固化", "Forgetting and consolidation"],
    "sequence-order": ["输入顺序比较", "Input-order comparison"],
    "free-form": ["开放研究协议", "Open research protocol"],
  };
  const pair = localized[template.id];
  return pair ? pair[locale === "en" ? 1 : 0] : template.title;
};

const experimentCommandTitle = (locale: Locale, op: string): string => {
  const localized: Record<string, [string, string]> = {
    "observe.summary": ["观测摘要", "Observe summary"],
    "observe.output": ["读取输出", "Observe output"],
    "observe.graph": ["读取图像", "Observe graph"],
    "history.tail": ["读取近期历史", "Read recent history"],
    "stimulus.send": ["发送刺激", "Send stimulus"],
    "runtime.wait": ["等待", "Wait"],
    "snapshot.capture": ["创建快照", "Capture snapshot"],
    "runtime.pause": ["暂停运行", "Pause runtime"],
    "runtime.resume": ["恢复运行", "Resume runtime"],
    "experiment.note": ["写入实验笔记", "Add experiment note"],
  };
  const pair = localized[op];
  return pair ? `${pair[locale === "en" ? 1 : 0]} · ${op}` : op;
};

const historyKindTitle = (locale: Locale, kind: string): string => {
  const localized: Record<string, [string, string]> = {
    stimuli: ["刺激记录", "Stimuli"],
    events: ["事件记录", "Events"],
    observations: ["被动读出", "Passive readouts"],
    interpretations: ["解读记录", "Interpretations"],
    trace: ["执行轨迹", "Execution trace"],
  };
  const pair = localized[kind];
  return pair ? pair[locale === "en" ? 1 : 0] : kind;
};

const experimentStatusTitle = (locale: Locale, status: string): string => {
  const localized: Record<string, [string, string]> = {
    created: ["已创建", "Created"],
    planned: ["已计划", "Planned"],
    awaiting_approval: ["等待确认", "Awaiting approval"],
    running: ["运行中", "Running"],
    completed: ["已完成", "Completed"],
    cancelled: ["已取消", "Cancelled"],
    failed: ["失败", "Failed"],
    stopped: ["已停止", "Stopped"],
  };
  const pair = localized[status];
  return pair ? pair[locale === "en" ? 1 : 0] : status;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { cache: "no-store", ...init, headers: { "content-type": "application/json", ...(init?.headers ?? {}) } });
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail ?? detail; } catch { /* use status text */ }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

async function readEventStream(path: string, init: RequestInit, onEvent: (event: StreamEvent) => void): Promise<void> {
  const response = await fetch(`${API}${path}`, {
    cache: "no-store",
    ...init,
    headers: { Accept: "text/event-stream", "content-type": "application/json", ...(init.headers ?? {}) },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail ?? detail; } catch { /* use status text */ }
    throw new Error(detail);
  }
  if (!response.body) throw new Error("Experiment stream is unavailable");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const dispatch = (block: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith("event:")) event = line.slice(6).trim() || "message";
      if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length) return;
    let data: Record<string, unknown> = {};
    try {
      const value = JSON.parse(dataLines.join("\n"));
      if (value && typeof value === "object" && !Array.isArray(value)) data = value as Record<string, unknown>;
    } catch {
      data = { detail: dataLines.join("\n") };
    }
    onEvent({ event, data });
  };
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split(/\r?\n\r?\n/);
      buffer = blocks.pop() ?? "";
      for (const block of blocks) dispatch(block);
    }
    buffer += decoder.decode();
    if (buffer.trim()) dispatch(buffer);
  } catch (error) {
    // AbortController is used by the visible "stop planning" action.  Tell
    // the browser to close this one-way response rather than leaving a reader
    // locked while the server finishes its bounded request.
    await reader.cancel().catch(() => undefined);
    throw error;
  } finally {
    reader.releaseLock();
  }
}

function operationStageText(locale: Locale, stage: string, fallback: string): string {
  const isEnglish = locale === "en";
  const copy: Record<string, [string, string]> = {
    validating: ["正在校验实验请求…", "Validating experiment request…"],
    target_ready: ["目标意识已就绪…", "Target consciousness is ready…"],
    cloning: ["正在克隆意识状态到隔离沙箱…", "Cloning consciousness state into an isolated sandbox…"],
    initializing: ["正在初始化隔离沙箱与适配器…", "Initializing isolated sandbox and adapters…"],
    sandbox_ready: ["隔离沙箱已经启动…", "Isolated sandbox is running…"],
    recording: ["正在记录实验初始状态…", "Recording initial experiment state…"],
    checkpointing: ["正在保存实验历史检查点…", "Checkpointing experiment history…"],
    ready: ["实验运行已创建。", "Experiment run is ready."],
    preparing: ["正在准备受限的 AI 规划请求…", "Preparing bounded AI planning request…"],
    requesting: ["正在请求 AI 生成实验计划…", "Requesting AI planning proposal…"],
    ai_validating: ["正在提取并校验 AI 提议的计划…", "Extracting and validating AI-proposed plan…"],
    completed: ["AI 计划已生成并通过校验。", "AI plan generated and validated."],
  };
  const item = copy[stage];
  return item ? item[isEnglish ? 1 : 0] : fallback;
}

function operationProgress(operation: ExperimentOperation): number {
  if (operation.state === "success") return 100;
  if (operation.state === "error" || operation.state === "cancelled") return 100;
  const progress: Record<string, number> = {
    validating: 8,
    target_ready: 18,
    cloning: 36,
    initializing: 54,
    sandbox_ready: 68,
    recording: 80,
    checkpointing: 90,
    ready: 100,
    preparing: 12,
    requesting: 32,
    ai_validating: 88,
  };
  return progress[operation.stage] ?? 20;
}

function planId() { return `step-${crypto.randomUUID().slice(0, 8)}`; }

export function ExperimentWorkbench({ locale, activeConsciousnessId }: { locale: Locale; activeConsciousnessId: string }) {
  const t = labels(locale);
  const restoredDraft = useMemo(readWorkbenchDraft, []);
  const [runs, setRuns] = useState<ExperimentRun[]>([]);
  const [selectedId, setSelectedId] = useState(() => readStorage(WORKBENCH_SELECTED_RUN_KEY));
  const [run, setRun] = useState<ExperimentRun | null>(null);
  const [graph, setGraph] = useState<Graph | null>(null);
  const [commands, setCommands] = useState<Command[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [bridge, setBridge] = useState<ExperimentMetadata["bridge"] | null>(null);
  const [tab, setTab] = useState<"manual" | "ai">(restoredDraft.tab ?? "manual");
  const [title, setTitle] = useState(restoredDraft.title ?? "");
  const [goal, setGoal] = useState(restoredDraft.goal ?? "");
  const [templateId, setTemplateId] = useState(restoredDraft.templateId ?? "repeatability");
  const [mode, setMode] = useState<"manual" | "approval" | "auto">(restoredDraft.mode ?? "manual");
  const [sandbox, setSandbox] = useState(restoredDraft.sandbox ?? true);
  const [pauseBackground, setPauseBackground] = useState(restoredDraft.pauseBackground ?? true);
  const [plannerProviderId, setPlannerProviderId] = useState(restoredDraft.plannerProviderId ?? "");
  const [analysisProviderId, setAnalysisProviderId] = useState(restoredDraft.analysisProviderId ?? "");
  const [carrier, setCarrier] = useState(restoredDraft.carrier ?? "A");
  const [intensity, setIntensity] = useState(restoredDraft.intensity ?? 1);
  const [waitTicks, setWaitTicks] = useState(restoredDraft.waitTicks ?? 24);
  const [manualOp, setManualOp] = useState(restoredDraft.manualOp ?? "stimulus.send");
  const [snapshotLabel, setSnapshotLabel] = useState(restoredDraft.snapshotLabel ?? "experiment snapshot");
  const [historyKind, setHistoryKind] = useState(restoredDraft.historyKind ?? "events");
  const [historyLimit, setHistoryLimit] = useState(restoredDraft.historyLimit ?? 40);
  const [graphLimit, setGraphLimit] = useState(restoredDraft.graphLimit ?? 500);
  const [noteText, setNoteText] = useState(restoredDraft.noteText ?? "");
  const [draftPlan, setDraftPlan] = useState<PlanStep[]>(() => copy(restoredDraft.draftPlan ?? []));
  const [aiPrompt, setAiPrompt] = useState(restoredDraft.aiPrompt ?? "");
  const [analysisPrompt, setAnalysisPrompt] = useState(restoredDraft.analysisPrompt ?? "");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [operation, setOperation] = useState<ExperimentOperation | null>(null);
  const [planningOutput, setPlanningOutput] = useState("");
  const [providerRefreshMessage, setProviderRefreshMessage] = useState("");
  const autoModeInitialized = useRef(Boolean(restoredDraft.mode));
  const planningOutputRef = useRef<HTMLPreElement>(null);

  const loadRuns = useCallback(async () => {
    try {
      const value = await request<{ items: ExperimentRun[] }>("/api/experiments?limit=100");
      setRuns(value.items);
      setSelectedId((current) => {
        if (current && value.items.some((item) => item.id === current)) return current;
        const stored = readStorage(WORKBENCH_SELECTED_RUN_KEY);
        if (stored && value.items.some((item) => item.id === stored)) return stored;
        return value.items[0]?.id || "";
      });
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to load experiments"); }
  }, []);

  const loadMetadata = useCallback(async () => {
    try {
      const [commandData, providerData] = await Promise.all([
        request<ExperimentMetadata>("/api/experiments/commands"),
        request<{ items: Provider[] }>("/api/ai/providers"),
      ]);
      setCommands(commandData.commands);
      setTemplates(commandData.templates);
      setProviders(providerData.items);
      setBridge(commandData.bridge ?? null);
      setPlannerProviderId((current) => current || providerData.items[0]?.id || "");
      if (!autoModeInitialized.current) {
        setMode(commandData.bridge?.auto_run_default ? "auto" : "manual");
        autoModeInitialized.current = true;
      }
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to load experiment metadata"); }
  }, []);

  const loadRun = useCallback(async (id: string) => {
    if (!id) { setRun(null); return; }
    try {
      const value = await request<ExperimentRun>(`/api/experiments/${id}`);
      setRun(value);
      setDraftPlan(copy(value.plan ?? []));
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to load experiment"); }
  }, []);

  const selectedRunRevision = useMemo(
    () => runs.find((item) => item.id === selectedId)?.updated_at ?? 0,
    [runs, selectedId],
  );

  useEffect(() => { void loadRuns(); void loadMetadata(); }, [loadMetadata, loadRuns]);
  useEffect(() => { void loadRun(selectedId); }, [loadRun, selectedId, selectedRunRevision]);
  useEffect(() => {
    const refresh = window.setInterval(() => void loadRuns(), 3000);
    return () => window.clearInterval(refresh);
  }, [loadRuns]);
  useEffect(() => {
    writeStorage(WORKBENCH_SELECTED_RUN_KEY, selectedId);
  }, [selectedId]);
  useEffect(() => {
    const draft: WorkbenchDraft = {
      tab,
      title,
      goal,
      templateId,
      mode,
      sandbox,
      pauseBackground,
      plannerProviderId,
      analysisProviderId,
      carrier,
      intensity,
      waitTicks,
      manualOp,
      snapshotLabel,
      historyKind,
      historyLimit,
      graphLimit,
      noteText,
      draftPlan,
      aiPrompt,
      analysisPrompt,
    };
    writeStorage(WORKBENCH_DRAFT_KEY, JSON.stringify(draft));
  }, [
    aiPrompt,
    analysisPrompt,
    analysisProviderId,
    carrier,
    draftPlan,
    goal,
    graphLimit,
    historyKind,
    historyLimit,
    intensity,
    manualOp,
    mode,
    noteText,
    pauseBackground,
    plannerProviderId,
    sandbox,
    snapshotLabel,
    tab,
    templateId,
    title,
    waitTicks,
  ]);
  useEffect(() => {
    if (planningOutputRef.current) planningOutputRef.current.scrollTop = planningOutputRef.current.scrollHeight;
  }, [planningOutput]);

  const refreshProviders = async () => {
    setProviderRefreshMessage(locale === "en" ? "Refreshing providers…" : "正在刷新供应商…");
    try {
      const data = await request<{ items: Provider[] }>("/api/ai/providers");
      setProviders(data.items);
      setPlannerProviderId((current) => data.items.some((item) => item.id === current) ? current : data.items[0]?.id || "");
      setProviderRefreshMessage(data.items.length ? (locale === "en" ? `${data.items.length} provider(s) available.` : `已发现 ${data.items.length} 个可用供应商。`) : t.providerUnavailable);
    } catch (error) {
      setProviderRefreshMessage(error instanceof Error ? error.message : (locale === "en" ? "Unable to refresh providers." : "无法刷新供应商。"));
    }
  };

  const targetRuntimeId = run?.target.runtime_id ?? activeConsciousnessId;
  useEffect(() => {
    if (!targetRuntimeId || targetRuntimeId === "—") { setGraph(null); return; }
    let alive = true;
    let socket: WebSocket | null = null;
    let reconnect: number | undefined;
    let pendingSnapshot: Graph | null = null;
    const connect = () => {
      socket = new WebSocket(`${WS_API}/api/ws/consciousnesses/${encodeURIComponent(targetRuntimeId)}`);
      socket.onmessage = (event) => {
        if (!alive) return;
        const payload = JSON.parse(event.data) as { type?: string; sequence?: number; graph?: Graph; part?: "nodes" | "edges"; items?: GraphNode[] | GraphEdge[]; metrics?: Graph["metrics"]; delta?: Record<string, unknown>; nodes?: GraphNode[]; edges?: GraphEdge[]; detail?: string };
        const acknowledge = () => {
          if (socket?.readyState === WebSocket.OPEN && typeof payload.sequence === "number") socket.send(JSON.stringify({ type: "ack", sequence: payload.sequence }));
        };
        if (payload.type === "snapshot_begin" && payload.graph) {
          pendingSnapshot = { ...payload.graph, nodes: [], edges: [] };
          acknowledge();
          return;
        }
        if (payload.type === "snapshot_chunk" && pendingSnapshot) {
          if (payload.part === "nodes") pendingSnapshot.nodes.push(...((payload.items ?? []) as GraphNode[]));
          if (payload.part === "edges") pendingSnapshot.edges.push(...((payload.items ?? []) as GraphEdge[]));
          acknowledge();
          return;
        }
        if (payload.type === "snapshot_end" && pendingSnapshot) {
          setGraph(pendingSnapshot);
          pendingSnapshot = null;
          return;
        }
        if (payload.type === "delta" && payload.metrics && payload.delta) {
          const removedNodes = new Set<number>((payload.delta.removed_nodes as number[] | undefined) ?? []);
          const removedEdges = new Set<string>(((payload.delta.removed_edges as number[][] | undefined) ?? []).map(([source, target]) => `${source}:${target}`));
          setGraph((previous) => {
            if (!previous) return previous;
            const nodes = new Map(previous.nodes.map((node) => [node.id, node]));
            for (const node of payload.nodes ?? []) nodes.set(node.id, { ...nodes.get(node.id), ...node });
            for (const nodeId of removedNodes) nodes.delete(nodeId);
            const edges = new Map(previous.edges.map((edge) => [`${edge.source}:${edge.target}`, edge]));
            for (const edge of payload.edges ?? []) edges.set(`${edge.source}:${edge.target}`, { ...edges.get(`${edge.source}:${edge.target}`), ...edge });
            for (const edgeKey of removedEdges) edges.delete(edgeKey);
            return { ...previous, metrics: payload.metrics, nodes: [...nodes.values()], edges: [...edges.values()] };
          });
          acknowledge();
          return;
        }
        if (payload.type === "error") setMessage(payload.detail ?? (locale === "en" ? "Experiment stream error" : "实验图像流错误"));
      };
      socket.onerror = () => socket?.close();
      socket.onclose = () => {
        if (!alive) return;
        // The stream carries a high-volume graph projection. Reconnect with a
        // modest delay instead of falling back to repeated full REST graphs.
        reconnect = window.setTimeout(connect, 1800);
      };
    };
    connect();
    return () => { alive = false; socket?.close(); if (reconnect !== undefined) window.clearTimeout(reconnect); };
  }, [locale, targetRuntimeId]);

  const mutate = async (action: () => Promise<ExperimentRun | { path?: string } | void>, success = "") => {
    setBusy(true);
    setOperation(null);
    try {
      const value = await action();
      const refreshedId = value && "id" in value ? (value as ExperimentRun).id : selectedId;
      if (value && "id" in value) { setRun(value as ExperimentRun); setSelectedId(refreshedId); }
      if (success) setMessage(success);
      await loadRuns();
      // A report or analysis endpoint returns an artifact rather than the
      // whole run.  Reload the selected run so its evidence pane immediately
      // shows the persisted artifact / analysis instead of looking stale.
      if (refreshedId) await loadRun(refreshedId);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Operation failed"); }
    finally { setBusy(false); }
  };

  const createRun = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setOperation({ kind: "create", state: "active", stage: "validating", message: operationStageText(locale, "validating", t.creating) });
    const createdResult: { value: ExperimentRun | null } = { value: null };
    try {
      await readEventStream("/api/experiments/stream", {
        method: "POST",
        body: JSON.stringify({
          target_id: activeConsciousnessId,
          title,
          goal,
          template_id: templateId,
          mode,
          provider_id: plannerProviderId,
          sandbox,
          background_mode: pauseBackground ? "paused" : "preserve",
        }),
      }, ({ event: eventType, data }) => {
        if (eventType === "progress") {
          const stage = String(data.stage ?? "validating");
          setOperation({ kind: "create", state: "active", stage, message: operationStageText(locale, stage, String(data.message ?? t.creating)) });
          return;
        }
        if (eventType === "result" && data.run && typeof data.run === "object") {
          createdResult.value = data.run as ExperimentRun;
          return;
        }
        if (eventType === "error") throw new Error(String(data.detail ?? (locale === "en" ? "Unable to create experiment." : "无法创建实验。")));
      });
      const created = createdResult.value;
      if (!created) throw new Error(locale === "en" ? "Experiment creation stream ended without a run." : "实验创建流在返回运行记录前结束。" );
      setRun(created);
      setSelectedId(created.id);
      setMessage(locale === "en" ? "Experiment created." : "实验已创建。");
      setOperation({ kind: "create", state: "success", stage: "ready", message: operationStageText(locale, "ready", locale === "en" ? "Experiment created." : "实验已创建。") });
      await loadRuns();
      await loadRun(created.id);
    } catch (error) {
      const detail = error instanceof Error ? error.message : (locale === "en" ? "Unable to create experiment." : "无法创建实验。");
      setMessage(detail);
      setOperation({ kind: "create", state: "error", stage: "error", message: detail });
    } finally {
      setBusy(false);
    }
  };

  const savePlan = async (plan: PlanStep[], origin = "manual") => {
    if (!run) return;
    await mutate(() => request<ExperimentRun>(`/api/experiments/${run.id}/plan`, { method: "POST", body: JSON.stringify({ steps: plan, origin }) }), locale === "en" ? "Plan saved." : "计划已保存。");
  };

  const createTemplatePlan = async () => {
    if (!run) return;
    const query = new URLSearchParams({ carrier_a: carrier || "A", carrier_b: "B", intensity: String(intensity) });
    await mutate(() => request<ExperimentRun>(`/api/experiments/${run.id}/template-plan?${query.toString()}`, { method: "POST" }), locale === "en" ? "Template plan created." : "模板计划已生成。");
  };

  const addStep = (step: Omit<PlanStep, "id">) => setDraftPlan((previous) => [...previous, { ...step, id: planId(), status: "pending" }]);
  const removeStep = (id: string) => setDraftPlan((previous) => previous.filter((step) => step.id !== id));
  const addSelectedCommand = () => {
    const rationale = locale === "en" ? "Manual protocol command" : "人工协议命令";
    if (manualOp === "stimulus.send") addStep({ op: manualOp, args: { text: carrier, intensity }, rationale });
    else if (manualOp === "runtime.wait") addStep({ op: manualOp, args: { ticks: waitTicks }, rationale });
    else if (manualOp === "snapshot.capture") addStep({ op: manualOp, args: { label: snapshotLabel }, rationale });
    else if (manualOp === "history.tail") addStep({ op: manualOp, args: { kind: historyKind, limit: historyLimit }, rationale });
    else if (manualOp === "observe.graph") addStep({ op: manualOp, args: { limit: graphLimit }, rationale });
    else if (manualOp === "experiment.note") {
      if (!noteText.trim()) { setMessage(locale === "en" ? "A researcher note cannot be empty." : "研究者注记不能为空。"); return; }
      addStep({ op: manualOp, args: { text: noteText }, rationale });
    } else addStep({ op: manualOp, args: {}, rationale });
  };
  const executeStep = async (id: string) => { if (run) await mutate(() => request<ExperimentRun>(`/api/experiments/${run.id}/steps/${id}/execute`, { method: "POST" }), locale === "en" ? "Step executed." : "步骤已执行。"); };
  const startPlan = async () => {
    if (!run) return;
    const approved = run.mode !== "manual" ? window.confirm(locale === "en" ? "Execute the validated plan?" : "确认执行已校验的计划？") : true;
    if (!approved) return;
    await mutate(() => request<ExperimentRun>(`/api/experiments/${run.id}/run`, { method: "POST", body: JSON.stringify({ approved }) }), locale === "en" ? "Experiment started." : "实验已启动。");
  };
  const cancel = async () => { if (run) await mutate(() => request<ExperimentRun>(`/api/experiments/${run.id}/cancel`, { method: "POST" }), locale === "en" ? "Cancellation requested." : "已请求停止。"); };
  const generateAiPlan = async () => {
    if (!run || !plannerProviderId || busy) return;
    setBusy(true);
    setPlanningOutput("");
    setOperation({ kind: "planning", state: "active", stage: "preparing", message: operationStageText(locale, "preparing", t.planning) });
    const plannedResult: { value: ExperimentRun | null } = { value: null };
    try {
      await readEventStream(`/api/experiments/${run.id}/ai-plan/stream`, {
        method: "POST",
        body: JSON.stringify({ provider_id: plannerProviderId, goal: aiPrompt || goal, language: locale }),
      }, ({ event: eventType, data }) => {
        if (eventType === "status") {
          const stage = String(data.stage ?? "preparing");
          const renderedStage = stage === "validating" ? "ai_validating" : stage;
          setOperation({ kind: "planning", state: "active", stage: renderedStage, message: operationStageText(locale, renderedStage, String(data.message ?? t.planning)) });
          return;
        }
        if (eventType === "delta") {
          const text = typeof data.text === "string" ? data.text : "";
          if (text) setPlanningOutput((previous) => `${previous}${text}`);
          return;
        }
        if (eventType === "result" && data.run && typeof data.run === "object") {
          plannedResult.value = data.run as ExperimentRun;
          return;
        }
        if (eventType === "error") {
          if (typeof data.raw === "string") setPlanningOutput(data.raw);
          throw new Error(String(data.detail ?? (locale === "en" ? "Unable to generate AI plan." : "无法生成 AI 计划。")));
        }
      });
      const planned = plannedResult.value;
      if (!planned) throw new Error(locale === "en" ? "AI planning stream ended without a validated plan." : "AI 规划流在返回校验计划前结束。" );
      setRun(planned);
      setSelectedId(planned.id);
      setMessage(locale === "en" ? "AI plan generated and validated." : "AI 计划已生成并校验。");
      setOperation({ kind: "planning", state: "success", stage: "completed", message: operationStageText(locale, "completed", locale === "en" ? "AI plan generated and validated." : "AI 计划已生成并校验。") });
      await loadRuns();
      await loadRun(planned.id);
    } catch (error) {
      const detail = error instanceof Error ? error.message : (locale === "en" ? "Unable to generate AI plan." : "无法生成 AI 计划。");
      setMessage(detail);
      setOperation({ kind: "planning", state: "error", stage: "error", message: detail });
    } finally {
      setBusy(false);
    }
  };
  const analyze = async () => { if (run) await mutate(() => request<ExperimentRun>(`/api/experiments/${run.id}/analyze`, { method: "POST", body: JSON.stringify({ provider_id: analysisProviderId, language: locale, prompt: analysisPrompt }) }), locale === "en" ? "Analysis recorded." : "分析已记录。"); };
  const exportReport = async () => { if (run) await mutate(() => request<{ path?: string }>(`/api/experiments/${run.id}/report`, { method: "POST", body: JSON.stringify({ language: locale }) }), locale === "en" ? "Report exported to lab/ai-debug." : "报告已导出到 lab/ai-debug。"); };

  const latestAnalysis = run?.analysis?.at(-1)?.analysis;
  const currentPlan = run?.plan ?? draftPlan;
  const commandNames = useMemo(() => commands.map((command) => command.op).join(" · "), [commands]);
  const bridgeDisabled = bridge?.enabled === false;

  return <section className="experiment-workbench">
    <header className="experiment-header">
      <div><h1>{t.title}</h1><p>{t.subtitle}</p></div>
      <div className="experiment-run-select">
        <label htmlFor="experiment-run-select">{t.view}</label>
        <select id="experiment-run-select" value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
          <option value="">{t.selectRun}</option>
          {runs.map((item) => <option key={item.id} value={item.id}>{item.title} · {experimentStatusTitle(locale, item.status)}</option>)}
        </select>
        <button type="button" onClick={() => void loadRuns()}>{t.refresh}</button>
        <small>{t.runRecovery}</small>
      </div>
    </header>
    {message && <div className="management-message">{message}</div>}
    {operation && <section className={`experiment-operation ${operation.state}`} role="status" aria-live="polite">
      {operation.state === "active" && <span className="experiment-activity-spinner" aria-hidden="true" />}
      <div className="experiment-operation-body"><strong>{operation.kind === "create" ? (operation.state === "success" ? (locale === "en" ? "Isolated experiment created" : "隔离实验已创建") : t.creating) : (operation.state === "success" ? (locale === "en" ? "AI plan validated" : "AI 计划已校验") : t.planning)}</strong><p>{operation.message}</p><span className="experiment-operation-track" aria-hidden="true"><span style={{ width: `${operationProgress(operation)}%` }} /></span></div>
    </section>}
    <div className="experiment-grid">
      <aside className="experiment-protocol-panel">
        <form onSubmit={createRun} className="experiment-create-form">
          <h2>{t.create}</h2>
          <label>{t.titleField}<input value={title} onChange={(event) => setTitle(event.target.value)} placeholder={locale === "en" ? "e.g. carrier repeatability" : "例如：载体重复性"} /></label>
          <label>{t.goal}<textarea value={goal} onChange={(event) => setGoal(event.target.value)} placeholder={locale === "en" ? "State a testable question." : "写下可检验的问题。"} /></label>
          <label>{t.template}<select value={templateId} onChange={(event) => setTemplateId(event.target.value)}>{templates.map((item) => <option key={item.id} value={item.id}>{experimentTemplateTitle(locale, item)}</option>)}</select></label>
          <label>{t.mode}<select value={mode} onChange={(event) => setMode(event.target.value as typeof mode)}><option value="manual">{t.manualMode}</option><option value="approval">{t.approval}</option><option value="auto">{t.auto}</option></select></label>
          {mode === "auto" && <small className="experiment-mode-help">{t.autoHelp}</small>}
          <div className="experiment-field-group"><span>{t.planningProvider}</span><div className="experiment-provider-control"><select aria-label={t.planningProvider} value={plannerProviderId} onChange={(event) => setPlannerProviderId(event.target.value)}><option value="">{locale === "en" ? "No provider selected" : "暂不选择供应商"}</option>{providers.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.model ?? item.id}</option>)}</select><button type="button" onClick={() => void refreshProviders()} disabled={busy}>{t.refreshProviders}</button></div><small>{t.planningProviderHelp}</small></div>
          {!providers.length && <p className="experiment-help">{providerRefreshMessage || t.providerUnavailable}</p>}
          {providers.length > 0 && providerRefreshMessage && <p className="experiment-help">{providerRefreshMessage}</p>}
          <label className="experiment-checkbox"><input type="checkbox" checked={sandbox} onChange={(event) => setSandbox(event.target.checked)} />{t.sandbox}</label>
          <label className="experiment-checkbox"><input type="checkbox" checked={pauseBackground} disabled={!sandbox} onChange={(event) => setPauseBackground(event.target.checked)} />{t.background}</label>
          {bridgeDisabled && <p className="experiment-help error">{t.bridgeUnavailable}</p>}
          <button className="primary" disabled={busy || bridgeDisabled || !activeConsciousnessId || activeConsciousnessId === "—"}>{busy && operation?.kind === "create" ? t.creating : t.create}</button>
        </form>
        <section className="experiment-boundary"><h2>{t.commandBoundary}</h2><p>{commandNames || "…"}</p><small>{locale === "en" ? "No destructive archive, credential, filesystem, persistence, network, or arbitrary Core command is exposed here. Adjust the bridge's visible bounds in Adapter management → AI experiment/debug bridge." : "这里不会暴露删除存档、凭据、文件系统、持久化、网络配置或任意 Core 命令。可在上方「适配器管理 → AI 实验／调试桥」调整该桥的可见边界。"}</small></section>
      </aside>
      <section className="experiment-graph-panel">
        <header><div><h2>{t.graph}</h2><span>{run ? `${run.target.runtime_name ?? run.target.runtime_id} · ${run.target.sandbox ? (locale === "en" ? "sandbox" : "隔离沙箱") : (locale === "en" ? "direct target" : "直接目标")}` : t.target}</span></div><span>{graph?.metrics?.tick !== undefined ? `tick ${graph.metrics.tick}` : ""}</span></header>
        <div className="experiment-graph"><Suspense fallback={<div className="graph-loading">{locale === "en" ? "Loading graph…" : "正在载入图像…"}</div>}><GraphViewport graph={graph} mode="3d" shape="glow" style="organic" continuousMotion={false} /></Suspense></div>
      </section>
      <aside className="experiment-console-panel">
        {!run ? <div className="experiment-empty">{t.noRun}</div> : <>
          <nav className="experiment-tabs"><button className={tab === "manual" ? "active" : ""} type="button" onClick={() => setTab("manual")}>{t.manual}</button><button className={tab === "ai" ? "active" : ""} type="button" onClick={() => setTab("ai")}>{t.ai}</button></nav>
          {tab === "manual" ? <section className="experiment-console-section">
            <div className="experiment-command-composer">
              <label>{t.command}<select value={manualOp} onChange={(event) => setManualOp(event.target.value)}>{commands.map((command) => <option key={command.op} value={command.op}>{experimentCommandTitle(locale, command.op)}</option>)}</select></label>
              {manualOp === "stimulus.send" && <><label>{t.carrier}<textarea value={carrier} onChange={(event) => setCarrier(event.target.value)} /></label><label>{t.intensity}<input type="number" min="0" max="2" step=".05" value={intensity} onChange={(event) => setIntensity(Number(event.target.value))} /></label></>}
              {manualOp === "runtime.wait" && <label>{t.wait}<input type="number" min="1" value={waitTicks} onChange={(event) => setWaitTicks(Math.max(1, Number(event.target.value)))} /></label>}
              {manualOp === "snapshot.capture" && <label>{t.snapshotLabel}<input value={snapshotLabel} onChange={(event) => setSnapshotLabel(event.target.value)} /></label>}
              {manualOp === "history.tail" && <div className="experiment-step-controls"><label>{t.historyKind}<select value={historyKind} onChange={(event) => setHistoryKind(event.target.value)}>{["stimuli", "events", "observations", "interpretations", "trace"].map((kind) => <option key={kind} value={kind}>{historyKindTitle(locale, kind)}</option>)}</select></label><label>{t.historyLimit}<input type="number" min="1" max="500" value={historyLimit} onChange={(event) => setHistoryLimit(Math.max(1, Number(event.target.value)))} /></label></div>}
              {manualOp === "observe.graph" && <label>{t.graphLimit}<input type="number" min="1" max="5000" value={graphLimit} onChange={(event) => setGraphLimit(Math.max(1, Number(event.target.value)))} /></label>}
              {manualOp === "experiment.note" && <label>{t.note}<textarea value={noteText} onChange={(event) => setNoteText(event.target.value)} /></label>}
              <button type="button" onClick={addSelectedCommand}>{t.addCommand}</button>
            </div>
            <div className="experiment-plan-actions"><button type="button" onClick={() => void createTemplatePlan()} disabled={busy}>{t.buildTemplate}</button><button type="button" onClick={() => void savePlan(draftPlan)} disabled={busy}>{t.savePlan}</button></div>
          </section> : <section className="experiment-console-section">
            <label>{t.aiPrompt}<textarea value={aiPrompt} onChange={(event) => setAiPrompt(event.target.value)} placeholder={locale === "en" ? "For example: design a repeatability test with an explicit control." : "例如：设计包含明确对照的重复性检验。"} /></label>
            <div className="experiment-field-group"><span>{locale === "en" ? "Planning provider" : "计划供应商"}</span><div className="experiment-provider-control"><select aria-label={locale === "en" ? "Planning provider" : "计划供应商"} value={plannerProviderId} onChange={(event) => setPlannerProviderId(event.target.value)}><option value="">{locale === "en" ? "Select provider" : "选择供应商"}</option>{providers.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.model ?? item.id}</option>)}</select><button type="button" onClick={() => void refreshProviders()} disabled={busy}>{t.refreshProviders}</button></div></div>
            {!providers.length && <p className="experiment-help">{providerRefreshMessage || t.noProvider}</p>}
            <button className="primary" type="button" onClick={() => void generateAiPlan()} disabled={busy || !plannerProviderId}>{busy && operation?.kind === "planning" ? t.planning : t.generate}</button>
            {(operation?.kind === "planning" || planningOutput) && <section className="experiment-planning-stream"><header><div><h3>{t.plannerOutput}</h3><span>{operation?.kind === "planning" ? operation.message : (locale === "en" ? "Latest planning transcript" : "最近一次规划记录")}</span></div>{operation?.kind === "planning" && operation.state === "active" && <span className="experiment-activity-spinner" aria-hidden="true" />}</header><pre ref={planningOutputRef} aria-live="off">{planningOutput || t.waitingOutput}</pre></section>}
          </section>}
          <section className="experiment-plan-list"><header><h2>{t.planned}</h2><span>{experimentStatusTitle(locale, run.status)}</span></header>{currentPlan.length ? currentPlan.map((step, index) => <article key={step.id} className={`experiment-plan-step ${step.status ?? "pending"}`}><div><strong>{index + 1}. {experimentCommandTitle(locale, step.op)}</strong><small>{JSON.stringify(step.args)}</small>{step.rationale && <p>{step.rationale}</p>}</div><div className="experiment-plan-step-actions">{step.status !== "completed" && <button type="button" onClick={() => void executeStep(step.id)} disabled={busy}>{t.execute}</button>}{!run.plan?.length && <button type="button" onClick={() => removeStep(step.id)} disabled={busy}>{locale === "en" ? "Remove" : "移除"}</button>}</div></article>) : <p>{t.noPlan}</p>}</section>
          <div className="experiment-run-actions"><button className="primary" type="button" onClick={() => void startPlan()} disabled={busy || !run.plan?.length}>{t.run}</button><button type="button" onClick={() => void cancel()} disabled={busy || run.status !== "running"}>{t.stop}</button></div>
        </>}
      </aside>
    </div>
    {run && <section className="experiment-evidence-panel"><header><div><h2>{t.evidence}</h2><p>{t.reportNote}</p></div><div><label>{locale === "en" ? "Analysis provider" : "分析供应商"}<select value={analysisProviderId} onChange={(event) => setAnalysisProviderId(event.target.value)}><option value="">{locale === "en" ? "Deterministic only" : "仅确定性摘要"}</option>{providers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><button type="button" onClick={() => void analyze()} disabled={busy}>{t.analyze}</button><button type="button" onClick={() => void exportReport()} disabled={busy}>{t.export}</button></div></header>
      <label className="experiment-analysis-prompt">{t.analysisPrompt}<textarea value={analysisPrompt} onChange={(event) => setAnalysisPrompt(event.target.value)} placeholder={locale === "en" ? "For example: distinguish direct observation from inference and identify a null comparison." : "例如：区分直接观测与推断，并指出一个零假设对照。"} /></label>
      <div className="experiment-evidence-grid"><section><h3>{t.trace}</h3>{run.steps?.length ? run.steps.map((step, index) => <article key={`${step.id}-${index}`}><strong>{step.op}</strong><span>{step.status} · {step.duration_ms ?? 0}ms</span><pre>{JSON.stringify(step.result, null, 2)}</pre></article>) : <p>{t.noPlan}</p>}</section><section><h3>{t.aiAnalysis}</h3>{latestAnalysis ? <pre>{JSON.stringify(latestAnalysis, null, 2)}</pre> : <p>{locale === "en" ? "No analysis recorded yet." : "尚未记录分析。"}</p>}{run.report?.path && <p className="experiment-report-path">{run.report.path}</p>}</section></div>
    </section>}
  </section>;
}

export function ExperimentRecordsPage({
  locale,
  onOpenWorkbench,
}: {
  locale: Locale;
  onOpenWorkbench: (runId: string) => void;
}) {
  const [items, setItems] = useState<ExperimentRun[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [mode, setMode] = useState("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [details, setDetails] = useState<ExperimentRun | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setMessage("");
    try {
      const result = await request<{ items: ExperimentRun[] }>("/api/experiments?limit=1000");
      setItems(result.items ?? []);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : (locale === "en" ? "Unable to load experiment records." : "无法读取实验记录。"));
    } finally {
      setLoading(false);
    }
  }, [locale]);

  useEffect(() => { void load(); }, [load]);
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return items.filter((item) => {
      if (status !== "all" && item.status !== status) return false;
      if (mode !== "all" && item.mode !== mode) return false;
      if (!needle) return true;
      return `${item.title} ${item.id} ${item.goal ?? ""} ${item.target?.runtime_name ?? ""} ${item.target?.runtime_id ?? ""}`.toLocaleLowerCase().includes(needle);
    });
  }, [items, mode, query, status]);
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pages);
  const rows = filtered.slice((safePage - 1) * pageSize, safePage * pageSize);

  const openDetails = async (id: string) => {
    setMessage("");
    try {
      setDetails(await request<ExperimentRun>(`/api/experiments/${encodeURIComponent(id)}`));
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : (locale === "en" ? "Unable to load experiment details." : "无法读取实验详情。"));
    }
  };

  const openWorkbench = (id: string) => {
    rememberExperimentRun(id);
    onOpenWorkbench(id);
  };

  return <section className="management-page experiment-records-page">
    <header className="management-header"><div><h2>{locale === "en" ? "Experiment records" : "实验记录"}</h2><p>{locale === "en" ? "Persistent protocols, execution state, evidence, analyses and exported reports." : "集中查看持久化的实验协议、执行状态、证据、分析与报告。"}</p></div><div className="page-actions"><button type="button" onClick={() => void load()} disabled={loading}>{locale === "en" ? "Refresh" : "刷新"}</button><button className="primary" type="button" onClick={() => onOpenWorkbench("")}>{locale === "en" ? "Open workbench" : "打开实验工作台"}</button></div></header>
    <div className="record-filters experiment-record-filters">
      <input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder={locale === "en" ? "Search title, ID, goal or target" : "按名称、ID、研究问题或目标意识筛选"} />
      <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}><option value="all">{locale === "en" ? "All statuses" : "全部状态"}</option>{["draft", "planned", "awaiting_approval", "running", "completed", "failed", "cancelled", "stopped"].map((value) => <option key={value} value={value}>{experimentStatusTitle(locale, value)}</option>)}</select>
      <select value={mode} onChange={(event) => { setMode(event.target.value); setPage(1); }}><option value="all">{locale === "en" ? "All modes" : "全部模式"}</option><option value="manual">{locale === "en" ? "Manual" : "人工逐步"}</option><option value="approval">{locale === "en" ? "Approval" : "确认后执行"}</option><option value="auto">{locale === "en" ? "Bounded auto" : "受限自动"}</option></select>
      <button type="button" onClick={() => { setQuery(""); setStatus("all"); setMode("all"); setPage(1); }}>{locale === "en" ? "Reset" : "重置"}</button>
    </div>
    {message && <div className="management-message">{message}</div>}
    {loading ? <div className="management-message is-pending"><span className="ui-spinner" aria-hidden="true" />{locale === "en" ? "Loading experiment records…" : "正在读取实验记录…"}</div> : <div className="record-table-wrap">
      <table className="record-table experiment-record-table"><thead><tr><th>{locale === "en" ? "Experiment" : "实验"}</th><th>{locale === "en" ? "Status / mode" : "状态 / 模式"}</th><th>{locale === "en" ? "Target" : "目标意识"}</th><th>{locale === "en" ? "Protocol" : "协议"}</th><th>{locale === "en" ? "Updated" : "更新时间"}</th><th>{locale === "en" ? "Actions" : "操作"}</th></tr></thead>
        <tbody>{rows.map((item) => <tr key={item.id}>
          <td><strong>{item.title || (locale === "en" ? "Untitled experiment" : "未命名实验")}</strong><small>{item.id}</small>{item.goal && <small>{item.goal}</small>}</td>
          <td><span className={`state-badge state-${item.status}`}>{experimentStatusTitle(locale, item.status)}</span><small>{item.mode === "manual" ? (locale === "en" ? "Manual" : "人工逐步") : item.mode === "approval" ? (locale === "en" ? "Approval" : "确认后执行") : (locale === "en" ? "Bounded auto" : "受限自动")}</small></td>
          <td>{item.target?.runtime_name ?? item.target?.runtime_id ?? "—"}<small>{item.target?.sandbox ? (locale === "en" ? "Isolated sandbox" : "隔离沙箱") : (locale === "en" ? "Direct target" : "直接目标")}</small></td>
          <td>{item.steps?.length ?? item.plan?.length ?? 0} {locale === "en" ? "steps" : "步"}<small>{item.analysis?.length ?? 0} {locale === "en" ? "analyses" : "份分析"} · {item.report?.path ? (locale === "en" ? "report exported" : "已导出报告") : (locale === "en" ? "no report" : "无报告")}</small></td>
          <td>{item.updated_at ? new Date(item.updated_at * 1000).toLocaleString() : "—"}<small>{item.created_at ? `${locale === "en" ? "Created" : "创建"} ${new Date(item.created_at * 1000).toLocaleString()}` : ""}</small></td>
          <td><div className="table-actions"><button type="button" onClick={() => void openDetails(item.id)}>{locale === "en" ? "Details" : "详情"}</button><button className="primary" type="button" onClick={() => openWorkbench(item.id)}>{locale === "en" ? "Open workbench" : "打开工作台"}</button></div></td>
        </tr>)}</tbody>
      </table>
      {!rows.length && <div className="empty-state"><strong>{locale === "en" ? "No matching experiment records" : "没有符合条件的实验记录"}</strong><span>{locale === "en" ? "Create an experiment in the workbench; its state will be stored by Core." : "可在实验工作台创建实验；运行状态会由 Core 持久化。"}</span></div>}
    </div>}
    <div className="record-pagination"><span>{locale === "en" ? `${filtered.length} records · page ${safePage} / ${pages}` : `共 ${filtered.length} 条 · 第 ${safePage} / ${pages} 页`}</span><label>{locale === "en" ? "Per page" : "每页"} <select value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }}><option value="10">10</option><option value="20">20</option><option value="50">50</option></select></label><button type="button" disabled={safePage <= 1} onClick={() => setPage(safePage - 1)}>{locale === "en" ? "Previous" : "上一页"}</button><button type="button" disabled={safePage >= pages} onClick={() => setPage(safePage + 1)}>{locale === "en" ? "Next" : "下一页"}</button></div>
    {details && <div className="settings-backdrop" onMouseDown={() => setDetails(null)}><section className="archive-modal experiment-record-detail" onMouseDown={(event) => event.stopPropagation()}><header className="settings-header"><div><strong>{details.title}</strong><span>{details.id} · {experimentStatusTitle(locale, details.status)}</span></div><button type="button" onClick={() => setDetails(null)}>×</button></header><div className="detail-summary"><span>{locale === "en" ? "Target" : "目标"}<b>{details.target?.runtime_name ?? details.target?.runtime_id ?? "—"}</b></span><span>{locale === "en" ? "Mode" : "模式"}<b>{details.mode}</b></span><span>{locale === "en" ? "Steps" : "步骤"}<b>{details.steps?.length ?? details.plan?.length ?? 0}</b></span><span>{locale === "en" ? "Analyses" : "分析"}<b>{details.analysis?.length ?? 0}</b></span></div><h3>{locale === "en" ? "Research question / hypothesis" : "研究问题 / 假设"}</h3><p>{details.goal || "—"}</p><h3>{locale === "en" ? "Execution trace" : "执行轨迹"}</h3><div className="experiment-record-step-list">{(details.steps ?? details.plan ?? []).map((step, index) => <article key={`${step.id}-${index}`}><strong>{index + 1}. {experimentCommandTitle(locale, step.op)}</strong><span>{step.status ?? "pending"} · {step.duration_ms ?? 0}ms</span><pre>{JSON.stringify(step.result ?? step.args, null, 2)}</pre></article>)}</div><div className="actions"><button className="primary" type="button" onClick={() => openWorkbench(details.id)}>{locale === "en" ? "Open in workbench" : "在工作台中打开"}</button><button type="button" onClick={() => setDetails(null)}>{locale === "en" ? "Close" : "关闭"}</button></div></section></div>}
  </section>;
}
