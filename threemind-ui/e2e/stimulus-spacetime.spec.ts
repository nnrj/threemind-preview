import { test, expect } from "@playwright/test";

test.skip(!process.env.THREEMIND_E2E_URL, "Requires the isolated test API");
for (const width of [1440, 390]) {
  test(`stimulus controls and world 2 at ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const project = await (
      await page.request.post("/api/v2/projects", {
        data: { name: `Stimulus ${width}` },
      })
    ).json();
    await page.addInitScript(
      (id) => localStorage.setItem("tm2.project", id),
      project.id,
    );
    const run = await (
      await page.request.post(`/api/v2/projects/${project.id}/runs`, {
        data: {
          name: "Input acceptance",
          spec: { environment: "manual", clock: "unbounded" },
        },
      })
    ).json();
    expect(run.id, JSON.stringify(run)).toBeTruthy();
    await page.goto(`/runs/${run.id}?view=conversation`);
    const text = page.getByLabel("文本载体", { exact: true });
    await expect(text).toBeVisible();
    await page.getByLabel("强度预设", { exact: true }).selectOption("strong");
    await expect(page.getByLabel("刺激强度数值", { exact: true })).toHaveValue(
      "4",
    );
    await text.fill("甲是松子。");
    const receipt = page.waitForResponse(
      (r) => r.url().endsWith("/inputs") && r.request().method() === "POST",
    );
    await text.press("Enter");
    const sent = await receipt;
    expect(sent.status()).toBe(202);
    expect(sent.request().postDataJSON().payload).toEqual({
      text: "甲是松子。",
      intensity: 4,
    });
    await expect(text).toHaveValue("");
    await page.getByLabel("刺激强度数值", { exact: true }).fill("0.55");
    await expect(page.getByLabel("强度预设", { exact: true })).toHaveValue(
      "custom",
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBeTruthy();
    await page.screenshot({ path: info.outputPath(`chat-${width}.png`) });
    await page.goto("/worlds");
    await page.getByRole("button", { name: "新建世界", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "新建世界", exact: true });
    await dialog
      .getByLabel("物理场景模板", { exact: true })
      .selectOption("gravity-pendulum");
    await dialog
      .getByRole("button", { name: "切换到 JSON 编辑", exact: true })
      .click();
    const request = page.waitForRequest((r) =>
      r.url().endsWith("/worlds/validate"),
    );
    await dialog
      .getByRole("button", { name: "校验与预览", exact: true })
      .click();
    const protocol = (await request).postDataJSON().protocol;
    expect(protocol.schema_id).toBe("threemind.world/2");
    expect(
      protocol.sensors.some((s: any) => s.kind === "accelerometer"),
    ).toBeTruthy();
    expect(
      protocol.sensors.some((s: any) => s.kind === "gyroscope"),
    ).toBeTruthy();
    await dialog
      .getByRole("button", { name: "切换到图形配置", exact: true })
      .click();
    if (width < 1000)
      await dialog.getByRole("tab", { name: "观察", exact: true }).click();
    await expect(dialog.locator(".world-scene canvas")).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBeTruthy();
    await page.screenshot({ path: info.outputPath(`world-${width}.png`) });
    expect(errors).toEqual([]);
  });
}
