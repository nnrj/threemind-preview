import { test, expect } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_TARGET_RUN,
  "Uses an existing read-only research record.",
);
for (const width of [1440, 390]) {
  test(`target response with preserved global evidence at ${width}px`, async ({
    page,
  }, info) => {
    const project = process.env.THREEMIND_TARGET_PROJECT!;
    const run = process.env.THREEMIND_TARGET_RUN!;
    await page.setViewportSize({ width, height: 950 });
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto("/");
    if (width < 700) {
      await page
        .getByRole("button", { name: "切换研究项目", exact: true })
        .click();
      await page
        .getByRole("dialog")
        .getByRole("combobox")
        .selectOption(project);
    } else {
      await page
        .getByLabel("当前研究项目", { exact: true })
        .selectOption(project);
    }
    const base = `/api/v2/projects/${project}/runs/${run}/readouts`;
    const history = await (await page.request.get(base)).json();
    const event = history.rows.find((r: any) => r.payload.analysis_schema);
    expect(event).toBeTruthy();
    const before = await (
      await page.request.get(`${base}/${event.id}/export`)
    ).text();
    const original = JSON.parse(before).payload;
    const chosen = original.nodes
      .filter((n: any) => n.peak_activation > 0)
      .slice(0, 2)
      .map((n: any) => n.node_id);
    expect(chosen.length).toBeGreaterThan(0);
    await page.goto(`/runs/${run}?view=readouts&record=${event.id}`);
    const tool = page.locator(".target-observation");
    await expect(tool.getByText("检测到响应", { exact: true })).toBeVisible();
    await expect(
      tool.getByRole("button", { name: "响应读出", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await tool.getByLabel("目标节点 ID（留空读取全部节点）").fill("999999999");
    await tool.getByRole("button", { name: "读取响应", exact: true }).click();
    await expect(tool.getByText(/selected node IDs are absent/)).toBeVisible();
    await tool
      .getByLabel("目标节点 ID（留空读取全部节点）")
      .fill(chosen.join(","));
    await tool.getByRole("button", { name: "读取响应", exact: true }).click();
    await expect(tool.getByText("检测到响应", { exact: true })).toBeVisible();
    const responseLink = tool.getByRole("link", {
      name: "导出完整响应 JSON",
      exact: true,
    });
    const responses = await (
      await page.request.get((await responseLink.getAttribute("href"))!)
    ).json();
    expect(responses.selection.node_ids).toEqual(
      [...chosen].sort((a, b) => a - b),
    );
    expect(responses.configuration.minimum_duration_us).toBe("0");
    expect(responses.original_classification).toBe(original.classification);
    const primary = responses.events[responses.strongest_event_index];
    expect(
      primary.ranking.every(
        (n: any) =>
          original.series[primary.sample_index].activation_vector[
            String(n.node_id)
          ] === n.activation,
      ),
    ).toBeTruthy();
    await tool
      .getByRole("button", { name: "查看此刻", exact: true })
      .first()
      .click();
    await expect(
      tool.getByRole("button", { name: "返回本窗最大响应", exact: true }),
    ).toBeEnabled();
    await tool
      .getByRole("button", { name: "返回本窗最大响应", exact: true })
      .click();
    await expect(
      tool.getByRole("button", { name: "返回本窗最大响应", exact: true }),
    ).toBeDisabled();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBeTruthy();
    await tool.screenshot({ path: info.outputPath(`response-${width}.png`) });
    await tool
      .getByRole("button", { name: "持续稳定（旧版）", exact: true })
      .click();
    await tool.getByLabel("目标节点 ID（逗号分隔）").fill("999999999");
    await tool
      .getByRole("button", { name: "分析目标响应", exact: true })
      .click();
    await expect(tool.getByText(/target identities not present/)).toBeVisible();
    await tool.getByLabel("目标节点 ID（逗号分隔）").fill(chosen.join(","));
    await tool
      .getByRole("button", { name: "分析目标响应", exact: true })
      .click();
    await expect(
      tool.getByText("过程内测到活动", { exact: true }),
    ).toBeVisible();
    await expect(tool.getByText("原全局判定", { exact: true })).toBeVisible();
    await expect(
      tool.getByRole("columnheader", { name: "激活积分", exact: true }),
    ).toBeVisible();
    const link = tool.getByRole("link", {
      name: "导出完整目标分析 JSON",
      exact: true,
    });
    const downloaded = await (
      await page.request.get((await link.getAttribute("href"))!)
    ).json();
    expect(downloaded.original_classification).toBe(original.classification);
    expect(downloaded.configuration.node_ids).toEqual(
      [...chosen].sort((a, b) => a - b),
    );
    expect(
      await (await page.request.get(`${base}/${event.id}/export`)).text(),
    ).toBe(before);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBeTruthy();
    await tool.screenshot({ path: info.outputPath(`target-${width}.png`) });
    expect(errors).toEqual([]);
  });
}
