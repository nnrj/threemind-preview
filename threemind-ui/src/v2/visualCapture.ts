/** Browser-side observation export. Never sends commands or stimuli to a model. */
export type CaptureMetadata = {
  world?: string;
  generation?: string;
  time?: string;
  legend?: string;
};
export type CaptureOptions = {
  title: string;
  showTitle: boolean;
  showWorld: boolean;
  showGeneration: boolean;
  showTime: boolean;
  showLegend: boolean;
  fps: number;
  seconds: number;
};
export type CaptureSource = {
  draw: () => HTMLCanvasElement;
  metadata: () => CaptureMetadata;
};
export const defaultCaptureOptions: CaptureOptions = {
  title: "ThreeMind",
  showTitle: true,
  showWorld: true,
  showGeneration: true,
  showTime: true,
  showLegend: true,
  fps: 20,
  seconds: 30,
};

export function captureFrame(
  source: CaptureSource,
  options: CaptureOptions,
  target?: HTMLCanvasElement,
) {
  const frame = source.draw(),
    metadata = source.metadata();
  if (!frame.width || !frame.height) throw new Error("Canvas is not ready");
  const canvas = target ?? document.createElement("canvas");
  const enabled = [
    options.showTitle,
    options.showWorld,
    options.showGeneration,
    options.showTime,
    options.showLegend,
  ].filter(Boolean).length;
  const footer = enabled ? enabled * 26 + 20 : 0;
  const width = target?.width || Math.min(1920, frame.width),
    scale = width / frame.width;
  const lines = [
    options.showTitle && options.title,
    options.showWorld && metadata.world,
    options.showGeneration && metadata.generation,
    options.showTime && metadata.time,
    options.showLegend && metadata.legend,
  ].filter((value): value is string => !!value);
  // A fixed footer height keeps video resolution stable when metadata changes.
  const height = target?.height
    ? target.height - footer
    : Math.round(frame.height * scale);
  if (canvas.width !== width || canvas.height !== height + footer) {
    canvas.width = width;
    canvas.height = height + footer;
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("2D canvas unavailable");
  ctx.fillStyle = "#102b2b";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  const fit = Math.min(width / frame.width, height / frame.height);
  ctx.drawImage(
    frame,
    (width - frame.width * fit) / 2,
    (height - frame.height * fit) / 2,
    frame.width * fit,
    frame.height * fit,
  );
  ctx.fillStyle = "#e6f2eb";
  ctx.font = "15px system-ui, sans-serif";
  lines.forEach((text, index) =>
    ctx.fillText(text.slice(0, 400), 12, height + 24 + index * 26, width - 24),
  );
  return canvas;
}

export async function capturePng(
  source: CaptureSource,
  options: CaptureOptions,
): Promise<Blob> {
  const canvas = captureFrame(source, options);
  return new Promise((resolve, reject) =>
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("PNG export failed"))),
      "image/png",
    ),
  );
}

export function startVisualRecording(
  source: CaptureSource,
  options: CaptureOptions,
) {
  if (
    !Number.isFinite(options.fps) ||
    options.fps < 1 ||
    options.fps > 30 ||
    !Number.isFinite(options.seconds) ||
    options.seconds < 1 ||
    options.seconds > 300
  )
    throw new Error("Capture requires 1–30 fps and 1–300 seconds");
  if (typeof MediaRecorder === "undefined")
    throw new Error("This browser does not support video recording");
  const canvas = captureFrame(source, options),
    stream = canvas.captureStream(options.fps);
  const track = stream.getVideoTracks()[0] as
    CanvasCaptureMediaStreamTrack | undefined;
  // VP8 starts faster on workstation/mobile CPUs; VP9 can miss an entire short capture while initializing.
  const mimeType = [
    "video/webm;codecs=vp8",
    "video/webm;codecs=vp9",
    "video/webm",
  ].find((x) => MediaRecorder.isTypeSupported(x));
  if (!mimeType) {
    stream.getTracks().forEach((t) => t.stop());
    throw new Error("WebM encoder unavailable");
  }
  let recorder: MediaRecorder;
  try {
    recorder = new MediaRecorder(stream, {
      mimeType,
      videoBitsPerSecond: 4000000,
    });
  } catch (error) {
    stream.getTracks().forEach((t) => t.stop());
    throw error;
  }
  const chunks: Blob[] = [];
  let bytes = 0,
    raf = 0,
    timer = 0,
    last = -Infinity,
    failure: Error | null = null;
  const clean = () => {
    cancelAnimationFrame(raf);
    clearTimeout(timer);
    stream.getTracks().forEach((t) => t.stop());
  };
  const stop = () => {
    if (recorder.state !== "inactive") recorder.stop();
  };
  const finished = new Promise<Blob>((resolve, reject) => {
    recorder.ondataavailable = (event) => {
      if (event.data.size) {
        chunks.push(event.data);
        bytes += event.data.size;
      }
      if (bytes > 128 * 1024 * 1024) stop();
    };
    recorder.onerror = () => {
      failure = new Error("Video encoder failed");
      stop();
      clean();
      reject(failure);
    };
    recorder.onstop = () => {
      clean();
      if (failure) reject(failure);
      else if (!bytes)
        reject(
          new Error(
            "The browser produced no video frames; try a longer recording or MP4 export",
          ),
        );
      else resolve(new Blob(chunks, { type: mimeType }));
    };
  });
  const draw = (now: number) => {
    if (recorder.state !== "recording") return;
    try {
      if (now - last >= 1000 / options.fps) {
        captureFrame(source, options, canvas);
        track?.requestFrame?.();
        last = now;
      }
      raf = requestAnimationFrame(draw);
    } catch (error) {
      failure = error instanceof Error ? error : new Error(String(error));
      stop();
    }
  };
  try {
    recorder.start(1000);
  } catch (error) {
    clean();
    throw error;
  }
  track?.requestFrame?.();
  raf = requestAnimationFrame(draw);
  timer = window.setTimeout(stop, options.seconds * 1000);
  return { stop, finished };
}

export function downloadCapture(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob),
    link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
