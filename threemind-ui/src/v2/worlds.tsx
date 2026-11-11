import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import { Plus, Sparkles } from "lucide-react";
import { api, post } from "./api";
import { t } from "./i18n";
import { can } from "./access";
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
import { WorldEditor, type WorldEditorHandle } from "./WorldEditor";
import { NewRun } from "./research";
import { AICallDetail, AICallHistory } from "./aiProviders";
const WorldAI = lazy(() => import("./WorldAI"));
const Robots = lazy(() => import("./Robots"));

export default function Worlds() {
  const [search, setSearch] = useSearchParams();
  const robots = search.get("view") === "robots";
  return (
    <>
      <div className="tabs" role="tablist" aria-label={t("世界与躯体分区")}>
        {[
          ["worlds", "世界库"],
          ["robots", "机器人任务"],
        ].map(([key, name]) => (
          <button
            key={key}
            role="tab"
            aria-selected={robots === (key === "robots")}
            className={robots === (key === "robots") ? "active" : ""}
            onClick={() =>
              setSearch(key === "robots" ? { view: "robots" } : {})
            }
          >
            {t(name)}
          </button>
        ))}
      </div>
      {robots ? (
        <Suspense fallback={<Loading />}>
          <Robots />
        </Suspense>
      ) : (
        <WorldLibrary />
      )}
    </>
  );
}

function WorldLibrary() {
  const { project, user } = useWorkspace(),
    client = useQueryClient();
  const [search, setSearch] = useSearchParams();
  const [proposal, setProposal] = useState<any>(null),
    [aiHistory, setAIHistory] = useState(false),
    [callDetail, setCallDetail] = useState<string>();
  const [q, setQ] = useState(""),
    [offset, setOffset] = useState(0),
    [archived, setArchived] = useState(false),
    [identity, setIdentity] = useState(search.get("world") || "");
  const [revision, setRevision] = useState<number | null>(null),
    [before, setBefore] = useState<number | null>(null);
  const [editing, setEditing] = useState<any>(null),
    [running, setRunning] = useState<any>(null),
    [error, setError] = useState<unknown>(null),
    [busy, setBusy] = useState(false);
  const nonce = useRef(crypto.randomUUID()),
    editor = useRef<WorldEditorHandle>(null);
  useEffect(() => {
    setIdentity(search.get("world") || "");
    setEditing(null);
    setRunning(null);
    setRevision(null);
    setOffset(0);
    setProposal(null);
    setAIHistory(false);
    setCallDetail(undefined);
  }, [project?.id]);
  useEffect(() => {
    const call = search.get("proposal");
    if (call && project) {
      setProposal({ call, key: call });
      setAIHistory(false);
    }
  }, [search, project?.id]);
  const writable =
    can(user, "worlds.write") &&
    (project?.role === "owner" || project?.role === "researcher");
  const root = `/projects/${project?.id}/worlds`;
  const list = useQuery({
    queryKey: ["worlds", project?.id, q, offset, archived],
    queryFn: () =>
      api<any>(
        `${root}?q=${encodeURIComponent(q)}&offset=${offset}&archived=${archived}`,
      ),
    enabled: !!project,
  });
  const detail = useQuery({
    queryKey: ["world", project?.id, identity, revision],
    queryFn: () =>
      api<any>(`${root}/${identity}${revision ? `?revision=${revision}` : ""}`),
    enabled: !!project && !!identity,
  });
  const history = useQuery({
    queryKey: ["world-history", project?.id, identity, before],
    queryFn: () =>
      api<any>(
        `${root}/${identity}/revisions${before ? `?before=${before}` : ""}`,
      ),
    enabled: !!project && !!identity,
  });
  if (!project)
    return <Empty title={t("请选择项目")} detail={t("世界库按项目保存。")} />;
  function open(data: any) {
    setError(null);
    nonce.current = crypto.randomUUID();
    setEditing(data);
  }
  async function save() {
    setBusy(true);
    setError(null);
    try {
      const protocol = await editor.current?.validate();
      if (!protocol) return;
      const row = await post<any>(root, {
        operation_id: nonce.current,
        document_id: editing.document_id ?? null,
        expected_revision: editing.revision ?? 0,
        protocol,
        ai_call_id: editing.ai_call_id ?? null,
      });
      await client.invalidateQueries({ queryKey: ["worlds"] });
      await client.invalidateQueries({ queryKey: ["world"] });
      await client.invalidateQueries({ queryKey: ["world-history"] });
      setIdentity(row.document_id);
      setRevision(null);
      setBefore(null);
      setEditing(null);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  const row = detail.data;
  return (
    <>
      <PageTitle
        eyebrow="WORLDS & BODIES"
        title={t("世界与躯体")}
        description={t(
          "保存物理环境、感官与执行器协议；在无界面训练和图形观察中复用同一版本。",
        )}
        actions={
          <>
            {writable && (
              <Button variant="primary" onClick={() => open({})}>
                <Plus size={16} />
                {t("新建世界")}
              </Button>
            )}
            {writable && (
              <Button
                onClick={() =>
                  setProposal({
                    protocol: row?.protocol,
                    key: crypto.randomUUID(),
                  })
                }
              >
                <Sparkles size={16} />
                {t("AI 生成世界草案")}
              </Button>
            )}
            <Button onClick={() => setAIHistory(true)}>
              {t("世界 AI 请求记录")}
            </Button>
            <Link className="text-link" to="/docs?doc=docs/zh/v2-worlds.md">
              {t("世界协议说明")}
            </Link>
          </>
        }
      />
      <div className="resource-filters">
        <Field label={t("搜索世界")}>
          <input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
          />
        </Field>
        <Field label={t("世界状态")}>
          <select
            value={archived ? "archived" : "active"}
            onChange={(e) => {
              setArchived(e.target.value === "archived");
              setOffset(0);
            }}
          >
            <option value="active">{t("使用中")}</option>
            <option value="archived">{t("已归档")}</option>
          </select>
        </Field>
      </div>
      <ErrorBox
        error={
          list.error ??
          detail.error ??
          history.error ??
          (!editing ? error : null)
        }
      />
      <div className="world-library-layout">
        <section className="panel world-library-list">
          {list.isPending ? (
            <Loading />
          ) : !list.data?.rows.length ? (
            <Empty
              title={t("尚无已保存世界")}
              detail={t("新建一个世界，或在编辑器中导入协议 JSON。")}
            />
          ) : (
            list.data.rows.map((r: any) => (
              <button
                type="button"
                key={r.id}
                className={identity === r.id ? "active" : ""}
                onClick={() => {
                  setIdentity(r.id);
                  setRevision(null);
                  setBefore(null);
                  setError(null);
                }}
              >
                <strong>{r.title}</strong>
                <small>
                  r{r.revision} · {new Date(r.updated_at).toLocaleString()}
                </small>
              </button>
            ))
          )}
          <div className="query-controls">
            <Button disabled={!offset} onClick={() => setOffset(offset - 30)}>
              {t("上一页")}
            </Button>
            <Button
              disabled={!list.data?.more}
              onClick={() => setOffset(offset + 30)}
            >
              {t("下一页")}
            </Button>
          </div>
        </section>
        <section className="panel world-library-detail">
          {identity && detail.isPending ? (
            <Loading />
          ) : !row ? (
            <Empty
              title={t("选择一个世界")}
              detail={t("查看版本、编辑参数或将它用于新的意识。")}
            />
          ) : (
            <>
              <div className="panel-heading">
                <h2>{row.protocol.label}</h2>
                <span>r{row.revision}</span>
              </div>
              <div className="world-library-actions">
                {writable && (
                  <>
                    <Button onClick={() => open({ protocol: row.protocol })}>
                      {t("复制为新世界")}
                    </Button>
                    {!row.archived && revision === null && (
                      <Button onClick={() => open(row)}>
                        {t("编辑并保存新版本")}
                      </Button>
                    )}
                    <Button
                      variant="primary"
                      onClick={() => setRunning(row.protocol)}
                    >
                      {t("配置意识并接入此世界")}
                    </Button>
                  </>
                )}
                <a
                  className="button"
                  href={`/api/v2${root}/${identity}/export?revision=${row.revision}`}
                >
                  {t("导出世界 JSON")}
                </a>
              </div>
              <Field label={t("世界修订")}>
                <select
                  value={revision ?? ""}
                  onChange={(e) =>
                    setRevision(e.target.value ? Number(e.target.value) : null)
                  }
                >
                  <option value="">{t("最新修订")}</option>
                  {history.data?.rows.map((r: any) => (
                    <option key={r.revision} value={r.revision}>
                      r{r.revision} · {new Date(r.created_at).toLocaleString()}
                    </option>
                  ))}
                </select>
              </Field>
              {(before || history.data?.more) && (
                <div className="query-controls">
                  <Button disabled={!before} onClick={() => setBefore(null)}>
                    {t("最新一组")}
                  </Button>
                  <Button
                    disabled={!history.data?.more}
                    onClick={() => setBefore(history.data.rows.at(-1).revision)}
                  >
                    {t("更早版本")}
                  </Button>
                </div>
              )}
              <details>
                <summary>{t("协议身份与复用边界")}</summary>
                <p className="hash-value">{row.protocol_hash}</p>
                <p>
                  {t(
                    "名称属于观察信息。物理参数、感官像素与接线会影响输入；已有运行始终保留创建时的完整世界协议。",
                  )}
                </p>
              </details>
              <WorldEditor
                key={`${identity}:${row.revision}`}
                project={project.id}
                initial={row.protocol}
                readOnly
              />
              {row.ai_call_id && (
                <p className="footnote">
                  {t("AI 辅助设计，已由用户保存。")}{" "}
                  {row.protocol_hash !== row.ai_protocol_hash &&
                    t("保存内容包含人工调整。")}{" "}
                  <button
                    className="text-link"
                    onClick={() => setCallDetail(row.ai_call_id)}
                  >
                    {t("查看完整调用记录")}
                  </button>
                </p>
              )}
              {writable && (
                <Button
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      await api(`${root}/${identity}/archive`, {
                        method: "PUT",
                        body: JSON.stringify({
                          archived: !row.archived,
                          expected_revision: row.revision,
                        }),
                      });
                      await client.invalidateQueries({ queryKey: ["worlds"] });
                      await client.invalidateQueries({ queryKey: ["world"] });
                    } catch (e) {
                      setError(e);
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  {row.archived ? t("恢复到世界库") : t("归档世界")}
                </Button>
              )}
            </>
          )}
        </section>
      </div>
      <Modal
        open={!!editing}
        onOpenChange={(v) => {
          if (!v && !busy) setEditing(null);
        }}
        title={editing?.document_id ? t("编辑世界版本") : t("新建世界")}
        wide
      >
        {editing && (
          <WorldEditor
            ref={editor}
            project={project.id}
            initial={editing.protocol}
            onDirty={() => {
              nonce.current = crypto.randomUUID();
            }}
          />
        )}
        <ErrorBox error={editing ? error : null} />
        <div className="modal-actions">
          <Button onClick={() => setEditing(null)} disabled={busy}>
            {t("取消")}
          </Button>
          <Button variant="primary" onClick={save} disabled={busy}>
            {t("校验并保存世界")}
          </Button>
        </div>
      </Modal>
      <NewRun
        open={!!running}
        onOpenChange={(v) => {
          if (!v) setRunning(null);
        }}
        worldProtocol={running}
      />
      {proposal && (
        <Suspense fallback={<Loading />}>
          <WorldAI
            key={proposal.key}
            project={project.id}
            initial={proposal.protocol}
            initialCall={proposal.call}
            writable={writable}
            onClose={() => {
              setProposal(null);
              if (search.has("proposal")) {
                const next = new URLSearchParams(search);
                next.delete("proposal");
                setSearch(next, { replace: true });
              }
            }}
            onAdopt={(protocol, call) => {
              setProposal(null);
              if (search.has("proposal")) {
                const next = new URLSearchParams(search);
                next.delete("proposal");
                setSearch(next, { replace: true });
              }
              open({ protocol, ai_call_id: call });
            }}
          />
        </Suspense>
      )}
      <Modal
        open={aiHistory}
        onOpenChange={setAIHistory}
        title={t("世界 AI 请求记录")}
        wide
      >
        {aiHistory && <AICallHistory purpose="world" />}
      </Modal>
      {callDetail && (
        <AICallDetail
          callId={callDetail}
          onClose={() => setCallDetail(undefined)}
        />
      )}
    </>
  );
}
