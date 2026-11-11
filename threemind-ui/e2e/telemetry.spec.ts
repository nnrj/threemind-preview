import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("physical telemetry configuration, real sampling, evidence and mobile layout", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `物理遥测验收 ${new Date().toISOString()}` },
    })
  ).json();
  const root = `/api/v2/projects/${project.id}`;
  const created = await page.request.post(`${root}/runs`, {
    data: {
      name: "宿主真实测量与递送",
      spec: {
        environment: "manual",
        duration_s: 30,
        clock: "realtime",
        host_telemetry: { enabled: true, sample_interval_ms: 1000 },
        process_telemetry: { enabled: true, sample_interval_ms: 1000 },
        runtime_telemetry: { enabled: true, sample_interval_ms: 1000 },
      },
    },
  });
  expect(created.status()).toBe(201);
  const run = await created.json(),
    url = `${root}/runs/${run.id}`;
  await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
  await expect
    .poll(async () => (await (await page.request.get(url)).json()).status)
    .toBe("paused");
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page.goto(`/runs/${run.id}`);
  await page.getByRole("button", { name: "参数配置", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.locator(".configuration-advanced > summary").click();
  await dialog
    .getByLabel("高级参数分类", { exact: true })
    .selectOption("host_telemetry");
  await dialog.getByLabel("物理内存压力 · 增益", { exact: true }).fill("0.7");
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  const validation = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/configuration/validate"),
  );
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  expect(
    (await validation).postDataJSON().spec.host_telemetry.signals
      .memory_pressure.gain,
  ).toBe(0.7);
  await expect(dialog.locator(".configuration-success")).toContainText(
    "校验通过",
  );
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(
    dialog.getByLabel("物理内存压力 · 增益", { exact: true }),
  ).toHaveValue("0.7");
  await page.screenshot({
    path: info.outputPath("telemetry-configuration.png"),
    fullPage: false,
  });
  await dialog.getByRole("button", { name: "保存配置", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  expect(
    (await (await page.request.get(url)).json()).spec.host_telemetry.signals
      .memory_pressure.gain,
  ).toBe(0.7);
  await page.request.post(`${url}/commands`, { data: { kind: "resume" } });
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`${url}/telemetry?limit=2`)).json()).rows
          .length,
    )
    .toBe(2);
  await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
  await expect
    .poll(async () => (await (await page.request.get(url)).json()).status)
    .toBe("paused");
  await page.getByRole("button", { name: "感官与输入", exact: true }).click();
  await page.getByRole("button", { name: "物理遥测", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "物理遥测", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".telemetry-panel")).toContainText(
    "memory_pressure",
  );
  await expect(page.locator(".telemetry-panel")).toContainText(
    "thread_cpu_load",
  );
  await page
    .getByRole("combobox", { name: "遥测范围", exact: true })
    .selectOption("host");
  await expect(
    page.getByRole("heading", { name: "宿主遥测", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("telemetry-desktop.png"),
    fullPage: true,
  });
  for (const format of ["CSV", "JSONL"]) {
    const downloaded = page.waitForEvent("download");
    await page
      .getByRole("link", { name: `导出 ${format}`, exact: true })
      .click();
    expect((await downloaded).suggestedFilename()).toBe(
      `telemetry.${format.toLowerCase()}`,
    );
  }
  const csv = await (
    await page.request.get(`${url}/telemetry/export?format=csv&scope=host`)
  ).text();
  expect(csv).toContain("unavailable_reason");
  expect(csv).toContain("memory_pressure");
  await page.getByRole("button", { name: "查看递送证据", exact: true }).click();
  await expect(dialog).toContainText("sample_id");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "较早采样", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "回到最新", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "回到最新", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByLabel("筛选指标", { exact: true }).fill("内存");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("telemetry-mobile.png"),
    fullPage: true,
  });
  await page.goto("/docs?doc=docs%2Fzh%2Fv2-telemetry.md");
  await expect(
    page.getByRole("heading", {
      name: "物理遥测、实例执行计量与递送证据",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.locator(".katex").first()).toBeVisible();
  await expect(page.locator(".katex-error")).toHaveCount(0);
  expect(errors).toEqual([]);
});
