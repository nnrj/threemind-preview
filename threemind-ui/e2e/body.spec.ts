import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("body configuration, raw and encoded evidence, historical selection and exports", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `躯体验收 ${new Date().toISOString()}` },
    })
  ).json();
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建运行", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("运行名称", { exact: true }).fill("显式环境与躯体");
  await dialog
    .getByLabel("环境与感官来源", { exact: true })
    .selectOption("ambient");
  await dialog.locator(".configuration-advanced > summary").click();
  await dialog
    .getByLabel("高级参数分类", { exact: true })
    .selectOption("body_filter");
  await dialog.getByLabel("启用环境躯体过滤", { exact: true }).check();
  await dialog.getByLabel("躯体单帧通道容量", { exact: true }).fill("1");
  await dialog.getByLabel("躯体测量噪声", { exact: true }).fill("0");
  await dialog.getByLabel("躯体采样间隔", { exact: true }).fill("200000");
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  const validate = page.waitForRequest((r) =>
    r.url().endsWith("/configuration/validate"),
  );
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  const spec = (await validate).postDataJSON().spec;
  expect(spec.body_filter.channel_count).toBe(1);
  spec.body_filter.channel_count = 2;
  spec.interoception.enabled = true;
  spec.ambient_field.transient_rate_per_s = 0;
  await dialog
    .getByRole("textbox", { name: "JSON 参数", exact: true })
    .fill(JSON.stringify(spec));
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(
    dialog.getByLabel("躯体单帧通道容量", { exact: true }),
  ).toHaveValue("2");
  await dialog.getByRole("button", { name: "创建并开始", exact: true }).click();
  await expect(page).toHaveURL(/\/runs\//);
  const id = page.url().split("/runs/")[1].split(/[?#]/)[0],
    url = `/api/v2/projects/${project.id}/runs/${id}`;
  const pause = async () => {
    await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
    await expect
      .poll(async () => (await (await page.request.get(url)).json()).status)
      .toBe("paused");
  };
  try {
    await expect
      .poll(async () => {
        const response = await page.request.get(`${url}/body-tools`);
        if (response.status() === 404) return 0;
        expect(response.ok()).toBe(true);
        return (await response.json()).status?.environment_samples ?? 0;
      })
      .toBeGreaterThan(10);
    await pause();
    await page.getByRole("button", { name: "感官与输入", exact: true }).click();
    await page.getByRole("button", { name: "环境与躯体", exact: true }).click();
    const panel = page.getByRole("region", { name: "环境与躯体", exact: true });
    await expect(
      panel.getByRole("img", {
        name: "当前页载体通道条目数 随模拟时间变化的曲线",
        exact: true,
      }),
    ).toBeVisible();
    await panel
      .getByLabel("环境载体来源", { exact: true })
      .selectOption("ambient-fixture");
    await expect(panel.locator("tbody")).toContainText("未到躯体采样时间");
    await expect(panel.locator("tbody")).toContainText("3 / 2");
    const old = await panel
      .getByLabel("环境证据检查点", { exact: true })
      .inputValue();
    await panel
      .getByRole("button", { name: "配置环境与躯体", exact: true })
      .click();
    await expect(
      dialog.getByRole("button", { name: "保存配置", exact: true }),
    ).toBeEnabled();
    await dialog.locator(".configuration-advanced > summary").click();
    await dialog
      .getByLabel("高级参数分类", { exact: true })
      .selectOption("body_filter");
    await dialog.getByLabel("躯体感知阈值", { exact: true }).fill("1");
    await dialog.getByRole("button", { name: "保存配置", exact: true }).click();
    await expect(dialog).toBeHidden();
    await page.request.post(`${url}/commands`, { data: { kind: "resume" } });
    await expect
      .poll(async () =>
        (
          await (
            await page.request.get(`${url}/body-tools?source=ambient-fixture`)
          ).json()
        ).rows?.some((r: any) => r.reason === "body_threshold"),
      )
      .toBe(true);
    await pause();
    await expect(
      panel.getByLabel("环境证据检查点", { exact: true }),
    ).toHaveValue(old);
    await panel.getByRole("button", { name: "刷新证据", exact: true }).click();
    await expect(panel.locator("tbody")).toContainText("未达到感知阈值");
    await panel.getByLabel("环境证据检查点", { exact: true }).selectOption(old);
    await expect(panel.locator("tbody")).toContainText("3 / 2");
    for (const name of ["完整载体 CSV", "完整载体 JSONL"]) {
      const download = page.waitForEvent("download");
      await panel.getByRole("link", { name, exact: true }).click();
      expect((await download).suggestedFilename()).toContain("body-");
    }
    await panel.screenshot({ path: info.outputPath("body-desktop.png") });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect
      .poll(async () =>
        panel
          .locator(".spatial-hash")
          .evaluate((e) => e.scrollWidth <= e.clientWidth),
      )
      .toBe(true);
    await expect
      .poll(async () =>
        page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      )
      .toBe(true);
    await panel.screenshot({ path: info.outputPath("body-mobile.png") });
    await page.goto("/docs?doc=docs%2Fzh%2Fv2-body-tools.md");
    await expect(page.locator(".markdown .katex").first()).toBeVisible();
    expect(await page.locator(".katex-error").count()).toBe(0);
    expect(errors).toEqual([]);
  } finally {
    await page.request
      .post(`${url}/commands`, { data: { kind: "pause" }, timeout: 5000 })
      .catch(() => {});
  }
});
