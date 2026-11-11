import { t } from "./i18n";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import { ArrowDown, ArrowUp, Copy, Download, Plus, Trash2 } from "lucide-react";
import { api, ApiError, post, timeLabel, type Run } from "./api";
import { Button, ErrorBox, Field, Loading, Modal, useWorkspace } from "./ui";
import JsonEditor, { parseJson } from "./JsonEditor";
import { AICallDetail } from "./aiProviders";
import StageEditor from "./researchStages";

type Step = { command: string; parameters: Record<string, any> };
type Protocol = {
  schema_version: string;
  mode: string;
  limits: Record<string, number>;
  steps: Step[];
};
type Command = {
  id: string;
  label: string;
  hint: string;
  defaults: Record<string, any>;
  plan: boolean;
};
const statuses: Record<string, string> = {
  ready: "待开始",
  queued: "等待工作进程",
  running: "执行中",
  paused: "已暂停",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};
const limitNames: Record<string, string> = {
  max_steps: "步骤数上限",
  max_stimuli: "文本刺激数上限",
  max_text_chars: "文本总字数上限",
  max_wait_us: "累计推进微秒上限",
};

function PlanEditor({
  base,
  run,
  commands,
  limits,
  initial,
  derivedFrom,
  onDone,
}: {
  base: string;
  run: Run;
  commands: Command[];
  limits: Record<string, number>;
  initial?: Protocol;
  derivedFrom?: string;
  onDone: (id: string) => void;
}) {
  const [name, setName] = useState(`${run.name} · 受控实验`);
  const [protocol, setProtocol] = useState<Protocol>(
    initial ?? {
      schema_version: "threemind.research-plan/2",
      mode: "confirm",
      limits,
      steps: [
        { command: "observe.summary", parameters: {} },
        {
          command: "experiment.note",
          parameters: { text: "请说明本次实验目的与比较对象。" },
        },
      ],
    },
  );
  const [jsonMode, setJsonMode] = useState(false),
    [raw, setRaw] = useState(""),
    [message, setMessage] = useState("");
  const [page, setPage] = useState(0),
    [previous, setPrevious] = useState<Protocol>();
  const [template, setTemplate] = useState("repeat"),
    [first, setFirst] = useState("甲"),
    [second, setSecond] = useState("乙"),
    [repeats, setRepeats] = useState(3),
    [seconds, setSeconds] = useState("0.1");
  const identity = useRef<{ value: string; id: string } | undefined>(undefined);
  const names = Object.fromEntries(commands.map((c) => [c.id, c]));
  const working = () => (jsonMode ? parseJson(raw) : protocol);
  const validate = useMutation({
    mutationFn: async (switchBack: boolean) => {
      const response = await post(`${base}/research/plans/validate`, working());
      setProtocol(response.protocol);
      if (switchBack) {
        setJsonMode(false);
        setPage(0);
      }
      setMessage(
        t("校验通过：{value0} 步，{value1} 次文本刺激，累计 {value2}。", {
          value0: String(response.totals.steps),
          value1: String(response.totals.stimuli),
          value2: String(timeLabel(response.totals.wait_us)),
        }),
      );
      return response;
    },
  });
  const save = useMutation({
    mutationFn: async () => {
      const valid = await post(`${base}/research/plans/validate`, working());
      const body = {
        name,
        expected_revision: run.revision,
        protocol: valid.protocol,
        derived_from: derivedFrom ?? null,
      };
      const key = JSON.stringify(body);
      if (identity.current?.value !== key)
        identity.current = { value: key, id: crypto.randomUUID() };
      return post(`${base}/research/plans`, {
        ...body,
        request_id: identity.current.id,
      });
    },
    onSuccess: (saved) => onDone(saved.id),
  });
  const apply = useMutation({
    mutationFn: async () => {
      const wait = Math.round(Number(seconds) * 1e6);
      if (!Number.isSafeInteger(wait) || wait < 1)
        throw new Error(t("请输入有效的模拟秒数。"));
      const result = await post(`${base}/research/templates`, {
        name: template,
        first,
        second,
        repeats,
        wait_us: wait,
      });
      setPrevious(protocol);
      setProtocol({ ...protocol, steps: result.steps });
      setPage(0);
      setMessage(t("模板已载入，可继续编辑。原草案保留一次撤销。"));
    },
  });
  const change = (index: number, value: Step) =>
    setProtocol({
      ...protocol,
      steps: protocol.steps.map((s, i) => (i === index ? value : s)),
    });
  function move(index: number, to: number) {
    const steps = [...protocol.steps];
    [steps[index], steps[to]] = [steps[to], steps[index]];
    setProtocol({ ...protocol, steps });
  }
  return (
    <div className="plan-editor">
      <Field label={t("实验计划名称")}>
        <input
          aria-label={t("实验计划名称")}
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={200}
        />
      </Field>
      <div className="panel-heading">
        <h3>{t("计划步骤与边界")}</h3>
        <button
          className="text-link"
          type="button"
          onClick={() => {
            setMessage("");
            if (jsonMode) validate.mutate(true);
            else {
              setRaw(JSON.stringify(protocol, null, 2));
              setJsonMode(true);
            }
          }}
        >
          {jsonMode ? t("切换为图形配置") : t("切换为 JSON 编辑")}
        </button>
      </div>
      <ErrorBox error={save.error || validate.error || apply.error} />
      {message && (
        <p className="notice" role="status">
          {message}
        </p>
      )}
      {jsonMode ? (
        <>
          <div className="json-actions">
            <Button
              onClick={() => {
                try {
                  setRaw(JSON.stringify(parseJson(raw), null, 2));
                  setMessage(t("JSON 已格式化；冻结前还会校验命令与边界。"));
                } catch (e) {
                  setMessage(String(e));
                }
              }}
            >
              {t("格式化 JSON")}
            </Button>
            <Button onClick={() => validate.mutate(false)}>
              {t("校验计划")}
            </Button>
          </div>
          <JsonEditor
            label={t("研究计划 JSON")}
            value={raw}
            onChange={setRaw}
            rows={22}
          />
        </>
      ) : (
        <>
          <div className="form-grid">
            <Field label={t("执行模式")}>
              <select
                aria-label={t("执行模式")}
                value={protocol.mode}
                onChange={(e) =>
                  setProtocol({ ...protocol, mode: e.target.value })
                }
              >
                <option value="confirm">{t("确认后执行完整计划")}</option>
                <option value="manual">
                  {t("人工逐步（每次只执行一步）")}
                </option>
                <option value="automatic">{t("受限自动（仅同源沙箱）")}</option>
              </select>
            </Field>
            <p className="footnote">
              {t(
                "计划保存后保持待开始。自动模式同样需要明确开始，后续步骤不再逐条确认。",
              )}
            </p>
          </div>
          <details className="plan-template">
            <summary>{t("从实验模板开始")}</summary>
            <div className="form-grid">
              <Field label={t("实验模板")}>
                <select
                  aria-label={t("实验模板")}
                  value={template}
                  onChange={(e) => setTemplate(e.target.value)}
                >
                  <option value="repeat">{t("重复刺激")}</option>
                  <option value="association">{t("联想与迁移")}</option>
                  <option value="forgetting">{t("遗忘与巩固")}</option>
                  <option value="order">{t("输入顺序")}</option>
                  <option value="free">{t("自由协议")}</option>
                </select>
              </Field>
              <Field label={t("每段推进（模拟秒）")}>
                <input
                  aria-label={t("每段推进（模拟秒）")}
                  type="number"
                  min=".000001"
                  step="any"
                  value={seconds}
                  onChange={(e) => setSeconds(e.target.value)}
                />
              </Field>
              <Field label={t("刺激 A")}>
                <textarea
                  aria-label={t("刺激 A")}
                  rows={2}
                  value={first}
                  onChange={(e) => setFirst(e.target.value)}
                />
              </Field>
              {(template === "association" || template === "order") && (
                <Field label={t("刺激 B")}>
                  <textarea
                    aria-label={t("刺激 B")}
                    rows={2}
                    value={second}
                    onChange={(e) => setSecond(e.target.value)}
                  />
                </Field>
              )}
              <Field label={t("重复次数")}>
                <input
                  aria-label={t("重复次数")}
                  type="number"
                  min={1}
                  max={12}
                  value={repeats}
                  onChange={(e) => setRepeats(Number(e.target.value))}
                />
              </Field>
            </div>
            <p className="footnote">
              {t(
                "模板替换步骤，可继续调整。顺序对照应在同一来源的独立沙箱中交换 A／B；背景刺激由意识配置明确控制，模板不会悄悄关闭。",
              )}
            </p>
            <div className="json-actions">
              <Button disabled={apply.isPending} onClick={() => apply.mutate()}>
                {t("应用模板到草案")}
              </Button>
              {previous && (
                <Button
                  onClick={() => {
                    setProtocol(previous);
                    setPrevious(undefined);
                    setPage(0);
                  }}
                >
                  {t("撤销模板替换")}
                </Button>
              )}
            </div>
          </details>
          <details className="plan-limits">
            <summary>{t("高级参数 · 本次执行边界")}</summary>
            <div className="form-grid">
              {Object.entries(protocol.limits).map(([key, value]) => (
                <Field key={key} label={t(limitNames[key] ?? key)}>
                  <input
                    aria-label={t(limitNames[key] ?? key)}
                    type="number"
                    step={1}
                    value={value}
                    onChange={(e) =>
                      setProtocol({
                        ...protocol,
                        limits: {
                          ...protocol.limits,
                          [key]: Number(e.target.value),
                        },
                      })
                    }
                  />
                </Field>
              ))}
            </div>
          </details>
          <div className="plan-steps">
            {protocol.steps.slice(page * 10, page * 10 + 10).map((step, i) => {
              const index = page * 10 + i,
                command = names[step.command];
              return (
                <article
                  className="plan-step"
                  key={index}
                  aria-label={t("步骤 {value0}", { value0: String(index + 1) })}
                >
                  <div className="plan-step-heading">
                    <strong>{index + 1}</strong>
                    <select
                      aria-label={t("步骤 {value0} 命令", {
                        value0: String(index + 1),
                      })}
                      value={step.command}
                      onChange={(e) =>
                        change(index, {
                          command: e.target.value,
                          parameters: { ...names[e.target.value].defaults },
                        })
                      }
                    >
                      {commands
                        .filter((c) => c.plan)
                        .map((c) => (
                          <option key={c.id} value={c.id}>
                            {t(c.label)}
                          </option>
                        ))}
                    </select>
                    <button
                      className="icon-button"
                      aria-label={t("上移步骤 {value0}", {
                        value0: String(index + 1),
                      })}
                      disabled={index === 0}
                      onClick={() => move(index, index - 1)}
                    >
                      <ArrowUp size={16} />
                    </button>
                    <button
                      className="icon-button"
                      aria-label={t("下移步骤 {value0}", {
                        value0: String(index + 1),
                      })}
                      disabled={index === protocol.steps.length - 1}
                      onClick={() => move(index, index + 1)}
                    >
                      <ArrowDown size={16} />
                    </button>
                    <button
                      className="icon-button"
                      aria-label={t("复制步骤 {value0}", {
                        value0: String(index + 1),
                      })}
                      disabled={protocol.steps.length >= 200}
                      onClick={() =>
                        setProtocol({
                          ...protocol,
                          steps: [
                            ...protocol.steps.slice(0, index + 1),
                            structuredClone(step),
                            ...protocol.steps.slice(index + 1),
                          ],
                        })
                      }
                    >
                      <Copy size={16} />
                    </button>
                    <button
                      className="icon-button"
                      aria-label={t("删除步骤 {value0}", {
                        value0: String(index + 1),
                      })}
                      disabled={protocol.steps.length === 1}
                      onClick={() => {
                        setProtocol({
                          ...protocol,
                          steps: protocol.steps.filter((_, k) => k !== index),
                        });
                        setPage(
                          Math.min(
                            page,
                            Math.floor((protocol.steps.length - 2) / 10),
                          ),
                        );
                      }}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                  <p className="muted">{t(command?.hint ?? "")}</p>
                  <div className="form-grid">
                    {Object.entries(step.parameters).map(([key, value]) => {
                      const label =
                        (
                          {
                            text:
                              step.command === "stimulus.send"
                                ? "文本载体"
                                : "实验注记",
                            intensity: "刺激强度",
                            duration_us: "推进时长（模拟秒）",
                            label: "状态引用名称",
                            limit: "历史条数",
                          } as Record<string, string>
                        )[key] ?? key;
                      const changed = (v: any) =>
                        change(index, {
                          ...step,
                          parameters: { ...step.parameters, [key]: v },
                        });
                      return (
                        <Field key={key} label={t(label)}>
                          {key === "text" ? (
                            <textarea
                              aria-label={`${index + 1} ${t(label)}`}
                              rows={3}
                              value={value}
                              onChange={(e) => changed(e.target.value)}
                            />
                          ) : (
                            <input
                              aria-label={`${index + 1} ${t(label)}`}
                              type={
                                typeof value === "number" ? "number" : "text"
                              }
                              step={
                                key === "duration_us" || key === "intensity"
                                  ? "any"
                                  : 1
                              }
                              value={
                                key === "duration_us" ? value / 1e6 : value
                              }
                              onChange={(e) =>
                                changed(
                                  key === "duration_us"
                                    ? Math.round(Number(e.target.value) * 1e6)
                                    : typeof value === "number"
                                      ? Number(e.target.value)
                                      : e.target.value,
                                )
                              }
                            />
                          )}
                        </Field>
                      );
                    })}
                  </div>
                </article>
              );
            })}
          </div>
          <div className="json-actions">
            <Button disabled={page === 0} onClick={() => setPage(page - 1)}>
              {t("上一页步骤")}
            </Button>
            <span>
              {t("第 {page} 页 · 共 {count} 步", {
                page: page + 1,
                count: protocol.steps.length,
              })}
            </span>
            <Button
              disabled={(page + 1) * 10 >= protocol.steps.length}
              onClick={() => setPage(page + 1)}
            >
              {t("下一页步骤")}
            </Button>
            <Button
              disabled={protocol.steps.length >= 200}
              onClick={() => {
                setProtocol({
                  ...protocol,
                  steps: [
                    ...protocol.steps,
                    { command: "observe.summary", parameters: {} },
                  ],
                });
                setPage(Math.floor(protocol.steps.length / 10));
              }}
            >
              <Plus size={16} />
              {t("添加步骤")}
            </Button>
          </div>
        </>
      )}
      <p className="footnote">
        {t("起点 r")}
        {run.revision} · {timeLabel(run.time_us)}
        {t(
          "。冻结后协议只读；复用会创建新计划。文本步骤记录接收回执，实际递送须经过后续推进，沿输入记录核查。",
        )}
      </p>
      <div className="modal-actions">
        <Button
          disabled={save.isPending || validate.isPending}
          onClick={() => validate.mutate(false)}
        >
          {t("校验计划")}
        </Button>
        <Button
          variant="primary"
          disabled={!name.trim() || save.isPending}
          onClick={() => save.mutate()}
        >
          {save.isPending ? t("正在冻结…") : t("冻结并保存计划")}
        </Button>
      </div>
    </div>
  );
}

export default function ResearchPlans({
  base,
  run,
}: {
  base: string;
  run: Run;
}) {
  const { project } = useWorkspace(),
    cache = useQueryClient();
  const [query, setQuery] = useSearchParams();
  const selected = query.get("plan") ?? "";
  const [aiCall, setAiCall] = useState<string>();
  const [derivedFrom, setDerivedFrom] = useState<string>();
  const [offset, setOffset] = useState(0),
    [editor, setEditor] = useState(false),
    [stageEditor, setStageEditor] = useState(false),
    [initial, setInitial] = useState<Protocol>();
  const [before, setBefore] = useState<string>(),
    [ceiling, setCeiling] = useState<string>(),
    [pages, setPages] = useState<(string | undefined)[]>([]);
  const [retry, setRetry] = useState<{ id: string; body: any }>();
  const write = ["owner", "researcher"].includes(project?.role ?? "");
  const catalog = useQuery<{
    commands: Command[];
    limits: Record<string, number>;
    stage_limits: Record<string, number>;
  }>({
    queryKey: ["research-commands", base],
    queryFn: () => api(`${base}/research/commands`),
    staleTime: Infinity,
  });
  const list = useQuery<any>({
    queryKey: ["research-plans", base, offset],
    queryFn: () => api(`${base}/research/plans?offset=${offset}&limit=20`),
    refetchInterval: 3000,
  });
  const frozen = useQuery<any>({
    queryKey: ["research-plan", base, selected],
    queryFn: () => api(`${base}/research/plans/${selected}`),
    enabled: !!selected,
    staleTime: Infinity,
  });
  const progress = useQuery<any>({
    queryKey: ["research-plan-state", base, selected],
    queryFn: () => api(`${base}/research/plans/${selected}/status`),
    enabled: !!selected,
    refetchInterval: 1500,
  });
  const plan = {
    data: frozen.data ? { ...frozen.data, ...progress.data } : undefined,
    error: frozen.error || progress.error,
  };
  const records = useQuery<any>({
    queryKey: ["plan-records", base, selected, before, ceiling],
    queryFn: () =>
      api(
        `${base}/research/actions?plan_id=${selected}&limit=30${before ? `&before=${before}` : ""}${ceiling ? `&ceiling=${ceiling}` : ""}`,
      ),
    enabled: !!selected,
    refetchInterval: ["running", "queued"].includes(plan.data?.status)
      ? 2000
      : false,
  });
  useEffect(() => {
    cache.invalidateQueries({ queryKey: ["plan-records", base, selected] });
  }, [cache, base, selected, progress.data?.updated_at]);
  const refresh = () => {
    for (const key of [
      "research-plans",
      "research-plan-state",
      "plan-records",
      "run",
      "research-actions",
    ])
      cache.invalidateQueries({ queryKey: [key] });
  };
  const control = useMutation({
    mutationFn: ({ id, body }: { id: string; body: any }) =>
      post(`${base}/research/plans/${id}/control`, body),
    onSuccess: () => {
      setRetry(undefined);
      refresh();
    },
    onError: (error, value) => {
      setRetry(
        error instanceof ApiError && error.status < 500 ? undefined : value,
      );
      refresh();
    },
  });
  function select(id: string) {
    const next = new URLSearchParams(query);
    next.set("plan", id);
    setQuery(next);
    setBefore(undefined);
    setCeiling(undefined);
    setPages([]);
  }
  function send(action: string) {
    control.mutate({
      id: selected,
      body: {
        action,
        request_id: crypto.randomUUID(),
        expected_step: plan.data.next_step,
        expected_revision: plan.data.expected_revision,
      },
    });
  }
  const names = Object.fromEntries(
    catalog.data?.commands.map((c) => [c.id, c.label]) ?? [],
  );
  const mutable =
    write &&
    ["paused", "blocked"].includes(run.status) &&
    run.life !== "dead" &&
    !run.spec.study_id;
  return (
    <section className="research-plans" aria-label={t("受控实验计划")}>
      <div className="panel-heading">
        <div>
          <h2>{t("受控实验计划")}</h2>
          <p>
            {t(
              "先冻结步骤与执行边界；通过真实输入、推进和观察留下可复核轨迹。",
            )}
          </p>
        </div>
        <Button
          variant="primary"
          disabled={!mutable || !catalog.data}
          onClick={() => {
            setInitial(undefined);
            setDerivedFrom(undefined);
            setEditor(true);
          }}
        >
          <Plus size={16} />
          {t("设计实验计划")}
        </Button>
        <Button
          disabled={!mutable || !catalog.data}
          onClick={() => {
            setInitial(undefined);
            setDerivedFrom(undefined);
            setStageEditor(true);
          }}
        >
          <Plus size={16} />
          {t("设计阶段重复实验")}
        </Button>
        <Link className="button" to="?view=ai&tool=assistant">
          {t("AI 生成与分析")}
        </Link>
      </div>
      {!mutable && (
        <p className="notice">
          {t(
            "请先暂停普通意识，或从“人工操作”创建同源暂停沙箱，再设计新计划。",
          )}
        </p>
      )}
      <ErrorBox
        error={
          catalog.error ||
          list.error ||
          plan.error ||
          records.error ||
          control.error
        }
      />
      {retry && (
        <div className="notice">
          {t("未收到控制请求的完整确认，重试会使用同一编号。")}
          <Button
            disabled={control.isPending}
            onClick={() => control.mutate(retry)}
          >
            {t("重试同一计划控制")}
          </Button>
        </div>
      )}
      <div className="plan-workspace">
        <aside className="panel plan-list">
          <h3>{t("计划库")}</h3>
          {list.isPending ? (
            <Loading />
          ) : (
            list.data?.rows.map((p: any) => (
              <button
                key={p.id}
                className={`plan-list-item ${selected === p.id ? "selected" : ""}`}
                onClick={() => select(p.id)}
              >
                <strong>{p.name}</strong>
                <span>
                  {t(
                    statuses[
                      selected === p.id && plan.data
                        ? plan.data.status
                        : p.status
                    ],
                  )}{" "}
                  ·{" "}
                  {selected === p.id && plan.data
                    ? plan.data.next_step
                    : p.next_step}
                  /{p.step_count}
                  {t(" 步")}
                </span>
              </button>
            ))
          )}
          {list.data && !list.data.rows.length && <p>{t("尚无计划。")}</p>}
          <div className="json-actions">
            <Button
              disabled={offset === 0}
              onClick={() => setOffset(offset - 20)}
            >
              {t("上一页计划")}
            </Button>
            <Button
              disabled={!list.data?.more}
              onClick={() => setOffset(offset + 20)}
            >
              {t("下一页计划")}
            </Button>
          </div>
        </aside>
        <section className="panel plan-detail">
          {!selected ? (
            <p className="muted">
              {t("选择已有计划查看冻结协议、执行位置和原始回执。")}
            </p>
          ) : !plan.data ? (
            <Loading />
          ) : (
            <>
              <div className="panel-heading">
                <div>
                  <h3>{plan.data.name}</h3>
                  <p>
                    {t(statuses[plan.data.status])}
                    {t(" · 已完成 ")}
                    {plan.data.next_step}/
                    {plan.data.cursor?.total ??
                      plan.data.protocol.steps?.length}
                    {t(" 步 ·")}{" "}
                    {plan.data.origin === "ai"
                      ? t("外部 AI 提议")
                      : t("人工设计")}
                  </p>
                </div>
                <a
                  className="text-link"
                  href={`/api/v2${base}/research/plans/${selected}/export`}
                >
                  <Download size={14} />
                  {t("导出计划与轨迹 JSONL")}
                </a>
              </div>
              {plan.data.cursor?.name && (
                <p className="notice">
                  {plan.data.cursor.name} · {t("第几次重复")}:{" "}
                  {plan.data.cursor.repetition + 1}/
                  {plan.data.cursor.stage_repetitions}
                </p>
              )}
              <ErrorBox error={plan.data.error} />
              {plan.data.ai_call_id && (
                <button
                  className="text-link"
                  onClick={() => setAiCall(plan.data.ai_call_id)}
                >
                  {t("查看 AI 原始提议、证据与供应商版本")}
                </button>
              )}
              {plan.data.derived_from && (
                <p className="footnote">
                  {t("人工修订自已有计划，原始来源与提议保留。")}
                  <button
                    className="text-link"
                    onClick={() => select(plan.data.derived_from)}
                  >
                    {t("查看来源计划")}
                  </button>
                </p>
              )}
              <div className="json-actions">
                {["ready", "paused"].includes(plan.data.status) && (
                  <Button
                    variant="primary"
                    disabled={!write || control.isPending || !!retry}
                    onClick={() => send("start")}
                  >
                    {plan.data.protocol.mode === "manual"
                      ? t("执行下一步骤")
                      : plan.data.next_step || plan.data.step_attempt
                        ? t("继续剩余计划")
                        : t("确认并开始计划")}
                  </Button>
                )}
                {["running", "queued"].includes(plan.data.status) && (
                  <Button
                    disabled={!write || control.isPending || !!retry}
                    onClick={() => send("pause")}
                  >
                    {t("当前步骤结束后暂停")}
                  </Button>
                )}
                {["ready", "paused", "running", "queued"].includes(
                  plan.data.status,
                ) && (
                  <Button
                    disabled={!write || control.isPending || !!retry}
                    onClick={() => send("cancel")}
                  >
                    {t("取消剩余步骤")}
                  </Button>
                )}
                <Button
                  disabled={!mutable || !catalog.data}
                  onClick={() => {
                    setInitial(structuredClone(plan.data.protocol));
                    setDerivedFrom(selected);
                    if (plan.data.protocol.stages) setStageEditor(true);
                    else setEditor(true);
                  }}
                >
                  <Copy size={16} />
                  {t("以此计划再设计")}
                </Button>
              </div>
              {plan.data.stop_requested &&
                ["running", "queued"].includes(plan.data.status) && (
                  <p className="notice">
                    {t(
                      "已请求在当前步骤结束后停止。需要立即打断模拟推进时，可使用意识的暂停按钮；未完成目标会保留。",
                    )}
                  </p>
                )}
              <div className="plan-boundary">
                <span>
                  {t("初始恢复点 ")}
                  <code>{plan.data.checkpoint_id}</code>
                </span>
                <span>
                  {t("协议哈希 ")}
                  <code>{plan.data.protocol_hash}</code>
                </span>
                <span>
                  {t("继续边界 r")}
                  {plan.data.expected_revision}
                  {t("；背景来源遵守冻结时的意识配置。")}
                </span>
              </div>
              <details className="plan-frozen">
                <summary>{t("查看完整冻结协议与命令范围")}</summary>
                <ol>
                  {(plan.data.protocol.steps ?? []).map(
                    (s: Step, i: number) => (
                      <li key={i}>
                        <strong>{t(names[s.command] ?? s.command)}</strong>
                        <code>{JSON.stringify(s.parameters)}</code>
                      </li>
                    ),
                  )}
                  {(plan.data.protocol.stages ?? []).map(
                    (stage: any, i: number) => (
                      <li key={`stage-${i}`}>
                        <strong>
                          {stage.name} × {stage.repeat}
                        </strong>
                        <p>
                          {stage.steps
                            .map((s: Step) => t(names[s.command] ?? s.command))
                            .join(" → ")}
                        </p>
                      </li>
                    ),
                  )}
                </ol>
                <JsonEditor
                  readOnly
                  label={t("冻结实验计划 JSON")}
                  value={JSON.stringify(plan.data.protocol, null, 2)}
                  onChange={() => {}}
                  rows={16}
                />
              </details>
              <h3>{t("逐步回执与原始证据")}</h3>
              {records.data?.rows.map((row: any) => (
                <article className="plan-receipt" key={row.id}>
                  <div className="plan-receipt-heading">
                    <strong>
                      {row.plan_step == null
                        ? t("控制")
                        : t("步骤 {value0} · 第 {value1} 次执行", {
                            value0: String(row.plan_step + 1),
                            value1: String(row.plan_attempt + 1),
                          })}{" "}
                      ·{" "}
                      {(names[row.kind] ? t(names[row.kind]) : null) ??
                        (row.kind === "runtime.advance"
                          ? t("推进模拟时间")
                          : row.kind)}
                    </strong>
                    <span>
                      {t(
                        (
                          {
                            completed: "已提交",
                            pending: "进行中",
                            interrupted: "已中断",
                            failed: "失败",
                          } as Record<string, string>
                        )[row.status],
                      )}
                    </span>
                  </div>
                  {row.kind === "runtime.advance" && (
                    <p>
                      {t("固定目标 ")}
                      {timeLabel(row.parameters.target_us)}
                      {t("；实际")}{" "}
                      {row.result.actual_time_us
                        ? timeLabel(row.result.actual_time_us)
                        : t("尚未提交终点")}
                    </p>
                  )}
                  {row.result.envelope_id && (
                    <Link
                      className="text-link"
                      to={`?view=inputs&envelope=${row.result.envelope_id}`}
                    >
                      {t("查看文本载体与递送证据")}
                    </Link>
                  )}
                  <Link
                    className="text-link"
                    to={`/data?run=${run.id}&checkpoint=${row.result_checkpoint_id || row.checkpoint_id}`}
                  >
                    {t("查询此恢复点")}
                  </Link>
                  <details>
                    <summary>{t("参数、结果与引用编号")}</summary>
                    <pre>{JSON.stringify(row, null, 2)}</pre>
                  </details>
                </article>
              ))}
              <div className="json-actions">
                <Button
                  disabled={!pages.length}
                  onClick={() => {
                    setBefore(pages.at(-1));
                    setPages(pages.slice(0, -1));
                  }}
                >
                  {t("上一页回执")}
                </Button>
                <Button
                  disabled={!records.data?.more}
                  onClick={() => {
                    setPages([...pages, before]);
                    setBefore(records.data.next);
                    setCeiling(records.data.ceiling);
                  }}
                >
                  {t("下一页回执")}
                </Button>
                <button
                  className="text-link"
                  onClick={() => {
                    setBefore(undefined);
                    setCeiling(undefined);
                    setPages([]);
                    refresh();
                  }}
                >
                  {t("回到最新回执")}
                </button>
              </div>
            </>
          )}
        </section>
      </div>
      {aiCall && (
        <AICallDetail callId={aiCall} onClose={() => setAiCall(undefined)} />
      )}
      {editor && catalog.data && (
        <Modal
          open
          wide
          onOpenChange={setEditor}
          title={t("设计受控实验计划")}
          description={t(
            "图形与 JSON 共用命令契约。保存不立即执行；随后在计划详情明确开始。",
          )}
        >
          <PlanEditor
            base={base}
            run={run}
            commands={catalog.data.commands.filter(
              (c) => c.id !== "stimulus.frames",
            )}
            limits={catalog.data.limits}
            initial={initial}
            derivedFrom={derivedFrom}
            onDone={(id) => {
              setEditor(false);
              select(id);
              setOffset(0);
              refresh();
            }}
          />
        </Modal>
      )}
      {stageEditor && catalog.data && (
        <Modal
          open
          wide
          onOpenChange={setStageEditor}
          title={t("设计阶段重复实验")}
        >
          <StageEditor
            base={base}
            revision={run.revision}
            limits={catalog.data.stage_limits}
            initial={initial as any}
            derivedFrom={derivedFrom}
            onDone={(id) => {
              setStageEditor(false);
              select(id);
              setOffset(0);
              refresh();
            }}
          />
        </Modal>
      )}
    </section>
  );
}
