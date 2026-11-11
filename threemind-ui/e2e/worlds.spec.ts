import { expect, test } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("worlds: graphical bodies and RGB sensing, JSON, fixed revisions and actual observation", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `世界工具工程验收 ${Date.now()}` },
    })
  ).json();
  const base = `/api/v2/projects/${project.id}`;
  await page.addInitScript(
    (id: string) => localStorage.setItem("tm2.project", id),
    project.id,
  );
  await page.goto("/worlds");
  await page.getByRole("button", { name: "新建世界", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "新建世界", exact: true });
  await dialog
    .getByLabel("世界名称", { exact: true })
    .fill("带物理眼睛的工程世界");
  await dialog
    .getByRole("combobox", { name: "新增感官类型", exact: true })
    .selectOption("camera_rgb");
  await dialog.getByRole("button", { name: "添加感官", exact: true }).click();
  const inspector = dialog.locator(".world-inspector");
  await inspector
    .getByRole("spinbutton", { name: "局部位置（m） 3", exact: true })
    .fill("1");
  await expect(inspector.locator("details")).not.toHaveAttribute("open");
  await inspector.locator("details > summary").click();
  await inspector.getByLabel("感官像素宽度", { exact: true }).fill("4");
  await inspector.getByLabel("感官像素高度", { exact: true }).fill("4");
  await dialog
    .getByRole("button", { name: "切换到 JSON 编辑", exact: true })
    .click();
  await expect(dialog.locator(".cm-lineNumbers")).toBeVisible();
  const captured = page.waitForRequest((r) =>
    r.url().endsWith("/worlds/validate"),
  );
  await dialog.getByRole("button", { name: "校验与预览", exact: true }).click();
  const protocol = (await captured).postDataJSON().protocol;
  expect(protocol.sensors.at(-1).width).toBe(4);
  const json = dialog.getByRole("textbox", {
    name: "世界协议 JSON",
    exact: true,
  });
  await json.fill('{"label":"a","label":"b"}');
  await dialog.getByRole("button", { name: "格式化", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("重复");
  protocol.sensors.at(-1).width = 5;
  await json.fill(JSON.stringify(protocol));
  await dialog
    .getByRole("button", { name: "切换到图形配置", exact: true })
    .click();
  await expect(
    inspector.getByLabel("感官像素宽度", { exact: true }),
  ).toHaveValue("5");
  await expect(dialog.locator(".world-scene canvas")).toBeVisible();
  await dialog.locator(".world-scene").scrollIntoViewIfNeeded();
  await page.screenshot({ path: info.outputPath("world-configuration.png") });
  const saved = page.waitForResponse(
    (r) => r.url().endsWith("/worlds") && r.request().method() === "POST",
  );
  await dialog
    .getByRole("button", { name: "校验并保存世界", exact: true })
    .click();
  const record = await (await saved).json();
  await expect(dialog).toHaveCount(0);
  expect(record.revision).toBe(1);
  const firstHash = record.protocol_hash;
  await page
    .getByRole("button", { name: "配置意识并接入此世界", exact: true })
    .click();
  const create = page.getByRole("dialog", { name: "创建运行", exact: true });
  await expect(
    create.getByRole("combobox", { name: "环境与感官来源", exact: true }),
  ).toHaveValue("world");
  await create.getByLabel("运行名称", { exact: true }).fill("世界接入工程实例");
  await create
    .getByRole("combobox", { name: "时钟模式", exact: true })
    .selectOption("unbounded");
  await create.getByLabel("运行时长（模拟秒）", { exact: true }).fill("0.047");
  await create.getByRole("button", { name: "创建并开始", exact: true }).click();
  await expect(page).toHaveURL(/\/runs\//);
  const runId = page.url().split("/runs/")[1].split(/[?#]/)[0];
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`${base}/runs/${runId}`)).json()).status,
    )
    .toBe("completed");
  await page.getByRole("button", { name: "感官与输入", exact: true }).click();
  await page.getByRole("button", { name: "环境与躯体", exact: true }).click();
  const observation = page.getByRole("region", {
    name: "虚拟躯体与世界观测",
    exact: true,
  });
  await expect(observation.locator(".world-scene canvas")).toBeVisible();
  await expect(observation.locator(".world-eye canvas")).toHaveAttribute(
    "width",
    "5",
  );
  await expect(observation.locator(".world-clock")).toContainText("47000");
  await expect(observation.locator(".world-clock")).toContainText("60000");
  const state = await (
    await page.request.get(`${base}/runs/${runId}/world/observation`)
  ).json();
  expect(state.world_hash).toBe(firstHash);
  expect(state.measurements.at(-1).values.length).toBe(60);
  await observation.locator(".world-scene").scrollIntoViewIfNeeded();
  await page.screenshot({ path: info.outputPath("world-observation.png") });
  await page.goto("/worlds");
  await page
    .locator(".world-library-list")
    .getByRole("button", { name: /带物理眼睛的工程世界/ })
    .click();
  await page
    .getByRole("button", { name: "编辑并保存新版本", exact: true })
    .click();
  const edit = page.getByRole("dialog", { name: "编辑世界版本", exact: true });
  await edit.getByLabel("世界名称", { exact: true }).fill("新版本的观察名称");
  await edit
    .getByLabel("导入世界协议文件", { exact: true })
    .setInputFiles({
      name: "invalid.world.json",
      mimeType: "application/json",
      buffer: Buffer.from('{"label":"a","label":"b"}'),
    });
  await expect(edit.getByRole("alert")).toContainText("重复");
  await expect(edit.getByLabel("世界名称", { exact: true })).toHaveValue(
    "新版本的观察名称",
  );
  await edit
    .getByLabel("导入世界协议文件", { exact: true })
    .setInputFiles({
      name: "revised.world.json",
      mimeType: "application/json",
      buffer: Buffer.from(
        JSON.stringify({ ...protocol, label: "新版本的观察名称" }),
      ),
    });
  await expect(edit.getByRole("alert")).toHaveCount(0);
  await edit
    .getByRole("button", { name: "校验并保存世界", exact: true })
    .click();
  await expect(edit).toHaveCount(0);
  expect(
    (
      await (
        await page.request.get(`${base}/worlds/${record.document_id}`)
      ).json()
    ).revision,
  ).toBe(2);
  expect(
    (
      await (
        await page.request.get(`${base}/runs/${runId}/world/observation`)
      ).json()
    ).world_hash,
  ).toBe(firstHash);
  await page
    .getByRole("combobox", { name: "世界修订", exact: true })
    .selectOption("1");
  await expect(page.locator(".world-library-detail h2")).toHaveText(
    "带物理眼睛的工程世界",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .locator(".world-library-detail .world-scene")
    .scrollIntoViewIfNeeded();
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    )
    .toBe(true);
  await page.screenshot({ path: info.outputPath("world-mobile.png") });
  expect(errors).toEqual([]);
});
