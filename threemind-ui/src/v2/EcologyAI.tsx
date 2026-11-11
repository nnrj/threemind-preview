import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, post, ApiError } from "./api";
import { t, messageKeys } from "./i18n";
import { AICallDetail, aiStatuses } from "./aiProviders";
import { Button, CodeEditor, ErrorBox, Field, Loading, Modal } from "./ui";

const choices = messageKeys({
  enabled: "启用 AI 观察解释",
  automatic: "允许后台自动解释",
  periodic: "按间隔解释",
  on_body_failure: "躯体失效时解释",
  on_birth_deferred: "繁殖暂缓时解释",
  on_warning: "规则预警命中时解释",
  on_finished: "训练结束后生成完整总结",
});

function Editor({ root, data, close, saved }: any) {
  const [revision] = useState(data.configuration?.revision ?? 0);
  const [value, setValue] = useState<any>(() =>
    structuredClone(data.configuration?.configuration ?? data.defaults),
  );
  const [mode, setMode] = useState("form"),
    [raw, setRaw] = useState("");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const providers = useQuery({
    queryKey: ["ecology-ai-providers", root],
    queryFn: () =>
      api<{
        providers: {
          id: string;
          network_allowed: boolean;
          config: { name: string; model: string; enabled: boolean };
        }[];
      }>(root.split("/ecologies")[0] + "/ai/providers"),
  });
  function change(key: string, next: any) {
    setValue((old: any) => ({
      ...old,
      [key]: next,
      ...(key === "enabled" && !next ? { automatic: false } : {}),
    }));
    setError(undefined);
  }
  async function read() {
    if (mode === "form") return value;
    return (await import("./JsonEditor")).parseJson(raw);
  }
  async function action(kind: string) {
    setBusy(true);
    setError(undefined);
    try {
      if (kind === "format") {
        setRaw(JSON.stringify(await read(), null, 2));
        return;
      }
      const checked = await post<any>(root + "/validate", await read());
      if (kind === "toggle") {
        setValue(checked.configuration);
        setRaw(JSON.stringify(checked.configuration, null, 2));
        setMode(mode === "form" ? "json" : "form");
      }
      if (kind === "save") {
        await post(root + "/configuration", {
          configuration: checked.configuration,
          expected_revision: revision,
        });
        saved();
      }
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  function check(key: keyof typeof choices) {
    return (
      <label className="check" key={key}>
        <input
          type="checkbox"
          checked={value[key]}
          disabled={key === "automatic" && !value.enabled}
          onChange={(e) => change(key, e.target.checked)}
        />
        {t(choices[key])}
      </label>
    );
  }
  function number(key: string, label: string, min: number, max: number) {
    return (
      <Field label={label}>
        <input
          aria-label={label}
          type="number"
          required
          min={min}
          max={max}
          step={1}
          value={value[key] ?? ""}
          onChange={(e) =>
            change(key, e.target.value === "" ? null : Number(e.target.value))
          }
        />
      </Field>
    );
  }
  return (
    <Modal
      open
      wide
      title={t("配置 AI 观察解释")}
      onOpenChange={(open) => {
        if (!open && !busy) close();
      }}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void action("save");
        }}
      >
        <div className="observer-toolbar">
          <p className="footnote">
            {t(
              "AI 只提供外部解释，不执行刺激、淘汰或参数修改。自动请求也会消耗所选供应商额度。",
            )}
          </p>
          <button
            type="button"
            className="text-link"
            disabled={busy}
            onClick={() => void action("toggle")}
          >
            {mode === "form" ? t("切换到 JSON 编辑") : t("切换到图形配置")}
          </button>
        </div>
        {mode === "json" ? (
          <>
            <div className="query-controls">
              <Button
                type="button"
                disabled={busy}
                onClick={() => void action("format")}
              >
                {t("格式化")}
              </Button>
              <Button
                type="button"
                disabled={busy}
                onClick={() => void action("validate")}
              >
                {t("校验")}
              </Button>
            </div>
            <CodeEditor
              label={t("AI 观察配置 JSON")}
              value={raw}
              readOnly={busy}
              onChange={setRaw}
              rows={20}
            />
          </>
        ) : (
          <fieldset disabled={busy} className="observer-form">
            <div className="observer-switches">
              {check("enabled")}
              {check("automatic")}
            </div>
            <div className="observer-fields">
              <Field label={t("AI 供应商")}>
                <select
                  aria-label={t("AI 供应商")}
                  value={value.provider_id ?? ""}
                  onChange={(e) =>
                    change("provider_id", e.target.value || null)
                  }
                >
                  <option value="">{t("请选择供应商")}</option>
                  {value.provider_id &&
                    !providers.data?.providers.some(
                      (p: any) => p.id === value.provider_id,
                    ) && (
                      <option value={value.provider_id}>
                        {t("原供应商不可用")}
                      </option>
                    )}
                  {providers.data?.providers.map((p) => (
                    <option
                      key={p.id}
                      value={p.id}
                      disabled={!p.config.enabled || !p.network_allowed}
                    >
                      {p.config.name} · {p.config.model}
                      {!p.config.enabled ? " · " + t("关闭") : ""}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t("解释语言")}>
                <select
                  aria-label={t("解释语言")}
                  value={value.language}
                  onChange={(e) => change("language", e.target.value)}
                >
                  <option value="zh-CN">{t("中文")}</option>
                  <option value="en">English</option>
                </select>
              </Field>
            </div>
            <Field label={t("观察目的与关注点")}>
              <textarea
                aria-label={t("观察目的与关注点")}
                rows={3}
                maxLength={4000}
                value={value.objective}
                onChange={(e) => change("objective", e.target.value)}
              />
            </Field>
            <details>
              <summary>{t("高级：触发、时间与调用上限")}</summary>
              <div className="observer-switches">
                {(
                  [
                    "periodic",
                    "on_body_failure",
                    "on_birth_deferred",
                    "on_warning",
                    "on_finished",
                  ] as const
                ).map(check)}
              </div>
              <div className="observer-fields">
                <Field label={t("AI 间隔采用的时钟")}>
                  <select
                    aria-label={t("AI 间隔采用的时钟")}
                    value={value.cadence_clock}
                    onChange={(e) => change("cadence_clock", e.target.value)}
                  >
                    <option value="host">{t("宿主墙钟（UTC）")}</option>
                    <option value="model">{t("模型模拟时间")}</option>
                  </select>
                </Field>
                {number("interval_s", t("解释间隔（秒）"), 30, 86400)}
                {number(
                  "minimum_host_interval_s",
                  t("自动请求最小宿主间隔（秒）"),
                  10,
                  86400,
                )}
                {number("maximum_calls", t("每个配置版本的请求上限"), 1, 10000)}
              </div>
              <p className="footnote">
                {t(
                  "积压间隔合并为当前证据的一次请求；同一训练最多一个请求处理中。结束总结覆盖全部提交范围，失败后需要显式恢复或手动重新生成。",
                )}
              </p>
            </details>
          </fieldset>
        )}
        <ErrorBox error={error || providers.error} />
        <div className="modal-actions">
          <Button type="button" disabled={busy} onClick={close}>
            {t("取消")}
          </Button>
          <Button type="submit" disabled={busy} variant="primary">
            {t("保存配置")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function Generate({ root, revision, checkpoint, close, generated }: any) {
  const [first, setFirst] = useState(1),
    [preview, setPreview] = useState<any>();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const nonce = useRef(crypto.randomUUID());
  const [submitted, setSubmitted] = useState(false);
  async function action(send: boolean) {
    setBusy(true);
    setError(undefined);
    try {
      if (!send) {
        setPreview(
          await post(root + "/preview", {
            configuration_revision: revision,
            checkpoint_id: checkpoint,
            first_revision: first,
          }),
        );
      } else {
        setSubmitted(true);
        const result = await post<any>(root + "/requests", {
          ...preview.evidence.scope,
          operation_id: nonce.current,
          evidence_hash: preview.evidence_hash,
        });
        generated(result.id);
      }
    } catch (e) {
      setError(e);
      if (
        e instanceof ApiError &&
        [400, 403, 404, 409, 422].includes(e.status)
      ) {
        setSubmitted(false);
        setPreview(undefined);
        nonce.current = crypto.randomUUID();
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      open
      wide
      title={t("生成生态观察解释")}
      onOpenChange={(open) => {
        if (!open && !busy) close();
      }}
    >
      <p>
        {t(
          "本次使用页面选定的种群恢复点。先预览实际发送内容；数字来自固定证据，AI 的文字仍需人工核查。",
        )}
      </p>
      <Field label={t("起始恢复点修订")}>
        <input
          aria-label={t("起始恢复点修订")}
          type="number"
          min={1}
          step={1}
          value={first}
          disabled={busy || submitted}
          onChange={(e) => {
            setFirst(Number(e.target.value));
            setPreview(undefined);
            nonce.current = crypto.randomUUID();
          }}
        />
      </Field>
      <Button disabled={busy || submitted} onClick={() => void action(false)}>
        {t("预览发送内容")}
      </Button>
      {preview && (
        <section className="observer-rule">
          <h3>{t("完整范围摘要")}</h3>
          <p>
            {t("恢复点 r{first} 至 r{last}；已记录事件 {events} 条。", {
              first: preview.evidence.first_checkpoint.revision,
              last: preview.evidence.last_checkpoint.revision,
              events: preview.evidence.facts.events.total,
            })}
          </p>
          <p>
            {t("发送 {bytes} 字节；不包含脑网络、原始载体或凭据。", {
              bytes: preview.request_bytes,
            })}
          </p>
          <details>
            <summary>{t("查看完整请求与证据")}</summary>
            <CodeEditor
              label={t("实际发送 JSON")}
              value={JSON.stringify(preview.prompt, null, 2)}
              onChange={() => {}}
              readOnly
              rows={18}
            />
          </details>
          <p className="hash-value">{preview.evidence_hash}</p>
        </section>
      )}
      <ErrorBox error={error} />
      <div className="modal-actions">
        <Button disabled={busy} onClick={close}>
          {t("关闭")}
        </Button>
        <Button
          variant="primary"
          disabled={busy || !preview}
          onClick={() => void action(true)}
        >
          {submitted ? t("使用原请求编号重试") : t("发送并生成解释")}
        </Button>
      </div>
    </Modal>
  );
}

export default function EcologyAI({
  root: observerRoot,
  checkpoint,
  write,
}: {
  root: string;
  checkpoint?: string;
  write: boolean;
}) {
  const root = observerRoot + "/ai",
    client = useQueryClient();
  const [editing, setEditing] = useState(false),
    [generation, setGeneration] = useState<{
      checkpoint: string;
      revision: number;
    }>(),
    [call, setCall] = useState<string>();
  const [before, setBefore] = useState<number>(),
    [historyBefore, setHistoryBefore] = useState<number>(),
    [showHistory, setShowHistory] = useState(false),
    [error, setError] = useState<unknown>();
  const detail = useQuery({
    queryKey: ["ecology-ai", root],
    queryFn: () => api<any>(root),
    refetchInterval: 5000,
  });
  const feed = useQuery({
    queryKey: ["ecology-ai-calls", root, before],
    queryFn: () =>
      api<any>(root + "/calls" + (before ? "?before=" + before : "")),
    refetchInterval: before ? false : 5000,
  });
  const history = useQuery({
    queryKey: ["ecology-ai-revisions", root, historyBefore],
    queryFn: () =>
      api<any>(
        root + "/revisions" + (historyBefore ? "?before=" + historyBefore : ""),
      ),
    enabled: showHistory,
  });
  function refresh() {
    void client.invalidateQueries({
      predicate: (q) => String(q.queryKey[0]).startsWith("ecology-ai"),
    });
  }
  const current = detail.data?.configuration;
  return (
    <section
      className="observer-rule ecology-ai-panel"
      aria-label={t("AI 观察解释")}
    >
      <div className="observer-toolbar">
        <h4>{t("AI 观察解释")}</h4>
        <div className="query-controls">
          <Button
            disabled={!write || !detail.data}
            onClick={() => setEditing(true)}
          >
            {t("配置 AI 观察")}
          </Button>
          <Button
            disabled={!write || !current?.configuration.enabled || !checkpoint}
            onClick={() => {
              if (checkpoint)
                setGeneration({ checkpoint, revision: current.revision });
            }}
          >
            {t("生成当前观察解释")}
          </Button>
        </div>
      </div>
      <p className="footnote">
        {t(
          "确定事实与 AI 解释分开保存。外部 AI 文字尚未人工复核，引用存在不代表推论得到证实。",
        )}
      </p>
      {detail.isPending && <Loading />}
      {detail.data && (
        <p role="status">
          {current?.configuration.enabled
            ? t("本版本已请求 {count} 次，上限 {limit}；自动调度{state}。", {
                count: detail.data.calls_in_revision,
                limit: current.configuration.maximum_calls,
                state: current.enabled ? t("启用") : t("关闭"),
              })
            : t("AI 观察当前关闭。基础事件说明和规则预警仍可独立使用。")}
        </p>
      )}
      <ErrorBox
        error={detail.error || feed.error || error || current?.state.last_error}
      />
      {current?.state.blocked && write && (
        <Button
          onClick={async () => {
            try {
              await post(root + "/resume", {
                expected_revision: current.revision,
              });
              refresh();
            } catch (e) {
              setError(e);
            }
          }}
        >
          {t("恢复自动观察（不重发旧请求）")}
        </Button>
      )}
      {feed.data?.rows.map((item: any) => (
        <article key={item.id} className="observer-rule">
          <div className="observer-toolbar">
            <strong>
              {t(aiStatuses[item.status])} · r{item.configuration_revision}
            </strong>
            <button
              type="button"
              className="text-link"
              onClick={() => setCall(item.id)}
            >
              {t("查看完整调用记录")}
            </button>
          </div>
          <p>
            {item.result?.summary?.text ||
              item.result?.error ||
              item.error ||
              t("尚无已校验的解释。")}
          </p>
          <small>
            {new Date(item.created_at).toLocaleString()} ·{" "}
            {item.result?.application_status === "recorded"
              ? t("待人工复核")
              : t("解释未采用或尚未生成")}
          </small>
        </article>
      ))}
      <div className="query-controls">
        <Button disabled={!before} onClick={() => setBefore(undefined)}>
          {t("最新一组")}
        </Button>
        <Button
          disabled={!feed.data?.more}
          onClick={() => setBefore(feed.data.rows.at(-1).ordinal)}
        >
          {t("更早调用")}
        </Button>
        <button
          type="button"
          className="text-link"
          onClick={() => setShowHistory(!showHistory)}
        >
          {t("AI 观察配置历史")}
        </button>
        <Link className="text-link" to="/settings?section=providers">
          {t("管理 AI 供应商")}
        </Link>
      </div>
      {showHistory && (
        <div>
          <ErrorBox error={history.error} />
          {history.data?.rows.map((r: any) => (
            <details key={r.revision}>
              <summary>
                r{r.revision} · {new Date(r.created_at).toLocaleString()}
              </summary>
              <CodeEditor
                label={t("历史 AI 观察配置")}
                value={JSON.stringify(r.configuration, null, 2)}
                onChange={() => {}}
                readOnly
                rows={12}
              />
            </details>
          ))}
          <div className="query-controls">
            <Button
              disabled={!historyBefore}
              onClick={() => setHistoryBefore(undefined)}
            >
              {t("最新配置")}
            </Button>
            <Button
              disabled={!history.data?.more}
              onClick={() =>
                setHistoryBefore(history.data.rows.at(-1).revision)
              }
            >
              {t("更早配置")}
            </Button>
          </div>
        </div>
      )}
      {editing && (
        <Editor
          key={root}
          root={root}
          data={detail.data}
          close={() => setEditing(false)}
          saved={() => {
            setEditing(false);
            refresh();
          }}
        />
      )}
      {generation && (
        <Generate
          root={root}
          checkpoint={generation.checkpoint}
          revision={generation.revision}
          close={() => setGeneration(undefined)}
          generated={(id: string) => {
            setGeneration(undefined);
            setCall(id);
            refresh();
          }}
        />
      )}
      {call && (
        <AICallDetail
          callId={call}
          onClose={() => {
            setCall(undefined);
            refresh();
          }}
        />
      )}
    </section>
  );
}
