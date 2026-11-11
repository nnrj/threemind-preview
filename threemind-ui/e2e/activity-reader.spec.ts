import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_ACTIVITY_RUN,
  "Requires the dedicated seeded activity-reader fixture.",
);

for (const width of [1440, 390]) {
  test(`activity analyses and evidence at ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 950 });
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const project = process.env.THREEMIND_ACTIVITY_PROJECT!;
    const run = process.env.THREEMIND_ACTIVITY_RUN!;
    await page.goto("/");
    if (width < 700) {
      await page
        .getByRole("button", { name: "切换研究项目", exact: true })
        .click();
      await page
        .getByRole("dialog")
        .getByRole("combobox")
        .selectOption(project);
    } else {
      await page
        .getByLabel("当前研究项目", { exact: true })
        .selectOption(project);
    }
    const history = await (
      await page.request.get(
        `/api/v2/projects/${project}/runs/${run}/readouts?kind=temporal_readout`,
      )
    ).json();
    const primary = history.rows.find(
      (row: any) => row.payload.analysis_schema,
    );
    expect(history.rows.length).toBe(2);
    expect(primary).toBeTruthy();
    expect(primary.payload.process.raw_activity_seen).toBe(true);
    await page.goto(`/runs/${run}?view=readouts&record=${primary.id}`);
    await expect(
      page
        .locator(".activity-analysis-facts")
        .getByText("响应模式收敛", { exact: true }),
    ).toBeVisible();
    await expect(
      page
        .locator(".activity-analysis-facts")
        .getByText("幅度变化", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("columnheader", { name: "判定时激活", exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "展开过程分析", exact: true })
      .click();
    await expect(
      page.getByRole("columnheader", { name: "峰值时刻（秒）", exact: true }),
    ).toBeVisible();
    await page.getByText("对照另一条完整轨迹", { exact: true }).click();
    await page
      .getByLabel("对照证据编号", { exact: true })
      .fill(String(primary.id));
    await page.getByRole("button", { name: "比较过程", exact: true }).click();
    await expect(page.getByText(/匹配采样.*变化节点.*0/)).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: info.outputPath(`activity-${width}.png`),
      fullPage: true,
    });
    const chat = await (
      await page.request.get(
        `/api/v2/projects/${project}/runs/${run}/conversation?passive=false`,
      )
    ).json();
    expect(chat.rows.length).toBe(1);
    expect(chat.rows[0].readout.display.text).toContain("甲");
    expect(chat.rows[0].readout.analyses.pattern.status).toBe("converged");
    expect(chat.rows[0].readout.process.raw_activity_seen).toBe(true);
    await page.goto("/");
    await page
      .getByRole("banner")
      .getByRole("button", { name: "新建意识", exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByLabel("内核版本", { exact: true })).toHaveValue(
      "threemind.continuous-memory/2",
    );
    await dialog.locator(".configuration-advanced > summary").click();
    await dialog
      .getByLabel("搜索高级参数", { exact: true })
      .fill("局部新颖性结算");
    const novelty = dialog.getByLabel("局部新颖性结算", { exact: true });
    await expect(novelty).toHaveValue("arrival-window");
    await novelty.selectOption("immediate");
    await dialog
      .getByRole("button", { name: "切换到 JSON", exact: true })
      .click();
    const editor = dialog.getByRole("textbox", {
      name: "JSON 参数",
      exact: true,
    });
    // CodeMirror mounts only visible lines. Inspect the actual validation
    // request so the assertion covers the complete JSON document.
    const validation = page.waitForRequest(
      (request) =>
        request.method() === "POST" &&
        request.url().endsWith("/configuration/validate"),
    );
    await dialog.getByRole("button", { name: "校验", exact: true }).click();
    const config = (await validation).postDataJSON().spec;
    expect(config.activity_readout.analysis_version).toBe(2);
    expect(config.config.novelty_mode).toBe("immediate");
    config.config.novelty_mode = "arrival-window";
    await editor.press("Control+Home");
    await editor.press("Control+a");
    await page.keyboard.insertText(JSON.stringify(config));
    await dialog.getByRole("button", { name: "格式化", exact: true }).click();
    await dialog.getByRole("button", { name: "校验", exact: true }).click();
    await expect(
      dialog.getByText("校验通过：类型、范围、关联条件与不可变参数均已检查。", {
        exact: true,
      }),
    ).toBeVisible();
    await dialog
      .getByRole("button", { name: "切换到图形配置", exact: true })
      .click();
    await expect(novelty).toHaveValue("arrival-window");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: info.outputPath(`configuration-${width}.png`),
      fullPage: true,
    });
    await dialog.getByRole("button", { name: "取消", exact: true }).click();
    expect(errors).toEqual([]);
  });
}
