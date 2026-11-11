import { can } from "./access";
import { t } from "./i18n";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Upload, Volume2, Settings2 } from "lucide-react";
import { api, timeLabel, type Run } from "./api";
import OrganMonitor from "./organMonitor";
import { Link } from "react-router-dom";
import { Button, Empty, ErrorBox, Field, useWorkspace } from "./ui";
import {
  transferMedia,
  type MediaUpload,
  type TransferProgress,
} from "./mediaTransfer";
import MediaUploadQueue, { mediaSize, uploadStages } from "./mediaUploadQueue";

function Preview({ file, kind }: { file: File | null; kind: string }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    if (!file) {
      setUrl("");
      return;
    }
    const value = URL.createObjectURL(file);
    setUrl(value);
    return () => URL.revokeObjectURL(value);
  }, [file]);
  if (!url) return null;
  return (
    <div className="media-carrier-preview">
      {kind === "image" ? (
        <img src={url} alt={t("待递送的图片原件预览")} />
      ) : kind === "audio" ? (
        <audio src={url} controls preload="metadata" />
      ) : (
        <video src={url} controls preload="metadata" />
      )}
      <span>{t("本地原件预览 · 尚不代表已进入内核")}</span>
    </div>
  );
}

export function MediaInput({
  base,
  run,
  configure,
  capabilities,
  initialKind = "audio",
  initialIntensity = 1,
}: {
  base: string;
  run: Run;
  configure: (kind?: string) => void;
  capabilities?: any;
  initialKind?: string;
  initialIntensity?: number;
}) {
  const client = useQueryClient();
  const [kind, setKind] = useState(initialKind);
  const policyEnabled =
    run.spec.source_policies?.manual_enabled !== false &&
    run.spec.source_policies?.[`${kind}_enabled`] !== false;
  const [file, setFile] = useState<File | null>(null);
  const [intensity, setIntensity] = useState(initialIntensity),
    [delay, setDelay] = useState(0);
  const [notice, setNotice] = useState("");
  const attempt = useRef({ key: "", id: "" });
  const controller = useRef<AbortController | null>(null);
  const [resume, setResume] = useState<MediaUpload | null>(null);
  const [activeId, setActiveId] = useState("");
  const [progress, setProgress] = useState<TransferProgress | null>(null);
  const { project, user } = useWorkspace();
  useEffect(() => () => controller.current?.abort(), []);
  const current = useQuery<MediaUpload>({
    queryKey: ["media-upload-status", base, activeId],
    queryFn: () => api(`${base}/media-uploads/${activeId}`),
    enabled: !!activeId,
    refetchInterval: (q) =>
      ["uploading", "processing", "cancel_requested"].includes(
        q.state.data?.status ?? "uploading",
      )
        ? 1000
        : false,
  });
  const config =
    run.spec[kind === "audio" ? "auditory_sensor" : "visual_sensor"];
  const eligible =
    ["running", "queued", "paused", "blocked"].includes(run.status) &&
    run.life !== "dead" &&
    project?.role !== "viewer" && can(user,"runs.stimulate") &&
    !run.spec.study_id;
  const available =
    kind === "audio"
      ? true
      : kind === "image"
        ? capabilities?.images
        : capabilities?.video_codecs;
  const upload = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error(t("请先选择媒体文件。"));
      if (file.size > config.upload_limit_mb * 1024 ** 2)
        throw new Error(
          t("原件超过 {value0} MiB，整条未提交。", {
            value0: String(config.upload_limit_mb),
          }),
        );
      const key = `${kind}:${file.name}:${file.size}:${file.lastModified}:${intensity}:${delay}`;
      if (resume && file.size !== Number(resume.byte_length))
        throw new Error(t("所选原件大小与该上传不符，请选择原文件。"));
      if (resume) attempt.current = { key, id: resume.id };
      else if (attempt.current.key !== key)
        attempt.current = { key, id: crypto.randomUUID() };
      setProgress({ stage: "uploading", bytes: 0, total: file.size });
      controller.current = new AbortController();
      try {
        return await transferMedia(
          base,
          file,
          resume?.metadata ?? {
            kind,
            filename: file.name,
            intensity,
            delay_us: Math.round(delay * 1000),
          },
          attempt.current.id,
          (value) => {
            setActiveId(attempt.current.id);
            setProgress(value);
            if (value.stage === "processing")
              client.invalidateQueries({
                queryKey: ["media-upload-status", base],
              });
          },
          controller.current.signal,
        );
      } catch (error) {
        if (controller.current.signal.aborted)
          throw new Error(
            t(
              "本页已停止传输或等待。已确认分块保留；正在进行的服务器解码仍可在下方查看或取消。",
            ),
          );
        throw error;
      }
    },
    onSuccess: (value) => {
      attempt.current = { key: "", id: "" };
      setResume(null);
      setFile(null);
      setProgress(null);
      setNotice(
        value.frame_count === 0
          ? t(
              "已保存原件和转换记录。此载体未产生非零刺激帧；继续运行后会完成这条零刺激记录。",
            )
          : t("已接收 {value0} 帧、{value1} 个通道值。{value2}", {
              value0: String(value.frame_count),
              value1: String(value.channel_count),
              value2: t(
                run.status === "paused"
                  ? "继续运行后递送。"
                  : "可在下方输入记录追踪递送结果。",
              ),
            }),
      );
      client.invalidateQueries({ queryKey: ["sensory", run.id] });
    },
    onSettled: () => {
      client.invalidateQueries({ queryKey: ["media-uploads", base] });
      client.invalidateQueries({ queryKey: ["media-upload-status", base] });
    },
  });
  return (
    <section className="panel media-input">
      <div className="panel-heading">
        <div>
          <h2>{t("音视频与图片输入")}</h2>
          <p>
            {t(
              "选择原件，由感官转换为匿名脉冲。原件和转换配置保存在当前项目数据库。",
            )}
          </p>
        </div>
        <Button disabled={!can(user,"runs.configure")} onClick={() => configure(kind)}>
          <Settings2 size={15} />
          {t("配置感官")}
        </Button>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setNotice("");
          upload.mutate();
        }}
      >
        {resume && (
          <div className="notice media-resume-notice">
            {t("继续上传：")}
            {resume.metadata.filename}（{mediaSize(resume.byte_length)}
            {t("）。请选择原文件；续传会核对已经保存的每一块。")}
            <Button
              type="button"
              disabled={upload.isPending}
              onClick={() => {
                setResume(null);
                setFile(null);
                setActiveId("");
                setProgress(null);
                attempt.current = { key: "", id: "" };
              }}
            >
              {t("退出续传")}
            </Button>
          </div>
        )}
        <div className="media-input-fields">
          <Field label={t("媒体种类")}>
            <select
              value={kind}
              disabled={upload.isPending || !!resume}
              onChange={(e) => {
                setKind(e.target.value);
                setFile(null);
                setNotice("");
                upload.reset();
                setProgress(null);
                setActiveId("");
                if (!resume) attempt.current = { key: "", id: "" };
              }}
            >
              <option value="audio">{t("声音 · 听觉感官")}</option>
              <option value="image">{t("图片 · 视觉感官")}</option>
              <option value="video">{t("视频 · 视觉感官")}</option>
            </select>
          </Field>
          <Field label={t("选择媒体原件")}>
            <input
              key={`${kind}:${resume?.id ?? "new"}`}
              type="file"
              disabled={upload.isPending}
              accept={
                kind === "audio"
                  ? "audio/*,.wav"
                  : kind === "image"
                    ? "image/*"
                    : "video/*"
              }
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                upload.reset();
                setNotice("");
                attempt.current = { key: "", id: "" };
              }}
            />
          </Field>
        </div>
        <Preview file={file} kind={kind} />
        <details className="media-delivery-options">
          <summary>{t("递送选项与接收范围")}</summary>
          <div className="media-input-fields">
            <Field label={t("媒体刺激强度")}>
              <input
                type="number"
                min={0}
                max={100}
                step="any"
                value={intensity}
                disabled={upload.isPending || !!resume}
                onChange={(e) => setIntensity(Number(e.target.value))}
                required
              />
            </Field>
            <Field label={t("媒体起点延迟（模拟毫秒）")}>
              <input
                type="number"
                min={0}
                max={1e9}
                step="0.001"
                value={delay}
                disabled={upload.isPending || !!resume}
                onChange={(e) => setDelay(Number(e.target.value))}
                required
              />
            </Field>
          </div>
          <p>
            {t("原件上限 ")}
            {config?.upload_limit_mb ?? (kind === "audio" ? 32 : 128)}{" "}
            {t("MiB；时长上限 ")}
            {config?.max_duration_s ?? 120}{" "}
            {t("秒。转换帧还受输入总线预算约束；超限会整条拒绝。")}
          </p>
          <p>
            {kind === "video"
              ? t(
                  "按实际画面时间戳采样。此入口只递送视频画面，音轨不会自动输入；视频旋转显示元数据不参与视网膜采样。",
                )
              : kind === "audio"
                ? t("按物理样本时长分窗；尾段不补零。各文件分别建立变化基线。")
                : t("按视网膜块依次递送；支持单帧图片，动画图片需转为视频。")}
          </p>
        </details>
        {!config?.enabled && (
          <p className="notice">
            {t("该感官默认关闭。请先通过“配置感官”开启，再接收文件。")}
          </p>
        )}
        {!eligible && (
          <p>
            {project?.role === "viewer"
              ? t("当前项目权限只允许查看，不能添加媒体。")
              : run.spec.study_id
                ? t("实验协议已冻结；请分叉为独立运行后添加载体。")
                : t("当前实例已结束，请分叉后输入。")}
          </p>
        )}
        {!available && kind !== "audio" && (
          <p>
            {t(
              "当前服务缺少该媒体格式所需的解码依赖，详见文档中的 media 安装说明。",
            )}
          </p>
        )}
        <ErrorBox error={upload.error} />
        {(progress || activeId) && (
          <div
            className="media-transfer-progress"
            role="status"
            aria-label={t("媒体处理进度")}
          >
            <strong>
              {current.data?.status === "processing"
                ? uploadStages[current.data.stage]
                : progress && upload.isPending
                  ? uploadStages[progress.stage]
                  : t(uploadStages[current.data?.stage ?? "uploading"])}
            </strong>
            {progress &&
              upload.isPending &&
              progress.stage !== "processing" && (
                <>
                  <progress
                    aria-label={t("已核对与传输的原件比例")}
                    value={progress.bytes}
                    max={progress.total}
                  />
                  <span>
                    {mediaSize(progress.bytes)} / {mediaSize(progress.total)}
                  </span>
                </>
              )}
            {current.data?.status === "processing" && (
              <span>
                {t("原件已完整传输；已形成 ")}
                {current.data.progress_frames}{" "}
                {t("个感官帧。解码进度不以文件读取位置估算。")}
              </span>
            )}
            {current.data?.error && <span>{current.data.error}</span>}
            {current.data?.status === "accepted" && (
              <span>{t("原件与转换帧已提交；实际递送结果见输入记录。")}</span>
            )}
          </div>
        )}
        {notice && (
          <p className="notice" role="status" aria-label={t("媒体接收结果")}>
            {notice}
          </p>
        )}
        <div className="media-input-actions">
          {!policyEnabled && (
            <p className="notice">
              {t("此类媒体来源已关闭。")}
              <Link className="text-link" to="?view=inputs&tool=sources">
                {t("查看来源策略")}
              </Link>
            </p>
          )}
          <Button
            variant="primary"
            disabled={
              !file ||
              !config?.enabled ||
              !policyEnabled ||
              !eligible ||
              !available ||
              upload.isPending
            }
          >
            <Upload size={15} />
            {upload.isPending ? t("上传、转换与校验中…") : t("接收媒体并排队")}
          </Button>
          {upload.isPending && (
            <Button type="button" onClick={() => controller.current?.abort()}>
              {t("停止本页传输／等待")}
            </Button>
          )}
          <a className="button" href={`/api/v2${base}/media/export`}>
            <Download size={15} />
            {t("导出媒体原件 ZIP")}
          </a>
        </div>
        <p className="footnote">
          {t(
            "原件 ZIP 包含当前运行已接收的媒体与 SHA-256 清单。每帧的计划及实际递送时间在“输入记录”中导出。麦克风、摄像头请使用“连续设备”入口。",
          )}
        </p>
      </form>
      <MediaUploadQueue
        base={base}
        busy={upload.isPending}
        eligible={eligible}
        onResume={(row) => {
          setResume(row);
          setActiveId(row.id);
          setKind(row.metadata.kind);
          setIntensity(row.metadata.intensity);
          setDelay(row.metadata.delay_us / 1000);
          setFile(null);
          setProgress(null);
          upload.reset();
          setNotice(
            t(
              "请选择原文件后点击接收媒体并排队；已完成的分块只校验、不重复上传。",
            ),
          );
          attempt.current = { key: "", id: row.id };
        }}
      />
    </section>
  );
}

export function Projection({ image, at }: { image: any; at: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!image || !canvas.current) return;
    const context = canvas.current.getContext("2d");
    if (!context) return;
    const output = context.createImageData(image.width, image.height);
    for (let i = 0; i < image.width * image.height; i++) {
      const value = parseInt(image.gray8_hex.slice(i * 2, i * 2 + 2), 16);
      output.data.set([value, value, value, 255], i * 4);
    }
    context.putImageData(output, 0, 0);
  }, [image]);
  if (!image)
    return (
      <Empty
        title={t("此采样未启用投影器")}
        detail={t("可在输出器官配置中开启，之后的观测采样才会记录图像。")}
      />
    );
  return (
    <div className="organ-projection">
      <canvas
        ref={canvas}
        width={image.width}
        height={image.height}
        aria-label={t("匿名节点活动的灰度投影")}
      />
      <p>
        {image.width} × {image.height}
        {t(" 灰度像素")}
      </p>
      <Button
        onClick={() =>
          canvas.current?.toBlob((blob) => {
            if (!blob) return;
            const url = URL.createObjectURL(blob),
              link = document.createElement("a");
            link.href = url;
            link.download = `activation-${at}us.png`;
            link.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
          })
        }
      >
        <Download size={15} />
        {t("导出此帧 PNG")}
      </Button>
    </div>
  );
}

export function OrganOutputs({
  base,
  run,
  configure,
}: {
  base: string;
  run: Run;
  configure: () => void;
}) {
  const [pages, setPages] = useState<string[]>([""]),
    [selected, setSelected] = useState(0);
  const [soundError, setSoundError] = useState<unknown>(null),
    [playing, setPlaying] = useState(false);
  const audio = useRef<AudioContext | null>(null);
  useEffect(
    () => () => {
      audio.current?.close().catch(() => {});
    },
    [],
  );
  const history = useQuery({
    queryKey: ["organs", run.id, pages.at(-1)],
    queryFn: () =>
      api(
        `${base}/organs?limit=5${pages.at(-1) ? `&before_id=${pages.at(-1)}` : ""}`,
      ),
    gcTime: 0,
    refetchInterval:
      ["running", "queued"].includes(run.status) && pages.length === 1
        ? 2000
        : false,
  });
  const row = history.data?.rows[selected] ?? history.data?.rows[0];
  const output = row?.payload;
  const listen = async () => {
    try {
      setSoundError(null);
      setPlaying(true);
      const context = new AudioContext();
      audio.current = context;
      await context.resume();
      const voices = output.voices ?? [],
        now = context.currentTime;
      for (const voice of voices) {
        const oscillator = context.createOscillator(),
          gain = context.createGain();
        oscillator.frequency.value = voice.frequency_hz;
        const level =
          (Math.min(1, Math.max(0, voice.amplitude)) * 0.16) /
          Math.max(1, voices.length);
        gain.gain.setValueAtTime(0, now);
        gain.gain.linearRampToValueAtTime(level, now + 0.01);
        gain.gain.setValueAtTime(level, now + 0.49);
        gain.gain.linearRampToValueAtTime(0, now + 0.5);
        oscillator.connect(gain).connect(context.destination);
        oscillator.start(now);
        oscillator.stop(now + 0.5);
      }
      window.setTimeout(() => {
        context.close().catch(() => {});
        if (audio.current === context) {
          audio.current = null;
          setPlaying(false);
        }
      }, 650);
    } catch (error) {
      setSoundError(error);
      setPlaying(false);
      audio.current?.close().catch(() => {});
    }
  };
  return (
    <section className="panel organ-outputs">
      <div className="panel-heading">
        <div>
          <h2>{t("器官输出")}</h2>
          <p>
            {t(
              "只读观察匿名活动。图像是确定性投影，声音是活动合成；不使用文本标签，也不自动反馈给内核。",
            )}
          </p>
        </div>
        <Button onClick={configure}>
          <Settings2 size={15} />
          {t("配置输出器官")}
        </Button>
      </div>
      <ErrorBox error={history.error ?? soundError} />
      <OrganMonitor
        base={base}
        run={run}
        renderProjection={(image, at) => <Projection image={image} at={at} />}
      />
      <h3>{t("完整输出记录")}</h3>
      {!row ? (
        <Empty
          title={t("尚无器官输出记录")}
          detail={t(
            "在参数配置中开启发声器或投影器，然后继续运行。两种器官各自具有独立采样间隔。",
          )}
        />
      ) : (
        <>
          <div className="organ-sample-toolbar">
            <Field label={t("输出采样时刻")}>
              <select
                value={selected}
                onChange={(e) => setSelected(Number(e.target.value))}
              >
                {history.data.rows.map((r: any, i: number) => (
                  <option key={r.event_key} value={i}>
                    {timeLabel(r.time_us)}
                    {t(" · 数据库 r")}
                    {r.commit_revision}
                  </option>
                ))}
              </select>
            </Field>
            <span className="footnote">
              {t("最近提交的观测快照，不是实时音频流")}
            </span>
          </div>
          <div className="organ-output-grid">
            <Projection image={output.image} at={row.time_us} />
            <div>
              <h3>{t("匿名活动发声")}</h3>
              {output.voices ? (
                <>
                  <div className="organ-voice-actions">
                    <Button
                      onClick={listen}
                      disabled={playing || !output.voices.length}
                    >
                      <Volume2 size={15} />
                      {playing ? t("播放中…") : t("试听此帧（0.5 秒）")}
                    </Button>
                    <a
                      className="button"
                      href={`/api/v2${base}/organs/${row.sample_id}/audio.wav`}
                    >
                      <Download size={15} />
                      {t("合成 WAV")}
                    </a>
                  </div>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>{t("节点 ID")}</th>
                          <th>{t("频率 Hz")}</th>
                          <th>{t("幅值")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {output.voices.map((v: any) => (
                          <tr key={v.node_id}>
                            <td>{v.node_id}</td>
                            <td>{v.frequency_hz.toFixed(2)}</td>
                            <td>{v.amplitude.toFixed(4)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {!output.voices.length && (
                    <p>{t("此帧没有超过发声阈值的活动。")}</p>
                  )}
                </>
              ) : (
                <p>{t("此采样未启用发声器。")}</p>
              )}
            </div>
          </div>
          <div className="pagination">
            <Button
              disabled={pages.length === 1}
              onClick={() => {
                setPages((p) => p.slice(0, -1));
                setSelected(0);
              }}
            >
              {t("更新的采样")}
            </Button>
            <span>{t("第 {page} 页", { page: pages.length })}</span>
            <Button
              disabled={!history.data.more}
              onClick={() => {
                setPages((p) => [...p, history.data.next]);
                setSelected(0);
              }}
            >
              {t("更早的采样")}
            </Button>
          </div>
        </>
      )}
      <a className="button" href={`/api/v2${base}/organs/export`}>
        <Download size={15} />
        {t("导出完整输出 JSONL")}
      </a>
      <p className="footnote">
        {t(
          "每条记录包含模拟时间、数据库提交版本、器官配置、振荡器控制值及完整灰度像素。WAV 是所选快照的半秒合成音，不是运行期间录制的声音。",
        )}
      </p>
      <Link
        className="text-link"
        to="/docs?doc=docs%2Fzh%2Fv2-continuous-output.md"
      >
        {t("查看连续输出、采样与保存规则")}
      </Link>
    </section>
  );
}
