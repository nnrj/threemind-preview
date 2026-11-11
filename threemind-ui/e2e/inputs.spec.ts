import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("text sensory configuration, paused admission, delivery audit and export", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const p = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `感官验收 ${new Date().toISOString()}` },
    })
  ).json();
  const base = `/api/v2/projects/${p.id}`;
  const created = await page.request.post(`${base}/runs`, {
    data: {
      name: "文本感官 · 分帧与证据",
      spec: {
        environment: "manual",
        clock: "realtime",
        duration_s: 30,
        text_sensor: {
          encoding: "labeled-observation",
          frame_characters: 2,
          frame_interval_us: 20000,
        },
      },
    },
  });
  expect(created.status()).toBe(201);
  const run = await created.json(),
    url = `${base}/runs/${run.id}`;
  await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
  await expect
    .poll(async () => (await (await page.request.get(url)).json()).status)
    .toBe("paused");
  await page.goto("/");
  await page.getByLabel("当前研究项目", { exact: true }).selectOption(p.id);
  await expect(page.getByLabel("当前研究项目", { exact: true })).toHaveValue(
    p.id,
  );
  await page.goto(`/runs/${run.id}`);
  await page.getByRole("button", { name: "参数配置", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.locator(".configuration-advanced > summary").click();
  await expect(
    dialog.getByLabel("文本感官编码", { exact: true }),
  ).toBeDisabled();
  await expect(
    dialog.locator('[data-parameter="text_sensor.encoding"]'),
  ).toContainText("创建后不可更改");
  await expect(dialog.getByLabel("每帧字符数", { exact: true })).toHaveValue(
    "2",
  );
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  // CodeMirror virtualizes offscreen lines; validate the entire edited document.
  const validation = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      request.url().endsWith("/configuration/validate"),
  );
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  expect(
    (await validation).postDataJSON().spec.text_sensor.frame_characters,
  ).toBe(2);
  await expect(dialog.locator(".configuration-success")).toContainText(
    "校验通过",
  );
  await page.keyboard.press("Escape");
  await page.getByLabel("文本载体", { exact: true }).fill("A汉B字");
  await page.getByRole("button", { name: "接收并排队", exact: true }).click();
  await expect(page.locator(".input-composer [role=status]")).toContainText(
    "已接收 2 帧",
  );
  await expect(page.locator(".input-composer [role=status]")).toContainText(
    "已暂停",
  );
  await page.screenshot({
    path: info.outputPath("text-input.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "感官与输入", exact: true }).click();
  await expect(page.locator(".sensory-cards")).toContainText("文本感官");
  await expect(
    page.getByText("已接收，待排入", { exact: true }).last(),
  ).toBeVisible();
  await page.getByRole("button", { name: "查看载体与帧", exact: true }).click();
  await expect(dialog.locator("pre").first()).toContainText("A汉B字");
  await expect(dialog).toContainText("载体尚未排入内核");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "继续", exact: true }).click();
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`${url}/inputs`)).json()).rows[0]
          .delivered_count,
    )
    .toBe(2);
  await page.getByRole("button", { name: "暂停", exact: true }).click();
  await expect(page.locator(".page-actions .badge")).toContainText("已暂停");
  await page.getByRole("button", { name: "刷新记录", exact: true }).click();
  await expect(
    page.getByText("全部帧已处理", { exact: true }).last(),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("sensory-records.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "查看载体与帧", exact: true }).click();
  await expect(dialog.locator("tbody tr")).toHaveCount(2);
  await dialog.locator("tbody details summary").first().click();
  await expect(dialog.locator("tbody pre").first()).toContainText('"labels"');
  await page.screenshot({
    path: info.outputPath("sensory-frame-detail.png"),
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  const downloading = page.waitForEvent("download");
  await page.getByRole("link", { name: "导出记录", exact: true }).click();
  const artifact = await downloading;
  expect(artifact.suggestedFilename()).toBe("inputs-frames.jsonl");
  await artifact.saveAs(info.outputPath("inputs-frames.jsonl"));
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("mobile-sensory-records.png"),
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "输入、分帧与证据说明", exact: true })
    .click();
  await expect(page.locator(".markdown h1")).toHaveText(
    "感官输入、分帧与递送证据",
  );
  expect(errors).toEqual([]);
});
