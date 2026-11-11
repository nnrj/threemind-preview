import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("graphical configuration, JSON validation, paused editing and project defaults", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByRole("button", { name: "新建研究项目", exact: true }).click();
  await page
    .getByLabel("项目名称", { exact: true })
    .fill(`配置完整性验收 ${new Date().toISOString()}`);
  await page.getByRole("button", { name: "创建项目", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建意识", exact: true })
    .click();
  await page.getByLabel("意识名称").fill("双模式配置验证");
  const duration = page.getByLabel("运行时长（模拟秒）", { exact: true });
  await expect(duration).toHaveValue("");
  await expect(duration).toHaveAttribute("placeholder", "持续运行（无限）");
  await duration.fill("120");
  await page.getByRole("button", { name: "切换到 JSON", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "JSON 参数", exact: true }),
  ).toContainText('"duration_s": 120');
  await page
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await duration.fill("");
  await expect(page.getByLabel("持续可塑性", { exact: true })).toBeChecked();
  await expect(page.locator(".configuration-advanced")).not.toHaveAttribute(
    "open",
  );
  await page
    .getByLabel("环境与感官来源", { exact: true })
    .selectOption("manual");
  await page.screenshot({
    path: info.outputPath("configuration-basic.png"),
    fullPage: false,
  });
  await page.locator(".configuration-advanced > summary").click();
  await page.getByLabel("联想传播速率", { exact: true }).fill("6.5");
  await page.getByLabel("激活衰减时间常数", { exact: true }).fill("0.42");
  await expect(page.locator('[data-parameter="config.step_us"]')).toContainText(
    "创建后不可更改",
  );
  await page.screenshot({
    path: info.outputPath("configuration-graphical.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "切换到 JSON", exact: true }).click();
  const editor = page.getByRole("textbox", { name: "JSON 参数", exact: true });
  await expect(editor).toBeVisible();
  await expect(page.locator(".cm-lineNumbers")).toBeVisible();
  const schema = await (await page.request.get("/api/v2/configuration")).json();
  expect(schema.defaults.duration_s).toBeNull();
  await expect(editor).toContainText('"duration_s": null');
  let spec = {
    ...schema.defaults,
    environment: "manual",
    config: {
      ...schema.defaults.config,
      propagation_rate: 6.5,
      activation_tau: 0.42,
    },
  };
  await expect(editor).toContainText('"propagation_rate": 6.5');
  await expect(editor).toContainText('"activation_tau": 0.42');
  await editor.fill('{"config": {"plasticity": true, "plasticity": false}}');
  await page.getByRole("button", { name: "格式化", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("重复");
  spec.config.learning_rate = 0.013;
  await editor.fill(JSON.stringify(spec));
  await page.getByRole("button", { name: "格式化", exact: true }).click();
  await page.getByRole("button", { name: "校验", exact: true }).click();
  await expect(page.locator(".configuration-success")).toContainText(
    "校验通过",
  );
  await page.screenshot({
    path: info.outputPath("configuration-json.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(page.getByLabel("连接学习率", { exact: true })).toHaveValue(
    "0.013",
  );
  // Long channel lists remain graphically editable instead of forcing JSON after the first page.
  await page.getByRole("button", { name: "切换到 JSON", exact: true }).click();
  await editor.fill(
    JSON.stringify({
      ...spec,
      replay: [
        {
          time_us: "0",
          channels: Array.from({ length: 40 }, (_, i) => [i, 0.5]),
          intensity: 1,
        },
      ],
    }),
  );
  await page
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await page.getByText("帧 1 · 0 μs · 40 通道", { exact: true }).click();
  await page.getByRole("button", { name: "下一组", exact: true }).click();
  await page.getByRole("button", { name: "下一组", exact: true }).click();
  await page.getByLabel("幅度 · 40", { exact: true }).fill("0.37");
  await page.getByRole("button", { name: "切换到 JSON", exact: true }).click();
  await page
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await page.getByText("帧 1 · 0 μs · 40 通道", { exact: true }).click();
  await page.getByRole("button", { name: "下一组", exact: true }).click();
  await page.getByRole("button", { name: "下一组", exact: true }).click();
  await expect(page.getByLabel("幅度 · 40", { exact: true })).toHaveValue(
    "0.37",
  );
  await page.getByRole("button", { name: "切换到 JSON", exact: true }).click();
  await editor.fill(JSON.stringify(spec));
  await page
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await page.getByRole("button", { name: "创建并开始", exact: true }).click();
  await expect(page).toHaveURL(/\/runs\//);
  const runURL = page.url();
  await page.getByRole("button", { name: "暂停", exact: true }).click();
  await expect(page.locator(".page-actions .badge")).toContainText("已暂停");
  await page.getByRole("button", { name: "参数配置", exact: true }).click();
  await page.locator(".configuration-advanced > summary").click();
  await expect(page.getByLabel("数值步长", { exact: true })).toHaveAttribute(
    "readonly",
  );
  await page.getByRole("button", { name: "切换到 JSON", exact: true }).click();
  spec.config.step_us = 20000;
  await editor.fill(JSON.stringify(spec));
  // Save must validate even when the user never presses Validate.
  await page.getByRole("button", { name: "保存配置", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("config.step_us");
  await expect(page.getByRole("alert")).toContainText("创建后不可修改");
  await page
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(editor).toBeVisible(); // invalid content is retained, not silently reset
  spec.config.step_us = 10000;
  spec.config.propagation_rate = 3.75;
  await editor.fill(JSON.stringify(spec));
  await page
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(page.getByLabel("联想传播速率", { exact: true })).toHaveValue(
    "3.75",
  );
  await page.getByRole("button", { name: "保存配置", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "因果事件", exact: true }).click();
  await expect(page.locator(".event-list")).toContainText(
    "configuration_changed",
  );
  await page.getByRole("link", { name: "设置", exact: true }).click();
  await page.getByRole("button", { name: "项目默认参数", exact: true }).click();
  await page.locator(".configuration-advanced > summary").click();
  await page.getByLabel("联想传播速率", { exact: true }).fill("9.25");
  await page
    .getByRole("button", { name: "保存项目默认配置", exact: true })
    .click();
  await expect(
    page.getByText("项目默认配置已保存，仅用于以后新建的意识。", {
      exact: true,
    }),
  ).toBeVisible();
  // Another window's saved version must not overwrite an unsaved draft.
  const other = await page.context().newPage();
  other.on("pageerror", (error) => errors.push(error.message));
  await other.goto("/settings");
  await other
    .getByRole("button", { name: "项目默认参数", exact: true })
    .click();
  await other.locator(".configuration-advanced > summary").click();
  await expect(other.getByLabel("联想传播速率", { exact: true })).toHaveValue(
    "9.25",
  );
  await other.getByLabel("联想传播速率", { exact: true }).fill("11.5");
  await page.getByLabel("联想传播速率", { exact: true }).fill("9.75");
  const firstUpdate = page.waitForResponse(
    (response) =>
      response.request().method() === "PUT" &&
      response.url().endsWith("/configuration/defaults"),
  );
  await page
    .getByRole("button", { name: "保存项目默认配置", exact: true })
    .click();
  expect((await firstUpdate).status()).toBe(200);
  await other
    .getByRole("banner")
    .getByRole("button", { name: "新建意识", exact: true })
    .click();
  await other
    .getByRole("dialog")
    .getByRole("button", { name: "取消", exact: true })
    .click();
  await other
    .getByRole("button", { name: "保存项目默认配置", exact: true })
    .click();
  await expect(other.getByRole("alert")).toContainText("项目默认配置已更新");
  await expect(other.getByLabel("联想传播速率", { exact: true })).toHaveValue(
    "11.5",
  );
  await other
    .getByRole("button", { name: "重新载入配置", exact: true })
    .click();
  await expect(other.getByLabel("联想传播速率", { exact: true })).toHaveValue(
    "9.75",
  );
  await other.close();
  await page.getByLabel("联想传播速率", { exact: true }).fill("9.25");
  const restoredDefault = page.waitForResponse(
    (response) =>
      response.request().method() === "PUT" &&
      response.url().endsWith("/configuration/defaults"),
  );
  await page
    .getByRole("button", { name: "保存项目默认配置", exact: true })
    .click();
  expect((await restoredDefault).status()).toBe(200);
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建意识", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .locator(".configuration-advanced > summary")
    .click();
  await expect(
    page.getByRole("dialog").getByLabel("联想传播速率", { exact: true }),
  ).toHaveValue("9.25");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(
    await page
      .getByRole("dialog")
      .evaluate((el) => el.scrollWidth <= el.clientWidth + 1),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("configuration-mobile.png"),
    fullPage: false,
  });
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "取消", exact: true })
    .click();
  await page.goto(runURL);
  await page.getByRole("button", { name: "参数配置", exact: true }).click();
  await page.locator(".configuration-advanced > summary").click();
  await expect(page.getByLabel("联想传播速率", { exact: true })).toHaveValue(
    "3.75",
  );
  expect(errors).toEqual([]);
});
