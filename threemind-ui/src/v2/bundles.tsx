import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Download, FileArchive, Upload } from "lucide-react";
import { api, projectPath, type Run } from "./api";
import {
  Badge,
  Button,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Modal,
  useWorkspace,
} from "./ui";
import { t, dateLabel } from "./i18n";
import { classes as readoutClasses } from "./readouts";
import "./bundles.css";

const chunkBytes = 4 * 1024 ** 2;
const sizeLabel = (n: number | string) =>
  `${(Number(n) / 1024 ** 2).toFixed(2)} MiB`;
type Page = { rows: any[]; more: boolean };

function TemporalEvidence({ record }: { record: any }) {
  const [offset, setOffset] = useState(0);
  const p = record?.payload ?? {};
  const rows = Array.isArray(p.nodes)
    ? [...p.nodes].sort(
        (a, b) =>
          (Number(b.last_activation) || 0) - (Number(a.last_activation) || 0) ||
          Number(a.node_id) - Number(b.node_id),
      )
    : [];
  const numeric = (x: unknown) =>
    typeof x === "number" ? x.toPrecision(5) : "—";
  return (
    <article className="bundle-temporal">
      <h4>{t(readoutClasses[String(p.classification)] ?? "窗内未定")}</h4>
      <p>
        {String(p.start_us ?? "?")} → {String(p.end_us ?? "?")} μs ·{" "}
        {String(p.reason ?? "")}
      </p>
      <p>
        {t("按窗口末次激活降序；未收敛的窗口仍如实保留，不能当成收敛答案。")}
      </p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>{t("节点")}</th>
              <th>{t("末次激活／投影")}</th>
              <th>{t("激活峰值")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(offset, offset + 20).map((n: any, i: number) => (
              <tr key={i}>
                <td>{String(n.node_id ?? "?")}</td>
                <td>{numeric(n.last_activation)}</td>
                <td>{numeric(n.peak_activation)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > 20 && (
        <div className="bundle-actions">
          <Button
            disabled={!offset}
            onClick={() => setOffset(Math.max(0, offset - 20))}
          >
            {t("上一页")}
          </Button>
          <span>
            {offset + 1}–{Math.min(offset + 20, rows.length)} / {rows.length}
          </span>
          <Button
            disabled={offset + 20 >= rows.length}
            onClick={() => setOffset(offset + 20)}
          >
            {t("下一页")}
          </Button>
        </div>
      )}
      <details>
        <summary>{t("完整原始记录")}</summary>
        <pre className="bundle-preview">{JSON.stringify(record, null, 2)}</pre>
      </details>
    </article>
  );
}

function useStableWrite() {
  const pending = useRef(new Map<string, string>());
  return async (path: string, body: unknown) => {
    const json = JSON.stringify(body),
      key = path + json;
    const id = pending.current.get(key) ?? crypto.randomUUID();
    pending.current.set(key, id);
    return api<any>(path, {
      method: "POST",
      body: json,
      headers: { "X-ThreeMind-Request-ID": id },
    });
  };
}

function AttachmentPicker({
  base,
  kind,
  selected,
  onChange,
}: {
  base: string;
  kind: string;
  selected: string[];
  onChange: (values: string[]) => void;
}) {
  const [offset, setOffset] = useState(0),
    [query, setQuery] = useState("");
  const notes = kind === "note" || kind === "draft";
  const result = useQuery({
    queryKey: ["bundle-attachments", base, kind, offset, query],
    queryFn: () =>
      api<Page>(
        `${base}/${notes ? "notes" : "research-documents"}?kind=${kind}&offset=${offset}&query=${encodeURIComponent(query)}`,
      ),
  });
  return (
    <div className="bundle-attachments">
      <input
        aria-label={t("搜索附件")}
        placeholder={t("搜索附件")}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOffset(0);
        }}
      />
      <ErrorBox error={result.error} />
      <div className="bundle-checklist">
        {result.data?.rows.map((item) => (
          <label key={item.id}>
            <input
              type="checkbox"
              checked={selected.includes(item.id)}
              disabled={!selected.includes(item.id) && selected.length >= 20}
              onChange={(e) =>
                onChange(
                  e.target.checked
                    ? [...selected, item.id]
                    : selected.filter((x) => x !== item.id),
                )
              }
            />
            {item.title}
          </label>
        ))}
      </div>
      <div className="bundle-actions">
        <Button
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 50))}
        >
          {t("上一页")}
        </Button>
        <Button
          disabled={!result.data?.more}
          onClick={() => setOffset(offset + 50)}
        >
          {t("下一页")}
        </Button>
        <small>{selected.length} / 20</small>
      </div>
    </div>
  );
}

function CreateBundle({
  base,
  close,
  done,
}: {
  base: string;
  close: () => void;
  done: () => void;
}) {
  const runs = useQuery({
    queryKey: ["bundle-runs", base],
    queryFn: () => api<Run[]>(`${base}/runs?summary=true&limit=1000`),
  });
  const [run, setRun] = useState(""),
    [name, setName] = useState(t("实验快照")),
    [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false),
    [notes, setNotes] = useState<string[]>([]),
    [documents, setDocuments] = useState<string[]>([]);
  const [kind, setKind] = useState("note"),
    [artifactIds, setArtifactIds] = useState<string[]>([]);
  const artifacts = useQuery({
    queryKey: ["bundle-artifacts", base],
    queryFn: () => api<any[]>(`${base}/artifacts`),
  });
  const selected = runs.data?.find((row) => row.id === run),
    write = useStableWrite();
  async function save() {
    setBusy(true);
    setError(null);
    try {
      await write(`${base}/runs/${run}/bundles`, {
        name,
        expected_revision: selected!.revision,
        note_ids: notes,
        document_ids: documents,
        artifact_ids: artifactIds,
      });
      done();
      close();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      open
      onOpenChange={(value) => {
        if (!value && !busy) close();
      }}
      title={t("保存实验快照")}
      description={t(
        "先暂停意识和实验计划。快照保留模型、在途输入、读出上下文与阶段游标。",
      )}
    >
      <div className="form-grid">
        <Field label={t("意识")}>
          <select
            aria-label={t("意识")}
            value={run}
            onChange={(e) => setRun(e.target.value)}
          >
            <option value="">{t("选择意识")}</option>
            {runs.data?.map((row) => (
              <option
                key={row.id}
                value={row.id}
                disabled={
                  ["running", "queued"].includes(row.status) || !row.revision
                }
              >
                {row.name} · r{row.revision} · {row.status}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("名称")}>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={160}
          />
        </Field>
      </div>
      <details className="bundle-attachment-section">
        <summary>{t("附带笔记、报告与工具模型（可选）")}</summary>
        <select
          aria-label={t("附件分类")}
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          <option value="note">{t("笔记")}</option>
          <option value="draft">{t("草稿")}</option>
          <option value="record">{t("实验记录")}</option>
          <option value="report">{t("实验报告")}</option>
        </select>
        <AttachmentPicker
          key={kind}
          base={base}
          kind={kind}
          selected={["note", "draft"].includes(kind) ? notes : documents}
          onChange={(values) =>
            (["note", "draft"].includes(kind) ? setNotes : setDocuments)(
              values.slice(0, 20),
            )
          }
        />
        <p>{t("工具模型和已完成制品")}</p>
        <div className="bundle-checklist">
          {artifacts.data
            ?.filter(
              (item) =>
                item.metadata?.schema !== "threemind.experiment-bundle/1",
            )
            .map((item) => (
              <label key={item.id}>
                <input
                  type="checkbox"
                  checked={artifactIds.includes(item.id)}
                  onChange={(e) =>
                    setArtifactIds(
                      e.target.checked
                        ? [...artifactIds, item.id].slice(0, 20)
                        : artifactIds.filter((id) => id !== item.id),
                    )
                  }
                />
                {item.name} · {sizeLabel(item.bytes)}
              </label>
            ))}
        </div>
      </details>
      <ErrorBox error={error || runs.error || artifacts.error} />
      <div className="modal-actions">
        <Button onClick={close} disabled={busy}>
          {t("取消")}
        </Button>
        <Button
          variant="primary"
          disabled={busy || !selected || !name.trim()}
          onClick={save}
        >
          {busy ? t("正在提交…") : t("保存实验快照")}
        </Button>
      </div>
    </Modal>
  );
}

function BundleDetails({
  base,
  id,
  close,
  done,
}: {
  base: string;
  id: string;
  close: () => void;
  done: () => void;
}) {
  const { project } = useWorkspace();
  const detail = useQuery({
    queryKey: ["bundle-detail", base, id],
    queryFn: () => api<any>(`${base}/bundles/${id}`),
  });
  const [entry, setEntry] = useState("readouts/temporal.jsonl"),
    [offset, setOffset] = useState(0),
    [name, setName] = useState(t("恢复的意识"));
  const [ack, setAck] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const [rid] = useState(() => crypto.randomUUID()),
    write = useStableWrite();
  const files = detail.data?.manifest.files ?? {};
  const preview = useQuery({
    queryKey: ["bundle-entry", base, id, entry, offset],
    enabled: !!files[entry],
    queryFn: () =>
      api<any>(
        `${base}/bundles/${id}/entry?name=${encodeURIComponent(entry)}&offset=${offset}&limit=20`,
      ),
  });
  const conditions = detail.data?.compatibility;
  async function resume() {
    setBusy(true);
    setError(null);
    try {
      await write(`${base}/bundles/${id}/resumes`, {
        request_id: rid,
        name,
        acknowledge_external_changes: ack,
      });
      done();
      close();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      open
      wide
      onOpenChange={(value) => {
        if (!value && !busy) close();
      }}
      title={detail.data?.name ?? t("实验快照")}
      description={t("查看原始证据；恢复会创建暂停的新意识，不覆盖来源。")}
    >
      {detail.isLoading ? (
        <Loading />
      ) : (
        <>
          <p className="bundle-digest">
            SHA-256 <code>{detail.data?.sha256}</code>
          </p>
          <Field label={t("证据内容")}>
            <select
              aria-label={t("证据内容")}
              value={entry}
              onChange={(e) => {
                setEntry(e.target.value);
                setOffset(0);
              }}
            >
              {Object.entries<any>(files)
                .filter(([, value]) =>
                  ["application/json", "application/x-ndjson"].includes(
                    value.media_type,
                  ),
                )
                .map(([key]) => (
                  <option key={key} value={key}>
                    {key === "readouts/temporal.jsonl"
                      ? t("时序读出（主要观察指标）")
                      : key}
                  </option>
                ))}
            </select>
          </Field>
          <ErrorBox error={preview.error} />
          {preview.isFetching ? (
            <Loading />
          ) : entry === "readouts/temporal.jsonl" ? (
            <div className="bundle-temporal-list">
              {preview.data?.rows?.length ? (
                preview.data.rows.map((record: any, index: number) => (
                  <TemporalEvidence key={offset + index} record={record} />
                ))
              ) : (
                <p>{t("此快照没有时序读出记录。")}</p>
              )}
            </div>
          ) : (
            <pre className="bundle-preview">
              {JSON.stringify(
                preview.data?.value ?? preview.data?.rows ?? [],
                null,
                2,
              )}
            </pre>
          )}
          {entry.endsWith(".jsonl") && (
            <div className="bundle-actions">
              <Button
                disabled={!offset}
                onClick={() => setOffset(Math.max(0, offset - 20))}
              >
                {t("上一页")}
              </Button>
              <Button
                disabled={!preview.data?.more}
                onClick={() => setOffset(offset + 20)}
              >
                {t("下一页")}
              </Button>
            </div>
          )}
          <section className="bundle-restore">
            <h3>{t("另建身份继续实验")}</h3>
            {conditions?.blockers?.map((reason: string) => (
              <p className="error-box" key={reason}>
                {reason}
              </p>
            ))}
            {conditions?.external_changes?.map((reason: string) => (
              <p key={reason}>{reason}</p>
            ))}
            {!!conditions?.external_changes?.length && (
              <label>
                <input
                  type="checkbox"
                  checked={ack}
                  onChange={(e) => setAck(e.target.checked)}
                />
                {t("确认并记录外部条件变化")}
              </label>
            )}
            <Field label={t("新意识名称")}>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={160}
              />
            </Field>
            <Button
              variant="primary"
              disabled={
                !conditions?.can_resume ||
                busy ||
                project?.role === "viewer" ||
                !name.trim() ||
                (!!conditions?.external_changes?.length && !ack)
              }
              onClick={resume}
            >
              {busy ? t("正在提交…") : t("恢复为暂停的意识")}
            </Button>
          </section>
        </>
      )}
      <ErrorBox error={error || detail.error} />
    </Modal>
  );
}

export default function Bundles() {
  const { project } = useWorkspace(),
    cache = useQueryClient(),
    base = projectPath(project!.id);
  const [offset, setOffset] = useState(0),
    [creating, setCreating] = useState(false),
    [detail, setDetail] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(),
    [progress, setProgress] = useState<number | null>(null),
    [uploadFile, setUploadFile] = useState<File | null>(null);
  const abort = useRef<AbortController | null>(null),
    write = useStableWrite();
  const bundles = useQuery({
    queryKey: ["bundles", base, offset],
    queryFn: () => api<Page>(`${base}/bundles?offset=${offset}`),
    refetchInterval: 5000,
  });
  const jobs = useQuery({
    queryKey: ["bundle-jobs", base],
    queryFn: () => api<any[]>(`${base}/jobs`),
    refetchInterval: 1500,
  });
  const refresh = () => {
    cache.invalidateQueries({ queryKey: ["bundles"] });
    cache.invalidateQueries({ queryKey: ["bundle-jobs"] });
    cache.invalidateQueries({ queryKey: ["runs"] });
  };
  useEffect(() => () => abort.current?.abort(), []);
  async function upload(file: File) {
    setError(null);
    setUploadFile(file);
    setProgress(0);
    const controller = new AbortController();
    abort.current = controller;
    const storageKey = `tm.bundle.upload.${project!.id}.${file.name}.${file.size}.${file.lastModified}`;
    try {
      let requestId: string = crypto.randomUUID();
      try {
        requestId = localStorage.getItem(storageKey) ?? requestId;
        localStorage.setItem(storageKey, requestId);
      } catch {
        /* Upload still works when persistent browser storage is disabled. */
      }
      if (file.size > 8 * 1024 ** 3)
        throw new Error(t("实验包不得超过 8 GiB。"));
      const session = await api<any>(`${base}/bundle-uploads`, {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({
          request_id: requestId,
          name: file.name.slice(0, 160),
          bytes: file.size,
        }),
      });
      const path = `${base}/bundle-uploads/${session.id}`,
        status = await api<any>(path, { signal: controller.signal });
      const present = new Map<number, any>(
        status.chunks.map((chunk: any) => [chunk.ordinal, chunk]),
      );
      for (
        let start = 0, index = 0;
        start < file.size;
        start += chunkBytes, index++
      ) {
        controller.signal.throwIfAborted();
        const part = await file.slice(start, start + chunkBytes).arrayBuffer();
        const sha = Array.from(
          new Uint8Array(await crypto.subtle.digest("SHA-256", part)),
        )
          .map((n) => n.toString(16).padStart(2, "0"))
          .join("");
        const old = present.get(index);
        if (
          old &&
          (old.sha256 !== sha || Number(old.bytes) !== part.byteLength)
        )
          throw new Error(t("已上传分块与所选文件不一致，请选择原文件。"));
        if (!old) {
          const saved = await api<any>(`${path}/chunks/${index}`, {
            method: "PUT",
            signal: controller.signal,
            headers: { "Content-Type": "application/octet-stream" },
            body: part,
          });
          if (saved.sha256 !== sha) throw new Error(t("上传校验失败。"));
        }
        setProgress(
          Math.min(100, ((start + part.byteLength) / file.size) * 100),
        );
      }
      await api(`${path}/complete`, {
        method: "POST",
        signal: controller.signal,
      });
      setUploadFile(null);
      refresh();
    } catch (e) {
      setError(e);
    } finally {
      setProgress(null);
      abort.current = null;
    }
  }
  const relevantJobs =
    jobs.data?.filter((job) => job.kind.startsWith("bundle_")) ?? [];
  return (
    <div className="bundle-workspace">
      <section className="panel bundle-intro">
        <div>
          <h2>{t("实验快照与交换")}</h2>
          <p>
            {t(
              "完整保存当前实验边界，按需下载或在另一台 ThreeMind 上只读导入。模型 .tmind 与实验包用途不同。",
            )}
          </p>
          <small>
            {t(
              "压缩包上限 8 GiB；临时目录保留 15 GiB。原数据不会因打包或导入被清理。",
            )}
          </small>
        </div>
        <div className="bundle-actions">
          <Button
            variant="primary"
            disabled={project?.role === "viewer"}
            onClick={() => setCreating(true)}
          >
            <FileArchive size={16} />
            {t("保存实验快照")}
          </Button>
          <label className="button">
            <Upload size={16} />
            {t("导入实验包")}
            <input
              type="file"
              hidden
              accept=".tmexperiment,.zip"
              disabled={progress !== null || project?.role === "viewer"}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void upload(file);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      </section>
      <ErrorBox error={error || bundles.error || jobs.error} />
      {progress !== null && (
        <div className="panel bundle-actions">
          <progress max={100} value={progress} />
          <span>
            {progress.toFixed(0)}% · {t("逐块上传，随后进行整包校验")}
          </span>
          <Button onClick={() => abort.current?.abort()}>
            {t("暂停上传")}
          </Button>
        </div>
      )}
      {uploadFile && progress === null && (
        <Button onClick={() => upload(uploadFile)}>
          {t("重试上传（复用已校验分块）")}
        </Button>
      )}
      {bundles.isLoading ? (
        <Loading />
      ) : !bundles.data?.rows.length ? (
        <Empty
          title={t("尚无实验快照")}
          detail={t(
            "暂停一个意识后保存快照，或导入已有实验包。导入不会自动运行。",
          )}
        />
      ) : (
        <div className="bundle-grid">
          {bundles.data.rows.map((bundle) => (
            <article className="panel bundle-card" key={bundle.id}>
              <FileArchive size={22} />
              <h3>{bundle.name}</h3>
              <p>
                {sizeLabel(bundle.bytes)} · {dateLabel(bundle.created_at)}
              </p>
              <p>
                {t("来源修订")} {bundle.metadata?.revision ?? "—"}
              </p>
              <code title={bundle.sha256}>{bundle.sha256.slice(0, 16)}…</code>
              <div className="bundle-actions">
                <Button onClick={() => setDetail(bundle.id)}>
                  {t("查看与恢复")}
                </Button>
                <a
                  className="button"
                  href={`/api/v2${base}/bundles/${bundle.id}/download`}
                >
                  <Download size={15} />
                  {t("下载")}
                </a>
              </div>
            </article>
          ))}
        </div>
      )}
      <div className="bundle-actions">
        <Button
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 20))}
        >
          {t("上一页")}
        </Button>
        <Button
          disabled={!bundles.data?.more}
          onClick={() => setOffset(offset + 20)}
        >
          {t("下一页")}
        </Button>
      </div>
      {!!relevantJobs.length && (
        <section className="panel">
          <h3>{t("实验包任务")}</h3>
          <div className="bundle-job-list">
            {relevantJobs.slice(0, 20).map((job) => (
              <div className="bundle-job" key={job.id}>
                <div>
                  <strong>
                    {job.kind === "bundle_export"
                      ? t("保存快照")
                      : job.kind === "bundle_import"
                        ? t("导入校验")
                        : t("恢复实验")}
                  </strong>
                  <small>{dateLabel(job.created_at)}</small>
                </div>
                <Badge status={job.status} />
                <ErrorBox error={job.error} />
                {job.result?.bundle_id && (
                  <Button onClick={() => setDetail(job.result.bundle_id)}>
                    {t("查看实验包")}
                  </Button>
                )}
                {job.result?.run_id && (
                  <Link className="button" to={`/runs/${job.result.run_id}`}>
                    {t("打开意识")}
                  </Link>
                )}
                {["pending", "leased"].includes(job.status) && (
                  <Button
                    onClick={() =>
                      write(`${base}/bundle-jobs/${job.id}/cancel`, {})
                        .then(refresh)
                        .catch(setError)
                    }
                  >
                    {t("取消任务")}
                  </Button>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
      {creating && (
        <CreateBundle
          base={base}
          close={() => setCreating(false)}
          done={refresh}
        />
      )}
      {detail && (
        <BundleDetails
          key={detail}
          base={base}
          id={detail}
          close={() => setDetail(null)}
          done={refresh}
        />
      )}
    </div>
  );
}
