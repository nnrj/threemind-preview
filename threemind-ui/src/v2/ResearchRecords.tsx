import { lazy, Suspense, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api, post } from "./api";
import { Button, Empty, ErrorBox, Field, Loading, Modal, PageTitle, useWorkspace } from "./ui";
import { t, useLocale, messageKeys } from "./i18n";
import { DocumentMarkdown } from "./DocumentMarkdown";
import "./researchRecords.css";

type Json = Record<string, any>;
const NoteEditor = lazy(() => import("./NoteEditor"));
const statusLabels: Record<string, string> = messageKeys({
  planned: "尚未执行", running: "运行中", completed: "已完成", failed: "运行失败",
  interrupted: "已中断", cancelled: "已终止", unknown: "执行状态待核查",
  indexed: "已登记，未完整核验", partial: "资料有缺项", verified: "已核验登记资料",
});
const label = (value: string) => t(statusLabels[value] || value);
const notebookLabel = (row: Json) => row.source_key?.startsWith("early-notebook:")
  ? t("检索标签 {label}；原札记编号 {number}", { label: row.original_id, number: row.source_key.split(":")[1] }) : null;

export default function ResearchRecords() {
  useLocale();
  const { projects, project, selectProject } = useWorkspace();
  const [params, setParams] = useSearchParams();
  const [adding, setAdding] = useState(false);
  const selected = params.get("project") || project?.id || "";
  const query = params.get("query") || "";
  const offset = Number(params.get("offset") || 0);
  const [kernel, setKernel] = useState(""), [executor, setExecutor] = useState("");
  const [status, setStatus] = useState(""), [coverage, setCoverage] = useState("");
  const [fromDate, setFromDate] = useState(""), [throughDate, setThroughDate] = useState("");
  const search = new URLSearchParams({ query, kernel, executor, status, coverage, offset: String(offset), limit: "50" });
  if (selected) search.set("project", selected);
  if (fromDate) search.set("from_date", fromDate);
  if (throughDate) search.set("through_date", throughDate);
  const records = useQuery<Json>({ queryKey: ["research-records", search.toString()], queryFn: () => api("/research-experiments?" + search) });
  const change = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    value ? next.set(key, value) : next.delete(key);
    if (key !== "offset") next.delete("offset");
    setParams(next);
  };
  if (params.get("experiment") && selected) return <RecordDetail project={selected} identity={params.get("experiment")!} onBack={() => { const next = new URLSearchParams(params); next.delete("experiment"); next.delete("project"); setParams(next); }} />;
  return <div className="research-records">
    <PageTitle eyebrow="RESEARCH REGISTER" title={t("实验总览")}
      description={t("汇总所有有权访问的研究项目。实验执行状态与资料完整性分别显示，原始证据保持原样。")}
      actions={<Button onClick={() => setAdding(true)} disabled={!projects.some(p => p.role !== "viewer")}>{t("登记实验")}</Button>} />
    <p className="record-scope">{selected ? t("筛选范围：所选研究项目") : t("筛选范围：全部有权访问的研究项目")}</p>
    <div className="record-filters">
      <Field label={t("研究项目")}><select value={selected} onChange={e => { selectProject?.(e.target.value); change("project", e.target.value); }}>
        <option value="">{t("全部项目")}</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select></Field>
      <Field label={t("实验编号或标题")}><input value={query} onChange={e => change("query", e.target.value)} /></Field>
      <Field label={t("相关内核")}><input value={kernel} onChange={e => { setKernel(e.target.value); change("offset", "0"); }} placeholder="threemind.continuous-memory/3" /></Field>
      <Field label={t("执行来源")}><select value={executor} onChange={e => { setExecutor(e.target.value); change("offset", "0"); }}>
        <option value="">{t("全部")}</option>{["ai", "human", "mixed", "unknown"].map(v => <option key={v}>{v}</option>)}
      </select></Field>
      <Field label={t("执行状态")}><select value={status} onChange={e => { setStatus(e.target.value); change("offset", "0"); }}>
        <option value="">{t("全部")}</option>{["planned", "running", "completed", "failed", "interrupted", "cancelled", "unknown"].map(v => <option value={v} key={v}>{label(v)}</option>)}
      </select></Field>
      <Field label={t("资料完整性")}><select value={coverage} onChange={e => { setCoverage(e.target.value); change("offset", "0"); }}>
        <option value="">{t("全部")}</option>{["indexed", "partial", "verified"].map(v => <option value={v} key={v}>{label(v)}</option>)}
      </select></Field>
      <Field label={t("实验日期从")}><input type="date" value={fromDate} onChange={e => { setFromDate(e.target.value); change("offset", "0"); }} /></Field>
      <Field label={t("实验日期至")}><input type="date" value={throughDate} onChange={e => { setThroughDate(e.target.value); change("offset", "0"); }} /></Field>
    </div>
    <ErrorBox error={records.error} />{records.isPending ? <Loading /> : records.data?.rows.length ? <>
      <p>{t("共 {count} 项", { count: records.data.total })}</p>
      <div className="record-list">{records.data.rows.map((row: Json) => <article key={row.id}>
        <div><Link to={`/research-records?project=${row.project_id}&experiment=${row.id}`}><strong>{row.original_id && `${row.original_id} · `}{row.title}</strong></Link>
          <small>{row.project_name} · {row.experiment_date || t("日期待核查")} · {row.executor}</small>
          {notebookLabel(row) && <small>{notebookLabel(row)}</small>}
          <small>{row.kernels.join(" · ") || t("内核待核查")}</small></div>
        <div className="record-status"><span>{label(row.execution_status)}</span><span>{label(row.coverage)}</span></div>
      </article>)}</div>
      <div className="record-actions"><Button disabled={!offset} onClick={() => change("offset", String(Math.max(0, offset - 50)))}>{t("上一页")}</Button>
        <Button disabled={!records.data.more} onClick={() => change("offset", String(offset + 50))}>{t("下一页")}</Button></div>
    </> : <Empty title={t("当前筛选范围没有实验")} detail={t("可清除项目和状态筛选，查看其他研究项目；资料缺失的历史实验仍应登记缺项。")}
      action={<Button onClick={() => { setParams({}); setStatus(""); setCoverage(""); setKernel(""); setExecutor(""); setFromDate(""); setThroughDate(""); }}>{t("清除筛选")}</Button>} />}
    {adding && <RegisterDialog projects={projects.filter(p => p.role !== "viewer")} initial={project?.id || ""} onClose={() => setAdding(false)} onCreated={(p, id) => setParams({ project: p, experiment: id })} />}
  </div>;
}

function RegisterDialog({ projects, initial, onClose, onCreated }: { projects: Json[]; initial: string; onClose: () => void; onCreated: (p: string, id: string) => void }) {
  const [project, setProject] = useState(initial || "" || "");
  const [title, setTitle] = useState(""), [original, setOriginal] = useState(""), [question, setQuestion] = useState(""), [protocol, setProtocol] = useState("");
  const [request] = useState(() => crypto.randomUUID());
  const save = useMutation({ mutationFn: () => post(`/projects/${project}/records`, { request_id: request, spec: {
    source_key: `manual:${request}`, original_id: original || null, title, question, protocol, executor: "human",
    execution_status: "planned", metadata: { entry: "manual-ui" },
  }}), onSuccess: value => { onCreated(project, value.id); onClose(); } });
  return <Modal open title={t("登记实验")} onOpenChange={open => !open && onClose()}><form onSubmit={e => { e.preventDefault(); save.mutate(); }}>
    <Field label={t("研究项目")}><select value={project} onChange={e => setProject(e.target.value)}>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field>
    <Field label={t("实验标题")}><input required value={title} maxLength={200} onChange={e => setTitle(e.target.value)} /></Field>
    <Field label={t("原实验编号")}><input value={original} maxLength={120} onChange={e => setOriginal(e.target.value)} /></Field>
    <Field label={t("研究问题")}><textarea required value={question} onChange={e => setQuestion(e.target.value)} /></Field>
    <Field label={t("实验协议")}><textarea required value={protocol} onChange={e => setProtocol(e.target.value)} /></Field>
    <ErrorBox error={save.error} /><Button type="submit" disabled={save.isPending}>{t("保存登记")}</Button>
  </form></Modal>;
}

function RecordDetail({ project, identity, onBack }: { project: string; identity: string; onBack: () => void }) {
  const client = useQueryClient();
  const { projects, selectProject } = useWorkspace();
  const write = projects.some(p => p.id === project && p.role !== "viewer");
  const base = `/projects/${project}/records/${identity}`;
  const [evidenceOffset, setEvidenceOffset] = useState(0), [entryOffset, setEntryOffset] = useState(0);
  const [editing, setEditing] = useState<"stage" | "report" | "note" | "evidence" | "finalize" | null>(null);
  const [preview, setPreview] = useState<Json | null>(null), [page, setPage] = useState(0);
  const record = useQuery<Json>({ queryKey: ["research-record", project, identity], queryFn: () => api(base) });
  const entries = useQuery<Json>({ queryKey: ["record-entries", project, identity, entryOffset], queryFn: () => api(`${base}/entries?offset=${entryOffset}`) });
  const evidence = useQuery<Json>({ queryKey: ["record-evidence", project, identity, evidenceOffset], queryFn: () => api(`${base}/evidence?offset=${evidenceOffset}`) });
  const content = useQuery<Json>({ queryKey: ["record-preview", project, preview?.id, page], queryFn: () => api(`/projects/${project}/record-evidence/${preview!.id}/preview?offset=${page}`), enabled: !!preview });
  const verify = useMutation({ mutationFn: () => api(base + "/verify") });
  const exportPlan = useMutation({ mutationFn: () => post(`/projects/${project}/data/export-plans`, { operation_id: crypto.randomUUID(), selection: { resources: [{ kind: "experiment", id: identity }] } }) });
  if (record.isPending) return <Loading />;
  if (!record.data) return <><Button onClick={onBack}>{t("返回实验总览")}</Button><ErrorBox error={record.error} /></>;
  const row = record.data;
  const doc = row.spec.metadata?.source_document || row.spec.metadata?.source_path || "lab/record.md";
  const markdown = (text: string) => <div className="document-content"><DocumentMarkdown markdown={text} doc={doc} /></div>;
  return <div className="research-records">
    <Button onClick={onBack}>{t("返回实验总览")}</Button>
    <PageTitle eyebrow={row.original_id || "RESEARCH REGISTER"} title={row.title} description={`${label(row.execution_status)} · ${label(row.coverage)}`} />
    {notebookLabel(row) && <p>{notebookLabel(row)}</p>}
    <p>{t("原实验日期")}: {row.experiment_date || t("待核查")} · {t("登记日期")}: {new Date(row.created_at).toLocaleString()}</p>
    <p>{t("日期依据")}: {row.spec.date_basis || t("待核查")} · {t("执行来源")}: {row.executor}</p>
    <p>{t("相关内核")}: {row.kernels.join(" · ") || t("待核查")}</p>
    {row.spec.metadata?.inventory_hash && <p>{t("历史内核标签来自原文及原生运行。各分组的执行版本和参数见协议与保存配置。")}</p>}
    <div className="record-actions"><Button onClick={() => verify.mutate()}>{t("核查资料关联")}</Button>
      {write && <><Button onClick={() => setEditing("stage")}>{t("追加阶段")}</Button><Button onClick={() => setEditing("report")}>{t("保存报告")}</Button><Button onClick={() => setEditing("note")}>{t("保存笔记")}</Button><Button onClick={() => setEditing("evidence")}>{t("关联证据")}</Button><Button onClick={() => setEditing("finalize")}>{t("结项核验")}</Button><Button onClick={() => exportPlan.mutate()}>{t("生成实验打包预览")}</Button></>}
      <Link to="/data-management" onClick={() => selectProject?.(project)}>{t("数据管理")}</Link></div>
    <ErrorBox error={verify.error || exportPlan.error} />
    {verify.data && <details open><summary>{t("资料核查结果")}</summary><pre>{JSON.stringify(verify.data, null, 2)}</pre></details>}
    {exportPlan.data && <p>{t("打包预览已保存")}: {exportPlan.data.id} · {exportPlan.data.bytes} bytes</p>}
    {row.spec.missing.length > 0 && <div className="record-gaps"><strong>{t("已知资料缺项")}</strong><ul>{row.spec.missing.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul></div>}
    {row.spec.question && <section><h2>{t("研究问题")}</h2>{markdown(row.spec.question)}</section>}
    {row.spec.protocol && <section><h2>{t("实验协议")}</h2>{markdown(row.spec.protocol)}</section>}
    {row.spec.conclusion && <section><h2>{t("原报告结论")}</h2>{markdown(row.spec.conclusion)}</section>}
    <section><h2>{t("报告、笔记与原始证据")}</h2><ErrorBox error={evidence.error} />
      <div className="record-list">{evidence.data?.rows.map((e: Json) => <article key={e.id}><div><strong>{e.label}</strong><small>{e.role} · {e.format} {e.locator.revision ? `· r${e.locator.revision}` : ""}</small><small>{e.sha256 || e.locator.content_hash || t("哈希待核查")}</small></div>
        <Button onClick={() => { setPreview(e); setPage(0); }}>{t("查看")}</Button>
        {e.run_id && <Link to={`/runs/${e.run_id}`} onClick={() => selectProject?.(project)}>{t("查看运行与回放")}</Link>}
        {["file", "artifact", "package"].includes(e.locator.kind) && <a href={`/api/v2/projects/${project}/record-evidence/${e.id}/content`}>{t("下载原件")}</a>}
      </article>)}</div>
      <div className="record-actions"><Button disabled={!evidenceOffset} onClick={() => setEvidenceOffset(Math.max(0, evidenceOffset - 50))}>{t("上一页")}</Button><Button disabled={!evidence.data?.more} onClick={() => setEvidenceOffset(evidenceOffset + 50)}>{t("下一页")}</Button></div>
    </section>
    <section><h2>{t("个体、条件与阶段")}</h2><ErrorBox error={entries.error} />{entries.data?.rows.map((e: Json) => <details key={e.id}><summary>{e.kind} · {e.original_key}</summary><pre>{JSON.stringify(e.content, null, 2)}</pre></details>)}
      <div className="record-actions"><Button disabled={!entryOffset} onClick={() => setEntryOffset(Math.max(0, entryOffset - 50))}>{t("上一页")}</Button><Button disabled={!entries.data?.more} onClick={() => setEntryOffset(entryOffset + 50)}>{t("下一页")}</Button></div>
    </section>
    {preview && <Modal open title={preview.label} onOpenChange={open => !open && setPreview(null)}><ErrorBox error={content.error} />{content.isPending ? <Loading /> : content.data && <>
      {typeof content.data.text === "string" ? markdown(content.data.text) : content.data.text?.blocks ? content.data.text.blocks.map((b: Json) => b.markdown ? <div key={b.id}>{markdown(b.markdown)}</div> : <pre key={b.id}>{JSON.stringify(b, null, 2)}</pre>) : content.data.text?.format === "markdown" ? markdown(content.data.text.text) : content.data.text?.format === "document" ? (
        content.data.text.content?.content?.[0]?.type === "codeBlock" && content.data.text.content.content[0].attrs?.language === "markdown"
          ? markdown(content.data.text.content.content[0].content.map((n: Json) => n.text || "").join(""))
          : <Suspense fallback={<Loading />}><NoteEditor readOnly project={project} value={content.data.text} onChange={() => {}} /></Suspense>
      ) : <pre>{JSON.stringify(content.data, null, 2)}</pre>}
      {content.data.runtime && <Link to={`/runs/${content.data.runtime.run_id}`} onClick={() => selectProject?.(project)}>{t("查看运行与回放")}</Link>}
      {content.data.format === "jsonl" && <div className="record-actions"><Button disabled={!page} onClick={() => setPage(Math.max(0, page - 50))}>{t("上一页")}</Button><Button disabled={!content.data.more} onClick={() => setPage(page + 50)}>{t("下一页")}</Button></div>}
    </>}</Modal>}
    {editing && <AppendDialog mode={editing} base={base} onClose={() => setEditing(null)} onSaved={() => { void client.invalidateQueries({ queryKey: ["record-evidence", project, identity] }); void client.invalidateQueries({ queryKey: ["record-entries", project, identity] }); void client.invalidateQueries({ queryKey: ["research-record", project, identity] }); void client.invalidateQueries({ queryKey: ["research-records"] }); }} />}
  </div>;
}

function AppendDialog({ mode, base, onClose, onSaved }: { mode: string; base: string; onClose: () => void; onSaved: () => void }) {
  const [title, setTitle] = useState(""), [text, setText] = useState(""), [request] = useState(() => crypto.randomUUID());
  const [status, setStatus] = useState("completed");
  const save = useMutation({ mutationFn: () => mode === "finalize" ? post(base + "/finalize", { request_id: request, execution_status: status }) : mode === "stage" ? post(base + "/entries", { request_id: request, kind: "stage", original_key: title, content: { markdown: text } }) : mode === "evidence" ? post(base + "/evidence", { request_id: request, evidence: JSON.parse(text) }) : post(base + "/texts", { request_id: request, identity: request, expected_revision: 0, kind: mode, title, markdown: text }), onSuccess: () => { onSaved(); onClose(); } });
  return <Modal open title={t(mode === "finalize" ? "结项核验" : mode === "stage" ? "追加阶段" : mode === "evidence" ? "关联证据" : mode === "report" ? "保存报告" : "保存笔记")} onOpenChange={open => !open && onClose()}><form onSubmit={e => { e.preventDefault(); save.mutate(); }}>
    {mode === "finalize" ? <><p>{t("仅核验和登记实际执行状态；不会启动、停止或重新运行实验。")}</p><Field label={t("执行状态")}><select value={status} onChange={e => setStatus(e.target.value)}>{["planned", "running", "completed", "failed", "interrupted", "cancelled", "unknown"].map(v => <option value={v} key={v}>{label(v)}</option>)}</select></Field></> : <>
      {mode !== "evidence" && <Field label={t("标题或阶段标识")}><input required value={title} onChange={e => setTitle(e.target.value)} maxLength={200} /></Field>}
      <Field label={t(mode === "evidence" ? "证据描述 JSON" : "正文")}><textarea required rows={12} value={text} onChange={e => setText(e.target.value)} /></Field>
    </>}
    <ErrorBox error={save.error} /><Button type="submit" disabled={save.isPending}>{t("保存")}</Button>
  </form></Modal>;
}
