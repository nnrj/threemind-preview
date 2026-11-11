import { test, expect } from "@playwright/test";
import { stat } from "node:fs/promises";
const pack = () => ({
  schema: "threemind.language-replay/1",
  title: "Recorded fixture",
  description: "Evidence fixture",
  created_on: "2026-10-05",
  width: 1920,
  height: 1080,
  provenance: { core_advanced: false },
  clips: [
    {
      id: "teaching",
      title: "教学片段",
      subtitle: "Original",
      caption: "Recorded teaching",
      duration: 2,
      kind: "card",
      source: "Fixture",
      from: 0,
      to: 0,
      frames: [],
      nodes: {},
      edges: [],
      objects: [],
      events: [],
      evidence: [],
    },
    {
      id: "answer",
      title: "命名片段",
      subtitle: "Independent snapshot",
      caption: "An answer after observation",
      duration: 3,
      motionSeconds: 2,
      kind: "probe",
      source: "Fixture",
      from: 1,
      to: 2,
      frames: [
        { t: 1, nodes: [[1, 0.1, 0.2, 0]] },
        { t: 1.5, nodes: [[1, 0.4, 0.1, 0.1]] },
      ],
      nodes: { "1": 500 },
      edges: [],
      objects: [
        { name: "红球", shape: "sphere", color: "#ea5851", position: [0, 0] },
      ],
      events: [
        { at: 0, role: "input", label: "Teacher", text: "它叫什么？", item: 0 },
        { at: 2, role: "answer", label: "Recorded answer", text: "甲。" },
      ],
      expected: "甲。",
      output: "甲。",
      evidence: ["fixture/process.json"],
    },
  ],
});
async function open(page: any) {
  await page.goto("/e2e/fixtures/language-replay.html");
  await page.waitForFunction(() => !!(window as any).languageReplayHarness);
}
test("seeking does not reveal a future answer; held samples and parser boundaries", async ({
  page,
}) => {
  await open(page);
  await page.evaluate(
    (p) => (window as any).languageReplayHarness.load(p),
    pack(),
  );
  const seek = async (value: number) =>
    page.getByRole("slider", { name: "回放时间轴" }).fill(String(value));
  await seek(3.95);
  await expect(page.locator(".replay-transcript")).toContainText("它叫什么？");
  await expect(page.locator(".replay-transcript .answer")).toHaveCount(0);
  await seek(4);
  await expect(page.locator(".replay-transcript .answer")).toHaveText(/甲。/);
  await seek(2.5);
  await expect(page.locator(".replay-transcript .answer")).toHaveCount(0);
  expect(
    await page.evaluate(() => {
      const h = (window as any).languageReplayHarness;
      return [
        h.heldSample([{ t: 1 }, { t: 2 }], 0.9) ?? null,
        h.heldSample([{ t: 1 }, { t: 2 }], 1.5).t,
      ];
    }),
  ).toEqual([null, 1]);
  expect(
    await page.evaluate((p) => {
      p.clips[1].frames.reverse();
      try {
        (window as any).languageReplayHarness.validate(p);
        return false;
      } catch {
        return true;
      }
    }, pack()),
  ).toBe(true);
});
test("library uses read-only artifacts, supports local import, screenshots and recording at narrow width", async ({
  page,
}) => {
  const requests: string[] = [];
  await page.route("**/api/**", async (route) => {
    requests.push(route.request().method());
    if (route.request().url().endsWith("/artifacts"))
      await route.fulfill({
        json: [
          {
            id: "replay-1",
            name: "Evidence replay",
            bytes: 4000,
            media_type: "application/json",
            metadata: { schema: "threemind.language-replay/1" },
          },
          {
            id: "mp4-1",
            name: "Movie",
            bytes: 100,
            media_type: "video/mp4",
            metadata: { replay_artifact_id: "replay-1" },
          },
        ],
      });
    else await route.fulfill({ json: pack() });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page);
  await page.evaluate(() =>
    (window as any).languageReplayHarness.page("fixture-project"),
  );
  await expect(page.getByRole("link", { name: "下载完整MP4" })).toHaveAttribute(
    "href",
    /mp4-1$/,
  );
  await expect(page.locator(".replay-canvas")).toHaveClass(/focused/);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const png = page.waitForEvent("download");
  await page.getByRole("button", { name: "截图", exact: true }).click();
  const shot = await png;
  expect(shot.suggestedFilename()).toMatch(/\.png$/);
  expect((await stat((await shot.path())!)).size).toBeGreaterThan(1000);
  await page.getByText("导出高级选项", { exact: true }).click();
  await page.getByRole("spinbutton", { name: "最长录制秒数" }).fill("3");
  const webm = page.waitForEvent("download", { timeout: 10000 });
  await page.getByRole("button", { name: "录屏", exact: true }).click();
  const video = await webm;
  expect(video.suggestedFilename()).toMatch(/\.webm$/);
  expect((await stat((await video.path())!)).size).toBeGreaterThan(1000);
  await page
    .getByLabel("打开回放文件", { exact: true })
    .setInputFiles({
      name: "invalid.json",
      mimeType: "application/json",
      buffer: Buffer.from('{"schema":"unknown"}'),
    });
  await expect(page.getByRole("alert")).toContainText("Unsupported");
  await page
    .getByLabel("打开回放文件", { exact: true })
    .setInputFiles({
      name: "valid.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(pack())),
    });
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByRole("slider", { name: "回放时间轴" })).toBeVisible();
  expect(requests.every((m) => m === "GET")).toBe(true);
});
