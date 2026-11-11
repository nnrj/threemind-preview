import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Mic,
  Camera,
  Volume2,
  Image as ImageIcon,
  FileAudio,
  FileVideo,
  Plus,
} from "lucide-react";
import { api, type Run } from "./api";
import { t } from "./i18n";
import { can } from "./access";
import { Button, ErrorBox, Modal, useWorkspace } from "./ui";
import {
  startCapture,
  type CaptureController,
  type CaptureStats,
} from "./captureClient";
import { Sonifier } from "./organMonitor";
import { MediaInput, Projection } from "./media";

type Control = "ear" | "eye" | "mouth" | "image";
type Status = "off" | "starting" | "on" | "stopping" | "failed";
const names = { ear: "耳朵", eye: "眼睛", mouth: "嘴巴", image: "图像读出" };
const labels = {
  off: "已关闭",
  starting: "开启中",
  on: "已开启",
  stopping: "关闭中",
  failed: "失败",
};

export async function setOrgan(
  base: string,
  control: string,
  enabled: boolean,
  signal?: AbortSignal,
) {
  let result = await api(`${base}/organ-controls`, {
    method: "POST",
    body: JSON.stringify({ control, enabled }),
    signal,
  });
  const command = result.command_id;
  const deadline = performance.now() + 30_000;
  while (result.status !== "applied") {
    signal?.throwIfAborted();
    if (
      performance.now() > deadline ||
      ["blocked", "failed", "cancelled"].includes(result.run_status)
    )
      throw new Error(t("设置尚未生效，请检查工作进程；命令记录已保留。"));
    await new Promise((resolve) => setTimeout(resolve, 150));
    result = await api(`${base}/organ-controls/${command}`, { signal });
  }
  return result;
}

export default function ChatOrgans({
  base,
  run,
  intensity = 1,
}: {
  base: string;
  run: Run;
  intensity?: number;
}) {
  const client = useQueryClient();
  const { project, user } = useWorkspace();
  const [states, setStates] = useState<Record<Control, Status>>({
    ear: "off",
    eye: "off",
    mouth: "off",
    image: "off",
  });
  const [error, setError] = useState<unknown>(null),
    [notice, setNotice] = useState("");
  const [captureStats, setCaptureStats] = useState<
    Partial<Record<Control, CaptureStats>>
  >({});
  const [upload, setUpload] = useState<string | null>(null),
    [uploadBusy, setUploadBusy] = useState(false);
  const [mediaMenu, setMediaMenu] = useState(false);
  const [spec, setSpec] = useState(run.spec),
    [frame, setFrame] = useState<any>(null);
  const registry = useQuery({
    queryKey: ["sensory-registry", run.id],
    queryFn: () => api(`${base}/sensory`),
    enabled: !!upload,
  });
  const captures = useRef<Partial<Record<Control, CaptureController>>>({});
  const pending = useRef<Partial<Record<Control | "upload", AbortController>>>(
    {},
  );
  const currentStates = useRef(states);
  currentStates.current = states;
  const player = useRef<Sonifier | null>(null),
    connection = useRef<EventSource | null>(null);
  const alive = useRef(true),
    lastAudio = useRef(0),
    audioAllowance = useRef(5000);
  const state = (key: Control, value: Status) => {
    if (!alive.current) return;
    currentStates.current = { ...currentStates.current, [key]: value };
    setStates((s) => ({ ...s, [key]: value }));
    if (
      ["off", "failed"].includes(value) &&
      (key === "mouth" || key === "image") &&
      ![currentStates.current.mouth, currentStates.current.image].some((s) =>
        ["on", "starting"].includes(s),
      )
    ) {
      connection.current?.close();
      connection.current = null;
    }
  };
  const allowed =
    ["running", "queued", "paused", "blocked"].includes(run.status) &&
    run.life !== "dead" &&
    !run.spec.study_id &&
    project?.role !== "viewer" &&
    can(user, "runs.configure");
  useEffect(() => {
    setSpec(run.spec);
  }, [run.spec]);
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ["run", run.id] });
    void client.invalidateQueries({ queryKey: ["runs"] });
  };
  const localStop = (key: Control) => {
    pending.current[key]?.abort();
    delete pending.current[key];
    if (key === "mouth") {
      player.current?.close();
      player.current = null;
    }
    if (key === "image") setFrame(null);
    const capture = captures.current[key];
    delete captures.current[key];
    if (capture) void capture.stop("page_left").catch(() => {});
  };
  useEffect(() => {
    alive.current = true;
    const watchdog = setInterval(() => {
      if (
        player.current &&
        lastAudio.current &&
        performance.now() - lastAudio.current > audioAllowance.current
      ) {
        player.current.close();
        player.current = null;
        state("mouth", "failed");
        setError(new Error(t("声音输出已超时，请重新开启嘴巴。")));
      }
    }, 500);
    return () => {
      alive.current = false;
      Object.values(pending.current).forEach((p) => p?.abort());
      Object.values(captures.current).forEach((c) => {
        void c?.stop("page_left").catch(() => {});
      });
      player.current?.close();
      connection.current?.close();
      clearInterval(watchdog);
    };
  }, [base]);
  useEffect(() => {
    if (!["running", "queued"].includes(run.status)) {
      for (const key of ["ear", "eye", "mouth", "image"] as Control[]) {
        localStop(key);
        state(key, "off");
      }
      connection.current?.close();
      connection.current = null;
    }
  }, [run.status]);

  const followOutput = () => {
    if (connection.current) return;
    const source = new EventSource(`/api/v2${base}/organs/monitor`);
    connection.current = source;
    source.addEventListener("output", (event) => {
      if (connection.current !== source) return;
      try {
        const value = JSON.parse((event as MessageEvent).data);
        for (const record of value.frames) {
          if (
            record.payload.image &&
            ["on", "starting"].includes(currentStates.current.image)
          )
            setFrame({ image: record.payload.image, at: record.time_us });
          if (record.payload.voices && player.current && value.enabled.audio) {
            player.current.update(record.payload.voices);
            lastAudio.current = performance.now();
            audioAllowance.current = Math.max(
              5000,
              (Number(
                record.payload.configuration?.acoustic_output
                  ?.output_interval_us ?? 100000,
              ) /
                1000) *
                2 +
                2000,
            );
          }
        }
        if (!value.enabled.audio && currentStates.current.mouth === "on") {
          localStop("mouth");
          state("mouth", "off");
        }
        if (!value.enabled.image && currentStates.current.image === "on") {
          localStop("image");
          state("image", "off");
        }
      } catch (e) {
        setError(e);
        source.close();
        connection.current = null;
        localStop("mouth");
        state("mouth", "failed");
      }
    });
    const lost = () => {
      source.close();
      if (connection.current !== source) return;
      connection.current = null;
      for (const key of ["mouth", "image"] as Control[])
        if (currentStates.current[key] === "on") {
          localStop(key);
          state(key, "failed");
        }
      setError(new Error(t("器官输出连接中断，可重新开启。")));
    };
    source.addEventListener("ended", lost);
    source.onerror = lost;
  };
  const toggle = async (key: Control) => {
    const enable = !["on", "starting"].includes(currentStates.current[key]);
    const previous = pending.current[key];
    previous?.abort();
    const attempt = new AbortController();
    pending.current[key] = attempt;
    const current = () =>
      alive.current &&
      pending.current[key] === attempt &&
      !attempt.signal.aborted;
    state(key, enable ? "starting" : "stopping");
    setError(null);
    try {
      // Create/resume audio in the user gesture, before waiting for network I/O.
      if (key === "mouth") {
        player.current?.close();
        player.current = null;
        if (enable) {
          player.current = new Sonifier(0.5);
          await player.current.context.resume();
          lastAudio.current = performance.now();
        }
      }
      if (!enable && captures.current[key]) {
        const capture = captures.current[key]!;
        delete captures.current[key];
        await capture.stop("user_stopped");
      }
      const receipt = await setOrgan(base, key, enable, attempt.signal);
      if (!current()) return;
      setSpec(receipt.spec);
      setNotice(
        t("器官设置已生效，模拟时间：") + `${Number(receipt.time_us) / 1e6} s`,
      );
      refresh();
      if (enable && (key === "ear" || key === "eye")) {
        const cfg = await api(`${base}/capture?limit=1`, {
          signal: attempt.signal,
        });
        const capture = await startCapture({
          base,
          kind: key === "ear" ? "audio" : "video",
          configuration: cfg.configuration,
          audioDevice: "",
          videoDevice: "",
          signal: attempt.signal,
          update: (stats) => {
            if (current())
              setCaptureStats((previous) => ({ ...previous, [key]: stats }));
          },
          failed: (message) => {
            if (current()) {
              state(key, "failed");
              setError(new Error(message));
            }
          },
        });
        if (!current()) {
          await capture.stop("page_left");
          return;
        }
        captures.current[key] = capture;
      }
      if (enable && (key === "mouth" || key === "image")) followOutput();
      if (!enable && key === "image") setFrame(null);
      if (current()) state(key, enable ? "on" : "off");
    } catch (e) {
      if (current()) {
        if (key === "mouth") {
          player.current?.close();
          player.current = null;
        }
        state(key, "failed");
        setError(e);
      }
    }
  };
  // Opening a picker is local UI state. Only an explicit configuration
  // action or a confirmed media submission may write to the instance.
  const openUpload = (kind: string) => {
    setUpload(kind);
    setError(null);
  };
  const configureMedia = async (kind: string) => {
    const attempt = new AbortController();
    pending.current.upload = attempt;
    setUploadBusy(true);
    setError(null);
    try {
      const receipt = await setOrgan(
        base,
        `media-${kind}`,
        true,
        attempt.signal,
      );
      if (alive.current && !attempt.signal.aborted) {
        setSpec(receipt.spec);
        refresh();
      }
    } catch (error) {
      if (alive.current && !attempt.signal.aborted) setError(error);
    } finally {
      if (alive.current) setUploadBusy(false);
    }
  };
  return (
    <div className="chat-organs">
      <div className="chat-organ-row" aria-label={t("器官开关")}>
        <div className="chat-media-add">
          <button
            type="button"
            className="organ-switch media-add"
            aria-label={t("添加媒体刺激")}
            aria-expanded={mediaMenu}
            aria-haspopup="menu"
            onClick={() => setMediaMenu((v) => !v)}
          >
            <Plus size={18} />
          </button>
          {mediaMenu && (
            <div
              className="chat-media-row"
              role="menu"
              aria-label={t("媒体刺激入口")}
            >
              {(
                [
                  ["image", ImageIcon, "图片"],
                  ["audio", FileAudio, "音频"],
                  ["video", FileVideo, "视频"],
                ] as const
              ).map(([kind, Icon, label]) => (
                <Button
                  key={kind}
                  disabled={
                    !can(user, "runs.stimulate") ||
                    run.life === "dead" ||
                    !!run.spec.study_id ||
                    uploadBusy
                  }
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setMediaMenu(false);
                    void openUpload(kind);
                  }}
                >
                  <Icon size={16} />
                  {t(label)}
                </Button>
              ))}
            </div>
          )}
        </div>
        {(
          [
            ["ear", Mic],
            ["eye", Camera],
            ["mouth", Volume2],
            ["image", ImageIcon],
          ] as const
        ).map(([key, Icon]) => (
          <button
            type="button"
            className={`organ-switch ${states[key]}`}
            key={key}
            aria-pressed={states[key] === "on"}
            aria-label={`${t(names[key])} · ${t(labels[states[key]])}`}
            title={`${t(names[key])} · ${t(labels[states[key]])}`}
            disabled={!allowed || states[key] === "stopping"}
            onClick={() => void toggle(key)}
          >
            <Icon size={17} />
            <span>{t(names[key])}</span>
            <small>{t(labels[states[key]])}</small>
          </button>
        ))}
      </div>
      {(["ear", "eye"] as const).map((key) => {
        const stats = captureStats[key];
        return stats && states[key] !== "off" ? (
          <small
            className="capture-queue-status"
            key={key}
            aria-label={t("{organ}采集状态", { organ: t(names[key]) })}
          >
            {t(
              "{organ}：已确认 {confirmed} · 待确认 {pending}/{capacity} · 最近确认 {latency} ms",
              {
                organ: t(names[key]),
                confirmed: stats.confirmed,
                pending: stats.pending,
                capacity:
                  stats.capacity ?? spec.live_capture.max_pending_packets,
                latency: Math.round(stats.acknowledgementMs ?? 0),
              },
            )}
          </small>
        ) : null;
      })}
      {frame && <Projection image={frame.image} at={frame.at} />}
      {notice && <small role="status">{notice}</small>}
      <ErrorBox error={error} />
      {upload && (
        <Modal
          open
          onOpenChange={(open) => {
            if (!open) setUpload(null);
          }}
          title={t("媒体刺激")}
          wide
        >
          <MediaInput
            key={upload}
            base={base}
            run={{ ...run, spec }}
            initialKind={upload}
            initialIntensity={intensity}
            capabilities={registry.data?.media_capabilities}
            configure={(kind) => void configureMedia(kind ?? upload)}
          />
        </Modal>
      )}
    </div>
  );
}
