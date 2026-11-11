import { test, expect } from "@playwright/test";
import { createServer, type Server } from "node:http";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);
let server: Server,
  origin = "",
  requests = 0;
test.beforeAll(async () => {
  server = createServer((req, res) => {
    let raw = "";
    req.on("data", (chunk) => {
      raw += chunk;
    });
    req.on("end", () => {
      const body = JSON.parse(raw),
        system = body.messages[0].content;
      const evidence = JSON.parse(body.messages[1].content);
      let text = "观察到已记录的状态；这不构成意识判定。";
      if (system.startsWith("Generate one fragment"))
        text = "窗外传来缓慢的雨声。";
      else if (system.startsWith("Propose a bounded"))
        text = JSON.stringify({
          name: "AI 只读观察计划",
          rationale: "先核查固定起点。",
          protocol: {
            mode: evidence.mode,
            limits: evidence.limits,
            steps: [{ command: "observe.summary" }],
          },
        });
      else if (system.includes("analysis schema"))
        text = JSON.stringify({
          summary: "固定恢复点分析",
          observations: [
            {
              text: "存在一个明确的已提交恢复点。",
              source_refs: [evidence.evidence.source_refs[0]],
            },
          ],
          conclusion: "需要进一步受控实验。",
        });
      requests++;
      res.writeHead(200, { "Content-Type": "text/event-stream" });
      res.write(
        "data: " +
          JSON.stringify({
            choices: [{ index: 0, delta: { content: text } }],
          }) +
          "\n\n",
      );
      res.write(
        "data: " +
          JSON.stringify({
            choices: [{ index: 0, delta: {}, finish_reason: "stop" }],
            usage: { prompt_tokens: 100, completion_tokens: 60 },
          }) +
          "\n\n",
      );
      res.end("data: [DONE]\n\n");
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

test("AI tools configure both modes, ordinary stimulus, analysis, plan and provenance", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "AI 工具全过程验收" },
    })
  ).json();
  const root = "/api/v2/projects/" + project.id;
  const provider = await (
    await page.request.post(root + "/ai/providers", {
      data: {
        config: {
          name: "本地工具验收",
          base_url: origin,
          model: "fixture-tools",
          enabled: true,
        },
      },
    })
  ).json();
  const source = await (
    await page.request.post(root + "/runs", {
      data: {
        name: "AI 研究起点",
        spec: {
          environment: "replay",
          clock: "unbounded",
          duration_s: 0.2,
          checkpoint_us: 10000,
          sample_us: 10000,
          replay: [
            {
              time_us: "0",
              channels: [
                [1, 0.7],
                [2, 0.5],
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
      data: { name: "AI 工具暂停沙箱", paused: true },
    })
  ).json();
  const base = root + "/runs/" + run.id;
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page.goto("/runs/" + run.id + "?view=ai");
  await page
    .getByLabel("环境刺激供应商", { exact: true })
    .selectOption(provider.id);
  await page.getByLabel("启用环境刺激", { exact: true }).check();
  await page.getByLabel("自动生成环境刺激", { exact: true }).uncheck();
  await page
    .getByLabel("环境情境", { exact: true })
    .fill("雨天，非语义的背景声音。");
  await expect(
    page.getByLabel("单条刺激字符上限", { exact: true }),
  ).not.toBeVisible();
  async function save() {
    const response = page.waitForResponse(
      (r) => r.request().method() === "PUT" && r.url().endsWith("/ai-tools"),
    );
    await page
      .getByRole("button", { name: "保存工具配置", exact: true })
      .click();
    expect((await response).ok()).toBe(true);
    await expect(page.getByText(/ · 已同步/, { exact: false })).toBeVisible();
  }
  await save();
  await page
    .getByRole("button", { name: "生成一次环境刺激", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("已接收为普通输入载体");
  const inputCall = (
    await (await page.request.get(root + "/ai/calls?run_id=" + run.id)).json()
  ).items[0];
  const inputResult = await (
    await page.request.get(root + "/ai/calls/" + inputCall.id)
  ).json();
  expect(inputResult.result.source).toBe("ai-environment");
  expect(inputResult.prompt.user).not.toContain("snapshot");
  await page.getByRole("button", { name: "关闭详情", exact: true }).click();
  let current = await (await page.request.get(base)).json();
  const advance = await page.request.post(base + "/research/actions", {
    data: {
      request_id: crypto.randomUUID(),
      kind: "runtime.advance",
      expected_revision: current.revision,
      duration_us: 1000,
    },
  });
  expect(advance.ok()).toBe(true);
  await expect
    .poll(async () => {
      const input = await (
        await page.request.get(
          base + "/inputs/" + inputResult.result.envelope_id,
        )
      ).json();
      return input.envelope.delivered_count;
    })
    .toBeGreaterThan(0);
  await expect
    .poll(async () => (await (await page.request.get(base)).json()).status)
    .toBe("paused");
  await page.getByRole("button", { name: "外部解读", exact: true }).click();
  await page
    .getByLabel("外部解读供应商", { exact: true })
    .selectOption(provider.id);
  await page.getByLabel("启用外部解读", { exact: true }).check();
  await page.getByLabel("定期解读已提交的整体状态", { exact: true }).uncheck();
  await page.getByLabel("周期解读间隔（秒）", { exact: true }).fill("45");
  await page
    .getByRole("button", { name: "切换为 JSON 编辑", exact: true })
    .click();
  const capture = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/ai-tools/validate"),
  );
  await page.getByRole("button", { name: "校验参数", exact: true }).click();
  const config = (await capture).postDataJSON();
  expect(config.interpreter.frequency_s).toBe(45);
  const json = page.getByRole("textbox", { name: "AI 工具 JSON", exact: true });
  config.interpreter.activation_min = 2;
  await json.fill(JSON.stringify(config));
  await page.getByRole("button", { name: "保存工具配置", exact: true }).click();
  await expect(page.getByRole("alert").first()).toContainText(
    "激活上限不能小于下限",
  );
  config.interpreter.activation_min = 0.05;
  await json.fill(JSON.stringify(config));
  await page
    .getByRole("button", { name: "切换为图形配置", exact: true })
    .click();
  await expect(
    page.getByLabel("周期解读间隔（秒）", { exact: true }),
  ).toHaveValue("45");
  await save();
  await page.getByRole("button", { name: "解读一次", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("尚未人工审阅");
  await expect(page.getByLabel("AI 返回内容", { exact: true })).toContainText(
    "不构成意识判定",
  );
  await page.getByRole("button", { name: "关闭详情", exact: true }).click();
  await page.getByRole("button", { name: "实验助手", exact: true }).click();
  await page
    .getByLabel("实验助手供应商", { exact: true })
    .selectOption(provider.id);
  await page.getByLabel("启用实验助手", { exact: true }).check();
  await save();
  await page
    .getByLabel("研究目的与关注问题", { exact: true })
    .fill("核查固定起点，再设计受控实验。");
  await page
    .getByRole("button", { name: "AI 分析现有证据", exact: true })
    .click();
  await expect(
    page.getByLabel("结构化实验分析", { exact: true }),
  ).toContainText("固定恢复点分析");
  await page.getByRole("button", { name: "关闭详情", exact: true }).click();
  await page
    .getByRole("button", { name: "AI 生成实验计划", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "实验计划已通过校验并保存",
  );
  await page
    .getByRole("link", { name: "查看生成的实验计划", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "AI 只读观察计划", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "确认并开始计划", exact: true })
    .click();
  await expect(
    page.getByText("已完成 · 已完成 1/1 步", { exact: false }),
  ).toBeVisible();
  await page
    .getByRole("button", {
      name: "查看 AI 原始提议、证据与供应商版本",
      exact: true,
    })
    .click();
  await expect(page.getByRole("dialog")).toContainText("本地工具验收");
  await page.getByRole("button", { name: "关闭详情", exact: true }).click();
  await page.goto("/runs/" + run.id + "?view=ai&tool=assistant");
  await expect(page.getByLabel("实验助手供应商", { exact: true })).toHaveValue(
    provider.id,
  );
  await page.screenshot({
    path: info.outputPath("ai-tools-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByText("高级参数与触发规则", { exact: true }).click();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(390);
  await page.screenshot({
    path: info.outputPath("ai-tools-mobile.png"),
    fullPage: true,
  });
  expect(requests).toBe(4);
  expect(errors).toEqual([]);
});

test("automatic environment runs outside runtime capacity with committed-time audit", async ({
  page,
}) => {
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "AI 自动调度验收" },
    })
  ).json();
  const root = "/api/v2/projects/" + project.id;
  const provider = await (
    await page.request.post(root + "/ai/providers", {
      data: {
        config: {
          name: "本地自动环境",
          base_url: origin,
          model: "fixture-tools",
          enabled: true,
        },
      },
    })
  ).json();
  const run = await (
    await page.request.post(root + "/runs", {
      data: {
        name: "AI 周期刺激",
        spec: {
          environment: "replay",
          clock: "realtime",
          duration_s: 5,
          checkpoint_us: 100000,
          sample_us: 100000,
          replay: [
            {
              time_us: "0",
              channels: [
                [1, 0.7],
                [2, 0.5],
              ],
            },
          ],
        },
      },
    })
  ).json();
  const base = root + "/runs/" + run.id;
  const defaults = (await (await page.request.get(base + "/ai-tools")).json())
    .defaults;
  defaults.environment = {
    ...defaults.environment,
    enabled: true,
    provider_id: provider.id,
    automatic: true,
    random_frequency: false,
    frequency_s: 1,
  };
  expect(
    (
      await page.request.put(base + "/ai-tools", {
        data: { expected_revision: 0, config: defaults },
      })
    ).ok(),
  ).toBe(true);
  await expect
    .poll(
      async () => {
        const list = await (
          await page.request.get(root + "/ai/calls?run_id=" + run.id)
        ).json();
        return list.items.filter((c: any) => c.application_status === "applied")
          .length;
      },
      { timeout: 20000 },
    )
    .toBeGreaterThan(0);
  await expect
    .poll(async () => (await (await page.request.get(base)).json()).status, {
      timeout: 20000,
    })
    .toBe("completed");
  const inputs = await (
    await page.request.get(base + "/inputs?source=ai-environment")
  ).json();
  expect(inputs.rows.some((e: any) => e.delivered_count > 0)).toBe(true);
  const saved = await (await page.request.get(base)).json();
  expect(saved.time_us).toBe("5000000");
});
