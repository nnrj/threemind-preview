import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("optional kernel settings are graphical, synchronized, validated and used by the model", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `内核对照验收 ${new Date().toISOString()}` },
    })
  ).json();
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建运行", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("运行名称").fill("可选内核 · 时窗与钳制");
  await dialog
    .getByLabel("环境与感官来源", { exact: true })
    .selectOption("manual");
  await dialog.getByLabel("运行时长（模拟秒）", { exact: true }).fill("20");
  await dialog.locator(".configuration-advanced > summary").click();
  await dialog
    .getByLabel("高级参数分类", { exact: true })
    .selectOption("optional");
  await expect(
    dialog.getByLabel("启用全局激活钳制", { exact: true }),
  ).not.toBeChecked();
  await expect(
    dialog.getByLabel("局部新颖巩固增益", { exact: true }),
  ).toHaveValue("0");
  await dialog
    .getByRole("combobox", { name: "连接形成策略", exact: true })
    .selectOption("temporal-association");
  await dialog.getByLabel("时窗生边窗口", { exact: true }).fill("123456");
  await dialog.getByLabel("启用全局激活钳制", { exact: true }).check();
  await dialog.getByLabel("全局激活目标上限", { exact: true }).fill("0.4");
  await dialog.getByLabel("局部新颖巩固增益", { exact: true }).fill("0.018");
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  const request = page.waitForRequest((r) =>
    r.url().endsWith("/configuration/validate"),
  );
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  const spec = (await request).postDataJSON().spec;
  expect(spec.config.association_window_us).toBe(123456);
  expect(spec.config.local_novelty_gain).toBe(0.018);
  const editor = dialog.getByRole("textbox", {
    name: "JSON 参数",
    exact: true,
  });
  spec.config.consolidation_cap = 0.06;
  spec.config.inhibition_saturation = 2;
  await editor.fill(JSON.stringify(spec));
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await dialog
    .getByLabel("高级参数分类", { exact: true })
    .selectOption("memory");
  await expect(dialog.getByLabel("单次巩固上限", { exact: true })).toHaveValue(
    "0.06",
  );
  await dialog
    .getByLabel("高级参数分类", { exact: true })
    .selectOption("optional");
  await dialog
    .getByLabel("时窗生边窗口", { exact: true })
    .scrollIntoViewIfNeeded();
  await expect(
    dialog.getByLabel("时窗生边窗口", { exact: true }),
  ).toBeInViewport({ ratio: 1 });
  await page.screenshot({
    path: info.outputPath("optional-core-desktop.png"),
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await dialog
    .getByLabel("时窗生边窗口", { exact: true })
    .scrollIntoViewIfNeeded();
  await expect(
    dialog.getByLabel("时窗生边窗口", { exact: true }),
  ).toBeInViewport({ ratio: 1 });
  await page.screenshot({
    path: info.outputPath("optional-core-mobile.png"),
    fullPage: false,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await dialog.getByRole("button", { name: "创建并开始", exact: true }).click();
  await expect(page).toHaveURL(/\/runs\//);
  const id = page.url().split("/runs/")[1].split(/[?#]/)[0];
  const url = `/api/v2/projects/${project.id}/runs/${id}`;
  try {
    await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
    await expect
      .poll(async () => (await (await page.request.get(url)).json()).status)
      .toBe("paused");
    const row = await (await page.request.get(url)).json();
    expect(row.spec.config).toMatchObject({
      edge_birth_policy: "temporal-association",
      consolidation_cap: 0.06,
      inhibition_saturation: 2,
    });
    await page.getByRole("button", { name: "参数配置", exact: true }).click();
    await expect(
      dialog.getByRole("button", { name: "保存配置", exact: true }),
    ).toBeEnabled();
    await dialog.locator(".configuration-advanced > summary").click();
    await dialog
      .getByLabel("高级参数分类", { exact: true })
      .selectOption("optional");
    await expect(
      dialog.getByRole("combobox", { name: "连接形成策略", exact: true }),
    ).toHaveValue("temporal-association");
    await dialog
      .getByRole("button", { name: "切换到 JSON", exact: true })
      .click();
    spec.config.novelty_touch_reference = 0;
    await editor.fill(JSON.stringify(spec));
    await dialog.getByRole("button", { name: "保存配置", exact: true }).click();
    await expect(dialog.getByRole("alert")).toContainText("positive");
    spec.config.novelty_touch_reference = 0.3;
    await editor.fill(JSON.stringify(spec));
    await dialog.getByRole("button", { name: "保存配置", exact: true }).click();
    await expect(dialog).toHaveCount(0);
    expect(
      (await (await page.request.get(url)).json()).spec.config
        .novelty_touch_reference,
    ).toBe(0.3);
    const history = await (
      await page.request.get(`${url}/events?kind=configuration_changed`)
    ).json();
    expect(history[0].payload.dynamics).toBe(
      (await (await page.request.get("/api/v2/configuration")).json()).dynamics,
    );
    await page.goto("/docs?doc=docs%2Fzh%2Fv2-optional-core.md");
    await expect(
      page.getByRole("heading", { name: "可选内核机制与对照", exact: true }),
    ).toBeVisible();
    await expect(page.locator(".markdown .katex").first()).toBeVisible();
    await expect(page.locator(".katex-error")).toHaveCount(0);
    expect(errors).toEqual([]);
  } finally {
    await page.request
      .post(`${url}/commands`, { data: { kind: "pause" }, timeout: 5000 })
      .catch(() => {});
  }
});
