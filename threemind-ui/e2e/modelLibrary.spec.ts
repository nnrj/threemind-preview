import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);
test("model annotations, exact origins, archive protection and reviewed cleanup", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "模型档案与清理验收" },
    })
  ).json();
  const root = `/api/v2/projects/${project.id}`;
  async function create(name: string) {
    const response = await page.request.post(root + "/runs", {
      data: {
        name,
        spec: {
          environment: "replay",
          clock: "unbounded",
          duration_s: 0.04,
          checkpoint_us: 10000,
          replay: [
            {
              time_us: "0",
              channels: [
                [1, 0.8],
                [2, 0.6],
              ],
            },
          ],
        },
      },
    });
    expect(response.status()).toBe(201);
    const run = await response.json();
    await expect
      .poll(
        async () =>
          (await (await page.request.get(`${root}/runs/${run.id}`)).json())
            .status,
      )
      .toBe("completed");
    return run;
  }
  const run = await create("待整理的意识"),
    url = `${root}/runs/${run.id}`;
  const baseline = await (await page.request.get(url)).json();
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page.goto("/models");
  const library = page.getByRole("region", {
    name: "意识模型档案库",
    exact: true,
  });
  await library.getByRole("button", { name: "编辑档案", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("意识名称", { exact: true })
    .fill("触觉研究 · 原型甲");
  await dialog
    .getByLabel("档案说明", { exact: true })
    .fill("从物理刺激形成的连接出发，保留基线版本用于后续比较。");
  await dialog.getByLabel("档案标签", { exact: true }).fill("触觉，基线");
  await dialog.getByRole("button", { name: "保存档案", exact: true }).click();
  await expect(dialog).toBeHidden();
  await library.getByLabel("搜索意识档案", { exact: true }).fill("原型甲");
  await expect(library.locator(".library-card")).toHaveCount(1);
  await library.getByRole("link", { name: "版本与谱系", exact: true }).click();
  const versions = page.getByRole("region", {
    name: "恢复点与谱系",
    exact: true,
  });
  await versions
    .locator(".library-version-list article")
    .first()
    .getByRole("button", { name: "编辑版本注释", exact: true })
    .click();
  await dialog.getByLabel("恢复点名称", { exact: true }).fill("触觉基线检查点");
  await dialog
    .getByLabel("版本笔记", { exact: true })
    .fill("保存观察说明，不改写当时的网络状态。");
  await dialog.getByLabel("版本标签", { exact: true }).fill("基线");
  await dialog.getByLabel("保留此版本，阻止档案清理", { exact: true }).check();
  await dialog
    .getByRole("button", { name: "保存版本注释", exact: true })
    .click();
  await expect(dialog).toBeHidden();
  await versions.getByLabel("搜索恢复点注释", { exact: true }).fill("触觉基线");
  await expect(versions.locator(".library-version-list article")).toHaveCount(
    1,
  );
  const download = page.waitForEvent("download");
  await versions
    .getByRole("link", { name: "导出档案注释", exact: true })
    .click();
  const file = await download;
  const annotations = await readFile((await file.path())!, "utf8");
  expect(annotations).toContain("触觉基线检查点");
  const beforeFork = await (
    await page.request.get(url + "/versions?q=触觉基线")
  ).json();
  await versions
    .getByRole("button", { name: "从此版本分叉", exact: true })
    .click();
  await dialog.getByLabel("分支名称", { exact: true }).fill("触觉比较分支");
  await dialog.getByRole("button", { name: "创建分支", exact: true }).click();
  await expect(dialog).toBeHidden();
  await page.goto(`/runs/${run.id}?view=checkpoints`);
  await versions
    .getByRole("button", { name: "来源与后代", exact: true })
    .click();
  await expect(
    versions.getByRole("link", { name: "触觉比较分支", exact: true }),
  ).toBeVisible();
  const children = (await (await page.request.get(url + "/lineage")).json())
    .children;
  expect(children[0].origin_checkpoint_id).toBe(beforeFork.rows[0].id);
  await page.getByRole("button", { name: "编辑档案", exact: true }).click();
  await dialog.getByLabel("归档已结束的意识", { exact: true }).check();
  await dialog.getByRole("button", { name: "保存档案", exact: true }).click();
  await expect(dialog).toBeHidden();
  const after = await (await page.request.get(url)).json();
  expect(after.state_hash).toBe(baseline.state_hash);
  expect(after.revision).toBe(baseline.revision);
  await page.goto("/models");
  await library
    .getByRole("combobox", { name: "归档范围", exact: true })
    .selectOption("archived");
  await library.getByRole("button", { name: "清理预览", exact: true }).click();
  await expect(dialog).toContainText("后代意识引用");
  await expect(dialog).toContainText("已保留的恢复点");
  await expect(
    dialog.getByRole("button", { name: "确认清理整份档案", exact: true }),
  ).toBeDisabled();
  await dialog.getByLabel("关闭", { exact: true }).click();
  await library.screenshot({
    path: info.outputPath("model-library-desktop.png"),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(350);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(391);
  await page.screenshot({
    path: info.outputPath("model-library-mobile.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  // Only this test's own disposable subject is permanently removed.
  const disposable = await create("允许清理的测试档案"),
    disposeUrl = `${root}/runs/${disposable.id}`;
  const item = await (await page.request.get(disposeUrl)).json();
  expect(
    (
      await page.request.patch(disposeUrl + "/metadata", {
        data: {
          name: item.name,
          archived: true,
          expected_metadata_revision: item.metadata_revision,
        },
      })
    ).status(),
  ).toBe(200);
  await library.getByRole("button", { name: "刷新", exact: true }).click();
  const card = library
    .locator(".library-card")
    .filter({ has: page.getByRole("link", { name: item.name, exact: true }) });
  await card.getByRole("button", { name: "清理预览", exact: true }).click();
  await expect(
    dialog.getByRole("button", { name: "确认清理整份档案", exact: true }),
  ).toBeDisabled();
  await dialog
    .getByLabel("输入完整意识名称以确认清理", { exact: true })
    .fill(item.name);
  await dialog
    .getByRole("button", { name: "确认清理整份档案", exact: true })
    .click();
  await expect(dialog).toBeHidden();
  await expect(card).toHaveCount(0);
  expect((await page.request.get(disposeUrl)).status()).toBe(404);
  await library
    .getByRole("button", { name: "查看清理记录", exact: true })
    .click();
  await expect(
    library.getByText(item.name + " ·", { exact: false }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
