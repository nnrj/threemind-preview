import { expect, test } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("development: graphical creation, pinned registration, inherited identity, lineage and model export", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `发育模块验收 ${Date.now()}` },
    })
  ).json();
  const base = `/api/v2/projects/${project.id}`;
  await page.addInitScript((id: string) => {
    if (window === window.top) localStorage.setItem("tm2.project", id);
  }, project.id);
  await page.goto("/studies?tab=development");
  await page.getByRole("button", { name: "新建发育训练", exact: true }).click();
  let dialog = page.getByRole("dialog");
  await expect(dialog.locator(".configuration-advanced")).not.toHaveAttribute(
    "open",
  );
  await expect(
    dialog.getByLabel("环境与感官来源", { exact: true }),
  ).toHaveValue("mujoco");
  await expect(dialog.getByLabel("时钟模式", { exact: true })).toHaveValue(
    "unbounded",
  );
  await dialog.getByLabel("训练名称", { exact: true }).fill("模拟身体发育甲");
  await dialog.getByLabel("运行时长（模拟秒）", { exact: true }).fill("0.08");
  await dialog.locator(".configuration-advanced > summary").click();
  const environmentSeed = dialog.getByLabel("环境随机化种子", { exact: true });
  await expect(environmentSeed).toHaveValue("");
  await expect(environmentSeed).toHaveAttribute(
    "placeholder",
    "沿用感官身份种子",
  );
  await environmentSeed.fill("91");
  await dialog
    .locator('[data-parameter="environment_seed"]')
    .evaluate((element) => element.scrollIntoView({ block: "center" }));
  await page.screenshot({
    path: info.outputPath("environment-seed-configuration.png"),
  });
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  const editor = dialog.getByRole("textbox", {
    name: "JSON 参数",
    exact: true,
  });
  await expect(editor).toContainText('"duration_s": 0.08');
  await expect(editor).toContainText('"environment_seed": 91');
  await expect(dialog.locator(".cm-lineNumbers")).toBeVisible();
  await dialog.getByRole("button", { name: "格式化", exact: true }).click();
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  await expect(dialog.locator(".configuration-success")).toContainText(
    "校验通过",
  );
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(
    dialog.getByLabel("运行时长（模拟秒）", { exact: true }),
  ).toHaveValue("0.08");
  await page.screenshot({ path: info.outputPath("development-creation.png") });
  await dialog.getByRole("button", { name: "创建并训练", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator(".development-sessions .badge")).toHaveText(
    "已完成",
  );
  const session = (await (await page.request.get(base + "/development")).json())
    .rows[0];
  await page.getByRole("button", { name: "登记先天版本", exact: true }).click();
  dialog = page.getByRole("dialog");
  await dialog.locator('input[type="radio"]').first().check();
  await dialog
    .getByLabel("版本名称", { exact: true })
    .fill("先天甲 · 物理输入来源");
  await dialog
    .getByRole("button", { name: "登记所选恢复点", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "先天甲 · 物理输入来源", exact: true }),
  ).toBeVisible();
  const version = (
    await (await page.request.get(base + "/innate-versions")).json()
  ).rows[0];
  const detail = await (
    await page.request.get(base + `/innate-versions/${version.id}`)
  ).json();
  await page.getByRole("button", { name: "从此版本发育", exact: true }).click();
  dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("持续可塑性", { exact: true })).toBeDisabled();
  await expect(
    dialog.getByLabel("感官身份种子", { exact: true }),
  ).toHaveAttribute("readonly");
  await dialog.locator(".configuration-advanced > summary").click();
  await expect(
    dialog.getByLabel("环境随机化种子", { exact: true }),
  ).not.toHaveAttribute("readonly");
  await dialog.getByLabel("训练名称", { exact: true }).fill("继承身体发育乙");
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  const inheritedEditor = dialog.getByRole("textbox", {
    name: "JSON 参数",
    exact: true,
  });
  await inheritedEditor.fill(
    JSON.stringify({
      ...detail.protocol,
      config: { ...detail.protocol.config, plasticity: false },
    }),
  );
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("须保留来源配置");
  await dialog.getByRole("button", { name: "创建并训练", exact: true }).click();
  expect(
    (await (await page.request.get(base + "/development")).json()).rows,
  ).toHaveLength(1);
  await inheritedEditor.fill(
    JSON.stringify({ ...detail.protocol, environment_seed: 103 }),
  );
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(
    dialog.getByLabel("环境随机化种子", { exact: true }),
  ).toHaveValue("103");
  await dialog.getByRole("button", { name: "创建并训练", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator(".development-sessions article")).toHaveCount(2);
  const childCard = page
    .locator(".development-sessions article")
    .filter({ hasText: "继承身体发育乙" });
  await expect(childCard.locator(".badge")).toHaveText("已完成");
  await childCard
    .getByRole("button", { name: "登记先天版本", exact: true })
    .click();
  dialog = page.getByRole("dialog");
  await dialog.locator('input[type="radio"]').first().check();
  await dialog
    .getByLabel("版本名称", { exact: true })
    .fill("先天乙 · 继承谱系");
  await dialog
    .getByRole("button", { name: "登记所选恢复点", exact: true })
    .click();
  await expect(page.locator(".development-lineage li")).toHaveCount(2);
  await page.getByLabel("模型格式", { exact: true }).selectOption("bundle");
  await page.getByRole("button", { name: "生成导出", exact: true }).click();
  const download = page.getByRole("link", { name: "下载文件", exact: true });
  await expect(download).toBeVisible();
  const result = await page.request.get((await download.getAttribute("href"))!);
  expect(result.ok()).toBeTruthy();
  expect((await result.body()).subarray(0, 2).toString()).toBe("PK");
  await page.screenshot({
    path: info.outputPath("development-lineage-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: info.outputPath("development-lineage-mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page
    .getByRole("link", { name: "阅读训练与继承说明", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "发育训练与先天版本", exact: true }),
  ).toBeVisible();
  await page.goto("/studies?tab=development");
  await page
    .getByRole("button", { name: "登记已有恢复点", exact: true })
    .click();
  dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("来源意识", { exact: true })
    .selectOption(session.run_id);
  await dialog.locator('input[type="radio"]').first().check();
  await expect(
    dialog.getByRole("button", { name: "登记所选恢复点", exact: true }),
  ).toBeEnabled();
  await dialog
    .getByLabel("查找来源意识", { exact: true })
    .fill("不存在的来源意识");
  await expect(
    dialog.getByRole("button", { name: "登记所选恢复点", exact: true }),
  ).toBeDisabled();
  expect(
    (await (await page.request.get(`${base}/runs/${session.run_id}`)).json())
      .state_hash,
  ).toBe(version.state_hash);
  expect(errors).toEqual([]);
});
