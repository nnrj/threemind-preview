import { test, expect } from "@playwright/test";
import { cpus } from "node:os";
import { DisplayModel, type DisplayGraph } from "../src/v2/graphModel";

function graph(count: number, edgeCount = count * 4): DisplayGraph {
  return {
    revision: 2,
    time_us: "123456",
    total_nodes: count,
    total_edges: edgeCount,
    complete: true,
    nodes: Array.from({ length: count }, (_, i) => ({
      id: i + 1,
      activation: (i % 31) / 31,
      direct: 0.1,
    })),
    edges: Array.from({ length: edgeCount }, (_, i) => ({
      source: (i % count) + 1,
      target: ((i * 13 + 17) % count) + 1,
      weight: 0.4,
    })),
  };
}

test("display layout preserves causal positions and sources, remains finite, and bounds frame data", async () => {
  const source = graph(60),
    original = JSON.stringify(source),
    model = new DisplayModel();
  model.replace(source, "2d", true, "ids", 7);
  const initial = model.positions.slice();
  for (let step = 0; step < 1000; step++) model.step(1 / 30);
  expect(model.positions.every(Number.isFinite)).toBe(true);
  expect(
    model.positions.filter((_, i) => i % 3 === 2).every((x) => x === 0),
  ).toBe(true);
  expect(model.positions).not.toEqual(initial);
  expect(model.labels).toHaveLength(7);
  const live = model.positions.slice();
  model.replace(source, "2d", true, "ids", 7);
  expect(model.positions).toEqual(live);
  expect(JSON.stringify(source)).toBe(original);
  const moving = model.frame(false);
  expect(moving).not.toHaveProperty("ids");
  expect(moving).not.toHaveProperty("colors");
  expect(moving).not.toHaveProperty("meta");
  moving.positions.fill(0);
  expect(model.positions).toEqual(live);
  const causal = {
    ...source,
    coordinates: "causal",
    nodes: source.nodes.map((n, i) => ({
      ...n,
      position: [i / 60, -0.5, 0.2],
    })),
  };
  model.replace(causal, "3d", true);
  const fixed = model.positions.slice();
  expect(fixed[1]).toBe(-75);
  expect(fixed[2]).toBe(30);
  expect(model.step(100)).toBe(false);
  expect(model.positions).toEqual(fixed);
  expect(() =>
    model.replace({ ...source, coordinates: "causal" }, "3d", true),
  ).toThrow("因果坐标");
  expect(() =>
    model.replace({ ...source, nodes: [{ id: 2 ** 53 }] }, "3d", false),
  ).toThrow("精确整数");
  model.replace(graph(2, 0), "3d", true);
  expect(model.ids).toHaveLength(2);
  expect(model.edgeIndices).toHaveLength(0);
  expect(model.positions).toHaveLength(6);
});

test("bounded label selection matches stable full ranking, including ties and external eligibility", () => {
  const data = graph(3000, 0);
  data.annotations = {};
  data.nodes.forEach((node, i) => {
    node.activation = Math.floor(i / 7) / 430;
    if (i % 3 === 0) data.annotations![String(node.id)] = ["汉", "A"];
  });
  const model = new DisplayModel();
  for (const mode of ["ids", "external"])
    for (const maximum of [1, 7, 500]) {
      const expected = data.nodes
        .map((node, index) => ({ node, index }))
        .filter(
          ({ node }) => mode === "ids" || !!data.annotations![String(node.id)],
        )
        .sort(
          (a, b) => b.node.activation - a.node.activation || a.index - b.index,
        )
        .slice(0, maximum)
        .map(({ index }) => index);
      model.replace(data, "3d", false, mode, maximum);
      expect(model.labels.map((label) => label.index)).toEqual(expected);
    }
});

test("historical string node identities stay exact through display frames and edge lookup", () => {
  const ids = ["9007199254740993", "18446744073709551615", "text:circle"];
  const data: DisplayGraph = {
    nodes: ids.map((id, index) => ({
      id,
      activation: 0.5,
      position: [index / 3, 0.2, -0.1],
    })),
    edges: [
      { source: ids[0], target: ids[1], weight: 0.6 },
      { source: ids[1], target: ids[2], weight: 0.4 },
    ],
    coordinates: "causal",
  };
  const original = JSON.stringify(data),
    model = new DisplayModel();
  model.replace(data, "3d", false, "ids", 3);
  const copied = structuredClone(model.frame(true));
  expect(copied.ids).toEqual(ids);
  expect(Array.from(model.edgeIndices)).toEqual([0, 1, 1, 2]);
  expect(model.positions.every(Number.isFinite)).toBe(true);
  expect(model.positions[1]).toBe(30);
  expect(model.labels.map((label) => label.text)).toContain(
    "n9007199254740993",
  );
  expect(JSON.stringify(data)).toBe(original);
  // Existing numeric kernels retain their compact typed-array transfer path.
  model.replace(graph(3, 0), "3d", false);
  expect(model.ids).toBeInstanceOf(Float64Array);
});

test("historical observation aliases retain raw attributes and drive the existing direct and associative colors", () => {
  const data: DisplayGraph = {
    nodes: [
      {
        id: "9007199254740993",
        channel: "18446744073709551615",
        activation: 0.5,
        direct_touch: 0.4,
        direct: 0.4,
        associative_touch: 0.1,
        associative: 0.1,
      },
      {
        id: "historical:association",
        channel: 7,
        activation: 0.5,
        direct_touch: 0,
        direct: 0,
        associative_touch: 0.1,
        associative: 0.1,
      },
      { id: "historical:unmeasured", activation: 0.5 },
    ],
    edges: [],
  };
  const original = JSON.stringify(data),
    model = new DisplayModel(),
    gain = 0.3 + 0.7 * Math.sqrt(0.5);
  model.replace(data, "2d", false);
  const frame = model.frame(true);
  expect(frame.ids).toEqual(data.nodes.map((node) => node.id));
  for (const [index, tint] of [
    [0, [0.953, 0.741, 0.447]],
    [1, [0.486, 0.878, 0.827]],
    [2, [0.506, 0.62, 0.588]],
  ] as const)
    tint.forEach((value, axis) =>
      expect(frame.colors[index * 3 + axis]).toBeCloseTo(value * gain, 6),
    );
  expect(JSON.stringify(data)).toBe(original);
  expect(data.nodes[0].channel).toBe("18446744073709551615");
});

test("bounded display preparation and layout benchmark", async ({}, info) => {
  const measurements: any[] = [];
  for (const [nodes, edges] of [
    [10000, 40000],
    [100000, 300000],
  ]) {
    const model = new DisplayModel(),
      data = graph(nodes, edges);
    const prepare: number[] = [],
      layout: number[] = [],
      transfer: number[] = [];
    for (let iteration = 0; iteration < 8; iteration++) {
      model.replace(data, "3d", true, "ids", 80);
      const start = performance.now();
      model.step(1 / 30);
      const then = performance.now();
      const frame = model.frame(iteration === 0);
      if (iteration) {
        prepare.push(model.lastPrepareMs);
        layout.push(then - start);
        transfer.push(performance.now() - then);
      }
      expect(frame.positions).toHaveLength(nodes * 3);
      expect(frame.edgePositions).toHaveLength(edges * 6);
    }
    const median = (items: number[]) =>
      items.sort((a, b) => a - b)[Math.floor(items.length / 2)];
    measurements.push({
      nodes,
      edges,
      labels: 80,
      prepare_ms: median(prepare),
      layout_step_ms: median(layout),
      transfer_pack_ms: median(transfer),
    });
  }
  const result = {
    schema: "threemind.display-benchmark/1",
    at: new Date().toISOString(),
    node: process.version,
    cpu: cpus()[0]?.model,
    scope:
      "Synthetic graph; Node worker calculation only, excludes database, HTTP, main-thread upload and GPU drawing.",
    measurements,
  };
  await info.attach("display-benchmark.json", {
    body: JSON.stringify(result, null, 2),
    contentType: "application/json",
  });
  console.log(JSON.stringify(result));
});
