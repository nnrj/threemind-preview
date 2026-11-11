import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("causal spatial controls, historical geometry, projected axes and complete export", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `因果空间验收 ${new Date().toISOString()}` },
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
  await dialog.getByLabel("运行名称").fill("空间 · 固定发育几何");
  await dialog
    .getByLabel("环境与感官来源", { exact: true })
    .selectOption("manual");
  await dialog.getByLabel("运行时长（模拟秒）", { exact: true }).fill("60");
  await dialog.locator(".configuration-advanced > summary").click();
  await dialog
    .getByLabel("高级参数分类", { exact: true })
    .selectOption("spatial");
  await dialog.getByLabel("启用因果空间基底", { exact: true }).check();
  await dialog.getByLabel("因果空间维数", { exact: true }).fill("4");
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  const validation = page.waitForRequest((r) =>
    r.url().endsWith("/configuration/validate"),
  );
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  const spec = (await validation).postDataJSON().spec;
  expect(spec.config.spatial_embedding).toBe(true);
  expect(spec.config.spatial_dimensions).toBe(4);
  spec.config.spatial_dimensions = 3;
  spec.config.spatial_radius = 4;
  await dialog
    .getByRole("textbox", { name: "JSON 参数", exact: true })
    .fill(JSON.stringify(spec));
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(dialog.getByLabel("因果空间维数", { exact: true })).toHaveValue(
    "3",
  );
  await expect(dialog.getByLabel("空间邻域半径", { exact: true })).toHaveValue(
    "4",
  );
  await dialog.getByRole("button", { name: "创建并开始", exact: true }).click();
  await expect(page).toHaveURL(/\/runs\//);
  const id = page.url().split("/runs/")[1].split(/[?#]/)[0];
  const url = `/api/v2/projects/${project.id}/runs/${id}`;
  const pause = async () => {
    await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
    await expect
      .poll(async () => (await (await page.request.get(url)).json()).status)
      .toBe("paused");
  };
  try {
    const carrier = await page.request.post(`${url}/inputs`, {
      data: {
        adapter_id: "anonymous-frames",
        request_id: crypto.randomUUID(),
        payload: {
          frames: [
            {
              time_us: "0",
              channels: Array.from({ length: 12 }, (_, i) => [
                i + 1,
                0.6 + 0.02 * i,
              ]),
              intensity: 1,
            },
          ],
        },
      },
    });
    expect(carrier.status()).toBe(202);
    await expect
      .poll(
        async () => (await (await page.request.get(url)).json()).metrics.nodes,
      )
      .toBe(12);
    await pause();
    const old = (
      await (await page.request.get(`${url}/checkpoint-history`)).json()
    ).rows[0];
    await page.getByRole("button", { name: "动力学", exact: true }).click();
    await page.getByRole("button", { name: "空间基底", exact: true }).click();
    const panel = page.getByRole("region", {
      name: "因果空间基底",
      exact: true,
    });
    await expect(panel.getByLabel("空间检查点", { exact: true })).toHaveValue(
      old.id,
    );
    await expect(panel.locator(".graph-footer")).toContainText("12 节点");
    await panel.getByLabel("Z 投影轴", { exact: true }).selectOption("-1");
    await panel.getByLabel("X 投影轴", { exact: true }).selectOption("2");
    await expect(panel.locator(".graph-footer")).toContainText(
      `r${old.revision}`,
    );
    const initial = await (
      await page.request.get(`${url}/spatial?checkpoint_id=${old.id}`)
    ).json();
    expect(initial.summary.neighbor_edges).toBe(132);
    const projected = await (
      await page.request.get(
        `${url}/spatial/graph?checkpoint_id=${old.id}&axes=2,1,-1`,
      )
    ).json();
    expect(projected.nodes[0].position).toEqual([
      initial.nodes[0].position[2],
      initial.nodes[0].position[1],
      0,
    ]);
    await panel
      .getByRole("button", { name: "配置空间参数", exact: true })
      .click();
    await expect(
      dialog.getByRole("button", { name: "保存配置", exact: true }),
    ).toBeEnabled();
    await dialog.locator(".configuration-advanced > summary").click();
    await dialog
      .getByLabel("高级参数分类", { exact: true })
      .selectOption("spatial");
    await dialog.getByLabel("因果空间维数", { exact: true }).fill("4");
    await dialog.getByLabel("空间邻域半径", { exact: true }).fill("0.01");
    await dialog.getByRole("button", { name: "保存配置", exact: true }).click();
    await expect(dialog).toBeHidden();
    await expect(panel.getByLabel("空间检查点", { exact: true })).toHaveValue(
      old.id,
    );
    await panel
      .getByRole("button", { name: "刷新当前组", exact: true })
      .click();
    await expect(
      panel.getByLabel("空间检查点", { exact: true }),
    ).not.toHaveValue(old.id);
    await expect(panel.locator(".metrics-grid")).toContainText("4");
    const latest = await (await page.request.get(`${url}/spatial`)).json();
    expect(latest.summary.parameters.spatial_dimensions).toBe(4);
    expect(latest.summary.neighbor_edges).toBe(0);
    expect(latest.total_edges).toBe(132);
    await panel.getByLabel("空间检查点", { exact: true }).selectOption(old.id);
    await expect(panel.locator(".graph-footer")).toContainText(
      `r${old.revision}`,
    );
    for (const name of ["节点坐标 CSV", "连接距离 CSV", "完整几何 JSONL"]) {
      const download = page.waitForEvent("download");
      await panel.getByRole("link", { name, exact: true }).click();
      expect((await download).suggestedFilename()).toContain(
        `-r${old.revision}-`,
      );
    }
    expect(
      (
        await (
          await page.request.get(`${url}/spatial?checkpoint_id=${old.id}`)
        ).json()
      ).state_hash,
    ).toBe(old.state_hash);
    await panel.screenshot({ path: info.outputPath("spatial-desktop.png") });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect
      .poll(async () =>
        page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      )
      .toBe(true);
    await panel.screenshot({ path: info.outputPath("spatial-mobile.png") });
    await page.goto("/docs?doc=docs%2Fzh%2Fv2-spatial.md");
    await expect(page.locator(".markdown .katex").first()).toBeVisible();
    expect(await page.locator(".katex-error").count()).toBe(0);
    expect(errors).toEqual([]);
  } finally {
    await page.request
      .post(`${url}/commands`, { data: { kind: "pause" }, timeout: 5000 })
      .catch(() => {});
  }
});
