import { test, expect } from "@playwright/test";
import { writeFile } from "node:fs/promises";

test.skip(!process.env.THREEMIND_E2E_URL, "Requires an isolated workstation.");
test.use({
  permissions: ["camera", "microphone"],
  launchOptions: {
    args: [
      "--use-fake-device-for-media-stream",
      "--use-fake-ui-for-media-stream",
    ],
  },
});

test("V3 basic encoding, faithful inline chat, IME, media and four organs", async ({
  page,
}, info) => {
  test.setTimeout(180000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByRole("button", { name: "新建研究项目", exact: true }).click();
  await page
    .getByLabel("项目名称", { exact: true })
    .fill(`V3 交互验收 ${Date.now()}`);
  await page.getByRole("button", { name: "创建项目", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建意识", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  const encoding = dialog.getByLabel("节点标记／感官模式", { exact: true });
  await expect(encoding).toHaveValue("anonymous-distributed");
  await encoding.selectOption("literal-character");
  await dialog.locator(".configuration-advanced > summary").click();
  const advancedEncoding = dialog.getByLabel("文本感官编码", { exact: true });
  await expect(advancedEncoding).toHaveValue("literal-character");
  await advancedEncoding.selectOption("labeled-observation");
  await expect(encoding).toHaveValue("labeled-observation");
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  const editor = dialog.getByRole("textbox", {
    name: "JSON 参数",
    exact: true,
  });
  await editor.press("Control+f");
  await dialog
    .getByPlaceholder("查找", { exact: true })
    .fill("labeled-observation");
  await dialog.getByRole("button", { name: "下一处", exact: true }).click();
  await expect(editor).toContainText('"encoding": "labeled-observation"');
  await dialog.getByPlaceholder("查找", { exact: true }).press("Escape");
  const defaults = await (
    await page.request.get("/api/v2/configuration")
  ).json();
  expect(defaults.defaults.config.propagation_interval_us).toBe(100000);
  expect(defaults.defaults.duration_s).toBeNull();
  const spec = {
    ...defaults.defaults,
    environment: "manual",
    clock: "realtime",
    checkpoint_us: 300000,
    config: {
      ...defaults.defaults.config,
      activation_decay_enabled: false,
      inhibition: false,
    },
    text_sensor: {
      ...defaults.defaults.text_sensor,
      encoding: "literal-character",
    },
  };
  // CodeMirror virtualizes offscreen lines. Use its select-all command rather
  // than replacing only the currently mounted contenteditable DOM fragment.
  await editor.press("Control+Home");
  await editor.press("Control+a");
  await page.keyboard.insertText(JSON.stringify(spec));
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(encoding).toHaveValue("literal-character");
  await dialog.getByLabel("意识名称", { exact: true }).fill("V3 聊天与器官");
  await page.screenshot({
    path: info.outputPath("creation-encoding.png"),
    fullPage: false,
  });
  await dialog.getByRole("button", { name: "创建并开始", exact: true }).click();
  await expect(page).toHaveURL(/\/runs\//);
  const project = await page
    .getByLabel("当前研究项目", { exact: true })
    .inputValue();
  const rid = new URL(page.url()).pathname.split("/").pop();
  const base = `/api/v2/projects/${project}/runs/${rid}`;
  const sidebar = page.locator(".inspector");
  const text = sidebar.getByLabel("文本载体", { exact: true });
  try {
    await expect(text).toBeVisible();
    await text.fill("蜂蜜");
    await text.dispatchEvent("compositionstart");
    await text.dispatchEvent("keydown", {
      key: "Enter",
      code: "Enter",
      isComposing: true,
      keyCode: 229,
    });
    await expect(text).toHaveValue("蜂蜜");
    expect(
      (
        await (await page.request.get(`${base}/conversation`)).json()
      ).rows.filter((r: any) => r.kind === "input"),
    ).toHaveLength(0);
    await text.dispatchEvent("compositionend");
    await text.press("Shift+Enter");
    await expect(text).toHaveValue("蜂蜜\n");
    await text.fill("蜂蜜");
    await text.press("Enter");
    await expect(text).toHaveValue("");
    await expect(
      sidebar.locator(".readout-plain").filter({ hasText: "蜂" }).first(),
    ).toBeVisible();
    const fail = async (route: any) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "验收用服务失败" }),
      });
    await page.route(`**${base}/inputs`, fail);
    await text.fill("失败保留草稿");
    await sidebar.getByRole("button", { name: "发送", exact: true }).click();
    await expect(sidebar.getByRole("alert")).toContainText("验收用服务失败");
    await expect(text).toHaveValue("失败保留草稿");
    await page.unroute(`**${base}/inputs`, fail);
    await sidebar.getByRole("button", { name: "发送", exact: true }).click();
    await expect(text).toHaveValue("");
    for (const [label, kind] of [
      ["图片", "image"],
      ["音频", "audio"],
      ["视频", "video"],
    ]) {
      await sidebar
        .getByRole("button", { name: "添加媒体刺激", exact: true })
        .click();
      await sidebar.getByRole("menuitem", { name: label, exact: true }).click();
      const media = page.getByRole("dialog", { name: "媒体刺激", exact: true });
      await expect(
        media.getByRole("combobox", { name: "媒体种类", exact: true }),
      ).toHaveValue(kind);
      await expect(
        media.getByLabel("选择媒体原件", { exact: true }),
      ).toBeEnabled();
      await media.getByLabel("关闭", { exact: true }).click();
    }
    for (const name of ["耳朵", "眼睛", "嘴巴", "图像读出"]) {
      await sidebar
        .getByRole("button", { name: `${name} · 已关闭`, exact: true })
        .click();
      await expect(
        sidebar.getByRole("button", { name: `${name} · 已开启`, exact: true }),
      ).toBeVisible({ timeout: 35000 });
      await sidebar
        .getByRole("button", { name: `${name} · 已开启`, exact: true })
        .click();
      await expect(
        sidebar.getByRole("button", { name: `${name} · 已关闭`, exact: true }),
      ).toBeVisible();
    }
    const list = sidebar.getByRole("log", {
      name: "刺激与意识读出历史",
      exact: true,
    });
    if (process.env.THREEMIND_E2E_SOAK === "1") {
      const cdp = await page.context().newCDPSession(page);
      await cdp.send("Performance.enable");
      const samples: any[] = [];
      for (let i = 0; i < 7; i++) {
        if (i) {
          await text.fill("蜂蜜");
          await text.press("Enter");
          await expect(text).toHaveValue("");
          await page.waitForTimeout(10000);
        }
        await cdp.send("HeapProfiler.collectGarbage");
        const perf = await cdp.send("Performance.getMetrics");
        const dom = await cdp.send("Memory.getDOMCounters");
        const messages = await list.locator("article").count();
        samples.push({
          elapsed_s: i * 10,
          messages,
          dom_nodes: dom.nodes,
          heap_bytes: perf.metrics.find((m: any) => m.name === "JSHeapUsedSize")
            ?.value,
        });
        expect(messages).toBeLessThanOrEqual(20);
      }
      await writeFile(
        info.outputPath("chat-soak.json"),
        JSON.stringify(samples, null, 2),
      );
      // A finite bounded-growth check, not an hours-long capacity claim.
      expect(samples.at(-1).heap_bytes - samples[1].heap_bytes).toBeLessThan(
        24 * 1024 ** 2,
      );
      expect(samples.at(-1).dom_nodes - samples[1].dom_nodes).toBeLessThan(
        1500,
      );
      await cdp.detach();
    }
    await list.evaluate((el) => {
      el.scrollTop = 0;
      el.dispatchEvent(new Event("scroll"));
    });
    const firstId = await list
      .locator("article")
      .first()
      .getAttribute("data-message-id");
    await page.waitForTimeout(2300);
    await expect(
      list.locator(`article[data-message-id="${firstId}"]`),
    ).toBeAttached();
    await sidebar.getByRole("button", { name: /回到最新|回到底部/ }).click();
    await expect(list.locator("article").first()).toBeVisible();
    expect(await list.locator("article").count()).toBeLessThanOrEqual(20);
    await expect(
      list.locator("article").last().locator("header"),
    ).toBeInViewport();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: info.outputPath("inline-chat.png"),
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(text).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
    await page.screenshot({
      path: info.outputPath("inline-chat-mobile.png"),
      fullPage: true,
    });
    expect(errors).toEqual([]);
  } finally {
    await page.request.post(`${base}/commands`, { data: { kind: "pause" } });
  }
});

test("restored kernel documentation and bilingual plan navigation", async ({
  page,
}) => {
  await page.goto("/docs?doc=docs/zh/v2-kernel.md");
  await expect(page.locator(".markdown h1")).toHaveText(
    "ThreeMind 内核：架构、时间与局部动力学",
  );
  await expect(page.locator(".markdown .mermaid svg")).toBeVisible();
  await expect(page.locator(".markdown .katex").first()).toBeVisible();
  await expect(page.locator(".katex-error")).toHaveCount(0);
  await page
    .locator(".markdown")
    .getByRole("link", { name: "English", exact: true })
    .click();
  await expect(page.locator(".markdown h1")).toHaveText(
    "ThreeMind kernel: architecture, time and local dynamics",
  );
  await page.goto("/docs?doc=docs/zh/plans/index.md");
  await page
    .locator(".markdown")
    .getByRole("link", { name: "V3 恢复实施记录", exact: true })
    .click();
  await expect(page.locator(".markdown")).toContainText("causal/9");
  await expect(page.locator(".markdown .katex").first()).toBeVisible();
  await expect(page.locator(".katex-error")).toHaveCount(0);
});
