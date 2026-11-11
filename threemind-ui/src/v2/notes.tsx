import { can } from "./access";
import { useEffect, useState, useSyncExternalStore } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import {
  Archive,
  Book,
  FilePenLine,
  Grid2X2,
  List,
  Plus,
  Save,
  History,
  FolderPlus,
  ArrowLeft,
} from "lucide-react";
import { api, post, ApiError } from "./api";
import { t, useLocale } from "./i18n";
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
import {
  NoteSession,
  noteDraft,
  setNoteIdentity,
  type NoteRow,
} from "./noteStore";
import NoteEditor from "./NoteEditor";
import "./notes.css";

type Collection = {
  id: string;
  name: string;
  color: string;
  kind: "notebook" | "category";
  revision: number;
  is_default: boolean;
  auto_named: boolean;
  notes: number;
  archived_at: string | null;
};
const nameOf = (collection: Collection) =>
  collection.auto_named ? t("默认笔记本") : collection.name;
const date = (value: string) => new Date(value).toLocaleString();
export default function Notes() {
  const { project, user } = useWorkspace();
  return project && user ? (
    <PersonalNotes
      key={`${user.id}:${project.id}`}
      project={project.id}
      user={user.id}
      write={project.role !== "viewer" && can(user,"notes.write")}
    />
  ) : null;
}
function PersonalNotes({
  project,
  user,
  write,
}: {
  project: string;
  user: string;
  write: boolean;
}) {
  useLocale();
  const client = useQueryClient(),
    base = `/projects/${project}`;
  const [params, setParams] = useSearchParams();
  const tab = ["write", "drafts", "notebooks"].includes(params.get("tab") || "")
    ? params.get("tab")!
    : "write";
  const [session] = useState(() => {
    setNoteIdentity(user);
    return new NoteSession(project, user, () =>
      client.invalidateQueries({ queryKey: ["notes", project, user] }),
    );
  });
  const state = useSyncExternalStore(session.subscribe, session.snapshot);
  const [recovery, setRecovery] = useState(() => session.recovery());
  const [query, setQuery] = useState(""),
    [sort, setSort] = useState("updated"),
    [filter, setFilter] = useState(""),
    [book, setBook] = useState<string | null>(null);
  const [offset, setOffset] = useState(0),
    [archived, setArchived] = useState(false),
    [gridDrafts, setGridDrafts] = useState(false),
    [gridBooks, setGridBooks] = useState(true);
  const [error, setError] = useState<unknown>(null),
    [loading, setLoading] = useState(false),
    [history, setHistory] = useState(false),
    [versionBefore, setVersionBefore] = useState<number | undefined>();
  const [preview, setPreview] = useState<NoteRow | null>(null);
  const [assetsOpen, setAssetsOpen] = useState(false),
    [assetsOffset, setAssetsOffset] = useState(0);
  const assets = useQuery<{ rows: any[]; more: boolean }>({
    queryKey: ["notes", project, user, "assets", assetsOffset],
    queryFn: () => api(`${base}/note-assets?offset=${assetsOffset}`),
    enabled: assetsOpen,
  });
  const [collectionEdit, setCollectionEdit] =
      useState<Partial<Collection> | null>(null),
    [collectionName, setCollectionName] = useState(""),
    [collectionColor, setCollectionColor] = useState("#237969"),
    [collectionSaving, setCollectionSaving] = useState(false);
  const collections = useQuery<Collection[]>({
    queryKey: ["notes", project, user, "collections", archived],
    queryFn: () => api(`${base}/note-collections?archived=${archived}`),
  });
  const activeCollections = useQuery<Collection[]>({
    queryKey: ["notes", project, user, "collections", false],
    queryFn: () => api(`${base}/note-collections`),
  });
  const all = activeCollections.data ?? [];
  useEffect(() => {
    if (write && !params.get("note"))
      post(`${base}/note-collections/default`, {})
        .then(() =>
          client.invalidateQueries({
            queryKey: ["notes", project, user, "collections"],
          }),
        )
        .catch(setError);
  }, [base, write, client, project, user]);
  useEffect(() => {
    if (state.dirty && !state.saving && !state.error && !recovery && write) {
      const timer = setTimeout(() => void session.flush(), 1200);
      return () => clearTimeout(timer);
    }
  }, [
    state.draft,
    state.dirty,
    state.saving,
    state.error,
    recovery,
    write,
    session,
  ]);
  useEffect(() => {
    const leave = (e: BeforeUnloadEvent) => {
      session.persist();
      if (session.snapshot().dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    const online = () => {
      const error = session.snapshot().error;
      if (
        error &&
        !(
          error instanceof ApiError &&
          [403, 404, 409, 422].includes(error.status)
        )
      )
        void session.flush();
    };
    window.addEventListener("beforeunload", leave);
    window.addEventListener("online", online);
    return () => {
      session.persist();
      window.removeEventListener("beforeunload", leave);
      window.removeEventListener("online", online);
    };
  }, [session]);
  useEffect(() => {
    setOffset(0);
  }, [tab, book, filter, query, sort, archived]);
  const showTab = (next: string) =>
    setParams({
      tab: next,
      ...(next === "write" && session.snapshot().revision > 0
        ? { note: session.snapshot().id }
        : {}),
    });
  const rows = useQuery<{ rows: any[]; more: boolean }>({
    queryKey: [
      "notes",
      project,
      user,
      "list",
      tab,
      book,
      filter,
      query,
      sort,
      archived,
      offset,
    ],
    queryFn: () =>
      api(
        `${base}/notes?${new URLSearchParams({ kind: tab === "drafts" ? "draft" : "note", query, sort, archived: String(archived), offset: String(offset), ...(tab === "drafts" ? (filter === "none" ? { uncategorized: "true" } : filter ? { collection: filter } : {}) : book && book !== "all" ? { collection: book } : {}) })}`,
      ),
    enabled: tab === "drafts" || (tab === "notebooks" && !!book),
  });
  const historyRows = useQuery<{
    rows: any[];
    more: boolean;
    next: number | null;
  }>({
    queryKey: [
      "notes",
      project,
      user,
      "history",
      state.id,
      state.revision,
      versionBefore,
    ],
    queryFn: () =>
      api(
        `${base}/notes/${state.id}/versions${versionBefore ? `?before=${versionBefore}` : ""}`,
      ),
    enabled: history && state.revision > 0,
  });
  const load = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      if (state.dirty && !(await session.flush())) return;
      const row = await api<NoteRow>(`${base}/notes/${id}`);
      if (row.archived_at) {
        setPreview(row);
        return;
      }
      session.replace(row);
      setRecovery(null);
      showTab("write");
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  };
  const linkedNote = params.get("note");
  useEffect(() => {
    if (linkedNote && (state.id !== linkedNote || !state.revision))
      void load(linkedNote);
  }, [linkedNote]);
  const fresh = async () => {
    if (state.dirty && !(await session.flush())) return;
    session.replace(null);
    setRecovery(null);
    showTab("write");
  };
  const editCollection = (value: Partial<Collection>) => {
    setCollectionEdit({ ...value, id: value.id ?? crypto.randomUUID() });
    setCollectionName(value.name ?? "");
    setCollectionColor(value.color ?? "#237969");
    setError(null);
  };
  const saveCollection = async () => {
    if (!collectionEdit) return;
    setCollectionSaving(true);
    setError(null);
    try {
      const result = await api<Collection>(
        `${base}/note-collections/${collectionEdit.id}`,
        {
          method: "PUT",
          body: JSON.stringify({
            name: collectionName,
            kind: collectionEdit.kind,
            color: collectionColor,
            expected_revision: collectionEdit.revision ?? 0,
          }),
        },
      );
      await client.invalidateQueries({
        queryKey: ["notes", project, user, "collections"],
      });
      if (!collectionEdit.revision && tab === "write")
        session.edit({
          kind: result.kind === "notebook" ? "note" : "draft",
          collection_id: result.id,
        });
      setCollectionEdit(null);
    } catch (e) {
      setError(e);
    } finally {
      setCollectionSaving(false);
    }
  };
  const archiveCollection = async (value: Collection) => {
    try {
      setError(null);
      await post(`${base}/note-collections/${value.id}/archive`, {
        expected_revision: value.revision,
        archived: !archived,
        operation_id: crypto.randomUUID(),
      });
      await client.invalidateQueries({ queryKey: ["notes", project, user] });
    } catch (e) {
      setError(e);
    }
  };
  const archiveNote = async (row: any) => {
    try {
      setError(null);
      await post(`${base}/notes/${row.id}/archive`, {
        expected_revision: row.revision,
        archived: !archived,
        operation_id: crypto.randomUUID(),
      });
      if (row.id === state.id && !archived) session.replace(null);
      await client.invalidateQueries({ queryKey: ["notes", project, user] });
    } catch (e) {
      setError(e);
    }
  };
  const selectedBook = (collections.data ?? []).find((c) => c.id === book);
  const options = all.filter(
    (c) => c.kind === (state.draft.kind === "note" ? "notebook" : "category"),
  );
  const books = (collections.data ?? []).filter((c) => c.kind === "notebook");
  const conflict =
    state.error instanceof ApiError && state.error.status === 409;
  const status = state.saving
    ? t("正在保存…")
    : state.error
      ? t("保存未完成")
      : state.dirty
        ? t("等待保存")
        : state.revision
          ? t("已保存 · 修订 {revision}", { revision: state.revision })
          : t("开始写作后自动保存");
  const layout = tab === "drafts" ? gridDrafts : gridBooks;
  return (
    <div className="notes-page">
      <PageTitle
        eyebrow="RESEARCH NOTEBOOKS"
        title={t("实验笔记")}
        description={t(
          "记录假说、实验过程与思考。正文和修订保存在当前部署的数据库中，仅自己可见。",
        )}
        actions={
          <Button
            variant="primary"
            disabled={!write || loading || !!recovery}
            onClick={fresh}
          >
            <Plus size={16} />
            {t("新建笔记")}
          </Button>
        }
      />
      <p className="record-scope">
        {t("此工作区显示所属项目中本人可见的笔记。")}{" "}
        <a href="/research-records">{t("查看全部实验")}</a>
      </p>
      <div className="tabs" role="tablist" aria-label={t("实验笔记页面")}>
        <button
          role="tab"
          aria-selected={tab === "write"}
          className={tab === "write" ? "active" : ""}
          onClick={() => showTab("write")}
        >
          <FilePenLine size={16} />
          {t("写作")}
        </button>
        <button
          role="tab"
          aria-selected={tab === "drafts"}
          className={tab === "drafts" ? "active" : ""}
          onClick={() => showTab("drafts")}
        >
          {t("草稿")}
        </button>
        <button
          role="tab"
          aria-selected={tab === "notebooks"}
          className={tab === "notebooks" ? "active" : ""}
          onClick={() => showTab("notebooks")}
        >
          <Book size={16} />
          {t("笔记本")}
        </button>
      </div>
      <ErrorBox error={error || collections.error} />
      {loading && <Loading />}
      {recovery && (
        <div className="note-recovery" role="status">
          <div>
            <strong>{t("发现尚未确认保存的写作内容")}</strong>
            <p>
              {recovery.draft.title} ·{" "}
              {t("恢复后会核对数据库修订，避免覆盖较新的内容。")}
            </p>
          </div>
          <Button
            onClick={() => {
              session.recover(recovery);
              setRecovery(null);
              showTab("write");
            }}
          >
            {t("恢复写作")}
          </Button>
          <Button
            onClick={() => {
              session.discardRecovery();
              setRecovery(null);
            }}
          >
            {t("放弃恢复草稿")}
          </Button>
        </div>
      )}
      {tab === "write" && (
        <div
          className="note-writing"
          onKeyDown={(e) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
              e.preventDefault();
              if (write && !recovery) void session.flush();
            }
          }}
        >
          <div className="note-writing-header">
            <Field label={t("笔记标题")}>
              <input
                className="note-title-input"
                value={state.draft.title}
                maxLength={200}
                readOnly={!write || !!recovery}
                onChange={(e) => session.edit({ title: e.target.value })}
              />
            </Field>
            <div className="note-save-actions">
              <span
                role="status"
                className={`note-save-status ${state.error ? "failed" : ""}`}
              >
                {status}
              </span>
              <Button
                disabled={!write || state.saving || !!recovery}
                onClick={() => void session.flush()}
              >
                <Save size={16} />
                {t("保存")}
              </Button>
              <Button
                disabled={!state.revision}
                onClick={() => {
                  setHistory(true);
                  setVersionBefore(undefined);
                }}
              >
                <History size={16} />
                {t("修订记录")}
              </Button>
            </div>
          </div>
          <div className="note-metadata">
            <Field label={t("内容类型")}>
              <select
                disabled={!write || !!recovery}
                value={state.draft.kind}
                onChange={(e) =>
                  session.edit({
                    kind: e.target.value as "note" | "draft",
                    collection_id:
                      e.target.value === "note"
                        ? (all.find((c) => c.is_default)?.id ?? null)
                        : null,
                  })
                }
              >
                <option value="draft">{t("草稿")}</option>
                <option value="note">{t("笔记")}</option>
              </select>
            </Field>
            <Field
              label={
                state.draft.kind === "note" ? t("保存到笔记本") : t("草稿分类")
              }
            >
              <select
                disabled={!write || !!recovery}
                value={state.draft.collection_id ?? ""}
                onChange={(e) =>
                  session.edit({ collection_id: e.target.value || null })
                }
              >
                <option value="">
                  {state.draft.kind === "note" ? t("默认笔记本") : t("无分类")}
                </option>
                {options.map((c) => (
                  <option key={c.id} value={c.id}>
                    {nameOf(c)}
                  </option>
                ))}
              </select>
            </Field>
            <Button
              disabled={!write || !!recovery}
              onClick={() =>
                editCollection({
                  kind: state.draft.kind === "note" ? "notebook" : "category",
                })
              }
            >
              <FolderPlus size={16} />
              {state.draft.kind === "note" ? t("新建笔记本") : t("新建分类")}
            </Button>
          </div>
          <ErrorBox error={state.error} />
          {!!state.error && (
            <div className="note-conflict">
              <span>
                {conflict
                  ? t(
                      "数据库已有更新，本地内容已保留。可以另存副本，或载入最新修订后重新整理。",
                    )
                  : t("尚未确认写入数据库，可修正内容或重试保存。")}
              </span>
              <Button
                disabled={state.saving || !write}
                onClick={() => void session.flush()}
              >
                {t("重试保存")}
              </Button>
              {conflict && (
                <>
                  <Button onClick={() => session.copy()}>
                    {t("另存副本")}
                  </Button>
                  <Button
                    onClick={async () => {
                      if (
                        !window.confirm(
                          t("载入数据库中的最新修订，并放弃当前未保存的修改？"),
                        )
                      )
                        return;
                      try {
                        const row = await api<NoteRow>(
                          `${base}/notes/${state.id}`,
                        );
                        session.replace(row);
                      } catch (e) {
                        setError(e);
                      }
                    }}
                  >
                    {t("载入最新修订")}
                  </Button>
                </>
              )}
            </div>
          )}
          {state.cacheError && (
            <p role="alert">
              {t("浏览器未能保留恢复草稿，请在离开前确认保存成功。")}
            </p>
          )}
          <NoteEditor
            key={state.id}
            value={state.draft.body}
            onChange={(body) => session.edit({ body })}
            project={project}
            readOnly={!write || !!recovery}
            beforeSwitch={session.flush}
          />
          <div className="note-writing-footer">
            <span>{t("自动保存到数据库 · Ctrl / ⌘ + S 手动保存")}</span>
            <Button
              onClick={() => {
                setAssetsOpen(true);
                void assets.refetch();
              }}
            >
              {t("图片附件")}
            </Button>
            <span>{t("修订历史保留原稿；个人笔记不作为原始测量数据。")}</span>
          </div>
        </div>
      )}
      {tab !== "write" && (
        <>
          <div className="note-library-tools">
            {book && tab === "notebooks" && (
              <Button onClick={() => setBook(null)}>
                <ArrowLeft size={16} />
                {t("全部笔记本")}
              </Button>
            )}
            {(tab === "drafts" || book) && (
              <>
                <input
                  type="search"
                  aria-label={t("搜索笔记")}
                  placeholder={t("搜索标题或正文")}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <select
                  aria-label={t("笔记排序")}
                  value={sort}
                  onChange={(e) => setSort(e.target.value)}
                >
                  <option value="updated">{t("最近修改")}</option>
                  <option value="created">{t("最近创建")}</option>
                  <option value="title">{t("标题排序")}</option>
                </select>
              </>
            )}
            {tab === "drafts" && (
              <>
                <select
                  aria-label={t("筛选草稿分类")}
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                >
                  <option value="">{t("全部分类")}</option>
                  <option value="none">{t("无分类")}</option>
                  {(collections.data ?? [])
                    .filter((c) => c.kind === "category")
                    .map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                </select>
                <Button
                  disabled={!write}
                  onClick={() => editCollection({ kind: "category" })}
                >
                  {t("新建分类")}
                </Button>
              </>
            )}
            {tab === "notebooks" && archived && (
              <Button onClick={() => setBook("all")}>
                {t("全部已归档笔记")}
              </Button>
            )}
            {tab === "notebooks" && !book && (
              <Button
                disabled={!write}
                onClick={() => editCollection({ kind: "notebook" })}
              >
                <Plus size={16} />
                {t("新建笔记本")}
              </Button>
            )}
            <label className="check-row">
              <input
                type="checkbox"
                checked={archived}
                onChange={(e) => {
                  setArchived(e.target.checked);
                  setBook(null);
                  setFilter("");
                }}
              />
              {t("查看已归档")}
            </label>
            <div
              className="note-view-toggle"
              role="group"
              aria-label={t("展示形式")}
            >
              <Button
                aria-pressed={!layout}
                aria-label={t("列表视图")}
                onClick={() =>
                  tab === "drafts" ? setGridDrafts(false) : setGridBooks(false)
                }
              >
                <List size={17} />
              </Button>
              <Button
                aria-pressed={layout}
                aria-label={t("卡片视图")}
                onClick={() =>
                  tab === "drafts" ? setGridDrafts(true) : setGridBooks(true)
                }
              >
                <Grid2X2 size={17} />
              </Button>
            </div>
          </div>
          {tab === "drafts" &&
            (collections.data ?? []).some((c) => c.kind === "category") && (
              <details className="note-category-management">
                <summary>{t("管理草稿分类")}</summary>
                <div>
                  {(collections.data ?? [])
                    .filter((c) => c.kind === "category")
                    .map((c) => (
                      <span key={c.id}>
                        {c.name}
                        <Button
                          disabled={!write || !!c.archived_at}
                          onClick={() => editCollection(c)}
                        >
                          {t("重命名")}
                        </Button>
                        <Button
                          disabled={!write || (!archived && c.notes > 0)}
                          onClick={() => archiveCollection(c)}
                        >
                          {archived ? t("恢复") : t("归档")}
                        </Button>
                      </span>
                    ))}
                </div>
              </details>
            )}
          {tab === "notebooks" && !book ? (
            <>
              {collections.isPending ? (
                <Loading />
              ) : books.length ? (
                <div className={gridBooks ? "notebook-shelf" : "notebook-list"}>
                  {books.map((c) => (
                    <article key={c.id} className="notebook-card">
                      <button
                        className="notebook-open"
                        onClick={() => setBook(c.id)}
                      >
                        <div
                          className="notebook-cover"
                          style={
                            { "--book-color": c.color } as React.CSSProperties
                          }
                        >
                          <span className="notebook-spine" />
                          <Book size={32} />
                          <span className="notebook-cover-label">
                            {t("研究笔记")}
                          </span>
                        </div>
                        <div className="notebook-caption">
                          <h3>{nameOf(c)}</h3>
                          <p>{t("{count} 篇笔记", { count: c.notes })}</p>
                        </div>
                      </button>
                      <div className="notebook-card-actions">
                        <Button
                          disabled={!write || !!c.archived_at}
                          onClick={() => editCollection(c)}
                        >
                          {t("编辑")}
                        </Button>
                        {!c.is_default && (
                          <Button
                            disabled={!write || (!archived && c.notes > 0)}
                            title={
                              !archived && c.notes
                                ? t("先移动或归档其中的笔记")
                                : undefined
                            }
                            onClick={() => archiveCollection(c)}
                          >
                            {archived ? t("恢复") : t("归档")}
                          </Button>
                        )}
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <Empty
                  title={t("这里还没有笔记本")}
                  detail={t("创建笔记本，按研究主题整理笔记。")}
                />
              )}
            </>
          ) : (
            <>
              {selectedBook && (
                <h2 className="note-book-heading">{nameOf(selectedBook)}</h2>
              )}
              <ErrorBox error={rows.error} />
              {rows.isPending ? (
                <Loading />
              ) : !rows.data?.rows.length ? (
                <Empty
                  title={t("没有符合条件的笔记")}
                  detail={t("在写作页开始记录，或调整当前筛选条件。")}
                />
              ) : (
                <div className={layout ? "note-card-grid" : "note-list"}>
                  {rows.data.rows.map((row) => (
                    <article key={row.id} className="note-item">
                      <button
                        className="note-item-open"
                        onClick={() => load(row.id)}
                      >
                        <FilePenLine size={20} />
                        <div>
                          <h3>{row.title}</h3>
                          <p>{row.excerpt}</p>
                          <span>
                            {date(row.updated_at)} ·{" "}
                            {row.collection_name
                              ? row.auto_named
                                ? t("默认笔记本")
                                : row.collection_name
                              : t("无分类")}
                          </span>
                        </div>
                      </button>
                      <Button
                        disabled={
                          !write ||
                          loading ||
                          (state.id === row.id && state.dirty)
                        }
                        onClick={() => archiveNote(row)}
                      >
                        <Archive size={15} />
                        {archived ? t("恢复") : t("归档")}
                      </Button>
                    </article>
                  ))}
                </div>
              )}
              {(offset > 0 || rows.data?.more) && (
                <div className="note-pagination">
                  <Button
                    disabled={!offset}
                    onClick={() => setOffset(Math.max(0, offset - 50))}
                  >
                    {t("上一页")}
                  </Button>
                  <span>{t("第 {page} 页", { page: offset / 50 + 1 })}</span>
                  <Button
                    disabled={!rows.data?.more}
                    onClick={() => setOffset(offset + 50)}
                  >
                    {t("下一页")}
                  </Button>
                </div>
              )}
            </>
          )}
        </>
      )}
      <Modal
        wide
        open={assetsOpen}
        onOpenChange={setAssetsOpen}
        title={t("图片附件")}
        description={t(
          "PNG、JPEG、WebP，单张上限 8 MiB；当前项目每人上限 1 GiB。历史修订引用的图片会保留。",
        )}
      >
        <ErrorBox error={assets.error || error} />
        {assets.isPending ? (
          <Loading />
        ) : !assets.data?.rows.length ? (
          <p>{t("还没有上传图片。")}</p>
        ) : (
          <div className="note-assets">
            {assets.data.rows.map((row) => (
              <article key={row.id}>
                <img
                  src={`/api/v2${base}/note-assets/${row.id}`}
                  alt={row.name}
                  loading="lazy"
                />
                <div>
                  <strong>{row.name}</strong>
                  <p>
                    {(row.bytes / 1024).toFixed(1)} KiB ·{" "}
                    {row.referenced ? t("修订正在引用") : t("尚未引用")}
                  </p>
                </div>
                <Button
                  disabled={!write || row.referenced}
                  onClick={async () => {
                    try {
                      await api(`${base}/note-assets/${row.id}`, {
                        method: "DELETE",
                      });
                      void assets.refetch();
                    } catch (e) {
                      setError(e);
                    }
                  }}
                >
                  {t("删除未引用图片")}
                </Button>
              </article>
            ))}
          </div>
        )}
        <div className="modal-actions">
          <Button
            disabled={!assetsOffset}
            onClick={() => setAssetsOffset(Math.max(0, assetsOffset - 50))}
          >
            {t("上一页")}
          </Button>
          <Button
            disabled={!assets.data?.more}
            onClick={() => setAssetsOffset(assetsOffset + 50)}
          >
            {t("下一页")}
          </Button>
        </div>
      </Modal>
      <Modal
        open={!!collectionEdit}
        onOpenChange={(open) => {
          if (!open && !collectionSaving) setCollectionEdit(null);
        }}
        title={
          collectionEdit?.kind === "category" ? t("草稿分类") : t("笔记本")
        }
        description={t("按研究主题整理，名称与封面颜色可以稍后修改。")}
      >
        <Field label={t("名称")}>
          <input
            value={collectionName}
            maxLength={100}
            onChange={(e) => setCollectionName(e.target.value)}
          />
        </Field>
        <Field label={t("封面颜色")}>
          <input
            type="color"
            value={collectionColor}
            onChange={(e) => setCollectionColor(e.target.value)}
          />
        </Field>
        <ErrorBox error={error} />
        <div className="modal-actions">
          <Button
            disabled={collectionSaving}
            onClick={() => setCollectionEdit(null)}
          >
            {t("取消")}
          </Button>
          <Button
            variant="primary"
            disabled={collectionSaving || !collectionName.trim()}
            onClick={saveCollection}
          >
            {t("保存")}
          </Button>
        </div>
      </Modal>
      <Modal
        wide
        open={history}
        onOpenChange={setHistory}
        title={t("修订记录")}
        description={t(
          "每次成功保存都保留原稿。恢复旧稿会产生新修订，不会覆盖历史。",
        )}
      >
        <ErrorBox error={historyRows.error} />
        {historyRows.isPending ? (
          <Loading />
        ) : (
          <div className="note-history">
            {historyRows.data?.rows.map((row) => (
              <button
                key={row.revision}
                onClick={async () => {
                  try {
                    setPreview(
                      await api(
                        `${base}/notes/${state.id}?revision=${row.revision}`,
                      ),
                    );
                    setHistory(false);
                  } catch (e) {
                    setError(e);
                  }
                }}
              >
                <strong>
                  {t("修订 {revision}", { revision: row.revision })} ·{" "}
                  {row.metadata.title}
                </strong>
                <span>{date(row.created_at)}</span>
                <code>{row.content_hash.slice(0, 16)}</code>
              </button>
            ))}
          </div>
        )}
        <div className="modal-actions">
          {versionBefore && (
            <Button onClick={() => setVersionBefore(undefined)}>
              {t("最新修订")}
            </Button>
          )}
          {historyRows.data?.next && (
            <Button
              onClick={() =>
                setVersionBefore(historyRows.data?.next ?? undefined)
              }
            >
              {t("更早修订")}
            </Button>
          )}
        </div>
      </Modal>
      <Modal
        wide
        open={!!preview}
        onOpenChange={(open) => {
          if (!open) setPreview(null);
        }}
        title={preview?.version_metadata.title ?? t("笔记预览")}
        description={t("历史正文为只读；载入写作区后保存为新修订。")}
      >
        {preview && (
          <NoteEditor
            key={`${preview.id}:${preview.content_hash}`}
            project={project}
            value={preview.body}
            onChange={() => {}}
            readOnly
          />
        )}
        <div className="modal-actions">
          <Button onClick={() => setPreview(null)}>{t("关闭")}</Button>
          <Button
            disabled={!write || !!preview?.archived_at || state.saving}
            variant="primary"
            onClick={async () => {
              if (!preview) return;
              if (state.dirty && !(await session.flush())) return;
              try {
                const current = await api<NoteRow>(
                  `${base}/notes/${preview.id}`,
                );
                session.replace(current);
                session.edit({
                  ...noteDraft({ ...preview, ...preview.version_metadata }),
                  body: preview.body,
                });
                setPreview(null);
                showTab("write");
              } catch (e) {
                setError(e);
              }
            }}
          >
            {t("载入此修订")}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
