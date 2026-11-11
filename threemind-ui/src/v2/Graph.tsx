import { t } from "./i18n";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { Camera, Maximize2, MousePointer2, RotateCcw } from "lucide-react";
import {
  usePreferences,
  effectivePreferences,
  updatePreferences,
} from "./preferences";
import { timeLabel, numberLabel } from "./api";
import { canvasGraph } from "./GraphCanvas";
import CapturePanel from "./CapturePanel";
import type { CaptureSource } from "./visualCapture";

export type Frame = {
  positions: Float32Array;
  colors: Float32Array;
  sizes: Float32Array;
  ids: Float64Array | (string | number)[];
  edgePositions: Float32Array;
  edgeColors: Float32Array;
  moved: boolean;
  snapshot: boolean;
  labels: { index: number; text: string }[];
  diagnostics: { prepare_ms: number; layout_ms: number; layout_steps: number };
  meta: any;
};
export default function Graph({
  project,
  run,
  onSelect,
  polling = true,
  revision,
  endpoint,
}: {
  project: string;
  run: string;
  onSelect?: (id: string | number) => void;
  polling?: boolean;
  revision?: number;
  endpoint?: string;
}) {
  const host = useRef<HTMLDivElement>(null),
    receiver = useRef<(frame: Frame) => void>(() => {}),
    reset = useRef(() => {}),
    exportImage = useRef(() => {});
  const renderReady = useRef(false),
    runRef = useRef(run);
  const capture = useRef<CaptureSource>({ draw: () => { throw new Error("Canvas is not ready"); }, metadata: () => ({}) });
  runRef.current = run;
  const preferences = usePreferences(),
    settings = effectivePreferences(preferences);
  const settingsRef = useRef(settings);
  settingsRef.current = settings;
  const selectedRef = useRef(onSelect);
  selectedRef.current = onSelect;
  const [meta, setMeta] = useState<any>(null),
    [error, setError] = useState("");
  const [stats, setStats] = useState<any>(null);
  const [canvasFallback, setCanvasFallback] = useState(false);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    if (canvasFallback) {
      try {
        const view = canvasGraph(
          element,
          () => settingsRef.current,
          (id) => selectedRef.current?.(id),
          setStats,
        );
        receiver.current = view.receive;
        reset.current = view.reset;
        exportImage.current = () => view.exportImage(runRef.current);
        capture.current = { draw: () => view.capture(), metadata: () => ({
          world: `ThreeMind · ${runRef.current}`,
          time: timeLabel(view.metadata()?.time_us),
          legend: t("直接触达、联想触达；画面为显示采样。"),
        }) };
        renderReady.current = true;
        setError("");
        return () => {
          view.dispose();
          receiver.current = () => {};
          exportImage.current = () => {};
          renderReady.current = false;
          capture.current = { draw: () => { throw new Error("Canvas is not ready"); }, metadata: () => ({}) };
        };
      } catch {
        setError(t("浏览器无法建立图形画布，仍可通过数据查询查看记录。"));
        return;
      }
    }
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: "high-performance",
      });
    } catch {
      setCanvasFallback(true);
      return;
    }
    renderer.setClearColor(0x081b1d, 0);
    renderer.domElement.className = "graph-webgl-canvas";
    renderReady.current = true;
    element.appendChild(renderer.domElement);
    const labelCanvas = document.createElement("canvas");
    labelCanvas.className = "graph-label-canvas";
    labelCanvas.setAttribute("aria-hidden", "true");
    element.appendChild(labelCanvas);
    const labelsContext = labelCanvas.getContext("2d");
    const scene = new THREE.Scene();
    const perspective = new THREE.PerspectiveCamera(48, 1, 0.1, 10000),
      orthographic = new THREE.OrthographicCamera(
        -180,
        180,
        180,
        -180,
        0.1,
        10000,
      );
    perspective.position.set(180, 130, 340);
    orthographic.position.set(0, 0, 500);
    let camera: THREE.Camera = perspective;
    let controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = false;
    const nodeGeometry = new THREE.BufferGeometry(),
      edgeGeometry = new THREE.BufferGeometry();
    const pointMaterial = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      depthTest: false,
      blending: THREE.AdditiveBlending,
      vertexColors: true,
      uniforms: {
        square: { value: 0 },
        organic: { value: 1 },
        ratio: { value: 1 },
        perspectiveMode: { value: 1 },
        nodeScale: { value: 1 },
      },
      vertexShader:
        "attribute float size; varying vec3 vColor; uniform float ratio; uniform float perspectiveMode; uniform float nodeScale; void main(){vColor=color;vec4 mv=modelViewMatrix*vec4(position,1.0);gl_PointSize=size*nodeScale*ratio*(perspectiveMode>.5?280.0/max(1.0,-mv.z):1.0);gl_Position=projectionMatrix*mv;}",
      fragmentShader:
        "uniform float square;uniform float organic;varying vec3 vColor;void main(){vec2 p=gl_PointCoord-vec2(.5);float r=length(p);if(square<.5&&r>.5)discard;float e=square>.5?max(abs(p.x),abs(p.y)):r;float core=1.0-smoothstep(organic>.5?.22:.40,.5,e);gl_FragColor=vec4(vColor,organic>.5?core*(.26+.74*core):core);}",
    });
    const points = new THREE.Points(nodeGeometry, pointMaterial);
    const lineMaterial = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.55,
      depthWrite: false,
    });
    const lines = new THREE.LineSegments(edgeGeometry, lineMaterial);
    points.frustumCulled = lines.frustumCulled = false;
    scene.add(lines, points);
    const sphereGeometry = new THREE.SphereGeometry(1, 12, 8),
      cubeGeometry = new THREE.BoxGeometry(1.7, 1.7, 1.7),
      solidMaterial = new THREE.MeshBasicMaterial({
        transparent: true,
        opacity: 0.95,
      });
    let solid: THREE.InstancedMesh | null = null,
      capacity = 0;
    let latest: Frame | null = null,
      dirty = true,
      raf = 0,
      lastDraw = 0,
      lastMode = "",
      lastShape = "",
      lastDpr = 0;
    let lastStyle = "",
      lastScale = 0,
      lastOpacity = -1,
      lastFont = 0;
    let draws = 0,
      lastStatsAt = 0,
      uploadMs = 0,
      drawMs = 0,
      labelsDrawn = 0;
    let allocations = 0;
    let autoFit = true;
    const bounds = new THREE.Sphere(new THREE.Vector3(), 180);
    const fitView = () => {
      const aspect = perspective.aspect;
      const angle = Math.min(
        THREE.MathUtils.degToRad(perspective.fov / 2),
        Math.atan(
          Math.tan(THREE.MathUtils.degToRad(perspective.fov / 2)) * aspect,
        ),
      );
      const radius = Math.max(15, bounds.radius) * 1.22;
      const direction = perspective.position
        .clone()
        .sub(controls.target)
        .normalize();
      perspective.position
        .copy(bounds.center)
        .addScaledVector(direction, radius / Math.sin(angle));
      orthographic.position
        .copy(bounds.center)
        .add(new THREE.Vector3(0, 0, 500));
      orthographic.zoom = (180 * Math.min(1, aspect)) / radius;
      orthographic.updateProjectionMatrix();
      controls.target.copy(bounds.center);
      controls.update();
      dirty = true;
    };
    const userView = () => {
      autoFit = false;
    };
    const matrix = new THREE.Matrix4(),
      position = new THREE.Vector3(),
      scale = new THREE.Vector3(),
      quaternion = new THREE.Quaternion(),
      color = new THREE.Color();
    const resize = () => {
      const w = Math.max(element.clientWidth, 1),
        h = Math.max(element.clientHeight, 1);
      renderer.setSize(w, h, false);
      const ratio = renderer.getPixelRatio();
      labelCanvas.width = Math.round(w * ratio);
      labelCanvas.height = Math.round(h * ratio);
      perspective.aspect = w / h;
      perspective.updateProjectionMatrix();
      orthographic.left = (-180 * w) / h;
      orthographic.right = (180 * w) / h;
      orthographic.updateProjectionMatrix();
      if (autoFit) fitView();
      dirty = true;
    };
    const change = () => {
      dirty = true;
    };
    controls.addEventListener("change", change);
    controls.addEventListener("start", userView);
    reset.current = () => {
      autoFit = true;
      controls.target.set(0, 0, 0);
      perspective.position.set(180, 130, 340);
      fitView();
    };
    function setAttribute(
      geometry: THREE.BufferGeometry,
      name: string,
      data: Float32Array,
      size: number,
      needed = true,
    ) {
      if (!needed) return;
      let attribute = geometry.getAttribute(name) as
        THREE.BufferAttribute | undefined;
      if (
        !attribute ||
        attribute.array.length < data.length ||
        attribute.array.length > Math.max(size, data.length) * 4
      ) {
        // Three.js does not dispose buffers when an attribute is replaced.
        // Dispose the geometry's GPU resources, then let the next draw rebuild
        // its still-current attributes. This also permits shrinking the budget.
        if (attribute) geometry.dispose();
        const count =
          size * 2 ** Math.ceil(Math.log2(Math.max(1, data.length / size)));
        attribute = new THREE.BufferAttribute(
          new Float32Array(count),
          size,
        ).setUsage(THREE.DynamicDrawUsage);
        geometry.setAttribute(name, attribute);
        allocations++;
      }
      const target = attribute.array as Float32Array;
      let start = -1,
        ranges = 0;
      attribute.clearUpdateRanges();
      for (let i = 0; i < data.length; i++) {
        if (target[i] !== data[i]) {
          if (start < 0) start = i;
          target[i] = data[i];
        } else if (start >= 0) {
          attribute.addUpdateRange(start, i - start);
          ranges++;
          start = -1;
        }
      }
      if (start >= 0) {
        attribute.addUpdateRange(start, data.length - start);
        ranges++;
      }
      if (ranges > 128) {
        attribute.clearUpdateRanges();
        attribute.addUpdateRange(0, data.length);
      }
      if (ranges) attribute.needsUpdate = true;
    }
    function upload(frame: Frame, changedColors = true) {
      const started = performance.now();
      const shape = settingsRef.current.shape;
      setAttribute(
        nodeGeometry,
        "position",
        frame.positions,
        3,
        frame.moved || !nodeGeometry.hasAttribute("position"),
      );
      setAttribute(nodeGeometry, "color", frame.colors, 3, changedColors);
      setAttribute(nodeGeometry, "size", frame.sizes, 1, changedColors);
      setAttribute(
        edgeGeometry,
        "position",
        frame.edgePositions,
        3,
        frame.moved || !edgeGeometry.hasAttribute("position"),
      );
      setAttribute(edgeGeometry, "color", frame.edgeColors, 3, changedColors);
      nodeGeometry.setDrawRange(0, frame.ids.length);
      edgeGeometry.setDrawRange(0, frame.edgePositions.length / 3);
      if (frame.snapshot) {
        if (frame.ids.length) {
          const box = new THREE.Box3().setFromArray(frame.positions);
          box.getBoundingSphere(bounds);
          if (autoFit) fitView();
        }
      }
      const useSolid = shape === "sphere" || shape === "cube";
      points.visible = !useSolid;
      if (useSolid) {
        if (
          !solid ||
          capacity < frame.ids.length ||
          capacity > Math.max(1, frame.ids.length) * 4 ||
          shape !== lastShape
        ) {
          if (solid) {
            scene.remove(solid);
            solid.dispose();
          }
          capacity = 2 ** Math.ceil(Math.log2(Math.max(1, frame.ids.length)));
          solid = new THREE.InstancedMesh(
            shape === "sphere" ? sphereGeometry : cubeGeometry,
            solidMaterial,
            capacity,
          );
          solid.frustumCulled = false;
          solid.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
          scene.add(solid);
        }
        solid.visible = true;
        solid.count = frame.ids.length;
        for (let i = 0; i < frame.ids.length; i++) {
          position.fromArray(frame.positions, i * 3);
          scale.setScalar(
            frame.sizes[i] * 0.18 * settingsRef.current.nodeScale,
          );
          matrix.compose(position, quaternion, scale);
          solid.setMatrixAt(i, matrix);
          if (changedColors || shape !== lastShape || !solid.instanceColor) {
            color.fromArray(frame.colors, i * 3);
            solid.setColorAt(i, color);
          }
        }
        solid.instanceMatrix.needsUpdate = true;
        if (solid.instanceColor && changedColors)
          solid.instanceColor.needsUpdate = true;
      } else if (solid) solid.visible = false;
      pointMaterial.uniforms.square.value = shape === "square" ? 1 : 0;
      pointMaterial.uniforms.organic.value =
        shape === "glow" && settingsRef.current.visualStyle === "organic"
          ? 1
          : 0;
      lastShape = shape;
      dirty = true;
      uploadMs = performance.now() - started;
    }
    receiver.current = (frame) => {
      if (!latest && !frame.snapshot) return;
      latest = { ...latest, ...frame } as Frame;
      upload(latest, frame.snapshot);
    };
    const projected = new THREE.Vector3();
    function drawLabels() {
      if (!labelsContext) return;
      const p = settingsRef.current,
        ratio = renderer.getPixelRatio();
      labelsContext.setTransform(ratio, 0, 0, ratio, 0, 0);
      labelsContext.clearRect(
        0,
        0,
        labelCanvas.width / ratio,
        labelCanvas.height / ratio,
      );
      labelsDrawn = 0;
      if (!latest || p.graphLabels === "none") return;
      const width = labelCanvas.width / ratio,
        height = labelCanvas.height / ratio,
        boxes: number[][] = [];
      labelsContext.font = p.labelFont + "px system-ui, sans-serif";
      labelsContext.textBaseline = "middle";
      for (const label of latest.labels ?? []) {
        projected.fromArray(latest.positions, label.index * 3).project(camera);
        if (
          projected.z < -1 ||
          projected.z > 1 ||
          Math.abs(projected.x) > 1 ||
          Math.abs(projected.y) > 1
        )
          continue;
        const x = ((projected.x + 1) * width) / 2 + 8,
          y = ((1 - projected.y) * height) / 2;
        const w = labelsContext.measureText(label.text).width + 8,
          h = p.labelFont + 8;
        if (x + w > width || y - h / 2 < 0 || y + h / 2 > height) continue;
        if (
          boxes.some(
            (b) =>
              x < b[0] + b[2] &&
              x + w > b[0] &&
              y - h / 2 < b[1] + b[3] &&
              y + h / 2 > b[1],
          )
        )
          continue;
        boxes.push([x, y - h / 2, w, h]);
        labelsContext.fillStyle = "rgba(6,24,25,.84)";
        labelsContext.fillRect(x, y - h / 2, w, h);
        labelsContext.fillStyle = "#e2efdc";
        labelsContext.fillText(label.text, x + 4, y);
        labelsDrawn++;
      }
    }
    const captureCanvas = document.createElement("canvas");
    capture.current = { draw: () => {
      if (!latest || !renderReady.current) throw new Error("Canvas is not ready");
      renderer.render(scene, camera); drawLabels();
      captureCanvas.width = renderer.domElement.width; captureCanvas.height = renderer.domElement.height;
      const ctx = captureCanvas.getContext("2d")!;
      ctx.fillStyle = "#081b1d"; ctx.fillRect(0, 0, captureCanvas.width, captureCanvas.height);
      ctx.drawImage(renderer.domElement, 0, 0); ctx.drawImage(labelCanvas, 0, 0);
      return captureCanvas;
    }, metadata: () => ({ world: `ThreeMind · ${runRef.current} · r${latest?.meta?.revision ?? "?"}`,
      time: timeLabel(latest?.meta?.time_us), legend: t("直接触达、联想触达；画面为显示采样。") }) };
    exportImage.current = () => {
      if (!latest || !renderReady.current) return;
      renderer.render(scene, camera);
      drawLabels();
      const canvas = document.createElement("canvas"),
        ratio = renderer.getPixelRatio();
      const imageRevision = latest.meta.revision;
      canvas.width = renderer.domElement.width;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.font = "12px system-ui";
      const footer = [
        "ThreeMind · r" +
          imageRevision +
          " · " +
          timeLabel(latest.meta.time_us) +
          " · 节点 " +
          latest.meta.shown_nodes +
          "/" +
          latest.meta.total_nodes +
          " · 连接 " +
          latest.meta.shown_edges +
          "/" +
          latest.meta.total_edges,
        latest.meta.coordinates === "causal"
          ? "已记录因果坐标的观察投影；画面不是完整模型导出。"
          : "布局与标签仅供观察；画面不是完整模型导出。",
      ];
      const wrapped: string[] = [];
      for (const line of footer) {
        let part = "";
        for (const character of line) {
          if (
            part &&
            ctx.measureText(part + character).width > element.clientWidth - 24
          ) {
            wrapped.push(part);
            part = "";
          }
          part += character;
        }
        if (part) wrapped.push(part);
      }
      canvas.height =
        renderer.domElement.height +
        Math.ceil((16 + 18 * wrapped.length) * ratio);
      ctx.fillStyle = "#081b1d";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(renderer.domElement, 0, 0);
      ctx.drawImage(labelCanvas, 0, 0);
      ctx.scale(ratio, ratio);
      ctx.fillStyle = "#e2efdc";
      ctx.font = "12px system-ui";
      wrapped.forEach((line, i) =>
        ctx.fillText(line, 12, element.clientHeight + 20 + i * 18),
      );
      canvas.toBlob((blob) => {
        if (!blob) return;
        const url = URL.createObjectURL(blob),
          link = document.createElement("a");
        link.href = url;
        link.download =
          "threemind-" + runRef.current + "-r" + imageRevision + ".png";
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }, "image/png");
    };
    const observer = new ResizeObserver(resize);
    observer.observe(element);
    resize();
    let pointerStart = [0, 0];
    const down = (e: PointerEvent) => {
      pointerStart = [e.clientX, e.clientY];
    };
    const click = (e: PointerEvent) => {
      if (
        !latest ||
        Math.hypot(e.clientX - pointerStart[0], e.clientY - pointerStart[1]) > 5
      )
        return;
      const rect = renderer.domElement.getBoundingClientRect();
      const pointer = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        (-(e.clientY - rect.top) / rect.height) * 2 + 1,
      );
      const raycaster = new THREE.Raycaster();
      nodeGeometry.computeBoundingSphere();
      solid?.computeBoundingSphere();
      raycaster.params.Points!.threshold = 5;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObject(
        points.visible ? points : solid!,
        false,
      )[0];
      const index = hit?.instanceId ?? hit?.index;
      if (index != null && latest.ids[index] != null)
        selectedRef.current?.(latest.ids[index]);
    };
    renderer.domElement.addEventListener("pointerdown", down);
    renderer.domElement.addEventListener("pointerup", click);
    const animate = (now: number) => {
      const p = settingsRef.current;
      if (p.mode !== lastMode) {
        lastMode = p.mode;
        const target = controls.target.clone();
        controls.dispose();
        camera = p.mode === "3d" ? perspective : orthographic;
        controls = new OrbitControls(camera, renderer.domElement);
        controls.enableRotate = p.mode === "3d";
        controls.target.copy(target);
        controls.addEventListener("change", change);
        controls.addEventListener("start", userView);
        if (autoFit) fitView();
        else controls.update();
        pointMaterial.uniforms.perspectiveMode.value = p.mode === "3d" ? 1 : 0;
        dirty = true;
      }
      if (p.dpr !== lastDpr) {
        lastDpr = p.dpr;
        renderer.setPixelRatio(Math.min(devicePixelRatio || 1, p.dpr));
        pointMaterial.uniforms.ratio.value = renderer.getPixelRatio();
        resize();
      }
      if (
        latest &&
        (p.shape !== lastShape ||
          p.nodeScale !== lastScale ||
          p.visualStyle !== lastStyle)
      ) {
        lastScale = p.nodeScale;
        lastStyle = p.visualStyle;
        pointMaterial.uniforms.nodeScale.value = p.nodeScale;
        pointMaterial.blending =
          p.visualStyle === "organic"
            ? THREE.AdditiveBlending
            : THREE.NormalBlending;
        upload(latest);
      }
      if (p.edgeOpacity !== lastOpacity || p.labelFont !== lastFont) {
        lastOpacity = p.edgeOpacity;
        lastFont = p.labelFont;
        lineMaterial.opacity = p.edgeOpacity;
        dirty = true;
      }
      if (dirty && !document.hidden && now - lastDraw >= 1000 / p.fps) {
        const started = performance.now();
        renderer.render(scene, camera);
        drawLabels();
        draws++;
        drawMs = performance.now() - started;
        lastDraw = now;
        dirty = false;
      }
      if (p.showGraphStats && now - lastStatsAt >= 1000) {
        const arrays = [
          ...Object.values(nodeGeometry.attributes),
          ...Object.values(edgeGeometry.attributes),
        ];
        setStats({
          fps: (draws * 1000) / Math.max(1, now - lastStatsAt),
          upload_ms: uploadMs,
          draw_ms: drawMs,
          bytes:
            arrays.reduce((sum, a) => sum + a.array.byteLength, 0) +
            (solid?.instanceMatrix.array.byteLength ?? 0) +
            (solid?.instanceColor?.array.byteLength ?? 0),
          geometries: renderer.info.memory.geometries,
          allocations,
          labels: labelsDrawn,
          ...latest?.diagnostics,
        });
        draws = 0;
        lastStatsAt = now;
      } else if (!p.showGraphStats) {
        draws = 0;
        lastStatsAt = now;
      }
      raf = requestAnimationFrame(animate);
    };
    raf = requestAnimationFrame(animate);
    const contextLost = (event: Event) => {
      event.preventDefault();
      renderReady.current = false;
      capture.current = { draw: () => { throw new Error("Canvas is not ready"); }, metadata: () => ({}) };
      setCanvasFallback(true);
    };
    const contextRestored = () => {
      renderReady.current = true;
      setError("");
      if (latest) upload(latest);
      dirty = true;
    };
    renderer.domElement.addEventListener("webglcontextlost", contextLost);
    renderer.domElement.addEventListener(
      "webglcontextrestored",
      contextRestored,
    );
    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
      controls.dispose();
      receiver.current = () => {};
      exportImage.current = () => {};
      renderReady.current = false;
      renderer.domElement.removeEventListener("pointerdown", down);
      renderer.domElement.removeEventListener("pointerup", click);
      renderer.domElement.removeEventListener("webglcontextlost", contextLost);
      renderer.domElement.removeEventListener(
        "webglcontextrestored",
        contextRestored,
      );
      solid?.dispose();
      sphereGeometry.dispose();
      cubeGeometry.dispose();
      solidMaterial.dispose();
      nodeGeometry.dispose();
      edgeGeometry.dispose();
      pointMaterial.dispose();
      lineMaterial.dispose();
      renderer.dispose();
      renderer.domElement.remove();
      labelCanvas.remove();
    };
  }, [canvasFallback]);
  useEffect(() => {
    const worker = new Worker(new URL("./graph.worker.ts", import.meta.url), {
      type: "module",
    });
    worker.onmessage = (e) => {
      if (e.data.type === "graph") {
        receiver.current(e.data);
        if (e.data.snapshot) setMeta(e.data.meta);
        if (renderReady.current) setError("");
        worker.postMessage({ type: "ack" });
      } else setError(e.data.message);
    };
    worker.postMessage({
      url: endpoint ?? `/api/v2/projects/${project}/runs/${run}/graph`,
      nodes: settings.nodes,
      edges: settings.edges,
      pollMs: polling ? settings.pollMs : 0,
      mode: canvasFallback ? "2d" : settings.mode,
      continuousMotion: settings.continuousMotion,
      layoutFps: settings.layoutFps,
      graphLabels: settings.graphLabels,
      maxLabels: settings.maxLabels,
      hidden: document.hidden,
    });
    const visibility = () =>
      worker.postMessage({ type: "visibility", hidden: document.hidden });
    document.addEventListener("visibilitychange", visibility);
    return () => {
      document.removeEventListener("visibilitychange", visibility);
      worker.postMessage({ type: "stop" });
      worker.terminate();
    };
  }, [
    project,
    canvasFallback,
    run,
    endpoint,
    settings.nodes,
    settings.edges,
    settings.pollMs,
    settings.mode,
    settings.continuousMotion,
    settings.layoutFps,
    settings.graphLabels,
    settings.maxLabels,
    polling,
    polling ? null : revision,
  ]);
  return (
    <div className="graph-export-view">
    <div className="graph-panel">
      <div className="graph-toolbar">
        <div className="segment">
          <button
            className={
              canvasFallback || settings.mode === "2d" ? "selected" : ""
            }
            onClick={() => updatePreferences({ mode: "2d" })}
          >
            2D
          </button>
          <button
            className={
              !canvasFallback && settings.mode === "3d" ? "selected" : ""
            }
            disabled={canvasFallback}
            onClick={() => updatePreferences({ mode: "3d" })}
          >
            3D
          </button>
        </div>
        <select
          aria-label={t("节点形状")}
          value={settings.shape}
          onChange={(e) => updatePreferences({ shape: e.target.value as any })}
        >
          <option value="glow">{t("光点")}</option>
          <option value="circle">{t("圆点")}</option>
          <option value="square">{t("方点")}</option>
          <option value="sphere">{t("球体")}</option>
          <option value="cube">{t("立方体")}</option>
        </select>
        <select
          aria-label={t("图形风格")}
          value={settings.visualStyle}
          onChange={(e) =>
            updatePreferences({ visualStyle: e.target.value as any })
          }
        >
          <option value="organic">{t("柔和风格")}</option>
          <option value="minimal">{t("简洁风格")}</option>
        </select>
        <select
          aria-label={t("图中标签")}
          value={settings.graphLabels}
          onChange={(e) =>
            updatePreferences({ graphLabels: e.target.value as any })
          }
        >
          <option value="none">{t("无标签")}</option>
          <option value="ids">{t("匿名编号")}</option>
          <option value="external">{t("外部字符注记")}</option>
        </select>
        <button
          className={
            "button small " + (settings.continuousMotion ? "selected" : "")
          }
          aria-pressed={settings.continuousMotion}
          disabled={meta?.coordinates === "causal"}
          onClick={() =>
            updatePreferences({ continuousMotion: !settings.continuousMotion })
          }
        >
          {meta?.coordinates === "causal"
            ? t("因果坐标固定")
            : settings.continuousMotion
              ? t("暂停布局")
              : t("持续布局")}
        </button>
        <button
          className="icon-button"
          title={t("导出当前画面 PNG")}
          aria-label={t("导出当前画面 PNG")}
          disabled={!meta || !!error}
          onClick={() => exportImage.current()}
        >
          <Camera size={16} />
        </button>
        <button
          className="icon-button"
          title={t("重置视角")}
          onClick={() => reset.current()}
        >
          <RotateCcw size={16} />
        </button>
        <button
          className="icon-button"
          title={t("全屏")}
          onClick={() => host.current?.parentElement?.parentElement?.requestFullscreen()}
        >
          <Maximize2 size={16} />
        </button>
        {canvasFallback && (
          <p className="graph-fallback-note" role="status">
            {t("当前使用 Canvas 2D 显示回退；只影响画面，不改变意识计算。")}{" "}
            <button
              className="text-link"
              onClick={() => setCanvasFallback(false)}
            >
              {t("重试 WebGL")}
            </button>
          </p>
        )}
      </div>
      <div ref={host} className="graph-canvas" />
      {settings.showGraphStats && stats && (
        <div className="graph-diagnostics" aria-label={t("图形性能诊断")}>
          <span>
            {stats.fps.toFixed(1)}
            {t(" FPS · 提交 ")}
            {stats.upload_ms.toFixed(2)}
            {t(" ms · 绘制 ")}
            {stats.draw_ms.toFixed(2)} ms
          </span>
          <span>
            {t("工作线程：准备 ")}
            {(stats.prepare_ms ?? 0).toFixed(2)}
            {t(" ms · 布局")} {(stats.layout_ms ?? 0).toFixed(2)} ms ·{" "}
            {stats.layout_steps ?? 0} {t("步")}
          </span>
          <span>
            {t("属性容量 ")}
            {(stats.bytes / 1048576).toFixed(2)}
            {t(" MiB · 几何")} {stats.geometries}
            {t(" · 分配 ")}
            {stats.allocations}
            {t(" · 标签 ")}
            {stats.labels}
          </span>
        </div>
      )}
      {error && (
        <div className="graph-message" role="alert">
          {error}
        </div>
      )}
      {!error && meta?.shown_nodes === 0 && (
        <div className="graph-message">
          <span>{t("等待第一束刺激")}</span>
          <small>{t("接入环境或发送输入后，网络会在这里形成。")}</small>
        </div>
      )}
      <div className="graph-footer">
        <span>
          <i className="legend-direct" />
          {t("直接触达 ")}
          <i className="legend-association" />
          {t("联想触达")}
        </span>
        <span>
          {meta
            ? t("{value0} 节点 · {value1} 连接 · r{value2}", {
                value0: String(numberLabel(meta.shown_nodes, 0)),
                value1: String(numberLabel(meta.shown_edges, 0)),
                value2: String(meta.revision),
              })
            : t("正在连接…")}
          {meta && !meta.complete ? t(" · 部分显示") : ""}
        </span>
      </div>
      {settings.graphLabels === "external" && (
        <p className="graph-annotation-note">
          {t("外部通道注记 · ")}
          {meta?.available_labels ?? 0}{" "}
          {t(
            "个候选标签，重叠项自动避让；同一通道可对应多个字符。原始刺激和完整标签在输入记录中。",
          )}
        </p>
      )}
    </div>
    <CapturePanel key={run} disabled={!meta || !!error} source={{
      draw: () => capture.current.draw(), metadata: () => capture.current.metadata(),
    }} />
    </div>
  );
}
