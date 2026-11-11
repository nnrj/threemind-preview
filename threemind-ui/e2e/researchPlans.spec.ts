import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

async function sandbox(page: any) {
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "受控实验计划验收" },
    })
  ).json();
  const root = `/api/v2/projects/${project.id}`;
  const source = await (
    await page.request.post(root + "/runs", {
      data: {
        name: "计划起点",
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
        (await (await page.request.get(root + `/runs/${source.id}`)).json())
          .status,
    )
    .toBe("completed");
  const run = await (
    await page.request.post(root + `/runs/${source.id}/forks`, {
      data: { name: "控制变量沙箱", paused: true, background: "suspend" },
    })
  ).json();
  await page.goto("/");
  await page
    .getByLabel("当前研究项目", { exact: true })
    .selectOption(project.id);
  await page.goto(`/runs/${run.id}?view=research&tool=plans`);
  expect(run.spec.source_policies.background_enabled).toBe(false);
  return { run, base: root + `/runs/${run.id}` };
}

test("graphical templates, JSON roundtrip, manual steps and frozen evidence", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const { run, base } = await sandbox(page);
  const panel = page.getByRole("region", { name: "受控实验计划", exact: true });
  await panel
    .getByRole("button", { name: "设计实验计划", exact: true })
    .click();
  const editor = page.getByRole("dialog", {
    name: "设计受控实验计划",
    exact: true,
  });
  await editor.getByLabel("实验计划名称", { exact: true }).fill("顺序实验 A→B");
  await editor.getByLabel("执行模式", { exact: true }).selectOption("manual");
  await editor.getByText("从实验模板开始", { exact: true }).click();
  await editor.getByLabel("实验模板", { exact: true }).selectOption("order");
  await editor.getByLabel("刺激 A", { exact: true }).fill("A");
  await editor.getByLabel("刺激 B", { exact: true }).fill("B");
  await editor.getByLabel("每段推进（模拟秒）", { exact: true }).fill("0.01");
  await editor
    .getByRole("button", { name: "应用模板到草案", exact: true })
    .click();
  await expect(editor.getByRole("status")).toContainText("模板已载入");
  await editor.getByLabel("2 文本载体", { exact: true }).fill("A edited");
  await editor
    .getByRole("button", { name: "切换为 JSON 编辑", exact: true })
    .click();
  const validated = page.waitForRequest(
    (r) =>
      r.method() === "POST" && r.url().endsWith("/research/plans/validate"),
  );
  await editor
    .getByRole("button", { name: "校验计划", exact: true })
    .first()
    .click();
  const protocol = (await validated).postDataJSON();
  expect(protocol.steps[1].parameters.text).toBe("A edited");
  const json = editor.getByRole("textbox", {
    name: "研究计划 JSON",
    exact: true,
  });
  await json.fill(
    JSON.stringify({
      ...protocol,
      steps: [
        ...protocol.steps,
        { command: "unregistered.call", parameters: {} },
      ],
    }),
  );
  await editor
    .getByRole("button", { name: "冻结并保存计划", exact: true })
    .click();
  await expect(editor).toContainText("unregistered.call");
  expect(
    (await (await page.request.get(base + "/research/plans")).json()).rows,
  ).toHaveLength(0);
  protocol.steps[1].parameters.text = "A from JSON";
  await json.fill(JSON.stringify(protocol));
  await editor
    .getByRole("button", { name: "格式化 JSON", exact: true })
    .click();
  await editor
    .getByRole("button", { name: "切换为图形配置", exact: true })
    .click();
  await expect(editor.getByLabel("2 文本载体", { exact: true })).toHaveValue(
    "A from JSON",
  );
  await editor
    .getByRole("button", { name: "冻结并保存计划", exact: true })
    .click();
  await expect(editor).toBeHidden();
  const id = new URL(page.url()).searchParams.get("plan")!;
  const frozen = await (
    await page.request.get(base + `/research/plans/${id}`)
  ).json();
  expect(frozen.status).toBe("ready");
  for (let step = 1; step <= protocol.steps.length; step++) {
    await panel
      .getByRole("button", { name: "执行下一步骤", exact: true })
      .click();
    await expect(panel.locator(".plan-detail > .panel-heading")).toContainText(
      `已完成 ${step}/${protocol.steps.length} 步`,
    );
  }
  const done = await (
    await page.request.get(base + `/research/plans/${id}`)
  ).json();
  expect(done.status).toBe("completed");
  expect(done.protocol_hash).toBe(frozen.protocol_hash);
  expect((await (await page.request.get(base)).json()).time_us).toBe(
    String(Number(run.time_us) + 20000),
  );
  await expect(panel.locator(".plan-receipt")).toHaveCount(
    protocol.steps.length * 2,
  );
  const download = page.waitForEvent("download");
  await panel
    .getByRole("link", { name: "导出计划与轨迹 JSONL", exact: true })
    .click();
  expect((await download).suggestedFilename()).toContain("research-plan-");
  await panel.screenshot({
    path: info.outputPath("research-plans-desktop.png"),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("research-plans-mobile.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("lost plan control acknowledgement retries without rerunning steps", async ({
  page,
}) => {
  const { run, base } = await sandbox(page);
  const plan = await (
    await page.request.post(base + "/research/plans", {
      data: {
        name: "一次确认",
        request_id: crypto.randomUUID(),
        expected_revision: run.revision,
        protocol: {
          steps: [
            { command: "stimulus.send", parameters: { text: "once" } },
            { command: "runtime.wait", parameters: { duration_us: 10000 } },
          ],
        },
      },
    })
  ).json();
  let lost = false;
  await page.route(
    `**${base}/research/plans/${plan.id}/control`,
    async (route) => {
      if (!lost && route.request().method() === "POST") {
        lost = true;
        await route.fetch();
        await route.abort("failed");
      } else await route.continue();
    },
  );
  await page.goto(`/runs/${run.id}?view=research&tool=plans&plan=${plan.id}`);
  await page
    .getByRole("button", { name: "确认并开始计划", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "重试同一计划控制", exact: true }),
  ).toBeVisible();
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(base + `/research/plans/${plan.id}`)
          ).json()
        ).status,
    )
    .toBe("completed");
  await page
    .getByRole("button", { name: "重试同一计划控制", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "重试同一计划控制", exact: true }),
  ).toBeHidden();
  const records = (
    await (
      await page.request.get(base + `/research/actions?plan_id=${plan.id}`)
    ).json()
  ).rows;
  expect(
    records.filter((row: any) => row.kind === "stimulus.send"),
  ).toHaveLength(1);
  expect(
    records.filter((row: any) => row.kind === "runtime.resume"),
  ).toHaveLength(1);
  expect((await (await page.request.get(base)).json()).time_us).toBe(
    String(Number(run.time_us) + 10000),
  );
});
