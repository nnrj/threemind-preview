import { test, expect } from "@playwright/test";
import { createServer, type Socket } from "node:net";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected local workstation.",
);

async function localMailSink() {
  const messages: string[] = [],
    sockets = new Set<Socket>();
  const server = createServer((socket) => {
    sockets.add(socket);
    socket.on("close", () => sockets.delete(socket));
    socket.on("error", () => {});
    socket.setTimeout(15000, () => socket.destroy());
    socket.write("220 local ThreeMind test sink\r\n");
    let pending = "",
      data = false,
      lines: string[] = [];
    socket.on("data", (chunk) => {
      pending += chunk.toString("utf8");
      if (pending.length > 2 * 1024 * 1024) {
        socket.destroy();
        return;
      }
      let end: number;
      while ((end = pending.indexOf("\r\n")) !== -1) {
        const line = pending.slice(0, end);
        pending = pending.slice(end + 2);
        if (data) {
          if (line === ".") {
            messages.push(lines.join("\n"));
            lines = [];
            data = false;
            socket.write("250 accepted by local test sink\r\n");
          } else lines.push(line.startsWith("..") ? line.slice(1) : line);
        } else if (/^EHLO /i.test(line))
          socket.write("250-localhost\r\n250 SIZE 2097152\r\n");
        else if (/^(HELO |MAIL FROM:|RCPT TO:|RSET)/i.test(line))
          socket.write("250 ok\r\n");
        else if (line.toUpperCase() === "DATA") {
          data = true;
          socket.write("354 End with a dot\r\n");
        } else if (line.toUpperCase() === "QUIT") socket.end("221 closing\r\n");
        else socket.write("500 unsupported test command\r\n");
      }
    });
  });
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const port = (server.address() as { port: number }).port;
  return {
    messages,
    port,
    close: async () => {
      for (const socket of sockets) socket.destroy();
      await new Promise<void>((resolve) => server.close(() => resolve()));
    },
  };
}

test("notification policy GUI JSON, local SMTP receipt, committed run facts and personal inbox", async ({
  page,
}, info) => {
  const sink = await localMailSink();
  let root = "";
  try {
    const project = await (
      await page.request.post("/api/v2/projects", {
        data: { name: "通知邮件验收 " + Date.now() },
      })
    ).json();
    root = `/api/v2/projects/${project.id}`;
    const base = root + "/notifications";
    const initial = await (await page.request.get(base + "/settings")).json();
    await page.goto("/");
    await page
      .getByLabel("当前研究项目", { exact: true })
      .selectOption(project.id);
    await page.goto("/settings?section=notifications");
    await page.getByLabel("启用项目通知", { exact: true }).check();
    await page.getByLabel("同时发送邮件", { exact: true }).check();
    await page.getByLabel("邮件服务", { exact: true }).selectOption("smtp");
    await page.getByLabel("邮件语言", { exact: true }).selectOption("en");
    await page
      .getByLabel("发件人", { exact: true })
      .fill("ThreeMind <sender@example.test>");
    await page
      .getByLabel("收件人", { exact: true })
      .fill("reviewer@example.test");
    await page.getByLabel("SMTP 主机", { exact: true }).fill("127.0.0.1");
    await page.getByLabel("SMTP 端口", { exact: true }).fill(String(sink.port));
    await page
      .getByLabel("SMTP 连接保护", { exact: true })
      .selectOption("none");
    await page.getByText("高级发送策略", { exact: true }).click();
    await page.getByLabel("邮件冷却期（秒）", { exact: true }).fill("0");
    await page
      .getByRole("button", { name: "切换到 JSON 编辑", exact: true })
      .click();
    await expect(page.locator(".cm-content")).toContainText('"enabled": true');
    await page.locator(".cm-content").fill('{"enabled":true,"enabled":false}');
    await page
      .getByRole("button", { name: "保存通知设置", exact: true })
      .click();
    await expect(page.getByRole("alert")).toContainText("重复");
    expect(
      (await (await page.request.get(base + "/settings")).json()).revision,
    ).toBe(0);
    const wanted = {
      ...initial.config,
      enabled: true,
      email_enabled: true,
      language: "en",
      transport: "smtp",
      sender: "ThreeMind <sender@example.test>",
      recipients: ["reviewer@example.test"],
      smtp_host: "127.0.0.1",
      smtp_port: sink.port,
      smtp_security: "none",
      cooldown_s: 0,
      daily_email_limit: 7,
    };
    await page.locator(".cm-content").fill(JSON.stringify(wanted));
    await page.getByRole("button", { name: "格式化", exact: true }).click();
    await page.getByRole("button", { name: "校验", exact: true }).click();
    await expect(
      page.getByText("配置校验通过。", { exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "切换到图形配置", exact: true })
      .click();
    await expect(page.getByLabel("SMTP 端口", { exact: true })).toHaveValue(
      String(sink.port),
    );
    await page.getByText("高级发送策略", { exact: true }).click();
    await expect(
      page.getByLabel("滚动 24 小时邮件请求上限", { exact: true }),
    ).toHaveValue("7");
    await page
      .getByRole("button", { name: "保存通知设置", exact: true })
      .click();
    await expect(
      page.getByText("通知设置已保存。", { exact: true }),
    ).toBeVisible();
    const saved = await (await page.request.get(base + "/settings")).json();
    expect(saved.revision).toBe(1);
    expect(saved.config).toEqual(wanted);
    await page.screenshot({
      path: info.outputPath("notifications-settings-desktop.png"),
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "发送测试邮件", exact: true })
      .click();
    await expect.poll(() => sink.messages.length).toBe(1);
    expect(sink.messages[0]).toContain("Notification test");
    expect(sink.messages[0]).toContain("reviewer@example.test");
    await page.getByRole("link", { name: /查看通知/ }).click();
    await expect(page.locator(".notification-list")).toContainText(
      "邮件服务已接收",
    );
    await page
      .getByRole("button", { name: "本页标为已读", exact: true })
      .click();
    await expect(
      page.getByRole("link", { name: "查看通知，0 条未读", exact: true }),
    ).toBeVisible();
    const created = await (
      await page.request.post(root + "/runs", {
        data: {
          name: "有通知的真实运行",
          spec: {
            environment: "replay",
            clock: "unbounded",
            duration_s: 0.01,
            replay: [
              {
                time_us: "0",
                channels: [
                  [1, 0.5],
                  [2, 0.3],
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
          (await (await page.request.get(root + "/runs/" + created.id)).json())
            .status,
      )
      .toBe("completed");
    await expect.poll(() => sink.messages.length).toBe(2);
    expect(sink.messages[1]).toContain(created.id);
    await page.getByRole("button", { name: "刷新通知", exact: true }).click();
    await expect(page.locator(".notification-list")).toContainText(
      "运行时长完成",
    );
    await page.screenshot({
      path: info.outputPath("notifications-history-desktop.png"),
      fullPage: true,
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.locator(".notification-item").first()).toContainText(
      "有通知的真实运行",
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath("notifications-history-mobile.png"),
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "规则与邮件设置", exact: true })
      .click();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath("notifications-settings-mobile.png"),
      fullPage: true,
    });
  } finally {
    if (root) {
      const response = await page.request.get(root + "/notifications/settings");
      if (response.ok()) {
        const current = await response.json();
        await page.request.put(root + "/notifications/settings", {
          data: {
            expected_revision: current.revision,
            config: { ...current.config, enabled: false, email_enabled: false },
          },
        });
      }
    }
    await sink.close();
  }
});
