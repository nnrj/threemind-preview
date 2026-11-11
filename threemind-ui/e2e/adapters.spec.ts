import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("adapter contracts, scoped capability reports and contextual configuration", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.addInitScript(() => {
    (window as any).__captureCalls = 0;
    if (navigator.mediaDevices) {
      navigator.mediaDevices.getUserMedia = async () => {
        (window as any).__captureCalls++;
        throw new Error("Capability inspection must not capture devices");
      };
    }
  });
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `适配器验收 ${new Date().toISOString()}` },
    })
  ).json();
  const run = await (
    await page.request.post(`/api/v2/projects/${project.id}/runs`, {
      data: {
        name: "设备能力与参数验收",
        spec: {
          environment: "manual",
          clock: "realtime",
          duration_s: 180,
          checkpoint_us: 500000,
          body_filter: { enabled: true },
        },
      },
    })
  ).json();
  const url = `/api/v2/projects/${project.id}/runs/${run.id}`;
  try {
    await expect
      .poll(async () => (await (await page.request.get(url)).json()).status)
      .toBe("running");
    await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
    await expect
      .poll(async () => (await (await page.request.get(url)).json()).status)
      .toBe("paused");
    await page.goto("/");
    await page
      .getByLabel("当前研究项目", { exact: true })
      .selectOption(project.id);
    await page.goto("/settings");
    await page
      .getByRole("button", { name: "设备与适配器", exact: true })
      .click();
    const panel = page.getByRole("region", {
      name: "设备与适配器",
      exact: true,
    });
    await expect(
      panel.getByRole("heading", {
        name: "接口服务：文件与网络接入",
        exact: true,
      }),
    ).toBeVisible();
    await panel
      .getByRole("button", { name: "检查当前浏览器能力", exact: true })
      .click();
    await expect(
      panel.getByText("网络图形渲染", { exact: true }),
    ).toBeVisible();
    expect(await page.evaluate(() => (window as any).__captureCalls)).toBe(0);
    const coreWorker = panel
      .locator(".worker-capability")
      .filter({ has: page.getByText("运行内核", { exact: true }) })
      .first();
    await expect(coreWorker).toBeVisible();
    await coreWorker.locator("summary").first().click();
    await expect(
      coreWorker.getByText("运行内核", { exact: true }),
    ).toBeVisible();
    await panel.screenshot({
      path: info.outputPath("capabilities-desktop.png"),
    });
    await panel
      .getByRole("button", { name: "适配器目录", exact: true })
      .click();
    await panel
      .getByLabel("查看意识绑定", { exact: true })
      .selectOption(run.id);
    let catalogue = page.getByRole("region", {
      name: "适配器目录",
      exact: true,
    });
    await catalogue
      .getByLabel("搜索适配器或参数", { exact: true })
      .fill("body-filter");
    await expect(catalogue.locator(".adapter-card")).toHaveCount(1);
    await expect(catalogue).toContainText("仅适用于模拟物理／合成环境");
    await catalogue
      .getByLabel("搜索适配器或参数", { exact: true })
      .fill("文本感官增益");
    await catalogue
      .getByRole("link", { name: "配置文本感官", exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByLabel("高级参数分类", { exact: true }),
    ).toHaveValue("text");
    await expect(
      dialog.getByLabel("文本帧间隔", { exact: true }),
    ).toBeVisible();
    await expect(
      dialog.getByLabel("分布式感受通道数", { exact: true }),
    ).toHaveAttribute("readonly", "");
    await dialog.getByLabel("文本感官增益", { exact: true }).fill("0.75");
    await dialog.getByRole("button", { name: "保存配置", exact: true }).click();
    await expect(dialog).toBeHidden();
    expect(
      (await (await page.request.get(url)).json()).spec.text_sensor.gain,
    ).toBe(0.75);
    await page.goto(`/runs/${run.id}?view=inputs&tool=catalogue`);
    catalogue = page.getByRole("region", { name: "适配器目录", exact: true });
    await catalogue
      .getByLabel("搜索适配器或参数", { exact: true })
      .fill("text-sensor");
    await catalogue
      .getByText("参数与不可变规则（8 项）", { exact: true })
      .click();
    await expect(catalogue.locator("tbody")).toContainText("0.75");
    await catalogue
      .getByLabel("搜索适配器或参数", { exact: true })
      .fill("听觉感官");
    await catalogue.screenshot({
      path: info.outputPath("adapters-desktop.png"),
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(350);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await catalogue.screenshot({
      path: info.outputPath("adapters-mobile.png"),
    });
    await catalogue
      .getByRole("link", { name: "打开听觉感官工具", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "音视频与图片输入", exact: true }),
    ).toBeVisible();
    await page.goto(`/runs/${run.id}?view=readouts`);
    await expect(
      page.getByRole("heading", { name: "读出与响应", exact: true }),
    ).toBeVisible();
    await page.goto("/docs?doc=docs%2Fzh%2Fv2-adapters-and-capabilities.md");
    await expect(page.locator(".markdown h1")).toHaveText(
      "适配器目录、设备能力与配置边界",
    );
    expect(errors).toEqual([]);
  } finally {
    await page.request
      .post(`${url}/commands`, { data: { kind: "pause" }, timeout: 5000 })
      .catch(() => {});
  }
});
