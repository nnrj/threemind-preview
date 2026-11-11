import { test, expect, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

async function subject(page: Page) {
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "网络显示验收 " + Date.now() },
    })
  ).json();
  const root = "/api/v2/projects/" + project.id;
  const source = await (
    await page.request.post(root + "/runs", {
      data: {
        name: "显示验证来源",
        spec: {
          environment: "replay",
          clock: "unbounded",
          duration_s: 0.03,
          text_sensor: { encoding: "literal-character", frame_characters: 2 },
          replay: [
            {
              time_us: "0",
              channels: [
                [1, 0.8],
                [2, 0.5],
              ],
            },
          ],
        },
      },
    })
  ).json();
  await expect
    .poll(
      async () =>
        (await (await page.request.get(root + "/runs/" + source.id)).json())
          .status,
    )
    .toBe("completed");
  const run = await (
    await page.request.post(root + "/runs/" + source.id + "/forks", {
      data: { name: "显示验证暂停沙箱", paused: true },
    })
  ).json();
  const url = root + "/runs/" + run.id;
  await expect
    .poll(async () => (await (await page.request.get(url)).json()).status)
    .toBe("paused");
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  return { project, run, url };
}

test("external labels, independent controls, PNG and responsive settings", async ({
  page,
}, info) => {
  await page.addInitScript(() => {
    if (!localStorage.getItem("tm2.preferences"))
      localStorage.setItem(
        "tm2.preferences",
        JSON.stringify({ showGraphStats: true }),
      );
  });
  const { run, url } = await subject(page);
  const input = await page.request.post(url + "/inputs", {
    data: {
      adapter_id: "text-sensor",
      request_id: crypto.randomUUID(),
      payload: { text: "A汉BA" },
      delay_us: 5000,
    },
  });
  expect(input.status()).toBe(202);
  const before = await (await page.request.get(url)).json();
  const step = await page.request.post(url + "/research/actions", {
    data: {
      kind: "runtime.advance",
      request_id: crypto.randomUUID(),
      expected_revision: before.revision,
      duration_us: 30000,
    },
  });
  expect(step.status()).toBe(200);
  await expect
    .poll(async () => (await (await page.request.get(url)).json()).revision)
    .toBeGreaterThan(before.revision);
  await expect
    .poll(async () => (await (await page.request.get(url)).json()).status)
    .toBe("completed");
  const state = await (await page.request.get(url)).json();
  await page.goto("/runs/" + run.id);
  await expect(page.locator(".graph-webgl-canvas")).toBeVisible();
  await page.locator(".graph-webgl-canvas").evaluate((canvas) => {
    (canvas as HTMLElement).dataset.localeWitness = "same-webgl-context";
  });
  await page.getByLabel("切换界面语言", { exact: true }).selectOption("en");
  await expect(page.locator(".graph-webgl-canvas")).toHaveAttribute(
    "data-locale-witness",
    "same-webgl-context",
  );
  await page
    .getByLabel("Switch interface language", { exact: true })
    .selectOption("zh-CN");
  await page.getByLabel("图中标签", { exact: true }).selectOption("external");
  await expect(page.locator(".graph-annotation-note")).toContainText(
    /[1-9]\d* 个候选/,
  );
  await page.getByLabel("图形风格", { exact: true }).selectOption("minimal");
  await page.getByRole("button", { name: "持续布局", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "暂停布局", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("图形性能诊断")).toContainText(/布局/);
  const pending = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "导出当前画面 PNG", exact: true })
    .click();
  const download = await pending,
    file = info.outputPath("network-export.png");
  await download.saveAs(file);
  expect((await readFile(file)).subarray(0, 8).toString("hex")).toBe(
    "89504e470d0a1a0a",
  );
  await page.screenshot({
    path: info.outputPath("network-display-desktop.png"),
    fullPage: true,
  });
  expect((await (await page.request.get(url)).json()).state_hash).toBe(
    state.state_hash,
  );
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("network-display-mobile.png"),
    fullPage: true,
  });
  await page.goto("/settings");
  await page.getByRole("button", { name: /^高性能/ }).click();
  await expect(page.locator(".effective-budget")).toContainText("300,000 连接");
  await page.reload();
  await expect(page.locator(".preset-card.selected")).toContainText("高性能");
  await expect(page.getByLabel("图形风格", { exact: true })).toHaveValue(
    "minimal",
  );
});

test("GPU buffers stay bounded through repeated display growth and shrink", async ({
  page,
  context,
}, info) => {
  await page.addInitScript(() => {
    localStorage.setItem(
      "tm2.preferences",
      JSON.stringify({
        preset: "custom",
        nodes: 10000,
        edges: 40000,
        pollMs: 100,
        dpr: 0.5,
        showGraphStats: true,
      }),
    );
    const live = new Set<WebGLBuffer>();
    const probe = { created: 0, deleted: 0, peak: 0, live: () => live.size };
    (window as any).__graphBuffers = probe;
    const originalCreate = WebGL2RenderingContext.prototype.createBuffer,
      originalDelete = WebGL2RenderingContext.prototype.deleteBuffer;
    WebGL2RenderingContext.prototype.createBuffer = function () {
      const buffer = originalCreate.call(this);
      if (buffer) {
        live.add(buffer);
        probe.created++;
        probe.peak = Math.max(probe.peak, live.size);
      }
      return buffer;
    };
    WebGL2RenderingContext.prototype.deleteBuffer = function (buffer) {
      if (buffer && live.delete(buffer)) probe.deleted++;
      originalDelete.call(this, buffer);
    };
  });
  const { run, url } = await subject(page),
    frozen = await (await page.request.get(url)).json();
  // Only the browser observation response is synthetic. The database run stays paused.
  await context.route("**" + url, (route) =>
    route.fulfill({ json: { ...frozen, status: "running" } }),
  );
  let revision = 1000,
    count = 60;
  await context.route("**" + url + "/graph?**", (route) => {
    const query = new URL(route.request().url()).searchParams;
    if (Number(query.get("since")) === revision)
      return route.fulfill({ status: 304 });
    return route.fulfill({
      json: {
        revision,
        time_us: "0",
        total_nodes: count,
        total_edges: count * 4,
        complete: true,
        nodes: Array.from({ length: count }, (_, i) => ({
          id: i + 1,
          activation: 0.5,
          direct: 0.2,
        })),
        edges: Array.from({ length: count * 4 }, (_, i) => ({
          source: (i % count) + 1,
          target: ((i * 13 + 17) % count) + 1,
          weight: 0.4,
        })),
      },
    });
  });
  await page.goto("/runs/" + run.id);
  await expect(page.locator(".graph-footer")).toContainText("60 节点");
  await expect
    .poll(() => page.evaluate(() => (window as any).__graphBuffers.live()))
    .toBeGreaterThan(0);
  const baseline = await page.evaluate(() =>
      (window as any).__graphBuffers.live(),
    ),
    cycles: any[] = [];
  for (let i = 0; i < 5; i++) {
    count = 10000;
    revision++;
    await expect(page.locator(".graph-footer")).toContainText("10,000 节点");
    count = 60;
    revision++;
    await expect(page.locator(".graph-footer")).toContainText("60 节点");
    await expect
      .poll(() => page.evaluate(() => (window as any).__graphBuffers.live()))
      .toBeLessThanOrEqual(baseline + 2);
    cycles.push(
      await page.evaluate(() => {
        const p = (window as any).__graphBuffers;
        return {
          created: p.created,
          deleted: p.deleted,
          live: p.live(),
          peak: p.peak,
        };
      }),
    );
  }
  expect(cycles[4].deleted).toBeGreaterThan(30);
  console.log(
    JSON.stringify({
      schema: "threemind.gpu-buffer-validation/1",
      baseline,
      cycles,
    }),
  );
  await page.goto("/settings");
  await expect
    .poll(() => page.evaluate(() => (window as any).__graphBuffers.live()))
    .toBe(0);
  await info.attach("gpu-buffer-validation.json", {
    body: JSON.stringify(
      {
        baseline,
        cycles,
        after_unmount: 0,
        fixture:
          "Repeated 60/10000 nodes and 240/40000 edges in browser observation only; WebGL API buffers, not total driver VRAM.",
      },
      null,
      2,
    ),
    contentType: "application/json",
  });
});
