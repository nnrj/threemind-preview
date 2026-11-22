import { test, expect, type Page } from "@playwright/test";
import { readFileSync, existsSync, readdirSync } from "node:fs";
const cataloguePath =
  process.env.THREEMIND_UI_CATALOGUE || "../.work/platform-ui-catalogue.json";
test.skip(
  !process.env.THREEMIND_E2E_URL || !existsSync(cataloguePath),
  "Requires isolated UI and generated source-only catalogue; no live database.",
);
const catalogue = existsSync(cataloguePath)
  ? JSON.parse(readFileSync(cataloguePath, "utf8"))
  : {};
const aiRouteSource = readFileSync("../src/threemind_lab/ai_api.py", "utf8");
const providerId = "44444444-4444-4444-8444-444444444444",
  callId = "55555555-5555-4555-8555-555555555555";
const provider = (diagnose = false) => ({
  id: providerId,
  project_id: null,
  revision: 1,
  config: {
    name: "Authorized text service",
    model: "mock-text",
    base_url: "https://example.invalid/v1",
    protocol: "chat",
    enabled: true,
    max_output_tokens: 64,
    timeout_s: 60,
  },
  has_api_key: true,
  network_allowed: true,
  authorized_projects: ["22222222-2222-4222-8222-222222222222"],
  can_diagnose: diagnose,
  can_manage: false,
});
function assertRegisteredAIRequests(
  requests: { method: string; path: string }[],
) {
  for (const request of requests.filter((r) => r.path.startsWith("/ai/"))) {
    const path = request.path
      .split("?")[0]
      .replace(providerId, "{provider_id}")
      .replace(callId, "{call_id}");
    expect(
      aiRouteSource,
      `${request.method} ${path} must be a registered backend route`,
    ).toContain(`@app.${request.method.toLowerCase()}("/api/v2${path}"`);
  }
  expect(requests.some((r) => r.path.startsWith("/admin/ai/calls"))).toBe(
    false,
  );
}
const local = "00000000-0000-4000-8000-000000000001",
  runId = "11111111-1111-4111-8111-111111111111",
  projectId = "22222222-2222-4222-8222-222222222222";
const projects = [
  {
    id: projectId,
    name: "Research A",
    role: "owner",
    created_at: "2026-10-11",
  },
  {
    id: "33333333-3333-4333-8333-333333333333",
    name: "Research B",
    role: "owner",
    created_at: "2026-10-11",
  },
];
const run = () => ({
  id: runId,
  name: "Read-only opening witness",
  spec: catalogue.defaults,
  status: "paused",
  life: "waiting",
  revision: 0,
  metadata_revision: 7,
  time_us: "0",
  metrics: { nodes: 0, edges: 0, activation: 0, inhibition: 0 },
  body: {},
  created_at: "2026-10-11",
  assessment: null,
  ecology: null,
});

test("memory/4 spatial tables include node zero and reset the initial cursor on checkpoint selection", async ({
  page,
}) => {
  const witness = await mock(page, { spatialWitness: true });
  await page.goto(`/runs/${runId}?project=${projectId}&view=dynamics`);
  await page.getByRole("button", { name: "空间基底", exact: true }).click();
  const panel = page.getByRole("region", { name: "因果空间基底", exact: true });
  await expect(panel.locator(".spatial-history tbody tr")).toHaveCount(2);
  await expect(
    panel.locator(".spatial-history tbody tr").first().locator("td").first(),
  ).toHaveText("0");
  await panel
    .getByLabel("空间检查点", { exact: true })
    .selectOption("checkpoint-2");
  await expect(panel.locator(".spatial-history tbody tr")).toHaveCount(2);
  await expect
    .poll(
      () =>
        witness.requests.filter((request) => request.path.includes("/spatial?"))
          .length,
    )
    .toBeGreaterThanOrEqual(2);
  for (const request of witness.requests.filter((row) =>
    row.path.includes("/spatial?"),
  ))
    expect(
      new URL(request.path, "http://example.invalid").searchParams.get(
        "node_after",
      ),
    ).toBe("-1");
  expect(
    witness.requests.filter((request) => request.method !== "GET"),
  ).toEqual([]);
  expect(witness.errors).toEqual([]);
});

async function mock(
  page: Page,
  options: {
    projectFail?: boolean;
    user?: any;
    projectRows?: any[];
    login?: boolean;
    setup?: boolean;
    runningRows?: any[];
    runningPage2?: any[];
    pauseFail?: boolean;
    pauseConfirmFailOnce?: boolean;
    providerRows?: any[];
    graphData?: any;
    inspectedNodes?: any[];
    spatialWitness?: boolean;
  } = {},
) {
  const requests: { method: string; path: string; body: any }[] = [];
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let signed = !options.login;
  let pauseAccepted = false,
    confirmationFailed = false;
  let callCancelled = false;
  let user = options.user || {
    id: local,
    username: "local",
    superadmin: true,
    roles: [
      {
        id: "role-super",
        key: "superadmin",
        name: "超级管理员",
        builtin: true,
      },
    ],
    permissions: [],
    csrf: "mock-csrf",
  };
  let roleRows: any[] = [
    {
      id: "role-super",
      key: "superadmin",
      name: "超级管理员",
      builtin: true,
      revision: 1,
      permissions: [],
    },
    {
      id: "role-user",
      key: "user",
      name: "普通用户",
      builtin: true,
      revision: 1,
      permissions: [],
    },
  ];
  await page.context().route("**/api/v2/**", async (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      path = url.pathname.replace("/api/v2", "");
    let body: any = null;
    try {
      body = request.postDataJSON();
    } catch {}
    requests.push({ method: request.method(), path: path + url.search, body });
    const reply = (data: any, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(data),
      });
    if (path === "/session")
      return signed
        ? reply({ user, mode: "workstation", backend: "python" })
        : reply({ detail: "Login required" }, 401);
    if (path === "/logout") {
      signed = false;
      return reply({ ok: true });
    }
    if (path === "/session/running-instances")
      return reply({
        items:
          url.searchParams.get("offset") === "200"
            ? options.runningPage2 || []
            : options.runningRows || [],
        next:
          options.runningPage2 && url.searchParams.get("offset") === "0"
            ? 200
            : null,
      });
    if (path.endsWith("/commands")) {
      pauseAccepted = !options.pauseFail;
      return options.pauseFail
        ? reply({ detail: "Synthetic pause refusal" }, 409)
        : reply({ accepted: true });
    }
    if (path === "/auth/setup/status")
      return reply({
        required: !!options.setup,
        username: "local",
        user_id: local,
      });
    if (path === "/login" || path === "/auth/setup") {
      signed = true;
      return reply({ user, csrf: "mock-csrf" });
    }
    if (path === "/projects")
      return options.projectFail
        ? reply({ detail: "Synthetic project list failure" }, 503)
        : reply(options.projectRows ?? projects);
    if (path.match(/^\/projects\/[^/]+$/))
      return reply(
        projects.find((p) => p.id === path.split("/")[2]) || projects[0],
      );
    if (path === "/configuration") return reply(catalogue);
    if (path === "/study-configuration")
      return reply(catalogue.study_catalogue);
    if (path === "/studies/validate")
      return reply({ valid: true, protocol: body, errors: [], warnings: [] });
    if (path.endsWith("/configuration/validate"))
      return reply({
        valid: true,
        spec: body.spec,
        errors: [],
        adjustments: [],
      });
    if (path === "/configuration/defaults") {
      const selectedKernel =
        url.searchParams.get("kernel_id") || catalogue.defaults.kernel_id;
      const spec = {
        ...catalogue.defaults,
        kernel_id: selectedKernel,
        config: catalogue.kernel_defaults[selectedKernel],
      };
      return reply({
        spec,
        factory: spec,
        revision: 0,
        source: "factory",
      });
    }
    if (/^\/projects\/[^/]+\/configuration\/defaults$/.test(path))
      return reply({
        spec: { ...catalogue.defaults, duration_s: 19 },
        revision: 5,
      });
    if (path === "/configuration/templates" && request.method() === "POST")
      return reply(
        { id: "saved-template", name: body.name, spec: body.spec, revision: 1 },
        201,
      );
    if (path.endsWith("/configuration-template"))
      return reply(
        {
          id: "instance-template",
          name: body.name,
          spec: catalogue.defaults,
          revision: 1,
        },
        201,
      );
    if (path === "/configuration/templates")
      return reply({
        items: [
          {
            id: "template-1",
            name: "Stored template",
            kernel_id: catalogue.defaults.kernel_id,
            revision: 1,
            spec: catalogue.defaults,
          },
          {
            id: "template-4",
            name: "Local memory template",
            kernel_id: "threemind.continuous-memory/4",
            revision: 2,
            spec: {
              ...catalogue.defaults,
              kernel_id: "threemind.continuous-memory/4",
              duration_s: 7,
              config:
                catalogue.kernel_defaults["threemind.continuous-memory/4"],
            },
          },
        ],
      });
    if (path === "/ai/providers")
      return reply({
        providers: options.providerRows ?? [],
        secrets_ready: true,
        mode: "workstation",
      });
    if (path === "/admin/ai/providers")
      return reply({
        providers: options.providerRows ?? [],
        grants: [],
        projects: projects,
        secrets_ready: true,
      });
    if (path === `/ai/providers/${providerId}/test`)
      return reply({ id: callId }, 202);
    if (path === "/ai/calls")
      return reply({
        items: [
          {
            id: callId,
            purpose: "provider_test",
            status: "queued",
            ordinal: 1,
            provider_name: provider().config.name,
            model: "mock-text",
            created_at: "2026-10-11",
          },
        ],
        next: null,
      });
    if (path.startsWith(`/ai/calls/${callId}`)) {
      const row = {
        id: callId,
        purpose: "provider_test",
        status: "queued",
        provider_id: providerId,
        provider_config: provider().config,
        provider_revision: 1,
        created_at: "2026-10-11",
        prompt: { system: "Mock diagnostic", user: "Connectivity witness" },
        evidence: [],
        cancel_requested: callCancelled,
        response_text: "",
        usage: null,
        job_status: "queued",
      };
      if (path.endsWith("/cancel")) {
        callCancelled = true;
        return reply({ ...row, cancel_requested: true });
      }
      if (path.endsWith("/export"))
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          headers: {
            "Content-Disposition": `attachment; filename="ai-call-${callId}.json"`,
          },
          body: JSON.stringify({ schema: "threemind.ai-call/2", call: row }),
        });
      return reply(row);
    }
    if (path === "/services/notifications")
      return reply({
        items: [],
        defaults: { transport: "smtp", enabled: true },
        schema: {},
      });
    if (path === "/notifications/unread") return reply({ unread: 3 });
    if (path === "/notifications") return reply({ items: [], next: null });
    if (path === "/admin/execution")
      return reply({
        global: { limits: { runtime: 2, ai: 2, notification: 1 }, revision: 0 },
        history: [],
        queues: [],
        active: {},
        workers: [],
      });
    if (path === "/admin/execution/projects")
      return reply({ rows: [], more: false });
    if (path.startsWith("/browse/location/"))
      return reply({ project_id: projectId, kind: "run", id: runId });
    if (path === "/browse/resources") {
      const kind = url.searchParams.get("kinds");
      return reply({
        rows:
          kind === "run"
            ? [
                {
                  id: runId,
                  kind: "run",
                  title: run().name,
                  project_id: projectId,
                  project_name: "Research A",
                  details: {
                    kernel: catalogue.defaults.kernel_id,
                    time_us: "0",
                    revision: 0,
                  },
                  status: "paused",
                  updated_at: "2026-10-11",
                },
              ]
            : [],
        total: kind === "run" ? 1 : 0,
        more: false,
      });
    }
    if (path.endsWith("/runs") && request.method() === "POST")
      return reply({ ...run(), name: body.name, spec: body.spec });
    if (
      path.endsWith("/artifacts") ||
      path.endsWith("/jobs") ||
      path.endsWith("/runs")
    )
      return reply([]);
    if (/\/runs\/[^/]+$/.test(path)) {
      if (
        pauseAccepted &&
        options.pauseConfirmFailOnce &&
        !confirmationFailed
      ) {
        confirmationFailed = true;
        return reply({ detail: "Synthetic pause confirmation outage" }, 503);
      }
      return reply(
        options.spatialWitness
          ? {
              ...run(),
              revision: 1,
              spec: {
                ...catalogue.defaults,
                kernel_id: "threemind.continuous-memory/4",
                config: {
                  ...catalogue.defaults.config,
                  spatial_embedding: true,
                },
              },
            }
          : run(),
      );
    }
    if (options.spatialWitness && path.endsWith("/checkpoint-history"))
      return reply({
        rows: [1, 2].map((revision) => ({
          id: `checkpoint-${revision}`,
          revision,
          time_us: String(revision * 10000),
          state_hash: `spatial-hash-${revision}`,
        })),
        more: false,
        next: null,
      });
    if (
      options.spatialWitness &&
      (path.endsWith("/spatial") || path.endsWith("/spatial/graph"))
    ) {
      const graph = path.endsWith("/graph");
      const nodes = [0, 1].map((id) => ({
        id,
        channel: id + 1,
        activation: 0.6,
        position: [id * 0.2, 0.1, 0.3],
        cluster: id,
      }));
      return reply({
        checkpoint_id: url.searchParams.get("checkpoint_id"),
        revision: 1,
        time_us: "10000",
        state_time_us: "10000",
        state_hash: "spatial-hash-1",
        supported: true,
        dynamics: "threemind.continuous-memory/4",
        total_nodes: 2,
        total_edges: 0,
        summary: {
          seed: 20260724,
          coordinate_rule: "threemind.sha256-id-axis/1",
          parameters: {
            spatial_embedding: true,
            spatial_dimensions: 3,
            neighborhood_enabled: true,
            spatial_radius: 2.5,
            spatial_competition_rate: 0,
          },
          neighbor_edges: 0,
          clusters: 2,
          isolated_nodes: 2,
        },
        nodes: graph
          ? nodes
          : nodes.filter(
              (n) => n.id > Number(url.searchParams.get("node_after")),
            ),
        edges: [],
        nodes_more: false,
        edges_more: false,
        nodes_next: 1,
        edges_next: 0,
        node_count: 2,
        edge_count: 0,
        shown_nodes: 2,
        shown_edges: 0,
        coordinates: "causal",
        complete: true,
      });
    }
    if (path.endsWith("/checkpoints")) return reply([]);
    if (path.endsWith("/conversation"))
      return reply({
        rows: [],
        more: false,
        next: null,
        ceiling: "0",
        direction: "older",
      });
    if (path.endsWith("/sensory"))
      return reply({
        media_capabilities: { images: true, video_codecs: true },
      });
    if (path.includes("/media-uploads"))
      return reply({
        rows: [],
        items: [],
        more: false,
        next: null,
        limits: {
          project_active_uploads: 0,
          project_active_limit: 10,
          project_staged_bytes: 1000000,
        },
      });
    if (path.endsWith("/graph"))
      return reply(
        options.graphData || {
          revision: 0,
          time_us: "0",
          nodes: [],
          edges: [],
          node_count: 0,
          edge_count: 0,
          shown_nodes: 0,
          shown_edges: 0,
          complete: true,
          coordinates: "causal",
          delta: false,
        },
      );
    if (path.endsWith("/data/nodes"))
      return reply({
        rows: options.inspectedNodes || [],
        revision: 1,
        more: false,
      });
    if (path.endsWith("/data/edges"))
      return reply({ rows: [], revision: 1, more: false });
    if (path.endsWith("/data-exports")) return reply({ accepted: true }, 202);
    if (path === "/accounts/users")
      return reply({ users: [{ ...user, enabled: true }] });
    if (path === "/accounts/roles") {
      if (request.method() === "POST") {
        roleRows.push({
          ...body,
          id: "custom-role",
          revision: 1,
          builtin: false,
        });
        return reply(roleRows.at(-1));
      }
      return reply({ roles: roleRows });
    }
    if (path === "/permissions/catalog")
      return reply({
        scopes: [
          { id: "platform", title: "平台" },
          { id: "member_projects", title: "成员项目" },
        ],
        actions: [
          {
            id: "menu.overview",
            title: "意识工作台",
            category: "菜单",
            scopes: ["platform"],
          },
          {
            id: "runs.read",
            title: "查看意识",
            category: "意识",
            scopes: ["member_projects"],
          },
          {
            id: "runs.resume",
            title: "启动与继续",
            category: "意识",
            scopes: ["member_projects"],
          },
        ],
      });
    return reply({ rows: [], items: [], more: false });
  });
  return { requests, errors };
}
test("historical graph click queries the exact string ID and displays original fields and channel aliases without writes", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (
      kind: string,
      ...args: any[]
    ) {
      if (kind.startsWith("webgl")) return null;
      return original.apply(this, [kind, ...args] as any);
    } as any;
  });
  const node = {
    id: "9007199254740993",
    channel: "18446744073709551615",
    activation: 0.5,
    direct_touch: 0.4,
    direct: 0.4,
    associative_touch: 0.1,
    associative: 0.1,
    touch_count: 3,
    touches: 3,
    plasticity: 0.8,
    local_plasticity: 0.8,
  };
  const witness = await mock(page, {
    inspectedNodes: [node],
    graphData: {
      revision: 1,
      time_us: "100000",
      nodes: [node],
      edges: [],
      total_nodes: 1,
      total_edges: 0,
      shown_nodes: 1,
      shown_edges: 0,
      complete: true,
      coordinates: "display",
    },
  });
  await page.goto(`/runs/${runId}?project=${projectId}`);
  await expect(page.locator(".graph-footer")).toContainText("1 节点");
  const canvas = page.locator(".graph-webgl-canvas"),
    box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  await canvas.click({
    position: { x: box!.width / 2, y: box!.height / 2 + 24 },
  });
  await expect(page.locator(".inspected-id")).toContainText(node.id);
  const fields = page.locator(".inspector-section dl");
  await expect(
    fields
      .locator("div")
      .filter({ has: page.locator("dt", { hasText: /^channel$/ }) }),
  ).toContainText(node.channel);
  for (const key of [
    "direct_touch",
    "direct",
    "associative_touch",
    "associative",
    "touch_count",
    "touches",
    "plasticity",
    "local_plasticity",
  ])
    await expect(
      fields.locator("dt", { hasText: new RegExp(`^${key}$`) }),
    ).toBeVisible();
  const request = witness.requests.find((row) =>
    row.path.includes("/data/nodes?node_id="),
  );
  expect(
    new URL(`http://mock${request?.path}`).searchParams.get("node_id"),
  ).toBe(node.id);
  expect(witness.requests.filter((row) => row.method !== "GET")).toEqual([]);
  expect(witness.errors).toEqual([]);
});

test("data queries and exports preserve historical string sources and unsigned 64-bit IDs", async ({
  page,
}) => {
  const witness = await mock(page);
  await page.goto(`/data?project=${projectId}&run=${runId}`);
  await page
    .getByRole("combobox", { name: "数据类型", exact: true })
    .selectOption("edges");
  const source = page.getByRole("textbox", {
    name: "源节点 ID（可选）",
    exact: true,
  });
  for (const value of ["18446744073709551615", "字/符&号"]) {
    await source.fill(value);
    await expect
      .poll(() =>
        witness.requests.some(
          (row) =>
            row.path.includes("/data/edges?") &&
            new URL(`http://mock${row.path}`).searchParams.get("source") ===
              value,
        ),
      )
      .toBe(true);
    for (const format of ["csv", "jsonl", "parquet"]) {
      await page
        .getByRole("combobox", { name: "筛选导出格式", exact: true })
        .selectOption(format);
      await page
        .getByRole("button", { name: "导出全部匹配结果", exact: true })
        .click();
      await expect
        .poll(
          () =>
            witness.requests.filter(
              (row) =>
                row.path.endsWith("/data-exports") &&
                row.body?.source === value &&
                row.body?.format === format,
            ).length,
        )
        .toBe(1);
    }
  }
  expect(witness.errors).toEqual([]);
});

test("member-scoped service reader sees only authorized catalogue without platform diagnostics", async ({
  page,
}) => {
  const witness = await mock(page, {
    providerRows: [provider()],
    user: {
      id: "service-reader",
      username: "reader",
      superadmin: false,
      roles: [],
      csrf: "mock",
      permissions: [
        { action: "menu.settings", scope: "platform" },
        { action: "services.read", scope: "member_projects" },
        { action: "services.use", scope: "member_projects" },
        { action: "projects.read", scope: "member_projects" },
      ],
    },
  });
  await page.goto("/settings?section=providers");
  await expect(
    page.getByRole("heading", { name: "Authorized text service", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "连接测试", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "请求记录", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "编辑", exact: true }),
  ).toHaveCount(0);
  expect(witness.requests.some((r) => r.path === "/ai/providers")).toBe(true);
  expect(witness.requests.some((r) => r.path.startsWith("/admin/ai"))).toBe(
    false,
  );
  expect(witness.requests.filter((r) => r.method !== "GET")).toEqual([]);
  assertRegisteredAIRequests(witness.requests);
  expect(witness.errors).toEqual([]);
});
test("platform diagnostic test, history, detail, status, cancel and export use registered public routes without a project", async ({
  page,
}, info) => {
  const witness = await mock(page, {
    projectRows: [],
    providerRows: [provider(true)],
    user: {
      id: "diagnostician",
      username: "diagnostician",
      superadmin: false,
      roles: [],
      csrf: "mock",
      permissions: [
        { action: "menu.settings", scope: "platform" },
        { action: "services.read", scope: "platform" },
        { action: "services.use", scope: "platform" },
      ],
    },
  });
  await page.goto("/settings?section=providers");
  await page.getByRole("button", { name: "连接测试", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("真实文本请求");
  await page.getByRole("button", { name: "发送测试请求", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Mock diagnostic");
  await page.getByRole("button", { name: "取消请求", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "取消中…", exact: true }),
  ).toBeDisabled();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "导出请求记录", exact: true }).click();
  expect((await download).suggestedFilename()).toBe(`ai-call-${callId}.json`);
  await page.getByRole("button", { name: "关闭详情", exact: true }).click();
  await page.getByRole("button", { name: "请求记录", exact: true }).click();
  await page.getByRole("button", { name: "查看请求", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Mock diagnostic");
  await page.screenshot({
    path: info.outputPath("platform-ai-diagnostic.png"),
    fullPage: true,
  });
  for (const path of [
    "/ai/providers",
    `/ai/providers/${providerId}/test`,
    "/ai/calls?limit=25",
    `/ai/calls/${callId}`,
    `/ai/calls/${callId}/status`,
    `/ai/calls/${callId}/cancel`,
    `/ai/calls/${callId}/export`,
  ])
    expect(
      witness.requests.some((r) => r.path === path),
      path,
    ).toBe(true);
  expect(witness.requests.some((r) => r.path.startsWith("/projects/"))).toBe(
    false,
  );
  assertRegisteredAIRequests(witness.requests);
  expect(witness.errors).toEqual([]);
});
test("server diagnostic denial is respected; English service catalogue remains usable at 390px", async ({
  page,
}, info) => {
  await page.addInitScript(() =>
    localStorage.setItem("tm2.preferences", JSON.stringify({ locale: "en" })),
  );
  const witness = await mock(page, {
    projectRows: [],
    providerRows: [provider(false)],
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/settings?section=providers");
  await expect(
    page.getByRole("heading", { name: "Authorized text service", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Connection test", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Request history", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("services-mobile-en.png"),
    fullPage: true,
  });
  expect(witness.requests.filter((r) => r.method !== "GET")).toEqual([]);
  assertRegisteredAIRequests(witness.requests);
  expect(witness.errors).toEqual([]);
});
test("logout paginates independent instances and preserves the exact accepted pause payload", async ({
  page,
}) => {
  const other = "66666666-6666-4666-8666-666666666666";
  const payload = { kind: "pause", payload: {}, expected_revision: 4 };
  const witness = await mock(page, {
    runningRows: [
      {
        id: runId,
        name: "First page",
        project_id: projectId,
        status: "running",
        can_pause: true,
      },
    ],
    runningPage2: [
      {
        id: other,
        name: "Second page",
        project_id: projectId,
        status: "running",
        can_pause: true,
        pause_payload: payload,
      },
    ],
  });
  await page.goto("/");
  await page.getByLabel("退出登录", { exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("button", { name: "查看更多实例", exact: true })
    .click();
  await expect(dialog.getByRole("checkbox")).toHaveCount(2);
  await dialog.getByRole("checkbox").nth(1).check();
  await dialog
    .getByRole("button", { name: "暂停 1 个实例后退出", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "登录 ThreeMind", exact: true }),
  ).toBeVisible();
  const commands = witness.requests.filter(
    (r) => r.method === "POST" && r.path.endsWith("/commands"),
  );
  expect(commands).toHaveLength(1);
  expect(commands[0].path).toBe(
    `/projects/${projectId}/runs/${other}/commands`,
  );
  expect(commands[0].body).toEqual(payload);
  expect(
    witness.requests.some(
      (r) => r.path === "/session/running-instances?limit=200&offset=200",
    ),
  ).toBe(true);
  expect(witness.errors).toEqual([]);
});
test("zero-project and failed project query do not block system or workbench", async ({
  page,
}) => {
  const witness = await mock(page, { projectFail: true, projectRows: [] });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "意识工作台", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "浏览范围", exact: true }),
  ).toHaveCount(0);
  for (const section of [
    "display",
    "providers",
    "templates",
    "notifications",
  ]) {
    await page.goto(`/settings?section=${section}`);
    await expect(
      page.getByRole("heading", { name: "系统设置", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("combobox", { name: "所属项目", exact: true }),
    ).toHaveCount(0);
  }
  await expect(page.getByLabel("查看通知，3 条未读")).toBeVisible();
  expect(witness.requests.filter((r) => r.method !== "GET")).toEqual([]);
  expect(witness.errors).toEqual([]);
});
test("new draft precedes destination and defaults to prepared creation", async ({
  page,
}) => {
  const witness = await mock(page);
  await page.goto("/");
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建意识", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("所属项目", { exact: true })).toHaveValue("");
  await dialog.getByLabel("意识名称", { exact: true }).fill("Prepared draft");
  const duration = dialog.getByLabel("运行时长（模拟秒）", { exact: true });
  await duration.fill("42");
  await dialog
    .getByLabel("所属项目", { exact: true })
    .selectOption(projects[1].id);
  await expect(duration).toHaveValue("42");
  await expect(dialog.getByLabel("创建后立即启动")).not.toBeChecked();
  await dialog.getByRole("button", { name: "创建并准备", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/runs/${runId}`));
  const create = witness.requests.find(
    (r) => r.method === "POST" && r.path === `/projects/${projects[1].id}/runs`,
  )!;
  expect(create.body.start_immediately).toBe(false);
  expect(create.body.spec.duration_s).toBe(42);
  expect(
    witness.requests.some(
      (r) =>
        r.path.includes("/configuration/defaults") &&
        r.path.startsWith("/projects"),
    ),
  ).toBe(false);
  expect(witness.errors).toEqual([]);
});
test("prepared configuration save carries both state and metadata revisions", async ({
  page,
}) => {
  const witness = await mock(page);
  await page.goto(`/runs/${runId}?project=${projectId}`);
  await page.getByRole("button", { name: "参数配置", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("textbox", { name: "意识名称", exact: true })
    .fill("Edited prepared name");
  await dialog.getByRole("button", { name: "保存配置", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  const save = witness.requests.find(
    (r) =>
      r.method === "PUT" &&
      r.path === `/projects/${projectId}/runs/${runId}/configuration`,
  );
  expect(save?.body.expected_revision).toBe(0);
  expect(save?.body.expected_metadata_revision).toBe(7);
  expect(save?.body.name).toBe("Edited prepared name");
  expect(witness.requests.some((r) => r.path.endsWith("/commands"))).toBe(
    false,
  );
  expect(witness.errors).toEqual([]);
});

test("creation hierarchy separates kernel versions and matching templates without carrying another kernel draft", async ({
  page,
}) => {
  const witness = await mock(page);
  await page.goto("/");
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建意识", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "创建意识", exact: true });
  const kernel = dialog.getByLabel("内核版本", { exact: true });
  await expect(kernel).toHaveValue(catalogue.defaults.kernel_id);
  await expect(kernel).toHaveValue("threemind.continuous-memory/5.3");
  for (const version of ["5.2", "5.3"]) {
    await expect(kernel.locator(`option[value='threemind.continuous-memory/${version}']`))
      .toContainText(`continuous-memory/${version}`);
  }
  await expect(
    kernel.locator("option[value='threemind.continuous-memory/4']"),
  ).toContainText("continuous-memory/4");
  await expect(
    kernel.locator("option[value='threemind.continuous-memory/3.1']"),
  ).toContainText("continuous-memory/3.1");
  await expect(dialog.getByLabel("意识内核", { exact: true })).toHaveCount(0);
  await expect(dialog.getByLabel("配置模板", { exact: true })).toHaveValue(
    "system",
  );
  await expect(
    dialog
      .getByLabel("配置模板", { exact: true })
      .locator("option[value='template-4']"),
  ).toHaveCount(0);
  const duration = dialog.getByLabel("运行时长（模拟秒）", { exact: true });
  await duration.fill("42");
  await kernel.selectOption("threemind.continuous-memory/4");
  await page
    .getByRole("dialog", { name: "替换当前参数？", exact: true })
    .getByRole("button", { name: "取消", exact: true })
    .click();
  await expect(kernel).toHaveValue(catalogue.defaults.kernel_id);
  await expect(duration).toHaveValue("42");
  await kernel.selectOption("threemind.continuous-memory/4");
  await page
    .getByRole("dialog", { name: "替换当前参数？", exact: true })
    .getByRole("button", { name: "替换参数", exact: true })
    .click();
  await expect(kernel).toHaveValue("threemind.continuous-memory/4");
  await expect(duration).toHaveValue("");
  await expect(
    dialog
      .getByLabel("配置模板", { exact: true })
      .locator("option[value='template-1']"),
  ).toHaveCount(0);
  await dialog
    .getByLabel("配置模板", { exact: true })
    .selectOption("template-4");
  await expect(duration).toHaveValue("7");
  await dialog.getByLabel("所属项目", { exact: true }).selectOption(projectId);
  await dialog.getByRole("button", { name: "创建并准备", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/runs/${runId}`));
  const created = witness.requests.find(
    (row) =>
      row.method === "POST" && row.path === `/projects/${projectId}/runs`,
  )!;
  expect(created.body.spec.kernel_id).toBe("threemind.continuous-memory/4");
  expect(created.body.spec.duration_s).toBe(7);
  expect(created.body.creation_source).toEqual({
    kind: "template",
    id: "template-4",
    revision: 2,
  });
  expect(witness.errors).toEqual([]);
});

for (const [version, curve] of [["5.2", "exponential"], ["5.3", "inverse-logarithmic"]]) {
  test(`memory${version} exposes its decay choices and preserves an explicit alternative`, async ({ page }) => {
    const witness = await mock(page);
    await page.goto("/");
    await page.getByRole("banner").getByRole("button", { name: "新建意识", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "创建意识", exact: true });
    await dialog.getByLabel("内核版本", { exact: true }).selectOption(`threemind.continuous-memory/${version}`);
    await dialog.locator(".configuration-advanced > summary").click();
    await dialog.getByLabel("搜索高级参数", { exact: true }).fill("衰减机制");
    const decay = dialog.getByLabel("衰减机制", { exact: true });
    await expect(decay).toHaveValue(curve);
    for (const value of ["exponential", "power-law", "inverse-logarithmic"]) {
      await expect(decay.locator(`option[value='${value}']`)).toHaveCount(1);
    }
    await expect(decay.locator("option[value='power-exponential']")).toHaveCount(version === "5.3" ? 1 : 0);
    await decay.selectOption("power-law");
    await dialog.getByLabel("所属项目", { exact: true }).selectOption(projectId);
    await dialog.getByRole("button", { name: "创建并准备", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/runs/${runId}`));
    const created = witness.requests.find(row => row.method === "POST" && row.path === `/projects/${projectId}/runs`)!;
    expect(created.body.spec.kernel_id).toBe(`threemind.continuous-memory/${version}`);
    expect(created.body.spec.config.decay_curve).toBe("power-law");
    expect(witness.errors).toEqual([]);
  });
}

test("memory3.1 creation preserves its version and uses its own configuration source", async ({
  page,
}) => {
  const witness = await mock(page);
  await page.goto("/");
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建意识", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "创建意识", exact: true });
  await dialog
    .getByLabel("内核版本", { exact: true })
    .selectOption("threemind.continuous-memory/3.1");
  await expect(dialog.getByLabel("配置模板", { exact: true })).toHaveValue(
    "system",
  );
  await expect(
    dialog
      .getByLabel("配置模板", { exact: true })
      .locator("option[value='template-1']"),
  ).toHaveCount(0);
  await dialog.getByLabel("所属项目", { exact: true }).selectOption(projectId);
  await dialog.getByRole("button", { name: "创建并准备", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/runs/${runId}`));
  const created = witness.requests.find(
    (row) =>
      row.method === "POST" && row.path === `/projects/${projectId}/runs`,
  )!;
  expect(created.body.spec.kernel_id).toBe("threemind.continuous-memory/3.1");
  expect(created.body.creation_source.kernel_id).toBe(
    "threemind.continuous-memory/3.1",
  );
  expect(created.body.spec.config.consolidation_mode).toBe(
    "adaptive-half-life",
  );
  expect(witness.errors).toEqual([]);
});

for (const version of ["5", "5.1"]) {
  for (const width of [1440, 390]) {
    test(`memory${version} creation keeps version, default reception and explicit research options at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 1000 });
      const witness = await mock(page);
      await page.goto("/");
      await page.getByRole("banner").getByRole("button", { name: "新建意识", exact: true }).click();
      const dialog = page.getByRole("dialog", { name: "创建意识", exact: true });
      const kernel = dialog.getByLabel("内核版本", { exact: true });
      await expect(kernel.locator('option[value="threemind.continuous-memory/2"]')).toContainText("continuous-memory/2");
      await expect(kernel.locator(`option[value="threemind.continuous-memory/${version}"]`)).toContainText(`continuous-memory/${version}`);
      await kernel.selectOption(`threemind.continuous-memory/${version}`);
      await expect(dialog.getByLabel("配置模板", { exact: true })).toHaveValue("system");
      await dialog.locator("details.configuration-advanced > summary").click();
      await expect(dialog.getByLabel("接收规则", { exact: true })).toHaveValue("legacy-source");
      await expect(dialog.getByLabel("到达整合方式", { exact: true })).toHaveValue("sequential");
      await expect(dialog.getByLabel("传播相位", { exact: true })).toHaveValue("aligned");
      await expect(dialog.locator('[data-parameter="config.reception_mode"] .parameter-meta')).toContainText("默认 legacy-source");
      await expect(dialog.locator('[data-parameter="config.arrival_mode"] .parameter-meta')).toContainText("默认 sequential");
      await expect(dialog.locator('[data-parameter="config.arrival_mode"]')).toContainText("可能改变新颖量及直接学习冲量");
      await expect(dialog.getByLabel("接收规则", { exact: true }).locator('option[value="unified"]')).toContainText("研究选项");
      await dialog.getByLabel("所属项目", { exact: true }).selectOption(projectId);
      await dialog.getByRole("button", { name: "创建并准备", exact: true }).click();
      await expect(page).toHaveURL(new RegExp(`/runs/${runId}`));
      const created = witness.requests.find(row => row.method === "POST" && row.path === `/projects/${projectId}/runs`)!;
      expect(created.body.spec.kernel_id).toBe(`threemind.continuous-memory/${version}`);
      expect(created.body.start_immediately).toBe(false);
      expect(created.body.spec.config.reception_mode).toBe("legacy-source");
      expect(created.body.spec.config.arrival_mode).toBe("sequential");
      expect(witness.errors).toEqual([]);
    });
  }
}

test("switching to another kernel's default updates immutable provenance", async ({
  page,
}) => {
  const witness = await mock(page);
  await page.goto("/");
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建意识", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "创建意识", exact: true });
  await dialog
    .getByLabel("内核版本", { exact: true })
    .selectOption("threemind.continuous-memory/4");
  await expect(
    dialog.getByLabel("运行时长（模拟秒）", { exact: true }),
  ).toHaveValue("");
  await dialog.getByLabel("所属项目", { exact: true }).selectOption(projectId);
  await dialog.getByRole("button", { name: "创建并准备", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/runs/${runId}`));
  const created = witness.requests.find(
    (row) =>
      row.method === "POST" && row.path === `/projects/${projectId}/runs`,
  )!;
  expect(created.body.creation_source).toEqual({
    kind: "factory",
    kernel_id: "threemind.continuous-memory/4",
    revision: 0,
  });
  expect(created.body.spec.config).toEqual(
    catalogue.kernel_defaults["threemind.continuous-memory/4"],
  );
  expect(witness.errors).toEqual([]);
});

test("saving a draft template does not create or start a consciousness", async ({
  page,
}) => {
  const witness = await mock(page);
  await page.goto("/");
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建意识", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "创建意识", exact: true });
  await dialog.getByLabel("运行时长（模拟秒）", { exact: true }).fill("25");
  await dialog
    .getByRole("button", { name: "将当前参数保存为模板", exact: true })
    .click();
  const save = page.getByRole("dialog", {
    name: "将当前参数保存为模板",
    exact: true,
  });
  await save
    .getByLabel("模板名称", { exact: true })
    .fill("Repeated teaching parameters");
  await save.getByRole("button", { name: "保存模板", exact: true }).click();
  await expect(save).toHaveCount(0);
  const written = witness.requests.find(
    (row) => row.method === "POST" && row.path === "/configuration/templates",
  )!;
  expect(written.body.spec.duration_s).toBe(25);
  expect(written.body.spec.kernel_id).toBe(catalogue.defaults.kernel_id);
  expect(
    witness.requests.some(
      (row) =>
        row.method === "POST" && /\/(runs|commands|inputs)$/.test(row.path),
    ),
  ).toBe(false);
  expect(witness.errors).toEqual([]);
});

test("JSON cannot bypass the selected kernel or write an inconsistent creation source", async ({
  page,
}) => {
  const witness = await mock(page);
  await page.goto("/");
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建意识", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "创建意识", exact: true });
  await dialog
    .getByRole("button", { name: "切换到 JSON", exact: true })
    .click();
  await dialog.getByRole("textbox", { name: "JSON 参数", exact: true }).fill(
    JSON.stringify({
      ...catalogue.defaults,
      kernel_id: "threemind.continuous-memory/4",
    }),
  );
  await dialog.getByLabel("所属项目", { exact: true }).selectOption(projectId);
  await dialog.getByRole("button", { name: "创建并准备", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("JSON 不能更换内核");
  expect(
    witness.requests.some(
      (row) =>
        row.method === "POST" && row.path === `/projects/${projectId}/runs`,
    ),
  ).toBe(false);
  expect(witness.errors).toEqual([]);
});

test("a late default response cannot replace the newly selected kernel draft", async ({
  page,
}) => {
  const witness = await mock(page);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(
    "**/api/v2/configuration/defaults?kernel_id=threemind.continuous-memory%2F4",
    async (route) => {
      await gate;
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "factory",
          revision: 0,
          spec: {
            ...catalogue.defaults,
            kernel_id: "threemind.continuous-memory/4",
            config: catalogue.kernel_defaults["threemind.continuous-memory/4"],
          },
        }),
      });
    },
  );
  await page.goto("/");
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建意识", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "创建意识", exact: true });
  const kernel = dialog.getByLabel("内核版本", { exact: true });
  await kernel.selectOption("threemind.continuous-memory/4");
  await kernel.selectOption("threemind.continuous-memory/2");
  await expect(
    dialog.getByLabel("运行时长（模拟秒）", { exact: true }),
  ).toHaveValue("");
  release();
  await expect(kernel).toHaveValue("threemind.continuous-memory/2");
  await dialog.getByLabel("所属项目", { exact: true }).selectOption(projectId);
  await dialog.getByRole("button", { name: "创建并准备", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/runs/${runId}`));
  const created = witness.requests.find(
    (row) =>
      row.method === "POST" && row.path === `/projects/${projectId}/runs`,
  )!;
  expect(created.body.spec.kernel_id).toBe("threemind.continuous-memory/2");
  expect(created.body.creation_source.kernel_id).toBe(
    "threemind.continuous-memory/2",
  );
  expect(witness.errors).toEqual([]);
});

test("instance parameters can become a template without advancing the individual", async ({
  page,
}) => {
  const witness = await mock(page);
  await page.goto(`/runs/${runId}?project=${projectId}`);
  await page
    .getByRole("button", { name: "从此实例参数创建模板", exact: true })
    .click();
  const save = page.getByRole("dialog", {
    name: "从此实例参数创建模板",
    exact: true,
  });
  await save
    .getByLabel("模板名称", { exact: true })
    .fill("Individual parameters");
  await save.getByRole("button", { name: "保存模板", exact: true }).click();
  await expect(save).toHaveCount(0);
  const written = witness.requests.find(
    (row) =>
      row.method === "POST" && row.path.endsWith("/configuration-template"),
  )!;
  expect(written.body).toEqual({
    name: "Individual parameters",
    expected_metadata_revision: 7,
  });
  expect(
    witness.requests.some(
      (row) =>
        row.method === "POST" && /\/(commands|inputs|forks)$/.test(row.path),
    ),
  ).toBe(false);
  expect(witness.errors).toEqual([]);
});

test("a project preset is explicitly selected and cannot switch the kernel", async ({
  page,
}) => {
  const witness = await mock(page);
  await page.goto("/");
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建意识", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "创建意识", exact: true });
  await dialog
    .getByRole("button", { name: "采用项目预设", exact: true })
    .click();
  const picker = page.getByRole("dialog", {
    name: "采用项目预设",
    exact: true,
  });
  await picker
    .getByLabel("预设来源项目", { exact: true })
    .selectOption(projectId);
  await picker
    .getByRole("button", { name: "采用预设参数", exact: true })
    .click();
  await expect(picker).toHaveCount(0);
  await expect(
    dialog.getByLabel("运行时长（模拟秒）", { exact: true }),
  ).toHaveValue("19");
  await expect(dialog.getByLabel("内核版本", { exact: true })).toHaveValue(
    catalogue.defaults.kernel_id,
  );
  await dialog
    .getByLabel("所属项目", { exact: true })
    .selectOption(projects[1].id);
  await dialog.getByRole("button", { name: "创建并准备", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/runs/${runId}`));
  const created = witness.requests.find(
    (row) =>
      row.method === "POST" && row.path === `/projects/${projects[1].id}/runs`,
  )!;
  expect(created.body.creation_source).toEqual({
    kind: "project-preset",
    project_id: projectId,
    revision: 5,
  });
  expect(created.body.spec.duration_s).toBe(19);
  expect(
    witness.requests.filter(
      (row) =>
        row.method === "GET" &&
        row.path.startsWith("/projects/") &&
        row.path.endsWith("/configuration/defaults"),
    ),
  ).toHaveLength(1);
  expect(witness.errors).toEqual([]);
});

test("kernel and template hierarchy remains visible in 390px Chinese and English creation", async ({
  page,
}) => {
  const witness = await mock(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建意识", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "创建意识", exact: true });
  await expect(dialog.getByLabel("内核版本", { exact: true })).toBeVisible();
  await expect(dialog.getByLabel("配置模板", { exact: true })).toBeVisible();
  expect(
    await dialog.evaluate(
      (element) => element.scrollWidth - element.clientWidth,
    ),
  ).toBeLessThanOrEqual(2);
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await page.evaluate(
    (local) =>
      localStorage.setItem(
        `tm2.preferences.user.${local}`,
        JSON.stringify({ locale: "en" }),
      ),
    local,
  );
  await page.reload();
  await page
    .getByRole("banner")
    .getByRole("button", { name: "New consciousness", exact: true })
    .click();
  const english = page.getByRole("dialog", {
    name: "Create consciousness",
    exact: true,
  });
  await expect(
    english.getByLabel("Kernel versions", { exact: true }),
  ).toBeVisible();
  await expect(
    english.getByLabel("Configuration templates", { exact: true }),
  ).toHaveValue("system");
  await expect(
    english.getByRole("button", {
      name: "Save current parameters as a template",
      exact: true,
    }),
  ).toBeVisible();
  expect(
    await english.evaluate(
      (element) => element.scrollWidth - element.clientWidth,
    ),
  ).toBeLessThanOrEqual(2);
  expect(witness.errors).toEqual([]);
});

test("the historical unified kernel is selectable with its reference backend and its own parameters", async ({
  page,
}) => {
  const witness = await mock(page);
  await page.goto("/");
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建意识", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "创建意识", exact: true });
  const kernel = dialog.getByLabel("内核版本", { exact: true });
  await expect(kernel.locator("option")).toHaveCount(catalogue.kernels.length);
  await kernel.selectOption("unified-associative");
  await expect(
    dialog.getByText("此内核使用 Python 实现；不会替换为其他内核版本。", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(dialog.getByLabel("配置模板", { exact: true })).toHaveValue(
    "system",
  );
  await dialog.locator("details.configuration-advanced > summary").click();
  await dialog
    .getByLabel("高级参数分类", { exact: true })
    .selectOption("legacy");
  const encoding = dialog.getByLabel("sensory_encoding", { exact: true });
  await expect(encoding).toHaveValue("anonymous-distributed");
  await expect(dialog.getByLabel("node_payload", { exact: true })).toHaveValue(
    "anonymous",
  );
  await dialog.getByLabel("高级参数分类", { exact: true }).selectOption("all");
  await expect(dialog.getByLabel("连接形成策略", { exact: true })).toHaveValue(
    "local-coactivation",
  );
  await encoding.selectOption("literal-character");
  await dialog.getByLabel("所属项目", { exact: true }).selectOption(projectId);
  await dialog.getByRole("button", { name: "创建并准备", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/runs/${runId}`));
  const created = witness.requests.find(
    (row) =>
      row.method === "POST" && row.path === `/projects/${projectId}/runs`,
  )!;
  expect(created.body.spec.kernel_id).toBe("unified-associative");
  expect(created.body.spec.config.sensory_encoding).toBe("literal-character");
  expect(created.body.execution).toEqual({ backend: "reference" });
  expect(created.body.creation_source).toEqual({
    kind: "factory",
    kernel_id: "unified-associative",
    revision: 0,
  });
  expect(witness.errors).toEqual([]);
});

test("an incompatible project preset cannot replace another kernel's draft", async ({
  page,
}) => {
  const witness = await mock(page);
  await page.goto("/");
  await page
    .getByRole("banner")
    .getByRole("button", { name: "新建意识", exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: "创建意识", exact: true });
  await dialog
    .getByLabel("内核版本", { exact: true })
    .selectOption("threemind.continuous-memory/4");
  await dialog
    .getByRole("button", { name: "采用项目预设", exact: true })
    .click();
  const picker = page.getByRole("dialog", {
    name: "采用项目预设",
    exact: true,
  });
  await picker
    .getByLabel("预设来源项目", { exact: true })
    .selectOption(projectId);
  await expect(
    picker.getByText("项目预设与当前内核不同，不能作为此内核的模板。", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    picker.getByRole("button", { name: "采用预设参数", exact: true }),
  ).toBeDisabled();
  await picker.getByRole("button", { name: "取消", exact: true }).click();
  await expect(dialog.getByLabel("内核版本", { exact: true })).toHaveValue(
    "threemind.continuous-memory/4",
  );
  await expect(
    dialog.getByLabel("运行时长（模拟秒）", { exact: true }),
  ).toHaveValue("");
  expect(witness.requests.filter((row) => row.method !== "GET")).toEqual([]);
  expect(witness.errors).toEqual([]);
});

test("the built graph worker transfers modern IDs and exact historical string IDs without model writes", async ({
  page,
}) => {
  const workerAsset = readdirSync("dist/assets").find((name) =>
    /^graph\.worker-.*\.js$/.test(name),
  );
  expect(workerAsset).toBeTruthy();
  const graphData = {
    revision: 1,
    time_us: "0",
    node_count: 2,
    edge_count: 1,
    shown_nodes: 2,
    shown_edges: 1,
    nodes: [
      { id: 1, activation: 0.5, position: [0, 0, 0] },
      { id: 2, activation: 0.7, position: [0.2, 0.1, 0] },
    ],
    edges: [{ source: 1, target: 2, weight: 0.4 }],
    coordinates: "causal",
    complete: true,
    delta: false,
  };
  const witness = await mock(page, { graphData });
  await page.goto("/");
  const transfer = async () =>
    page.evaluate(
      ({ workerAsset, url }) =>
        new Promise<{ ids: (string | number)[]; numeric: boolean }>(
          (resolve, reject) => {
            const worker = new Worker(`/assets/${workerAsset}`, {
              type: "module",
            });
            const timeout = setTimeout(() => {
              worker.terminate();
              reject(new Error("Graph worker timed out"));
            }, 5000);
            worker.onerror = (event) => {
              clearTimeout(timeout);
              worker.terminate();
              reject(new Error(event.message));
            };
            worker.onmessage = (event) => {
              clearTimeout(timeout);
              worker.terminate();
              if (event.data.type === "error")
                reject(new Error(event.data.message));
              else
                resolve({
                  ids: Array.from(event.data.ids),
                  numeric: event.data.ids instanceof Float64Array,
                });
            };
            worker.postMessage({ url, hidden: false, pollMs: 0 });
          },
        ),
      { workerAsset, url: `/api/v2/projects/${projectId}/runs/${runId}/graph` },
    );
  expect(await transfer()).toEqual({ ids: [1, 2], numeric: true });
  const ids = ["9007199254740993", "18446744073709551615"];
  graphData.nodes.forEach((node, i) => Object.assign(node, { id: ids[i] }));
  Object.assign(graphData.edges[0], { source: ids[0], target: ids[1] });
  expect(await transfer()).toEqual({ ids, numeric: false });
  expect(witness.requests.filter((row) => row.method !== "GET")).toEqual([]);
  expect(witness.errors).toEqual([]);
});
test("open, refresh and upload cancellation have zero instance writes", async ({
  page,
}, info) => {
  const witness = await mock(page);
  await page.goto("/");
  await page.locator(".workbench-recent-item").click();
  await expect(
    page.getByRole("heading", { name: run().name, exact: true }),
  ).toBeVisible();
  await expect(page.locator(".observatory .inspector")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "属性、刺激与读出", exact: true }),
  ).toBeHidden();
  await page.getByLabel("添加媒体刺激").click();
  await page.getByRole("menuitem", { name: "图片", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "关闭", exact: true })
    .click();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: run().name, exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("workbench-readonly.png"),
    fullPage: true,
  });
  expect(witness.requests.filter((r) => r.method !== "GET")).toEqual([]);
  expect(witness.errors).toEqual([]);
});
test("menu capability and precise run commands stay distinct", async ({
  page,
}) => {
  const user = {
    id: "reader",
    username: "reader",
    superadmin: false,
    roles: [],
    permissions: [
      { action: "menu.overview", scope: "platform" },
      { action: "runs.read", scope: "member_projects" },
      { action: "projects.read", scope: "member_projects" },
      { action: "runs.control", scope: "member_projects" },
    ],
    csrf: "reader-csrf",
  };
  const witness = await mock(page, { user });
  await page.goto(`/runs/${runId}?project=${projectId}`);
  await expect(
    page.getByRole("button", { name: "启动", exact: true }),
  ).toBeDisabled();
  await expect(
    page
      .getByRole("banner")
      .getByRole("button", { name: "新建意识", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("link", { name: "用户与权限", exact: true }),
  ).toHaveCount(0);
  await page.goto("/settings?section=providers");
  await expect(
    page.getByRole("heading", { name: "没有此功能的访问权限", exact: true }),
  ).toBeVisible();
  expect(
    witness.requests.filter((r) => r.path === "/admin/ai/providers"),
  ).toEqual([]);
  expect(witness.errors).toEqual([]);
});
test("system configuration readers cannot enter the platform execution monitor or query its queues", async ({
  page,
}) => {
  const witness = await mock(page, {
    user: {
      id: "configuration-reader",
      username: "configuration-reader",
      superadmin: false,
      roles: [],
      permissions: [
        { action: "menu.settings", scope: "platform" },
        { action: "system.read", scope: "platform" },
      ],
      csrf: "reader-csrf",
    },
  });
  await page.goto("/settings?section=defaults");
  await expect(page.getByLabel("内核版本", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "执行队列与额度", exact: true }),
  ).toHaveCount(0);
  await page.goto("/settings?section=execution");
  await expect(
    page.getByRole("heading", { name: "没有此功能的访问权限", exact: true }),
  ).toBeVisible();
  expect(
    witness.requests.filter((row) => row.path.startsWith("/admin/execution")),
  ).toEqual([]);
  expect(witness.errors).toEqual([]);
});

test("project switch filters lists without replacing page capability", async ({
  page,
}) => {
  const witness = await mock(page);
  await page.goto("/notes");
  await expect(
    page.getByRole("button", { name: "新建笔记", exact: true }),
  ).toBeVisible();
  await page.getByLabel("浏览范围", { exact: true }).selectOption(projectId);
  await expect(
    page.getByRole("button", { name: "新建笔记", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByLabel("搜索资料或项目", { exact: true }),
  ).toBeVisible();
  await page.goto(`/notes?project=${projectId}`);
  await expect(
    page.getByLabel("搜索资料或项目", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("浏览范围", { exact: true }).selectOption("");
  await expect(page).not.toHaveURL(/project=/);
  expect(witness.errors).toEqual([]);
});
test("local preferences stay isolated by account; 390px English does not overflow", async ({
  page,
}, info) => {
  await page.addInitScript(
    ({ local }) => {
      localStorage.setItem(
        "tm2.preferences",
        JSON.stringify({
          locale: "en",
          theme: "dark",
          fps: 17,
          preset: "custom",
        }),
      );
    },
    { local },
  );
  const witness = await mock(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Consciousness workbench", exact: true }),
  ).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.goto("/settings?section=display");
  await expect(
    page.getByRole("heading", { name: "System settings", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("settings-mobile-en.png"),
    fullPage: true,
  });
  expect(witness.errors).toEqual([]);
});
test("role editor uses capability scope grants and unified account UI", async ({
  page,
}) => {
  const witness = await mock(page);
  await page.goto("/admin");
  await page.getByRole("button", { name: "角色与权限", exact: true }).click();
  await page.getByRole("button", { name: "新建角色", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("角色名称").fill("Observer role");
  await dialog.getByLabel("角色标识").fill("observer_custom");
  await dialog
    .locator(".permission-action")
    .filter({ hasText: "runs.read" })
    .getByRole("checkbox")
    .check();
  await dialog.getByRole("button", { name: "保存权限", exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "Observer role", exact: true }),
  ).toBeVisible();
  const save = witness.requests.find(
    (r) => r.method === "POST" && r.path === "/accounts/roles",
  )!;
  expect(save.body.permissions).toEqual([
    { action: "runs.read", scope: "member_projects" },
  ]);
  expect(witness.errors).toEqual([]);
});
test("login sends explicit remembered-session preference", async ({ page }) => {
  const witness = await mock(page, { login: true });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "登录 ThreeMind" }),
  ).toBeVisible();
  await page.getByLabel("账号", { exact: true }).fill("local");
  await page.getByLabel("密码", { exact: true }).fill("SyntheticPassword!123");
  await page.getByLabel("记住会话").uncheck();
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "意识工作台", exact: true }),
  ).toBeVisible();
  expect(witness.requests.find((r) => r.path === "/login")!.body.remember).toBe(
    false,
  );
});

test("first setup assigns a password to the existing local identity", async ({
  page,
}) => {
  const witness = await mock(page, { login: true, setup: true });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "首次设置本机账号", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("账号", { exact: true })).toHaveValue("local");
  await page.getByLabel("密码", { exact: true }).fill("SyntheticPassword!123");
  await page
    .getByLabel("确认密码", { exact: true })
    .fill("SyntheticPassword!123");
  await page
    .getByRole("button", { name: "设置密码并进入", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "意识工作台", exact: true }),
  ).toBeVisible();
  expect(
    witness.requests.find((r) => r.path === "/auth/setup")!.body.username,
  ).toBe("local");
  expect(
    witness.requests.some(
      (r) => r.path === "/accounts/users" && r.method === "POST",
    ),
  ).toBe(false);
});
test("another account does not inherit local or another user's browser settings", async ({
  page,
}) => {
  await page.addInitScript(() => {
    localStorage.setItem(
      "tm2.preferences",
      JSON.stringify({ locale: "en", theme: "dark" }),
    );
    localStorage.setItem(
      "tm2.preferences.user.alice",
      JSON.stringify({ locale: "en", theme: "dark" }),
    );
  });
  const alice = await mock(page, {
    user: {
      id: "alice",
      username: "alice",
      superadmin: true,
      roles: [],
      permissions: [],
    },
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Consciousness workbench", exact: true }),
  ).toBeVisible();
  await page.context().unroute("**/api/v2/**");
  const bob = await mock(page, {
    user: {
      id: "bob",
      username: "bob",
      superadmin: true,
      roles: [],
      permissions: [],
    },
  });
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "意识工作台", exact: true }),
  ).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  expect(
    [...alice.requests, ...bob.requests].some(
      (r) => r.path === "/account/preferences",
    ),
  ).toBe(false);
});
test("formal note/report drafts can be edited before a project exists, and cancelled without writes", async ({
  page,
}) => {
  const witness = await mock(page, { projectRows: [] });
  for (const [path, button] of [
    ["/notes", "新建笔记"],
    ["/reports", "编写记录或报告"],
  ]) {
    await page.goto(path);
    await page.getByRole("button", { name: button, exact: true }).click();
    const dialog = page.getByRole("dialog");
    await dialog
      .getByLabel("标题", { exact: true })
      .fill("Unassigned research draft");
    await dialog
      .getByLabel("Markdown 正文", { exact: true })
      .fill("Preserve the draft before selecting a destination.");
    await expect(
      dialog.getByRole("button", { name: "保存并继续编辑", exact: true }),
    ).toBeDisabled();
    await dialog.getByRole("button", { name: "取消", exact: true }).click();
  }
  expect(witness.requests.filter((r) => r.method !== "GET")).toEqual([]);
  expect(witness.errors).toEqual([]);
});
test("project tools have a stable object route and changing tabs does not change resource menus", async ({
  page,
}) => {
  const witness = await mock(page);
  await page.goto(`/projects/${projectId}/tools/models?view=artifacts`);
  await expect(
    page.getByRole("button", { name: "实验快照", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "实验快照", exact: true }).click();
  await expect(page).toHaveURL(
    new RegExp(`/projects/${projectId}/tools/models\\?view=bundles`),
  );
  await page.getByRole("link", { name: "意识档案与模型", exact: true }).click();
  await expect(page).toHaveURL(/\/models$/);
  await expect(
    page.getByLabel("搜索资料或项目", { exact: true }),
  ).toBeVisible();
  expect(witness.requests.filter((r) => r.method !== "GET")).toEqual([]);
  expect(witness.errors).toEqual([]);
});
test("logout defaults to continued execution and cancellation has no commands", async ({
  page,
}) => {
  const witness = await mock(page, {
    runningRows: [
      {
        id: runId,
        name: "Independent running instance",
        project_id: projectId,
        status: "running",
        can_pause: true,
      },
    ],
  });
  await page.goto("/");
  await page.getByLabel("退出登录", { exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("checkbox")).not.toBeChecked();
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  expect(witness.requests.filter((r) => r.method !== "GET")).toEqual([]);
  await page.getByLabel("退出登录", { exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "退出，意识继续运行", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "登录 ThreeMind", exact: true }),
  ).toBeVisible();
  expect(
    witness.requests.filter((r) => r.method === "POST").map((r) => r.path),
  ).toEqual(["/logout"]);
  expect(witness.errors).toEqual([]);
});
test("explicit selected independent instance pauses before logout; managed ones cannot be selected", async ({
  page,
}) => {
  const witness = await mock(page, {
    runningRows: [
      {
        id: runId,
        name: "Independent running instance",
        project_id: projectId,
        status: "running",
        can_pause: true,
      },
      {
        id: "managed",
        name: "Managed experiment",
        project_id: projectId,
        status: "running",
        can_pause: false,
        reason: "由实验管理",
      },
    ],
  });
  await page.goto("/");
  await page.getByLabel("退出登录", { exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("checkbox").nth(1)).toBeDisabled();
  await dialog.getByRole("checkbox").first().check();
  await dialog
    .getByRole("button", { name: "暂停 1 个实例后退出", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "登录 ThreeMind", exact: true }),
  ).toBeVisible();
  expect(
    witness.requests.filter((r) => r.method === "POST").map((r) => r.path),
  ).toEqual([`/projects/${projectId}/runs/${runId}/commands`, "/logout"]);
  expect(witness.errors).toEqual([]);
});
test("pause refusal preserves the login and shows the failure", async ({
  page,
}) => {
  const witness = await mock(page, {
    pauseFail: true,
    runningRows: [
      {
        id: runId,
        name: "Independent running instance",
        project_id: projectId,
        status: "running",
        can_pause: true,
      },
    ],
  });
  await page.goto("/");
  await page.getByLabel("退出登录", { exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("checkbox").check();
  await dialog
    .getByRole("button", { name: "暂停 1 个实例后退出", exact: true })
    .click();
  await expect(dialog.getByRole("alert")).toContainText(
    "Synthetic pause refusal",
  );
  expect(witness.requests.some((r) => r.path === "/logout")).toBe(false);
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "意识工作台", exact: true }),
  ).toBeVisible();
});
test("new system, account, mail and logout labels render English, including 390px workbench panels", async ({
  page,
}, info) => {
  await page.addInitScript(() =>
    localStorage.setItem("tm2.preferences", JSON.stringify({ locale: "en" })),
  );
  const witness = await mock(page);
  for (const [path, label] of [
    ["/settings?section=providers", "AI providers"],
    ["/settings?section=notifications", "Notifications and email"],
    ["/admin", "Users and permissions"],
  ]) {
    await page.goto(path);
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  }
  await page.goto("/");
  await page.getByLabel("Sign out", { exact: true }).click();
  await expect(
    page.getByRole("button", {
      name: "Log out and keep consciousness running",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Cancel", exact: true })
    .click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/runs/${runId}?project=${projectId}`);
  await expect(
    page.getByRole("button", {
      name: "Properties, stimuli and readouts",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", {
      name: "Properties, stimuli and readouts",
      exact: true,
    })
    .click();
  await expect(page.locator(".observatory .inspector")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("workbench-mobile-en.png"),
    fullPage: true,
  });
  expect(witness.requests.filter((r) => r.method !== "GET")).toEqual([]);
  expect(witness.errors).toEqual([]);
});
test("retrying an accepted pause only checks its result and never sends it twice", async ({
  page,
}) => {
  const witness = await mock(page, {
    pauseConfirmFailOnce: true,
    runningRows: [
      {
        id: runId,
        name: "Independent running instance",
        project_id: projectId,
        status: "running",
        can_pause: true,
      },
    ],
  });
  await page.goto("/");
  await page.getByLabel("退出登录", { exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("checkbox").check();
  await dialog
    .getByRole("button", { name: "暂停 1 个实例后退出", exact: true })
    .click();
  await expect(dialog.getByRole("alert")).toContainText(
    "Synthetic pause confirmation outage",
  );
  await expect(dialog).toContainText(
    "重试只查询这些实例的暂停结果，不重复发送命令",
  );
  await dialog
    .getByRole("button", { name: "暂停 1 个实例后退出", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "登录 ThreeMind", exact: true }),
  ).toBeVisible();
  expect(
    witness.requests.filter(
      (r) => r.method === "POST" && r.path.endsWith("/commands"),
    ),
  ).toHaveLength(1);
  expect(witness.requests.filter((r) => r.path === "/logout")).toHaveLength(1);
});
test("protocol editing and validation precede project selection, while execution still requires it", async ({
  page,
}) => {
  test.skip(
    !catalogue.study_catalogue,
    "Needs the optional source-only study catalogue.",
  );
  const witness = await mock(page, { projectRows: [] });
  await page.goto("/studies");
  await page.getByRole("button", { name: "创建实验", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("combobox", { name: "所属项目", exact: true }),
  ).toHaveValue("");
  await dialog
    .getByRole("button", { name: "切换到协议 JSON", exact: true })
    .click();
  await dialog
    .getByRole("button", { name: "切换到图形设计", exact: true })
    .click();
  await expect(
    dialog.getByRole("button", { name: "冻结协议并运行", exact: true }),
  ).toBeDisabled();
  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  expect(
    witness.requests.filter((r) => r.method !== "GET").map((r) => r.path),
  ).toEqual(["/studies/validate"]);
  expect(witness.errors).toEqual([]);
});
test("390px network and system views remain usable in Chinese and English without project prerequisites", async ({
  page,
}, info) => {
  const witness = await mock(page, { projectRows: [] });
  await page.setViewportSize({ width: 390, height: 844 });
  for (const language of ["zh-CN", "en"]) {
    await page.addInitScript(
      ({ id, language }) =>
        localStorage.setItem(
          `tm2.preferences.user.${id}`,
          JSON.stringify({ locale: language }),
        ),
      { id: local, language },
    );
    await page.goto(`/runs/${runId}?project=${projectId}`);
    await expect(page.locator(".observatory .graph-export-view")).toBeVisible();
    await expect(page.locator(".observatory .inspector")).toBeHidden();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: info.outputPath(`network-mobile-${language}.png`),
      fullPage: true,
    });
    await page.goto("/settings?section=display");
    await expect(
      page.getByRole("heading", {
        name: language === "en" ? "System settings" : "系统设置",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("combobox", {
        name: language === "en" ? "Project" : "所属项目",
        exact: true,
      }),
    ).toHaveCount(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
  }
  expect(witness.requests.filter((r) => r.method !== "GET")).toEqual([]);
  expect(witness.errors).toEqual([]);
});
