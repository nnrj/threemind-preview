import { t, locale } from "./i18n";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Camera, Mic, Square, Settings2, RefreshCw } from "lucide-react";
import { api, type Run } from "./api";
import { Button, Field, Empty, ErrorBox, Loading } from "./ui";
import { startCapture, type CaptureController } from "./captureClient";

const status: Record<string, string> = {
  active: "采集中",
  stopped: "已结束",
  interrupted: "已中断",
};
const seconds = (v: any) =>
  v == null
    ? "—"
    : `${(Number(v) / 1e6).toLocaleString(locale(), { maximumFractionDigits: 6 })} s`;
const initialStats = {
  confirmed: 0,
  pending: 0,
  bytes: 0,
  videoFrames: 0,
  videoSkipped: 0,
};

export default function LiveCapturePanel({
  base,
  run,
  configure,
}: {
  base: string;
  run: Run;
  configure: () => void;
}) {
  const [kind, setKind] = useState<"audio" | "video" | "av">("audio"),
    [audioDevice, setAudioDevice] = useState(""),
    [videoDevice, setVideoDevice] = useState("");
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]),
    [error, setError] = useState<unknown>(null),
    [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false),
    [active, setActive] = useState(false),
    [selected, setSelected] = useState<string | null>(null),
    [offset, setOffset] = useState(0),
    [pages, setPages] = useState([-1]);
  const [stats, setStats] = useState(initialStats);
  const controller = useRef<CaptureController | null>(null),
    attempt = useRef<AbortController | null>(null),
    stoppingUi = useRef(false),
    mounted = useRef(true);
  const sessions = useQuery({
    queryKey: ["capture", run.id, offset],
    queryFn: () => api(`${base}/capture?offset=${offset}`),
    gcTime: 0,
    refetchInterval: 2000,
  });
  const selectedId = selected ?? sessions.data?.rows[0]?.id,
    after = pages.at(-1) ?? -1;
  const packets = useQuery({
    queryKey: ["capture-packets", run.id, selectedId, after],
    queryFn: () => api(`${base}/capture/${selectedId}/packets?after=${after}`),
    enabled: !!selectedId,
    gcTime: 0,
    refetchInterval: run.status === "running" ? 2000 : false,
  });
  const refresh = () => {
    void sessions.refetch();
    if (selectedId) void packets.refetch();
  };
  const stop = async (reason = "user_stopped") => {
    if (stoppingUi.current) return;
    const current = controller.current;
    controller.current = null;
    const pending = attempt.current;
    if (!current) {
      pending?.abort();
      attempt.current = null;
      setBusy(false);
      return;
    }
    stoppingUi.current = true;
    setBusy(true);
    try {
      await current.stop(reason);
      if (mounted.current)
        setNotice(t("设备已释放，已确认的原始块与在途刺激保留在数据库中。"));
    } catch (e) {
      if (mounted.current) setError(e);
    } finally {
      stoppingUi.current = false;
      if (attempt.current === pending) {
        pending?.abort();
        attempt.current = null;
      }
      if (mounted.current) {
        setActive(false);
        setBusy(false);
        refresh();
      }
    }
  };
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      attempt.current?.abort();
      void controller.current?.stop("page_left").catch(() => {});
      controller.current = null;
    };
  }, []);
  useEffect(() => {
    if (active && run.status !== "running") void stop("page_left");
  }, [run.status, active]);
  useEffect(() => {
    const row = sessions.data?.rows.find(
      (s: any) => s.id === controller.current?.sessionId,
    );
    if (active && row && row.status !== "active") void stop("request_failed");
  }, [sessions.data, active]);
  const enumerate = async () => {
    try {
      if (!navigator.mediaDevices)
        throw new Error(t("设备采集需要 HTTPS 或本机地址。"));
      setDevices(await navigator.mediaDevices.enumerateDevices());
    } catch (e) {
      setError(e);
    }
  };
  const start = async () => {
    const cfg = sessions.data?.configuration;
    if (!cfg) return;
    setBusy(true);
    setError(null);
    setNotice("");
    setStats(initialStats);
    const pending = new AbortController();
    attempt.current = pending;
    const current = () => mounted.current && attempt.current === pending;
    try {
      const value = await startCapture({
        base,
        kind,
        configuration: cfg,
        audioDevice,
        videoDevice,
        signal: pending.signal,
        update: (s) => {
          if (current()) setStats(s);
        },
        failed: (message) => {
          if (current()) {
            setError(new Error(message));
            setActive(false);
            setBusy(false);
            refresh();
          }
        },
      });
      if (pending.signal.aborted) {
        await value.stop("page_left");
        return;
      }
      controller.current = value;
      setSelected(value.sessionId);
      setPages([-1]);
      setOffset(0);
      setActive(true);
      refresh();
      void enumerate();
    } catch (e) {
      if (current() && !pending.signal.aborted) setError(e);
    } finally {
      if (current()) setBusy(false);
    }
  };
  const cfg = sessions.data?.configuration;
  const allowed =
    cfg &&
    cfg.source_policies?.background_enabled !== false &&
    (kind === "video" || cfg.source_policies?.microphone_enabled !== false) &&
    (kind === "audio" || cfg.source_policies?.camera_enabled !== false) &&
    (kind === "video" ||
      (cfg.live_capture.microphone_enabled && cfg.auditory_sensor.enabled)) &&
    (kind === "audio" ||
      (cfg.live_capture.camera_enabled && cfg.visual_sensor.enabled));
  const session = packets.data?.session;
  return (
    <section className="panel live-capture-panel">
      <div className="panel-heading">
        <div>
          <h2>{t("连续设备采集")}</h2>
          <p>{t("麦克风、摄像头或音画联合会话；设备在明确开启后采集。")}</p>
        </div>
        <Button onClick={configure}>
          <Settings2 size={15} />
          {t("配置连续感官")}
        </Button>
      </div>
      <ErrorBox error={error ?? sessions.error ?? packets.error} />
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      <div className="query-controls">
        <Field label={t("连续采集类型")}>
          <select
            value={kind}
            disabled={active || busy}
            onChange={(e) => setKind(e.target.value as typeof kind)}
          >
            <option value="audio">{t("麦克风")}</option>
            <option value="video">{t("摄像头")}</option>
            <option value="av">{t("音画联合采集")}</option>
          </select>
        </Field>
        {kind !== "video" && (
          <Field label={t("麦克风设备")}>
            <select
              value={audioDevice}
              disabled={active || busy}
              onChange={(e) => setAudioDevice(e.target.value)}
            >
              <option value="">{t("系统默认麦克风")}</option>
              {devices
                .filter((d) => d.kind === "audioinput" && d.deviceId)
                .map((d, i) => (
                  <option key={d.deviceId} value={d.deviceId}>
                    {d.label ||
                      t("音频设备 {value0}", { value0: String(i + 1) })}
                  </option>
                ))}
            </select>
          </Field>
        )}
        {kind !== "audio" && (
          <Field label={t("摄像头设备")}>
            <select
              value={videoDevice}
              disabled={active || busy}
              onChange={(e) => setVideoDevice(e.target.value)}
            >
              <option value="">{t("系统默认摄像头")}</option>
              {devices
                .filter((d) => d.kind === "videoinput" && d.deviceId)
                .map((d, i) => (
                  <option key={d.deviceId} value={d.deviceId}>
                    {d.label ||
                      t("视频设备 {value0}", { value0: String(i + 1) })}
                  </option>
                ))}
            </select>
          </Field>
        )}
        <Button disabled={active || busy} onClick={enumerate}>
          <RefreshCw size={15} />
          {t("读取设备列表")}
        </Button>
      </div>
      <div className="live-capture-actions">
        <Button
          variant="primary"
          disabled={
            active ||
            busy ||
            !!controller.current ||
            !allowed ||
            run.status !== "running" ||
            run.spec.clock !== "realtime"
          }
          onClick={start}
        >
          {kind === "audio" ? <Mic size={15} /> : <Camera size={15} />}
          {t("开始采集")}
        </Button>
        <Button
          disabled={!active && !busy && !controller.current}
          onClick={() => stop()}
        >
          <Square size={15} />
          {busy ? t("取消 / 停止") : t("停止采集")}
        </Button>
        <span role="status">
          {active
            ? t("设备采集中")
            : busy
              ? t("正在处理设备与待确认块…")
              : t("设备未开启")}
        </span>
      </div>
      <p className="footnote">
        {!allowed &&
          "请先暂停，在参数配置中启用相应感官、连续采集和来源准入开关。"}
        {run.status !== "running" && "开始前请继续运行意识。"}
        {t(
          "音画共用会话时标；音频使用浏览器渲染时钟估计，画面记录采集或呈现时间来源，不能视为经校准的硬件同步。PCM 与缩放后灰度画面会保存在当前数据库。",
        )}
      </p>
      <div className="live-capture-counters">
        <span>
          {t("已确认 ")}
          <strong>{stats.confirmed}</strong>
          {t(" 块")}
        </span>
        <span>
          {t("待确认 ")}
          <strong>{stats.pending}</strong>
        </span>
        <span>
          {t("确认原件 ")}
          <strong>{(stats.bytes / 1024).toFixed(1)}</strong> KiB
        </span>
        <span>
          {t("发送画面 ")}
          <strong>{stats.videoFrames}</strong>
        </span>
        <span>
          {t("浏览器跳过 / 采样过滤 ")}
          <strong>{stats.videoSkipped}</strong>
        </span>
      </div>
      <div className="panel-heading">
        <h3>{t("采集会话记录")}</h3>
        <Button onClick={refresh}>{t("刷新会话")}</Button>
      </div>
      {sessions.isLoading ? (
        <Loading />
      ) : sessions.data?.rows.length ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t("会话")}</th>
                <th>{t("状态")}</th>
                <th>{t("确认块数 / 原始大小")}</th>
                <th>{t("时钟锚点")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {sessions.data.rows.map((s: any) => (
                <tr key={s.id}>
                  <td>
                    {s.name}
                    <small>
                      {new Date(s.created_at).toLocaleString(locale())}
                    </small>
                  </td>
                  <td>
                    {t(status[s.status])}
                    {s.reason && <small>{s.reason}</small>}
                  </td>
                  <td>
                    {s.next_sequence} /{" "}
                    {(Number(s.byte_count) / 1024).toFixed(1)} KiB
                  </td>
                  <td>{seconds(s.origin_sim_us)}</td>
                  <td>
                    <Button
                      onClick={() => {
                        setSelected(s.id);
                        setPages([-1]);
                      }}
                    >
                      {t("查看采集 ")}
                      {s.id.slice(0, 8)}
                    </Button>
                    {s.status === "active" &&
                      s.id !== controller.current?.sessionId && (
                        <Button
                          onClick={async () => {
                            try {
                              await api(`${base}/capture/${s.id}/stop`, {
                                method: "POST",
                                body: JSON.stringify({
                                  reason: "user_stopped",
                                }),
                              });
                              refresh();
                            } catch (e) {
                              setError(e);
                            }
                          }}
                        >
                          {t("结束该会话")}
                        </Button>
                      )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty
          title={t("还没有采集会话")}
          detail={t(
            "在运行中的实时意识上开始采集，随后可查看原始块与递送结果。",
          )}
        />
      )}
      <div className="live-capture-actions">
        <Button
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 30))}
        >
          {t("较新会话")}
        </Button>
        <Button
          disabled={!sessions.data?.more}
          onClick={() => setOffset(offset + 30)}
        >
          {t("较早会话")}
        </Button>
      </div>
      {session && (
        <>
          <details className="readout-provenance">
            <summary>{t("本会话的设备、时钟与冻结配置")}</summary>
            <pre>
              {JSON.stringify(
                {
                  source_clock: session.source_clock,
                  configuration: session.configuration,
                },
                null,
                2,
              )}
            </pre>
          </details>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t("块序号 / 类型")}</th>
                  <th>{t("采集区间")}</th>
                  <th>{t("时间来源")}</th>
                  <th>{t("刺激帧 / 已递送")}</th>
                  <th>{t("状态")}</th>
                  <th>{t("原始块")}</th>
                </tr>
              </thead>
              <tbody>
                {packets.data.rows.map((p: any) => (
                  <tr key={p.sequence}>
                    <td>
                      {p.sequence} /{" "}
                      {p.metadata.kind === "audio" ? "PCM" : t("灰度画面")}
                      {p.metadata.final && <small>{t("音频结束块")}</small>}
                      {p.metadata.clipped_mono_samples > 0 && (
                        <small>
                          {t("感官归一化饱和 ")}
                          {p.metadata.clipped_mono_samples}{" "}
                          {t("样本；原件峰值 ")}
                          {p.metadata.raw_pcm_peak.toFixed(4)}
                        </small>
                      )}
                    </td>
                    <td>
                      {seconds(p.metadata.capture_us)}–
                      {seconds(p.metadata.captured_end_us)}
                    </td>
                    <td>
                      {p.metadata.timestamp_kind}
                      <small>
                        {t("来源索引 ")}
                        {p.metadata.source_index}
                        {t(" · 跳过")} {p.metadata.skipped_before}
                      </small>
                    </td>
                    <td>
                      {p.frame_count} / {p.delivered_count}
                    </td>
                    <td>
                      {p.status}
                      {p.error && <small>{p.error}</small>}
                    </td>
                    <td>
                      <a
                        className="text-link"
                        href={`/api/v2${base}/media/${p.envelope_id}/original`}
                        download
                      >
                        {t("下载 #")}
                        {p.sequence}
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="live-capture-actions">
            <Button
              disabled={pages.length === 1}
              onClick={() => setPages(pages.slice(0, -1))}
            >
              {t("前一页采集块")}
            </Button>
            <Button
              disabled={!packets.data.more}
              onClick={() => setPages([...pages, packets.data.next])}
            >
              {t("后一页采集块")}
            </Button>
            <a
              className="text-link"
              href={`/api/v2${base}/media/export`}
              download
            >
              {t("导出该意识全部媒体原件")}
            </a>
          </div>
        </>
      )}
      <Link
        className="text-link live-capture-doc"
        to="/docs?doc=docs%2Fzh%2Fv2-live-capture.md"
      >
        {t("查看连续感官的时间、保存与恢复规则")}
      </Link>
    </section>
  );
}
