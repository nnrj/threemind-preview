import { t } from "./i18n";
import {
  createContext,
  useContext,
  useState,
  lazy,
  Suspense,
  type ReactNode,
  type FormEvent,
} from "react";
import * as Dialog from "@radix-ui/react-dialog";
import {
  X,
  AlertCircle,
  LoaderCircle,
  ArrowUpRight,
  Plus,
  Settings2,
  FolderPen,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  statuses,
  type Project,
  type Run,
  timeLabel,
  numberLabel,
} from "./api";
const JsonEditor = lazy(() => import("./JsonEditor"));

export const Workspace = createContext<{
  project: Project | null;
  projects: Project[];
  user: any;
  selectProject?: (identity: string) => void;
}>({ project: null, projects: [], user: null });
export const useWorkspace = () => useContext(Workspace);
export function Button({
  children,
  variant = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: string }) {
  return (
    <button className={`button ${variant}`} {...props}>
      {children}
    </button>
  );
}
export function Badge({ status }: { status: string }) {
  return (
    <span className={`badge ${status}`}>
      <i />
      {statuses[status] ? t(statuses[status]) : status}
    </span>
  );
}
export function ErrorBox({ error }: { error: unknown }) {
  return error ? (
    <div className="error-box" role="alert">
      <AlertCircle size={17} />
      <span>{error instanceof Error ? error.message : String(error)}</span>
    </div>
  ) : null;
}
export function Loading() {
  return (
    <div className="loading">
      <LoaderCircle size={20} className="spin" />
      {t("正在读取研究数据…")}
    </div>
  );
}
export function Empty({
  title,
  detail,
  action,
}: {
  title: string;
  detail: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-mark">◌</div>
      <h3>{title}</h3>
      <p>{detail}</p>
      {action}
    </div>
  );
}
export function PageTitle({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="page-actions">{actions}</div>
    </div>
  );
}
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
  wide = false,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content
          className={`modal ${wide ? "modal-wide" : ""}`}
          onEscapeKeyDown={(event) => {
            const target = event.target;
            const search =
              target instanceof Element
                ? target.closest(".cm-editor")?.querySelector(".cm-search")
                : null;
            if (search) {
              // Radix listens on document capture; let Escape close the search
              // panel without also discarding the enclosing configuration form.
              event.preventDefault();
              search
                .querySelector<HTMLButtonElement>('[name="close"]')
                ?.click();
            }
          }}
        >
          <Dialog.Title>{title}</Dialog.Title>
          <Dialog.Description>{description}</Dialog.Description>
          <Dialog.Close
            className="icon-button modal-close"
            aria-label={t("关闭")}
          >
            <X size={18} />
          </Dialog.Close>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function RunTable({ runs }: { runs: Run[] }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>{t("运行 / 模型")}</th>
            <th>{t("执行状态")}</th>
            <th>{t("模拟时间")}</th>
            <th>{t("节点 / 连接")}</th>
            <th>{t("数据版本")}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id}>
              <td>
                <Link className="table-title" to={`/runs/${run.id}`}>
                  {run.name}
                </Link>
                <small>
                  {run.spec.environment === "mujoco"
                    ? t("模拟物理环境")
                    : run.spec.environment === "host"
                      ? t("宿主物理遥测")
                      : run.spec.environment === "replay"
                        ? t("记录输入重放")
                        : run.spec.environment === "ambient"
                          ? t("合成环境场")
                          : run.spec.environment === "world"
                            ? t("可配置物理世界与躯体")
                            : t("手动输入")}{" "}
                  · seed {run.spec.seed}
                </small>
              </td>
              <td>
                <Badge status={run.status} />
              </td>
              <td className="mono">{timeLabel(run.time_us)}</td>
              <td>
                {numberLabel(run.metrics.nodes, 0)}{" "}
                <span className="muted">/</span>{" "}
                {numberLabel(run.metrics.edges, 0)}
              </td>
              <td className="mono">r{run.revision}</td>
              <td>
                <Link
                  className="icon-button"
                  aria-label={t("档案 {name}", { name: run.name })}
                  title={t("名称、标签与归档")}
                  to={`/runs/${run.id}?metadata=1`}
                >
                  <FolderPen size={17} />
                </Link>
                <Link
                  className="icon-button"
                  aria-label={t("配置 {name}", { name: run.name })}
                  title={t("查看与编辑配置")}
                  to={`/runs/${run.id}?configure=1`}
                >
                  <Settings2 size={17} />
                </Link>
                <Link
                  className="icon-button"
                  aria-label={t("打开 {name}", { name: run.name })}
                  to={`/runs/${run.id}`}
                >
                  <ArrowUpRight size={17} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: ReactNode;
  detail: string;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}
export function CodeEditor({
  value,
  onChange,
  rows = 8,
  readOnly = false,
  label,
}: {
  value: string;
  onChange: (v: string) => void;
  rows?: number;
  readOnly?: boolean;
  label?: string;
}) {
  return (
    <Suspense
      fallback={<div className="editor-loading">{t("正在加载编辑器…")}</div>}
    >
      <JsonEditor
        value={value}
        onChange={onChange}
        rows={rows}
        readOnly={readOnly}
        label={label}
      />
    </Suspense>
  );
}
