import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

async function subject(page: any) {
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "人工研究控制验收" },
    })
  ).json();
  const root = `/api/v2/projects/${project.id}`;
  const source = await (
    await page.request.post(root + "/runs", {
      data: {
        name: "同源刺激模型",
        spec: {
          environment: "replay",
          clock: "unbounded",
          duration_s: 0.02,
          sample_us: 1000,
          replay: [
            {
              time_us: "0",
              channels: [
                [1, 0.7],
                [2, 0.5],
              ],
              intensity: 1,
            },
          ],
        },
      },
    })
  ).json();
  await expect
    .poll(
      async () =>
        (await (await page.request.get(root + `/runs/${source.id}`)).json())
          .status,
    )
    .toBe("completed");
  const saved = await (
    await page.request.get(root + `/runs/${source.id}`)
  ).json();
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  return { project, root, source: saved };
}

test("manual observations, exact paused sandbox, stepping and fixed evidence views", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const { root, source } = await subject(page);
  await page.goto(`/runs/${source.id}?view=research`);
  const panel = page.getByRole("region", {
    name: "人工实验控制台",
    exact: true,
  });
  await panel
    .getByRole("button", { name: "记录状态摘要", exact: true })
    .click();
  await expect(panel.locator(".research-history article")).toHaveCount(1);
  await panel
    .getByLabel("实验注记", { exact: true })
    .fill("输入之后的原始观察；<script>不执行</script>");
  await panel
    .getByRole("button", { name: "保存恢复点注记", exact: true })
    .click();
  await expect(panel.locator(".research-note")).toContainText(
    "<script>不执行</script>",
  );
  await panel
    .getByRole("button", { name: "从此恢复点创建暂停沙箱", exact: true })
    .click();
  const fork = page.getByRole("dialog", {
    name: "创建同源实验沙箱",
    exact: true,
  });
  await fork
    .getByLabel("沙箱名称", { exact: true })
    .fill("暂停沙箱 · 手动控制");
  await fork.getByRole("button", { name: "创建暂停沙箱", exact: true }).click();
  await expect(page).not.toHaveURL(new RegExp(source.id));
  const id = page.url().match(/runs\/([^?]+)/)![1];
  const base = root + `/runs/${id}`;
  await expect(
    panel.getByRole("button", { name: "推进并暂停", exact: true }),
  ).toBeEnabled();
  const original = await (await page.request.get(base)).json();
  expect(original.status).toBe("paused");
  expect(original.state_hash).toBe(source.state_hash);
  await panel.getByLabel("推进时长（模拟秒）", { exact: true }).fill("0.0037");
  await panel.getByRole("button", { name: "推进并暂停", exact: true }).click();
  await expect
    .poll(async () => (await (await page.request.get(base)).json()).time_us)
    .toBe(String(Number(original.time_us) + 3700));
  await expect
    .poll(async () => (await (await page.request.get(base)).json()).status)
    .toBe("paused");
  await expect(panel.locator(".research-history article")).toContainText(
    "逐步推进",
  );
  await expect(
    panel.getByRole("button", { name: "一个数值步长", exact: true }),
  ).toBeEnabled();
  await panel
    .getByRole("button", { name: "一个数值步长", exact: true })
    .click();
  await expect
    .poll(async () => (await (await page.request.get(base)).json()).time_us)
    .toBe(
      String(Number(original.time_us) + 3700 + original.spec.config.step_us),
    );
  await panel
    .getByRole("button", { name: "查看并记录图谱", exact: true })
    .click();
  const graph = page.getByRole("dialog", {
    name: "固定恢复点的意识图谱",
    exact: true,
  });
  await expect(graph.locator(".graph-webgl-canvas")).toBeVisible();
  await expect(graph).not.toContainText("图数据读取失败");
  await graph.getByRole("button", { name: "关闭", exact: true }).click();
  const event = panel.locator(".research-history article").first();
  const target = await event
    .getByRole("link", { name: "查询该点节点与连接", exact: true })
    .getAttribute("href");
  await event
    .getByRole("link", { name: "查询该点节点与连接", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "数据查询", exact: true }),
  ).toBeVisible();
  const cp = new URL(target!, "http://local").searchParams.get("checkpoint")!;
  await expect(page.getByLabel("状态版本", { exact: true })).toHaveValue(cp);
  await page.goto(`/runs/${id}?view=research`);
  await panel.screenshot({
    path: info.outputPath("research-console-desktop.png"),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(350);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("research-console-mobile.png"),
    fullPage: true,
  });
  const download = page.waitForEvent("download");
  await panel
    .getByRole("link", { name: "导出完整操作记录 JSONL", exact: true })
    .click();
  expect((await download).suggestedFilename()).toContain("research-actions");
  expect(
    (await (await page.request.get(root + `/runs/${source.id}`)).json())
      .state_hash,
  ).toBe(source.state_hash);
  expect(errors).toEqual([]);
});

test("lost advance acknowledgement reuses the request identity without advancing twice", async ({
  page,
}) => {
  const { root, source } = await subject(page);
  const run = await (
    await page.request.post(root + `/runs/${source.id}/forks`, {
      data: { name: "确认丢失的暂停分支", paused: true },
    })
  ).json();
  const base = root + `/runs/${run.id}`;
  let lost = false;
  await page.route(`**${base}/research/actions`, async (route) => {
    if (
      route.request().method() === "POST" &&
      route.request().postDataJSON().kind === "runtime.advance" &&
      !lost
    ) {
      lost = true;
      await route.fetch();
      await route.abort("failed");
    } else await route.continue();
  });
  await page.goto(`/runs/${run.id}?view=research`);
  const panel = page.getByRole("region", {
    name: "人工实验控制台",
    exact: true,
  });
  await panel.getByLabel("推进时长（模拟秒）", { exact: true }).fill("0.003");
  await panel.getByRole("button", { name: "推进并暂停", exact: true }).click();
  await expect(
    panel.getByRole("button", { name: "重试同一操作", exact: true }),
  ).toBeVisible();
  await expect
    .poll(async () => (await (await page.request.get(base)).json()).time_us)
    .toBe(String(Number(run.time_us) + 3000));
  await panel
    .getByRole("button", { name: "重试同一操作", exact: true })
    .click();
  await expect(
    panel.getByRole("button", { name: "重试同一操作", exact: true }),
  ).toBeHidden();
  expect(
    (await (await page.request.get(base + "/research/actions")).json()).rows,
  ).toHaveLength(1);
  expect((await (await page.request.get(base)).json()).time_us).toBe(
    String(Number(run.time_us) + 3000),
  );
});
