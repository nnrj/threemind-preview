// Display-only state. No operation in this module writes a model or stimulus.
export type DisplayGraph = {
  nodes: any[];
  edges: any[];
  coordinates?: string;
  annotations?: Record<string, string[]>;
  [key: string]: any;
};

function displaySeed(id: string | number): number {
  if (typeof id === "number") return id;
  if (/^\d+$/.test(id)) {
    const integer = BigInt(id);
    return Number(
      integer <= BigInt(Number.MAX_SAFE_INTEGER)
        ? integer
        : integer % 4294967296n,
    );
  }
  let hash = 2166136261;
  for (let i = 0; i < id.length; i++)
    hash = Math.imul(hash ^ id.charCodeAt(i), 16777619);
  return hash >>> 0;
}

// The root is the least preferred entry. Preserve source order on activation
// ties, as a stable full sort would, using O(N log K) work and O(K) storage.
function labelIndices(graph: DisplayGraph, mode: string, maximum: number) {
  const heap: number[] = [];
  const activation = (i: number) => Number(graph.nodes[i].activation) || 0;
  const worse = (a: number, b: number) =>
    activation(a) < activation(b) || (activation(a) === activation(b) && a > b);
  if (mode === "none" || maximum <= 0) return heap;
  graph.nodes.forEach((node, index) => {
    if (mode === "external" && !graph.annotations?.[String(node.id)]?.length)
      return;
    if (heap.length < maximum) {
      heap.push(index);
      let at = heap.length - 1;
      while (at > 0) {
        const parent = (at - 1) >> 1;
        if (!worse(heap[at], heap[parent])) break;
        [heap[at], heap[parent]] = [heap[parent], heap[at]];
        at = parent;
      }
    } else if (worse(heap[0], index)) {
      heap[0] = index;
      let at = 0;
      while (at * 2 + 1 < heap.length) {
        let child = at * 2 + 1;
        if (child + 1 < heap.length && worse(heap[child + 1], heap[child]))
          child++;
        if (!worse(heap[child], heap[at])) break;
        [heap[at], heap[child]] = [heap[child], heap[at]];
        at = child;
      }
    }
  });
  return heap.sort((a, b) => activation(b) - activation(a) || a - b);
}

export class DisplayModel {
  ids: Float64Array | (string | number)[] = new Float64Array();
  positions = new Float32Array();
  anchors = new Float32Array();
  velocities = new Float32Array();
  forces = new Float32Array();
  colors = new Float32Array();
  sizes = new Float32Array();
  edgeIndices = new Uint32Array();
  edgeWeights = new Float32Array();
  edgeColors = new Float32Array();
  degrees = new Uint32Array();
  labels: { index: number; text: string }[] = [];
  meta: any = {};
  causal = false;
  mode = "3d";
  continuous = false;
  steps = 0;
  lastPrepareMs = 0;
  lastLayoutMs = 0;

  replace(
    graph: DisplayGraph,
    mode: string,
    continuous: boolean,
    labelMode = "none",
    maxLabels = 80,
  ) {
    const started = performance.now(),
      previous = new Map<string | number, number>();
    const oldPositions = this.positions,
      oldVelocities = this.velocities;
    const preserve =
      this.mode === mode &&
      continuous &&
      this.continuous &&
      !this.causal &&
      graph.coordinates !== "causal";
    if (preserve) this.ids.forEach((id, i) => previous.set(id, i));
    this.mode = mode;
    this.causal = graph.coordinates === "causal";
    this.continuous = continuous && !this.causal;
    const nodes = graph.nodes,
      index = new Map<string | number, number>();
    this.ids = nodes.every((node) => typeof node.id === "number")
      ? new Float64Array(nodes.length)
      : new Array(nodes.length);
    this.positions = new Float32Array(nodes.length * 3);
    this.anchors = new Float32Array(nodes.length * 3);
    this.velocities = new Float32Array(nodes.length * 3);
    this.forces = new Float32Array(nodes.length * 3);
    this.colors = new Float32Array(nodes.length * 3);
    this.sizes = new Float32Array(nodes.length);
    this.degrees = new Uint32Array(nodes.length);
    nodes.forEach((n, i) => {
      if (
        !(typeof n.id === "string" && n.id.length > 0) &&
        (!Number.isSafeInteger(n.id) || n.id < 0)
      )
        throw new Error("节点编号超出浏览器精确整数范围，请使用完整数据导出。");
      index.set(n.id, i);
      this.ids[i] = n.id;
      // Layout coordinates are display-only; scientific IDs stay in their original type.
      const seed = displaySeed(n.id);
      const phi = (seed * 2.399963229728653) % (Math.PI * 2),
        radius = 26 + Math.sqrt(seed % 503) * 12;
      if (
        this.causal &&
        (!Array.isArray(n.position) ||
          n.position.length !== 3 ||
          n.position.some((x: any) => !Number.isFinite(x)))
      )
        throw new Error("因果坐标缺失或无效，未用显示布局替代。");
      const base = this.causal
        ? n.position.map((x: number) => x * 150)
        : [
            Math.cos(phi) * radius,
            Math.sin(phi) * radius,
            ((seed * 37) % 150) - 75,
          ];
      if (mode === "2d") base[2] = 0;
      this.anchors.set(base, i * 3);
      const prior = preserve ? previous.get(n.id) : undefined;
      for (let axis = 0; axis < 3; axis++) {
        this.positions[i * 3 + axis] =
          prior === undefined ? base[axis] : oldPositions[prior * 3 + axis];
        this.velocities[i * 3 + axis] =
          prior === undefined ? 0 : oldVelocities[prior * 3 + axis];
      }
      const activation = Math.max(0, Number(n.activation) || 0),
        gain = 0.3 + 0.7 * Math.sqrt(activation);
      const tint =
        n.direct > 0.01
          ? [0.953, 0.741, 0.447]
          : n.associative > 0.005
            ? [0.486, 0.878, 0.827]
            : [0.506, 0.62, 0.588];
      for (let axis = 0; axis < 3; axis++)
        this.colors[i * 3 + axis] = tint[axis] * gain;
      this.sizes[i] = 5 + Math.sqrt(activation) * 9;
    });
    const edges = graph.edges.filter(
      (e) => index.has(e.source) && index.has(e.target),
    );
    this.edgeIndices = new Uint32Array(edges.length * 2);
    this.edgeWeights = new Float32Array(edges.length);
    this.edgeColors = new Float32Array(edges.length * 6);
    const edgeTint = [0.3, 0.65, 0.58];
    edges.forEach((e, i) => {
      const a = index.get(e.source)!,
        b = index.get(e.target)!,
        weight = Math.max(0, Math.min(1, Number(e.weight) || 0));
      this.edgeIndices[i * 2] = a;
      this.edgeIndices[i * 2 + 1] = b;
      this.edgeWeights[i] = weight;
      this.degrees[a]++;
      this.degrees[b]++;
      for (let axis = 0; axis < 3; axis++)
        this.edgeColors[i * 6 + axis] = this.edgeColors[i * 6 + axis + 3] =
          edgeTint[axis] * (0.2 + 0.8 * weight);
    });
    // Allocate text only for selected labels, never for every graph node.
    this.labels = labelIndices(graph, labelMode, maxLabels).map((index) => {
      const node = nodes[index];
      return {
        index,
        text:
          labelMode === "external"
            ? graph.annotations![String(node.id)].join(" / ").slice(0, 36) +
              " · n" +
              node.id
            : "n" + node.id,
      };
    });
    this.meta = {
      revision: graph.revision,
      time_us: graph.time_us,
      state_hash: graph.state_hash,
      checkpoint_id: graph.checkpoint_id,
      shown_nodes: nodes.length,
      shown_edges: edges.length,
      total_nodes: graph.total_nodes,
      total_edges: graph.total_edges,
      complete: graph.complete,
      coordinates: this.causal ? "causal" : "display",
      annotation_scope: graph.annotation_scope,
      available_labels: this.labels.length,
    };
    this.lastPrepareMs = performance.now() - started;
  }

  step(elapsedSeconds: number) {
    if (!this.continuous || !this.ids.length) return false;
    const started = performance.now(),
      dt = Math.max(0, Math.min(1 / 15, elapsedSeconds)) * 30;
    this.forces.fill(0);
    for (let e = 0; e < this.edgeWeights.length; e++) {
      const a = this.edgeIndices[e * 2] * 3,
        b = this.edgeIndices[e * 2 + 1] * 3;
      const dx = this.positions[b] - this.positions[a],
        dy = this.positions[b + 1] - this.positions[a + 1],
        dz = this.positions[b + 2] - this.positions[a + 2];
      const length = Math.max(0.01, Math.hypot(dx, dy, dz)),
        weight = this.edgeWeights[e];
      const force =
        ((length - (35 + (1 - weight) * 72)) * (0.002 + weight * 0.004)) /
        length;
      this.forces[a] += dx * force;
      this.forces[b] -= dx * force;
      this.forces[a + 1] += dy * force;
      this.forces[b + 1] -= dy * force;
      this.forces[a + 2] += dz * force;
      this.forces[b + 2] -= dz * force;
    }
    let maximum = 0;
    const damping = Math.pow(0.85, dt);
    for (let i = 0; i < this.positions.length; i++) {
      const acceleration =
        this.forces[i] / Math.max(1, this.degrees[Math.floor(i / 3)]) +
        (this.anchors[i] - this.positions[i]) * 0.004;
      this.velocities[i] = Math.max(
        -6,
        Math.min(6, (this.velocities[i] + acceleration * dt) * damping),
      );
      const displacement = this.velocities[i] * dt;
      this.positions[i] += displacement;
      maximum = Math.max(maximum, Math.abs(displacement));
    }
    this.steps++;
    this.lastLayoutMs = performance.now() - started;
    return maximum > 0.001;
  }

  frame(snapshot: boolean) {
    const positions = this.positions.slice(),
      edgePositions = new Float32Array(this.edgeIndices.length * 3);
    for (let i = 0; i < this.edgeIndices.length; i++) {
      const node = this.edgeIndices[i] * 3;
      edgePositions[i * 3] = positions[node];
      edgePositions[i * 3 + 1] = positions[node + 1];
      edgePositions[i * 3 + 2] = positions[node + 2];
    }
    return {
      type: "graph",
      snapshot,
      positions,
      edgePositions,
      moved: true,
      ...(snapshot
        ? {
            ids: this.ids.slice(),
            colors: this.colors.slice(),
            sizes: this.sizes.slice(),
            edgeColors: this.edgeColors.slice(),
            labels: this.labels,
            meta: this.meta,
          }
        : {}),
      diagnostics: {
        prepare_ms: this.lastPrepareMs,
        layout_ms: this.lastLayoutMs,
        layout_steps: this.steps,
      },
    };
  }
}
