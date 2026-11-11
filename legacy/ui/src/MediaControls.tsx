import { useEffect, useRef, useState } from "react";
import type { Locale } from "./i18n";

const API = (import.meta.env.VITE_THREEMIND_API as string | undefined)?.replace(/\/$/, "") ?? "";
const WS_API = API ? API.replace(/^http/, "ws") : `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}`;

type Feedback = (kind: "pending" | "success" | "error", message: string) => void;
type Props = { consciousnessId: string; intensity: number; disabled: boolean; locale: Locale; onFeedback: Feedback };
type InputConnection = { socket: WebSocket; config: Record<string, unknown> };
type OutputAdapterId = "acoustic-output-organ" | "activation-image-projector";
type OutputConnection = { socket: WebSocket };

function copy(locale: Locale, zh: string, en: string): string { return locale === "en" ? en : zh; }

function outputPreferenceKey(consciousnessId: string, adapterId: OutputAdapterId): string {
  return `threemind.media-output.${consciousnessId}.${adapterId}`;
}

function outputPreference(consciousnessId: string, adapterId: OutputAdapterId): boolean | null {
  try {
    const value = window.localStorage.getItem(outputPreferenceKey(consciousnessId, adapterId));
    return value === null ? null : value === "true";
  } catch {
    return null;
  }
}

function rememberOutputPreference(consciousnessId: string, adapterId: OutputAdapterId, enabled: boolean): void {
  try { window.localStorage.setItem(outputPreferenceKey(consciousnessId, adapterId), String(enabled)); } catch { /* Browser storage is optional. */ }
}

function audioPacket(sequence: number, timestamp: number, sampleRate: number, samples: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(19 + samples.length * 4); const view = new DataView(buffer);
  view.setUint8(0, 1); view.setUint32(1, sequence, true); view.setFloat64(5, timestamp, true);
  view.setUint32(13, sampleRate, true); view.setUint16(17, 1, true);
  for (let index = 0; index < samples.length; index += 1) view.setFloat32(19 + index * 4, samples[index], true);
  return buffer;
}

function videoPacket(sequence: number, timestamp: number, width: number, height: number, pixels: Uint8Array): ArrayBuffer {
  const buffer = new ArrayBuffer(18 + pixels.length); const view = new DataView(buffer);
  view.setUint8(0, 2); view.setUint32(1, sequence, true); view.setFloat64(5, timestamp, true);
  view.setUint16(13, width, true); view.setUint16(15, height, true); view.setUint8(17, 1);
  new Uint8Array(buffer, 18).set(pixels); return buffer;
}

async function responseDetail(response: Response): Promise<string> {
  const payload = await response.json().catch(() => ({})) as { detail?: string };
  return payload.detail ?? `${response.status} ${response.statusText}`;
}

export function MediaControls({ consciousnessId, intensity, disabled, locale, onFeedback }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [status, setStatus] = useState("");
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [microphoneActive, setMicrophoneActive] = useState(false);
  const [microphoneStarting, setMicrophoneStarting] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraStarting, setCameraStarting] = useState(false);
  const [soundActive, setSoundActive] = useState(false);
  const [soundConnected, setSoundConnected] = useState(false);
  const [soundStarting, setSoundStarting] = useState(false);
  const [imageActive, setImageActive] = useState(false);
  const [imageStarting, setImageStarting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const microphoneRef = useRef<{ socket: WebSocket; stream: MediaStream; context: AudioContext; node: AudioWorkletNode; url: string } | null>(null);
  const cameraRef = useRef<{ socket: WebSocket; stream: MediaStream; timer: number; video: HTMLVideoElement } | null>(null);
  const soundRef = useRef<{ socket: WebSocket; context: AudioContext } | null>(null);
  const imageSocketRef = useRef<WebSocket | null>(null);
  const imageCanvasRef = useRef<HTMLCanvasElement>(null);
  const sequenceRef = useRef({ audio: 0, video: 0 });
  const microphoneAttemptRef = useRef(0);
  const cameraAttemptRef = useRef(0);
  const microphoneStartingRef = useRef(false);
  const cameraStartingRef = useRef(false);
  const soundAttemptRef = useRef(0);
  const imageAttemptRef = useRef(0);
  const soundStartingRef = useRef(false);
  const imageStartingRef = useRef(false);

  const enableAdapter = async (adapterId: string, live = false): Promise<Record<string, unknown>> => {
    // Read before writing.  Re-enabling an already enabled output used to
    // rewrite the complete model package on every click, making a restored
    // page appear unresponsive for large consciousnesses.
    const [hostStateResponse, bindingsResponse] = await Promise.all([
      fetch(`${API}/api/adapters/${encodeURIComponent(adapterId)}`, { cache: "no-store" }),
      fetch(`${API}/api/consciousnesses/${encodeURIComponent(consciousnessId)}/adapters`, { cache: "no-store" }),
    ]);
    if (!hostStateResponse.ok) throw new Error(await responseDetail(hostStateResponse));
    if (!bindingsResponse.ok) throw new Error(await responseDetail(bindingsResponse));
    const hostState = await hostStateResponse.json() as { enabled?: boolean; config?: Record<string, unknown> };
    const bindingsPayload = await bindingsResponse.json() as { items?: { adapter_id?: string; enabled?: boolean; config?: Record<string, unknown> }[] };
    const currentBinding = (bindingsPayload.items ?? []).find((item) => item.adapter_id === adapterId);
    const hostLive = Boolean(hostState.config?.live_enabled);
    const bindingLive = Boolean(currentBinding?.config?.live_enabled);
    if (!hostState.enabled || (live && !hostLive)) {
      const host = await fetch(`${API}/api/adapters/${encodeURIComponent(adapterId)}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: true, ...(live ? { config: { live_enabled: true } } : {}) }),
      });
      if (!host.ok) throw new Error(await responseDetail(host));
    }
    if (!currentBinding?.enabled || (live && !bindingLive)) {
      const binding = await fetch(`${API}/api/consciousnesses/${encodeURIComponent(consciousnessId)}/adapters/${encodeURIComponent(adapterId)}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: true, ...(live ? { config: { live_enabled: true } } : {}) }),
      });
      if (!binding.ok) throw new Error(await responseDetail(binding));
      const payload = await binding.json() as { binding?: { config?: Record<string, unknown> } };
      return payload.binding?.config ?? {};
    }
    return currentBinding.config ?? {};
  };

  const pollSession = (sessionId: string) => {
    const timer = window.setInterval(() => {
      void fetch(`${API}/api/media/sessions/${encodeURIComponent(sessionId)}`, { cache: "no-store" })
        .then(async (response) => { if (!response.ok) throw new Error(await responseDetail(response)); return response.json(); })
        .then((session: { state: string; progress: number; frames_encoded: number; error?: string }) => {
          setUploadProgress(Math.round(Number(session.progress ?? 0) * 100));
          setStatus(copy(locale, `媒体处理：${session.state} · ${session.frames_encoded ?? 0} 个匿名帧`, `Media: ${session.state} · ${session.frames_encoded ?? 0} anonymous frames`));
          if (["queued", "failed", "cancelled"].includes(session.state)) {
            window.clearInterval(timer); setUploadProgress(null);
            if (session.state === "queued") onFeedback("success", copy(locale, "媒体刺激已完整进入 InputBus 队列。", "The media stimulus has entered the InputBus queue."));
            else onFeedback("error", session.error ?? copy(locale, "媒体处理失败。", "Media processing failed."));
          }
        })
        .catch((error: Error) => { window.clearInterval(timer); setUploadProgress(null); onFeedback("error", error.message); });
    }, 700);
  };

  const upload = async (file: File) => {
    const suffix = file.name.split(".").pop()?.toLocaleLowerCase() ?? "";
    const adapterId = file.type.startsWith("audio/") || ["wav", "wave", "mp3", "ogg", "flac", "m4a", "aac"].includes(suffix)
      ? "auditory-sensor"
      : "visual-sensor";
    try {
      setMenuOpen(false); setUploadProgress(0);
      onFeedback("pending", copy(locale, "正在保存并编码媒体刺激…", "Saving and encoding the media stimulus…"));
      await enableAdapter(adapterId);
      const form = new FormData(); form.append("file", file);
      const payload = await new Promise<{ session: { session_id: string } }>((resolve, reject) => {
        const request = new XMLHttpRequest();
        request.open("POST", `${API}/api/media/uploads?consciousness_id=${encodeURIComponent(consciousnessId)}&intensity=${encodeURIComponent(String(intensity))}`);
        request.upload.onprogress = (event) => { if (event.lengthComputable) setUploadProgress(Math.round(event.loaded / event.total * 35)); };
        request.onerror = () => reject(new Error(copy(locale, "媒体上传连接失败。", "Media upload connection failed.")));
        request.onload = () => {
          const parsed = (() => { try { return JSON.parse(request.responseText); } catch { return {}; } })() as { detail?: string; session?: { session_id: string } };
          if (request.status < 200 || request.status >= 300 || !parsed.session) reject(new Error(parsed.detail ?? `HTTP ${request.status}`));
          else resolve(parsed as { session: { session_id: string } });
        };
        request.send(form);
      });
      setStatus(copy(locale, `已接收 ${file.name}，正在进行非语义编码。`, `${file.name} received; non-semantic encoding is running.`));
      pollSession(payload.session.session_id);
    } catch (error) {
      setUploadProgress(null); onFeedback("error", error instanceof Error ? error.message : copy(locale, "媒体上传失败。", "Media upload failed."));
    }
  };

  const openInputSocket = async (adapterId: "auditory-sensor" | "visual-sensor"): Promise<InputConnection> => {
    const socket = new WebSocket(`${WS_API}/api/media/input/${encodeURIComponent(consciousnessId)}/${adapterId}`);
    socket.binaryType = "arraybuffer";
    const config = await new Promise<Record<string, unknown>>((resolve, reject) => {
      let settled = false;
      const fail = (error: Error) => {
        if (settled) return;
        settled = true; window.clearTimeout(timeout); socket.close(); reject(error);
      };
      const timeout = window.setTimeout(() => fail(new Error(copy(locale, "实时感官连接超时。", "Live sensory connection timed out."))), 8000);
      socket.onopen = () => socket.send(JSON.stringify({ protocol: "threemind-media/1", type: "hello", intensity }));
      socket.onmessage = (event) => {
        let message: { type?: string; detail?: string; config?: Record<string, unknown> } = {};
        try { message = JSON.parse(String(event.data)) as { type?: string; detail?: string; config?: Record<string, unknown> }; }
        catch { fail(new Error(copy(locale, "实时感官连接返回了无效数据。", "The live sensory connection returned invalid data."))); return; }
        if (message.type === "ready" && !settled) { settled = true; window.clearTimeout(timeout); resolve(message.config ?? {}); }
        if (message.type === "error") fail(new Error(message.detail ?? "media error"));
      };
      socket.onerror = () => fail(new Error(copy(locale, "实时感官连接失败。", "Live sensory connection failed.")));
      socket.onclose = () => fail(new Error(copy(locale, "实时感官连接在就绪前关闭。", "The live sensory connection closed before it was ready.")));
    });
    if (socket.readyState !== WebSocket.OPEN) {
      throw new Error(copy(locale, "实时感官连接已关闭，请重试。", "The live sensory connection closed; please try again."));
    }
    return { socket, config };
  };

  const openOutputSocket = async (adapterId: OutputAdapterId): Promise<OutputConnection> => {
    const socket = new WebSocket(`${WS_API}/api/media/output/${encodeURIComponent(consciousnessId)}/${adapterId}`);
    await new Promise<void>((resolve, reject) => {
      let settled = false;
      const fail = (error: Error) => {
        if (settled) return;
        settled = true; window.clearTimeout(timeout); socket.close(); reject(error);
      };
      const timeout = window.setTimeout(() => fail(new Error(copy(locale, "媒体输出连接超时。", "Media output connection timed out."))), 8000);
      socket.onmessage = (event) => {
        let message: { type?: string; detail?: string } = {};
        try { message = JSON.parse(String(event.data)) as { type?: string; detail?: string }; }
        catch { fail(new Error(copy(locale, "媒体输出返回了无效数据。", "The media output returned invalid data."))); return; }
        if (message.type === "ready" && !settled) { settled = true; window.clearTimeout(timeout); resolve(); }
        else if (message.type === "error") fail(new Error(message.detail ?? "media output error"));
      };
      socket.onerror = () => fail(new Error(copy(locale, "媒体输出连接失败。", "Media output connection failed.")));
      socket.onclose = () => fail(new Error(copy(locale, "媒体输出连接在就绪前关闭。", "The media output connection closed before it was ready.")));
    });
    return { socket };
  };

  const stopMicrophone = () => {
    microphoneAttemptRef.current += 1;
    microphoneStartingRef.current = false;
    const active = microphoneRef.current; microphoneRef.current = null;
    if (active) { if (active.socket.readyState === WebSocket.OPEN) active.socket.send(JSON.stringify({ type: "stop" })); active.socket.close(); active.stream.getTracks().forEach((track) => track.stop()); active.node.disconnect(); void active.context.close(); URL.revokeObjectURL(active.url); }
    setMicrophoneActive(false); setMicrophoneStarting(false);
  };

  const startMicrophone = async () => {
    if (microphoneRef.current) { stopMicrophone(); return; }
    if (microphoneStartingRef.current) return;
    microphoneStartingRef.current = true;
    const attempt = ++microphoneAttemptRef.current;
    setMenuOpen(false);
    setMicrophoneStarting(true);
    let socket: WebSocket | null = null; let stream: MediaStream | null = null;
    let context: AudioContext | null = null; let node: AudioWorkletNode | null = null; let url = "";
    try {
      onFeedback("pending", copy(locale, "正在请求麦克风并建立听觉通道…", "Requesting the microphone and opening the auditory channel…"));
      // AudioContext.resume() must begin in the original click gesture.  If it
      // is postponed until after HTTP/WebSocket awaits, browsers may leave the
      // context suspended while the server already owns a live session.
      const audioContext = new AudioContext(); context = audioContext;
      const resumePromise = audioContext.resume();
      const streamPromise = navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false }, video: false });
      const capturedStream = await streamPromise;
      stream = capturedStream;
      await resumePromise;
      await enableAdapter("auditory-sensor", true);
      if (attempt !== microphoneAttemptRef.current) throw new DOMException("microphone start cancelled", "AbortError");
      const sourceCode = `class ThreeMindCapture extends AudioWorkletProcessor { process(inputs) { const input=inputs[0]&&inputs[0][0]; if(input&&input.length){const copy=new Float32Array(input);this.port.postMessage(copy,[copy.buffer]);} return true; } } registerProcessor('threemind-capture',ThreeMindCapture);`;
      url = URL.createObjectURL(new Blob([sourceCode], { type: "text/javascript" }));
      await audioContext.audioWorklet.addModule(url);
      if (attempt !== microphoneAttemptRef.current) throw new DOMException("microphone start cancelled", "AbortError");
      const workletNode = new AudioWorkletNode(audioContext, "threemind-capture"); node = workletNode;
      const source = audioContext.createMediaStreamSource(capturedStream); const silent = audioContext.createGain(); silent.gain.value = 0;
      source.connect(workletNode); workletNode.connect(silent); silent.connect(audioContext.destination);
      const connection = await openInputSocket("auditory-sensor"); socket = connection.socket;
      if (attempt !== microphoneAttemptRef.current) throw new DOMException("microphone start cancelled", "AbortError");
      workletNode.port.onmessage = (event: MessageEvent<Float32Array>) => {
        if (connection.socket.readyState !== WebSocket.OPEN) return;
        connection.socket.send(audioPacket(++sequenceRef.current.audio, performance.now(), Math.round(audioContext.sampleRate), new Float32Array(event.data)));
      };
      microphoneRef.current = { socket: connection.socket, stream: capturedStream, context: audioContext, node: workletNode, url };
      connection.socket.onclose = () => { if (microphoneRef.current?.socket === connection.socket) stopMicrophone(); };
      microphoneStartingRef.current = false;
      setMicrophoneActive(true); setMicrophoneStarting(false);
      onFeedback("success", copy(locale, "麦克风听觉通道已开启；原始声音不会持久化。", "The auditory channel is live; raw microphone audio is not retained."));
    } catch (error) {
      node?.disconnect(); stream?.getTracks().forEach((track) => track.stop()); socket?.close();
      if (context) void context.close(); if (url) URL.revokeObjectURL(url);
      if (attempt === microphoneAttemptRef.current) {
        microphoneStartingRef.current = false;
        setMicrophoneActive(false); setMicrophoneStarting(false);
        onFeedback("error", error instanceof Error ? error.message : copy(locale, "无法开启麦克风。", "Unable to start the microphone."));
      }
    }
  };

  const stopCamera = () => {
    cameraAttemptRef.current += 1;
    cameraStartingRef.current = false;
    const active = cameraRef.current; cameraRef.current = null;
    if (active) { if (active.socket.readyState === WebSocket.OPEN) active.socket.send(JSON.stringify({ type: "stop" })); active.socket.close(); active.stream.getTracks().forEach((track) => track.stop()); window.clearInterval(active.timer); active.video.srcObject = null; }
    setCameraActive(false); setCameraStarting(false);
  };

  const startCamera = async () => {
    if (cameraRef.current) { stopCamera(); return; }
    if (cameraStartingRef.current) return;
    cameraStartingRef.current = true;
    const attempt = ++cameraAttemptRef.current;
    setMenuOpen(false);
    setCameraStarting(true);
    let socket: WebSocket | null = null; let stream: MediaStream | null = null;
    let timer: number | null = null; let video: HTMLVideoElement | null = null;
    try {
      onFeedback("pending", copy(locale, "正在请求摄像头并建立视觉通道…", "Requesting the camera and opening the visual channel…"));
      const adapterConfig = await enableAdapter("visual-sensor", true);
      if (attempt !== cameraAttemptRef.current) throw new DOMException("camera start cancelled", "AbortError");
      const configuredWidth = Number(adapterConfig.target_width ?? 24);
      const configuredHeight = Number(adapterConfig.target_height ?? 16);
      const configuredRate = Number(adapterConfig.sensory_frame_rate ?? 6);
      const width = Math.max(2, Math.min(256, Math.round(configuredWidth)));
      const height = Math.max(2, Math.min(256, Math.round(configuredHeight)));
      const frameRate = Math.max(.2, Math.min(60, configuredRate));
      const capturedStream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: Math.max(320, width) }, height: { ideal: Math.max(240, height) }, frameRate: { ideal: frameRate, max: frameRate } }, audio: false });
      stream = capturedStream;
      if (attempt !== cameraAttemptRef.current) throw new DOMException("camera start cancelled", "AbortError");
      const videoElement = document.createElement("video"); video = videoElement; videoElement.muted = true; videoElement.playsInline = true; videoElement.srcObject = capturedStream; await videoElement.play();
      if (attempt !== cameraAttemptRef.current) throw new DOMException("camera start cancelled", "AbortError");
      const canvas = document.createElement("canvas"); canvas.width = width; canvas.height = height;
      const context = canvas.getContext("2d", { willReadFrequently: true }); if (!context) throw new Error("2D canvas unavailable");
      const connection = await openInputSocket("visual-sensor"); socket = connection.socket;
      if (attempt !== cameraAttemptRef.current) throw new DOMException("camera start cancelled", "AbortError");
      timer = window.setInterval(() => {
        if (connection.socket.readyState !== WebSocket.OPEN || videoElement.readyState < 2) return;
        context.drawImage(videoElement, 0, 0, width, height); const rgba = context.getImageData(0, 0, width, height).data; const gray = new Uint8Array(width * height);
        for (let index = 0; index < gray.length; index += 1) { const offset = index * 4; gray[index] = Math.round(.2126 * rgba[offset] + .7152 * rgba[offset + 1] + .0722 * rgba[offset + 2]); }
        connection.socket.send(videoPacket(++sequenceRef.current.video, performance.now(), width, height, gray));
      }, 1000 / frameRate);
      cameraRef.current = { socket: connection.socket, stream: capturedStream, timer, video: videoElement };
      connection.socket.onclose = () => { if (cameraRef.current?.socket === connection.socket) stopCamera(); };
      cameraStartingRef.current = false;
      setCameraActive(true); setCameraStarting(false);
      onFeedback("success", copy(locale, "摄像头视觉通道已开启；原始画面不会持久化。", "The visual channel is live; raw camera frames are not retained."));
    } catch (error) {
      if (timer !== null) window.clearInterval(timer); if (video) video.srcObject = null;
      stream?.getTracks().forEach((track) => track.stop()); socket?.close();
      if (attempt === cameraAttemptRef.current) {
        cameraStartingRef.current = false;
        setCameraActive(false); setCameraStarting(false);
        onFeedback("error", error instanceof Error ? error.message : copy(locale, "无法开启摄像头。", "Unable to start the camera."));
      }
    }
  };

  const stopSound = (remember = false) => {
    soundAttemptRef.current += 1;
    soundStartingRef.current = false;
    const active = soundRef.current; soundRef.current = null;
    if (active) { active.socket.close(); void active.context.close(); }
    setSoundActive(false); setSoundConnected(false); setSoundStarting(false);
    if (remember) rememberOutputPreference(consciousnessId, "acoustic-output-organ", false);
  };

  const connectSound = async (automatic = false) => {
    if (soundRef.current || soundStartingRef.current) return;
    soundStartingRef.current = true;
    const attempt = ++soundAttemptRef.current;
    setSoundStarting(true);
    let context: AudioContext | null = null; let socket: WebSocket | null = null;
    try {
      if (!automatic) onFeedback("pending", copy(locale, "正在开启声音输出…", "Opening acoustic output…"));
      // AudioContext creation/resume must begin inside the original click.
      // Waiting for adapter HTTP calls first loses browser user activation
      // after a reload and can leave resume() pending forever.
      const audioContext = new AudioContext(); context = audioContext;
      const resumePromise = automatic ? Promise.resolve() : audioContext.resume();
      await enableAdapter("acoustic-output-organ");
      await resumePromise;
      if (attempt !== soundAttemptRef.current) throw new DOMException("sound start cancelled", "AbortError");
      const connection = await openOutputSocket("acoustic-output-organ"); socket = connection.socket;
      if (attempt !== soundAttemptRef.current) throw new DOMException("sound start cancelled", "AbortError");
      connection.socket.onmessage = (event) => {
        const message = JSON.parse(String(event.data)) as { type?: string; detail?: string; voices?: { frequency: number; amplitude: number }[] };
        if (message.type === "error") { onFeedback("error", message.detail ?? "output error"); stopSound(); return; }
        if (message.type !== "audio-control" || audioContext.state !== "running") return;
        const now = audioContext.currentTime;
        for (const voice of (message.voices ?? []).slice(0, 12)) {
          const oscillator = audioContext.createOscillator(); const gain = audioContext.createGain();
          oscillator.frequency.value = Math.max(20, Math.min(12000, voice.frequency)); gain.gain.setValueAtTime(0, now);
          gain.gain.linearRampToValueAtTime(Math.min(.035, Math.max(0, voice.amplitude) * .035), now + .01); gain.gain.exponentialRampToValueAtTime(.0001, now + .09);
          oscillator.connect(gain); gain.connect(audioContext.destination); oscillator.start(now); oscillator.stop(now + .1);
        }
      };
      connection.socket.onerror = () => onFeedback("error", copy(locale, "声音输出连接失败。", "Acoustic output connection failed."));
      connection.socket.onclose = () => { if (soundRef.current?.socket === connection.socket) stopSound(); };
      soundRef.current = { socket: connection.socket, context: audioContext };
      soundStartingRef.current = false;
      setSoundConnected(true); setSoundActive(audioContext.state === "running"); setSoundStarting(false);
      rememberOutputPreference(consciousnessId, "acoustic-output-organ", true);
      if (!automatic) onFeedback("success", copy(locale, "声音输出已开启。", "Acoustic output is active."));
    } catch (error) {
      socket?.close(); if (context) void context.close();
      if (attempt === soundAttemptRef.current) {
        soundStartingRef.current = false;
        setSoundConnected(false); setSoundActive(false); setSoundStarting(false);
        if (!automatic) onFeedback("error", error instanceof Error ? error.message : "output failed");
      }
    }
  };

  const toggleSound = async () => {
    const active = soundRef.current;
    if (active) {
      if (active.context.state !== "running") {
        try {
          setSoundStarting(true);
          await active.context.resume();
          if ((active.context.state as AudioContextState) !== "running") throw new Error(copy(locale, "浏览器仍在阻止声音播放。", "The browser is still blocking audio playback."));
          setSoundActive(true); setSoundStarting(false);
          onFeedback("success", copy(locale, "声音输出已恢复。", "Acoustic output resumed."));
        } catch (error) {
          setSoundStarting(false);
          onFeedback("error", error instanceof Error ? error.message : copy(locale, "无法恢复声音输出。", "Unable to resume acoustic output."));
        }
        return;
      }
      stopSound(true); return;
    }
    await connectSound(false);
  };

  const stopImage = (remember = false) => {
    imageAttemptRef.current += 1;
    imageStartingRef.current = false;
    imageSocketRef.current?.close(); imageSocketRef.current = null;
    setImageActive(false); setImageStarting(false);
    if (remember) rememberOutputPreference(consciousnessId, "activation-image-projector", false);
  };

  const connectImage = async (automatic = false) => {
    if (imageSocketRef.current || imageStartingRef.current) return;
    imageStartingRef.current = true;
    const attempt = ++imageAttemptRef.current;
    setImageStarting(true);
    let socket: WebSocket | null = null;
    try {
      if (!automatic) onFeedback("pending", copy(locale, "正在开启图像读出…", "Opening image readout…"));
      await enableAdapter("activation-image-projector");
      if (attempt !== imageAttemptRef.current) throw new DOMException("image output start cancelled", "AbortError");
      const connection = await openOutputSocket("activation-image-projector"); socket = connection.socket;
      if (attempt !== imageAttemptRef.current) throw new DOMException("image output start cancelled", "AbortError");
      connection.socket.onmessage = (event) => {
        const message = JSON.parse(String(event.data)) as { type?: string; detail?: string; width?: number; height?: number; pixels?: string };
        if (message.type === "error") { onFeedback("error", message.detail ?? "output error"); stopImage(); return; }
        if (message.type !== "image-frame" || !message.pixels || !message.width || !message.height) return;
        const canvas = imageCanvasRef.current; const context = canvas?.getContext("2d"); if (!canvas || !context) return;
        canvas.width = message.width; canvas.height = message.height; const raw = atob(message.pixels); const image = context.createImageData(message.width, message.height);
        for (let index = 0; index < raw.length; index += 1) { const value = raw.charCodeAt(index); image.data[index * 4] = value; image.data[index * 4 + 1] = value; image.data[index * 4 + 2] = value; image.data[index * 4 + 3] = 255; }
        context.putImageData(image, 0, 0);
      };
      connection.socket.onerror = () => onFeedback("error", copy(locale, "图像读出连接失败。", "Image readout connection failed."));
      connection.socket.onclose = () => { if (imageSocketRef.current === connection.socket) stopImage(); };
      imageSocketRef.current = connection.socket;
      imageStartingRef.current = false;
      setImageActive(true); setImageStarting(false);
      rememberOutputPreference(consciousnessId, "activation-image-projector", true);
      if (!automatic) onFeedback("success", copy(locale, "图像读出已开启。", "Image readout is active."));
    } catch (error) {
      socket?.close();
      if (attempt === imageAttemptRef.current) {
        imageStartingRef.current = false;
        setImageActive(false); setImageStarting(false);
        if (!automatic) onFeedback("error", error instanceof Error ? error.message : "output failed");
      }
    }
  };

  const toggleImage = async () => {
    if (imageSocketRef.current) { stopImage(true); return; }
    await connectImage(false);
  };

  useEffect(() => {
    let cancelled = false;
    const restore = async () => {
      try {
        const response = await fetch(`${API}/api/consciousnesses/${encodeURIComponent(consciousnessId)}/adapters`, { cache: "no-store" });
        if (!response.ok) return;
        const payload = await response.json() as { items?: { adapter_id?: string; enabled?: boolean }[] };
        if (cancelled) return;
        const enabled = new Set((payload.items ?? []).filter((item) => item.enabled).map((item) => item.adapter_id));
        const restoreSound = outputPreference(consciousnessId, "acoustic-output-organ");
        const restoreImage = outputPreference(consciousnessId, "activation-image-projector");
        // A missing preference is the migration path from the first media
        // release: an explicitly enabled model binding is restored once.
        const restorations: Promise<void>[] = [];
        if ((restoreSound ?? enabled.has("acoustic-output-organ")) && !cancelled) restorations.push(connectSound(true));
        if ((restoreImage ?? enabled.has("activation-image-projector")) && !cancelled) restorations.push(connectImage(true));
        await Promise.allSettled(restorations);
      } catch {
        // Restoration is best-effort. Manual buttons still report actionable
        // errors and can establish a fresh session.
      }
    };
    void restore();
    return () => {
      cancelled = true;
      stopMicrophone(); stopCamera(); stopSound(); stopImage();
    };
  }, [consciousnessId]);

  return <div className="media-controls">
    <input ref={fileRef} type="file" hidden accept="audio/*,image/*,video/*" onChange={(event) => { const file = event.target.files?.[0]; event.currentTarget.value = ""; if (file) void upload(file); }} />
    <div className="media-toolbar">
      <div className="media-add-wrap">
        <button className="media-add" type="button" disabled={disabled} aria-haspopup="menu" aria-expanded={menuOpen} title={copy(locale, "添加媒体刺激", "Add media stimulus")} onClick={() => setMenuOpen((value) => !value)}>＋</button>
        {menuOpen && <div className="media-menu" role="menu">
          <button type="button" role="menuitem" onClick={() => fileRef.current?.click()}>{copy(locale, "上传图像、音频或视频", "Upload image, audio, or video")}</button>
          <button type="button" role="menuitem" disabled={microphoneStarting} onClick={() => void startMicrophone()}>{microphoneStarting ? copy(locale, "正在开启麦克风…", "Starting microphone…") : microphoneActive ? copy(locale, "停止麦克风", "Stop microphone") : copy(locale, "开启麦克风（耳朵）", "Start microphone (ear)")}</button>
          <button type="button" role="menuitem" disabled={cameraStarting} onClick={() => void startCamera()}>{cameraStarting ? copy(locale, "正在开启摄像头…", "Starting camera…") : cameraActive ? copy(locale, "停止摄像头", "Stop camera") : copy(locale, "开启摄像头（眼睛）", "Start camera (eye)")}</button>
        </div>}
      </div>
      <button type="button" className={microphoneActive || microphoneStarting ? "active" : ""} aria-pressed={microphoneActive} aria-busy={microphoneStarting} disabled={disabled || microphoneStarting} onClick={() => void startMicrophone()}>🎙 {copy(locale, "耳朵", "Ear")}{microphoneStarting ? "…" : ""}</button>
      <button type="button" className={cameraActive || cameraStarting ? "active" : ""} aria-pressed={cameraActive} aria-busy={cameraStarting} disabled={disabled || cameraStarting} onClick={() => void startCamera()}>◉ {copy(locale, "眼睛", "Eye")}{cameraStarting ? "…" : ""}</button>
      <span className="media-toolbar-separator" />
      <button
        type="button"
        className={soundActive ? "active" : soundConnected ? "media-ready" : ""}
        aria-pressed={soundActive}
        aria-busy={soundStarting}
        title={soundConnected && !soundActive ? copy(locale, "输出连接已恢复；点击允许浏览器播放声音", "Output restored; click to allow browser audio") : undefined}
        disabled={disabled || soundStarting}
        onClick={() => void toggleSound()}
      >♪ {copy(locale, "嘴巴", "Mouth")}{soundStarting ? "…" : soundConnected && !soundActive ? " ·" : ""}</button>
      <button
        type="button"
        className={imageActive ? "active" : ""}
        aria-pressed={imageActive}
        aria-busy={imageStarting}
        disabled={disabled || imageStarting}
        onClick={() => void toggleImage()}
      >▣ {copy(locale, "图像读出", "Image readout")}{imageStarting ? "…" : ""}</button>
    </div>
    {(status || uploadProgress !== null) && <div className="media-status" role="status"><span>{status}</span>{uploadProgress !== null && <progress max={100} value={uploadProgress} />}</div>}
    <canvas ref={imageCanvasRef} className={`activation-image-output ${imageActive ? "visible" : ""}`} aria-label={copy(locale, "匿名激活图像读出", "Anonymous activation image readout")} />
  </div>;
}
