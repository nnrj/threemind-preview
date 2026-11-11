import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("event evidence: capture real input deliveries, fixed table, raw detail, JSON validation and narrow layout", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `事件来源验收 ${Date.now()}` },
    })
  ).json();
  const base = `/api/v2/projects/${project.id}`;
  await page.addInitScript(
    (id) => localStorage.setItem("tm2.project", id),
    project.id,
  );
  const response = await page.request.post(`${base}/runs`, {
    data: {
      name: "两次物理载体重放",
      spec: {
        environment: "replay",
        clock: "unbounded",
        duration_s: 0.06,
        sample_us: 1000,
        replay: [
          {
            time_us: "0",
            channels: [
              [1, 0.8],
              [2, 0.7],
            ],
          },
          { time_us: "20000", channels: [[2, 0.6]] },
        ],
      },
    },
  });
  expect(response.status()).toBe(201);
  const run = await response.json();
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`${base}/runs/${run.id}`)).json())
          .status,
    )
    .toBe("completed");
  await page.goto("/reports");
  await page.getByRole("button", { name: "新建实验记录", exact: true }).click();
  await page
    .getByRole("textbox", { name: "文档标题", exact: true })
    .fill("刺激递送与事件时间");
  await page.getByRole("button", { name: "添加数据来源", exact: true }).click();
  const picker = page.getByRole("dialog", {
    name: "选择或采集数据来源",
    exact: true,
  });
  await picker
    .getByRole("combobox", { name: "来源类型", exact: true })
    .selectOption("events");
  await picker
    .getByRole("combobox", { name: "意识", exact: true })
    .selectOption(run.id);
  await picker
    .getByRole("combobox", { name: "事件范围", exact: true })
    .selectOption("inputs");
  await picker
    .getByRole("textbox", { name: "指定事件类型（可选）", exact: true })
    .fill("input_delivered");
  await picker.getByRole("button", { name: "开始采集", exact: true }).click();
  await picker.getByRole("button", { name: "使用此来源", exact: true }).click();
  await expect(picker).not.toBeVisible();
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已保存修订 1");
  const saved = (
    await (await page.request.get(`${base}/research-documents`)).json()
  ).rows[0];
  const rendered = await (
    await page.request.get(`${base}/research-documents/${saved.id}/render`)
  ).json();
  const table = rendered.blocks.find((b: any) => b.type === "table");
  expect(table.source_kind).toBe("events");
  expect(table.rows.length).toBe(2);
  expect(table.rows.map((r: any) => r.time_us)).toEqual(["0", "20000"]);
  expect(table.rows.every((r: any) => !("payload" in r.provenance))).toBe(true);
  await page.getByRole("button", { name: "预览与校验", exact: true }).click();
  const preview = page.getByRole("dialog", { name: "记录预览", exact: true });
  await expect(preview.locator(".report-chart svg")).toBeVisible();
  await expect(
    preview.getByRole("columnheader", { name: "事件类型与阶段" }),
  ).toBeVisible();
  await preview
    .getByRole("button", { name: /^查看事件 / })
    .first()
    .click();
  const detail = page.getByRole("dialog", {
    name: "固定事件原始内容",
    exact: true,
  });
  await expect(detail.locator("pre")).toContainText('"payload"');
  await expect(detail.locator("pre")).toContainText('"time_us": "0"');
  await detail.getByRole("button", { name: "关闭", exact: true }).click();
  await preview.locator(".report-figure").last().scrollIntoViewIfNeeded();
  await page.screenshot({
    path: info.outputPath("report-events-desktop.png"),
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await preview.locator(".report-figure").last().scrollIntoViewIfNeeded();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("report-events-mobile.png"),
    fullPage: false,
  });
  await preview.getByRole("button", { name: "关闭", exact: true }).click();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page
    .getByRole("button", { name: "切换到 JSON 编辑", exact: true })
    .click();
  const spec = (
    await (
      await page.request.get(`${base}/research-documents/${saved.id}`)
    ).json()
  ).spec;
  const fact = spec.blocks.find((b: any) => b.type === "fact");
  fact.statistic = "mean";
  await page
    .getByRole("textbox", { name: "记录与报告 JSON", exact: true })
    .fill(JSON.stringify(spec));
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "event facts count log entries",
  );
  expect(
    (
      await (
        await page.request.get(`${base}/research-documents/${saved.id}`)
      ).json()
    ).revision,
  ).toBe(1);
  expect(errors).toEqual([]);
});
