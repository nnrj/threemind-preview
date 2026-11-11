import { expect, test } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("ecology observer: graphical and JSON rules, immutable history, sources and export", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "观察规则工程验收 " + Date.now() },
    })
  ).json();
  const base = "/api/v2/projects/" + project.id + "/ecologies";
  const protocol = (await (await page.request.get(base + "/catalogue")).json())
    .defaults;
  protocol.base.duration_s = 0.1;
  protocol.base.checkpoint_us = 20000;
  protocol.ecology.founder_count = 2;
  const created = await page.request.post(base, {
    data: {
      operation_id: crypto.randomUUID(),
      name: "观察与预警验收",
      objective: "Engineering validation only",
      protocol,
    },
  });
  expect(created.status()).toBe(201);
  const campaign = await created.json();
  const root = base + "/" + campaign.id + "/observer";
  await expect
    .poll(
      async () =>
        (await (await page.request.get(base + "/" + campaign.id)).json())
          .campaign.status,
    )
    .toBe("completed");
  await page.addInitScript(
    (id) => localStorage.setItem("tm2.project", id),
    project.id,
  );
  await page.goto("/studies?tab=ecology&campaign=" + campaign.id);
  const panel = page.getByRole("region", {
    name: "生态观察与预警",
    exact: true,
  });
  await expect(panel).toContainText("生态观察当前关闭");
  await panel.getByRole("button", { name: "配置观察", exact: true }).click();
  const dialog = page.getByRole("dialog", {
    name: "配置生态观察与预警",
    exact: true,
  });
  await expect(
    dialog.getByLabel("启用生态观察", { exact: true }),
  ).not.toBeChecked();
  await expect(
    dialog
      .locator("summary")
      .filter({ hasText: "高级时长与重复提示" })
      .locator(".."),
  ).not.toHaveAttribute("open");
  await dialog.getByLabel("启用生态观察", { exact: true }).check();
  await dialog
    .getByLabel("本版本从哪里开始观察", { exact: true })
    .selectOption("beginning");
  await dialog.getByLabel("规则名称", { exact: true }).fill("真实躯体计数提示");
  await dialog
    .getByLabel("观察指标", { exact: true })
    .selectOption("living_bodies");
  await dialog.getByLabel("触发阈值", { exact: true }).fill("1");
  await page.screenshot({
    path: info.outputPath("observer-configuration.png"),
    fullPage: false,
  });
  await dialog
    .getByRole("button", { name: "切换到 JSON 编辑", exact: true })
    .click();
  await expect(dialog.locator(".cm-lineNumbers")).toBeVisible();
  const editor = dialog.getByRole("textbox", {
    name: "观察与预警 JSON",
    exact: true,
  });
  const validated = page.waitForRequest((r) =>
    r.url().endsWith("/observer/validate"),
  );
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  const value = (await validated).postDataJSON();
  expect(value.enabled).toBe(true);
  expect(value.rules[0].metric).toBe("living_bodies");
  expect(value.rules[0].threshold).toBe(1);
  await editor.fill('{"enabled":true,"enabled":false}');
  await dialog.getByRole("button", { name: "格式化", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("重复");
  await editor.fill(
    JSON.stringify({
      ...value,
      rules: [{ ...value.rules[0], metric: "invented_intent" }],
    }),
  );
  await dialog
    .getByRole("button", { name: "保存观察配置", exact: true })
    .click();
  await expect(dialog.getByRole("alert")).toBeVisible();
  expect((await (await page.request.get(root)).json()).observer).toBeNull();
  value.rules[0].threshold = 2;
  await editor.fill(JSON.stringify(value));
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(dialog.getByLabel("触发阈值", { exact: true })).toHaveValue("2");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: info.outputPath("observer-mobile-configuration.png"),
    fullPage: false,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 2,
    ),
  ).toBe(true);
  await dialog
    .getByRole("button", { name: "保存观察配置", exact: true })
    .scrollIntoViewIfNeeded();
  await page.screenshot({
    path: info.outputPath("observer-mobile-actions.png"),
    fullPage: false,
  });
  await dialog
    .getByRole("button", { name: "保存观察配置", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await expect
    .poll(
      async () =>
        (await (await page.request.get(root)).json()).observer.job_status,
      { timeout: 30000 },
    )
    .toBe("done");
  await panel
    .getByLabel("观察条目类型", { exact: true })
    .selectOption("warning");
  await expect(panel.getByText("预警命中", { exact: true })).toBeVisible();
  await panel
    .locator("summary")
    .filter({ hasText: /^查看事实与原始依据$/ })
    .first()
    .click();
  await expect(panel.locator("pre").first()).toContainText("checkpoint_hash");
  await panel.screenshot({
    path: info.outputPath("observer-mobile-evidence.png"),
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 2,
    ),
  ).toBe(true);
  const link = panel.getByRole("link", {
    name: "导出当前规则的观察 JSONL",
    exact: true,
  });
  const exported = await page.request.get((await link.getAttribute("href"))!);
  expect(exported.status()).toBe(200);
  const lines = (await exported.text())
    .trim()
    .split("\n")
    .map((line) => JSON.parse(line));
  expect(lines[0].configuration.rules[0].threshold).toBe(2);
  expect(lines.length - 1).toBe(lines[0].entry_count);
  expect(
    lines
      .slice(1)
      .every((line) => line.source.checkpoint_hash && line.content_hash),
  ).toBe(true);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await panel.scrollIntoViewIfNeeded();
  await panel.screenshot({
    path: info.outputPath("observer-evidence.png"),
  });
  const history = await (
    await page.request.get(base + "/" + campaign.id + "/checkpoints")
  ).json();
  const earliest = history.rows.at(-1);
  await page
    .getByLabel("种群恢复点", { exact: true })
    .selectOption(earliest.id);
  await expect
    .poll(async () =>
      (
        await (
          await page.request.get(root + "/entries?checkpoint_id=" + earliest.id)
        ).json()
      ).rows.every((r: any) => r.body.source.checkpoint_revision === 1),
    )
    .toBe(true);
  await panel.getByRole("button", { name: "配置观察", exact: true }).click();
  await dialog.getByLabel("启用生态观察", { exact: true }).uncheck();
  await dialog
    .getByRole("button", { name: "保存观察配置", exact: true })
    .click();
  await expect(dialog).not.toBeVisible();
  await expect(panel).toContainText("生态观察当前关闭");
  await expect(panel).toContainText("此范围尚无观察条目");
  await panel.getByLabel("观察规则版本", { exact: true }).selectOption("1");
  await expect(panel.getByText("预警命中", { exact: true })).toBeVisible();
  await panel
    .getByRole("link", { name: "观察与预警的证据边界", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "生态观察与规则预警", exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
