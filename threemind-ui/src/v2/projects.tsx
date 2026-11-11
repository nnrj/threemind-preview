import { lazy, Suspense, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api, post, type Project } from "./api";
import {
  Button,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Modal,
  PageTitle,
  Workspace,
  useWorkspace,
} from "./ui";
import { ProjectDefaults } from "./configuration";
import { ProjectNotificationRules } from "./notificationSettings";
import { can } from "./access";
import { t } from "./i18n";
const StorageAudit = lazy(() => import("./storageAudit"));
const ExecutionResources = lazy(() => import("./executionResources"));
export default function ProjectsPage() {
  const workspace = useWorkspace(),
    client = useQueryClient(),
    [params, setParams] = useSearchParams();
  const query = useQuery<Project[]>({
    queryKey: ["projects"],
    queryFn: () => api("/projects"),
  });
  const identity = params.get("project"),
    project = query.data?.find((p) => p.id === identity);
  const [creating, setCreating] = useState(false),
    [name, setName] = useState("");
  const create = useMutation({
    mutationFn: () => post("/projects", { name }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["projects"] });
      setCreating(false);
      setName("");
    },
  });
  return (
    <>
      <PageTitle
        eyebrow="RESEARCH PROJECTS"
        title={t("研究项目")}
        description={t(
          "项目组织实验、意识与研究资料；系统服务和显示偏好独立管理。",
        )}
        actions={
          can(workspace.user, "projects.create") && (
            <Button variant="primary" onClick={() => setCreating(true)}>
              {t("新建研究项目")}
            </Button>
          )
        }
      />
      <ErrorBox error={query.error} />
      {identity ? (
        project ? (
          <Workspace.Provider value={{ ...workspace, project }}>
            <Link className="button" to="/projects">
              {t("返回项目列表")}
            </Link>
            <ProjectDetails key={project.id} project={project} />
          </Workspace.Provider>
        ) : query.isPending ? (
          <Loading />
        ) : (
          <Empty
            title={t("项目不可访问")}
            detail={t("请返回项目列表检查权限或项目身份。")}
          />
        )
      ) : query.isPending ? (
        <Loading />
      ) : (
        <div className="project-cards">
          {(query.data || []).map((p) => (
            <Link
              className="panel project-card"
              to={`/projects?project=${p.id}`}
              key={p.id}
            >
              <h2>{p.name}</h2>
              <p>
                {t("项目角色")}：{t(p.role)}
              </p>
              <span className="text-link">{t("查看项目配置")}</span>
            </Link>
          ))}
        </div>
      )}
      {!identity && !query.isPending && !query.error && !query.data?.length && (
        <Empty
          title={t("尚无研究项目")}
          detail={t("可以先在意识工作台编辑新建配置，保存时再创建或选择项目。")}
        />
      )}
      <Modal
        open={creating}
        onOpenChange={setCreating}
        title={t("新建研究项目")}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <Field label={t("项目名称")}>
            <input
              required
              maxLength={120}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
          <ErrorBox error={create.error} />
          <Button variant="primary" disabled={create.isPending}>
            {t("创建项目")}
          </Button>
        </form>
      </Modal>
    </>
  );
}
function ProjectDetails({ project }: { project: Project }) {
  const { user } = useWorkspace(),
    client = useQueryClient(),
    [params, setParams] = useSearchParams();
  const [name, setName] = useState(project.name),
    [username, setUsername] = useState(""),
    [role, setRole] = useState("researcher");
  const tab = params.get("tab") || "overview",
    write =
      can(user, "projects.manage") &&
      (project.role === "owner" || user?.superadmin);
  const members = useQuery<any[]>({
    queryKey: ["members", project.id],
    queryFn: () => api(`/projects/${project.id}/members`),
    enabled: tab === "members",
  });
  const rename = useMutation({
    mutationFn: () =>
      api(`/projects/${project.id}`, {
        method: "PUT",
        body: JSON.stringify({ name }),
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["projects"] }),
  });
  const member = useMutation({
    mutationFn: () =>
      post(`/projects/${project.id}/members`, { username, role }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["members", project.id] });
      setUsername("");
    },
  });
  const change = (tab: string) => setParams({ project: project.id, tab });
  return (
    <>
      <h2>{project.name}</h2>
      <div className="tabs">
        <button
          className={tab === "overview" ? "active" : ""}
          onClick={() => change("overview")}
        >
          {t("项目概况")}
        </button>
        <button
          className={tab === "defaults" ? "active" : ""}
          onClick={() => change("defaults")}
        >
          {t("项目创建预设")}
        </button>
        <button
          className={tab === "members" ? "active" : ""}
          onClick={() => change("members")}
        >
          {t("项目成员")}
        </button>
        <button
          className={tab === "notifications" ? "active" : ""}
          onClick={() => change("notifications")}
        >
          {t("项目通知规则")}
        </button>
        <button
          className={tab === "execution" ? "active" : ""}
          onClick={() => change("execution")}
        >
          {t("项目执行队列")}
        </button>
        <button
          className={tab === "storage" ? "active" : ""}
          onClick={() => change("storage")}
        >
          {t("实验存储检查")}
        </button>
      </div>
      {tab === "storage" ? (
        <Suspense fallback={<Loading />}>
          <StorageAudit />
        </Suspense>
      ) : tab === "execution" ? (
        <Suspense fallback={<Loading />}>
          <ExecutionResources />
        </Suspense>
      ) : tab === "defaults" ? (
        <ProjectDefaults />
      ) : tab === "notifications" ? (
        <ProjectNotificationRules projectId={project.id} />
      ) : tab === "members" ? (
        <section className="panel">
          <ErrorBox error={members.error || member.error} />
          {members.isPending ? (
            <Loading />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t("账号")}</th>
                    <th>{t("项目角色")}</th>
                  </tr>
                </thead>
                <tbody>
                  {(members.data || []).map((row) => (
                    <tr key={row.id}>
                      <td>{row.username}</td>
                      <td>{t(row.role)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {write && (
            <form
              className="form-grid"
              onSubmit={(e) => {
                e.preventDefault();
                member.mutate();
              }}
            >
              <Field label={t("账号")}>
                <input
                  value={username}
                  required
                  onChange={(e) => setUsername(e.target.value)}
                />
              </Field>
              <Field label={t("项目角色")}>
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                  <option value="researcher">{t("研究者")}</option>
                  <option value="viewer">{t("观察者")}</option>
                </select>
              </Field>
              <Button disabled={member.isPending}>
                {t("添加 / 更新成员")}
              </Button>
            </form>
          )}
        </section>
      ) : (
        <section className="panel">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              rename.mutate();
            }}
          >
            <Field label={t("项目名称")}>
              <input
                disabled={!write}
                value={name}
                required
                maxLength={120}
                onChange={(e) => setName(e.target.value)}
              />
            </Field>
            <ErrorBox error={rename.error} />
            {write && (
              <Button disabled={rename.isPending}>{t("保存项目名称")}</Button>
            )}
          </form>
          <p>{t("项目预设只在新建时主动选用，不会覆盖现存意识或新建草稿。")}</p>
          <div className="form-actions">
            <Link
              className="button"
              to={`/projects/${project.id}/tools/studies`}
            >
              {t("实验与训练工具")}
            </Link>
            <Link
              className="button"
              to={`/projects/${project.id}/tools/worlds`}
            >
              {t("世界与躯体工具")}
            </Link>
            <Link
              className="button"
              to={`/projects/${project.id}/tools/models`}
            >
              {t("模型与导入导出工具")}
            </Link>
            <Link
              className="button"
              to={`/projects/${project.id}/tools/data-management`}
            >
              {t("项目数据管理")}
            </Link>
            <Link
              className="button"
              to={`/research-records?project=${project.id}`}
            >
              {t("实验总览")}
            </Link>
            <Link className="button" to={`/models?project=${project.id}`}>
              {t("意识档案与模型")}
            </Link>
          </div>
        </section>
      )}
    </>
  );
}
