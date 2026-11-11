import { t, useLocale } from "./i18n";
import LanguagePicker from "./LanguagePicker";
import { Suspense, lazy, useEffect, useState, type ReactNode } from "react";
import {
  NavLink,
  Routes,
  Route,
  Link,
  useLocation,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  FlaskConical,
  GitCompareArrows,
  Database,
  Box,
  BookOpen,
  Settings2,
  ShieldCheck,
  Plus,
  ChevronDown,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  FolderOpen,
  NotebookPen,
  Files,
  Globe2,
  Cpu,
  Menu,
  Network,
} from "lucide-react";
import { api, post, setCsrf, ApiError, type Project } from "./api";
import {
  Button,
  Modal,
  Field,
  Workspace,
  ErrorBox,
  Loading,
  useWorkspace,
} from "./ui";
import "./researchRecords.css";
import { RunPage, DataPage, ModelsPage, NewRun } from "./research";
import { GlobalOverview, ResourceBoundary } from "./ResourceBrowser";
import { usePreferences } from "./preferences";
import NotificationBell from "./notificationBell";
import { clearNoteRecovery } from "./noteStore";
import { clearReportRecovery } from "./reportDraft";
import { AccessBoundary, can } from "./access";
import { setPreferenceUser } from "./preferences";
import "./platform.css";
import "./history.css";
import LogoutDialog from "./LogoutDialog";
const Studies = lazy(() => import("./studies"));
const Worlds = lazy(() => import("./worlds"));
const Dialogue = lazy(() => import("./Dialogue"));
const LanguageReplayPage = lazy(() => import("./replay/LanguageReplayPage"));
const Kernels = lazy(() => import("./Kernels"));
const Documentation = lazy(() => import("./docs"));
const History = lazy(() => import("./history"));
const Settings = lazy(() => import("./settings"));
const Administration = lazy(() => import("./admin"));
const Notes = lazy(() => import("./notes"));
const Reports = lazy(() => import("./reports"));
const SharedReport = lazy(() => import("./SharedReport"));
const DataManagement = lazy(() => import("./DataManagement"));
const ResearchRecords = lazy(() => import("./ResearchRecords"));
const Workbench = lazy(() => import("./workbench"));
const ProjectsPage = lazy(() => import("./projects"));
const ProjectTools = lazy(() => import("./ProjectTools"));

const navigation = [
  ["/", "意识工作台", Network, "menu.workbench"],
  ["/research", "研究概览", Activity, "menu.overview"],
  ["/projects", "研究项目", FolderOpen, "menu.projects"],
  ["/research-records", "实验总览", Files, "menu.experiments"],
  ["/studies", "实验与训练", FlaskConical, "menu.experiments"],
  ["/worlds", "世界与躯体", Globe2, "menu.worlds"],
  ["/dialogue", "对话实验", NotebookPen, "menu.conversation"],
  ["/compare", "比较与消融", GitCompareArrows, "menu.comparisons"],
  ["/models", "意识档案与模型", Box, "menu.models"],
  ["/data", "数据查询", Database, "menu.query"],
  ["/notes", "实验笔记", NotebookPen, "menu.notes"],
  ["/reports", "记录与报告", Files, "menu.reports"],
  ["/data-management", "数据管理", FolderOpen, "menu.data"],
  ["/settings", "系统设置", Settings2, "menu.settings"],
  ["/admin", "用户与权限", ShieldCheck, "menu.accounts"],
  ["/kernels", "内核与适配器", Cpu, "menu.kernels"],
  ["/docs", "使用文档", BookOpen, "menu.docs"],
  ["/history", "史书", BookOpen, "menu.docs"],
] as const;
const navigationGroups = [
  { label: "意识工作台", items: navigation.slice(0, 1) },
  { label: "研究中心", items: navigation.slice(1, 8) },
  { label: "资料中心", items: navigation.slice(8, 13) },
  { label: "系统设置", items: navigation.slice(13, 15) },
  { label: "文档与帮助", items: navigation.slice(15) },
];
function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useWorkspace();
  return (
    <nav aria-label={t("主要导航")} className="grouped-navigation">
      {navigationGroups
        .filter((group) => group.items.some((item) => can(user, item[3])))
        .map((group) => (
          <div key={group.label} className="nav-group">
            <span className="nav-group-title">{t(group.label)}</span>
            {group.items
              .filter((item) => can(user, item[3]))
              .map(([url, label, Icon]) => (
                <NavLink
                  key={url}
                  to={url}
                  end={url === "/"}
                  aria-label={t(label)}
                  title={t(label)}
                  onClick={onNavigate}
                >
                  <Icon size={19} />
                  <span>{t(label)}</span>
                </NavLink>
              ))}
          </div>
        ))}
    </nav>
  );
}
function Brand() {
  return (
    <div className="brand">
      <svg width="35" height="35" viewBox="0 0 40 40" aria-hidden="true">
        <path
          d="M8 29L20 8L32 29Z M8 29L20 21L32 29M20 8V21"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.3"
        />
        <circle cx="20" cy="8" r="4" fill="currentColor" />
        <circle cx="8" cy="29" r="4" fill="currentColor" />
        <circle cx="32" cy="29" r="4" fill="currentColor" />
        <circle cx="20" cy="21" r="2" fill="currentColor" />
      </svg>
      <div>
        ThreeMind<span>RESEARCH LAB</span>
      </div>
    </div>
  );
}

function LoginPage({ onSuccess }: { onSuccess: () => void }) {
  const [username, setUsername] = useState(""),
    [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState(""),
    [remember, setRemember] = useState(true);
  const setup = useQuery({
    queryKey: ["auth-setup"],
    queryFn: () => api("/auth/setup/status"),
    retry: false,
  });
  const initializing = setup.data?.required === true;
  const mutation = useMutation({
    mutationFn: () =>
      initializing
        ? post("/auth/setup", {
            username: username || setup.data.username,
            password,
          })
        : post("/login", { username, password, remember }),
    onSuccess: (data) => {
      setCsrf(data.csrf);
      onSuccess();
    },
  });
  return (
    <div className="login-page">
      <div className="login-card">
        <Brand />
        <LanguagePicker compact />
        <span className="eyebrow">THREEMIND</span>
        <h1>{initializing ? t("首次设置本机账号") : t("登录 ThreeMind")}</h1>
        <p>
          {initializing
            ? t("为现有 local 身份设置密码，保留全部原有资料与作者关系。")
            : t("登录本部署的账号，进入意识工作台。")}
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
        >
          <Field label={t("账号")}>
            <input
              value={username || (initializing ? setup.data.username : "")}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required={!initializing}
            />
          </Field>
          <Field label={t("密码")}>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              minLength={initializing ? 12 : undefined}
              required
            />
          </Field>
          {initializing ? (
            <Field label={t("确认密码")}>
              <input
                type="password"
                value={repeat}
                autoComplete="new-password"
                minLength={12}
                required
                onChange={(event) => setRepeat(event.target.value)}
              />
            </Field>
          ) : (
            <label className="check">
              <input
                type="checkbox"
                checked={remember}
                onChange={(event) => setRemember(event.target.checked)}
              />
              {t("记住会话")}
            </label>
          )}
          <ErrorBox error={mutation.error || setup.error} />
          <Button
            variant="primary"
            disabled={
              mutation.isPending ||
              setup.isPending ||
              (initializing && password !== repeat)
            }
          >
            {initializing ? t("设置密码并进入") : t("登录")}
          </Button>
        </form>
        <Link to="/docs">{t("阅读项目文档")}</Link>
        <Link to="/history">{t("阅读项目史书")}</Link>
      </div>
    </div>
  );
}

export default function App() {
  const location = useLocation();
  if (location.pathname === "/history" || location.pathname === "/docs")
    return <HistoryPage documentation={location.pathname === "/docs"} />;
  if (location.pathname.startsWith("/shared/"))
    return (
      <Suspense fallback={<Loading />}>
        <SharedReport />
      </Suspense>
    );
  return <LabApp />;
}

// Historical text is public project documentation, independent of a selected
// research project or an authenticated database session.
function HistoryPage({ documentation = false }: { documentation?: boolean }) {
  const preferences = usePreferences(),
    language = useLocale();
  useEffect(() => {
    document.documentElement.dataset.theme = preferences.theme;
    document.documentElement.lang = language;
  }, [preferences.theme, language]);
  return (
    <div className="history-shell">
      <header className="history-shell-header">
        <Link to="/" className="brand-link">
          <Brand />
        </Link>
        <nav aria-label={t("主要导航")}>
          <Link to="/">{t("研究工作台")}</Link>
          <Link to="/docs" aria-current={documentation ? "page" : undefined}>
            {t("项目文档")}
          </Link>
          <Link
            to="/history"
            aria-current={!documentation ? "page" : undefined}
          >
            {t("史书")}
          </Link>
          <LanguagePicker compact />
        </nav>
      </header>
      <main className="history-shell-main">
        <Suspense fallback={<Loading />}>
          {documentation ? <Documentation /> : <History />}
        </Suspense>
      </main>
    </div>
  );
}

function OwnedPage({
  area,
  children,
}: {
  area?: Parameters<typeof ResourceBoundary>[0]["area"];
  children: ReactNode;
}) {
  const { id } = useParams();
  const [params] = useSearchParams();
  const candidates: [string, string | null][] = [
    ["run", id || (area === "data" ? params.get("run") : null)],
    ["language", area === "dialogue" ? params.get("run") : null],
    ["document", params.get("document")],
    ["source", area === "reports" ? params.get("source") : null],
    ["ecology", area === "reports" ? params.get("ecology") : null],
    ["run", area === "reports" ? params.get("temporal_run") : null],
    ["note", params.get("note")],
    ["world", params.get("world")],
    ["study", params.get("study")],
    ["assessment", params.get("assessment")],
    [
      params.get("tab") === "ecology" ? "ecology" : "evolution",
      params.get("campaign"),
    ],
    ["artifact", params.get("artifact")],
    ["innate", params.get("version")],
    [
      area === "data-management" ? "data_bundle" : "experiment_bundle",
      params.get("bundle"),
    ],
    [params.get("kind") || "artifact", params.get("resource")],
  ];
  const selected = candidates.find(([, identity]) => !!identity);
  return (
    <ResourceBoundary
      area={area}
      resource={selected ? { kind: selected[0], id: selected[1] } : undefined}
      force={area === "data-management" && params.get("view") === "storage"}
    >
      {children}
    </ResourceBoundary>
  );
}

function LabApp() {
  const preferences = usePreferences();
  const language = useLocale();
  useEffect(() => {
    document.documentElement.dataset.theme = preferences.theme;
    document.documentElement.lang = language;
  }, [preferences.theme, language]);
  const client = useQueryClient();
  const session = useQuery({
    queryKey: ["session"],
    queryFn: () => api("/session"),
    retry: false,
  });
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Project[]>("/projects"),
    enabled: !!session.data && can(session.data?.user, "projects.read"),
  });
  // Browsing starts globally. The old saved creation/workspace selection must
  // not silently hide data in other authorized projects.
  const [projectId, setProjectId] = useState("");
  const [createOpen, setCreateOpen] = useState(false),
    [name, setName] = useState(""),
    [newRun, setNewRun] = useState(false),
    [collapsed, setCollapsed] = useState(false),
    [mobileMenu, setMobileMenu] = useState(false),
    [switchOpen, setSwitchOpen] = useState(false),
    [logoutOpen, setLogoutOpen] = useState(false);
  const project = projects.data?.find((p) => p.id === projectId) ?? null;
  const create = useMutation({
    mutationFn: () => post<Project>("/projects", { name }),
    onSuccess: () => {
      setCreateOpen(false);
      setName("");
      client.invalidateQueries({ queryKey: ["projects"] });
    },
  });
  const logout = useMutation({
    mutationFn: () => post("/logout", {}),
    onSuccess: () => {
      clearNoteRecovery();
      clearReportRecovery();
      client.clear();
      window.location.reload();
    },
  });
  const location = useLocation();
  const [browseParams, setBrowseParams] = useSearchParams();
  const changeScope = (identity: string) => {
    setProjectId(identity);
    if (
      browseParams.has("project") &&
      ![
        "run",
        "document",
        "note",
        "world",
        "study",
        "assessment",
        "campaign",
        "artifact",
        "version",
        "bundle",
        "resource",
        "experiment",
      ].some((key) => browseParams.has(key)) &&
      !browseParams.has("action")
    ) {
      const next = new URLSearchParams(browseParams);
      if (identity) next.set("project", identity);
      else next.delete("project");
      setBrowseParams(next);
    }
  };
  const browsingPage = [
    "/research",
    "/research-records",
    "/studies",
    "/worlds",
    "/dialogue",
    "/compare",
    "/data",
    "/models",
    "/notes",
    "/reports",
    "/data-management",
  ].includes(location.pathname);
  useEffect(() => {
    setPreferenceUser(session.data?.user?.id ?? null);
  }, [session.data?.user?.id]);
  useEffect(() => {
    if (session.data?.user?.csrf) setCsrf(session.data.user.csrf);
  }, [session.data]);
  if (session.isPending) return <Loading />;
  if (session.error) {
    if (session.error instanceof ApiError && session.error.status === 401) {
      if (location.pathname === "/docs")
        return (
          <Suspense fallback={<Loading />}>
            <Documentation />
          </Suspense>
        );
      return (
        <LoginPage
          onSuccess={() => client.invalidateQueries({ queryKey: ["session"] })}
        />
      );
    }
    return (
      <div className="connection-page">
        <Brand />
        <h1>{t("工作台暂时无法连接")}</h1>
        <ErrorBox error={session.error} />
        <p>{t("确认 ThreeMind 服务和数据库已启动。")}</p>
        <Button onClick={() => session.refetch()}>{t("重新连接")}</Button>
      </div>
    );
  }
  return (
    <Workspace.Provider
      value={{
        project,
        projects: projects.data ?? [],
        user: session.data?.user,
        selectProject: setProjectId,
      }}
    >
      <div className={`app-shell ${collapsed ? "collapsed" : ""}`}>
        <aside className="sidebar">
          <Link to="/" className="brand-link">
            <Brand />
          </Link>
          {browsingPage && (
            <div className="project-picker">
              <span className="nav-label">{t("浏览范围")}</span>
              <div>
                <select
                  aria-label={t("浏览范围")}
                  value={project?.id ?? ""}
                  onChange={(e) => changeScope(e.target.value)}
                >
                  <option value="">{t("全部项目")}</option>
                  {projects.data?.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <button
                  className="icon-button"
                  aria-label={t("新建研究项目")}
                  disabled={!can(session.data?.user, "projects.create")}
                  onClick={() => setCreateOpen(true)}
                >
                  <Plus size={16} />
                </button>
              </div>
            </div>
          )}
          <Navigation />
          <div className="sidebar-footer">
            <div className="user-row">
              <span className="avatar">
                {session.data?.user.username?.slice(0, 1).toUpperCase()}
              </span>
              <div>
                {session.data?.user.username}
                <small>
                  {session.data?.mode === "workstation"
                    ? t("本地工作站")
                    : t("研究平台")}
                </small>
              </div>
              {session.data?.user && (
                <button
                  className="icon-button"
                  aria-label={t("退出登录")}
                  onClick={() => setLogoutOpen(true)}
                >
                  <LogOut size={16} />
                </button>
              )}
            </div>
          </div>
        </aside>
        <div className="main-shell">
          <header className="topbar">
            <div>
              <button
                className="icon-button mobile-menu-button"
                aria-label={t("打开导航菜单")}
                aria-expanded={mobileMenu}
                onClick={() => setMobileMenu(true)}
              >
                <Menu size={21} />
              </button>
              <button
                className="icon-button sidebar-toggle"
                aria-label={t("切换侧栏")}
                onClick={() => setCollapsed((v) => !v)}
              >
                {collapsed ? (
                  <PanelLeftOpen size={18} />
                ) : (
                  <PanelLeftClose size={18} />
                )}
              </button>
              {browsingPage && (
                <button
                  className="icon-button project-switch-button"
                  aria-label={t("切换浏览范围")}
                  title={project?.name ?? t("全部项目")}
                  onClick={() => setSwitchOpen(true)}
                >
                  <FolderOpen size={18} />
                </button>
              )}
              <span className="breadcrumb">
                {browsingPage ? (project?.name ?? t("全部项目")) : "ThreeMind"}
                <span>/</span>
                {t(
                  navigation.find(
                    ([path]) =>
                      path !== "/" &&
                      (location.pathname === path ||
                        location.pathname.startsWith(path + "/")),
                  )?.[1] ?? "意识工作台",
                )}
              </span>
            </div>
            <div>
              <span className="connection-indicator">
                <i />
                {t("数据已连接")}
              </span>
              <NotificationBell />
              <LanguagePicker compact />
              <Button
                variant="primary small"
                onClick={() => setNewRun(true)}
                disabled={!can(session.data?.user, "runs.create")}
              >
                <Plus size={15} />
                {t("新建意识")}
              </Button>
            </div>
          </header>
          <main className="page">
            {browsingPage && <ErrorBox error={projects.error} />}
            <AccessBoundary
              action={
                location.pathname.startsWith("/runs/")
                  ? "runs.read"
                  : (navigation.find(
                      ([path]) =>
                        path !== "/" &&
                        (location.pathname === path ||
                          location.pathname.startsWith(path + "/")),
                    )?.[3] ?? "menu.workbench")
              }
            >
              <Suspense fallback={<Loading />}>
                <Routes>
                  <Route path="/" element={<Workbench />} />
                  <Route
                    path="/research"
                    element={<GlobalOverview onNew={() => setNewRun(true)} />}
                  />
                  <Route path="/projects" element={<ProjectsPage />} />
                  <Route
                    path="/projects/:id/tools/:area"
                    element={<ProjectTools />}
                  />
                  <Route
                    path="/runs/:id"
                    element={
                      <OwnedPage>
                        <RunPage />
                      </OwnedPage>
                    }
                  />
                  <Route path="/kernels" element={<Kernels />} />
                  <Route
                    path="/studies"
                    element={
                      <OwnedPage area="studies">
                        <Studies />
                      </OwnedPage>
                    }
                  />
                  <Route
                    path="/research-records"
                    element={<ResearchRecords />}
                  />
                  <Route
                    path="/worlds"
                    element={
                      <OwnedPage area="worlds">
                        <Worlds />
                      </OwnedPage>
                    }
                  />
                  <Route
                    path="/dialogue"
                    element={
                      <OwnedPage area="dialogue">
                        <Dialogue />
                      </OwnedPage>
                    }
                  />
                  <Route
                    path="/dialogue/replay"
                    element={
                      <OwnedPage area="models">
                        <LanguageReplayPage />
                      </OwnedPage>
                    }
                  />
                  <Route
                    path="/compare"
                    element={
                      <OwnedPage area="compare">
                        <Studies compare />
                      </OwnedPage>
                    }
                  />
                  <Route
                    path="/data"
                    element={
                      <OwnedPage area="data">
                        <DataPage />
                      </OwnedPage>
                    }
                  />
                  <Route
                    path="/data-management"
                    element={
                      <OwnedPage area="data-management">
                        <DataManagement />
                      </OwnedPage>
                    }
                  />
                  <Route
                    path="/models"
                    element={
                      <OwnedPage area="models">
                        <ModelsPage />
                      </OwnedPage>
                    }
                  />
                  <Route
                    path="/notes"
                    element={
                      <OwnedPage area="notes">
                        <Notes />
                      </OwnedPage>
                    }
                  />
                  <Route
                    path="/reports"
                    element={
                      <OwnedPage area="reports">
                        <Reports />
                      </OwnedPage>
                    }
                  />
                  <Route path="/docs" element={<Documentation />} />
                  <Route path="/settings" element={<Settings />} />
                  <Route path="/admin" element={<Administration />} />
                  <Route path="*" element={<Workbench />} />
                </Routes>
              </Suspense>
            </AccessBoundary>
          </main>
        </div>
      </div>
      <Modal
        open={mobileMenu}
        onOpenChange={setMobileMenu}
        title={t("导航菜单")}
        description={project?.name ?? "ThreeMind"}
      >
        <div className="mobile-navigation">
          <Navigation onNavigate={() => setMobileMenu(false)} />
          {browsingPage && (
            <div className="mobile-navigation-footer">
              <Button
                onClick={() => {
                  setMobileMenu(false);
                  setSwitchOpen(true);
                }}
              >
                <FolderOpen size={19} />
                {t("切换浏览范围")}
              </Button>
            </div>
          )}
        </div>
      </Modal>
      <Modal
        open={switchOpen}
        onOpenChange={setSwitchOpen}
        title={t("切换浏览范围")}
        description={t("默认浏览全部有权访问的项目，也可按项目筛选。")}
      >
        <Field label={t("研究项目")}>
          <select
            value={project?.id ?? ""}
            onChange={(e) => {
              changeScope(e.target.value);
              setSwitchOpen(false);
            }}
          >
            <option value="">{t("全部项目")}</option>
            {projects.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </Field>
        <Button
          disabled={!can(session.data?.user, "projects.create")}
          onClick={() => {
            setSwitchOpen(false);
            setCreateOpen(true);
          }}
        >
          <Plus size={16} />
          {t("新建研究项目")}
        </Button>
        {session.data?.user && (
          <Button
            onClick={() => {
              setSwitchOpen(false);
              setLogoutOpen(true);
            }}
          >
            {t("退出登录")}
          </Button>
        )}
      </Modal>
      <Modal
        open={createOpen}
        onOpenChange={setCreateOpen}
        title={t("新建研究项目")}
        description={t("项目将集中保存模型、实验协议、运行记录和研究证据。")}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <Field label={t("项目名称")}>
            <input
              autoFocus
              required
              maxLength={120}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("例如：持续可塑性与记忆保持")}
            />
          </Field>
          <ErrorBox error={create.error} />
          <div className="form-actions">
            <Button type="button" onClick={() => setCreateOpen(false)}>
              {t("取消")}
            </Button>
            <Button variant="primary" disabled={create.isPending}>
              {t("创建项目")}
            </Button>
          </div>
        </form>
      </Modal>
      {logoutOpen && (
        <LogoutDialog
          close={() => setLogoutOpen(false)}
          logout={logout.mutateAsync}
        />
      )}
      <NewRun open={newRun} onOpenChange={setNewRun} />
    </Workspace.Provider>
  );
}
