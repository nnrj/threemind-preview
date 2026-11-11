import DraftResource from "./DraftResource";
import { StudyDesigner } from "./studyDesigner";
import { useState, useEffect, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Plus, ArrowRight } from "lucide-react";
import { api, type Project } from "./api";
import { t, useLocale, messageKeys, dateLabel } from "./i18n";
import {
  Badge,
  Button,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Metric,
  Modal,
  PageTitle,
  Workspace,
  useWorkspace,
} from "./ui";
import "./resourceBrowser.css";
import { can } from "./access";

type Json = Record<string, any>;
type Area =
  | "studies"
  | "compare"
  | "worlds"
  | "dialogue"
  | "data"
  | "models"
  | "notes"
  | "reports"
  | "data-management";
const titles: Record<Area, string> = messageKeys({
  studies: "实验与训练",
  compare: "比较与消融",
  worlds: "世界与躯体",
  dialogue: "对话实验",
  data: "数据查询",
  models: "模型与证据",
  notes: "实验笔记",
  reports: "记录与报告",
  "data-management": "数据管理",
});
const labels: Record<string, string> = messageKeys({
  run: "意识实例",
  experiment: "研究实验",
  study: "配对实验",
  document: "记录与报告",
  note: "实验笔记",
  world: "世界与躯体",
  evolution: "多代定向训练",
  ecology: "生态演化",
  assessment: "独立评估",
  development: "发育与先天模型",
  innate: "先天模型",
  language: "对话实验",
  species: "物种模型",
  artifact: "研究产物",
  experiment_bundle: "实验归档包",
  data_bundle: "数据包",
  media: "媒体原件",
  probe: "探针校准",
  source: "固定数据来源",
});
const kinds: Record<Area, string[]> = {
  studies: [
    "experiment",
    "study",
    "development",
    "evolution",
    "ecology",
    "assessment",
    "probe",
  ],
  compare: ["study", "experiment", "assessment"],
  worlds: ["world"],
  dialogue: ["language"],
  data: ["run"],
  models: ["run", "innate", "species", "artifact", "experiment_bundle"],
  notes: ["note"],
  reports: ["document"],
  "data-management": Object.keys(labels),
};
const date = dateLabel;
const resourceTitle = (row: Json) =>
  row.kind === "language" ? row.details.name : row.title;

function resourceLink(row: Json, area: Area) {
  const params = new URLSearchParams({ project: row.project_id });
  let path = "/data-management";
  if (row.kind === "experiment") {
    path = "/research-records";
    params.set("experiment", row.id);
  } else if (row.kind === "run") {
    path = area === "data" ? "/data" : `/runs/${row.id}`;
    if (area === "data") params.set("run", row.id);
  } else if (row.kind === "document") {
    path = "/reports";
    params.set("document", row.id);
    params.set("tab", row.details.type);
  } else if (row.kind === "note") {
    path = "/notes";
    params.set("note", row.id);
    params.set("tab", "write");
  } else if (row.kind === "world") {
    path = "/worlds";
    params.set("world", row.id);
    if (row.details.type === "robot") params.set("view", "robots");
  } else if (row.kind === "language") {
    path = "/dialogue";
    params.set("run", row.id);
  } else if (row.kind === "study") {
    path = area === "compare" ? "/compare" : "/studies";
    params.set("study", row.id);
  } else if (row.kind === "development") {
    path = `/runs/${row.details.run_id}`;
  } else if (
    ["evolution", "ecology", "assessment", "innate"].includes(row.kind)
  ) {
    path = "/studies";
    params.set("tab", row.kind === "innate" ? "development" : row.kind);
    params.set(
      row.kind === "assessment"
        ? "assessment"
        : row.kind === "innate"
          ? "version"
          : row.kind === "development"
            ? "session"
            : "campaign",
      row.id,
    );
  } else if (row.kind === "probe") {
    path = `/runs/${row.details.run_id}`;
  } else if (row.kind === "data_bundle") {
    params.set("view", "bundles");
    params.set("bundle", row.id);
  } else {
    params.set("resource", row.id);
    params.set("kind", row.kind);
  }
  return `${path}?${params}`;
}

export function ScopeBanner() {
  const { project } = useWorkspace();
  return (
    <p className="browse-scope">
      {project
        ? t("浏览范围：{name}", { name: project.name })
        : t("浏览范围：全部有权访问的项目")}
    </p>
  );
}

export function ProjectDestination({
  children,
  locked = false,
  writableOnly = true,
}: {
  children: ReactNode;
  locked?: boolean;
  writableOnly?: boolean;
}) {
  const workspace = useWorkspace();
  const [params] = useSearchParams();
  const choices = workspace.projects.filter(
    (p) => !writableOnly || p.role !== "viewer",
  );
  const [chosen, setChosen] = useState(() => {
    const initial = params.get("project") || workspace.project?.id || "";
    return choices.some((p) => p.id === initial) ? initial : "";
  });
  const project = choices.find((p) => p.id === chosen) || null;
  return (
    <>
      <Field label={t("所属项目")}>
        <select
          aria-label={t("所属项目")}
          value={chosen}
          disabled={locked && !!project}
          onChange={(e) => setChosen(e.target.value)}
        >
          <option value="">{t("请选择归属项目")}</option>
          {choices.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </Field>
      {project ? (
        <Workspace.Provider value={{ ...workspace, project }}>
          <div key={project.id}>{children}</div>
        </Workspace.Provider>
      ) : (
        <p>{t("选择归属项目后继续。浏览范围不会决定新资料的归属。")}</p>
      )}
    </>
  );
}

export function ResourceBoundary({
  area,
  children,
  resource,
  force = false,
}: {
  area?: Area;
  children: ReactNode;
  resource?: { kind: string; id: string | null };
  force?: boolean;
}) {
  const workspace = useWorkspace();
  const [params, setParams] = useSearchParams();
  const explicit = params.get("project");
  const located = useQuery<Json>({
    queryKey: ["browse-location", resource?.kind, resource?.id],
    queryFn: () =>
      api(
        `/browse/location/${resource!.kind}/${encodeURIComponent(resource!.id!)}`,
      ),
    enabled: !!resource?.id,
    retry: false,
  });
  const identity = located.data?.project_id || explicit;
  const owner = useQuery<Project>({
    queryKey: ["resource-project", identity],
    queryFn: () => api(`/projects/${identity}`),
    enabled: !!identity && (!!resource?.id || params.has("action")),
    retry: false,
  });
  const project =
    workspace.projects.find((p) => p.id === identity) || owner.data || null;
  useEffect(() => {
    if (
      resource?.id &&
      located.data?.project_id &&
      explicit !== located.data.project_id
    )
      setParams(
        (current) => {
          const next = new URLSearchParams(current);
          next.set("project", located.data.project_id);
          return next;
        },
        { replace: true },
      );
  }, [explicit, resource?.id, located.data?.project_id, setParams]);
  if (resource?.id && located.isPending) return <Loading />;
  if (located.error) return <ErrorBox error={located.error} />;
  if (
    identity &&
    !project &&
    owner.isPending &&
    (!!resource?.id || params.has("action"))
  )
    return <Loading />;
  if (identity && !project && (!!resource?.id || params.has("action")))
    return <ErrorBox error={new Error(t("资料所属项目不可访问。"))} />;
  if (!force && area && !resource?.id && !params.has("action")) {
    const filter = explicit
      ? workspace.projects.find((p) => p.id === explicit) || null
      : workspace.project;
    return (
      <Workspace.Provider value={{ ...workspace, project: filter }}>
        <GlobalResources key={area} area={area} />
      </Workspace.Provider>
    );
  }
  if (!project && !force)
    return area ? <GlobalResources key={area} area={area} /> : null;
  if (!project) return <>{children}</>;
  return (
    <Workspace.Provider value={{ ...workspace, project }}>
      <div className="resource-owner">
        <span>
          {t("所属项目")}：{project.name}
        </span>
        {area && (
          <Button
            onClick={() => {
              workspace.selectProject?.("");
              setParams({});
            }}
          >
            {t("返回全部资料")}
          </Button>
        )}
      </div>
      <div key={project.id}>{children}</div>
    </Workspace.Provider>
  );
}

export function GlobalResources({ area }: { area: Area }) {
  useLocale();
  const workspace = useWorkspace();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(""),
    [offset, setOffset] = useState(0),
    [archived, setArchived] = useState("active");
  const presetKind =
    area === "studies" &&
    ["development", "evolution", "ecology", "assessment"].includes(
      params.get("tab") || "",
    )
      ? params.get("tab")!
      : area === "models"
        ? {
            artifacts: "artifact",
            species: "species",
            bundles: "experiment_bundle",
          }[params.get("view") || ""] || ""
        : area === "reports"
          ? "document"
          : area === "notes"
            ? "note"
            : "";
  const [kind, setKind] = useState(presetKind);
  const [subtype, setSubtype] = useState(
    area === "reports"
      ? params.get("tab") || ""
      : area === "worlds" && params.get("view") === "robots"
        ? "robot"
        : "",
  );
  const [draftKind, setDraftKind] = useState<
      "note" | "record" | "report" | null
    >(null),
    [designing, setDesigning] = useState(false);
  const [destination, setDestination] = useState(false),
    [target, setTarget] = useState(""),
    [tools, setTools] = useState(false);
  useEffect(() => setOffset(0), [workspace.project?.id]);
  const selectedKinds = kind ? [kind] : kinds[area];
  const search = new URLSearchParams({
    kinds: selectedKinds.join(","),
    q,
    subtype,
    archived,
    offset: String(offset),
    limit: "50",
  });
  if (workspace.project) search.set("project", workspace.project.id);
  const data = useQuery<Json>({
    queryKey: ["browse-resources", area, search.toString()],
    queryFn: () => api("/browse/resources?" + search),
    refetchOnWindowFocus: true,
  });
  const writable = workspace.projects.filter((p) => p.role !== "viewer");
  const creationPermission: Record<Area, string> = {
    studies: "experiments.create",
    compare: "experiments.create",
    worlds: "worlds.write",
    dialogue: "experiments.create",
    data: "data.read",
    models: "data.import",
    notes: "notes.write",
    reports: "reports.write",
    "data-management": "data.manage",
  };
  function change(setter: (v: string) => void, value: string) {
    setter(value);
    setOffset(0);
  }
  const rows = data.data?.rows || [];
  return (
    <div className="global-resources">
      <PageTitle
        eyebrow="RESEARCH WORKSPACE"
        title={t(titles[area])}
        description={
          area === "data"
            ? t("跨项目查找意识实例，选择后查看其节点、连接及检查点数据。")
            : t("跨项目查看研究资料；打开资料后按其所属项目操作。")
        }
        actions={
          <>
            <Button
              onClick={() => {
                setTools(true);
                setTarget(workspace.project?.id || "");
                setDestination(true);
              }}
            >
              {t("项目资料工具")}
            </Button>
            {area === "data-management" &&
              can(workspace.user, "system.read") && (
                <Link className="button" to="/settings?section=storage">
                  {t("存储位置")}
                </Link>
              )}
            {area !== "data" &&
              can(workspace.user, creationPermission[area]) && (
                <Button
                  variant="primary"
                  onClick={() => {
                    setTools(false);
                    if (area === "notes") {
                      setDraftKind("note");
                      return;
                    }
                    if (area === "reports") {
                      setDraftKind(subtype === "record" ? "record" : "report");
                      return;
                    }
                    if (
                      (area === "studies" || area === "compare") &&
                      ![
                        "development",
                        "evolution",
                        "ecology",
                        "assessment",
                      ].includes(kind)
                    ) {
                      setDesigning(true);
                      return;
                    }

                    setTarget(
                      workspace.project?.role !== "viewer"
                        ? workspace.project?.id || ""
                        : "",
                    );
                    setDestination(true);
                  }}
                >
                  <Plus size={15} />
                  {t(
                    area === "notes"
                      ? "新建笔记"
                      : area === "worlds"
                        ? "新建世界或躯体"
                        : area === "reports"
                          ? "编写记录或报告"
                          : area === "data-management"
                            ? "导入、导出与数据操作"
                            : area === "dialogue"
                              ? "创建对话实验"
                              : area === "compare"
                                ? "创建比较实验"
                                : area === "models"
                                  ? "导入与模型管理"
                                  : "创建实验",
                  )}
                </Button>
              )}
          </>
        }
      />
      <ScopeBanner />
      <div className="browse-filters">
        <Field label={t("搜索资料或项目")}>
          <input
            value={q}
            onChange={(e) => change(setQ, e.target.value)}
            maxLength={160}
          />
        </Field>
        {kinds[area].length > 1 && (
          <Field label={t("资料类型")}>
            <select
              value={kind}
              onChange={(e) => {
                change(setKind, e.target.value);
                setSubtype("");
              }}
            >
              <option value="">{t("全部类型")}</option>
              {kinds[area].map((k) => (
                <option key={k} value={k}>
                  {t(labels[k])}
                </option>
              ))}
            </select>
          </Field>
        )}
        {["reports", "notes", "worlds"].includes(area) && (
          <Field label={t("资料分类")}>
            <select
              value={subtype}
              onChange={(e) => change(setSubtype, e.target.value)}
            >
              <option value="">{t("全部分类")}</option>
              {(area === "reports"
                ? [
                    ["record", "实验记录"],
                    ["report", "实验报告"],
                  ]
                : area === "notes"
                  ? [
                      ["note", "实验笔记"],
                      ["draft", "草稿"],
                    ]
                  : [
                      ["world", "世界库"],
                      ["robot", "机器人任务"],
                    ]
              ).map(([k, title]) => (
                <option key={k} value={k}>
                  {t(title)}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field label={t("归档状态")}>
          <select
            value={archived}
            onChange={(e) => change(setArchived, e.target.value)}
          >
            <option value="active">{t("未归档")}</option>
            <option value="archived">{t("已归档")}</option>
            <option value="all">{t("全部")}</option>
          </select>
        </Field>
      </div>
      <ErrorBox error={data.error} />
      {data.isPending ? (
        <Loading />
      ) : data.error ? null : rows.length ? (
        <>
          <p>{t("共 {count} 条资料", { count: data.data?.total || 0 })}</p>
          <div className="table-wrap">
            <table className="browse-table">
              <thead>
                <tr>
                  <th>{t("资料名称")}</th>
                  <th>{t("所属项目")}</th>
                  <th>{t("资料类型")}</th>
                  <th>{t("状态")}</th>
                  <th>{t("更新时间")}</th>
                  <th>{t("操作")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row: Json) => (
                  <tr key={`${row.project_id}:${row.kind}:${row.id}`}>
                    <td>
                      <Link to={resourceLink(row, area)}>
                        {row.details.original_id
                          ? `${row.details.original_id} · `
                          : ""}
                        {resourceTitle(row)}
                      </Link>
                      {row.details.excerpt && (
                        <small className="browse-excerpt">
                          {row.details.excerpt}
                        </small>
                      )}
                    </td>
                    <td>{row.project_name}</td>
                    <td>{t(labels[row.kind])}</td>
                    <td>{row.status ? <Badge status={row.status} /> : "—"}</td>
                    <td>{date(row.updated_at)}</td>
                    <td>
                      <Link className="text-link" to={resourceLink(row, area)}>
                        {t("查看资料")} <ArrowRight size={14} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <Empty
          title={t("此范围内没有资料")}
          detail={t(
            "可调整项目、类型或归档筛选；全局列表仅显示有权访问的资料。",
          )}
        />
      )}
      <div className="pagination">
        <Button
          disabled={!offset || data.isFetching}
          onClick={() => setOffset(offset - 50)}
        >
          {t("上一页")}
        </Button>
        <span>{Math.floor(offset / 50) + 1}</span>
        <Button
          disabled={!data.data?.more || data.isFetching}
          onClick={() => setOffset(offset + 50)}
        >
          {t("下一页")}
        </Button>
      </div>
      {area === "notes" && (
        <p className="browse-scope">{t("笔记仅显示本人有权访问的内容。")}</p>
      )}
      {draftKind && (
        <DraftResource kind={draftKind} onClose={() => setDraftKind(null)} />
      )}
      {designing && (
        <StudyDesigner
          project={workspace.project?.id || ""}
          close={() => setDesigning(false)}
          created={(id, project) => {
            setDesigning(false);
            setParams({ study: id, project: project || "" });
          }}
        />
      )}
      <Modal
        open={destination}
        onOpenChange={setDestination}
        title={t("选择归属项目")}
        description={t("新资料保存在所选项目；已有资料的归属保持不变。")}
      >
        <Field label={t("所属项目")}>
          <select
            aria-label={t("所属项目")}
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          >
            <option value="">{t("请选择归属项目")}</option>
            {(tools ? workspace.projects : writable).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </Field>
        <Button
          variant="primary"
          disabled={!target}
          onClick={() => {
            const next = new URLSearchParams(params);
            next.delete("project");
            next.delete("action");
            if (area === "reports" && subtype) next.set("tab", subtype);
            if (
              area === "studies" &&
              ["development", "evolution", "ecology", "assessment"].includes(
                kind,
              )
            )
              next.set("tab", kind);
            if (area === "worlds" && subtype === "robot")
              next.set("view", "robots");
            if (
              area === "models" &&
              ["artifact", "species", "experiment_bundle"].includes(kind)
            )
              next.set(
                "view",
                {
                  artifact: "artifacts",
                  species: "species",
                  experiment_bundle: "bundles",
                }[kind] || "library",
              );
            navigate(
              `/projects/${encodeURIComponent(target)}/tools/${area}${next.size ? `?${next}` : ""}`,
            );
            setDestination(false);
          }}
        >
          {t("继续")}
        </Button>
      </Modal>
    </div>
  );
}

export function GlobalOverview({ onNew }: { onNew: () => void }) {
  useLocale();
  const { project, selectProject } = useWorkspace();
  const [q, setQ] = useState(""),
    [offset, setOffset] = useState(0);
  useEffect(() => setOffset(0), [project?.id]);
  const params = new URLSearchParams({
    q,
    offset: String(offset),
    limit: "12",
  });
  if (project) params.set("project", project.id);
  const data = useQuery<Json>({
    queryKey: ["browse-overview", params.toString()],
    queryFn: () => api("/browse/overview?" + params),
  });
  const counts = data.data?.totals || {};
  return (
    <div className="global-overview">
      <PageTitle
        eyebrow="RESEARCH OVERVIEW"
        title={t("研究概览")}
        description={t("汇总全部有权访问的项目、意识实例及研究资料。")}
        actions={
          <Button variant="primary" onClick={onNew}>
            <Plus size={15} />
            {t("新建意识")}
          </Button>
        }
      />
      <ScopeBanner />
      <ErrorBox error={data.error} />
      {data.isPending ? (
        <Loading />
      ) : (
        !data.error && (
          <>
            <div className="metrics-grid">
              <Metric
                label={t("研究项目")}
                value={data.data?.total || 0}
                detail={t("当前浏览范围内可访问的项目")}
              />
              <Metric
                label={t("意识实例")}
                value={counts.run || 0}
                detail={t("保存的独立个体，不代表实验完成次数")}
              />
              <Metric
                label={t("研究实验")}
                value={counts.experiment || 0}
                detail={t("统一研究索引，执行状态另列")}
              />
              <Metric
                label={t("报告与笔记")}
                value={(counts.document || 0) + (counts.note || 0)}
                detail={t("报告记录及本人可见笔记")}
              />
            </div>
            <div className="browse-links">
              <Link className="button" to="/research-records">
                {t("实验总览")}
              </Link>
              <Link className="button" to="/reports">
                {t("记录与报告")}
              </Link>
              <Link className="button" to="/notes">
                {t("实验笔记")}
              </Link>
              <Link className="button" to="/models">
                {t("模型与证据")}
              </Link>
            </div>
            <section className="panel">
              <h2>{t("项目列表")}</h2>
              <Field label={t("搜索项目")}>
                <input
                  value={q}
                  onChange={(e) => {
                    setQ(e.target.value);
                    setOffset(0);
                  }}
                  maxLength={160}
                />
              </Field>
              <div className="project-summary-grid">
                {(data.data?.rows || []).map(
                  (p: Project & { counts: Json }) => (
                    <article className="project-summary" key={p.id}>
                      <h3>{p.name}</h3>
                      <p>
                        {t(
                          "意识 {runs} · 实验 {experiments} · 报告 {documents} · 笔记 {notes}",
                          {
                            runs: p.counts.run || 0,
                            experiments: p.counts.experiment || 0,
                            documents: p.counts.document || 0,
                            notes: p.counts.note || 0,
                          },
                        )}
                      </p>
                      <Button
                        onClick={() => {
                          selectProject?.(p.id);
                          setOffset(0);
                        }}
                      >
                        {t("按此项目浏览")}
                      </Button>
                      <Link
                        className="text-link"
                        to={`/models?project=${p.id}`}
                      >
                        {t("项目操作")}
                      </Link>
                    </article>
                  ),
                )}
              </div>
              {!data.data?.rows?.length && (
                <Empty
                  title={t("此范围内没有项目")}
                  detail={t("创建研究项目，或调整筛选条件。")}
                />
              )}
              <div className="pagination">
                <Button
                  disabled={!offset}
                  onClick={() => setOffset(offset - 12)}
                >
                  {t("上一页")}
                </Button>
                <span>{offset / 12 + 1}</span>
                <Button
                  disabled={!data.data?.more}
                  onClick={() => setOffset(offset + 12)}
                >
                  {t("下一页")}
                </Button>
              </div>
            </section>
          </>
        )
      )}
    </div>
  );
}
