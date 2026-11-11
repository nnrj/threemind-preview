import { expect, test } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("evolution: graphical protocol, independent copies and fixed evidence", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `多代流程工程验收 ${Date.now()}` },
    })
  ).json();
  const base = `/api/v2/projects/${project.id}`;
  await page.addInitScript(
    (id: string) => localStorage.setItem("tm2.project", id),
    project.id,
  );
  await page.goto("/studies?tab=evolution");
  await page.getByRole("button", { name: "新建多代实验", exact: true }).click();
  const dialog = page.getByRole("dialog", {
    name: "新建多代定向实验",
    exact: true,
  });
  await expect(dialog.locator(".evolution-seeds")).not.toHaveAttribute("open");
  await expect(dialog.locator(".evolution-criterion")).toHaveCount(0);
  await dialog
    .getByLabel("实验名称", { exact: true })
    .fill("两代独立副本工程样例");
  await dialog
    .getByLabel("研究目标与选择依据", { exact: true })
    .fill("验证流程和证据完整性，不作为演化或意识有效性的研究结论。");
  await dialog.getByLabel("每代个体数", { exact: true }).fill("2");
  await dialog.getByLabel("每代父本数", { exact: true }).fill("1");
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  await expect(dialog.getByRole("alert")).toBeVisible();
  await dialog
    .getByRole("button", { name: "添加筛选指标", exact: true })
    .click();
  await dialog
    .getByRole("combobox", { name: "指标 1", exact: true })
    .selectOption("nodes");
  await dialog
    .getByRole("button", { name: "添加筛选指标", exact: true })
    .click();
  await dialog
    .getByRole("combobox", { name: "指标 2", exact: true })
    .selectOption("observed_lifetime_s");
  await dialog
    .getByRole("button", { name: "提高指标 2 优先级", exact: true })
    .click();
  await expect(
    dialog.getByRole("combobox", { name: "指标 1", exact: true }),
  ).toHaveValue("observed_lifetime_s");
  await dialog
    .getByRole("button", { name: "降低指标 1 优先级", exact: true })
    .click();
  for (const [button, title] of [
    ["配置发育", "发育与共用参数"],
    ["配置评估", "评估环境与记录参数"],
  ]) {
    await dialog.getByRole("button", { name: button, exact: true }).click();
    const parameters = page.getByRole("dialog", { name: title, exact: true });
    await expect(
      parameters.locator(".configuration-advanced"),
    ).not.toHaveAttribute("open");
    await parameters
      .getByLabel("环境与感官来源", { exact: true })
      .selectOption("ambient");
    await parameters
      .getByLabel("运行时长（模拟秒）", { exact: true })
      .fill("0.24");
    if (button === "配置评估") {
      await expect(
        parameters.getByLabel("感官身份种子", { exact: true }),
      ).toHaveAttribute("readonly");
    }
    await parameters
      .getByRole("button", { name: "应用参数", exact: true })
      .click();
    await expect(parameters).toHaveCount(0);
  }
  await dialog.locator(".evolution-seeds > summary").click();
  await dialog.getByLabel("筛选环境数", { exact: true }).fill("2");
  await dialog.getByLabel("最终验证环境数", { exact: true }).fill("2");
  await dialog
    .getByRole("button", { name: "按当前规模重新生成种子表", exact: true })
    .click();
  const checked = page.waitForRequest(
    (r) => r.url().endsWith("/evolutions/validate") && r.method() === "POST",
  );
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  const protocol = (await checked).postDataJSON();
  await expect(dialog.locator(".configuration-success")).toContainText(
    "校验通过",
  );
  expect(protocol.development.duration_s).toBe(0.24);
  expect(protocol.evaluation.duration_s).toBe(0.24);
  const seeds = [
    ...protocol.development_seeds.flat(),
    ...protocol.evaluation_seeds,
    ...protocol.verification_seeds,
  ];
  expect(new Set(seeds).size).toBe(seeds.length);
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  const json = dialog.getByRole("textbox", {
    name: "多代实验协议 JSON",
    exact: true,
  });
  await expect(dialog.locator(".cm-lineNumbers")).toBeVisible();
  await json.fill('{"generations":2,"generations":3}');
  await dialog
    .getByRole("button", { name: "创建多代实验", exact: true })
    .click();
  await expect(dialog.getByRole("alert")).toContainText("重复");
  expect(
    (await (await page.request.get(base + "/evolutions")).json()).rows,
  ).toHaveLength(0);
  await json.fill(JSON.stringify(protocol));
  await dialog.getByRole("button", { name: "格式化", exact: true }).click();
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(dialog.getByLabel("每代个体数", { exact: true })).toHaveValue(
    "2",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await dialog.getByLabel("实验名称", { exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({
    path: info.outputPath("evolution-configuration-mobile.png"),
  });
  expect(
    await dialog.evaluate((node) => node.scrollWidth <= node.clientWidth + 1),
  ).toBeTruthy();
  await page.setViewportSize({ width: 1365, height: 960 });
  await dialog.getByLabel("实验名称", { exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({
    path: info.outputPath("evolution-configuration.png"),
  });
  await dialog
    .getByRole("button", { name: "创建多代实验", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  const campaign = (await (await page.request.get(base + "/evolutions")).json())
    .rows[0];
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(base + `/evolutions/${campaign.id}`)
          ).json()
        ).status,
      { timeout: 60000 },
    )
    .toBe("completed");
  await page.getByRole("button", { name: "刷新", exact: true }).click();
  await expect(
    page
      .locator(".evolution-detail")
      .getByText("已完成", { exact: true })
      .first(),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: /终点节点数.*跨代描述统计/ }),
  ).toBeVisible();
  const finished = await (
    await page.request.get(base + `/evolutions/${campaign.id}`)
  ).json();
  expect(finished.members).toHaveLength(10);
  expect(finished.selections).toHaveLength(2);
  expect(
    finished.members.every((m: any) => m.outcome.metrics.nodes > 0),
  ).toBeTruthy();
  await page.getByRole("button", { name: "查看冻结协议", exact: true }).click();
  const frozen = page.getByRole("dialog", {
    name: "冻结的多代实验协议",
    exact: true,
  });
  await expect(frozen.getByLabel("实验名称", { exact: true })).toHaveAttribute(
    "readonly",
  );
  await expect(
    frozen.getByRole("button", { name: "创建多代实验", exact: true }),
  ).toHaveCount(0);
  await frozen
    .locator(".modal-actions")
    .getByRole("button", { name: "关闭", exact: true })
    .click();
  await page.getByRole("button", { name: "生成证据 ZIP", exact: true }).click();
  const download = page.getByRole("link", { name: /下载证据 ZIP/ });
  await expect(download).toBeVisible({ timeout: 60000 });
  const fetched = await page.request.get(
    (await download.getAttribute("href"))!,
  );
  expect(fetched.ok()).toBeTruthy();
  expect((await fetched.body()).subarray(0, 2).toString()).toBe("PK");
  await page.locator(".evolution-trend").scrollIntoViewIfNeeded();
  await page.screenshot({ path: info.outputPath("evolution-evidence.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: info.outputPath("evolution-evidence-mobile.png"),
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
  await page.goto("/docs?doc=docs/zh/v2-evolution.md");
  await expect(page.getByRole("heading", { name: "多代定向训练与固定证据", exact: true })).toBeVisible();
});

test("evolution reports: capture a full generation and author from its fixed evidence", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `多代报告工程验收 ${Date.now()}` },
    })
  ).json();
  const base = `/api/v2/projects/${project.id}`;
  const catalogue = await (
    await page.request.get(base + "/evolutions/catalogue")
  ).json();
  const seeds = await (
    await page.request.post(base + "/evolutions/seeds", {
      data: {
        seed: 902,
        generations: 1,
        population_size: 2,
        evaluation_blocks: 1,
        verification_blocks: 1,
      },
    })
  ).json();
  const spec = {
    ...catalogue.defaults.development,
    environment: "ambient",
    duration_s: 0.22,
    sample_us: 10000,
    checkpoint_us: 10000,
  };
  const started = await page.request.post(base + "/evolutions", {
    data: {
      operation_id: crypto.randomUUID(),
      name: "报告用多代样例",
      objective: "Only engineering acceptance of evidence authoring.",
      protocol: {
        ...catalogue.defaults,
        ...seeds,
        generations: 1,
        population_size: 2,
        survivor_count: 1,
        development: spec,
        evaluation: spec,
        criteria: [
          { metric: "nodes", direction: "maximize", aggregate: "mean" },
        ],
      },
    },
  });
  expect(started.status()).toBe(201);
  const campaign = await started.json();
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(base + `/evolutions/${campaign.id}`)
          ).json()
        ).status,
      { timeout: 45000 },
    )
    .toBe("completed");
  await page.addInitScript(
    (id: string) => localStorage.setItem("tm2.project", id),
    project.id,
  );
  await page.goto("/reports");
  await page.getByRole("button", { name: "新建实验记录", exact: true }).click();
  await page.getByRole("button", { name: "添加数据来源", exact: true }).click();
  const dialog = page.getByRole("dialog", {
    name: "选择或采集数据来源",
    exact: true,
  });
  await dialog
    .getByRole("combobox", { name: "来源类型", exact: true })
    .selectOption("evolution");
  await dialog
    .getByRole("combobox", { name: "多代实验", exact: true })
    .selectOption(campaign.id);
  await dialog
    .getByRole("combobox", { name: "多代结果阶段", exact: true })
    .selectOption("selection");
  await dialog.getByRole("button", { name: "开始采集", exact: true }).click();
  await dialog.getByRole("button", { name: "使用此来源", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await page
    .getByLabel("文档标题", { exact: true })
    .fill("包含全部候选的固定筛选记录");
  await page.getByRole("button", { name: "预览与校验", exact: true }).click();
  const preview = page.getByRole("dialog", { name: "记录预览", exact: true });
  await expect(preview.getByRole("heading", { name: "节点数", exact: true })).toBeVisible();
  await expect(preview.locator(".report-chart svg")).toBeVisible();
  await page.screenshot({ path: info.outputPath("evolution-report-preview.png") });
  await page.keyboard.press("Escape");
  await expect(page.getByRole("status")).toContainText("校验通过");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已保存修订 1");
  await page.screenshot({
    path: info.outputPath("evolution-report-source.png"),
    fullPage: true,
  });
  const sources = (
    await (await page.request.get(base + "/report-sources")).json()
  ).rows;
  expect(sources).toHaveLength(1);
  const evidence = await (
    await page.request.get(base + `/report-sources/${sources[0].id}/rows`)
  ).json();
  expect(evidence.rows.map((r: any) => r.provenance.selected).sort()).toEqual([
    false,
    true,
  ]);
  expect(errors).toEqual([]);
});
