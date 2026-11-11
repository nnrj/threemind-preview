"use client";

import { FormEvent, lazy, type ReactNode, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ThreeNodeShape, ViewMode, VisualStyle } from "./GraphViewport";
import {
  GraphProjectionStore,
  type GraphData,
  type GraphEdge,
  type GraphNode,
  type Metrics,
  type ModelManifestView,
} from "./graphProjectionStore";
import { HistoryManager, InstanceManager, PackageManager, StorageCleanupManager } from "./ManagementPages";
import { adapterText, edgeBirthPolicyText, I18nContext, kernelText, Locale, localizeStructuralReadout, persistenceKindText, providerKindText, resolveLocale, runtimeStatusText, sourcePolicyText, telemetryGroupText, telemetrySignalText, tr, useLocale, useT } from "./i18n";
import { AppChrome, type AppPage } from "./AppChrome";
import { MediaControls } from "./MediaControls";

const GraphViewport = lazy(() => import("./GraphViewport"));
const ThreeJsonGraphViewport = lazy(() => import("./ThreeJsonGraphViewport"));
const ExperimentWorkbench = lazy(() => import("./ExperimentWorkbench").then((module) => ({ default: module.ExperimentWorkbench })));
const ExperimentRecordsPage = lazy(() => import("./ExperimentWorkbench").then((module) => ({ default: module.ExperimentRecordsPage })));
const StatisticsEvidencePage = lazy(() => import("./StatisticsEvidencePage").then((module) => ({ default: module.StatisticsEvidencePage })));

function DockPinIcon({ pinned }: { pinned: boolean }) {
  return <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M8 4h8" />
    <path d="M9.5 4v5.2c0 1.22-.44 2.4-1.25 3.31L6.8 14.2h10.4l-1.45-1.69a5.06 5.06 0 0 1-1.25-3.31V4" />
    <path d="M12 14.2V21" />
    {!pinned && <path d="m5 5 14 14" />}
  </svg>;
}

// Requests stay on the UI origin. The local Next route below forwards them to Core,
// avoiding browser-side CORS and loopback-address mismatches.
const API = (import.meta.env.VITE_THREEMIND_API as string | undefined)?.replace(/\/$/, "") ?? "";
const WS_API = API ? API.replace(/^http/, "ws") : `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}`;

type OperationFeedback = {
  kind: "pending" | "success" | "error";
  message: string;
};

type RunOptions = {
  pendingMessage?: string;
  feedback?: boolean;
};

type KernelId = "labeled-feature-v1" | "anonymous-sensory-v2" | "anonymous-spatial-v3";
type V3NodeMode = "anonymous" | "labeled-observation" | "literal-character";
type NewModelOptions = {
  host_telemetry_enabled: boolean;
  process_telemetry_enabled: boolean;
  runtime_telemetry_enabled: boolean;
  random_ambient_enabled: boolean;
  spatial_enabled: boolean;
  spatial_dimensions: number;
  spatial_radius: number;
  spatial_competition: number;
  attention_budget: number;
  attention_competition_enabled: boolean;
  edge_adaptation_limit: number | null;
  propagation_limit: number | null;
  edge_birth_activation_product_min: number | null;
  propagation_activation_min: number | null;
  local_novelty_gain: number;
  novelty_touch_reference: number;
  association_window: number;
  edge_birth_policy: "local-coactivation" | "temporal-association";
  propagation_gain: number;
  learning_rate: number;
  edge_decay: number;
  stability_gain: number;
  stability_decay: number;
  consolidation_repeat_gain: number;
  consolidation_associative_gain: number;
  consolidation_intensity_gain: number;
  node_prune_after: number;
  sensory_channels: number;
  max_nodes: number | null;
  max_edges: number | null;
  homeostasis_enabled: boolean;
  target_total_activation: number;
  topology_inhibition_enabled: boolean;
  inhibition_generation_gain: number;
  inhibition_decay: number;
  inhibition_diffusion: number;
  inhibition_response_gain: number;
  inhibition_saturation: number;
  inhibition_propagation_min: number;
  energy_simulation_enabled: boolean;
  energy_initial_reserve: number;
  energy_capacity: number;
  energy_direct_cost: number;
  energy_associative_cost: number;
  energy_inhibition_cost: number;
  irreversible_energy_death_enabled: boolean;
  energy_maintenance_cost_per_node: number;
  energy_maintenance_cost_per_edge: number;
  energy_starvation_structural_decay: number;
  energy_starvation_death_ticks: number;
};

const DEFAULT_NEW_MODEL_OPTIONS: NewModelOptions = {
  host_telemetry_enabled: true,
  process_telemetry_enabled: false,
  runtime_telemetry_enabled: false,
  random_ambient_enabled: false,
  spatial_enabled: true,
  spatial_dimensions: 3,
  spatial_radius: 2.5,
  // Spatial inhibition is an experimental constraint, not a default
  // developmental tendency.
  spatial_competition: 0,
  // Keep the established V2 associative timescale while retaining V3's
  // optional spatial constraints.
  // Transparent attention is the default.  The capacity only becomes active
  // when an optional environmental competition plugin is enabled.
  attention_budget: 28,
  attention_competition_enabled: false,
  edge_adaptation_limit: null,
  propagation_limit: null,
  edge_birth_activation_product_min: null,
  propagation_activation_min: null,
  local_novelty_gain: 0.018,
  novelty_touch_reference: 0.20,
  association_window: 5,
  edge_birth_policy: "local-coactivation",
  propagation_gain: 0.42,
  learning_rate: 0.055,
  edge_decay: 0.0025,
  stability_gain: 0.018,
  stability_decay: 0.00015,
  consolidation_repeat_gain: 0.018,
  consolidation_associative_gain: 0.01,
  consolidation_intensity_gain: 0.075,
  node_prune_after: 800,
  sensory_channels: 192,
  max_nodes: null,
  max_edges: null,
  homeostasis_enabled: false,
  target_total_activation: 12,
  topology_inhibition_enabled: true,
  inhibition_generation_gain: 0.24,
  inhibition_decay: 0.35,
  inhibition_diffusion: 0.35,
  inhibition_response_gain: 2,
  inhibition_saturation: 1,
  inhibition_propagation_min: 0.002,
  energy_simulation_enabled: false,
  energy_initial_reserve: 1,
  energy_capacity: 1,
  energy_direct_cost: 0.035,
  energy_associative_cost: 0.02,
  energy_inhibition_cost: 0.01,
  irreversible_energy_death_enabled: false,
  energy_maintenance_cost_per_node: 0.00002,
  energy_maintenance_cost_per_edge: 0.000004,
  energy_starvation_structural_decay: 0.006,
  energy_starvation_death_ticks: 900,
};
type Position = { x: number; y: number; vx: number; vy: number };
type Snapshot = {
  id?: string;
  name: string;
  label?: string;
  path: string;
  kind: "snapshot" | "portrait";
  saved_at?: number;
  consciousness_id?: string;
  consciousness_name?: string;
  automatic?: boolean | null;
  reason?: string;
  provenance?: "manual" | "automatic" | "legacy" | "legacy-automatic" | string;
  metrics?: { tick: number; nodes: number; edges: number; life_state: string };
};

function formatSnapshotTime(value: number | undefined): string {
  if (!value) return "时间未知";
  const milliseconds = value < 100_000_000_000 ? value * 1000 : value;
  const date = new Date(milliseconds);
  return Number.isNaN(date.getTime()) ? "时间未知" : date.toLocaleString();
}

function snapshotProvenance(snapshot: Snapshot): string {
  if (snapshot.provenance === "legacy") return "历史存档（未记录来源）";
  if (snapshot.provenance === "legacy-automatic") return "历史自动存档";
  if (snapshot.automatic) return `自动 · ${snapshot.reason ?? "规则触发"}`;
  return "手动";
}
function temporalClassificationText(locale: Locale, value?: string): string {
  const labels: Record<string, [string, string]> = {
    converged: ["收敛", "Converged"],
    oscillatory: ["周期振荡", "Oscillatory"],
    residual_decay: ["残留衰减", "Residual decay"],
    transient: ["瞬态响应", "Transient"],
    unresolved: ["尚未判定", "Unresolved"],
    interrupted: ["观测中断", "Interrupted"],
  };
  const label = labels[value ?? ""];
  return label ? label[locale === "en" ? 1 : 0] : (value || "—");
}
type ObserverEvent = {
  id: string;
  tick: number;
  occurrences: number;
  readout: string;
  anonymous_readout?: string;
  display_readout?: string;
  readable_labels?: string[];
  label_entries?: ReadoutLabelEntry[];
  internal_edges: number;
  delivery?: { state?: string; detail?: string };
  kind?: string;
  readout_kind?: string;
  start_tick?: number;
  end_tick?: number;
  classification?: string;
  rankings?: TemporalNodeRanking[];
  convergence?: Record<string, unknown>;
};
type ReadoutLabelEntry = { node_id: number; label: string; activation: number; stability: number; touch_count: number; direct_touch?: number; associative_touch?: number };
type TemporalNodeRanking = { node_id: number; origin: string; active_ticks: number; active_ratio: number; tail_active_ticks: number; tail_active_ratio: number; longest_active_run: number; activation_integral: number; excess_activation_integral: number; peak_activation: number; mean_activation: number; inhibition_integral: number; score: number };
type TemporalReadout = ObserverEvent & { anonymous_readout: string; display_readout: string; node_ids: number[]; classification: string; rankings: TemporalNodeRanking[]; window?: { observed_ticks?: number; tail_ticks?: number } };
type ObserverView = {
  current: {
    tick: number;
    text: string;
    anonymous_readout?: string;
    display_readout?: string;
    readable_labels?: string[];
    label_entries?: ReadoutLabelEntry[];
    node_ids?: number[];
    occurrences: number;
    internal_edges: number;
    repeatable: boolean;
  };
  events: ObserverEvent[];
  temporal?: { current: TemporalReadout | null; active_windows: { envelope_id: string; source: string; start_tick: number; delivery_end_tick?: number | null; last_tick: number; tail_ticks: number }[] };
  config: ObserverSettings;
};
type TemporalReadoutSettings = {
  enabled: boolean;
  trigger_manual: boolean;
  trigger_ai: boolean;
  trigger_ambient: boolean;
  consider_activation_strength: boolean;
  ranking_mode: "composite" | "duration" | "activation-integral";
  candidate_scope: "associative-or-persistent" | "associative-only" | "all-active";
  baseline_ticks: number;
  min_response_ticks: number;
  max_response_ticks: number;
  settle_ticks: number;
  activation_threshold: number;
  excess_activation_min: number;
  baseline_noise_gain: number;
  convergence_jaccard_min: number;
  convergence_drift_max: number;
  display_limit: number;
};
type ObserverSettings = {
  snapshot_enabled: boolean;
  activation_threshold: number;
  min_nodes: number;
  max_nodes: number;
  min_internal_edges: number;
  recurrence_window_ticks: number;
  min_occurrences: number;
  min_span_ticks: number;
  alert_cooldown_ticks: number;
  read_touched_activity: boolean;
  repeatable_structure_readout: boolean;
  label_sort_by_activation: boolean;
  label_display_limit: number;
  temporal: TemporalReadoutSettings;
};
type ConversationMessage = { kind: "stimulus" | "interpretation" | "readout"; role: "user" | "environment" | "interpreter"; tick: number; text: string; conversation_key?: string; anonymous_text?: string; node_ids?: number[]; readable_labels?: string[]; label_entries?: ReadoutLabelEntry[]; source?: string; source_provenance?: string[]; background?: boolean; intensity?: number; important?: boolean; provider_id?: string; trigger?: string; trigger_stimulus_tick?: number; readout_kind?: string; start_tick?: number; end_tick?: number; classification?: string; rankings?: TemporalNodeRanking[]; convergence?: Record<string, unknown>; window?: { observed_ticks?: number; tail_ticks?: number }; occurrences?: number; internal_edges?: number; repeatable?: boolean };

function mergeConversation(previous: ConversationMessage[], additions: ConversationMessage[]): ConversationMessage[] {
  const rows = new Map<string, ConversationMessage>();
  for (const row of previous) rows.set(row.conversation_key ?? `${row.kind}:${row.tick}:${row.text}`, row);
  for (const row of additions) rows.set(row.conversation_key ?? `${row.kind}:${row.tick}:${row.text}`, row);
  const order = { stimulus: 0, readout: 1, interpretation: 2 } as Record<ConversationMessage["kind"], number>;
  return [...rows.values()].sort((left, right) => left.tick - right.tick || order[left.kind] - order[right.kind]);
}
type ConsciousnessSummary = { id: string; name: string; kernel?: KernelId | "unknown"; parent_id?: string | null; snapshots: number; portraits: number; status: string; running: boolean; active?: boolean; persisted?: boolean; saved_at?: number; metrics?: Metrics; latest?: { metrics?: { tick?: number } } | null };
type NotificationSettings = {
  enabled: boolean;
  sender: string;
  recipients: string[];
  language?: "follow-ui" | "zh-CN" | "en";
  resend_api_key_configured: boolean;
  resend_api_key_hint: string;
};
type CanvasNodeShape = "circle" | "square";
type VisualizationSettings = {
  mode: ViewMode;
  renderer: "threejson" | "three" | "canvas";
  canvas_shape: CanvasNodeShape;
  three_shape: ThreeNodeShape;
  style: VisualStyle;
  continuous_motion: boolean;
};
type AiProvider = { id: string; name: string; kind: "openai" | "deepseek" | "openai-compatible"; base_url: string; model: string; api_key?: string; api_key_configured?: boolean };
type ProviderTestResult = { state: "testing" | "success" | "error"; message: string };
type AiSettings = { providers: AiProvider[]; environment: { enabled: boolean; provider_id: string; frequency_ticks: number; random_frequency: boolean; intensity: number; irregularity: number }; interpreter: { enabled: boolean; provider_id: string; frequency_ticks: number; periodic_enabled: boolean; on_repeatable_structure: boolean; active_nodes_enabled: boolean; on_manual_stimulus: boolean; listen_background_active_nodes: boolean; deduplicate_readouts: boolean; activation_min: number; activation_max: number; language: string }; auto_snapshot: { enabled: boolean; frequency_ticks: number; on_repeatable_structure: boolean; on_interpreter_important: boolean } };
type SourcePolicyId = "ui-text" | "cli-text" | "ai-environment" | "ai-debug" | "ui-audio" | "ui-image" | "ui-video" | "live-microphone" | "live-camera" | "background";
type SourcePolicy = { enabled: boolean; bypass_attention: boolean };
type StimuliSettings = { manual_enabled: boolean; ai_enabled: boolean; background_enabled: boolean; submit_on_enter: boolean; bypass_filter_sources: ("manual" | "ai" | "ambient")[]; source_policies: Record<SourcePolicyId, SourcePolicy> };
type ConversationSettings = { show_environment_stimuli: boolean; show_triggering_environment_stimuli: boolean; show_background_readouts: boolean };
type NetworkSettings = { enabled: boolean; allow_remote_modulation: boolean; modulation_timeout_ticks: number; output_interval_ms: number; token_configured?: boolean; protocol?: string };
type BodySettings = { enabled: boolean; sampling_ticks: number; threshold: number; adaptation: number; noise: number; energy_supply: { enabled: boolean; supply_per_tick: number; total_supply_limit: number } };
type AdapterRule = { type?: string; title?: string; minimum?: number; maximum?: number; multipleOf?: number; enum?: Array<string | number>; properties?: Record<string, AdapterRule> };
type AdapterSchema = AdapterRule;
type AdapterRuntime = { backend?: string; dependency?: "full" | "partial"; last_sample_time?: string | null; last_sample_id?: string; last_duration_ms?: number; available_metrics?: string[]; unavailable_metrics?: Record<string, string>; available_inputs?: string[]; unavailable_inputs?: Record<string, string>; recent_error?: string | null; scope?: "host" | "process" | "runtime"; whole_process?: boolean; per_consciousness?: boolean; consciousness_id?: string | null; protocol?: string; raw_retention?: string; subscribed?: boolean; semantic_models?: string[]; live_session_id?: string | null; audit?: { path?: string; writes?: number; recent_error?: string; assets?: number; sessions?: number; deliveries?: number; active_sessions?: number; retention?: string } };
type AdapterGroup = { id: string; signals: string[] };
type AdapterInfo = { id: string; name: string; direction: string; bus: string; description: string; enabled: boolean; config: Record<string, unknown>; schema: AdapterSchema; dependencies: string[]; ui?: { component?: string; scope?: string; groups?: AdapterGroup[] }; runtime?: AdapterRuntime };
type AdapterBinding = { adapter_id: string; enabled: boolean; effective_enabled?: boolean; status?: string; config?: Record<string, unknown> };
type MediaSession = { session_id: string; consciousness_id: string; adapter_id: string; mode: string; state: string; progress: number; frames_encoded: number; created_at_utc: string; error?: string | null };
type ArchiveIndexStatus = { backend?: string; path?: string; indexed_artifacts?: number; running?: boolean; phase?: string; total?: number; processed?: number; indexed?: number; skipped?: number; failed?: number; writer?: { queued?: number; pending?: number; written?: number; failed?: number } };
type Settings = { notifications: NotificationSettings; visualization: VisualizationSettings; observer: ObserverSettings; archive?: { prompt_for_snapshot_name: boolean }; ai?: AiSettings; stimuli?: StimuliSettings; body?: BodySettings; network?: NetworkSettings; conversation?: ConversationSettings; ui?: { locale?: "auto" | Locale } };

const EMPTY_METRICS: Metrics = {
  id: "—",
  tick: 0,
  life_state: "connecting",
  node_count: 0,
  edge_count: 0,
  active_nodes: 0,
  total_activation: 0,
  mean_stability: 0,
};

const EMPTY_OBSERVER: ObserverView = {
  current: { tick: 0, text: "—", occurrences: 0, internal_edges: 0, repeatable: false },
  events: [],
  temporal: { current: null, active_windows: [] },
  config: {
    snapshot_enabled: true,
    activation_threshold: 0.055,
    min_nodes: 3,
    max_nodes: 7,
    min_internal_edges: 2,
    recurrence_window_ticks: 240,
    min_occurrences: 4,
    min_span_ticks: 8,
    alert_cooldown_ticks: 1200,
    read_touched_activity: true,
    repeatable_structure_readout: true,
    label_sort_by_activation: true,
    label_display_limit: 0,
    temporal: {
      enabled: true,
      trigger_manual: true,
      trigger_ai: false,
      trigger_ambient: false,
      consider_activation_strength: true,
      ranking_mode: "composite",
      candidate_scope: "associative-or-persistent",
      baseline_ticks: 12,
      min_response_ticks: 12,
      max_response_ticks: 120,
      settle_ticks: 8,
      activation_threshold: .055,
      excess_activation_min: .005,
      baseline_noise_gain: 1,
      convergence_jaccard_min: .8,
      convergence_drift_max: .12,
      display_limit: 7,
    },
  },
};

const EMPTY_SETTINGS: Settings = {
  notifications: { enabled: false, sender: "ThreeMind <onboarding@resend.dev>", recipients: [], language: "follow-ui", resend_api_key_configured: false, resend_api_key_hint: "" },
  observer: EMPTY_OBSERVER.config,
  visualization: { mode: "3d", renderer: "threejson", canvas_shape: "circle", three_shape: "glow", style: "organic", continuous_motion: false },
  archive: { prompt_for_snapshot_name: true },
  ai: { providers: [], environment: { enabled: false, provider_id: "", frequency_ticks: 120, random_frequency: true, intensity: .7, irregularity: .65 }, interpreter: { enabled: false, provider_id: "", frequency_ticks: 300, periodic_enabled: true, on_repeatable_structure: false, active_nodes_enabled: true, on_manual_stimulus: false, listen_background_active_nodes: false, deduplicate_readouts: false, activation_min: .08, activation_max: 1, language: "auto" }, auto_snapshot: { enabled: false, frequency_ticks: 0, on_repeatable_structure: true, on_interpreter_important: true } },
  stimuli: { manual_enabled: true, ai_enabled: true, background_enabled: true, submit_on_enter: true, bypass_filter_sources: [], source_policies: { "ui-text": { enabled: true, bypass_attention: false }, "cli-text": { enabled: true, bypass_attention: false }, "ai-environment": { enabled: true, bypass_attention: false }, "ai-debug": { enabled: true, bypass_attention: false }, "ui-audio": { enabled: true, bypass_attention: false }, "ui-image": { enabled: true, bypass_attention: false }, "ui-video": { enabled: true, bypass_attention: false }, "live-microphone": { enabled: true, bypass_attention: false }, "live-camera": { enabled: true, bypass_attention: false }, background: { enabled: true, bypass_attention: false } } },
  body: { enabled: false, sampling_ticks: 1, threshold: .035, adaptation: .55, noise: .02, energy_supply: { enabled: false, supply_per_tick: .004, total_supply_limit: 0 } },
  network: { enabled: false, allow_remote_modulation: false, modulation_timeout_ticks: 300, output_interval_ms: 150, token_configured: false, protocol: "threemind-network/1" },
  conversation: { show_environment_stimuli: false, show_triggering_environment_stimuli: true, show_background_readouts: false },
  ui: { locale: "auto" },
};

function normalizeSettings(settings: Settings): Settings {
  return {
    ...settings,
    notifications: { ...EMPTY_SETTINGS.notifications, ...settings.notifications, recipients: settings.notifications?.recipients ?? [] },
    observer: { ...EMPTY_SETTINGS.observer, ...(settings.observer ?? {}), temporal: { ...EMPTY_SETTINGS.observer.temporal, ...(settings.observer?.temporal ?? {}) } },
    visualization: { ...EMPTY_SETTINGS.visualization, ...(settings.visualization ?? {}) },
    archive: { prompt_for_snapshot_name: settings.archive?.prompt_for_snapshot_name ?? true },
    ai: { ...EMPTY_SETTINGS.ai!, ...(settings.ai ?? {}), environment: { ...EMPTY_SETTINGS.ai!.environment, ...(settings.ai?.environment ?? {}) }, interpreter: { ...EMPTY_SETTINGS.ai!.interpreter, ...(settings.ai?.interpreter ?? {}) }, auto_snapshot: { ...EMPTY_SETTINGS.ai!.auto_snapshot, ...(settings.ai?.auto_snapshot ?? {}) } },
    stimuli: { ...EMPTY_SETTINGS.stimuli!, ...(settings.stimuli ?? {}), source_policies: { ...EMPTY_SETTINGS.stimuli!.source_policies, ...(settings.stimuli?.source_policies ?? {}) } },
    body: { ...EMPTY_SETTINGS.body!, ...(settings.body ?? {}), energy_supply: { ...EMPTY_SETTINGS.body!.energy_supply, ...(settings.body?.energy_supply ?? {}) } },
    network: { ...EMPTY_SETTINGS.network!, ...(settings.network ?? {}) },
    conversation: { ...EMPTY_SETTINGS.conversation!, ...(settings.conversation ?? {}) },
    ui: { ...EMPTY_SETTINGS.ui!, ...(settings.ui ?? {}) },
  };
}

async function command(name: string, args: Record<string, unknown> = {}) {
  const response = await fetch(`${API}/api/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command: name, args }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail ?? "操作失败");
  return payload;
}

function NetworkCanvas({
  graph,
  onSelect,
  shape,
  continuousMotion,
}: {
  graph: GraphData | null;
  onSelect: (node: GraphNode | null) => void;
  shape: CanvasNodeShape;
  continuousMotion: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const positionsRef = useRef(new Map<number, Position>());
  const graphRef = useRef<GraphData | null>(graph);
  const shapeRef = useRef(shape);
  const continuousMotionRef = useRef(continuousMotion);

  useEffect(() => {
    graphRef.current = graph;
  }, [graph]);
  useEffect(() => { shapeRef.current = shape; }, [shape]);
  useEffect(() => { continuousMotionRef.current = continuousMotion; }, [continuousMotion]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    let animation = 0;
    let width = 1;
    let height = 1;
    let pixelRatio = 1;

    const resize = () => {
      const box = canvas.getBoundingClientRect();
      pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      width = Math.max(1, box.width);
      height = Math.max(1, box.height);
      canvas.width = width * pixelRatio;
      canvas.height = height * pixelRatio;
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    };
    resize();
    // Resizing the canvas from inside a ResizeObserver can recursively schedule
    // another layout notification in some development overlays. Window resize is
    // sufficient here because the stage only changes size with the page layout.
    window.addEventListener("resize", resize);

    const draw = () => {
      const data = graphRef.current;
      context.clearRect(0, 0, width, height);
      if (!data) {
        animation = requestAnimationFrame(draw);
        return;
      }
      const positions = positionsRef.current;
      const liveIds = new Set(data.nodes.map((node) => node.id));
      for (const id of positions.keys()) {
        if (!liveIds.has(id)) positions.delete(id);
      }
      for (const node of data.nodes) {
        if (!positions.has(node.id)) {
          const angle = (node.id * 2.39996) % (Math.PI * 2);
          const radius = 30 + Math.sqrt(node.id % 400) * 12;
          positions.set(node.id, {
            x: width / 2 + Math.cos(angle) * radius,
            y: height / 2 + Math.sin(angle) * radius,
            vx: 0,
            vy: 0,
          });
        }
      }

      // Position integration is a non-Core visual effect.  Keep it opt-in so
      // a frozen Core cannot appear to continue evolving on the canvas.
      if (continuousMotionRef.current) {
        for (const edge of data.edges) {
          const source = positions.get(edge.source);
          const target = positions.get(edge.target);
          if (!source || !target) continue;
          const dx = target.x - source.x;
          const dy = target.y - source.y;
          const distance = Math.max(1, Math.hypot(dx, dy));
          const desired = 42 + (1 - edge.weight) * 66;
          const force = (distance - desired) * (0.0008 + edge.weight * 0.0015);
          source.vx += dx * force;
          source.vy += dy * force;
          target.vx -= dx * force;
          target.vy -= dy * force;
        }

        for (const node of data.nodes) {
          const position = positions.get(node.id)!;
          position.vx += (width / 2 - position.x) * 0.00005;
          position.vy += (height / 2 - position.y) * 0.00005;
          const drift = Math.sin(node.id * 11.7 + data.metrics.tick * 0.025) * 0.002;
          position.vx += drift;
          position.vy -= drift;
          position.vx *= 0.91;
          position.vy *= 0.91;
          position.x = Math.max(12, Math.min(width - 12, position.x + position.vx));
          position.y = Math.max(70, Math.min(height - 12, position.y + position.vy));
        }
      }

      context.lineCap = "round";
      for (const edge of data.edges) {
        const source = positions.get(edge.source);
        const target = positions.get(edge.target);
        if (!source || !target) continue;
        const alpha = Math.min(0.68, 0.025 + edge.weight * 0.24 + edge.stability * 0.28);
        context.beginPath();
        context.moveTo(source.x, source.y);
        context.lineTo(target.x, target.y);
        context.strokeStyle = edge.touched
          ? `rgba(124, 224, 211, ${Math.max(alpha, 0.42)})`
          : `rgba(119, 157, 147, ${alpha})`;
        context.lineWidth = 0.45 + edge.stability * 1.8;
        context.stroke();
      }

      for (const node of data.nodes) {
        const position = positions.get(node.id)!;
        const radius = 2.1 + Math.sqrt(node.touch_count) * 0.18 + node.stability * 2.7;
        const direct = node.direct > 0;
        const associated = !direct && node.associative > 0;
        const color = direct
          ? "243, 189, 114"
          : associated
            ? "124, 224, 211"
            : "129, 158, 150";
        if (node.activation > 0.02) {
          context.beginPath();
          context.arc(position.x, position.y, radius + 4 + node.activation * 6, 0, Math.PI * 2);
          context.fillStyle = `rgba(${color}, ${0.025 + node.activation * 0.10})`;
          context.fill();
        }
        context.beginPath();
        if (shapeRef.current === "square") context.rect(position.x - radius, position.y - radius, radius * 2, radius * 2);
        else context.arc(position.x, position.y, radius, 0, Math.PI * 2);
        context.fillStyle = `rgba(${color}, ${0.28 + node.activation * 0.72})`;
        context.fill();
      }
      animation = requestAnimationFrame(draw);
    };
    draw();

    const handlePointer = (event: PointerEvent) => {
      const data = graphRef.current;
      if (!data) return;
      const box = canvas.getBoundingClientRect();
      const x = event.clientX - box.left;
      const y = event.clientY - box.top;
      let closest: GraphNode | null = null;
      let distance = 14;
      for (const node of data.nodes) {
        const position = positionsRef.current.get(node.id);
        if (!position) continue;
        const candidate = Math.hypot(position.x - x, position.y - y);
        if (candidate < distance) {
          closest = node;
          distance = candidate;
        }
      }
      onSelect(closest);
    };
    const clearSelection = () => onSelect(null);
    canvas.addEventListener("pointermove", handlePointer);
    canvas.addEventListener("pointerleave", clearSelection);

    return () => {
      cancelAnimationFrame(animation);
      window.removeEventListener("resize", resize);
      canvas.removeEventListener("pointermove", handlePointer);
      canvas.removeEventListener("pointerleave", clearSelection);
    };
  }, [onSelect]);

  return <canvas ref={canvasRef} aria-label="连续可塑联想网络实时图" />;
}

function SettingsDisclosure({ title, description, children, defaultOpen = false }: { title: string; description?: string; children: ReactNode; defaultOpen?: boolean }) {
  const [expanded, setExpanded] = useState(defaultOpen);
  return <details className="settings-disclosure" open={expanded} onToggle={(event) => setExpanded(event.currentTarget.open)}>
    <summary>
      <span><strong>{title}</strong>{description && <small>{description}</small>}</span>
      <i aria-hidden="true">⌄</i>
    </summary>
    <div className="settings-disclosure-content">{children}</div>
  </details>;
}

function SettingsPanel({
  open,
  initialCategory,
  settings,
  apiKey,
  onClose,
  onChange,
  onKeyChange,
  onSave,
  onTest,
  onToggleStimulusSource,
  navigationAutoHide,
  onNavigationAutoHideChange,
  traceEnabled,
  traceAvailable,
  onTraceChange,
  saving,
  loading,
}: {
  open: boolean;
  initialCategory: string;
  settings: Settings;
  apiKey: string;
  onClose: () => void;
  onChange: (next: Settings) => void;
  onKeyChange: (value: string) => void;
  onSave: () => Promise<unknown>;
  onTest: () => void;
  onToggleStimulusSource: (source: "manual" | "ai" | "ambient", enabled: boolean) => void;
  navigationAutoHide: boolean;
  onNavigationAutoHideChange: (enabled: boolean) => void;
  traceEnabled: boolean;
  traceAvailable: boolean;
  onTraceChange: (enabled: boolean) => Promise<void>;
  saving: boolean;
  loading: boolean;
}) {
  const t = useT();
  const locale = useLocale();
  const [active, setActive] = useState("visualization");
  // SQLite is the safe normal choice for an append-heavy experiment. The old
  // JSON backend must decode its entire document at startup, so it is kept as
  // a small compatibility option rather than the default.
  const [persistenceKind, setPersistenceKind] = useState("sqlite");
  const [persistenceValue, setPersistenceValue] = useState("");
  const [persistenceMessage, setPersistenceMessage] = useState("");
  const [persistenceStartupWarning, setPersistenceStartupWarning] = useState("");
  const [archiveIndex, setArchiveIndex] = useState<ArchiveIndexStatus | null>(null);
  const [archiveIndexMessage, setArchiveIndexMessage] = useState("");
  const [modelInfo, setModelInfo] = useState<{ manifest: { spatial_embedding?: boolean; spatial_dimensions?: number; parameters?: Record<string, unknown> }; runtime_config: Record<string, unknown> } | null>(null);
  const [modelLoading, setModelLoading] = useState(false);
  const [modelMessage, setModelMessage] = useState("");
  const [networkToken, setNetworkToken] = useState("");
  const [networkMessage, setNetworkMessage] = useState("");
  const [providerTestResults, setProviderTestResults] = useState<Record<string, ProviderTestResult>>({});
  const [panelOperation, setPanelOperation] = useState("");
  const categoryGroups = (locale === "en" ? [
    { label: "Workspace", items: [["visualization", "Interface & interaction"], ["runtime", "Stimuli & input"]] },
    { label: "Mind & observation", items: [["body", "Senses, attention & energy"], ["model", "Model dynamics & space"], ["observer", "Observation & records"]] },
    { label: "AI & integration", items: [["ai", "AI providers"], ["automation", "AI stimuli & interpretation"], ["network", "Network interface"]] },
    { label: "System", items: [["persistence", "Storage & archives"], ["notifications", "Notifications & email"]] },
  ] : [
    { label: "工作区", items: [["visualization", "界面与交互"], ["runtime", "刺激与输入"]] },
    { label: "意识与观测", items: [["body", "感官、注意与能量"], ["model", "模型动力学与空间"], ["observer", "观测、读出与记录"]] },
    { label: "AI 与集成", items: [["ai", "AI 供应商"], ["automation", "AI 刺激与意识解读"], ["network", "网络接口"]] },
    { label: "系统", items: [["persistence", "存储与归档"], ["notifications", "通知与邮件"]] },
  ]) as ReadonlyArray<{ label: string; items: ReadonlyArray<readonly [string, string]> }>;
  const categoryNames = categoryGroups.flatMap((group) => group.items.map(([name]) => name));
  useEffect(() => {
    if (!open) return;
    const requested = initialCategory === "interpretations" ? "automation" : initialCategory;
    setActive(categoryNames.includes(requested) ? requested : "visualization");
  }, [initialCategory, open, locale]);
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setModelLoading(true);
    setModelInfo(null);
    setModelMessage("");
    void fetch(`${API}/api/model`, { cache: "no-store" })
      .then(async (response) => {
        const payload = await response.json().catch(() => null) as unknown;
        if (response.status === 409) {
          if (!cancelled) {
            setModelMessage(locale === "en"
              ? "No consciousness is currently running. Create or open one to configure its model parameters."
              : "当前没有运行中的意识。新建或打开意识后，可在此配置其模型参数。");
          }
          return;
        }
        if (!response.ok) throw new Error("model unavailable");
        if (!payload || typeof payload !== "object") throw new Error("invalid model response");
        const candidate = payload as { manifest?: unknown; runtime_config?: unknown };
        if (!candidate.manifest || typeof candidate.manifest !== "object" || !candidate.runtime_config || typeof candidate.runtime_config !== "object") {
          throw new Error("invalid model response");
        }
        if (!cancelled) {
          setModelInfo(payload as { manifest: { spatial_embedding?: boolean; spatial_dimensions?: number; parameters?: Record<string, unknown> }; runtime_config: Record<string, unknown> });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setModelInfo(null);
          setModelMessage(locale === "en" ? "Current model settings could not be loaded." : "无法读取当前模型设置。");
        }
      })
      .finally(() => {
        if (!cancelled) setModelLoading(false);
      });
    return () => { cancelled = true; };
  }, [locale, open]);
  useEffect(() => {
    if (!open) return;
    fetch(`${API}/api/persistence`, { cache: "no-store" })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("persistence unavailable")))
      .then((status: { kind?: string; config?: { path?: string; endpoint?: string }; startup_warning?: string | null; legacy_file?: { bytes?: number; preserved?: boolean } | null }) => {
        if (status.kind && ["file", "sqlite", "mysql", "d1"].includes(status.kind)) setPersistenceKind(status.kind);
        setPersistenceValue(status.config?.path ?? status.config?.endpoint ?? "");
        const bytes = Number(status.legacy_file?.bytes ?? 0);
        const legacyNotice = bytes > 0
          ? (locale === "en" ? `A legacy JSON history file (${(bytes / 1024 / 1024 / 1024).toFixed(2)} GiB) is retained without being opened.` : `检测到旧版 JSON 历史文件（${(bytes / 1024 / 1024 / 1024).toFixed(2)} GiB），已保留且不会在启动时打开。`)
          : "";
        setPersistenceStartupWarning(String(status.startup_warning ?? legacyNotice));
      })
      .catch(() => setPersistenceStartupWarning(""));
  }, [locale, open]);
  const refreshArchiveIndex = async (announce = false) => {
    if (announce) setPanelOperation(locale === "en" ? "Refreshing archive catalogue…" : "正在刷新归档目录…");
    try {
      const response = await fetch(`${API}/api/archive-index`, { cache: "no-store" });
      if (!response.ok) throw new Error("archive index unavailable");
      setArchiveIndex(await response.json() as ArchiveIndexStatus);
      setArchiveIndexMessage("");
    } catch {
      setArchiveIndexMessage(locale === "en" ? "Archive catalogue status is unavailable." : "归档目录状态暂时不可用。");
    } finally {
      if (announce) setPanelOperation("");
    }
  };
  useEffect(() => {
    if (!open) return;
    void refreshArchiveIndex();
  }, [open]);
  if (!open) return null;

  const notification = settings.notifications;
  const observer = settings.observer;
  const visualization = settings.visualization;
  const archive = settings.archive ?? EMPTY_SETTINGS.archive!;
  const ai = settings.ai ?? EMPTY_SETTINGS.ai!;
  const stimuli = settings.stimuli ?? EMPTY_SETTINGS.stimuli!;
  const body = settings.body ?? EMPTY_SETTINGS.body!;
  const network = settings.network ?? EMPTY_SETTINGS.network!;
  const conversationSettings = settings.conversation ?? EMPTY_SETTINGS.conversation!;
  const temporal = observer.temporal ?? EMPTY_OBSERVER.config.temporal;
  const persistenceCopy = locale === "en" ? {
    title: "Local archive catalogue",
    description: "Portable experimental state remains in .tmind files. This service always uses a local SQLite metadata catalogue for fast archive, snapshot, and consciousness queries; it is derived from packages and never changes Core dynamics.",
    generic: "The controls below are retained for the optional generic management-record backend. They do not move .tmind artifacts or replace the archive catalogue.",
    refresh: "Refresh catalogue status",
    rebuild: "Rebuild catalogue in background",
    ready: "ready",
    indexing: "indexing",
  } : {
    title: "本地归档目录",
    description: "完整、可移植的实验状态仍保存在 .tmind 文件中。当前服务始终使用本地 SQLite 元数据目录快速查询档案、快照和意识；目录由模型包派生，不会改变 Core 动力学。",
    generic: "下方控件保留给可选的通用管理记录后端；它们不会迁移 .tmind 工件，也不会替代归档目录。",
    refresh: "刷新目录状态",
    rebuild: "后台重建目录",
    ready: "就绪",
    indexing: "正在建立索引",
  };
  const updateNotification = (patch: Partial<NotificationSettings>) =>
    onChange({ ...settings, notifications: { ...notification, ...patch } });
  const updateObserver = (patch: Partial<ObserverSettings>) =>
    onChange({ ...settings, observer: { ...observer, ...patch } });
  const updateTemporal = (patch: Partial<TemporalReadoutSettings>) =>
    updateObserver({ temporal: { ...temporal, ...patch } });
  const updateVisualization = (patch: Partial<VisualizationSettings>) =>
    onChange({ ...settings, visualization: { ...visualization, ...patch } });
  const updateArchive = (patch: { prompt_for_snapshot_name: boolean }) =>
    onChange({ ...settings, archive: { ...archive, ...patch } });
  const updateAi = (patch: Partial<AiSettings>) => onChange({ ...settings, ai: { ...ai, ...patch } });
  const testProvider = async (provider: AiProvider) => {
    const providerId = provider.id;
    const baseUrl = provider.base_url.trim();
    const apiKey = provider.api_key?.trim() ?? "";
    if (!baseUrl) {
      setProviderTestResults((previous) => ({ ...previous, [providerId]: { state: "error", message: t("providerTestNeedsUrl") } }));
      return;
    }
    if (!apiKey && !provider.api_key_configured) {
      setProviderTestResults((previous) => ({ ...previous, [providerId]: { state: "error", message: t("providerTestNeedsKey") } }));
      return;
    }
    setProviderTestResults((previous) => ({ ...previous, [providerId]: { state: "testing", message: t("providerTesting") } }));
    try {
      const response = await fetch(`${API}/api/ai/providers/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: providerId,
          name: provider.name,
          kind: provider.kind,
          base_url: baseUrl,
          model: provider.model.trim(),
          api_key: apiKey,
          use_stored_key: !apiKey && Boolean(provider.api_key_configured),
        }),
      });
      const payload = await response.json().catch(() => ({} as { detail?: string; text?: string }));
      if (!response.ok) throw new Error(payload.detail || t("requestFailed"));
      const responseText = typeof payload.text === "string" && payload.text.trim() ? `：${payload.text.trim()}` : "";
      setProviderTestResults((previous) => ({ ...previous, [providerId]: { state: "success", message: `${t("providerTestConnected")}${responseText}` } }));
    } catch (error) {
      const message = error instanceof Error ? error.message : t("requestFailed");
      setProviderTestResults((previous) => ({ ...previous, [providerId]: { state: "error", message } }));
    }
  };
  const updateBody = (patch: Partial<BodySettings>) => onChange({ ...settings, body: { ...body, ...patch } });
  const updateNetwork = (patch: Partial<NetworkSettings>) => onChange({ ...settings, network: { ...network, ...patch } });
  const withPanelOperation = async <T,>(label: string, action: () => Promise<T>): Promise<T | undefined> => {
    if (panelOperation) return undefined;
    setPanelOperation(label);
    try {
      return await action();
    } finally {
      setPanelOperation("");
    }
  };
  const saveNetworkSettings = async () => withPanelOperation(locale === "en" ? "Saving network adapter settings…" : "正在保存网络适配器设置…", async () => {
    try {
      const response = await fetch(`${API}/api/network/settings`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled: network.enabled, allow_remote_modulation: network.allow_remote_modulation, modulation_timeout_ticks: network.modulation_timeout_ticks, output_interval_ms: network.output_interval_ms, ...(networkToken ? { token: networkToken } : {}) }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "Network settings could not be saved.");
      updateNetwork(payload as NetworkSettings);
      setNetworkToken("");
      setNetworkMessage(locale === "en" ? "Network adapter settings saved." : "网络适配器设置已保存。 ");
    } catch (error) {
      setNetworkMessage(error instanceof Error ? error.message : (locale === "en" ? "Network settings could not be saved." : "网络设置保存失败。"));
    }
  });
  const applyModelParameters = async (): Promise<boolean> => {
    if (!modelInfo) return true;
    const result = await withPanelOperation(locale === "en" ? "Applying model parameters…" : "正在应用模型参数…", async () => {
      try {
        const response = await fetch(`${API}/api/model/parameters`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ spatial_dimensions: modelInfo.manifest.spatial_embedding ? modelInfo.manifest.spatial_dimensions : undefined, parameters: modelInfo.manifest.parameters ?? {} }) });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail ?? "Model settings could not be applied.");
        setModelInfo({ manifest: result.manifest, runtime_config: result.runtime_config });
        setModelMessage(locale === "en" ? "Model parameters applied." : "模型参数已应用。 ");
        return true;
      } catch (error) {
        setModelMessage(error instanceof Error ? error.message : (locale === "en" ? "Model settings could not be applied." : "模型配置失败。"));
        return false;
      }
    });
    return result ?? false;
  };
  const savePanelSettings = async () => {
    // Model parameters live on the active consciousness rather than in the
    // service UI-settings document.  The main Save button must commit both
    // stores so a checked switch cannot remain a merely local UI draft.
    if (!await applyModelParameters()) return;
    await onSave();
  };
  const updateModelParameter = (key: string, value: unknown) => {
    if (!modelInfo) return;
    setModelInfo({ ...modelInfo, manifest: { ...modelInfo.manifest, parameters: { ...modelInfo.manifest.parameters, [key]: value } } });
  };
  const modelNumberField = (key: string, label: string, min: number, max: number, step: number, disabled = false) => modelInfo ? (
    <label className="settings-field" key={key}>{label}
      <input type="number" min={min} max={max} step={step} disabled={disabled} value={Number(modelInfo.manifest.parameters?.[key] ?? modelInfo.runtime_config?.[key] ?? 0)} onChange={(event) => updateModelParameter(key, Number(event.target.value))} />
    </label>
  ) : null;
  const rebuildArchiveIndex = async () => withPanelOperation(locale === "en" ? "Starting archive catalogue rebuild…" : "正在启动归档目录重建…", async () => {
    try {
      const response = await fetch(`${API}/api/archive-index/reindex?force=true`, { method: "POST" });
      if (!response.ok) throw new Error("reindex failed");
      setArchiveIndex(await response.json() as ArchiveIndexStatus);
      setArchiveIndexMessage(locale === "en" ? "Background catalogue rebuild started." : "已启动后台归档目录重建。 ");
    } catch {
      setArchiveIndexMessage(locale === "en" ? "Unable to start the archive rebuild." : "无法启动归档目录重建。 ");
    }
  });
  const switchPersistence = async () => withPanelOperation(locale === "en" ? "Switching persistence backend…" : "正在切换持久化后端…", async () => {
    try {
      const config = persistenceKind === "sqlite" ? { path: persistenceValue } : persistenceKind === "mysql" ? { url: persistenceValue } : persistenceKind === "d1" ? { endpoint: persistenceValue } : {};
      const response = await fetch(`${API}/api/persistence/switch`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind: persistenceKind, config, migrate: true }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Switch failed.");
      setPersistenceMessage(locale === "en" ? `Switched to ${result.kind}.` : `已切换为 ${result.kind}。`);
    } catch (error) {
      setPersistenceMessage(error instanceof Error ? error.message : (locale === "en" ? "Switch failed." : "切换失败。"));
    }
  });
  const sourcePolicies: { id: SourcePolicyId; label: string; description: string }[] = ["ui-text", "cli-text", "ai-environment", "ai-debug", "background"].map((id) => {
    const [label, description] = sourcePolicyText(locale, id);
    return { id: id as SourcePolicyId, label, description };
  });
  const updateSourcePolicy = (source: SourcePolicyId, patch: Partial<SourcePolicy>) => {
    const next = { ...stimuli.source_policies, [source]: { ...stimuli.source_policies[source], ...patch } };
    if (patch.enabled === false && !Object.values(next).some((policy) => policy.enabled) && !window.confirm(t("sourceCloseWarning"))) return;
    onChange({ ...settings, stimuli: { ...stimuli, source_policies: next } });
  };
  const go = (name: string) => setActive(name);

  return (
    <div className="settings-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="settings-modal" role="dialog" aria-modal="true" aria-label="ThreeMind 设置" onMouseDown={(event) => event.stopPropagation()}>
        <header className="settings-header">
          <div className="settings-header-copy"><small>{locale === "en" ? "THREEMIND WORKSPACE" : "THREEMIND 工作区"}</small><strong>{t("settings")}</strong><span>{locale === "en" ? "Preferences are grouped by responsibility. Saving never changes the associative rules unless a runtime setting explicitly says so." : "设置按职责归类；除非某项明确说明会影响运行时，否则保存不会改变联想网络规则。"}</span></div>
          <button type="button" onClick={onClose} aria-label="关闭设置">×</button>
        </header>
        <div className="settings-body">
          <nav className="settings-nav" aria-label="设置分类">
            {categoryGroups.map((group) => <div className="settings-nav-group" key={group.label}>
              <div className="settings-nav-label">{group.label}</div>
              {group.items.map(([name, label]) => <button key={name} className={active === name ? "active" : ""} type="button" onClick={() => go(name)}>{label}</button>)}
            </div>)}
          </nav>
          <div className="settings-content">
            <section hidden={active !== "visualization"}>
              <h3>{t("displayNavigation")}</h3>
              <p>显示模式只改变同一张拓扑图的观察方式；它不会向 Core 写入空间坐标、距离或方向。</p>
              <div className="view-switch" role="group" aria-label="显示模式">
                <button className={visualization.mode === "3d" ? "active" : ""} type="button" onClick={() => updateVisualization({ mode: "3d" })}>3D 默认</button>
                <button className={visualization.mode === "2d" ? "active" : ""} type="button" onClick={() => updateVisualization({ mode: "2d" })}>2D</button>
              </div>
              <label className="settings-field">渲染器
                <select value={visualization.renderer} onChange={(event) => updateVisualization({ renderer: event.target.value as VisualizationSettings["renderer"] })}>
                  <option value="threejson">{locale === "en" ? "ThreeJSON GPU projection (recommended)" : "ThreeJSON GPU 投影（推荐）"}</option>
                  <option value="three">{locale === "en" ? "Three.js (legacy fallback)" : "Three.js（旧版回退）"}</option>
                  <option value="canvas">{locale === "en" ? "Canvas 2D (classic)" : "Canvas 2D（经典）"}</option>
                </select>
              </label>
              <SettingsDisclosure title={locale === "en" ? "Visual appearance and navigation" : "视觉样式与导航"} description={locale === "en" ? "Node shape, motion and workspace navigation preferences" : "节点形状、视觉动画与工作区导航偏好"}>
                {visualization.renderer === "canvas" ? (
                  <label className="settings-field">经典 2D 节点形状
                    <select value={visualization.canvas_shape} onChange={(event) => updateVisualization({ canvas_shape: event.target.value as CanvasNodeShape })}>
                      <option value="circle">{locale === "en" ? "Circle (original style)" : "圆形（原始风格）"}</option><option value="square">{locale === "en" ? "Square" : "正方形"}</option>
                    </select>
                  </label>
                ) : (
                  <label className="settings-field">{locale === "en" ? "ThreeJSON / Three.js node shape" : "ThreeJSON / Three.js 节点形状"}
                    <select value={visualization.three_shape} onChange={(event) => updateVisualization({ three_shape: event.target.value as ThreeNodeShape })}>
                      <option value="glow">{locale === "en" ? "Glowing point (organic)" : "发光圆点（有机）"}</option><option value="circle">{locale === "en" ? "Soft circle" : "圆形软点"}</option><option value="square">{locale === "en" ? "Soft square" : "正方形软点"}</option><option value="sphere">{locale === "en" ? "Sphere (3D only)" : "球体（仅 3D）"}</option><option value="cube">{locale === "en" ? "Cube (3D only)" : "正方体（仅 3D）"}</option>
                    </select>
                  </label>
                )}
                <label className="settings-field">视觉风格
                  <select value={visualization.style} onChange={(event) => updateVisualization({ style: event.target.value as VisualStyle })}>
                    <option value="organic">{locale === "en" ? "Organic glow (default)" : "有机发光（默认）"}</option><option value="minimal">{locale === "en" ? "Minimal" : "简洁"}</option>
                  </select>
                </label>
                <label className="settings-switch"><input type="checkbox" checked={visualization.continuous_motion} onChange={(event) => updateVisualization({ continuous_motion: event.target.checked })} /> 启用连续力导向动画（仅视觉效果）</label>
                <label className="settings-switch settings-switch-with-help"><input type="checkbox" checked={navigationAutoHide} onChange={(event) => onNavigationAutoHideChange(event.target.checked)} /> {locale === "en" ? "Auto-hide the top navigation" : "自动隐藏顶部导航"}<span className="settings-note">{locale === "en" ? "The navigation remains available from the top edge of the screen. This is a local visual preference only; it never changes Core, adapters, or the running consciousness." : "鼠标移到屏幕上边缘即可临时显示。此项仅保存在当前浏览器的界面偏好中，不会改变 Core、适配器或运行中的意识。"}</span></label>
                <p className="settings-note">默认关闭。关闭时节点位置固定，颜色、大小和连接只随 Core 返回的实际状态更新；开启后会加入前端聚散与漂移，不能将其理解为 Core 内的空间运动。</p>
                <p className="settings-note">滚轮缩放；右键或中键拖动平移；W/A/S/D 移动；F 复位。3D 模式中左键旋转，Q/E 调整观察深度。</p>
              </SettingsDisclosure>
              <SettingsDisclosure title={locale === "en" ? "Archive interaction" : "存档交互"} description={locale === "en" ? "Naming behaviour when taking a snapshot" : "拍摄快照时的命名行为"}>
                <label className="settings-switch"><input type="checkbox" checked={archive.prompt_for_snapshot_name} onChange={(event) => updateArchive({ prompt_for_snapshot_name: event.target.checked })} /> 拍摄快照前要求命名</label>
              </SettingsDisclosure>
            </section>
            <section hidden={active !== "runtime"}>
              <h3>{t("runtimeEnvironment")}</h3>
              <p>右侧控制栏保留相同快捷控制；这里提供集中设置入口。</p>
              <p className="settings-note">模拟速度和背景刺激可继续在右侧直接调整。它们是外部环境参数，不是 Core 的内驱。</p>
              <h3>{t("sourceSensorAttention")}</h3>
              <p className="settings-note">{t("sourceSensorAttentionNote")}</p>
              <div className="source-policy-grid">
                {sourcePolicies.map((source) => <article className="source-policy-card" key={source.id}>
                  <strong>{source.label}</strong><small>{source.description}</small>
                  <label className="settings-switch"><input type="checkbox" checked={stimuli.source_policies[source.id].enabled} onChange={(event) => updateSourcePolicy(source.id, { enabled: event.target.checked })} /> {t("enableSource")}</label>
                  <label className="settings-switch"><input type="checkbox" disabled={!stimuli.source_policies[source.id].enabled} checked={stimuli.source_policies[source.id].bypass_attention} onChange={(event) => updateSourcePolicy(source.id, { bypass_attention: event.target.checked })} /> {t("fullDelivery")}</label>
                </article>)}
              </div>
              <label className="settings-switch"><input type="checkbox" checked={stimuli.submit_on_enter} onChange={(event) => onChange({ ...settings, stimuli: { ...stimuli, submit_on_enter: event.target.checked } })} /> 文本输入框按 Enter 发送（Shift+Enter 换行）</label>
              <SettingsDisclosure title={locale === "en" ? "Chat presentation" : "聊天窗口呈现"} description={locale === "en" ? "Display filters only; no stimulus or record is discarded" : "仅控制显示，不丢弃刺激或日志"}>
                <label className="settings-switch"><input type="checkbox" checked={conversationSettings.show_environment_stimuli} onChange={(event) => onChange({ ...settings, conversation: { ...conversationSettings, show_environment_stimuli: event.target.checked } })} /> 在“刺激”聊天窗口显示环境刺激消息</label>
                <label className="settings-switch"><input type="checkbox" checked={conversationSettings.show_triggering_environment_stimuli} disabled={conversationSettings.show_environment_stimuli} onChange={(event) => onChange({ ...settings, conversation: { ...conversationSettings, show_triggering_environment_stimuli: event.target.checked } })} /> 即使环境消息已隐藏，仍显示触发被动解读的关联刺激</label>
                <label className="settings-switch"><input type="checkbox" checked={conversationSettings.show_background_readouts} onChange={(event) => onChange({ ...settings, conversation: { ...conversationSettings, show_background_readouts: event.target.checked } })} /> 在“刺激”聊天窗口显示背景驱动的被动读出</label>
                <p className="settings-note">这里只过滤聊天窗口的呈现；刺激仍会进入 Core，背景被动读出也会完整保留在被动读出日志中。</p>
              </SettingsDisclosure>
              <p className="settings-note">关闭最后一个来源仍会结束当前意识；界面会要求确认。关闭文本感官适配器则会拒绝所有文本来源，但不影响背景感官。</p>
            </section>
            <section hidden={active !== "body"}>
              <h3>{t("bodyAttention")}</h3>
              <p>背景环境先经躯体采样、阈值、适应和噪声编码，再进入输入总线；注意/竞争门仍在 Core 内选择有限通道。</p>
              <label className="settings-switch"><input type="checkbox" checked={body.enabled} onChange={(event) => updateBody({ enabled: event.target.checked })} /> 启用背景躯体适配器</label>
              <SettingsDisclosure title={locale === "en" ? "Body-sensor parameters" : "躯体感官参数"} description={locale === "en" ? "Sampling, adaptation and sensor noise" : "采样、适应与感官噪声"}>
                <label className="settings-field">背景采样间隔（tick）<input type="number" min="1" max="10000" value={body.sampling_ticks} onChange={(event) => updateBody({ sampling_ticks: Number(event.target.value) })} /></label>
                <label className="settings-field">感官阈值<input type="number" min="0" max="1" step=".005" value={body.threshold} onChange={(event) => updateBody({ threshold: Number(event.target.value) })} /></label>
                <label className="settings-field">背景适应度<input type="number" min="0" max="1" step=".01" value={body.adaptation} onChange={(event) => updateBody({ adaptation: Number(event.target.value) })} /></label>
                <label className="settings-field">感官噪声<input type="number" min="0" max=".5" step=".005" value={body.noise} onChange={(event) => updateBody({ noise: Number(event.target.value) })} /></label>
                <p className="settings-note">这些是身体与传感器的局限，不会识别文字意义，也不会直接修改节点或连接。</p>
              </SettingsDisclosure>
              <h4>{locale === "en" ? "Optional external energy supply" : "可选外部能量供应"}</h4>
              <label className="settings-switch"><input type="checkbox" checked={body.energy_supply.enabled} onChange={(event) => updateBody({ energy_supply: { ...body.energy_supply, enabled: event.target.checked } })} /> {locale === "en" ? "Enable finite metabolic energy adapter" : "启用有限代谢能量适配器"}</label>
              <SettingsDisclosure title={locale === "en" ? "Energy-supply parameters" : "能量供应参数"} description={locale === "en" ? "Only applies when the finite energy adapter is enabled" : "仅在有限能量适配器启用时生效"}>
                <label className="settings-field">{locale === "en" ? "Supply per observed Core tick" : "每个已观测 Core tick 的供应量"}<input type="number" min="0" max="1000000" step=".001" disabled={!body.energy_supply.enabled} value={body.energy_supply.supply_per_tick} onChange={(event) => updateBody({ energy_supply: { ...body.energy_supply, supply_per_tick: Number(event.target.value) } })} /></label>
                <label className="settings-field">{locale === "en" ? "Lifetime supply limit (0 = unlimited)" : "生命周期供应上限（0 表示不设上限）"}<input type="number" min="0" max="1000000000" step=".01" disabled={!body.energy_supply.enabled} value={body.energy_supply.total_supply_limit} onChange={(event) => updateBody({ energy_supply: { ...body.energy_supply, total_supply_limit: Number(event.target.value) } })} /></label>
                <p className="settings-note">{locale === "en" ? "This adapter only supplies the optional energy ledger. It never ranks, filters, or semantically interprets stimuli, and Core has no hidden energy recovery." : "该适配器只向可选能量账本供应有限能量，不排序、不筛选也不解释刺激；Core 内没有隐藏的能量恢复。"}</p>
              </SettingsDisclosure>
            </section>
            <section hidden={active !== "network"}>
              <h3>{t("networkAdapter")}</h3>
              <p>网络层是外部边界适配器，不属于输入/输出总线。它只传递已编码的匿名感官帧和匿名输出帧。</p>
              <label className="settings-switch"><input type="checkbox" checked={network.enabled} onChange={(event) => updateNetwork({ enabled: event.target.checked })} /> 启用网络适配器</label>
              <SettingsDisclosure title={locale === "en" ? "Connection and protocol parameters" : "连接与协议参数"} description={locale === "en" ? "Authentication, modulation and output cadence" : "认证、远程调制与输出节奏"}>
                <label className="settings-field">共享认证令牌<input type="password" value={networkToken} onChange={(event) => setNetworkToken(event.target.value)} placeholder={network.token_configured ? "已配置；留空保持不变" : "至少 16 个字符"} /></label>
                <label className="settings-switch"><input type="checkbox" checked={network.allow_remote_modulation} disabled={!network.enabled} onChange={(event) => updateNetwork({ allow_remote_modulation: event.target.checked })} /> 允许受限远程生理调制</label>
                <label className="settings-field">远程调制超时（tick）<input type="number" min="1" max="1000000" disabled={!network.allow_remote_modulation} value={network.modulation_timeout_ticks} onChange={(event) => updateNetwork({ modulation_timeout_ticks: Number(event.target.value) })} /></label>
                <label className="settings-field">输出推送检查间隔（ms）<input type="number" min="20" max="10000" value={network.output_interval_ms} onChange={(event) => updateNetwork({ output_interval_ms: Number(event.target.value) })} /></label>
                <p className="settings-note">协议：{network.protocol ?? "threemind-network/1"}。网络输入只允许匿名通道；远程调制只能改变整体增益和注意预算，不能修改节点、连接或发送语义命令。</p>
              </SettingsDisclosure>
              <button type="button" disabled={Boolean(panelOperation)} onClick={() => void saveNetworkSettings()}>{panelOperation ? "正在处理…" : "保存网络设置"}</button>
              {networkMessage && <p className="settings-note">{networkMessage}</p>}
            </section>
            <section hidden={active !== "model"}>
              <h3>{t("modelSpace")}</h3>
              <p>这些参数属于当前模型实例，由 Core 的通用模型配置 API 修改；前端只提供操作入口。</p>
              {modelLoading ? <p className="settings-note">{locale === "en" ? "Loading current model…" : "正在读取当前模型…"}</p> : !modelInfo ? <p className="settings-note">{modelMessage || (locale === "en" ? "No consciousness is currently running." : "当前没有运行中的意识。")}</p> : <>
                <SettingsDisclosure title={locale === "en" ? "Spatial basis" : "空间基底"} description={locale === "en" ? "Dimensions, neighbourhood and spatial competition" : "维数、邻域与空间竞争"}>
                <label className="settings-field">空间基底
                  <input value={modelInfo.manifest.spatial_embedding ? "已启用" : "未启用（需创建空间模型）"} disabled />
                </label>
                <label className="settings-field">空间维数
                  <input type="number" min="2" max="32" disabled={!modelInfo.manifest.spatial_embedding} value={modelInfo.manifest.spatial_dimensions ?? 3} onChange={(event) => setModelInfo({ ...modelInfo, manifest: { ...modelInfo.manifest, spatial_dimensions: Number(event.target.value) } })} />
                </label>
                <label className="settings-field">空间邻域半径
                  <input type="number" min=".01" max="10" step=".05" disabled={!modelInfo.manifest.spatial_embedding} value={Number(modelInfo.manifest.parameters?.spatial_radius ?? 1)} onChange={(event) => setModelInfo({ ...modelInfo, manifest: { ...modelInfo.manifest, parameters: { ...modelInfo.manifest.parameters, spatial_radius: Number(event.target.value) } } })} />
                </label>
                <label className="settings-field">空间竞争强度
                  <input type="number" min="0" max="1" step=".01" disabled={!modelInfo.manifest.spatial_embedding} value={Number(modelInfo.manifest.parameters?.spatial_competition ?? 0)} onChange={(event) => setModelInfo({ ...modelInfo, manifest: { ...modelInfo.manifest, parameters: { ...modelInfo.manifest.parameters, spatial_competition: Number(event.target.value) } } })} />
                </label>
                <label className="settings-switch"><input type="checkbox" disabled={!modelInfo.manifest.spatial_embedding} checked={Boolean(modelInfo.manifest.parameters?.neighborhood_enabled ?? true)} onChange={(event) => setModelInfo({ ...modelInfo, manifest: { ...modelInfo.manifest, parameters: { ...modelInfo.manifest.parameters, neighborhood_enabled: event.target.checked } } })} /> 启用空间邻域对连接形成和传播的约束</label>
                </SettingsDisclosure>
                <SettingsDisclosure title={locale === "en" ? "Association, forgetting and homeostasis" : "关联、遗忘与稳态"} description={locale === "en" ? "Environmental competition and the optional legacy global clamp" : "环境竞争与可选的旧式全局稳态钳制"}>
                <h4>关联、遗忘与生命循环</h4>
                <label className="settings-switch"><input type="checkbox" checked={Boolean(modelInfo.manifest.parameters?.attention_competition_enabled ?? modelInfo.runtime_config?.attention_competition_enabled ?? false)} onChange={(event) => setModelInfo({ ...modelInfo, manifest: { ...modelInfo.manifest, parameters: { ...modelInfo.manifest.parameters, attention_competition_enabled: event.target.checked } } })} /> 启用环境竞争门（默认关闭；关闭时所有已编码通道透明进入网络）</label>
                <p className="settings-note">{locale === "en" ? "Attention capacity is used only by the environmental competition gate. Relevance and novelty remain local graph properties; the energy subsystem never ranks stimuli." : "注意容量仅在启用环境竞争门时生效。相关性与新颖度仍由局部连接规则处理；能量子系统绝不排序刺激。"}</p>
                <label className="settings-switch"><input type="checkbox" checked={Boolean(modelInfo.manifest.parameters?.homeostasis_enabled ?? modelInfo.runtime_config?.homeostasis_enabled ?? false)} onChange={(event) => updateModelParameter("homeostasis_enabled", event.target.checked)} /> {locale === "en" ? "Enable legacy global activation clamp" : "启用旧式全局稳态钳制"}</label>
                <p className="settings-note">{locale === "en" ? "Legacy comparison mechanism, disabled by default. It rescales total activation and therefore changes network dynamics when explicitly enabled." : "旧式对照机制，默认关闭。显式开启后会缩放网络总激活量，因此会改变网络动力学。"}</p>
                {modelNumberField("target_total_activation", locale === "en" ? "Global activation target" : "稳态总激活", .01, 1000000, .1, !Boolean(modelInfo.manifest.parameters?.homeostasis_enabled ?? modelInfo.runtime_config?.homeostasis_enabled ?? false))}
                </SettingsDisclosure>
                <SettingsDisclosure title={locale === "en" ? "Topology-local inhibition" : "拓扑局部抑制"} description={locale === "en" ? "Local generation, diffusion and decay" : "局部生成、扩散与衰减"}>
                <h4>{locale === "en" ? "Topology-local inhibition" : "拓扑局部抑制"}</h4>
                <label className="settings-switch"><input type="checkbox" checked={Boolean(modelInfo.manifest.parameters?.topology_inhibition_enabled ?? modelInfo.runtime_config?.topology_inhibition_enabled ?? true)} onChange={(event) => updateModelParameter("topology_inhibition_enabled", event.target.checked)} /> {locale === "en" ? "Enable local inhibition (default on)" : "启用局部抑制（默认开启）"}</label>
                <p className="settings-note">{locale === "en" ? "Excitatory edges remain directed. Inhibition uses undirected physical adjacency, finite branch-conserving diffusion and delayed shunting response." : "兴奋边仍保持有向；抑制使用无向物理邻接、分支守恒的有限扩散和延迟分流式响应。"}</p>
                <div className="model-parameter-grid">
                  {modelNumberField("inhibition_generation_gain", locale === "en" ? "Inhibition generation gain" : "抑制生成增益", 0, 10, .01, !Boolean(modelInfo.manifest.parameters?.topology_inhibition_enabled ?? modelInfo.runtime_config?.topology_inhibition_enabled ?? true))}
                  {modelNumberField("inhibition_decay", locale === "en" ? "Inhibition decay" : "抑制衰减", 0, 1, .01, !Boolean(modelInfo.manifest.parameters?.topology_inhibition_enabled ?? modelInfo.runtime_config?.topology_inhibition_enabled ?? true))}
                  {modelNumberField("inhibition_diffusion", locale === "en" ? "Inhibition diffusion" : "抑制扩散比例", 0, 1, .01, !Boolean(modelInfo.manifest.parameters?.topology_inhibition_enabled ?? modelInfo.runtime_config?.topology_inhibition_enabled ?? true))}
                  {modelNumberField("inhibition_response_gain", locale === "en" ? "Response attenuation gain" : "响应抑制增益", 0, 100, .05, !Boolean(modelInfo.manifest.parameters?.topology_inhibition_enabled ?? modelInfo.runtime_config?.topology_inhibition_enabled ?? true))}
                  {modelNumberField("inhibition_saturation", locale === "en" ? "Inhibition saturation" : "抑制饱和值", .000001, 1000000, .01, !Boolean(modelInfo.manifest.parameters?.topology_inhibition_enabled ?? modelInfo.runtime_config?.topology_inhibition_enabled ?? true))}
                  {modelNumberField("inhibition_propagation_min", locale === "en" ? "Minimum propagated inhibition" : "最小传播抑制", 0, 1000000, .001, !Boolean(modelInfo.manifest.parameters?.topology_inhibition_enabled ?? modelInfo.runtime_config?.topology_inhibition_enabled ?? true))}
                </div>
                </SettingsDisclosure>
                <SettingsDisclosure title={locale === "en" ? "Experimental energy accounting" : "实验性能量记账"} description={locale === "en" ? "Optional accounting and irreversible starvation behaviour" : "可选能量账本与不可逆饥饿行为"}>
                <h4>{locale === "en" ? "Experimental energy accounting" : "实验性能量记账"}</h4>
                <label className="settings-switch"><input type="checkbox" checked={Boolean(modelInfo.manifest.parameters?.energy_simulation_enabled ?? modelInfo.runtime_config?.energy_simulation_enabled ?? false)} onChange={(event) => updateModelParameter("energy_simulation_enabled", event.target.checked)} /> {locale === "en" ? "Enable energy simulation (default off)" : "启用能量模拟（默认关闭）"}</label>
                <label className="settings-switch"><input type="checkbox" disabled={!Boolean(modelInfo.manifest.parameters?.energy_simulation_enabled ?? modelInfo.runtime_config?.energy_simulation_enabled ?? false)} checked={Boolean(modelInfo.manifest.parameters?.irreversible_energy_death_enabled ?? modelInfo.runtime_config?.irreversible_energy_death_enabled ?? false)} onChange={(event) => updateModelParameter("irreversible_energy_death_enabled", event.target.checked)} /> {locale === "en" ? "Enable irreversible starvation death (default off)" : "启用不可逆饥饿死亡（默认关闭）"}</label>
                <p className="settings-note">{locale === "en" ? "There is no internal recovery rule. External supply is controlled independently in Adapter Management." : "系统不存在内部恢复规则；外部供应需在“适配器管理”中独立启用。"}</p>
                <div className="model-parameter-grid">
                  {modelNumberField("energy_initial_reserve", locale === "en" ? "Initial reserve" : "初始能量储备", 0, 1000000000, .01, !Boolean(modelInfo.manifest.parameters?.energy_simulation_enabled ?? modelInfo.runtime_config?.energy_simulation_enabled ?? false))}
                  {modelNumberField("energy_capacity", locale === "en" ? "Reserve capacity" : "能量容量", .000001, 1000000000, .01, !Boolean(modelInfo.manifest.parameters?.energy_simulation_enabled ?? modelInfo.runtime_config?.energy_simulation_enabled ?? false))}
                  {modelNumberField("energy_direct_cost", locale === "en" ? "Direct activation cost" : "直接激活成本", 0, 1000000, .001, !Boolean(modelInfo.manifest.parameters?.energy_simulation_enabled ?? modelInfo.runtime_config?.energy_simulation_enabled ?? false))}
                  {modelNumberField("energy_associative_cost", locale === "en" ? "Associative propagation cost" : "联想传播成本", 0, 1000000, .001, !Boolean(modelInfo.manifest.parameters?.energy_simulation_enabled ?? modelInfo.runtime_config?.energy_simulation_enabled ?? false))}
                  {modelNumberField("energy_inhibition_cost", locale === "en" ? "Inhibitory diffusion cost" : "抑制扩散成本", 0, 1000000, .001, !Boolean(modelInfo.manifest.parameters?.energy_simulation_enabled ?? modelInfo.runtime_config?.energy_simulation_enabled ?? false))}
                  {modelNumberField("energy_maintenance_cost_per_node", locale === "en" ? "Node maintenance cost" : "节点维持成本", 0, 1000000, .000001, !Boolean(modelInfo.manifest.parameters?.irreversible_energy_death_enabled ?? modelInfo.runtime_config?.irreversible_energy_death_enabled ?? false))}
                  {modelNumberField("energy_maintenance_cost_per_edge", locale === "en" ? "Edge maintenance cost" : "连接维持成本", 0, 1000000, .000001, !Boolean(modelInfo.manifest.parameters?.irreversible_energy_death_enabled ?? modelInfo.runtime_config?.irreversible_energy_death_enabled ?? false))}
                  {modelNumberField("energy_starvation_structural_decay", locale === "en" ? "Starvation structural decay" : "饥饿结构衰减", 0, 1, .001, !Boolean(modelInfo.manifest.parameters?.irreversible_energy_death_enabled ?? modelInfo.runtime_config?.irreversible_energy_death_enabled ?? false))}
                  {modelNumberField("energy_starvation_death_ticks", locale === "en" ? "Starvation death window (ticks)" : "饥饿死亡窗口（tick）", 1, 10000000, 1, !Boolean(modelInfo.manifest.parameters?.irreversible_energy_death_enabled ?? modelInfo.runtime_config?.irreversible_energy_death_enabled ?? false))}
                </div>
                </SettingsDisclosure>
                <SettingsDisclosure title={locale === "en" ? "Advanced plasticity and optional limits" : "高级可塑性与可选边界"} description={locale === "en" ? "Edge birth, learning, consolidation, forgetting and explicitly enabled limits" : "新边形成、学习、固化、遗忘与显式启用的边界"}>
                <label className="settings-field">新边形成策略
                  <select value={String(modelInfo.manifest.parameters?.edge_birth_policy ?? modelInfo.runtime_config?.edge_birth_policy ?? "local-coactivation")} onChange={(event) => setModelInfo({ ...modelInfo, manifest: { ...modelInfo.manifest, parameters: { ...modelInfo.manifest.parameters, edge_birth_policy: event.target.value } } })}>
                    <option value="local-coactivation">{edgeBirthPolicyText(locale, "local-coactivation")}</option>
                    <option value="temporal-association">{edgeBirthPolicyText(locale, "temporal-association")}</option>
                  </select>
                </label>
                <div className="model-parameter-grid">
                  {([
                    ["edge_adaptation_limit", "每 tick 边适应预算", 1, 1],
                    ["propagation_limit", "每 tick 传播预算", 1, 1],
                    ["edge_birth_activation_product_min", "候选边最小共激活", 0, .001],
                    ["propagation_activation_min", "最小传播激活", 0, .001],
                    ["max_nodes", "最大节点数", 1, 1],
                    ["max_edges", "最大连接数", 1, 1],
                  ] as const).map(([key, label, min, step]) => {
                    const enabled = modelInfo.manifest.parameters?.[key] != null;
                    const value = Number(modelInfo.manifest.parameters?.[key] ?? min);
                    return <label className="settings-field" key={key}><span className="settings-inline"><input type="checkbox" checked={enabled} onChange={(event) => setModelInfo({ ...modelInfo, manifest: { ...modelInfo.manifest, parameters: { ...modelInfo.manifest.parameters, [key]: event.target.checked ? value : null } } })} /> 启用{label}</span><input type="number" min={min} step={step} disabled={!enabled} value={value} onChange={(event) => setModelInfo({ ...modelInfo, manifest: { ...modelInfo.manifest, parameters: { ...modelInfo.manifest.parameters, [key]: Number(event.target.value) } } })} /></label>;
                  })}
                  {([
                    ["attention_budget", "环境竞争容量", 1, 100000, 1],
                    ["association_window", "跨时联想窗口", 1, 10000, 1],
                    ["activation_decay", "激活衰减", 0, 1, 0.01],
                    ["propagation_gain", "联想传播增益", 0, 4, 0.01],
                    ["learning_rate", "连接学习率", 0, 1, 0.001],
                    ["edge_decay", "遗忘速率", 0, 1, 0.0001],
                    ["stability_gain", "固化增益", 0, 1, 0.001],
                    ["stability_decay", "固化衰减", 0, 1, 0.0001],
                    ["consolidation_first_gain", "首次触达固化增益", 0, 1, 0.001],
                    ["consolidation_repeat_gain", "重复触达固化增益", 0, 1, 0.001],
                    ["consolidation_associative_gain", "联想触达固化增益", 0, 1, 0.001],
                    ["consolidation_intensity_gain", "强刺激固化增益", 0, 1, 0.001],
                    ["local_novelty_gain", "局部新颖连接增益", 0, 1, 0.001],
                    ["novelty_touch_reference", "新颖触达参考值", 0.000001, 1, 0.001],
                    ["consolidation_cap", "单次固化上限", 0, 1, 0.01],
                    ["node_support_gain", "节点存在支持增益", 0, 1, 0.001],
                    ["node_support_decay", "节点存在支持衰减", 0, 1, 0.0001],
                    ["node_support_prune_threshold", "节点消退阈值", 0, 1, 0.001],
                    ["node_prune_after", "无连接节点保留（tick）", 1, 10000000, 1],
                    ["sensory_channels", "文本感官通道数", 32, 8192, 1],
                    ["unresponsive_window", "无响应死亡窗口", 2, 10000000, 1],
                  ] as const).map(([key, label, min, max, step]) => <label className="settings-field" key={key}>{label}
                    <input type="number" min={min} max={max} step={step} value={Number(modelInfo.manifest.parameters?.[key] ?? modelInfo.runtime_config?.[key] ?? 0)} onChange={(event) => setModelInfo({ ...modelInfo, manifest: { ...modelInfo.manifest, parameters: { ...modelInfo.manifest.parameters, [key]: Number(event.target.value) } } })} />
                  </label>)}
                </div>
                </SettingsDisclosure>
                <button type="button" disabled={Boolean(panelOperation)} onClick={() => void applyModelParameters()}>{panelOperation ? "正在处理…" : "应用模型参数"}</button>
                {modelMessage && <p className="settings-note">{modelMessage}</p>}
              </>}
            </section>
            <section hidden={active !== "ai"}>
              <h3>{locale === "en" ? "AI providers" : "AI 供应商"}</h3>
              <p>{locale === "en" ? "Manage reusable model endpoints and credentials here. Environment generation and interpretation are configured separately." : "在这里统一管理可复用的模型端点与凭据。环境刺激和意识解读在独立分类中选择这些供应商。"}</p>
              <div className="provider-list">
                {ai.providers.map((provider, index) => {
                  const updateProvider = (patch: Partial<AiProvider>) => {
                    setProviderTestResults((previous) => {
                      if (!(provider.id in previous)) return previous;
                      const next = { ...previous };
                      delete next[provider.id];
                      return next;
                    });
                    updateAi({ providers: ai.providers.map((item, current) => current === index ? { ...item, ...patch } : item) });
                  };
                  const testResult = providerTestResults[provider.id];
                  return <SettingsDisclosure key={provider.id} title={provider.name || `${locale === "en" ? "Provider" : "供应商"} ${index + 1}`} description={`${providerKindText(locale, provider.kind)} · ${provider.model || (locale === "en" ? "model not specified" : "未指定模型")}`} defaultOpen={ai.providers.length === 1}>
                    <div className="provider-card">
                    <div className="provider-card-header"><strong>供应商 {index + 1}</strong><button className="danger" type="button" onClick={() => updateAi({ providers: ai.providers.filter((_, current) => current !== index) })}>删除</button></div>
                    <label className="settings-field">名称<input value={provider.name} onChange={(e) => updateProvider({ name: e.target.value })} placeholder="例如：OpenAI 主账号" /></label>
                    <label className="settings-field">{locale === "en" ? "Provider type" : "供应商类型"}<select value={provider.kind} onChange={(e) => updateProvider({ kind: e.target.value as AiProvider["kind"] })}><option value="openai">{providerKindText(locale, "openai")}</option><option value="deepseek">{providerKindText(locale, "deepseek")}</option><option value="openai-compatible">{providerKindText(locale, "openai-compatible")}</option></select></label>
                    <label className="settings-field">Base URL<input value={provider.base_url} onChange={(e) => updateProvider({ base_url: e.target.value })} placeholder="https://api.openai.com/v1" /></label>
                    <label className="settings-field">模型（可选）<input value={provider.model} onChange={(e) => updateProvider({ model: e.target.value })} placeholder="gpt-4o-mini" /></label>
                    <label className="settings-field">API Key<input type="password" value={provider.api_key ?? ""} onChange={(e) => updateProvider({ api_key: e.target.value })} placeholder={provider.api_key_configured ? "已配置；留空则保持不变" : "sk-..."} /></label>
                    <button type="button" disabled={testResult?.state === "testing"} onClick={() => void testProvider(provider)}>{testResult?.state === "testing" ? t("providerTesting") : t("providerTest")}</button>
                    {testResult && <p className={`provider-test-result ${testResult.state}`} aria-live="polite">{testResult.message}</p>}
                    </div>
                  </SettingsDisclosure>;
                })}
              </div>
              <button type="button" onClick={() => updateAi({ providers: [...ai.providers, { id: `provider-${Date.now()}`, name: "新供应商", kind: "openai-compatible", base_url: "", model: "", api_key: "" }] })}>添加供应商</button>
            </section>
            <section hidden={active !== "automation"}>
              <h3>{locale === "en" ? "AI stimuli & consciousness interpretation" : "AI 刺激与意识解读"}</h3>
              <p>{locale === "en" ? "The generator enters Core only as an external stimulus. The interpreter is read-only and never writes into the network." : "AI 生成器只作为外界刺激进入 Core；意识解读器只读观测与事件，绝不向网络写回。"}</p>
              <SettingsDisclosure title={locale === "en" ? "AI environment-stimulus generator" : "AI 环境刺激生成器"} description={ai.environment.enabled ? (locale === "en" ? "Enabled" : "已启用") : (locale === "en" ? "Disabled" : "已关闭")} defaultOpen>
              <label className="settings-switch"><input type="checkbox" checked={ai.environment.enabled} onChange={(e) => updateAi({ environment: { ...ai.environment, enabled: e.target.checked } })} /> 启用 AI 环境刺激生成器</label>
              <label className="settings-field">{locale === "en" ? "Ambient-stimulus provider" : "环境刺激供应商"}<select value={ai.environment.provider_id} onChange={(e) => updateAi({ environment: { ...ai.environment, provider_id: e.target.value } })}><option value="">{locale === "en" ? "Select provider" : "请选择供应商"}</option>{ai.providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name || provider.id}（{providerKindText(locale, provider.kind)}）</option>)}</select></label>
              <label className="settings-switch"><input type="checkbox" checked={ai.environment.random_frequency ?? true} onChange={(e) => updateAi({ environment: { ...ai.environment, random_frequency: e.target.checked } })} /> 随机环境刺激频率</label>
              <label className="settings-field">{ai.environment.random_frequency ?? true ? "平均环境频率（tick，随机范围约为 0.5×–1.5×）" : "固定环境频率（tick）"}<input type="number" min="10" value={ai.environment.frequency_ticks} onChange={(e) => updateAi({ environment: { ...ai.environment, frequency_ticks: Number(e.target.value) } })} /></label>
              <label className="settings-field">刺激强度<input type="range" min=".05" max="2" step=".05" value={ai.environment.intensity} onChange={(e) => updateAi({ environment: { ...ai.environment, intensity: Number(e.target.value) } })} /></label>
              <label className="settings-field">不规律比例<input type="range" min="0" max="1" step=".05" value={ai.environment.irregularity} onChange={(e) => updateAi({ environment: { ...ai.environment, irregularity: Number(e.target.value) } })} /></label>
              </SettingsDisclosure>
              <SettingsDisclosure title={locale === "en" ? "AI consciousness interpreter" : "AI 意识解读器"} description={ai.interpreter.enabled ? (locale === "en" ? "Enabled" : "已启用") : (locale === "en" ? "Disabled" : "已关闭")}>
              <label className="settings-switch"><input type="checkbox" checked={ai.interpreter.enabled} onChange={(e) => updateAi({ interpreter: { ...ai.interpreter, enabled: e.target.checked } })} /> 启用被动意识解读器</label>
              <label className="settings-field">{locale === "en" ? "Interpretation provider" : "意识解读供应商"}<select value={ai.interpreter.provider_id} onChange={(e) => updateAi({ interpreter: { ...ai.interpreter, provider_id: e.target.value } })}><option value="">{locale === "en" ? "Select provider" : "请选择供应商"}</option>{ai.providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name || provider.id}（{providerKindText(locale, provider.kind)}）</option>)}</select></label>
              <label className="settings-switch"><input type="checkbox" checked={ai.interpreter.periodic_enabled} onChange={(e) => updateAi({ interpreter: { ...ai.interpreter, periodic_enabled: e.target.checked } })} /> 启用定时解读（默认）</label>
              <label className="settings-field">定时解读频率（tick）<input type="number" min="20" disabled={!ai.interpreter.periodic_enabled} value={ai.interpreter.frequency_ticks} onChange={(e) => updateAi({ interpreter: { ...ai.interpreter, frequency_ticks: Number(e.target.value) } })} /></label>
              <label className="settings-switch"><input type="checkbox" checked={ai.interpreter.on_repeatable_structure} onChange={(e) => updateAi({ interpreter: { ...ai.interpreter, on_repeatable_structure: e.target.checked } })} /> 检测到重复结构时立即额外 AI 解读</label>
              <label className="settings-switch"><input type="checkbox" checked={ai.interpreter.active_nodes_enabled} onChange={(e) => updateAi({ interpreter: { ...ai.interpreter, active_nodes_enabled: e.target.checked } })} /> 在重复结构解读中附加激活节点（按激活度降序）</label>
              <label className="settings-switch"><input type="checkbox" checked={ai.interpreter.on_manual_stimulus} onChange={(e) => updateAi({ interpreter: { ...ai.interpreter, on_manual_stimulus: e.target.checked } })} /> 文本输入刺激后立即解读激活节点</label>
              <label className="settings-switch"><input type="checkbox" checked={ai.interpreter.listen_background_active_nodes} onChange={(e) => updateAi({ interpreter: { ...ai.interpreter, listen_background_active_nodes: e.target.checked } })} /> 监听背景激活节点</label>
              <label className="settings-switch"><input type="checkbox" checked={ai.interpreter.deduplicate_readouts} onChange={(e) => updateAi({ interpreter: { ...ai.interpreter, deduplicate_readouts: e.target.checked } })} /> 被动解读严格去重（默认关闭）</label>
              <label className="settings-field">统计激活下限<input type="number" min="0" max="1" step=".01" disabled={!ai.interpreter.active_nodes_enabled} value={ai.interpreter.activation_min} onChange={(e) => updateAi({ interpreter: { ...ai.interpreter, activation_min: Number(e.target.value) } })} /></label>
              <label className="settings-field">统计激活上限<input type="number" min="0" max="1" step=".01" disabled={!ai.interpreter.active_nodes_enabled} value={ai.interpreter.activation_max} onChange={(e) => updateAi({ interpreter: { ...ai.interpreter, activation_max: Number(e.target.value) } })} /></label>
              </SettingsDisclosure>
              <SettingsDisclosure title={locale === "en" ? "Automatic snapshots" : "自动快照"} description={ai.auto_snapshot.enabled ? (locale === "en" ? "Enabled" : "已启用") : (locale === "en" ? "Disabled" : "已关闭")}>
              <label className="settings-switch"><input type="checkbox" checked={ai.auto_snapshot.enabled} onChange={(e) => updateAi({ auto_snapshot: { ...ai.auto_snapshot, enabled: e.target.checked } })} /> 启用自动快照</label>
              <p className="settings-note">{ai.auto_snapshot.enabled ? "自动快照总开关已开启：仅下方已勾选的规则会创建标注为“自动”的快照。" : "自动快照总开关已关闭：无论下方规则如何设置，系统都不会自动拍摄快照；手动快照和停止时的遗照不受此开关影响。"}</p>
              <label className="settings-field">定时快照频率（tick；0 为关闭）<input type="number" min="0" value={ai.auto_snapshot.frequency_ticks} onChange={(e) => updateAi({ auto_snapshot: { ...ai.auto_snapshot, frequency_ticks: Number(e.target.value) } })} /></label>
              <label className="settings-switch"><input type="checkbox" checked={ai.auto_snapshot.on_repeatable_structure} onChange={(e) => updateAi({ auto_snapshot: { ...ai.auto_snapshot, on_repeatable_structure: e.target.checked } })} /> 重复结构出现时立即快照</label>
              <label className="settings-switch"><input type="checkbox" checked={ai.auto_snapshot.on_interpreter_important} onChange={(e) => updateAi({ auto_snapshot: { ...ai.auto_snapshot, on_interpreter_important: e.target.checked } })} /> 解读器报告重要事件时立即快照</label>
              </SettingsDisclosure>
            </section>
            <section hidden={active !== "observer"}>
              <h3>{locale === "en" ? "Observation, readout & records" : "观测、读出与记录"}</h3>
              <p>{locale === "en" ? "Passive readout and detailed dynamics are two different read-only observation paths. Neither writes information back into Core." : "被动读出与详细动力学记录是两条不同的只读观测路径；二者都不会向 Core 写回信息。"}</p>
              <div className="settings-feature-card">
                <div><strong>{locale === "en" ? "Detailed dynamics trace" : "详细动力学记录"}</strong><small>{locale === "en" ? "Records a full initial keyframe and sparse per-tick node/edge changes for the current consciousness. This is immediate runtime state, not a saved interface preference." : "为当前意识记录初始完整关键帧，以及逐 tick 的节点/连接稀疏变化。这是即时运行状态，不是普通界面偏好。"}</small></div>
                <label className="settings-switch"><input type="checkbox" checked={traceEnabled} disabled={!traceAvailable || Boolean(panelOperation)} onChange={(event) => void onTraceChange(event.target.checked)} /> {traceEnabled ? (locale === "en" ? "Recording" : "正在记录") : (locale === "en" ? "Start recording" : "开始记录")}</label>
              </div>
              {!traceAvailable && <p className="settings-note">{locale === "en" ? "Create or open a running consciousness before enabling dynamics recording." : "请先新建或打开一个运行中的意识，再开启动力学记录。"}</p>}
              <h4>{locale === "en" ? "Passive readout modes" : "被动读出模式"}</h4>
              <SettingsDisclosure title={locale === "en" ? "Single-tick snapshot readout" : "单 tick 截面读出"} description={observer.snapshot_enabled ? (locale === "en" ? "Enabled · preserves the original structural reader" : "已启用 · 保留原有结构读出逻辑") : (locale === "en" ? "Disabled" : "已关闭")} defaultOpen>
              <label className="settings-switch"><input type="checkbox" checked={observer.snapshot_enabled} onChange={(event) => updateObserver({ snapshot_enabled: event.target.checked })} /> {locale === "en" ? "Enable single-tick snapshot readout" : "启用单 tick 截面读出"}</label>
              <div aria-disabled={!observer.snapshot_enabled}>
              <label className="settings-switch"><input type="checkbox" checked={observer.read_touched_activity} onChange={(event) => updateObserver({ read_touched_activity: event.target.checked })} /> {locale === "en" ? "Record direct and associative touch activity" : "记录直接与联想触达的活动节点"}</label>
              <label className="settings-switch"><input type="checkbox" checked={observer.repeatable_structure_readout} onChange={(event) => updateObserver({ repeatable_structure_readout: event.target.checked })} /> {locale === "en" ? "Immediately emit a passive readout when a repeatable structure is detected" : "检测到可重复结构时立即记录被动读出"}</label>
              <label className="settings-switch"><input type="checkbox" checked={observer.label_sort_by_activation} onChange={(event) => updateObserver({ label_sort_by_activation: event.target.checked })} /> {locale === "en" ? "Order readable labels by activation strength" : "明文标签按激活强度排序"}</label>
              <SettingsDisclosure title={locale === "en" ? "Readout and repeat-detection thresholds" : "读出与重复结构判定参数"} description={locale === "en" ? "Advanced thresholds; normal use rarely requires changing them" : "高级阈值；常规使用通常无需调整"}>
                <label className="settings-field">{locale === "en" ? "Readable-label display limit (0 = no truncation)" : "明文标签显示上限（0 为不截断）"}<input type="number" min="0" value={observer.label_display_limit} onChange={(event) => updateObserver({ label_display_limit: Math.max(0, Number(event.target.value)) })} /></label>
                <label className="settings-field">{locale === "en" ? "Structural activation threshold" : "重复结构激活阈值"}<input type="number" min="0" max="1" step=".001" value={observer.activation_threshold} onChange={(event) => updateObserver({ activation_threshold: Math.max(0, Math.min(1, Number(event.target.value))) })} /></label>
                <label className="settings-field">{locale === "en" ? "Structural candidate-node limit" : "重复结构候选节点上限"}<input type="number" min="3" value={observer.max_nodes} onChange={(event) => updateObserver({ max_nodes: Math.max(3, Number(event.target.value)) })} /></label>
                <label className="settings-field">最低重复次数<input type="number" min="2" value={observer.min_occurrences} onChange={(event) => updateObserver({ min_occurrences: Number(event.target.value) })} /></label>
                <label className="settings-field">重复窗口（tick）<input type="number" min="10" value={observer.recurrence_window_ticks} onChange={(event) => updateObserver({ recurrence_window_ticks: Number(event.target.value) })} /></label>
                <label className="settings-field">最少候选节点<input type="number" min="2" value={observer.min_nodes} onChange={(event) => updateObserver({ min_nodes: Number(event.target.value) })} /></label>
                <label className="settings-field">最少内部连接<input type="number" min="1" value={observer.min_internal_edges} onChange={(event) => updateObserver({ min_internal_edges: Number(event.target.value) })} /></label>
                <label className="settings-field">提醒冷却（tick）<input type="number" min="10" value={observer.alert_cooldown_ticks} onChange={(event) => updateObserver({ alert_cooldown_ticks: Number(event.target.value) })} /></label>
              </SettingsDisclosure>
              </div>
              </SettingsDisclosure>

              <SettingsDisclosure title={locale === "en" ? "Temporal-window convergence readout" : "时间区间收敛读出"} description={temporal.enabled ? (locale === "en" ? "Enabled · stimulus-anchored multi-tick observation" : "已启用 · 以刺激为锚点观测多个 tick") : (locale === "en" ? "Disabled" : "已关闭")}>
                <label className="settings-switch"><input type="checkbox" checked={temporal.enabled} onChange={(event) => updateTemporal({ enabled: event.target.checked })} /> {locale === "en" ? "Enable temporal-window readout" : "启用时间区间读出"}</label>
                <p className="settings-note">{locale === "en" ? "This reader subtracts a pre-stimulus baseline, then records duration, activation integral, inhibition and convergence. It never feeds a result back into Core." : "该读出器扣除刺激前基线，再统计持续时间、激活积分、抑制与收敛；结果绝不写回 Core。"}</p>
                <div className="settings-grid">
                  <label className="settings-switch"><input type="checkbox" checked={temporal.trigger_manual} onChange={(event) => updateTemporal({ trigger_manual: event.target.checked })} /> {locale === "en" ? "Observe manual text stimuli" : "观测人工文本刺激"}</label>
                  <label className="settings-switch"><input type="checkbox" checked={temporal.trigger_ai} onChange={(event) => updateTemporal({ trigger_ai: event.target.checked })} /> {locale === "en" ? "Observe AI stimuli" : "观测 AI 刺激"}</label>
                  <label className="settings-switch"><input type="checkbox" checked={temporal.trigger_ambient} onChange={(event) => updateTemporal({ trigger_ambient: event.target.checked })} /> {locale === "en" ? "Observe ambient stimuli" : "观测背景刺激"}</label>
                  <label className="settings-switch"><input type="checkbox" checked={temporal.consider_activation_strength} onChange={(event) => updateTemporal({ consider_activation_strength: event.target.checked })} /> {locale === "en" ? "Include activation strength in composite ranking" : "综合排序时考虑激活强度"}</label>
                </div>
                <label className="settings-field">{locale === "en" ? "Default ranking" : "默认排序方式"}<select value={temporal.ranking_mode} onChange={(event) => updateTemporal({ ranking_mode: event.target.value as TemporalReadoutSettings["ranking_mode"] })}><option value="composite">{locale === "en" ? "Composite evidence" : "综合证据"}</option><option value="duration">{locale === "en" ? "Activation duration" : "激活持续时间"}</option><option value="activation-integral">{locale === "en" ? "Activation integral" : "激活积分"}</option></select></label>
                <label className="settings-field">{locale === "en" ? "Candidate nodes" : "候选节点范围"}<select value={temporal.candidate_scope} onChange={(event) => updateTemporal({ candidate_scope: event.target.value as TemporalReadoutSettings["candidate_scope"] })}><option value="associative-or-persistent">{locale === "en" ? "Associative or persistent (recommended)" : "联想触达或持续激活（推荐）"}</option><option value="associative-only">{locale === "en" ? "Associative touch only" : "仅联想触达"}</option><option value="all-active">{locale === "en" ? "All above-baseline activity" : "全部高于基线的活动"}</option></select></label>
                <SettingsDisclosure title={locale === "en" ? "Temporal detection thresholds" : "时窗判定参数"} description={locale === "en" ? "Advanced experimental values; each record retains its configuration snapshot" : "高级实验参数；每条记录都会保留当时的配置快照"}>
                  <div className="settings-grid">
                    <label className="settings-field">{locale === "en" ? "Baseline ticks" : "刺激前基线（tick）"}<input type="number" min="0" value={temporal.baseline_ticks} onChange={(event) => updateTemporal({ baseline_ticks: Math.max(0, Number(event.target.value)) })} /></label>
                    <label className="settings-field">{locale === "en" ? "Minimum response ticks" : "最短响应窗口（tick）"}<input type="number" min="1" value={temporal.min_response_ticks} onChange={(event) => updateTemporal({ min_response_ticks: Math.max(1, Number(event.target.value)) })} /></label>
                    <label className="settings-field">{locale === "en" ? "Maximum response ticks" : "最长响应窗口（tick）"}<input type="number" min="1" value={temporal.max_response_ticks} onChange={(event) => updateTemporal({ max_response_ticks: Math.max(1, Number(event.target.value)) })} /></label>
                    <label className="settings-field">{locale === "en" ? "Settlement sample ticks" : "收敛采样长度（tick）"}<input type="number" min="2" value={temporal.settle_ticks} onChange={(event) => updateTemporal({ settle_ticks: Math.max(2, Number(event.target.value)) })} /></label>
                    <label className="settings-field">{locale === "en" ? "Activation threshold" : "激活阈值"}<input type="number" min="0" max="1" step=".001" value={temporal.activation_threshold} onChange={(event) => updateTemporal({ activation_threshold: Math.max(0, Math.min(1, Number(event.target.value))) })} /></label>
                    <label className="settings-field">{locale === "en" ? "Minimum excess over baseline" : "高于基线的最小激活"}<input type="number" min="0" max="1" step=".001" value={temporal.excess_activation_min} onChange={(event) => updateTemporal({ excess_activation_min: Math.max(0, Number(event.target.value)) })} /></label>
                    <label className="settings-field">{locale === "en" ? "Baseline-noise multiplier" : "基线噪声倍数"}<input type="number" min="0" step=".1" value={temporal.baseline_noise_gain} onChange={(event) => updateTemporal({ baseline_noise_gain: Math.max(0, Number(event.target.value)) })} /></label>
                    <label className="settings-field">{locale === "en" ? "Top-set Jaccard minimum" : "候选集合相似度下限"}<input type="number" min="0" max="1" step=".01" value={temporal.convergence_jaccard_min} onChange={(event) => updateTemporal({ convergence_jaccard_min: Math.max(0, Math.min(1, Number(event.target.value))) })} /></label>
                    <label className="settings-field">{locale === "en" ? "Distribution drift maximum" : "激活分布漂移上限"}<input type="number" min="0" max="1" step=".01" value={temporal.convergence_drift_max} onChange={(event) => updateTemporal({ convergence_drift_max: Math.max(0, Math.min(1, Number(event.target.value))) })} /></label>
                    <label className="settings-field">{locale === "en" ? "Displayed candidates (0 = all)" : "显示候选数（0 为全部）"}<input type="number" min="0" value={temporal.display_limit} onChange={(event) => updateTemporal({ display_limit: Math.max(0, Number(event.target.value)) })} /></label>
                  </div>
                </SettingsDisclosure>
              </SettingsDisclosure>
            </section>
            <section hidden={active !== "persistence"}>
              <h3>数据持久化</h3>
              <h4>{persistenceCopy.title}</h4>
              <p>{persistenceCopy.description}</p>
              <p className="settings-note">{archiveIndex ? `${archiveIndex.backend ?? "sqlite"} · ${archiveIndex.indexed_artifacts ?? 0} ${locale === "en" ? "artifacts" : "个工件"} · ${archiveIndex.running ? persistenceCopy.indexing : persistenceCopy.ready}${archiveIndex.running ? ` (${archiveIndex.processed ?? 0}/${archiveIndex.total ?? 0})` : ""}${Number(archiveIndex.writer?.queued ?? 0) > 0 ? ` · ${locale === "en" ? "writer queue" : "写入队列"} ${archiveIndex.writer?.queued}` : ""}` : (locale === "en" ? "Loading archive catalogue status…" : "正在读取归档目录状态…")}</p>
              <div className="settings-inline-actions">
                <button type="button" disabled={Boolean(panelOperation)} onClick={() => void refreshArchiveIndex(true)}>{panelOperation ? "正在处理…" : persistenceCopy.refresh}</button>
                <button type="button" disabled={Boolean(panelOperation)} onClick={() => void rebuildArchiveIndex()}>{panelOperation ? "正在处理…" : persistenceCopy.rebuild}</button>
              </div>
              {archiveIndexMessage && <p className="settings-note">{archiveIndexMessage}</p>}
              <SettingsDisclosure title={locale === "en" ? "Advanced management-record backend" : "高级管理记录后端"} description={locale === "en" ? "Optional backend switching and migration; does not replace .tmind packages" : "可选后端切换与迁移；不会替代 .tmind 模型包"}>
                <p>{persistenceCopy.generic}</p>
                {persistenceStartupWarning && <p className="settings-note settings-warning">{locale === "en" ? "Legacy JSON persistence was safely bypassed. Its original file remains on disk; new history is using SQLite." : "旧版 JSON 持久化已被安全绕过；原文件仍保留在磁盘中，新的历史记录已改用 SQLite。"}<small>{persistenceStartupWarning}</small></p>}
                <label className="settings-field">{locale === "en" ? "Storage backend" : "存储后端"}<select value={persistenceKind} onChange={(event) => setPersistenceKind(event.target.value)}><option value="file">{persistenceKindText(locale, "file")}</option><option value="sqlite">{persistenceKindText(locale, "sqlite")}</option><option value="mysql">{persistenceKindText(locale, "mysql")}</option><option value="d1">{persistenceKindText(locale, "d1")}</option></select></label>
                <label className="settings-field">连接配置<input type={persistenceKind === "mysql" ? "password" : "text"} value={persistenceValue} onChange={(event) => setPersistenceValue(event.target.value)} placeholder={persistenceKind === "sqlite" ? "data/threemind.sqlite3" : persistenceKind === "mysql" ? "mysql://user:password@127.0.0.1:3306/threemind" : persistenceKind === "d1" ? "D1 HTTP endpoint" : "无需配置"} /></label>
                <button type="button" disabled={Boolean(panelOperation)} onClick={() => void switchPersistence()}>{panelOperation ? "正在处理…" : "切换并迁移"}</button>
                {persistenceMessage && <p className="settings-note">{persistenceMessage}</p>}
              </SettingsDisclosure>
            </section>
            <section hidden={active !== "notifications"}>
              <h3>{t("notifications")}</h3>
              <p>API Key 只发送给本机 Core 保存，读取设置时不会返回它。只有检测到重复结构且通知已启用时才会发送邮件。</p>
              <label className="settings-switch"><input type="checkbox" checked={notification.enabled} onChange={(event) => updateNotification({ enabled: event.target.checked })} /> 启用邮件提醒</label>
              <SettingsDisclosure title={locale === "en" ? "Delivery and recipient settings" : "邮件发送与收件设置"} description={locale === "en" ? "Resend credentials, sender, recipients and language" : "Resend 凭据、发件人、收件人和语言"}>
              <label className="settings-field">Resend API Key
                <input type="password" value={apiKey} placeholder={notification.resend_api_key_configured ? `已配置：${notification.resend_api_key_hint}` : "re_..."} onChange={(event) => onKeyChange(event.target.value)} />
              </label>
              <label className="settings-field">发件人
                <input value={notification.sender} onChange={(event) => updateNotification({ sender: event.target.value })} placeholder="ThreeMind <alerts@your-domain.com>" />
              </label>
              <label className="settings-field">收件人邮箱
                <textarea value={notification.recipients.join("\n")} onChange={(event) => updateNotification({ recipients: event.target.value.split(/[\n,;]+/).map((item) => item.trim()).filter(Boolean) })} placeholder={"you@example.com\ncolleague@example.com"} />
              </label>
              <label className="settings-field">邮件语言
                <select value={notification.language ?? "follow-ui"} onChange={(event) => updateNotification({ language: event.target.value as NotificationSettings["language"] })}><option value="follow-ui">{locale === "en" ? "Follow interface language" : "跟随界面语言"}</option><option value="zh-CN">{locale === "en" ? "Simplified Chinese" : "简体中文"}</option><option value="en">English</option></select>
              </label>
              <p className="settings-note">可填写多个邮箱；每行一个，也支持逗号或分号分隔。所有收件人会收到同一封提醒邮件。</p>
              <p className="settings-note">Resend 需要 API Key；对外发送通常还需要验证发件域名。</p>
              <button type="button" disabled={saving || loading || Boolean(panelOperation)} onClick={onTest}>{saving ? "正在发送测试邮件…" : "发送测试邮件"}</button>
              </SettingsDisclosure>
            </section>
          </div>
        </div>
        <footer className="settings-footer">
          <span className="settings-save-status" role="status" aria-live="polite">
            {panelOperation || (loading ? (locale === "en" ? "Loading saved settings…" : "正在读取已保存的设置…") : saving ? (locale === "en" ? "Saving settings…" : "正在保存设置…") : "")}
          </span>
          <button className="primary" type="button" onClick={() => void savePanelSettings()} disabled={saving || loading || Boolean(panelOperation)}>
            {saving ? <><span className="ui-spinner" aria-hidden="true" />{locale === "en" ? "Saving…" : "正在保存…"}</> : t("saveSettings")}
          </button>
        </footer>
      </section>
    </div>
  );
}

function NameDialog({ title, initial, onConfirm, onCancel, confirmLabel, kernel, onKernelChange, v3NodeMode, onV3NodeModeChange, options, onOptionsChange }: { title: string; initial: string; onConfirm: (name: string) => void; onCancel: () => void; confirmLabel?: string; kernel?: KernelId; onKernelChange?: (kernel: KernelId) => void; v3NodeMode?: V3NodeMode; onV3NodeModeChange?: (mode: V3NodeMode) => void; options?: NewModelOptions; onOptionsChange?: (options: NewModelOptions) => void }) {
  const t = useT();
  const locale = useLocale();
  const [value, setValue] = useState(initial);
  const setOption = (key: keyof NewModelOptions, raw: string) => {
    if (!options || !onOptionsChange) return;
    const next = Number(raw);
    if (Number.isFinite(next)) onOptionsChange({ ...options, [key]: next });
  };
  const isV3 = kernel === "anonymous-spatial-v3";
  const spatialEnabled = isV3 && Boolean(options?.spatial_enabled ?? true);
  const advanced = (label: string, key: keyof NewModelOptions, min: number, step: number, disabled = false) => (
    <label className="settings-field" key={key}>{label}<input type="number" min={min} step={step} disabled={disabled} value={Number(options?.[key] ?? 0)} onChange={(event) => setOption(key, event.target.value)} /></label>
  );
  const optionalLimit = (label: string, key: "edge_adaptation_limit" | "propagation_limit" | "edge_birth_activation_product_min" | "propagation_activation_min" | "max_nodes" | "max_edges", min: number, step: number) => {
    const enabled = options?.[key] != null;
    const value = Number(options?.[key] ?? min);
    return <label className="settings-field" key={key}><span className="settings-inline"><input type="checkbox" checked={enabled} onChange={(event) => options && onOptionsChange?.({ ...options, [key]: event.target.checked ? value : null })} /> 启用{label}</span><input type="number" min={min} step={step} disabled={!enabled} value={value} onChange={(event) => setOption(key, event.target.value)} /></label>;
  };
  return <div className="settings-backdrop" onMouseDown={onCancel}><section className="name-dialog create-consciousness-dialog" onMouseDown={(event) => event.stopPropagation()}>
    <h3>{title}</h3>
    <label className="settings-field">意识名称<input autoFocus value={value} onChange={(event) => setValue(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && value.trim()) onConfirm(value.trim()); }} /></label>
    {kernel && onKernelChange && <>
      <div className="field"><label htmlFor="new-consciousness-kernel">{locale === "en" ? "Consciousness model" : "意识模型"}</label><select id="new-consciousness-kernel" value={kernel} onChange={(event) => onKernelChange(event.target.value as KernelId)}><option value="labeled-feature-v1">{kernelText(locale, "labeled-feature-v1")}</option><option value="anonymous-sensory-v2">{kernelText(locale, "anonymous-sensory-v2")}</option><option value="anonymous-spatial-v3">{kernelText(locale, "anonymous-spatial-v3")}</option></select></div>
      {isV3 && v3NodeMode && onV3NodeModeChange && <label className="settings-field">{t("v3NodeMode")}
        <select value={v3NodeMode} onChange={(event) => onV3NodeModeChange(event.target.value as V3NodeMode)}>
          <option value="anonymous">{t("v3Anonymous")}</option>
          <option value="labeled-observation">{t("v3LabeledObservation")}</option>
          <option value="literal-character">{t("v3LiteralCharacter")}</option>
        </select>
        <span className="settings-note">{t("v3NodeModeImmutable")} {t("v3NodeModeDetail")}</span>
      </label>}
      {isV3 && options && onOptionsChange && <label className="settings-switch"><input type="checkbox" checked={Boolean(options.spatial_enabled)} onChange={(event) => onOptionsChange({ ...options, spatial_enabled: event.target.checked })} /> {t("enableSpatialEmbedding")}<span className="settings-note">{t("spatialEmbeddingCreationDetail")}</span></label>}
      <p className="settings-note">{isV3 ? (spatialEnabled ? t("spatialEmbeddingEnabledHint") : t("spatialEmbeddingDisabledHint")) : "所有字段都有实验默认值，可直接创建。"}</p>
      {options && onOptionsChange && <section className="new-model-background-defaults">
        <h4>{locale === "en" ? "Background sensory defaults" : "背景感官默认项"}</h4>
        <p className="settings-note">{locale === "en" ? "Host physical telemetry is enabled by default. Random ambient input, whole-process telemetry and per-consciousness runtime feedback are opt-in; all remain external sensory inputs." : "默认启用宿主物理遥测；随机环境、整个进程遥测和单意识实例物理自反馈默认关闭。它们都只是外部感官输入。"}</p>
        <label className="settings-switch"><input type="checkbox" checked={options.host_telemetry_enabled} onChange={(event) => onOptionsChange({ ...options, host_telemetry_enabled: event.target.checked })} /> {locale === "en" ? "Host physical telemetry (default on)" : "宿主物理遥测（默认开启）"}</label>
        <label className="settings-switch"><input type="checkbox" checked={options.random_ambient_enabled} onChange={(event) => onOptionsChange({ ...options, random_ambient_enabled: event.target.checked })} /> {locale === "en" ? "Random ambient field (default off)" : "随机环境场（默认关闭）"}</label>
        <label className="settings-switch"><input type="checkbox" checked={options.process_telemetry_enabled} onChange={(event) => onOptionsChange({ ...options, process_telemetry_enabled: event.target.checked })} /> {locale === "en" ? "ThreeMind whole-process telemetry (default off)" : "ThreeMind 整体进程遥测（默认关闭）"}<span className="settings-note">{locale === "en" ? "In a multi-consciousness run this describes the service process, not one consciousness." : "多意识并行时，它反映整个服务进程，不能解释为某个意识的独立资源消耗。"}</span></label>
        <label className="settings-switch"><input type="checkbox" checked={options.runtime_telemetry_enabled} onChange={(event) => onOptionsChange({ ...options, runtime_telemetry_enabled: event.target.checked })} /> {locale === "en" ? "Per-consciousness physical runtime feedback (experimental, default off)" : "单意识实例物理自反馈（实验性，默认关闭）"}<span className="settings-note">{locale === "en" ? "Feeds delayed, anonymous measurements of this runtime's real thread CPU time and execution timing back through InputBus. It does not echo OutputBus or semantic content." : "把该实例真实线程 CPU 时间与执行时序的延迟匿名测量经 InputBus 反馈；不会回灌 OutputBus 或任何语义内容。"}</span></label>
      </section>}
      {spatialEnabled && <div className="new-model-basics"><label className="settings-field">空间维数<input type="number" min="1" max="16" step="1" value={options?.spatial_dimensions ?? 3} onChange={(event) => setOption("spatial_dimensions", event.target.value)} /></label><label className="settings-field">空间邻域半径<input type="number" min="0.01" step="0.1" value={options?.spatial_radius ?? 2.5} onChange={(event) => setOption("spatial_radius", event.target.value)} /></label><label className="settings-field">空间竞争<input type="number" min="0" max="1" step="0.01" value={options?.spatial_competition ?? 0} onChange={(event) => setOption("spatial_competition", event.target.value)} /></label></div>}
      <details className="new-model-advanced">
        <summary>{locale === "en" ? "Advanced settings" : "高级设置"}</summary>
        <p className="settings-note">{locale === "en" ? "No computational truncation is enabled by default. Local inhibition is enabled by default; the independent experimental energy simulation remains disabled." : "默认不启用计算截断。局部抑制默认开启；与之独立的实验性能量模拟仍默认关闭。"}</p>
        <label className="settings-switch"><input type="checkbox" checked={options?.attention_competition_enabled ?? false} onChange={(event) => options && onOptionsChange?.({ ...options, attention_competition_enabled: event.target.checked })} /> {locale === "en" ? "Enable environmental competition gate" : "启用环境竞争门"}</label>
        <label className="settings-switch"><input type="checkbox" checked={options?.homeostasis_enabled ?? false} onChange={(event) => options && onOptionsChange?.({ ...options, homeostasis_enabled: event.target.checked })} /> {locale === "en" ? "Enable legacy global activation clamp (default off)" : "启用旧式全局稳态钳制（默认关闭）"}</label>
        <p className="settings-note">{locale === "en" ? "This legacy comparison mechanism rescales total activation and changes dynamics. Leave it off for the mainline model." : "该旧式对照机制会缩放总激活量并改变动力学；主线模型应保持关闭。"}</p>
        <h4>{locale === "en" ? "Topology-local inhibition" : "拓扑局部抑制"}</h4>
        <label className="settings-switch"><input type="checkbox" checked={options?.topology_inhibition_enabled ?? true} onChange={(event) => options && onOptionsChange?.({ ...options, topology_inhibition_enabled: event.target.checked })} /> {locale === "en" ? "Enable local inhibition (default on)" : "启用局部抑制（默认开启）"}</label>
        <p className="settings-note">{locale === "en" ? "Excitatory edges remain directed. Inhibition diffuses as a finite, decaying potential across physical neighbours and produces a delayed refractory effect." : "兴奋连接仍保持有向；抑制作为有限且衰减的势沿物理邻接扩散，并产生延迟的不应期效果。"}</p>
        <div className="settings-grid">
          {advanced(locale === "en" ? "Inhibition generation gain" : "抑制生成增益", "inhibition_generation_gain", 0, .01, !(options?.topology_inhibition_enabled ?? true))}
          {advanced(locale === "en" ? "Inhibition decay" : "抑制衰减", "inhibition_decay", 0, .01, !(options?.topology_inhibition_enabled ?? true))}
          {advanced(locale === "en" ? "Inhibition diffusion" : "抑制扩散比例", "inhibition_diffusion", 0, .01, !(options?.topology_inhibition_enabled ?? true))}
          {advanced(locale === "en" ? "Response attenuation gain" : "响应抑制增益", "inhibition_response_gain", 0, .05, !(options?.topology_inhibition_enabled ?? true))}
          {advanced(locale === "en" ? "Inhibition saturation" : "抑制饱和值", "inhibition_saturation", .000001, .01, !(options?.topology_inhibition_enabled ?? true))}
          {advanced(locale === "en" ? "Minimum propagated inhibition" : "最小传播抑制", "inhibition_propagation_min", 0, .001, !(options?.topology_inhibition_enabled ?? true))}
        </div>
        <h4>{locale === "en" ? "Experimental energy accounting" : "实验性能量记账"}</h4>
        <label className="settings-switch"><input type="checkbox" checked={options?.energy_simulation_enabled ?? false} onChange={(event) => options && onOptionsChange?.({ ...options, energy_simulation_enabled: event.target.checked })} /> {locale === "en" ? "Enable energy simulation (default off)" : "启用能量模拟（默认关闭）"}</label>
        <label className="settings-switch"><input type="checkbox" disabled={!options?.energy_simulation_enabled} checked={options?.irreversible_energy_death_enabled ?? false} onChange={(event) => options && onOptionsChange?.({ ...options, irreversible_energy_death_enabled: event.target.checked })} /> {locale === "en" ? "Enable irreversible starvation death (default off)" : "启用不可逆饥饿死亡（默认关闭）"}</label>
        <p className="settings-note">{locale === "en" ? "Core never replenishes energy internally. Enable and configure the finite energy-supply adapter separately when a run needs external supply." : "Core 绝不会在内部恢复能量；需要外部供应时，请另行启用并配置有限能量供应适配器。"}</p>
        <div className="settings-grid">
          {advanced(locale === "en" ? "Initial reserve" : "初始能量储备", "energy_initial_reserve", 0, .01, !options?.energy_simulation_enabled)}
          {advanced(locale === "en" ? "Reserve capacity" : "能量容量", "energy_capacity", .000001, .01, !options?.energy_simulation_enabled)}
          {advanced(locale === "en" ? "Direct activation cost" : "直接激活成本", "energy_direct_cost", 0, .001, !options?.energy_simulation_enabled)}
          {advanced(locale === "en" ? "Associative propagation cost" : "联想传播成本", "energy_associative_cost", 0, .001, !options?.energy_simulation_enabled)}
          {advanced(locale === "en" ? "Inhibitory diffusion cost" : "抑制扩散成本", "energy_inhibition_cost", 0, .001, !options?.energy_simulation_enabled)}
          {advanced(locale === "en" ? "Node maintenance cost" : "节点维持成本", "energy_maintenance_cost_per_node", 0, .000001, !options?.irreversible_energy_death_enabled)}
          {advanced(locale === "en" ? "Edge maintenance cost" : "连接维持成本", "energy_maintenance_cost_per_edge", 0, .000001, !options?.irreversible_energy_death_enabled)}
          {advanced(locale === "en" ? "Starvation structural decay" : "饥饿结构衰减", "energy_starvation_structural_decay", 0, .001, !options?.irreversible_energy_death_enabled)}
          {advanced(locale === "en" ? "Starvation death window (ticks)" : "饥饿死亡窗口（tick）", "energy_starvation_death_ticks", 1, 1, !options?.irreversible_energy_death_enabled)}
        </div>
        <h4>{locale === "en" ? "Existing associative dynamics" : "现有关联动力学"}</h4>
        <div className="settings-grid">{advanced(locale === "en" ? "Competition capacity" : "环境竞争容量（仅竞争门开启时）", "attention_budget", 1, 1)}{advanced(locale === "en" ? "Global activation target" : "稳态总激活", "target_total_activation", .01, .1, !options?.homeostasis_enabled)}{optionalLimit(locale === "en" ? "edge adaptations per tick" : "每 tick 边适应预算", "edge_adaptation_limit", 1, 1)}{optionalLimit(locale === "en" ? "propagations per tick" : "每 tick 传播预算", "propagation_limit", 1, 1)}{optionalLimit(locale === "en" ? "minimum co-activation for candidate edge" : "候选边最小共激活", "edge_birth_activation_product_min", 0, .001)}{optionalLimit(locale === "en" ? "minimum propagation activation" : "最小传播激活", "propagation_activation_min", 0, .001)}{optionalLimit(locale === "en" ? "maximum nodes" : "最大节点数", "max_nodes", 1, 1)}{optionalLimit(locale === "en" ? "maximum edges" : "最大连接数", "max_edges", 1, 1)}{advanced(locale === "en" ? "Local novelty gain" : "局部新颖连接增益", "local_novelty_gain", 0, 0.001)}{advanced(locale === "en" ? "Novelty touch reference" : "新颖触达参考值", "novelty_touch_reference", 0.000001, 0.001)}{advanced(locale === "en" ? "Association window (ticks)" : "关联窗口（tick）", "association_window", 1, 1)}{advanced(locale === "en" ? "Propagation gain" : "传播增益", "propagation_gain", 0, 0.01)}{advanced(locale === "en" ? "Learning rate" : "学习率", "learning_rate", 0, 0.01)}{advanced(locale === "en" ? "Edge forgetting rate" : "边遗忘率", "edge_decay", 0, 0.001)}{advanced(locale === "en" ? "Stability gain" : "稳定度增益", "stability_gain", 0, 0.001)}{advanced(locale === "en" ? "Stability decay" : "稳定度衰减", "stability_decay", 0, 0.00001)}{advanced(locale === "en" ? "Repeated-touch consolidation" : "重复触达固化增益", "consolidation_repeat_gain", 0, 0.001)}{advanced(locale === "en" ? "Associative consolidation" : "联想固化增益", "consolidation_associative_gain", 0, 0.001)}{advanced(locale === "en" ? "Strong-stimulus consolidation" : "强刺激固化增益", "consolidation_intensity_gain", 0, 0.01)}{advanced(locale === "en" ? "Orphan node retention (ticks)" : "无连接节点保留（tick）", "node_prune_after", 1, 1)}{advanced(locale === "en" ? "Text sensory channels" : "文本感官通道数", "sensory_channels", 32, 1)}</div>
      </details>
    </>}
    <div className="actions"><button type="button" onClick={onCancel}>取消</button><button className="primary" type="button" disabled={!value.trim()} onClick={() => onConfirm(value.trim())}>{confirmLabel ?? "创建"}</button></div>
  </section></div>;
}

function OpenConsciousnessDialog({
  items,
  locale,
  busy,
  onClose,
  onOpen,
  onImport,
}: {
  items: ConsciousnessSummary[];
  locale: Locale;
  busy: boolean;
  onClose: () => void;
  onOpen: (consciousnessId: string, snapshotPath?: string) => Promise<void>;
  onImport: (file: File) => Promise<void>;
}) {
  const [selectedId, setSelectedId] = useState(items[0]?.id ?? "");
  const [snapshotRows, setSnapshotRows] = useState<Snapshot[]>([]);
  const [selectedPath, setSelectedPath] = useState("");
  const [loadingSnapshots, setLoadingSnapshots] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!selectedId && items[0]?.id) setSelectedId(items[0].id);
  }, [items, selectedId]);

  useEffect(() => {
    let alive = true;
    setSnapshotRows([]);
    setSelectedPath("");
    if (!selectedId) return () => { alive = false; };
    setLoadingSnapshots(true);
    fetch(`${API}/api/consciousnesses/${encodeURIComponent(selectedId)}/snapshots`, { cache: "no-store" })
      .then(async (response) => {
        const payload = await response.json() as { items?: Snapshot[]; detail?: string };
        if (!response.ok) throw new Error(payload.detail ?? "Unable to load snapshots");
        if (!alive) return;
        const rows = Array.isArray(payload.items) ? payload.items : [];
        setSnapshotRows(rows);
        // The archive index is newest-first; continuing therefore defaults to
        // the latest snapshot while still allowing an explicit historical one.
        setSelectedPath(rows[0]?.path ?? "");
      })
      .catch((caught) => { if (alive) setMessage(caught instanceof Error ? caught.message : "Unable to load snapshots"); })
      .finally(() => { if (alive) setLoadingSnapshots(false); });
    return () => { alive = false; };
  }, [selectedId]);

  const selected = items.find((item) => item.id === selectedId);
  return <div className="settings-backdrop" onMouseDown={onClose}>
    <section className="archive-modal open-consciousness-dialog" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
      <header className="settings-header">
        <div><strong>{locale === "en" ? "Open consciousness" : "打开意识"}</strong><span>{locale === "en" ? "Continue from the latest snapshot, choose an earlier archive, or import a .tmind package." : "默认从最新快照继续，也可选择历史快照或导入本地 .tmind 包。"}</span></div>
        <button type="button" onClick={onClose} aria-label={locale === "en" ? "Close" : "关闭"}>×</button>
      </header>
      <div className="open-consciousness-layout">
        <div className="open-consciousness-list" role="listbox" aria-label={locale === "en" ? "Consciousnesses" : "意识列表"}>
          {items.map((item) => <button type="button" key={item.id} className={selectedId === item.id ? "is-selected" : ""} onClick={() => setSelectedId(item.id)}>
            <strong>{item.name}</strong>
            <span>{item.kernel ?? "unified-associative"} · tick {item.metrics?.tick ?? item.latest?.metrics?.tick ?? 0}</span>
            <small>{item.snapshots} {locale === "en" ? "snapshots" : "快照"} · {formatSnapshotTime(item.saved_at)}</small>
          </button>)}
          {!items.length && <div className="empty-state"><strong>{locale === "en" ? "No stored consciousness" : "没有已保存的意识"}</strong><span>{locale === "en" ? "Import a .tmind package below, or create a new consciousness." : "可在下方导入 .tmind，或返回创建新意识。"}</span></div>}
        </div>
        <div className="open-consciousness-options">
          <h3>{selected?.name ?? (locale === "en" ? "Choose a consciousness" : "请选择意识")}</h3>
          <label className="settings-field">{locale === "en" ? "Starting point" : "继续位置"}
            <select value={selectedPath} disabled={!selectedId || loadingSnapshots || busy} onChange={(event) => setSelectedPath(event.target.value)}>
              <option value="">{locale === "en" ? "Latest available state" : "最新可用状态"}</option>
              {snapshotRows.map((row) => <option key={row.path} value={row.path}>{row.label ?? row.name} · tick {row.metrics?.tick ?? 0} · {formatSnapshotTime(row.saved_at)}</option>)}
            </select>
            <span className="settings-note">{loadingSnapshots ? (locale === "en" ? "Loading snapshots…" : "正在读取快照…") : selectedPath ? (locale === "en" ? "The selected snapshot will be restored exactly." : "将精确恢复所选快照。") : (locale === "en" ? "ThreeMind will use the latest snapshot or package state." : "ThreeMind 将使用最新快照或模型包状态。")}</span>
          </label>
          <button className="primary" type="button" disabled={!selectedId || busy || loadingSnapshots} onClick={() => void onOpen(selectedId, selectedPath || undefined)}>{busy ? (locale === "en" ? "Opening…" : "正在打开…") : (locale === "en" ? "Open and continue" : "打开并继续")}</button>
          <div className="open-consciousness-import">
            <span>{locale === "en" ? "Local model package" : "本地模型包"}</span>
            <label className="file-button">{locale === "en" ? "Choose .tmind and open" : "选择 .tmind 并打开"}<input type="file" accept=".tmind,.bbx,application/zip" disabled={busy} onChange={(event) => { const file = event.target.files?.[0]; if (file) void onImport(file); event.currentTarget.value = ""; }} /></label>
          </div>
          {message && <p className="management-message">{message}</p>}
        </div>
      </div>
    </section>
  </div>;
}

function ArchivePanel({ items, onClose, onResume, onClone, onDelete, busy }: { items: Snapshot[]; onClose: () => void; onResume: (item: Snapshot) => void; onClone: (item: Snapshot) => void; onDelete: (item: Snapshot) => void; busy: boolean }) {
  const [filter, setFilter] = useState<"all" | "snapshot" | "portrait">("all");
  const visible = items.filter((item) => filter === "all" || item.kind === filter);
  return <div className="settings-backdrop" onMouseDown={onClose}><section className="archive-modal" onMouseDown={(event) => event.stopPropagation()}>
    <header className="settings-header"><div><strong>快照与遗照</strong><span>恢复前请确认覆盖当前运行中的意识；“自动”来源会明确标注。</span></div><button type="button" onClick={onClose}>×</button></header>
    <div className="archive-toolbar"><button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>全部</button><button className={filter === "snapshot" ? "active" : ""} onClick={() => setFilter("snapshot")}>快照</button><button className={filter === "portrait" ? "active" : ""} onClick={() => setFilter("portrait")}>遗照</button></div>
    <div className="archive-list">{visible.map((item) => <article className="archive-row" key={item.path}><div><strong>{item.label ?? item.name}</strong><span>{item.kind === "portrait" ? "遗照" : "快照"} · {snapshotProvenance(item)} · {item.consciousness_name ?? item.consciousness_id}</span><span>{formatSnapshotTime(item.saved_at)} · tick {item.metrics?.tick ?? 0} · {item.metrics?.nodes ?? 0} 节点 / {item.metrics?.edges ?? 0} 连接</span></div><div className="archive-actions"><button disabled={busy} onClick={() => window.alert(`意识：${item.consciousness_name ?? item.consciousness_id}\n来源：${snapshotProvenance(item)}\n状态：${item.metrics?.life_state ?? "未知"}\ntick：${item.metrics?.tick ?? 0}\n节点：${item.metrics?.nodes ?? 0}\n连接：${item.metrics?.edges ?? 0}`)}>详情</button><a href={`/api/archive?path=${encodeURIComponent(item.path)}`}>导出</a><button disabled={busy} onClick={() => onResume(item)}>继续</button><button disabled={busy} onClick={() => onClone(item)}>克隆</button><button disabled={busy} className="danger" onClick={() => onDelete(item)}>删除</button></div></article>)}{visible.length === 0 && <p className="settings-note">没有符合筛选条件的存档。</p>}</div>
  </section></div>;
}

type DetailTab = "snapshots" | "clones" | "stimuli" | "observations" | "events" | "interpretations" | "trace";
type LogRow = Record<string, unknown>;

function ConsciousnessDetailPage({ item, snapshots: initialSnapshots, consciousnesses, onBack, onResumeSnapshot }: { item: ConsciousnessSummary; snapshots: Snapshot[]; consciousnesses: ConsciousnessSummary[]; onBack: () => void; onResumeSnapshot: (snapshot: Snapshot) => void }) {
  const locale = useLocale();
  const [tab, setTab] = useState<DetailTab>("snapshots");
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("all");
  const [records, setRecords] = useState<LogRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [recordError, setRecordError] = useState("");
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [archiveRows, setArchiveRows] = useState<Snapshot[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const logTab = tab === "snapshots" || tab === "clones" ? null : tab;
  useEffect(() => {
    let alive = true;
    const fallback = initialSnapshots.filter((row) => row.consciousness_id === item.id);
    setArchiveRows(fallback);
    setSnapshotLoading(true);
    fetch(`${API}/api/consciousnesses/${encodeURIComponent(item.id)}/snapshots`, { cache: "no-store" })
      .then(async (response) => response.ok ? response.json() as Promise<{ items?: Snapshot[] }> : Promise.reject(new Error("无法读取快照")))
      .then((payload) => { if (alive) setArchiveRows(Array.isArray(payload.items) ? payload.items : []); })
      .catch(() => { if (alive) setArchiveRows(fallback); })
      .finally(() => { if (alive) setSnapshotLoading(false); });
    return () => { alive = false; };
  }, [item.id]);
  useEffect(() => {
    if (!logTab) { setRecords([]); setRecordError(""); setLoading(false); return; }
    let alive = true;
    setLoading(true);
    setRecordError("");
    fetch(`${API}/api/logs/${logTab}/${item.id}?limit=5000`, { cache: "no-store" })
      .then(async (response) => response.ok ? response.json() as Promise<{ items?: LogRow[] }> : Promise.reject(new Error("无法读取记录")))
      .then((payload) => { if (alive) setRecords(Array.isArray(payload.items) ? payload.items : []); })
      .catch(() => { if (alive) { setRecords([]); setRecordError(locale === "en" ? "This record stream could not be loaded." : "该记录流读取失败，请检查后端日志或稍后重试。"); } })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [item.id, locale, logTab]);
  const tabs: [DetailTab, string][] = [
    ["snapshots", locale === "en" ? "Snapshots & portraits" : "快照与遗照"],
    ["clones", locale === "en" ? "Direct clones" : "直系克隆"],
    ["stimuli", locale === "en" ? "Stimuli" : "刺激记录"],
    ["observations", locale === "en" ? "Passive readouts (snapshot / temporal)" : "被动读出（截面 / 时序）"],
    ["events", locale === "en" ? "Events" : "事件记录"],
    ["interpretations", locale === "en" ? "Interpretations" : "解读记录"],
    ["trace", locale === "en" ? "Dynamics trace" : "动力学追踪"],
  ];
  const filterText = (value: unknown) => JSON.stringify(value ?? "").toLowerCase().includes(query.trim().toLowerCase());
  const snapshotRows = archiveRows.filter((row) => (source === "all" || row.kind === source) && filterText([row.label, row.name, row.kind, row.metrics, row.reason, row.provenance]));
  const cloneRows = consciousnesses.filter((row) => row.parent_id === item.id && (source === "all" || row.status === source) && filterText(row));
  const logRows = records.filter((row) => (source === "all" || String(row.source ?? row.kind ?? "") === source) && filterText(row));
  const allRows = tab === "snapshots" ? snapshotRows : tab === "clones" ? cloneRows : logRows;
  const totalPages = Math.max(1, Math.ceil(allRows.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageRows = allRows.slice((safePage - 1) * pageSize, safePage * pageSize);
  const applyQuery = () => { setQuery(draft); setPage(1); };
  const reset = () => { setDraft(""); setQuery(""); setSource("all"); setPage(1); };
  const selectTab = (next: DetailTab) => { setTab(next); reset(); };
  const kindOptions = tab === "snapshots" ? [["all", locale === "en" ? "All types" : "全部类型"], ["snapshot", locale === "en" ? "Snapshots" : "普通快照"], ["portrait", locale === "en" ? "Portraits" : "遗照"]] : tab === "clones" ? [["all", locale === "en" ? "All statuses" : "全部状态"], ["active", runtimeStatusText(locale, "active")], ["dead", runtimeStatusText(locale, "dead")], ["archived", runtimeStatusText(locale, "archived")]] : tab === "stimuli" ? [["all", locale === "en" ? "All sources" : "全部来源"], ["ui", locale === "en" ? "User input" : "用户输入"], ["cli", locale === "en" ? "Command line" : "命令行"], ["ai-environment", locale === "en" ? "AI stimulus generator" : "AI 刺激器"]] : [["all", locale === "en" ? "All types" : "全部类型"]];
  const rows = pageRows as (Snapshot | ConsciousnessSummary | LogRow)[];
  const snapshotCount = archiveRows.filter((row) => row.kind === "snapshot").length;
  const portraitCount = archiveRows.filter((row) => row.kind === "portrait").length;
  const kernelDescription = kernelText(locale, item.kernel ?? "labeled-feature-v1");
  return <section className={`management-page consciousness-detail-page detail-tab-${tab}`}>
    <header><div><button type="button" onClick={onBack}>{locale === "en" ? "← Back to consciousnesses" : "← 返回意识列表"}</button><h2>{item.name}</h2><p>{kernelDescription} · {runtimeStatusText(locale, item.status)} {item.running ? (locale === "en" ? "· Running now" : "· 当前运行中") : ""}</p></div></header>
    <div className="detail-summary"><span><b>意识 ID</b>{item.id}</span><span><b>父意识</b>{item.parent_id ?? "—"}</span><span><b>快照 / 遗照</b>{snapshotLoading ? "读取中" : `${snapshotCount} / ${portraitCount}`}</span><span><b>当前 / 最近 tick</b>{item.metrics?.tick ?? item.latest?.metrics?.tick ?? 0}</span></div>
    <nav className="record-tabs">{tabs.map(([id, label]) => <button key={id} className={tab === id ? "active" : ""} onClick={() => selectTab(id)}>{label}</button>)}</nav>
    <div className="record-filters"><input value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") applyQuery(); }} placeholder={tab === "snapshots" ? "按名称、类型或状态筛选" : "按内容、来源或类型筛选"} /><select value={source} onChange={(event) => { setSource(event.target.value); setPage(1); }}>{kindOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><button type="button" onClick={applyQuery}>查询</button><button type="button" onClick={reset}>重置</button></div>
    {recordError && <p className="settings-note settings-warning" role="alert">{recordError}</p>}
    {loading ? <p className="settings-note">{locale === "en" ? "Loading records…" : "正在读取记录…"}</p> : <><div className="record-table-wrap"><table className="record-table"><thead>{tab === "snapshots" ? <tr><th>名称</th><th>类型</th><th>时间</th><th>tick</th><th>节点 / 连接</th><th>状态</th></tr> : tab === "clones" ? <tr><th>意识名称</th><th>ID</th><th>内核</th><th>状态</th><th>快照</th><th>最近 tick</th></tr> : tab === "stimuli" ? <tr><th>tick</th><th>来源</th><th>强度</th><th>刺激文本（外部日志）</th></tr> : tab === "observations" ? <tr><th>tick</th><th>类型</th><th>匿名结构</th><th>明文标签（外部注释）</th><th>重复</th><th>内部连接</th></tr> : tab === "events" ? <tr><th>tick</th><th>事件类型</th><th>名称 / 详情</th></tr> : tab === "trace" ? <tr><th>tick</th><th>{locale === "en" ? "Changed nodes" : "变化节点"}</th><th>{locale === "en" ? "Activation Δ" : "激活变化"}</th><th>{locale === "en" ? "Inhibition" : "抑制生成 / 传播"}</th><th>{locale === "en" ? "Energy reserve" : "能量余量"}</th><th>{locale === "en" ? "Details" : "详情"}</th></tr> : <tr><th>tick</th><th>重要</th><th>供应商</th><th>解读</th></tr>}</thead><tbody>{tab === "snapshots" ? (rows as Snapshot[]).map((row) => <tr key={row.path}><td>{row.label ?? row.name}</td><td>{row.kind === "portrait" ? (locale === "en" ? "Portrait" : "遗照") : (locale === "en" ? "Snapshot" : "快照")}</td><td>{row.saved_at ?? "—"}</td><td>{row.metrics?.tick ?? 0}</td><td>{row.metrics?.nodes ?? 0} / {row.metrics?.edges ?? 0}</td><td>{runtimeStatusText(locale, String(row.metrics?.life_state ?? "—"))}</td></tr>) : tab === "clones" ? (rows as ConsciousnessSummary[]).map((row) => <tr key={row.id}><td>{row.name}</td><td>{row.id}</td><td>{kernelText(locale, row.kernel ?? "labeled-feature-v1")}</td><td>{runtimeStatusText(locale, row.status)}</td><td>{row.snapshots}</td><td>{row.metrics?.tick ?? row.latest?.metrics?.tick ?? 0}</td></tr>) : tab === "stimuli" ? (rows as LogRow[]).map((row, index) => <tr key={`${row.tick}-${index}`}><td>{String(row.tick ?? "—")}</td><td>{String(row.source ?? "—")}</td><td>{String(row.intensity ?? "—")}</td><td>{String(row.text ?? "")}</td></tr>) : tab === "observations" ? (rows as LogRow[]).map((row, index) => { const readout = row.readout as Record<string, unknown> | undefined; const anonymous = String(row.anonymous_readout ?? readout?.anonymous_readout ?? (typeof row.readout === "string" ? row.readout : "—")); const labels = Array.isArray(row.readable_labels) ? row.readable_labels.map(String) : Array.isArray(readout?.readable_labels) ? (readout?.readable_labels as unknown[]).map(String) : []; const temporalRow = row.kind === "temporal_convergence_readout"; const tickLabel = temporalRow ? `${String(row.start_tick ?? "?")}–${String(row.end_tick ?? row.tick ?? "?")}` : String(row.tick ?? "—"); const typeLabel = temporalRow ? `${locale === "en" ? "Temporal" : "时序"} · ${temporalClassificationText(locale, String(row.classification ?? ""))}` : String(row.kind ?? "—"); return <tr key={`${row.tick}-${index}`}><td>{tickLabel}</td><td>{typeLabel}</td><td>{anonymous}</td><td>{labels.length ? labels.join(" · ") : "—"}</td><td>{String(readout?.occurrences ?? row.occurrences ?? "—")}</td><td>{String(readout?.internal_edges ?? row.internal_edges ?? "—")}</td></tr>; }) : tab === "events" ? (rows as LogRow[]).map((row, index) => <tr key={`${row.tick}-${index}`}><td>{String(row.tick ?? "—")}</td><td>{String(row.kind ?? "—")}</td><td>{String(row.name ?? row.path ?? "—")}</td></tr>) : tab === "trace" ? (rows as LogRow[]).map((row, index) => { const keyframe = row.kind === "dynamics_keyframe"; const changed = keyframe && Array.isArray(row.nodes) ? row.nodes.length : Array.isArray(row.node_dynamics) ? row.node_dynamics.length : 0; return <tr key={`${row.tick}-${index}`}><td>{String(row.tick ?? "—")}</td><td>{keyframe ? `${locale === "en" ? "Keyframe" : "关键帧"} · ${changed}` : changed}</td><td>{String(row.activation_delta ?? "—")}</td><td>{String(row.inhibition_generated ?? 0)} / {String(row.inhibition_transferred ?? 0)}</td><td>{String(row.energy_reserve_after ?? row.energy_reserve ?? "—")}</td><td><details><summary>{keyframe ? (locale === "en" ? "Inspect initial state" : "查看初始状态") : (locale === "en" ? "Inspect sparse delta" : "查看稀疏增量")}</summary><pre>{JSON.stringify(row, null, 2)}</pre></details></td></tr>; }) : (rows as LogRow[]).map((row, index) => <tr key={`${row.tick}-${index}`}><td>{String(row.tick ?? "—")}</td><td>{row.important ? "是" : "否"}</td><td>{String(row.provider_id ?? "—")}</td><td>{String(row.text ?? "")}</td></tr>)}</tbody></table>{allRows.length === 0 && <p className="settings-note">{tab === "trace" ? (locale === "en" ? "No dynamics trace has been recorded. Open Settings → Observation & records and enable Detailed dynamics trace for the running consciousness." : "尚无动力学记录。请打开“设置 → 观测、读出与记录”，为运行中的意识开启“详细动力学记录”。") : (locale === "en" ? "No records match the current filters." : "没有符合当前条件的记录。")}</p>}</div><div className="record-pagination"><span>{locale === "en" ? `${allRows.length} records, page ${safePage} / ${totalPages}` : `共 ${allRows.length} 条，第 ${safePage} / ${totalPages} 页`}</span><label>{locale === "en" ? "Per page" : "每页"} <select value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }}><option value="25">25</option><option value="50">50</option><option value="100">100</option></select> {locale === "en" ? "" : "条"}</label><button type="button" disabled={safePage <= 1} onClick={() => setPage(1)}>{locale === "en" ? "First" : "首页"}</button><button type="button" disabled={safePage <= 1} onClick={() => setPage(safePage - 1)}>{locale === "en" ? "Previous" : "上一页"}</button><button type="button" disabled={safePage >= totalPages} onClick={() => setPage(safePage + 1)}>{locale === "en" ? "Next" : "下一页"}</button><button type="button" disabled={safePage >= totalPages} onClick={() => setPage(totalPages)}>{locale === "en" ? "Last" : "末页"}</button></div></>}
    {tab === "snapshots" && <section className="detail-snapshot-actions" aria-label="快照运行与导出">
      <h3>快照操作</h3>
      {snapshotLoading ? <p className="settings-note">正在读取该意识的快照…</p> : <div className="archive-list">
        {snapshotRows.map((row) => <article className="archive-row" key={`action-${row.path}`}>
          <div><strong>{row.label ?? row.name}</strong><span>{row.kind === "portrait" ? "遗照" : "快照"} · {snapshotProvenance(row)}</span><span>{formatSnapshotTime(row.saved_at)} · tick {row.metrics?.tick ?? 0} · {row.metrics?.nodes ?? 0} 节点 / {row.metrics?.edges ?? 0} 连接</span></div>
          <div className="archive-actions"><button type="button" onClick={() => onResumeSnapshot(row)}>运行此快照</button><a href={`${API}/api/archive?path=${encodeURIComponent(row.path)}`}>导出</a></div>
        </article>)}
        {!snapshotRows.length && <p className="settings-note">该意识尚未保存任何可运行的快照或遗照。</p>}
      </div>}
    </section>}
  </section>;
}

const FALLBACK_TELEMETRY_GROUPS: Record<string, AdapterGroup[]> = {
  host: [
    { id: "compute", signals: ["cpu_load", "cpu_frequency"] },
    { id: "memory", signals: ["memory_pressure", "memory_commit_pressure", "swap_pressure", "page_in_rate", "page_out_rate", "page_fault_rate"] },
    { id: "disk", signals: ["disk_read_rate", "disk_write_rate", "disk_read_iops", "disk_write_iops"] },
    { id: "network", signals: ["network_receive_rate", "network_send_rate", "network_receive_packets", "network_send_packets", "network_error_rate", "network_drop_rate"] },
    { id: "power", signals: ["battery_level", "ac_power", "battery_charging"] },
  ],
  process: [
    { id: "compute", signals: ["cpu_load"] },
    { id: "memory", signals: ["rss_pressure", "private_memory_pressure", "page_fault_rate"] },
    { id: "io", signals: ["read_rate", "write_rate"] },
    { id: "scheduler", signals: ["thread_count", "handle_count", "scheduler_latency_ms", "tick_execution_time_ms"] },
  ],
  runtime: [
    { id: "compute", signals: ["thread_cpu_load", "epoch_busy_ratio", "epoch_execution_time_ms"] },
    { id: "scheduler", signals: ["scheduler_latency_ms"] },
  ],
};

function TelemetryAdapterEditor({ item, binding, consciousnessId, locale, busy, onConfig }: { item: AdapterInfo; binding?: AdapterBinding; consciousnessId?: string | null; locale: Locale; busy: boolean; onConfig: (patch: Record<string, unknown>) => void }) {
  const config = (binding?.config ?? item.config) as Record<string, unknown>;
  const signalConfig = (config.signals ?? {}) as Record<string, Record<string, unknown>>;
  const signalRules = item.schema.properties?.signals?.properties ?? {};
  const runtime = item.runtime;
  const available = new Set(runtime?.available_metrics ?? []);
  const unavailable = runtime?.unavailable_metrics ?? {};
  const scope = runtime?.scope ?? String(item.ui?.scope ?? "host");
  // A disabled model binding retains an editable configuration, so it can be
  // prepared before the device is mounted. The host device switch remains
  // the authority that disables all controls when collection itself is off.
  const usable = item.enabled;
  const patchSignal = (name: string, patch: Record<string, unknown>) => onConfig({ signals: { [name]: patch } });
  const status = runtime?.last_sample_time == null
    ? (locale === "en" ? "Waiting for first real-time sample" : "等待首次实时采样")
    : runtime.dependency === "full"
      ? (locale === "en" ? "Full psutil backend" : "完整 psutil 采集后端")
      : (locale === "en" ? "Partial native fallback" : "部分原生降级采集");
  return <div className="telemetry-editor">
    <div className="telemetry-status" data-state={runtime?.recent_error || runtime?.audit?.recent_error ? "error" : runtime?.dependency === "full" ? "full" : "partial"}>
      <strong>{status}</strong><span>{runtime?.backend ?? "—"}{runtime?.last_sample_time ? ` · ${new Date(runtime.last_sample_time).toLocaleString()}` : ""}</span>
      {scope === "process" && <small>{locale === "en" ? "These signals describe the complete ThreeMind service process, never one consciousness in isolation." : "这些信号描述整个 ThreeMind 服务进程，绝不冒充某个意识的独立资源消耗。"}</small>}
      {scope === "runtime" && <small>{locale === "en" ? "These are delayed physical measurements of the selected consciousness runtime. They are opt-in sensory feedback, not a Core control signal or an OutputBus echo." : "这些是所选意识实例的延迟物理测量。它们是可选感官反馈，不是 Core 控制信号，也不是 OutputBus 回声。"}</small>}
      {(runtime?.recent_error || runtime?.audit?.recent_error) && <small className="telemetry-error">{runtime.recent_error || runtime.audit?.recent_error}</small>}
    </div>
    <div className="telemetry-master-controls">
      <label className="settings-field">{adapterText(locale, "Sampling interval (ms)")}<input key={`interval-${String(config.sample_interval_ms)}`} type="number" min="250" max="60000" step="50" disabled={busy || !usable} defaultValue={Number(config.sample_interval_ms ?? 1000)} onBlur={(event) => onConfig({ sample_interval_ms: Number.parseInt(event.target.value, 10) })} /></label>
      <label className="settings-field">{adapterText(locale, "Temporal smoothing")}<input key={`smoothing-${String(config.smoothing)}`} type="number" min="0" max=".999" step=".01" disabled={busy || !usable} defaultValue={Number(config.smoothing ?? .8)} onBlur={(event) => onConfig({ smoothing: Number(event.target.value) })} /></label>
      <label className="settings-switch"><input type="checkbox" disabled={busy || !usable} checked={Boolean(config.levels_enabled)} onChange={(event) => onConfig({ levels_enabled: event.target.checked })} /> {locale === "en" ? "All level channels" : "全部水平通道"}</label>
      <label className="settings-switch"><input type="checkbox" disabled={busy || !usable} checked={Boolean(config.changes_enabled)} onChange={(event) => onConfig({ changes_enabled: event.target.checked })} /> {locale === "en" ? "All rise/fall channels" : "全部上升／下降通道"}</label>
    </div>
    <p className="settings-note">{locale === "en" ? "Turning a master switch off preserves every per-signal choice. The first sample after enable/resume establishes a change baseline and cannot create a false spike." : "关闭总开关会保留每个信号的子项配置；启用或恢复后的首次采样只建立变化基线，不会制造虚假尖峰。"}</p>
    {((item.ui?.groups?.length ? item.ui.groups : FALLBACK_TELEMETRY_GROUPS[scope]) ?? []).map((group) => <section className="telemetry-group" key={group.id}>
      <h4>{telemetryGroupText(locale, group.id)}</h4>
      <div className="telemetry-table-wrap"><table className="telemetry-table"><thead><tr><th>{locale === "en" ? "Signal" : "信号"}</th><th>{locale === "en" ? "Availability" : "可用性"}</th><th>{locale === "en" ? "Level" : "水平"}</th><th>{locale === "en" ? "Change" : "变化"}</th><th>{locale === "en" ? "Gain" : "增益"}</th></tr></thead><tbody>
        {group.signals.filter((name) => name in signalRules).map((name) => {
          const signal = signalConfig[name] ?? {};
          const waiting = runtime?.last_sample_time == null;
          const reason = unavailable[name];
          return <tr key={name}><td><strong>{telemetrySignalText(locale, name)}</strong><small>{name}</small></td><td><span className={`metric-availability ${waiting ? "waiting" : available.has(name) ? "available" : "unavailable"}`} title={reason ?? ""}>{waiting ? (locale === "en" ? "Waiting" : "等待") : available.has(name) ? (locale === "en" ? "Available" : "可用") : (locale === "en" ? "Unavailable" : "不可用")}</span>{reason && <small title={reason}>{reason}</small>}</td><td><input aria-label={`${name} level`} type="checkbox" disabled={busy || !usable} checked={Boolean(signal.level)} onChange={(event) => patchSignal(name, { level: event.target.checked })} /></td><td><input aria-label={`${name} change`} type="checkbox" disabled={busy || !usable} checked={Boolean(signal.change)} onChange={(event) => patchSignal(name, { change: event.target.checked })} /></td><td><input key={`${name}-gain-${String(signal.gain)}`} aria-label={`${name} gain`} type="number" min="0" max="100" step=".05" disabled={busy || !usable} defaultValue={Number(signal.gain ?? 1)} onBlur={(event) => patchSignal(name, { gain: Number(event.target.value) })} /></td></tr>;
        })}
      </tbody></table></div>
    </section>)}
    <details className="telemetry-advanced"><summary>{locale === "en" ? "Advanced normalization references" : "高级归一化参考尺度"}</summary><p>{locale === "en" ? "Disk and other unbounded rates use explicit, auditable references. Aggregate network throughput prefers the combined speed of active interfaces when available unless you explicitly override it." : "磁盘等无固定上限的速率使用显式、可审计的参考尺度；网络汇总吞吐在可用时优先采用所有活动网卡链路速度之和，除非你明确覆盖它。"}</p><div className="telemetry-reference-grid">{Object.entries(signalConfig).filter(([, signal]) => signal.reference != null).map(([name, signal]) => <div className="telemetry-reference-row" key={name}><label className="settings-switch"><input type="checkbox" disabled={busy || !usable} checked={Boolean(signal.reference_override)} onChange={(event) => patchSignal(name, { reference_override: event.target.checked })} /> {locale === "en" ? "Manual" : "手动"}</label><label className="settings-field">{telemetrySignalText(locale, name)}<input key={`${name}-reference-${String(signal.reference)}`} type="number" min="0.000000000001" step="1" disabled={busy || !usable || !Boolean(signal.reference_override)} defaultValue={Number(signal.reference)} onBlur={(event) => patchSignal(name, { reference: Number(event.target.value) })} /></label></div>)}</div></details>
    <div className="telemetry-export-actions">{(() => { const owner = scope === "runtime" && consciousnessId ? `&consciousness_id=${encodeURIComponent(consciousnessId)}` : ""; return <><a href={`${API}/api/telemetry/export?records=deliveries&format=csv&adapter_id=${encodeURIComponent(item.id)}${owner}`}>{locale === "en" ? "Delivery CSV" : "投递 CSV"}</a><a href={`${API}/api/telemetry/export?records=deliveries&format=jsonl&adapter_id=${encodeURIComponent(item.id)}${owner}`}>{locale === "en" ? "Delivery JSONL" : "投递 JSONL"}</a><a href={`${API}/api/telemetry/export?records=samples&format=csv&adapter_id=${encodeURIComponent(item.id)}${owner}`}>{locale === "en" ? "Raw CSV" : "原始 CSV"}</a><a href={`${API}/api/telemetry/export?records=samples&format=jsonl&adapter_id=${encodeURIComponent(item.id)}${owner}`}>{locale === "en" ? "Raw JSONL" : "原始 JSONL"}</a></>; })()}</div>
  </div>;
}

function MediaAdapterStatus({ item, consciousnessId, locale }: { item: AdapterInfo; consciousnessId: string | null; locale: Locale }) {
  const [sessions, setSessions] = useState<MediaSession[]>([]);
  const [loading, setLoading] = useState(false);
  const inputAdapter = item.id === "auditory-sensor" || item.id === "visual-sensor";
  useEffect(() => {
    if (!inputAdapter) { setSessions([]); return; }
    let cancelled = false; setLoading(true);
    const owner = consciousnessId ? `&consciousness_id=${encodeURIComponent(consciousnessId)}` : "";
    void fetch(`${API}/api/media/sessions?adapter_id=${encodeURIComponent(item.id)}${owner}&limit=5`, { cache: "no-store" })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`)))
      .then((payload: { items?: MediaSession[] }) => { if (!cancelled) setSessions(payload.items ?? []); })
      .catch(() => { if (!cancelled) setSessions([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [consciousnessId, inputAdapter, item.id]);
  const runtime = item.runtime ?? {};
  const unavailable = Object.entries(runtime.unavailable_inputs ?? {});
  const mediaText = (value: string) => {
    if (locale === "en") return value;
    return ({
      "live microphone PCM": "实时麦克风 PCM", "WAV upload": "WAV 上传", "compressed audio upload": "压缩音频上传",
      "live camera pixels": "实时摄像头像素", "image upload": "图像上传", "video upload": "视频上传",
      "install the optional media dependency": "请安装可选的 media 依赖",
      queued: "已排队", decoding: "解码中", encoding: "编码中", running: "运行中", completed: "已完成", failed: "失败", cancelled: "已取消",
    } as Record<string, string>)[value] ?? value;
  };
  const query = `adapter_id=${encodeURIComponent(item.id)}${consciousnessId ? `&consciousness_id=${encodeURIComponent(consciousnessId)}` : ""}`;
  return <div className="media-adapter-runtime">
    <div className="media-capability-row">
      <span className={`metric-availability ${runtime.dependency === "full" ? "available" : "waiting"}`}>{runtime.dependency === "full" ? (locale === "en" ? "Full codec support" : "完整编解码支持") : (locale === "en" ? "Partial codec support" : "部分编解码支持")}</span>
      <small>{runtime.backend ?? "—"} · {runtime.protocol ?? "threemind-media/1"}</small>
    </div>
    {(runtime.available_inputs ?? []).length > 0 && <p className="settings-note">{locale === "en" ? "Available: " : "可用："}{(runtime.available_inputs ?? []).map(mediaText).join(" · ")}</p>}
    {unavailable.length > 0 && <div className="media-unavailable-list">{unavailable.map(([name, reason]) => <small key={name}><strong>{mediaText(name)}</strong>：{mediaText(reason)}</small>)}</div>}
    <p className="settings-note">{locale === "en" ? `Semantic models: none. ${runtime.raw_retention ?? ""}` : `语义模型：无。${inputAdapter ? "上传载体按内容寻址保存，实时原始信号不落盘。" : "原始输出不落盘。"}`}</p>
    {runtime.audit && <p className="settings-note">{locale === "en" ? "Audit" : "审计"}：{runtime.audit.assets ?? 0} {locale === "en" ? "assets" : "份载体"} · {runtime.audit.sessions ?? 0} {locale === "en" ? "sessions" : "次会话"} · {runtime.audit.deliveries ?? 0} {locale === "en" ? "deliveries" : "次投递"}</p>}
    {inputAdapter && <>
      <div className="media-history-heading"><strong>{locale === "en" ? "Recent sensory sessions" : "最近感官会话"}</strong><span>{loading ? (locale === "en" ? "Loading…" : "读取中…") : ""}</span></div>
      {!loading && sessions.length === 0 ? <p className="settings-note">{locale === "en" ? "No recorded session for this scope." : "当前范围内还没有媒体会话记录。"}</p> : <div className="media-session-list">{sessions.map((session) => <div key={session.session_id}><span><strong>{session.mode === "live" ? (locale === "en" ? "Live" : "实时") : (locale === "en" ? "Upload" : "上传")}</strong> · {mediaText(session.state)}</span><small>{new Date(session.created_at_utc).toLocaleString()} · {session.frames_encoded} {locale === "en" ? "anonymous frames" : "个匿名帧"}{session.error ? ` · ${session.error}` : ""}</small></div>)}</div>}
      <div className="telemetry-export-actions"><a href={`${API}/api/media/export?format=csv&${query}`}>{locale === "en" ? "Delivery CSV" : "投递 CSV"}</a><a href={`${API}/api/media/export?format=jsonl&${query}`}>{locale === "en" ? "Delivery JSONL" : "投递 JSONL"}</a></div>
    </>}
    {!inputAdapter && <p className="settings-note">{runtime.subscribed ? (locale === "en" ? "The current browser output subscription is active." : "当前浏览器输出订阅已连接。") : (locale === "en" ? "No browser is currently consuming this output." : "当前没有浏览器正在消费此输出。")}</p>}
  </div>;
}

function AdapterManager({ locale }: { locale: Locale }) {
  const [items, setItems] = useState<AdapterInfo[]>([]);
  const [bindings, setBindings] = useState<AdapterBinding[]>([]);
  const [activeConsciousnessId, setActiveConsciousnessId] = useState<string | null>(null);
  const [backgroundEnabled, setBackgroundEnabled] = useState(true);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [operation, setOperation] = useState("");
  const load = useCallback(async () => {
    setBusy(true); setOperation(locale === "en" ? "Loading adapters…" : "正在读取适配器…");
    try {
      const response = await fetch(`${API}/api/adapters`, { cache: "no-store" }); const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "无法读取适配器");
      setItems(payload.items as AdapterInfo[]); setBindings((payload.bindings ?? []) as AdapterBinding[]);
      setActiveConsciousnessId(payload.active_consciousness_id ?? null); setBackgroundEnabled(Boolean(payload.background_input?.enabled ?? true));
    } catch (error) { setMessage(error instanceof Error ? error.message : "无法读取适配器"); }
    finally { setOperation(""); setBusy(false); }
  }, [locale]);
  useEffect(() => { void load(); }, [load]);
  const update = async (item: AdapterInfo, patch: { enabled?: boolean; config?: Record<string, unknown> }) => {
    if (busy) return; setBusy(true); setOperation(locale === "en" ? `Updating ${item.name}…` : `正在更新 ${item.name}…`);
    try {
      const response = await fetch(`${API}/api/adapters/${encodeURIComponent(item.id)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) }); const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "适配器更新失败");
      setItems((old) => old.map((current) => current.id === item.id ? { ...current, ...payload } as AdapterInfo : current)); setMessage(locale === "en" ? `${payload.name} updated.` : `${payload.name} 已更新。`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "适配器更新失败"); }
    finally { setOperation(""); setBusy(false); }
  };
  const updateBinding = async (item: AdapterInfo, enabled: boolean, config?: Record<string, unknown>) => {
    if (!activeConsciousnessId || busy) return; setBusy(true); setOperation(locale === "en" ? "Writing adapter binding to the current model package…" : "正在将适配器绑定写入当前模型包…");
    try {
      const response = await fetch(`${API}/api/consciousnesses/${encodeURIComponent(activeConsciousnessId)}/adapters/${encodeURIComponent(item.id)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled, ...(config ? { config } : {}) }) }); const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? "模型适配器绑定更新失败");
      setBindings((old) => [...old.filter((row) => row.adapter_id !== item.id), payload.binding as AdapterBinding]); setMessage(locale === "en" ? "Current model binding saved." : "当前模型绑定已保存。");
    } catch (error) { setMessage(error instanceof Error ? error.message : "模型适配器绑定更新失败"); }
    finally { setOperation(""); setBusy(false); }
  };
  const updateBackground = async (enabled: boolean) => {
    if (busy) return; setBusy(true); setOperation(locale === "en" ? "Updating background input master…" : "正在更新全部背景输入总开关…");
    try { const response = await fetch(`${API}/api/background-input`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled }) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.detail ?? "update failed"); setBackgroundEnabled(Boolean(payload.enabled)); setMessage(locale === "en" ? "Background input master updated." : "全部背景输入总开关已更新。"); }
    catch (error) { setMessage(error instanceof Error ? error.message : "背景输入更新失败"); } finally { setOperation(""); setBusy(false); }
  };
  return <section className="management-page adapter-management-page"><header className="management-header"><div><h2>{tr(locale,"adapterManagement")}</h2><p>{tr(locale,"adapterIntro")}</p></div><button type="button" disabled={busy} onClick={() => void load()}>{tr(locale,"refresh")}</button></header>
    {operation && <div className="management-message is-pending" role="status"><span className="ui-spinner" aria-hidden="true" />{operation}</div>}{message && <p className="settings-note" role="status">{message}</p>}
    <section className="background-master-card"><div><strong>{locale === "en" ? "All background input" : "全部背景输入"}</strong><p>{locale === "en" ? "Master permission only. Random ambient, host telemetry, process telemetry, and per-consciousness runtime feedback retain independent switches and configuration." : "这里只是总许可；随机环境、宿主遥测、进程遥测和单意识实例物理反馈仍保留各自独立的开关与配置。"}</p></div><label className="settings-switch"><input type="checkbox" disabled={busy} checked={backgroundEnabled} onChange={(event) => void updateBackground(event.target.checked)} /> {backgroundEnabled ? (locale === "en" ? "Enabled" : "已开启") : (locale === "en" ? "Disabled" : "已关闭")}</label></section>
    <div className="adapter-grid">{items.map((item) => {
      const binding = bindings.find((row) => row.adapter_id === item.id);
      const telemetry = item.ui?.component === "telemetry-table";
      const media = item.ui?.component === "media-adapter" || item.ui?.component === "media-output";
      const config = media && binding ? { ...item.config, ...(binding.config ?? {}) } : item.config;
      const patchConfig = (patch: Record<string, unknown>) => binding && activeConsciousnessId && media
        ? void updateBinding(item, binding.enabled, patch)
        : void update(item, { config: patch });
      return <article className={`adapter-card ${telemetry ? "telemetry-card" : ""} ${media ? "media-card" : ""}`} key={item.id}><header><div><strong>{adapterText(locale, item.id) === item.id ? adapterText(locale, item.name) : adapterText(locale, item.id)}</strong><span>{item.id} · {adapterText(locale, item.direction)} · {adapterText(locale, item.bus)}</span></div><label className="settings-switch"><input type="checkbox" disabled={busy} checked={item.enabled} onChange={(event) => void update(item, { enabled: event.target.checked })} /> {locale === "en" ? "Host device" : "宿主设备"}</label></header><p>{adapterText(locale, item.description)}</p>
        {binding && <label className="settings-switch model-binding-switch"><input type="checkbox" disabled={busy || !activeConsciousnessId} checked={binding.enabled} onChange={(event) => void updateBinding(item, event.target.checked)} /> {locale === "en" ? "Bind to current consciousness model" : "绑定到当前意识模型"}<span className="settings-note">{locale === "en" ? `Package status: ${binding.status ?? "declared"}` : `模型包状态：${binding.status ?? "已声明"}`}</span></label>}
        {telemetry ? <TelemetryAdapterEditor item={item} binding={binding} consciousnessId={activeConsciousnessId} locale={locale} busy={busy} onConfig={(patch) => binding && activeConsciousnessId ? void updateBinding(item, binding.enabled, patch) : void update(item, { config: patch })} /> : Object.entries(item.schema.properties ?? {}).filter(([, rule]) => rule.type !== "object").map(([name, rule]) => <label className="settings-field" key={name}>{adapterText(locale, String(rule.title ?? name))}{rule.type === "boolean" ? <input type="checkbox" checked={Boolean(config[name])} disabled={busy || !item.enabled} onChange={(event) => patchConfig({ [name]: event.target.checked })} /> : rule.type === "string" && rule.enum?.length ? <select disabled={busy || !item.enabled} value={String(config[name] ?? rule.enum[0])} onChange={(event) => patchConfig({ [name]: event.target.value })}>{rule.enum.map((value) => <option key={String(value)} value={String(value)}>{adapterText(locale, String(value))}</option>)}</select> : <input key={`${item.id}-${name}-${String(config[name])}`} type="number" min={rule.minimum} max={rule.maximum} step={rule.multipleOf ?? (rule.type === "integer" ? 1 : .01)} disabled={busy || !item.enabled} defaultValue={Number(config[name] ?? 0)} onBlur={(event) => patchConfig({ [name]: rule.type === "integer" ? Number.parseInt(event.target.value, 10) : Number(event.target.value) })} />}</label>)}
        {media && <MediaAdapterStatus item={item} consciousnessId={activeConsciousnessId} locale={locale} />}
      </article>;
    })}</div></section>;
}

export default function Lab() {
  const [locale, setLocale] = useState<Locale>(() => resolveLocale(localStorage.getItem("threemind-ui-locale") ?? navigator.language));
  useEffect(() => { localStorage.setItem("threemind-ui-locale", locale); document.documentElement.lang = locale; }, [locale]);
  const graphStoreRef = useRef<GraphProjectionStore | null>(null);
  if (!graphStoreRef.current) graphStoreRef.current = new GraphProjectionStore();
  const graphStore = graphStoreRef.current;
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [metrics, setMetrics] = useState<Metrics>(EMPTY_METRICS);
  const [hasActiveConsciousness, setHasActiveConsciousness] = useState(false);
  const [startupChecked, setStartupChecked] = useState(false);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [text, setText] = useState("");
  const [intensity, setIntensity] = useState(1);
  const [ambient, setAmbient] = useState(0.08);
  const [speed, setSpeed] = useState(1);
  const [trace, setTrace] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [operationFeedback, setOperationFeedback] = useState<OperationFeedback | null>(null);
  const feedbackTimerRef = useRef<number | undefined>(undefined);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [selectedSnapshot, setSelectedSnapshot] = useState("");
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [nameDialog, setNameDialog] = useState<{ kind: "snapshot" | "new"; initial: string } | null>(null);
  const [pendingResume, setPendingResume] = useState<Snapshot | null>(null);
  const [observer, setObserver] = useState<ObserverView>(EMPTY_OBSERVER);
  const [conversation, setConversation] = useState<ConversationMessage[]>([]);
  const [sidebarTab, setSidebarTab] = useState<"observation" | "control" | "stimulus">("observation");
  const chatRef = useRef<HTMLDivElement>(null);
  const lastChatSignatureRef = useRef("");
  const [consciousnesses, setConsciousnesses] = useState<ConsciousnessSummary[]>([]);
  const [consciousnessLoading, setConsciousnessLoading] = useState(true);
  const [consciousnessError, setConsciousnessError] = useState("");
  const [managementOpen, setManagementOpen] = useState(false);
  const [openConsciousnessDialog, setOpenConsciousnessDialog] = useState(false);
  const [activePage, setActivePage] = useState<AppPage>("observatory");
  const [detail, setDetail] = useState<ConsciousnessSummary | null>(null);
  const [settings, setSettings] = useState<Settings>(EMPTY_SETTINGS);
  const [viewMode, setViewMode] = useState<ViewMode>("3d");
  const [showNavigationHint, setShowNavigationHint] = useState(true);
  const [dockPinned, setDockPinned] = useState(true);
  const [dockPeek, setDockPeek] = useState(false);
  const [navigationAutoHide, setNavigationAutoHide] = useState(() => window.localStorage.getItem("threemind.ui.navigationAutoHide") === "true");
  const [navigationPeek, setNavigationPeek] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsCategory, setSettingsCategory] = useState("visualization");
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [newKernel, setNewKernel] = useState<KernelId>("anonymous-spatial-v3");
  const [newV3NodeMode, setNewV3NodeMode] = useState<V3NodeMode>("anonymous");
  const [newModelOptions, setNewModelOptions] = useState<NewModelOptions>(DEFAULT_NEW_MODEL_OPTIONS);
  const [pendingNewName, setPendingNewName] = useState<string | null>(null);
  const [pendingDialogAction, setPendingDialogAction] = useState<"new-overwrite" | "new-snapshot" | "resume-overwrite" | "resume-snapshot" | null>(null);
  useEffect(() => {
    let frame: number | null = null;
    const publish = () => {
      frame = null;
      const snapshot = graphStore.snapshot();
      setGraph(snapshot);
      if (snapshot) setMetrics(snapshot.metrics);
    };
    const unsubscribe = graphStore.subscribe(() => {
      if (frame !== null) return;
      frame = window.requestAnimationFrame(publish);
    });
    const initial = graphStore.snapshot();
    if (initial) {
      setGraph(initial);
      setMetrics(initial.metrics);
    }
    return () => {
      unsubscribe();
      if (frame !== null) window.cancelAnimationFrame(frame);
    };
  }, [graphStore]);
  useEffect(() => {
    setTrace(hasActiveConsciousness && Boolean(metrics.trace_enabled));
  }, [hasActiveConsciousness, metrics.id, metrics.trace_enabled]);
  useEffect(() => { window.localStorage.setItem("threemind.ui.navigationAutoHide", String(navigationAutoHide)); }, [navigationAutoHide]);
  useEffect(() => () => {
    if (feedbackTimerRef.current !== undefined) window.clearTimeout(feedbackTimerRef.current);
  }, []);
  const showFeedback = useCallback((kind: OperationFeedback["kind"], nextMessage: string) => {
    if (feedbackTimerRef.current !== undefined) window.clearTimeout(feedbackTimerRef.current);
    setOperationFeedback({ kind, message: nextMessage });
    if (kind !== "pending") {
      feedbackTimerRef.current = window.setTimeout(() => setOperationFeedback(null), 4600);
    }
  }, []);
  const clearActiveProjection = useCallback(() => {
    graphStore.clear();
    setGraph(null);
    setMetrics(EMPTY_METRICS);
    setSelected(null);
    setObserver(EMPTY_OBSERVER);
    setConversation([]);
    setHasActiveConsciousness(false);
  }, [graphStore]);
  const selectNode = useCallback((node: GraphNode | null) => setSelected(node), []);
  const chatPinnedToBottomRef = useRef(true);
  const visibleConversation = useMemo(() => {
    const display = settings.conversation ?? EMPTY_SETTINGS.conversation!;
    const isBackgroundReadout = (entry: ConversationMessage) => entry.kind === "readout" && (
      Boolean(entry.background) ||
      entry.trigger === "background_active_nodes" ||
      entry.source === "background_active_nodes"
    );
    return conversation.filter((entry) => {
      if (isBackgroundReadout(entry) && !display.show_background_readouts) return false;
      if (entry.role !== "environment") return true;
      if (display.show_environment_stimuli) return true;
      if (!display.show_triggering_environment_stimuli) return false;
      return conversation.some((candidate) => {
        if (!isBackgroundReadout(candidate) || !display.show_background_readouts) return false;
        return candidate.trigger_stimulus_tick === entry.tick || (candidate.tick >= entry.tick && candidate.tick - entry.tick <= 12);
      });
    });
  }, [conversation, settings.conversation]);

  useEffect(() => {
    if (sidebarTab !== "stimulus") return;
    const latest = conversation[conversation.length - 1];
    const signature = latest ? `${latest.kind}:${latest.tick}:${latest.text}` : "";
    if (!signature || signature === lastChatSignatureRef.current) return;
    const chat = chatRef.current;
    if (!chat) return;
    lastChatSignatureRef.current = signature;
    if (chatPinnedToBottomRef.current) chat.scrollTop = chat.scrollHeight;
  }, [conversation, sidebarTab]);

  useEffect(() => {
    setShowNavigationHint(true);
    const timer = window.setTimeout(() => setShowNavigationHint(false), 6500);
    return () => window.clearTimeout(timer);
  }, [viewMode]);

  const loadSnapshots = useCallback(async () => {
    try {
      const response = await fetch(`${API}/api/snapshots`, { cache: "no-store" });
      if (!response.ok) throw new Error("无法读取存档");
      const payload = (await response.json()) as { items: Snapshot[] };
      setSnapshots(payload.items);
      setSelectedSnapshot((current) => current || payload.items[0]?.path || "");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "无法读取存档");
    }
  }, []);

  const loadConsciousnesses = useCallback(async () => {
    setConsciousnessLoading(true);
    try {
      const response = await fetch(`${API}/api/consciousnesses`, { cache: "no-store" });
      if (!response.ok) throw new Error("无法读取意识列表");
      const payload = (await response.json()) as { items?: ConsciousnessSummary[]; active_id?: string | null };
      setConsciousnesses(Array.isArray(payload.items) ? payload.items : []);
      if ("active_id" in payload) setHasActiveConsciousness(Boolean(payload.active_id));
      setConsciousnessError("");
    } catch (caught) {
      setConsciousnessError(caught instanceof Error ? caught.message : "无法读取意识列表");
    } finally {
      setConsciousnessLoading(false);
    }
  }, []);

  useEffect(() => {
    let alive = true;
    let socket: WebSocket | null = null;
    let reconnect: number | undefined;
    let archiveRefresh: number | undefined;
    let pendingSnapshot: GraphData | null = null;
    const connect = () => {
      socket = new WebSocket(`${WS_API}/api/ws/live`);
      socket.onmessage = (event) => {
        if (!alive) return;
        const payload = JSON.parse(event.data) as { type?: "empty" | "snapshot" | "snapshot_begin" | "snapshot_chunk" | "snapshot_end" | "delta"; has_active?: boolean; sequence?: number; part?: "nodes" | "edges"; items?: GraphNode[] | GraphEdge[]; graph?: GraphData; observer?: ObserverView; conversation?: ConversationMessage[]; conversation_append?: ConversationMessage[]; metrics?: Metrics; delta?: Record<string, unknown>; nodes?: GraphNode[]; edges?: GraphEdge[] };
        const acknowledge = () => {
          if (socket?.readyState === WebSocket.OPEN && typeof payload.sequence === "number") {
            socket.send(JSON.stringify({ type: "ack", sequence: payload.sequence }));
          }
        };
        if (payload.type === "empty") {
          clearActiveProjection();
          setStartupChecked(true);
          setError("");
          return;
        }
        if (payload.type === "snapshot_begin" && payload.graph) {
          setHasActiveConsciousness(true);
          setStartupChecked(true);
          pendingSnapshot = { ...payload.graph, nodes: [], edges: [] };
          if (payload.observer) setObserver(payload.observer);
          if (payload.conversation) setConversation(payload.conversation);
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
          graphStore.replace(pendingSnapshot);
          setHasActiveConsciousness(true);
          setStartupChecked(true);
          pendingSnapshot = null;
          setError("");
          return;
        }
        if (payload.type === "delta" && payload.metrics && payload.delta) {
          setHasActiveConsciousness(true);
          setStartupChecked(true);
          graphStore.applyDelta({
            metrics: payload.metrics,
            nodes: payload.nodes ?? [],
            edges: payload.edges ?? [],
            removed_nodes: payload.delta.removed_nodes as number[] | undefined,
            removed_edges: payload.delta.removed_edges as number[][] | undefined,
            removed_neighbors: payload.delta.removed_neighbors as number[][] | undefined,
          });
          if (payload.conversation_append) {
            const additions = payload.conversation_append;
            setConversation((previous) => mergeConversation(previous, additions));
            const readouts = additions.filter((entry) => entry.kind === "readout");
            if (readouts.length) {
              setObserver((previous) => {
                let next = previous;
                const appendedEvents: ObserverEvent[] = readouts.map((entry) => ({
                  id: entry.conversation_key ?? `readout-${entry.tick}-${entry.anonymous_text ?? entry.text}`,
                  tick: entry.tick,
                  occurrences: entry.occurrences ?? 1,
                  readout: entry.anonymous_text ?? entry.text,
                  anonymous_readout: entry.anonymous_text,
                  display_readout: entry.text,
                  readable_labels: entry.readable_labels,
                  label_entries: entry.label_entries,
                  internal_edges: entry.internal_edges ?? 0,
                  kind: entry.source,
                  readout_kind: entry.readout_kind,
                  start_tick: entry.start_tick,
                  end_tick: entry.end_tick,
                  classification: entry.classification,
                  rankings: entry.rankings,
                  convergence: entry.convergence,
                }));
                const eventIds = new Set(appendedEvents.map((entry) => entry.id));
                next = { ...next, events: [...next.events.filter((entry) => !eventIds.has(entry.id)), ...appendedEvents].slice(-100) };
                const snapshot = [...readouts].reverse().find((entry) => entry.readout_kind !== "temporal");
                if (snapshot) next = { ...next, current: {
                  tick: snapshot.tick,
                  text: snapshot.text,
                  anonymous_readout: snapshot.anonymous_text,
                  display_readout: snapshot.text,
                  readable_labels: snapshot.readable_labels,
                  label_entries: snapshot.label_entries,
                  node_ids: snapshot.node_ids,
                  occurrences: snapshot.occurrences ?? 1,
                  internal_edges: snapshot.internal_edges ?? 0,
                  repeatable: Boolean(snapshot.repeatable),
                } };
                const temporalEntry = [...readouts].reverse().find((entry) => entry.readout_kind === "temporal");
                if (temporalEntry) {
                  const temporalCurrent: TemporalReadout = {
                    id: temporalEntry.conversation_key ?? `temporal-${temporalEntry.tick}`,
                    tick: temporalEntry.tick,
                    occurrences: temporalEntry.occurrences ?? 1,
                    readout: temporalEntry.anonymous_text ?? temporalEntry.text,
                    anonymous_readout: temporalEntry.anonymous_text ?? temporalEntry.text,
                    display_readout: temporalEntry.text,
                    readable_labels: temporalEntry.readable_labels,
                    label_entries: temporalEntry.label_entries,
                    internal_edges: temporalEntry.internal_edges ?? 0,
                    kind: temporalEntry.source,
                    readout_kind: "temporal",
                    start_tick: temporalEntry.start_tick,
                    end_tick: temporalEntry.end_tick,
                    classification: temporalEntry.classification ?? "unresolved",
                    rankings: temporalEntry.rankings ?? [],
                    convergence: temporalEntry.convergence,
                    node_ids: temporalEntry.node_ids ?? [],
                    window: temporalEntry.window,
                  };
                  next = { ...next, temporal: { current: temporalCurrent, active_windows: next.temporal?.active_windows ?? [] } };
                }
                return next;
              });
            }
          }
        } else if (payload.graph) {
          graphStore.replace(payload.graph);
          setHasActiveConsciousness(true);
          setStartupChecked(true);
          if (payload.observer) setObserver(payload.observer);
          if (payload.conversation) setConversation(payload.conversation);
        }
        setError("");
      };
      socket.onerror = () => socket?.close();
      socket.onclose = () => {
        if (!alive) return;
        setError("无法连接 Core。请确认另一终端正在运行：python -m threemind serve");
        reconnect = window.setTimeout(connect, 4000);
      };
    };
    const refreshOnce = async () => {
      try {
        // Complete graph transfer belongs to the acknowledged WebSocket
        // stream. Avoid serialising a second full graph during startup.
        const response = await fetch(`${API}/api/status`, { cache: "no-store" });
        if (!response.ok) throw new Error("Core 未响应");
        const status = (await response.json()) as { has_active?: boolean; metrics?: Metrics | null };
        setStartupChecked(true);
        if (status.has_active === false || !status.metrics) {
          if (alive) {
            clearActiveProjection();
            setError("");
          }
          return;
        }
        const [observerResponse, conversationResponse] = await Promise.all([
          fetch(`${API}/api/observer`, { cache: "no-store" }),
          fetch(`${API}/api/conversation`, { cache: "no-store" }),
        ]);
        const observerData = observerResponse.ok ? (await observerResponse.json()) as ObserverView : null;
        if (alive) {
          setHasActiveConsciousness(true);
          setMetrics(status.metrics);
          if (observerData) setObserver(observerData);
          if (conversationResponse.ok) setConversation(((await conversationResponse.json()) as { items: ConversationMessage[] }).items);
          setError("");
        }
      } catch (caught) {
        if (alive) {
          setError(
            "无法连接 Core。请确认另一终端仍在运行：python -m threemind serve"
          );
        }
      }
    };
    void refreshOnce();
    connect();
    void loadSnapshots();
    void loadConsciousnesses();
    const refreshArchiveIndex = async () => {
      try {
        const response = await fetch(`${API}/api/archive-index`, { cache: "no-store" });
        if (!response.ok) return;
        const index = await response.json() as { running?: boolean; writer?: { pending?: number; queued?: number } };
        // `pending` is the queue depth; `queued` also includes the file that
        // the single archive writer is currently compressing.  Keep the
        // lightweight catalogue refresh alive for both cases so a just-saved
        // snapshot appears without a page reload.
        const busyIndex = Boolean(index.running)
          || Number(index.writer?.pending ?? 0) > 0
          || Number(index.writer?.queued ?? 0) > 0;
        if (busyIndex) {
          void loadSnapshots();
          void loadConsciousnesses();
        } else if (archiveRefresh !== undefined) {
          window.clearInterval(archiveRefresh);
          archiveRefresh = undefined;
        }
      } catch {
        // The normal Core reconnect path reports transport failures.
      }
    };
    void refreshArchiveIndex();
    archiveRefresh = window.setInterval(() => { void refreshArchiveIndex(); }, 1500);
    return () => {
      alive = false;
      socket?.close();
      if (reconnect) window.clearTimeout(reconnect);
      if (archiveRefresh !== undefined) window.clearInterval(archiveRefresh);
    };
  }, [clearActiveProjection, graphStore, loadConsciousnesses, loadSnapshots]);

  const run = async (name: string, args: Record<string, unknown> = {}, note?: string, options: RunOptions = {}) => {
    setBusy(true);
    setError("");
    if (options.feedback !== false) {
      showFeedback("pending", options.pendingMessage ?? (locale === "en" ? "Working…" : "正在处理…"));
    }
    try {
      const result = await command(name, args);
      if (name === "new" && result.graph) {
        graphStore.replace(result.graph as GraphData);
        setHasActiveConsciousness(true);
        setStartupChecked(true);
      }
      const successMessage = note ?? result.path ?? (locale === "en" ? "Completed." : "操作已完成。");
      setMessage(successMessage);
      if (options.feedback !== false) showFeedback("success", successMessage);
      return result;
    } catch (caught) {
      const failureMessage = caught instanceof Error ? caught.message : (locale === "en" ? "Operation failed." : "操作失败。");
      setError(failureMessage);
      if (options.feedback !== false) showFeedback("error", failureMessage);
    } finally {
      setBusy(false);
    }
  };

  const openSettings = async (category = "visualization") => {
    setSettingsCategory(category);
    setSettingsOpen(true);
    setSettingsLoading(true);
    try {
      const response = await fetch(`${API}/api/settings`, { cache: "no-store" });
      if (!response.ok) throw new Error("无法读取设置");
      const loaded = normalizeSettings(await response.json() as Settings);
      setSettings(loaded);
      setViewMode(loaded.visualization?.mode ?? "3d");
      setApiKey("");
    } catch (caught) {
      const failureMessage = caught instanceof Error ? caught.message : (locale === "en" ? "Unable to load settings." : "无法读取设置。");
      setError(failureMessage);
      showFeedback("error", failureMessage);
    } finally {
      setSettingsLoading(false);
    }
  };

  const saveSettings = async () => {
    const notificationPayload: Record<string, unknown> = { ...settings.notifications };
    delete notificationPayload.resend_api_key_configured;
    delete notificationPayload.resend_api_key_hint;
    if (apiKey.trim()) notificationPayload.resend_api_key = apiKey.trim();
    const result = await run(
      "settings_update",
      { settings: { notifications: notificationPayload, observer: settings.observer, visualization: settings.visualization, archive: settings.archive, ai: settings.ai, stimuli: settings.stimuli, body: settings.body, network: settings.network, conversation: settings.conversation, ui: { ...(settings.ui ?? {}), locale } } },
      "设置已保存",
      { pendingMessage: locale === "en" ? "Saving settings…" : "正在保存设置…" },
    );
    if (result?.settings) {
      const saved = normalizeSettings(result.settings as Settings);
      setSettings(saved);
      setViewMode(saved.visualization?.mode ?? "3d");
    }
    setApiKey("");
    return result;
  };

  const changeLocale = async (next: Locale) => {
    setLocale(next);
    try {
      const result = await command("settings_update", { settings: { ui: { ...(settings.ui ?? {}), locale: next } } });
      if (result?.settings) setSettings(normalizeSettings(result.settings as Settings));
    } catch {
      // Local selection remains useful even if Core is temporarily unavailable.
    }
  };

  const toggleStimulusSource = async (source: "manual" | "ai" | "ambient", enabled: boolean) => {
    const current = settings.stimuli ?? EMPTY_SETTINGS.stimuli!;
    const key = source === "ambient" ? "background_enabled" : `${source}_enabled`;
    const next = { ...current, [key]: enabled } as StimuliSettings;
    const activeCount = [next.manual_enabled, next.ai_enabled, next.background_enabled].filter(Boolean).length;
    if (!enabled && activeCount === 0 && !window.confirm("此操作将取消仅剩的刺激，使该意识立即死亡，并保存遗照。是否确认？")) return;
    const result = await run("settings_update", { settings: { stimuli: next }, confirm_source_shutdown: !enabled && activeCount === 0 }, enabled ? "刺激来源已启用" : "刺激来源已关闭");
    if (result?.settings) setSettings(normalizeSettings(result.settings as Settings));
  };

  const changeView = async (mode: ViewMode) => {
    const next = { ...settings, visualization: { ...settings.visualization, mode, ...(mode === "3d" && settings.visualization.renderer === "canvas" ? { renderer: "threejson" as const } : {}) } };
    setSettings(next);
    setViewMode(mode);
    const result = await run("settings_update", { settings: { visualization: { mode } } }, `切换到 ${mode.toUpperCase()} 观察模式`);
    if (result?.settings) setSettings(normalizeSettings(result.settings as Settings));
  };

  const testNotification = async () => {
    // The test button is expected to test the values currently visible in the
    // form, including a newly entered write-only Resend key.  Persist first so
    // it never accidentally tests an older server-side configuration.
    const saved = await saveSettings();
    if (!saved) return;
    const result = await run("notification_test", {}, "测试邮件请求已执行");
    if (result?.delivery?.state !== "sent") {
      setError(result?.delivery?.detail ?? "测试邮件未发出；请检查通知配置。");
    }
  };

  const submitStimulus = async (event: FormEvent) => {
    event.preventDefault();
    if (!text.trim()) return;
    const submitted = text;
    setText("");
    const result = await run("stimulate", { text: submitted, intensity, source: "ui-text" }, "刺激已进入环境");
    if (Array.isArray(result?.conversation_append)) setConversation((previous) => mergeConversation(previous, result.conversation_append as ConversationMessage[]));
  };

  const changeTrace = async (next: boolean) => {
    const result = await run(next ? "trace_start" : "trace_stop");
    if (result) setTrace(Boolean(result.enabled ?? next));
  };

  const toggleTrace = async () => changeTrace(!trace);

  const stop = async () => {
    if (!window.confirm("停止外界刺激将结束当前意识，并自动保存遗照。确定继续吗？")) return;
    await run("stop", {}, "当前意识已死亡，遗照已保存");
  };

  const createNew = async (name?: string) => {
    const isV3 = newKernel === "anonymous-spatial-v3";
    const spatial = isV3 && newModelOptions.spatial_enabled;
    const parameters: Record<string, number | boolean | string | null> = {
      attention_budget: newModelOptions.attention_budget,
      attention_competition_enabled: newModelOptions.attention_competition_enabled,
      edge_adaptation_limit: newModelOptions.edge_adaptation_limit,
      propagation_limit: newModelOptions.propagation_limit,
      edge_birth_activation_product_min: newModelOptions.edge_birth_activation_product_min,
      propagation_activation_min: newModelOptions.propagation_activation_min,
      local_novelty_gain: newModelOptions.local_novelty_gain,
      novelty_touch_reference: newModelOptions.novelty_touch_reference,
      association_window: newModelOptions.association_window,
      edge_birth_policy: newModelOptions.edge_birth_policy,
      propagation_gain: newModelOptions.propagation_gain,
      learning_rate: newModelOptions.learning_rate,
      edge_decay: newModelOptions.edge_decay,
      stability_gain: newModelOptions.stability_gain,
      stability_decay: newModelOptions.stability_decay,
      consolidation_repeat_gain: newModelOptions.consolidation_repeat_gain,
      consolidation_associative_gain: newModelOptions.consolidation_associative_gain,
      consolidation_intensity_gain: newModelOptions.consolidation_intensity_gain,
      node_prune_after: newModelOptions.node_prune_after,
      sensory_channels: newModelOptions.sensory_channels,
      max_nodes: newModelOptions.max_nodes,
      max_edges: newModelOptions.max_edges,
      homeostasis_enabled: newModelOptions.homeostasis_enabled,
      target_total_activation: newModelOptions.target_total_activation,
      topology_inhibition_enabled: newModelOptions.topology_inhibition_enabled,
      inhibition_generation_gain: newModelOptions.inhibition_generation_gain,
      inhibition_decay: newModelOptions.inhibition_decay,
      inhibition_diffusion: newModelOptions.inhibition_diffusion,
      inhibition_response_gain: newModelOptions.inhibition_response_gain,
      inhibition_saturation: newModelOptions.inhibition_saturation,
      inhibition_propagation_min: newModelOptions.inhibition_propagation_min,
      energy_simulation_enabled: newModelOptions.energy_simulation_enabled,
      energy_initial_reserve: newModelOptions.energy_initial_reserve,
      energy_capacity: newModelOptions.energy_capacity,
      energy_direct_cost: newModelOptions.energy_direct_cost,
      energy_associative_cost: newModelOptions.energy_associative_cost,
      energy_inhibition_cost: newModelOptions.energy_inhibition_cost,
      irreversible_energy_death_enabled: newModelOptions.irreversible_energy_death_enabled,
      energy_maintenance_cost_per_node: newModelOptions.energy_maintenance_cost_per_node,
      energy_maintenance_cost_per_edge: newModelOptions.energy_maintenance_cost_per_edge,
      energy_starvation_structural_decay: newModelOptions.energy_starvation_structural_decay,
      energy_starvation_death_ticks: newModelOptions.energy_starvation_death_ticks,
      ...(spatial ? { neighborhood_enabled: true, spatial_radius: newModelOptions.spatial_radius, spatial_competition: newModelOptions.spatial_competition } : {}),
    };
    const v3Encoding = newV3NodeMode === "anonymous" ? "anonymous-distributed" : newV3NodeMode;
    const manifest = {
      kernel_id: newKernel,
      // V3 graph nodes remain anonymous in every sensory mode. Readable
      // material lives in the package annotation table, outside dynamics.
      node_payload: newKernel === "labeled-feature-v1" ? "labeled" : "anonymous",
      spatial_embedding: spatial,
      spatial_dimensions: spatial ? newModelOptions.spatial_dimensions : 0,
      adapter_bindings: [
        { adapter_id: "ambient-field", enabled: newModelOptions.random_ambient_enabled, route: "environment.frame -> input.bus" },
        { adapter_id: "body-background", enabled: false, upstream: "ambient-field", route: "environment.frame -> sensory.frame -> input.bus" },
        { adapter_id: "energy-budget", enabled: false, route: "energy.supply -> core.resource" },
        { adapter_id: "host-telemetry-field", enabled: newModelOptions.host_telemetry_enabled, route: "host.telemetry -> sensory.frame -> input.bus" },
        { adapter_id: "process-telemetry-field", enabled: newModelOptions.process_telemetry_enabled, route: "process.telemetry -> sensory.frame -> input.bus" },
        { adapter_id: "runtime-telemetry-field", enabled: newModelOptions.runtime_telemetry_enabled, route: "runtime.telemetry -> sensory.frame -> input.bus" },
        { adapter_id: "auditory-sensor", enabled: false, route: "audio.pcm -> sensory.frame -> input.bus" },
        { adapter_id: "visual-sensor", enabled: false, route: "image.pixels|video.pixels -> sensory.frame -> input.bus" },
        { adapter_id: "acoustic-output-organ", enabled: false, route: "output.bus -> audio.control" },
        { adapter_id: "activation-image-projector", enabled: false, route: "output.bus -> image.pixels" },
      ],
      parameters: { ...Object.fromEntries(Object.entries(parameters).filter(([, value]) => value !== null)), sensory_encoding: isV3 ? v3Encoding : newKernel === "labeled-feature-v1" ? "legacy-labeled" : "anonymous-distributed" },
    };
    const result = await run(
      "new",
      { seed: Date.now() % 2147483647, name, manifest },
      "新的意识已诞生",
      { pendingMessage: locale === "en" ? "Creating consciousness…" : "正在创建意识…" },
    );
    if (result) {
      setTrace(false);
      void loadConsciousnesses();
    }
    return result;
  };

  const openStoredConsciousness = async (consciousnessId: string, snapshotPath?: string) => {
    if (busy) return;
    setBusy(true);
    setError("");
    showFeedback("pending", locale === "en" ? "Opening consciousness…" : "正在打开意识…");
    try {
      const response = await fetch(`${API}/api/consciousnesses/${encodeURIComponent(consciousnessId)}/${snapshotPath ? "continue" : "activate"}`, {
        method: "POST",
        headers: snapshotPath ? { "Content-Type": "application/json" } : undefined,
        body: snapshotPath ? JSON.stringify({ path: snapshotPath }) : undefined,
      });
      const payload = await response.json() as { detail?: string; metrics?: Metrics };
      if (!response.ok) throw new Error(payload.detail ?? (locale === "en" ? "Unable to open consciousness." : "无法打开意识。"));
      if (payload.metrics) setMetrics(payload.metrics);
      setHasActiveConsciousness(true);
      setStartupChecked(true);
      setOpenConsciousnessDialog(false);
      await Promise.all([loadConsciousnesses(), loadSnapshots()]);
      showFeedback("success", locale === "en" ? "Consciousness opened and running." : "意识已打开并继续运行。");
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : (locale === "en" ? "Unable to open consciousness." : "无法打开意识。");
      setError(detail);
      showFeedback("error", detail);
    } finally {
      setBusy(false);
    }
  };

  const importAndOpenConsciousness = async (file: File) => {
    if (busy) return;
    setBusy(true);
    setError("");
    showFeedback("pending", locale === "en" ? "Importing model package…" : "正在导入模型包…");
    try {
      const form = new FormData();
      form.append("file", file);
      const importedResponse = await fetch(`${API}/api/packages/import`, { method: "POST", body: form });
      const imported = await importedResponse.json() as { detail?: string; consciousness_id?: string };
      if (!importedResponse.ok || !imported.consciousness_id) throw new Error(imported.detail ?? (locale === "en" ? "Package import failed." : "模型包导入失败。"));
      const activateResponse = await fetch(`${API}/api/consciousnesses/${encodeURIComponent(imported.consciousness_id)}/activate`, { method: "POST" });
      const activated = await activateResponse.json() as { detail?: string; metrics?: Metrics };
      if (!activateResponse.ok) throw new Error(activated.detail ?? (locale === "en" ? "Imported package could not be opened." : "导入的模型包无法打开。"));
      if (activated.metrics) setMetrics(activated.metrics);
      setHasActiveConsciousness(true);
      setStartupChecked(true);
      setOpenConsciousnessDialog(false);
      await Promise.all([loadConsciousnesses(), loadSnapshots()]);
      showFeedback("success", locale === "en" ? "Package imported and opened." : "模型包已导入并打开。");
    } catch (caught) {
      const detail = caught instanceof Error ? caught.message : (locale === "en" ? "Package import failed." : "模型包导入失败。");
      setError(detail);
      showFeedback("error", detail);
    } finally {
      setBusy(false);
    }
  };
  const createNewWithChoice = async (choice: "overwrite" | "snapshot") => {
    const name = pendingNewName;
    if (!name || pendingDialogAction) return;
    setPendingDialogAction(choice === "snapshot" ? "new-snapshot" : "new-overwrite");
    try {
      if (choice === "snapshot") {
        const snapshot = await saveSnapshot();
        if (!snapshot) return;
      }
      const created = await createNew(name);
      if (created) setPendingNewName(null);
    } finally {
      setPendingDialogAction(null);
    }
  };

  const defaultName = () => `意识-${new Date().toLocaleString("zh-CN", { hour12: false }).replace(/[/: ]/g, "-")}`;
  const saveSnapshot = async (label?: string) => {
    const result = await run(
      "snapshot",
      label ? { label } : {},
      "快照已保存",
      { pendingMessage: locale === "en" ? "Saving snapshot…" : "正在保存快照…" },
    );
    if (result) {
      void loadSnapshots();
      void loadConsciousnesses();
    }
    return result;
  };
  const askSnapshot = () => {
    if (settings.archive?.prompt_for_snapshot_name ?? true) setNameDialog({ kind: "snapshot", initial: `${metrics.name ?? "意识"}-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}` });
    else void saveSnapshot();
  };

  const restore = async (mode: "resume" | "clone") => {
    if (!selectedSnapshot) return;
    await run(mode, { path: selectedSnapshot }, mode === "resume" ? "已继续该意识" : "已从快照诞生新意识");
  };
  const resumeWithChoice = async (choice: "overwrite" | "snapshot") => {
    const item = pendingResume;
    if (!item || pendingDialogAction) return;
    setPendingDialogAction(choice === "snapshot" ? "resume-snapshot" : "resume-overwrite");
    try {
      if (choice === "snapshot") {
        const snapshot = await saveSnapshot();
        if (!snapshot) return;
      }
      const result = await run(
        "resume",
        { path: item.path },
        "已继续该意识",
        { pendingMessage: locale === "en" ? "Restoring consciousness…" : "正在恢复意识…" },
      );
      if (result) {
        setPendingResume(null);
        setArchiveOpen(false);
        void loadSnapshots();
        void loadConsciousnesses();
      }
    } finally {
      setPendingDialogAction(null);
    }
  };

  const stateLabel: Record<string, string> = {
    active: tr(locale, "active"),
    unstable: tr(locale, "unstable"),
    unresponsive: tr(locale, "unresponsive"),
    dead: tr(locale, "dead"),
    connecting: tr(locale, "connecting"),
  };
  const dead = metrics.life_state === "dead";
  const navigate = (page: Exclude<AppPage, "detail">) => {
    setActivePage(page);
    if (page === "management" || page === "stimuli" || page === "interpretations") void loadConsciousnesses();
  };
  const dockOpen = dockPinned || dockPeek;
  const recentConsciousnesses = [...consciousnesses]
    .sort((left, right) => Number(right.saved_at ?? 0) - Number(left.saved_at ?? 0))
    .slice(0, 6);

  return (
    <I18nContext.Provider value={locale}>
    <div className="app-shell">
    {navigationAutoHide && <button className="topbar-reveal" type="button" onMouseEnter={() => setNavigationPeek(true)} onFocus={() => setNavigationPeek(true)} onClick={() => setNavigationPeek(true)} aria-label={locale === "en" ? "Show top navigation" : "显示顶部导航"} />}
    <div className={`chrome-shell ${navigationAutoHide ? "auto-hide" : ""} ${navigationPeek ? "is-revealed" : ""}`} onMouseEnter={() => setNavigationPeek(true)} onMouseLeave={() => { if (navigationAutoHide) setNavigationPeek(false); }}>
      <AppChrome
        locale={locale}
        onLocaleChange={(next) => void changeLocale(next)}
        activePage={activePage}
        onNavigate={navigate}
        onOpenArchives={() => { void loadSnapshots(); setArchiveOpen(true); }}
        onOpenSettings={(category) => void openSettings(category)}
      />
    </div>
    {operationFeedback && <div className={`ui-operation-feedback ${operationFeedback.kind}`} role={operationFeedback.kind === "error" ? "alert" : "status"} aria-live="polite">
      {operationFeedback.kind === "pending" ? <span className="ui-spinner" aria-hidden="true" /> : <span className="ui-operation-mark" aria-hidden="true">{operationFeedback.kind === "success" ? "✓" : "!"}</span>}
      <span>{operationFeedback.message}</span>
      {operationFeedback.kind !== "pending" && <button type="button" onClick={() => setOperationFeedback(null)} aria-label={locale === "en" ? "Dismiss notification" : "关闭提示"}>×</button>}
    </div>}
    <main className={`lab ${activePage !== "observatory" ? "management-layout" : ""} ${activePage === "observatory" && !dockOpen ? "right-dock-closed" : ""}`}>
      {activePage === "observatory" ? !startupChecked ? <section className="startup-empty-stage is-loading">
        <span className="ui-spinner" aria-hidden="true" />
        <strong>{locale === "en" ? "Connecting to ThreeMind Core…" : "正在连接 ThreeMind Core…"}</strong>
      </section> : !hasActiveConsciousness ? <section className="startup-empty-stage">
        <div className="startup-empty-card">
          <span className="startup-empty-mark" aria-hidden="true">◇</span>
          <h1>{locale === "en" ? "No consciousness is running" : "当前没有运行中的意识"}</h1>
          <p>{locale === "en" ? "Create a new consciousness, or continue a stored one from its latest snapshot." : "创建一个新意识，或从已保存意识的最新快照继续。"}</p>
          <div className="startup-empty-actions">
            <button className="primary" type="button" disabled={busy} onClick={() => setNameDialog({ kind: "new", initial: defaultName() })}>{locale === "en" ? "New consciousness" : "新建意识"}</button>
            <button type="button" disabled={busy} onClick={() => { void loadConsciousnesses(); setOpenConsciousnessDialog(true); }}>{locale === "en" ? "Open consciousness" : "打开意识"}</button>
          </div>
          <section className="startup-recent">
            <header><strong>{locale === "en" ? "Recently used" : "最近运行的意识"}</strong><button type="button" onClick={() => void loadConsciousnesses()} disabled={consciousnessLoading}>{locale === "en" ? "Refresh" : "刷新"}</button></header>
            <div>
              {recentConsciousnesses.map((item) => <button type="button" key={item.id} disabled={busy} onClick={() => void openStoredConsciousness(item.id)}>
                <span><strong>{item.name}</strong><small>{item.kernel ?? "unified-associative"} · tick {item.metrics?.tick ?? item.latest?.metrics?.tick ?? 0}</small></span>
                <time>{formatSnapshotTime(item.saved_at)}</time>
              </button>)}
              {!recentConsciousnesses.length && <p>{consciousnessLoading ? (locale === "en" ? "Loading archives…" : "正在读取档案…") : (locale === "en" ? "No recently saved consciousness." : "还没有最近保存的意识。")}</p>}
            </div>
          </section>
        </div>
      </section> : <>
       <section className="stage observatory-stage">
        <div className="observatory-context" aria-label={locale === "en" ? "Observatory context" : "观测上下文"}>
          <span>{locale === "en" ? "LIVE OBSERVATORY" : "实时观测台"}</span>
          <strong>{metrics.name ?? (locale === "en" ? "Unnamed consciousness" : "未命名意识")}</strong>
        </div>
        <div className="stage-actions">
          {showNavigationHint && (
            <div className="navigation-hint" role="status">
              <button type="button" onClick={() => setShowNavigationHint(false)} aria-label="关闭导航提示">×</button>
              <strong>{viewMode.toUpperCase()} 观察投影</strong>
              <span>滚轮缩放 · 右键拖动平移 · WASD 移动 · F 复位{viewMode === "3d" ? " · 左键旋转 · Q/E 深度移动" : ""}</span>
            </div>
          )}
        </div>
        {settings.visualization.renderer === "canvas" ? (
          <NetworkCanvas graph={graph} onSelect={selectNode} shape={settings.visualization.canvas_shape} continuousMotion={settings.visualization.continuous_motion} />
        ) : settings.visualization.renderer === "three" ? (
          <Suspense fallback={<div className="graph-loading">正在载入三维观察器…</div>}><GraphViewport key={`${viewMode}-${settings.visualization.three_shape}-${settings.visualization.style}`} graph={graph} mode={viewMode} shape={settings.visualization.three_shape} style={settings.visualization.style} continuousMotion={settings.visualization.continuous_motion} /></Suspense>
        ) : (
          <Suspense fallback={<div className="graph-loading">{locale === "en" ? "Loading ThreeJSON GPU projection…" : "正在加载 ThreeJSON GPU 投影…"}</div>}><ThreeJsonGraphViewport key={`threejson:${viewMode}:${settings.visualization.three_shape}:${settings.visualization.style}:${settings.visualization.continuous_motion}`} store={graphStore} mode={viewMode} shape={settings.visualization.three_shape} style={settings.visualization.style} continuousMotion={settings.visualization.continuous_motion} /></Suspense>
        )}
        {selected && (
          <div className="selected">
            <strong>{selected.feature}</strong>
            <span>
              激活 {selected.activation.toFixed(3)} · 稳定 {selected.stability.toFixed(3)} ·
              触达 {selected.touch_count}{selected.cluster ? ` · 空间簇 ${selected.cluster}` : ""}
            </span>
          </div>
        )}
        <div className={`status-pill ${dead ? "dead" : ""}`}>
          <i className="status-dot" />
          {stateLabel[metrics.life_state] ?? metrics.life_state} · tick {metrics.tick}
          {metrics.death_reason ? ` · ${metrics.death_reason}` : ""}
        </div>
        <div className="legend" aria-label="节点状态图例">
          <span><i className="direct" />{tr(locale, "directTouch")}</span>
          <span><i className="associated" />{tr(locale, "associatedTouch")}</span>
          <span><i className="resting" />{tr(locale, "residual")}</span>
        </div>
        {!dockPinned && <button className="dock-reveal" type="button" onMouseEnter={() => setDockPeek(true)} onFocus={() => setDockPeek(true)} onClick={() => setDockPeek((value) => !value)} aria-label={locale === "en" ? "Show observer dock" : "显示观测抽屉"}>‹</button>}
       </section>

       <aside
        className={`sidebar observer-dock sidebar-${sidebarTab} ${dockOpen ? "is-open" : "is-hidden"}`}
        onMouseEnter={() => setDockPeek(true)}
        onMouseLeave={() => { if (!dockPinned) setDockPeek(false); }}
       >
        <nav className="sidebar-tabs" aria-label="右侧面板">
          <div className="dock-tab-heading"><span>{locale === "en" ? "Observer dock" : "观测抽屉"}</span><button type="button" className={dockPinned ? "is-pinned" : ""} aria-pressed={dockPinned} onClick={() => { setDockPinned((value) => !value); setDockPeek(true); }} title={dockPinned ? (locale === "en" ? "Unpin dock" : "取消钉住") : (locale === "en" ? "Pin dock" : "钉住抽屉")}><DockPinIcon pinned={dockPinned} /></button></div>
          <button type="button" className={sidebarTab === "observation" ? "active" : ""} onClick={() => setSidebarTab("observation")}>{tr(locale, "observation")}</button>
          <button type="button" className={sidebarTab === "control" ? "active" : ""} onClick={() => setSidebarTab("control")}>{tr(locale, "control")}</button>
          <button type="button" className={sidebarTab === "stimulus" ? "active" : ""} onClick={() => setSidebarTab("stimulus")}>{tr(locale, "stimulus")}</button>
        </nav>
        {error && <div className="sidebar-error error">{error}</div>}

        <div className={`sidebar-panel ${sidebarTab}`}>
          {sidebarTab === "observation" && <>
            <div className="consciousness-name"><span>{tr(locale, "currentConsciousness")}</span><strong>{metrics.name ?? "Unnamed consciousness"}</strong><button type="button" onClick={() => setNameDialog({ kind: "new", initial: metrics.name ?? defaultName() })}>{tr(locale, "rename")}</button></div>
            <h2>{tr(locale, "observation")}</h2>
            <div className="metrics">
              <div className="metric"><strong>{metrics.node_count}</strong><span>{tr(locale, "node")}</span></div>
              <div className="metric"><strong>{metrics.edge_count}</strong><span>{tr(locale, "edge")}</span></div>
              <div className="metric"><strong>{metrics.active_nodes}</strong><span>{tr(locale, "nodeActivating")}</span></div>
              <div className="metric"><strong>{metrics.mean_stability.toFixed(3)}</strong><span>{tr(locale, "meanConsolidation")}</span></div>
              {metrics.topology_inhibition_enabled && <>
                <div className="metric"><strong>{Number(metrics.total_inhibition ?? 0).toFixed(3)}</strong><span>{locale === "en" ? "total inhibition" : "总抑制势"}</span></div>
                <div className="metric"><strong>{metrics.inhibited_nodes ?? 0}</strong><span>{locale === "en" ? "inhibited nodes" : "受抑节点"}</span></div>
              </>}
            </div>
            {((metrics.queued_stimuli ?? 0) > 0 || typeof metrics.input_epoch === "number") && <div className="spatial-summary input-queue-summary"><span>{tr(locale, "inputQueue")} {metrics.queued_stimuli ?? 0}</span><span>{tr(locale, "inputEpoch")} {metrics.input_epoch ?? 0}</span></div>}
            {metrics.spatial_embedding && <div className="spatial-summary"><span>{metrics.spatial_dimensions ?? 0}D 空间基底</span><span>{metrics.spatial_neighbor_edges ?? 0} 邻域连接</span><span>{metrics.spatial_clusters ?? 0} 局部簇</span></div>}
            <section className="model-observation" aria-label="当前模型信息">
              <h2>{tr(locale, "currentModel")}</h2>
              <div className="model-facts">
                <span><small>{tr(locale, "formatVersion")}</small><b>{graph?.manifest?.package_schema_version ?? "3.0.0"}</b></span>
                <span><small>{tr(locale, "kernel")}</small><b>{graph?.manifest?.kernel_id ?? metrics.kernel_id ?? "Unknown"}</b></span>
                <span><small>{tr(locale, "nodeRepresentation")}</small><b>{graph?.manifest?.node_payload === "anonymous" ? tr(locale, "anonymousNodes") : graph?.manifest?.node_payload === "labeled" ? tr(locale, "labeledNodes") : "Unknown"}</b></span>
                <span><small>{tr(locale, "sensoryEncoding")}</small><b>{String(graph?.manifest?.parameters?.sensory_encoding ?? "anonymous-distributed")}</b></span>
                <span><small>{tr(locale, "edge")}</small><b>{graph?.manifest?.weighted_edges === false ? tr(locale, "unweightedEdges") : tr(locale, "weightedEdges")}</b></span>
                <span><small>{tr(locale, "spatialEmbedding")}</small><b>{(graph?.manifest?.spatial_embedding ?? metrics.spatial_embedding) ? tr(locale, "enabled") : tr(locale, "notEnabled")}</b></span>
                <span><small>{tr(locale, "spatialDimensions")}</small><b>{(graph?.manifest?.spatial_embedding ?? metrics.spatial_embedding) ? `${graph?.manifest?.spatial_dimensions ?? metrics.spatial_dimensions ?? 0}D` : "—"}</b></span>
                {(graph?.manifest?.spatial_embedding ?? metrics.spatial_embedding) && <span><small>邻域半径</small><b>{String(graph?.manifest?.parameters?.spatial_radius ?? "默认")}</b></span>}
                {(graph?.manifest?.spatial_embedding ?? metrics.spatial_embedding) && <span><small>空间竞争</small><b>{String(graph?.manifest?.parameters?.spatial_competition ?? "0")}</b></span>}
                <span><small>{locale === "en" ? "Local inhibition" : "局部抑制"}</small><b>{metrics.topology_inhibition_enabled ? tr(locale, "enabled") : tr(locale, "notEnabled")}</b></span>
                <span><small>{locale === "en" ? "Energy simulation" : "能量模拟"}</small><b>{metrics.energy_simulation_enabled ? tr(locale, "enabled") : tr(locale, "notEnabled")}</b></span>
                {metrics.energy_simulation_enabled && <span><small>{locale === "en" ? "Energy reserve" : "能量储备"}</small><b>{Number(metrics.energy_reserve ?? 0).toFixed(4)} / {Number(metrics.energy_capacity ?? 0).toFixed(4)}</b></span>}
              </div>
            </section>
            <section className="section">
              <h2>{locale === "en" ? "Single-tick readout" : "截面被动读出"}</h2>
              <p className="readout-text">{localizeStructuralReadout(locale, observer.current.text)}</p>
              {observer.current.anonymous_readout && observer.current.anonymous_readout !== observer.current.text && <p className="readout-anonymous">{observer.current.anonymous_readout}{observer.current.node_ids?.length ? ` · nodes ${observer.current.node_ids.join(", ")}` : ""}</p>}
              <p className="readout-meta">{locale === "en" ? `Occurrences ${observer.current.occurrences} · internal edges ${observer.current.internal_edges}` : `重复 ${observer.current.occurrences} 次 · 内部连接 ${observer.current.internal_edges}`}</p>
              {observer.events.filter((event) => event.readout_kind !== "temporal").slice(-1).map((event) => (
                <div className="observation-alert" key={event.id}>
                  <strong>{locale === "en" ? "Repeatable structure detected" : "检测到可重复结构"}</strong>
                  <span>tick {event.tick} · {localizeStructuralReadout(locale, event.display_readout ?? event.readout)}</span>
                  {event.delivery && <span>{locale === "en" ? "Email" : "邮件"}：{event.delivery.state ?? (locale === "en" ? "pending" : "等待处理")}</span>}
                </div>
              ))}
            </section>
            <section className="section temporal-readout-section">
              <h2>{locale === "en" ? "Temporal-window readout" : "时间区间读出"}</h2>
              {observer.temporal?.current ? <>
                <p className="readout-text">{localizeStructuralReadout(locale, observer.temporal.current.display_readout ?? observer.temporal.current.anonymous_readout)}</p>
                {observer.temporal.current.display_readout !== observer.temporal.current.anonymous_readout && <p className="readout-anonymous">{observer.temporal.current.anonymous_readout} · nodes {observer.temporal.current.node_ids.join(", ")}</p>}
                <p className="readout-meta">tick {observer.temporal.current.start_tick}–{observer.temporal.current.end_tick} · {temporalClassificationText(locale, observer.temporal.current.classification)} · {locale === "en" ? "tail" : "响应尾段"} {observer.temporal.current.window?.tail_ticks ?? 0} tick</p>
                {observer.temporal.current.rankings?.length > 0 && <ol className="temporal-ranking-list">{observer.temporal.current.rankings.slice(0, 5).map((row) => <li key={row.node_id}><span>node {row.node_id}</span><small>{locale === "en" ? "active" : "激活"} {row.active_ticks} tick · ∫ {row.excess_activation_integral.toFixed(3)}</small></li>)}</ol>}
              </> : <p className="readout-meta">{observer.temporal?.active_windows?.length ? (locale === "en" ? `${observer.temporal.active_windows.length} response window(s) are being observed.` : `正在观测 ${observer.temporal.active_windows.length} 个响应时窗。`) : (locale === "en" ? "No completed temporal response yet." : "尚无已完成的时序响应。")}</p>}
            </section>
          </>}

          {sidebarTab === "control" && <>
            <section className="section compact-view-section">
              <h2>记录与生命周期</h2>
              <div className="actions">
                <button type="button" onClick={askSnapshot} disabled={busy}>保存快照</button>
                <button type="button" onClick={() => void run("portrait")} disabled={busy}>导出遗照</button>
                <button type="button" onClick={() => void toggleTrace()} disabled={busy || dead}>{trace ? "停止详细记录" : "开始详细记录"}</button>
                <button type="button" onClick={() => setNameDialog({ kind: "new", initial: defaultName() })} disabled={busy}>新意识</button>
                <button className="danger" type="button" onClick={() => void stop()} disabled={busy || dead}>停止刺激</button>
              </div>
              <p className="message">{message}</p>
            </section>
            <section className="section">
              <h2>快照与遗照</h2>
              <div className="field">
                <label htmlFor="snapshot">选择存档</label>
                <select id="snapshot" value={selectedSnapshot} onChange={(event) => setSelectedSnapshot(event.target.value)} disabled={busy || snapshots.length === 0}>
                  {snapshots.length === 0 && <option value="">{locale === "en" ? "No archive available" : "没有可用存档"}</option>}
                  {snapshots.map((snapshot) => <option key={snapshot.path} value={snapshot.path}>[{snapshot.kind === "portrait" ? (locale === "en" ? "Portrait" : "遗照") : (locale === "en" ? "Snapshot" : "快照")}] {snapshot.name}</option>)}
                </select>
              </div>
              <div className="actions">
                <button type="button" onClick={() => { void loadSnapshots(); setArchiveOpen(true); }} disabled={busy}>打开档案库</button>
                <button type="button" onClick={() => setPendingResume(snapshots.find((item) => item.path === selectedSnapshot) ?? null)} disabled={busy || !selectedSnapshot}>继续</button>
                <button type="button" onClick={() => void restore("clone")} disabled={busy || !selectedSnapshot}>克隆为新意识</button>
              </div>
            </section>
          </>}

          {sidebarTab === "stimulus" && <>
            <section className="stimulus-environment">
              <h2>环境</h2>
              <div className="environment-controls">
                <div className="field">
                  <label htmlFor="ambient"><span>微弱背景刺激</span><span>{ambient.toFixed(2)}</span></label>
                  <input id="ambient" type="range" min="0.01" max="0.4" step="0.01" value={ambient} disabled={dead} onChange={(event) => { const value = Number(event.target.value); setAmbient(value); void run("ambient", { intensity: value }, `背景刺激 ${value.toFixed(2)}`, { feedback: false }); }} />
                </div>
                <div className="field">
                  <label htmlFor="speed"><span>模拟速度</span><span>{speed.toFixed(1)}×</span></label>
                  <input id="speed" type="range" min="0.1" max="10" step="0.1" value={speed} disabled={dead} onChange={(event) => { const value = Number(event.target.value); setSpeed(value); void run("speed", { value }, `运行速度 ${value.toFixed(1)}×`, { feedback: false }); }} />
                </div>
              </div>
            </section>
            <section className="interpreter-chat-section">
              <h2>意识解读</h2>
              <div ref={chatRef} className="interpreter-chat" aria-label="刺激与意识解读历史" onScroll={(event) => { const element = event.currentTarget; chatPinnedToBottomRef.current = element.scrollHeight - element.scrollTop - element.clientHeight < 24; }}>
                {visibleConversation.length ? visibleConversation.map((entry, index) => <article className={`chat-message ${entry.role}`} key={`${entry.kind}-${entry.tick}-${index}`}>
                  <header>
                    <strong>{entry.role === "user" ? (locale === "en" ? "Me" : "我") : entry.role === "environment" ? (locale === "en" ? "Environment" : "环境") : entry.kind === "readout" ? (entry.readout_kind === "temporal" ? (locale === "en" ? "Temporal readout" : "时序读出") : (locale === "en" ? "Passive readout" : "被动读出")) : (locale === "en" ? "Interpretation" : "意识解读")}</strong>
                    <span>{entry.readout_kind === "temporal" && entry.start_tick != null ? `tick ${entry.start_tick}–${entry.end_tick ?? entry.tick}` : `tick ${entry.tick}`}{entry.important ? (locale === "en" ? " · important" : " · 重要") : ""}</span>
                  </header>
                  <p>{entry.kind === "readout" ? localizeStructuralReadout(locale, entry.text) : entry.text}</p>
                  {entry.kind === "readout" && entry.anonymous_text && entry.anonymous_text !== entry.text && <small className="anonymous-readout">{entry.anonymous_text}{entry.node_ids?.length ? ` · nodes ${entry.node_ids.join(", ")}` : ""}</small>}
                  {entry.readout_kind === "temporal" && <small>{temporalClassificationText(locale, entry.classification)}{entry.rankings?.length ? ` · ${locale === "en" ? "leading nodes" : "主要节点"} ${entry.rankings.slice(0, 5).map((row) => row.node_id).join(", ")}` : ""}</small>}
                  {entry.role === "environment" && <small>{entry.source === "ai-environment" ? "AI 环境刺激" : "环境刺激"}</small>}
                  {entry.kind === "interpretation" && entry.trigger === "manual_stimulus" && <small>文本刺激后的激活节点解读</small>}
                </article>) : <p className="readout-meta">当前没有可显示的消息；被屏蔽的环境刺激仍在持续运行并写入日志。</p>}
              </div>
            </section>
            <form className="stimulus-composer" onSubmit={submitStimulus}>
              <label htmlFor="stimulus">文本</label>
              <MediaControls consciousnessId={metrics.id} intensity={intensity} disabled={busy || dead} locale={locale} onFeedback={showFeedback} />
              <textarea
                id="stimulus"
                value={text}
                onChange={(event) => setText(event.target.value)}
                onKeyDown={(event) => { if ((settings.stimuli?.submit_on_enter ?? true) && event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }}
                placeholder="输入任意文本；Enter 发送，Shift+Enter 换行。"
                disabled={dead}
              />
              <div className="stimulus-composer-footer">
                <div className="field">
                  <label htmlFor="intensity"><span>刺激强度</span><span>{intensity.toFixed(2)}</span></label>
                  <input id="intensity" type="range" min="0.05" max="2" step="0.05" value={intensity} onChange={(event) => setIntensity(Number(event.target.value))} />
                </div>
                <button className="primary" type="submit" disabled={busy || dead || !text.trim()}>施加刺激</button>
              </div>
            </form>
          </>}
        </div>
      </aside>
      </> : activePage === "experiments" ? <Suspense fallback={<div className="graph-loading">{locale === "en" ? "Loading experiment workbench…" : "正在载入实验工作台…"}</div>}><ExperimentWorkbench locale={locale} activeConsciousnessId={hasActiveConsciousness ? metrics.id : ""} /></Suspense> : activePage === "experiment-records" ? <Suspense fallback={<div className="graph-loading">{locale === "en" ? "Loading experiment records…" : "正在载入实验记录…"}</div>}><ExperimentRecordsPage locale={locale} onOpenWorkbench={() => setActivePage("experiments")} /></Suspense> : activePage === "statistics" ? <Suspense fallback={<div className="graph-loading">{locale === "en" ? "Loading statistics and evidence…" : "正在载入统计与证据…"}</div>}><StatisticsEvidencePage locale={locale} activeConsciousnessId={hasActiveConsciousness ? metrics.id : ""}/></Suspense> : activePage === "detail" && detail ? <ConsciousnessDetailPage item={detail} snapshots={snapshots} consciousnesses={consciousnesses} onBack={() => { setActivePage("management"); setDetail(null); }} onResumeSnapshot={(snapshot) => setPendingResume(snapshot)} /> : activePage === "packages" ? <PackageManager /> : activePage === "adapters" ? <AdapterManager locale={locale} /> : activePage === "storage" ? <StorageCleanupManager /> : activePage === "stimuli" ? <HistoryManager kind="stimuli" consciousnesses={consciousnesses} onConfigure={() => void openSettings("automation")} /> : activePage === "interpretations" ? <HistoryManager kind="interpretations" consciousnesses={consciousnesses} onConfigure={() => void openSettings("automation")} /> : <InstanceManager items={consciousnesses} loading={consciousnessLoading} error={consciousnessError} onRefresh={() => void loadConsciousnesses()} onOpenDetails={(item) => { setDetail(item as ConsciousnessSummary); setActivePage("detail"); }} />}
      <SettingsPanel
        open={settingsOpen}
        initialCategory={settingsCategory}
        settings={settings}
        apiKey={apiKey}
        onClose={() => setSettingsOpen(false)}
        onChange={(next) => {
          setSettings(next);
          setViewMode(next.visualization?.mode ?? "3d");
        }}
        onKeyChange={setApiKey}
        onSave={saveSettings}
        onTest={() => void testNotification()}
        onToggleStimulusSource={(source, enabled) => void toggleStimulusSource(source, enabled)}
        navigationAutoHide={navigationAutoHide}
        onNavigationAutoHideChange={(enabled) => { setNavigationAutoHide(enabled); setNavigationPeek(!enabled); }}
        traceEnabled={trace}
        traceAvailable={hasActiveConsciousness && metrics.life_state !== "dead"}
        onTraceChange={changeTrace}
        saving={busy}
        loading={settingsLoading}
      />
      {nameDialog && <NameDialog title={nameDialog.kind === "snapshot" ? "命名快照" : metrics.name && nameDialog.initial === metrics.name ? "重命名意识" : "创建新意识"} initial={nameDialog.initial} confirmLabel={nameDialog.kind === "snapshot" || (metrics.name && nameDialog.initial === metrics.name) ? "保存" : "创建"} kernel={nameDialog.kind === "new" && !(metrics.name && nameDialog.initial === metrics.name) ? newKernel : undefined} onKernelChange={setNewKernel} v3NodeMode={nameDialog.kind === "new" && !(metrics.name && nameDialog.initial === metrics.name) ? newV3NodeMode : undefined} onV3NodeModeChange={setNewV3NodeMode} options={nameDialog.kind === "new" && !(metrics.name && nameDialog.initial === metrics.name) ? newModelOptions : undefined} onOptionsChange={setNewModelOptions} onCancel={() => setNameDialog(null)} onConfirm={(name) => { if (nameDialog.kind === "snapshot") void saveSnapshot(name); else if (metrics.name && nameDialog.initial === metrics.name) void run("rename", { name }, "意识已重命名"); else if (!hasActiveConsciousness) void createNew(name); else setPendingNewName(name); setNameDialog(null); }} />}
      {openConsciousnessDialog && <OpenConsciousnessDialog items={consciousnesses} locale={locale} busy={busy} onClose={() => setOpenConsciousnessDialog(false)} onOpen={openStoredConsciousness} onImport={importAndOpenConsciousness} />}
      {archiveOpen && <ArchivePanel items={snapshots} busy={busy} onClose={() => setArchiveOpen(false)} onResume={(item) => setPendingResume(item)} onClone={(item) => { void run("clone", { path: item.path }, "已从档案克隆新意识", { pendingMessage: locale === "en" ? "Cloning from archive…" : "正在从档案克隆意识…" }); setArchiveOpen(false); }} onDelete={(item) => { if (window.confirm(`删除 ${item.label ?? item.name}？此操作不可恢复。`)) { void run("archive_delete", { path: item.path }, "存档已删除", { pendingMessage: locale === "en" ? "Deleting archive…" : "正在删除存档…" }).then(() => void loadSnapshots()); } }} />}
      {pendingNewName && <div className="settings-backdrop"><section className="name-dialog operation-dialog" role="dialog" aria-modal="true"><h3>创建新意识将覆盖当前意识</h3><p>可以直接覆盖，或先保存当前意识的快照后再创建。</p>{pendingDialogAction?.startsWith("new-") && <p className="dialog-operation" role="status"><span className="ui-spinner" aria-hidden="true" />{pendingDialogAction === "new-snapshot" ? "正在保存快照并创建新意识…" : "正在创建并覆盖当前意识…"}</p>}<div className="actions"><button type="button" disabled={Boolean(pendingDialogAction)} onClick={() => setPendingNewName(null)}>取消</button><button type="button" disabled={Boolean(pendingDialogAction)} onClick={() => void createNewWithChoice("overwrite")}>{pendingDialogAction === "new-overwrite" ? "正在覆盖…" : "直接覆盖"}</button><button className="primary" type="button" disabled={Boolean(pendingDialogAction)} onClick={() => void createNewWithChoice("snapshot")}>{pendingDialogAction === "new-snapshot" ? "正在保存…" : "保存快照并覆盖"}</button></div></section></div>}
      {pendingResume && <div className="settings-backdrop"><section className="name-dialog operation-dialog" role="dialog" aria-modal="true"><h3>继续将覆盖当前意识</h3><p>选择直接覆盖，或先为当前意识拍摄快照后再覆盖。</p>{pendingDialogAction?.startsWith("resume-") && <p className="dialog-operation" role="status"><span className="ui-spinner" aria-hidden="true" />{pendingDialogAction === "resume-snapshot" ? "正在保存快照并恢复…" : "正在恢复意识…"}</p>}<div className="actions"><button type="button" disabled={Boolean(pendingDialogAction)} onClick={() => setPendingResume(null)}>取消</button><button type="button" disabled={Boolean(pendingDialogAction)} onClick={() => void resumeWithChoice("overwrite")}>{pendingDialogAction === "resume-overwrite" ? "正在覆盖…" : "直接覆盖"}</button><button className="primary" type="button" disabled={Boolean(pendingDialogAction)} onClick={() => void resumeWithChoice("snapshot")}>{pendingDialogAction === "resume-snapshot" ? "正在保存…" : "拍摄快照并覆盖"}</button></div></section></div>}
      {managementOpen && <div className="settings-backdrop" onMouseDown={() => setManagementOpen(false)}><section className="archive-modal" onMouseDown={(event) => event.stopPropagation()}><header className="settings-header"><div><strong>意识管理</strong><span>意识档案、谱系与时序记录。</span></div><button type="button" onClick={() => setManagementOpen(false)}>×</button></header><div className="archive-list">{consciousnesses.map((item) => <article className="archive-row" key={item.id}><div><strong>{item.name} {item.running ? "· 当前运行中" : ""}</strong><span>{item.status} · {item.id.slice(0, 8)} · 父意识 {item.parent_id?.slice(0, 8) ?? "—"}</span><span>{item.snapshots} 快照 · {item.portraits} 遗照 · tick {item.metrics?.tick ?? item.latest?.metrics?.tick ?? 0}</span></div><div className="archive-actions"><button onClick={() => setDetail(item)}>详情</button></div></article>)}</div></section></div>}
    </main>
    </div>
    </I18nContext.Provider>
  );
}
