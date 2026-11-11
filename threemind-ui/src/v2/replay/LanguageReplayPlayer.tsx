import { useEffect, useMemo, useRef, useState } from "react";
import CapturePanel from "../CapturePanel";
import { t } from "../i18n";
import { downloadCapture } from "../visualCapture";
import {
  clipAt,
  clock,
  LanguageReplayRenderer,
  type LanguageReplayData,
} from "./languageReplay";
import "./replay.css";

export default function LanguageReplayPlayer({
  data,
}: {
  data: LanguageReplayData;
}) {
  const renderer = useMemo(() => new LanguageReplayRenderer(data), [data]);
  const canvas = useRef<HTMLCanvasElement>(null);
  const position = useRef(0);
  const [at, setAt] = useState(0),
    [playing, setPlaying] = useState(false),
    [speed, setSpeed] = useState(1);
  const [focus, setFocus] = useState(() =>
    matchMedia("(max-width: 700px)").matches ? "dialogue" : "all",
  );
  const seek = (seconds: number) => {
    position.current = Math.max(0, Math.min(renderer.duration, seconds));
    setAt(position.current);
  };
  useEffect(() => {
    if (canvas.current) renderer.view(canvas.current, at, focus);
  }, [renderer, at, focus]);
  useEffect(() => {
    if (!playing) return;
    let raf = 0,
      previous = performance.now();
    const step = (now: number) => {
      // Pausing a background tab does not skip chapters when the researcher returns.
      position.current = Math.min(
        renderer.duration,
        position.current + Math.min(0.2, (now - previous) / 1000) * speed,
      );
      previous = now;
      setAt(position.current);
      if (position.current >= renderer.duration) setPlaying(false);
      else raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, renderer]);
  const current = clipAt(data, at);
  const events = current.clip.events
    .filter((e) => e.at <= current.offset)
    .slice(-3);
  const source = {
    draw: () => renderer.render(position.current),
    metadata: () => {
      const { clip, offset } = clipAt(data, position.current);
      const sim =
        clip.from +
        (clip.to - clip.from) *
          Math.min(1, offset / (clip.motionSeconds ?? clip.duration));
      return {
        world: clip.source,
        time: `${sim.toFixed(2)} s`,
        legend: t("记录回放；原始回答；不推进意识"),
      };
    },
  };
  let chapterStart = 0;
  return (
    <section className="language-replay" aria-label={t("教学回放播放器")}>
      <div className="replay-view-tabs" aria-label={t("画面视图")}>
        {[
          ["all", "完整画面"],
          ["world", "教学场景"],
          ["activity", "意识活动"],
          ["dialogue", "教学与回答"],
        ].map(([key, label]) => (
          <button
            type="button"
            key={key}
            className={focus === key ? "active" : ""}
            aria-pressed={focus === key}
            onClick={() => setFocus(key)}
          >
            {t(label)}
          </button>
        ))}
      </div>
      <canvas
        ref={canvas}
        className={`replay-canvas ${focus === "all" ? "wide" : "focused"}`}
        aria-label={t("已记录的教学场景、活动与实际回答")}
      />
      <div className="replay-controls">
        <button
          type="button"
          className="button primary"
          onClick={() => {
            if (at >= renderer.duration) seek(0);
            setPlaying(!playing);
          }}
        >
          {playing ? t("暂停") : t("播放")}
        </button>
        <button
          type="button"
          className="button"
          onClick={() => {
            setPlaying(false);
            seek(0);
          }}
        >
          {t("从头开始")}
        </button>
        <output aria-label={t("回放进度")}>
          {clock(at)} / {clock(renderer.duration)}
        </output>
        <label>
          {t("回放速度")}
          <select
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
          >
            {[0.25, 0.5, 1, 2, 4].map((v) => (
              <option key={v} value={v}>
                {v}×
              </option>
            ))}
          </select>
        </label>
      </div>
      <input
        className="replay-seek"
        type="range"
        min={0}
        max={renderer.duration}
        step={0.05}
        value={at}
        aria-label={t("回放时间轴")}
        onChange={(e) => seek(Number(e.target.value))}
      />
      <p className="replay-current">
        <strong>{current.clip.title}</strong> · {current.clip.subtitle}
      </p>
      <p className="replay-explanation">{current.clip.caption}</p>
      {current.clip.motionSeconds &&
        current.offset >= current.clip.motionSeconds && (
          <p className="replay-explanation">
            {t(
              "观察窗口已结束，活动画面保持最后一个记录；后续文字不代表新增活动采样。",
            )}
          </p>
        )}
      <CapturePanel
        source={source}
        initialOptions={{
          seconds: Math.min(300, Math.ceil(renderer.duration)),
          title: data.title,
          showTitle: false,
          showLegend: false,
          showWorld: false,
          showGeneration: false,
          showTime: false,
        }}
        onRecordStart={() => {
          if (position.current >= renderer.duration) seek(0);
          setPlaying(true);
        }}
      />
      <p className="replay-hint">
        {t(
          "录屏会从当前进度播放，保存完整横屏画面为 WebM。拖动时间轴会改变录制内容；完整 MP4 可通过导出命令生成。",
        )}
      </p>
      <div className="replay-lower">
        <details open>
          <summary>{t("章节")}</summary>
          <ol className="replay-chapters">
            {data.clips.map((c, i) => {
              const start = chapterStart;
              chapterStart += c.duration;
              return (
                <li key={c.id}>
                  <button
                    type="button"
                    aria-current={i === current.index ? "step" : undefined}
                    onClick={() => seek(start)}
                  >
                    <span>{clock(start)}</span>
                    {c.title}
                  </button>
                </li>
              );
            })}
          </ol>
        </details>
        <div>
          <details open>
            <summary>{t("当前原文")}</summary>
            <div className="replay-transcript">
              {events.length ? (
                events.map((e, i) => (
                  <article key={`${current.clip.id}-${i}`} className={e.role}>
                    <small>{e.label}</small>
                    <p>{e.text || t("当时未输出")}</p>
                  </article>
                ))
              ) : (
                <p>{t("本章节暂无对话记录")}</p>
              )}
            </div>
          </details>
          <details>
            <summary>{t("来源与回放说明")}</summary>
            <p>{data.description}</p>
            <ul>
              {current.clip.evidence.map((p) => (
                <li key={p}>
                  <code>{p}</code>
                </li>
              ))}
            </ul>
            <p>
              {t(
                "场景为示意重建，节点布局只用于显示。只保持已有采样，不插值、不重新生成回答。原文按实验使用的语言显示。",
              )}
            </p>
            <button
              type="button"
              className="button"
              onClick={() =>
                downloadCapture(
                  new Blob([JSON.stringify(data)], {
                    type: "application/json",
                  }),
                  "threemind-language-replay.json",
                )
              }
            >
              {t("下载回放数据")}
            </button>
          </details>
        </div>
      </div>
    </section>
  );
}
