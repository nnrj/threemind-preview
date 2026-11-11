import { expect, test } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("ecology: graphical senses, JSON round-trip, actual population and fixed export", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "生态训练工程验收 " + Date.now() },
    })
  ).json();
  const root = "/api/v2/projects/" + project.id + "/ecologies";
  await page.addInitScript(
    (id: string) => localStorage.setItem("tm2.project", id),
    project.id,
  );
  await page.goto("/studies?tab=ecology");
  await page.getByRole("button", { name: "新建生态训练", exact: true }).click();
  const dialog = page.getByRole("dialog", {
    name: "新建生态训练",
    exact: true,
  });
  const advanced = dialog
    .locator("summary")
    .filter({ hasText: "生态高级参数" });
  await expect(advanced.locator("..")).not.toHaveAttribute("open");
  await dialog
    .getByLabel("训练名称", { exact: true })
    .fill("真实生态两代工程样例");
  await dialog.getByLabel("初始个体数", { exact: true }).fill("3");
  await advanced.click();
  await dialog
    .locator("summary")
    .filter({ hasText: /^躯体状态感官$/ })
    .click();
  await expect(
    dialog.getByLabel("感知身体储备", { exact: true }),
  ).toBeChecked();
  await expect(
    dialog.getByLabel("感知身体损伤", { exact: true }),
  ).toBeChecked();
  await expect(
    dialog.getByLabel("感知附近资源", { exact: true }),
  ).toBeChecked();
  await dialog.getByLabel("感知身体损伤", { exact: true }).uncheck();
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  const json = dialog.getByRole("textbox", {
    name: "生态协议 JSON",
    exact: true,
  });
  await expect(dialog.locator(".cm-lineNumbers")).toBeVisible();
  const checked = page.waitForRequest((r) =>
    r.url().endsWith("/ecologies/validate"),
  );
  await dialog.getByRole("button", { name: "校验协议", exact: true }).click();
  const value = (await checked).postDataJSON();
  expect(value.ecology.founder_count).toBe(3);
  expect(value.ecology.senses.damage_enabled).toBe(false);
  await json.fill('{"base":{},"base":{}}');
  await dialog.getByRole("button", { name: "格式化", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("重复");
  value.base.duration_s = 0.1;
  value.base.clock = "unbounded";
  value.ecology.founder_count = 2;
  value.ecology.rules.uptake_per_s = 100;
  value.ecology.rules.maintenance_per_s = 0;
  value.ecology.rules.patches = [
    {
      id: "food",
      radius: 10,
      capacity: 100,
      initial: 100,
      regeneration_per_s: 0,
    },
  ];
  Object.assign(value.ecology.rules.reproduction, {
    interval_us: 20000,
    minimum_age_us: 20000,
    cooldown_us: 1000000,
    threshold: 4,
    offspring_reserve: 1,
    population_limit: 6,
  });
  await json.fill(JSON.stringify(value));
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(dialog.getByLabel("初始个体数", { exact: true })).toHaveValue(
    "2",
  );
  await page.screenshot({
    path: info.outputPath("ecology-configuration.png"),
    fullPage: true,
  });
  const created = page.waitForResponse(
    (r) => r.url().endsWith("/ecologies") && r.request().method() === "POST",
  );
  await dialog
    .getByRole("button", { name: "创建并开始训练", exact: true })
    .click();
  const response = await created;
  expect(response.status()).toBe(201);
  const row = await response.json();
  await expect(dialog).not.toBeVisible();
  await expect
    .poll(
      async () =>
        (await (await page.request.get(root + "/" + row.id)).json()).campaign
          .status,
    )
    .toBe("completed");
  const detail = page.locator(".ecology-detail");
  await expect(
    detail.getByRole("link", { name: "查看意识与完整数据" }),
  ).toHaveCount(6);
  await expect(detail.locator("canvas")).toHaveCount(1);
  const history = await (
    await page.request.get(root + "/" + row.id + "/checkpoints")
  ).json();
  await detail
    .getByLabel("种群恢复点", { exact: true })
    .selectOption(history.rows.at(-1).id);
  await expect(
    detail.getByRole("link", { name: "查看意识与完整数据" }),
  ).toHaveCount(2);
  await detail.getByLabel("种群恢复点", { exact: true }).selectOption("");
  await expect(
    detail.getByRole("link", { name: "查看意识与完整数据" }),
  ).toHaveCount(6);
  await detail
    .locator("summary")
    .filter({ hasText: /^导出种群证据$/ })
    .click();
  await detail
    .getByRole("button", { name: "导出当前种群恢复点", exact: true })
    .click();
  await expect(
    detail.getByRole("link", { name: "下载证据包", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("ecology-population.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: info.outputPath("ecology-mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 2,
    ),
  ).toBe(true);
  await detail
    .getByRole("button", { name: "查看冻结协议", exact: true })
    .click();
  const frozen = page.getByRole("dialog", { name: "冻结的生态训练协议" });
  await expect(
    frozen.getByLabel("初始个体数", { exact: true }),
  ).toHaveAttribute("readonly", "");
  expect(errors).toEqual([]);
});

test("ecology: active group controls, individual ownership and direct navigation", async ({
  page,
}) => {
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "生态控制工程验收 " + Date.now() },
    })
  ).json();
  const root = "/api/v2/projects/" + project.id + "/ecologies";
  const protocol = (await (await page.request.get(root + "/catalogue")).json())
    .defaults;
  protocol.base.clock = "realtime";
  protocol.base.duration_s = 20;
  protocol.ecology.rules.reproduction.enabled = false;
  const created = await page.request.post(root, {
    data: {
      operation_id: crypto.randomUUID(),
      name: "种群统一控制",
      objective: "工程控制验收，不作意识结论",
      protocol,
    },
  });
  expect(created.status(), await created.text()).toBe(201);
  const row = await created.json();
  const read = async () =>
    (await (await page.request.get(root + "/" + row.id)).json()).campaign;
  await page.addInitScript(
    (id: string) => localStorage.setItem("tm2.project", id),
    project.id,
  );
  try {
    await page.goto("/studies?tab=ecology&campaign=" + row.id);
    const detail = page.locator(".ecology-detail");
    await expect(
      detail.getByRole("link", { name: "查看意识与完整数据" }),
    ).toHaveCount(2);
    await detail.getByRole("button", { name: "暂停", exact: true }).click();
    await expect.poll(async () => (await read()).status).toBe("paused");
    await detail
      .getByRole("link", { name: "查看意识与完整数据" })
      .first()
      .click();
    await expect(
      page.getByRole("link", { name: "管理所属生态训练", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "继续", exact: true }),
    ).toHaveCount(0);
    await page.getByRole("button", { name: "参数配置", exact: true }).click();
    const configuration = page.getByRole("dialog", {
      name: "意识参数配置",
      exact: true,
    });
    await expect(
      configuration.getByRole("button", { name: "保存配置", exact: true }),
    ).toBeDisabled();
    await expect(configuration).toContainText("协议已冻结");
    await configuration
      .getByRole("button", { name: "关闭", exact: true })
      .last()
      .click();
    await page
      .getByRole("link", { name: "管理所属生态训练", exact: true })
      .click();
    await expect(
      detail.getByRole("button", { name: "继续", exact: true }),
    ).toBeVisible();
    await detail.getByRole("button", { name: "继续", exact: true }).click();
    await expect.poll(async () => (await read()).status).toBe("active");
    await detail.getByRole("button", { name: "取消训练", exact: true }).click();
    await expect.poll(async () => (await read()).status).toBe("cancelled");
  } finally {
    const state = await read();
    if (["active", "paused", "blocked"].includes(state.status)) {
      await page.request.post(root + "/" + row.id + "/controls", {
        data: { action: "cancel", expected_revision: state.control_revision },
      });
      await expect.poll(async () => (await read()).status).toBe("cancelled");
    }
  }
});
