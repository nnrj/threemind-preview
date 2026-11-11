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
    req.on("data", (part) => {
      raw += part;
    });
    req.on("end", () => {
      const prompt = JSON.parse(JSON.parse(raw).messages[1].content);
      const design = prompt.design;
      received.push(design);
      const protocol = structuredClone(design.scope.world_protocol);
      protocol.label = "AI 提议的物理世界";
      protocol.sensors.push({
        id: "eye",
        kind: "camera_rgb",
        body_id: protocol.bodies[0].id,
        port: 9,
        position: [0, 0, 1],
        width: 4,
        height: 4,
      });
      if (design.scope.objective === "invalid-fixture")
        protocol.script = "must not run";
      const proposal = {
        rationale: "为当前虚拟躯体增加实际成像感官。",
        limitations: ["工程验收示例，不代表演化结果。"],
        protocol,
      };
      res.writeHead(200, { "Content-Type": "text/event-stream" });
      res.write(
        `data: ${JSON.stringify({ choices: [{ index: 0, delta: { content: JSON.stringify(proposal) } }] })}\n\n`,
      );
      res.write(
        `data: ${JSON.stringify({ choices: [{ index: 0, delta: {}, finish_reason: "stop" }], usage: { prompt_tokens: 400, completion_tokens: 200 } })}\n\n`,
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

test("world AI: explicit transmitted scope, compiled proposal, editable adoption, history and rejected scripts", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `世界 AI 工程验收 ${Date.now()}` },
    })
  ).json();
  const base = `/api/v2/projects/${project.id}`;
  const provider = await (
    await page.request.post(base + "/ai/providers", {
      data: {
        config: {
          name: "本地世界草案验收",
          model: "fixture-world",
          base_url: origin,
          enabled: true,
        },
      },
    })
  ).json();
  await page.addInitScript(
    (id: string) => localStorage.setItem("tm2.project", id),
    project.id,
  );
  await page.goto("/worlds");
  await page
    .getByRole("button", { name: "AI 生成世界草案", exact: true })
    .click();
  const modal = page.getByRole("dialog", {
    name: "AI 世界与躯体草案",
    exact: true,
  });
  await modal
    .getByRole("combobox", { name: "AI 供应商", exact: true })
    .selectOption(provider.id);
  await modal
    .getByLabel("世界设计目的", { exact: true })
    .fill("给当前躯体增加可离屏工作的低分辨率眼睛");
  await modal
    .getByRole("button", { name: "预览发送内容", exact: true })
    .click();
  await expect(
    modal.getByRole("button", { name: "发送世界草案请求", exact: true }),
  ).toBeVisible();
  expect(received.length).toBe(0);
  await modal.getByText("完整发送内容", { exact: true }).click();
  await expect(modal.locator(".ai-preview")).toContainText(
    "threemind.world-authoring/1",
  );
  const created = page.waitForResponse(
    (r) =>
      r.url().endsWith("/worlds/ai/requests") &&
      r.request().method() === "POST",
  );
  await modal
    .getByRole("button", { name: "发送世界草案请求", exact: true })
    .click();
  const call = await (await created).json();
  const result = modal.getByRole("region", {
    name: "世界草案结果",
    exact: true,
  });
  await expect(
    result.getByRole("button", { name: "载入草案并继续编辑", exact: true }),
  ).toBeVisible();
  expect(received.length).toBe(1);
  expect(received[0].contains_model_state_or_research_measurements).toBe(false);
  expect(
    (await (await page.request.get(base + "/worlds")).json()).rows,
  ).toEqual([]);
  expect(await (await page.request.get(base + "/runs")).json()).toEqual([]);
  await result.getByText("查看图形配置与三维预览", { exact: true }).click();
  await expect(result.locator(".world-scene canvas")).toBeVisible();
  await result
    .getByRole("region", { name: "世界配置差异", exact: true })
    .scrollIntoViewIfNeeded();
  await page.screenshot({ path: info.outputPath("world-ai-proposal.png") });
  await result
    .getByRole("button", { name: "载入草案并继续编辑", exact: true })
    .click();
  const edit = page.getByRole("dialog", { name: "新建世界", exact: true });
  await edit
    .getByLabel("世界名称", { exact: true })
    .fill("人工采用并调整的物理世界");
  await edit
    .getByRole("button", { name: "校验并保存世界", exact: true })
    .click();
  await expect(edit).toHaveCount(0);
  const saved = (await (await page.request.get(base + "/worlds")).json())
    .rows[0];
  const version = await (
    await page.request.get(base + `/worlds/${saved.id}`)
  ).json();
  expect(version.ai_call_id).toBe(call.id);
  expect(version.protocol_hash).not.toBe(version.ai_protocol_hash);
  await expect(page.getByText(/保存内容包含人工调整/)).toBeVisible();
  await page.goto(`/worlds?proposal=${call.id}`);
  await expect(
    page.getByRole("dialog", { name: "AI 世界与躯体草案", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "载入草案并继续编辑", exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("region", { name: "世界配置差异", exact: true })
    .scrollIntoViewIfNeeded();
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    )
    .toBe(true);
  await page.screenshot({ path: info.outputPath("world-ai-mobile.png") });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/worlds");
  await page
    .getByRole("button", { name: "AI 生成世界草案", exact: true })
    .click();
  await modal
    .getByRole("combobox", { name: "AI 供应商", exact: true })
    .selectOption(provider.id);
  await modal
    .getByLabel("世界设计目的", { exact: true })
    .fill("invalid-fixture");
  await modal
    .getByRole("button", { name: "预览发送内容", exact: true })
    .click();
  await modal
    .getByRole("button", { name: "发送世界草案请求", exact: true })
    .click();
  await expect(modal.getByRole("alert")).toContainText("script");
  await expect(
    modal.getByRole("button", { name: "载入草案并继续编辑", exact: true }),
  ).toHaveCount(0);
  expect(
    (await (await page.request.get(base + "/worlds")).json()).rows,
  ).toHaveLength(1);
  expect(errors).toEqual([]);
});
