import { expect, test } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("independent assessment: graphical and JSON configuration, immutable parent and report decisions", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "独立评估工程验收 " + Date.now() },
    })
  ).json();
  const base = "/api/v2/projects/" + project.id;
  const spec = (await (await page.request.get("/api/v2/configuration")).json())
    .defaults;
  Object.assign(spec, {
    environment: "ambient",
    clock: "unbounded",
    duration_s: 0.04,
    checkpoint_us: 10000,
    sample_us: 10000,
    environment_seed: 881,
  });
  const parent = await (
    await page.request.post(base + "/development", {
      data: {
        operation_id: crypto.randomUUID(),
        name: "评估父本",
        objective: "工程验收",
        spec,
      },
    })
  ).json();
  await expect
    .poll(
      async () =>
        (await (await page.request.get(base + "/runs/" + parent.run_id)).json())
          .status,
    )
    .toBe("completed");
  const cp = (
    await (
      await page.request.get(base + `/runs/${parent.run_id}/checkpoints`)
    ).json()
  )[0];
  const version = await (
    await page.request.post(base + "/innate-versions", {
      data: {
        operation_id: crypto.randomUUID(),
        name: "评估来源",
        selection_note: "工程验收来源，不是科学结果",
        run_id: parent.run_id,
        checkpoint_id: cp.id,
        expected_state_hash: cp.state_hash,
      },
    })
  ).json();
  await page.addInitScript(
    (id) => localStorage.setItem("tm2.project", id),
    project.id,
  );
  await page.goto("/studies?tab=assessment");
  await page.getByRole("button", { name: "新建独立评估", exact: true }).click();
  const dialog = page.getByRole("dialog", {
    name: "新建独立评估",
    exact: true,
  });
  await dialog.getByLabel("评估名称", { exact: true }).fill("独立出生验证");
  await dialog
    .getByLabel("评估目标与限制", { exact: true })
    .fill("验收两种规则判定、完整试验覆盖和父本不变。");
  await dialog
    .getByLabel("评估来源版本", { exact: true })
    .selectOption(version.id);
  await expect(dialog.getByLabel("评估指标", { exact: true })).toHaveValue(
    "not_dead_at_end",
  );
  await dialog.getByLabel(/^评估环境种子/).fill("882, 883");
  await expect(
    dialog
      .locator("details")
      .filter({
        has: page.locator("summary", { hasText: "额外排除种子（高级）" }),
      }),
  ).not.toHaveAttribute("open");
  await dialog.getByRole("button", { name: "添加规则", exact: true }).click();
  await dialog
    .getByLabel("评估指标", { exact: true })
    .nth(1)
    .selectOption("nodes");
  await dialog.getByLabel("阈值", { exact: true }).nth(1).fill("99999");
  // The common catalogue supplies all environment and Core fields.
  const duration = dialog.getByLabel(/运行时长/).first();
  await duration.fill("0.04");
  await page.screenshot({
    path: info.outputPath("assessment-configuration.png"),
    fullPage: false,
  });
  await dialog
    .getByRole("button", { name: "切换到 JSON 编辑", exact: true })
    .click();
  const editor = dialog.getByRole("textbox", {
    name: "独立评估 JSON",
    exact: true,
  });
  await expect(dialog.locator(".cm-lineNumbers")).toBeVisible();
  const request = page.waitForRequest((r) =>
    r.url().endsWith("/assessments/validate"),
  );
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  const value = (await request).postDataJSON();
  expect(value.environment_seeds).toEqual([882, 883]);
  expect(value.criteria[1].threshold).toBe(99999);
  expect(value.evaluation.duration_s).toBe(0.04);
  await editor.fill(
    JSON.stringify({
      ...value,
      evaluation: { ...value.evaluation, seed: 999999 },
    }),
  );
  await dialog
    .getByRole("button", { name: "创建并启动独立评估", exact: true })
    .click();
  await expect(dialog.getByRole("alert")).toContainText("感官身份");
  expect(
    (await (await page.request.get(base + "/assessments")).json()).rows.length,
  ).toBe(0);
  await editor.fill(
    JSON.stringify({ ...value, environment_seeds: [881, 883] }),
  );
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("重叠");
  value.criteria[1].threshold = 88888;
  await editor.fill(JSON.stringify(value));
  await dialog.getByRole("button", { name: "格式化", exact: true }).click();
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(dialog.getByLabel("阈值", { exact: true }).nth(1)).toHaveValue(
    "88888",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: info.outputPath("assessment-mobile-configuration.png"),
    fullPage: false,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 2,
    ),
  ).toBe(true);
  const created = page.waitForResponse(
    (r) => r.url().endsWith("/assessments") && r.request().method() === "POST",
  );
  await dialog
    .getByRole("button", { name: "创建并启动独立评估", exact: true })
    .click();
  expect((await created).status()).toBe(201);
  await expect(dialog).not.toBeVisible();
  const batch = await (await created).json();
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(base + "/assessments/" + batch.id)
          ).json()
        ).all_trials_complete,
    )
    .toBe(true);
  await page
    .getByRole("button", { name: "采集当前完整评估证据", exact: true })
    .click();
  const recordLink = page.getByRole("link", {
    name: "从此证据创建记录",
    exact: true,
  });
  await expect(recordLink).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: info.outputPath("assessment-results.png"),
    fullPage: false,
  });
  await page.getByRole("button", { name: "查看固定判定", exact: true }).click();
  const fixed = page.getByRole("dialog", { name: "查看固定判定", exact: true });
  await expect(
    fixed.getByRole("region", { name: "固定规则判定", exact: true }),
  ).toContainText("不符合");
  await fixed.getByRole("button", { name: /关闭|Close/ }).click();
  await recordLink.click();
  await expect(
    page.getByRole("textbox", { name: "文档标题", exact: true }),
  ).toBeVisible();
  const validateRecord = page.getByRole("button", {
    name: "预览与校验",
    exact: true,
  });
  await validateRecord.click();
  await expect(
    page.getByRole("region", { name: "固定规则判定", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("assessment-record.png"),
    fullPage: false,
  });
  const after = await (
    await page.request.get(base + "/runs/" + parent.run_id)
  ).json();
  expect(after.state_hash).toBe(cp.state_hash);
  expect(errors).toEqual([]);
});
