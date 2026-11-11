import { test, expect } from "@playwright/test";
import { writeFile } from "node:fs/promises";

test.skip(!process.env.THREEMIND_E2E_URL, "Requires an isolated workstation.");
test.use({
  permissions: ["microphone"],
  launchOptions: {
    args: [
      "--use-fake-device-for-media-stream",
      "--use-fake-ui-for-media-stream",
    ],
  },
});

for (const environment of ["manual", "mujoco", "replay"])
  test(`${environment}: default ear and mouth sustain capture without losing packet order`, async ({
    page,
  }, info) => {
    test.setTimeout(120000);
    const project = await (
      await page.request.post("/api/v2/projects", {
        data: { name: `默认听觉持续采集 ${Date.now()}` },
      })
    ).json();
    const root = `/api/v2/projects/${project.id}`;
    const created = await page.request.post(`${root}/runs`, {
      data: {
        name: "默认耳朵与嘴巴吞吐验收",
        spec: {
          environment,
          clock: "realtime",
          duration_s: 90,
          ...(environment === "replay"
            ? {
                replay: Array.from({ length: 16 }, (_, group) => ({
                  time_us: "0",
                  intensity: 1,
                  channels: Array.from({ length: 64 }, (_, i) => [
                    10000 + group * 64 + i,
                    0.5,
                  ]),
                })),
              }
            : {}),
        },
      },
    });
    expect(created.status()).toBe(201);
    const run = await created.json(),
      base = `${root}/runs/${run.id}`;
    const timings: { status: number; ms: number }[] = [];
    const starts = new Map<any, number>();
    page.on("request", (r) => {
      if (r.method() === "POST" && /\/capture\/[^/]+\/packets$/.test(r.url()))
        starts.set(r, Date.now());
    });
    page.on("response", (r) => {
      if (starts.has(r.request()))
        timings.push({
          status: r.status(),
          ms: Date.now() - starts.get(r.request())!,
        });
    });
    try {
      await page.goto("/");
      await page
        .getByLabel("当前研究项目", { exact: true })
        .selectOption(project.id);
      await page.goto(`/runs/${run.id}`);
      const sidebar = page.locator(".inspector");
      await sidebar
        .getByRole("button", { name: "耳朵 · 已关闭", exact: true })
        .click();
      await expect(
        sidebar.getByRole("button", { name: "耳朵 · 已开启", exact: true }),
      ).toBeVisible({ timeout: 35000 });
      await sidebar
        .getByRole("button", { name: "嘴巴 · 已关闭", exact: true })
        .click();
      await expect(
        sidebar.getByRole("button", { name: "嘴巴 · 已开启", exact: true }),
      ).toBeVisible({ timeout: 35000 });
      await page.waitForTimeout(25000);
      const sessions = await (await page.request.get(`${base}/capture`)).json();
      await writeFile(
        info.outputPath("capture-latency.json"),
        JSON.stringify({ timings, sessions }, null, 2),
      );
      await info.attach("capture-latency.json", {
        body: JSON.stringify({ timings, sessions }, null, 2),
        contentType: "application/json",
      });
      await expect(
        sidebar.getByRole("button", { name: "耳朵 · 已开启", exact: true }),
      ).toBeVisible();
      expect(sessions.rows[0].next_sequence).toBeGreaterThanOrEqual(100);
      expect(timings.filter((t) => t.status !== 202)).toEqual([]);
      await sidebar
        .getByRole("button", { name: "耳朵 · 已开启", exact: true })
        .click();
      await expect(
        sidebar.getByRole("button", { name: "耳朵 · 已关闭", exact: true }),
      ).toBeVisible();
      const session = (await (await page.request.get(`${base}/capture`)).json())
        .rows[0];
      expect(session.status).toBe("stopped");
      const packets = (
        await (
          await page.request.get(
            `${base}/capture/${session.id}/packets?limit=100`,
          )
        ).json()
      ).rows;
      expect(packets.map((p: any) => p.sequence)).toEqual(
        packets.map((_: any, i: number) => i),
      );
    } finally {
      await page.request.post(`${base}/commands`, { data: { kind: "pause" } });
    }
  });
