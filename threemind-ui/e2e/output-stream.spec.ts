import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);
test.use({ launchOptions: { args: ["--mute-audio"] } });

test("independent organ settings, continuous output, mute on pause and navigation, complete history", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() => {
    const Audio = window.AudioContext,
      Events = window.EventSource;
    (window as any).__organContexts = [];
    (window as any).__organSources = [];
    (window as any).__oscillators = 0;
    window.AudioContext = class extends Audio {
      constructor(...args: any[]) {
        super(...args);
        (window as any).__organContexts.push(this);
      }
      createOscillator() {
        (window as any).__oscillators++;
        return super.createOscillator();
      }
    };
    window.EventSource = class extends Events {
      constructor(...args: any[]) {
        super(...(args as [string]));
        (window as any).__organSources.push(this);
      }
    };
  });
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `连续器官验收 ${new Date().toISOString()}` },
    })
  ).json();
  const root = `/api/v2/projects/${project.id}`;
  const created = await page.request.post(`${root}/runs`, {
    data: {
      name: "独立声音与图像 · 只读跟随",
      spec: {
        environment: "manual",
        clock: "realtime",
        duration_s: 40,
        checkpoint_us: 250000,
        sample_us: 200000,
        config: { activation_tau: 20, inhibition: false },
        acoustic_output: { enabled: true },
        activation_projector: { enabled: true, width: 16, height: 16 },
        structural_readout: { enabled: false },
        temporal_readout: { enabled: false },
      },
    },
  });
  expect(created.status()).toBe(201);
  const run = await created.json(),
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
    await page.getByRole("button", { name: "器官输出", exact: true }).click();
    await page
      .getByRole("button", { name: "配置输出器官", exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    await dialog.locator(".configuration-advanced > summary").click();
    await dialog
      .getByLabel("高级参数分类", { exact: true })
      .selectOption("acoustic_output");
    await dialog.getByLabel("发声控制采样间隔", { exact: true }).fill("70000");
    await dialog.getByLabel("发声频率下界", { exact: true }).fill("220");
    await dialog.getByLabel("发声频率上界", { exact: true }).fill("880");
    await dialog.getByLabel("发声输出增益", { exact: true }).fill("0.8");
    await dialog
      .getByLabel("高级参数分类", { exact: true })
      .selectOption("activation_projector");
    await dialog.getByLabel("投影控制采样间隔", { exact: true }).fill("110000");
    await dialog.getByLabel("投影亮度增益", { exact: true }).fill("1.5");
    await dialog.getByRole("button", { name: "保存配置", exact: true }).click();
    await expect(dialog).toHaveCount(0);
    const input = await page.request.post(`${url}/inputs`, {
      data: {
        adapter_id: "anonymous-frames",
        request_id: crypto.randomUUID(),
        payload: {
          frames: [
            {
              time_us: "0",
              channels: [
                [1, 0.8],
                [2, 0.7],
              ],
              intensity: 1,
            },
          ],
        },
      },
    });
    expect(input.status()).toBe(202);
    await page.request.post(`${url}/commands`, { data: { kind: "resume" } });
    const monitor = page.getByRole("region", {
      name: "连续器官输出",
      exact: true,
    });
    await monitor
      .getByRole("button", { name: "跟随当前输出", exact: true })
      .click();
    await expect(monitor).toContainText("图像 · 模拟");
    await monitor
      .getByRole("button", { name: "开启连续声音", exact: true })
      .click();
    await expect(monitor.getByRole("status").last()).toHaveText(
      "连续声音已开启",
    );
    await expect
      .poll(() => page.evaluate(() => (window as any).__oscillators))
      .toBeGreaterThan(0);
    const before = (
      await (await page.request.get(`${url}/organs?limit=1`)).json()
    ).rows[0].sample_id;
    await expect
      .poll(
        async () =>
          (await (await page.request.get(`${url}/organs?limit=1`)).json())
            .rows[0].sample_id,
      )
      .toBeGreaterThan(before);
    await page.screenshot({
      path: info.outputPath("output-stream-desktop.png"),
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath("output-stream-mobile.png"),
      fullPage: true,
    });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
    await expect(monitor.getByRole("status").last()).toHaveText("静音");
    await expect
      .poll(() =>
        page.evaluate(
          () =>
            (window as any).__organContexts.every(
              (c: AudioContext) => c.state === "closed",
            ) &&
            (window as any).__organSources.every(
              (s: EventSource) => s.readyState === 2,
            ),
        ),
      )
      .toBe(true);
    const history = await page.request.get(`${url}/organs/export`);
    const rows = (await history.text())
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));
    expect(
      rows.some(
        (r) =>
          r.payload.voices &&
          r.payload.configuration.acoustic_output.output_interval_us === 70000,
      ),
    ).toBe(true);
    expect(
      rows.some(
        (r) =>
          r.payload.image &&
          r.payload.configuration.activation_projector.output_interval_us ===
            110000,
      ),
    ).toBe(true);
    expect(
      rows
        .filter((r) => r.payload.voices)
        .flatMap((r) => r.payload.voices)
        .every((v) => v.frequency_hz >= 220 && v.frequency_hz < 880),
    ).toBe(true);
    await page.request.post(`${url}/commands`, { data: { kind: "resume" } });
    await monitor
      .getByRole("button", { name: "跟随当前输出", exact: true })
      .click();
    await monitor
      .getByRole("button", { name: "开启连续声音", exact: true })
      .click();
    await expect(monitor.getByRole("status").last()).toHaveText(
      "连续声音已开启",
    );
    await page.getByRole("button", { name: "输入记录", exact: true }).click();
    await expect
      .poll(() =>
        page.evaluate(
          () =>
            (window as any).__organContexts.every(
              (c: AudioContext) => c.state === "closed",
            ) &&
            (window as any).__organSources.every(
              (s: EventSource) => s.readyState === 2,
            ),
        ),
      )
      .toBe(true);
    await page.goto("/docs?doc=docs%2Fzh%2Fv2-continuous-output.md");
    await expect(
      page.getByRole("heading", {
        name: "连续发声与激活图像输出",
        exact: true,
      }),
    ).toBeVisible();
    await expect(page.locator(".katex-error")).toHaveCount(0);
    expect(errors).toEqual([]);
  } finally {
    await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
  }
});
