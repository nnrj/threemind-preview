import { test, expect } from "@playwright/test";
test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly isolated workstation.",
);

async function project(page: any) {
  const response = await page.request.post("/api/v2/projects", {
    data: { name: `内核验收 ${Date.now()}` },
  });
  expect(response.status()).toBe(201);
  const value = await response.json();
  await page.addInitScript(
    (id) => localStorage.setItem("tm2.project", id),
    value.id,
  );
  return value;
}

test("kernel identities, creation defaults, mode switching and definitions", async ({
  page,
}, info) => {
  await project(page);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/kernels");
  await expect(page.locator(".kernel-card")).toHaveCount(7);
  await expect(
    page
      .locator(".kernel-card")
      .filter({ hasText: "threemind.continuous-memory/4" }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("kernels-wide.png"),
    fullPage: true,
  });
  const card = page.locator(".kernel-card").filter({ hasText: "独立脉冲候选" });
  const download = page.waitForEvent("download");
  await card.getByRole("button", { name: "导出定义" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toContain("lif-1");
  await card.getByRole("button", { name: "创建意识" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("内核版本", { exact: true })).toHaveValue(
    "threemind.lif/1",
  );
  await expect(
    dialog.getByLabel("运行时长（模拟秒）", { exact: true }),
  ).toHaveValue("");
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  const json = dialog.getByRole("textbox", { name: "JSON 参数", exact: true });
  await expect(json).toContainText('"threshold_mv": -50');
  await expect(json).not.toContainText('"activation_tau"');
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  await expect(dialog.locator(".configuration-success")).toContainText(
    "校验通过",
  );
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await dialog
    .getByLabel("内核版本", { exact: true })
    .selectOption("threemind.continuous/1");
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  await expect(json).toContainText('"activation_tau"');
  await expect(json).not.toContainText('"threshold_mv"');
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  await expect(dialog.locator(".configuration-success")).toContainText(
    "校验通过",
  );
  await dialog.getByRole("button", { name: "关闭", exact: true }).click();
  expect(errors).toEqual([]);
});

test("narrow-screen text navigation and accessible kernel configuration", async ({
  page,
}, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await project(page);
  await page.goto("/kernels");
  await expect(
    page.getByRole("button", { name: "打开导航菜单" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "打开导航菜单" }).click();
  const nav = page.getByRole("dialog");
  await expect(
    nav.getByRole("link", { name: "实验笔记", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("mobile-navigation.png"),
    fullPage: false,
  });
  await nav.getByRole("link", { name: "内核与对照工具", exact: true }).click();
  await expect(nav).toHaveCount(0);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page
    .locator(".kernel-card")
    .first()
    .getByRole("button", { name: "创建意识" })
    .click();
  await expect(
    page.getByLabel("节点标记／感官模式", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("kernel-mobile-config.png"),
    fullPage: false,
  });
  const rect = await page.getByRole("dialog").boundingBox();
  expect(rect!.x).toBeGreaterThanOrEqual(0);
  expect(rect!.width).toBeLessThan(390);
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "关闭", exact: true })
    .click();
  await page.setViewportSize({ width: 320, height: 740 });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(320);
});

test("local Transformer training and probability evidence", async ({
  page,
}, info) => {
  const p = await project(page);
  await page.goto("/kernels");
  await page
    .getByRole("button", { name: "本地 Transformer", exact: true })
    .click();
  await page.getByLabel("训练步数上限", { exact: true }).fill("20");
  await page.getByRole("button", { name: "开始本地训练", exact: true }).click();
  await expect(
    page.getByText(
      "训练已排队。结果和数值模型将保存为项目证据，不改动现有意识。",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "计算下一事件概率" }),
  ).toBeEnabled({ timeout: 60000 });
  await page.getByRole("button", { name: "计算下一事件概率" }).click();
  await expect(page.locator(".probability-result li")).toHaveCount(8, {
    timeout: 60000,
  });
  await expect(page.getByRole("link", { name: "下载数值模型" })).toBeVisible();
  await page.screenshot({
    path: info.outputPath("transformer-wide.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.screenshot({
    path: info.outputPath("transformer-mobile.png"),
    fullPage: true,
  });
  const run = await (
    await page.request.post(`/api/v2/projects/${p.id}/runs`, {
      data: {
        name: "显式外部接入",
        spec: {
          environment: "manual",
          duration_s: 30,
          config: { activation_decay_enabled: false },
        },
      },
    })
  ).json();
  try {
    await page.locator(".probability-feedback > summary").click();
    await expect(
      page.getByLabel("接收意识").locator(`option[value="${run.id}"]`),
    ).toHaveCount(1);
    await page.getByLabel("接收意识").selectOption(run.id);
    const accepted = page.waitForResponse(
      (r) =>
        r.request().method() === "POST" &&
        r.url().includes("/predictions/") &&
        r.url().endsWith("/inputs"),
    );
    await page.getByRole("button", { name: "发送一次外部概率刺激" }).click();
    const receipt = await accepted;
    expect(receipt.status()).toBe(202);
    expect(
      (await receipt.json()).configuration.transduction.external_contribution,
    ).toBe(true);
    await expect(
      page.getByText("外部概率刺激已接收，来源、模型和通道映射已记录。"),
    ).toBeVisible();
  } finally {
    await page.request.post(
      `/api/v2/projects/${p.id}/runs/${run.id}/commands`,
      { data: { kind: "pause" } },
    );
  }
});

test("physical states and actual spike events remain separate", async ({
  page,
}, info) => {
  const p = await project(page);
  const response = await page.request.post(`/api/v2/projects/${p.id}/runs`, {
    data: {
      name: "脉冲原始观测",
      spec: {
        kernel_id: "threemind.lif/1",
        config: { input_gain_na: 5 },
        environment: "replay",
        clock: "unbounded",
        duration_s: 0.021,
        replay: [
          {
            time_us: "0",
            channels: [
              [1, 0.8],
              [2, 0.7],
            ],
          },
        ],
      },
    },
  });
  expect(response.status()).toBe(201);
  const r = await response.json();
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(`/api/v2/projects/${p.id}/runs/${r.id}`)
          ).json()
        ).status,
    )
    .toBe("completed");
  await page.goto(`/runs/${r.id}?view=dynamics`);
  await expect(
    page.getByRole("heading", { name: "膜电位与电流", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "发放事件", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".spike-node-list").first()).toContainText("1");
  await page.screenshot({
    path: info.outputPath("lif-physical.png"),
    fullPage: true,
  });
});
