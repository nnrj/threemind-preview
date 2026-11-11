import { expect, test } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_ROBOT_PROJECT,
  "Requires isolated robot fixture",
);
test.use({ actionTimeout: 15000 });
for (const width of [1440, 390]) {
  test(`robot task controls and scene ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 960 });
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const project = process.env.THREEMIND_ROBOT_PROJECT!,
      run = process.env.THREEMIND_ROBOT_RUN!;
    await page.goto("/");
    if (width < 700) {
      await page
        .getByRole("button", { name: "切换研究项目", exact: true })
        .click();
      await page
        .getByRole("dialog")
        .getByRole("combobox")
        .selectOption(project);
    } else
      await page
        .getByLabel("当前研究项目", { exact: true })
        .selectOption(project);
    await page.goto("/worlds?view=robots");
    if (width < 700)
      await page.getByRole("tab", { name: "配置", exact: true }).click();
    await expect(page.getByLabel("任务名称", { exact: true })).toBeVisible();
    await page.getByLabel("任务名称", { exact: true }).fill(`UI arm ${width}`);
    await page
      .getByRole("combobox", { name: "控制模式", exact: true })
      .selectOption("velocity");
    await page
      .getByRole("button", { name: "切换到 JSON 编辑", exact: true })
      .click();
    await page
      .getByRole("button", { name: "切换到图形配置", exact: true })
      .click();
    await expect(
      page.getByRole("combobox", { name: "控制模式", exact: true }),
    ).toHaveValue("velocity");
    await page.getByRole("button", { name: "校验与预览", exact: true }).click();
    await expect(page.locator(".world-scene canvas")).toBeVisible();
    await page.screenshot({
      path: info.outputPath(`robot-preview-${width}.png`),
      fullPage: true,
    });
    if (width < 700)
      await page.getByRole("tab", { name: "配置", exact: true }).click();
    await page
      .getByRole("button", { name: "保存任务版本", exact: true })
      .click();
    await expect(
      page.getByText("任务版本已保存。", { exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "创建意识并接入", exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByLabel("内核版本", { exact: true })).toHaveValue(
      "threemind.continuous-memory/2",
    );
    await dialog
      .getByRole("button", { name: "创建并开始", exact: true })
      .click();
    await expect(dialog).toBeHidden();
    await expect(page).toHaveURL(/run=/);
    const created = new URL(page.url()).searchParams.get("run")!;
    await expect(page.locator(".world-scene canvas")).toBeVisible();
    await page.request.post(
      `/api/v2/projects/${project}/runs/${created}/commands`,
      { data: { kind: "cancel" } },
    );
    await page.goto(`/worlds?view=robots&run=${run}`);
    await page.getByText("人工干预与快照", { exact: true }).click();
    await page.getByLabel("力（N） X", { exact: true }).fill("0.1");
    await page.getByRole("button", { name: "提交干预", exact: true }).click();
    await expect(
      page.getByRole("status").filter({ hasText: "收据" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "单步", exact: true }).click();
    await expect
      .poll(
        async () =>
          (
            await (
              await page.request.get(`/api/v2/projects/${project}/runs/${run}`)
            ).json()
          ).time_us,
      )
      .not.toBe("0");
    await page
      .getByRole("button", { name: "保存完整快照", exact: true })
      .click();
    await expect(page.locator(".world-scene canvas")).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: info.outputPath(`robot-running-${width}.png`),
      fullPage: true,
    });
    if (width < 700)
      await page.getByRole("tab", { name: "感官与动作", exact: true }).click();
    await expect(
      page.getByRole("columnheader", { name: "实际施力", exact: true }),
    ).toBeVisible();
    await page.goto("/worlds?view=robots");
    if (width < 700)
      await page.getByRole("tab", { name: "配置", exact: true }).click();
    await page
      .getByRole("combobox", { name: "选择机器人模板", exact: true })
      .selectOption("playground-panda");
    await expect(page.getByRole("combobox", { name: /^计算后端/ })).toHaveValue(
      "jax/cpu",
    );
    await expect(page.getByLabel("控制模式", { exact: true })).toHaveCount(0);
    await page.getByLabel("感官输入强度", { exact: true }).fill("0.5");
    await page
      .getByRole("button", { name: "切换到 JSON 编辑", exact: true })
      .click();
    await page
      .getByRole("button", { name: "切换到图形配置", exact: true })
      .click();
    await expect(page.getByLabel("感官输入强度", { exact: true })).toHaveValue(
      "0.5",
    );
    await page.getByRole("button", { name: "校验与预览", exact: true }).click();
    if (width < 700)
      await page.getByRole("tab", { name: "配置", exact: true }).click();
    await page
      .getByRole("button", { name: "保存任务版本", exact: true })
      .click();
    await expect(
      page.getByText("任务版本已保存。", { exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: info.outputPath(`playground-config-${width}.png`),
      fullPage: true,
    });
    expect(errors).toEqual([]);
  });
}
