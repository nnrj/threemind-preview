import { t } from "./i18n";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Activity, Square, Volume2, VolumeX } from "lucide-react";
import { type Run } from "./api";
import { Button, Field, ErrorBox, Empty } from "./ui";

type Voice = { node_id: number; frequency_hz: number; amplitude: number };
export class Sonifier {
  context = new AudioContext({ sampleRate: 48000 });
  output = this.context.createGain();
  voices = new Map<number, { oscillator: OscillatorNode; gain: GainNode }>();
  constructor(volume: number) {
    this.output.gain.value = volume;
    this.output.connect(this.context.destination);
  }
  update(values: Voice[]) {
    if (
      values.length > 128 ||
      values.some(
        (v) =>
          !Number.isFinite(v.frequency_hz) ||
          v.frequency_hz <= 0 ||
          v.frequency_hz >= 24000 ||
          !Number.isFinite(v.amplitude) ||
          v.amplitude < 0 ||
          v.amplitude > 1,
      )
    )
      throw new Error(t("器官声音控制值无效，停止播放。"));
    const now = this.context.currentTime,
      remaining = new Set(this.voices.keys());
    for (const value of values) {
      let tone = this.voices.get(value.node_id);
      if (!tone) {
        const oscillator = this.context.createOscillator(),
          gain = this.context.createGain();
        oscillator.frequency.value = value.frequency_hz;
        gain.gain.value = 0;
        oscillator.connect(gain).connect(this.output);
        oscillator.start();
        tone = { oscillator, gain };
        this.voices.set(value.node_id, tone);
      }
      remaining.delete(value.node_id);
      tone.oscillator.frequency.setTargetAtTime(value.frequency_hz, now, 0.01);
      tone.gain.gain.cancelScheduledValues(now);
      tone.gain.gain.setTargetAtTime(
        (value.amplitude * 0.16) / Math.max(1, values.length),
        now,
        0.01,
      );
    }
    for (const id of remaining) {
      const tone = this.voices.get(id)!;
      this.voices.delete(id);
      tone.gain.gain.cancelScheduledValues(now);
      tone.gain.gain.setTargetAtTime(0, now, 0.005);
      tone.oscillator.stop(now + 0.04);
      tone.oscillator.onended = () => {
        tone.oscillator.disconnect();
        tone.gain.disconnect();
      };
    }
  }
  close() {
    this.voices.clear();
    void this.context.close().catch(() => {});
  }
}

export default function OrganMonitor({
  base,
  run,
  renderProjection,
}: {
  base: string;
  run: Run;
  renderProjection: (image: any, at: string) => ReactNode;
}) {
  const [following, setFollowing] = useState(false),
    [sound, setSound] = useState(false);
  const [volume, setVolume] = useState(0.5),
    [error, setError] = useState<unknown>(null);
  const [audioFrame, setAudioFrame] = useState<any>(null),
    [imageFrame, setImageFrame] = useState<any>(null);
  const [skipped, setSkipped] = useState(0),
    [notice, setNotice] = useState("声音默认静音，点击开启后才合成播放。");
  const source = useRef<EventSource | null>(null),
    player = useRef<Sonifier | null>(null);
  const latestAudio = useRef<any>(null),
    audioReceived = useRef(0),
    mounted = useRef(true);
  const mute = () => {
    player.current?.close();
    player.current = null;
    if (mounted.current) setSound(false);
  };
  const stop = (message = "已停止跟随，保留最后一帧。") => {
    source.current?.close();
    source.current = null;
    mute();
    if (mounted.current) {
      setFollowing(false);
      setNotice(message);
    }
  };
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      source.current?.close();
      player.current?.close();
      source.current = null;
      player.current = null;
    };
  }, []);
  useEffect(() => {
    const watchdog = setInterval(() => {
      const allowance = Math.max(
        3000,
        (Number(
          latestAudio.current?.payload.configuration.acoustic_output
            .output_interval_us ?? 100000,
        ) /
          1000) *
          2 +
          2000,
      );
      if (
        player.current &&
        performance.now() - audioReceived.current > allowance
      ) {
        mute();
        setNotice(t("声音控制帧已过期，已静音；可检查运行与连接后重新开启。"));
      }
    }, 500);
    return () => clearInterval(watchdog);
  }, []);
  const start = () => {
    if (source.current) return;
    latestAudio.current = null;
    audioReceived.current = 0;
    setAudioFrame(null);
    setImageFrame(null);
    setError(null);
    setSkipped(0);
    setNotice(t("跟随最新已提交输出，声音默认静音。"));
    const connection = new EventSource(`/api/v2${base}/organs/monitor`);
    source.current = connection;
    setFollowing(true);
    connection.addEventListener("output", (event) => {
      if (source.current !== connection) return;
      try {
        const data = JSON.parse((event as MessageEvent).data);
        if (!data.enabled.audio) {
          if (player.current) setNotice(t("发声器配置已关闭，声音已停止。"));
          latestAudio.current = null;
          setAudioFrame(null);
          mute();
        }
        if (!data.enabled.image) setImageFrame(null);
        if (data.skipped_samples)
          setSkipped((value) => value + data.skipped_samples);
        for (const frame of data.frames) {
          if (data.enabled.image && frame.payload.image) setImageFrame(frame);
          if (data.enabled.audio && Array.isArray(frame.payload.voices)) {
            latestAudio.current = frame;
            audioReceived.current = performance.now();
            setAudioFrame(frame);
            player.current?.update(frame.payload.voices);
          }
        }
      } catch (e) {
        setError(e);
        stop("输出数据异常，连接和声音已停止。");
      }
    });
    connection.addEventListener("ended", (event) => {
      if (source.current !== connection) return;
      const reason = JSON.parse((event as MessageEvent).data).reason;
      stop(`运行或访问已结束（${reason}），声音已关闭。`);
    });
    connection.onerror = () => {
      if (source.current === connection)
        stop("输出连接已中断，声音已关闭；可以重新跟随。");
    };
  };
  const listen = async () => {
    if (player.current) {
      mute();
      setNotice(t("声音已静音，画面继续跟随。"));
      return;
    }
    let created: Sonifier | null = null;
    try {
      setError(null);
      created = new Sonifier(volume);
      player.current = created;
      await created.context.resume();
      if (player.current !== created) return;
      created.update(latestAudio.current?.payload.voices ?? []);
      setSound(true);
      setNotice(t("连续声音已开启，依据最新已提交控制帧合成。"));
    } catch (e) {
      setError(e);
      mute();
    }
  };
  return (
    <div className="organ-monitor" role="region" aria-label={t("连续器官输出")}>
      <div className="panel-heading">
        <div>
          <h3>{t("连续输出")}</h3>
          <p>{t("跟随最新数据库提交；声音与画面分别保留各自的模拟时间。")}</p>
        </div>
        <div className="button-row">
          <Button
            onClick={start}
            disabled={
              following ||
              !["running", "queued"].includes(run.status) ||
              !(
                run.spec.acoustic_output?.enabled ||
                run.spec.activation_projector?.enabled
              )
            }
          >
            <Activity size={15} />
            {t("跟随当前输出")}
          </Button>
          <Button onClick={() => stop()} disabled={!following}>
            <Square size={15} />
            {t("停止跟随")}
          </Button>
        </div>
      </div>
      <ErrorBox error={error} />
      <p className="notice" role="status">
        {notice}
      </p>
      <div className="organ-output-grid">
        <div>
          {imageFrame ? (
            renderProjection(imageFrame.payload.image, imageFrame.time_us)
          ) : (
            <Empty
              title={following ? t("等待已提交图像") : t("尚未跟随输出")}
              detail={t("启用投影器后点击“跟随当前输出”，在这里查看连续图像。")}
            />
          )}
          {imageFrame && (
            <p className="footnote">
              {t("图像 · 模拟 ")}
              {(Number(imageFrame.time_us) / 1e6).toFixed(4)}
              {t(" s · 数据库 r")}
              {imageFrame.commit_revision}
            </p>
          )}
        </div>
        <div>
          <h4>{t("连续发声")}</h4>
          <div className="button-row">
            <Button onClick={listen} disabled={!following || !audioFrame}>
              {sound ? <VolumeX size={15} /> : <Volume2 size={15} />}
              {sound ? t("静音") : t("开启连续声音")}
            </Button>
            <span role="status">{sound ? t("连续声音已开启") : t("静音")}</span>
          </div>
          <Field label={t("监听音量")}>
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={volume}
              onChange={(event) => {
                const value = Number(event.target.value);
                setVolume(value);
                if (player.current)
                  player.current.output.gain.setTargetAtTime(
                    value,
                    player.current.context.currentTime,
                    0.01,
                  );
              }}
            />
          </Field>
          {audioFrame && (
            <p>
              {t("声音 · 模拟 ")}
              {(Number(audioFrame.time_us) / 1e6).toFixed(4)} s ·{" "}
              {audioFrame.payload.voices.length}
              {t(" 个振荡器 · 数据库 r")}
              {audioFrame.commit_revision}
            </p>
          )}
          <p className="footnote">
            {t("为跟随最新状态，跳过 ")}
            {skipped}{" "}
            {t(
              "条已保存输出。完整采样可在下方查询或导出；这里的连续合成不是原始声音录音，也不按全部历史帧重放。",
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
