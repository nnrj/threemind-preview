import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import { api, post } from "./api";
import {
  Button,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Modal,
  PageTitle,
  useWorkspace,
} from "./ui";
import LanguageEditor from "./LanguageEditor";
import JsonEditor, { parseJson } from "./JsonEditor";
import { t } from "./i18n";
import "./dialogue.css";

export default function Dialogue() {
  const { project } = useWorkspace(),
    client = useQueryClient(),
    [search, setSearch] = useSearchParams();
  const run = search.get("run"),
    root = `/projects/${project?.id}/language`;
  const [draft, setDraft] = useState(""),
    [intensity, setIntensity] = useState(1),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const [creating, setCreating] = useState(false),
    [config, setConfig] = useState<any>(),
    [name, setName] = useState("语言实验意识");
  const [source, setSource] = useState(""),
    [core, setCore] = useState("{}"),
    [offset, setOffset] = useState(0),
    [tab, setTab] = useState("dialogue");
  const [kernel, setKernel] = useState("");
  const [valid, setValid] = useState(true);
  const [watching, setWatching] = useState(false);
  const observedWindows = useRef(0),
    queuedRevision = useRef(-1);
  const previousProject = useRef<string | undefined>(undefined);
  const [corpus, setCorpus] = useState("甲是松子。\n乙是铃铛。"),
    [steps, setSteps] = useState(100),
    [role, setRole] = useState("input");
  const [targets, setTargets] = useState<Record<string, string>>({}),
    [trainBase, setTrainBase] = useState(true);
  const timeline = useRef<HTMLDivElement>(null),
    following = useRef(true),
    request = useRef(crypto.randomUUID());
  const writable = ["owner", "researcher"].includes(project?.role ?? "");
  const catalogue = useQuery({
    queryKey: ["language", project?.id],
    queryFn: () => api<any>(root),
    enabled: !!project,
    refetchInterval: 2500,
  });
  const turns = useQuery({
    queryKey: ["language-turns", project?.id, run, offset],
    queryFn: () => api<any>(`${root}/sessions/${run}/turns?offset=${offset}`),
    enabled: !!project && !!run,
    refetchInterval: 1500,
  });
  const kernels = useQuery({
    queryKey: ["kernel-catalogue"],
    queryFn: () => api<any>("/configuration"),
    enabled: creating,
  });
  const current = catalogue.data?.sessions.find((s: any) => s.id === run);
  const rows = turns.data?.rows ?? [],
    models = catalogue.data?.models ?? [];
  const processing = rows.some((r: any) =>
    ["pending", "leased"].includes(r.status),
  );
  // Results and session status are polled independently. Wait until the session
  // snapshot has caught up before using its revision for the next operation.
  const latestRevision = Math.max(
    0,
    ...rows.map((r: any) => r.result?.revision ?? 0),
  );
  const ready =
    !!current &&
    current.status === "paused" &&
    current.revision >= 1 &&
    current.revision >= latestRevision &&
    current.life !== "dead" &&
    !processing;
  useEffect(() => {
    if (previousProject.current && previousProject.current !== project?.id)
      setSearch({});
    previousProject.current = project?.id;
    setDraft("");
    setOffset(0);
    setConfig(undefined);
    setError(null);
  }, [project?.id]);
  useEffect(() => {
    if (catalogue.data && !config)
      setConfig({
        protocol: catalogue.data.default_protocol,
        compute: catalogue.data.default_compute,
        assets: {},
      });
  }, [catalogue.data, config]);
  useEffect(() => {
    if (following.current && timeline.current)
      timeline.current.scrollTop = timeline.current.scrollHeight;
  }, [turns.data, run]);
  useEffect(() => {
    setWatching(false);
    observedWindows.current = 0;
    queuedRevision.current = -1;
  }, [run, project?.id]);
  useEffect(() => {
    if (!watching) return;
    if (
      current?.life === "dead" ||
      observedWindows.current >= 120 ||
      error ||
      rows.some(
        (r: any) =>
          r.expected_revision === queuedRevision.current &&
          ["failed", "cancelled"].includes(r.status),
      )
    ) {
      setWatching(false);
      return;
    }
    if (
      !ready ||
      busy ||
      !writable ||
      current.revision <= queuedRevision.current
    )
      return;
    const timer = window.setTimeout(() => {
      void observe();
    }, 300);
    return () => window.clearTimeout(timer);
  }, [
    watching,
    current?.revision,
    current?.life,
    ready,
    busy,
    writable,
    error,
    turns.data,
  ]);
  async function attempt(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await client.invalidateQueries({ queryKey: ["language", project?.id] });
      await client.invalidateQueries({
        queryKey: ["language-turns", project?.id, run],
      });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  function prepare(fromCurrent = false) {
    setValid(true);
    setKernel(
      fromCurrent && current
        ? current.kernel_id
        : (kernels.data?.kernels?.find((item: any) => item.default)?.kernel_id ?? ""),
    );
    setConfig(
      fromCurrent && current
        ? {
            protocol: current.protocol,
            compute: current.compute,
            assets: current.assets,
            text_sensor: current.text_sensor,
            seed: current.seed,
          }
        : {
            protocol: catalogue.data.default_protocol,
            compute: catalogue.data.default_compute,
            assets: {},
          },
    );
    setSource(fromCurrent ? (run ?? "") : "");
    setCreating(true);
    request.current = crypto.randomUUID();
  }
  async function create() {
    await attempt(async () => {
      const result = await post(`${root}/sessions`, {
        request_id: request.current,
        name,
        ...config,
        ...(kernel ? { kernel_id: kernel } : {}),
        config: parseJson(core),
        ...(source ? { source_run_id: source } : {}),
      });
      setCreating(false);
      request.current = crypto.randomUUID();
      setSearch({ run: result.run_id });
      setOffset(0);
    });
  }
  async function send() {
    if (!draft.trim() || !ready) return;
    setWatching(false);
    await attempt(async () => {
      await post(`${root}/sessions/${run}/turns`, {
        request_id: request.current,
        expected_revision: current.revision,
        text: draft,
        intensity,
      });
      setDraft("");
      request.current = crypto.randomUUID();
      setOffset(0);
      following.current = true;
    });
  }
  async function observe() {
    if (!ready || busy) return;
    await attempt(async () => {
      await post(`${root}/sessions/${run}/observations`, {
        request_id: crypto.randomUUID(),
        expected_revision: current.revision,
      });
      queuedRevision.current = current.revision;
      observedWindows.current += 1;
      setOffset(0);
    });
  }
  async function trainScratch() {
    await attempt(async () => {
      if (!current) throw Error(t("请先选择意识"));
      await post(`${root}/scratch-training`, {
        request_id: crypto.randomUUID(),
        checkpoint: current.assets[role] ?? null,
        training: {
          protocol: current.protocol,
          compute: current.compute,
          role,
          texts: corpus.split(/\r?\n/).filter((s) => s.length),
          steps,
        },
      });
    });
  }
  async function trainHead() {
    await attempt(async () => {
      if (!current) throw Error(t("请先选择意识"));
      const samples = rows
        .filter((r: any) => targets[r.job_id]?.trim() && r.result)
        .map((r: any) => ({
          features: r.result.process.features,
          text: targets[r.job_id],
        }));
      if (samples.length < 2)
        throw Error(t("至少选择两次活动并填写对应的校准文字"));
      await post(`${root}/head-training`, {
        request_id: crypto.randomUUID(),
        checkpoint: current.assets.output ?? null,
        training: {
          protocol: current.protocol,
          compute: current.compute,
          samples,
          steps,
          train_decoder:
            current.protocol.output_model === "scratch" && trainBase,
        },
      });
    });
  }
  if (!project)
    return (
      <Empty
        title={t("请选择项目")}
        detail={t("对话、转换器与训练证据按项目保存。")}
      />
    );
  if (!catalogue.data)
    return catalogue.error ? <ErrorBox error={catalogue.error} /> : <Loading />;
  return (
    <>
      <PageTitle
        eyebrow="LANGUAGE LAB"
        title={t("对话实验")}
        description={t(
          "让语言经过感官适配器进入意识，观察其实际活动，再选择是否转换为语言。",
        )}
      />
      <div className="language-toolbar">
        <Link className="button" to={`/dialogue/replay?project=${project.id}`}>
          {t("教学回放与视频")}
        </Link>
        <Field label={t("意识")}>
          <select
            value={run ?? ""}
            onChange={(e) => {
              setSearch(e.target.value ? { run: e.target.value } : {});
              setOffset(0);
              request.current = crypto.randomUUID();
            }}
          >
            <option value="">{t("选择语言实验意识")}</option>
            {catalogue.data.sessions.map((s: any) => (
              <option key={s.id} value={s.id}>
                {s.name} · {s.status}
              </option>
            ))}
          </select>
        </Field>
        <Button onClick={() => prepare()} disabled={!writable}>
          {t("创建意识")}
        </Button>
        {current && (
          <Button
            onClick={() => prepare(true)}
            disabled={!writable || current.revision < 1}
          >
            {t("从此意识建立对照")}
          </Button>
        )}
      </div>
      <ErrorBox error={error || turns.error} />
      <div className="segmented" role="tablist">
        {[
          ["dialogue", "对话与活动"],
          ["training", "训练转换器"],
          ["evidence", "版本与证据"],
        ].map(([v, label]) => (
          <Button
            key={v}
            role="tab"
            aria-selected={tab === v}
            onClick={() => setTab(v)}
          >
            {t(label)}
          </Button>
        ))}
      </div>
      {tab === "dialogue" && (
        <div className="language-workspace">
          <section
            className="language-conversation"
            aria-label={t("对话与原始读出")}
          >
            <div
              className="language-timeline"
              ref={timeline}
              onScroll={(e) => {
                const el = e.currentTarget;
                following.current =
                  el.scrollHeight - el.scrollTop - el.clientHeight < 64;
              }}
            >
              {(offset > 0 || turns.data?.more) && (
                <div className="language-pages">
                  <Button
                    disabled={!turns.data?.more}
                    onClick={() => setOffset(offset + 20)}
                  >
                    {t("更早记录")}
                  </Button>
                  <Button
                    disabled={offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - 20))}
                  >
                    {t("较新记录")}
                  </Button>
                </div>
              )}
              {!run && (
                <Empty
                  title={t("创建一个意识，开始对话实验")}
                  detail={t(
                    "输入可选原文本感官、随机权重 Transformer 或预训练模型，输出可独立选择。",
                  )}
                />
              )}
              {run && !rows.length && (
                <p className="muted">
                  {t(
                    "输入第一句话。未经训练的转换器可能只产生不可读的输出，原始活动仍可观察。",
                  )}
                </p>
              )}
              {[...rows].reverse().map((row: any) => (
                <div key={row.job_id} className="language-turn">
                  <article className="language-message input">
                    <small>
                      {row.text
                        ? `${t("输入刺激")} · ${row.intensity}`
                        : t("无新输入 · 内部活动观察")}
                    </small>
                    <p>
                      {row.text ||
                        t(
                          "正常推进意识，未发送提示。已经在途的输入仍正常递送。",
                        )}
                    </p>
                  </article>
                  {!row.result ? (
                    <article className="language-message">
                      <p>
                        {row.error ??
                          t(row.status === "done" ? "完成" : "正在处理…")}
                      </p>
                    </article>
                  ) : (
                    <>
                      <article className="language-message">
                        <small>
                          {t("意识活动")} ·{" "}
                          {Number(row.result.process.end_us) / 1e6}s
                          {row.result.wall_seconds != null && (
                            <>
                              {" "}
                              · {t("本窗计算耗时")}{" "}
                              {Number(row.result.wall_seconds).toFixed(2)}s
                            </>
                          )}
                        </small>
                        {row.result.readouts
                          .slice(-8)
                          .map((r: any, i: number) => (
                            <p key={i}>{r.payload?.chat?.text ?? r.kind}</p>
                          ))}
                        {row.result.readouts.length > 8 && (
                          <small>{t("最近八条读出；完整记录可下载。")}</small>
                        )}
                        {!row.result.readouts.length && (
                          <p>
                            {t(
                              row.result.process.has_activity
                                ? "本轮已记录活动，尚无完成的时序读出窗口。"
                                : "本轮未观察到激活。",
                            )}
                          </p>
                        )}
                        <div className="language-activities">
                          {[...row.result.final_activities]
                            .sort(
                              (a: any, b: any) => b.activation - a.activation,
                            )
                            .slice(0, 12)
                            .map((n: any) => (
                              <span key={n.id}>
                                #{n.id} <b>{n.activation.toFixed(4)}</b>
                              </span>
                            ))}
                        </div>
                        <small>
                          {t(
                            "末次采样的前十二个激活节点，仅作显示；完整过程已保存。",
                          )}
                        </small>
                        {row.result.process.censored && (
                          <p>{t("观察提前结束，未补造后续状态。")}</p>
                        )}
                      </article>
                      {current?.protocol.output_model !== "raw" && (
                        <article className="language-message interpretation">
                          <small>
                            {t(
                              current?.protocol.mode === "assisted"
                                ? "外部语言辅助"
                                : "活动的语言转换",
                            )}
                          </small>
                          <p>
                            {row.result.interpretation.text ||
                              t(
                                row.result.interpretation.reason ===
                                  "calibration_head_required"
                                  ? "尚未训练活动到语言的映射，请在训练转换器中校准。"
                                  : "没有可读的语言输出；原始活动见上方。",
                              )}
                          </p>
                          {row.result.interpretation.status ===
                            "decoder_failed" && (
                            <p role="alert">
                              {row.result.interpretation.reason}
                            </p>
                          )}
                        </article>
                      )}
                    </>
                  )}
                </div>
              ))}
            </div>
            <form
              className="language-composer"
              onSubmit={(e) => {
                e.preventDefault();
                send();
              }}
            >
              <textarea
                aria-label={t("文本刺激")}
                value={draft}
                maxLength={2048}
                onChange={(e) => {
                  setDraft(e.target.value);
                  request.current = crypto.randomUUID();
                }}
                placeholder={t("输入语言刺激…")}
                onKeyDown={(e) => {
                  if (
                    e.key === "Enter" &&
                    !e.shiftKey &&
                    !e.nativeEvent.isComposing
                  ) {
                    e.preventDefault();
                    send();
                  }
                }}
              />
              <div>
                <Button
                  type="button"
                  disabled={!writable || (!watching && (!ready || busy))}
                  onClick={() => {
                    setError(null);
                    observedWindows.current = 0;
                    queuedRevision.current = -1;
                    setWatching(!watching);
                  }}
                >
                  {watching ? t("停止观察") : t("连续观察内部活动")}
                </Button>
                {watching && (
                  <small>
                    {t(
                      "逐窗显示；无新输入。停止后当前窗口完成，每次最多120窗。",
                    )}
                  </small>
                )}
                <label>
                  {t("刺激强度")}{" "}
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step={0.1}
                    value={intensity}
                    onChange={(e) => {
                      setIntensity(Number(e.target.value));
                      request.current = crypto.randomUUID();
                    }}
                  />
                </label>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={
                    !writable ||
                    busy ||
                    !ready ||
                    !draft.trim() ||
                    !current ||
                    current.revision < 1 ||
                    current.life === "dead"
                  }
                >
                  {t("发送")}
                </Button>
              </div>
            </form>
          </section>
          <aside className="language-inspector">
            <h3>{t("当前实验")}</h3>
            {current ? (
              <>
                <p>
                  {t("输入")}：{current.protocol.input_model}
                </p>
                <p>
                  {t("输出")}：{current.protocol.output_model}
                </p>
                <p>
                  {t("转换方式")}：{current.protocol.mode}
                </p>
                <p>
                  {t("模拟时间")}：{Number(current.time_us) / 1e6}s
                </p>
                <Link to={`/runs/${run}`}>
                  {t("查看意识图像、结构与检查点")}
                </Link>
                <p className="muted">
                  {t(
                    "按轮推进模拟，也可连续观察无新输入活动。未开启观察时等待输入会暂停；计算耗时与模拟时间分别显示。",
                  )}
                </p>
              </>
            ) : (
              <p>{t("请先选择意识")}</p>
            )}
            <Link to="/docs?doc=docs/zh/language-adapters.md">
              {t("语言适配器说明")}
            </Link>
          </aside>
        </div>
      )}
      {tab === "training" && (
        <div className="language-training">
          <section>
            <h2>{t("从随机权重学习文本")}</h2>
            <p>
              {t(
                "只训练外置 Transformer。每行是一个完整样本，不改标点，不改 Core 参数。",
              )}
            </p>
            <Field label={t("训练输入或输出模型")}>
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="input">{t("输入")}</option>
                <option value="output">{t("输出")}</option>
              </select>
            </Field>
            <Field label={t("训练文本（每行一句）")}>
              <textarea
                rows={8}
                value={corpus}
                onChange={(e) => setCorpus(e.target.value)}
              />
            </Field>
            <Field label={t("训练步数")}>
              <input
                type="number"
                min={1}
                max={2000}
                value={steps}
                onChange={(e) => setSteps(Number(e.target.value))}
              />
            </Field>
            <Button
              disabled={
                !writable ||
                busy ||
                !current ||
                current.protocol[role + "_model"] !== "scratch"
              }
              onClick={trainScratch}
            >
              {t("训练并保存新版本")}
            </Button>
          </section>
          <section>
            <h2>{t("活动到语言的校准")}</h2>
            <p>
              {t(
                "选择本页已测活动并填写期望表达。这是外置转换器的监督目标，不能当作 Core 已经理解的证据。",
              )}
            </p>
            {rows
              .filter((r: any) => r.result)
              .map((r: any) => (
                <Field
                  key={r.job_id}
                  label={`${r.text} · ${r.job_id.slice(0, 8)}`}
                >
                  <input
                    placeholder={t("希望转换成的文字（留空不参加）")}
                    value={targets[r.job_id] ?? ""}
                    onChange={(e) =>
                      setTargets({ ...targets, [r.job_id]: e.target.value })
                    }
                  />
                </Field>
              ))}
            {current?.protocol.output_model === "scratch" && (
              <label>
                <input
                  type="checkbox"
                  checked={trainBase}
                  onChange={(e) => setTrainBase(e.target.checked)}
                />
                {t("同时训练随机输出模型的权重")}
              </label>
            )}
            <Button
              disabled={
                !writable ||
                busy ||
                !current ||
                current.protocol.output_model === "raw"
              }
              onClick={trainHead}
            >
              {t("训练输出映射")}
            </Button>
            <p className="muted">
              {t(
                "训练不会替换现有会话的权重；完成后建立对照意识并选择新版本。",
              )}
            </p>
          </section>
        </div>
      )}
      {tab === "evidence" && (
        <section className="language-evidence">
          <Field label={t("导入完整语言意识")}>
            <input
              type="file"
              accept=".tmlanguage"
              disabled={!writable || busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (!file) return;
                void attempt(async () => {
                  if (file.size > 256 * 1024 * 1024)
                    throw Error(t("语言设备包不能超过 256 MiB"));
                  const result = await api<any>(
                    `${root}/imports?request_id=${crypto.randomUUID()}&name=${encodeURIComponent(file.name)}`,
                    {
                      method: "POST",
                      headers: { "Content-Type": "application/octet-stream" },
                      body: file,
                    },
                  );
                  setSearch({ run: result.run_id });
                  setOffset(0);
                });
              }}
            />
          </Field>

          {current?.revision > 0 && (
            <p>
              <a
                href={`/api/v2${root}/sessions/${run}/bundle?revision=${current.revision}`}
                download
              >
                {t("导出完整语言意识")}
              </a>
              <small>
                {" "}
                ·{" "}
                {t(
                  "包括 Core、适配器状态和已训练权重；Qwen 基础模型按固定版本另行安装。",
                )}
              </small>
            </p>
          )}
          <h2>{t("模型版本")}</h2>
          {models.map((m: any) => (
            <p key={m.id}>
              <a
                href={`/api/v2/projects/${project.id}/artifacts/${m.id}`}
                download
              >
                {m.name}
              </a>{" "}
              · {m.sha256.slice(0, 16)} · {(m.bytes / 1024 / 1024).toFixed(2)}{" "}
              MiB
            </p>
          ))}
          <h2>{t("最近任务")}</h2>
          {catalogue.data.jobs.map((j: any) => (
            <p key={j.id}>
              {j.operation} · {j.status}
              {j.error && <span role="alert"> · {j.error}</span>}
            </p>
          ))}
          <h2>{t("本页对话证据")}</h2>
          {rows
            .filter((r: any) => r.result)
            .map((r: any) => (
              <p key={r.job_id}>
                <a
                  href={`/api/v2/projects/${project.id}/artifacts/${r.result.result_artifact_id}`}
                  download
                >
                  {r.text} · {t("下载完整过程")}
                </a>
              </p>
            ))}
        </section>
      )}
      {creating && config && (
        <Modal
          title={t("创建语言实验意识")}
          open={creating}
          onOpenChange={setCreating}
          wide
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              create();
            }}
          >
            <Field label={t("意识名称")}>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </Field>
            <LanguageEditor
              value={config}
              onChange={setConfig}
              models={models}
              onValidityChange={setValid}
            />
            <details>
              <summary>{t("内核与来源")}</summary>
              <Field label={t("内核版本")}>
                <input
                  value={kernel}
                  onChange={(e) => setKernel(e.target.value)}
                  list="language-kernels"
                />
                <datalist id="language-kernels">
                  {(kernels.data?.kernels ?? []).map((k: any) => (
                    <option key={k.kernel_id} value={k.kernel_id} />
                  ))}
                </datalist>
              </Field>
              <Field label={t("来源意识编号（空白表示新建）")}>
                <input
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                />
              </Field>
              <JsonEditor
                value={core}
                onChange={setCore}
                label={t("内核参数")}
              />
            </details>
            <ErrorBox error={error} />
            <Button variant="primary" type="submit" disabled={busy || !valid}>
              {t("创建意识")}
            </Button>
          </form>
        </Modal>
      )}
    </>
  );
}
