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
      const body = JSON.parse(raw);
      if (body.model !== "fixture-browser-model") {
        res.writeHead(400);
        res.end();
        return;
      }
      requests++;
      res.writeHead(200, { "Content-Type": "text/event-stream" });
      res.write(
        `data: ${JSON.stringify({ choices: [{ index: 0, delta: { content: "本地连接测试成功。" } }] })}\n\n`,
      );
      res.write(
        `data: ${JSON.stringify({ choices: [{ index: 0, delta: {}, finish_reason: "stop" }], usage: { prompt_tokens: 10, completion_tokens: 4 } })}\n\n`,
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

test("provider graphical configuration, secret retention, real queue and mobile layout", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "AI 工具浏览器验收" },
    })
  ).json();
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page.goto("/settings");
  await page.getByRole("button", { name: "AI 供应商", exact: true }).click();
  await page.getByRole("button", { name: "添加供应商", exact: true }).click();
  let dialog = page.getByRole("dialog", {
    name: "添加 AI 供应商",
    exact: true,
  });
  await dialog.getByLabel("供应商名称", { exact: true }).fill("本地验收供应商");
  await dialog.getByLabel("API 基础地址", { exact: true }).fill(origin);
  await dialog
    .getByLabel("模型名称", { exact: true })
    .fill("fixture-browser-model");
  await dialog
    .getByLabel("API Key", { exact: true })
    .fill("browser-test-secret");
  await dialog.getByLabel("启用此供应商", { exact: true }).check();
  await expect(
    dialog.getByLabel("总超时（秒）", { exact: true }),
  ).not.toBeVisible();
  await dialog
    .getByText("高级参数 · 协议、超时与输出", { exact: true })
    .click();
  await dialog.getByLabel("总超时（秒）", { exact: true }).fill("12");
  await dialog.getByText("请求配额与费用记录", { exact: true }).click();
  await dialog
    .getByLabel("输入单价（美元 / 百万 Token）", { exact: true })
    .fill("0");
  await dialog
    .getByLabel("输出单价（美元 / 百万 Token）", { exact: true })
    .fill("0");
  await dialog.getByRole("button", { name: "保存供应商", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  let listing = await (
    await page.request.get(`/api/v2/projects/${project.id}/ai/providers`)
  ).json();
  expect(listing.providers[0].has_api_key).toBe(true);
  expect(JSON.stringify(listing)).not.toContain("browser-test-secret");
  expect(listing.providers[0].config.timeout_s).toBe(12);
  await page.getByRole("button", { name: "编辑", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "编辑 AI 供应商", exact: true });
  await expect(dialog.getByLabel("API Key", { exact: true })).toHaveValue("");
  await dialog.getByRole("button", { name: "保存供应商", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await page.getByRole("button", { name: "连接测试", exact: true }).click();
  await page.getByRole("button", { name: "发送测试请求", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("连接测试 · 已完成");
  await expect(page.getByLabel("AI 返回内容", { exact: true })).toHaveText(
    "本地连接测试成功。",
  );
  await expect(page.getByRole("dialog")).toContainText("10 / 4");
  const download = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "导出请求记录", exact: true }).click(),
  ]);
  expect(download[0].suggestedFilename()).toMatch(/^ai-call-.*\.json$/);
  await page.screenshot({
    path: info.outputPath("ai-call-desktop.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "关闭详情", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "编辑", exact: true }).click();
  dialog = page.getByRole("dialog", { name: "编辑 AI 供应商", exact: true });
  const box = await dialog.boundingBox();
  expect(box!.width).toBeLessThanOrEqual(390);
  await expect(dialog.getByLabel("供应商名称", { exact: true })).toBeVisible();
  await page.screenshot({
    path: info.outputPath("ai-provider-mobile.png"),
    fullPage: true,
  });
  await dialog.getByLabel("清除已保存的 API Key", { exact: true }).check();
  await dialog.getByRole("button", { name: "保存供应商", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  listing = await (
    await page.request.get(`/api/v2/projects/${project.id}/ai/providers`)
  ).json();
  expect(listing.providers[0].has_api_key).toBe(false);
  expect(requests).toBe(1);
  expect(errors).toEqual([]);
});
