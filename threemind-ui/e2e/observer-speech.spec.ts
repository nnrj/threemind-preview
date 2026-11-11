import { expect, test } from "@playwright/test";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

test("observer speech: off by default, bounded backlog, service errors and rule changes", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: "播报组件工程验收 " + Date.now() },
    })
  ).json();
  const base = `/api/v2/projects/${project.id}/ecologies`;
  const protocol = (await (await page.request.get(base + "/catalogue")).json())
    .defaults;
  protocol.base.duration_s = 0.02;
  protocol.ecology.founder_count = 2;
  const campaign = await (
    await page.request.post(base, {
      data: {
        operation_id: crypto.randomUUID(),
        name: "播报组件验收",
        objective: "Engineering fixture; no speech provider is contacted",
        protocol,
      },
    })
  ).json();
  const root = `${base}/${campaign.id}/observer`;
  await expect
    .poll(
      async () =>
        (await (await page.request.get(`${base}/${campaign.id}`)).json())
          .campaign.status,
    )
    .toBe("completed");
  const config = (await (await page.request.get(root)).json()).catalogue
    .defaults;
  config.enabled = true;
  config.start_from = "beginning";
  expect(
    (
      await page.request.post(root + "/configuration", {
        data: { configuration: config, expected_revision: 0 },
      })
    ).status(),
  ).toBe(200);
  await expect
    .poll(
      async () =>
        (await (await page.request.get(root)).json()).observer.job_status,
    )
    .toBe("done");
  const before = await (
    await page.request.get(`${base}/${campaign.id}`)
  ).json();
  const original = await (
    await page.request.get(root + "/export?configuration_revision=1")
  ).text();
  await page.addInitScript((id) => {
    localStorage.setItem("tm2.project", id);
    const fixture: any = {
      spoken: [],
      cancelled: 0,
      utterance: null,
      fail: false,
    };
    (window as any).__speechFixture = fixture;
    const synth = Object.assign(new EventTarget(), {
      getVoices: () => [
        {
          voiceURI: "fixture-local",
          name: "本机测试语音",
          lang: "zh-CN",
          localService: true,
        },
        {
          voiceURI: "fixture-network",
          name: "网络测试语音",
          lang: "zh-CN",
          localService: false,
        },
      ],
      resume() {},
      speak(utterance: any) {
        fixture.spoken.push(utterance.text);
        fixture.utterance = utterance;
        if (fixture.fail) utterance.onerror({ error: "voice-unavailable" });
      },
      cancel() {
        fixture.cancelled += 1;
        fixture.utterance = null;
      },
    });
    Object.defineProperty(window, "speechSynthesis", {
      value: synth,
      configurable: true,
    });
    Object.defineProperty(window, "SpeechSynthesisUtterance", {
      value: class {
        text: string;
        constructor(text: string) {
          this.text = text;
        }
      },
      configurable: true,
    });
  }, project.id);
  let reads = 0,
    baseline = "100",
    failureRequested = false;
  function row(id: number) {
    return {
      id: String(id),
      kind: "summary",
      body: { text: { zh: `播报组件样例 ${id}`, en: `Speech fixture ${id}` } },
    };
  }
  await page.route("**/observer/live?*", async (route) => {
    reads += 1;
    const after = new URL(route.request().url()).searchParams.get("after");
    let response: any = {
      cursor: after ?? baseline,
      rows: [],
      omitted: 0,
      baseline: after === null,
    };
    if (after === "100") {
      response = {
        cursor: "108",
        rows: [row(106), row(107), row(108)],
        omitted: 5,
        baseline: false,
      };
      baseline = "108";
    } else if (after === "108") {
      response = {
        cursor: "113",
        rows: [row(111), row(112), row(113)],
        omitted: 2,
        baseline: false,
      };
      baseline = "113";
    } else if (failureRequested && after === "113") {
      response = {
        cursor: "114",
        rows: [row(114)],
        omitted: 0,
        baseline: false,
      };
      baseline = "114";
    }
    await route.fulfill({ json: response });
  });
  await page.goto(`/studies?tab=ecology&campaign=${campaign.id}`);
  const panel = page.getByRole("region", {
    name: "生态观察与预警",
    exact: true,
  });
  const speech = panel.locator(".observer-speech");
  await speech.locator("summary").click();
  await expect(speech.getByText("播报已关闭", { exact: true })).toBeVisible();
  await expect(speech.getByLabel("播报语音", { exact: true })).toHaveValue(
    "fixture-local",
  );
  expect(reads).toBe(0);
  expect(
    await page.evaluate(() => (window as any).__speechFixture.spoken),
  ).toEqual([]);
  await speech
    .getByLabel("播报语音", { exact: true })
    .selectOption("fixture-network");
  await expect(speech).toContainText("播报文本可能发送给浏览器的语音服务");
  await speech
    .getByLabel("播报语音", { exact: true })
    .selectOption("fixture-local");
  await speech.getByRole("button", { name: "启用播报", exact: true }).click();
  await expect.poll(() => reads).toBeGreaterThan(0);
  await expect
    .poll(
      async () =>
        (await page.evaluate(() => (window as any).__speechFixture.spoken))
          .length,
    )
    .toBe(1);
  await expect(speech).toContainText("跳过 9 条");
  await page.evaluate(() => (window as any).__speechFixture.utterance.onend());
  await expect
    .poll(
      async () =>
        await page.evaluate(() => (window as any).__speechFixture.spoken),
    )
    .toEqual(["播报组件样例 106", "播报组件样例 111"]);
  await expect(speech).toContainText("已播报 1 条");
  await speech.screenshot({ path: info.outputPath("observer-speech.png") });
  await speech.getByRole("button", { name: "停止播报", exact: true }).click();
  await expect(speech.getByText("播报已关闭", { exact: true })).toBeVisible();
  expect(
    await page.evaluate(() => (window as any).__speechFixture.cancelled),
  ).toBeGreaterThan(0);
  await page.evaluate(() => {
    (window as any).__speechFixture.fail = true;
  });
  failureRequested = true;
  await speech.getByRole("button", { name: "启用播报", exact: true }).click();
  await expect(speech.getByRole("alert")).toContainText("voice-unavailable");
  await expect(speech.getByText("播报已关闭", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await speech.screenshot({
    path: info.outputPath("observer-speech-mobile-error.png"),
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 2,
    ),
  ).toBe(true);
  expect(
    await (
      await page.request.get(root + "/export?configuration_revision=1")
    ).text(),
  ).toBe(original);
  const after = await (await page.request.get(`${base}/${campaign.id}`)).json();
  expect(after.campaign.checkpoint_id).toBe(before.campaign.checkpoint_id);
  expect(after.checkpoint.state_hash).toBe(before.checkpoint.state_hash);
  await page.evaluate(() => {
    (window as any).__speechFixture.fail = false;
  });
  await speech.getByRole("button", { name: "启用播报", exact: true }).click();
  expect(
    (
      await page.request.post(root + "/configuration", {
        data: { configuration: config, expected_revision: 1 },
      })
    ).status(),
  ).toBe(200);
  await expect(speech).not.toHaveAttribute("open", "");
  await speech.locator("summary").click();
  await expect(
    speech.getByRole("button", { name: "启用播报", exact: true }),
  ).toBeVisible();
  await expect(speech.getByText("播报已关闭", { exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});
