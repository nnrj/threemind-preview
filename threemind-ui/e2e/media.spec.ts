import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

function wav() {
  const samples = 643,
    raw = Buffer.alloc(44 + samples * 2);
  raw.write("RIFF", 0);
  raw.writeUInt32LE(raw.length - 8, 4);
  raw.write("WAVEfmt ", 8);
  raw.writeUInt32LE(16, 16);
  raw.writeUInt16LE(1, 20);
  raw.writeUInt16LE(1, 22);
  raw.writeUInt32LE(16000, 24);
  raw.writeUInt32LE(32000, 28);
  raw.writeUInt16LE(2, 32);
  raw.writeUInt16LE(16, 34);
  raw.write("data", 36);
  raw.writeUInt32LE(samples * 2, 40);
  for (let i = 0; i < samples; i++) raw.writeInt16LE(18000, 44 + i * 2);
  return raw;
}

test("media config, upload, preserved original, output snapshot and mobile tools", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `媒体与器官验收 ${new Date().toISOString()}` },
    })
  ).json();
  const root = `/api/v2/projects/${project.id}`;
  const response = await page.request.post(`${root}/runs`, {
    data: {
      name: "声音刺激 · 被动器官读出",
      spec: {
        environment: "manual",
        clock: "realtime",
        duration_s: 30,
        sample_us: 50000,
        auditory_sensor: {
          enabled: true,
          encoding: "waveform",
          waveform_bins: 4,
          window_us: 20000,
        },
        visual_sensor: { enabled: true },
        acoustic_output: { enabled: true, minimum_activation: 0 },
        activation_projector: { enabled: true },
      },
    },
  });
  expect(response.status()).toBe(201);
  const run = await response.json(),
    url = `${root}/runs/${run.id}`;
  await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
  await expect
    .poll(async () => (await (await page.request.get(url)).json()).status)
    .toBe("paused");
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await expect(page.getByLabel("当前研究项目", { exact: true })).toHaveValue(
    project.id,
  );
  await page.goto(`/runs/${run.id}`);
  await page.getByRole("button", { name: "参数配置", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.locator(".configuration-advanced > summary").click();
  await expect(dialog.getByLabel("听觉编码", { exact: true })).toBeDisabled();
  await expect(
    dialog.getByLabel("视网膜宽度", { exact: true }),
  ).toHaveAttribute("readonly");
  await expect(dialog.getByLabel("启用发声器", { exact: true })).toBeChecked();
  await dialog.getByLabel("听觉增益", { exact: true }).fill("1.2");
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  const validating = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/configuration/validate"),
  );
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  expect((await validating).postDataJSON().spec.auditory_sensor.gain).toBe(1.2);
  await expect(dialog.locator(".configuration-success")).toContainText(
    "校验通过",
  );
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "感官与输入", exact: true }).click();
  await page.getByRole("button", { name: "媒体输入", exact: true }).click();
  await page.getByLabel("选择媒体原件", { exact: true }).setInputFiles({
    name: "验收声音.wav",
    mimeType: "audio/wav",
    buffer: wav(),
  });
  await page
    .getByRole("button", { name: "接收媒体并排队", exact: true })
    .click();
  await expect(
    page.getByRole("status", { name: "媒体接收结果", exact: true }),
  ).toContainText("已接收 3 帧");
  await page.screenshot({
    path: info.outputPath("media-input.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "输入记录", exact: true }).click();
  await page
    .getByRole("combobox", { name: "输入来源", exact: true })
    .selectOption("upload-audio");
  await page.getByRole("button", { name: "查看载体与帧", exact: true }).click();
  await expect(dialog).toContainText("asset_sha256");
  const download = page.waitForEvent("download");
  await dialog.getByRole("link", { name: "下载媒体原件", exact: true }).click();
  expect((await download).suggestedFilename()).toBe("验收声音.wav");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "继续", exact: true }).click();
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(`${url}/inputs?source=upload-audio`)
          ).json()
        ).rows[0].delivered_count,
    )
    .toBe(3);
  await page.getByRole("button", { name: "暂停", exact: true }).click();
  await expect(page.locator(".page-actions .badge")).toContainText("已暂停");
  await page.getByRole("button", { name: "器官输出", exact: true }).click();
  await expect(page.locator(".organ-projection canvas")).toBeVisible();
  await expect(page.locator(".organ-outputs")).toContainText("数据库");
  // Latest samples may already be quiescent before the pause takes effect.
  // Select an actually voiced historical sample; pausing itself consumes no time.
  const selector = page.getByRole("combobox", {
    name: "输出采样时刻",
    exact: true,
  });
  const audition = page.locator(".organ-voice-actions button").first();
  let voiced = false;
  for (let historyPage = 0; historyPage < 12 && !voiced; historyPage++) {
    const count = await selector.locator("option").count();
    expect(count).toBeGreaterThan(0);
    for (let i = 0; i < count; i++) {
      await selector.selectOption(String(i));
      if (await audition.isEnabled()) {
        voiced = true;
        break;
      }
    }
    if (!voiced) {
      const earlier = page.getByRole("button", {
        name: "更早的采样",
        exact: true,
      });
      if (!(await earlier.isEnabled())) break;
      const previous = await selector.locator("option").first().textContent();
      await earlier.click();
      await expect(selector.locator("option").first()).not.toHaveText(
        previous!,
      );
    }
  }
  expect(voiced).toBe(true);
  await expect(audition).toBeEnabled();
  await audition.click();
  await expect(audition).toHaveText("播放中…");
  await expect(audition).toHaveText("试听此帧（0.5 秒）");
  const wavDownload = page.waitForEvent("download");
  await page.getByRole("link", { name: "合成 WAV", exact: true }).click();
  expect((await wavDownload).suggestedFilename()).toMatch(
    /^activity-sample-\d+\.wav$/,
  );
  const pngDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出此帧 PNG", exact: true }).click();
  expect((await pngDownload).suggestedFilename()).toMatch(
    /^activation-.*\.png$/,
  );
  await page.screenshot({
    path: info.outputPath("organ-output.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("mobile-organ-output.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "媒体输入", exact: true }).click();
  await page
    .getByRole("combobox", { name: "媒体种类", exact: true })
    .selectOption("image");
  await expect(page.getByLabel("选择媒体原件", { exact: true })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("mobile-media-input.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "因果事件", exact: true }).click();
  await expect(
    page.locator(".event-row strong", { hasText: "organ_output" }),
  ).toHaveCount(0);
  await expect(page.locator("main")).toContainText("器官采样在");
  await page.goto("/docs?doc=docs%2Fzh%2Fv2-media.md");
  await expect(page.locator(".markdown h1")).toHaveText(
    "物理媒体感官与被动输出器官",
  );
  await expect(page.locator(".markdown .katex").first()).toBeVisible();
  await expect(page.locator(".katex-error")).toHaveCount(0);
  expect(errors).toEqual([]);
});
