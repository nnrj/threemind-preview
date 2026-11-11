import { useEffect, useRef, useState } from "react";
import { t } from "./i18n";
import {
  capturePng,
  defaultCaptureOptions,
  downloadCapture,
  startVisualRecording,
} from "./visualCapture";
import type { CaptureSource, CaptureOptions } from "./visualCapture";
import "./capture.css";

export default function CapturePanel({
  source,
  disabled = false,
  initialOptions,
  onRecordStart,
}: {
  source: CaptureSource;
  disabled?: boolean;
  initialOptions?: Partial<CaptureOptions>;
  onRecordStart?: () => void;
}) {
  const live = useRef(source);
  live.current = source;
  const [options, setOptions] = useState(() => ({
    ...defaultCaptureOptions,
    ...initialOptions,
  }));
  const [recording, setRecording] = useState(false),
    [error, setError] = useState("");
  const controller = useRef<ReturnType<typeof startVisualRecording> | null>(
    null,
  );
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      controller.current?.stop();
    };
  }, []);
  const current = {
    draw: () => live.current.draw(),
    metadata: () => live.current.metadata(),
  };
  const filename = () =>
    "threemind-" + new Date().toISOString().replace(/[:.]/g, "-");
  async function screenshot() {
    setError("");
    try {
      downloadCapture(await capturePng(current, options), filename() + ".png");
    } catch (e) {
      setError(String(e));
    }
  }
  async function record() {
    if (controller.current) return;
    setError("");
    try {
      const name = filename() + ".webm";
      const session = startVisualRecording(current, { ...options });
      controller.current = session;
      setRecording(true);
      onRecordStart?.();
      const blob = await session.finished;
      // Leaving or switching the view ends capture but must not discard it.
      downloadCapture(blob, name);
    } catch (e) {
      if (mounted.current) setError(String(e));
    } finally {
      controller.current = null;
      if (mounted.current) setRecording(false);
    }
  }
  const toggles = [
    ["showTitle", "标题"],
    ["showLegend", "图例"],
    ["showWorld", "世界信息"],
    ["showGeneration", "个体与代次"],
    ["showTime", "模拟时间"],
  ] as const;
  return (
    <div className="capture-panel">
      <button
        type="button"
        className="button small"
        disabled={disabled}
        onClick={screenshot}
      >
        {t("截图")}
      </button>
      <button
        type="button"
        className="button small"
        disabled={disabled && !recording}
        onClick={() => (recording ? controller.current?.stop() : void record())}
      >
        {recording ? t("停止并保存录屏") : t("录屏")}
      </button>
      {recording && <span role="status">{t("正在录制画面")}</span>}
      <details>
        <summary>{t("导出高级选项")}</summary>
        <fieldset disabled={recording}>
          <label>
            {t("标题")}
            <input
              value={options.title}
              maxLength={160}
              onChange={(e) =>
                setOptions({ ...options, title: e.target.value })
              }
            />
          </label>
          <div className="capture-toggles">
            {toggles.map(([key, text]) => (
              <label key={key}>
                <input
                  type="checkbox"
                  checked={options[key]}
                  onChange={(e) =>
                    setOptions({ ...options, [key]: e.target.checked })
                  }
                />
                {t(text)}
              </label>
            ))}
          </div>
          <label>
            {t("录制帧率")}
            <select
              value={options.fps}
              onChange={(e) =>
                setOptions({ ...options, fps: Number(e.target.value) })
              }
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={30}>30</option>
            </select>
          </label>
          <label>
            {t("最长录制秒数")}
            <input
              type="number"
              min={1}
              max={300}
              value={options.seconds}
              onChange={(e) =>
                setOptions({ ...options, seconds: Number(e.target.value) })
              }
            />
          </label>
          <small>
            {t(
              "录制参数只控制画面导出，不调整内核参数。若意识接入实时宿主遥测，录制负载可能成为输入；严格对照可使用离线轨迹导出。",
            )}
          </small>
        </fieldset>
      </details>
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
