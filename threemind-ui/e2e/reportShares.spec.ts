import { expect, test } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("fixed publication: explicit preview, lost acknowledgement, anonymous route and revocation", async ({
  page,
  browser,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "固定分享验收 " + Date.now() },
    })
  ).json();
  const base = `/api/v2/projects/${project.id}`;
  await page.addInitScript((id: string) => {
    if (window === window.top) localStorage.setItem("tm2.project", id);
  }, project.id);
  const run = await (
    await page.request.post(base + "/runs", {
      data: {
        name: "分享来源",
        spec: {
          environment: "replay",
          duration_s: 0.03,
          sample_us: 1000,
          clock: "unbounded",
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
    })
  ).json();
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`${base}/runs/${run.id}`)).json())
          .status,
    )
    .toBe("completed");
  const source = await (
    await page.request.post(base + "/report-sources", {
      data: {
        operation_id: crypto.randomUUID(),
        kind: "trajectory",
        run_id: run.id,
        metrics: ["activation"],
      },
    })
  ).json();
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(`${base}/report-sources/${source.id}`)
          ).json()
        ).content_hash,
    )
    .toBeTruthy();
  const spec = await (
    await page.request.get(`${base}/report-sources/${source.id}/template`)
  ).json();
  spec.title = "公开阅读的固定证据";
  spec.blocks[0].markdown =
    "作者的 **待检验假设**，不等同于意识成立。<script>window.shareScriptRan=true</script>";
  spec.blocks.push({
    id: "activation-chart",
    type: "chart",
    source: source.id,
    metric: "activation",
    chart: "line",
    title: "活动随时间变化",
  });
  const document = crypto.randomUUID();
  expect(
    (
      await page.request.put(`${base}/research-documents/${document}`, {
        data: { operation_id: crypto.randomUUID(), expected_revision: 0, spec },
      })
    ).ok(),
  ).toBeTruthy();
  await page.goto("/reports");
  await page.getByRole("button", { name: "分享", exact: true }).click();
  const modal = page.getByRole("dialog", { name: "分享固定版本" });
  await expect(
    modal.getByRole("checkbox", { name: "同时公开完整证据 ZIP" }),
  ).not.toBeChecked();
  await expect(
    modal.getByRole("button", { name: "创建分享链接" }),
  ).toBeDisabled();
  await modal.getByRole("button", { name: "生成分享预览" }).click();
  await expect(
    modal
      .frameLocator('iframe[title="分享正文预览"]')
      .getByRole("heading", { name: spec.title }),
  ).toBeVisible();
  await expect(
    modal.getByRole("button", { name: "创建分享链接" }),
  ).toBeEnabled();
  let dropped = false;
  await page.route(
    `**/research-documents/${document}/shares`,
    async (route) => {
      if (!dropped && route.request().method() === "POST") {
        dropped = true;
        await route.fetch();
        await route.abort();
      } else await route.continue();
    },
  );
  await modal.getByRole("button", { name: "创建分享链接" }).click();
  await expect(modal.getByRole("alert")).toBeVisible();
  await modal.getByRole("button", { name: "创建分享链接" }).click();
  await expect(
    modal.getByRole("textbox", { name: "分享链接", exact: true }),
  ).toHaveCount(1);
  const link = await modal
    .getByRole("textbox", { name: "分享链接", exact: true })
    .inputValue();
  const first = (
    await (
      await page.request.get(`${base}/research-documents/${document}/shares`)
    ).json()
  ).rows;
  expect(first).toHaveLength(1);
  expect(first[0].metadata.bundle).toBeNull();
  await modal.evaluate((element) => {
    element.scrollTop = 0;
  });
  await page.screenshot({
    path: info.outputPath("share-management-desktop.png"),
  });

  // Editing the original cannot move an existing publication to a different revision.
  expect(
    (
      await page.request.put(`${base}/research-documents/${document}`, {
        data: {
          operation_id: crypto.randomUUID(),
          expected_revision: 1,
          spec: { ...spec, title: "后续私人修订" },
        },
      })
    ).ok(),
  ).toBeTruthy();
  const anonymous = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });
  const publicPage = await anonymous.newPage();
  const privateRequests: string[] = [];
  publicPage.on("request", (request) => {
    if (
      request.url().includes("/api/v2/") &&
      !request.url().includes("/api/v2/shared-documents/")
    )
      privateRequests.push(request.url());
  });
  publicPage.on("pageerror", (error) => errors.push(error.message));
  await publicPage.goto(link);
  await expect(
    publicPage.getByRole("heading", { name: spec.title, exact: true }),
  ).toBeVisible();
  await expect(
    publicPage
      .frameLocator('iframe[title="分享正文"]')
      .getByRole("heading", { name: "活动随时间变化" }),
  ).toBeVisible();
  await expect(
    publicPage.getByRole("link", { name: "下载完整证据 ZIP" }),
  ).toHaveCount(0);
  expect(await publicPage.locator("iframe").getAttribute("sandbox")).toBe("");
  expect(privateRequests).toEqual([]);
  await publicPage.screenshot({
    path: info.outputPath("shared-document-desktop.png"),
    fullPage: true,
  });
  await publicPage.setViewportSize({ width: 390, height: 844 });
  expect(
    await publicPage.evaluate(
      () => document.documentElement.scrollWidth - innerWidth,
    ),
  ).toBeLessThanOrEqual(1);
  await publicPage.screenshot({
    path: info.outputPath("shared-document-mobile.png"),
    fullPage: true,
  });
  await modal.getByRole("checkbox", { name: "同时公开完整证据 ZIP" }).check();
  await expect(
    modal.getByRole("button", { name: "创建分享链接" }),
  ).toBeDisabled();
  await modal.getByRole("button", { name: "生成分享预览" }).click();
  await expect(
    modal.getByRole("button", { name: "创建分享链接" }),
  ).toBeEnabled();
  await modal.getByRole("button", { name: "创建分享链接" }).click();
  await expect(
    modal.getByRole("textbox", { name: "分享链接", exact: true }),
  ).toHaveCount(2);
  const latest = (
    await (
      await page.request.get(`${base}/research-documents/${document}/shares`)
    ).json()
  ).rows;
  expect(latest[0].revision).toBe(1); // Dialog keeps the revision selected when it opened.
  expect(latest[0].metadata.bundle).toBeTruthy();
  await publicPage.goto(new URL(`/shared/${latest[0].id}`, link).href);
  await expect(
    publicPage.getByRole("link", { name: "下载完整证据 ZIP" }),
  ).toBeVisible();
  const downloaded = await publicPage.request.get(
    new URL(`/api/v2/shared-documents/${latest[0].id}/files/bundle`, link).href,
  );
  expect(downloaded.ok()).toBeTruthy();
  expect((await downloaded.body()).subarray(0, 2).toString()).toBe("PK");
  await modal.getByRole("button", { name: "撤销分享" }).last().click();
  await publicPage.goto(link);
  await expect(publicPage.getByRole("alert")).toContainText(
    "链接可能已过期或被撤销",
  );
  expect(privateRequests).toEqual([]);
  expect(errors).toEqual([]);
  await anonymous.close();
});
