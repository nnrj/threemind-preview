/** Offline MP4 from exactly the React UI's evidence renderer; no Lab/Core calls. */
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { readFile, writeFile, mkdir, stat, rename } from "node:fs/promises";
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { once } from "node:events";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(resolve(root, "threemind-ui/package.json"));
const { chromium } = require("playwright");
const args = process.argv.slice(2);
const option = (name, fallback) =>
  args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
if (!option("--input"))
  throw new Error(
    "Usage: node tools/export_language_replay.mjs --input replay.json --output video.mp4 [--fps 15] [--preview-only] [--ffmpeg executable]",
  );
const input = resolve(option("--input")),
  output = resolve(option("--output", input.replace(/\.json$/, ".mp4")));
const fps = Number(option("--fps", "15")),
  previewOnly = args.includes("--preview-only");
if (!Number.isInteger(fps) || fps < 1 || fps > 30)
  throw new Error("FPS must be 1–30");
if ((await stat(input)).size > 32 * 1024 ** 2)
  throw new Error("Replay exceeds 32 MiB");
const data = JSON.parse(await readFile(input, "utf8"));
await mkdir(dirname(output), { recursive: true });
if (!previewOnly && (await stat(output).catch(() => null)))
  throw new Error("Output exists; choose a new filename");
const listener = createServer();
listener.listen(0, "127.0.0.1");
await once(listener, "listening");
const port = listener.address().port;
await new Promise((r) => listener.close(r));
const server = spawn(
  process.execPath,
  [
    resolve(root, "threemind-ui/node_modules/vite/bin/vite.js"),
    "--host",
    "127.0.0.1",
    "--port",
    String(port),
    "--strictPort",
  ],
  {
    cwd: resolve(root, "threemind-ui"),
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  },
);
let log = "",
  browser,
  encoder,
  encoderDone,
  encodeError;
server.on("error", (e) => {
  log += String(e);
});
for (const s of [server.stdout, server.stderr])
  s.on("data", (b) => {
    log = (log + b.toString()).slice(-6000);
  });
const started = Date.now();
try {
  const url = `http://127.0.0.1:${port}/e2e/fixtures/language-replay.html`;
  let ready = false;
  for (let n = 0; n < 80; n++) {
    if (
      await fetch(url)
        .then((r) => r.ok)
        .catch(() => false)
    ) {
      ready = true;
      break;
    }
    if (server.exitCode !== null) throw new Error(log);
    await new Promise((r) => setTimeout(r, 250));
  }
  if (!ready) throw new Error(`Preview did not start: ${log}`);
  browser = await chromium.launch({
    channel: process.env.THREEMIND_BROWSER || "msedge",
    headless: true,
  });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1050 },
    deviceScaleFactor: 1,
  });
  page.on("pageerror", (e) => {
    throw e;
  });
  await page.goto(url);
  await page.waitForFunction(() => !!window.languageReplayHarness);
  const duration = await page.evaluate(
    (d) => window.languageReplayHarness.load(d),
    data,
  );
  await page.evaluate(() => document.fonts.ready);
  const sampleTimes = [0, 36, 77, 139, 159, 187, 196, 216].filter(
    (t) => t < duration,
  );
  for (const time of sampleTimes) {
    const bytes = Buffer.from(
      await page.evaluate((t) => window.languageReplayHarness.frame(t), time),
      "base64",
    );
    await writeFile(
      resolve(dirname(output), `frame-${String(time).padStart(3, "0")}.png`),
      bytes,
    );
  }
  await writeFile(
    resolve(dirname(output), "poster.png"),
    Buffer.from(
      await page.evaluate(() => window.languageReplayHarness.frame(77)),
      "base64",
    ),
  );
  await page.screenshot({
    path: resolve(dirname(output), "ui-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "教学与回答", exact: true }).click();
  await page.screenshot({
    path: resolve(dirname(output), "ui-mobile.png"),
    fullPage: true,
  });
  if (previewOnly) {
    console.log(JSON.stringify({ duration, previews: dirname(output) }));
  } else {
    const partial = output.replace(/\.mp4$/i, "") + ".partial.mp4";
    let stderr = "";
    const ffmpeg = option("--ffmpeg", process.env.FFMPEG || "ffmpeg");
    encoder = spawn(
      ffmpeg,
      [
        "-hide_banner",
        "-loglevel",
        "warning",
        "-n",
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "-framerate",
        String(fps),
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-threads",
        "2",
        "-preset",
        "fast",
        "-crf",
        "19",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        partial,
      ],
      { windowsHide: true, stdio: ["pipe", "ignore", "pipe"] },
    );
    encoder.stderr.on("data", (b) => {
      stderr = (stderr + b.toString()).slice(-6000);
    });
    encoder.stdin.on("error", (e) => {
      encodeError = e;
    });
    encoderDone = new Promise((resolve) => {
      encoder.on("error", (e) => {
        encodeError = e;
        resolve(-1);
      });
      encoder.on("close", resolve);
    });
    const count = Math.ceil(duration * fps);
    for (let n = 0; n < count; n++) {
      if (encodeError || encoder.exitCode !== null)
        throw encodeError || new Error(stderr);
      if (Date.now() - started > 20 * 60 * 1000)
        throw new Error("Export reached 20-minute wall-clock budget");
      const bytes = Buffer.from(
        await page.evaluate(
          (t) => window.languageReplayHarness.frame(t),
          n / fps,
        ),
        "base64",
      );
      if (!encoder.stdin.write(bytes))
        await Promise.race([
          once(encoder.stdin, "drain"),
          encoderDone.then(() => {
            throw encodeError || new Error(stderr);
          }),
        ]);
      if (n % (fps * 15) === 0) {
        if (
          (await stat(partial).catch(() => ({ size: 0 }))).size >
          512 * 1024 ** 2
        )
          throw new Error("Video exceeded 512 MiB budget");
        console.log(
          `Rendered ${n}/${count} frames (${Math.round((100 * n) / count)}%)`,
        );
      }
    }
    encoder.stdin.end();
    const exit = await encoderDone;
    if (exit !== 0) throw new Error(`FFmpeg ${exit}: ${stderr}`);
    await rename(partial, output);
    const manifest = {
      input,
      output,
      duration_s: duration,
      fps,
      frames: count,
      bytes: (await stat(output)).size,
      wall_seconds: (Date.now() - started) / 1000,
      renderer: "UI LanguageReplayRenderer",
      core_advanced: false,
      answers_regenerated: false,
      audio: false,
    };
    await writeFile(
      resolve(dirname(output), "video-manifest.json"),
      JSON.stringify(manifest, null, 2),
    );
    console.log(JSON.stringify(manifest));
  }
} finally {
  if (encoder && encoder.exitCode === null) {
    encoder.kill();
    await encoderDone;
  }
  await browser?.close();
  server.kill();
}
