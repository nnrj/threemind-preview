import { test, expect } from "@playwright/test";
test.skip(!process.env.THREEMIND_E2E_URL, "Requires an isolated workstation.");

async function fixture(page: any) {
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "研究工具验收" },
    })
  ).json();
  await page.addInitScript(
    (id) => localStorage.setItem("tm2.project", id),
    project.id,
  );
  const root = `/api/v2/projects/${project.id}`;
  const run = await (
    await page.request.post(root + "/runs", {
      data: {
        name: "快照起点",
        spec: {
          environment: "replay",
          clock: "unbounded",
          duration_s: 0.2,
          sample_us: 10000,
          replay: [
            {
              time_us: "0",
              channels: [
                [1, 0.7],
                [2, 0.6],
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
        (await (await page.request.get(root + `/runs/${run.id}`)).json())
          .status,
    )
    .toBe("completed");
  return { project, root, run };
}

test("snapshot save, primary readout, verified upload and explicit paused restoration", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const { root, run } = await fixture(page);
  await page.goto("/models?view=bundles");
  await page.getByRole("button", { name: "保存实验快照", exact: true }).click();
  const editor = page.getByRole("dialog");
  await editor.getByLabel("意识", { exact: true }).selectOption(run.id);
  await editor.getByLabel("名称", { exact: true }).fill("完整实验快照");
  await editor
    .getByRole("button", { name: "保存实验快照", exact: true })
    .click();
  await expect(page.locator(".bundle-card")).toHaveCount(1, { timeout: 30000 });
  await page.getByRole("button", { name: "查看与恢复", exact: true }).click();
  const detail = page.getByRole("dialog");
  await expect(detail.getByLabel("证据内容", { exact: true })).toHaveValue(
    "readouts/temporal.jsonl",
  );
  await expect(
    detail.getByRole("button", { name: "恢复为暂停的意识" }),
  ).toBeEnabled();
  await detail.screenshot({ path: info.outputPath("bundle-desktop.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(391);
  await detail.screenshot({ path: info.outputPath("bundle-mobile.png") });
  await detail.getByLabel("新意识名称").fill("恢复验收");
  await detail.getByRole("button", { name: "恢复为暂停的意识" }).click();
  await expect(
    page.getByRole("link", { name: "打开意识", exact: true }),
  ).toHaveCount(1, { timeout: 30000 });
  const runs = await (await page.request.get(root + "/runs")).json();
  const restored = runs.find((r: any) => r.name === "恢复验收");
  expect(restored.status).toBe("paused");
  expect(restored.id).not.toBe(run.id);
  const bundle = (await (await page.request.get(root + "/bundles")).json())
    .rows[0];
  const raw = await (
    await page.request.get(root + `/bundles/${bundle.id}/download`)
  ).body();
  await page
    .locator('input[type="file"][accept=".tmexperiment,.zip"]')
    .setInputFiles({
      name: "roundtrip.tmexperiment",
      mimeType: "application/zip",
      buffer: raw,
    });
  await expect(page.locator(".bundle-card")).toHaveCount(2, { timeout: 30000 });
  expect((await (await page.request.get(root + "/runs")).json()).length).toBe(
    2,
  );
  expect(errors).toEqual([]);
});

test("device settings and schema navigation on narrow screens", async ({
  page,
}, info) => {
  await fixture(page);
  await page.goto("/settings?section=tools");
  await page.getByLabel("计算设备", { exact: true }).selectOption("cpu");
  await page.getByLabel("显存预留（MiB）").fill("768");
  await page.getByLabel("搜索操作", { exact: true }).fill("bundle.export");
  await page
    .getByLabel("选择操作", { exact: true })
    .selectOption("bundle.export");
  await expect(page.locator(".settings-panel").last()).toContainText(
    "expected_revision",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(391);
  await page.screenshot({
    path: info.outputPath("compute-mobile.png"),
    fullPage: true,
  });
  await page.getByRole("link", { name: "打开 Transformer 工具" }).click();
  await expect(page.getByLabel("本次训练与查询使用")).toHaveValue("cpu");
  await expect(page.getByLabel("显存预留（MiB）")).toHaveValue("768");
});

test("unavailable WebGL falls back to a selectable two-dimensional view", async ({
  page,
}, info) => {
  const { run, root } = await fixture(page);
  const before = await (
    await page.request.get(root + `/runs/${run.id}`)
  ).json();
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (
      type: any,
      options: any,
    ) {
      return String(type).includes("webgl")
        ? null
        : original.call(this, type, options);
    } as any;
  });
  await page.goto(`/runs/${run.id}`);
  await expect(
    page.getByText(
      "当前使用 Canvas 2D 显示回退；只影响画面，不改变意识计算。",
      { exact: false },
    ),
  ).toBeVisible();
  await expect(page.locator(".graph-canvas canvas")).toHaveCount(1);
  const button = page.getByRole("button", {
    name: "导出当前画面 PNG",
    exact: true,
  });
  await expect(button).toBeEnabled();
  const download = page.waitForEvent("download");
  await button.click();
  expect((await download).suggestedFilename()).toContain("canvas");
  await page
    .locator(".graph-panel")
    .screenshot({ path: info.outputPath("canvas-fallback.png") });
  const after = await (await page.request.get(root + `/runs/${run.id}`)).json();
  expect(after.state_hash).toBe(before.state_hash);
});

test("stage GUI and JSON preserve repeats and paginate anonymous channels", async ({
  page,
}, info) => {
  const { run, root } = await fixture(page);
  const fork = await (
    await page.request.post(root + `/runs/${run.id}/forks`, {
      data: { name: "阶段沙箱", paused: true, background: "suspend" },
    })
  ).json();
  await page.goto(`/runs/${fork.id}?view=research&tool=plans`);
  await page
    .getByRole("button", { name: "设计阶段重复实验", exact: true })
    .click();
  const editor = page.getByRole("dialog");
  await editor.getByLabel("完整重复次数", { exact: true }).first().fill("12");
  await editor
    .getByRole("button", { name: "切换为 JSON 编辑", exact: true })
    .click();
  const json = editor.getByRole("textbox", { name: "阶段协议 JSON" });
  await expect(json).toContainText('"repeat": 12');
  const request = page.waitForRequest(
    (r) =>
      r.method() === "POST" && r.url().endsWith("/research/plans/validate"),
  );
  await editor.getByRole("button", { name: "校验计划", exact: true }).click();
  const protocol = (await request).postDataJSON();
  protocol.mode = "manual";
  protocol.stages = [
    {
      name: "匿名通道分页",
      repeat: 2,
      steps: [
        {
          command: "stimulus.frames",
          parameters: {
            frames: [
              {
                time_us: "0",
                channels: Array.from({ length: 72 }, (_, i) => [i + 1, 0.5]),
                intensity: 0.8,
              },
            ],
          },
        },
        { command: "runtime.wait", parameters: { duration_us: 1000 } },
      ],
    },
  ];
  await json.fill(JSON.stringify(protocol));
  await editor
    .getByRole("button", { name: "切换为图形配置", exact: true })
    .click();
  await expect(editor.getByLabel("通道", { exact: true })).toHaveCount(50);
  await editor
    .getByRole("button", { name: "下一页", exact: true })
    .first()
    .click();
  await expect(editor.getByLabel("通道", { exact: true })).toHaveCount(22);
  await editor.getByLabel("通道", { exact: true }).first().fill("151");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(391);
  await editor.screenshot({ path: info.outputPath("stages-mobile.png") });
  await editor
    .getByRole("button", { name: "冻结并保存计划", exact: true })
    .click();
  await expect(editor).toBeHidden();
  const plans = (
    await (
      await page.request.get(root + `/runs/${fork.id}/research/plans`)
    ).json()
  ).rows;
  expect(plans).toHaveLength(1);
  const saved = await (
    await page.request.get(
      root + `/runs/${fork.id}/research/plans/${plans[0].id}`,
    )
  ).json();
  expect(saved.protocol.stages[0].repeat).toBe(2);
  expect(
    saved.protocol.stages[0].steps[0].parameters.frames[0].channels[50][0],
  ).toBe(151);
});
