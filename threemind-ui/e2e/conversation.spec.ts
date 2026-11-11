import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly isolated workstation.",
);

test("mixed chat, live receipt status, forward bursts, stable reading and bounded viewport", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `连续聊天验收 ${Date.now()}` },
    })
  ).json();
  const run = await (
    await page.request.post(`/api/v2/projects/${project.id}/runs`, {
      data: {
        name: "混合读出与历史游标",
        spec: {
          environment: "manual",
          clock: "realtime",
          duration_s: 180,
          checkpoint_us: 500000,
          text_sensor: { encoding: "literal-character" },
          structural_readout: { interval_us: 1000000 },
          config: {
            activation_decay_enabled: false,
            inhibition_gain: 0,
            propagation_rate: 0,
          },
        },
      },
    })
  ).json();
  expect(run.id, JSON.stringify(run)).toBeTruthy();
  const base = `/api/v2/projects/${project.id}/runs/${run.id}`;
  try {
    await page.goto("/");
    await page
      .getByLabel("当前研究项目", { exact: true })
      .selectOption(project.id);
    await page.goto(`/runs/${run.id}?view=conversation`);
    const panel = page.locator(".conversation-panel"),
      list = panel.getByRole("log");
    await expect(
      panel.getByRole("heading", { name: "意识读出", exact: true }),
    ).toBeVisible();
    await expect(panel.getByLabel("消息类别", { exact: true })).toHaveCount(0);
    const layoutWidth = (await page
      .locator(".conversation-layout")
      .boundingBox())!.width;
    expect((await panel.boundingBox())!.width).toBeGreaterThanOrEqual(
      layoutWidth - 2,
    );
    const input = page.getByLabel("文本载体", { exact: true });
    await input.fill("甲是松子。");
    await input.press("Enter");
    await expect(input).toHaveValue("");
    await expect(
      list
        .locator("article.stimulus-message")
        .filter({ hasText: "甲是松子。" }),
    ).toContainText("全部帧已处理");
    await expect
      .poll(
        async () =>
          (
            await (
              await page.request.get(`${base}/readouts?kind=temporal_readout`)
            ).json()
          ).rows.length,
      )
      .toBeGreaterThan(0);
    await expect(
      list.locator(".readout-plain").filter({ hasText: "甲" }).first(),
    ).toBeVisible();
    await expect(
      list.getByText("时序读出", { exact: true }).first(),
    ).toBeVisible();
    await page.screenshot({
      path: info.outputPath("mixed-chat.png"),
      fullPage: true,
    });
    await page.request.post(`${base}/commands`, { data: { kind: "pause" } });
    await expect
      .poll(async () => (await (await page.request.get(base)).json()).status)
      .toBe("paused");
    const before = await (await page.request.get(base)).json();
    const temporalMessage = list
      .locator("article")
      .filter({ has: page.getByText("时序读出", { exact: true }) })
      .first();
    await temporalMessage.locator("summary").click();
    await expect(temporalMessage.locator("table tbody tr")).toHaveCount(5);
    await temporalMessage.locator("summary").click();
    const send = async (text: string) => {
      const res = await page.request.post(`${base}/inputs`, {
        data: {
          adapter_id: "text-sensor",
          request_id: randomUUID(),
          payload: { text },
        },
      });
      expect(res.status()).toBe(202);
    };
    for (let i = 0; i < 145; i++) await send(`甲。${i}`);
    await expect(list.getByText("甲。144", { exact: true })).toBeVisible();
    expect(await list.locator("article").count()).toBeLessThan(30);
    await list.evaluate((el) => {
      el.scrollTop = Math.max(0, el.scrollTop - 650);
      el.dispatchEvent(new Event("scroll"));
    });
    await page.waitForTimeout(400);
    const anchor = await list.locator("article").evaluateAll((nodes) => {
      const root = nodes[0].closest('[role="log"]')!.getBoundingClientRect();
      const node = nodes.find(
        (n) => n.getBoundingClientRect().top >= root.top,
      )!;
      return {
        id: node.getAttribute("data-message-id"),
        top: node.getBoundingClientRect().top,
      };
    });
    await send("翻阅期间的新刺激。");
    await expect(
      panel.getByRole("button", { name: "有新消息 · 回到最新", exact: true }),
    ).toBeVisible();
    expect(
      Math.abs(
        (await list
          .locator(`article[data-message-id="${anchor.id}"]`)
          .boundingBox())!.y - anchor.top,
      ),
    ).toBeLessThan(3);
    await panel
      .getByRole("button", { name: "有新消息 · 回到最新", exact: true })
      .click();
    await expect(
      list.getByText("翻阅期间的新刺激。", { exact: true }),
    ).toBeVisible();
    await panel
      .getByRole("button", { name: "加载更早消息", exact: true })
      .click();
    await list.evaluate((el) => {
      el.scrollTop = 0;
      el.dispatchEvent(new Event("scroll"));
    });
    await expect
      .poll(async () => await list.locator("article").first().innerText(), {
        timeout: 10000,
      })
      .toContain("甲。");
    await expect(list.locator("article")).not.toHaveCount(0);
    const after = await (await page.request.get(base)).json();
    expect(after.revision).toBe(before.revision);
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
    const toolbar = page.locator(".chat-organ-row");
    const toolbarBox = (await toolbar.boundingBox())!;
    for (const button of await toolbar.getByRole("button").all()) {
      const box = (await button.boundingBox())!;
      expect(box.x + box.width).toBeLessThanOrEqual(
        toolbarBox.x + toolbarBox.width + 1,
      );
    }
    await page.screenshot({
      path: info.outputPath("mixed-chat-mobile.png"),
      fullPage: true,
    });
    expect(errors).toEqual([]);
  } finally {
    await page.request.post(`${base}/commands`, { data: { kind: "pause" } });
  }
});
