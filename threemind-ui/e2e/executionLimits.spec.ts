import { test, expect } from "@playwright/test";
test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("project admission limits, real queue execution, JSON validation and concurrent edits", async ({
  page,
}, info) => {
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "执行额度验收 " + Date.now() },
    })
  ).json();
  const base = `/api/v2/projects/${project.id}`;
  const budgetUrl = `/api/v2/admin/execution/projects/${project.id}/limits`;
  try {
    await page.goto("/");
    await page
      .getByLabel("当前研究项目", { exact: true })
      .selectOption(project.id);
    await page.goto("/admin");
    const panel = page.getByLabel("执行队列与额度", { exact: true });
    const editor = panel.locator(".execution-limit-editor").filter({
      has: page.getByRole("heading", { name: "项目并发额度", exact: true }),
    });
    await expect(editor).toBeVisible();
    await editor
      .getByLabel("实验与数据处理继承部署上限", { exact: true })
      .uncheck();
    await editor
      .getByLabel("实验与数据处理并发额度", { exact: true })
      .fill("0");
    await editor
      .getByRole("button", { name: "保存执行额度", exact: true })
      .click();
    await expect
      .poll(
        async () =>
          (await (await page.request.get(base + "/execution")).json()).effective
            .runtime,
      )
      .toBe(0);
    const created = await page.request.post(base + "/runs", {
      data: {
        name: "真实队列准入验证",
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
    });
    expect(created.status()).toBe(201);
    const run = await created.json();
    await expect
      .poll(
        async () =>
          (await (await page.request.get(base + "/execution")).json()).usage
            .runtime.pending,
      )
      .toBe(1);
    expect(
      (await (await page.request.get(base + "/runs/" + run.id)).json()).status,
    ).toBe("queued");
    await editor
      .getByRole("button", { name: "切换到 JSON 编辑", exact: true })
      .click();
    const json = editor.getByRole("textbox", {
      name: "执行额度 JSON",
      exact: true,
    });
    await expect(json).toContainText('"runtime": 0');
    await json.fill('{"runtime":true,"ai":null,"notification":null}');
    await editor
      .getByRole("button", { name: "保存执行额度", exact: true })
      .click();
    await expect(editor).toContainText("Input should be a valid integer");
    expect(
      (await (await page.request.get(base + "/execution")).json()).project
        .revision,
    ).toBe(1);
    await json.fill('{"runtime":1,"ai":null,"notification":null}');
    await editor.getByRole("button", { name: "格式化", exact: true }).click();
    await editor.getByRole("button", { name: "校验", exact: true }).click();
    await expect(editor).toContainText("校验通过；尚未保存。");
    await editor
      .getByRole("button", { name: "切换到图形配置", exact: true })
      .click();
    await expect(
      editor.getByLabel("实验与数据处理并发额度", { exact: true }),
    ).toHaveValue("1");
    await editor
      .getByRole("button", { name: "保存执行额度", exact: true })
      .click();
    await expect
      .poll(
        async () =>
          (await (await page.request.get(base + "/runs/" + run.id)).json())
            .status,
      )
      .toBe("completed");
    await panel.screenshot({
      path: info.outputPath("execution-limits-desktop.png"),
    });
    await editor
      .getByLabel("实验与数据处理并发额度", { exact: true })
      .fill("2");
    const previous = (
      await (await page.request.get(base + "/execution")).json()
    ).project;
    expect(
      (
        await page.request.post(budgetUrl, {
          data: {
            limits: { runtime: 0 },
            expected_revision: previous.revision,
          },
        })
      ).status(),
    ).toBe(200);
    await expect(editor).toContainText("策略已被其他窗口修改");
    await editor
      .getByRole("button", { name: "保存执行额度", exact: true })
      .click();
    await expect(editor).toContainText("execution limits changed");
    await expect(
      editor.getByLabel("实验与数据处理并发额度", { exact: true }),
    ).toHaveValue("2");
    await editor
      .getByRole("button", { name: "重新载入已保存策略", exact: true })
      .click();
    await expect(
      editor.getByLabel("实验与数据处理并发额度", { exact: true }),
    ).toHaveValue("0");
    await editor
      .getByLabel("实验与数据处理继承部署上限", { exact: true })
      .check();
    await editor
      .getByRole("button", { name: "保存执行额度", exact: true })
      .click();
    await expect
      .poll(
        async () =>
          (await (await page.request.get(base + "/execution")).json()).project
            .limits.runtime,
      )
      .toBe(null);
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await panel.screenshot({
      path: info.outputPath("execution-limits-mobile.png"),
    });
    await page.getByLabel("切换界面语言", { exact: true }).selectOption("en");
    await expect(
      page.getByLabel("Execution queues and limits", { exact: true }),
    ).toContainText("Project concurrency limits");
    await expect(
      page.getByLabel("Execution queues and limits", { exact: true }),
    ).toContainText(
      "Execution limits saved. Active tasks continue to completion.",
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page
      .getByLabel("Execution queues and limits", { exact: true })
      .screenshot({
        path: info.outputPath("execution-limits-english-mobile.png"),
      });
    await page
      .getByLabel("Switch interface language", { exact: true })
      .selectOption("zh-CN");
    await page.goto("/settings?section=execution");
    await expect(
      page.getByRole("heading", { name: "所选项目的队列状态", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "保存执行额度", exact: true }),
    ).toHaveCount(0);
  } finally {
    const current = (await (await page.request.get(base + "/execution")).json())
      .project;
    await page.request.post(budgetUrl, {
      data: {
        limits: { runtime: null, ai: null, notification: null },
        expected_revision: current.revision,
      },
    });
  }
});
