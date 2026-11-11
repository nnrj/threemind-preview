import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Locale } from "./i18n";
import { GraphProjectionStore, type GraphData } from "./graphProjectionStore";
import ThreeJsonGraphViewport from "./ThreeJsonGraphViewport";

const API = (import.meta.env.VITE_THREEMIND_API as string | undefined)?.replace(/\/$/, "") ?? "";

type ConsciousnessRow = { id: string; name?: string; status?: string; life_state?: string; tick?: number; active?: boolean };
type Overview = {
  origin: string;
  metrics: Record<string, unknown>;
  counts: Record<string, number>;
  stimulus_sources: Record<string, number>;
  trace: { available: boolean; starts_with_keyframe: boolean; first_tick?: number | null; last_tick?: number | null };
};
type DynamicsPoint = Record<string, number | null> & { tick: number };
type StructureRow = {
  structure_id: string;
  identity_quality: string;
  topology_class_id: string;
  first_tick: number;
  last_tick: number;
  occurrences: number;
  repeatable_alerts: number;
  node_ids: number[];
  node_count: number;
  internal_edges: number;
  mean_activation: number;
  source_counts: Record<string, number>;
  source_proportions: Record<string, number>;
  labels: string[];
  latest_subgraph: { tick?: number; nodes?: Array<Record<string, unknown>>; edges?: Array<Record<string, unknown>> };
  latest_event?: { label_entries?: Array<{ node_id: number; label: string }> };
};
type TemporalRow = {
  id: string;
  start_tick: number;
  end_tick: number;
  classification: string;
  source_provenance?: string[];
  node_ids?: number[];
  display_readout?: string;
  anonymous_readout?: string;
  convergence?: Record<string, number>;
  rankings?: Array<{ node_id: number; score: number; active_ticks: number; excess_activation_integral: number }>;
};
type NodeDynamicsPoint = { tick: number; node_id: number; present: boolean; activation: number; inhibition: number; support: number };
type PairRow = { id: string; title: string; mode: string; status: string; source_consciousness_id: string; control_runtime_id: string; intervention_runtime_id: string; updated_at?: number };
type Tab = "overview" | "dynamics" | "structures" | "convergence" | "ablation";

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { ...init, headers: { "content-type": "application/json", ...(init?.headers ?? {}) } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(String(payload.detail ?? payload.error ?? response.statusText));
  return payload as T;
}

function formatNumber(value: unknown, digits = 3): string {
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: digits }) : "—";
}

function LineChart({ rows, fields, locale }: { rows: DynamicsPoint[]; fields: Array<{ key: string; label: string; color: string }>; locale: Locale }) {
  const width = 900, height = 260, pad = 34;
  const values = rows.flatMap((row) => fields.map((field) => Number(row[field.key])).filter(Number.isFinite));
  const minimum = Math.min(0, ...values), maximum = Math.max(1e-9, ...values);
  const first = rows[0]?.tick ?? 0, last = rows.at(-1)?.tick ?? first + 1;
  const x = (tick: number) => pad + ((tick - first) / Math.max(1, last - first)) * (width - pad * 2);
  const y = (value: number) => height - pad - ((value - minimum) / Math.max(1e-9, maximum - minimum)) * (height - pad * 2);
  return <div className="evidence-chart-shell">
    {!rows.length ? <div className="evidence-empty">{locale === "en" ? "No detailed dynamics trace has been recorded." : "尚未记录详细动力学追踪。"}</div> : <>
      <svg className="evidence-line-chart" viewBox={`0 0 ${width} ${height}`} role="img">
        <path d={`M${pad} ${pad}V${height - pad}H${width - pad}`} className="evidence-axis"/>
        {[0, .25, .5, .75, 1].map((ratio) => <line key={ratio} x1={pad} x2={width - pad} y1={pad + ratio * (height - pad * 2)} y2={pad + ratio * (height - pad * 2)} className="evidence-grid-line"/>)}
        {fields.map((field) => <polyline key={field.key} fill="none" stroke={field.color} strokeWidth="2" vectorEffect="non-scaling-stroke" points={rows.map((row) => `${x(row.tick)},${y(Number(row[field.key] ?? 0))}`).join(" ")}/>) }
      </svg>
      <div className="evidence-chart-legend">{fields.map((field) => <span key={field.key}><i style={{ background: field.color }}/>{field.label}</span>)}</div>
    </>}
  </div>;
}

function SourceBars({ values, locale }: { values: Record<string, number>; locale: Locale }) {
  const total = Object.values(values).reduce((sum, value) => sum + value, 0) || 1;
  const rows = Object.entries(values).sort((a, b) => b[1] - a[1]);
  return <div className="evidence-source-bars">{rows.length ? rows.map(([source, value]) => <div key={source}>
    <span>{source}</span><div><i style={{ width: `${(value / total) * 100}%` }}/></div><strong>{value} · {formatNumber(value / total * 100, 1)}%</strong>
  </div>) : <div className="evidence-empty">{locale === "en" ? "No source evidence" : "暂无来源证据"}</div>}</div>;
}

function frozenGraph(row: StructureRow): GraphData {
  const labels = new Map((row.latest_event?.label_entries ?? []).map((entry) => [Number(entry.node_id), String(entry.label)]));
  const nodes = (row.latest_subgraph?.nodes ?? []).map((raw) => ({
    id: Number(raw.id), feature: labels.get(Number(raw.id)) ?? "", activation: Number(raw.activation ?? 0), inhibition: Number(raw.inhibition ?? 0),
    stability: Number(raw.stability ?? 0), touch_count: Number(raw.touch_count ?? 0), direct: Number(raw.direct_touch ?? 0), associative: Number(raw.associative_touch ?? 0),
    source: "anonymous", position: Array.isArray(raw.position) ? raw.position.map(Number) : null,
  }));
  const edges = (row.latest_subgraph?.edges ?? []).map((raw) => ({ source: Number(raw.source), target: Number(raw.target), weight: Number(raw.weight ?? 0), stability: Number(raw.stability ?? 0), touched: false }));
  return {
    metrics: { id: row.structure_id, name: row.structure_id, tick: Number(row.latest_subgraph?.tick ?? row.last_tick), life_state: "frozen-evidence", node_count: nodes.length, edge_count: edges.length, active_nodes: nodes.filter((node) => node.activation > 0).length, total_activation: nodes.reduce((sum, node) => sum + node.activation, 0), mean_stability: nodes.length ? nodes.reduce((sum, node) => sum + node.stability, 0) / nodes.length : 0 },
    nodes, edges, neighbors: [],
  };
}

function StructureInspector({ row, locale, onClose }: { row: StructureRow; locale: Locale; onClose: () => void }) {
  const store = useRef(new GraphProjectionStore()).current;
  useEffect(() => { store.replace(frozenGraph(row)); }, [row, store]);
  const labelMap = new Map((row.latest_event?.label_entries ?? []).map((entry) => [entry.node_id, entry.label]));
  return <div className="evidence-inspector-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="evidence-inspector" role="dialog" aria-modal="true">
      <header><div><strong>{locale === "en" ? "Frozen repeatable structure" : "重复结构冻结证据"}</strong><small>{row.structure_id}</small></div><button onClick={onClose}>×</button></header>
      <div className="evidence-inspector-grid">
        <div className="evidence-subgraph"><ThreeJsonGraphViewport store={store} mode="3d" shape="glow" style="organic" continuousMotion={false}/></div>
        <aside>
          <dl><div><dt>{locale === "en" ? "Identity quality" : "身份质量"}</dt><dd>{row.identity_quality}</dd></div><div><dt>{locale === "en" ? "Occurrences" : "出现次数"}</dt><dd>{row.occurrences}</dd></div><div><dt>{locale === "en" ? "Tick range" : "Tick 区间"}</dt><dd>{row.first_tick}–{row.last_tick}</dd></div><div><dt>{locale === "en" ? "Topology class" : "拓扑类别"}</dt><dd>{row.topology_class_id || "—"}</dd></div></dl>
          <h4>{locale === "en" ? "Node annotations (external)" : "节点标注（外部注释）"}</h4>
          <div className="evidence-node-list">{row.node_ids.map((id) => <span key={id}><b>{labelMap.get(id) || `#${id}`}</b><small>node {id}</small></span>)}</div>
          <p>{locale === "en" ? "Labels are an observation aid and never participate in graph dynamics." : "标签仅用于观察，不参与意识网络动力学。"}</p>
        </aside>
      </div>
    </section>
  </div>;
}

function TemporalInspector({ row, nodeSeries, loading, locale, onClose }: { row: TemporalRow; nodeSeries: NodeDynamicsPoint[]; loading: boolean; locale: Locale; onClose: () => void }) {
  const nodeIds = (row.rankings ?? []).slice(0, 6).map((entry) => entry.node_id);
  const palette = ["#68d8c9", "#f0a65a", "#86a8ff", "#e397d2", "#a5dc86", "#f1778e"];
  const ticks = new Map<number, DynamicsPoint>();
  for (const sample of nodeSeries) {
    const point = ticks.get(sample.tick) ?? { tick: sample.tick };
    point[`node_${sample.node_id}`] = sample.activation;
    ticks.set(sample.tick, point);
  }
  const rows = [...ticks.values()].sort((a, b) => a.tick - b.tick);
  return <div className="evidence-inspector-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="evidence-inspector temporal-inspector" role="dialog" aria-modal="true">
      <header><div><strong>{locale === "en" ? "Temporal response evidence" : "时间区间响应证据"}</strong><small>{row.id} · {row.classification} · tick {row.start_tick}–{row.end_tick}</small></div><button onClick={onClose}>×</button></header>
      <div className="temporal-inspector-body">
        <p>{locale === "en" ? "Per-node activation is reconstructed only from recorded dynamics frames. Missing trace is shown as missing evidence, never inferred from the final snapshot." : "单节点激活仅从已记录的动力学帧重建；缺失追踪会显示为证据缺失，绝不会依据最终快照反推。"}</p>
        {loading ? <div className="evidence-empty">{locale === "en" ? "Loading recorded node traces…" : "正在载入已记录的节点时序…"}</div> : <LineChart rows={rows} locale={locale} fields={nodeIds.map((nodeId, index) => ({ key: `node_${nodeId}`, label: `node ${nodeId}`, color: palette[index % palette.length] }))}/>} 
        <div className="temporal-node-metrics">{(row.rankings ?? []).slice(0, 12).map((node) => <div key={node.node_id}><strong>node {node.node_id}</strong><span>{locale === "en" ? "score" : "得分"} {formatNumber(node.score, 5)}</span><span>{locale === "en" ? "active" : "激活持续"} {node.active_ticks} tick</span><span>∫Δa {formatNumber(node.excess_activation_integral, 5)}</span></div>)}</div>
      </div>
    </section>
  </div>;
}

export function StatisticsEvidencePage({ locale, activeConsciousnessId }: { locale: Locale; activeConsciousnessId: string }) {
  const [tab, setTab] = useState<Tab>("overview");
  const [consciousnesses, setConsciousnesses] = useState<ConsciousnessRow[]>([]);
  const [selectedId, setSelectedId] = useState(activeConsciousnessId);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [dynamics, setDynamics] = useState<DynamicsPoint[]>([]);
  const [structures, setStructures] = useState<StructureRow[]>([]);
  const [temporal, setTemporal] = useState<TemporalRow[]>([]);
  const [pairs, setPairs] = useState<PairRow[]>([]);
  const [selectedStructure, setSelectedStructure] = useState<StructureRow | null>(null);
  const [selectedTemporal, setSelectedTemporal] = useState<TemporalRow | null>(null);
  const [temporalNodeSeries, setTemporalNodeSeries] = useState<NodeDynamicsPoint[]>([]);
  const [temporalTraceLoading, setTemporalTraceLoading] = useState(false);
  const [ablationStructure, setAblationStructure] = useState("");
  const [ablationMode, setAblationMode] = useState<"silence" | "remove">("silence");
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [pairedProbe, setPairedProbe] = useState("");
  const [pairedProbeIntensity, setPairedProbeIntensity] = useState(1);
  const [pairedStepTicks, setPairedStepTicks] = useState(20);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadConsciousnesses = useCallback(async () => {
    const payload = await jsonRequest<{ active_id?: string; items: ConsciousnessRow[] }>("/api/consciousnesses");
    setConsciousnesses(payload.items);
    setSelectedId((value) => value || activeConsciousnessId || payload.active_id || payload.items[0]?.id || "");
  }, [activeConsciousnessId]);
  const loadEvidence = useCallback(async (id: string) => {
    if (!id) return;
    setBusy(true); setError("");
    try {
      const [summary, series, catalog, convergence, pairRows] = await Promise.all([
        jsonRequest<Overview>(`/api/analytics/consciousnesses/${id}/overview`),
        jsonRequest<{ series: DynamicsPoint[] }>(`/api/analytics/consciousnesses/${id}/dynamics?max_points=1600`),
        jsonRequest<{ items: StructureRow[] }>(`/api/analytics/consciousnesses/${id}/structures?page_size=500`),
        jsonRequest<{ items: TemporalRow[] }>(`/api/analytics/consciousnesses/${id}/convergence`),
        jsonRequest<{ items: PairRow[] }>("/api/interventions/pairs"),
      ]);
      setOverview(summary); setDynamics(series.series); setStructures(catalog.items); setTemporal(convergence.items); setPairs(pairRows.items);
      setAblationStructure((value) => value || catalog.items[0]?.structure_id || "");
    } catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); }
    finally { setBusy(false); }
  }, []);
  useEffect(() => { void loadConsciousnesses().catch((caught) => setError(String(caught))); }, [loadConsciousnesses]);
  useEffect(() => { if (selectedId) void loadEvidence(selectedId); }, [selectedId, loadEvidence]);
  useEffect(() => { if (activeConsciousnessId) setSelectedId(activeConsciousnessId); }, [activeConsciousnessId]);

  const chosenStructure = useMemo(() => structures.find((row) => row.structure_id === ablationStructure) ?? null, [structures, ablationStructure]);
  const createPair = async () => {
    if (!chosenStructure || (ablationMode === "remove" && !confirmRemove)) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const edges = (chosenStructure.latest_subgraph?.edges ?? []).map((edge) => [Number(edge.source), Number(edge.target)]);
      await jsonRequest("/api/interventions/pairs", { method: "POST", body: JSON.stringify({ target_id: selectedId, title: `${chosenStructure.structure_id} paired ablation`, mode: ablationMode, node_ids: chosenStructure.node_ids, edge_pairs: edges, background_mode: "paused" }) });
      setNotice(locale === "en" ? "Paired control and intervention sandboxes created in paused state." : "已创建暂停状态的对照组与干预组隔离沙箱。 ");
      setPairs((await jsonRequest<{ items: PairRow[] }>("/api/interventions/pairs")).items); setConfirmRemove(false);
    } catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); }
    finally { setBusy(false); }
  };
  const pairControl = async (id: string, action: "pause" | "resume" | "step") => {
    setBusy(true); setError("");
    try { await jsonRequest(`/api/interventions/pairs/${id}/control`, { method: "POST", body: JSON.stringify({ action, ticks: pairedStepTicks }) }); setPairs((await jsonRequest<{ items: PairRow[] }>("/api/interventions/pairs")).items); }
    catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); }
    finally { setBusy(false); }
  };
  const stimulatePair = async (id: string) => {
    if (!pairedProbe.trim()) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await jsonRequest(`/api/interventions/pairs/${id}/stimulus`, { method: "POST", body: JSON.stringify({ text: pairedProbe, intensity: pairedProbeIntensity }) });
      setNotice(locale === "en" ? "The same ordered probe was queued for both paired isolates." : "同一有序探针已进入两个配对隔离体的输入队列。");
      setPairedProbe("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); }
    finally { setBusy(false); }
  };
  const inspectTemporal = async (row: TemporalRow) => {
    setSelectedTemporal(row); setTemporalNodeSeries([]); setTemporalTraceLoading(true); setError("");
    const nodeIds = (row.rankings ?? []).slice(0, 6).map((entry) => entry.node_id);
    try {
      const query = new URLSearchParams({ from_tick: String(row.start_tick), to_tick: String(row.end_tick), max_points: "800", node_ids: nodeIds.join(",") });
      const payload = await jsonRequest<{ node_series: NodeDynamicsPoint[] }>(`/api/analytics/consciousnesses/${selectedId}/dynamics?${query}`);
      setTemporalNodeSeries(payload.node_series);
    } catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); }
    finally { setTemporalTraceLoading(false); }
  };
  const visiblePairs = pairs.filter((pair) => pair.source_consciousness_id === selectedId);

  const tabs: Array<[Tab, string]> = locale === "en" ? [["overview", "Overview"], ["dynamics", "Dynamics"], ["structures", "Repeatable structures"], ["convergence", "Temporal convergence"], ["ablation", "Ablation"]] : [["overview", "总览"], ["dynamics", "动力学"], ["structures", "重复结构"], ["convergence", "时间收敛"], ["ablation", "消融实验"]];
  return <section className="evidence-page">
    <header className="evidence-page-header"><div><h1>{locale === "en" ? "Statistics & Evidence" : "统计与证据"}</h1><p>{locale === "en" ? "Read-only measurements, frozen structural evidence, reproducible exports and isolated paired interventions." : "只读测量、冻结结构证据、可复现数据导出与隔离配对干预。"}</p></div><div className="evidence-header-actions"><select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>{consciousnesses.map((row) => <option value={row.id} key={row.id}>{row.name || row.id} · {row.id.slice(0, 8)}</option>)}</select><a className={!selectedId ? "is-disabled" : ""} href={selectedId ? `${API}/api/analytics/consciousnesses/${selectedId}/export` : undefined}>{locale === "en" ? "Export evidence ZIP" : "导出证据数据包"}</a><button disabled={busy || !selectedId} onClick={() => void loadEvidence(selectedId)}>{busy ? (locale === "en" ? "Loading…" : "载入中…") : (locale === "en" ? "Refresh" : "刷新")}</button></div></header>
    {error && <div className="evidence-feedback error">{error}</div>}{notice && <div className="evidence-feedback success">{notice}</div>}
    <nav className="evidence-tabs">{tabs.map(([key, label]) => <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>{label}</button>)}</nav>
    {tab === "overview" && <div className="evidence-overview">
      <div className="evidence-kpis">{Object.entries(overview?.counts ?? {}).map(([key, value]) => <article key={key}><strong>{formatNumber(value, 0)}</strong><span>{key.replaceAll("_", " ")}</span></article>)}</div>
      <div className="evidence-card-grid"><article className="evidence-card"><h2>{locale === "en" ? "Stimulus provenance" : "刺激来源构成"}</h2><SourceBars values={overview?.stimulus_sources ?? {}} locale={locale}/></article><article className="evidence-card"><h2>{locale === "en" ? "Measurement status" : "测量状态"}</h2><dl className="evidence-dl"><div><dt>{locale === "en" ? "History origin" : "历史来源"}</dt><dd>{overview?.origin ?? "—"}</dd></div><div><dt>{locale === "en" ? "Detailed trace" : "详细追踪"}</dt><dd>{overview?.trace.available ? (locale === "en" ? "Available" : "可用") : (locale === "en" ? "Not recorded" : "未记录")}</dd></div><div><dt>{locale === "en" ? "Trace range" : "追踪范围"}</dt><dd>{overview?.trace.first_tick ?? "—"} – {overview?.trace.last_tick ?? "—"}</dd></div></dl><p>{locale === "en" ? "A missing trace is reported as missing evidence, not silently converted into zero activity." : "缺少追踪会明确标记为证据缺失，不会被静默解释成零活动。"}</p></article></div>
    </div>}
    {tab === "dynamics" && <div className="evidence-stack"><article className="evidence-card"><h2>{locale === "en" ? "Activation and inhibition through time" : "激活与抑制时序"}</h2><LineChart locale={locale} rows={dynamics} fields={[{ key: "total_activation", label: locale === "en" ? "Activation" : "总激活", color: "#68d8c9" }, { key: "total_inhibition", label: locale === "en" ? "Inhibition" : "总抑制", color: "#f0a65a" }]}/></article><article className="evidence-card"><h2>{locale === "en" ? "Topology change through time" : "拓扑变化时序"}</h2><LineChart locale={locale} rows={dynamics} fields={[{ key: "node_count", label: locale === "en" ? "Nodes" : "节点", color: "#86a8ff" }, { key: "edge_count", label: locale === "en" ? "Edges" : "连接", color: "#e397d2" }]}/></article></div>}
    {tab === "structures" && <article className="evidence-card evidence-table-card"><header><div><h2>{locale === "en" ? "Repeatable structure catalogue" : "重复结构目录"}</h2><p>{locale === "en" ? "Exact identity, topology class and instantaneous state are deliberately separated." : "精确结构身份、拓扑类别与瞬时状态被刻意分离统计。"}</p></div></header><div className="evidence-table-wrap"><table><thead><tr><th>{locale === "en" ? "Structure" : "结构"}</th><th>{locale === "en" ? "Occurrences" : "次数"}</th><th>{locale === "en" ? "Ticks" : "Tick 区间"}</th><th>{locale === "en" ? "Nodes / edges" : "节点 / 边"}</th><th>{locale === "en" ? "Sources" : "来源"}</th><th/></tr></thead><tbody>{structures.map((row) => <tr key={row.structure_id}><td><strong>{row.labels.join(" · ") || row.structure_id}</strong><small>{row.structure_id} · {row.identity_quality}</small></td><td>{row.occurrences}<small>{row.repeatable_alerts} alerts</small></td><td>{row.first_tick}–{row.last_tick}</td><td>{row.node_count} / {row.internal_edges}</td><td>{Object.entries(row.source_counts).map(([key, value]) => `${key}:${value}`).join(" · ") || "—"}</td><td><button onClick={() => setSelectedStructure(row)}>{locale === "en" ? "Inspect" : "查看"}</button></td></tr>)}</tbody></table>{!structures.length && <div className="evidence-empty">{locale === "en" ? "No frozen repeatable structures have been recorded." : "尚未记录可冻结查看的重复结构。"}</div>}</div></article>}
    {tab === "convergence" && <div className="evidence-stack">{temporal.map((row) => <article className="evidence-card temporal-evidence" key={row.id}><header><div><h2>{row.display_readout || row.anonymous_readout || row.id}</h2><small>{row.classification} · tick {row.start_tick}–{row.end_tick}</small></div><span>{row.source_provenance?.join(" · ") || "unknown"}</span></header><div className="temporal-ranking-bars">{(row.rankings ?? []).slice(0, 12).map((node) => <div key={node.node_id}><span>node {node.node_id}</span><i><b style={{ width: `${Math.max(2, Math.min(100, node.score * 100))}%` }}/></i><strong>{formatNumber(node.score, 4)} · {node.active_ticks}t</strong></div>)}</div><button className="temporal-trace-button" onClick={() => void inspectTemporal(row)}>{locale === "en" ? "Inspect per-node trace" : "查看单节点时序"}</button></article>)}{!temporal.length && <div className="evidence-empty">{locale === "en" ? "No completed temporal response windows." : "尚无已完成的时间区间响应。"}</div>}</div>}
    {tab === "ablation" && <div className="evidence-ablation-grid"><article className="evidence-card"><h2>{locale === "en" ? "Create paired isolated intervention" : "创建配对隔离干预"}</h2><p>{locale === "en" ? "The source is captured once, then cloned into a control and intervention sandbox. Both start paused." : "源意识只捕获一次，随后克隆为对照组与干预组；两者均以暂停状态创建。"}</p><label>{locale === "en" ? "Frozen structure" : "冻结结构"}<select value={ablationStructure} onChange={(event) => setAblationStructure(event.target.value)}>{structures.map((row) => <option value={row.structure_id} key={row.structure_id}>{row.labels.join(" · ") || row.structure_id} · {row.node_count}N/{row.internal_edges}E</option>)}</select></label><label>{locale === "en" ? "Intervention mode" : "干预模式"}<select value={ablationMode} onChange={(event) => { setAblationMode(event.target.value as "silence" | "remove"); setConfirmRemove(false); }}><option value="silence">{locale === "en" ? "Temporary functional silence (reversible)" : "临时功能沉默（可逆）"}</option><option value="remove">{locale === "en" ? "Structural removal in clone (irreversible)" : "克隆体结构移除（不可逆）"}</option></select></label>{ablationMode === "remove" && <label className="evidence-confirm"><input type="checkbox" checked={confirmRemove} onChange={(event) => setConfirmRemove(event.target.checked)}/>{locale === "en" ? "I understand that removed nodes/edges cannot be restored inside the intervention clone." : "我理解被移除的节点/边无法在该干预克隆中恢复。"}</label>}<button disabled={busy || !chosenStructure || (ablationMode === "remove" && !confirmRemove)} onClick={() => void createPair()}>{locale === "en" ? "Create paired experiment" : "创建配对实验"}</button><small>{locale === "en" ? "The original consciousness is never modified. This intervention is explicitly logged and cannot be confused with endogenous forgetting." : "原意识绝不会被修改；干预会被显式记录，不会与内源性遗忘混淆。"}</small></article><article className="evidence-card"><h2>{locale === "en" ? "Paired experiments" : "配对实验"}</h2>{visiblePairs.length > 0 && <><div className="evidence-paired-probe"><label>{locale === "en" ? "Matched probe for both isolates" : "同时发送给两个隔离体的匹配探针"}<textarea value={pairedProbe} onChange={(event) => setPairedProbe(event.target.value)} placeholder={locale === "en" ? "The carrier is queued identically; step or resume the pair to observe its response." : "载体将按相同顺序排队；同步推进或继续后观察两组响应。"}/></label><label>{locale === "en" ? "Intensity" : "刺激强度"}<input type="number" min="0" max="2" step="0.05" value={pairedProbeIntensity} onChange={(event) => setPairedProbeIntensity(Number(event.target.value))}/></label></div><label className="evidence-step-ticks">{locale === "en" ? "Deterministic paired step (ticks)" : "确定性配对推进（tick）"}<input type="number" min="1" max="10000" value={pairedStepTicks} onChange={(event) => setPairedStepTicks(Math.max(1, Number(event.target.value) || 1))}/></label></>}<div className="evidence-pair-list">{visiblePairs.map((pair) => <div key={pair.id}><strong>{pair.title}</strong><small>{pair.mode} · {pair.status}<br/>{pair.control_runtime_id.slice(0, 8)} ↔ {pair.intervention_runtime_id.slice(0, 8)}</small><span><button disabled={busy || !pairedProbe.trim()} onClick={() => void stimulatePair(pair.id)}>{locale === "en" ? "Queue matched probe" : "排入匹配探针"}</button><button disabled={busy} onClick={() => void pairControl(pair.id, "step")}>{locale === "en" ? "Step pair" : "同步推进"}</button><button disabled={busy} onClick={() => void pairControl(pair.id, "resume")}>{locale === "en" ? "Resume pair" : "同步继续"}</button><button disabled={busy} onClick={() => void pairControl(pair.id, "pause")}>{locale === "en" ? "Pause pair" : "同步暂停"}</button></span></div>)}{!visiblePairs.length && <div className="evidence-empty">{locale === "en" ? "No paired interventions for this consciousness." : "当前意识尚无配对干预实验。"}</div>}</div></article></div>}
    {selectedStructure && <StructureInspector row={selectedStructure} locale={locale} onClose={() => setSelectedStructure(null)}/>} 
    {selectedTemporal && <TemporalInspector row={selectedTemporal} nodeSeries={temporalNodeSeries} loading={temporalTraceLoading} locale={locale} onClose={() => setSelectedTemporal(null)}/>} 
  </section>;
}
