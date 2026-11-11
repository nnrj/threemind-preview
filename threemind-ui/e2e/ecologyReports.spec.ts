import { expect, test } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("ecology reports: fixed population, graphical ledger, templates and mobile preview", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "生态报告工程验收 " + Date.now() },
    })
  ).json();
  const base = `/api/v2/projects/${project.id}`;
  const { defaults } = await (
    await page.request.get(base + "/ecologies/catalogue")
  ).json();
  defaults.base.duration_s = 0.06;
  defaults.base.clock = "unbounded";
  defaults.ecology.rules.habitat = "independent";
  defaults.ecology.rules.reproduction.enabled = false;
  const response = await page.request.post(base + "/ecologies", {
    data: {
      operation_id: crypto.randomUUID(),
      name: "完整种群报告样例",
      objective: "工程验收：完整个体和提交轨迹，不作意识结论",
      protocol: defaults,
    },
  });
  expect(response.status(), await response.text()).toBe(201);
  const population = await response.json();
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(base + `/ecologies/${population.id}`)
          ).json()
        ).campaign.status,
    )
    .toBe("completed");
  const detail = await (
    await page.request.get(base + `/ecologies/${population.id}`)
  ).json();
  await page.addInitScript(
    (id: string) => localStorage.setItem("tm2.project", id),
    project.id,
  );
  await page.goto(`/studies?tab=ecology&campaign=${population.id}`);
  const ledger = page
    .locator("details")
    .filter({ has: page.locator("summary", { hasText: /^资源收支账本$/ }) });
  await ledger.locator("summary").first().click();
  await expect(ledger.getByText("n0", { exact: true })).toBeVisible();
  await expect(ledger.getByText("身体维持支出", { exact: true })).toBeVisible();
  await page
    .getByRole("link", { name: "用此恢复点创建记录", exact: true })
    .click();
  const source = page.getByRole("dialog", {
    name: "选择或采集数据来源",
    exact: true,
  });
  await expect(
    source.getByRole("combobox", { name: "来源类型", exact: true }),
  ).toHaveValue("ecology_trajectory");
  await expect(
    source.getByRole("combobox", { name: "生态训练", exact: true }),
  ).toHaveValue(population.id);
  await expect(
    source.getByRole("combobox", { name: "固定种群恢复点", exact: true }),
  ).toHaveValue(detail.checkpoint.id);
  await source.getByRole("button", { name: "开始采集", exact: true }).click();
  const captured = source.locator(".report-source-list > .selected");
  await captured
    .getByRole("button", { name: "使用此来源", exact: true })
    .click();
  await expect(source).not.toBeVisible();
  await page.getByLabel("文档标题", { exact: true }).fill("完整生态轨迹记录");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已保存修订 1");
  await page.getByRole("button", { name: "预览与校验", exact: true }).click();
  const preview = page.getByRole("dialog", { name: "记录预览", exact: true });
  await expect(
    preview.getByRole("img", { name: "living_bodies · line", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("ecology-trajectory-report.png"),
    fullPage: false,
  });
  await preview.getByRole("button", { name: "关闭", exact: true }).click();
  await page.getByRole("button", { name: "返回列表", exact: true }).click();
  await page.getByRole("button", { name: "新建实验记录", exact: true }).click();
  await page.getByRole("button", { name: "添加数据来源", exact: true }).click();
  await source
    .getByRole("combobox", { name: "来源类型", exact: true })
    .selectOption("ecology_members");
  await source
    .getByRole("combobox", { name: "生态训练", exact: true })
    .selectOption(population.id);
  await source.getByRole("button", { name: "开始采集", exact: true }).click();
  await captured
    .getByRole("button", { name: "使用此来源", exact: true })
    .click();
  await page.getByRole("button", { name: "预览与校验", exact: true }).click();
  await expect(
    preview.getByRole("img", { name: "body_reserve · histogram", exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await preview
    .locator(".report-histogram-offset")
    .first()
    .scrollIntoViewIfNeeded();
  await page.screenshot({
    path: info.outputPath("ecology-members-mobile.png"),
    fullPage: false,
  });
  const layout = await page.evaluate(() => ({
    width: innerWidth,
    scroll: document.documentElement.scrollWidth,
    overflowing: Array.from(
      document.querySelectorAll(
        ".report-editor,.report-compose,.report-block-editor,.form-grid,.report-metric-choices label",
      ),
    )
      .filter(
        (element) => element.getBoundingClientRect().right > innerWidth + 2,
      )
      .map((element) => ({
        name: element.className,
        right: element.getBoundingClientRect().right,
        text: element.textContent?.slice(0, 100),
      })),
  }));
  expect(layout.scroll, JSON.stringify(layout)).toBeLessThanOrEqual(
    layout.width + 2,
  );
  expect(errors).toEqual([]);
});
