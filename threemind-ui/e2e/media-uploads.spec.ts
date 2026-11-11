import { test, expect } from "@playwright/test";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

test.skip(
  !process.env.THREEMIND_E2E_URL,
  "Requires an explicitly selected workstation.",
);

function fixture() {
  const padding = 2 * 1024 ** 2,
    samples = 321;
  const raw = Buffer.alloc(52 + padding + samples * 2);
  raw.write("RIFF");
  raw.writeUInt32LE(raw.length - 8, 4);
  raw.write("WAVEJUNK", 8);
  raw.writeUInt32LE(padding, 16);
  const at = padding + 20;
  raw.write("fmt ", at);
  raw.writeUInt32LE(16, at + 4);
  raw.writeUInt16LE(1, at + 8);
  raw.writeUInt16LE(1, at + 10);
  raw.writeUInt32LE(16000, at + 12);
  raw.writeUInt32LE(32000, at + 16);
  raw.writeUInt16LE(2, at + 20);
  raw.writeUInt16LE(16, at + 22);
  raw.write("data", at + 24);
  raw.writeUInt32LE(samples * 2, at + 28);
  for (let i = 0; i < samples; i++) raw.writeInt16LE(9000, at + 32 + i * 2);
  return raw;
}

test("media acknowledgement loss, reload resume, wrong-file rejection and evidence", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const project = await (
    await page.request.post("/api/v2/projects", {
      data: { name: `分块媒体验收 ${new Date().toISOString()}` },
    })
  ).json();
  const run = await (
    await page.request.post(`/api/v2/projects/${project.id}/runs`, {
      data: {
        name: "原件续传与证据验收",
        spec: {
          environment: "manual",
          clock: "realtime",
          duration_s: 180,
          checkpoint_us: 500000,
          auditory_sensor: {
            enabled: true,
            encoding: "waveform",
            waveform_bins: 4,
            window_us: 20000,
            upload_limit_mb: 512,
          },
        },
      },
    })
  ).json();
  const base = `/api/v2/projects/${project.id}/runs/${run.id}`;
  let lost = false,
    blocked = true,
    firstPuts = 0,
    uploadId = "";
  await page.route("**/media-uploads/*/chunks/*?*", async (route) => {
    if (route.request().method() !== "PUT") return route.continue();
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/0")) {
      firstPuts++;
      if (!lost) {
        lost = true;
        const received = await route.fetch();
        expect(received.status()).toBe(200);
        return route.abort("failed");
      }
    }
    if (blocked && url.pathname.endsWith("/1")) return route.abort("failed");
    return route.continue();
  });
  try {
    await expect
      .poll(async () => (await (await page.request.get(base)).json()).status)
      .toBe("running");
    await page.request.post(`${base}/commands`, { data: { kind: "pause" } });
    await expect
      .poll(async () => (await (await page.request.get(base)).json()).status)
      .toBe("paused");
    await page.goto("/");
    await page
      .getByLabel("当前研究项目", { exact: true })
      .selectOption(project.id);
    await page.goto(`/runs/${run.id}?view=inputs&tool=media`);
    const raw = fixture(),
      name = "分块续传样本.wav";
    await page
      .getByLabel("选择媒体原件", { exact: true })
      .setInputFiles({ name, mimeType: "audio/wav", buffer: raw });
    await page
      .getByRole("button", { name: "接收媒体并排队", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "接收媒体并排队", exact: true }),
    ).toBeEnabled();
    expect(firstPuts).toBe(2);
    const upload = (
      await (await page.request.get(`${base}/media-uploads`)).json()
    ).rows[0];
    uploadId = upload.id;
    expect(upload.next_chunk).toBe(1);
    expect(
      (await (await page.request.get(`${base}/inputs`)).json()).rows,
    ).toHaveLength(0);
    await page.reload();
    const queue = page.getByRole("region", {
      name: "媒体传输与暂存",
      exact: true,
    });
    await queue
      .getByRole("button", { name: "继续／重试", exact: true })
      .click();
    await expect(page.locator(".media-resume-notice")).toContainText(name);
    const wrong = Buffer.from(raw);
    wrong[0] ^= 1;
    await page
      .getByLabel("选择媒体原件", { exact: true })
      .setInputFiles({ name, mimeType: "audio/wav", buffer: wrong });
    await page
      .getByRole("button", { name: "接收媒体并排队", exact: true })
      .click();
    await expect(page.getByRole("alert")).toContainText(
      "第 1 块与原上传不一致",
    );
    expect(
      (
        await (
          await page.request.get(`${base}/media-uploads/${uploadId}`)
        ).json()
      ).next_chunk,
    ).toBe(1);
    blocked = false;
    await page
      .getByLabel("选择媒体原件", { exact: true })
      .setInputFiles({ name, mimeType: "audio/wav", buffer: raw });
    await page
      .getByRole("button", { name: "接收媒体并排队", exact: true })
      .click();
    await expect(
      page.getByRole("status", { name: "媒体处理进度", exact: true }),
    ).toContainText("已进入输入账本");
    expect(firstPuts).toBe(2);
    const rows = (await (await page.request.get(`${base}/inputs`)).json()).rows;
    expect(rows).toHaveLength(1);
    await queue.getByLabel("显示已完成与已取消", { exact: true }).check();
    const download = page.waitForEvent("download");
    await queue.getByRole("link", { name: "下载原件", exact: true }).click();
    const downloadedPath = await (await download).path();
    expect(
      createHash("sha256")
        .update(await readFile(downloadedPath!))
        .digest("hex"),
    ).toBe(createHash("sha256").update(raw).digest("hex"));
    await page
      .locator(".media-input")
      .screenshot({ path: info.outputPath("media-upload-desktop.png") });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(350);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await page
      .locator(".media-input")
      .screenshot({ path: info.outputPath("media-upload-mobile.png") });
    await page.request.post(`${base}/commands`, { data: { kind: "resume" } });
    await expect
      .poll(
        async () =>
          (await (await page.request.get(`${base}/inputs/${uploadId}`)).json())
            .envelope.status,
      )
      .toBe("completed");
    await page.goto("/docs?doc=docs%2Fzh%2Fv2-media-uploads.md");
    await expect(page.locator(".markdown h1")).toHaveText(
      "大媒体分块上传、续传与原件证据",
    );
    expect(errors).toEqual([]);
  } finally {
    await page.request
      .post(`${base}/commands`, { data: { kind: "pause" }, timeout: 5000 })
      .catch(() => {});
    if (uploadId)
      await page.request
        .delete(`${base}/media-uploads/${uploadId}`)
        .catch(() => {});
  }
});
