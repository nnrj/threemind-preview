import { expect, test } from "@playwright/test";
import { createServer, type Server } from "node:http";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);
let server: Server,
  origin = "";
const received: any[] = [];
test.beforeAll(async () => {
  server = createServer((request, response) => {
    let raw = "";
    request.on("data", (chunk) => {
      raw += chunk;
    });
    request.on("end", () => {
      const evidence = JSON.parse(JSON.parse(raw).messages[1].content).evidence;
      received.push(evidence);
      const statement = {
        text: "本地模拟解释：只依据完整已提交范围，不代表意识证明。",
        source_refs: [evidence.source_refs.population],
      };
      const content = {
        summary: statement,
        observations: [],
        hypotheses: [],
        suggestions: [],
        limitations: ["只覆盖已提交证据，不能将个体当作独立种群重复。"],
      };
      response.writeHead(200, { "Content-Type": "text/event-stream" });
      response.write(
        "data: " +
          JSON.stringify({
            choices: [
              { index: 0, delta: { content: JSON.stringify(content) } },
            ],
          }) +
          "\n\n",
      );
      response.write(
        "data: " +
          JSON.stringify({
            choices: [{ index: 0, delta: {}, finish_reason: "stop" }],
            usage: { prompt_tokens: 200, completion_tokens: 80 },
          }) +
          "\n\n",
      );
      response.end("data: [DONE]\n\n");
    });
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  origin =
    "http://127.0.0.1:" +
    (typeof address === "object" && address ? address.port : "") +
    "/v1";
});
test.afterAll(async () => {
  if (server)
    await new Promise<void>((resolve) => server.close(() => resolve()));
});

test("optional ecological AI commentary: defaults, graphical/JSON, explicit preview and immutable evidence", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "AI 观察工程验收 " + Date.now() },
    })
  ).json();
  const base = "/api/v2/projects/" + project.id;
  const provider = await (
    await page.request.post(base + "/ai/providers", {
      data: {
        config: {
          name: "本地观察模拟服务",
          base_url: origin,
          model: "fixture-observer",
          enabled: true,
        },
        api_key: "fixture-only",
        expected_revision: 0,
      },
    })
  ).json();
  const protocol = (
    await (await page.request.get(base + "/ecologies/catalogue")).json()
  ).defaults;
  protocol.base.duration_s = 0.06;
  protocol.base.checkpoint_us = 20000;
  protocol.ecology.founder_count = 2;
  const campaign = await (
    await page.request.post(base + "/ecologies", {
      data: {
        operation_id: crypto.randomUUID(),
        name: "可选 AI 观察",
        objective: "Engineering validation only",
        protocol,
      },
    })
  ).json();
  const campaignRoot = base + "/ecologies/" + campaign.id;
  await expect
    .poll(
      async () =>
        (await (await page.request.get(campaignRoot)).json()).campaign.status,
    )
    .toBe("completed");
  const before = (await (await page.request.get(campaignRoot)).json())
    .checkpoint;
  await page.addInitScript(
    (id) => localStorage.setItem("tm2.project", id),
    project.id,
  );
  await page.goto("/studies?tab=ecology&campaign=" + campaign.id);
  const panel = page.getByRole("region", { name: "AI 观察解释", exact: true });
  await expect(panel).toContainText("AI 观察当前关闭");
  await panel
    .getByRole("button", { name: "配置 AI 观察", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "配置 AI 观察解释",
    exact: true,
  });
  await expect(
    dialog.getByLabel("启用 AI 观察解释", { exact: true }),
  ).not.toBeChecked();
  await expect(
    dialog.getByLabel("允许后台自动解释", { exact: true }),
  ).not.toBeChecked();
  await dialog
    .getByLabel("AI 供应商", { exact: true })
    .selectOption(provider.id);
  await dialog.getByLabel("启用 AI 观察解释", { exact: true }).check();
  await dialog
    .getByLabel("观察目的与关注点", { exact: true })
    .fill("完整种群与缺失覆盖");
  await dialog.getByText("高级：触发、时间与调用上限", { exact: true }).click();
  await dialog.getByLabel("每个配置版本的请求上限", { exact: true }).fill("3");
  await dialog
    .getByRole("button", { name: "切换到 JSON 编辑", exact: true })
    .click();
  const editor = dialog.locator(".cm-content");
  await expect(editor).toContainText('"maximum_calls": 3');
  await expect(editor).toContainText("完整种群与缺失覆盖");
  await editor.fill('{"enabled": "false"}');
  await dialog.getByRole("button", { name: "校验", exact: true }).click();
  await expect(dialog.getByRole("alert")).toBeVisible();
  const defaults = (
    await (await page.request.get(campaignRoot + "/observer/ai")).json()
  ).defaults;
  Object.assign(defaults, {
    enabled: true,
    provider_id: provider.id,
    objective: "完整种群与缺失覆盖",
    maximum_calls: 3,
  });
  await editor.fill(JSON.stringify(defaults, null, 2));
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(
    dialog.getByLabel("允许后台自动解释", { exact: true }),
  ).not.toBeChecked();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({ path: info.outputPath("ecology-ai-mobile.png") });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await dialog.getByRole("button", { name: "保存配置", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  expect(received).toHaveLength(0);
  await panel
    .getByRole("button", { name: "生成当前观察解释", exact: true })
    .click();
  const generate = page.getByRole("dialog", {
    name: "生成生态观察解释",
    exact: true,
  });
  await expect(
    generate.getByRole("button", { name: "发送并生成解释", exact: true }),
  ).toBeDisabled();
  await generate
    .getByRole("button", { name: "预览发送内容", exact: true })
    .click();
  await expect(generate).toContainText("完整范围摘要");
  await expect(generate).toContainText("不包含脑网络、原始载体或凭据");
  await page.screenshot({ path: info.outputPath("ecology-ai-preview.png") });
  await generate
    .getByRole("button", { name: "发送并生成解释", exact: true })
    .click();
  const result = page
    .getByRole("dialog")
    .filter({ hasText: "输出属于外部工具内容" });
  await expect(result).toContainText("本地模拟解释");
  await expect(result).toContainText("尚未人工审阅");
  await expect(result).toContainText("证据局限");
  await page.screenshot({ path: info.outputPath("ecology-ai-result.png") });
  expect(received).toHaveLength(1);
  expect(received[0].facts.events.total).toBeGreaterThan(0);
  const after = (await (await page.request.get(campaignRoot)).json())
    .checkpoint;
  expect(after.state_hash).toBe(before.state_hash);
  expect(errors).toEqual([]);
});
