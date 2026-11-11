/**
 * UI-side projection of the live ThreeMind graph.
 *
 * The Core owns consciousness state and emits snapshots/deltas through its
 * OutputBus/WebSocket protocol.  This store owns only a mutable visual index:
 * it never writes to Core and is intentionally independent of ThreeJSON.
 *
 * Keeping this layer separate lets React management panels receive a bounded
 * snapshot at animation-frame cadence while renderers consume exact deltas.
 */

export type GraphNode = {
  id: number;
  feature: string;
  activation: number;
  inhibition?: number;
  pending_inhibition?: number;
  stability: number;
  touch_count: number;
  direct: number;
  associative: number;
  source: string;
  position?: number[] | null;
  cluster?: number | null;
};

export type GraphEdge = {
  source: number;
  target: number;
  weight: number;
  stability: number;
  touched: boolean;
};

export type Metrics = {
  id: string;
  name?: string;
  tick: number;
  life_state: string;
  death_reason?: string | null;
  node_count: number;
  edge_count: number;
  active_nodes: number;
  total_activation: number;
  total_inhibition?: number;
  inhibited_nodes?: number;
  mean_stability: number;
  kernel?: string;
  kernel_id?: string;
  spatial_embedding?: boolean;
  spatial_dimensions?: number;
  spatial_neighbor_edges?: number;
  spatial_clusters?: number;
  queued_stimuli?: number;
  input_epoch?: number;
  topology_inhibition_enabled?: boolean;
  energy_simulation_enabled?: boolean;
  energy_reserve?: number | null;
  energy_capacity?: number | null;
  energy_starved_ticks?: number;
  trace_enabled?: boolean;
};

export type ModelManifestView = {
  package_schema_version: string;
  kernel_id: string;
  node_payload: "anonymous" | "labeled";
  weighted_edges: boolean;
  spatial_embedding: boolean;
  spatial_dimensions: number;
  parameters?: Record<string, unknown>;
};

export type GraphData = {
  metrics: Metrics;
  manifest?: ModelManifestView;
  nodes: GraphNode[];
  edges: GraphEdge[];
  neighbors?: GraphEdge[];
};

export type GraphDelta = {
  metrics: Metrics;
  nodes?: GraphNode[];
  edges?: GraphEdge[];
  neighbors?: GraphEdge[];
  removed_nodes?: number[];
  removed_edges?: number[][];
  removed_neighbors?: number[][];
  manifest?: ModelManifestView;
};

export type GraphProjectionChange =
  | { type: "replace"; graph: GraphData }
  | {
      type: "delta";
      metrics: Metrics;
      nodes: GraphNode[];
      edges: GraphEdge[];
      neighbors: GraphEdge[];
      removedNodes: number[];
      removedEdges: Array<[number, number]>;
      removedNeighbors: Array<[number, number]>;
      manifest?: ModelManifestView;
    };

type Listener = (change: GraphProjectionChange) => void;

export function edgeKey(source: number, target: number): string {
  return `${source}:${target}`;
}

function toPair(value: number[] | undefined): [number, number] | null {
  if (!Array.isArray(value) || value.length < 2) return null;
  const source = Number(value[0]);
  const target = Number(value[1]);
  return Number.isFinite(source) && Number.isFinite(target) ? [source, target] : null;
}

/**
 * Mutable, renderer-neutral live graph projection.
 *
 * Snapshot construction remains deliberately coarse because it runs only when
 * React needs a management/side-panel view.  Renderers should instead
 * subscribe and apply the emitted delta directly.
 */
export class GraphProjectionStore {
  private readonly nodes = new Map<number, GraphNode>();
  private readonly edges = new Map<string, GraphEdge>();
  private readonly neighbors = new Map<string, GraphEdge>();
  private readonly listeners = new Set<Listener>();
  private currentMetrics: Metrics | null = null;
  private currentManifest: ModelManifestView | undefined;

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  replace(graph: GraphData): void {
    this.nodes.clear();
    this.edges.clear();
    this.neighbors.clear();
    for (const node of graph.nodes) this.nodes.set(node.id, { ...node });
    for (const edge of graph.edges) this.edges.set(edgeKey(edge.source, edge.target), { ...edge });
    for (const edge of graph.neighbors ?? []) this.neighbors.set(edgeKey(edge.source, edge.target), { ...edge });
    this.currentMetrics = { ...graph.metrics };
    this.currentManifest = graph.manifest ? { ...graph.manifest, parameters: graph.manifest.parameters ? { ...graph.manifest.parameters } : undefined } : undefined;
    this.emit({ type: "replace", graph: this.snapshot()! });
  }

  clear(): void {
    this.nodes.clear();
    this.edges.clear();
    this.neighbors.clear();
    this.currentMetrics = null;
    this.currentManifest = undefined;
  }

  applyDelta(delta: GraphDelta): void {
    const removedNodes = [...new Set((delta.removed_nodes ?? []).map(Number).filter(Number.isFinite))];
    const removedEdges = (delta.removed_edges ?? []).map(toPair).filter((pair): pair is [number, number] => pair !== null);
    const removedNeighbors = (delta.removed_neighbors ?? []).map(toPair).filter((pair): pair is [number, number] => pair !== null);

    for (const id of removedNodes) {
      this.nodes.delete(id);
      this.removeIncident(this.edges, id, removedEdges);
      this.removeIncident(this.neighbors, id, removedNeighbors);
    }
    for (const [source, target] of removedEdges) this.edges.delete(edgeKey(source, target));
    for (const [source, target] of removedNeighbors) this.neighbors.delete(edgeKey(source, target));

    const nodes: GraphNode[] = [];
    for (const patch of delta.nodes ?? []) {
      const previous = this.nodes.get(patch.id);
      const next = { ...previous, ...patch } as GraphNode;
      this.nodes.set(next.id, next);
      nodes.push(next);
    }

    const edges: GraphEdge[] = [];
    for (const patch of delta.edges ?? []) {
      const key = edgeKey(patch.source, patch.target);
      const next = { ...this.edges.get(key), ...patch } as GraphEdge;
      this.edges.set(key, next);
      edges.push(next);
    }

    const neighbors: GraphEdge[] = [];
    for (const patch of delta.neighbors ?? []) {
      const key = edgeKey(patch.source, patch.target);
      const next = { ...this.neighbors.get(key), ...patch } as GraphEdge;
      this.neighbors.set(key, next);
      neighbors.push(next);
    }

    this.currentMetrics = { ...delta.metrics };
    if (delta.manifest) {
      this.currentManifest = { ...delta.manifest, parameters: delta.manifest.parameters ? { ...delta.manifest.parameters } : undefined };
    }
    this.emit({
      type: "delta",
      metrics: this.currentMetrics,
      nodes,
      edges,
      neighbors,
      removedNodes,
      removedEdges,
      removedNeighbors,
      manifest: delta.manifest,
    });
  }

  snapshot(): GraphData | null {
    if (!this.currentMetrics) return null;
    return {
      metrics: { ...this.currentMetrics },
      manifest: this.currentManifest ? { ...this.currentManifest, parameters: this.currentManifest.parameters ? { ...this.currentManifest.parameters } : undefined } : undefined,
      nodes: [...this.nodes.values()],
      edges: [...this.edges.values()],
      neighbors: this.neighbors.size ? [...this.neighbors.values()] : undefined,
    };
  }

  getNode(id: number): GraphNode | null {
    return this.nodes.get(id) ?? null;
  }

  getNodes(): Iterable<GraphNode> {
    return this.nodes.values();
  }

  getEdges(): Iterable<GraphEdge> {
    return this.edges.values();
  }

  getNeighbors(): Iterable<GraphEdge> {
    return this.neighbors.values();
  }

  private removeIncident(target: Map<string, GraphEdge>, id: number, removed: Array<[number, number]>): void {
    for (const [key, edge] of target) {
      if (edge.source !== id && edge.target !== id) continue;
      target.delete(key);
      if (!removed.some(([source, destination]) => source === edge.source && destination === edge.target)) {
        removed.push([edge.source, edge.target]);
      }
    }
  }

  private emit(change: GraphProjectionChange): void {
    for (const listener of this.listeners) listener(change);
  }
}
