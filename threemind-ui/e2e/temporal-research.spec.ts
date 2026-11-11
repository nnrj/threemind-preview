import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly isolated workstation.",
);

test("temporal experiment inherits settings, validates JSON, exports and creates a graphical report", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `时序工具验收 ${Date.now()}` },
    })
  ).json();
  const source = await (
    await page.request.post(`/api/v2/projects/${project.id}/runs`, {
      data: {
        name: "时序验收来源",
        spec: {
          environment: "manual",
          duration_s: 0.3,
          clock: "unbounded",
          text_sensor: { encoding: "literal-character" },
          config: {
            propagation_rate: 0,
            activation_decay_enabled: false,
            inhibition_gain: 0,
          },
        },
      },
    })
  ).json();
  expect(source.id, JSON.stringify(source)).toBeTruthy();
  const base = `/api/v2/projects/${project.id}/runs/${source.id}`;
  await expect
    .poll(async () => (await (await page.request.get(base)).json()).status)
    .toBe("completed");
  const before = await (await page.request.get(base)).json();
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page.goto(`/runs/${source.id}?view=research&tool=calibration`);
  await expect(
    page.getByRole("heading", { name: "时序观察实验", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "完整探针句子（每行一句）", exact: true })
    .fill("甲是松子。");
  await page.locator("summary").filter({ hasText: "高级观察配置" }).click();
  await expect(
    page.getByRole("combobox", { name: "副本起点", exact: true }),
  ).toHaveValue("continuation");
  await expect(
    page.getByRole("combobox", { name: "测量时学习", exact: true }),
  ).toHaveValue("inherit");
  await page
    .getByRole("spinbutton", { name: "本批实验墙钟预算（秒）", exact: true })
    .fill("70");
  await page.getByRole("button", { name: "JSON 编辑", exact: true }).click();
  const json = page.getByRole("textbox", {
    name: "时序实验协议 JSON",
    exact: true,
  });
  await expect(json).toContainText('"max_wall_seconds": 70');
  await expect(json).toContainText('"甲是松子。"');
  await page.getByRole("button", { name: "图形配置", exact: true }).click();
  await page.getByRole("button", { name: "开始时序观察", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "导出完整证据 ZIP", exact: true }),
  ).toBeVisible({ timeout: 45000 });
  await expect(
    page.getByRole("checkbox", {
      name: "显示全部节点（包含非候选及零活动）",
      exact: true,
    }),
  ).toBeVisible();
  const calibration = await page
    .getByLabel("选择时序实验", { exact: true })
    .inputValue();
  const result = await (
    await page.request.get(
      `/api/v2/projects/${project.id}/calibrations/${calibration}/result`,
    )
  ).json();
  expect(result.protocol.max_wall_seconds).toBe(70);
  expect(result.protocol.route).toBe("continuation");
  expect(result.protocol.blank_us).toBe(0);
  expect(
    Number(result.rows[0].temporal.end_us) -
      Number(result.rows[0].temporal.delivery_end_us),
  ).toBeGreaterThanOrEqual(1200000);
  const download = await page.request.get(
    (await page
      .getByRole("link", { name: "导出完整证据 ZIP", exact: true })
      .getAttribute("href"))!,
  );
  expect(download.status()).toBe(200);
  expect((await download.body()).subarray(0, 2).toString()).toBe("PK");
  await page.screenshot({
    path: info.outputPath("temporal-observation.png"),
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "用此时序实验创建记录", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "选择或采集数据来源",
    exact: true,
  });
  await expect(
    dialog.getByRole("combobox", { name: "已完成的时序实验", exact: true }),
  ).toHaveValue(calibration);
  await dialog
    .getByRole("combobox", { name: "来源类型", exact: true })
    .selectOption("temporal_series");
  await dialog
    .getByRole("combobox", { name: "观察窗口（曲线须选择一个）", exact: true })
    .selectOption(result.rows[0].temporal.window_id);
  await dialog.getByRole("button", { name: "开始采集", exact: true }).click();
  await dialog
    .getByRole("button", { name: "使用此来源", exact: true })
    .first()
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(page.locator(".report-editor")).toBeVisible();
  await page.screenshot({
    path: info.outputPath("temporal-report-draft.png"),
    fullPage: true,
  });
  const after = await (await page.request.get(base)).json();
  expect(after.revision).toBe(before.revision);
  expect(errors).toEqual([]);
});
