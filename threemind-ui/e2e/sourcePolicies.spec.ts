import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { writeFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { resolve } from "node:path";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("source controls edit in both modes, enforce admission and preserve CLI evidence", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() => {
    (window as any).__captureCalls = 0;
    navigator.mediaDevices.getUserMedia = async () => {
      (window as any).__captureCalls++;
      throw new Error("No physical device in source policy validation");
    };
  });
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "来源策略图形验收" },
    })
  ).json();
  const run = await (
    await page.request.post(`/api/v2/projects/${project.id}/runs`, {
      data: {
        name: "界面与命令行独立来源",
        spec: {
          environment: "manual",
          clock: "realtime",
          duration_s: 90,
          checkpoint_us: 200000,
          config: { attention_competition_enabled: true, attention_budget: 1 },
          auditory_sensor: { enabled: true },
          visual_sensor: { enabled: true },
          live_capture: { microphone_enabled: true, camera_enabled: true },
          source_policies: {
            background_enabled: false,
            cli_text_bypass_attention: true,
          },
        },
      },
    })
  ).json();
  const base = `/api/v2/projects/${project.id}/runs/${run.id}`;
  try {
    await page.request.post(base + "/commands", { data: { kind: "pause" } });
    await expect
      .poll(async () => (await (await page.request.get(base)).json()).status)
      .toBe("paused");
    await page.goto("/");
    await page
      .getByLabel("当前研究项目", { exact: true })
      .selectOption(project.id);
    await page.goto(`/runs/${run.id}?view=inputs&tool=sources`);
    const panel = page.getByRole("region", {
      name: "输入来源与竞争策略",
      exact: true,
    });
    await expect(panel.locator("article")).toHaveCount(17);
    await panel
      .getByRole("button", { name: "调整来源策略", exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("界面文本 · 启用", { exact: true }).uncheck();
    await dialog
      .getByRole("button", { name: "切换到 JSON", exact: true })
      .click();
    const editor = dialog.getByRole("textbox", {
      name: "JSON 参数",
      exact: true,
    });
    const validation = page.waitForRequest((request) =>
      request.url().endsWith("/configuration/validate"),
    );
    await dialog.getByRole("button", { name: "校验", exact: true }).click();
    const changed = (await validation).postDataJSON().spec;
    expect(changed.source_policies.ui_text_enabled).toBe(false);
    changed.source_policies.audio_enabled = false;
    await editor.fill(JSON.stringify(changed));
    await dialog
      .getByRole("button", { name: "切换到图形配置", exact: true })
      .click();
    await expect(
      dialog.getByLabel("音频文件 · 启用", { exact: true }),
    ).not.toBeChecked();
    await dialog.getByRole("button", { name: "保存配置", exact: true }).click();
    await expect(dialog).toBeHidden();
    await expect(
      panel
        .locator("article")
        .filter({ has: page.getByText("界面文本", { exact: true }) }),
    ).toContainText("策略关闭准入");
    await panel.screenshot({
      path: info.outputPath("source-policies-desktop.png"),
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(350);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(391);
    await page.screenshot({
      path: info.outputPath("source-policies-mobile.png"),
      fullPage: true,
    });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(`/runs/${run.id}?view=conversation`);
    await expect(
      page.getByRole("button", { name: "接收并排队", exact: true }),
    ).toBeDisabled();
    const requestId = randomUUID();
    const carrier = info.outputPath("cli-stimulus.txt");
    await writeFile(carrier, "CLI 来源分帧证据", "utf8");
    const { stdout } = await promisify(execFile)(
      resolve("../.venv/Scripts/python.exe"),
      [
        "-X",
        "utf8",
        "-m",
        "threemind_lab.cli",
        "input-text",
        "--url",
        process.env.THREEMIND_E2E_URL!,
        "--project",
        project.id,
        "--run",
        run.id,
        "--file",
        carrier,
        "--request-id",
        requestId,
      ],
      { cwd: resolve("..") },
    );
    expect(JSON.parse(stdout).id).toBe(requestId);
    await page.request.post(base + "/commands", { data: { kind: "resume" } });
    await expect
      .poll(
        async () =>
          (await (await page.request.get(base + "/inputs/" + requestId)).json())
            .frames?.[0]?.status,
      )
      .toBe("delivered");
    const detail = await (
      await page.request.get(base + "/inputs/" + requestId)
    ).json();
    expect(detail.envelope.source).toBe("manual-cli-text");
    expect(detail.frames[0].source_policy.bypass_attention).toBe(true);
    expect(detail.frames[0].input_gate.competition_bypassed).toBe(true);
    await page.goto(`/runs/${run.id}?view=inputs&tool=capture`);
    await expect(
      page.getByRole("button", { name: "开始采集", exact: true }),
    ).toBeDisabled();
    expect(await page.evaluate(() => (window as any).__captureCalls)).toBe(0);
    expect(errors).toEqual([]);
  } finally {
    await page.request.post(base + "/commands", { data: { kind: "cancel" } });
  }
});
