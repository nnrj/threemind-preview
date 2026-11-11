import { parseJson } from "./JsonEditor";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "./api";
import {
  Button,
  CodeEditor,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Modal,
  useWorkspace,
} from "./ui";
import { t, messageKeys } from "./i18n";
const mailLabels: Record<string, string> = messageKeys({
  sender: "发件人",
  smtp_host: "SMTP 主机",
  smtp_username: "SMTP 用户名",
  smtp_port: "SMTP 端口",
  timeout_s: "超时（秒）",
  cooldown_s: "冷却间隔（秒）",
  daily_email_limit: "每天邮件上限",
});
const eventLabels: Record<string, string> = messageKeys({
  structure_recurrence: "结构复现",
  run_completed: "运行时长完成",
  run_failed: "运行失败",
  run_dead: "模型活动耗尽",
  run_blocked: "运行需要处理",
  export_ready: "导出文件就绪",
  analysis_ready: "统计分析完成",
  job_failed: "后台任务失败",
  execution_health: "执行资源或进度预警",
});
import { useAccess } from "./access";
import { NotificationHistory } from "./notifications";
import { ExecutionHealthFields } from "./ExecutionHealth";
const ruleKeys = [
  "enabled",
  "email_enabled",
  "language",
  "ui_language",
  "events",
  "execution_health",
  "recipients",
  "cooldown_s",
  "daily_email_limit",
];
export function ProjectNotificationRules({ projectId }: { projectId: string }) {
  const allowed = useAccess(),
    client = useQueryClient(),
    { project, user } = useWorkspace();
  const row = useQuery({
    queryKey: ["notification-settings", projectId],
    queryFn: () => api(`/projects/${projectId}/notifications/settings`),
  });
  const services = useQuery({
    queryKey: ["project-mail-services", projectId],
    queryFn: () => api(`/projects/${projectId}/notifications/services`),
  });
  if (row.isPending) return <Loading />;
  return (
    <>
      <ErrorBox error={row.error} />
      {row.data && (
        <RulesEditor
          key={`${projectId}:${row.data.revision}`}
          row={{ ...row.data, transports: services.data?.items || [] }}
          projectId={projectId}
          writable={
            allowed("projects.manage") &&
            (project?.role === "owner" || user?.superadmin)
          }
          saved={() =>
            client.invalidateQueries({
              queryKey: ["notification-settings", projectId],
            })
          }
        />
      )}
    </>
  );
}
function RulesEditor({
  row,
  projectId,
  writable,
  saved,
}: {
  row: any;
  projectId: string;
  writable: boolean;
  saved: () => void;
}) {
  const [rules, setRules] = useState<any>(() =>
    Object.fromEntries(
      ruleKeys
        .filter((k) => k in (row.rules || row.config))
        .map((k) => [k, structuredClone((row.rules || row.config)[k])]),
    ),
  );
  const [transport, setTransport] = useState(row.service_id || "");
  const [json, setJson] = useState(false),
    [text, setText] = useState("");
  const [error, setError] = useState<unknown>(null);
  const set = (key: string, value: any) =>
    setRules((old: any) => ({ ...old, [key]: value }));
  const save = useMutation({
    mutationFn: () =>
      api(`/projects/${projectId}/notifications/settings`, {
        method: "PUT",
        body: JSON.stringify({
          config: json ? parseJson(text) : rules,
          service_id: transport || null,
          expected_revision: row.revision,
        }),
      }),
    onSuccess: saved,
  });
  return (
    <form
      className="panel"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <h2>{t("项目通知规则")}</h2>
      <p>
        {t(
          "项目选择已授权的邮件服务，并保存自己的事件订阅与接收人。传输凭据在系统设置中维护。",
        )}
      </p>
      <fieldset disabled={!writable || save.isPending}>
        <Button
          type="button"
          onClick={() => {
            if (json) {
              try {
                setRules(parseJson(text));
                setJson(false);
                setError(null);
              } catch (error) {
                setError(error);
              }
            } else {
              setText(JSON.stringify(rules, null, 2));
              setJson(true);
            }
          }}
        >
          {json ? t("切换到图形配置") : t("切换到 JSON 编辑")}
        </Button>
        <Field label={t("邮件服务")}>
          <select
            value={transport}
            onChange={(e) => setTransport(e.target.value)}
          >
            <option value="">{t("仅站内通知")}</option>
            {(row.transports || []).map((item: any) => (
              <option key={item.id} value={item.id}>
                {item.name || item.config?.name || item.id}
              </option>
            ))}
          </select>
        </Field>
        {json ? (
          <CodeEditor
            label={t("项目通知规则 JSON")}
            value={text}
            rows={18}
            onChange={setText}
          />
        ) : (
          <>
            <label className="check">
              <input
                type="checkbox"
                checked={!!rules.enabled}
                onChange={(e) => set("enabled", e.target.checked)}
              />
              {t("启用通知")}
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={!!rules.email_enabled}
                onChange={(e) => set("email_enabled", e.target.checked)}
              />
              {t("发送邮件")}
            </label>
            <Field label={t("邮件语言")}>
              <select
                value={rules.language || "zh"}
                onChange={(e) => set("language", e.target.value)}
              >
                <option value="zh">{t("中文")}</option>
                <option value="en">English</option>
              </select>
            </Field>
            <Field label={t("邮件接收人")}>
              <textarea
                rows={3}
                value={(rules.recipients || []).join("\n")}
                onChange={(e) =>
                  set(
                    "recipients",
                    e.target.value
                      .split(/[\n,;]+/)
                      .map((v) => v.trim())
                      .filter(Boolean),
                  )
                }
              />
            </Field>
            {["cooldown_s", "daily_email_limit"].map((key) => (
              <Field label={t(mailLabels[key] || key)} key={key}>
                <input
                  type="number"
                  min={0}
                  value={rules[key] ?? 0}
                  onChange={(e) => set(key, Number(e.target.value))}
                />
              </Field>
            ))}
            <h3>{t("事件订阅")}</h3>
            {Object.entries(rules.events || {}).map(([key, value]) => (
              <label className="check" key={key}>
                <input
                  type="checkbox"
                  checked={!!value}
                  onChange={(e) =>
                    set("events", { ...rules.events, [key]: e.target.checked })
                  }
                />
                {t(eventLabels[key] || key)}
              </label>
            ))}
            {rules.execution_health && (
              <ExecutionHealthFields
                base={`/projects/${projectId}/notifications`}
                value={rules.execution_health}
                onChange={(value: any) => set("execution_health", value)}
              />
            )}
          </>
        )}
        <ErrorBox error={error || save.error} />
        {writable && <Button variant="primary">{t("保存通知规则")}</Button>}
      </fieldset>
    </form>
  );
}
export default function NotificationSettings() {
  const allowed = useAccess(),
    client = useQueryClient(),
    [params, setParams] = useSearchParams();
  const history = params.get("view") === "history" || !allowed("services.read");
  const query = useQuery({
    queryKey: ["notification-transports"],
    queryFn: () => api("/services/notifications"),
    enabled: allowed("services.read"),
  });
  const [editing, setEditing] = useState<any>(null);
  return (
    <>
      <div className="tabs">
        <button
          className={history ? "active" : ""}
          onClick={() =>
            setParams({ section: "notifications", view: "history" })
          }
        >
          {t("我的通知")}
        </button>
        {allowed("services.read") && (
          <button
            className={!history ? "active" : ""}
            onClick={() =>
              setParams({ section: "notifications", view: "services" })
            }
          >
            {t("宿主邮件服务")}
          </button>
        )}
      </div>
      {history ? (
        <NotificationHistory base="/notifications" />
      ) : (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>{t("宿主邮件服务")}</h2>
              <p>
                {t(
                  "这里配置传输和凭据。项目在自己的配置中选择服务与通知规则。",
                )}
              </p>
            </div>
            {allowed("services.manage") && (
              <Button
                onClick={() =>
                  setEditing({ config: query.data?.defaults || {}, name: "" })
                }
              >
                {t("添加邮件服务")}
              </Button>
            )}
          </div>
          <ErrorBox error={query.error} />
          {query.isPending ? (
            <Loading />
          ) : (
            (query.data?.items || []).map((row: any) => (
              <article className="service-row" key={row.id}>
                <div>
                  <strong>{row.name}</strong>
                  <p>
                    {row.config.transport} · r{row.revision}
                  </p>
                </div>
                <Button onClick={() => setEditing(row)}>
                  {allowed("services.manage") ? t("查看与编辑") : t("查看")}
                </Button>
              </article>
            ))
          )}
          {query.data && !query.data.items?.length && (
            <Empty
              title={t("尚无邮件服务")}
              detail={t("没有邮件服务也可保留站内通知。")}
            />
          )}
        </section>
      )}
      {editing && (
        <TransportEditor
          row={editing}
          writable={allowed("services.manage")}
          close={() => setEditing(null)}
          saved={() => {
            client.invalidateQueries({ queryKey: ["notification-transports"] });
            setEditing(null);
          }}
        />
      )}
    </>
  );
}
function TransportEditor({
  row,
  writable,
  close,
  saved,
}: {
  row: any;
  writable: boolean;
  close: () => void;
  saved: () => void;
}) {
  const [name, setName] = useState(row.name || ""),
    [config, setConfig] = useState<any>(
      Object.fromEntries(
        Object.entries(row.config || {}).filter(([key]) =>
          [
            "transport",
            "sender",
            "smtp_host",
            "smtp_port",
            "smtp_security",
            "smtp_username",
            "timeout_s",
          ].includes(key),
        ),
      ),
    ),
    [key, setKey] = useState(""),
    [password, setPassword] = useState("");
  const { projects } = useWorkspace();
  const [grants, setGrants] = useState<string[]>(
    row.project_ids || (row.grants || []).map((g: any) => g.project_id),
  );
  const [clearKey, setClearKey] = useState(false),
    [clearPassword, setClearPassword] = useState(false);
  const set = (key: string, value: any) =>
    setConfig((old: any) => ({ ...old, [key]: value }));
  const save = useMutation({
    mutationFn: () =>
      api(`/services/notifications${row.id ? `/${row.id}` : ""}`, {
        method: row.id ? "PUT" : "POST",
        body: JSON.stringify({
          name,
          config,
          project_ids: grants,
          expected_revision: row.revision || 0,
          api_key: key,
          smtp_password: password,
          clear_api_key: clearKey,
          clear_smtp_password: clearPassword,
        }),
      }),
    onSuccess: saved,
  });
  return (
    <Modal
      open
      wide
      title={t("宿主邮件服务")}
      onOpenChange={(value) => {
        if (!value) close();
      }}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <fieldset disabled={!writable || save.isPending}>
          <Field label={t("名称")}>
            <input
              value={name}
              required
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
          <Field label={t("邮件传输方式")}>
            <select
              value={config.transport || "smtp"}
              onChange={(e) => set("transport", e.target.value)}
            >
              <option value="smtp">SMTP</option>
              <option value="resend">Resend</option>
            </select>
          </Field>

          {["sender", "smtp_host", "smtp_username"].map((key) => (
            <Field key={key} label={t(mailLabels[key] || key)}>
              <input
                value={config[key] || ""}
                onChange={(e) => set(key, e.target.value)}
              />
            </Field>
          ))}
          {["smtp_port", "timeout_s"].map((key) => (
            <Field key={key} label={t(mailLabels[key] || key)}>
              <input
                type="number"
                min={0}
                value={config[key] ?? 0}
                onChange={(e) => set(key, Number(e.target.value))}
              />
            </Field>
          ))}
          <Field label={t("SMTP 安全方式")}>
            <select
              value={config.smtp_security || "starttls"}
              onChange={(e) => set("smtp_security", e.target.value)}
            >
              <option value="starttls">STARTTLS</option>
              <option value="tls">TLS</option>
              <option value="none">{t("无")}</option>
            </select>
          </Field>
          {writable && (
            <>
              <Field
                label={t("API 密钥")}
                hint={row.has_api_key ? t("密钥已配置；留空保留。") : ""}
              >
                <input
                  type="password"
                  autoComplete="new-password"
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                />
              </Field>
              <label className="check">
                <input
                  type="checkbox"
                  checked={clearKey}
                  onChange={(e) => setClearKey(e.target.checked)}
                />
                {t("清除 API 密钥")}
              </label>
              <Field
                label={t("SMTP 密码")}
                hint={row.has_smtp_password ? t("密码已配置；留空保留。") : ""}
              >
                <input
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </Field>
              <label className="check">
                <input
                  type="checkbox"
                  checked={clearPassword}
                  onChange={(e) => setClearPassword(e.target.checked)}
                />
                {t("清除 SMTP 密码")}
              </label>
            </>
          )}
          <fieldset>
            <legend>{t("授权项目")}</legend>
            {projects.map((project) => (
              <label className="check" key={project.id}>
                <input
                  type="checkbox"
                  checked={grants.includes(project.id)}
                  onChange={(e) =>
                    setGrants((old) =>
                      e.target.checked
                        ? [...old, project.id]
                        : old.filter((id) => id !== project.id),
                    )
                  }
                />
                {project.name}
              </label>
            ))}
          </fieldset>
          <ErrorBox error={save.error} />
          {writable && <Button variant="primary">{t("保存服务")}</Button>}
        </fieldset>
      </form>
    </Modal>
  );
}
