import { DisplayModel } from "./graphModel";

let stopped = false,
  hidden = false,
  revision = -1,
  awaiting = false,
  pendingSnapshot = false;
let options = {
  url: "",
  nodes: 10000,
  edges: 40000,
  pollMs: 1000,
  mode: "3d",
  continuousMotion: false,
  layoutFps: 15,
  graphLabels: "none",
  maxLabels: 80,
};
let pollTimer: ReturnType<typeof setTimeout> | undefined,
  layoutTimer: ReturnType<typeof setTimeout> | undefined;
let abort: AbortController | undefined,
  lastLayout = performance.now(),
  settled = false;
const model = new DisplayModel();
function emit(snapshot: boolean) {
  pendingSnapshot ||= snapshot;
  if (awaiting || hidden || stopped) return;
  const frame = model.frame(pendingSnapshot);
  pendingSnapshot = false;
  awaiting = true;
  const transfer = [frame.positions.buffer, frame.edgePositions.buffer];
  if (frame.snapshot)
    transfer.push(
      frame.colors!.buffer,
      frame.sizes!.buffer,
      frame.edgeColors!.buffer,
    );
  if (frame.snapshot && frame.ids instanceof Float64Array)
    transfer.push(frame.ids.buffer);
  self.postMessage(frame, { transfer });
}
function layout() {
  clearTimeout(layoutTimer);
  if (hidden || stopped || !model.continuous || settled) return;
  const now = performance.now();
  if (!awaiting && model.ids.length) {
    settled = !model.step((now - lastLayout) / 1000);
    if (!settled) emit(false);
  }
  lastLayout = now;
  layoutTimer = setTimeout(layout, 1000 / options.layoutFps);
}
self.onmessage = (e) => {
  if (e.data.type === "ack") {
    awaiting = false;
    if (pendingSnapshot) emit(true);
    return;
  }
  if (e.data.type === "stop") {
    stopped = true;
    abort?.abort();
    clearTimeout(pollTimer);
    clearTimeout(layoutTimer);
    return;
  }
  if (e.data.type === "visibility") {
    hidden = e.data.hidden;
    abort?.abort();
    clearTimeout(pollTimer);
    clearTimeout(layoutTimer);
    if (!hidden && !stopped) {
      lastLayout = performance.now();
      if (pendingSnapshot) emit(true);
      if (options.pollMs > 0 || revision < 0) void poll();
      layout();
    }
    return;
  }
  options = { ...options, ...e.data };
  hidden = !!e.data.hidden;
  revision = -1;
  stopped = false;
  settled = false;
  abort?.abort();
  clearTimeout(pollTimer);
  clearTimeout(layoutTimer);
  if (!hidden) void poll();
};
async function poll() {
  const controller = new AbortController();
  abort = controller;
  try {
    const params = new URLSearchParams({
      limit: String(options.nodes),
      edge_limit: String(options.edges),
      since: String(revision),
      label_limit:
        options.graphLabels === "external" ? String(options.maxLabels) : "0",
    });
    const response = await fetch(
      options.url + (options.url.includes("?") ? "&" : "?") + params,
      { credentials: "same-origin", signal: controller.signal },
    );
    if (response.status !== 304) {
      if (!response.ok)
        throw new Error((await response.json()).detail ?? "图数据读取失败");
      const graph = await response.json();
      if (controller.signal.aborted || stopped || hidden) return;
      if (graph.revision !== revision) {
        model.replace(
          graph,
          options.mode,
          options.continuousMotion,
          options.graphLabels,
          options.maxLabels,
        );
        revision = graph.revision;
        settled = false;
        lastLayout = performance.now();
        emit(true);
        layout();
      }
    }
  } catch (error) {
    if (!controller.signal.aborted)
      self.postMessage({
        type: "error",
        message: error instanceof Error ? error.message : String(error),
      });
  } finally {
    if (!stopped && !hidden && abort === controller && options.pollMs > 0)
      pollTimer = setTimeout(poll, options.pollMs);
  }
}
export {};
