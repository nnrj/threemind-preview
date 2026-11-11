import { t, locale } from "./i18n";
import { can } from "./access";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Archive,
  Bookmark,
  FilePenLine,
  GitFork,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { api, post, projectPath, timeLabel, type Run } from "./api";
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

const kinds: Record<string, string> = {
  created: "空白创建",
  imported: "模型导入",
  fork: "精确恢复分支",
  inherited: "继承出生",
  paired: "配对实验分支",
};
const countNames: Record<string, string> = {
  state_captures: "状态捕获回执",
  research_operations: "人工研究操作记录",
  research_plans: "受控实验计划",
  ai_calls: "AI 工具请求与返回内容",
  ai_tool_versions: "AI 工具配置版本",
  model_metadata_history: "档案注释历史",
  checkpoints: "恢复点",
  events: "科学事件",
  observations: "观测采样",
  input_envelopes: "输入载体",
  input_frames: "输入帧",
  capture_sessions: "采集会话",
  device_bindings: "设备绑定",
  media_uploads: "媒体上传",
  jobs: "后台任务",
};
const terminal = ["completed", "failed", "cancelled", "dead"];
function usePermissions() {
  const { project, user } = useWorkspace();
  return {
    write:
      can(user, "runs.configure") &&
      ["owner", "researcher"].includes(project?.role ?? ""),
    owner: can(user, "data.delete") && project?.role === "owner",
  };
}
function Tags({ tags }: { tags: string[] }) {
  return (
    <span className="library-tags">
      {tags.map((tag) => (
        <span key={tag}>{tag}</span>
      ))}
    </span>
  );
}
function useRefreshLibrary() {
  const client = useQueryClient();
  return () =>
    [
      "run",
      "runs",
      "model-library",
      "versions",
      "checkpoints",
      "lineage",
      "metadata-history",
      "cleanup-history",
    ].forEach((key) => client.invalidateQueries({ queryKey: [key] }));
}
export function ModelMetadataDialog({
  base,
  close,
}: {
  base: string;
  close: () => void;
}) {
  const data = useQuery<Run>({
    queryKey: ["metadata-draft", base],
    queryFn: () => api(base + "/metadata"),
    gcTime: 0,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  return (
    <Modal
      open
      onOpenChange={(open) => !open && close()}
      title={t("意识档案")}
      description={t("名称、标签和说明独立保存，不修改连接、参数或模拟时间。")}
    >
      <ErrorBox error={data.error} />
      {data.isPending && <Loading />}
      {data.data && (
        <ModelMetadataForm
          key={data.data.metadata_revision}
          base={base}
          run={data.data}
          close={close}
          reload={() => data.refetch()}
        />
      )}
    </Modal>
  );
}
function ModelMetadataForm({
  base,
  run,
  close,
  reload,
}: {
  base: string;
  run: Run;
  close: () => void;
  reload: () => void;
}) {
  const [name, setName] = useState(run.name),
    [description, setDescription] = useState(run.description),
    [tags, setTags] = useState(run.tags.join("，")),
    [archived, setArchived] = useState(!!run.archived_at);
  const refresh = useRefreshLibrary(),
    { write } = usePermissions();
  const save = useMutation({
    mutationFn: () =>
      api(base + "/metadata", {
        method: "PATCH",
        body: JSON.stringify({
          name,
          description,
          tags: tags
            .split(/[,，\n]/)
            .map((t) => t.trim())
            .filter(Boolean),
          archived,
          expected_metadata_revision: run.metadata_revision,
        }),
      }),
    onSuccess: () => {
      refresh();
      close();
    },
  });
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
      className="library-edit-form"
    >
      <Field label={t("意识名称")}>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={120}
          required
          readOnly={!write}
        />
      </Field>
      <Field label={t("档案说明")}>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={5}
          maxLength={20000}
          readOnly={!write}
        />
      </Field>
      <Field label={t("档案标签")}>
        <input
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder={t("用逗号分隔，最多 20 项")}
          readOnly={!write}
        />
      </Field>
      <label className="check">
        <input
          type="checkbox"
          checked={archived}
          onChange={(e) => setArchived(e.target.checked)}
          disabled={!write || !terminal.includes(run.status)}
        />
        {t("归档已结束的意识")}
      </label>
      <p className="footnote">
        {t("归档后默认列表隐藏，仍可查询、导出和创建分支。档案版本 m")}
        {run.metadata_revision}
        {t("；科学状态 r")}
        {run.revision}
        {t(" 保持独立。")}
      </p>
      <ErrorBox error={save.error} />
      <div className="form-actions">
        <Button type="button" onClick={reload}>
          {t("重新载入")}
        </Button>
        <Button variant="primary" disabled={!write || save.isPending}>
          {t("保存档案")}
        </Button>
      </div>
    </form>
  );
}

export default function ModelLibrary() {
  const { project } = useWorkspace(),
    { owner } = usePermissions();
  const root = projectPath(project!.id);
  const [showCleanupHistory, setShowCleanupHistory] = useState(false);
  const [q, setQ] = useState(""),
    [tag, setTag] = useState(""),
    [archived, setArchived] = useState("active"),
    [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0),
    [edit, setEdit] = useState(""),
    [cleanup, setCleanup] = useState<any>(null);
  const params = new URLSearchParams({
    q,
    tag,
    archived,
    status,
    offset: String(offset),
    limit: "24",
  });
  const data = useQuery({
    queryKey: ["model-library", project?.id, params.toString()],
    queryFn: () => api(root + "/model-library?" + params),
    gcTime: 0,
  });
  function filter(setter: (value: string) => void, value: string) {
    setter(value);
    setOffset(0);
  }
  return (
    <section className="panel model-library" aria-label={t("意识模型档案库")}>
      <div className="panel-heading">
        <div>
          <h2>{t("意识模型档案")}</h2>
          <p>{t("在数据库中整理当前模型、实验对象与已结束的意识。")}</p>
        </div>
        <Button onClick={() => data.refetch()}>
          <RefreshCw size={15} />
          {t("刷新")}
        </Button>
      </div>
      <div className="library-filters">
        <Field label={t("搜索意识档案")}>
          <input
            value={q}
            onChange={(e) => filter(setQ, e.target.value)}
            maxLength={160}
            placeholder={t("名称或说明")}
          />
        </Field>
        <Field label={t("筛选档案标签")}>
          <input
            value={tag}
            onChange={(e) => filter(setTag, e.target.value)}
            maxLength={48}
          />
        </Field>
        <Field label={t("归档范围")}>
          <select
            value={archived}
            onChange={(e) => filter(setArchived, e.target.value)}
          >
            <option value="active">{t("未归档")}</option>
            <option value="archived">{t("已归档")}</option>
            <option value="all">{t("全部档案")}</option>
          </select>
        </Field>
        <Field label={t("档案执行状态")}>
          <select
            value={status}
            onChange={(e) => filter(setStatus, e.target.value)}
          >
            <option value="">{t("全部状态")}</option>
            <option value="running">{t("运行中")}</option>
            <option value="paused">{t("已暂停")}</option>
            <option value="completed">{t("已完成")}</option>
            <option value="cancelled">{t("已终止")}</option>
            <option value="dead">{t("活动耗尽")}</option>
            <option value="failed">{t("失败")}</option>
            <option value="blocked">{t("等待处理")}</option>
            <option value="queued">{t("排队中")}</option>
          </select>
        </Field>
      </div>
      <ErrorBox error={data.error} />
      {data.isPending && <Loading />}
      <div className="library-grid">
        {data.data?.rows.map((row: any) => (
          <article key={row.id} className="library-card">
            <div className="library-card-heading">
              <Link to={`/runs/${row.id}`}>{row.name}</Link>
              <Badge status={row.status} />
            </div>
            {row.archived_at && (
              <span className="library-archive">
                <Archive size={13} />
                {t("已归档")}
              </span>
            )}
            <p>{row.description || t("尚未添加档案说明")}</p>
            <Tags tags={row.tags} />
            <dl>
              <div>
                <dt>{t("模拟时间")}</dt>
                <dd>{timeLabel(row.time_us)}</dd>
              </div>
              <div>
                <dt>{t("科学 / 档案版本")}</dt>
                <dd>
                  r{row.revision} / m{row.metadata_revision}
                </dd>
              </div>
            </dl>
            <div className="library-card-actions">
              <Button variant="small" onClick={() => setEdit(row.id)}>
                <FilePenLine size={14} />
                {t("编辑档案")}
              </Button>
              <Link
                className="button small"
                to={`/runs/${row.id}?view=checkpoints`}
              >
                {t("版本与谱系")}
              </Link>
              {row.archived_at && owner && (
                <Button variant="small" onClick={() => setCleanup(row)}>
                  <Trash2 size={14} />
                  {t("清理预览")}
                </Button>
              )}
            </div>
          </article>
        ))}
      </div>
      {data.data && !data.data.rows.length && (
        <Empty
          title={t("没有符合条件的意识档案")}
          detail={t("调整筛选，或创建／导入一个模型。")}
        />
      )}
      <div className="library-paging">
        <Button
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 24))}
        >
          {t("上一页档案")}
        </Button>
        <span>{t("第 {page} 页", { page: offset / 24 + 1 })}</span>
        <Button
          disabled={!data.data?.more}
          onClick={() => setOffset(offset + 24)}
        >
          {t("下一页档案")}
        </Button>
      </div>
      {edit && (
        <ModelMetadataDialog
          base={`${root}/runs/${edit}`}
          close={() => setEdit("")}
        />
      )}
      {cleanup && (
        <CleanupDialog
          base={`${root}/runs/${cleanup.id}`}
          close={() => setCleanup(null)}
        />
      )}
      {owner && (
        <div className="library-paging">
          <Button onClick={() => setShowCleanupHistory(!showCleanupHistory)}>
            {showCleanupHistory ? t("收起清理记录") : t("查看清理记录")}
          </Button>
        </div>
      )}
      {showCleanupHistory && <CleanupHistory root={root} />}
      <p className="footnote">
        <Link to="/docs?doc=docs/zh/v2-model-library.md">
          {t("档案、版本、谱系与清理规则")}
        </Link>
      </p>
    </section>
  );
}

function CleanupHistory({ root }: { root: string }) {
  const [offset, setOffset] = useState(0);
  const history = useQuery({
    queryKey: ["cleanup-history", root, offset],
    queryFn: () => api(root + `/cleanup-history?offset=${offset}`),
    gcTime: 0,
  });
  return (
    <div className="library-history" aria-label={t("档案清理记录")}>
      <h3>{t("档案清理记录")}</h3>
      <ErrorBox error={history.error} />
      {history.isPending && <Loading />}
      {history.data?.rows.map((row: any) => (
        <details key={row.id}>
          <summary>
            {row.summary.preview.name} ·{" "}
            {new Date(row.created_at).toLocaleString(locale())}
          </summary>
          <p>
            {t("删除的意识编号：")}
            {row.removed_run_id}
            {t(" · 操作者：")}
            {row.actor_id}
          </p>
          <pre>{JSON.stringify(row.summary, null, 2)}</pre>
        </details>
      ))}
      {history.data && !history.data.rows.length && (
        <p className="muted">{t("尚无清理记录。")}</p>
      )}
      <div className="library-paging">
        <Button
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 30))}
        >
          {t("较新清理记录")}
        </Button>
        <Button
          disabled={!history.data?.more}
          onClick={() => setOffset(offset + 30)}
        >
          {t("更早清理记录")}
        </Button>
      </div>
    </div>
  );
}

function CleanupDialog({ base, close }: { base: string; close: () => void }) {
  const plan = useQuery({
    queryKey: ["cleanup-preview", base],
    queryFn: () => api(base + "/cleanup-preview"),
    gcTime: 0,
    refetchOnWindowFocus: false,
  });
  const [confirmName, setConfirmName] = useState("");
  const refresh = useRefreshLibrary();
  const remove = useMutation({
    mutationFn: () =>
      post(base + "/cleanup", {
        token: plan.data.token,
        confirm_name: confirmName,
      }),
    onSuccess: () => {
      refresh();
      close();
    },
  });
  return (
    <Modal
      open
      onOpenChange={(open) => !open && close()}
      title={t("清理整份意识档案")}
      description={t(
        "永久删除这份档案的状态、科学记录及生成的导出文件；共享原件仍由引用保护。",
      )}
    >
      <ErrorBox error={plan.error ?? remove.error} />
      {plan.isPending && <Loading />}
      {plan.data && (
        <>
          <h3>{plan.data.name}</h3>
          <dl className="library-cleanup-counts">
            {Object.entries(plan.data.counts).map(([key, value]) => (
              <div key={key}>
                <dt>{t(countNames[key] ?? key)}</dt>
                <dd>{String(value)}</dd>
              </div>
            ))}
            <div>
              <dt>{t("生成文件")}</dt>
              <dd>
                {plan.data.artifacts.n}
                {t(" 件")}
              </dd>
            </div>
            <div>
              <dt>{t("恢复点 + 文件")}</dt>
              <dd>
                {(
                  (plan.data.checkpoint_bytes + plan.data.artifacts.bytes) /
                  1048576
                ).toFixed(2)}{" "}
                MiB
              </dd>
            </div>
            <div>
              <dt>{t("未共享原件")}</dt>
              <dd>
                {(plan.data.unshared_media.bytes / 1048576).toFixed(2)} MiB
              </dd>
            </div>
          </dl>
          {!plan.data.allowed && (
            <div className="notice">
              <strong>{t("当前不能清理")}</strong>
              <ul>
                {plan.data.reasons.map((reason: string) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </div>
          )}
          {plan.data.allowed && (
            <Field label={t("输入完整意识名称以确认清理")}>
              <input
                value={confirmName}
                onChange={(e) => setConfirmName(e.target.value)}
                autoComplete="off"
              />
            </Field>
          )}
          <p className="footnote">
            {t(
              "不会逐个删除仍被差量恢复依赖的锚点。保存时重新检查引用与预览版本，有变化则拒绝操作。清理回执保留在项目中。",
            )}
          </p>
          <div className="form-actions">
            <Button onClick={() => plan.refetch()}>{t("重新预览")}</Button>
            <Button
              variant="danger"
              disabled={
                !plan.data.allowed ||
                confirmName !== plan.data.name ||
                remove.isPending
              }
              onClick={() => remove.mutate()}
            >
              {t("确认清理整份档案")}
            </Button>
          </div>
        </>
      )}
    </Modal>
  );
}

export function VersionLibrary({
  base,
  run,
  onFork,
}: {
  base: string;
  run: Run;
  onFork: (id: string) => void;
}) {
  const [q, setQ] = useState(""),
    [tag, setTag] = useState(""),
    [pinned, setPinned] = useState(false),
    [pages, setPages] = useState<(number | null)[]>([null]),
    [edit, setEdit] = useState<any>(null);
  const [view, setView] = useState("versions");
  const query = new URLSearchParams({
    q,
    tag,
    pinned: String(pinned),
    limit: "24",
  });
  if (pages.at(-1) !== null) query.set("before", String(pages.at(-1)));
  const data = useQuery({
    queryKey: ["versions", run.id, run.revision, query.toString()],
    queryFn: () => api(base + "/versions?" + query),
    gcTime: 0,
    enabled: view === "versions",
  });
  function reset() {
    setPages([null]);
  }
  return (
    <section className="panel version-library" aria-label={t("恢复点与谱系")}>
      <div className="panel-heading">
        <div>
          <h2>{t("恢复点与谱系")}</h2>
          <p>{t("注释保存在独立档案版本；原始状态哈希和模拟时间保持不变。")}</p>
        </div>
        <a className="button" href={`/api/v2${base}/metadata-export`} download>
          {t("导出档案注释")}
        </a>
      </div>
      <nav className="tabs view-tabs" aria-label={t("版本档案工具")}>
        {[
          ["versions", "命名与保留"],
          ["lineage", "来源与后代"],
          ["history", "注释历史"],
        ].map(([key, label]) => (
          <button
            key={key}
            className={view === key ? "active" : ""}
            onClick={() => setView(key)}
          >
            {t(label)}
          </button>
        ))}
      </nav>
      {view === "versions" && (
        <>
          <div className="library-filters">
            <Field label={t("搜索恢复点注释")}>
              <input
                value={q}
                maxLength={160}
                onChange={(e) => {
                  setQ(e.target.value);
                  reset();
                }}
              />
            </Field>
            <Field label={t("恢复点标签")}>
              <input
                value={tag}
                maxLength={48}
                onChange={(e) => {
                  setTag(e.target.value);
                  reset();
                }}
              />
            </Field>
            <label className="check">
              <input
                type="checkbox"
                checked={pinned}
                onChange={(e) => {
                  setPinned(e.target.checked);
                  reset();
                }}
              />
              {t("只看已保留版本")}
            </label>
          </div>
          <ErrorBox error={data.error} />
          {data.isPending && <Loading />}
          <div className="library-version-list">
            {data.data?.rows.map((cp: any) => (
              <article key={cp.id}>
                <div>
                  <h3>
                    {cp.pinned && <Bookmark size={15} />}{" "}
                    {cp.label ||
                      t("未命名恢复点 r{value0}", {
                        value0: String(cp.revision),
                      })}
                  </h3>
                  <span className="mono">
                    r{cp.revision} · {timeLabel(cp.time_us)} ·{" "}
                    {cp.storage_format === "row-delta/1"
                      ? t("差量深度 {value0}", {
                          value0: String(cp.delta_depth),
                        })
                      : t("完整锚点")}
                  </span>
                </div>
                <p>{cp.notes}</p>
                <Tags tags={cp.tags} />
                <code className="library-hash">{cp.state_hash}</code>
                <div className="library-card-actions">
                  <Button variant="small" onClick={() => setEdit(cp)}>
                    {t("编辑版本注释")}
                  </Button>
                  <Button variant="small" onClick={() => onFork(cp.id)}>
                    {t("从此版本分叉")}
                  </Button>
                </div>
              </article>
            ))}
          </div>
          {data.data && !data.data.rows.length && (
            <Empty
              title={t("没有符合条件的恢复点")}
              detail={t("等待一次状态提交，或调整筛选。")}
            />
          )}
          <div className="library-paging">
            <Button
              disabled={pages.length === 1}
              onClick={() => setPages(pages.slice(0, -1))}
            >
              {t("较新版本")}
            </Button>
            <span>{t("第 {page} 页", { page: pages.length })}</span>
            <Button
              disabled={!data.data?.more}
              onClick={() => setPages([...pages, data.data.next])}
            >
              {t("更早版本")}
            </Button>
          </div>
        </>
      )}
      {view === "lineage" && <Lineage base={base} run={run} />}
      {view === "history" && <MetadataHistory base={base} run={run} />}
      {edit && (
        <Modal
          open
          onOpenChange={(open) => !open && setEdit(null)}
          title={t("恢复点 r{value0} 的注释", {
            value0: String(edit.revision),
          })}
          description={t(
            "保留标记会阻止整份档案清理，便于保护需要继续研究的恢复点。",
          )}
        >
          <VersionForm
            key={edit.id}
            base={base}
            cp={edit}
            close={() => setEdit(null)}
          />
        </Modal>
      )}
    </section>
  );
}
function VersionForm({
  base,
  cp,
  close,
}: {
  base: string;
  cp: any;
  close: () => void;
}) {
  const [label, setLabel] = useState(cp.label),
    [notes, setNotes] = useState(cp.notes),
    [tags, setTags] = useState<string>(cp.tags.join("，")),
    [pinned, setPinned] = useState(cp.pinned);
  const refresh = useRefreshLibrary(),
    { write } = usePermissions();
  const save = useMutation({
    mutationFn: () =>
      api(`${base}/versions/${cp.id}/metadata`, {
        method: "PATCH",
        body: JSON.stringify({
          label,
          notes,
          tags: tags
            .split(/[,，\n]/)
            .map((t) => t.trim())
            .filter(Boolean),
          pinned,
          expected_metadata_revision: cp.metadata_revision,
        }),
      }),
    onSuccess: () => {
      refresh();
      close();
    },
  });
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
      className="library-edit-form"
    >
      <Field label={t("恢复点名称")}>
        <input
          value={t(label)}
          onChange={(e) => setLabel(e.target.value)}
          maxLength={120}
          readOnly={!write}
        />
      </Field>
      <Field label={t("版本笔记")}>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={6}
          maxLength={20000}
          readOnly={!write}
        />
      </Field>
      <Field label={t("版本标签")}>
        <input
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder={t("逗号分隔")}
          readOnly={!write}
        />
      </Field>
      <label className="check">
        <input
          type="checkbox"
          checked={pinned}
          onChange={(e) => setPinned(e.target.checked)}
          disabled={!write}
        />
        {t("保留此版本，阻止档案清理")}
      </label>
      <ErrorBox error={save.error} />
      <div className="form-actions">
        <Button variant="primary" disabled={!write || save.isPending}>
          {t("保存版本注释")}
        </Button>
      </div>
    </form>
  );
}
function Lineage({ base, run }: { base: string; run: Run }) {
  const [offset, setOffset] = useState(0);
  const data = useQuery({
    queryKey: ["lineage", run.id, offset],
    queryFn: () => api(base + `/lineage?offset=${offset}`),
    gcTime: 0,
  });
  return (
    <div className="library-lineage">
      <ErrorBox error={data.error} />
      {data.isPending && <Loading />}
      <h3>{t("当前意识与来源链")}</h3>
      {data.data?.ancestors.map((row: any) => (
        <article key={row.id}>
          <GitFork size={17} />
          <div>
            <Link to={`/runs/${row.id}?view=checkpoints`}>{row.name}</Link>
            <p>
              {t(kinds[row.origin_kind] ?? "早期记录：来源类型未登记")}
              {row.origin_revision
                ? t(" · 来源 r{value0}{value1}", {
                    value0: String(row.origin_revision),
                    value1: String(
                      row.origin_label ? `「${row.origin_label}」` : "",
                    ),
                  })
                : ""}
            </p>
            {row.origin_hash && (
              <code className="library-hash">
                {t("来源哈希 ")}
                {row.origin_hash}
              </code>
            )}
            {row.parent_id && !row.origin_checkpoint_id && (
              <small>
                {t("仅记录父意识和来源哈希，不能唯一推定某个历史版本。")}
              </small>
            )}
          </div>
          <Badge status={row.status} />
        </article>
      ))}
      {data.data?.ancestors_truncated && (
        <p>{t("此处展示 64 层祖先；进入最早一项可继续查看。")}</p>
      )}
      <h3>{t("直接后代")}</h3>
      {data.data?.children.map((row: any) => (
        <article key={row.id}>
          <GitFork size={17} />
          <Link to={`/runs/${row.id}?view=checkpoints`}>{row.name}</Link>
          <span>{t(kinds[row.origin_kind] ?? "类型未登记")}</span>
          <Badge status={row.status} />
        </article>
      ))}
      {data.data && !data.data.children.length && (
        <p className="muted">{t("没有直接后代。")}</p>
      )}
      <div className="library-paging">
        <Button
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 30))}
        >
          {t("上一页后代")}
        </Button>
        <Button
          disabled={!data.data?.more}
          onClick={() => setOffset(offset + 30)}
        >
          {t("下一页后代")}
        </Button>
      </div>
    </div>
  );
}
function MetadataHistory({ base, run }: { base: string; run: Run }) {
  const [pages, setPages] = useState<(number | null)[]>([null]);
  const data = useQuery({
    queryKey: ["metadata-history", run.id, pages.at(-1)],
    queryFn: () =>
      api(
        base +
          "/metadata-history" +
          (pages.at(-1) ? `?before=${pages.at(-1)}` : ""),
      ),
    gcTime: 0,
  });
  return (
    <div className="library-history">
      <ErrorBox error={data.error} />
      {data.isPending && <Loading />}
      {data.data?.rows.map((row: any) => (
        <details key={row.id}>
          <summary>
            {row.checkpoint_id ? t("恢复点注释") : t("意识档案")} · m
            {row.metadata_revision} ·{" "}
            {new Date(row.created_at).toLocaleString(locale())}
          </summary>
          <small>
            {t("操作者 ")}
            {row.actor_id}
          </small>
          <pre>
            {JSON.stringify(
              { 修改前: row.before_value, 修改后: row.after_value },
              null,
              2,
            )}
          </pre>
        </details>
      ))}
      {data.data && !data.data.rows.length && (
        <p className="muted">{t("尚无档案编辑记录。")}</p>
      )}
      <div className="library-paging">
        <Button
          disabled={pages.length === 1}
          onClick={() => setPages(pages.slice(0, -1))}
        >
          {t("较新注释")}
        </Button>
        <Button
          disabled={!data.data?.more}
          onClick={() => setPages([...pages, data.data.next])}
        >
          {t("更早注释")}
        </Button>
      </div>
    </div>
  );
}
