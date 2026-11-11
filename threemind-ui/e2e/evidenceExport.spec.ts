import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("evidence download shows checkpoint scope and preserves unscoped lifecycle facts", async ({
  page,
}, info) => {
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "证据边界验收 " + Date.now() },
    })
  ).json();
  const root = "/api/v2/projects/" + project.id;
  const source = await (
    await page.request.post(root + "/runs", {
      data: {
        name: "原始边界",
        spec: {
          environment: "replay",
          clock: "unbounded",
          duration_s: 0.01,
          replay: [
            {
              time_us: "0",
              channels: [
                [1, 0.5],
                [2, 0.3],
              ],
            },
          ],
        },
      },
    })
  ).json();
  await expect
    .poll(
      async () =>
        (await (await page.request.get(root + "/runs/" + source.id)).json())
          .status,
    )
    .toBe("completed");
  const run = await (
    await page.request.post(root + "/runs/" + source.id + "/forks", {
      data: { name: "独立终止事实", paused: true },
    })
  ).json();
  const url = root + "/runs/" + run.id;
  const cancelled = await page.request.post(url + "/commands", {
    data: { kind: "cancel" },
  });
  expect(cancelled.status()).toBe(200);
  const task = await (
    await page.request.post(url + "/exports", { data: { format: "evidence" } })
  ).json();
  let artifactId = "";
  await expect
    .poll(async () => {
      const job = (await (await page.request.get(root + "/jobs")).json()).find(
        (j: any) => j.id === task.id,
      );
      artifactId = job?.result?.artifact_id ?? "";
      return job?.status;
    })
    .toBe("done");
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page.goto("/models?view=artifacts");
  await expect(page.locator(".artifact-evidence-scope")).toContainText(
    "0 条采样、1 条事件",
  );
  await expect(page.locator(".artifact-evidence-scope")).toContainText(
    "提交版本未知，未计入统计",
  );
  const downloaded = page.waitForEvent("download");
  await page.locator(`a[download][href$="/artifacts/${artifactId}"]`).click();
  const download = await downloaded,
    path = info.outputPath("scoped-evidence.zip");
  await download.saveAs(path);
  expect((await readFile(path)).subarray(0, 2).toString()).toBe("PK");
  await page.screenshot({
    path: info.outputPath("evidence-scope-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  const downloadButton = await page
    .locator(".artifact-table a[download]")
    .boundingBox();
  expect(downloadButton).not.toBeNull();
  expect(downloadButton!.x + downloadButton!.width).toBeLessThanOrEqual(390);
  expect(
    (await page.locator(".artifact-evidence-scope").boundingBox())!.width,
  ).toBeGreaterThan(220);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("evidence-scope-mobile.png"),
    fullPage: true,
  });
});
