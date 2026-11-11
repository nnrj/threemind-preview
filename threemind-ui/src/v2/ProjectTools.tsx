import { lazy, Suspense, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type Project } from "./api";
import { DataPage, ModelsPage, Overview, NewRun } from "./research";
import { AccessBoundary } from "./access";
import { ErrorBox, Loading, Workspace, useWorkspace } from "./ui";
import { t } from "./i18n";
const Studies = lazy(() => import("./studies")),
  Worlds = lazy(() => import("./worlds")),
  Dialogue = lazy(() => import("./Dialogue")),
  Notes = lazy(() => import("./notes")),
  Reports = lazy(() => import("./reports")),
  DataManagement = lazy(() => import("./DataManagement"));
const actions: Record<string, string> = {
  overview: "menu.overview",
  studies: "menu.experiments",
  compare: "menu.comparisons",
  worlds: "menu.worlds",
  dialogue: "menu.conversation",
  notes: "menu.notes",
  reports: "menu.reports",
  data: "menu.query",
  models: "menu.models",
  "data-management": "menu.data",
};
export default function ProjectTools() {
  const { id, area = "overview" } = useParams(),
    workspace = useWorkspace(),
    [creating, setCreating] = useState(false);
  const project = useQuery<Project>({
    queryKey: ["resource-project", id],
    queryFn: () => api(`/projects/${encodeURIComponent(id || "")}`),
    enabled: !!id,
    retry: false,
  });
  if (project.isPending) return <Loading />;
  if (project.error) return <ErrorBox error={project.error} />;
  if (!project.data) return null;
  return (
    <Workspace.Provider value={{ ...workspace, project: project.data }}>
      <div className="resource-owner">
        <span>
          {t("所属项目")}：{project.data.name}
        </span>
        <Link className="button" to={`/projects?project=${id}`}>
          {t("查看项目配置")}
        </Link>
        <Link
          className="button"
          to={area === "overview" ? "/research" : `/${area}`}
        >
          {t("返回全部资料")}
        </Link>
      </div>
      <p className="footnote">
        {t("此处管理已选项目的对象和工具。各资料菜单仍提供统一的跨项目列表。")}
      </p>
      <AccessBoundary action={actions[area] || "menu.overview"}>
        <Suspense key={`${id}:${area}`} fallback={<Loading />}>
          {area === "studies" ? (
            <Studies />
          ) : area === "compare" ? (
            <Studies compare />
          ) : area === "worlds" ? (
            <Worlds />
          ) : area === "dialogue" ? (
            <Dialogue />
          ) : area === "notes" ? (
            <Notes />
          ) : area === "reports" ? (
            <Reports />
          ) : area === "data" ? (
            <DataPage />
          ) : area === "models" ? (
            <ModelsPage />
          ) : area === "data-management" ? (
            <DataManagement />
          ) : (
            <Overview onNew={() => setCreating(true)} />
          )}
        </Suspense>
      </AccessBoundary>
      <NewRun open={creating} onOpenChange={setCreating} />
    </Workspace.Provider>
  );
}
