import { test, expect, type Page } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Select a disposable frontend preview; every API request below is mocked.",
);
const project = "00000000-0000-0000-0000-000000000001";
async function fixture(page: Page, admin = true, withProject = true) {
  const writes: { path: string; body: any; identity: string }[] = [];
  await page.route("**/api/v2/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    const body = request.method() === "GET" ? null : request.postDataJSON();
    if (body)
      writes.push({
        path,
        body,
        identity: request.headers()["x-threemind-request-id"],
      });
    let response: any = {};
    if (path.endsWith("/session"))
      response = {
        user: { id: "fixture-user", admin, superadmin: admin },
        mode: "workstation",
      };
    else if (path === "/api/v2/projects")
      response = withProject
        ? [{ id: project, name: "Disposable fixture", role: "owner" }]
        : [];
    else if (path.endsWith("/notifications/unread")) response = { unread: 0 };
    else if (path.endsWith("/data"))
      response = {
        rows: [
          {
            kind: "document",
            id: "report-fixture",
            name: "Evidence report",
            bytes: 128,
          },
        ],
        more: false,
      };
    else if (path.endsWith("/export-plans"))
      response = {
        id: "plan-fixture",
        objects: ["report-fixture"],
        bytes: 128,
        blockers: [],
      };
    else if (path.endsWith("/exports"))
      response = { id: "job-fixture", status: "queued" };
    else if (path.endsWith("/bundles"))
      response = {
        rows: [{ id: "bundle-fixture", name: "Imported fixture" }],
        more: false,
      };
    else if (path.endsWith("/bundles/bundle-fixture"))
      response = { name: "Imported fixture", volumes: [] };
    else if (path.endsWith("/resume-plan"))
      response = {
        can_resume:
          new URL(request.url()).searchParams.get("backend") === "reference",
        blockers: [],
      };
    else if (path.endsWith("/resumes")) response = { state: "paused" };
    else if (path.endsWith("/blob-candidates"))
      response = {
        rows: [{ id: "candidate-fixture", bytes: 512, state: "failed" }],
        more: false,
      };
    else if (path.endsWith("/research-artifacts"))
      response = {
        rows: [
          {
            resource_id: "research-artifact:fixture",
            legacy_path: "lab/E-fixture/result.json.gz",
            archive_path: "data/experiments/E-fixture/result.json.gz",
            bytes: 4096,
          },
        ],
        more: false,
      };
    else if (path === "/api/v2/storage")
      response = {
        policies: { revision: 0, categories: {} },
        data_root: { path: "E:/test", requested_path: "E:/test", revision: 0 },
        checkpoint_settings: { backend: "database", revision: 0 },
        checkpoint_backend: "database",
        targets: [],
        resources: [
          { id: "offline-fixture", revision: 1, writer_mode: "sealed" },
        ],
        features: {},
      };
    else if (path === "/api/v2/storage/resources/offline-fixture")
      response = {
        resource: { id: "offline-fixture", revision: 1, writer_mode: "sealed" },
        bytes: 256,
      };
    else if (path === "/api/v2/storage/data-exports")
      response = {
        id: body.operation_id,
        resource_id: "offline-fixture",
        state: "complete",
        volumes: [{ ordinal: 0, filename: "fixture.v001.tmdata", bytes: 256 }],
      };
    else if (path.endsWith("/cleanup-preview"))
      response = {
        allowed: false,
        name: "candidate-fixture",
        token: "a".repeat(64),
        reasons: ["protected immutable evidence"],
      };
    await route.fulfill({ json: response });
  });
  await page.goto("/data-management");
  await expect(
    page.getByRole("heading", { name: "数据管理", exact: true }),
  ).toBeVisible();
  return writes;
}

test("experiment disk placement previews before reserving, with splitting off by default", async ({
  page,
}) => {
  await fixture(page);
  const directories = [
    {
      id: "primary",
      path: "E:/test",
      priority: 1,
      reserve_bytes: 0,
      limit_bytes: null,
      enabled: true,
      online: true,
      available_bytes: 1024 ** 3,
    },
    {
      id: "portable",
      path: "H:/test",
      priority: 2,
      reserve_bytes: 0,
      limit_bytes: null,
      enabled: true,
      online: true,
      available_bytes: 2 * 1024 ** 3,
    },
  ];
  const requests: any[] = [];
  let saved: any;
  await page.route("**/api/v2/storage/experiment-pool**", async (route) => {
    const req = route.request(),
      path = new URL(req.url()).pathname;
    if (req.method() === "GET") {
      await route.fulfill({
        json: path.includes("/studies/")
          ? saved
          : { revision: 1, directories, studies: saved ? [saved] : [] },
      });
      return;
    }
    const body = req.postDataJSON();
    requests.push(body);
    const plan = {
      ...body,
      fits: true,
      status: "reserved",
      parts: body.parts.map((p: any) => ({
        ...p,
        directory: "portable",
        relative_path: "experiments/" + body.name,
      })),
    };
    if (path.endsWith("/reserve")) saved = plan;
    await route.fulfill({ json: plan });
  });
  await page.getByRole("link", { name: "存储位置", exact: true }).click();
  await page.getByText("实验数据目录与多盘分配", { exact: true }).click();
  await expect(page.getByLabel("允许本次实验跨目录存储")).not.toBeChecked();
  await page.getByLabel("实验目录名", { exact: true }).fill("mayfly");
  await expect(page.getByRole("button", { name: "确认预留" })).toBeDisabled();
  await page.getByRole("button", { name: "预估空间" }).click();
  await expect(page.getByText(/portable \/ experiments\/mayfly/)).toBeVisible();
  await page.getByRole("button", { name: "确认预留" }).click();
  await expect.poll(() => requests.length).toBe(2);
  expect(requests[1]).toMatchObject({
    name: "mayfly",
    allow_split: false,
    parts: [{ name: "main", kind: "data", bytes: 1024 ** 3 }],
  });
});

test("experiment transfers preview archive separately from releasing its old copy", async ({
  page,
}) => {
  await fixture(page);
  const dirs = [
    {
      id: "e",
      path: "E:/test",
      role: "run",
      volume: "e-volume",
      physical_disks: ["1"],
      enabled: true,
      online: true,
      priority: 1,
      reserve_bytes: 0,
      limit_bytes: null,
    },
    {
      id: "h",
      path: "H:/test-archive",
      role: "archive",
      volume: "h-volume",
      physical_disks: ["3"],
      enabled: true,
      online: true,
      priority: 2,
      reserve_bytes: 0,
      limit_bytes: null,
    },
  ];
  dirs.unshift(
    {
      ...dirs[1],
      id: "same-volume",
      path: "E:/other",
      volume: "e-volume",
      physical_disks: ["1"],
      priority: 0,
    },
    {
      ...dirs[1],
      id: "same-device",
      path: "F:/other",
      volume: "f-volume",
      physical_disks: ["1"],
      priority: 0,
    },
  );
  const study = {
    name: "aquatic",
    status: "complete",
    residency: "active",
    directories: ["e"],
  };
  const job = {
    id: "job-fixture",
    name: "aquatic",
    operation: "archive",
    destination: "h",
    status: "complete",
    created: 1,
  };
  let started = false,
    released = false;
  await page.route("**/api/v2/storage/experiment-pool**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let result: unknown = { directories: dirs, revision: 1, studies: [study] };
    if (path.endsWith("/transfers"))
      result = { studies: [study], jobs: started ? [job] : [] };
    else if (path.endsWith("/preview"))
      result = { bytes: 64, files: 1, available_bytes: 2048, online: true };
    else if (path.endsWith("/jobs")) {
      expect(route.request().postDataJSON()).toMatchObject({
        operation: "archive",
        destination: "h",
        name: "aquatic",
      });
      started = true;
      result = job;
    } else if (path.endsWith("/release")) {
      released = true;
      job.status = "released";
      result = job;
    }
    await route.fulfill({ json: result });
  });
  await page.getByRole("link", { name: "存储位置", exact: true }).click();
  await page.getByText("实验数据目录与多盘分配", { exact: true }).click();
  await page.getByText("实验同步、迁移与归档", { exact: true }).click();
  const panel = page
    .getByText("实验同步、迁移与归档", { exact: true })
    .locator("..");
  await panel.getByRole("combobox", { name: "操作", exact: true }).selectOption("archive");
  await panel.getByRole("combobox", { name: "实验名称", exact: true }).selectOption("aquatic");
  const destination = panel.getByRole("combobox", { name: "目标目录", exact: true });
  await expect(destination).toHaveValue("h");
  await destination.selectOption("same-volume");
  await expect(panel.getByText(/归档目录与源数据在同一卷/)).toBeVisible();
  await destination.selectOption("h");
  await expect(panel.getByRole("button", { name: "开始传输" })).toBeDisabled();
  await panel.getByRole("button", { name: "预览传输" }).click();
  await panel.getByRole("button", { name: "开始传输" }).click();
  await panel.getByRole("button", { name: "释放旧副本", exact: true }).click();
  expect(released).toBe(false);
  await panel.getByRole("button", { name: "确认释放旧副本" }).click();
  await expect.poll(() => released).toBe(true);
});

test("inventory export is previewed first and repeated commands retain their request identity", async ({
  page,
}, info) => {
  const writes = await fixture(page);
  await expect(
    page.getByRole("button", { name: "确认建立导出任务" }),
  ).toHaveCount(0);
  await page.getByRole("checkbox").check();
  await page
    .getByRole("button", { name: "预览所选资料打包", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "确认建立导出任务", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "确认建立导出任务", exact: true })
    .click();
  await expect(
    page.getByText("任务已登记；请等待任务完成后在数据包中下载。"),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "确认建立导出任务", exact: true })
    .click();
  await expect
    .poll(() => writes.filter((row) => row.path.endsWith("/exports")).length)
    .toBe(2);
  const plans = writes.filter((row) => row.path.endsWith("/export-plans"));
  expect(plans[0].body.selection).toEqual({
    resources: [{ kind: "document", id: "report-fixture" }],
  });
  const jobs = writes.filter((row) => row.path.endsWith("/exports"));
  expect(jobs[0].identity).toBe(jobs[1].identity);
  expect(jobs[0].body.operation_id).toBe(jobs[1].body.operation_id);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("heading", { name: "资料目录", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("data-management-mobile.png"),
    fullPage: true,
  });
});

test("host tools require an administrator and protected cleanup cannot be confirmed", async ({
  page,
}, info) => {
  await fixture(page, false);
  await expect(
    page.getByRole("button", { name: "存储位置", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "完整性与清理", exact: true }).click();
  await page.getByRole("button", { name: "检查此候选", exact: true }).click();
  await expect(page.getByLabel("上传候选编号", { exact: true })).toHaveValue(
    "candidate-fixture",
  );
  await page
    .getByLabel("上传候选编号", { exact: true })
    .fill("candidate-fixture");
  await page.getByRole("button", { name: "生成清理预览", exact: true }).click();
  await page
    .getByLabel("输入预览中的对象名称以确认永久删除", { exact: true })
    .fill("candidate-fixture");
  await expect(
    page.getByRole("button", { name: "确认永久清理候选", exact: true }),
  ).toBeDisabled();
  await page.screenshot({
    path: info.outputPath("data-cleanup-protected.png"),
    fullPage: true,
  });
});

test("host archive browsing uses registered logical IDs and correct breadcrumbs", async ({
  page,
}) => {
  await fixture(page);
  await page.getByRole("button", { name: "存储位置", exact: true }).click();
  await expect(
    page.getByText("lab/E-fixture/result.json.gz", { exact: true }),
  ).toBeVisible();
  const download = page.getByRole("link", { name: "下载原件", exact: true });
  await expect(download).toHaveAttribute(
    "href",
    "/api/v2/storage/research-artifacts/research-artifact%3Afixture/content",
  );
  await expect(page.locator(".breadcrumb")).toContainText("数据管理");
  await expect(page.locator(".breadcrumb")).not.toContainText("数据查询");
});

test("host administrator storage tools do not require a fabricated project", async ({
  page,
}) => {
  await fixture(page, true, false);
  await expect(
    page.getByRole("heading", { name: "归档实验原件", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "资料目录", exact: true }),
  ).toHaveCount(0);
});

test("offline export requires inspected host resource and exposes only read-only archive downloads", async ({
  page,
}) => {
  const writes = await fixture(page, true, false);
  await expect(
    page.getByRole("button", { name: "打包所检查的离线资料", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "检查迁移条件", exact: true }).click();
  await expect(
    page.getByText(
      "保存所检查目录内的全部原件为只读数据包；目录外的依赖不自动推断，不能作为完整主体续跑。",
      { exact: true },
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "打包所检查的离线资料", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: "下载总清单", exact: true }),
  ).toBeVisible();
  const saved = writes.find(
    (row) => row.path === "/api/v2/storage/data-exports",
  )!;
  expect(saved.body.resource_id).toBe("offline-fixture");
  expect(saved.body.expected_revision).toBe(1);
  expect(saved.body.operation_id).toBe(saved.identity);
  await expect(
    page.getByRole("link", { name: /fixture.v001.tmdata/ }),
  ).toHaveAttribute(
    "href",
    `/api/v2/storage/data-exports/${saved.identity}/volumes/0`,
  );
  expect(writes.some((row) => row.path.includes("/migrations"))).toBe(false);
});

test("runtime backend changes invalidate previews and the chosen backend is sent to resumption", async ({
  page,
}) => {
  const writes = await fixture(page);
  await page.getByRole("button", { name: "数据包", exact: true }).click();
  await page.getByRole("button", { name: "查看数据包", exact: true }).click();
  await page
    .getByLabel("待恢复主体的来源对象编号", { exact: true })
    .fill("subject-fixture");
  await page
    .getByRole("combobox", { name: "主体恢复运行后端", exact: true })
    .selectOption("reference");
  await page
    .getByRole("button", { name: "检查主体恢复条件", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "确认恢复为暂停副本", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("combobox", { name: "主体恢复运行后端", exact: true })
    .selectOption("native");
  await expect(
    page.getByRole("button", { name: "确认恢复为暂停副本", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("combobox", { name: "主体恢复运行后端", exact: true })
    .selectOption("reference");
  await page
    .getByRole("button", { name: "检查主体恢复条件", exact: true })
    .click();
  await page
    .getByRole("button", { name: "确认恢复为暂停副本", exact: true })
    .click();
  await expect
    .poll(() => writes.filter((row) => row.path.endsWith("/resumes")).length)
    .toBe(1);
  expect(
    writes.find((row) => row.path.endsWith("/resumes"))!.body.backend,
  ).toBe("reference");
});
