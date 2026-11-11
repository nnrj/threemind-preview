import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("attention graphical JSON roundtrip, queued modulation, actual input selection and evidence", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `输入注意验收 ${new Date().toISOString()}` },
    })
  ).json();
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建运行", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("运行名称").fill("输入注意 · 显式标量");
  await dialog
    .getByLabel("环境与感官来源", { exact: true })
    .selectOption("manual");
  await dialog.getByLabel("运行时长（模拟秒）", { exact: true }).fill("60");
  await dialog.locator(".configuration-advanced > summary").click();
  await dialog
    .getByLabel("高级参数分类", { exact: true })
    .selectOption("attention");
  await dialog.getByLabel("启用输入注意竞争", { exact: true }).check();
  await dialog.getByLabel("每帧注意通道容量", { exact: true }).fill("2");
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  const validation = page.waitForRequest((r) =>
    r.url().endsWith("/configuration/validate"),
  );
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  const spec = (await validation).postDataJSON().spec;
  expect(spec.config.attention_budget).toBe(2);
  expect(spec.config.attention_competition_enabled).toBe(true);
  spec.config.attention_budget = 1;
  await dialog
    .getByRole("textbox", { name: "JSON 参数", exact: true })
    .fill(JSON.stringify(spec));
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(
    dialog.getByLabel("每帧注意通道容量", { exact: true }),
  ).toHaveValue("1");
  await dialog.getByRole("button", { name: "创建并开始", exact: true }).click();
  await expect(page).toHaveURL(/\/runs\//);
  const id = page.url().split("/runs/")[1].split(/[?#]/)[0];
  const url = `/api/v2/projects/${project.id}/runs/${id}`;
  async function pause() {
    await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
    await expect
      .poll(async () => (await (await page.request.get(url)).json()).status)
      .toBe("paused");
  }
  try {
    await pause();
    await page.getByRole("button", { name: "感官与输入", exact: true }).click();
    await page.getByRole("button", { name: "输入注意", exact: true }).click();
    const panel = page.getByRole("region", {
      name: "输入注意与调制",
      exact: true,
    });
    await panel.getByLabel("刺激增益", { exact: true }).fill("0.5");
    await panel.getByRole("button", { name: "递送调制", exact: true }).click();
    await expect(panel).toContainText("调制已排队，继续运行后递送");
    const carrier = await (
      await page.request.post(`${url}/inputs`, {
        data: {
          adapter_id: "anonymous-frames",
          request_id: crypto.randomUUID(),
          delay_us: 20000,
          payload: {
            frames: [
              {
                time_us: "0",
                channels: [
                  [9, 0.4],
                  [2, 0.9],
                  [8, 0.9],
                ],
                intensity: 1,
              },
            ],
          },
        },
      })
    ).json();
    expect(carrier.frame_count).toBe(1);
    await page.request.post(`${url}/commands`, { data: { kind: "resume" } });
    await expect
      .poll(
        async () =>
          (await (await page.request.get(`${url}/attention`)).json()).latest
            ?.passed_channels,
      )
      .toBe("1");
    await pause();
    const frame = (
      await (await page.request.get(`${url}/inputs/${carrier.id}`)).json()
    ).frames[0];
    expect(frame.stimulus.channels).toHaveLength(3);
    expect(frame.input_gate.effective_stimulus.channels).toEqual([[2, 0.9]]);
    expect(frame.input_gate.effective_stimulus.intensity).toBe(0.5);
    await expect(panel).toContainText("已生效");
    await expect(panel).not.toContainText("调制已排队，继续运行后递送");
    for (const name of ["CSV", "JSONL", "导出全部调制记录"]) {
      const download = page.waitForEvent("download");
      await panel.getByRole("link", { name, exact: true }).click();
      expect((await download).suggestedFilename()).toContain(id);
    }
    await panel.screenshot({ path: info.outputPath("attention-desktop.png") });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect
      .poll(async () =>
        page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      )
      .toBe(true);
    await panel.screenshot({ path: info.outputPath("attention-mobile.png") });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.getByRole("button", { name: "输入记录", exact: true }).click();
    await page
      .getByRole("button", { name: "查看载体与帧", exact: true })
      .first()
      .click();
    await expect(dialog).toContainText("原始 3 通道 → 通过 1 / 抑制 2");
    await dialog.getByLabel("关闭", { exact: true }).click();
    await page.goto("/docs?doc=docs%2Fzh%2Fv2-attention.md");
    await expect(page.locator(".markdown .katex").first()).toBeVisible();
    expect(await page.locator(".katex-error").count()).toBe(0);
    expect(errors).toEqual([]);
  } finally {
    await page.request
      .post(`${url}/commands`, { data: { kind: "pause" }, timeout: 5000 })
      .catch(() => {});
  }
});
