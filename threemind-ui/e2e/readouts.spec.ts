import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("recoverable readout configuration, complete evidence, charts and mobile layout", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `读出验收 ${new Date().toISOString()}` },
    })
  ).json();
  const root = `/api/v2/projects/${project.id}`;
  const created = await page.request.post(`${root}/runs`, {
    data: {
      name: "时序与结构观察",
      spec: { environment: "manual", clock: "realtime", duration_s: 30 },
    },
  });
  expect(created.status()).toBe(201);
  const run = await created.json(),
    url = `${root}/runs/${run.id}`;
  await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
  await expect
    .poll(async () => (await (await page.request.get(url)).json()).status)
    .toBe("paused");
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page.goto(`/runs/${run.id}`);
  await page.getByRole("button", { name: "读出与响应", exact: true }).click();
  await page.getByRole("button", { name: "配置读出器", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.locator(".configuration-advanced > summary").click();
  await dialog
    .getByLabel("高级参数分类", { exact: true })
    .selectOption("temporal_readout");
  await dialog.getByLabel("时序采样间隔", { exact: true }).fill("50000");
  await dialog.getByLabel("尾段判定窗口", { exact: true }).fill("100000");
  await dialog.getByLabel("输入结束后最短观察", { exact: true }).fill("200000");
  await dialog.getByLabel("单个响应窗口上限", { exact: true }).fill("1000000");
  await dialog.getByLabel("时序默认显示数", { exact: true }).fill("1");
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  const validate = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/configuration/validate"),
  );
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  expect(
    (await validate).postDataJSON().spec.temporal_readout.display_limit,
  ).toBe(1);
  await expect(dialog.locator(".configuration-success")).toContainText(
    "校验通过",
  );
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await page.screenshot({
    path: info.outputPath("readouts-configuration.png"),
    fullPage: false,
  });
  await dialog.getByRole("button", { name: "保存配置", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  const accepted = await page.request.post(`${url}/inputs`, {
    data: {
      adapter_id: "text-sensor",
      request_id: crypto.randomUUID(),
      payload: { text: "ABABCCAB" },
    },
  });
  expect(accepted.status()).toBe(202);
  await page.request.post(`${url}/commands`, { data: { kind: "resume" } });
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(`${url}/readouts?kind=temporal_readout`)
          ).json()
        ).rows.length,
      { timeout: 30000 },
    )
    .toBeGreaterThan(0);
  await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
  await expect
    .poll(async () => (await (await page.request.get(url)).json()).status)
    .toBe("paused");
  await page.getByRole("button", { name: "刷新读出", exact: true }).click();
  await expect(page.locator(".readout-detail")).toBeVisible();
  await expect(
    page.getByLabel("只看候选节点", { exact: true }),
  ).not.toBeChecked();
  await expect(
    page.getByRole("img", {
      name: "超基线活动总量 随模拟时间变化的曲线",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByLabel("每页读出节点", { exact: true })).toHaveValue(
    "1",
  );
  await expect(
    page.getByRole("button", { name: "下一页节点", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "下一页节点", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "上一页节点", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("combobox", { name: "指标分组", exact: true })
    .selectOption("traces");
  await expect(
    page.locator(".readout-detail th").filter({ hasText: "直接痕迹积分" }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("readouts-desktop.png"),
    fullPage: true,
  });
  for (const [label, extension] of [
    ["完整记录 JSON", "json"],
    ["全部节点 CSV", "csv"],
    ["完整轨迹 SVG", "svg"],
    ["完整轨迹 PNG", "png"],
    ["完整轨迹 PDF", "pdf"],
  ]) {
    const download = page.waitForEvent("download");
    await page.getByRole("link", { name: label, exact: true }).click();
    expect((await download).suggestedFilename()).toMatch(
      new RegExp(`\\.${extension}$`),
    );
  }
  const rows = await (
    await page.request.get(`${url}/readouts?kind=temporal_readout`)
  ).json();
  const full = await (
    await page.request.get(`${url}/readouts/${rows.rows[0].id}/export`)
  ).json();
  expect(full.payload.nodes.length).toBeGreaterThan(1);
  expect(full.payload.series.length).toBeGreaterThan(3);
  expect(full.payload.configuration.display_limit).toBe(1);
  await page
    .getByRole("combobox", { name: "读出类型", exact: true })
    .selectOption("structural_readout");
  await expect(
    page.getByRole("heading", { name: "匿名活动与结构截面", exact: true }),
  ).toBeVisible();
  const structures = await (
    await page.request.get(`${url}/readouts?kind=structural_readout`)
  ).json();
  await expect(
    page.getByRole("combobox", { name: "截面内容", exact: true }),
  ).toHaveValue("raw_nodes");
  const latest = await (
    await page.request.get(`${url}/readouts/${structures.rows[0].id}/export`)
  ).json();
  expect(latest.payload.raw_observation.complete).toBe(true);
  await expect(
    page.locator(".readout-history tbody tr").first().locator("td").nth(2),
  ).toHaveText(String(latest.payload.raw_nodes.length));
  await expect(page.locator(".readout-history tbody tr").first()).toContainText(
    "完整原始截面",
  );
  expect(latest.payload.raw_nodes.length).toBe(
    latest.payload.source_node_count,
  );
  await expect(
    page.getByText("原始截面 / 源节点", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("readouts-raw.png"),
    fullPage: true,
  });
  let structure = structures.rows.find(
    (r: any) => r.payload.structure?.edge_count > 0,
  );
  let historyPage = structures;
  while (!structure && historyPage.more) {
    historyPage = await (
      await page.request.get(
        `${url}/readouts?kind=structural_readout&before_id=${historyPage.next}&limit=100`,
      )
    ).json();
    structure = historyPage.rows.find(
      (r: any) => r.payload.structure?.edge_count > 0,
    );
  }
  expect(structure).toBeTruthy();
  // Complete raw samples continue after candidates disappear, so an older
  // candidate is not necessarily on the first history page.
  await page.goto(`/runs/${run.id}?view=readouts&record=${structure.id}`);
  await expect(
    page.getByRole("heading", { name: "匿名活动与结构截面", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "截面内容", exact: true })
    .selectOption("edges");
  await expect(
    page.locator(".readout-detail th").filter({ hasText: "权重" }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("readouts-structure.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("readouts-mobile.png"),
    fullPage: true,
  });
  await page.goto("/docs?doc=docs%2Fzh%2Fv2-readouts.md");
  await expect(
    page.getByRole("heading", { name: "截面结构与时序响应读出", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".katex").first()).toBeVisible();
  await expect(page.locator(".katex-error")).toHaveCount(0);
  expect(errors).toEqual([]);
});
