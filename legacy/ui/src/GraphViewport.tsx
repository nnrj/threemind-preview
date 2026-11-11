"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

export type ViewMode = "2d" | "3d";
export type ThreeNodeShape = "glow" | "circle" | "square" | "sphere" | "cube";
export type VisualStyle = "organic" | "minimal";

type GraphNode = { id: number; activation: number; stability: number; touch_count: number; direct: number; associative: number; position?: number[] | null; cluster?: number | null };
type GraphEdge = { source: number; target: number; weight: number; stability: number; touched: boolean };
type GraphData = { nodes: GraphNode[]; edges: GraphEdge[]; neighbors?: GraphEdge[] };
type Particle = { position: THREE.Vector3; velocity: THREE.Vector3 };

function seededPosition(id: number, mode: ViewMode) {
  const phi = (id * 2.399963229728653) % (Math.PI * 2);
  const radius = 26 + Math.sqrt(id % 503) * 12;
  return new THREE.Vector3(Math.cos(phi) * radius, Math.sin(phi) * radius, mode === "3d" ? ((id * 37) % 150) - 75 : 0);
}

function projectedPosition(node: GraphNode, mode: ViewMode) {
  if (!node.position?.length) return seededPosition(node.id, mode);
  const scale = 105;
  return new THREE.Vector3(
    Number(node.position[0] ?? 0) * scale,
    Number(node.position[1] ?? 0) * scale,
    mode === "3d" ? Number(node.position[2] ?? 0) * scale : 0,
  );
}

function nodeColor(node: GraphNode) {
  if (node.direct > 0) return new THREE.Color(0xf3bd72);
  if (node.associative > 0) return new THREE.Color(0x7ce0d3);
  return new THREE.Color(0x819e96);
}

export default function GraphViewport({ graph, mode, shape, style, continuousMotion }: { graph: GraphData | null; mode: ViewMode; shape: ThreeNodeShape; style: VisualStyle; continuousMotion: boolean }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef(graph);
  const modeRef = useRef(mode);
  const shapeRef = useRef(shape);
  const styleRef = useRef(style);
  const continuousMotionRef = useRef(continuousMotion);
  useEffect(() => { graphRef.current = graph; }, [graph]);
  useEffect(() => { modeRef.current = mode; }, [mode]);
  useEffect(() => { shapeRef.current = shape; }, [shape]);
  useEffect(() => { styleRef.current = style; }, [style]);
  useEffect(() => { continuousMotionRef.current = continuousMotion; }, [continuousMotion]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const scene = new THREE.Scene();
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);
    host.appendChild(renderer.domElement);

    const perspective = new THREE.PerspectiveCamera(48, 1, 0.1, 3000);
    const orthographic = new THREE.OrthographicCamera(-100, 100, 100, -100, 0.1, 3000);
    const nodeGeometry = new THREE.BufferGeometry();
    const edgeGeometry = new THREE.BufferGeometry();
    const neighborhoodGeometry = new THREE.BufferGeometry();
    const pointMaterial = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      depthTest: false,
      blending: THREE.AdditiveBlending,
      vertexColors: true,
      vertexShader: `attribute float size; varying vec3 vColor; void main() { vColor = color; vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_PointSize = size * (280.0 / max(1.0, -mv.z)); gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `uniform float square; uniform float organic; varying vec3 vColor; void main() { vec2 p = gl_PointCoord - vec2(.5); float radius = length(p); if (square < .5 && radius > .5) discard; float edge = square > .5 ? max(abs(p.x), abs(p.y)) : radius; float core = 1.0 - smoothstep(organic > .5 ? .22 : .40, .5, edge); float alpha = organic > .5 ? core * (.26 + .74 * core) : core; gl_FragColor = vec4(vColor, alpha); }`,
      uniforms: { square: { value: 0 }, organic: { value: 1 } },
    });
    const points = new THREE.Points(nodeGeometry, pointMaterial);
    const lines = new THREE.LineSegments(edgeGeometry, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.42, depthWrite: false }));
    const neighborhoods = new THREE.LineSegments(neighborhoodGeometry, new THREE.LineBasicMaterial({ color: 0x4f8f88, transparent: true, opacity: 0.13, depthWrite: false }));
    const sphereMesh = new THREE.InstancedMesh(new THREE.SphereGeometry(1, 12, 10), new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.94, depthWrite: false }), 10_000);
    const cubeMesh = new THREE.InstancedMesh(new THREE.BoxGeometry(1.7, 1.7, 1.7), new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.92, depthWrite: false }), 10_000);
    points.frustumCulled = false;
    lines.frustumCulled = false;
    neighborhoods.frustumCulled = false;
    points.renderOrder = 3;
    sphereMesh.renderOrder = 3;
    cubeMesh.renderOrder = 3;
    lines.renderOrder = 1;
    neighborhoods.renderOrder = 0;
    sphereMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    cubeMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    scene.add(neighborhoods, lines, points, sphereMesh, cubeMesh);

    const particles = new Map<number, Particle>();
    const target = new THREE.Vector3();
    const identity = new THREE.Quaternion();
    const matrix = new THREE.Matrix4();
    const scale = new THREE.Vector3();
    let yaw = 0.62, pitch = 0.42, distance = 285, orthographicZoom = 1, width = 1, height = 1, frame = 0;
    let activePointer: { mode: "pan" | "orbit"; x: number; y: number } | null = null;

    const resize = () => {
      const box = host.getBoundingClientRect(); width = Math.max(1, box.width); height = Math.max(1, box.height);
      renderer.setSize(width, height, false); perspective.aspect = width / height; perspective.updateProjectionMatrix();
      const span = 180; orthographic.left = -span * width / height; orthographic.right = span * width / height; orthographic.top = span; orthographic.bottom = -span; orthographic.updateProjectionMatrix();
    };
    const updateCamera = (currentMode: ViewMode) => {
      if (currentMode === "3d") {
        const cosPitch = Math.cos(pitch);
        perspective.position.set(target.x + distance * cosPitch * Math.sin(yaw), target.y + distance * Math.sin(pitch), target.z + distance * cosPitch * Math.cos(yaw));
        perspective.lookAt(target); return perspective;
      }
      orthographic.position.set(target.x, target.y, 300); orthographic.zoom = orthographicZoom; orthographic.lookAt(target.x, target.y, 0); orthographic.updateProjectionMatrix(); return orthographic;
    };
    resize(); window.addEventListener("resize", resize);

    const animate = () => {
      const data = graphRef.current; const currentMode = modeRef.current; const currentShape = shapeRef.current; const currentStyle = styleRef.current;
      pointMaterial.uniforms.square.value = currentShape === "square" ? 1 : 0;
      pointMaterial.uniforms.organic.value = currentStyle === "organic" ? 1 : 0;
      if (data) {
        const live = new Set(data.nodes.map((node) => node.id));
        for (const id of particles.keys()) if (!live.has(id)) particles.delete(id);
        for (const node of data.nodes) {
          if (!particles.has(node.id)) particles.set(node.id, { position: projectedPosition(node, currentMode), velocity: new THREE.Vector3() });
          else if (node.position?.length && !continuousMotionRef.current) particles.get(node.id)!.position.copy(projectedPosition(node, currentMode));
        }
        // These forces are a display-only layout, never Core dynamics.
        if (continuousMotionRef.current) {
          for (const edge of data.edges) {
            const source = particles.get(edge.source), destination = particles.get(edge.target); if (!source || !destination) continue;
            const delta = destination.position.clone().sub(source.position); const length = Math.max(.01, delta.length()); const desired = 35 + (1 - edge.weight) * 72;
            delta.multiplyScalar(((length - desired) * (.00055 + edge.weight * .0012)) / length); source.velocity.add(delta); destination.velocity.sub(delta);
          }
          for (const node of data.nodes) {
            const particle = particles.get(node.id)!; particle.velocity.addScaledVector(particle.position, -.000045);
            if (currentMode === "2d") particle.velocity.z += -particle.position.z * .14;
            particle.velocity.multiplyScalar(.915); particle.position.add(particle.velocity);
          }
        }
        const positions = new Float32Array(data.nodes.length * 3), colors = new Float32Array(data.nodes.length * 3), sizes = new Float32Array(data.nodes.length);
        const solid = currentMode === "3d" && (currentShape === "sphere" || currentShape === "cube");
        points.visible = !solid; sphereMesh.visible = solid && currentShape === "sphere"; cubeMesh.visible = solid && currentShape === "cube";
        data.nodes.forEach((node, index) => {
          const particle = particles.get(node.id)!; const color = nodeColor(node).multiplyScalar(.58 + Math.min(.72, node.activation * .8 + node.stability * .42));
          const nodeSize = 5.2 + Math.sqrt(node.touch_count) * .48 + node.stability * 5 + node.activation * 6;
          positions.set([particle.position.x, particle.position.y, currentMode === "2d" ? 0 : particle.position.z], index * 3); colors.set([color.r, color.g, color.b], index * 3); sizes[index] = nodeSize * (currentStyle === "organic" ? 2.5 : 1.7);
          if (solid) {
            scale.setScalar(nodeSize * .42); matrix.compose(particle.position, identity, scale);
            const mesh = currentShape === "sphere" ? sphereMesh : cubeMesh; mesh.setMatrixAt(index, matrix); mesh.setColorAt(index, color);
          }
        });
        if (solid) { const mesh = currentShape === "sphere" ? sphereMesh : cubeMesh; mesh.count = data.nodes.length; mesh.instanceMatrix.needsUpdate = true; if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true; }
        nodeGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3)); nodeGeometry.setAttribute("color", new THREE.BufferAttribute(colors, 3)); nodeGeometry.setAttribute("size", new THREE.BufferAttribute(sizes, 1));
        const edgePositions = new Float32Array(data.edges.length * 6), edgeColors = new Float32Array(data.edges.length * 6); let write = 0;
        for (const edge of data.edges) {
          const source = particles.get(edge.source), destination = particles.get(edge.target); if (!source || !destination) continue;
          const color = (edge.touched ? new THREE.Color(0x7ce0d3) : new THREE.Color(0x5c7b74)).multiplyScalar(.35 + edge.weight * .6 + edge.stability * .3);
          edgePositions.set([source.position.x, source.position.y, currentMode === "2d" ? 0 : source.position.z, destination.position.x, destination.position.y, currentMode === "2d" ? 0 : destination.position.z], write * 6); edgeColors.set([color.r, color.g, color.b, color.r, color.g, color.b], write * 6); write += 1;
        }
        edgeGeometry.setAttribute("position", new THREE.BufferAttribute(edgePositions.slice(0, write * 6), 3)); edgeGeometry.setAttribute("color", new THREE.BufferAttribute(edgeColors.slice(0, write * 6), 3));
        const neighborhoodPositions = new Float32Array((data.neighbors?.length ?? 0) * 6); let neighborhoodWrite = 0;
        for (const edge of data.neighbors ?? []) {
          const source = particles.get(edge.source), destination = particles.get(edge.target); if (!source || !destination) continue;
          neighborhoodPositions.set([source.position.x, source.position.y, currentMode === "2d" ? 0 : source.position.z, destination.position.x, destination.position.y, currentMode === "2d" ? 0 : destination.position.z], neighborhoodWrite * 6);
          neighborhoodWrite += 1;
        }
        neighborhoodGeometry.setAttribute("position", new THREE.BufferAttribute(neighborhoodPositions.slice(0, neighborhoodWrite * 6), 3));
        neighborhoods.visible = neighborhoodWrite > 0;
      }
      renderer.render(scene, updateCamera(currentMode)); frame = requestAnimationFrame(animate);
    };
    animate();

    const pan = (dx: number, dy: number) => { const factor = modeRef.current === "3d" ? distance / Math.max(width, height) : 170 / (Math.max(width, height) * orthographicZoom); target.x -= dx * factor; target.y += dy * factor; };
    const pointerDown = (event: PointerEvent) => { host.focus(); activePointer = { mode: event.button === 2 || event.button === 1 || modeRef.current === "2d" ? "pan" : "orbit", x: event.clientX, y: event.clientY }; host.setPointerCapture(event.pointerId); };
    const pointerMove = (event: PointerEvent) => { if (!activePointer) return; const dx = event.clientX - activePointer.x, dy = event.clientY - activePointer.y; activePointer.x = event.clientX; activePointer.y = event.clientY; if (activePointer.mode === "orbit") { yaw -= dx * .007; pitch = Math.max(-1.32, Math.min(1.32, pitch - dy * .007)); } else pan(dx, dy); };
    const pointerUp = () => { activePointer = null; };
    const wheel = (event: WheelEvent) => { event.preventDefault(); if (modeRef.current === "3d") distance = Math.max(35, Math.min(1400, distance * (event.deltaY > 0 ? 1.1 : .9))); else orthographicZoom = Math.max(.18, Math.min(8, orthographicZoom * (event.deltaY > 0 ? .9 : 1.1))); };
    const keyDown = (event: KeyboardEvent) => { const step = modeRef.current === "3d" ? distance * .04 : 14 / orthographicZoom; const key = event.key.toLowerCase(); if (key === "w") target.y += step; else if (key === "s") target.y -= step; else if (key === "a") target.x -= step; else if (key === "d") target.x += step; else if (key === "q" && modeRef.current === "3d") target.z -= step; else if (key === "e" && modeRef.current === "3d") target.z += step; else if (key === "f") { target.set(0, 0, 0); distance = 285; orthographicZoom = 1; } else return; event.preventDefault(); };
    const preventMenu = (event: Event) => event.preventDefault();
    host.addEventListener("pointerdown", pointerDown); host.addEventListener("pointermove", pointerMove); host.addEventListener("pointerup", pointerUp); host.addEventListener("pointercancel", pointerUp); host.addEventListener("wheel", wheel, { passive: false }); host.addEventListener("keydown", keyDown); host.addEventListener("contextmenu", preventMenu);
    return () => { cancelAnimationFrame(frame); window.removeEventListener("resize", resize); host.removeEventListener("pointerdown", pointerDown); host.removeEventListener("pointermove", pointerMove); host.removeEventListener("pointerup", pointerUp); host.removeEventListener("pointercancel", pointerUp); host.removeEventListener("wheel", wheel); host.removeEventListener("keydown", keyDown); host.removeEventListener("contextmenu", preventMenu); renderer.dispose(); nodeGeometry.dispose(); edgeGeometry.dispose(); neighborhoodGeometry.dispose(); sphereMesh.geometry.dispose(); cubeMesh.geometry.dispose(); pointMaterial.dispose(); (lines.material as THREE.Material).dispose(); (neighborhoods.material as THREE.Material).dispose(); (sphereMesh.material as THREE.Material).dispose(); (cubeMesh.material as THREE.Material).dispose(); renderer.domElement.remove(); };
  }, []);
  return <div ref={hostRef} className="graph-viewport" tabIndex={0} aria-label="可导航的网络观察空间" />;
}
