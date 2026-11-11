import { can } from "./access";
import { t, locale } from "./i18n";
import EcologyInterpretation from "./EcologyInterpretation";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Pencil,
  Play,
  Download,
  KeyRound,
  Users,
  RefreshCw,
} from "lucide-react";
import { Link } from "react-router-dom";
import { api, post, projectPath } from "./api";
import {
  Button,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Modal,
  useWorkspace,
} from "./ui";

export const aiStatuses: Record<string, string> = {
  queued: "待处理",
  sending: "正在生成",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  uncertain: "结果不确定",
};
export const aiPurposes: Record<string, string> = {
  provider_test: "连接测试",
  environment: "环境刺激",
  interpretation: "外部解读",
  research_plan: "实验计划",
  analysis: "实验分析",
  record: "实验记录",
  report: "实验报告",
  world: "世界与躯体草案",
  ecology_observation: "AI 观察解释",
};
export const aiActive = (status?: string) =>
  status === "queued" || status === "sending";
const defaults: Record<string, any> = {
  name: "",
  protocol: "chat",
  base_url: "",
  model: "",
  enabled: false,
  priority: 100,
  timeout_s: 60,
  max_output_tokens: 2048,
  temperature: null,
  stream: true,
  include_usage: true,
  chat_token_field: "max_completion_tokens",
  max_pending: 4,
  daily_request_limit: 1000,
  monthly_budget_usd: null,
  input_usd_per_million: null,
  output_usd_per_million: null,
  proxy_url: null,
  proxy_username: "",
};

function ProviderEditor({
  row,
  base,
  onClose,
}: {
  row: any;
  base: string;
  onClose: () => void;
}) {
  const [config, setConfig] = useState<Record<string, any>>({
    ...defaults,
    ...row.config,
  });
  const [key, setKey] = useState(""),
    [password, setPassword] = useState("");
  const [clearKey, setClearKey] = useState(false),
    [clearPassword, setClearPassword] = useState(false);
  const client = useQueryClient();
  const set = (name: string, value: any) =>
    setConfig((c) => ({ ...c, [name]: value }));
  const save = useMutation({
    mutationFn: () =>
      api(`${base}${row.id ? `/${row.id}` : ""}`, {
        method: row.id ? "PUT" : "POST",
        body: JSON.stringify({
          config,
          expected_revision: row.revision ?? 0,
          api_key: key,
          proxy_password: password,
          clear_api_key: clearKey,
          clear_proxy_password: clearPassword,
        }),
      }),
    onSuccess: () => {
      setKey("");
      setPassword("");
      client.invalidateQueries({ queryKey: ["ai-providers"] });
      onClose();
    },
  });
  const number = (
    name: string,
    label: string,
    min: number,
    max: number,
    hint = "",
    nullable = false,
    step = "1",
  ) => (
    <Field key={name} label={t(label)} hint={t(hint)}>
      <input
        aria-label={t(label)}
        type="number"
        min={min}
        max={max}
        step={step}
        required={!nullable}
        value={config[name] ?? ""}
        onChange={(e) =>
          set(
            name,
            e.target.value === "" && nullable ? null : Number(e.target.value),
          )
        }
      />
    </Field>
  );
  return (
    <Modal
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      wide
      title={row.id ? t("编辑 AI 供应商") : t("添加 AI 供应商")}
      description={t(
        "配置保存到当前范围，凭据加密存储。环境刺激、外部解读和实验助手分别选择供应商。",
      )}
    >
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <ErrorBox error={save.error} />
        <div className="form-grid">
          <Field label={t("供应商名称")}>
            <input
              aria-label={t("供应商名称")}
              value={config.name}
              required
              maxLength={120}
              onChange={(e) => set("name", e.target.value)}
            />
          </Field>
          <Field label={t("接口协议")}>
            <select
              aria-label={t("接口协议")}
              value={config.protocol}
              onChange={(e) => set("protocol", e.target.value)}
            >
              <option value="chat">
                {t("Chat Completions · OpenAI 兼容")}
              </option>
              <option value="responses">OpenAI Responses</option>
            </select>
          </Field>
          <Field
            label={t("API 基础地址")}
            hint={t(
              "填写服务商提供的地址（通常以 /v1 结尾）；也支持完整请求地址。",
            )}
          >
            <input
              aria-label={t("API 基础地址")}
              type="url"
              placeholder="https://api.example.com/v1"
              required
              value={config.base_url}
              onChange={(e) => set("base_url", e.target.value)}
            />
          </Field>
          <Field
            label={t("模型名称")}
            hint={t("填写此供应商实际支持的模型 ID。")}
          >
            <input
              aria-label={t("模型名称")}
              required
              value={config.model}
              maxLength={200}
              onChange={(e) => set("model", e.target.value)}
            />
          </Field>
          <Field
            label="API Key"
            hint={
              row.has_api_key
                ? t("已配置；留空保留现有密钥。")
                : t("无鉴权的本地服务可留空。")
            }
          >
            <input
              aria-label="API Key"
              autoComplete="new-password"
              type="password"
              value={key}
              onChange={(e) => {
                setKey(e.target.value);
                setClearKey(false);
              }}
            />
          </Field>
          <div className="field">
            <label className="check">
              <input
                type="checkbox"
                checked={config.enabled}
                onChange={(e) => set("enabled", e.target.checked)}
              />
              {t("启用此供应商")}
            </label>
            {row.has_api_key && (
              <label className="check">
                <input
                  type="checkbox"
                  checked={clearKey}
                  onChange={(e) => {
                    setClearKey(e.target.checked);
                    if (e.target.checked) setKey("");
                  }}
                />
                {t("清除已保存的 API Key")}
              </label>
            )}
          </div>
        </div>
        <details className="config-section ai-advanced">
          <summary>{t("高级参数 · 协议、超时与输出")}</summary>
          <div className="form-grid">
            {number(
              "timeout_s",
              "总超时（秒）",
              1,
              600,
              "包含连接与完整生成过程。",
            )}
            {number("max_output_tokens", "输出 Token 上限", 1, 131072)}
            {number(
              "temperature",
              "温度",
              0,
              2,
              "留空由供应商决定，适用于不接受 temperature 的模型。",
              true,
              "0.05",
            )}
            {number(
              "priority",
              "显示排序",
              0,
              10000,
              "数值越小越靠前；不会静默切换供应商。",
            )}
            {config.protocol === "chat" && (
              <Field label={t("输出上限参数")}>
                <select
                  aria-label={t("输出上限参数")}
                  value={config.chat_token_field}
                  onChange={(e) => set("chat_token_field", e.target.value)}
                >
                  <option value="max_completion_tokens">
                    max_completion_tokens
                  </option>
                  <option value="max_tokens">
                    {t("max_tokens · 旧兼容服务")}
                  </option>
                </select>
              </Field>
            )}
            <div className="field">
              <label className="check">
                <input
                  type="checkbox"
                  checked={config.stream}
                  onChange={(e) => set("stream", e.target.checked)}
                />
                {t("流式接收结果")}
              </label>
              {config.protocol === "chat" && (
                <label className="check">
                  <input
                    type="checkbox"
                    checked={config.include_usage}
                    onChange={(e) => set("include_usage", e.target.checked)}
                  />
                  {t("请求流式 Token 用量")}
                </label>
              )}
            </div>
          </div>
        </details>
        <details className="config-section ai-advanced">
          <summary>{t("请求配额与费用记录")}</summary>
          <div className="form-grid">
            {number(
              "max_pending",
              "待处理请求上限",
              1,
              100,
              "包括排队与生成中的请求。",
            )}
            {number(
              "daily_request_limit",
              "每日请求上限",
              1,
              1000000,
              "按 UTC 日期统计已受理请求，取消也计入数量。",
            )}
            {number(
              "input_usd_per_million",
              "输入单价（美元 / 百万 Token）",
              0,
              100000,
              "选填；免费本地模型可明确填写 0。",
              true,
              "0.0001",
            )}
            {number(
              "output_usd_per_million",
              "输出单价（美元 / 百万 Token）",
              0,
              100000,
              "单价由你填写并维护，不自动推测。",
              true,
              "0.0001",
            )}
            {number(
              "monthly_budget_usd",
              "月费用预算（美元）",
              0.0001,
              1000000,
              "选填；需要同时填写两种单价。按 UTC 月份预留费用。",
              true,
              "0.0001",
            )}
          </div>
          <p className="footnote">
            {t(
              "以供应商返回的 Token 用量结算估算费用。用量缺失时保留预留金额；这里的预算不替代供应商账单限额。",
            )}
          </p>
        </details>
        <details className="config-section ai-advanced">
          <summary>{t("HTTP 代理")}</summary>
          <div className="form-grid">
            <Field
              label={t("代理地址")}
              hint={t("留空直连，例如 http://127.0.0.1:7890。")}
            >
              <input
                aria-label={t("代理地址")}
                type="url"
                value={config.proxy_url ?? ""}
                onChange={(e) => {
                  set("proxy_url", e.target.value || null);
                  if (!e.target.value) set("proxy_username", "");
                }}
              />
            </Field>
            <Field label={t("代理用户名")}>
              <input
                aria-label={t("代理用户名")}
                disabled={!config.proxy_url}
                value={config.proxy_username}
                onChange={(e) => set("proxy_username", e.target.value)}
              />
            </Field>
            <Field
              label={t("代理密码")}
              hint={
                row.has_proxy_password ? t("已配置；留空保留。") : t("选填。")
              }
            >
              <input
                aria-label={t("代理密码")}
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  setClearPassword(false);
                }}
              />
            </Field>
            {row.has_proxy_password && (
              <label className="check">
                <input
                  type="checkbox"
                  checked={clearPassword}
                  onChange={(e) => {
                    setClearPassword(e.target.checked);
                    if (e.target.checked) setPassword("");
                  }}
                />
                {t("清除已保存的代理密码")}
              </label>
            )}
          </div>
        </details>
        <footer className="form-actions">
          <Button type="button" onClick={onClose}>
            {t("取消")}
          </Button>
          <Button variant="primary" disabled={save.isPending}>
            {t("保存供应商")}
          </Button>
        </footer>
      </form>
    </Modal>
  );
}

export function AICallDetail({
  callId,
  onClose,
  platform = false,
}: {
  callId: string;
  onClose: () => void;
  platform?: boolean;
}) {
  const { project, user } = useWorkspace(),
    client = useQueryClient();
  const base = platform
    ? `/ai/calls/${callId}`
    : `${projectPath(project!.id)}/ai/calls/${callId}`;
  const query = useQuery({
    queryKey: ["ai-call", platform, project?.id, callId],
    queryFn: () => api(base),
    staleTime: Infinity,
  });
  const status = useQuery({
    queryKey: ["ai-call-status", platform, project?.id, callId],
    queryFn: () => api(base + "/status"),
    refetchInterval: (q) => {
      const row = q.state.data;
      return !row ||
        aiActive(row.status) ||
        (row.status === "completed" &&
          row.purpose !== "provider_test" &&
          !row.result?.application_status &&
          ["pending", "leased"].includes(row.job_status))
        ? 1000
        : false;
    },
  });
  const cancel = useMutation({
    mutationFn: () => post(base + "/cancel", {}),
    onSuccess: () => client.invalidateQueries({ queryKey: ["ai-call-status"] }),
  });
  const row = query.data ? { ...query.data, ...status.data } : undefined;
  const applying =
    row?.status === "completed" &&
    row?.purpose !== "provider_test" &&
    !row?.result?.application_status &&
    ["pending", "leased"].includes(row?.job_status);
  return (
    <Modal
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      wide
      title={
        row
          ? `${t(aiPurposes[row.purpose])} · ${t(aiStatuses[row.status])}`
          : t("AI 请求")
      }
      description={t(
        "输出属于外部工具内容。原始提示、证据引用与供应商版本保留在此请求中。",
      )}
    >
      <ErrorBox error={query.error ?? status.error ?? cancel.error} />
      {!row ? (
        <Loading />
      ) : (
        <>
          <div className="ai-request-meta">
            <span>
              {row.provider_config.name} · {row.provider_config.model}
            </span>
            <span>
              {t("配置版本 ")}
              {row.provider_revision}
            </span>
            <span>{new Date(row.created_at).toLocaleString(locale())}</span>
          </div>
          {row.error && <ErrorBox error={row.error} />}
          {row.job_error && <ErrorBox error={row.job_error} />}
          {applying && (
            <p className="notice">
              {t("供应商已返回，正在校验结果与应用边界。")}
            </p>
          )}
          {row.result?.application_status === "rejected" && (
            <ErrorBox error={"结果未应用：" + row.result.error} />
          )}
          {row.result?.application_status === "applied" && (
            <p className="notice">
              {row.result.envelope_id
                ? t("已接收为普通输入载体。实际分帧递送请沿输入记录核查。")
                : t("实验计划已通过校验并保存。")}
            </p>
          )}
          {row.result?.review_status === "unreviewed" && (
            <p className="footnote">
              {t(
                "外部 AI 生成 · 尚未人工审阅。引用存在不代表模型的推论已经得到证实。",
              )}
            </p>
          )}
          {row.result?.plan_id && (
            <Link
              className="button"
              onClick={onClose}
              to={
                "/runs/" +
                row.run_id +
                "?view=research&tool=plans&plan=" +
                row.result.plan_id
              }
            >
              {t("查看生成的实验计划")}
            </Link>
          )}
          {row.result?.document_id && (
            <Link
              className="button"
              onClick={onClose}
              to={`/reports?tab=${row.purpose}&document=${row.result.document_id}`}
            >
              {t("打开生成草案")}
            </Link>
          )}
          {row.purpose === "world" &&
            row.result?.application_status === "proposed" && (
              <Link
                className="button"
                onClick={onClose}
                to={`/worlds?project=${project!.id}&proposal=${callId}`}
              >
                {t("查看并采用世界草案")}
              </Link>
            )}
          {row.result?.envelope_id && (
            <Link
              className="text-link"
              onClick={onClose}
              to={
                "/runs/" +
                row.run_id +
                "?view=inputs&input=" +
                row.result.envelope_id
              }
            >
              {t("查看输入载体与递送")}
            </Link>
          )}
          {row.result?.interpretation && (
            <EcologyInterpretation value={row.result.interpretation} />
          )}
          {row.result?.analysis && (
            <section className="ai-analysis" aria-label={t("结构化实验分析")}>
              <h3>{t("分析摘要")}</h3>
              <p>{row.result.analysis.summary}</p>
              {row.result.analysis.observations.map((s: any, i: number) => (
                <div key={i}>
                  <p>{s.text}</p>
                  <small>
                    {t("证据：")}
                    {s.source_refs.join(" · ")}
                  </small>
                </div>
              ))}
              {row.result.analysis.interpretation && (
                <>
                  <h4>{t("解释与推论")}</h4>
                  <p>{row.result.analysis.interpretation}</p>
                </>
              )}
              {!!row.result.analysis.alternatives.length && (
                <>
                  <h4>{t("其他解释")}</h4>
                  <ul>
                    {row.result.analysis.alternatives.map(
                      (s: string, i: number) => (
                        <li key={i}>{s}</li>
                      ),
                    )}
                  </ul>
                </>
              )}
              {row.result.analysis.conclusion && (
                <>
                  <h4>{t("待核查结论")}</h4>
                  <p>{row.result.analysis.conclusion}</p>
                </>
              )}
              {!!row.result.analysis.follow_up.length && (
                <>
                  <h4>{t("后续验证建议")}</h4>
                  <ul>
                    {row.result.analysis.follow_up.map(
                      (s: string, i: number) => (
                        <li key={i}>{s}</li>
                      ),
                    )}
                  </ul>
                </>
              )}
            </section>
          )}
          <pre className="ai-preview" aria-label={t("AI 返回内容")}>
            {row.response_text ||
              (aiActive(row.status)
                ? t("等待供应商返回…")
                : t("没有返回文本。"))}
          </pre>
          <div className="ai-request-meta">
            <span>
              {t("输入 / 输出 Token：")}
              {row.usage
                ? `${row.usage.input_tokens} / ${row.usage.output_tokens}`
                : t("供应商未返回完整用量")}
            </span>
            <span>
              {t("费用：")}
              {row.cost_usd != null
                ? t("${value0}（按配置单价）", {
                    value0: String(
                      Number(row.cost_usd).toLocaleString(locale(), {
                        maximumFractionDigits: 8,
                      }),
                    ),
                  })
                : row.reserved_usd != null
                  ? t("${value0}（预留，未结算）", {
                      value0: String(
                        Number(row.reserved_usd).toLocaleString(locale(), {
                          maximumFractionDigits: 8,
                        }),
                      ),
                    })
                  : t("未配置单价或用量未知")}
            </span>
          </div>
          <details className="ai-advanced">
            <summary>{t("提示词与证据引用")}</summary>
            <h4>{t("系统提示")}</h4>
            <pre className="ai-preview">{row.prompt.system}</pre>
            <h4>{t("请求内容")}</h4>
            <pre className="ai-preview">{row.prompt.user}</pre>
            <h4>{t("证据引用")}</h4>
            <pre className="ai-preview">
              {JSON.stringify(row.evidence, null, 2)}
            </pre>
          </details>
          <footer className="form-actions">
            <a className="button" href={`/api/v2${base}/export`}>
              <Download size={15} />
              {t("导出请求记录")}
            </a>
            {(aiActive(row.status) || applying) &&
              (platform
                ? can(user, "services.use", "platform")
                : can(user, "services.use") && project?.role !== "viewer") && (
                <Button
                  disabled={row.cancel_requested || cancel.isPending}
                  onClick={() => cancel.mutate()}
                >
                  {row.cancel_requested ? t("取消中…") : t("取消请求")}
                </Button>
              )}
            <Button onClick={onClose}>{t("关闭详情")}</Button>
          </footer>
        </>
      )}
    </Modal>
  );
}

export function AICallHistory({
  runId,
  purpose,
  platform = false,
}: {
  runId?: string;
  purpose?: string;
  platform?: boolean;
}) {
  const { project } = useWorkspace();
  const [cursor, setCursor] = useState<number | null>(null),
    [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState(purpose ?? "");
  const params = new URLSearchParams({ limit: "25" });
  if (cursor) params.set("before", String(cursor));
  if (runId) params.set("run_id", runId);
  if (filter) params.set("purpose", filter);
  const data = useQuery({
    queryKey: ["ai-calls", platform, project?.id, runId, cursor, filter],
    queryFn: () =>
      api(
        `${platform ? "/ai/calls" : `${projectPath(project!.id)}/ai/calls`}?${params}`,
      ),
    enabled: platform || !!project,
    refetchInterval: cursor ? false : 3000,
  });
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>{t("AI 请求记录")}</h2>
          <p>{t("可查看、取消请求并导出完整调用记录。")}</p>
        </div>
        <div className="ai-actions">
          {!platform && (
            <select
              aria-label={t("AI 请求类型")}
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value);
                setCursor(null);
              }}
            >
              <option value="">{t("全部类型")}</option>
              {Object.entries(aiPurposes).map(([key, label]) => (
                <option key={key} value={key}>
                  {t(label)}
                </option>
              ))}
            </select>
          )}
          <Button
            onClick={() => {
              setCursor(null);
              data.refetch();
            }}
          >
            <RefreshCw size={15} />
            {t("最新记录")}
          </Button>
        </div>
      </div>
      <ErrorBox error={data.error} />
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>{t("类型 / 时间")}</th>
              <th>{t("供应商 / 模型")}</th>
              <th>{t("状态")}</th>
              <th>{t("用量（输入 / 输出）")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {data.data?.items.map((row: any) => (
              <tr key={row.id}>
                <td>
                  {t(aiPurposes[row.purpose])}
                  <small>
                    {new Date(row.created_at).toLocaleString(locale())}
                  </small>
                </td>
                <td>
                  {row.provider_name}
                  <small>{row.model}</small>
                </td>
                <td>
                  {t(aiStatuses[row.status])}
                  {row.application_status && (
                    <small>
                      {t(
                        {
                          applied: "已应用",
                          recorded: "已记录 · 待审阅",
                          proposed: "草案待采用",
                          rejected: "结果未应用",
                        }[row.application_status as string] ??
                          row.application_status,
                      )}
                    </small>
                  )}
                  {row.cancel_requested && aiActive(row.status) && (
                    <small>{t("已请求取消")}</small>
                  )}
                </td>
                <td>
                  {row.usage
                    ? `${row.usage.input_tokens} / ${row.usage.output_tokens}`
                    : t("未返回")}
                </td>
                <td>
                  <Button variant="small" onClick={() => setSelected(row.id)}>
                    {t("查看请求")}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.data?.items.length === 0 && (
        <Empty
          title={t("尚无 AI 请求")}
          detail={t("启用供应商后，可从连接测试或对应工具入口发起请求。")}
        />
      )}
      {data.data?.next && (
        <Button onClick={() => setCursor(data.data.next)}>
          {t("更早的记录")}
        </Button>
      )}
      {selected && (
        <AICallDetail
          callId={selected}
          platform={platform}
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  );
}

function ShareGrants({
  row,
  data,
  onClose,
}: {
  row: any;
  data: any;
  onClose: () => void;
}) {
  const [selected, setSelected] = useState<string[]>(
    data.grants
      .filter((g: any) => g.provider_id === row.id)
      .map((g: any) => g.project_id),
  );
  const client = useQueryClient();
  const save = useMutation({
    mutationFn: () =>
      api(`/admin/ai/providers/${row.id}/grants`, {
        method: "PUT",
        body: JSON.stringify({ projects: selected }),
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["ai-providers"] });
      onClose();
    },
  });
  return (
    <Modal
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={t("共享授权 · {value0}", { value0: String(row.config.name) })}
      description={t(
        "只有勾选项目的研究者能使用此供应商。项目成员无法读取平台凭据。",
      )}
    >
      <ErrorBox error={save.error} />
      <div className="ai-grant-list">
        {data.projects.map((p: any) => (
          <label className="check" key={p.id}>
            <input
              type="checkbox"
              checked={selected.includes(p.id)}
              onChange={(e) =>
                setSelected((old) =>
                  e.target.checked
                    ? [...old, p.id]
                    : old.filter((id) => id !== p.id),
                )
              }
            />
            {p.name}
          </label>
        ))}
      </div>
      <footer className="form-actions">
        <Button onClick={onClose}>{t("取消")}</Button>
        <Button
          variant="primary"
          disabled={save.isPending}
          onClick={() => save.mutate()}
        >
          {t("保存共享授权")}
        </Button>
      </footer>
    </Modal>
  );
}

export default function AIProviders() {
  const { user, projects } = useWorkspace(),
    client = useQueryClient();
  const [tab, setTab] = useState("platform"),
    [editing, setEditing] = useState<any>(null),
    [sharing, setSharing] = useState<any>(null);
  const [testRow, setTestRow] = useState<any>(null),
    [prompt, setPrompt] = useState("请仅回复：连接成功。");
  const [requestId, setRequestId] = useState(() => crypto.randomUUID()),
    [selectedCall, setSelectedCall] = useState<string | null>(null);
  const platform = true,
    base = "/admin/ai/providers";
  const query = useQuery({
    queryKey: ["ai-providers", "authorized"],
    queryFn: () => api("/ai/providers"),
    enabled: can(user, "services.read"),
  });
  const canEdit =
    can(user, "services.manage", "platform") &&
    can(user, "services.read", "platform");
  const grants = useQuery({
    queryKey: ["ai-providers", "management"],
    queryFn: () => api(base),
    enabled: canEdit,
  });
  const test = useMutation({
    mutationFn: () =>
      post(`/ai/providers/${testRow.id}/test`, {
        request_id: requestId,
        prompt,
      }),
    onSuccess: (call) => {
      setTestRow(null);
      setSelectedCall(call.id);
      client.invalidateQueries({ queryKey: ["ai-calls"] });
    },
  });
  return (
    <>
      <div className="tabs" aria-label={t("AI 供应商分类")}>
        <button
          className={tab === "platform" ? "active" : ""}
          onClick={() => setTab("platform")}
        >
          {t("系统 AI 目录")}
        </button>
        {can(user, "services.read", "platform") && (
          <button
            className={tab === "calls" ? "active" : ""}
            onClick={() => setTab("calls")}
          >
            {t("请求记录")}
          </button>
        )}
      </div>
      {tab === "calls" ? (
        <AICallHistory platform />
      ) : (
        <section className="panel settings-panel">
          <div className="panel-heading">
            <div>
              <h2>{platform ? t("平台共享供应商") : t("AI 供应商")}</h2>
              <p>
                {platform
                  ? t("由管理员维护凭据，并授权给指定项目。")
                  : t("可同时配置云端与本地模型。每个工具独立选择供应商。")}
              </p>
            </div>
            {canEdit && (
              <Button
                variant="primary"
                onClick={() => setEditing({})}
                disabled={!query.data?.secrets_ready}
              >
                <Plus size={16} />
                {t("添加供应商")}
              </Button>
            )}
          </div>
          <ErrorBox error={query.error} />
          {query.data && !query.data.secrets_ready && (
            <ErrorBox error="部署尚未配置供应商凭据加密钥。工作站请使用 workstation 启动；服务器配置 THREEMIND_SECRET_KEYS 后重启 API 与 AI worker。" />
          )}
          <div className="ai-provider-grid">
            {query.data?.providers.map((row: any) => (
              <article className="ai-provider-card" key={row.id}>
                <div className="panel-heading">
                  <h3>{row.config.name}</h3>
                  <span
                    className={`badge ${row.config.enabled ? "completed" : "paused"}`}
                  >
                    {row.config.enabled ? t("已启用") : t("已停用")}
                  </span>
                </div>
                <strong>{row.config.model}</strong>
                <p className="ai-endpoint">{row.config.base_url}</p>
                <div className="ai-request-meta">
                  <span>
                    {row.config.protocol === "responses"
                      ? "Responses"
                      : "Chat Completions"}
                  </span>
                  <span>
                    {row.project_id ? t("项目配置") : t("平台共享")} · v
                    {row.revision}
                  </span>
                  <span>
                    <KeyRound size={12} />{" "}
                    {row.has_api_key ? t("密钥已配置") : t("未设置密钥")}
                  </span>
                </div>
                <p>
                  {t("输出上限 ")}
                  {row.config.max_output_tokens.toLocaleString(locale())}
                  {t(" Token · 总超时 ")}
                  {row.config.timeout_s}
                  {t(" 秒")}
                </p>
                {row.network_allowed === false && (
                  <p className="footnote">
                    {t("此地址尚未被部署管理员允许访问。")}
                  </p>
                )}
                <div className="ai-actions">
                  {canEdit && row.can_manage === true && (
                    <Button variant="small" onClick={() => setEditing(row)}>
                      <Pencil size={14} />
                      {t("编辑")}
                    </Button>
                  )}
                  {canEdit && row.can_manage === true && (
                    <Button
                      variant="small"
                      disabled={!grants.data}
                      onClick={() => setSharing(row)}
                    >
                      <Users size={14} />
                      {t("共享授权")}
                    </Button>
                  )}
                  {row.can_diagnose === true &&
                    can(user, "services.use", "platform") &&
                    can(user, "services.read", "platform") && (
                      <Button
                        variant="small"
                        disabled={
                          !row.config.enabled || row.network_allowed === false
                        }
                        onClick={() => {
                          setTestRow(row);
                          setRequestId(crypto.randomUUID());
                          setPrompt("请仅回复：连接成功。");
                          test.reset();
                        }}
                      >
                        <Play size={14} />
                        {t("连接测试")}
                      </Button>
                    )}
                </div>
              </article>
            ))}
          </div>
          {query.data?.providers.length === 0 && (
            <Empty
              title={t("尚未配置供应商")}
              detail={
                platform
                  ? t("添加供应商后，再选择可以使用它的项目。")
                  : t("添加一个供应商，或请管理员授权已有平台供应商。")
              }
            />
          )}
          <p className="footnote">
            <Link className="text-link" to="/docs?doc=docs/zh/v2-ai-tools.md">
              {t("查看凭据、共享权限、配额与调用记录说明")}
            </Link>
          </p>
        </section>
      )}
      {editing && (
        <ProviderEditor
          key={`${platform}-${editing.id ?? "new"}`}
          row={editing}
          base={base}
          onClose={() => setEditing(null)}
        />
      )}
      {sharing && (
        <ShareGrants
          row={sharing}
          data={{ ...grants.data, projects: grants.data?.projects ?? projects }}
          onClose={() => setSharing(null)}
        />
      )}
      {testRow && (
        <Modal
          open
          onOpenChange={(open) => {
            if (!open) setTestRow(null);
          }}
          title={t("连接测试 · {value0}", {
            value0: String(testRow.config.name),
          })}
          description={t(
            "将向此供应商发起一次真实文本请求，用量计入配置的配额。",
          )}
        >
          <ErrorBox error={test.error} />
          <Field label={t("测试内容")}>
            <textarea
              aria-label={t("测试内容")}
              rows={3}
              value={prompt}
              onChange={(e) => {
                setPrompt(e.target.value);
                setRequestId(crypto.randomUUID());
              }}
              maxLength={2000}
            />
          </Field>
          <footer className="form-actions">
            <Button onClick={() => setTestRow(null)}>{t("取消")}</Button>
            <Button
              variant="primary"
              disabled={test.isPending || !prompt.trim()}
              onClick={() => test.mutate()}
            >
              {t("发送测试请求")}
            </Button>
          </footer>
        </Modal>
      )}
      {selectedCall && (
        <AICallDetail
          callId={selectedCall}
          platform
          onClose={() => setSelectedCall(null)}
        />
      )}
    </>
  );
}
