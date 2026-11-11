import { useAccess } from "./access";
import { t, locale } from "./i18n";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Send, RefreshCw, Download, Settings2 } from "lucide-react";
import { api, post, type Run } from "./api";
import { MediaInput, OrganOutputs } from "./media";
import { TelemetryPanel } from "./telemetry";
import LiveCapturePanel from "./liveCapture";
import AttentionPanel from "./attention";
import BodyPanel from "./body";
import { usePreferences, updatePreferences } from "./preferences";
import { useCatalogue } from "./configuration";
const DevicePanel = lazy(() => import("./devices"));
const SourcePolicyPanel = lazy(() => import("./sourcePolicies"));
const AdapterCatalogue = lazy(() =>
  import("./adapterCatalogue").then((m) => ({ default: m.AdapterCatalogue })),
);
import {
  Button,
  Field,
  ErrorBox,
  Empty,
  Loading,
  Modal,
  CodeEditor,
} from "./ui";

export const sources: Record<string, string> = {
  "manual-text": "手动文本",
  "manual-cli-text": "命令行文本",
  "manual-anonymous": "匿名帧接入",
  "manual-observation": "手动无刺激观察",
  mujoco: "模拟物理环境",
  "host-physical": "宿主物理遥测",
  "host-telemetry": "宿主遥测",
  "process-telemetry": "工作进程遥测",
  "runtime-telemetry": "意识实例反馈",
  replay: "记录重放",
  "checkpoint-queue": "检查点继承队列",
  "ambient-fixture": "合成环境基底",
  "ambient-disturbance": "合成环境扰动",
  "simulated-interoception": "模拟内感受",
  "upload-audio": "音频文件",
  "upload-image": "图片文件",
  "upload-video": "视频文件",
};
export const statuses: Record<string, string> = {
  accepted: "已接收，待排入",
  scheduled: "已排入内核",
  completed: "全部帧已处理",
  rejected: "未递送",
  delivered: "已递送",
  filtered: "协议过滤",
};
const encodings: Record<string, string> = {
  "anonymous-distributed": "匿名分布编码",
  "labeled-observation": "匿名编码＋观察标签",
  "literal-character": "逐字通道编码",
};

export function InputComposer({
  base,
  run,
  compact = false,
  intensityValue,
  onIntensityChange,
}: {
  base: string;
  run: Run;
  compact?: boolean;
  intensityValue?: number;
  onIntensityChange?: (value: number) => void;
}) {
  const client = useQueryClient();
  const permitted = useAccess();
  const catalogue = useCatalogue();
  const presets = catalogue.data?.text_intensity_presets;
  const [preset, setPreset] = useState(
    intensityValue === undefined || intensityValue === 1 ? "normal" : "custom",
  );
  const [randomMode, setRandomMode] = useState("fresh-single");
  const [randomSeed, setRandomSeed] = useState(run.spec.seed ?? 1);
  const [randomCount, setRandomCount] = useState(20);
  const [randomInterval, setRandomInterval] = useState(100);
  const [randomIntensity, setRandomIntensity] = useState(0.2);
  const fixture = useMutation({
    mutationFn: () =>
      post(base.split("/runs/")[0] + "/input-fixtures/random", {
        config: {
          seed: randomSeed,
          mode: randomMode,
          channels: 4,
          interval_us: Math.round(randomInterval * 1000),
          intensity: randomIntensity,
        },
        count: randomCount,
      }),
    onSuccess: (value) => setFrames(JSON.stringify(value.units, null, 2)),
  });
  const [mode, setMode] = useState("text-sensor"),
    [text, setText] = useState("");
  const [frames, setFrames] = useState(
    '[\n  {"time_us": "0", "channels": [[1, 0.7], [2, 0.5]], "intensity": 1}\n]',
  );
  const frameDrafts = useRef<Record<string, string>>({
    "stimulus-units": JSON.stringify(
      [
        {
          schema_id: "threemind.stimulus-unit/1",
          kind: "group",
          source: "manual-observation",
          mapping_version: "manual/1",
          grouping_basis: "one explicitly shared observation",
          time_us: "0",
          intensity: 1,
          elements: [
            { channel: 1, value: 0.7 },
            { channel: 2, value: 0.5 },
          ],
        },
      ],
      null,
      2,
    ),
  });
  const [localIntensity, setLocalIntensity] = useState(1),
    [delay, setDelay] = useState(0);
  const intensity = intensityValue ?? localIntensity;
  const changeIntensity = onIntensityChange ?? setLocalIntensity;
  const setIntensity = (value: number) => {
    setPreset("custom");
    changeIntensity(value);
  };
  const [notice, setNotice] = useState(""),
    [localError, setLocalError] = useState<unknown>(null);
  const { enterSend } = usePreferences();
  const attempt = useRef({ fingerprint: "", id: "" });
  const composing = useRef(false);
  const diagnostic = useMutation({
    mutationFn: async () =>
      post(`${base}/input-diagnostics`, {
        adapter_id: mode,
        payload:
          mode === "text-sensor"
            ? { text, intensity }
            : {
                [mode === "stimulus-units" ? "units" : "frames"]: (
                  await import("./JsonEditor")
                ).parseJson(frames),
              },
      }),
  });
  const allowed =
    ["queued", "running", "paused", "blocked"].includes(run.status) &&
    run.life !== "dead" &&
    !run.spec.study_id;
  const sourceBlocked =
    run.spec.source_policies?.manual_enabled === false ||
    (mode === "text-sensor"
      ? run.spec.source_policies?.ui_text_enabled === false
      : run.spec.source_policies?.anonymous_enabled === false);
  const disabled =
    !permitted("runs.stimulate") || !allowed ||
    sourceBlocked ||
    (mode === "text-sensor" && run.spec.text_sensor?.enabled === false);
  const submit = useMutation({
    mutationFn: async () => {
      const payload =
        mode === "text-sensor"
          ? { text, intensity }
          : {
              [mode === "stimulus-units" ? "units" : "frames"]: (
                await import("./JsonEditor")
              ).parseJson(frames),
            };
      const value = {
        adapter_id: mode,
        payload,
        delay_us: Math.round(delay * 1000),
      };
      const fingerprint = JSON.stringify(value);
      if (attempt.current.fingerprint !== fingerprint)
        attempt.current = { fingerprint, id: crypto.randomUUID() };
      const result = await post(`${base}/inputs`, {
        ...value,
        request_id: attempt.current.id,
      });
      return { ...result, sentText: text };
    },
    onSuccess: (result) => {
      if (result.status !== "rejected" && mode === "text-sensor")
        setText((draft) => (draft === result.sentText ? "" : draft));
      setNotice(
        result.status === "accepted"
          ? t("已接收 {value0} 帧。{value1}", {
              value0: String(result.frame_count),
              value1: t(
                run.status === "paused"
                  ? "当前已暂停，点击“继续”后才会排入并递送。"
                  : "递送进度与读出会显示在聊天记录中。",
              ),
            })
          : t(
              "该请求已有记录：{value0}。已递送 {value1} / {value2} 帧。{value3}",
              {
                value0: t(statuses[result.status] ?? result.status),
                value1: String(result.delivered_count),
                value2: String(result.frame_count),
                value3: String(result.error ?? ""),
              },
            ),
      );
      attempt.current = { fingerprint: "", id: "" };
      client.invalidateQueries({ queryKey: ["sensory", run.id] });
      client.invalidateQueries({ queryKey: ["conversation", run.id] });
    },
  });
  return (
    <form
      className="input-composer"
      onSubmit={(e) => {
        e.preventDefault();
        setLocalError(null);
        setNotice("");
        submit.mutate();
      }}
    >
      {!compact && (
        <>
          <h3>{t("递送输入")}</h3>
          <p>{t("载体经感官编码后，以数值脉冲进入内核。")}</p>
        </>
      )}
      {(run.spec.source_policies?.manual_enabled === false ||
        (mode === "text-sensor"
          ? run.spec.source_policies?.ui_text_enabled === false
          : run.spec.source_policies?.anonymous_enabled === false)) && (
        <p className="notice">
          {t("此输入来源已关闭。")}
          <Link className="text-link" to="?view=inputs&tool=sources">
            {t("查看来源策略")}
          </Link>
        </p>
      )}
      {!compact && (
        <Field label={t("输入形式")}>
          <select
            value={mode}
            onChange={(e) => {
              if (mode !== "text-sensor") frameDrafts.current[mode] = frames;
              if (e.target.value !== "text-sensor")
                setFrames(
                  frameDrafts.current[e.target.value] ??
                    '[{"time_us":"0","channels":[[1,0.7]],"intensity":1}]',
                );
              setMode(e.target.value);
              submit.reset();
              setNotice("");
            }}
          >
            <option value="text-sensor">{t("文本感官")}</option>
            <option value="anonymous-frames">{t("匿名帧序列")}</option>
            <option value="stimulus-units">
              {t("刺激体（共同观测与来源）")}
            </option>
          </select>
        </Field>
      )}
      {!compact && mode === "stimulus-units" && (
        <details>
          <summary>{t("生成独立随机对照（不会自动递送）")}</summary>
          <Field label={t("随机对照类型")}>
            <select
              value={randomMode}
              onChange={(e) => setRandomMode(e.target.value)}
            >
              <option value="fresh-single">{t("每次一个新通道")}</option>
              <option value="fresh-group">{t("每次一组新通道")}</option>
              <option value="fixed-amplitude">{t("固定通道、随机幅度")}</option>
            </select>
          </Field>
          <div className="form-grid">
            <Field label={t("随机种子")}>
              <input
                type="number"
                min={0}
                max={4294967295}
                value={randomSeed}
                onChange={(e) => setRandomSeed(e.target.valueAsNumber)}
              />
            </Field>
            <Field label={t("采样次数")}>
              <input
                type="number"
                min={1}
                max={1000}
                value={randomCount}
                onChange={(e) => setRandomCount(e.target.valueAsNumber)}
              />
            </Field>
            <Field label={t("采样间隔（ms）")}>
              <input
                type="number"
                min={0.001}
                max={1000000}
                step="any"
                value={randomInterval}
                onChange={(e) => setRandomInterval(e.target.valueAsNumber)}
              />
            </Field>
            <Field label={t("随机输入强度")}>
              <input
                type="number"
                min={0}
                max={100}
                step="any"
                value={randomIntensity}
                onChange={(e) => setRandomIntensity(e.target.valueAsNumber)}
              />
            </Field>
          </div>
          <p>
            {t("相同种子和序列位置会复用相同通道；重复递送不再是一次性噪声。")}
          </p>
          <Button
            type="button"
            disabled={fixture.isPending}
            onClick={() => fixture.mutate()}
          >
            {t("生成到编辑框")}
          </Button>
          <ErrorBox error={fixture.error} />
        </details>
      )}
      {mode === "text-sensor" ? (
        <>
          <Field label={t("文本载体")}>
            <textarea
              aria-label={t("文本载体")}
              rows={compact ? 3 : 5}
              value={text}
              placeholder={t("输入文字；空格和换行也会作为载体保留。")}
              onChange={(e) => setText(e.target.value)}
              onCompositionStart={() => {
                composing.current = true;
              }}
              onCompositionEnd={() => {
                composing.current = false;
              }}
              onKeyDown={(e) => {
                if (
                  enterSend &&
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing &&
                  !composing.current &&
                  e.keyCode !== 229
                ) {
                  e.preventDefault();
                  if (!disabled && !submit.isPending)
                    e.currentTarget.form?.requestSubmit();
                }
              }}
            />
          </Field>
          {!compact && (
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={enterSend}
                onChange={(e) =>
                  updatePreferences({ enterSend: e.target.checked })
                }
              />
              {t("Enter 发送，Shift＋Enter 换行")}
            </label>
          )}
          <span className="footnote">
            {t(
              encodings[
                run.spec.text_sensor?.encoding ?? "anonymous-distributed"
              ],
            )}
          </span>
        </>
      ) : (
        <>
          <CodeEditor
            value={frames}
            onChange={setFrames}
            rows={6}
            label={t(
              mode === "stimulus-units" ? "刺激体 JSON" : "匿名输入帧 JSON",
            )}
          />
          <button
            type="button"
            className="text-link"
            onClick={async () => {
              try {
                setFrames(
                  JSON.stringify(
                    (await import("./JsonEditor")).parseJson(frames),
                    null,
                    2,
                  ),
                );
                setLocalError(null);
              } catch (error) {
                setLocalError(error);
              }
            }}
          >
            {t("格式化 JSON")}
          </button>
          <p className="footnote">
            {t("time_us 为相对首帧起点的微秒数，须单调不减。每帧独立保留。")}
          </p>
        </>
      )}
      {mode === "text-sensor" && (
        <div className="chat-intensity">
          <span>{t("刺激强度")}</span>
          <select
            aria-label={t("强度预设")}
            value={preset}
            onChange={(e) => {
              setPreset(e.target.value);
              if (presets && e.target.value !== "custom")
                changeIntensity(presets[e.target.value]);
            }}
          >
            <option value="normal" disabled={!presets}>
              {t("普通")}
            </option>
            <option value="strong" disabled={!presets}>
              {t("强刺激")}
            </option>
            <option value="custom">{t("自定义")}</option>
          </select>
          <input
            aria-label={t("刺激强度")}
            type="range"
            min="0"
            max="4"
            step="0.05"
            value={Math.min(4, intensity)}
            onChange={(e) => setIntensity(Number(e.target.value))}
          />
          <input
            aria-label={t("刺激强度数值")}
            type="number"
            min={0}
            max={100}
            step="any"
            value={intensity}
            required
            onChange={(e) => setIntensity(e.target.valueAsNumber)}
          />
        </div>
      )}
      {!compact && (
        <details>
          <summary>{t("递送选项")}</summary>
          <Button
            type="button"
            disabled={diagnostic.isPending}
            onClick={() => diagnostic.mutate()}
          >
            {t("副本诊断（不递送）")}
          </Button>
          <p className="footnote">
            {t(
              "在最新检查点的独立副本上观察 0.5 秒，不改变原意识；不经过环境和躯体过滤。",
            )}
          </p>
          <ErrorBox error={diagnostic.error} />
          {!!diagnostic.data && (
            <details open>
              <summary>{t("输入、触达、激活与巩固诊断")}</summary>
              <pre>{JSON.stringify(diagnostic.data, null, 2)}</pre>
            </details>
          )}
          {mode === "text-sensor" && (
            <Field label={t("刺激强度")}>
              <input
                type="number"
                min={0}
                max={100}
                step="any"
                value={intensity}
                onChange={(e) => setIntensity(Number(e.target.value))}
                required
              />
            </Field>
          )}
          <Field label={t("起点延迟（模拟毫秒）")}>
            <input
              type="number"
              min={0}
              max={1e9}
              step="0.001"
              value={delay}
              onChange={(e) => setDelay(Number(e.target.value))}
              required
            />
          </Field>
          <p className="footnote">{t("从内核处理该输入命令的时刻起计算。")}</p>
        </details>
      )}
      {disabled && (
        <p>
          {run.spec.study_id
            ? t("实验协议已冻结；请分叉为独立意识后添加输入。")
            : !allowed
              ? t("实例已结束，请分叉后继续。")
              : sourceBlocked
                ? t("当前来源准入已关闭，可在来源策略中调整。")
                : t("文本感官已停用，可在参数配置中开启。")}
        </p>
      )}
      <ErrorBox error={localError ?? submit.error} />
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      <Button variant="primary" disabled={disabled || submit.isPending}>
        <Send size={15} />
        {submit.isPending
          ? t("提交中…")
          : compact
            ? t("发送")
            : t("接收并排队")}
      </Button>
    </form>
  );
}

export default function SensoryPage({
  base,
  run,
  configure,
  initialTool,
  initialInput,
}: {
  base: string;
  run: Run;
  configure: (group?: string) => void;
  initialTool?: string;
  initialInput?: string;
}) {
  const validTool = (value?: string) =>
    [
      "catalogue",
      "history",
      "body",
      "media",
      "outputs",
      "telemetry",
      "capture",
      "devices",
      "attention",
      "sources",
    ].includes(value ?? "");
  const [view, setView] = useState(
    validTool(initialTool) ? initialTool! : "history",
  );
  useEffect(() => {
    if (validTool(initialTool)) setView(initialTool!);
  }, [initialTool]);
  const [source, setSource] = useState(""),
    [status, setStatus] = useState("");
  const [pages, setPages] = useState([0]),
    [selected, setSelected] = useState(initialInput ?? "");
  const [framePages, setFramePages] = useState([-1]);
  useEffect(() => {
    if (initialInput) {
      setSelected(initialInput);
      setFramePages([-1]);
    }
  }, [initialInput]);
  const [records, setRecords] = useState("frames"),
    [format, setFormat] = useState("jsonl");
  const active = ["queued", "running"].includes(run.status);
  const common = {
    gcTime: 0,
    refetchInterval: active ? 3000 : (false as const),
  };
  const registry = useQuery({
    queryKey: ["sensory", run.id, "registry", run.spec],
    queryFn: () => api(`${base}/sensory`),
    gcTime: 0,
  });
  const queue = useQuery({
    queryKey: ["sensory", run.id, "queue", run.revision],
    queryFn: () => api(`${base}/input-queue`),
    ...common,
  });
  const query = new URLSearchParams({
    after: String(pages.at(-1)),
    limit: "30",
  });
  if (source) query.set("source", source);
  if (status) query.set("status", status);
  const history = useQuery({
    queryKey: ["sensory", run.id, "history", query.toString(), run.revision],
    queryFn: () => api(`${base}/inputs?${query}`),
    ...common,
  });
  const detail = useQuery({
    queryKey: [
      "sensory",
      run.id,
      "detail",
      selected,
      framePages.at(-1),
      run.revision,
    ],
    queryFn: () =>
      api(`${base}/inputs/${selected}?after=${framePages.at(-1)}&limit=30`),
    enabled: !!selected,
    ...common,
  });
  const exports = new URLSearchParams({ records, format });
  if (source) exports.set("source", source);
  const item = detail.data?.envelope;
  return (
    <div className="sensory-page">
      <section className="panel sensory-registry">
        <div className="panel-heading">
          <div>
            <h2>{t("感官接线与输入总线")}</h2>
            <p>
              {t(
                "运行时负责接线、编码和来源策略；内核接收带时间戳的匿名刺激与逐帧竞争标记。",
              )}
            </p>
          </div>
          <Button onClick={() => configure()}>
            <Settings2 size={15} />
            {t("配置感官与预算")}
          </Button>
        </div>
        <ErrorBox error={registry.error ?? queue.error} />
        <details className="sensory-wiring-details">
          <summary>
            {t("查看感官、器官与环境接线（")}
            {registry.data?.adapters.filter((a: any) => a.enabled).length ??
              0}{" "}
            {t("项启用）")}
          </summary>
          <div className="sensory-cards">
            {registry.data?.adapters.map((a: any) => (
              <article key={a.id}>
                <span className={`badge ${a.enabled ? "running" : "paused"}`}>
                  {a.enabled ? t("配置启用") : t("配置停用")}
                </span>
                <h3>{t(a.name)}</h3>
                <p>{t(a.description)}</p>
                <small className="mono">
                  {a.id} · {a.version}
                </small>
              </article>
            ))}
          </div>
        </details>
        <Button onClick={() => setView("catalogue")}>
          {t("查看适配器、能力与参数")}
        </Button>
        {registry.data && (
          <p className="footnote">
            {t("文本：")}
            {t(encodings[registry.data.text_sensor.encoding])}
            {t(" · 每帧")} {registry.data.text_sensor.frame_characters}
            {t(" 字符 · 间隔")} {registry.data.text_sensor.frame_interval_us}
            {t(" μs · 接线种子")} {registry.data.seed}
            {t("。待递送人工输入预算：")}
            {registry.data.input_bus.max_pending_frames.toLocaleString(
              locale(),
            )}
            {t(" 帧 /")}{" "}
            {registry.data.input_bus.max_pending_channels.toLocaleString(
              locale(),
            )}{" "}
            {t("通道值。")}
          </p>
        )}
        {queue.data && (
          <div className="input-queue-summary" aria-label={t("输入队列状态")}>
            <span>
              {t("已提交队列 ")}
              <strong>
                {queue.data.pending_frames}
                {t(" 帧")}
              </strong>
            </span>
            <span>
              {t("通道值")}{" "}
              <strong>
                {queue.data.pending_channels.toLocaleString(locale())}
              </strong>
            </span>
            <span>
              {t("数据库版本 ")}
              <strong>r{queue.data.revision}</strong>
            </span>
            <span>
              {t("下一帧")}{" "}
              <strong>
                {queue.data.next
                  ? `${queue.data.next.scheduled_time_us} μs`
                  : t("无")}
              </strong>
            </span>
          </div>
        )}
        <p className="footnote">
          {t(
            "队列展示最近检查点；刚接收的载体可能还未排入。暂停时接收的输入会等待继续运行。新接收内容保留其当时的编码配置，之后修改配置不改变这些载体。",
          )}
        </p>
        <Link className="text-link" to="/docs?doc=docs%2Fzh%2Fv2-inputs.md">
          {t("输入、分帧与证据说明")}
        </Link>
      </section>
      <nav className="sensory-navigation" aria-label={t("感官工具")}>
        <Button
          aria-pressed={view === "catalogue"}
          onClick={() => setView("catalogue")}
        >
          {t("适配器目录")}
        </Button>
        <Button aria-pressed={view === "body"} onClick={() => setView("body")}>
          {t("环境与躯体")}
        </Button>
        <Button
          aria-pressed={view === "history"}
          onClick={() => setView("history")}
        >
          {t("输入记录")}
        </Button>
        <Button
          aria-pressed={view === "media"}
          onClick={() => setView("media")}
        >
          {t("媒体输入")}
        </Button>
        <Button
          aria-pressed={view === "outputs"}
          onClick={() => setView("outputs")}
        >
          {t("器官输出")}
        </Button>
        <Button
          aria-pressed={view === "telemetry"}
          onClick={() => setView("telemetry")}
        >
          {t("物理遥测")}
        </Button>
        <Button
          aria-pressed={view === "capture"}
          onClick={() => setView("capture")}
        >
          {t("连续设备")}
        </Button>
        <Button
          aria-pressed={view === "devices"}
          onClick={() => setView("devices")}
        >
          {t("网络设备")}
        </Button>
        <Button
          aria-pressed={view === "attention"}
          onClick={() => setView("attention")}
        >
          {t("输入注意")}
        </Button>
        <Button
          aria-pressed={view === "sources"}
          onClick={() => setView("sources")}
        >
          {t("来源与竞争")}
        </Button>
      </nav>
      {view === "catalogue" && (
        <Suspense fallback={<Loading />}>
          <AdapterCatalogue base={base} run={run} configure={configure} />
        </Suspense>
      )}
      {view === "sources" && (
        <Suspense fallback={<Loading />}>
          <SourcePolicyPanel
            base={base}
            run={run}
            configure={() => configure("source_policies")}
          />
        </Suspense>
      )}
      {view === "devices" && (
        <Suspense fallback={<Loading />}>
          <DevicePanel
            base={base}
            run={run}
            inspect={(id) => {
              setSelected(id);
              setFramePages([-1]);
            }}
          />
        </Suspense>
      )}
      {view === "body" && (
        <BodyPanel
          base={base}
          run={run}
          configure={configure}
          inspect={(id) => {
            setSelected(id);
            setFramePages([-1]);
          }}
        />
      )}
      {view === "attention" && (
        <AttentionPanel base={base} run={run} configure={configure} />
      )}
      {view === "capture" && (
        <LiveCapturePanel base={base} run={run} configure={configure} />
      )}
      {view === "media" && (
        <MediaInput
          base={base}
          run={run}
          configure={configure}
          capabilities={registry.data?.media_capabilities}
        />
      )}
      {view === "outputs" && (
        <OrganOutputs base={base} run={run} configure={configure} />
      )}
      {view === "telemetry" && (
        <TelemetryPanel
          base={base}
          run={run}
          configure={configure}
          inspect={(id) => {
            setSelected(id);
            setFramePages([-1]);
          }}
        />
      )}
      <section className="panel" hidden={view !== "history"}>
        <div className="panel-heading">
          <div>
            <h2>{t("输入记录")}</h2>
            <p>{t("从原始载体追溯到每一帧的计划时间与实际递送时间。")}</p>
          </div>
          <Button
            onClick={() => {
              history.refetch();
              queue.refetch();
            }}
          >
            <RefreshCw size={15} />
            {t("刷新记录")}
          </Button>
        </div>
        <div className="input-filters">
          <Field label={t("输入来源")}>
            <select
              value={source}
              onChange={(e) => {
                setSource(e.target.value);
                setPages([0]);
              }}
            >
              <option value="">{t("全部来源")}</option>
              {Object.entries(sources).map(([v, n]) => (
                <option key={v} value={v}>
                  {n}
                </option>
              ))}
              {registry.data?.network_devices?.map((device: any) => (
                <option key={device.id} value={`remote:${device.id}`}>
                  {t("网络设备 · ")}
                  {device.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("递送状态")}>
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPages([0]);
              }}
            >
              <option value="">{t("全部状态")}</option>
              {["accepted", "scheduled", "completed", "rejected"].map((v) => (
                <option key={v} value={v}>
                  {t(statuses[v])}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <ErrorBox error={history.error} />
        {history.isPending ? (
          <Loading />
        ) : history.data?.rows.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t("载体 / 接收时间")}</th>
                  <th>{t("来源")}</th>
                  <th>{t("状态")}</th>
                  <th>{t("已递送 / 总帧")}</th>
                  <th>{t("过滤")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {history.data.rows.map((r: any) => (
                  <tr key={r.id}>
                    <td>
                      <span className="mono">{r.id.slice(0, 8)}</span>
                      <small className="input-date">
                        {new Date(r.created_at).toLocaleString(locale())}
                      </small>
                    </td>
                    <td>{t(sources[r.source] ?? r.source)}</td>
                    <td>{t(statuses[r.status])}</td>
                    <td>
                      {r.delivered_count} / {r.frame_count}
                    </td>
                    <td>{r.filtered_count}</td>
                    <td>
                      <Button
                        variant="small"
                        onClick={() => {
                          setSelected(r.id);
                          setFramePages([-1]);
                        }}
                      >
                        {t("查看载体与帧")}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title={t("该条件下暂无输入记录")}
            detail={t(
              "可在意识网络右侧递送文本；环境采样和重放请切换相应来源。",
            )}
          />
        )}
        <div className="pagination">
          <Button
            disabled={pages.length === 1}
            onClick={() => setPages((p) => p.slice(0, -1))}
          >
            {t("上一页")}
          </Button>
          <span>{t("第 {page} 页", { page: pages.length })}</span>
          <Button
            disabled={!history.data?.more}
            onClick={() => setPages((p) => [...p, history.data.next])}
          >
            {t("下一页")}
          </Button>
        </div>
        <div className="input-export">
          <Field label={t("导出内容")}>
            <select
              value={records}
              onChange={(e) => setRecords(e.target.value)}
            >
              <option value="frames">{t("逐帧递送与通道值")}</option>
              <option value="envelopes">{t("原始载体与编码配置")}</option>
            </select>
          </Field>
          <Field label={t("记录格式")}>
            <select value={format} onChange={(e) => setFormat(e.target.value)}>
              <option value="jsonl">{t("JSONL（保留完整结构）")}</option>
              <option value="csv">{t("CSV 表格")}</option>
            </select>
          </Field>
          <a
            className="button"
            href={`/api/v2${base}/inputs/export?${exports}`}
          >
            <Download size={15} />
            {t("导出记录")}
          </a>
        </div>
        <p className="footnote">
          {t(
            "导出当前来源的全部记录，不受页面、状态筛选限制。历史检查点证据请使用“模型与证据”中的证据包。",
          )}
        </p>
      </section>
      <Modal
        wide
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) setSelected("");
        }}
        title={t("载体与递送证据")}
        description={t(
          "原始载体、编码配置和递送结果分别保留。观察标签不参与内核计算。",
        )}
      >
        <ErrorBox error={detail.error} />
        {detail.isPending ? (
          <Loading />
        ) : (
          item && (
            <div className="input-detail">
              <p>
                {t(sources[item.source] ?? item.source)} ·{" "}
                {t(statuses[item.status])} · {item.delivered_count} /{" "}
                {item.frame_count}
                {t(" 帧已递送")}
              </p>
              <ErrorBox error={item.error} />
              <h3>{t("原始载体")}</h3>
              <pre>{JSON.stringify(item.payload, null, 2).slice(0, 16000)}</pre>
              {JSON.stringify(item.payload).length > 16000 && (
                <p>{t("载体预览最多 16,000 字符，完整内容可导出。")}</p>
              )}
              <details>
                <summary>{t("编码配置与校验值")}</summary>
                <pre>{JSON.stringify(item.configuration, null, 2)}</pre>
                <p className="mono">
                  {t("载体 SHA-256: ")}
                  {item.payload_hash}
                  <br />
                  {t("配置 SHA-256: ")}
                  {item.configuration_hash}
                </p>
              </details>
              {item.payload.asset_sha256 && (
                <p>
                  <a
                    className="button"
                    href={`/api/v2${base}/media/${item.id}/original`}
                  >
                    <Download size={15} />
                    {t("下载媒体原件")}
                  </a>
                  <span className="mono media-sha">
                    {t("原件 SHA-256: ")}
                    {item.payload.asset_sha256}
                  </span>
                </p>
              )}
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>{t("帧序号")}</th>
                      <th>{t("状态")}</th>
                      <th>{t("计划时间 μs")}</th>
                      <th>{t("递送时间 μs")}</th>
                      <th>{t("脉冲与观察标签")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.data.frames.map((f: any) => (
                      <tr key={f.frame_index}>
                        <td>{f.frame_index + 1}</td>
                        <td>
                          {t(statuses[f.status])}
                          {f.reason && <small>{f.reason}</small>}
                        </td>
                        <td className="mono">{f.scheduled_time_us}</td>
                        <td className="mono">{f.delivered_time_us ?? "—"}</td>
                        <td>
                          <details>
                            <summary>
                              {t("原始 ")}
                              {f.channel_count}
                              {t(" 通道")}
                              {f.input_gate
                                ? t(" → 通过 {value0} / 抑制 {value1}", {
                                    value0: String(
                                      f.input_gate.passed_channels,
                                    ),
                                    value1: String(
                                      f.input_gate.suppressed_channels,
                                    ),
                                  })
                                : ""}
                            </summary>
                            <pre>
                              {JSON.stringify(
                                {
                                  event_id: f.core_event_id,
                                  stimulus: f.stimulus,
                                  input_gate: f.input_gate,
                                  source_policy: f.source_policy,
                                  labels: f.labels,
                                },
                                null,
                                2,
                              )}
                            </pre>
                          </details>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!detail.data.frames.length && (
                <p>
                  {t(
                    "载体尚未排入内核；若当前已暂停，请继续运行以处理输入命令。",
                  )}
                </p>
              )}
              <div className="pagination">
                <Button
                  disabled={framePages.length === 1}
                  onClick={() => setFramePages((p) => p.slice(0, -1))}
                >
                  {t("上一组帧")}
                </Button>
                <span>{t("第 {page} 页", { page: framePages.length })}</span>
                <Button
                  disabled={!detail.data.more}
                  onClick={() => setFramePages((p) => [...p, detail.data.next])}
                >
                  {t("下一组帧")}
                </Button>
              </div>
            </div>
          )
        )}
      </Modal>
    </div>
  );
}
