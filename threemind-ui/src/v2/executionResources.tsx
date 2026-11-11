import { can } from "./access";
import { lazy, Suspense, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, post, projectPath } from "./api";
import { t, dateLabel, messageKeys } from "./i18n";
import { Button, Empty, ErrorBox, Field, Loading, useWorkspace } from "./ui";
import { parseJson } from "./JsonEditor";
const CodeEditor = lazy(() => import("./JsonEditor"));
const SchedulingPanel = lazy(() => import("./scheduling"));
const queues = ["runtime", "ai", "notification"] as const;
type Queue = (typeof queues)[number];
type Values = Record<Queue, number | null | string>;
type Policy = { revision: number; limits: Values };
const names: Record<Queue, string> = messageKeys({
  runtime: "实验与数据处理",
  ai: "AI 请求",
  notification: "通知邮件",
});

function LimitsEditor({
  policy,
  inherited,
  projectId,
}: {
  policy: Policy;
  inherited: Values;
  projectId?: string;
}) {
  const client = useQueryClient();
  const [base, setBase] = useState(policy),
    [values, setValues] = useState<Values>(policy.limits);
  const [dirty, setDirty] = useState(false),
    [json, setJson] = useState(false);
  const [text, setText] = useState(JSON.stringify(policy.limits, null, 2));
  const [error, setError] = useState<unknown>(null),
    [message, setMessage] = useState("");
  const [checking, setChecking] = useState(false);
  const load = (next: Policy) => {
    setBase(next);
    setValues(next.limits);
    setText(JSON.stringify(next.limits, null, 2));
    setDirty(false);
    setError(null);
  };
  useEffect(() => {
    if (!dirty && policy.revision !== base.revision) load(policy);
  }, [policy.revision]);
  const draft = () => (json ? parseJson(text) : values);
  const validate = async (switchMode = false) => {
    setChecking(true);
    setError(null);
    setMessage("");
    try {
      const checked = await post("/admin/execution/validate", {
        limits: draft(),
        project: !!projectId,
      });
      setValues(checked.limits);
      setText(JSON.stringify(checked.limits, null, 2));
      if (switchMode) setJson(false);
      else setMessage("校验通过；尚未保存。");
    } catch (e) {
      setError(e);
    } finally {
      setChecking(false);
    }
  };
  const save = useMutation({
    mutationFn: () =>
      post(
        projectId
          ? `/admin/execution/projects/${projectId}/limits`
          : "/admin/execution/limits",
        {
          limits: draft(),
          expected_revision: base.revision,
        },
      ),
    onSuccess: (result) => {
      load(result);
      setMessage("执行额度已保存。正在执行的任务继续完成。");
      client.invalidateQueries({ queryKey: ["execution"] });
      client.invalidateQueries({ queryKey: ["admin"] });
    },
    onError: setError,
  });
  return (
    <div className="execution-limit-editor">
      <div className="panel-heading">
        <div>
          <h3>{t(projectId ? "项目并发额度" : "部署并发上限")}</h3>
          <p>
            {t(
              "每个队列独立计数。0 暂停领取新任务；降低额度不会终止已有租约。",
            )}
          </p>
        </div>
        <button
          type="button"
          className="text-link"
          disabled={checking || save.isPending}
          onClick={() => {
            if (json) void validate(true);
            else {
              setText(JSON.stringify(values, null, 2));
              setJson(true);
              setError(null);
            }
          }}
        >
          {t(json ? "切换到图形配置" : "切换到 JSON 编辑")}
        </button>
      </div>
      {policy.revision > base.revision && dirty && (
        <p className="notice">
          {t("策略已被其他窗口修改。当前草稿仍保留；请比较后重新载入。")}
          <button
            type="button"
            className="text-link"
            disabled={checking || save.isPending}
            onClick={() => load(policy)}
          >
            {t("重新载入已保存策略")}
          </button>
        </p>
      )}
      {json ? (
        <>
          <div className="json-actions">
            <button
              type="button"
              className="text-link"
              disabled={checking || save.isPending}
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
          </div>
          <Suspense fallback={<Loading />}>
            <CodeEditor
              label={t("执行额度 JSON")}
              value={text}
              rows={7}
              readOnly={checking || save.isPending}
              onChange={(value) => {
                setText(value);
                setDirty(true);
                setMessage("");
              }}
            />
          </Suspense>
        </>
      ) : (
        <div className="execution-limits-grid">
          {queues.map((queue) => (
            <Field key={queue} label={t(names[queue])}>
              {projectId && (
                <label className="check">
                  <input
                    type="checkbox"
                    aria-label={t("{queue}继承部署上限", {
                      queue: t(names[queue]),
                    })}
                    disabled={checking || save.isPending}
                    checked={values[queue] == null}
                    onChange={(e) => {
                      setValues({
                        ...values,
                        [queue]: e.target.checked ? null : inherited[queue],
                      });
                      setDirty(true);
                      setMessage("");
                    }}
                  />
                  {t("继承部署上限")}
                </label>
              )}
              <input
                type="number"
                min={0}
                max={1024}
                step={1}
                aria-label={t("{queue}并发额度", { queue: t(names[queue]) })}
                disabled={
                  (projectId != null && values[queue] == null) ||
                  checking ||
                  save.isPending
                }
                value={values[queue] ?? inherited[queue] ?? ""}
                onChange={(e) => {
                  setValues({
                    ...values,
                    [queue]:
                      e.target.value === "" ? "" : Number(e.target.value),
                  });
                  setDirty(true);
                  setMessage("");
                }}
              />
              <small>
                {projectId
                  ? t("有效额度不会超过部署上限。")
                  : t("由所有连接此数据库的执行节点共同遵守。")}
              </small>
            </Field>
          ))}
        </div>
      )}
      <ErrorBox error={error} />
      {message && (
        <p className="notice" role="status">
          {t(message)}
        </p>
      )}
      <div className="form-actions">
        <Button
          disabled={checking || save.isPending}
          onClick={() => void validate()}
        >
          {t("校验")}
        </Button>
        <Button
          variant="primary"
          disabled={checking || save.isPending || !dirty}
          onClick={() => {
            setError(null);
            save.mutate();
          }}
        >
          {t("保存执行额度")}
        </Button>
      </div>
    </div>
  );
}

function Usage({ data, project = false }: { data: any; project?: boolean }) {
  return (
    <div className="execution-usage">
      {queues.map((queue) => (
        <article key={queue}>
          <h4>{t(names[queue])}</h4>
          <dl>
            <div>
              <dt>{t("执行中")}</dt>
              <dd>{data.usage[queue].active}</dd>
            </div>
            <div>
              <dt>{t("等待领取")}</dt>
              <dd>{data.usage[queue].pending}</dd>
            </div>
            <div>
              <dt>{t("租约已过期")}</dt>
              <dd>{data.usage[queue].expired}</dd>
            </div>
            <div>
              <dt>{t("有效上限")}</dt>
              <dd>
                {project ? data.effective[queue] : data.global.limits[queue]}
              </dd>
            </div>
          </dl>
        </article>
      ))}
    </div>
  );
}

export default function ExecutionResources({
  manage = false,
}: {
  manage?: boolean;
}) {
  const { project, user } = useWorkspace();
  const [selected, setSelected] = useState(project?.id ?? "");
  const [search, setSearch] = useState(""),
    [offset, setOffset] = useState(0);
  const choices = useQuery({
    queryKey: ["execution", "projects", search, offset],
    queryFn: () =>
      api(
        `/admin/execution/projects?query=${encodeURIComponent(search)}&offset=${offset}`,
      ),
    enabled: manage && can(user, "execution.read"),
  });
  const data = useQuery({
    queryKey: ["execution", "deployment"],
    queryFn: () => api("/admin/execution"),
    enabled: manage && can(user, "execution.read"),
    refetchInterval: 3000,
  });
  const projectId = manage ? selected : project?.id;
  const usage = useQuery({
    queryKey: ["execution", "project", projectId, manage],
    queryFn: () =>
      api(
        manage
          ? `/admin/execution/projects/${projectId}`
          : `${projectPath(projectId!)}/execution`,
      ),
    enabled: !!projectId && (!manage || can(user, "execution.read")),
    refetchInterval: 3000,
  });
  const projectPolicy = usage.data?.project;
  if (manage && !can(user, "execution.read"))
    return (
      <Empty
        title={t("没有此功能的访问权限")}
        detail={t("请联系管理员检查角色权限。")}
      />
    );
  if (!manage && !project)
    return (
      <Empty
        title={t("请选择研究项目")}
        detail={t("选择项目后查看其执行队列和额度。")}
      />
    );
  return (
    <section
      className="panel execution-resources"
      aria-label={t("执行队列与额度")}
    >
      <div className="panel-heading">
        <div>
          <h2>{t("执行队列与额度")}</h2>
          <p>
            {t(
              "这些额度管理 Lab 任务并发，与显示档位、模型容量和模拟时间速度分开。",
            )}
          </p>
        </div>
        {!manage && can(user, "system.read") && (
          <Link className="text-link" to="/settings?section=execution">
            {t("前往管理页面调整")}
          </Link>
        )}
      </div>
      <ErrorBox error={data.error ?? usage.error ?? choices.error} />
      {manage && data.isPending && <Loading />}
      {manage && data.data && (
        <>
          <Usage data={data.data} />
          <fieldset disabled={!can(user, "system.write")}>
            <LimitsEditor
              policy={data.data.global}
              inherited={data.data.global.limits}
            />
          </fieldset>
          <div className="execution-project-selector">
            <Field label={t("搜索研究项目")}>
              <input
                type="search"
                aria-label={t("搜索研究项目")}
                value={search}
                maxLength={80}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setOffset(0);
                }}
              />
            </Field>
            <Field label={t("配置项目额度")}>
              <select
                aria-label={t("配置项目额度")}
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
              >
                <option value="">{t("选择研究项目")}</option>
                {selected &&
                  !choices.data?.rows.some((p: any) => p.id === selected) && (
                    <option value={selected}>
                      {usage.data?.project_name ?? project?.name ?? selected}
                    </option>
                  )}
                {choices.data?.rows.map((p: any) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
            <div className="pagination">
              <Button
                disabled={offset === 0 || choices.isFetching}
                onClick={() => setOffset(Math.max(0, offset - 50))}
              >
                {t("上一页")}
              </Button>
              <span>
                {t("第 {page} 页", { page: Math.floor(offset / 50) + 1 })}
              </span>
              <Button
                disabled={!choices.data?.more || choices.isFetching}
                onClick={() => setOffset(offset + 50)}
              >
                {t("下一页")}
              </Button>
            </div>
          </div>
          {projectPolicy && (
            <fieldset disabled={!can(user, "projects.manage")}>
              <LimitsEditor
                key={selected}
                projectId={selected}
                policy={{
                  revision: projectPolicy.revision,
                  limits: {
                    runtime: null,
                    ai: null,
                    notification: null,
                    ...projectPolicy.limits,
                  },
                }}
                inherited={data.data.global.limits}
              />
            </fieldset>
          )}
        </>
      )}
      {projectId && usage.isPending && <Loading />}
      {usage.data && (
        <>
          <div className="panel-heading">
            <h3>{t("所选项目的队列状态")}</h3>
          </div>
          <Usage data={usage.data} project />
          {projectId && (
            <Suspense fallback={<Loading />}>
              <SchedulingPanel
                key={projectId}
                projectId={projectId}
                manage={manage && can(user, "execution.read")}
              />
            </Suspense>
          )}
        </>
      )}
      <p className="footnote">
        {t(
          "队列额度不会改变模型参数，也不代表 CPU、内存或磁盘的硬配额。任务所需依赖、设备及运行时预算仍须满足。",
        )}
      </p>
      {manage && data.data && (
        <details className="execution-policy-history">
          <summary>{t("最近 50 次额度变更")}</summary>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t("时间")}</th>
                  <th>{t("范围")}</th>
                  <th>{t("修订")}</th>
                  <th>{t("操作者")}</th>
                  <th>JSON</th>
                </tr>
              </thead>
              <tbody>
                {data.data.history.map((row: any) => (
                  <tr key={row.id}>
                    <td>{dateLabel(row.created_at)}</td>
                    <td>{row.project_id ?? t("整个部署")}</td>
                    <td>{row.revision}</td>
                    <td>{row.actor ?? t("部署初始化")}</td>
                    <td>
                      <code>{JSON.stringify(row.limits)}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </section>
  );
}
