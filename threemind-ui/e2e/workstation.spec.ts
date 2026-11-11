import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Set THREEMIND_E2E_URL to an explicitly selected test workstation; these tests create a small acceptance project.",
);

test("physical run, immutable export, documentation and responsive settings", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByRole("button", { name: "新建研究项目", exact: true }).click();
  await page
    .getByLabel("项目名称", { exact: true })
    .fill(`浏览器验收 ${new Date().toISOString()}`);
  await page.getByRole("button", { name: "创建项目", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建运行", exact: true })
    .click();
  await page.getByLabel("运行名称").fill("物理闭环 · 自动验收");
  await page.getByLabel("时钟模式").selectOption("unbounded");
  await page.getByLabel("运行时长（模拟秒）").fill("2");
  await page.getByRole("button", { name: "创建并开始" }).click();
  await expect(page).toHaveURL(/\/runs\//);
  const runURL = page.url();
  await expect(page.locator(".graph-footer")).toContainText(/[1-9]\d* 节点/);
  await expect(page.locator(".page-actions .badge")).toContainText("已完成");
  await expect(page.locator(".graph-webgl-canvas")).toBeVisible();
  for (const shape of ["sphere", "cube", "circle", "square", "glow"]) {
    await page.getByLabel("节点形状").selectOption(shape);
    await expect(page.locator(".graph-webgl-canvas")).toBeVisible();
  }
  await page.getByRole("button", { name: "2D", exact: true }).click();
  await page.getByRole("button", { name: "3D", exact: true }).click();
  await page.screenshot({
    path: info.outputPath("network.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "动力学", exact: true }).click();
  await expect(
    page.getByRole("img", {
      name: "activation 随模拟时间变化的曲线",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "意识网络", exact: true }).click();
  await page.getByRole("button", { name: "按需导出", exact: true }).click();
  await page.getByRole("link", { name: "查看导出任务", exact: true }).click();
  const downloadLink = page.getByRole("link", { name: /下载/ }).first();
  await expect(downloadLink).toBeVisible();
  const downloading = page.waitForEvent("download");
  await downloadLink.click();
  const model = await downloading;
  expect(model.suggestedFilename()).toMatch(/\.tmind$/);
  await model.saveAs(info.outputPath("model.tmind"));

  await page.getByRole("link", { name: "项目文档", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "文档索引", exact: true }),
  ).toBeVisible();
  await page.goto("/docs?doc=docs/zh/v2-kernel.md");
  await expect(page.locator(".markdown .katex").first()).toBeVisible();
  await expect(page.locator(".mermaid svg")).toBeVisible();
  await page.screenshot({
    path: info.outputPath("kernel-docs.png"),
    fullPage: true,
  });
  await page.getByRole("link", { name: "设置", exact: true }).click();
  await page.getByRole("button", { name: /^高性能/ }).click();
  await expect(page.locator(".effective-budget")).toContainText("100,000 节点");
  await page.reload();
  await expect(page.locator(".preset-card.selected")).toContainText("高性能");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "切换研究项目", exact: true }).click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("combobox", { name: "研究项目", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("mobile-settings.png"),
    fullPage: true,
  });
  await page.goto(runURL);
  await expect(page.locator(".graph-footer")).toContainText(/[1-9]\d* 节点/);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("mobile-network.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("paired physical study and downloadable statistical evidence", async ({
  page,
}, info) => {
  await page.goto("/studies");
  await page.getByRole("button", { name: "设计新实验", exact: true }).click();
  await page.getByLabel("实验名称").fill("配对消融 · 浏览器验收");
  await page.getByLabel("共同发育时长（模拟秒）").fill("0.2");
  await page.getByLabel("条件运行时长（模拟秒）").fill("0.5");
  await page.getByLabel("独立环境种子").fill("11, 23");
  await page
    .getByRole("button", { name: "冻结协议并运行", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByText("6 / 6 已完成")).toBeVisible({ timeout: 60000 });
  await page.getByRole("button", { name: "执行配对分析", exact: true }).click();
  const link = page.getByRole("link", { name: "下载完整分析与配对数据" });
  await expect(link).toBeVisible({ timeout: 30000 });
  const downloading = page.waitForEvent("download");
  await link.click();
  const analysis = await downloading;
  await analysis.saveAs(info.outputPath("analysis.json"));
  await page.screenshot({
    path: info.outputPath("paired-study.png"),
    fullPage: true,
  });
  await page.getByLabel("干预条件").selectOption({ label: "关闭局部抑制" });
  await expect(link).toHaveCount(0);
});

test("withdrawal form, complete-history comparison and censored evidence", async ({
  page,
}, info) => {
  await page.goto("/studies");
  await page.getByRole("button", { name: "设计新实验", exact: true }).click();
  await page.getByText("从研究模板开始", { exact: true }).click();
  await page.getByLabel("研究模板").selectOption("withdrawal");
  await page.getByLabel("实验名称").fill("撤除恢复 · 浏览器验收");
  await page.getByLabel("共同发育时长（模拟秒）").fill("0.1");
  await page.getByLabel("驱动阶段（秒）").fill("0.3");
  await page.getByLabel("撤除窗口（秒）").fill("0.7");
  await page.getByLabel("恢复阶段（秒）").fill("0.3");
  await page.getByLabel("独立环境种子").fill("11, 23");
  await page
    .getByRole("button", { name: "应用模板到草案", exact: true })
    .click();
  await expect(page.getByLabel("条件运行时长（模拟秒）")).toHaveValue("1.3");
  await page
    .getByRole("button", { name: "冻结协议并运行", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByText("6 / 6 已完成")).toBeVisible({ timeout: 60000 });
  await page.getByLabel("比较曲线指标").selectOption("saturated_fraction");
  await expect(
    page.getByRole("img", { name: "saturated_fraction 随模拟时间变化的曲线" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "执行配对分析", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "下载完整分析与配对数据" }),
  ).toBeVisible({ timeout: 30000 });
  await expect(
    page.getByText(/未观察到 · 随访 .*右删失/).first(),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("withdrawal-study.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "设计新实验", exact: true }).click();
  await page.getByText("从研究模板开始", { exact: true }).click();
  await page.getByLabel("研究模板").selectOption("sweep");
  await page.getByLabel("独立环境种子").fill("11, 23");
  await page.getByLabel("共同发育时长（模拟秒）").fill("0.1");
  await page
    .getByLabel("扫描参数", { exact: true })
    .selectOption("config.inhibition_gain");
  await page.getByLabel("参数取值").fill("0, 4.2");
  await page
    .getByRole("button", { name: "应用模板到草案", exact: true })
    .click();
  await page.getByLabel("条件运行时长（模拟秒）").fill("0.3");
  await page.screenshot({
    path: info.outputPath("mobile-parameter-sweep.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page
    .getByRole("button", { name: "冻结协议并运行", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByText("4 / 4 已完成")).toBeVisible({ timeout: 60000 });
});
