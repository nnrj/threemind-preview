import { expect, test } from "@playwright/test";
test.skip(
  !process.env.THREEMIND_LANGUAGE_PROJECT,
  "Requires isolated language fixture",
);
test.use({ actionTimeout: 15000 });
for (const width of [1440, 390]) {
  test(`dialogue routes, raw readouts and training ${width}`, async ({
    page,
  }, info) => {
    test.setTimeout(100000);
    await page.setViewportSize({ width, height: 960 });
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto("/");
    if (width < 700) {
      await page
        .getByRole("button", { name: "切换研究项目", exact: true })
        .click();
      await page
        .getByRole("dialog")
        .getByRole("combobox")
        .selectOption(process.env.THREEMIND_LANGUAGE_PROJECT!);
    } else
      await page
        .getByLabel("当前研究项目", { exact: true })
        .selectOption(process.env.THREEMIND_LANGUAGE_PROJECT!);
    await page.goto("/dialogue");
    await page.getByRole("button", { name: "创建意识", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await dialog
      .getByLabel("意识名称", { exact: true })
      .fill(`Scratch ${width}`);
    await dialog
      .getByRole("combobox", { name: "输入路径", exact: true })
      .selectOption("scratch");
    await dialog
      .getByRole("combobox", { name: "输出路径", exact: true })
      .selectOption("scratch");
    await dialog
      .getByLabel("活动转换特征", { exact: true })
      .selectOption("unsigned-peak");
    await dialog
      .getByRole("button", { name: "JSON 编辑", exact: true })
      .click();
    await dialog.getByRole("button", { name: "图形配置", exact: true }).click();
    await expect(
      dialog.getByRole("combobox", { name: "输入路径", exact: true }),
    ).toHaveValue("scratch");
    await expect(
      dialog.getByLabel("活动转换特征", { exact: true }),
    ).toHaveValue("unsigned-peak");
    await page.screenshot({
      path: info.outputPath(`dialogue-config-${width}.png`),
      fullPage: true,
    });
    await dialog.getByRole("button", { name: "创建意识", exact: true }).click();
    await expect(dialog).toBeHidden();
    await expect(page).toHaveURL(/run=/);
    const input = page.getByRole("textbox", { name: "文本刺激", exact: true });
    await input.fill("甲是松子。");
    const send = page.getByRole("button", { name: "发送", exact: true });
    await expect(send).toBeEnabled({ timeout: 25000 });
    await send.click();
    await expect(input).toHaveValue("");
    await expect(page.locator(".language-message.input")).toContainText(
      "甲是松子。",
    );
    await expect(page.locator(".language-activities span").first()).toBeVisible(
      { timeout: 45000 },
    );
    await expect(
      page.getByText("尚未训练活动到语言的映射，请在训练转换器中校准。", {
        exact: true,
      }),
    ).toBeVisible();
    await page.screenshot({
      path: info.outputPath(`dialogue-running-${width}.png`),
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "连续观察内部活动", exact: true })
      .click();
    await expect(
      page.getByText("无新输入 · 内部活动观察", { exact: true }).first(),
    ).toBeVisible({ timeout: 30000 });
    const stop = page.getByRole("button", { name: "停止观察", exact: true });
    if (await stop.isVisible()) await stop.click();
    await expect(
      page.getByRole("button", { name: "连续观察内部活动", exact: true }),
    ).toBeVisible();
    await expect(page.locator(".language-message.input").first()).toContainText(
      "甲是松子。",
    );
    await page.screenshot({
      path: info.outputPath(`dialogue-observation-${width}.png`),
      fullPage: true,
    });
    await page.getByRole("tab", { name: "训练转换器", exact: true }).click();
    await page.getByLabel("训练步数", { exact: true }).fill("2");
    await page
      .getByRole("button", { name: "训练并保存新版本", exact: true })
      .click();
    await page.getByRole("tab", { name: "版本与证据", exact: true }).click();
    await expect(
      page
        .getByRole("link", {
          name: "language-scratch.safetensors",
          exact: true,
        })
        .first(),
    ).toBeVisible({ timeout: 45000 });
    await expect(
      page.getByRole("link", { name: /下载完整过程/ }).first(),
    ).toBeVisible();
    const download = page.waitForEvent("download");
    await page
      .getByRole("link", { name: "导出完整语言意识", exact: true })
      .click();
    const file = await download;
    const path = info.outputPath(`language-${width}.tmlanguage`);
    await file.saveAs(path);
    const original = page.url();
    await page
      .getByLabel("导入完整语言意识", { exact: true })
      .setInputFiles(path);
    await expect(page).not.toHaveURL(original);
    await expect(
      page.getByRole("link", { name: "导出完整语言意识", exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 2,
      ),
    ).toBeTruthy();
    expect(errors).toEqual([]);
  });
}
