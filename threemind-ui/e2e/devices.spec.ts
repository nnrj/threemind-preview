import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("network device graphical binding, real websocket delivery, evidence and revocation", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `设备验收 ${new Date().toISOString()}` },
    })
  ).json();
  const run = await (
    await page.request.post(`/api/v2/projects/${project.id}/runs`, {
      data: {
        name: "匿名仪器接入验收",
        spec: {
          environment: "manual",
          clock: "realtime",
          duration_s: 180,
          checkpoint_us: 500000,
        },
      },
    })
  ).json();
  const url = `/api/v2/projects/${project.id}/runs/${run.id}`;
  let deviceId = "";
  try {
    await page.goto("/");
    await page
      .getByLabel("当前研究项目", { exact: true })
      .selectOption(project.id);
    await page.goto(`/runs/${run.id}`);
    await page.getByRole("button", { name: "感官与输入", exact: true }).click();
    await page.getByRole("button", { name: "网络设备", exact: true }).click();
    const panel = page.getByRole("region", { name: "网络设备", exact: true });
    await panel
      .getByRole("button", { name: "添加网络设备", exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("设备名称", { exact: true }).fill("测试仪器 A");
    await expect(dialog.locator(".device-limits")).not.toHaveAttribute("open");
    await dialog.locator(".device-limits > summary").click();
    await dialog.getByLabel("输出节点上限", { exact: true }).fill("1");
    await dialog
      .getByRole("button", { name: "创建设备绑定", exact: true })
      .click();
    await expect(dialog.getByRole("heading")).toHaveText("设备凭据已生成");
    const token = await dialog
      .getByLabel("设备独立凭据", { exact: true })
      .inputValue();
    await dialog
      .getByRole("button", { name: "已保存凭据", exact: true })
      .click();
    await expect(dialog).not.toBeVisible();
    deviceId = await panel
      .getByLabel("已绑定设备", { exact: true })
      .inputValue();
    await panel.locator(".device-connection > summary").click();
    const socketUrl = await panel
      .getByLabel("设备 WebSocket 地址", { exact: true })
      .inputValue();
    await expect
      .poll(async () => (await (await page.request.get(url)).json()).status)
      .toBe("running");
    const now = BigInt((await (await page.request.get(url)).json()).time_us);
    const exchange = await page.evaluate(
      async ({ socketUrl, token, when }) => {
        return await new Promise<any>((resolve, reject) => {
          const socket = new WebSocket(socketUrl);
          const protocol = "threemind-network/2";
          const timeout = setTimeout(() => {
            socket.close();
            reject(new Error("device acknowledgement timed out"));
          }, 10000);
          let session = "";
          socket.onerror = () => {
            clearTimeout(timeout);
            reject(new Error("device websocket failed"));
          };
          socket.onopen = () =>
            socket.send(
              JSON.stringify({
                protocol,
                type: "hello",
                token,
                source_clock: { mode: "simulation" },
              }),
            );
          socket.onmessage = (event) => {
            const value = JSON.parse(event.data);
            if (value.type === "ready") {
              session = value.session.id;
              socket.send(
                JSON.stringify({
                  protocol,
                  type: "input",
                  sequence: "0",
                  capture_us: "0",
                  frames: [
                    {
                      time_us: when,
                      channels: [
                        [12, -0.7],
                        [15, 0.4],
                      ],
                    },
                  ],
                }),
              );
            } else if (value.type === "receipt") {
              clearTimeout(timeout);
              socket.close();
              resolve({ session, receipt: value });
            } else {
              clearTimeout(timeout);
              socket.close();
              reject(new Error(JSON.stringify(value)));
            }
          };
        });
      },
      { socketUrl, token, when: (now + 3000000n).toString() },
    );
    expect(exchange.receipt.status).toBe("accepted");
    await expect
      .poll(
        async () =>
          (
            await (
              await page.request.get(
                `${url}/inputs/${exchange.receipt.envelope_id}`,
              )
            ).json()
          ).envelope.status,
      )
      .toBe("completed");
    await panel
      .getByRole("button", { name: "刷新设备记录", exact: true })
      .click();
    await expect(panel.locator("tbody")).toContainText("全部帧已处理");
    await panel
      .getByRole("button", { name: "查看载体证据", exact: true })
      .click();
    await expect(dialog.locator("tbody")).toContainText("已递送");
    await dialog.getByLabel("关闭", { exact: true }).click();
    for (const name of ["此设备全部载体 JSONL", "此设备全部递送 CSV"]) {
      const downloaded = page.waitForEvent("download");
      await panel.getByRole("link", { name, exact: true }).click();
      expect((await downloaded).suggestedFilename()).toContain("inputs-");
    }
    await panel.getByRole("button", { name: "轮换凭据", exact: true }).click();
    await dialog
      .getByRole("button", { name: "生成新凭据", exact: true })
      .click();
    const newToken = await dialog
      .getByLabel("设备独立凭据", { exact: true })
      .inputValue();
    expect(newToken).not.toBe(token);
    await dialog
      .getByRole("button", { name: "已保存凭据", exact: true })
      .click();
    const denied = await page.request.get(
      `/api/v2/network/${project.id}/${run.id}/${deviceId}/sessions/${exchange.session}/output`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    expect(denied.status()).toBe(403);
    await expect(panel.locator(".device-summary")).toContainText([
      "凭据版本 2",
      "授权已更新",
    ]);
    await page.request.post(`${url}/commands`, { data: { kind: "pause" } });
    await expect
      .poll(async () => (await (await page.request.get(url)).json()).status)
      .toBe("paused");
    await panel.screenshot({ path: info.outputPath("devices-desktop.png") });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(350); // Let the mobile reflow settle before the element capture.
    await expect
      .poll(async () =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true);
    await panel.screenshot({ path: info.outputPath("devices-mobile.png") });
    await panel
      .getByRole("button", { name: "编辑设备配置", exact: true })
      .click();
    await dialog.getByLabel("启用此设备绑定", { exact: true }).uncheck();
    await dialog
      .getByRole("button", { name: "保存设备配置", exact: true })
      .click();
    await expect(panel).toContainText("绑定停用");
    await page.goto("/docs?doc=docs%2Fzh%2Fv2-network-devices.md");
    await expect(page.locator(".markdown .katex").first()).toBeVisible();
    expect(await page.locator(".katex-error").count()).toBe(0);
    expect(errors).toEqual([]);
  } finally {
    await page.request
      .post(`${url}/commands`, { data: { kind: "pause" }, timeout: 5000 })
      .catch(() => {});
    if (deviceId) {
      const items = await (await page.request.get(`${url}/devices`)).json();
      const device = items.find((d: any) => d.id === deviceId);
      if (device)
        await page.request
          .put(`${url}/devices/${deviceId}`, {
            data: {
              name: device.name,
              configuration: device.configuration,
              enabled: false,
            },
          })
          .catch(() => {});
    }
  }
});

test("portable wiring download, validated reuse and immutable graphical identity", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `接线复用验收 ${Date.now()}` },
    })
  ).json();
  const base = `/api/v2/projects/${project.id}`;
  const runs = [];
  for (const name of ["原感官模型", "部署模型副本"]) {
    runs.push(
      await (
        await page.request.post(`${base}/runs`, {
          data: {
            name,
            spec: {
              environment: "manual",
              clock: "unbounded",
              duration_s: 0.02,
            },
          },
        })
      ).json(),
    );
  }
  try {
    await page.goto("/");
    await page
      .getByLabel("当前研究项目", { exact: true })
      .selectOption(project.id);
    const openDevices = async (identity: string) => {
      await page.goto(`/runs/${identity}`);
      await page
        .getByRole("button", { name: "感官与输入", exact: true })
        .click();
      await page.getByRole("button", { name: "网络设备", exact: true }).click();
      return page.getByRole("region", { name: "网络设备", exact: true });
    };
    let panel = await openDevices(runs[0].id);
    const dialog = page.getByRole("dialog");
    await panel
      .getByRole("button", { name: "添加网络设备", exact: true })
      .click();
    await expect(dialog.getByLabel("接线方式", { exact: true })).toHaveValue(
      "new",
    );
    await dialog.getByLabel("设备名称", { exact: true }).fill("原接线仪器");
    await dialog
      .getByRole("button", { name: "创建设备绑定", exact: true })
      .click();
    const originalToken = await dialog
      .getByLabel("设备独立凭据", { exact: true })
      .inputValue();
    await dialog
      .getByRole("button", { name: "已保存凭据", exact: true })
      .click();
    const originalDevice = await panel
      .getByLabel("已绑定设备", { exact: true })
      .inputValue();
    const download = page.waitForEvent("download");
    await panel
      .getByRole("link", { name: "导出接线清单", exact: true })
      .click();
    const saved = await download;
    expect(saved.suggestedFilename()).toBe(
      `network-${originalDevice}.wiring.json`,
    );
    const raw = await readFile((await saved.path())!);
    const wiring = JSON.parse(raw.toString("utf8"));
    expect(raw.toString("utf8")).not.toContain(originalToken);
    panel = await openDevices(runs[1].id);
    await panel
      .getByRole("button", { name: "添加网络设备", exact: true })
      .click();
    await dialog.getByLabel("设备名称", { exact: true }).fill("重新部署的仪器");
    await dialog.getByLabel("接线方式", { exact: true }).selectOption("reuse");
    await dialog.getByLabel("接线清单文件", { exact: true }).setInputFiles({
      name: "corrupt.wiring.json",
      mimeType: "application/json",
      buffer: Buffer.from(
        JSON.stringify({ ...wiring, sha256: "0".repeat(64) }),
      ),
    });
    await expect(dialog).toContainText("checksum");
    await dialog
      .getByRole("button", { name: "创建设备绑定", exact: true })
      .click();
    await expect(dialog).toContainText("请先选择并校验对应模型的接线清单");
    await dialog.getByLabel("接线清单文件", { exact: true }).setInputFiles({
      name: saved.suggestedFilename(),
      mimeType: "application/json",
      buffer: raw,
    });
    await expect(dialog).toContainText("接线校验通过");
    await expect(
      dialog.getByLabel("稳定接线编号", { exact: true }),
    ).toHaveValue(originalDevice);
    await dialog.evaluate((node) => {
      node.scrollTop = 0;
    });
    await dialog.screenshot({
      path: info.outputPath("wiring-reuse-desktop.png"),
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBe(true);
    await dialog.evaluate((node) => {
      node.scrollTop = 0;
    });
    await dialog.screenshot({
      path: info.outputPath("wiring-reuse-mobile.png"),
    });
    await dialog
      .getByRole("button", { name: "创建设备绑定", exact: true })
      .click();
    const newToken = await dialog
      .getByLabel("设备独立凭据", { exact: true })
      .inputValue();
    expect(newToken).not.toBe(originalToken);
    await dialog
      .getByRole("button", { name: "已保存凭据", exact: true })
      .click();
    expect(
      await panel.getByLabel("已绑定设备", { exact: true }).inputValue(),
    ).not.toBe(originalDevice);
    await panel
      .getByRole("button", { name: "编辑设备配置", exact: true })
      .click();
    await expect(
      dialog.getByLabel("稳定接线编号", { exact: true }),
    ).toHaveValue(originalDevice);
    await expect(
      dialog.getByLabel("稳定接线编号", { exact: true }),
    ).toHaveJSProperty("readOnly", true);
    await expect(dialog).toContainText("创建后固定");
    await dialog.screenshot({
      path: info.outputPath("wiring-readonly-mobile.png"),
    });
    await dialog.getByRole("button", { name: "取消", exact: true }).click();
    expect(errors).toEqual([]);
  } finally {
    for (const run of runs) {
      await page.request
        .post(`${base}/runs/${run.id}/commands`, { data: { kind: "cancel" } })
        .catch(() => {});
    }
  }
});
