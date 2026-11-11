import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, post, ApiError } from "./api";
import { t, locale } from "./i18n";
import { Button, ErrorBox, Field, Loading, Modal } from "./ui";
import { AICallDetail, aiStatuses } from "./aiProviders";
import { WorldEditor } from "./WorldEditor";

export default function WorldAI({
  project,
  initial,
  initialCall,
  writable,
  onClose,
  onAdopt,
}: {
  project: string;
  initial?: any;
  initialCall?: string;
  writable: boolean;
  onClose: () => void;
  onAdopt: (protocol: any, call: string) => void;
}) {
  const base = `/projects/${project}`;
  const cache = useQueryClient();
  const [objective, setObjective] = useState("");
  const [language, setLanguage] = useState(locale() === "en" ? "en" : "zh-CN");
  const [provider, setProvider] = useState("");
  const [callId, setCallId] = useState(initialCall);
  const [preview, setPreview] = useState<any>();
  const [busy, setBusy] = useState(false),
    [detail, setDetail] = useState(false);
  const [error, setError] = useState<unknown>();
  const retry = useRef<any>(null);
  const providers = useQuery({
    queryKey: ["world-ai-providers", project],
    queryFn: () => api<any>(base + "/ai/providers"),
    enabled: writable,
  });
  const defaults = useQuery({
    queryKey: ["world-catalogue", project],
    queryFn: () => api<any>(base + "/worlds/catalogue"),
    enabled: !initial && !initialCall,
  });
  const protocol = initial ?? defaults.data?.defaults;
  const scope = { objective, language, world_protocol: protocol };
  const key = JSON.stringify(scope);
  const currentKey = useRef(key);
  currentKey.current = key;
  useEffect(() => {
    setPreview(undefined);
    retry.current = null;
    setError(undefined);
  }, [key, provider]);
  const status = useQuery({
    queryKey: ["world-ai-status", project, callId],
    queryFn: () => api<any>(`${base}/ai/calls/${callId}/status`),
    enabled: !!callId,
    refetchInterval: (q) =>
      !q.state.data ||
      ["queued", "sending"].includes(q.state.data.status) ||
      (q.state.data.status === "completed" &&
        !q.state.data.result?.application_status &&
        ["pending", "leased"].includes(q.state.data.job_status))
        ? 1200
        : false,
  });
  const row = status.data,
    result = row?.purpose === "world" ? row.result : null;
  const pending =
    !!callId &&
    (!row ||
      ["queued", "sending"].includes(row.status) ||
      (row.status === "completed" &&
        !result?.application_status &&
        ["pending", "leased"].includes(row.job_status)));
  async function prepare() {
    setBusy(true);
    setError(undefined);
    const requestKey = key;
    try {
      const value = await post<any>(base + "/worlds/ai/preview", scope);
      if (currentKey.current === requestKey) setPreview(value);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function generate() {
    if (!preview || !provider) return;
    setBusy(true);
    setError(undefined);
    retry.current ??= {
      ...scope,
      provider_id: provider,
      evidence_hash: preview.evidence_hash,
      operation_id: crypto.randomUUID(),
    };
    try {
      const response = await post<any>(
        base + "/worlds/ai/requests",
        retry.current,
      );
      setCallId(response.id);
      retry.current = null;
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
    <Modal
      open
      wide
      title={t("AI 世界与躯体草案")}
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
      description={t(
        "选择基准世界并说明设计目的。AI 提案经校验后供人工采用；不会自动创建世界或启动实验。",
      )}
    >
      <ErrorBox
        error={
          error ??
          providers.error ??
          defaults.error ??
          status.error ??
          row?.error ??
          row?.job_error
        }
      />
      {row && row.purpose !== "world" && (
        <ErrorBox error={t("此调用不是世界草案。")} />
      )}
      {writable && !initialCall && (
        <fieldset disabled={busy || pending} className="research-ai-fields">
          <p className="footnote">
            {t("基准世界：")}
            {protocol?.label ?? t("正在加载…")}
          </p>
          <div className="report-field-grid">
            <Field label={t("AI 供应商")}>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                aria-label={t("AI 供应商")}
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
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
              >
                <option value="zh-CN">{t("简体中文")}</option>
                <option value="en">English</option>
              </select>
            </Field>
          </div>
          {!providers.isPending &&
            !providers.data?.providers.some((p: any) => p.config.enabled) && (
              <p>
                <Link onClick={onClose} to="/settings?section=providers">
                  {t("前往设置配置供应商")}
                </Link>
              </p>
            )}
          <Field label={t("世界设计目的")}>
            <textarea
              rows={4}
              value={objective}
              maxLength={12000}
              onChange={(e) => setObjective(e.target.value)}
              placeholder={t(
                "描述物理布局、虚拟躯体和感官需求；例如给当前躯体增加一只低分辨率眼睛。",
              )}
            />
          </Field>
          <Button disabled={!protocol || !objective.trim()} onClick={prepare}>
            {t("预览发送内容")}
          </Button>
        </fieldset>
      )}
      {preview && !pending && !initialCall && (
        <section className="panel">
          <p>
            {t(
              "发送内容为设计目的、基准世界协议和配置约束，不包含意识状态或研究测量。",
            )}
          </p>
          <p className="footnote">
            {t("请求大小：{size} KB", {
              size: (preview.request_bytes / 1024).toFixed(1),
            })}
          </p>
          <details>
            <summary>{t("完整发送内容")}</summary>
            <pre className="ai-preview">
              {JSON.stringify(preview.prompt, null, 2)}
            </pre>
          </details>
          <Button
            variant="primary"
            disabled={busy || !provider}
            onClick={generate}
          >
            {retry.current ? t("按原请求编号重试") : t("发送世界草案请求")}
          </Button>
        </section>
      )}
      {callId && (
        <section className="panel" aria-label={t("世界草案结果")}>
          <div className="panel-heading">
            <h3>{t("世界草案结果")}</h3>
            <Button variant="small" onClick={() => setDetail(true)}>
              {t("查看完整调用记录")}
            </Button>
          </div>
          {pending && <Loading />}
          {row && (
            <p className="footnote">
              {t(aiStatuses[row.status] ?? row.status)} ·{" "}
              {row.usage
                ? `${row.usage.input_tokens} / ${row.usage.output_tokens}`
                : t("未返回用量")}
            </p>
          )}
          {result?.application_status === "rejected" && (
            <ErrorBox error={result.error} />
          )}
          {result?.application_status === "proposed" && (
            <>
              <p className="notice">
                {t(
                  "草案已通过配置与物理模型编译校验，尚未运行或人工采用。AI 的设计说明仍需研究者判断。",
                )}
              </p>
              <p>{result.rationale}</p>
              <ul>
                {result.limitations.map((line: string, index: number) => (
                  <li key={index}>{line}</li>
                ))}
              </ul>
              <WorldChanges changes={result.changes} />
              <details>
                <summary>{t("查看图形配置与三维预览")}</summary>
                <WorldEditor
                  key={result.protocol_hash}
                  project={project}
                  initial={result.protocol}
                  readOnly
                />
              </details>
              {writable && (
                <Button
                  variant="primary"
                  onClick={() => onAdopt(result.protocol, callId)}
                >
                  {t("载入草案并继续编辑")}
                </Button>
              )}
            </>
          )}
          {!pending && writable && !initialCall && (
            <Button
              onClick={() => {
                setCallId(undefined);
                setPreview(undefined);
              }}
            >
              {t("设计另一份草案")}
            </Button>
          )}
        </section>
      )}
      {detail && callId && (
        <AICallDetail callId={callId} onClose={() => setDetail(false)} />
      )}
    </Modal>
  );
}

function WorldChanges({ changes }: { changes: any[] }) {
  const [page, setPage] = useState(0);
  return (
    <section className="world-ai-changes" aria-label={t("世界配置差异")}>
      <h3>
        {t("世界配置差异")} · {changes.length}
      </h3>
      <p className="footnote">
        {t(
          "按部件编号比较属性，列表顺序调整不算接线变化。可逐页核对全部差异。",
        )}
      </p>
      {!changes.length ? (
        <p>{t("与基准世界配置相同。")}</p>
      ) : (
        <>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t("参数路径")}</th>
                  <th>{t("修改前")}</th>
                  <th>{t("修改后")}</th>
                </tr>
              </thead>
              <tbody>
                {changes.slice(page * 20, page * 20 + 20).map((change: any) => (
                  <tr key={change.path}>
                    <td className="hash-value" data-label={t("参数路径")}>
                      {change.path}
                    </td>
                    <td className="hash-value" data-label={t("修改前")}>
                      {change.before_present
                        ? JSON.stringify(change.before)
                        : t("不存在")}
                    </td>
                    <td className="hash-value" data-label={t("修改后")}>
                      {change.after_present
                        ? JSON.stringify(change.after)
                        : t("不存在")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="query-controls">
            <Button disabled={!page} onClick={() => setPage(page - 1)}>
              {t("上一页")}
            </Button>
            <span>
              {page + 1} / {Math.ceil(changes.length / 20)}
            </span>
            <Button
              disabled={(page + 1) * 20 >= changes.length}
              onClick={() => setPage(page + 1)}
            >
              {t("下一页")}
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
