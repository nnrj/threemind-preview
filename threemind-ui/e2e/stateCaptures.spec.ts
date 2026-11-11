import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("named and automatic captures bind real checkpoints and survive a lost acknowledgement", async ({
  page,
}, info) => {
  page.setDefaultTimeout(10000);
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "状态命名验收" },
    })
  ).json();
  const run = await (
    await page.request.post(`/api/v2/projects/${project.id}/runs`, {
      data: {
        name: "命名测试意识",
        spec: { environment: "manual", clock: "realtime", duration_s: 60 },
      },
    })
  ).json();
  const base = `/api/v2/projects/${project.id}/runs/${run.id}`;
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  try {
    await page.goto("/");
    await page
      .getByLabel("当前研究项目", { exact: true })
      .selectOption(project.id);
    await page.goto("/settings?section=display#capture-preferences");
    await expect(
      page.getByLabel("捕获状态前询问名称", { exact: true }),
    ).toBeChecked();
    await page.goto(`/runs/${run.id}?view=checkpoints`);
    const section = page.getByRole("region", { name: "状态捕获", exact: true });
    await section
      .getByRole("button", { name: "捕获最新状态", exact: true })
      .click();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "取消", exact: true })
      .click();
    expect(
      (await (await page.request.get(base + "/state-captures")).json()).rows,
    ).toHaveLength(0);
    await section
      .getByRole("button", { name: "捕获最新状态", exact: true })
      .click();
    const modal = page.getByRole("dialog");
    await modal
      .getByLabel("恢复点名称", { exact: true })
      .fill("保留的实验边界");
    await modal
      .getByLabel("保留此恢复点，阻止整份档案被清理", { exact: true })
      .check();
    await page.route("**/state-captures", async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      await route.fetch();
      await route.abort("failed");
    });
    await modal.getByRole("button", { name: "确认捕获", exact: true }).click();
    await expect(modal).toBeHidden(); // The history receipt also acknowledges a lost POST response.
    await page.unroute("**/state-captures");
    await expect(section.locator(".capture-receipt.completed")).toHaveCount(1);
    const manual = (
      await (await page.request.get(base + "/state-captures")).json()
    ).rows[0];
    expect(manual.result.label).toBe("保留的实验边界");
    const cp = await (
      await page.request.get(base + "/versions/" + manual.checkpoint_id)
    ).json();
    expect(cp.label).toBe(manual.result.label);
    expect(cp.state_hash).toBe(manual.result.state_hash);
    expect(cp.pinned).toBe(true);
    await page.goto("/settings?section=display#capture-preferences");
    await page.getByLabel("捕获状态前询问名称", { exact: true }).uncheck();
    await page
      .getByLabel("自动命名方式", { exact: true })
      .selectOption("revision");
    await page.reload();
    await expect(
      page.getByLabel("捕获状态前询问名称", { exact: true }),
    ).not.toBeChecked();
    await page.goto(`/runs/${run.id}?view=checkpoints`);
    await section
      .getByRole("button", { name: "捕获最新状态", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toBeHidden();
    await expect(section.locator(".capture-receipt.completed")).toHaveCount(2);
    const automatic = (
      await (await page.request.get(base + "/state-captures")).json()
    ).rows[0];
    expect(automatic.result.label).toBe(
      `命名测试意识 · r${automatic.result.revision}`,
    );
    expect(automatic.checkpoint_id).not.toBe(manual.checkpoint_id);
    const autoCp = await (
      await page.request.get(base + "/versions/" + automatic.checkpoint_id)
    ).json();
    expect(autoCp.pinned).toBe(false);
    await page.request.post(base + "/commands", { data: { kind: "pause" } });
    await expect
      .poll(async () => (await (await page.request.get(base)).json()).status)
      .toBe("paused");
    await expect(
      section.getByRole("button", { name: "捕获最新状态", exact: true }),
    ).toBeDisabled();
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({
      path: info.outputPath("state-captures-desktop.png"),
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    const selectedTool = await page.locator('.runtime-tabs .active').boundingBox();
    expect(selectedTool!.x + selectedTool!.width).toBeLessThanOrEqual(390);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath("state-captures-mobile.png"),
      fullPage: true,
    });
    expect(errors).toEqual([]);
  } finally {
    await page.request.post(base + "/commands", { data: { kind: "cancel" }, timeout: 5000 }).catch(() => {});
  }
});
