import { test, expect } from "@playwright/test";

// Read-only: safe on the standalone history server or a Lab instance.
for (const width of [1440, 390]) {
  test(`history editions, sources and navigation at ${width}px`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width, height: 960 });
    const errors: string[] = [],
      requests: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("request", (r) => {
      if (r.url().includes("/api/v2/"))
        requests.push(new URL(r.url()).pathname);
    });
    await page.goto("/history");
    await expect(page.locator(".history-prose h1")).toContainText(
      "ThreeMind 通史",
    );
    await expect(page.locator(".history-prose")).toContainText("2026-07-23");
    expect(
      requests.every(
        (p) => p === "/api/v2/history" || p.startsWith("/api/v2/documents"),
      ),
    ).toBeTruthy();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 2,
      ),
    ).toBeTruthy();
    if (width === 390) {
      await expect(page.locator(".history-book-toc")).not.toHaveAttribute(
        "open",
        "",
      );
      await page.locator(".history-book-toc > summary").click();
    }
    await page
      .getByRole("textbox", { name: "搜索章节", exact: true })
      .fill("强刺激");
    await page
      .getByRole("navigation", { name: "史书章节" })
      .getByRole("link", {
        name: "强刺激巩固：来历、证据与暂留判断",
        exact: true,
      })
      .click();
    await expect(page.locator(".history-prose h1")).toContainText("强刺激巩固");
    await page.locator(".history-page-toc > summary").click();
    await page
      .locator(".history-page-toc")
      .getByRole("link", { name: "出处怎样一步步补齐", exact: true })
      .click();
    await expect(page).toHaveURL(/#%|#出处/);
    await page.reload();
    await expect(
      page.locator(".history-prose h2", { hasText: "出处怎样一步步补齐" }),
    ).toBeInViewport();
    await page
      .locator(".history-prose")
      .getByRole("link", { name: "7 月原始讨论", exact: true })
      .click();
    await expect(page.locator(".history-prose h1")).toContainText("强刺激史料");
    await expect(page.locator(".history-prose")).toContainText(
      "2026-07-25T14:10:09+08:00",
    );
    await page.goBack();
    await page
      .locator(".history-prose")
      .getByRole("link", { name: "E19 · 最新报告", exact: true })
      .click();
    await expect(page.locator(".history-back")).toBeVisible();
    await expect(page.locator(".history-prose h1")).toContainText("强刺激");
    const figure = page.locator(".history-prose img").first();
    await figure.scrollIntoViewIfNeeded();
    await expect
      .poll(() =>
        figure.evaluate(
          (image: HTMLImageElement) => image.complete && image.naturalWidth > 0,
        ),
      )
      .toBeTruthy();
    await page.locator(".history-back").click();
    await expect(page.locator(".history-prose h1")).toContainText("暂留判断");
    if (width === 390)
      await page
        .getByLabel("史书版本", { exact: true })
        .selectOption("modern-en");
    else
      await page
        .getByRole("button", { name: /A History of ThreeMind/ })
        .click();
    await expect(page.locator(".history-prose h1")).toContainText(
      "Strong-input consolidation",
    );
    await page
      .getByRole("button", { name: "Markdown 源码", exact: true })
      .click();
    await expect(page.locator(".markdown-source")).toContainText(
      "max(0, frame_intensity - 1)",
    );
    await page.getByRole("button", { name: "阅读视图", exact: true }).click();
    const downloadEvent = page.waitForEvent("download");
    await page.getByRole("button", { name: "下载本章", exact: true }).click();
    expect((await downloadEvent).suggestedFilename()).toBe(
      "strong-stimulus.md",
    );
    for (const [edition, title] of [
      ["classical-biographical", "ThreeMind 史记"],
      ["classical-chronological", "ThreeMind 通鉴"],
    ]) {
      if (width === 390)
        await page
          .getByLabel("史书版本", { exact: true })
          .selectOption(edition);
      else await page.getByRole("button", { name: new RegExp(title) }).click();
      await expect(page.locator(".history-prose h1")).toContainText(title);
      await page
        .getByRole("navigation", { name: "章节翻阅" })
        .getByRole("link", { name: /下一章/ })
        .click();
      await expect(page.locator(".history-prose h1")).toContainText("卷二");
    }
    await page.screenshot({
      path: info.outputPath(`history-${width}.png`),
      fullPage: false,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 2,
      ),
    ).toBeTruthy();
    expect(errors).toEqual([]);
  });
}

test("English interface, unknown chapter and public document reader", async ({
  page,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("tm2.preferences", JSON.stringify({ locale: "en" })),
  );
  await page.goto("/history?book=modern-en&chapter=manifesto");
  await expect(page.locator(".history-prose h1")).toContainText("Manifesto");
  await expect(
    page.getByRole("button", { name: "Download chapter", exact: true }),
  ).toBeVisible();
  await page.goto("/history?book=absent");
  await expect(
    page.getByRole("heading", { name: "History edition or chapter not found" }),
  ).toBeVisible();
  await page.goto("/docs?doc=docs%2Fen%2Fhistory%2Fmanifesto.md");
  await expect(page.locator(".doc-body article h1")).toContainText("Manifesto");
  await expect(page.locator(".connection-page")).toHaveCount(0);
});
