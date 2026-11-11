import * as THREE from "three";
import {
  createDynamicPointBatch,
  createDynamicSegmentBatch,
  createFrameCommitScheduler,
  createRuntimeContext,
  createSceneRuntime,
  registerRuntimeEntity,
  removeRuntimeEntity,
  type DynamicGeometryBatch,
  type SceneRuntime,
} from "threejson/core";
import {
  edgeKey,
  type GraphData,
  type GraphEdge,
  type GraphNode,
  type GraphProjectionChange,
} from "./graphProjectionStore";

export type ThreeMindViewMode = "2d" | "3d";
export type ThreeMindNodeShape = "glow" | "circle" | "square" | "sphere" | "cube";
export type ThreeMindVisualStyle = "organic" | "minimal";

type Particle = { position: THREE.Vector3; velocity: THREE.Vector3; target: THREE.Vector3 };
type EdgeMap = Map<string, GraphEdge>;
type EdgeAdjacency = Map<number, Set<string>>;

type ThreeMindGraphDomainOptions = {
  canvas: HTMLCanvasElement;
  mode: ThreeMindViewMode;
  shape: ThreeMindNodeShape;
  style: ThreeMindVisualStyle;
  continuousMotion: boolean;
};

const NODE_OWNER = "threemind-graph";
const NODE_PREFIX = "threemind:node:";
const EDGE_PREFIX = "threemind:edge:";
const NEIGHBOR_PREFIX = "threemind:neighbor:";

function seededPosition(id: number, mode: ThreeMindViewMode): THREE.Vector3 {
  const phi = (id * 2.399963229728653) % (Math.PI * 2);
  const radius = 26 + Math.sqrt(id % 503) * 12;
  return new THREE.Vector3(
    Math.cos(phi) * radius,
    Math.sin(phi) * radius,
    mode === "3d" ? ((id * 37) % 150) - 75 : 0,
  );
}

function projectedPosition(node: GraphNode, mode: ThreeMindViewMode): THREE.Vector3 {
  if (!node.position?.length) return seededPosition(node.id, mode);
  const scale = 105;
  return new THREE.Vector3(
    Number(node.position[0] ?? 0) * scale,
    Number(node.position[1] ?? 0) * scale,
    mode === "3d" ? Number(node.position[2] ?? 0) * scale : 0,
  );
}

function nodeColor(node: GraphNode): THREE.Color {
  if (node.direct > 0) return new THREE.Color(0xf3bd72);
  if (node.associative > 0) return new THREE.Color(0x7ce0d3);
  return new THREE.Color(0x819e96);
}

function nodeSize(node: GraphNode): number {
  return 5.2 + Math.sqrt(Math.max(0, node.touch_count)) * 0.48 + node.stability * 5 + node.activation * 6;
}

function edgeColor(edge: GraphEdge, neighbor = false): THREE.Color {
  if (neighbor) return new THREE.Color(0x4f8f88).multiplyScalar(0.26);
  const color = edge.touched ? new THREE.Color(0x7ce0d3) : new THREE.Color(0x5c7b74);
  return color.multiplyScalar(0.35 + edge.weight * 0.6 + edge.stability * 0.3);
}

function edgeEntityId(prefix: string, edge: GraphEdge): string {
  return `${prefix}${edge.source}:${edge.target}`;
}

function addAdjacency(adjacency: EdgeAdjacency, edge: GraphEdge, key: string): void {
  for (const id of [edge.source, edge.target]) {
    let keys = adjacency.get(id);
    if (!keys) {
      keys = new Set();
      adjacency.set(id, keys);
    }
    keys.add(key);
  }
}

function removeAdjacency(adjacency: EdgeAdjacency, edge: GraphEdge, key: string): void {
  for (const id of [edge.source, edge.target]) {
    const keys = adjacency.get(id);
    if (!keys) continue;
    keys.delete(key);
    if (!keys.size) adjacency.delete(id);
  }
}

/**
 * ThreeMind-specific visual domain on top of ThreeJSON runtime primitives.
 *
 * It owns no consciousness state.  Its IDs are runtime-only object handles
 * such as `threemind:node:42`, unrelated to any Core node semantics or `.tmind`
 * persistence.  Dynamic batches are used for points and segments so a delta
 * touches only changed GPU ranges until the next animation-frame commit.
 */
export class ThreeMindGraphDomain {
  readonly runtime: SceneRuntime;
  private readonly runtimeContext: unknown;
  private readonly root = new THREE.Group();
  private readonly nodeBatch: DynamicGeometryBatch;
  private readonly edgeBatch: DynamicGeometryBatch;
  private readonly neighborBatch: DynamicGeometryBatch;
  private readonly commits = createFrameCommitScheduler();
  private readonly points: THREE.Points;
  private readonly edges: THREE.LineSegments;
  private readonly neighborhoods: THREE.LineSegments;
  private readonly pointMaterial: THREE.ShaderMaterial;
  private readonly edgeMaterial: THREE.LineBasicMaterial;
  private readonly neighborMaterial: THREE.LineBasicMaterial;
  private readonly nodes = new Map<number, GraphNode>();
  private readonly edgeRecords: EdgeMap = new Map();
  private readonly neighborRecords: EdgeMap = new Map();
  private readonly edgeAdjacency: EdgeAdjacency = new Map();
  private readonly neighborAdjacency: EdgeAdjacency = new Map();
  private readonly particles = new Map<number, Particle>();
  private readonly identity = new THREE.Quaternion();
  private readonly matrix = new THREE.Matrix4();
  private readonly scale = new THREE.Vector3();
  private readonly nodeEntityIds = new Set<string>();
  private readonly edgeEntityIds = new Set<string>();
  private readonly neighborEntityIds = new Set<string>();
  private readonly mode: ThreeMindViewMode;
  private readonly shape: ThreeMindNodeShape;
  private readonly style: ThreeMindVisualStyle;
  private readonly continuousMotion: boolean;
  private sphereMesh: THREE.InstancedMesh | null = null;
  private cubeMesh: THREE.InstancedMesh | null = null;
  private solidCapacity = 0;
  private solidDirty = false;
  private disposed = false;

  constructor(options: ThreeMindGraphDomainOptions) {
    this.mode = options.mode;
    this.shape = options.shape;
    this.style = options.style;
    this.continuousMotion = options.continuousMotion;
    const box = options.canvas.getBoundingClientRect();
    const width = Math.max(1, Math.round(box.width));
    const height = Math.max(1, Math.round(box.height));
    this.runtimeContext = createRuntimeContext();
    this.runtime = createSceneRuntime({
      canvas: options.canvas,
      runtimeContext: this.runtimeContext,
      disposeRuntimeContext: true,
      beforeFrame: () => {
        if (this.continuousMotion) this.advanceVisualMotion();
      },
      config: {
        canvasWidth: width,
        canvasHeight: height,
        scene: {},
        camera: this.mode === "3d"
          ? { type: "perspective", fov: 48, near: 0.1, far: 3000, position: { x: 158, y: 116, z: 214 }, lookAt: { x: 0, y: 0, z: 0 } }
          : { type: "orthographic", near: 0.1, far: 3000, top: 180, bottom: -180, position: { x: 0, y: 0, z: 300 }, lookAt: { x: 0, y: 0, z: 0 } },
        renderer: {
          alpha: true,
          antialias: true,
          clearAlpha: 0,
          ratioRate: Math.min(1, 2 / Math.max(1, window.devicePixelRatio || 1)),
        },
        controls: {
          type: "orbit",
          enableDamping: true,
          dampingFactor: 0.08,
          enablePan: true,
          minDistance: 35,
          maxDistance: 1400,
          target: { x: 0, y: 0, z: 0 },
        },
        renderLoop: {
          scheduleMode: this.continuousMotion ? "continuous" : "demand",
          updateAnimations: false,
          autoResize: false,
        },
      },
    });
    this.runtime.renderer.setClearColor(0x000000, 0);
    if (this.mode === "2d" && this.runtime.controls) {
      this.runtime.controls.enableRotate = false;
      this.runtime.controls.screenSpacePanning = true;
    }

    this.nodeBatch = createDynamicPointBatch({
      capacity: 256,
      attributes: {
        position: { itemSize: 3, defaultValue: [0, 0, 0] },
        color: { itemSize: 3, defaultValue: [0.5, 0.8, 0.75] },
        size: { itemSize: 1, defaultValue: 6 },
      },
    });
    this.edgeBatch = createDynamicSegmentBatch({
      capacity: 512,
      attributes: {
        position: { itemSize: 3, defaultValue: 0 },
        color: { itemSize: 3, defaultValue: [0.3, 0.6, 0.56] },
      },
    });
    this.neighborBatch = createDynamicSegmentBatch({
      capacity: 256,
      attributes: {
        position: { itemSize: 3, defaultValue: 0 },
        color: { itemSize: 3, defaultValue: [0.2, 0.45, 0.42] },
      },
    });

    this.pointMaterial = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      depthTest: false,
      blending: THREE.AdditiveBlending,
      vertexColors: true,
      uniforms: {
        square: { value: this.shape === "square" || this.shape === "cube" ? 1 : 0 },
        organic: { value: this.style === "organic" ? 1 : 0 },
      },
      vertexShader: `
        attribute float size;
        varying vec3 vColor;
        void main() {
          vColor = color;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          gl_PointSize = size * (280.0 / max(1.0, -mv.z));
          gl_Position = projectionMatrix * mv;
        }
      `,
      fragmentShader: `
        uniform float square;
        uniform float organic;
        varying vec3 vColor;
        void main() {
          vec2 p = gl_PointCoord - vec2(.5);
          float radius = length(p);
          if (square < .5 && radius > .5) discard;
          float edge = square > .5 ? max(abs(p.x), abs(p.y)) : radius;
          float core = 1.0 - smoothstep(organic > .5 ? .22 : .40, .5, edge);
          float alpha = organic > .5 ? core * (.26 + .74 * core) : core;
          gl_FragColor = vec4(vColor, alpha);
        }
      `,
    });
    this.edgeMaterial = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.42, depthWrite: false });
    this.neighborMaterial = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.13, depthWrite: false });
    this.points = new THREE.Points(this.nodeBatch.geometry, this.pointMaterial);
    this.edges = new THREE.LineSegments(this.edgeBatch.geometry, this.edgeMaterial);
    this.neighborhoods = new THREE.LineSegments(this.neighborBatch.geometry, this.neighborMaterial);
    for (const object of [this.points, this.edges, this.neighborhoods]) {
      object.frustumCulled = false;
    }
    this.points.renderOrder = 3;
    this.edges.renderOrder = 1;
    this.neighborhoods.renderOrder = 0;
    this.root.add(this.neighborhoods, this.edges, this.points);
    this.runtime.scene.add(this.root);
    this.createSolidMeshes();
    this.setSolidVisibility();
    this.runtime.start();
  }

  resize(width: number, height: number): void {
    if (this.disposed) return;
    this.runtime.resize({ width: Math.max(1, width), height: Math.max(1, height), updateStyle: false });
  }

  apply(change: GraphProjectionChange): void {
    if (this.disposed) return;
    if (change.type === "replace") {
      this.replace(change.graph);
    } else {
      this.applyDelta(change);
    }
    this.scheduleCommit();
  }

  moveCameraBy(key: string): boolean {
    if (this.disposed) return false;
    const controls = this.runtime.controls;
    const camera = this.runtime.camera;
    if (!controls?.target) return false;
    const perspective = camera instanceof THREE.PerspectiveCamera;
    const distance = perspective ? camera.position.distanceTo(controls.target) : 220 / Math.max(0.15, (camera as THREE.OrthographicCamera).zoom || 1);
    const step = perspective ? distance * 0.04 : distance * 0.08;
    switch (key.toLowerCase()) {
      case "w": controls.target.y += step; break;
      case "s": controls.target.y -= step; break;
      case "a": controls.target.x -= step; break;
      case "d": controls.target.x += step; break;
      case "q": if (perspective) controls.target.z -= step; else return false; break;
      case "e": if (perspective) controls.target.z += step; else return false; break;
      case "f":
        controls.target.set(0, 0, 0);
        if (perspective) camera.position.set(158, 116, 214);
        else {
          camera.position.set(0, 0, 300);
          (camera as THREE.OrthographicCamera).zoom = 1;
          (camera as THREE.OrthographicCamera).updateProjectionMatrix();
        }
        break;
      default: return false;
    }
    controls.update?.();
    this.runtime.invalidate();
    return true;
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.commits.dispose();
    for (const entityId of this.nodeEntityIds) removeRuntimeEntity(entityId, this.runtimeContext);
    for (const entityId of this.edgeEntityIds) removeRuntimeEntity(entityId, this.runtimeContext);
    for (const entityId of this.neighborEntityIds) removeRuntimeEntity(entityId, this.runtimeContext);
    this.nodeBatch.dispose();
    this.edgeBatch.dispose();
    this.neighborBatch.dispose();
    this.pointMaterial.dispose();
    this.edgeMaterial.dispose();
    this.neighborMaterial.dispose();
    this.disposeSolidMesh(this.sphereMesh);
    this.disposeSolidMesh(this.cubeMesh);
    this.runtime.scene.remove(this.root);
    this.runtime.dispose();
  }

  private replace(graph: GraphData): void {
    for (const entityId of this.nodeEntityIds) removeRuntimeEntity(entityId, this.runtimeContext);
    for (const entityId of this.edgeEntityIds) removeRuntimeEntity(entityId, this.runtimeContext);
    for (const entityId of this.neighborEntityIds) removeRuntimeEntity(entityId, this.runtimeContext);
    this.nodeEntityIds.clear();
    this.edgeEntityIds.clear();
    this.neighborEntityIds.clear();
    this.nodeBatch.clear();
    this.edgeBatch.clear();
    this.neighborBatch.clear();
    this.nodes.clear();
    this.edgeRecords.clear();
    this.neighborRecords.clear();
    this.edgeAdjacency.clear();
    this.neighborAdjacency.clear();
    this.particles.clear();
    for (const node of graph.nodes) this.upsertNode(node);
    for (const edge of graph.edges) this.upsertEdge(edge, false);
    for (const edge of graph.neighbors ?? []) this.upsertEdge(edge, true);
  }

  private applyDelta(change: Extract<GraphProjectionChange, { type: "delta" }>): void {
    for (const id of change.removedNodes) this.removeNode(id);
    for (const [source, target] of change.removedEdges) this.removeEdge(source, target, false);
    for (const [source, target] of change.removedNeighbors) this.removeEdge(source, target, true);
    for (const node of change.nodes) this.upsertNode(node);
    for (const edge of change.edges) this.upsertEdge(edge, false);
    for (const edge of change.neighbors) this.upsertEdge(edge, true);
  }

  private upsertNode(patch: GraphNode): void {
    const node = { ...this.nodes.get(patch.id), ...patch } as GraphNode;
    this.nodes.set(node.id, node);
    let particle = this.particles.get(node.id);
    const target = projectedPosition(node, this.mode);
    if (!particle) {
      particle = { position: target.clone(), velocity: new THREE.Vector3(), target };
      this.particles.set(node.id, particle);
    } else {
      particle.target.copy(target);
      if (!this.continuousMotion) particle.position.copy(target);
    }
    this.writeNode(node);
    this.registerNode(node);
    this.updateIncidentEdges(node.id, false);
    this.updateIncidentEdges(node.id, true);
  }

  private removeNode(id: number): void {
    this.nodes.delete(id);
    this.particles.delete(id);
    const entityId = `${NODE_PREFIX}${id}`;
    this.nodeBatch.remove(entityId);
    this.nodeEntityIds.delete(entityId);
    removeRuntimeEntity(entityId, this.runtimeContext);
    for (const key of [...(this.edgeAdjacency.get(id) ?? [])]) {
      const edge = this.edgeRecords.get(key);
      if (edge) this.removeEdge(edge.source, edge.target, false);
    }
    for (const key of [...(this.neighborAdjacency.get(id) ?? [])]) {
      const edge = this.neighborRecords.get(key);
      if (edge) this.removeEdge(edge.source, edge.target, true);
    }
    this.solidDirty = true;
  }

  private upsertEdge(patch: GraphEdge, neighbor: boolean): void {
    const records = neighbor ? this.neighborRecords : this.edgeRecords;
    const adjacency = neighbor ? this.neighborAdjacency : this.edgeAdjacency;
    const key = edgeKey(patch.source, patch.target);
    const previous = records.get(key);
    const edge = { ...previous, ...patch } as GraphEdge;
    if (previous) removeAdjacency(adjacency, previous, key);
    records.set(key, edge);
    addAdjacency(adjacency, edge, key);
    this.writeEdge(edge, neighbor);
    this.registerEdge(edge, neighbor);
  }

  private removeEdge(source: number, target: number, neighbor: boolean): void {
    const records = neighbor ? this.neighborRecords : this.edgeRecords;
    const adjacency = neighbor ? this.neighborAdjacency : this.edgeAdjacency;
    const prefix = neighbor ? NEIGHBOR_PREFIX : EDGE_PREFIX;
    const entityIds = neighbor ? this.neighborEntityIds : this.edgeEntityIds;
    const batch = neighbor ? this.neighborBatch : this.edgeBatch;
    const key = edgeKey(source, target);
    const edge = records.get(key);
    if (edge) removeAdjacency(adjacency, edge, key);
    records.delete(key);
    const entityId = `${prefix}${source}:${target}`;
    batch.remove(entityId);
    entityIds.delete(entityId);
    removeRuntimeEntity(entityId, this.runtimeContext);
  }

  private updateIncidentEdges(id: number, neighbor: boolean): void {
    const records = neighbor ? this.neighborRecords : this.edgeRecords;
    const adjacency = neighbor ? this.neighborAdjacency : this.edgeAdjacency;
    for (const key of adjacency.get(id) ?? []) {
      const edge = records.get(key);
      if (edge) this.writeEdge(edge, neighbor);
    }
  }

  private writeNode(node: GraphNode): void {
    const particle = this.particles.get(node.id);
    if (!particle) return;
    const color = nodeColor(node).multiplyScalar(0.58 + Math.min(0.72, node.activation * 0.8 + node.stability * 0.42));
    this.nodeBatch.patch(`${NODE_PREFIX}${node.id}`, {
      position: [particle.position.x, particle.position.y, this.mode === "2d" ? 0 : particle.position.z],
      color: [color.r, color.g, color.b],
      size: nodeSize(node) * (this.style === "organic" ? 2.5 : 1.7),
    });
    this.solidDirty = true;
  }

  private writeEdge(edge: GraphEdge, neighbor: boolean): void {
    const source = this.particles.get(edge.source);
    const target = this.particles.get(edge.target);
    const batch = neighbor ? this.neighborBatch : this.edgeBatch;
    const prefix = neighbor ? NEIGHBOR_PREFIX : EDGE_PREFIX;
    const entityId = edgeEntityId(prefix, edge);
    if (!source || !target) {
      batch.remove(entityId);
      return;
    }
    const color = edgeColor(edge, neighbor);
    batch.patch(entityId, {
      position: [
        source.position.x, source.position.y, this.mode === "2d" ? 0 : source.position.z,
        target.position.x, target.position.y, this.mode === "2d" ? 0 : target.position.z,
      ],
      color: [color.r, color.g, color.b],
    });
  }

  private registerNode(node: GraphNode): void {
    const id = `${NODE_PREFIX}${node.id}`;
    this.nodeEntityIds.add(id);
    registerRuntimeEntity({ id, ownerId: NODE_OWNER, kind: "threemind-node", handle: { batch: "nodes", entityId: id }, metadata: { nodeId: node.id } }, this.runtimeContext);
  }

  private registerEdge(edge: GraphEdge, neighbor: boolean): void {
    const prefix = neighbor ? NEIGHBOR_PREFIX : EDGE_PREFIX;
    const ids = neighbor ? this.neighborEntityIds : this.edgeEntityIds;
    const id = edgeEntityId(prefix, edge);
    ids.add(id);
    registerRuntimeEntity({ id, ownerId: NODE_OWNER, kind: neighbor ? "threemind-spatial-neighbor" : "threemind-edge", handle: { batch: neighbor ? "neighbors" : "edges", entityId: id }, metadata: { source: edge.source, target: edge.target } }, this.runtimeContext);
  }

  private scheduleCommit(): void {
    this.commits.enqueue(NODE_OWNER, () => {
      if (this.disposed) return;
      this.commitBatches();
      this.runtime.invalidate();
    });
  }

  private commitBatches(): void {
    this.nodeBatch.commit();
    this.edgeBatch.commit();
    this.neighborBatch.commit();
    this.refreshSolidMesh();
    this.neighborhoods.visible = this.neighborBatch.entityCount > 0;
  }

  private advanceVisualMotion(): void {
    if (this.disposed || !this.nodes.size) return;
    for (const edge of this.edgeRecords.values()) {
      const source = this.particles.get(edge.source);
      const target = this.particles.get(edge.target);
      if (!source || !target) continue;
      const delta = target.position.clone().sub(source.position);
      const length = Math.max(0.01, delta.length());
      const desired = 35 + (1 - edge.weight) * 72;
      delta.multiplyScalar(((length - desired) * (0.00055 + edge.weight * 0.0012)) / length);
      source.velocity.add(delta);
      target.velocity.sub(delta);
    }
    for (const node of this.nodes.values()) {
      const particle = this.particles.get(node.id);
      if (!particle) continue;
      particle.velocity.addScaledVector(particle.target.clone().sub(particle.position), 0.0025);
      particle.velocity.addScaledVector(particle.position, -0.000045);
      if (this.mode === "2d") particle.velocity.z += -particle.position.z * 0.14;
      particle.velocity.multiplyScalar(0.915);
      particle.position.add(particle.velocity);
      this.writeNode(node);
    }
    for (const edge of this.edgeRecords.values()) this.writeEdge(edge, false);
    for (const edge of this.neighborRecords.values()) this.writeEdge(edge, true);
    this.commitBatches();
  }

  private createSolidMeshes(): void {
    if (this.shape !== "sphere" && this.shape !== "cube") return;
    this.ensureSolidCapacity(256);
  }

  private ensureSolidCapacity(required: number): void {
    if (required <= this.solidCapacity && this.sphereMesh && this.cubeMesh) return;
    let capacity = Math.max(256, this.solidCapacity || 256);
    while (capacity < required) capacity *= 2;
    this.disposeSolidMesh(this.sphereMesh);
    this.disposeSolidMesh(this.cubeMesh);
    this.sphereMesh = new THREE.InstancedMesh(
      new THREE.SphereGeometry(1, 12, 10),
      new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.94, depthWrite: false }),
      capacity,
    );
    this.cubeMesh = new THREE.InstancedMesh(
      new THREE.BoxGeometry(1.7, 1.7, 1.7),
      new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.92, depthWrite: false }),
      capacity,
    );
    this.sphereMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.cubeMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.sphereMesh.frustumCulled = false;
    this.cubeMesh.frustumCulled = false;
    this.sphereMesh.renderOrder = 3;
    this.cubeMesh.renderOrder = 3;
    this.root.add(this.sphereMesh, this.cubeMesh);
    this.solidCapacity = capacity;
    this.solidDirty = true;
    this.setSolidVisibility();
  }

  private refreshSolidMesh(): void {
    if (!this.solidDirty || (this.shape !== "sphere" && this.shape !== "cube")) return;
    this.ensureSolidCapacity(this.nodeBatch.entityCount);
    const mesh = this.shape === "sphere" ? this.sphereMesh : this.cubeMesh;
    if (!mesh) return;
    for (const node of this.nodes.values()) {
      const particle = this.particles.get(node.id);
      const slot = this.nodeBatch.getSlot(`${NODE_PREFIX}${node.id}`);
      if (!particle || slot < 0) continue;
      const color = nodeColor(node).multiplyScalar(0.58 + Math.min(0.72, node.activation * 0.8 + node.stability * 0.42));
      this.scale.setScalar(nodeSize(node) * 0.42);
      this.matrix.compose(particle.position, this.identity, this.scale);
      mesh.setMatrixAt(slot, this.matrix);
      mesh.setColorAt(slot, color);
    }
    mesh.count = this.nodeBatch.entityCount;
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    this.solidDirty = false;
  }

  private setSolidVisibility(): void {
    const solid = this.mode === "3d" && (this.shape === "sphere" || this.shape === "cube");
    this.points.visible = !solid;
    if (this.sphereMesh) this.sphereMesh.visible = solid && this.shape === "sphere";
    if (this.cubeMesh) this.cubeMesh.visible = solid && this.shape === "cube";
  }

  private disposeSolidMesh(mesh: THREE.InstancedMesh | null): void {
    if (!mesh) return;
    this.root.remove(mesh);
    mesh.geometry.dispose();
    (mesh.material as THREE.Material).dispose();
  }
}
