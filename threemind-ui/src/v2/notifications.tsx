import { ProjectNotificationRules } from "./notificationSettings";
import { can } from "./access";
import { t, locale } from "./i18n";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Check, Mail, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import { api, post, projectPath } from "./api";
import {
  Button,
  CodeEditor,
  Empty,
  ErrorBox,
  Field,
  Loading,
  useWorkspace,
} from "./ui";
import { parseJson } from "./JsonEditor";
import ExecutionHealth, { ExecutionHealthFields } from "./ExecutionHealth";

const kinds: Record<string, string> = {
  structure_recurrence: "结构复现",
  run_completed: "运行时长完成",
  run_failed: "运行失败",
  run_dead: "模型活动耗尽",
  run_blocked: "运行需要处理",
  export_ready: "导出文件就绪",
  analysis_ready: "统计分析完成",
  job_failed: "后台任务失败",
  execution_health: "执行资源或进度预警",
  test: "通知测试",
};
const states: Record<string, string> = {
  disabled: "仅站内记录",
  queued: "邮件待发送",
  sending: "邮件发送中",
  sent: "邮件服务已接收",
  partial: "部分收件人被拒绝",
  failed: "邮件发送失败",
  uncertain: "邮件结果不确定",
  cancelled: "邮件已取消",
  skipped: "邮件未发送",
};
const reasons: Record<string, string> = {
  rolling_24h_limit: "已达到滚动 24 小时发送上限",
  cooldown: "处于邮件冷却期",
  policy_or_permission_changed: "规则版本或操作者权限已改变",
  endpoint_not_allowed: "此邮件端点未获部署许可",
  worker_replaced_after_dispatch: "发送期间 worker 被接管，未自动重发",
  worker_recovery_exhausted: "worker 恢复次数已耗尽",
  worker_failure: "邮件任务未完成，请检查部署配置",
  resend_connection_or_response: "连接或响应未能确认，未自动重发",
  resend_response_limit: "响应超过大小上限，未自动重发",
  resend_missing_receipt: "服务响应没有有效接收编号",
  smtp_authentication: "SMTP 认证失败",
  smtp_setup: "SMTP 连接、问候或 TLS 协商未完成",
  smtp_rejected: "SMTP 服务拒绝了邮件",
  smtp_connection_or_response: "SMTP 连接或响应未能确认，未自动重发",
  smtp_partial_recipient_refusal: "SMTP 服务仅接受部分收件人",
};

function PolicyEditor({
  row,
  base,
  onSaved,
}: {
  row: any;
  base: string;
  onSaved: (row: any) => void;
}) {
  const [config, setConfig] = useState<Record<string, any>>(() =>
    structuredClone(row.config),
  );
  const [recipients, setRecipients] = useState<string>(
    row.config.recipients.join("\n"),
  );
  const [json, setJson] = useState(false),
    [text, setText] = useState("");
  const [secret, setSecret] = useState({
    api_key: "",
    smtp_password: "",
    clear_api_key: false,
    clear_smtp_password: false,
  });
  const [feedback, setFeedback] = useState(""),
    [error, setError] = useState<unknown>(null),
    [checking, setChecking] = useState(false);
  const set = (key: string, value: any) => {
    setConfig((c) => ({ ...c, [key]: value }));
    setFeedback("");
  };
  const formConfig = () => ({
    ...config,
    recipients: recipients
      .split(/[\n,;]+/)
      .map((s) => s.trim())
      .filter(Boolean),
  });
  const selected = () => (json ? parseJson(text) : formConfig());
  async function validate(toForm = false) {
    setChecking(true);
    setError(null);
    setFeedback("");
    try {
      const result = await post(base + "/validate", selected());
      setConfig(result.config);
      setRecipients(result.config.recipients.join("\n"));
      if (toForm) setJson(false);
      setFeedback(t("配置校验通过。"));
    } catch (e) {
      setError(e);
    } finally {
      setChecking(false);
    }
  }
  const save = useMutation({
    mutationFn: () =>
      api(base + "/settings", {
        method: "PUT",
        body: JSON.stringify({
          config: selected(),
          expected_revision: row.revision,
          ...secret,
        }),
      }),
    onSuccess: (row) => {
      setSecret({
        api_key: "",
        smtp_password: "",
        clear_api_key: false,
        clear_smtp_password: false,
      });
      onSaved(row);
    },
  });
  const numeric = (
    key: string,
    label: string,
    min: number,
    max: number,
    step = "1",
  ) => (
    <Field label={t(label)} key={key}>
      <input
        aria-label={t(label)}
        type="number"
        value={config[key]}
        min={min}
        max={max}
        step={step}
        required
        onChange={(e) => set(key, Number(e.target.value))}
      />
    </Field>
  );
  return (
    <form
      className="panel notification-policy"
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        save.mutate();
      }}
    >
      <fieldset disabled={save.isPending || checking}>
        <div className="panel-heading">
          <div>
            <h2>{t("通知规则")}</h2>
            <p>
              {t(
                "通知来自已提交的工具事件。规则变更会取消旧规则尚未发送的邮件；已发出的请求不能撤回。",
              )}
            </p>
          </div>
          <button
            className="text-link"
            type="button"
            disabled={checking || save.isPending}
            onClick={() => {
              if (json) void validate(true);
              else {
                setText(JSON.stringify(formConfig(), null, 2));
                setJson(true);
                setError(null);
              }
            }}
          >
            {json ? t("切换到图形配置") : t("切换到 JSON 编辑")}
          </button>
        </div>
        {json ? (
          <>
            <div className="json-actions">
              <button
                type="button"
                className="text-link"
                onClick={() => {
                  try {
                    setText(JSON.stringify(parseJson(text), null, 2));
                    setError(null);
                  } catch (e) {
                    setError(e);
                  }
                }}
              >
                {t("格式化")}
              </button>
              <button
                type="button"
                className="text-link"
                disabled={checking}
                onClick={() => void validate()}
              >
                {t("校验")}
              </button>
            </div>
            <CodeEditor
              label={t("通知规则 JSON")}
              readOnly={save.isPending || checking}
              value={text}
              onChange={setText}
              rows={17}
            />
          </>
        ) : (
          <>
            <label className="check">
              <input
                type="checkbox"
                checked={config.enabled}
                onChange={(e) => set("enabled", e.target.checked)}
              />
              {t("启用项目通知")}
            </label>
            <div className="notification-events">
              {Object.keys(config.events).map((key) => (
                <label className="check" key={key}>
                  <input
                    type="checkbox"
                    checked={config.events[key]}
                    onChange={(e) =>
                      set("events", {
                        ...config.events,
                        [key]: e.target.checked,
                      })
                    }
                  />
                  {t(kinds[key] ?? key)}
                </label>
              ))}
            </div>
            <ExecutionHealthFields
              base={base}
              value={config.execution_health}
              onChange={(value) => set("execution_health", value)}
            />
            <label className="check">
              <input
                type="checkbox"
                checked={config.email_enabled}
                onChange={(e) => set("email_enabled", e.target.checked)}
              />
              {t("同时发送邮件")}
            </label>
            <p className="footnote">
              {t(
                "关闭邮件时仍可保留站内通知。邮件被限流或发送失败时，事件摘要仍保留。",
              )}
            </p>
            <div className="form-grid">
              <Field label={t("邮件服务")}>
                <select
                  aria-label={t("邮件服务")}
                  value={config.transport}
                  onChange={(e) => set("transport", e.target.value)}
                >
                  <option value="resend">Resend</option>
                  <option value="smtp">SMTP</option>
                </select>
              </Field>
              <Field label={t("邮件语言")}>
                <select
                  aria-label={t("邮件语言")}
                  value={config.language}
                  onChange={(e) => set("language", e.target.value)}
                >
                  <option value="follow-ui">{t("使用规则的参考语言")}</option>
                  <option value="zh-CN">{t("简体中文")}</option>
                  <option value="en">English</option>
                </select>
              </Field>
              {config.language === "follow-ui" && (
                <Field
                  label={t("后台参考语言")}
                  hint={t(
                    "供没有浏览器在线时使用；切换界面语言不会自动改写已保存的项目通知规则。",
                  )}
                >
                  <select
                    aria-label={t("后台参考语言")}
                    value={config.ui_language}
                    onChange={(e) => set("ui_language", e.target.value)}
                  >
                    <option value="zh-CN">{t("简体中文")}</option>
                    <option value="en">English</option>
                  </select>
                  <button
                    type="button"
                    className="text-link"
                    onClick={() => set("ui_language", locale())}
                  >
                    {t("使用当前界面语言")}
                  </button>
                </Field>
              )}
              <Field label={t("发件人")}>
                <input
                  aria-label={t("发件人")}
                  value={config.sender}
                  maxLength={320}
                  required
                  onChange={(e) => set("sender", e.target.value)}
                  placeholder="ThreeMind <alerts@example.com>"
                />
              </Field>
              <Field
                label={t("收件人")}
                hint={t(
                  "每行一个地址，也可用逗号或分号分隔；所有收件人会在同一封邮件中可见。",
                )}
              >
                <textarea
                  aria-label={t("收件人")}
                  value={recipients}
                  onChange={(e) => setRecipients(e.target.value)}
                  rows={3}
                />
              </Field>
            </div>
            {config.transport === "smtp" && (
              <div className="form-grid">
                <Field label={t("SMTP 主机")}>
                  <input
                    aria-label={t("SMTP 主机")}
                    value={config.smtp_host}
                    onChange={(e) => set("smtp_host", e.target.value)}
                    placeholder="smtp.example.com"
                  />
                </Field>
                {numeric("smtp_port", "SMTP 端口", 1, 65535)}
                <Field label={t("SMTP 连接保护")}>
                  <select
                    aria-label={t("SMTP 连接保护")}
                    value={config.smtp_security}
                    onChange={(e) => set("smtp_security", e.target.value)}
                  >
                    <option value="starttls">STARTTLS</option>
                    <option value="tls">{t("TLS（直接加密）")}</option>
                    <option value="none">
                      {t("明文（仅工作站回环地址）")}
                    </option>
                  </select>
                </Field>
                <Field label={t("SMTP 用户名")}>
                  <input
                    aria-label={t("SMTP 用户名")}
                    value={config.smtp_username}
                    onChange={(e) => set("smtp_username", e.target.value)}
                    autoComplete="off"
                  />
                </Field>
              </div>
            )}
            <details className="configuration-advanced">
              <summary>{t("高级发送策略")}</summary>
              <div className="form-grid">
                {numeric("timeout_s", "连接与读取超时（秒）", 1, 30, "any")}
                {numeric("cooldown_s", "邮件冷却期（秒）", 0, 86400)}
                {numeric(
                  "daily_email_limit",
                  "滚动 24 小时邮件请求上限",
                  1,
                  10000,
                )}
              </div>
              <p className="footnote">
                {t(
                  "按发送请求次数计数，每次可包含多个收件人。超限请求不积压补发。后台跟随语言保留本次保存的选择。",
                )}
              </p>
            </details>
          </>
        )}
        <details className="notification-credentials" open={!json}>
          <summary>{t("发送凭据")}</summary>
          <p className="footnote">
            {t(
              "凭据在数据库中加密保存，留空保留。它们不进入规则 JSON、通知内容或版本历史。",
            )}
          </p>
          <div className="form-grid">
            {(["api_key", "smtp_password"] as const)
              .filter(
                (key) =>
                  json ||
                  key ===
                    (config.transport === "resend"
                      ? "api_key"
                      : "smtp_password"),
              )
              .map((key) => (
                <Field
                  key={key}
                  label={key === "api_key" ? "Resend API Key" : t("SMTP 密码")}
                  hint={
                    row[key === "api_key" ? "has_api_key" : "has_smtp_password"]
                      ? t("已配置；留空保留")
                      : t("尚未配置")
                  }
                >
                  <input
                    aria-label={
                      key === "api_key" ? "Resend API Key" : t("SMTP 密码")
                    }
                    type="password"
                    autoComplete="new-password"
                    value={secret[key]}
                    onChange={(e) =>
                      setSecret((s) => ({ ...s, [key]: e.target.value }))
                    }
                  />
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={
                        secret[
                          key === "api_key"
                            ? "clear_api_key"
                            : "clear_smtp_password"
                        ]
                      }
                      onChange={(e) =>
                        setSecret((s) => ({
                          ...s,
                          [key === "api_key"
                            ? "clear_api_key"
                            : "clear_smtp_password"]: e.target.checked,
                        }))
                      }
                    />
                    {key === "api_key"
                      ? t("清除 API Key")
                      : t("清除 SMTP 密码")}
                  </label>
                </Field>
              ))}
          </div>
        </details>
        <ErrorBox error={error || save.error} />
        {feedback && <p role="status">{t(feedback)}</p>}
        <div className="form-actions">
          <Button variant="primary" disabled={save.isPending || checking}>
            {t("保存通知设置")}
          </Button>
          <button
            type="button"
            className="text-link"
            disabled={checking}
            onClick={() => void validate()}
          >
            {t("校验配置")}
          </button>
          <span className="muted">
            {t("规则版本 ")}
            {row.revision}
            {t(" · 保存时始终校验")}
          </span>
        </div>
      </fieldset>
    </form>
  );
}

export function NotificationHistory({ base }: { base: string }) {
  const { project, user } = useWorkspace();
  const client = useQueryClient();
  const [before, setBefore] = useState<number | null>(null),
    [stack, setStack] = useState<(number | null)[]>([]),
    [unread, setUnread] = useState(false);
  const history = useQuery({
    queryKey: ["notifications", project?.id, user?.id, before, unread],
    queryFn: () =>
      api(
        `${base}?limit=30&unread=${unread}${before ? `&before=${before}` : ""}`,
      ),
    refetchInterval: before ? false : 5000,
    refetchIntervalInBackground: false,
  });
  const read = useMutation({
    mutationFn: (ids: string[]) => post(base + "/read", { ids }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["notifications"] });
      client.invalidateQueries({ queryKey: ["notification-unread"] });
    },
  });
  const rows: any[] = history.data?.items ?? [];
  return (
    <section className="panel notification-history">
      <div className="panel-heading">
        <div>
          <h2>{t("通知记录")}</h2>
          <p>
            {t("通知摘要保留当时的事实和规则版本；已读状态只对当前账号生效。")}
          </p>
        </div>
        <button
          className="icon-button"
          aria-label={t("刷新通知")}
          onClick={() => history.refetch()}
        >
          <RefreshCw size={16} />
        </button>
      </div>
      <div className="notification-history-actions">
        <label className="check">
          <input
            type="checkbox"
            checked={unread}
            onChange={(e) => {
              setUnread(e.target.checked);
              setBefore(null);
              setStack([]);
            }}
          />
          {t("仅看未读")}
        </label>
        <button
          className="text-link"
          disabled={read.isPending || !rows.some((r) => !r.read_at)}
          onClick={() =>
            read.mutate(rows.filter((r) => !r.read_at).map((r) => r.id))
          }
        >
          {t("本页标为已读")}
        </button>
      </div>
      <ErrorBox error={history.error || read.error} />
      {history.isLoading ? (
        <Loading />
      ) : !rows.length ? (
        <Empty
          title={t("暂无符合条件的通知")}
          detail={t(
            "启用通知后，新触发的工具事件会显示在这里；不会倒放旧历史发送邮件。",
          )}
        />
      ) : (
        <div className="notification-list">
          {rows.map((item) => (
            <article
              className={`notification-item ${item.read_at ? "" : "unread"}`}
              key={item.id}
            >
              <div className="notification-heading">
                <h3>{t(kinds[item.kind] ?? item.kind)}</h3>
                <span>
                  {new Date(item.created_at).toLocaleString(locale())}
                </span>
              </div>
              {item.facts.run_name && <strong>{item.facts.run_name}</strong>}
              {item.kind === "execution_health" && (
                <p>
                  {item.facts.facts.rule.label || item.facts.rule_id} ·{" "}
                  {item.facts.text[locale() === "en" ? "en" : "zh"]}{" "}
                  {item.facts.facts.value ?? t("证据不足")}{" "}
                  {item.facts.source.unit}
                </p>
              )}
              <div className="notification-details">
                <span
                  className={`badge ${item.email_status === "sent" ? "done" : ["failed", "uncertain", "partial"].includes(item.email_status) ? "failed" : "pending"}`}
                >
                  <Mail size={12} />
                  {t(states[item.email_status] ?? item.email_status)}
                </span>
                <span className="muted">
                  {t("规则 v")}
                  {item.policy_revision}
                </span>
                {!item.read_at && (
                  <span className="notice-unread">{t("未读")}</span>
                )}
              </div>
              {item.email_reason && (
                <p>
                  {(reasons[item.email_reason]
                    ? t(reasons[item.email_reason])
                    : null) ??
                    (item.email_reason.startsWith("resend_http_")
                      ? t("Resend 返回 HTTP {value0}", {
                          value0: String(item.email_reason.slice(12)),
                        })
                      : item.email_reason)}
                </p>
              )}
              <div className="notification-item-actions">
                {item.run_id && (
                  <Link
                    className="text-link"
                    to={`/runs/${item.run_id}${item.kind === "structure_recurrence" ? "?view=readouts" : ""}`}
                  >
                    {t("查看意识与证据")}
                  </Link>
                )}
                {item.facts.artifact_id && (
                  <Link className="text-link" to="/models?view=artifacts">
                    {t("查看导出文件")}
                  </Link>
                )}
                {!item.read_at && (
                  <button
                    className="text-link"
                    disabled={read.isPending}
                    onClick={() => read.mutate([item.id])}
                  >
                    <Check size={14} />
                    {t("标为已读")}
                  </button>
                )}
              </div>
              <details>
                <summary>{t("查看事件摘要")}</summary>
                <pre>{JSON.stringify(item.facts, null, 2)}</pre>
              </details>
            </article>
          ))}
        </div>
      )}
      <div className="pagination">
        <button
          className="button small"
          disabled={!stack.length}
          onClick={() => {
            setBefore(stack[stack.length - 1]);
            setStack((s) => s.slice(0, -1));
          }}
        >
          {t("上一页")}
        </button>
        <span>{t("第 {page} 页", { page: stack.length + 1 })}</span>
        <button
          className="button small"
          disabled={!history.data?.next}
          onClick={() => {
            setStack((s) => [...s, before]);
            setBefore(history.data.next);
          }}
        >
          {t("下一页")}
        </button>
      </div>
    </section>
  );
}

function Versions({ base }: { base: string }) {
  const [open, setOpen] = useState(false),
    [before, setBefore] = useState<number | null>(null);
  const data = useQuery({
    queryKey: ["notification-versions", base, before],
    queryFn: () =>
      api(base + `/versions?limit=20${before ? `&before=${before}` : ""}`),
    enabled: open,
  });
  return (
    <details
      className="panel notification-versions"
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>{t("规则变更历史")}</summary>
      <ErrorBox error={data.error} />
      {data.data?.items.map((row: any) => (
        <details key={row.revision}>
          <summary>
            v{row.revision} ·{" "}
            {new Date(row.created_at).toLocaleString(locale())}
          </summary>
          <pre>{JSON.stringify(row.config, null, 2)}</pre>
        </details>
      ))}
      {data.data?.next && (
        <button className="text-link" onClick={() => setBefore(data.data.next)}>
          {t("查看更早版本")}
        </button>
      )}
      {before && (
        <button className="text-link" onClick={() => setBefore(null)}>
          {t("返回最新版本")}
        </button>
      )}
    </details>
  );
}

export default function Notifications() {
  const {project,user}=useWorkspace(),[query,setQuery]=useSearchParams();
  const owner=!!project&&(project.role==="owner"||user?.superadmin)&&can(user,"projects.manage");
  const history=query.get("view")==="history"||!owner;
  if(!project)return <NotificationHistory base="/notifications"/>;
  const base=`${projectPath(project.id)}/notifications`;
  return <><div className="tabs"><button className={history?"active":""} onClick={()=>setQuery({view:"history"})}>{t("通知记录")}</button>{owner&&<button className={!history?"active":""} onClick={()=>setQuery({view:"rules"})}>{t("项目通知规则")}</button>}</div><ExecutionHealth base={base}/>{history?<NotificationHistory base={base}/>:<><ProjectNotificationRules projectId={project.id}/><Versions base={base}/></>}</>;
}
