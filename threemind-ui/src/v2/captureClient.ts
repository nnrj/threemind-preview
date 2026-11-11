import { t } from "./i18n";
import { api, ApiError } from "./api";

export type CaptureStats = {
  confirmed: number;
  pending: number;
  bytes: number;
  videoFrames: number;
  videoSkipped: number;
  acknowledgementMs?: number;
  capacity?: number;
};
const delay = (ms: number) =>
  new Promise<void>((resolve) => setTimeout(resolve, ms));

function header(
  kind: number,
  sequence: number,
  captureUs: number,
  length: number,
  final = false,
  sourceIndex = 0,
  timestampKind = 0,
) {
  const raw = new Uint8Array(length),
    view = new DataView(raw.buffer);
  raw.set([84, 77, 86, 50]);
  view.setUint8(4, kind);
  view.setUint8(5, final ? 1 : 0);
  view.setUint32(6, sequence, true);
  view.setBigUint64(10, BigInt(captureUs), true);
  view.setBigUint64(18, BigInt(sourceIndex), true);
  view.setUint8(26, timestampKind);
  return { raw, view };
}

class PacketQueue {
  items: Uint8Array[] = [];
  next = 0;
  failed = false;
  running: Promise<void> | null = null;
  stats: CaptureStats = {
    confirmed: 0,
    pending: 0,
    bytes: 0,
    videoFrames: 0,
    videoSkipped: 0,
  };
  constructor(
    public url: string,
    public capacity: number,
    public update: (s: CaptureStats) => void,
    public fail: (message: string, reason: string) => void,
  ) {}
  enqueue(make: (sequence: number) => Uint8Array) {
    if (this.failed) return;
    if (this.items.length >= this.capacity) {
      this.failed = true;
      this.fail(
        t(
          "待确认采集块 {pending}/{capacity}，确认队列已满，采集已停止。最近确认耗时 {latency} ms。可在参数配置 → 高级参数 → 连续设备采集中调整上限；持续积压需要检查工作进程和数据库写入速度。",
          {
            pending: this.items.length,
            capacity: this.capacity,
            latency: Math.round(this.stats.acknowledgementMs ?? 0),
          },
        ),
        "queue_overflow",
      );
      return;
    }
    this.items.push(make(this.next++));
    this.publish();
    if (!this.running)
      this.running = this.send().finally(() => {
        this.running = null;
      });
  }
  publish() {
    this.stats.pending = this.items.length;
    this.stats.capacity = this.capacity;
    this.update({ ...this.stats });
  }
  async send() {
    while (this.items.length) {
      const raw = this.items[0];
      const started = performance.now();
      try {
        for (let attempt = 0; ; attempt++) {
          try {
            await api(this.url, {
              method: "POST",
              headers: { "Content-Type": "application/octet-stream" },
              body: raw as unknown as BodyInit,
              signal: AbortSignal.timeout(4000),
            });
            break;
          } catch (error) {
            const retry =
              !(error instanceof ApiError) ||
              [408, 409, 429, 500, 502, 503, 504].includes(error.status);
            if (!retry || attempt >= 3) throw error;
            await delay(100 * 2 ** attempt);
          }
        }
        this.items.shift();
        this.stats.confirmed++;
        this.stats.bytes += raw.byteLength;
        this.stats.acknowledgementMs = performance.now() - started;
        this.publish();
      } catch (error) {
        this.failed = true;
        this.fail(
          error instanceof Error ? error.message : String(error),
          "request_failed",
        );
        return;
      }
    }
  }
  async drain() {
    if (this.running) await this.running;
  }
}

export type CaptureController = {
  sessionId: string;
  stop: (reason?: string) => Promise<void>;
};
export async function startCapture(options: {
  base: string;
  kind: "audio" | "video" | "av";
  configuration: any;
  audioDevice: string;
  videoDevice: string;
  update: (stats: CaptureStats) => void;
  failed: (message: string) => void;
  signal: AbortSignal;
}): Promise<CaptureController> {
  const { base, kind, configuration: c, update, failed, signal } = options;
  const audio = kind !== "video",
    video = kind !== "audio";
  // Favor stable capture blocks over a minimal speaker-monitoring latency.
  const context = audio
    ? new AudioContext({
        latencyHint: "playback",
        ...("setSinkId" in AudioContext.prototype
          ? { sinkId: { type: "none" } }
          : {}),
      })
    : null;
  // Start these in the original click gesture, before network awaits.
  const resumed = context?.resume();
  let stream: MediaStream | null = null,
    node: AudioWorkletNode | null = null,
    element: HTMLVideoElement | null = null;
  let frameRequest: number | null = null,
    sessionId = "",
    queue: PacketQueue | null = null,
    closing = false;
  let stopped: () => void = () => {};
  let stopping: Promise<void> | null = null;
  let failureMessage = "采集已在启动期间中断。";
  const check = () => {
    if (signal.aborted) throw new DOMException("采集启动已取消", "AbortError");
  };
  const release = () => {
    stream?.getTracks().forEach((t) => t.stop());
    node?.disconnect();
    if (context && context.state !== "closed")
      void context.close().catch(() => {});
    if (element) element.srcObject = null;
  };
  const stop = (reason = "user_stopped"): Promise<void> => {
    if (stopping) return stopping;
    closing = true;
    stopping = (async () => {
      if (element && frameRequest !== null)
        element.cancelVideoFrameCallback(frameRequest);
      if (node) {
        const flushed = new Promise<void>((resolve) => {
          stopped = resolve;
        });
        node.port.postMessage("stop");
        await Promise.race([flushed, delay(1000)]);
      }
      release();
      await queue?.drain();
      if (sessionId)
        await api(`${base}/capture/${sessionId}/stop`, {
          method: "POST",
          body: JSON.stringify({ reason }),
        });
    })();
    return stopping;
  };
  const fail = (message: string, reason: string) => {
    failureMessage = message;
    failed(message);
    void stop(reason).catch(() => {});
  };
  try {
    if (!navigator.mediaDevices?.getUserMedia)
      throw new Error(
        t("浏览器未提供设备采集；请使用 HTTPS 或本机 localhost 工作站。"),
      );
    stream = await navigator.mediaDevices.getUserMedia({
      audio: audio
        ? {
            channelCount: 1,
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false,
            ...(options.audioDevice
              ? { deviceId: { exact: options.audioDevice } }
              : {}),
          }
        : false,
      video: video
        ? {
            width: { ideal: 640 },
            height: { ideal: 480 },
            frameRate: {
              ideal: Math.min(60, 1e6 / c.visual_sensor.frame_interval_us),
            },
            ...(options.videoDevice
              ? { deviceId: { exact: options.videoDevice } }
              : {}),
          }
        : false,
    });
    await resumed;
    check();
    sessionId = crypto.randomUUID();
    const sourceClock = {
      timeline: "browser performance clock; relative microseconds",
      audio: audio
        ? "Web Audio render frame clock, approximately mapped to browser time; ADC capture latency is unknown"
        : null,
      audio_render_latency_s: context?.baseLatency ?? null,
      audio_output:
        context && "setSinkId" in AudioContext.prototype
          ? "processing-only sink"
          : "silent output fallback",
      video: video
        ? "requestVideoFrameCallback captureTime when provided, otherwise presentationTime; browser sampling and resize"
        : null,
      submitted_pixels: video
        ? {
            width: c.visual_sensor.target_width,
            height: c.visual_sensor.target_height,
            components: 1,
            filter: "canvas resize, grayscale luminance",
          }
        : null,
      tracks: stream
        .getTracks()
        .map((track) => ({ kind: track.kind, settings: track.getSettings() })),
    };
    await api(`${base}/capture`, {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        kind,
        name:
          kind === "av" ? "音画联合采集" : audio ? "麦克风采集" : "摄像头采集",
        source_clock: sourceClock,
      }),
    });
    check();
    queue = new PacketQueue(
      `${base}/capture/${sessionId}/packets`,
      c.live_capture.max_pending_packets,
      update,
      fail,
    );
    const origin = performance.now(),
      audioAnchor = context?.currentTime ?? 0;
    stream.getTracks().forEach((track) =>
      track.addEventListener("ended", () => {
        if (!closing) {
          fail("设备已断开，采集结束。", "device_lost");
        }
      }),
    );
    if (context) {
      await context.audioWorklet.addModule("/capture-worklet.js");
      check();
      node = new AudioWorkletNode(context, "threemind-capture-v2", {
        channelCount: 1,
        channelCountMode: "explicit",
        processorOptions: {
          samplesPerPacket: Math.round(
            (c.live_capture.audio_packet_us * context.sampleRate) / 1e6,
          ),
        },
      });
      let firstFrame: number | null = null,
        firstUs = 0;
      node.port.onmessage = (event) => {
        const value = event.data;
        if (value.type === "stopped") {
          stopped();
          return;
        }
        if (value.type === "gap") {
          fail(value.reason, "capture_gap");
          return;
        }
        if (value.type !== "audio") return;
        if (firstFrame === null) {
          firstFrame = value.firstFrame;
          firstUs = Math.max(
            0,
            Math.round((firstFrame! / context.sampleRate - audioAnchor) * 1e6),
          );
        }
        const captureUs =
          firstUs +
          Math.round(
            ((value.firstFrame - firstFrame!) * 1e6) / context.sampleRate,
          );
        const samples = value.samples as Float32Array;
        queue!.enqueue((sequence) => {
          const { raw, view } = header(
            1,
            sequence,
            captureUs,
            33 + samples.byteLength,
            value.final,
            value.firstFrame,
            1,
          );
          view.setUint32(27, Math.round(context.sampleRate), true);
          view.setUint16(31, 1, true);
          for (let i = 0; i < samples.length; i++)
            view.setFloat32(33 + i * 4, samples[i], true);
          return raw;
        });
      };
      const source = context.createMediaStreamSource(stream),
        silent = context.createGain();
      silent.gain.value = 0;
      source.connect(node);
      node.connect(silent);
      silent.connect(context.destination);
    }
    if (video) {
      element = document.createElement("video");
      element.muted = true;
      element.playsInline = true;
      element.srcObject = stream;
      if (!element.requestVideoFrameCallback)
        throw new Error(
          t(
            "浏览器缺少逐画面采集接口，请使用支持 requestVideoFrameCallback 的浏览器。",
          ),
        );
      await element.play();
      check();
      const canvas = document.createElement("canvas");
      canvas.width = c.visual_sensor.target_width;
      canvas.height = c.visual_sensor.target_height;
      const pixels = canvas.getContext("2d", { willReadFrequently: true });
      if (!pixels) throw new Error(t("无法创建画面采集画布。"));
      let last = -Infinity,
        previousPresented = 0,
        previousSkipped = 0;
      const capture = (_now: number, metadata: VideoFrameCallbackMetadata) => {
        if (closing) return;
        const at = Number(
          (metadata as any).captureTime ?? metadata.presentationTime,
        );
        const captureUs = Math.max(0, Math.round((at - origin) * 1000));
        queue!.stats.videoSkipped += Math.max(
          0,
          metadata.presentedFrames - previousPresented - 1,
        );
        previousPresented = metadata.presentedFrames;
        if (captureUs - last >= c.visual_sensor.frame_interval_us) {
          last = captureUs;
          pixels.drawImage(element!, 0, 0, canvas.width, canvas.height);
          const rgba = pixels.getImageData(
            0,
            0,
            canvas.width,
            canvas.height,
          ).data;
          queue!.enqueue((sequence) => {
            const { raw, view } = header(
              2,
              sequence,
              captureUs,
              36 + canvas.width * canvas.height,
              false,
              metadata.presentedFrames,
              (metadata as any).captureTime != null ? 2 : 3,
            );
            view.setUint16(27, canvas.width, true);
            view.setUint16(29, canvas.height, true);
            view.setUint8(31, 1);
            view.setUint32(
              32,
              queue!.stats.videoSkipped - previousSkipped,
              true,
            );
            previousSkipped = queue!.stats.videoSkipped;
            for (let i = 0; i < canvas.width * canvas.height; i++)
              raw[36 + i] = Math.round(
                0.2126 * rgba[i * 4] +
                  0.7152 * rgba[i * 4 + 1] +
                  0.0722 * rgba[i * 4 + 2],
              );
            return raw;
          });
          queue!.stats.videoFrames++;
        } else queue!.stats.videoSkipped++;
        queue!.publish();
        if (!closing)
          frameRequest = element!.requestVideoFrameCallback(capture);
      };
      frameRequest = element.requestVideoFrameCallback(capture);
    }
    check();
    if (closing || queue.failed) throw new Error(failureMessage);
    return { sessionId, stop };
  } catch (error) {
    void resumed?.catch(() => {});
    await stop("request_failed").catch(() => {});
    throw error;
  }
}
