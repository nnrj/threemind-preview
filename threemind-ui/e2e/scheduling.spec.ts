import { test, expect } from "@playwright/test";
test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("queue waiting reason, actual worker receipt and narrow layouts", async ({
  page,
}, info) => {
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "调度验收 " + Date.now() },
    })
  ).json();
  const base = `/api/v2/projects/${project.id}`;
  const budget = `/api/v2/admin/execution/projects/${project.id}/limits`;
  try {
    expect(
      (
        await page.request.post(budget, {
          data: { limits: { runtime: 0 }, expected_revision: 0 },
        })
      ).status(),
    ).toBe(200);
    const run = await (
      await page.request.post(base + "/runs", {
        data: {
          name: "调度的真实运行",
          spec: {
            environment: "replay",
            clock: "unbounded",
            duration_s: 0.03,
            replay: [
              {
                time_us: "0",
                channels: [
                  [1, 0.7],
                  [2, 0.6],
                ],
              },
            ],
          },
        },
      })
    ).json();
    await page.goto("/");
    await page
      .getByLabel("当前研究项目", { exact: true })
      .selectOption(project.id);
    await page.goto(`/runs/${run.id}`);
    const panel = page.getByRole("region", {
      name: "任务调度与执行记录",
      exact: true,
    });
    await expect(panel).toContainText("执行额度为 0，已暂停领取");
    await expect(panel).toContainText("尚未分配");
    await panel.screenshot({
      path: info.outputPath("scheduling-queued-desktop.png"),
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await panel.screenshot({
      path: info.outputPath("scheduling-queued-mobile.png"),
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(
      (
        await page.request.post(budget, {
          data: { limits: { runtime: 1 }, expected_revision: 1 },
        })
      ).status(),
    ).toBe(200);
    await expect
      .poll(
        async () =>
          (await (await page.request.get(base + "/runs/" + run.id)).json())
            .status,
      )
      .toBe("completed");
    const jobs = await (
      await page.request.get(
        base + "/execution/jobs?history=true&run_id=" + run.id,
      )
    ).json();
    const actual = jobs.rows[0];
    expect(actual.backend).toBe("native");
    expect(actual.attempts).toBe(1);
    await page.goto("/settings?section=execution");
    await panel.getByLabel("包含已结束任务", { exact: true }).check();
    await expect(panel).toContainText("任务已结束");
    await panel
      .getByRole("button", { name: "查看执行回执 (1)", exact: true })
      .click();
    await expect(panel.locator(".assignment-receipts")).toContainText(
      actual.worker_id,
    );
    await panel.getByText("领取时的能力快照", { exact: true }).click();
    await expect(panel.locator("pre")).toContainText('"backend": "native"');
    const downloadReady = page.waitForEvent("download");
    await panel
      .getByRole("link", { name: "导出执行回执", exact: true })
      .click();
    const download = await downloadReady;
    expect(download.suggestedFilename()).toBe(
      `execution-assignments-${actual.id}.json`,
    );
    const stream = await download.createReadStream();
    let content = "";
    for await (const chunk of stream!) content += chunk.toString();
    expect(JSON.parse(content)[0].worker_id).toBe(actual.worker_id);
    await page.getByLabel("切换界面语言", { exact: true }).selectOption("en");
    const english = page.getByRole("region", {
      name: "Scheduling and execution history",
      exact: true,
    });
    await expect(english).toContainText(actual.worker_id);
    await expect(english).toContainText("Actual core backend");
    await expect(english).toContainText("Consciousness run");
    await expect(english).toContainText("Consciousness core");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await english.screenshot({
      path: info.outputPath("scheduling-receipt-english-mobile.png"),
    });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page
      .getByLabel("Switch interface language", { exact: true })
      .selectOption("zh-CN");
    await panel.screenshot({
      path: info.outputPath("scheduling-receipt-desktop.png"),
    });
  } finally {
    const policy = (await (await page.request.get(base + "/execution")).json())
      .project;
    await page.request.post(budget, {
      data: {
        limits: { runtime: null, ai: null, notification: null },
        expected_revision: policy.revision,
      },
    });
  }
});
