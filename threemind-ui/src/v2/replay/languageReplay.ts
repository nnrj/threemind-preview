/** Evidence-only replay. No Core/API commands, inference, or invented sample interpolation. */
export type ReplayNode = [number, number, number, number]; // id, activation, inhibition, association
export type ReplayFrame = { t: number; nodes: ReplayNode[] };
export type ReplayEvent = {
  at: number;
  role: string;
  label: string;
  text: string;
  item?: number;
  repeat?: number;
  measurement?: { rays: { distance_m: number; rgb: number[] }[] };
};
export type ReplayObject = {
  name: string;
  shape: string;
  color: string;
  position: number[];
};
export type ReplayClip = {
  id: string;
  title: string;
  subtitle: string;
  caption: string;
  duration: number;
  kind: string;
  source: string;
  from: number;
  to: number;
  motionSeconds?: number;
  item?: number;
  output?: string;
  expected?: string;
  sampling?: string;
  intervention?: string;
  frames: ReplayFrame[];
  nodes: Record<string, number>;
  edges: { t: number; total: number; rows: number[][] }[];
  events: ReplayEvent[];
  objects: ReplayObject[];
  evidence: string[];
  stats?: { value: string; label: string }[];
};
export type LanguageReplayData = {
  schema: string;
  title: string;
  description: string;
  clips: ReplayClip[];
  provenance: Record<string, unknown>;
  created_on: string;
  width: number;
  height: number;
};

export function parseLanguageReplay(value: unknown): LanguageReplayData {
  const d = value as LanguageReplayData;
  if (
    !d ||
    d.schema !== "threemind.language-replay/1" ||
    !Array.isArray(d.clips) ||
    !d.clips.length ||
    d.clips.length > 100
  )
    throw new Error("Unsupported or empty language replay");
  let duration = 0,
    samples = 0;
  const str = (v: unknown, n = 3000) => typeof v === "string" && v.length <= n;
  const num = (v: unknown) => typeof v === "number" && Number.isFinite(v);
  if (!str(d.title, 200) || !str(d.description) || !d.provenance)
    throw new Error("Invalid replay metadata");
  for (const c of d.clips) {
    if (
      ![c.id, c.title, c.subtitle, c.caption, c.source].every((s) => str(s)) ||
      !num(c.duration) ||
      c.duration <= 0 ||
      c.duration > 300 ||
      !num(c.from) ||
      !num(c.to) ||
      c.to < c.from ||
      !Array.isArray(c.frames) ||
      !Array.isArray(c.events) ||
      !c.nodes ||
      !Array.isArray(c.edges) ||
      !Array.isArray(c.objects) ||
      c.objects.length > 20 ||
      !Array.isArray(c.evidence) ||
      (c.motionSeconds !== undefined &&
        (!num(c.motionSeconds) ||
          c.motionSeconds <= 0 ||
          c.motionSeconds > c.duration))
    )
      throw new Error("Invalid replay clip");
    duration += c.duration;
    samples += c.frames.length;
    let last = -Infinity;
    for (const f of c.frames) {
      if (
        !num(f.t) ||
        f.t < c.from ||
        f.t > c.to ||
        f.t <= last ||
        !Array.isArray(f.nodes) ||
        f.nodes.length > 2048
      )
        throw new Error("Invalid or unordered recorded frame");
      last = f.t;
      for (const n of f.nodes)
        if (
          n.length !== 4 ||
          !n.every(num) ||
          !Number.isSafeInteger(n[0]) ||
          !num(c.nodes[String(n[0])])
        )
          throw new Error("Invalid recorded node");
    }
    for (const e of c.events)
      if (
        !num(e.at) ||
        e.at < 0 ||
        e.at > c.duration ||
        !str(e.role, 40) ||
        !str(e.label, 160) ||
        !str(e.text) ||
        (e.item !== undefined &&
          (!Number.isInteger(e.item) ||
            e.item < 0 ||
            e.item >= c.objects.length)) ||
        (e.measurement !== undefined &&
          (!Array.isArray(e.measurement.rays) ||
            e.measurement.rays.length > 64 ||
            e.measurement.rays.some(
              (r) =>
                !num(r.distance_m) ||
                !Array.isArray(r.rgb) ||
                r.rgb.length !== 3 ||
                !r.rgb.every(num),
            )))
      )
        throw new Error("Invalid replay event");
    if (
      c.stats &&
      (!Array.isArray(c.stats) ||
        c.stats.length > 6 ||
        c.stats.some((s) => !str(s.value, 100) || !str(s.label, 300)))
    )
      throw new Error("Invalid replay statistics");
    if (c.evidence.some((s) => !str(s, 1000)))
      throw new Error("Invalid source reference");
    if (
      c.events.length > 5000 ||
      c.edges.length > 5000 ||
      Object.keys(c.nodes).length > 2048
    )
      throw new Error("Replay detail budget");
    for (const e of c.edges)
      if (
        !num(e.t) ||
        !num(e.total) ||
        !Array.isArray(e.rows) ||
        e.rows.length > 300 ||
        e.rows.some((r) => r.length !== 3 || !r.every(num))
      )
        throw new Error("Invalid edge sample");
    for (const o of c.objects)
      if (
        !str(o.name, 100) ||
        !str(o.shape, 30) ||
        !/^#[0-9a-fA-F]{6}$/.test(o.color) ||
        !Array.isArray(o.position) ||
        o.position.length !== 2 ||
        !o.position.every(num)
      )
        throw new Error("Invalid scene object");
  }
  if (duration > 900 || samples > 10000)
    throw new Error("Replay exceeds 15 minutes or 10000 samples");
  return d;
}

export function replayDuration(d: LanguageReplayData) {
  return d.clips.reduce((s, c) => s + c.duration, 0);
}
export function clipAt(d: LanguageReplayData, at: number) {
  let start = 0;
  for (let index = 0; index < d.clips.length; index++) {
    const clip = d.clips[index];
    if (at < start + clip.duration || index === d.clips.length - 1)
      return {
        clip,
        index,
        start,
        offset: Math.max(0, Math.min(clip.duration, at - start)),
      };
    start += clip.duration;
  }
  throw new Error("Empty replay");
}
export function heldSample<T extends { t: number }>(
  frames: T[],
  at: number,
): T | undefined {
  let lo = 0,
    hi = frames.length;
  while (lo < hi) {
    const m = (lo + hi) >> 1;
    if (frames[m].t <= at) lo = m + 1;
    else hi = m;
  }
  return lo ? frames[lo - 1] : undefined;
}

const C = {
  bg: "#eef4f1",
  ink: "#173d37",
  muted: "#62796f",
  teal: "#137e6b",
  gold: "#c78b37",
  line: "#d8e5de",
  paper: "#ffffff",
};
const FONT = '"Microsoft YaHei", "Noto Sans CJK SC", sans-serif';
function text(
  ctx: CanvasRenderingContext2D,
  s: string,
  x: number,
  y: number,
  size = 25,
  color = C.ink,
  bold = false,
) {
  ctx.font = `${bold ? 700 : 400} ${size}px ${FONT}`;
  ctx.fillStyle = color;
  ctx.textBaseline = "top";
  ctx.fillText(s, x, y);
}
function wrap(
  ctx: CanvasRenderingContext2D,
  s: string,
  x: number,
  y: number,
  w: number,
  size = 25,
  color = C.ink,
  line = 38,
) {
  ctx.font = `400 ${size}px ${FONT}`;
  let yy = y;
  for (const paragraph of s.split("\n")) {
    let row = "";
    for (const ch of paragraph) {
      if (ctx.measureText(row + ch).width > w && row) {
        text(ctx, row, x, yy, size, color);
        yy += line;
        row = "";
      }
      row += ch;
    }
    text(ctx, row, x, yy, size, color);
    yy += line;
  }
  return yy;
}
function box(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  fill = C.paper,
  r = 20,
) {
  ctx.fillStyle = fill;
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  ctx.fill();
}
function mix(color: string, amount: number) {
  const v = Math.max(0, Math.min(1, amount)),
    raw = parseInt(color.slice(1), 16);
  return `rgb(${[raw >> 16, (raw >> 8) & 255, raw & 255].map((n) => Math.round(n + (255 - n) * v)).join(",")})`;
}

/** Canvas scene used unchanged by React previews, screenshots, and deterministic MP4 export. */
export class LanguageReplayRenderer {
  readonly canvas = document.createElement("canvas");
  private positions = new Map<string, [number, number]>();
  private curves = new Map<ReplayClip, { sums: number[]; max: number }>();
  readonly duration: number;
  constructor(readonly data: LanguageReplayData) {
    this.canvas.width = 1920;
    this.canvas.height = 1080;
    this.duration = replayDuration(data);
    for (const c of data.clips) {
      const sums = c.frames.map((r) => r.nodes.reduce((s, n) => s + n[1], 0));
      this.curves.set(c, { sums, max: Math.max(0.001, ...sums) });
    }
  }
  private position(channel: number): [number, number] {
    const key = String(channel);
    let p = this.positions.get(key);
    if (!p) {
      // An anonymous, fixed display layout; no anatomical or semantic region claim.
      const a =
        ((Math.imul(channel, 2654435761) >>> 0) / 2 ** 32) * Math.PI * 2;
      const radius =
        40 +
        185 *
          Math.sqrt(
            (Math.imul(channel ^ 0x9e3779b9, 2246822519) >>> 0) / 2 ** 32,
          );
      p = [942 + Math.cos(a) * radius, 454 + Math.sin(a) * radius * 0.62];
      this.positions.set(key, p);
    }
    return p;
  }
  render(at: number) {
    const ctx = this.canvas.getContext("2d")!;
    const { clip: c, index, offset } = clipAt(this.data, at);
    const sim =
      c.from +
      (c.to - c.from) * Math.min(1, offset / (c.motionSeconds ?? c.duration));
    const frame = heldSample(c.frames, sim),
      edges = heldSample(c.edges, sim);
    const events = c.events.filter((e) => e.at <= offset),
      active = [...events].reverse().find((e) => e.item !== undefined);
    const item = active?.item ?? c.item;
    ctx.clearRect(0, 0, 1920, 1080);
    ctx.fillStyle = C.bg;
    ctx.fillRect(0, 0, 1920, 1080);
    box(ctx, 0, 0, 1920, 14, C.teal, 0);
    text(ctx, "THREEMIND  /  TEACHING & EXPRESSION", 48, 38, 21, C.muted, true);
    text(
      ctx,
      c.kind === "card" ? "证据导览" : "已记录的实验回放",
      1600,
      38,
      23,
      C.teal,
      true,
    );
    text(ctx, c.title, 48, 82, 45, C.ink, true);
    text(ctx, c.subtitle, 48, 146, 25, C.muted);
    if (c.kind === "card") this.card(ctx, c, offset);
    else {
      this.world(ctx, c, item, active);
      this.activity(ctx, c, frame, edges, sim);
      this.dialogue(ctx, c, events);
      this.timeline(ctx, c, frame, sim);
    }
    box(ctx, 48, 910, 1824, 116, "#173d37", 18);
    wrap(ctx, c.caption, 76, 932, 1766, 28, "#f2f7f2", 40);
    text(
      ctx,
      `${index + 1} / ${this.data.clips.length}   ·   ${c.source}`,
      48,
      1042,
      18,
      C.muted,
    );
    text(ctx, `${clock(at)} / ${clock(this.duration)}`, 1690, 1040, 21, C.ink);
    ctx.fillStyle = C.line;
    ctx.fillRect(48, 1030, 1824, 4);
    ctx.fillStyle = C.teal;
    ctx.fillRect(48, 1030, 1824 * Math.min(1, at / this.duration), 4);
    return this.canvas;
  }
  private card(ctx: CanvasRenderingContext2D, c: ReplayClip, _at: number) {
    box(ctx, 48, 205, 1824, 665);
    text(ctx, "从真实记录，看已经发生了什么", 95, 244, 27, C.teal, true);
    const items = c.stats ?? [],
      w = 1640 / Math.max(1, items.length);
    items.forEach((s, i) => {
      const x = 100 + i * w;
      box(ctx, x, 326, w - 30, 206, "#f0f6f2");
      text(ctx, s.value, x + 30, 367, 51, C.teal, true);
      wrap(ctx, s.label, x + 30, 451, w - 88, 27, C.muted, 38);
    });
    text(ctx, "教学与测试可追溯", 102, 596, 32, C.ink, true);
    wrap(
      ctx,
      "教师原话、实际回答、模拟时间与活动采样同步显示。\n场景按原定义示意重建；匿名节点的位置只服务于阅读。",
      102,
      658,
      1600,
      28,
      C.muted,
      48,
    );
    text(
      ctx,
      "原始数据保留  ·  不重新推理答案  ·  回放不推进意识",
      102,
      794,
      25,
      C.teal,
    );
  }
  private world(
    ctx: CanvasRenderingContext2D,
    c: ReplayClip,
    item: number | undefined,
    event: ReplayEvent | undefined,
  ) {
    box(ctx, 48, 205, 548, 501);
    text(ctx, "01  教学场景", 76, 229, 28, C.ink, true);
    text(ctx, "示意重建 · 原感官为五条射线", 76, 271, 21, C.muted);
    const scene = (x: number, y: number): [number, number] => [
      322 + (x - y) * 134,
      452 + (x + y) * 61,
    ];
    ctx.fillStyle = "#e5eeea";
    ctx.beginPath();
    [
      [-1, -1],
      [1, -1],
      [1, 1],
      [-1, 1],
    ].forEach(([x, y], i) => {
      const p = scene(x, y);
      if (i) ctx.lineTo(...p);
      else ctx.moveTo(...p);
    });
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = "#d1dfd7";
    ctx.lineWidth = 1;
    for (let k = -1; k <= 1; k += 0.25) {
      ctx.beginPath();
      ctx.moveTo(...scene(k, -1));
      ctx.lineTo(...scene(k, 1));
      ctx.moveTo(...scene(-1, k));
      ctx.lineTo(...scene(1, k));
      ctx.stroke();
    }
    [...c.objects.entries()]
      .sort(
        (a, b) =>
          a[1].position[0] +
          a[1].position[1] -
          b[1].position[0] -
          b[1].position[1],
      )
      .forEach(([i, o]) => {
        const [x, y] = scene(o.position[0], o.position[1]);
        ctx.fillStyle = "#1b3e3522";
        ctx.beginPath();
        ctx.ellipse(x, y + 5, 44, 16, 0, 0, Math.PI * 2);
        ctx.fill();
        if (i === item) {
          ctx.strokeStyle = C.teal;
          ctx.lineWidth = 4;
          ctx.beginPath();
          ctx.ellipse(x, y + 4, 58, 26, 0, 0, Math.PI * 2);
          ctx.stroke();
        }
        if (o.shape === "sphere") {
          const g = ctx.createRadialGradient(x - 14, y - 41, 3, x, y - 26, 37);
          g.addColorStop(0, mix(o.color, 0.55));
          g.addColorStop(0.55, o.color);
          g.addColorStop(1, mix(o.color, 0));
          ctx.fillStyle = g;
          ctx.beginPath();
          ctx.arc(x, y - 30, 35, 0, Math.PI * 2);
          ctx.fill();
        } else if (o.shape === "cylinder") {
          ctx.fillStyle = o.color;
          ctx.fillRect(x - 28, y - 68, 56, 67);
          ctx.beginPath();
          ctx.ellipse(x, y - 1, 28, 13, 0, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = mix(o.color, 0.45);
          ctx.beginPath();
          ctx.ellipse(x, y - 68, 28, 13, 0, 0, Math.PI * 2);
          ctx.fill();
        } else {
          const h = o.shape === "block" ? 38 : 59;
          ctx.fillStyle = o.color;
          ctx.beginPath();
          ctx.moveTo(x - 37, y - 17);
          ctx.lineTo(x, y);
          ctx.lineTo(x, y - h);
          ctx.lineTo(x - 37, y - h - 17);
          ctx.closePath();
          ctx.fill();
          ctx.fillStyle = mix(o.color, 0.18);
          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(x + 37, y - 17);
          ctx.lineTo(x + 37, y - h - 17);
          ctx.lineTo(x, y - h);
          ctx.closePath();
          ctx.fill();
          ctx.fillStyle = mix(o.color, 0.5);
          ctx.beginPath();
          ctx.moveTo(x - 37, y - h - 17);
          ctx.lineTo(x, y - h - 34);
          ctx.lineTo(x + 37, y - h - 17);
          ctx.lineTo(x, y - h);
          ctx.closePath();
          ctx.fill();
        }
        ctx.font = `500 22px ${FONT}`;
        const w = ctx.measureText(o.name).width;
        text(
          ctx,
          o.name,
          x - w / 2,
          y + 31,
          22,
          i === item ? C.teal : C.muted,
          i === item,
        );
      });
    const rays = event?.measurement?.rays;
    if (rays?.length) {
      text(ctx, "原始射线测量 · 距离 / RGB", 76, 594, 20, C.muted);
      rays.slice(0, 5).forEach((r, i) => {
        ctx.fillStyle = `rgb(${r.rgb
          .slice(0, 3)
          .map((v) => Math.round(Math.max(0, Math.min(1, v)) * 255))
          .join(",")})`;
        ctx.fillRect(78 + i * 99, 629, 75, 12);
        text(ctx, `${r.distance_m.toFixed(3)}m`, 76 + i * 99, 650, 17, C.muted);
      });
    } else
      wrap(
        ctx,
        item !== undefined
          ? `当前观察：${c.objects[item]?.name ?? "物体"}\n场景标签只给观众看，不进入意识。`
          : "所有物体仍在场景中。",
        76,
        603,
        490,
        23,
        C.muted,
        33,
      );
  }
  private activity(
    ctx: CanvasRenderingContext2D,
    c: ReplayClip,
    f: ReplayFrame | undefined,
    e: ReplayClip["edges"][number] | undefined,
    sim: number,
  ) {
    box(ctx, 620, 205, 652, 501);
    text(
      ctx,
      sim >= c.to && c.motionSeconds
        ? "02  意识活动 · 窗口末帧"
        : "02  意识活动",
      648,
      229,
      28,
      C.ink,
      true,
    );
    text(
      ctx,
      `模拟 ${sim.toFixed(2)} s${f ? `  ·  记录 ${f.t.toFixed(2)} s` : "  ·  等待首个记录"}`,
      648,
      271,
      21,
      C.muted,
    );
    if (!f) return;
    const shown = new Set(f.nodes.map((n) => n[0]));
    ctx.lineWidth = 0.9;
    for (const [a, b, w] of e?.rows ?? []) {
      if (!shown.has(a) || !shown.has(b)) continue;
      const pa = this.position(c.nodes[String(a)]),
        pb = this.position(c.nodes[String(b)]);
      ctx.strokeStyle = `rgba(27,107,90,${0.035 + Math.min(1, w) * 0.11})`;
      ctx.beginPath();
      ctx.moveTo(...pa);
      ctx.lineTo(...pb);
      ctx.stroke();
    }
    for (const [id, a, inh, assoc] of f.nodes) {
      const [x, y] = this.position(c.nodes[String(id)]),
        v = Math.max(0, Math.min(1, a));
      if (v > 0.005) {
        ctx.fillStyle = `rgba(26,170,127,${Math.min(0.25, v)})`;
        ctx.beginPath();
        ctx.arc(x, y, 7 + v * 15, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.fillStyle =
        v > 0 ? mix("#098368", 0.75 * (1 - Math.sqrt(v))) : "#cbd8d1";
      ctx.beginPath();
      ctx.arc(x, y, 3 + Math.sqrt(v) * 5, 0, Math.PI * 2);
      ctx.fill();
      if (inh > 0.001) {
        ctx.strokeStyle = `rgba(190,123,39,${0.15 + Math.min(1, inh) * 0.6})`;
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        ctx.arc(x, y, 8 + Math.min(1, inh) * 5, 0, Math.PI * 2);
        ctx.stroke();
      }
      if (assoc > 0) {
        ctx.fillStyle = "#995dab";
        ctx.beginPath();
        ctx.arc(x + 7, y - 7, 2.4, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    text(ctx, "绿：激活  金圈：抑制  紫点：联想触达", 648, 625, 21, C.muted);
    text(
      ctx,
      e
        ? `连边绘图抽样 ${e.rows.length}/${e.total} · 布局非脑区`
        : "此段未记录连边 · 只显示真实节点活动",
      648,
      660,
      20,
      C.muted,
    );
  }
  private dialogue(
    ctx: CanvasRenderingContext2D,
    c: ReplayClip,
    events: ReplayEvent[],
  ) {
    box(ctx, 1296, 205, 576, 677);
    text(ctx, "03  教学与回答", 1324, 229, 28, C.ink, true);
    text(ctx, "按记录原文显示", 1324, 271, 21, C.muted);
    let y = 318;
    const shown = events.slice(-3);
    for (const e of shown) {
      const own = e.role === "answer",
        x = own ? 1364 : 1320,
        w = own ? 480 : 524;
      text(ctx, e.label, x + 12, y, 20, own ? C.teal : C.muted, true);
      y += 33;
      const height = 50 + Math.ceil(e.text.length / 18) * 35;
      box(ctx, x, y, w, height, own ? "#dceee6" : "#f0f4f1", 14);
      wrap(
        ctx,
        e.text || "（当时未输出）",
        x + 20,
        y + 21,
        w - 40,
        own ? 37 : 27,
        own ? C.teal : C.ink,
        39,
      );
      y += height + 24;
    }
    if (c.kind === "teaching") {
      const r = shown[shown.length - 1];
      text(
        ctx,
        `此句已出现 ${r?.repeat ?? 0} 次 / 16 次`,
        1328,
        788,
        25,
        C.teal,
        true,
      );
      text(ctx, "课程原文回放 · 此阶段不播放回答", 1328, 832, 20, C.muted);
    } else if (!events.some((e) => e.role === "answer")) {
      text(ctx, "正在观察记录中的活动……", 1328, 789, 25, C.teal);
      text(ctx, "窗口结束后展示本次真实解码结果", 1328, 831, 20, C.muted);
    } else if (c.expected) {
      const correct = c.output === c.expected;
      text(
        ctx,
        correct ? "与本轮教学对应一致" : "与本轮教学对应不同",
        1328,
        789,
        25,
        correct ? C.teal : "#a65844",
        true,
      );
      text(
        ctx,
        `教学所指：${c.expected}（外部评分，不是测试输入）`,
        1328,
        833,
        19,
        C.muted,
      );
    }
  }
  private timeline(
    ctx: CanvasRenderingContext2D,
    c: ReplayClip,
    f: ReplayFrame | undefined,
    sim: number,
  ) {
    box(ctx, 48, 730, 1224, 152);
    text(ctx, "记录节点的激活总量", 76, 752, 23, C.ink, true);
    text(
      ctx,
      c.kind === "teaching"
        ? `教学回放 ${(c.to - c.from) / c.duration > 1 ? "加速 " : ""}${((c.to - c.from) / c.duration).toFixed(1)}×`
        : "2模拟秒观察窗口 · 放慢4倍显示",
      830,
      752,
      22,
      C.teal,
    );
    if (!c.frames.length) return;
    const { sums, max } = this.curves.get(c)!,
      x = 79,
      y = 853,
      w = 900,
      h = 56;
    ctx.strokeStyle = C.line;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x + w, y);
    ctx.stroke();
    ctx.strokeStyle = C.teal;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    c.frames.forEach((r, i) => {
      if (r.t > sim) return;
      const xx = x + ((r.t - c.from) / Math.max(0.00001, c.to - c.from)) * w,
        yy = y - (sums[i] / max) * h;
      if (i) ctx.lineTo(xx, yy);
      else ctx.moveTo(xx, yy);
    });
    ctx.stroke();
    text(
      ctx,
      `激活总量 ${(f?.nodes.reduce((s, n) => s + n[1], 0) ?? 0).toFixed(3)}`,
      1007,
      795,
      21,
      C.ink,
    );
    text(ctx, `曲线范围 0—${max.toFixed(2)}`, 1007, 831, 19, C.muted);
  }
  view(target: HTMLCanvasElement, at: number, focus = "all") {
    const frame = this.render(at);
    if (focus === "all") {
      if (target.width !== 1920 || target.height !== 1080) {
        target.width = 1920;
        target.height = 1080;
      }
      target.getContext("2d")!.drawImage(frame, 0, 0);
      return;
    }
    target.width = 720;
    target.height = 1060;
    const ctx = target.getContext("2d")!;
    ctx.fillStyle = C.bg;
    ctx.fillRect(0, 0, 720, 1060);
    const { clip } = clipAt(this.data, at);
    wrap(ctx, clip.title, 24, 24, 672, 32, C.ink, 45);
    if (clip.kind === "card") {
      const stats = clip.stats ?? [],
        h = Math.min(175, 600 / Math.max(1, stats.length));
      stats.forEach((s, i) => {
        const y = 145 + i * h;
        box(ctx, 24, y, 672, h - 15);
        text(ctx, s.value, 48, y + 16, 42, C.teal, true);
        wrap(ctx, s.label, 48, y + 70, 624, 27, C.muted, 33);
      });
      if (stats.length * h < 460)
        wrap(
          ctx,
          "来自已完成实验的真实记录。\n答案按原文显示，不重新推理。",
          34,
          170 + stats.length * h,
          652,
          29,
          C.muted,
          45,
        );
    } else {
      const rect =
        focus === "world"
          ? [48, 205, 548, 501]
          : focus === "activity"
            ? [620, 205, 652, 501]
            : [1296, 205, 576, 677];
      const s = Math.min(696 / rect[2], 650 / rect[3]);
      ctx.drawImage(
        frame,
        ...(rect as [number, number, number, number]),
        (720 - rect[2] * s) / 2,
        143,
        rect[2] * s,
        rect[3] * s,
      );
    }
    box(ctx, 12, 826, 696, 218, "#173d37", 15);
    wrap(ctx, clip.caption, 32, 847, 656, 24, "#eff5f1", 36);
  }
}
export function clock(s: number) {
  return `${Math.floor(s / 60)}:${Math.floor(s % 60)
    .toString()
    .padStart(2, "0")}`;
}
