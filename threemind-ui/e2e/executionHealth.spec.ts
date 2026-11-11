import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("optional execution health: dual configuration, sampled evidence, no model changes", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "执行监测工程验收 " + Date.now() },
    })
  ).json();
  const root = "/api/v2/projects/" + project.id,
    base = root + "/notifications";
  const run = async () => {
    const response = await page.request.post(root + "/runs", {
      data: {
        name: "固定刺激对照",
        spec: {
          environment: "replay",
          clock: "unbounded",
          duration_s: 0.01,
          replay: [
            {
              time_us: "0",
              channels: [
                [1, 0.5],
                [2, 0.3],
              ],
            },
          ],
        },
      },
    });
    expect(response.ok()).toBeTruthy();
    const value = await response.json();
    await expect
      .poll(
        async () =>
          (await (await page.request.get(root + "/runs/" + value.id)).json())
            .status,
      )
      .toBe("completed");
    return (await (await page.request.get(root + "/runs/" + value.id)).json())
      .state_hash;
  };
  const initial = await (await page.request.get(base + "/settings")).json();
  expect(initial.config.execution_health.enabled).toBe(false);
  const baseline = await run();
  try {
    await page.goto("/");
    await page
      .getByLabel("当前研究项目", { exact: true })
      .selectOption(project.id);
    await page.goto("/settings?section=notifications");
    const editor = page.locator("form.notification-policy");
    await expect(
      page.getByText("执行预警当前关闭；项目所有者可在通知规则中开启。", {
        exact: true,
      }),
    ).toBeVisible();
    await editor.getByLabel("启用项目通知", { exact: true }).check();
    await editor.getByLabel("启用可配置执行预警", { exact: true }).check();
    const advanced = editor.locator("details").filter({
      has: page.locator("summary", { hasText: "高级：编辑执行预警规则" }),
    });
    await expect(advanced).not.toHaveAttribute("open", "");
    await advanced.locator("summary").click();
    await editor
      .getByLabel("规则名称", { exact: true })
      .first()
      .fill("工程验收条件：零等待也命中，并非故障");
    await editor.getByLabel("触发阈值", { exact: true }).first().fill("0");
    await editor
      .getByLabel("持续采样时长（秒）", { exact: true })
      .first()
      .fill("0");
    const enabled = editor.getByLabel("启用此规则", { exact: true });
    for (let i = 1; i < (await enabled.count()); i++)
      await enabled.nth(i).uncheck();
    await editor
      .getByRole("button", { name: "切换到 JSON 编辑", exact: true })
      .click();
    const validating = page.waitForRequest(
      (request) =>
        request.url().endsWith(base + "/validate") &&
        request.method() === "POST",
    );
    await editor.getByRole("button", { name: "校验", exact: true }).click();
    const config = (await validating).postDataJSON();
    await expect(
      page.getByText("配置校验通过。", { exact: true }),
    ).toBeVisible();
    expect(config.execution_health.rules[0].threshold).toBe(0);
    expect(config.execution_health.enabled).toBe(true);
    await editor.locator(".cm-content").fill(
      JSON.stringify({
        ...config,
        execution_health: {
          ...config.execution_health,
          rules: [
            {
              ...config.execution_health.rules[0],
              metric: "imaginary_intent",
            },
          ],
        },
      }),
    );
    await editor
      .getByRole("button", { name: "保存通知设置", exact: true })
      .click();
    await expect(page.getByRole("alert")).toBeVisible();
    expect(
      (await (await page.request.get(base + "/settings")).json()).revision,
    ).toBe(0);
    await editor.locator(".cm-content").fill(JSON.stringify(config));
    await editor.getByRole("button", { name: "格式化", exact: true }).click();
    await editor.getByRole("button", { name: "校验", exact: true }).click();
    await expect(
      page.getByText("配置校验通过。", { exact: true }),
    ).toBeVisible();
    await editor
      .getByRole("button", { name: "切换到图形配置", exact: true })
      .click();
    await expect(
      editor.getByLabel("启用可配置执行预警", { exact: true }),
    ).toBeChecked();
    await editor
      .getByRole("button", { name: "保存通知设置", exact: true })
      .click();
    await expect(
      page.getByText("通知设置已保存。", { exact: true }),
    ).toBeVisible();
    const monitor = page.getByRole("region", {
      name: "执行资源与进度监测",
      exact: true,
    });
    await expect(monitor).toContainText("waiting · 条件成立");
    const downloadPromise = page.waitForEvent("download");
    await monitor
      .getByRole("button", { name: "导出本次执行观测", exact: true })
      .click();
    const downloaded = await downloadPromise;
    const evidence = JSON.parse(
      await readFile((await downloaded.path())!, "utf8"),
    );
    expect(evidence.monitor.snapshot.metrics.ready_wait_s.ready_tasks).toBe(0);
    expect(evidence.monitor.snapshot.metrics.worker_rss_mib.applicable).toBe(
      false,
    );
    expect(evidence.monitor.policy_revision).toBe(1);
    expect(await run()).toBe(baseline);
    await page.getByRole("button", { name: "通知记录", exact: true }).click();
    await expect(page.locator(".notification-list")).toContainText(
      "执行资源或进度预警",
    );
    await expect(page.locator(".notification-list")).toContainText(
      "工程验收条件：零等待也命中，并非故障",
    );
    await page.screenshot({
      path: info.outputPath("execution-health-desktop.png"),
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath("execution-health-mobile.png"),
      fullPage: true,
    });
    expect(errors).toEqual([]);
  } finally {
    const current = await (await page.request.get(base + "/settings")).json();
    await page.request.put(base + "/settings", {
      data: {
        expected_revision: current.revision,
        config: { ...current.config, enabled: false, email_enabled: false },
      },
    });
  }
});
