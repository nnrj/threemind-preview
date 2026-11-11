import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("energy forms, immutable birth reserve, queued supply, finite reservoir and evidence", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `能量验收 ${new Date().toISOString()}` },
    })
  ).json();
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建意识", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("意识名称").fill("能量 · 有限外部储库");
  await dialog
    .getByLabel("环境与感官来源", { exact: true })
    .selectOption("manual");
  await dialog.getByLabel("运行时长（模拟秒）", { exact: true }).fill("50");
  await dialog.locator(".configuration-advanced > summary").click();
  await dialog
    .getByLabel("高级参数分类", { exact: true })
    .selectOption("energy");
  await dialog.getByLabel("启用能量记账", { exact: true }).check();
  const damage = dialog.getByLabel("启用缺能结构损伤", { exact: true });
  await expect(damage).not.toBeChecked();
  await damage.check();
  await expect(
    dialog.getByLabel("不可逆饥饿时长", { exact: true }),
  ).toHaveCount(0);
  await dialog.getByLabel("初始能量储备", { exact: true }).fill("0.05");
  await dialog.getByLabel("直接响应能量成本", { exact: true }).fill("0.2");
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  const validation = page.waitForRequest((r) =>
    r.url().endsWith("/configuration/validate"),
  );
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  const spec = (await validation).postDataJSON().spec;
  expect(spec.config.energy_initial_reserve).toBe(0.05);
  expect(spec.config.energy_starvation_damage_enabled).toBe(true);
  expect(spec.config).not.toHaveProperty("irreversible_energy_death_enabled");
  expect(spec.config).not.toHaveProperty("energy_starvation_death_us");
  spec.config.energy_capacity = 0.5;
  spec.config.activation_decay_enabled = false;
  spec.config.inhibition = false;
  spec.duration_s = null;
  const editor = dialog.getByRole("textbox", {
    name: "JSON 参数",
    exact: true,
  });
  await editor.press("Control+Home");
  await editor.press("Control+a");
  await page.keyboard.insertText(JSON.stringify(spec));
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(dialog.getByLabel("能量储备容量", { exact: true })).toHaveValue(
    "0.5",
  );
  await expect(damage).toBeChecked();
  await dialog
    .getByLabel("高级参数分类", { exact: true })
    .selectOption("energy_supply");
  await dialog.getByLabel("启用外部能量供给", { exact: true }).check();
  await dialog.getByLabel("外部储库总供给上限", { exact: true }).fill("0.02");
  await dialog.getByRole("button", { name: "创建并开始", exact: true }).click();
  await expect(page).toHaveURL(/\/runs\//);
  const id = page.url().split("/runs/")[1].split(/[?#]/)[0];
  const url = `/api/v2/projects/${project.id}/runs/${id}`;
  try {
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
                [2, 0.6],
              ],
              intensity: 1,
            },
          ],
        },
      },
    });
    expect(input.status()).toBe(202);
    await expect
      .poll(
        async () =>
          (await (await page.request.get(`${url}/energy`)).json()).provider
            ?.accepted_total,
      )
      .toBe(0.02);
    await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
    await expect
      .poll(async () => (await (await page.request.get(url)).json()).status)
      .toBe("paused");
    await page.getByRole("button", { name: "参数配置", exact: true }).click();
    await expect(
      dialog.getByRole("button", { name: "保存配置", exact: true }),
    ).toBeEnabled();
    await dialog.locator(".configuration-advanced > summary").click();
    await dialog
      .getByLabel("高级参数分类", { exact: true })
      .selectOption("energy");
    await expect(
      dialog.getByLabel("初始能量储备", { exact: true }),
    ).toHaveAttribute("readonly", "");
    await dialog
      .getByRole("button", { name: "切换到 JSON", exact: true })
      .click();
    const changed = (await (await page.request.get(url)).json()).spec;
    changed.config.energy_initial_reserve = 0.8;
    await editor.press("Control+Home");
    await editor.press("Control+a");
    await page.keyboard.insertText(JSON.stringify(changed));
    await dialog.getByRole("button", { name: "保存配置", exact: true }).click();
    await expect(dialog).toContainText("config.energy_initial_reserve");
    await expect(dialog.locator(".configuration-errors")).toBeVisible();
    await dialog.getByLabel("关闭", { exact: true }).click();
    await page.getByRole("button", { name: "动力学", exact: true }).click();
    await page.getByRole("button", { name: "能量与供给", exact: true }).click();
    const panel = page.getByRole("region", { name: "能量与供给", exact: true });
    await expect(panel).toContainText("缺能结构损伤：已启用对照");
    await expect(panel).not.toContainText("不可逆饥饿");
    await panel.getByLabel("供给数量（实验单位）", { exact: true }).fill("0.1");
    await panel.getByRole("button", { name: "排队供给", exact: true }).click();
    await expect(panel).toContainText("供给已排队，继续运行后递送");
    const before = (await (await page.request.get(`${url}/energy`)).json())
      .latest;
    expect(before.supplied_total).toBeCloseTo(0.02, 10);
    await page.request.post(`${url}/commands`, { data: { kind: "resume" } });
    await expect
      .poll(
        async () =>
          (await (await page.request.get(`${url}/energy`)).json()).latest
            ?.supplied_total,
      )
      .toBeCloseTo(0.12, 10);
    await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
    await expect
      .poll(async () => (await (await page.request.get(url)).json()).status)
      .toBe("paused");
    await expect(panel.locator("tbody tr").first()).toBeVisible();
    await expect(panel).not.toContainText("供给已排队，继续运行后递送");
    for (const name of ["能量 CSV", "能量 JSONL", "供给日志 JSONL"]) {
      const download = page.waitForEvent("download");
      await panel.getByRole("link", { name, exact: true }).click();
      expect((await download).suggestedFilename()).toContain(id);
    }
    await panel.screenshot({ path: info.outputPath("energy-desktop.png") });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect
      .poll(async () =>
        panel
          .getByRole("img")
          .first()
          .evaluate((host) => {
            const svg = host.querySelector("svg");
            return (
              !!svg && svg.getBoundingClientRect().width <= host.clientWidth + 1
            );
          }),
      )
      .toBe(true);
    await panel.screenshot({ path: info.outputPath("energy-mobile.png") });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.goto("/docs?doc=docs%2Fzh%2Fv2-energy.md");
    await expect(page.locator(".markdown .katex").first()).toBeVisible();
    expect(await page.locator(".katex-error").count()).toBe(0);
    expect(errors).toEqual([]);
  } finally {
    await page.request
      .post(`${url}/commands`, { data: { kind: "pause" }, timeout: 5000 })
      .catch(() => {});
  }
});
