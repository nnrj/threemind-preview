import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Network, Plus, FolderOpen, ArrowRight } from "lucide-react";
import { api, timeLabel } from "./api";
import { t, useLocale } from "./i18n";
import {
  Button,
  ErrorBox,
  Field,
  Loading,
  Modal,
  PageTitle,
  Badge,
  useWorkspace,
} from "./ui";
import { NewRun } from "./research";
import "./workbench.css";
import { can } from "./access";

export default function ConsciousnessWorkbench() {
  useLocale();
  const workspace = useWorkspace(),
    navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [creating, setCreating] = useState(false);
  const [opening, setOpening] = useState(params.get("open") === "1");
  const [search, setSearch] = useState("");
  const [project, setProject] = useState("");
  const [archived, setArchived] = useState(false);
  const [offset, setOffset] = useState(0);
  const recent = useQuery({
    queryKey: ["workbench-recent"],
    queryFn: () =>
      api("/browse/resources?kinds=run&archived=active&limit=6&offset=0"),
    enabled: can(workspace.user, "runs.read"),
  });
  const query = new URLSearchParams({
    kinds: "run",
    archived: archived ? "all" : "active",
    q: search,
    limit: "30",
    offset: String(offset),
  });
  if (project) query.set("project", project);
  const choices = useQuery({
    queryKey: ["workbench-open", query.toString()],
    queryFn: () => api(`/browse/resources?${query}`),
    enabled: opening && can(workspace.user, "runs.read"),
  });
  const open = (row: any) =>
    navigate(
      `/runs/${row.id}?project=${encodeURIComponent(row.project_id)}&view=network`,
    );
  const closePicker = (value: boolean) => {
    setOpening(value);
    if (!value && params.get("open")) setParams({}, { replace: true });
  };
  const rowStatus = (row: any) =>
    row.details?.revision === 0 && row.status === "paused" ? (
      <span className="badge paused">
        <i />
        {t("未启动")}
      </span>
    ) : (
      <Badge status={row.status || row.details?.status || "unknown"} />
    );
  return (
    <div className="consciousness-workbench">
      <PageTitle
        eyebrow="CONSCIOUSNESS WORKBENCH"
        title={t("意识工作台")}
        description={t("创建、打开和观察意识。运行与刺激由你明确控制。")}
        actions={
          <Link className="button" to="/research">
            {t("研究概览")}
            <ArrowRight size={15} />
          </Link>
        }
      />
      <section className="consciousness-player-empty">
        <Network size={68} aria-hidden="true" />
        <h2>{t("打开一份意识，观察它的变化")}</h2>
        <p>
          {t(
            "这里展示意识网络、属性、刺激与读出。进入页面不会自动启动意识或开启设备。",
          )}
        </p>
        <div className="consciousness-player-buttons">
          <Button
            variant="primary"
            disabled={!can(workspace.user, "runs.create")}
            onClick={() => setCreating(true)}
          >
            <Plus size={18} />
            {t("新建意识")}
          </Button>
          <Button
            disabled={!can(workspace.user, "runs.read")}
            onClick={() => setOpening(true)}
          >
            <FolderOpen size={18} />
            {t("打开意识")}
          </Button>
        </div>
      </section>
      <section className="panel workbench-recent">
        <div className="panel-heading">
          <h2>{t("最近创建的意识")}</h2>
          <Button
            disabled={!can(workspace.user, "runs.read")}
            onClick={() => setOpening(true)}
          >
            {t("查看全部意识")}
          </Button>
        </div>
        {recent.isPending && can(workspace.user, "runs.read") ? (
          <Loading />
        ) : (
          <div className="workbench-recent-grid">
            {(recent.data?.rows || []).map((row: any) => (
              <button
                type="button"
                className="workbench-recent-item"
                key={row.id}
                onClick={() => open(row)}
              >
                <strong>{row.title}</strong>
                <span>
                  {t("所属项目")}：{row.project_name}
                </span>
                <span>
                  {row.details?.kernel} ·{" "}
                  {timeLabel(row.details?.time_us || "0")}
                </span>
                {rowStatus(row)}
              </button>
            ))}
          </div>
        )}
        {!recent.isPending && !recent.data?.rows?.length && !recent.error && (
          <p>{t("尚无意识。可以先编辑新建配置，再选择保存项目。")}</p>
        )}
        <ErrorBox error={recent.error} />
      </section>
      <NewRun open={creating} onOpenChange={setCreating} />
      <Modal
        open={opening}
        onOpenChange={closePicker}
        wide
        title={t("打开意识")}
        description={t("打开只查看原实例，不自动运行、克隆或恢复到历史状态。")}
      >
        <div className="workbench-open-filters">
          <Field label={t("搜索意识")}>
            <input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setOffset(0);
              }}
            />
          </Field>
          <Field label={t("项目筛选")}>
            <select
              value={project}
              onChange={(e) => {
                setProject(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">{t("全部有权访问的项目")}</option>
              {workspace.projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </Field>
          <label>
            <input
              type="checkbox"
              checked={archived}
              onChange={(e) => {
                setArchived(e.target.checked);
                setOffset(0);
              }}
            />
            {t("包含已归档")}
          </label>
        </div>
        {choices.isPending ? (
          <Loading />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t("意识名称")}</th>
                  <th>{t("所属项目")}</th>
                  <th>{t("状态")}</th>
                  <th>{t("内核")}</th>
                  <th>{t("操作")}</th>
                </tr>
              </thead>
              <tbody>
                {(choices.data?.rows || []).map((row: any) => (
                  <tr key={row.id}>
                    <td>{row.title}</td>
                    <td>{row.project_name}</td>
                    <td>{rowStatus(row)}</td>
                    <td>{row.details?.kernel}</td>
                    <td>
                      <Button onClick={() => open(row)}>{t("打开")}</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!choices.isPending &&
          !choices.error &&
          !choices.data?.rows?.length && (
            <p>{t("此范围内没有意识。请调整筛选，或新建意识。")}</p>
          )}
        <ErrorBox error={choices.error} />
        <div className="pagination">
          <Button
            disabled={!offset || choices.isFetching}
            onClick={() => setOffset((v) => v - 30)}
          >
            {t("上一页")}
          </Button>
          <span>{Math.floor(offset / 30) + 1}</span>
          <Button
            disabled={!choices.data?.more || choices.isFetching}
            onClick={() => setOffset((v) => v + 30)}
          >
            {t("下一页")}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
