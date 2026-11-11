import type { Frame } from "./Graph";
import type { effectivePreferences } from "./preferences";

// Reuses the worker's display sample. This renderer never updates Core state.
export function canvasGraph(
  element: HTMLDivElement,
  settings: () => ReturnType<typeof effectivePreferences>,
  select: (id: string | number) => void,
  stats: (value: unknown) => void,
) {
  const canvas = document.createElement("canvas");
  canvas.className = "graph-webgl-canvas";
  canvas.style.touchAction = "none";
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas 2D unavailable");
  element.appendChild(canvas);
  let frame: Frame | null = null,
    width = 1,
    height = 1,
    ratio = 1;
  let center = [0, 0],
    zoom = 1,
    autoFit = true,
    dirty = true;
  let raf = 0,
    lastDraw = 0,
    lastStats = 0,
    draws = 0,
    drawMs = 0;
  let lastPreferences = "";
  const point = (x: number, y: number) => [
    width / 2 + (x - center[0]) * zoom,
    height / 2 + 24 - (y - center[1]) * zoom,
  ];
  const fit = () => {
    if (!frame?.positions.length) return;
    let x0 = Infinity,
      y0 = Infinity,
      x1 = -Infinity,
      y1 = -Infinity;
    for (let i = 0; i < frame.positions.length; i += 3) {
      x0 = Math.min(x0, frame.positions[i]);
      x1 = Math.max(x1, frame.positions[i]);
      y0 = Math.min(y0, frame.positions[i + 1]);
      y1 = Math.max(y1, frame.positions[i + 1]);
    }
    center = [(x0 + x1) / 2, (y0 + y1) / 2];
    zoom =
      Math.min(
        (width - 32) / Math.max(40, x1 - x0),
        Math.max(80, height - 160) / Math.max(40, y1 - y0),
      ) * 0.8;
    dirty = true;
  };
  const resize = () => {
    width = Math.max(1, element.clientWidth);
    height = Math.max(1, element.clientHeight);
    ratio = Math.min(devicePixelRatio || 1, settings().dpr);
    canvas.width = Math.ceil(width * ratio);
    canvas.height = Math.ceil(height * ratio);
    if (autoFit) fit();
    dirty = true;
  };
  const color = (values: Float32Array, offset: number) =>
    `rgb(${[0, 1, 2].map((k) => Math.round(Math.max(0, Math.min(1, values[offset + k] ?? 0)) * 255)).join(",")})`;
  const draw = () => {
    const start = performance.now(),
      p = settings();
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    if (!frame) return;
    ctx.lineWidth = 1;
    ctx.globalAlpha = p.edgeOpacity;
    for (let i = 0; i < frame.edgePositions.length; i += 6) {
      const a = point(frame.edgePositions[i], frame.edgePositions[i + 1]);
      const b = point(frame.edgePositions[i + 3], frame.edgePositions[i + 4]);
      ctx.strokeStyle = color(frame.edgeColors, i);
      ctx.beginPath();
      ctx.moveTo(a[0], a[1]);
      ctx.lineTo(b[0], b[1]);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    for (let i = 0; i < frame.ids.length; i++) {
      const at = point(frame.positions[i * 3], frame.positions[i * 3 + 1]);
      const radius = Math.max(0.5, (frame.sizes[i] * p.nodeScale) / 2);
      if (
        at[0] < -radius ||
        at[0] > width + radius ||
        at[1] < -radius ||
        at[1] > height + radius
      )
        continue;
      ctx.fillStyle = color(frame.colors, i * 3);
      if (p.shape === "square" || p.shape === "cube")
        ctx.fillRect(at[0] - radius, at[1] - radius, radius * 2, radius * 2);
      else {
        ctx.beginPath();
        ctx.arc(at[0], at[1], radius, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.font = `${p.labelFont}px system-ui`;
    ctx.fillStyle = "#a9c9ba";
    for (const label of frame.labels ?? []) {
      const at = point(
        frame.positions[label.index * 3],
        frame.positions[label.index * 3 + 1],
      );
      ctx.fillText(label.text, at[0] + 6, at[1] - 6);
    }
    drawMs = performance.now() - start;
    draws++;
    dirty = false;
  };
  const animate = (now: number) => {
    const p = settings(),
      signature = [
        p.dpr,
        p.shape,
        p.nodeScale,
        p.labelFont,
        p.edgeOpacity,
      ].join(":");
    if (lastPreferences !== signature) {
      lastPreferences = signature;
      resize();
    }
    if (dirty && !document.hidden && now - lastDraw >= 1000 / p.fps) {
      draw();
      lastDraw = now;
    }
    if (now - lastStats >= 1000) {
      if (p.showGraphStats)
        stats({
          fps: (draws * 1000) / Math.max(1, now - lastStats),
          upload_ms: 0,
          draw_ms: drawMs,
          bytes: frame
            ? [
                frame.positions,
                frame.colors,
                frame.sizes,
                frame.edgePositions,
                frame.edgeColors,
              ].reduce(
                (n, a) => n + a.byteLength,
                frame.ids instanceof Float64Array
                  ? frame.ids.byteLength
                  : frame.ids.reduce<number>(
                      (bytes, id) =>
                        bytes + (typeof id === "number" ? 8 : id.length * 2),
                      0,
                    ),
              )
            : 0,
          geometries: 0,
          allocations: 0,
          labels: frame?.labels.length ?? 0,
          ...frame?.diagnostics,
        });
      draws = 0;
      lastStats = now;
    }
    raf = requestAnimationFrame(animate);
  };
  let start: number[] | null = null,
    previous = [0, 0];
  const down = (e: PointerEvent) => {
    start = previous = [e.clientX, e.clientY];
    canvas.setPointerCapture(e.pointerId);
  };
  const move = (e: PointerEvent) => {
    if (!start) return;
    center[0] -= (e.clientX - previous[0]) / zoom;
    center[1] += (e.clientY - previous[1]) / zoom;
    previous = [e.clientX, e.clientY];
    autoFit = false;
    dirty = true;
  };
  const up = (e: PointerEvent) => {
    if (
      frame &&
      start &&
      Math.hypot(e.clientX - start[0], e.clientY - start[1]) < 5
    ) {
      const rect = canvas.getBoundingClientRect(),
        x = e.clientX - rect.left,
        y = e.clientY - rect.top;
      let distance = 12,
        found = -1;
      for (let i = 0; i < frame.ids.length; i++) {
        const at = point(frame.positions[i * 3], frame.positions[i * 3 + 1]),
          d = Math.hypot(at[0] - x, at[1] - y);
        if (d < distance) {
          distance = d;
          found = i;
        }
      }
      if (found >= 0) select(frame.ids[found]);
    }
    start = null;
  };
  const cancel = () => {
    start = null;
  };
  const wheel = (e: WheelEvent) => {
    e.preventDefault();
    zoom = Math.max(
      0.0001,
      Math.min(10000, zoom * Math.exp(-e.deltaY * 0.001)),
    );
    autoFit = false;
    dirty = true;
  };
  canvas.addEventListener("pointerdown", down);
  canvas.addEventListener("pointermove", move);
  canvas.addEventListener("pointerup", up);
  canvas.addEventListener("pointercancel", cancel);
  canvas.addEventListener("wheel", wheel, { passive: false });
  const observer = new ResizeObserver(resize);
  observer.observe(element);
  resize();
  raf = requestAnimationFrame(animate);
  return {
    receive(value: Frame) {
      frame = { ...frame, ...value };
      if (autoFit) fit();
      dirty = true;
    },
    reset() {
      autoFit = true;
      fit();
    },
    capture() {
      draw();
      return canvas;
    },
    metadata() {
      return frame?.meta;
    },
    exportImage(run: string) {
      draw();
      const image = document.createElement("canvas");
      image.width = canvas.width;
      image.height = canvas.height + Math.ceil(44 * ratio);
      const target = image.getContext("2d")!;
      target.fillStyle = "#081b1d";
      target.fillRect(0, 0, image.width, image.height);
      target.drawImage(canvas, 0, 0);
      target.scale(ratio, ratio);
      target.fillStyle = "#e2efdc";
      target.font = "12px system-ui";
      target.fillText(
        `Canvas 2D · ${run} · r${frame?.meta?.revision ?? "?"}`,
        8,
        height + 18,
        width - 16,
      );
      target.fillText(
        "Display sample / 显示采样；原始数据请另行导出",
        8,
        height + 36,
        width - 16,
      );
      image.toBlob((blob) => {
        if (!blob) return;
        const url = URL.createObjectURL(blob),
          link = document.createElement("a");
        link.href = url;
        link.download = `threemind-${run}-canvas.png`;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      });
    },
    dispose() {
      cancelAnimationFrame(raf);
      observer.disconnect();
      canvas.removeEventListener("wheel", wheel);
      canvas.removeEventListener("pointerdown", down);
      canvas.removeEventListener("pointermove", move);
      canvas.removeEventListener("pointerup", up);
      canvas.removeEventListener("pointercancel", cancel);
      canvas.remove();
      frame = null;
    },
  };
}
