import { test, expect } from "@playwright/test";
test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);
test.use({ locale: "en-US" });

test("language changes preserve unsaved user text and device configuration", async ({
  page,
}, info) => {
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "设置 {count}" },
    })
  ).json();
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page.goto("/settings");
  const before = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("tm2.preferences") ?? "{}"),
  );
  await page.getByRole("button", { name: "新建研究项目", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByLabel("项目名称", { exact: true })
    .fill("原始名称 {name}");
  // Model a preference changed by another tab while this unsaved dialog stays open.
  await page.evaluate(() => {
    const value = {
      ...JSON.parse(localStorage.getItem("tm2.preferences") ?? "{}"),
      locale: "en",
    };
    localStorage.setItem("tm2.preferences", JSON.stringify(value));
    dispatchEvent(
      new StorageEvent("storage", {
        key: "tm2.preferences",
        newValue: JSON.stringify(value),
      }),
    );
  });
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("Project name", { exact: true })).toHaveValue(
    "原始名称 {name}",
  );
  await dialog.getByLabel("Close", { exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Settings", exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByLabel("Current project", { exact: true })
      .locator("option:checked"),
  ).toHaveText("设置 {count}");
  await expect(
    page.getByLabel("Interface language", { exact: true }),
  ).toHaveValue("en");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Settings", exact: true }),
  ).toBeVisible();
  const after = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("tm2.preferences") ?? "{}"),
  );
  for (const key of Object.keys(before).filter((key) => key !== "locale"))
    expect(after[key]).toEqual(before[key]);
  await page.screenshot({
    path: info.outputPath("language-settings-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("language-settings-mobile.png"),
    fullPage: true,
  });
  await page
    .getByLabel("Switch interface language", { exact: true })
    .selectOption("zh-CN");
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await expect(
    page.getByRole("heading", { name: "设置", exact: true }),
  ).toBeVisible();
  await page.getByLabel("切换界面语言", { exact: true }).selectOption("auto");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
});

test("English parameter search and JSON locale changes preserve scientific values and undo", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "语言验证 · 原始项目" },
    })
  ).json();
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page.getByLabel("切换界面语言", { exact: true }).selectOption("en");
  await page
    .getByRole("banner")
    .getByRole("button", { name: "New run", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Run name", { exact: true })
    .fill("不要翻译：设置 {value0}");
  await expect(
    dialog.getByLabel("Continuous plasticity", { exact: true }),
  ).toBeChecked();
  await expect(dialog.locator(".configuration-advanced")).not.toHaveAttribute(
    "open",
  );
  await dialog
    .getByLabel("Environment and sensory source", { exact: true })
    .selectOption("manual");
  await dialog.locator(".configuration-advanced > summary").click();
  await dialog
    .getByLabel("Search advanced parameters", { exact: true })
    .fill("propagation delay");
  await dialog
    .getByLabel("Causal propagation delay", { exact: true })
    .fill("30000");
  await dialog
    .getByLabel("Search advanced parameters", { exact: true })
    .fill("");
  await expect(
    dialog.locator('[data-parameter="config.step_us"]'),
  ).toContainText("Fixed after creation");
  await dialog.getByRole("button", { name: "Edit JSON", exact: true }).click();
  let editor = dialog.getByRole("textbox", {
    name: "JSON parameters",
    exact: true,
  });
  await expect(editor).toContainText('"delay_us": 30000');
  const draft =
    '{"environment":"manual","config":{"delay_us":30000,"learning_rate":0.019}}';
  await editor.fill(draft);
  await editor.evaluate((el) => {
    (el as HTMLElement).dataset.localeWitness = "same-editor";
  });
  await editor.press("Control+End");
  await editor.press("Space");
  const beforeUndo = await editor.textContent();
  await editor.press("Control+f");
  await dialog.getByPlaceholder("Find", { exact: true }).fill("learning_rate");
  await page.evaluate(() => {
    const current = JSON.parse(localStorage.getItem("tm2.preferences") ?? "{}");
    const value = JSON.stringify({ ...current, locale: "zh-CN" });
    localStorage.setItem("tm2.preferences", value);
    dispatchEvent(
      new StorageEvent("storage", { key: "tm2.preferences", newValue: value }),
    );
  });
  editor = dialog.getByRole("textbox", { name: "JSON 参数", exact: true });
  await expect(editor).toHaveAttribute("data-locale-witness", "same-editor");
  await expect(dialog.getByPlaceholder("查找", { exact: true })).toHaveValue(
    "learning_rate",
  );
  await dialog
    .locator(".cm-search")
    .getByRole("button", { name: "关闭", exact: true })
    .click();
  await editor.press("Control+z");
  expect(await editor.textContent()).not.toBe(beforeUndo);
  await editor.fill(draft);
  await expect(dialog.getByLabel("运行名称", { exact: true })).toHaveValue(
    "不要翻译：设置 {value0}",
  );
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(dialog.getByLabel("因果传播延迟", { exact: true })).toHaveValue(
    "30000",
  );
  await expect(dialog.getByLabel("连接学习率", { exact: true })).toHaveValue(
    "0.019",
  );
  await dialog.getByLabel("关闭", { exact: true }).click();
  await page.getByLabel("切换界面语言", { exact: true }).selectOption("en");
  await page.goto("/settings");
  await page
    .getByRole("button", { name: "Project defaults", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Defaults for new consciousnesses",
      exact: true,
    }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("language-parameters-mobile.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("language selection works with blocked browser storage", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "localStorage", {
      get() {
        throw new DOMException("Storage disabled", "SecurityError");
      },
    });
  });
  await page.goto("/settings");
  await page.getByLabel("切换界面语言", { exact: true }).selectOption("en");
  await expect(
    page.getByRole("heading", { name: "Settings", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Switch interface language", { exact: true })
    .selectOption("zh-CN");
  await expect(
    page.getByRole("heading", { name: "设置", exact: true }),
  ).toBeVisible();
});

test("device language does not rewrite background notification language", async ({
  page,
}) => {
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "通知参考语言验证" },
    })
  ).json();
  const settings = `/api/v2/projects/${project.id}/notifications/settings`;
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page.goto("/settings?section=notifications");
  await page.getByLabel("邮件语言", { exact: true }).selectOption("follow-ui");
  await page.getByLabel("后台参考语言", { exact: true }).selectOption("en");
  await page
    .getByRole("button", { name: "切换到 JSON 编辑", exact: true })
    .click();
  await expect(
    page.getByRole("textbox", { name: "通知规则 JSON", exact: true }),
  ).toContainText('"ui_language": "en"');
  await page
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(page.getByLabel("后台参考语言", { exact: true })).toHaveValue(
    "en",
  );
  await page.getByRole("button", { name: "保存通知设置", exact: true }).click();
  await expect
    .poll(
      async () =>
        (await (await page.request.get(settings)).json()).config.ui_language,
    )
    .toBe("en");
  await page.getByLabel("切换界面语言", { exact: true }).selectOption("en");
  await expect(
    page.getByLabel("Background reference language", { exact: true }),
  ).toHaveValue("en");
  await page
    .getByLabel("Background reference language", { exact: true })
    .selectOption("zh-CN");
  await page
    .getByRole("button", { name: "Save notification settings", exact: true })
    .click();
  await expect
    .poll(
      async () =>
        (await (await page.request.get(settings)).json()).config.ui_language,
    )
    .toBe("zh-CN");
  await page
    .getByLabel("Switch interface language", { exact: true })
    .selectOption("zh-CN");
  await expect(page.getByLabel("后台参考语言", { exact: true })).toHaveValue(
    "zh-CN",
  );
  const stored = await (await page.request.get(settings)).json();
  expect(stored.config.ui_language).toBe("zh-CN");
  expect(stored.config.email_enabled).toBe(false);
});

test("chart language preserves the inspected simulation interval", async ({
  page,
}) => {
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "图表语言验证" },
    })
  ).json();
  const root = `/api/v2/projects/${project.id}`;
  const run = await (
    await page.request.post(`${root}/runs`, {
      data: {
        name: "保留原始名称",
        spec: {
          environment: "replay",
          clock: "unbounded",
          duration_s: 0.4,
          sample_us: 10000,
          replay: Array.from({ length: 40 }, (_, i) => ({
            time_us: String(i * 10000),
            channels: [
              [1, ((i % 4) + 1) / 4],
              [2, 0.4],
            ],
          })),
        },
      },
    })
  ).json();
  const url = `${root}/runs/${run.id}`;
  await expect
    .poll(async () => (await (await page.request.get(url)).json()).status)
    .toBe("completed");
  const before = await (await page.request.get(url)).json();
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page.goto(`/runs/${run.id}?view=dynamics`);
  const chart = page.locator('.chart-grid [role="img"]').first();
  await expect(chart).toContainText("模拟时间（s）");
  const axisNumbers = async () =>
    (await chart.locator("svg text").allTextContents()).filter((v) =>
      /^-?\d[\d,.]*$/.test(v),
    );
  const initial = await axisNumbers();
  const box = (await chart.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.65, box.y + box.height * 0.4);
  await page.mouse.wheel(0, -450);
  await expect.poll(axisNumbers).not.toEqual(initial);
  const zoomed = await axisNumbers();
  await page.getByLabel("切换界面语言", { exact: true }).selectOption("en");
  await expect(chart).toContainText("Simulation time (s)");
  await expect.poll(axisNumbers).toEqual(zoomed);
  await page
    .getByLabel("Switch interface language", { exact: true })
    .selectOption("zh-CN");
  await expect(chart).toContainText("模拟时间（s）");
  await expect.poll(axisNumbers).toEqual(zoomed);
  expect((await (await page.request.get(url)).json()).state_hash).toBe(
    before.state_hash,
  );
});
