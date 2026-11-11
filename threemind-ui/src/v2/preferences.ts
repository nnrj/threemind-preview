import { useSyncExternalStore } from "react";
export type Preferences = {
  locale: "auto" | "zh-CN" | "en";
  preset: "auto" | "light" | "standard" | "high" | "custom";
  fps: number;
  dpr: number;
  nodes: number;
  edges: number;
  layoutFps: number;
  pollMs: number;
  mode: "2d" | "3d";
  shape: "glow" | "circle" | "square" | "sphere" | "cube";
  visualStyle: "organic" | "minimal";
  continuousMotion: boolean;
  graphLabels: "none" | "ids" | "external";
  maxLabels: number;
  labelFont: number;
  nodeScale: number;
  edgeOpacity: number;
  showGraphStats: boolean;
  theme: "light" | "dark";
  enterSend: boolean;
  showEnvironmentStimuli: boolean;
  showTriggeringStimuli: boolean;
  showBackgroundReadouts: boolean;
  showChatPassive: boolean;
  chatActivationOrder: boolean;
  temporalChatItems: number;
  promptCaptureName: boolean;
  captureNameStyle: "revision" | "timestamp";
  toolComputeDevice: "auto" | "cpu" | "cuda";
  toolGpuMemory: number;
  toolGpuHeadroom: number;
};
const defaults: Preferences = {
  locale: "zh-CN",
  preset: "standard",
  fps: 30,
  dpr: 1.5,
  nodes: 10000,
  edges: 40000,
  layoutFps: 15,
  pollMs: 1000,
  mode: "3d",
  shape: "glow",
  visualStyle: "organic",
  continuousMotion: false,
  graphLabels: "none",
  maxLabels: 80,
  labelFont: 12,
  nodeScale: 1,
  edgeOpacity: 0.55,
  showGraphStats: false,
  theme: "light",
  enterSend: true,
  showEnvironmentStimuli: false,
  showTriggeringStimuli: true,
  showBackgroundReadouts: false,
  showChatPassive: true,
  chatActivationOrder: true,
  temporalChatItems: 7,
  promptCaptureName: true,
  captureNameStyle: "timestamp",
  toolComputeDevice: "auto",
  toolGpuMemory: 2048,
  toolGpuHeadroom: 512,
};
let current: Preferences;
let preferenceUser: string | null = null;
const localUser = "00000000-0000-4000-8000-000000000001";
const storageKey = () => preferenceUser ? `tm2.preferences.user.${preferenceUser}` : "tm2.preferences.guest";
function normalize(value: Partial<Preferences>): Preferences {
  const p = { ...defaults };
  const number = (
    key:
      | "fps"
      | "dpr"
      | "nodes"
      | "edges"
      | "layoutFps"
      | "maxLabels"
      | "labelFont"
      | "nodeScale"
      | "edgeOpacity"
      | "toolGpuMemory"
      | "toolGpuHeadroom"
      | "pollMs",
    min: number,
    max: number,
    integer = true,
  ) => {
    const n = value[key];
    if (typeof n === "number" && Number.isFinite(n)) {
      p[key] = Math.max(min, Math.min(max, integer ? Math.round(n) : n));
    }
  };
  number("fps", 1, 144);
  number("dpr", 0.5, 3, false);
  number("nodes", 1, 100000);
  number("edges", 0, 1000000);
  number("layoutFps", 1, 60);
  number("maxLabels", 1, 500);
  number("labelFont", 9, 24);
  number("nodeScale", 0.25, 4, false);
  number("edgeOpacity", 0, 1, false);
  number("pollMs", 100, 10000);
  number("toolGpuMemory", 128, 131072);
  number("toolGpuHeadroom", 128, 32768);
  if (["auto", "cpu", "cuda"].includes(value.toolComputeDevice ?? ""))
    p.toolComputeDevice = value.toolComputeDevice!;
  if (
    typeof value.temporalChatItems === "number" &&
    Number.isFinite(value.temporalChatItems)
  )
    p.temporalChatItems = Math.round(
      Math.max(0, Math.min(2000, value.temporalChatItems)),
    );
  if (
    ["auto", "light", "standard", "high", "custom"].includes(value.preset ?? "")
  )
    p.preset = value.preset!;
  if (["2d", "3d"].includes(value.mode ?? "")) p.mode = value.mode!;
  if (["auto", "zh-CN", "en"].includes(value.locale ?? ""))
    p.locale = value.locale!;
  if (
    ["glow", "circle", "square", "sphere", "cube"].includes(value.shape ?? "")
  )
    p.shape = value.shape!;
  if (["light", "dark"].includes(value.theme ?? "")) p.theme = value.theme!;
  if (["organic", "minimal"].includes(value.visualStyle ?? ""))
    p.visualStyle = value.visualStyle!;
  if (["none", "ids", "external"].includes(value.graphLabels ?? ""))
    p.graphLabels = value.graphLabels!;
  if (["revision", "timestamp"].includes(value.captureNameStyle ?? ""))
    p.captureNameStyle = value.captureNameStyle!;
  for (const key of [
    "enterSend",
    "continuousMotion",
    "showGraphStats",
    "showEnvironmentStimuli",
    "showTriggeringStimuli",
    "showBackgroundReadouts",
    "showChatPassive",
    "chatActivationOrder",
    "promptCaptureName",
  ] as const)
    if (typeof value[key] === "boolean") p[key] = value[key];
  return p;
}
function readPreferences(): Preferences {
  try {
    // Only the existing local identity may inherit the old browser preference.
    // New accounts neither inherit another user's settings nor sync devices.
    const stored = localStorage.getItem(storageKey())
      ?? (preferenceUser === localUser ? localStorage.getItem("tm2.preferences") : null);
    const value = JSON.parse(stored ?? "{}") ?? {};
    if (
      value.enterSend === undefined &&
      preferenceUser === localUser && localStorage.getItem("tm2.input.enterSend") != null
    )
      value.enterSend = localStorage.getItem("tm2.input.enterSend") === "true";
    return normalize(value);
  } catch {
    return { ...defaults };
  }
}
current = readPreferences();
const listeners = new Set<() => void>();
window.addEventListener("storage", (event) => {
  if (
    event.key === null ||
    event.key === storageKey() || preferenceUser === localUser && ["tm2.preferences", "tm2.input.enterSend"].includes(event.key)
  ) {
    current = readPreferences();
    for (const cb of listeners) cb();
  }
});
export function preferences() {
  return current;
}
export function setPreferenceUser(identity: string | null) {
  if (preferenceUser === identity) return;
  preferenceUser = identity;
  current = readPreferences();
  for (const cb of listeners) cb();
}
export function updatePreferences(patch: Partial<Preferences>) {
  current = normalize({ ...current, ...patch });
  try {
    localStorage.setItem(storageKey(), JSON.stringify(current));
  } catch {
    /* Private browser storage may be disabled. */
  }
  for (const cb of listeners) cb();
}
export function usePreferences() {
  return useSyncExternalStore((cb) => {
    listeners.add(cb);
    return () => {
      listeners.delete(cb);
    };
  }, preferences);
}
export function effectivePreferences(p: Preferences) {
  const preset =
    p.preset === "auto"
      ? navigator.hardwareConcurrency >= 8
        ? "standard"
        : "light"
      : p.preset;
  const options = {
    light: {
      fps: 24,
      dpr: 1,
      nodes: 2000,
      edges: 5000,
      layoutFps: 10,
      pollMs: 1500,
    },
    standard: {
      fps: 30,
      dpr: 1.5,
      nodes: 10000,
      edges: 40000,
      layoutFps: 15,
      pollMs: 1000,
    },
    high: {
      fps: 60,
      dpr: 2,
      nodes: 100000,
      edges: 300000,
      layoutFps: 30,
      pollMs: 500,
    },
    custom: {
      fps: p.fps,
      dpr: p.dpr,
      nodes: p.nodes,
      edges: p.edges,
      layoutFps: p.layoutFps,
      pollMs: p.pollMs,
    },
  };
  return { ...p, ...options[preset] };
}
