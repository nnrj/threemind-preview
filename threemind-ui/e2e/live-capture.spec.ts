import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);
// Browser-generated devices only: never acquire the user's microphone or camera.
test.use({
  launchOptions: {
    args: [
      "--use-fake-device-for-media-stream",
      "--use-fake-ui-for-media-stream",
    ],
  },
});

test("live AV configuration, bounded physical packets, stop, retained evidence and device cleanup", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let lostAcknowledgement = false;
  await page.route("**/capture/*/packets", async (route) => {
    if (route.request().method() === "POST" && !lostAcknowledgement) {
      lostAcknowledgement = true;
      const accepted = await route.fetch();
      expect(accepted.status()).toBe(202);
      await route.abort("failed");
    } else await route.continue();
  });
  await page.addInitScript(() => {
    const get = navigator.mediaDevices.getUserMedia.bind(
      navigator.mediaDevices,
    );
    (window as any).__captureTracks = [];
    navigator.mediaDevices.getUserMedia = async (c) => {
      const stream = await get(c);
      (window as any).__captureTracks.push(...stream.getTracks());
      return stream;
    };
  });
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `连续设备验收 ${new Date().toISOString()}` },
    })
  ).json();
  const root = `/api/v2/projects/${project.id}`;
  const response = await page.request.post(`${root}/runs`, {
    data: {
      name: "虚拟音画设备 · 连续采集",
      spec: {
        environment: "manual",
        clock: "realtime",
        duration_s: 60,
        checkpoint_us: 200000,
        auditory_sensor: {
          enabled: true,
          encoding: "waveform",
          waveform_bins: 4,
          window_us: 50000,
        },
        visual_sensor: {
          enabled: true,
          target_width: 4,
          target_height: 4,
          patch_width: 2,
          patch_height: 2,
          frame_interval_us: 200000,
        },
        structural_readout: { enabled: false },
        temporal_readout: { enabled: false },
      },
    },
  });
  expect(response.status()).toBe(201);
  const run = await response.json(),
    url = `${root}/runs/${run.id}`;
  try {
    await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
    await expect
      .poll(async () => (await (await page.request.get(url)).json()).status)
      .toBe("paused");
    await page.goto("/");
    await page
      .getByLabel("当前研究项目", { exact: true })
      .selectOption(project.id);
    await page.goto(`/runs/${run.id}`);
    await page.getByRole("button", { name: "感官与输入", exact: true }).click();
    await page.getByRole("button", { name: "连续设备", exact: true }).click();
    await page
      .getByRole("button", { name: "配置连续感官", exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    await dialog.locator(".configuration-advanced > summary").click();
    await dialog
      .getByLabel("高级参数分类", { exact: true })
      .selectOption("live_capture");
    await dialog.getByLabel("允许连续麦克风", { exact: true }).check();
    await dialog.getByLabel("允许连续摄像头", { exact: true }).check();
    await dialog
      .getByLabel("连续采集递送缓冲", { exact: true })
      .fill("2000000");
    await page.screenshot({
      path: info.outputPath("capture-configuration.png"),
    });
    await dialog.getByRole("button", { name: "保存配置", exact: true }).click();
    await expect(dialog).toHaveCount(0);
    await page.request.post(`${url}/commands`, { data: { kind: "resume" } });
    await expect
      .poll(async () => (await (await page.request.get(url)).json()).status)
      .toBe("running");
    await page
      .getByRole("combobox", { name: "连续采集类型", exact: true })
      .selectOption("av");
    await page.getByRole("button", { name: "开始采集", exact: true }).click();
    await expect(
      page.locator(".live-capture-actions [role=status]"),
    ).toHaveText("设备采集中");
    const current = async () =>
      (await (await page.request.get(`${url}/capture`)).json()).rows[0];
    await expect
      .poll(async () => (await current())?.next_sequence || 0)
      .toBeGreaterThanOrEqual(8);
    await page.getByRole("button", { name: "停止采集", exact: true }).click();
    await expect(
      page.locator(".live-capture-actions [role=status]"),
    ).toHaveText("设备未开启");
    await expect.poll(async () => (await current()).status).toBe("stopped");
    const session = await current();
    const packets = async () =>
      (
        await (
          await page.request.get(
            `${url}/capture/${session.id}/packets?limit=100`,
          )
        ).json()
      ).rows;
    await expect
      .poll(async () =>
        (await packets()).every((p: any) => p.status === "completed"),
      )
      .toBe(true);
    const rows = await packets();
    expect(
      rows.some((p: any) => p.metadata.kind === "audio" && p.metadata.final),
    ).toBe(true);
    expect(rows.some((p: any) => p.metadata.kind === "video")).toBe(true);
    expect(
      rows
        .filter((p: any) => p.metadata.kind === "audio")
        .every((p: any) => p.metadata.timestamp_kind === "audio-render-frame"),
    ).toBe(true);
    expect(rows.map((p: any) => p.sequence)).toEqual(
      rows.map((_: any, i: number) => i),
    );
    expect(lostAcknowledgement).toBe(true);
    const raw = await page.request.get(
      `${url}/media/${rows[0].envelope_id}/original`,
    );
    expect(raw.status()).toBe(200);
    expect((await raw.body()).subarray(0, 4).toString()).toBe("TMV2");
    expect(
      await page.evaluate(() =>
        (window as any).__captureTracks.every(
          (t: MediaStreamTrack) => t.readyState === "ended",
        ),
      ),
    ).toBe(true);
    await page.getByRole("button", { name: "刷新会话", exact: true }).click();
    await expect(page.locator(".live-capture-panel")).toContainText(
      "音频结束块",
    );
    await page.screenshot({
      path: info.outputPath("capture-desktop.png"),
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath("capture-mobile.png"),
      fullPage: true,
    });
    await page.setViewportSize({ width: 1440, height: 1000 });
    // Starting again and leaving the tool must release both virtual devices.
    await page.getByRole("button", { name: "开始采集", exact: true }).click();
    await expect(
      page.locator(".live-capture-actions [role=status]"),
    ).toHaveText("设备采集中");
    await expect
      .poll(async () => (await current()).next_sequence)
      .toBeGreaterThan(0);
    await page.getByRole("button", { name: "输入记录", exact: true }).click();
    await expect
      .poll(async () =>
        page.evaluate(() =>
          (window as any).__captureTracks.every(
            (t: MediaStreamTrack) => t.readyState === "ended",
          ),
        ),
      )
      .toBe(true);
    await expect.poll(async () => (await current()).status).toBe("interrupted");
    expect((await current()).reason).toBe("page_left");
    await page.goto("/docs?doc=docs%2Fzh%2Fv2-live-capture.md");
    await expect(
      page.getByRole("heading", {
        name: "连续设备采集：麦克风、摄像头与音画会话",
        exact: true,
      }),
    ).toBeVisible();
    expect(errors).toEqual([]);
  } finally {
    await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
  }
});
