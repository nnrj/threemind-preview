import { can } from "./access";
import { useState, useEffect } from "react";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, projectPath } from "./api";
import { Button, ErrorBox, Field, Loading, useWorkspace } from "./ui";
import { t } from "./i18n";
import StorageAudit from "./storageAudit";
import ExperimentStorage from "./ExperimentStorage";
import "./dataManagement.css";

type Json = Record<string, any>;
const bytes = (value: number | undefined) =>
  value == null
    ? "—"
    : `${(value / 1024 ** 2).toLocaleString(undefined, { maximumFractionDigits: 2 })} MiB`;
function Evidence({ value }: { value: unknown }) {
  return (
    <details className="data-evidence">
      <summary>{t("查看完整元数据与回执")}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}
// Keep the same identity across a disconnect/reload. Metadata revisions and input
// changes naturally get a different request; there is no blind new-ID retry.
async function command(
  path: string,
  body: Json,
  field?: "operation_id" | "request_id",
  method = "POST",
) {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(JSON.stringify(body)),
  );
  const fingerprint = Array.from(new Uint8Array(digest), (value) =>
    value.toString(16).padStart(2, "0"),
  ).join("");
  const key = `threemind-data-request:${path}:${fingerprint}`;
  let identity = sessionStorage.getItem(key);
  if (!identity) {
    identity = crypto.randomUUID();
    sessionStorage.setItem(key, identity);
  }
  return api<Json>(path, {
    method,
    body: JSON.stringify(field ? { ...body, [field]: identity } : body),
    headers: { "X-ThreeMind-Request-ID": identity },
  });
}

function RootChange({
  overview,
  changed,
}: {
  overview: Json;
  changed: () => void;
}) {
  const [destination, setDestination] = useState(
    overview.data_root?.requested_path ?? "",
  );
  const [changeId, setChangeId] = useState(
    sessionStorage.getItem("threemind-root-change") ?? "",
  );
  const status = useQuery<Json>({
    queryKey: ["root-change", changeId],
    queryFn: () => api(`/storage/root-changes/${changeId}`),
    enabled: !!changeId,
    refetchInterval: 3000,
  });
  const preview = useMutation({
    mutationFn: () => command("/storage/root-changes/preview", { destination }),
  });
  const submit = useMutation({
    mutationFn: async () => {
      const plan = await command(
        "/storage/root-changes",
        {
          destination,
          expected_revision: overview.data_root.revision,
        },
        "operation_id",
      );
      setChangeId(plan.id);
      sessionStorage.setItem("threemind-root-change", plan.id);
      return command(
        `/storage/root-changes/${plan.id}/execute`,
        {},
        "operation_id",
      );
    },
  });
  const action = useMutation({
    mutationFn: (name: string) =>
      command(`/storage/root-changes/${changeId}/${name}`, {}, "operation_id"),
    onSuccess: () => {
      status.refetch();
      changed();
    },
  });
  const backend = useMutation({
    mutationFn: (value: string) =>
      command(
        "/storage/checkpoint-backend",
        {
          backend: value,
          expected_revision: overview.checkpoint_settings.revision,
        },
        undefined,
        "PUT",
      ),
    onSuccess: changed,
  });
  useEffect(() => {
    if (
      status.data?.state === "complete" ||
      status.data?.state === "rolled_back"
    )
      changed();
  }, [status.data?.state]);
  return (
    <section className="data-evidence">
      <h3>{t("研究数据根目录")}</h3>
      <p>
        {t("当前目录")}: {overview.data_root.path}
      </p>
      <p>
        {t(
          "目录变更复制并校验原件，再切换位置；源副本保留。数据库查询数据和宿主控制区不移动。",
        )}
      </p>
      {overview.data_root.migration_required && (
        <p role="alert">
          {t("配置指向新目录，旧登记仍有效；请完成目录变更。")}
        </p>
      )}
      <Field label={t("新数据目录")}>
        <input
          value={destination}
          onChange={(e) => {
            setDestination(e.target.value);
            preview.reset();
          }}
        />
      </Field>
      <Button
        disabled={!destination || preview.isPending}
        onClick={() => preview.mutate()}
      >
        {t("预览目录变更")}
      </Button>
      {preview.data && (
        <>
          <p>
            {t("文件")}: {preview.data.files} · {t("数据库原件")}:{" "}
            {preview.data.payload_count} · {bytes(preview.data.bytes)}
          </p>
          <p>
            {t("可用空间")}: {bytes(preview.data.free_bytes)} · {t("预留空间")}:{" "}
            {bytes(preview.data.reserve_bytes)}
          </p>
          {!preview.data.space_sufficient && (
            <p role="alert">{t("空间不足，不能执行；请先清理或更换目录。")}</p>
          )}
          <Evidence value={preview.data} />
          <Button
            disabled={!preview.data.space_sufficient || submit.isPending}
            onClick={() => {
              if (
                window.confirm(
                  t(
                    "确认复制并切换研究原件目录？源副本将保留，途中可取消或稍后继续。",
                  ),
                )
              )
                submit.mutate();
            }}
          >
            {t("执行目录变更")}
          </Button>
        </>
      )}
      <Field label={t("目录变更任务编号")}>
        <input value={changeId} onChange={(e) => setChangeId(e.target.value)} />
      </Field>
      {status.data && (
        <>
          <p>
            {t("任务状态")}: {status.data.state} · {t("已完成资源")}:{" "}
            {status.data.resources_completed}/{status.data.resource_count} ·{" "}
            {t("已完成原件")}: {status.data.payloads_completed}/
            {status.data.payload_count}
          </p>
          {["resume", "cancel", "verify", "rollback"].map((name) => (
            <Button
              key={name}
              disabled={action.isPending}
              onClick={() => {
                if (
                  name !== "rollback" ||
                  window.confirm(
                    t("确认回退读取位置？将核验源副本，保留新目录副本。"),
                  )
                )
                  action.mutate(name);
              }}
            >
              {t(
                (
                  {
                    resume: "继续",
                    cancel: "取消",
                    verify: "校验",
                    rollback: "回退",
                  } as Json
                )[name],
              )}
            </Button>
          ))}
          <a href={`/api/v2/storage/root-changes/${changeId}/manifest`}>
            {t("下载逐项迁移清单")}
          </a>
          <Evidence value={status.data} />
        </>
      )}
      <Field label={t("运行检查点保存方式")}>
        <select
          value={overview.checkpoint_backend}
          disabled={backend.isPending}
          onChange={(e) => backend.mutate(e.target.value)}
        >
          <option value="database">{t("数据库（默认）")}</option>
          <option value="filesystem">{t("文件系统")}</option>
        </select>
      </Field>
      <p>
        {t(
          "这是宿主保存配置；不改变内核、模拟时间或图查询。文件检查点先校验，再提交完整恢复引用。",
        )}
      </p>
      <ErrorBox
        error={
          preview.error ??
          submit.error ??
          status.error ??
          action.error ??
          backend.error
        }
      />
    </section>
  );
}

export default function DataManagement() {
  const { project, user } = useWorkspace();
  const [search] = useSearchParams();
  const [tab, setTab] = useState(
    search.get("view") === "storage"
      ? "storage"
      : search.get("view") === "bundles"
        ? "bundles"
        : "inventory",
  );
  if (!project && !can(user, "system.read"))
    return <p>{t("请先选择研究项目")}</p>;
  const activeTab = project ? tab : "storage";
  return (
    <div className="data-management">
      <header className="page-header">
        <div>
          <h1>{t("数据管理")}</h1>
          <p>
            {t("查询研究资料，核对依赖后打包；迁移和永久清理需要独立确认。")}
          </p>
        </div>
      </header>
      <nav className="data-tabs" aria-label={t("数据管理功能")}>
        {[
          ...(project
            ? [
                ["inventory", "资料目录"],
                ["bundles", "数据包"],
                ["integrity", "完整性与清理"],
              ]
            : []),
          ...(can(user, "system.read") ? [["storage", "存储位置"]] : []),
        ].map(([id, label]) => (
          <Button
            key={id}
            aria-pressed={activeTab === id}
            variant={activeTab === id ? "primary" : ""}
            onClick={() => setTab(id)}
          >
            {t(label)}
          </Button>
        ))}
      </nav>
      {activeTab === "inventory" && project && (
        <Inventory key={project.id} project={project.id} />
      )}
      {activeTab === "bundles" && project && (
        <Bundles key={project.id} project={project.id} />
      )}
      {activeTab === "integrity" && project && (
        <Integrity
          key={project.id}
          project={project.id}
          owner={project.role === "owner"}
        />
      )}
      {activeTab === "storage" && can(user, "system.read") && <HostStorage />}
    </div>
  );
}

function Inventory({ project }: { project: string }) {
  const [search] = useSearchParams();
  const base = `${projectPath(project)}/data`;
  const [q, setQ] = useState(""),
    [kind, setKind] = useState(""),
    [dimension, setDimension] = useState("run"),
    [scope, setScope] = useState(""),
    [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Json[]>([]);
  const params = new URLSearchParams({
    q,
    offset: String(offset),
    limit: "50",
  });
  if (kind) params.set("kind", kind);
  if (scope) params.set(dimension, scope);
  const query = useQuery<Json>({
    queryKey: ["data-inventory", project, params.toString()],
    queryFn: () => api(base + "?" + params),
  });
  const detail = useMutation({
    mutationFn: (row: Json) =>
      api(
        `${base}/resources/${encodeURIComponent(row.kind)}/${encodeURIComponent(row.id)}`,
      ),
  });
  const resourceId = search.get("resource"),
    resourceKind = search.get("kind");
  useEffect(() => {
    if (resourceId && resourceKind)
      detail.mutate({ id: resourceId, kind: resourceKind });
  }, [resourceId, resourceKind]);
  const preview = useMutation({
    mutationFn: (wholeRange: boolean) =>
      command(
        base + "/export-plans",
        {
          selection: wholeRange
            ? {
                filters: {
                  q,
                  ...(kind ? { kind } : {}),
                  ...(scope ? { [dimension]: scope } : {}),
                },
              }
            : {
                resources: selected.map((row) => ({
                  kind: row.kind,
                  id: row.id,
                })),
              },
        },
        "operation_id",
      ),
  });
  const exportJob = useMutation({
    mutationFn: () =>
      command(base + "/exports", { plan_id: preview.data!.id }, "operation_id"),
  });
  return (
    <section className="data-panel">
      <h2>{t("资料目录")}</h2>
      <div className="data-form-grid">
        <Field label={t("搜索名称或标签")}>
          <input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
          />
        </Field>
        <Field label={t("资料类型")}>
          <input
            value={kind}
            placeholder="run / report / note"
            onChange={(e) => {
              setKind(e.target.value);
              setOffset(0);
            }}
          />
        </Field>
        <Field label={t("查询维度")}>
          <select
            value={dimension}
            onChange={(e) => {
              setDimension(e.target.value);
              setOffset(0);
            }}
          >
            {["experiment", "run", "population", "batch", "dataset", "tag"].map(
              (value) => (
                <option key={value}>{value}</option>
              ),
            )}
          </select>
        </Field>
        <Field label={t("维度编号或标签")}>
          <input
            value={scope}
            onChange={(e) => {
              setScope(e.target.value);
              setOffset(0);
            }}
          />
        </Field>
      </div>
      <ErrorBox error={query.error} />
      {query.isPending && <Loading />}
      <div className="data-resource-list">
        {(query.data?.rows ?? []).map((row: Json) => {
          const checked = selected.some(
            (item) => item.kind === row.kind && item.id === row.id,
          );
          return (
            <article key={`${row.kind}:${row.id}`}>
              <label>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => {
                    setSelected(
                      checked
                        ? selected.filter(
                            (item) =>
                              !(item.kind === row.kind && item.id === row.id),
                          )
                        : [...selected, row],
                    );
                    preview.reset();
                    exportJob.reset();
                  }}
                />
                <span>
                  <strong>{row.name ?? row.title ?? row.id}</strong>
                  <small>
                    {row.kind} · {row.id}
                  </small>
                </span>
              </label>
              <span>{bytes(row.bytes)}</span>
              <Button onClick={() => detail.mutate(row)}>
                {t("查看资料")}
              </Button>
            </article>
          );
        })}
      </div>
      {query.data && !query.data.rows?.length && <p>{t("此范围暂无资料")}</p>}
      <div className="data-actions">
        <Button disabled={offset === 0} onClick={() => setOffset(offset - 50)}>
          {t("上一页")}
        </Button>
        <Button
          disabled={!query.data?.more}
          onClick={() => setOffset(offset + 50)}
        >
          {t("下一页")}
        </Button>
        <Button
          disabled={!selected.length || preview.isPending}
          onClick={() => preview.mutate(false)}
        >
          {t("预览所选资料打包")}
        </Button>
        <span>
          {selected.length} {t("项已选择")}
        </span>
        <Button
          disabled={preview.isPending || !query.data}
          onClick={() => preview.mutate(true)}
        >
          {t("预览当前范围完整打包")}
        </Button>
      </div>
      <ErrorBox error={detail.error ?? preview.error ?? exportJob.error} />
      {detail.data && <Evidence value={detail.data} />}
      {preview.data && (
        <div className="data-risk">
          <h3>{t("导出预览")}</h3>
          <p>{t("服务会包含必要依赖和完整历史。缺失的必要对象会阻止导出。")}</p>
          <p>
            {bytes(preview.data.bytes)} · {preview.data.objects?.length ?? "—"}{" "}
            {t("个对象")}
          </p>
          {(preview.data.blockers ?? []).map((item: any, index: number) => (
            <p key={index}>
              {typeof item === "string" ? item : JSON.stringify(item)}
            </p>
          ))}
          <Button
            variant="primary"
            disabled={exportJob.isPending || !!preview.data.blockers?.length}
            onClick={() => exportJob.mutate()}
          >
            {t("确认建立导出任务")}
          </Button>
          <Evidence value={preview.data} />
        </div>
      )}
      {exportJob.data && (
        <div role="status">
          <p>{t("任务已登记；请等待任务完成后在数据包中下载。")}</p>
          <Evidence value={exportJob.data} />
          <JobProgress base={base} id={exportJob.data.id} />
        </div>
      )}
    </section>
  );
}

function JobProgress({ base, id }: { base: string; id: string }) {
  const query = useQuery<Json>({
    queryKey: ["data-job", base, id],
    queryFn: () => api(`${base}/jobs/${id}`),
    refetchInterval: 3000,
  });
  const cancel = useMutation({
    mutationFn: () => command(`${base}/jobs/${id}/cancel`, {}, "operation_id"),
    onSuccess: () => query.refetch(),
  });
  return (
    <div>
      <p>
        {t("数据任务状态")}: {query.data?.status ?? "—"} · {id}
      </p>
      <Button
        disabled={
          cancel.isPending ||
          !["pending", "leased"].includes(query.data?.status)
        }
        onClick={() => cancel.mutate()}
      >
        {t("取消未完成数据任务")}
      </Button>
      <ErrorBox error={query.error ?? cancel.error} />
      {query.data && <Evidence value={query.data} />}
    </div>
  );
}

function Bundles({ project }: { project: string }) {
  const [search] = useSearchParams();
  const base = `${projectPath(project)}/data`,
    queryClient = useQueryClient();
  const [files, setFiles] = useState<File[]>([]),
    [manifest, setManifest] = useState<File | null>(null),
    [name, setName] = useState("Imported data bundle"),
    [backend, setBackend] = useState("native");
  const [offset, setOffset] = useState(0),
    [chosen, setChosen] = useState<string | null>(search.get("bundle")),
    [objectId, setObjectId] = useState("");
  const list = useQuery<Json>({
    queryKey: ["data-bundles", project, offset],
    queryFn: () => api(`${base}/bundles?offset=${offset}&limit=50`),
    refetchInterval: 10000,
  });
  const detail = useQuery<Json>({
    queryKey: ["data-bundle", project, chosen],
    queryFn: () => api(`${base}/bundles/${chosen}`),
    enabled: !!chosen,
    refetchInterval: chosen ? 10000 : false,
  });
  const upload = (register: boolean) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    if (manifest) form.append("manifest", manifest);
    if (!register) form.append("backend", backend);
    if (register) {
      const identityKey = `threemind-data-import:${project}:${name}:${preview.data?.bundle_id ?? files.map((file) => `${file.name}:${file.size}:${file.lastModified}`).join("|")}`;
      let importId = sessionStorage.getItem(identityKey);
      if (!importId) {
        importId = crypto.randomUUID();
        sessionStorage.setItem(identityKey, importId);
      }
      form.append("operation_id", importId);
      form.append("name", name);
    }
    return api<Json>(`${base}/imports${register ? "" : "/preflight"}`, {
      method: "POST",
      body: form,
    });
  };
  const preview = useMutation({ mutationFn: () => upload(false) });
  const imported = useMutation({
    mutationFn: () => upload(true),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["data-bundles", project] });
      if (data.id) setChosen(data.id);
    },
  });
  const restore = useMutation({
    mutationFn: () =>
      command(`${base}/bundles/${chosen}/restore-records`, {}, "operation_id"),
  });
  const original = useMutation({
    mutationFn: () =>
      api(`${base}/bundles/${chosen}/objects/${encodeURIComponent(objectId)}`),
  });
  const resumePreview = useMutation({
    mutationFn: () =>
      api(
        `${base}/bundles/${chosen}/resume-plan?object_id=${encodeURIComponent(objectId)}&backend=${backend}`,
      ),
  });
  const resumed = useMutation({
    mutationFn: () =>
      command(
        `${base}/bundles/${chosen}/resumes`,
        {
          object_id: objectId,
          name: "Imported subject",
          backend,
          acknowledge_external_changes: false,
        },
        "operation_id",
      ),
  });
  const changed = () => {
    preview.reset();
    imported.reset();
  };
  return (
    <section className="data-panel">
      <h2>{t("数据包")}</h2>
      <p>
        {t(
          "导入先登记只读来源资料。恢复报告与笔记、恢复实验主体分别操作，不会自动运行。",
        )}
      </p>
      <div className="data-form-grid">
        <Field label={t("主体恢复运行后端")}>
          <select
            value={backend}
            onChange={(e) => {
              setBackend(e.target.value);
              changed();
              resumePreview.reset();
              resumed.reset();
            }}
          >
            <option value="native">native</option>
            <option value="reference">reference</option>
          </select>
        </Field>
        <Field label={t("包名称")}>
          <input
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              changed();
            }}
          />
        </Field>
        <Field label={t("选择数据包分卷")}>
          <input
            type="file"
            multiple
            accept=".tmdata"
            onChange={(e) => {
              setFiles(Array.from(e.target.files ?? []));
              changed();
            }}
          />
        </Field>
        <Field label={t("多卷总清单（可选）")}>
          <input
            type="file"
            accept=".json"
            onChange={(e) => {
              setManifest(e.target.files?.[0] ?? null);
              changed();
            }}
          />
        </Field>
      </div>
      <div className="data-actions">
        <Button
          disabled={!files.length || preview.isPending}
          onClick={() => preview.mutate()}
        >
          {t("核验导入包")}
        </Button>
        <Button
          disabled={
            !preview.data ||
            !!preview.data.missing_required?.length ||
            imported.isPending
          }
          onClick={() => imported.mutate()}
        >
          {t("确认登记来源资料")}
        </Button>
      </div>
      <ErrorBox error={preview.error ?? imported.error} />
      {preview.data && (
        <div className="data-risk">
          <p>
            {t(
              "所有必要分卷和对象须齐全且哈希一致。未知对象可只读查看，旧公开分享链接不会重新启用。",
            )}
          </p>
          <Evidence value={preview.data} />
        </div>
      )}
      {imported.data && (
        <p role="status">{t("资料已登记，原生恢复需要另行确认。")}</p>
      )}
      <div className="data-resource-list">
        {(list.data?.rows ?? []).map((row: Json) => (
          <article key={row.id}>
            <span>
              <strong>{row.name ?? row.id}</strong>
              <small>{row.status ?? row.schema}</small>
            </span>
            <Button
              onClick={() => {
                setChosen(row.id);
                restore.reset();
                resumePreview.reset();
                resumed.reset();
              }}
            >
              {t("查看数据包")}
            </Button>
          </article>
        ))}
      </div>
      <ErrorBox error={list.error ?? detail.error} />
      <div className="data-actions">
        <Button disabled={!offset} onClick={() => setOffset(offset - 50)}>
          {t("上一页")}
        </Button>
        <Button
          disabled={!list.data?.more}
          onClick={() => setOffset(offset + 50)}
        >
          {t("下一页")}
        </Button>
      </div>
      {detail.data && (
        <div className="data-risk">
          <h3>{detail.data.name ?? chosen}</h3>
          <div className="data-actions">
            <a
              className="button"
              href={`/api/v2${base}/bundles/${chosen}/manifest`}
            >
              {t("下载总清单")}
            </a>
            {(detail.data.volumes ?? []).map((volume: Json) => (
              <a
                key={volume.ordinal}
                className="button"
                href={`/api/v2${base}/bundles/${chosen}/volumes/${volume.ordinal}`}
              >
                {t("下载分卷")} {volume.ordinal + 1} · {bytes(volume.bytes)}
              </a>
            ))}
          </div>
          <p>
            {t(
              "报告与本人笔记恢复为新本地编号，保留来源版本和原始证据；原公开授权不会复活。",
            )}
          </p>
          <Button disabled={restore.isPending} onClick={() => restore.mutate()}>
            {t("恢复报告与笔记")}
          </Button>
          <div className="data-form-grid">
            <Field label={t("待恢复主体的来源对象编号")}>
              <input
                value={objectId}
                onChange={(e) => {
                  setObjectId(e.target.value);
                  resumePreview.reset();
                  resumed.reset();
                  original.reset();
                }}
              />
            </Field>
          </div>
          <Button
            disabled={!objectId || original.isPending}
            onClick={() => original.mutate()}
          >
            {t("查看来源原件")}
          </Button>
          {original.data && <Evidence value={original.data} />}
          <Button
            disabled={!objectId || resumePreview.isPending}
            onClick={() => resumePreview.mutate()}
          >
            {t("检查主体恢复条件")}
          </Button>
          {resumePreview.data && (
            <>
              <Evidence value={resumePreview.data} />
              <p>
                {t(
                  "主体必须由对应专用格式恢复，保持完整状态并暂停；未知资料禁止恢复运行。",
                )}
              </p>
              <Button
                disabled={
                  resumed.isPending ||
                  resumePreview.data.can_resume !== true ||
                  !!resumePreview.data.blockers?.length
                }
                onClick={() => resumed.mutate()}
              >
                {t("确认恢复为暂停副本")}
              </Button>
            </>
          )}
          <ErrorBox
            error={
              restore.error ??
              resumePreview.error ??
              resumed.error ??
              original.error
            }
          />
          {restore.data && <Evidence value={restore.data} />}
          {restore.data?.kind === "data_restore" && (
            <JobProgress base={base} id={restore.data.id} />
          )}
          {resumed.data && <Evidence value={resumed.data} />}
          {resumed.data?.kind === "data_resume" && (
            <JobProgress base={base} id={resumed.data.id} />
          )}
          <Evidence value={detail.data} />
        </div>
      )}
      <p>
        <Link to="/models">{t("旧实验包与模型库")}</Link>
      </p>
    </section>
  );
}

function Integrity({ project, owner }: { project: string; owner: boolean }) {
  const base = `${projectPath(project)}/data`;
  const candidates = useQuery<Json>({
    queryKey: ["blob-candidates", project],
    queryFn: () => api(base + "/blob-candidates"),
    enabled: owner,
  });
  const audit = useMutation({
    mutationFn: (verify: boolean) => api(`${base}/integrity?verify=${verify}`),
  });
  const [candidate, setCandidate] = useState(""),
    [confirm, setConfirm] = useState("");
  const preview = useMutation<Json>({
    mutationFn: () =>
      api(
        `${base}/blob-candidates/${encodeURIComponent(candidate)}/cleanup-preview`,
      ),
  });
  const cleanup = useMutation({
    mutationFn: () =>
      api(`${base}/blob-candidates/${encodeURIComponent(candidate)}/cleanup`, {
        method: "POST",
        body: JSON.stringify({
          token: preview.data!.token,
          confirm_name: confirm,
        }),
      }),
  });
  return (
    <section className="data-panel">
      <h2>{t("完整性与清理")}</h2>
      <p>
        {t(
          "逻辑对象字节不等于数据库索引、WAL或后端物理占用。校验受显式对象和字节预算限制。",
        )}
      </p>
      <div className="data-actions">
        <Button disabled={audit.isPending} onClick={() => audit.mutate(false)}>
          {t("查询原件登记")}
        </Button>
        <Button disabled={audit.isPending} onClick={() => audit.mutate(true)}>
          {t("校验原件哈希")}
        </Button>
      </div>
      <ErrorBox error={audit.error} />
      {audit.data && <Evidence value={audit.data} />}
      <StorageAudit />
      <p>
        <Link to="/models">{t("模型库的归档与清理预览")}</Link>
      </p>
      {owner && (
        <div className="data-risk">
          <h3>{t("过期上传候选清理")}</h3>
          <ErrorBox error={candidates.error} />
          <div className="data-resource-list">
            {(candidates.data?.rows ?? []).map((row: Json) => (
              <article key={row.id}>
                <span>
                  <strong>{row.id}</strong>
                  <small>
                    {row.state} · {bytes(row.bytes)}
                  </small>
                </span>
                <Button
                  onClick={() => {
                    setCandidate(row.id);
                    setConfirm("");
                    preview.reset();
                    cleanup.reset();
                  }}
                >
                  {t("检查此候选")}
                </Button>
              </article>
            ))}
          </div>
          <Button
            disabled={candidates.isFetching}
            onClick={() => candidates.refetch()}
          >
            {t("刷新候选目录")}
          </Button>
          {candidates.data?.more && (
            <p>{t("候选目录达到预算，需缩小范围或通过命令查看。")}</p>
          )}
          <p>
            {t(
              "永久删除不可撤销。已登记或仍被引用的原件会被阻止；Agent接口只提供预览。",
            )}
          </p>
          <Field label={t("上传候选编号")}>
            <input
              value={candidate}
              onChange={(e) => {
                setCandidate(e.target.value);
                setConfirm("");
                preview.reset();
                cleanup.reset();
              }}
            />
          </Field>
          <Button
            disabled={!candidate || preview.isPending}
            onClick={() => preview.mutate()}
          >
            {t("生成清理预览")}
          </Button>
          {preview.data && (
            <>
              <Evidence value={preview.data} />
              {(preview.data.reasons ?? []).map((reason: string) => (
                <p key={reason}>{reason}</p>
              ))}
              <Field label={t("输入预览中的对象名称以确认永久删除")}>
                <input
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                />
              </Field>
              <Button
                disabled={
                  !preview.data.allowed ||
                  confirm !== preview.data.name ||
                  cleanup.isPending
                }
                onClick={() => cleanup.mutate()}
              >
                {t("确认永久清理候选")}
              </Button>
            </>
          )}
          <ErrorBox error={preview.error ?? cleanup.error} />
          {cleanup.data && <Evidence value={cleanup.data} />}
        </div>
      )}
    </section>
  );
}

export function HostStorage() {
  const { user } = useWorkspace();
  const writable = can(user, "system.write");
  const queryClient = useQueryClient();
  const overview = useQuery<Json>({
    queryKey: ["host-storage"],
    queryFn: () => api("/storage"),
  });
  const [artifactQuery, setArtifactQuery] = useState(""),
    [artifactOffset, setArtifactOffset] = useState(0);
  const artifactIndex = useQuery<Json>({
    queryKey: ["research-artifacts", artifactQuery, artifactOffset],
    queryFn: () =>
      api(
        `/storage/research-artifacts?q=${encodeURIComponent(artifactQuery)}&offset=${artifactOffset}&limit=50`,
      ),
  });
  const [kind, setKind] = useState("filesystem"),
    [name, setName] = useState(""),
    [path, setPath] = useState(""),
    [bucket, setBucket] = useState(""),
    [endpoint, setEndpoint] = useState(""),
    [accessKey, setAccessKey] = useState(""),
    [secret, setSecret] = useState("");
  const [category, setCategory] = useState("media-original"),
    [target, setTarget] = useState("");
  const [resourceId, setResourceId] = useState(""),
    [resourceTarget, setResourceTarget] = useState(""),
    [relative, setRelative] = useState(""),
    [writer, setWriter] = useState("unknown");
  const [selected, setSelected] = useState<Json | null>(null),
    [destination, setDestination] = useState(""),
    [destinationPath, setDestinationPath] = useState(""),
    [planId, setPlanId] = useState("");
  const changed = () =>
    queryClient.invalidateQueries({ queryKey: ["host-storage"] });
  const targetMutation = useMutation({
    mutationFn: () =>
      command("/storage/targets", {
        kind,
        name,
        expected_revision: 0,
        ...(kind === "filesystem" ? { path } : {}),
        configuration: kind === "s3" ? { bucket, endpoint } : {},
        ...(kind === "s3"
          ? {
              credentials: {
                access_key_id: accessKey,
                secret_access_key: secret,
              },
            }
          : {}),
      }),
    onSuccess: () => {
      setSecret("");
      setAccessKey("");
      changed();
    },
  });
  const policy = useMutation({
    mutationFn: () =>
      command(
        `/storage/policies/${category}`,
        {
          target_id: target,
          expected_revision: overview.data!.policies.revision,
        },
        undefined,
        "PUT",
      ),
    onSuccess: changed,
  });
  const resource = useMutation({
    mutationFn: () =>
      command("/storage/resources", {
        resource_id: resourceId,
        target_id: resourceTarget,
        relative_path: relative,
        writer_mode: writer,
        expected_revision: 0,
      }),
    onSuccess: changed,
  });
  const inspect = useMutation<Json, Error, Json>({
    mutationFn: (row: Json) =>
      api(`/storage/resources/${encodeURIComponent(row.id)}?hashes=true`),
    onSuccess: (data) => {
      setSelected(data.resource ?? data);
      offlineExport.reset();
    },
  });
  const offlineExport = useMutation<Json>({
    mutationFn: () =>
      command(
        "/storage/data-exports",
        {
          resource_id: selected!.id,
          expected_revision: selected!.revision,
        },
        "operation_id",
      ),
  });
  const plan = useMutation({
    mutationFn: () =>
      command(
        "/storage/migrations",
        {
          resource_id: selected!.id,
          target_id: destination,
          relative_path: destinationPath || null,
          expected_revision: selected!.revision,
        },
        "request_id",
      ),
    onSuccess: (data) => setPlanId(data.id),
  });
  const status = useQuery<Json>({
    queryKey: ["storage-migration", planId],
    queryFn: () => api(`/storage/migrations/${encodeURIComponent(planId)}`),
    enabled: !!planId,
    refetchInterval: planId ? 3000 : false,
  });
  const action = useMutation({
    mutationFn: (value: string) =>
      command(
        `/storage/migrations/${planId}/${value}`,
        value === "activate" || value === "rollback"
          ? {
              expected_revision: overview.data?.resources.find(
                (row: Json) => row.id === status.data?.resource_id,
              )?.revision,
            }
          : {},
        value === "execute" || value === "resume" ? "request_id" : undefined,
      ),
    onSuccess: () => {
      changed();
      status.refetch();
    },
  });
  const targets = overview.data?.targets ?? [];
  return (
    <section className="data-panel">
      <h2>{t("存储位置")}</h2>
      <ExperimentStorage writable={writable} />
      {overview.data && (
        <fieldset disabled={!writable}>
          <RootChange overview={overview.data} changed={changed} />
        </fieldset>
      )}
      <p>
        {t(
          "存储配置由具有系统管理权限的账号修改；只读账号可查询与核验。保存配置只影响未来写入。",
        )}
      </p>
      <ErrorBox error={overview.error} />
      {overview.isPending && <Loading />}
      <div className="data-resource-list">
        {targets.map((row: Json) => (
          <article key={row.id}>
            <span>
              <strong>{row.name}</strong>
              <small>
                {row.kind} · {row.id} · r{row.config_revision}
              </small>
              <small>
                {row.configuration.path ?? row.configuration.bucket}
              </small>
            </span>
            <span>{row.has_secret ? t("已保存加密凭据") : ""}</span>
          </article>
        ))}
      </div>
      <fieldset disabled={!writable}>
        <h3>{t("登记存储目标")}</h3>
        <div className="data-form-grid">
          <Field label={t("目标名称")}>
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label={t("后端")}>
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              {["filesystem", "s3", "db"].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </Field>
          {kind === "filesystem" && (
            <Field label={t("绝对目录")}>
              <input value={path} onChange={(e) => setPath(e.target.value)} />
            </Field>
          )}
          {kind === "s3" && (
            <>
              <Field label="Bucket">
                <input
                  value={bucket}
                  onChange={(e) => setBucket(e.target.value)}
                />
              </Field>
              <Field label="Endpoint">
                <input
                  value={endpoint}
                  onChange={(e) => setEndpoint(e.target.value)}
                />
              </Field>
              <Field label={t("访问密钥")}>
                <input
                  type="password"
                  autoComplete="off"
                  value={accessKey}
                  onChange={(e) => setAccessKey(e.target.value)}
                />
              </Field>
              <Field label={t("秘密密钥")}>
                <input
                  type="password"
                  autoComplete="off"
                  value={secret}
                  onChange={(e) => setSecret(e.target.value)}
                />
              </Field>
            </>
          )}
        </div>
        <Button
          disabled={!name || targetMutation.isPending}
          onClick={() => targetMutation.mutate()}
        >
          {t("保存存储目标")}
        </Button>
        <ErrorBox error={targetMutation.error} />
        <h3>{t("未来原件写入位置")}</h3>
        <div className="data-form-grid">
          <Field label={t("原件类别")}>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {["media-original", "note-image", "export"].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </Field>
          <Field label={t("存储目标")}>
            <select value={target} onChange={(e) => setTarget(e.target.value)}>
              <option value="">{t("选择目标")}</option>
              {targets.map((row: Json) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Button
          disabled={!target || policy.isPending}
          onClick={() => policy.mutate()}
        >
          {t("确认未来写入位置")}
        </Button>
        <ErrorBox error={policy.error} />
        <h3>{t("离线实验资料登记")}</h3>
        <p>
          {t(
            "历史写入程序未知时只能查询。封存表示已停止写入；协作写入要求程序实际遵守存储锁与写入协议。",
          )}
        </p>
        <div className="data-form-grid">
          <Field label={t("资源编号")}>
            <input
              value={resourceId}
              onChange={(e) => setResourceId(e.target.value)}
            />
          </Field>
          <Field label={t("存储目标")}>
            <select
              value={resourceTarget}
              onChange={(e) => setResourceTarget(e.target.value)}
            >
              <option value="">{t("选择目标")}</option>
              {targets
                .filter((row: Json) => row.kind === "filesystem")
                .map((row: Json) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                  </option>
                ))}
            </select>
          </Field>
          <Field label={t("目标内相对路径")}>
            <input
              value={relative}
              onChange={(e) => setRelative(e.target.value)}
            />
          </Field>
          <Field label={t("写入状态声明")}>
            <select value={writer} onChange={(e) => setWriter(e.target.value)}>
              <option value="unknown">{t("未知")}</option>
              <option value="sealed">{t("已封存")}</option>
              <option value="cooperative">{t("程序遵守协作协议")}</option>
            </select>
          </Field>
        </div>
        <Button
          disabled={
            !resourceId || !resourceTarget || !relative || resource.isPending
          }
          onClick={() => resource.mutate()}
        >
          {t("登记资料位置")}
        </Button>
        <ErrorBox error={resource.error} />
      </fieldset>
      <div className="data-resource-list">
        {(overview.data?.resources ?? []).map((row: Json) => (
          <article key={row.id}>
            <span>
              <strong>{row.id}</strong>
              <small>
                {row.writer_mode} · r{row.revision}
              </small>
            </span>
            <Button onClick={() => inspect.mutate(row)}>
              {t("检查迁移条件")}
            </Button>
          </article>
        ))}
      </div>
      <ErrorBox error={inspect.error} />
      {inspect.data && <Evidence value={inspect.data} />}
      {selected && (
        <fieldset disabled={!writable}>
          <div className="data-risk">
            <h3>{t("离线资料打包")}</h3>
            <p>
              {selected.id} · r{selected.revision} · {selected.writer_mode} ·{" "}
              {bytes(inspect.data?.bytes)}
            </p>
            <p>
              {t(
                "保存所检查目录内的全部原件为只读数据包；目录外的依赖不自动推断，不能作为完整主体续跑。",
              )}
            </p>
            <Button
              disabled={
                selected.writer_mode === "unknown" || offlineExport.isPending
              }
              onClick={() => offlineExport.mutate()}
            >
              {t("打包所检查的离线资料")}
            </Button>
            <ErrorBox error={offlineExport.error} />
            {offlineExport.data && (
              <>
                <p>
                  {t(
                    "离线数据包已保存；下载总清单和全部分卷后，可在项目数据包中登记为只读来源。",
                  )}
                </p>
                <div className="data-actions">
                  <a
                    href={`/api/v2/storage/data-exports/${offlineExport.data.id}/manifest`}
                  >
                    {t("下载总清单")}
                  </a>
                  {(offlineExport.data.volumes ?? []).map((row: Json) => (
                    <a
                      key={row.ordinal}
                      href={`/api/v2/storage/data-exports/${offlineExport.data!.id}/volumes/${row.ordinal}`}
                    >
                      {row.filename} · {bytes(row.bytes)}
                    </a>
                  ))}
                </div>
                <Evidence value={offlineExport.data} />
              </>
            )}
            <h3>{t("创建迁移计划")}</h3>
            <p>
              {t(
                "先复制并校验，启用新位置另行确认；保留原位置。启用后的新写入会限制回滚。",
              )}
            </p>
            <div className="data-form-grid">
              <Field label={t("迁移目标")}>
                <select
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                >
                  <option value="">{t("选择目标")}</option>
                  {targets
                    .filter((row: Json) => row.kind === "filesystem")
                    .map((row: Json) => (
                      <option key={row.id} value={row.id}>
                        {row.name}
                      </option>
                    ))}
                </select>
              </Field>
              <Field label={t("目标内相对路径")}>
                <input
                  value={destinationPath}
                  onChange={(e) => setDestinationPath(e.target.value)}
                />
              </Field>
            </div>
            <Button
              disabled={!destination || plan.isPending}
              onClick={() => plan.mutate()}
            >
              {t("保存迁移计划")}
            </Button>
            <ErrorBox error={plan.error} />
          </div>
        </fieldset>
      )}
      <Field label={t("查询已有迁移计划编号")}>
        <input value={planId} onChange={(e) => setPlanId(e.target.value)} />
      </Field>
      <ErrorBox error={status.error ?? action.error} />
      {status.data && (
        <div className="data-risk">
          <p>
            {t("迁移状态")}: {status.data.state} ·{" "}
            {bytes(status.data.copied_bytes)} / {bytes(status.data.bytes)}
          </p>
          <div className="data-actions">
            {[
              ["execute", "开始复制"],
              ["resume", "继续复制"],
              ["cancel", "取消复制"],
              ["verify", "校验目标"],
              ["activate", "确认启用新位置"],
              ["rollback", "回滚位置映射"],
            ].map(([id, label]) => (
              <Button
                key={id}
                disabled={
                  !writable ||
                  action.isPending ||
                  (id === "activate" && status.data.state !== "verified")
                }
                onClick={() => action.mutate(id)}
              >
                {t(label)}
              </Button>
            ))}
          </div>
          <Evidence value={status.data} />
        </div>
      )}
      <h3>{t("归档实验原件")}</h3>
      <p>{t("仅列出已校验的精确位置清单，下载时重新核验原始字节哈希。")}</p>
      <Field label={t("搜索原件路径或编号")}>
        <input
          value={artifactQuery}
          onChange={(e) => {
            setArtifactQuery(e.target.value);
            setArtifactOffset(0);
          }}
        />
      </Field>
      <ErrorBox error={artifactIndex.error} />
      <div className="data-resource-list">
        {(artifactIndex.data?.rows ?? []).map((row: Json) => (
          <article key={row.resource_id}>
            <span>
              <strong>{row.legacy_path}</strong>
              <small>{row.resource_id}</small>
              <small>{row.archive_path}</small>
            </span>
            <span>{bytes(row.bytes)}</span>
            <a
              className="button"
              href={`/api/v2/storage/research-artifacts/${encodeURIComponent(row.resource_id)}/content`}
            >
              {t("下载原件")}
            </a>
          </article>
        ))}
      </div>
      <div className="data-actions">
        <Button
          disabled={!artifactOffset}
          onClick={() => setArtifactOffset(artifactOffset - 50)}
        >
          {t("上一页")}
        </Button>
        <Button
          disabled={!artifactIndex.data?.more}
          onClick={() => setArtifactOffset(artifactOffset + 50)}
        >
          {t("下一页")}
        </Button>
      </div>
      <h3>{t("备份与恢复")}</h3>
      <p>
        {t(
          "备份由管理员在宿主机手动执行：threemind storage backup。数据库管理凭据仅通过环境变量提供；恢复必须使用新的空数据库。",
        )}
      </p>
      <Evidence value={overview.data?.features} />
    </section>
  );
}
