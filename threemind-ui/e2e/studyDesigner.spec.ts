import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("model archive controls reflect the project's researcher and viewer roles", async ({
  page,
}) => {
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "档案角色界面验收" },
    })
  ).json();
  await page.request.post(`/api/v2/projects/${project.id}/runs`, {
    data: {
      name: "角色检查对象",
      spec: { environment: "manual", clock: "unbounded", duration_s: 0.01 },
    },
  });
  let role = "researcher";
  // Only presentation identities are substituted. Backend remains authenticated
  // and is separately covered by the actual project authorization API tests.
  await page.route("**/api/v2/projects", async (route) => {
    const response = await route.fetch();
    const rows = await response.json();
    await route.fulfill({
      response,
      json: rows.map((row: any) =>
        row.id === project.id ? { ...row, role } : row,
      ),
    });
  });
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page.goto("/models");
  await page.getByRole("button", { name: "编辑档案", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByLabel("意识名称", { exact: true }),
  ).not.toHaveAttribute("readonly", "");
  await expect(
    dialog.getByRole("button", { name: "保存档案", exact: true }),
  ).toBeEnabled();
  role = "viewer";
  await page.reload();
  await page.getByRole("button", { name: "编辑档案", exact: true }).click();
  await expect(dialog.getByLabel("意识名称", { exact: true })).toHaveAttribute(
    "readonly",
    "",
  );
  await expect(
    dialog.getByRole("button", { name: "保存档案", exact: true }),
  ).toBeDisabled();
});

test("graphical paired protocols, shared identities, typed runtime conditions and frozen reuse", async ({
  page,
}, info) => {
  const errors: string[] = [],
    requests: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => requests.push(r.url()));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "图形实验协议验收" },
    })
  ).json();
  const root = `/api/v2/projects/${project.id}`;
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page.goto("/studies");
  await page.getByRole("button", { name: "设计新实验", exact: true }).click();
  const main = page.getByRole("dialog", { name: "设计配对实验", exact: true });
  await main.getByLabel("实验名称", { exact: true }).fill("完整图形条件验收");
  await main.getByLabel("独立环境种子", { exact: true }).fill("31, 47");
  await main
    .getByLabel("共同发育时长（模拟秒）", { exact: true })
    .fill("0.025");
  await main.getByLabel("条件运行时长（模拟秒）", { exact: true }).fill("0.08");
  await main.getByRole("button", { name: "配置基础协议", exact: true }).click();
  const base = page.getByRole("dialog", { name: "共同基础协议", exact: true });
  await base
    .locator('[data-parameter="environment"] select')
    .selectOption("ambient");
  await base
    .getByRole("button", { name: "应用到协议草案", exact: true })
    .click();
  await expect(base).toBeHidden();
  await main
    .getByRole("article", { name: "实验条件 2", exact: true })
    .getByRole("button", { name: "编辑条件参数", exact: true })
    .click();
  const arm = page.getByRole("dialog", {
    name: "条件参数 · 关闭可塑性",
    exact: true,
  });
  await arm.locator(".configuration-advanced > summary").click();
  await expect(
    arm.locator('[data-parameter="config.step_us"] input'),
  ).toHaveAttribute("readonly", "");
  await arm.getByLabel("联想传播速率", { exact: true }).fill("0");
  await arm
    .getByLabel("高级参数分类", { exact: true })
    .selectOption("source_policies");
  await arm
    .locator(
      '[data-parameter="source_policies.environment_bypass_attention"] input',
    )
    .check();
  await arm.getByRole("button", { name: "切换到 JSON", exact: true }).click();
  const validation = page.waitForRequest((r) =>
    r.url().endsWith("/configuration/validate"),
  );
  await arm.getByRole("button", { name: "校验", exact: true }).click();
  const actual = (await validation).postDataJSON().spec;
  expect(actual.config.propagation_rate).toBe(0);
  expect(actual.source_policies.environment_bypass_attention).toBe(true);
  const json = arm.getByRole("textbox", { name: "JSON 参数", exact: true });
  await json.fill(JSON.stringify({ ...actual, seed: actual.seed + 1 }));
  await arm
    .getByRole("button", { name: "应用到协议草案", exact: true })
    .click();
  await expect(arm.getByRole("alert")).toContainText("条件间共享");
  await json.fill(JSON.stringify(actual));
  await arm
    .getByRole("button", { name: "应用到协议草案", exact: true })
    .click();
  await expect(arm).toBeHidden();
  const checked = page.waitForRequest((r) =>
    r.url().endsWith("/studies/validate"),
  );
  await main.getByRole("button", { name: "校验协议", exact: true }).click();
  const protocol = (await checked).postDataJSON();
  expect(
    protocol.arms[1].runtime_patch.source_policies.environment_bypass_attention,
  ).toBe(true);
  await main
    .getByRole("button", { name: "切换到协议 JSON", exact: true })
    .click();
  const editor = main.getByRole("textbox", {
    name: "实验协议 JSON",
    exact: true,
  });
  await expect(main.locator(".cm-lineNumbers")).toBeVisible();
  await editor.fill('{"name":"x","name":"y"}');
  await main
    .getByRole("button", { name: "冻结协议并运行", exact: true })
    .click();
  await expect(main.getByRole("alert")).toContainText("重复");
  expect(await (await page.request.get(root + "/studies")).json()).toEqual([]);
  protocol.arms[1].runtime_patch.body_filter = {
    enabled: true,
    channel_count: 1,
  };
  await editor.fill(JSON.stringify(protocol));
  await main
    .getByRole("button", { name: "切换到图形设计", exact: true })
    .click();
  await expect(
    main.getByRole("article", { name: "实验条件 2", exact: true }),
  ).toContainText("2 个工具分组覆盖");
  await main.screenshot({
    path: info.outputPath("study-designer-desktop.png"),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(350);
  expect(
    await main.evaluate((el) => el.scrollWidth <= el.clientWidth + 1),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("study-designer-mobile.png"),
    fullPage: false,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  const created = page.waitForResponse(
    (r) => r.url().endsWith("/studies") && r.request().method() === "POST",
  );
  await main
    .getByRole("button", { name: "冻结协议并运行", exact: true })
    .click();
  const study = (await (await created).json()).params.study_id;
  await expect(main).toBeHidden();
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(root + `/runs?study_id=${study}`)
          ).json()
        ).filter((r: any) => r.status === "completed").length,
    )
    .toBe(6);
  const frozen = await (
    await page.request.get(root + `/studies/${study}`)
  ).json();
  await page
    .getByRole("button", { name: "以此协议再设计", exact: true })
    .click();
  await expect(main.getByLabel("实验名称", { exact: true })).toHaveValue(
    "完整图形条件验收",
  );
  await main.getByLabel("实验名称", { exact: true }).fill("尚未冻结的草案");
  await main.getByRole("button", { name: "取消", exact: true }).click();
  expect(
    (await (await page.request.get(root + `/studies/${study}`)).json())
      .protocol_hash,
  ).toBe(frozen.protocol_hash);
  expect(requests.some((url) => url.includes("summary=true"))).toBe(true);
  expect(errors).toEqual([]);
});

test("independent replay blocks support frame controls and JSON without reusing a recording silently", async ({
  page,
}) => {
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "区组帧编辑验收" },
    })
  ).json();
  const root = `/api/v2/projects/${project.id}`;
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page.goto("/studies");
  await page.getByRole("button", { name: "设计新实验", exact: true }).click();
  const main = page.getByRole("dialog", { name: "设计配对实验", exact: true });
  await main.getByLabel("独立环境种子", { exact: true }).fill("31, 47");
  await main.getByLabel("共同发育时长（模拟秒）", { exact: true }).fill("0");
  await main.getByLabel("条件运行时长（模拟秒）", { exact: true }).fill("0.04");
  await main.getByRole("button", { name: "配置基础协议", exact: true }).click();
  const base = page.getByRole("dialog", { name: "共同基础协议", exact: true });
  await base
    .locator('[data-parameter="environment"] select')
    .selectOption("replay");
  await base
    .getByRole("button", { name: "应用到协议草案", exact: true })
    .click();
  await main
    .getByRole("button", { name: "冻结协议并运行", exact: true })
    .click();
  await expect(main.getByRole("alert")).toContainText("replay_blocks");
  for (const seed of [31, 47]) {
    await main
      .getByRole("button", { name: `区组 ${seed} · 未配置 帧`, exact: true })
      .click();
    const block = page.getByRole("dialog", {
      name: `重放区组 ${seed}`,
      exact: true,
    });
    await block
      .getByRole("button", { name: "添加刺激帧", exact: true })
      .click();
    await block.getByLabel("帧 1 时间（微秒）", { exact: true }).fill("10000");
    await block.getByRole("button", { name: "添加通道", exact: true }).click();
    await block
      .getByLabel("匿名节点 ID · 1", { exact: true })
      .fill(String(seed));
    await block.getByLabel("通道幅值 · 1", { exact: true }).fill("0.7");
    await block
      .getByRole("button", { name: "切换到刺激 JSON", exact: true })
      .click();
    await expect(
      block.getByRole("textbox", { name: "重放刺激 JSON", exact: true }),
    ).toContainText('"time_us": "10000"');
    await block
      .getByRole("button", { name: "切换到帧表单", exact: true })
      .click();
    await expect(
      block.getByLabel("匿名节点 ID · 1", { exact: true }),
    ).toHaveValue(String(seed));
    await block
      .getByRole("button", { name: "校验并保存区组", exact: true })
      .click();
    await expect(block).toBeHidden();
  }
  const created = page.waitForResponse(
    (r) => r.url().endsWith("/studies") && r.request().method() === "POST",
  );
  await main
    .getByRole("button", { name: "冻结协议并运行", exact: true })
    .click();
  const study = (await (await created).json()).params.study_id;
  await expect(main).toBeHidden();
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(root + `/runs?study_id=${study}`)
          ).json()
        ).filter((r: any) => r.status === "completed").length,
    )
    .toBe(6);
  const saved = (
    await (await page.request.get(root + `/studies/${study}`)).json()
  ).protocol;
  expect(saved.replay_blocks["31"][0].channels[0][0]).toBe(31);
  expect(saved.replay_blocks["47"][0].channels[0][0]).toBe(47);
});
