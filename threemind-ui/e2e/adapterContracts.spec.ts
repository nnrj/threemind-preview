import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("adapter declarations: graphical negotiation, import, checksum and no device execution", async ({
  page,
}, info) => {
  const errors: string[] = [],
    mutations: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      !request.url().endsWith("/adapters/validate")
    )
      mutations.push(request.url());
  });
  await page.goto("/settings?section=devices");
  await page.getByRole("button", { name: "接入验收", exact: true }).click();
  const tools = page.getByRole("region", {
    name: "适配器接入验收",
    exact: true,
  });
  await expect(tools.getByLabel("所需协议版本", { exact: true })).toHaveValue(
    "threemind-network/2",
  );
  await tools
    .getByLabel("所需传输方式", { exact: true })
    .selectOption("websocket");
  await tools.getByLabel("刺激输入", { exact: true }).check();
  await tools
    .getByRole("button", { name: "校验所需能力", exact: true })
    .click();
  await expect(tools.getByRole("status")).toContainText(
    "声明具备所需协议和能力。",
  );
  await expect(tools.getByRole("status")).toContainText("尚未执行或授权设备");
  await tools.getByLabel("要求完整状态恢复声明", { exact: true }).check();
  await tools
    .getByRole("button", { name: "校验所需能力", exact: true })
    .click();
  await expect(tools.getByRole("status")).toContainText(
    "未声明完整状态恢复能力",
  );
  await tools.getByLabel("要求完整状态恢复声明", { exact: true }).uncheck();
  await tools
    .getByLabel("所需协议版本", { exact: true })
    .fill("incompatible/1");
  await tools
    .getByRole("button", { name: "校验所需能力", exact: true })
    .click();
  await expect(tools.getByRole("status")).toContainText("协议版本不匹配");
  await tools.getByText("高级：校验时钟与端口单位", { exact: true }).click();
  await tools
    .getByLabel("所需协议版本", { exact: true })
    .fill("threemind-network/2");
  await tools
    .getByLabel("所需时钟域", { exact: true })
    .selectOption("physical_us");
  await tools.getByLabel("逐项校验端口单位声明", { exact: true }).check();
  await tools
    .getByLabel(/^期望单位/)
    .first()
    .fill("incompatible unit");
  await tools
    .getByRole("button", { name: "校验所需能力", exact: true })
    .click();
  await expect(tools.getByRole("status")).toContainText("未声明所需时钟域");
  await expect(tools.getByRole("status")).toContainText(
    "数据端口的单位声明不一致",
  );
  await tools.getByText("高级：校验时钟与端口单位", { exact: true }).click();
  const promise = page.waitForEvent("download");
  await tools
    .getByRole("button", { name: "下载契约声明", exact: true })
    .click();
  const download = await promise,
    raw = await readFile((await download.path())!, "utf8"),
    value = JSON.parse(raw);
  expect(value.contract.topology_access).toBe("none");
  expect(value.sha256).toHaveLength(64);
  await tools.getByLabel("导入契约声明 JSON", { exact: true }).setInputFiles({
    name: "corrupted.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ ...value, sha256: "0".repeat(64) })),
  });
  await expect(tools.getByRole("alert")).toContainText("checksum");
  await tools.getByLabel("导入契约声明 JSON", { exact: true }).setInputFiles({
    name: "valid.json",
    mimeType: "application/json",
    buffer: Buffer.from(raw),
  });
  await expect(tools.getByRole("status")).toContainText(
    "与当前安装版本的声明一致。",
  );
  await tools
    .getByLabel("已实现的契约", { exact: true })
    .selectOption("physical-world");
  await expect(tools).toContainText("当前是固定投影的工程对照");
  await tools.getByText("高级：查看契约 JSON", { exact: true }).click();
  await expect(tools.locator(".cm-gutters")).toBeVisible();
  await tools.getByText("高级：查看契约 JSON", { exact: true }).click();
  await page.screenshot({
    path: info.outputPath("adapter-contracts-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await tools.evaluate(
      (element) => element.scrollWidth <= element.clientWidth + 1,
    ),
  ).toBe(true);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("adapter-contracts-mobile.png"),
    fullPage: true,
  });
  await page.evaluate(() => {
    const value = {
      ...JSON.parse(localStorage.getItem("tm2.preferences") ?? "{}"),
      locale: "en",
    };
    localStorage.setItem("tm2.preferences", JSON.stringify(value));
    dispatchEvent(
      new StorageEvent("storage", {
        key: "tm2.preferences",
        newValue: JSON.stringify(value),
      }),
    );
  });
  await expect(
    page.getByRole("heading", {
      name: "Adapter integration checks",
      exact: true,
    }),
  ).toBeVisible();
  expect(
    await page
      .getByRole("region", { name: "Adapter integration checks", exact: true })
      .evaluate((element) => element.scrollWidth <= element.clientWidth + 1),
  ).toBe(true);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("adapter-contracts-english-mobile.png"),
    fullPage: true,
  });
  expect(mutations).toEqual([]);
  expect(errors).toEqual([]);
});
