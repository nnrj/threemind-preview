import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("resource controls synchronize null and zero, apply on pause, and export committed evidence", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `预算验收 ${new Date().toISOString()}` },
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
  await dialog.getByLabel("运行名称").fill("容量与预算 · 可追溯限制");
  await dialog
    .getByLabel("环境与感官来源", { exact: true })
    .selectOption("manual");
  await dialog.getByLabel("运行时长（模拟秒）", { exact: true }).fill("40");
  await dialog.locator(".configuration-advanced > summary").click();
  await dialog
    .getByLabel("高级参数分类", { exact: true })
    .selectOption("resources");
  const capacity = dialog.getByLabel("模型节点容量", { exact: true });
  await expect(capacity).toHaveValue("");
  await capacity.fill("3");
  await dialog.getByLabel("模型连接容量", { exact: true }).fill("3");
  await dialog.getByLabel("每步兴奋传播预算", { exact: true }).fill("0");
  await dialog.getByLabel("每步连接适应预算", { exact: true }).fill("4");
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  const validation = page.waitForRequest((r) =>
    r.url().endsWith("/configuration/validate"),
  );
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  const spec = (await validation).postDataJSON().spec;
  expect(spec.config.propagation_limit).toBe(0);
  expect(spec.config.max_nodes).toBe(3);
  spec.config.propagation_limit = 1;
  await dialog
    .getByRole("textbox", { name: "JSON 参数", exact: true })
    .fill(JSON.stringify(spec));
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(
    dialog.getByLabel("每步兴奋传播预算", { exact: true }),
  ).toHaveValue("1");
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
                [2, 0.7],
                [3, 0.6],
                [4, 0.5],
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
          (await (await page.request.get(`${url}/resources`)).json()).latest
            ?.node_capacity_rejections,
      )
      .toBe("1");
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
      .selectOption("resources");
    await capacity.fill("1");
    await dialog.getByLabel("每步兴奋传播预算", { exact: true }).fill("");
    await dialog.getByRole("button", { name: "保存配置", exact: true }).click();
    await expect(dialog).toHaveCount(0);
    const row = await (await page.request.get(url)).json();
    expect(row.metrics.nodes).toBe(3);
    expect(row.spec.config.propagation_limit).toBeNull();
    await page.getByRole("button", { name: "动力学", exact: true }).click();
    await page.getByRole("button", { name: "容量与预算", exact: true }).click();
    const panel = page.getByRole("region", {
      name: "容量与预算记录",
      exact: true,
    });
    await expect(panel).toContainText("节点出生受限");
    await expect(panel.locator(".resource-limit-summary")).toContainText(
      "不限制",
    );
    await expect(panel.locator("tbody tr").first()).toBeVisible();
    await panel.getByLabel("起始时间（微秒）").fill("999999999999");
    await panel.getByRole("button", { name: "应用筛选" }).click();
    await expect(panel).toContainText("所选区间暂无预算观测");
    await panel.getByLabel("起始时间（微秒）").fill("0");
    await panel.getByRole("button", { name: "应用筛选" }).click();
    await expect(panel.locator("tbody tr").first()).toBeVisible();
    const download = page.waitForEvent("download");
    await panel
      .getByRole("link", { name: "导出筛选 JSONL", exact: true })
      .click();
    expect((await download).suggestedFilename()).toBe(`resources-${id}.jsonl`);
    await panel.screenshot({
      path: info.outputPath("resource-evidence-desktop.png"),
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await panel.screenshot({
      path: info.outputPath("resource-evidence-mobile.png"),
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    expect(errors).toEqual([]);
  } finally {
    await page.request
      .post(`${url}/commands`, { data: { kind: "pause" }, timeout: 5000 })
      .catch(() => {});
  }
});
