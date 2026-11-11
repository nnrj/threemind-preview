import { test, expect } from "@playwright/test";
import { createServer, type Server } from "node:http";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);
let server: Server,
  origin = "";
const received: any[] = [];
test.beforeAll(async () => {
  server = createServer((req, res) => {
    let raw = "";
    req.on("data", (chunk) => {
      raw += chunk;
    });
    req.on("end", () => {
      const body = JSON.parse(raw),
        evidence = JSON.parse(body.messages[1].content).evidence;
      received.push(evidence);
      const sources = evidence.sources;
      const blocks: any[] = sources.map((s: any, i: number) => ({
        id: `data_${i}`,
        type: "table",
        source: s.id,
        metrics: Object.keys(s.metrics).slice(0, 16),
        title: "原始数值",
      }));
      for (const r of evidence.records)
        for (const b of r.blocks)
          blocks.push({
            id: `reference_${blocks.length}`,
            type: "record_block",
            record_id: r.record_id,
            revision: r.revision,
            block_id: b.id,
          });
      blocks.push({
        id: "limits",
        type: "commentary",
        section: "limitations",
        markdown: "本地工程夹具；需要人工复核，缺失不补零，不能据此断言意识。",
      });
      if (evidence.scope.objective === "invalid-fixture")
        blocks[0].values = [999];
      const spec = {
        kind: evidence.scope.kind,
        title:
          evidence.scope.kind === "record" ? "AI 待核查记录" : "AI 待核查报告",
        sources: sources.map((s: any) => s.id),
        blocks,
      };
      res.writeHead(200, { "Content-Type": "text/event-stream" });
      res.write(
        `data: ${JSON.stringify({ choices: [{ index: 0, delta: { content: JSON.stringify(spec) } }] })}\n\n`,
      );
      res.write(
        `data: ${JSON.stringify({ choices: [{ index: 0, delta: {}, finish_reason: "stop" }], usage: { prompt_tokens: 200, completion_tokens: 100 } })}\n\n`,
      );
      res.end("data: [DONE]\n\n");
    });
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  origin = `http://127.0.0.1:${typeof address === "object" && address ? address.port : ""}/v1`;
});
test.afterAll(async () => {
  if (server)
    await new Promise<void>((resolve) => server.close(() => resolve()));
});

async function fixture(page: any) {
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "AI 研究文档工程验收 " + Date.now() },
    })
  ).json();
  const base = `/api/v2/projects/${project.id}`;
  const provider = await (
    await page.request.post(base + "/ai/providers", {
      data: {
        config: {
          name: "本地文档验收",
          base_url: origin,
          model: "fixture-research",
          enabled: true,
        },
      },
    })
  ).json();
  const run = await (
    await page.request.post(base + "/runs", {
      data: {
        name: "AI 文档固定来源",
        spec: {
          environment: "replay",
          clock: "unbounded",
          duration_s: 0.15,
          sample_us: 1000,
          replay: [
            {
              time_us: "0",
              channels: [
                [1, 0.7],
                [2, 0.6],
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
        (await (await page.request.get(`${base}/runs/${run.id}`)).json())
          .status,
    )
    .toBe("completed");
  const source = await (
    await page.request.post(base + "/report-sources", {
      data: {
        operation_id: crypto.randomUUID(),
        kind: "trajectory",
        run_id: run.id,
        metrics: ["activation", "edges", "mean_weight"],
      },
    })
  ).json();
  await expect
    .poll(
      async () =>
        !!(
          await (
            await page.request.get(`${base}/report-sources/${source.id}`)
          ).json()
        ).content_hash,
    )
    .toBeTruthy();
  await page.addInitScript(
    (id: string) => localStorage.setItem("tm2.project", id),
    project.id,
  );
  return { base, provider, run, source };
}

test("AI records: complete preview, lost acknowledgement, independent draft and rejected fabrication", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const { base, provider, source } = await fixture(page);
  const count = received.length;
  await page.goto("/reports");
  await page.getByRole("button", { name: "AI 生成", exact: true }).click();
  const dialog = page.getByRole("dialog", {
    name: "AI 生成实验记录",
    exact: true,
  });
  await dialog
    .getByLabel("AI 供应商", { exact: true })
    .selectOption(provider.id);
  await dialog
    .getByRole("button", { name: "添加数据来源", exact: true })
    .click();
  await page.getByRole("button", { name: "使用此来源", exact: true }).click();
  await dialog
    .getByRole("button", { name: "预览发送内容", exact: true })
    .click();
  await expect(
    dialog.getByRole("heading", { name: "即将发送的证据", exact: true }),
  ).toBeVisible();
  await dialog
    .locator("summary")
    .filter({ hasText: "查看完整发送内容" })
    .click();
  await expect(dialog.locator("pre").first()).toContainText(
    "aggregate-all-captured-rows/1",
  );
  await dialog
    .locator("summary")
    .filter({ hasText: "查看完整发送内容" })
    .click();
  let drop = true;
  await page.route("**/research-generation", async (route) => {
    if (route.request().method() === "POST" && drop) {
      drop = false;
      await route.fetch();
      await route.abort("failed");
    } else await route.continue();
  });
  await dialog.getByRole("button", { name: "生成新草案", exact: true }).click();
  await dialog.getByRole("button", { name: "重试提交", exact: true }).click();
  await expect(
    dialog.getByRole("button", { name: "打开生成草案", exact: true }),
  ).toBeVisible();
  expect(received.length).toBe(count + 1);
  expect(received.at(-1).sources[0].id).toBe(source.id);
  expect(received.at(-1).sources[0].coverage.row_count).toBeGreaterThan(32);
  await page.screenshot({
    path: info.outputPath("research-ai-record.png"),
    fullPage: true,
  });
  await dialog
    .getByRole("button", { name: "打开生成草案", exact: true })
    .click();
  await expect(page.getByLabel("文档标题", { exact: true })).toHaveValue(
    "AI 待核查记录",
  );
  await expect(page.getByLabel("复核状态", { exact: true })).toHaveValue(
    "draft",
  );
  await page.getByRole("button", { name: "返回列表", exact: true }).click();
  await page.getByRole("button", { name: "AI 生成来源", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("尚未人工审阅");
  await page.getByRole("link", { name: "打开生成草案", exact: true }).click();
  await expect(page.getByLabel("文档标题", { exact: true })).toHaveValue(
    "AI 待核查记录",
  );
  await page.getByRole("button", { name: "返回列表", exact: true }).click();
  await page.getByRole("button", { name: "AI 生成", exact: true }).click();
  await dialog
    .getByLabel("AI 供应商", { exact: true })
    .selectOption(provider.id);
  await dialog
    .getByRole("button", { name: "添加数据来源", exact: true })
    .click();
  await page.getByRole("button", { name: "使用此来源", exact: true }).click();
  await dialog.getByLabel("研究关注点").fill("invalid-fixture");
  await dialog
    .getByRole("button", { name: "预览发送内容", exact: true })
    .click();
  await dialog.getByRole("button", { name: "生成新草案", exact: true }).click();
  await expect(dialog).toContainText("Extra inputs are not permitted");
  const documents = await (
    await page.request.get(base + "/research-documents")
  ).json();
  expect(documents.rows).toHaveLength(1);
  expect(errors).toEqual([]);
});

test("AI reports: choose fixed record content, preview, language and mobile layout", async ({
  page,
}, info) => {
  const { base, provider, source } = await fixture(page);
  const spec = await (
    await page.request.get(`${base}/report-sources/${source.id}/template`)
  ).json();
  const table = spec.blocks.find((b: any) => b.type === "table");
  table.title = "固定表格";
  spec.title = "人工固定记录";
  const recordId = crypto.randomUUID();
  expect(
    (
      await page.request.put(`${base}/research-documents/${recordId}`, {
        data: { operation_id: crypto.randomUUID(), expected_revision: 0, spec },
      })
    ).ok(),
  ).toBe(true);
  await page.goto("/reports?tab=report");
  await page.getByRole("button", { name: "AI 生成", exact: true }).click();
  const dialog = page.getByRole("dialog", {
    name: "AI 生成实验报告",
    exact: true,
  });
  await dialog
    .getByLabel("AI 供应商", { exact: true })
    .selectOption(provider.id);
  await dialog
    .getByRole("button", { name: "引用实验记录", exact: true })
    .click();
  const picker = page.getByRole("dialog", {
    name: "引用实验记录",
    exact: true,
  });
  await picker.getByLabel("实验记录", { exact: true }).selectOption(recordId);
  await picker
    .locator(".report-source-list > div")
    .filter({ hasText: "固定表格" })
    .getByRole("button", { name: "添加引用", exact: true })
    .click();
  await dialog
    .getByRole("button", { name: "预览发送内容", exact: true })
    .click();
  await expect(dialog).toContainText("即将发送的证据");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => (document.documentElement.dataset.theme = "dark"));
  expect((await dialog.boundingBox())!.width).toBeLessThanOrEqual(390);
  expect(
    await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth + 1),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("research-ai-mobile.png"),
    fullPage: true,
  });
  await dialog
    .getByRole("button", { name: "生成新草案", exact: true })
    .scrollIntoViewIfNeeded();
  await page.screenshot({
    path: info.outputPath("research-ai-mobile-evidence.png"),
    fullPage: true,
  });
  await dialog.getByRole("button", { name: "生成新草案", exact: true }).click();
  await expect(
    dialog.getByRole("button", { name: "打开生成草案", exact: true }),
  ).toBeVisible();
  expect(received.at(-1).records[0].revision).toBe(1);
  expect(received.at(-1).records[0].blocks[0].id).toBe(table.id);
  await dialog
    .getByRole("button", { name: "打开生成草案", exact: true })
    .click();
  await expect(page.getByLabel("文档标题", { exact: true })).toHaveValue(
    "AI 待核查报告",
  );
  const report = (
    await (
      await page.request.get(base + "/research-documents?kind=report")
    ).json()
  ).rows[0];
  expect(report.ai_call_id).toBeTruthy();
  await page.goto(`/reports?tab=report&document=${report.id}`);
  await expect(page.getByLabel("文档标题", { exact: true })).toHaveValue(
    "AI 待核查报告",
  );
});
