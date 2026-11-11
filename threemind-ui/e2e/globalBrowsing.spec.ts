import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

test.skip(
  !process.env.THREEMIND_BROWSE_FIXTURE || !process.env.THREEMIND_E2E_URL,
  "Requires the dedicated browsing acceptance server and fixture.",
);
const fixture = process.env.THREEMIND_BROWSE_FIXTURE
  ? JSON.parse(readFileSync(process.env.THREEMIND_BROWSE_FIXTURE, "utf8"))
  : {};

test.beforeEach(async ({ page }) => {
  await page.addInitScript((project) => {
    localStorage.setItem("tm2.project", project);
    localStorage.setItem(
      "tm2.preferences",
      JSON.stringify({ locale: "zh-CN" }),
    );
  }, fixture.projects?.[0] || "old-project");
});

test("menus default to global lists, ignore old selection and paginate", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/research");
  await expect(
    page.getByRole("combobox", { name: "浏览范围", exact: true }),
  ).toHaveValue("");
  await expect(
    page.getByRole("heading", { name: "项目列表", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".project-summary-grid")).toContainText("Browse A");
  await expect(page.locator(".project-summary-grid")).toContainText("Browse B");
  for (const [path, title] of [
    ["/reports", "记录与报告"],
    ["/notes", "实验笔记"],
    ["/studies", "实验与训练"],
    ["/worlds", "世界与躯体"],
    ["/dialogue", "对话实验"],
    ["/compare", "比较与消融"],
    ["/data", "数据查询"],
    ["/data-management", "数据管理"],
    ["/models", "模型与证据"],
  ]) {
    await page.goto(path);
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
    await expect(page.locator(".browse-scope").first()).toContainText(
      "全部有权访问的项目",
    );
    if (path !== "/dialogue")
      await expect(
        page.getByRole("columnheader", { name: "所属项目", exact: true }),
      ).toBeVisible();
    await expect(page.getByRole("alert")).toHaveCount(0);
  }
  await page
    .getByRole("textbox", { name: "搜索资料或项目", exact: true })
    .fill("Browse instance");
  await expect(page.locator(".browse-table tbody tr")).toHaveCount(50);
  await page.getByRole("button", { name: "下一页", exact: true }).click();
  await expect(page.locator(".browse-table tbody tr")).toHaveCount(4);
  await page.screenshot({
    path: info.outputPath("global-models.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("explicit project filter spans menus and can return to all", async ({
  page,
}) => {
  await page.goto("/models");
  const scope = page.getByRole("combobox", { name: "浏览范围", exact: true });
  await scope.selectOption(fixture.projects[0]);
  await expect(page.locator(".browse-table tbody tr")).toHaveCount(27);
  await expect(page.locator(".browse-table tbody")).not.toContainText(
    "Browse B",
  );
  await page.getByRole("link", { name: "记录与报告", exact: true }).click();
  await page
    .getByRole("textbox", { name: "搜索资料或项目", exact: true })
    .fill("Browse report");
  await expect(page.locator(".browse-table tbody tr")).toHaveCount(1);
  await scope.selectOption("");
  await expect(page.locator(".browse-table tbody tr")).toHaveCount(2);
});

test("note and report ownership survives detail navigation and reload", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const note = fixture.notes[1],
    report = fixture.documents[1];
  await page.goto(`/notes?project=${note.project}&note=${note.id}&tab=write`);
  await expect(page.locator(".resource-owner")).toContainText("Browse B");
  await expect(
    page.getByRole("textbox", { name: "Markdown 正文", exact: true }),
  ).toContainText("UI fixture note content 1");
  await page.reload();
  await expect(
    page.getByRole("textbox", { name: "Markdown 正文", exact: true }),
  ).toContainText("UI fixture note content 1");
  await page.getByRole("button", { name: "返回全部资料", exact: true }).click();
  await expect(page.locator(".browse-table tbody tr")).toHaveCount(2);
  await page.goto(
    `/reports?project=${report.project}&document=${report.id}&tab=report`,
  );
  await expect(page.locator(".resource-owner")).toContainText("Browse B");
  await expect(
    page.getByRole("textbox", { name: "Markdown 说明", exact: true }),
  ).toHaveValue(/UI fixture report content 1/);
  await page.getByRole("button", { name: "预览与校验", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText(
    "UI fixture report content 1",
  );
  await expect(page.getByRole("alert")).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("legacy run link resolves ownership independently of browsing scope", async ({
  page,
}) => {
  await page.goto("/models");
  await page
    .getByRole("combobox", { name: "浏览范围", exact: true })
    .selectOption(fixture.projects[1]);
  const run = fixture.runs[0];
  await page.evaluate((url) => {
    window.history.pushState({}, "", url);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, `/runs/${run.id}`);
  await expect(
    page.getByRole("combobox", { name: "浏览范围", exact: true }),
  ).toHaveCount(0);
  await expect(page.locator(".resource-owner")).toContainText("Browse A");
  await expect(page).toHaveURL(new RegExp(`project=${fixture.projects[0]}`));
  await expect(
    page.getByRole("heading", { name: run.name, exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("creation requires a visible destination and writes to that project", async ({
  page,
}) => {
  await page.goto(`/projects?project=${fixture.viewer_project}`);
  await expect(
    page.getByRole("heading", { name: "新建意识的默认配置", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "保存项目默认配置", exact: true }),
  ).toBeDisabled();
  await page.goto("/");
  await page
    .locator(".consciousness-player-buttons")
    .getByRole("button", { name: "新建意识", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  const destination = dialog.getByRole("combobox", {
    name: "所属项目",
    exact: true,
  });
  await expect(destination).toHaveValue("");
  await expect(
    destination.locator(`option[value="${fixture.viewer_project}"]`),
  ).toHaveCount(0);
  await expect(
    dialog.getByRole("button", { name: "创建并准备", exact: true }),
  ).toBeDisabled();
  await destination.selectOption(fixture.projects[1]);
  await dialog
    .getByRole("textbox", { name: "意识名称", exact: true })
    .fill("Explicit destination fixture");
  const created = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/projects/${fixture.projects[1]}/runs`),
  );
  await dialog.getByRole("button", { name: "创建并准备", exact: true }).click();
  const response = await created;
  expect(response.status()).toBe(201);
  expect((await response.json()).project_id).toBe(fixture.projects[1]);
  await expect(page.locator(".resource-owner")).toContainText("Browse B");
});

test("English narrow-screen browsing keeps global scope and bounded layout", async ({
  page,
}, info) => {
  await page.addInitScript(() =>
    localStorage.setItem("tm2.preferences", JSON.stringify({ locale: "en" })),
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/reports");
  await expect(
    page.getByRole("heading", { name: "Records & reports", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".browse-scope").first()).toContainText(
    "all authorized projects",
  );
  await page
    .getByRole("textbox", { name: "Search resources or projects", exact: true })
    .fill("Browse report");
  await expect(page.locator(".browse-table tbody tr")).toHaveCount(2);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("global-reports-en-mobile.png"),
    fullPage: true,
  });
});
