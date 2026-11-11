/**
 * ThreeMind uses a deliberately narrow, runtime-only slice of ThreeJSON.
 *
 * ThreeJSON ships JavaScript-first packages.  Keeping this local declaration
 * narrow prevents ThreeMind from depending on undocumented internals while still
 * giving the projection domain strict enough TypeScript contracts.
 */
declare module "threejson/core" {
  import type * as THREE from "three";

  export type DynamicGeometryBatch = {
    geometry: THREE.BufferGeometry;
    entityCount: number;
    capacity: number;
    set(entityId: string | number, values?: Record<string, unknown>): number;
    patch(entityId: string | number, values?: Record<string, unknown>): number;
    remove(entityId: string | number): boolean;
    clear(): void;
    commit(): { entityCount: number; vertexCount: number; capacity: number };
    dispose(): void;
    has(entityId: string | number): boolean;
    getSlot(entityId: string | number): number;
  };

  export function createDynamicPointBatch(options: Record<string, unknown>): DynamicGeometryBatch;
  export function createDynamicSegmentBatch(options: Record<string, unknown>): DynamicGeometryBatch;

  export type FrameCommitScheduler = {
    enqueue(key: string, job: (now: number) => unknown): number;
    dispose(): void;
  };
  export function createFrameCommitScheduler(options?: Record<string, unknown>): FrameCommitScheduler;

  export type SceneRuntime = {
    scene: THREE.Scene;
    camera: THREE.Camera;
    renderer: THREE.WebGLRenderer;
    controls: {
      enabled?: boolean;
      enableRotate?: boolean;
      screenSpacePanning?: boolean;
      target?: THREE.Vector3;
      update?: () => void;
      dispose?: () => void;
    } | null;
    start(): void;
    resize(size: { width: number; height: number; updateStyle?: boolean }): void;
    invalidate(): boolean;
    dispose(): void;
  };
  export function createSceneRuntime(options: Record<string, unknown>): SceneRuntime;

  export function createRuntimeContext(): unknown;
  export function registerRuntimeEntity(record: Record<string, unknown>, runtimeScope: unknown, options?: Record<string, unknown>): unknown;
  export function removeRuntimeEntity(id: string | number, runtimeScope: unknown): boolean;
}
