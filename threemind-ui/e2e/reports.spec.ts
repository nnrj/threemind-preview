import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

async function fixture(page: any, withRun = true) {
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "记录与报告工程验收 " + Date.now() },
    })
  ).json();
  const base = `/api/v2/projects/${project.id}`;
  await page.addInitScript(
    (id: string) => localStorage.setItem("tm2.project", id),
    project.id,
  );
  let run: any;
  if (withRun) {
    const response = await page.request.post(base + "/runs", {
      data: {
        name: "固定来源工程样例",
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
    });
    expect(response.status()).toBe(201);
    run = await response.json();
    await expect
      .poll(
        async () =>
          (await (await page.request.get(`${base}/runs/${run.id}`)).json())
            .status,
      )
      .toBe("completed");
  }
  await page.goto("/reports");
  await expect(
    page.getByRole("heading", { name: "记录与报告", exact: true }),
  ).toBeVisible();
  return { project, base, run };
}
const editor = (page: any) =>
  page.getByRole("textbox", { name: "记录与报告 JSON", exact: true });
async function readSpec(page: any) {
  // CodeMirror virtualizes long documents; rendered DOM text is not its whole JSON.
  const request = page.waitForRequest(
    (r: any) =>
      r.url().endsWith("/research-documents/preview") && r.method() === "POST",
  );
  await page.getByRole("button", { name: "校验", exact: true }).click();
  const body = (await request).postDataJSON();
  await expect(page.getByRole("status")).toContainText("校验通过");
  return body;
}
async function captured(page: any, base: string, run: any) {
  const request = await (
    await page.request.post(base + "/report-sources", {
      data: {
        operation_id: crypto.randomUUID(),
        run_id: run.id,
        kind: "trajectory",
        metrics: ["activation", "mean_weight", "edges"],
      },
    })
  ).json();
  await expect
    .poll(
      async () =>
        !!(
          await (
            await page.request.get(`${base}/report-sources/${request.id}`)
          ).json()
        ).content_hash,
    )
    .toBeTruthy();
  return request.id;
}

test("exports: fixed revision, lost acknowledgement, documents and complete evidence downloads", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const { base, run } = await fixture(page);
  const source = await captured(page, base, run);
  const spec = await (
    await page.request.get(`${base}/report-sources/${source}/template`)
  ).json();
  spec.title = "可复核的导出样例";
  spec.blocks[0].markdown = "中文记录与公式 $a(t)=a_0e^{-t/\\tau}$。";
  const id = crypto.randomUUID();
  expect(
    (
      await page.request.put(`${base}/research-documents/${id}`, {
        data: { operation_id: crypto.randomUUID(), expected_revision: 0, spec },
      })
    ).ok(),
  ).toBeTruthy();
  await page.reload();
  await page.getByRole("button", { name: "导出", exact: true }).click();
  const modal = page.getByRole("dialog", {
    name: "导出记录与报告",
    exact: true,
  });
  await modal
    .getByRole("checkbox", { name: "证据包附带全部固定来源数据行（可能较大）" })
    .check();
  await modal
    .getByRole("spinbutton", { name: "每张正文表格最多行数", exact: true })
    .fill("120");
  let dropped = false;
  await page.route(`**/research-documents/${id}/exports`, async (route) => {
    if (!dropped && route.request().method() === "POST") {
      dropped = true;
      await route.fetch();
      await route.abort();
    } else await route.continue();
  });
  await modal
    .getByRole("button", { name: "生成导出文件", exact: true })
    .click();
  await expect(modal.getByRole("alert")).toBeVisible();
  await modal
    .getByRole("button", { name: "生成导出文件", exact: true })
    .click();
  await expect(
    modal.getByRole("link", { name: "下载正文", exact: true }),
  ).toBeVisible({ timeout: 60000 });
  const history = await (
    await page.request.get(`${base}/research-documents/${id}/exports`)
  ).json();
  expect(history.rows).toHaveLength(1);
  expect(history.rows[0].revision).toBe(1);
  const pdfPending = page.waitForEvent("download");
  await modal.getByRole("link", { name: "下载正文", exact: true }).click();
  const pdf = await pdfPending;
  const path = info.outputPath("research-export.pdf");
  await pdf.saveAs(path);
  expect((await readFile(path)).subarray(0, 5).toString()).toBe("%PDF-");
  const zipPending = page.waitForEvent("download");
  await modal.getByRole("link", { name: "下载证据 ZIP", exact: true }).click();
  const zip = await zipPending;
  await zip.saveAs(info.outputPath("research-evidence.zip"));
  expect(zip.suggestedFilename()).toMatch(/\.zip$/);
  await page.screenshot({
    path: info.outputPath("report-export.png"),
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "编辑", exact: true }).click();
  await page
    .getByRole("textbox", { name: "文档标题", exact: true })
    .fill("未保存的更改");
  await page.getByRole("button", { name: "导出", exact: true }).click();
  await expect(
    modal.getByRole("button", { name: "生成导出文件", exact: true }),
  ).toBeDisabled();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await modal.evaluate((el) => el.scrollWidth <= el.clientWidth + 1),
  ).toBeTruthy();
  await page.screenshot({
    path: info.outputPath("report-export-mobile.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("records: graphical capture, defaults, synchronized JSON and authoritative validation", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const { base, run } = await fixture(page);
  await page.getByRole("button", { name: "新建实验记录", exact: true }).click();
  await page
    .getByRole("textbox", { name: "文档标题", exact: true })
    .fill("固定数据的实验观察");
  await page.getByRole("button", { name: "添加数据来源", exact: true }).click();
  const dialog = page.getByRole("dialog", {
    name: "选择或采集数据来源",
    exact: true,
  });
  await dialog
    .getByRole("combobox", { name: "意识", exact: true })
    .selectOption(run.id);
  await dialog.getByRole("button", { name: "开始采集", exact: true }).click();
  await dialog.getByRole("button", { name: "使用此来源", exact: true }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator(".report-block-editor")).toHaveCount(6);
  await page
    .getByRole("textbox", { name: "Markdown 说明", exact: true })
    .first()
    .fill("检验刺激后的连接变化。\n\n假说：$a(t)=a_0e^{-t/\\tau}$。");
  await page
    .getByRole("button", { name: "切换到 JSON 编辑", exact: true })
    .click();
  let spec = await readSpec(page);
  expect(spec.title).toBe("固定数据的实验观察");
  expect(spec.blocks[0].markdown).toContain("检验刺激");
  await editor(page).fill(
    JSON.stringify({ ...spec, title: "经来源校验的观察" }),
  );
  await page.getByRole("button", { name: "格式化", exact: true }).click();
  await page
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(
    page.getByRole("textbox", { name: "文档标题", exact: true }),
  ).toHaveValue("经来源校验的观察");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已保存修订 1");
  await page.screenshot({
    path: info.outputPath("records-editor.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "切换到 JSON 编辑", exact: true })
    .click();
  spec = await readSpec(page);
  await editor(page).fill(
    JSON.stringify({
      ...spec,
      blocks: [{ ...spec.blocks[1], fabricated_values: [99] }],
    }),
  );
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("fabricated_values");
  expect(
    (await (await page.request.get(base + "/research-documents")).json())
      .rows[0].revision,
  ).toBe(1);
  await editor(page).fill(JSON.stringify(spec));
  await page.getByRole("button", { name: "预览与校验", exact: true }).click();
  const preview = page.getByRole("dialog", { name: "记录预览", exact: true });
  await expect(preview.locator(".report-chart svg").first()).toBeVisible();
  await expect(preview.locator(".katex").first()).toBeVisible();
  expect(
    await preview
      .locator(".katex-mathml")
      .first()
      .evaluate((el) => getComputedStyle(el).position),
  ).toBe("absolute");
  await expect(
    preview.getByText("共 151 行；每页显示 100 行。", { exact: true }),
  ).toBeVisible();
  await preview
    .getByRole("button", { name: "浏览全部数据", exact: true })
    .click();
  await preview.getByRole("button", { name: "下一页", exact: true }).click();
  await expect(preview.locator("tbody tr")).toHaveCount(51);
  await preview.evaluate((element) => {
    element.scrollTop = 0;
  });
  await page.screenshot({
    path: info.outputPath("records-preview.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("records: interrupted save retries once; unsaved JSON recovers across navigation", async ({
  page,
}) => {
  const { base } = await fixture(page, false);
  await page.getByRole("button", { name: "新建实验记录", exact: true }).click();
  await page
    .getByRole("textbox", { name: "文档标题", exact: true })
    .fill("需要恢复的记录");
  await page
    .getByRole("button", { name: "切换到 JSON 编辑", exact: true })
    .click();
  const value = JSON.parse(await editor(page).innerText());
  await editor(page).fill(
    JSON.stringify({
      ...value,
      blocks: [
        {
          id: "a",
          type: "commentary",
          section: "hypothesis",
          markdown: "暂存内容",
        },
      ],
    }),
  );
  await page.getByRole("link", { name: "项目文档", exact: true }).click();
  await page.getByRole("link", { name: "记录与报告", exact: true }).click();
  await page.getByRole("button", { name: "新建实验记录", exact: true }).click();
  await expect(editor(page)).toContainText("暂存内容");
  let lost = false;
  await page.route("**/research-documents/*", async (route) => {
    if (route.request().method() === "PUT" && !lost) {
      lost = true;
      await route.fetch();
      await route.abort("failed");
    } else await route.continue();
  });
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已保存修订 1");
  const list = (
    await (await page.request.get(base + "/research-documents")).json()
  ).rows;
  expect(list).toHaveLength(1);
  expect(list[0].revision).toBe(1);
  await page.getByRole("button", { name: "返回列表", exact: true }).click();
  await page.getByRole("button", { name: "编辑", exact: true }).click();
  await page
    .getByRole("textbox", { name: "文档标题", exact: true })
    .fill("保留我的并发草案");
  const row = await (
    await page.request.get(`${base}/research-documents/${list[0].id}`)
  ).json();
  await page.request.put(`${base}/research-documents/${row.id}`, {
    data: {
      operation_id: crypto.randomUUID(),
      expected_revision: 1,
      spec: { ...row.spec, title: "另一位作者的新版本" },
    },
  });
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("document changed");
  await page.getByRole("button", { name: "另存为副本", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已保存修订 1");
  const final = (
    await (await page.request.get(base + "/research-documents")).json()
  ).rows;
  expect(final.map((r: any) => r.title).sort()).toEqual(
    ["保留我的并发草案", "另一位作者的新版本"].sort(),
  );
});

test("reports: fixed record references survive later changes; English and mobile dark layout", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const { base, run } = await fixture(page);
  const source = await captured(page, base, run);
  const spec = await (
    await page.request.get(`${base}/report-sources/${source}/template`)
  ).json();
  const record = crypto.randomUUID();
  await page.request.put(`${base}/research-documents/${record}`, {
    data: {
      operation_id: crypto.randomUUID(),
      expected_revision: 0,
      spec: { ...spec, title: "可引用的固定实验记录" },
    },
  });
  await page.getByRole("tab", { name: "实验报告", exact: true }).click();
  await page.getByRole("button", { name: "新建实验报告", exact: true }).click();
  await page
    .getByRole("textbox", { name: "文档标题", exact: true })
    .fill("跨记录的研究报告");
  await page.getByRole("button", { name: "引用实验记录", exact: true }).click();
  const picker = page.getByRole("dialog", {
    name: "引用实验记录",
    exact: true,
  });
  await picker
    .getByRole("combobox", { name: "实验记录", exact: true })
    .selectOption(record);
  await picker
    .locator(".report-source-list>div")
    .filter({ hasText: "mean_weight" })
    .getByRole("button", { name: "添加引用" })
    .click();
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("已保存修订 1");
  await page.request.put(`${base}/research-documents/${record}`, {
    data: {
      operation_id: crypto.randomUUID(),
      expected_revision: 1,
      spec: { ...spec, title: "修改后的记录", blocks: [] },
    },
  });
  await page.getByRole("button", { name: "预览与校验", exact: true }).click();
  await expect(
    page.locator(".report-reference .report-chart svg"),
  ).toBeVisible();
  await page
    .getByRole("dialog", { name: "记录预览", exact: true })
    .getByRole("button", { name: "关闭", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "切换界面语言", exact: true })
    .selectOption("en");
  await expect(
    page.getByRole("button", { name: "Preview & validate", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("status")).toContainText("Validated");
  await expect(
    page.getByText("Unsaved changes", { exact: true }),
  ).not.toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "Document title", exact: true }),
  ).toHaveValue("跨记录的研究报告");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate(() => {
    document.documentElement.dataset.theme = "dark";
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: info.outputPath("reports-mobile-dark.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
