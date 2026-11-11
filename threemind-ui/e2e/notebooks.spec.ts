import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

async function projectFor(page: any, name: string) {
  page.setDefaultTimeout(10000);
  const project = await (
    await page.request.post("/api/v2/projects", { data: { name } })
  ).json();
  await page.addInitScript(
    (id: string) => localStorage.setItem("tm2.project", id),
    project.id,
  );
  await page.goto("/notes");
  await expect(
    page.getByRole("heading", { name: "实验笔记", exact: true }),
  ).toBeVisible();
  return { project, base: `/api/v2/projects/${project.id}` };
}
const saved = (page: any) =>
  expect(page.locator(".note-save-status")).toContainText("已保存");
const source = (page: any) =>
  page.getByRole("textbox", { name: "Markdown 正文", exact: true });
const save = (page: any) =>
  page
    .locator(".note-save-actions")
    .getByRole("button", { name: "保存", exact: true })
    .click();

test("notebooks: rich table attributes, language, undo and narrow dark layout", async ({
  page,
}, info) => {
  const { base } = await projectFor(page, "复杂文档验收");
  const id = crypto.randomUUID();
  const paragraph = (text: string) => ({
    type: "paragraph",
    content: [{ type: "text", text }],
  });
  const content = {
    type: "doc",
    content: [
      {
        type: "paragraph",
        attrs: { textAlign: "center" },
        content: [
          {
            type: "text",
            text: "可恢复的格式",
            marks: [
              {
                type: "textStyle",
                attrs: {
                  color: "#237969",
                  fontSize: "24px",
                  fontFamily: "serif",
                },
              },
              { type: "underline" },
            ],
          },
        ],
      },
      {
        type: "table",
        content: [
          {
            type: "tableRow",
            content: [
              {
                type: "tableHeader",
                attrs: { colspan: 2, rowspan: 1, colwidth: [110, 130] },
                content: [paragraph("合并的标题")],
              },
            ],
          },
          {
            type: "tableRow",
            content: [
              { type: "tableCell", content: [paragraph("原始数据")] },
              { type: "tableCell", content: [paragraph("保留缺失")] },
            ],
          },
        ],
      },
      {
        type: "taskList",
        content: [
          {
            type: "taskItem",
            attrs: { checked: false },
            content: [paragraph("检查来源")],
          },
        ],
      },
      paragraph("尾段"),
    ],
  };
  expect(
    (
      await page.request.put(`${base}/notes/${id}`, {
        data: {
          operation_id: crypto.randomUUID(),
          expected_revision: 0,
          title: "表格与格式原稿",
          kind: "draft",
          body: { format: "document", content },
        },
      })
    ).ok(),
  ).toBeTruthy();
  await page.getByRole("tab", { name: "草稿", exact: true }).click();
  await page
    .locator(".note-item-open")
    .filter({ hasText: "表格与格式原稿" })
    .click();
  await page.getByRole("button", { name: "Markdown", exact: true }).click();
  await expect(source(page)).toContainText('colspan="2"');
  await page.getByRole("button", { name: "文档", exact: true }).click();
  await save(page);
  await saved(page);
  const persisted = (
    await (await page.request.get(`${base}/notes/${id}`)).json()
  ).body.content;
  expect(persisted.content[1].content[0].content[0].attrs).toMatchObject({
    colspan: 2,
    rowspan: 1,
    colwidth: [110, 130],
  });
  expect(persisted.content[0].attrs.textAlign).toBe("center");
  expect(persisted.content[0].content[0].marks).toEqual(
    expect.arrayContaining([
      { type: "underline" },
      expect.objectContaining({
        type: "textStyle",
        attrs: expect.objectContaining({
          fontSize: "24px",
          fontFamily: "serif",
        }),
      }),
    ]),
  );
  const editor = page.getByRole("textbox", { name: "文档正文", exact: true });
  await editor.locator("p").filter({ hasText: "尾段" }).click();
  await page.keyboard.press("End");
  await page.keyboard.type("XYZ");
  await page.getByLabel("切换界面语言", { exact: true }).selectOption("en");
  await expect(
    page.getByRole("textbox", { name: "Document content", exact: true }),
  ).toContainText("尾段XYZ");
  await expect(
    page.getByRole("checkbox", { name: "Task: 检查来源", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "Document content", exact: true }),
  ).not.toContainText("XYZ");
  await page
    .locator(".note-save-actions")
    .getByRole("button", { name: "Save", exact: true })
    .click();
  await expect(page.locator(".note-save-status")).toContainText("Saved");
  await page
    .getByRole("button", { name: "Fullscreen editor", exact: true })
    .click();
  await page.getByRole("button", { name: "Equation", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "Insert equation" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await page
    .getByRole("button", { name: "Exit fullscreen", exact: true })
    .click();
  await page.evaluate(() => {
    document.documentElement.dataset.theme = "dark";
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "Research notes", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: info.outputPath("notes-mobile-dark.png"),
    fullPage: true,
  });
});

test("notebooks: typing during an outstanding save is serialized without losing the later edit", async ({
  page,
}) => {
  const { base } = await projectFor(page, "笔记连续保存验收");
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let arrived!: () => void;
  const started = new Promise<void>((resolve) => {
    arrived = resolve;
  });
  let held = false;
  await page.route("**/notes/*", async (route) => {
    if (route.request().method() !== "PUT" || held) return route.continue();
    held = true;
    const response = await route.fetch();
    arrived();
    await gate;
    await route.fulfill({ response });
  });
  await source(page).fill("保存中的第一版");
  await save(page);
  await started;
  await source(page).fill("保存期间继续输入的第二版");
  release();
  await saved(page);
  const rows = (await (await page.request.get(base + "/notes")).json()).rows;
  expect(rows).toHaveLength(1);
  expect(rows[0].revision).toBe(2);
  expect(
    (await (await page.request.get(base + "/notes/" + rows[0].id)).json()).body
      .text,
  ).toBe("保存期间继续输入的第二版");
});

test("notebooks: authoring, two modes, organization, revisions, attachments and archive recovery", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const { base } = await projectFor(page, "笔记功能验收");
  await page
    .getByLabel("笔记标题", { exact: true })
    .fill("刺激撤除观察 · 写作验收");
  const markdown =
    "# 观察与假说\n\n**观察**不等于结论，保留阴性结果。\n\n- [ ] 核对输入\n- [x] 记录条件\n\n| 时刻 | 活动 |\n| --- | --- |\n| 0 | 1 |\n\n$$\nx^2 + y^2\n$$\n\n```python\nprint('research')\n```";
  await source(page).fill(markdown);
  await save(page);
  await saved(page);
  let row = (await (await page.request.get(base + "/notes")).json()).rows[0];
  const original = await (
    await page.request.get(base + "/notes/" + row.id)
  ).json();
  expect(original.body.text).toBe(markdown);
  await expect(page.locator(".cm-lineNumbers")).toBeVisible();
  await page.getByRole("button", { name: "文档", exact: true }).click();
  const document = page.getByRole("textbox", { name: "文档正文", exact: true });
  await expect(
    document.getByRole("heading", { name: "观察与假说" }),
  ).toBeVisible();
  await expect(document.locator("table")).toHaveCount(1);
  await expect(document.locator(".katex")).toHaveCount(1);
  await expect(document.locator(".katex-display")).toHaveCount(1);
  await document.locator('[data-type="block-math"]').click();
  await page
    .getByRole("dialog", { name: "编辑公式", exact: true })
    .getByLabel("LaTeX 公式", { exact: true })
    .fill("x^2 + y^2 + 1");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "确认", exact: true })
    .click();
  await expect(document.locator('[data-type="block-math"]')).toHaveAttribute(
    "data-latex",
    "x^2 + y^2 + 1",
  );
  await document.locator("p").filter({ hasText: "观察不等于结论" }).click();
  await page.getByLabel("对齐方式", { exact: true }).selectOption("center");
  await page.getByRole("button", { name: "Markdown", exact: true }).click();
  await expect(source(page)).toContainText("text-align: center");
  await page.getByRole("button", { name: "文档", exact: true }).click();
  await expect(
    document.locator("p").filter({ hasText: "观察不等于结论" }),
  ).toHaveCSS("text-align", "center");
  // Upload a valid, local image without external services.
  await page.locator('.note-editor input[type="file"]').setInputFiles({
    name: "观察.png",
    mimeType: "image/png",
    buffer: Buffer.from(
      await page.evaluate(() => {
        const canvas = document.createElement("canvas");
        canvas.width = 8;
        canvas.height = 8;
        const context = canvas.getContext("2d")!;
        context.fillStyle = "#237969";
        context.fillRect(0, 0, 8, 8);
        return canvas.toDataURL("image/png").split(",")[1];
      }),
      "base64",
    ),
  });
  await expect(document.locator("img")).toHaveCount(1);
  await save(page);
  await saved(page);
  await page.getByRole("button", { name: "图片附件", exact: true }).click();
  await expect(
    page.getByRole("dialog").getByText("修订正在引用", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "删除未引用图片" }),
  ).toBeDisabled();
  await page.getByRole("dialog").getByLabel("关闭", { exact: true }).click();
  await page.getByRole("button", { name: "新建分类", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByLabel("名称", { exact: true })
    .fill("刺激撤除");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "保存", exact: true })
    .click();
  await expect(
    page.getByRole("combobox", { name: "草稿分类", exact: true }),
  ).not.toHaveValue("");
  await save(page);
  await saved(page);
  await page.getByRole("tab", { name: "草稿", exact: true }).click();
  await expect(page.locator(".note-list .note-item")).toHaveCount(1);
  await page.getByRole("button", { name: "卡片视图", exact: true }).click();
  await expect(page.locator(".note-card-grid .note-item")).toHaveCount(1);
  await page.locator(".note-item-open").click();
  await page
    .getByRole("combobox", { name: "内容类型", exact: true })
    .selectOption("note");
  await expect(
    page.getByRole("combobox", { name: "保存到笔记本", exact: true }),
  ).not.toHaveValue("");
  await page.getByRole("button", { name: "新建笔记本", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByLabel("名称", { exact: true })
    .fill("感知与时间");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "保存", exact: true })
    .click();
  await save(page);
  await saved(page);
  await page.screenshot({
    path: info.outputPath("notes-writing.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "修订记录", exact: true }).click();
  await expect(page.locator(".note-history button").first()).toBeVisible();
  await page.locator(".note-history button").last().click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("textbox", { name: "Markdown 正文", exact: true }),
  ).toContainText("观察与假说");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "载入此修订", exact: true })
    .click();
  await save(page);
  await saved(page);
  expect(
    (await (await page.request.get(base + "/notes/" + row.id)).json()).body,
  ).toEqual(original.body);
  // Restore the rich note from a later revision and place it in the named notebook again.
  await page
    .getByRole("combobox", { name: "内容类型", exact: true })
    .selectOption("note");
  await page
    .getByRole("combobox", { name: "保存到笔记本", exact: true })
    .selectOption({ label: "感知与时间" });
  await save(page);
  await saved(page);
  await page.getByRole("tab", { name: "笔记本", exact: true }).click();
  await expect(page.locator(".notebook-shelf .notebook-card")).toHaveCount(2);
  await page.screenshot({
    path: info.outputPath("notes-shelf.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "列表视图", exact: true }).click();
  await expect(page.locator(".notebook-list .notebook-card")).toHaveCount(2);
  await page
    .locator(".notebook-open")
    .filter({ hasText: "感知与时间" })
    .click();
  await page
    .locator(".note-item")
    .getByRole("button", { name: "归档", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "没有符合条件的笔记" }),
  ).toBeVisible();
  await page.getByLabel("查看已归档", { exact: true }).check();
  await page
    .getByRole("button", { name: "全部已归档笔记", exact: true })
    .click();
  await page
    .locator(".note-item")
    .getByRole("button", { name: "恢复", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "没有符合条件的笔记" }),
  ).toBeVisible();
  row = await (await page.request.get(base + "/notes/" + row.id)).json();
  expect(row.archived_at).toBeNull();
  expect(row.kind).toBe("note");
  expect(errors).toEqual([]);
});

test("notebooks: lost acknowledgement recovers once; concurrent editing keeps both authors' versions", async ({
  page,
}) => {
  const { base } = await projectFor(page, "笔记恢复与冲突验收");
  page.on("dialog", (dialog) => dialog.accept());
  await page.getByLabel("笔记标题", { exact: true }).fill("网络中断原稿");
  await source(page).fill("尚未确认的原文");
  await page.route("**/notes/*", async (route) => {
    if (route.request().method() !== "PUT") return route.continue();
    await route.fetch();
    await route.abort("failed");
  });
  await save(page);
  await expect(page.locator(".note-save-status")).toContainText("保存未完成");
  let row = (await (await page.request.get(base + "/notes")).json()).rows[0];
  expect(row.revision).toBe(1);
  await page.reload();
  await expect(
    page.getByText("发现尚未确认保存的写作内容", { exact: true }),
  ).toBeVisible();
  await page.unroute("**/notes/*");
  await page.getByRole("button", { name: "恢复写作", exact: true }).click();
  await saved(page);
  row = await (await page.request.get(base + "/notes/" + row.id)).json();
  expect(row.revision).toBe(1);
  expect(row.body.text).toBe("尚未确认的原文");
  const external = await page.request.put(base + "/notes/" + row.id, {
    data: {
      title: "另一个窗口的新稿",
      kind: "draft",
      collection_id: null,
      expected_revision: 1,
      operation_id: crypto.randomUUID(),
      body: { format: "markdown", text: "另一个窗口写入的内容" },
    },
  });
  expect(external.ok()).toBeTruthy();
  await source(page).fill("当前窗口需要保留的修改");
  await save(page);
  await expect(
    page.getByRole("button", { name: "另存副本", exact: true }),
  ).toBeVisible();
  expect(
    (await (await page.request.get(base + "/notes/" + row.id)).json()).body
      .text,
  ).toBe("另一个窗口写入的内容");
  await expect(source(page)).toContainText("当前窗口需要保留的修改");
  await page.getByRole("button", { name: "另存副本", exact: true }).click();
  await saved(page);
  const rows = (await (await page.request.get(base + "/notes")).json()).rows;
  expect(rows).toHaveLength(2);
  const copied = rows.find((v: any) => v.id !== row.id);
  expect(copied.revision).toBe(1);
  expect(
    (await (await page.request.get(base + "/notes/" + copied.id)).json()).body
      .text,
  ).toBe("当前窗口需要保留的修改");
});
