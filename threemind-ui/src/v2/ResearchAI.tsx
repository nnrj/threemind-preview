import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Sparkles, Plus, Trash2 } from "lucide-react";
import { api, post, ApiError } from "./api";
import { t, locale } from "./i18n";
import { Button, ErrorBox, Field, Modal } from "./ui";
import { AICallDetail, AICallHistory } from "./aiProviders";
import { kindNames } from "./reportRender";

type Props = {
  base: string;
  kind: "record" | "report";
  onGenerated: (id: string) => void;
  sourcePicker: (choose: (id: string) => void, close: () => void) => ReactNode;
  recordPicker: (choose: (block: any) => void, close: () => void) => ReactNode;
};

export default function ResearchAI({
  base,
  kind,
  onGenerated,
  sourcePicker,
  recordPicker,
}: Props) {
  const cache = useQueryClient();
  const [open, setOpen] = useState(false),
    [picker, setPicker] = useState<"source" | "record">();
  const [sources, setSources] = useState<any[]>([]),
    [records, setRecords] = useState<any[]>([]);
  const [provider, setProvider] = useState(""),
    [objective, setObjective] = useState("");
  const [language, setLanguage] = useState(locale() === "en" ? "en" : "zh-CN");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const [preview, setPreview] = useState<any>(),
    [callId, setCallId] = useState<string>();
  const [detail, setDetail] = useState(false),
    [history, setHistory] = useState(false);
  const retry = useRef<any>(null);
  const providers = useQuery({
    queryKey: ["research-ai-providers", base],
    queryFn: () => api(`${base}/ai/providers`),
    enabled: open,
  });
  const scope = {
    kind,
    language,
    objective,
    sources: sources.map((s) => s.id),
    records: records.map((r) => ({
      record_id: r.record_id,
      revision: r.revision,
      block_ids: r.blocks.map((b: any) => b.id),
    })),
  };
  const scopeKey = JSON.stringify(scope);
  const currentScope = useRef(scopeKey);
  currentScope.current = scopeKey;
  useEffect(() => {
    setPreview(undefined);
    setError(undefined);
    retry.current = null;
  }, [scopeKey, provider]);
  const status = useQuery({
    queryKey: ["ai-call-status", base, callId],
    queryFn: () => api(`${base}/ai/calls/${callId}/status`),
    enabled: open && !!callId,
    refetchInterval: (q) =>
      !q.state.data ||
      ["queued", "sending"].includes(q.state.data.status) ||
      (q.state.data.status === "completed" &&
        !q.state.data.result?.application_status &&
        ["pending", "leased"].includes(q.state.data.job_status))
        ? 1200
        : false,
  });
  const result = status.data?.result;
  useEffect(() => {
    if (result?.document_id)
      cache.invalidateQueries({ queryKey: ["research-documents", base] });
  }, [result?.document_id, base, cache]);
  const pending =
    !!callId &&
    (!status.data ||
      ["queued", "sending"].includes(status.data.status) ||
      (status.data.status === "completed" &&
        !result?.application_status &&
        ["pending", "leased"].includes(status.data.job_status)));

  async function addSource(id: string) {
    setPicker(undefined);
    setBusy(true);
    setError(undefined);
    try {
      const source = await api(`${base}/report-sources/${id}`);
      setSources((old) =>
        old.some((s) => s.id === id) ? old : [...old, source],
      );
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function addRecord(block: any) {
    setPicker(undefined);
    setBusy(true);
    setError(undefined);
    try {
      const record = await api(
        `${base}/research-documents/${block.record_id}?revision=${block.revision}`,
      );
      const selected = record.spec.blocks.find(
        (b: any) => b.id === block.block_id,
      );
      setRecords((old) => {
        const found = old.find(
          (r) =>
            r.record_id === block.record_id && r.revision === block.revision,
        );
        if (found?.blocks.some((b: any) => b.id === selected.id)) return old;
        return found
          ? old.map((r) =>
              r === found ? { ...r, blocks: [...r.blocks, selected] } : r,
            )
          : [
              ...old,
              {
                record_id: block.record_id,
                revision: block.revision,
                title: record.spec.title,
                blocks: [selected],
              },
            ];
      });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function inspect() {
    setBusy(true);
    setError(undefined);
    const key = scopeKey;
    try {
      const response = await post(`${base}/research-generation/preview`, scope);
      if (currentScope.current === key) setPreview(response);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function generate() {
    if (!preview) return;
    setBusy(true);
    setError(undefined);
    retry.current ??= {
      ...scope,
      provider_id: provider,
      evidence_hash: preview.evidence_hash,
      operation_id: crypto.randomUUID(),
    };
    try {
      const call = await post(`${base}/research-generation`, retry.current);
      retry.current = null;
      setCallId(call.id);
      cache.invalidateQueries({ queryKey: ["ai-calls"] });
    } catch (e) {
      if (e instanceof ApiError && e.status >= 400 && e.status < 500)
        retry.current = null;
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Button onClick={() => setOpen(true)}>
        <Sparkles size={16} />
        {t("AI 生成")}
      </Button>
      <Modal
        open={open}
        onOpenChange={(v) => {
          if (!busy) setOpen(v);
        }}
        wide
        title={kind === "record" ? t("AI 生成实验记录") : t("AI 生成实验报告")}
        description={t(
          "选择固定证据并预览发送内容。每次生成保存为新的待复核草案，原始数据保持不变。",
        )}
      >
        <ErrorBox error={error || providers.error || status.error} />
        <fieldset disabled={busy} className="research-ai-fields">
          <div className="report-field-grid">
            <Field label={t("AI 供应商")}>
              <select
                aria-label={t("AI 供应商")}
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
              >
                <option value="">{t("请选择")}</option>
                {providers.data?.providers
                  .filter((p: any) => p.config.enabled)
                  .map((p: any) => (
                    <option key={p.id} value={p.id}>
                      {p.config.name} · {p.config.model}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label={t("生成语言")}>
              <select
                aria-label={t("生成语言")}
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
              >
                <option value="zh-CN">{t("中文")}</option>
                <option value="en">{t("英文")}</option>
              </select>
            </Field>
          </div>
          {!providers.isLoading &&
            !providers.data?.providers.some((p: any) => p.config.enabled) && (
              <p className="footnote">
                {t("没有可用的供应商，请先在设置中配置。")}{" "}
                <Link
                  to="/settings?section=providers"
                  onClick={() => setOpen(false)}
                >
                  {t("AI 供应商设置")}
                </Link>
              </p>
            )}
          <Field
            label={t("研究关注点")}
            hint={t(
              "描述希望比较的现象、问题与报告角度。数值事实由固定证据解析，解释仍需人工复核。",
            )}
          >
            <textarea
              aria-label={t("研究关注点")}
              value={objective}
              maxLength={6000}
              rows={3}
              onChange={(e) => setObjective(e.target.value)}
            />
          </Field>
          <div className="report-inline">
            <h3>{t("发送范围")}</h3>
            <div className="report-spacer" />
            <Button
              disabled={sources.length >= 8}
              onClick={() => setPicker("source")}
            >
              <Plus size={15} />
              {t("添加数据来源")}
            </Button>
            {kind === "report" && (
              <Button onClick={() => setPicker("record")}>
                <Plus size={15} />
                {t("引用实验记录")}
              </Button>
            )}
          </div>
          {!sources.length && !records.length && (
            <p className="footnote">
              {t("先选取或采集来源；不会自动读取整个意识或项目数据。")}
            </p>
          )}
          <div className="research-ai-selection">
            {sources.map((s) => (
              <div key={s.id}>
                <div>
                  <strong>
                    {s.provenance?.run_name ||
                      t(kindNames[s.kind as keyof typeof kindNames])}
                  </strong>
                  <small>
                    {t(kindNames[s.kind as keyof typeof kindNames])} ·{" "}
                    {t("{count} 行", { count: s.row_count })}
                  </small>
                  <code>{s.id}</code>
                </div>
                <Button
                  aria-label={t("移除来源")}
                  onClick={() =>
                    setSources((old) => old.filter((v) => v.id !== s.id))
                  }
                >
                  <Trash2 size={15} />
                </Button>
              </div>
            ))}
            {records.map((r) => (
              <div key={`${r.record_id}:${r.revision}`}>
                <div>
                  <strong>
                    {r.title} · r{r.revision}
                  </strong>
                  <small>
                    {t("已选 {count} 个内容块", { count: r.blocks.length })}
                  </small>
                </div>
                <Button
                  aria-label={t("移除记录引用")}
                  onClick={() =>
                    setRecords((old) => old.filter((v) => v !== r))
                  }
                >
                  <Trash2 size={15} />
                </Button>
              </div>
            ))}
          </div>
          <div className="form-actions">
            <Button
              disabled={!sources.length && !records.length}
              onClick={() => void inspect()}
            >
              {t("预览发送内容")}
            </Button>
          </div>
        </fieldset>
        {preview && (
          <section className="research-ai-evidence">
            <h3>{t("即将发送的证据")}</h3>
            <p className="footnote">
              {t(
                "摘要基于全部已选样本，保留缺失与分析终点；不发送模型本体、媒体、凭据或完整回放。",
              )}
            </p>
            <div className="research-ai-selection">
              {preview.evidence.sources.map((s: any) => (
                <div key={s.id}>
                  <div>
                    <strong>
                      {s.provenance.run_name ||
                        t(kindNames[s.kind as keyof typeof kindNames])}
                    </strong>
                    <small>
                      {t("{count} 行", { count: s.coverage.row_count })} ·{" "}
                      {Object.keys(s.metrics).join(", ")}
                    </small>
                    <code>SHA256 {s.content_hash}</code>
                  </div>
                </div>
              ))}
            </div>
            <details>
              <summary>
                {t("查看完整发送内容（{size} KiB）", {
                  size: (preview.request_bytes / 1024).toFixed(1),
                })}
              </summary>
              <pre className="ai-preview">
                {JSON.stringify(preview.prompt, null, 2)}
              </pre>
            </details>
            <p className="footnote">
              {t(
                "点击生成后，此处内容会发送至选定供应商。返回的文字属于未核实解释；伪造数值字段或越界引用会被拒绝。",
              )}
            </p>
            <div className="form-actions">
              <Button
                variant="primary"
                disabled={busy || pending || !provider}
                onClick={() => void generate()}
              >
                <Sparkles size={15} />
                {retry.current ? t("重试提交") : t("生成新草案")}
              </Button>
            </div>
          </section>
        )}
        {callId && (
          <section className="research-ai-result" aria-live="polite">
            {pending && (
              <p>{t("正在排队、生成或校验；关闭此窗口后任务继续。")}</p>
            )}
            {result?.document_id && (
              <p>{t("已生成新的待复核草案。请核对解释、局限与数据来源。")}</p>
            )}
            <ErrorBox
              error={
                result?.application_status === "rejected"
                  ? result.error
                  : status.data?.error || status.data?.job_error
              }
            />
            <div className="report-inline">
              <Button onClick={() => setDetail(true)}>
                {t("查看生成调用")}
              </Button>
              {result?.document_id && (
                <Button
                  variant="primary"
                  onClick={() => {
                    setOpen(false);
                    onGenerated(result.document_id);
                  }}
                >
                  {t("打开生成草案")}
                </Button>
              )}
            </div>
          </section>
        )}
        <details
          open={history}
          onToggle={(e) => setHistory(e.currentTarget.open)}
        >
          <summary>{t("生成历史与调用记录")}</summary>
          {history && <AICallHistory purpose={kind} />}
        </details>
      </Modal>
      {picker === "source" &&
        sourcePicker(
          (id) => void addSource(id),
          () => setPicker(undefined),
        )}
      {picker === "record" &&
        recordPicker(
          (b) => void addRecord(b),
          () => setPicker(undefined),
        )}
      {detail && callId && (
        <AICallDetail callId={callId} onClose={() => setDetail(false)} />
      )}
    </>
  );
}
