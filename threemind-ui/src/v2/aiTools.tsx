import { t, locale } from "./i18n";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import { Download, Sparkles } from "lucide-react";
import { api, post, projectPath, timeLabel, type Run } from "./api";
import { Button, ErrorBox, Field, Loading, useWorkspace } from "./ui";
import JsonEditor, { parseJson } from "./JsonEditor";
import { AICallDetail, AICallHistory } from "./aiProviders";

const names: Record<string, string> = {
  environment: "环境刺激",
  interpreter: "外部解读",
  assistant: "实验助手",
  history: "请求记录",
};
const descriptions: Record<string, string> = {
  environment:
    "生成外部情境文本，经普通文本感官和输入总线递送。生成器只看到此处的情境描述，不读取意识内部状态。",
  interpreter:
    "对固定恢复点之前已提交的读出与采样提供外部解释。输出保留为研究辅助内容，不回灌意识。",
  assistant:
    "根据已有证据生成受控实验计划或分析。计划只能使用注册命令，并受执行模式与预算约束。",
};

export default function AITools({ base, run }: { base: string; run: Run }) {
  const { project } = useWorkspace(),
    cache = useQueryClient();
  const write = ["owner", "researcher"].includes(project?.role ?? "");
  const [params, setParams] = useSearchParams();
  const tab = names[params.get("tool") ?? ""]
    ? params.get("tool")!
    : "environment";
  const endpoint = base + "/ai-tools";
  const query = useQuery({
    queryKey: ["ai-tools", base],
    queryFn: () => api(endpoint),
  });
  const status = useQuery({
    queryKey: ["ai-tool-status", base],
    queryFn: () => api(endpoint + "/status"),
    refetchInterval: 3000,
  });
  const providers = useQuery({
    queryKey: ["ai-providers", project?.id],
    queryFn: () => api(projectPath(project!.id) + "/ai/providers"),
  });
  const [draft, setDraft] = useState<any>(),
    [revision, setRevision] = useState(0),
    [original, setOriginal] = useState("");
  const [json, setJson] = useState(false),
    [raw, setRaw] = useState(""),
    [notice, setNotice] = useState("");
  const [callId, setCallId] = useState<string | null>(params.get("call"));
  const [checkpoint, setCheckpoint] = useState<any>(null),
    [cpPage, setCpPage] = useState<(number | null)[]>([null]);
  const [cpSearch, setCpSearch] = useState(""),
    [planId, setPlanId] = useState("");
  const [planPage, setPlanPage] = useState(0),
    [objective, setObjective] = useState(""),
    [mode, setMode] = useState("confirm");
  const [versionCursor, setVersionCursor] = useState<number | null>(null),
    [showVersions, setShowVersions] = useState(false);
  const identity = useRef<{ value: string; id: string } | undefined>(undefined);
  const read = (row: any) => {
    setDraft(row.config);
    setRevision(row.revision);
    setOriginal(JSON.stringify(row.config));
    setRaw(JSON.stringify(row.config, null, 2));
  };
  useEffect(() => {
    if (!draft && query.data) read(query.data);
  }, [draft, query.data]);
  useEffect(() => {
    if (params.get("call")) setCallId(params.get("call"));
  }, [params]);
  const working = () => (json ? parseJson(raw) : draft);
  let dirty = false;
  try {
    dirty = !!draft && JSON.stringify(working()) !== original;
  } catch {
    dirty = true;
  }
  const versions = useQuery({
    queryKey: ["ai-tools-versions", base, versionCursor, query.data?.revision],
    queryFn: () =>
      api(
        endpoint +
          "/versions?limit=20" +
          (versionCursor ? "&before=" + versionCursor : ""),
      ),
    enabled: showVersions,
  });
  const checkpoints = useQuery({
    queryKey: ["ai-tool-checkpoints", base, cpPage.at(-1), cpSearch],
    queryFn: () =>
      api(
        base +
          "/versions?limit=20&q=" +
          encodeURIComponent(cpSearch) +
          (cpPage.at(-1) ? "&before=" + cpPage.at(-1) : ""),
      ),
    enabled: tab === "interpreter" || tab === "assistant",
  });
  const plans = useQuery({
    queryKey: ["ai-tool-plans", base, planPage],
    queryFn: () =>
      api(base + "/research/plans?limit=20&offset=" + planPage * 20),
    enabled: tab === "assistant",
  });
  const validate = useMutation({
    mutationFn: async (back: boolean) => {
      const value = await post(endpoint + "/validate", working());
      setDraft(value.config);
      setRaw(JSON.stringify(value.config, null, 2));
      if (back) setJson(false);
      setNotice(t("参数校验通过。保存时仍会检查当前权限与配置版本。"));
    },
  });
  const save = useMutation({
    mutationFn: () =>
      api(endpoint, {
        method: "PUT",
        body: JSON.stringify({
          expected_revision: revision,
          config: working(),
        }),
      }),
    onSuccess: (row) => {
      read(row);
      setNotice(t("已保存工具配置 v") + row.revision + "。");
      cache.invalidateQueries({ queryKey: ["ai-tools", base] });
      cache.invalidateQueries({ queryKey: ["ai-tool-status", base] });
    },
  });
  const request = useMutation({
    mutationFn: (purpose: string) => {
      const body = {
        purpose,
        objective,
        mode,
        checkpoint_id:
          purpose === "environment" || purpose === "research_plan"
            ? null
            : (checkpoint?.id ?? null),
        plan_id: purpose === "analysis" ? planId || null : null,
      };
      const key = JSON.stringify(body);
      if (identity.current?.value !== key)
        identity.current = { value: key, id: crypto.randomUUID() };
      return post(endpoint + "/requests", {
        ...body,
        request_id: identity.current.id,
      });
    },
    onSuccess: (row) => {
      identity.current = undefined;
      setCallId(row.id);
      cache.invalidateQueries({ queryKey: ["ai-calls"] });
      cache.invalidateQueries({ queryKey: ["ai-tool-status", base] });
    },
  });
  const set = (name: string, value: any) =>
    setDraft((d: any) => ({ ...d, [tab]: { ...d[tab], [name]: value } }));
  const number = (
    name: string,
    label: string,
    min: number,
    max: number,
    step = "1",
    hint = "",
  ) => (
    <Field label={t(label)} hint={t(hint)}>
      <input
        aria-label={t(label)}
        type="number"
        required
        min={min}
        max={max}
        step={step === "1" ? "1" : "any"}
        value={draft[tab][name]}
        onChange={(e) => set(name, Number(e.target.value))}
      />
    </Field>
  );
  const check = (name: string, label: string) => (
    <label className="checkbox">
      <input
        type="checkbox"
        checked={draft[tab][name]}
        onChange={(e) => set(name, e.target.checked)}
      />
      {t(label)}
    </label>
  );
  const clock = () => (
    <Field
      label={t("调度时钟")}
      hint={t("依据最近已提交的模拟时间或宿主机时钟调度；不会调整内核时间。")}
    >
      <select
        aria-label={t("调度时钟")}
        value={draft[tab].cadence_clock}
        onChange={(e) => set("cadence_clock", e.target.value)}
      >
        <option value="host">{t("宿主机经过时间")}</option>
        <option value="simulation">{t("已提交的模拟时间")}</option>
      </select>
    </Field>
  );
  const schedule = status.data?.schedule?.state?.[tab];
  const canRequest =
    write &&
    !dirty &&
    !!draft?.[tab]?.enabled &&
    !request.isPending &&
    !save.isPending;
  const stable =
    ["paused", "blocked"].includes(run.status) &&
    run.life !== "dead" &&
    !run.spec.study_id;
  return (
    <section className="ai-tool-workspace">
      <nav className="tabs view-tabs" aria-label={t("AI 工具分类")}>
        {Object.entries(names).map(([key, label]) => (
          <button
            key={key}
            className={tab === key ? "active" : ""}
            onClick={() => {
              const next = new URLSearchParams(params);
              next.set("tool", key);
              next.delete("call");
              setParams(next);
            }}
          >
            {t(label)}
          </button>
        ))}
      </nav>
      {tab === "history" ? (
        <AICallHistory runId={run.id} />
      ) : !draft ? (
        <>
          <ErrorBox error={query.error} />
          <Loading />
        </>
      ) : (
        <>
          <form
            className="panel ai-tool-config"
            onSubmit={(e) => {
              e.preventDefault();
              save.mutate();
            }}
          >
            <div className="panel-heading">
              <div>
                <h2>{t(names[tab])}</h2>
                <p>{t(descriptions[tab])}</p>
              </div>
              <button
                type="button"
                className="text-link"
                onClick={() => {
                  setNotice("");
                  if (json) validate.mutate(true);
                  else {
                    setRaw(JSON.stringify(draft, null, 2));
                    setJson(true);
                  }
                }}
              >
                {json ? t("切换为图形配置") : t("切换为 JSON 编辑")}
              </button>
            </div>
            <ErrorBox
              error={
                query.error || providers.error || save.error || validate.error
              }
            />
            {notice && (
              <p className="notice" role="status">
                {notice}
              </p>
            )}
            {status.data && status.data.revision !== revision && (
              <p className="notice">
                {t("其他操作已保存了新版本，请读取最新配置后再编辑。")}
              </p>
            )}
            {json ? (
              <>
                <p className="footnote">
                  {t(
                    "JSON 包含三类工具的完整配置，切回图形界面会同步所有字段。",
                  )}
                </p>
                <div className="json-actions">
                  <Button
                    type="button"
                    onClick={() => {
                      try {
                        setRaw(JSON.stringify(parseJson(raw), null, 2));
                        setNotice(t("JSON 已格式化。"));
                      } catch (e) {
                        setNotice(String(e));
                      }
                    }}
                  >
                    {t("格式化 JSON")}
                  </Button>
                  <Button type="button" onClick={() => validate.mutate(false)}>
                    {t("校验参数")}
                  </Button>
                </div>
                <JsonEditor
                  label={t("AI 工具 JSON")}
                  value={raw}
                  onChange={setRaw}
                  readOnly={!write}
                  rows={24}
                />
              </>
            ) : (
              <fieldset
                disabled={!write || save.isPending}
                className="ai-tool-fields"
              >
                <div className="form-grid">
                  <Field
                    label={t("{tool}供应商", { tool: t(names[tab]) })}
                    hint={t(
                      "分别配置；没有可用供应商时，可前往设置添加或申请共享授权。",
                    )}
                  >
                    <select
                      aria-label={t("{tool}供应商", { tool: t(names[tab]) })}
                      value={draft[tab].provider_id ?? ""}
                      onChange={(e) =>
                        set("provider_id", e.target.value || null)
                      }
                    >
                      <option value="">{t("请选择供应商")}</option>
                      {providers.data?.providers.map((p: any) => (
                        <option key={p.id} value={p.id}>
                          {p.config.name} · {p.config.model}
                          {!p.config.enabled
                            ? t("（未启用）")
                            : p.network_allowed === false
                              ? t("（服务器未授权地址）")
                              : ""}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <div className="field">
                    <span>{t("工具开关")}</span>
                    {check("enabled", t("启用{tool}", { tool: t(names[tab]) }))}
                    <small>
                      {t("仅作用于当前意识的外部工具；不会修改模型参数。")}
                    </small>
                  </div>
                  {tab === "environment" && (
                    <>
                      {number("frequency_s", "生成间隔（秒）", 1, 86400, "0.1")}
                      {number("intensity", "输入强度", 0, 100, "0.01")}
                    </>
                  )}
                  {tab === "interpreter" && (
                    <>
                      {number(
                        "frequency_s",
                        "周期解读间隔（秒）",
                        2,
                        86400,
                        "0.1",
                      )}
                      <Field label={t("解读语言")}>
                        <input
                          aria-label={t("解读语言")}
                          maxLength={50}
                          required
                          value={draft.interpreter.language}
                          onChange={(e) => set("language", e.target.value)}
                        />
                      </Field>
                    </>
                  )}
                  {tab === "assistant" && (
                    <Field label={t("分析语言")}>
                      <input
                        aria-label={t("分析语言")}
                        maxLength={50}
                        required
                        value={draft.assistant.language}
                        onChange={(e) => set("language", e.target.value)}
                      />
                    </Field>
                  )}
                </div>
                {tab === "environment" && (
                  <>
                    <Field
                      label={t("环境情境")}
                      hint={t("作为生成器的外部场景描述；留空使用开放环境。")}
                    >
                      <textarea
                        aria-label={t("环境情境")}
                        rows={3}
                        maxLength={4000}
                        value={draft.environment.scenario}
                        onChange={(e) => set("scenario", e.target.value)}
                      />
                    </Field>
                    {check("automatic", "自动生成环境刺激")}
                  </>
                )}
                {tab === "interpreter" &&
                  check("periodic_enabled", "定期解读已提交的整体状态")}
                <details className="ai-advanced">
                  <summary>{t("高级参数与触发规则")}</summary>
                  {tab === "environment" && (
                    <>
                      <div className="form-grid">
                        {clock()}
                        {number(
                          "irregularity",
                          "情境不规则程度",
                          0,
                          1,
                          "0.01",
                          "发给生成器的偏好值，不是内核中的随机参数。",
                        )}
                        {number("max_text_chars", "单条刺激字符上限", 1, 20000)}
                        {number("random_seed", "间隔随机种子", 0, 4294967295)}
                      </div>
                      {check(
                        "random_frequency",
                        "随机化间隔（基准间隔的 0.5～1.5 倍，最短 1 秒）",
                      )}
                    </>
                  )}
                  {tab === "interpreter" && (
                    <>
                      <div className="form-grid">
                        {clock()}
                        {number("activation_min", "激活下限", 0, 100, "0.01")}
                        {number("activation_max", "激活上限", 0, 100, "0.01")}
                        {number(
                          "max_active_nodes",
                          "活跃节点数量上限",
                          1,
                          2000,
                        )}
                        {number("max_edges", "已记录连接数量上限", 0, 5000)}
                      </div>
                      <div className="ai-check-list">
                        {check("on_repeatable_structure", "结构复现时解读")}
                        {check(
                          "active_nodes_enabled",
                          "结构复现解读附带活跃节点",
                        )}
                        {check(
                          "on_manual_stimulus",
                          "人工刺激的时序读出完成后解读",
                        )}
                        {check(
                          "listen_background_active_nodes",
                          "监听含活跃节点的背景结构读出",
                        )}
                        {check(
                          "deduplicate_readouts",
                          "跳过与上次成功解读相同的读出",
                        )}
                      </div>
                      <p className="footnote">
                        {t(
                          "自动触发依赖已启用并记录的结构／时序读出。数量上限和筛选范围会随证据保存；周期解读只取整体摘要。",
                        )}
                      </p>
                    </>
                  )}
                  {tab === "assistant" && (
                    <>
                      <div className="form-grid">
                        {Object.entries({
                          max_steps: ["计划步骤数上限", 1, 200],
                          max_stimuli: ["计划刺激数上限", 0, 100],
                          max_text_chars: ["计划文本总字符上限", 1, 200000],
                          max_wait_us: [
                            "累计模拟推进上限（微秒）",
                            1,
                            86400000000,
                          ],
                        }).map(([key, [label, min, max]]) => (
                          <Field key={key} label={t(String(label))}>
                            <input
                              aria-label={t(String(label))}
                              type="number"
                              min={Number(min)}
                              max={Number(max)}
                              step="1"
                              required
                              value={draft.assistant.limits[key]}
                              onChange={(e) =>
                                set("limits", {
                                  ...draft.assistant.limits,
                                  [key]: Number(e.target.value),
                                })
                              }
                            />
                          </Field>
                        ))}
                        {number(
                          "max_stimulus_chars",
                          "计划单次刺激字符上限",
                          1,
                          20000,
                        )}
                      </div>
                      {check(
                        "allow_automatic",
                        "允许在明确分叉的沙箱中受限自动执行",
                      )}
                    </>
                  )}
                </details>
              </fieldset>
            )}
            <footer className="form-actions">
              <Link className="text-link" to="/settings?section=providers">
                {t("管理 AI 供应商")}
              </Link>
              <span className="footnote">
                v{revision}
                {dirty ? t(" · 有未保存修改") : t(" · 已同步")}
              </span>
              <Button
                type="button"
                onClick={async () => {
                  const result = await query.refetch();
                  if (result.data) {
                    read(result.data);
                    setNotice(t("已读取最新配置，未保存修改已丢弃。"));
                  }
                }}
              >
                {t("读取最新配置")}
              </Button>
              <Button
                type="submit"
                variant="primary"
                disabled={!write || save.isPending}
              >
                {t("保存工具配置")}
              </Button>
            </footer>
          </form>
          <section className="panel ai-tool-action">
            <div className="panel-heading">
              <div>
                <h3>
                  {tab === "environment"
                    ? t("生成与递送")
                    : tab === "interpreter"
                      ? t("解读选定证据")
                      : t("生成计划与分析")}
                </h3>
                <p>
                  {dirty
                    ? t("请先保存参数，再发起请求。")
                    : t(
                        "每次请求冻结供应商版本、工具配置与证据范围，可在请求记录中查看原文和执行结果。",
                      )}
                </p>
              </div>
            </div>
            <ErrorBox
              error={
                request.error ||
                status.error ||
                checkpoints.error ||
                plans.error
              }
            />
            {tab !== "environment" && (
              <details className="ai-advanced">
                <summary>
                  {t("证据范围 ·")}{" "}
                  {checkpoint
                    ? "r" +
                      checkpoint.revision +
                      " / " +
                      timeLabel(checkpoint.time_us)
                    : t("请求时的最新已提交恢复点")}
                </summary>
                <p className="footnote">
                  {t("解读与分析可选择历史点；新计划固定从当前暂停点设计。")}
                </p>
                <Field label={t("搜索恢复点")}>
                  <input
                    aria-label={t("搜索恢复点")}
                    value={cpSearch}
                    onChange={(e) => {
                      setCpSearch(e.target.value);
                      setCpPage([null]);
                    }}
                  />
                </Field>
                <Field label={t("历史恢复点")}>
                  <select
                    aria-label={t("历史恢复点")}
                    value={checkpoint?.id ?? ""}
                    onChange={(e) =>
                      setCheckpoint(
                        checkpoints.data?.rows.find(
                          (c: any) => c.id === e.target.value,
                        ) ?? null,
                      )
                    }
                  >
                    <option value="">
                      {t("最新已提交恢复点（请求时固定）")}
                    </option>
                    {checkpoint &&
                      !checkpoints.data?.rows.some(
                        (c: any) => c.id === checkpoint.id,
                      ) && (
                        <option value={checkpoint.id}>
                          {t("已选 r")}
                          {checkpoint.revision}
                        </option>
                      )}
                    {checkpoints.data?.rows.map((c: any) => (
                      <option key={c.id} value={c.id}>
                        r{c.revision} · {timeLabel(c.time_us)} {c.label}
                      </option>
                    ))}
                  </select>
                </Field>
                <div className="json-actions">
                  <Button
                    disabled={cpPage.length === 1}
                    onClick={() => setCpPage(cpPage.slice(0, -1))}
                  >
                    {t("较新的恢复点")}
                  </Button>
                  <Button
                    disabled={!checkpoints.data?.more}
                    onClick={() =>
                      setCpPage([...cpPage, checkpoints.data.next])
                    }
                  >
                    {t("更早的恢复点")}
                  </Button>
                </div>
                {tab === "assistant" && (
                  <>
                    <Field
                      label={t("附加实验轨迹")}
                      hint={t(
                        "仅附加已完成且处于所选证据边界内的操作；计划当前状态另外标注。",
                      )}
                    >
                      <select
                        aria-label={t("附加实验轨迹")}
                        value={planId}
                        onChange={(e) => setPlanId(e.target.value)}
                      >
                        <option value="">{t("不附加")}</option>
                        {planId &&
                          !plans.data?.rows.some(
                            (p: any) => p.id === planId,
                          ) && (
                            <option value={planId}>
                              {t("已选择的实验计划")}
                            </option>
                          )}
                        {plans.data?.rows.map((p: any) => (
                          <option key={p.id} value={p.id}>
                            {p.name}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <div className="json-actions">
                      <Button
                        disabled={!planPage}
                        onClick={() => setPlanPage(planPage - 1)}
                      >
                        {t("较新的计划")}
                      </Button>
                      <Button
                        disabled={!plans.data?.more}
                        onClick={() => setPlanPage(planPage + 1)}
                      >
                        {t("更早的计划")}
                      </Button>
                    </div>
                  </>
                )}
              </details>
            )}
            {tab === "assistant" && (
              <>
                <Field label={t("研究目的与关注问题")}>
                  <textarea
                    aria-label={t("研究目的与关注问题")}
                    rows={4}
                    maxLength={12000}
                    value={objective}
                    onChange={(e) => setObjective(e.target.value)}
                    placeholder={t(
                      "说明要比较的现象、已有假设和希望获得的证据。",
                    )}
                  />
                </Field>
                <Field label={t("生成计划的执行模式")}>
                  <select
                    aria-label={t("生成计划的执行模式")}
                    value={mode}
                    onChange={(e) => setMode(e.target.value)}
                  >
                    <option value="confirm">{t("生成后确认，再执行")}</option>
                    <option value="manual">{t("生成后人工逐步执行")}</option>
                    <option
                      value="automatic"
                      disabled={!draft.assistant.allow_automatic}
                    >
                      {t("沙箱受限自动执行（须显式允许）")}
                    </option>
                  </select>
                </Field>
                {!stable && (
                  <p className="notice">
                    {t(
                      "生成新计划需要普通意识处于暂停状态。可在人工实验中创建同源暂停沙箱；现有证据仍可分析。",
                    )}
                  </p>
                )}
              </>
            )}
            <div className="json-actions">
              {tab === "environment" ? (
                <Button
                  variant="primary"
                  disabled={!canRequest}
                  onClick={() => request.mutate("environment")}
                >
                  <Sparkles size={16} />
                  {t("生成一次环境刺激")}
                </Button>
              ) : tab === "interpreter" ? (
                <Button
                  variant="primary"
                  disabled={!canRequest}
                  onClick={() => request.mutate("interpretation")}
                >
                  <Sparkles size={16} />
                  {t("解读一次")}
                </Button>
              ) : (
                <>
                  <Button
                    variant="primary"
                    disabled={!canRequest || !stable || !objective.trim()}
                    onClick={() => request.mutate("research_plan")}
                  >
                    <Sparkles size={16} />
                    {t("AI 生成实验计划")}
                  </Button>
                  <Button
                    disabled={!canRequest}
                    onClick={() => request.mutate("analysis")}
                  >
                    {t("AI 分析现有证据")}
                  </Button>
                  <Link className="text-link" to="?view=research&tool=plans">
                    {t("打开受控计划")}
                  </Link>
                </>
              )}
            </div>
            {schedule && (
              <div className="ai-schedule">
                <p>
                  {t("自动请求：")}
                  {schedule.queued ?? 0}
                  {t(" 次 · 成功应用 / 记录：")}
                  {schedule.generated ?? 0}
                  {t(" 次 · 相同读出去重：")}
                  {schedule.deduplicated ?? 0}
                  {t(" 次 · 合并错过的模拟周期：")}
                  {schedule.coalesced_intervals ?? 0}
                  {t(" 次")}
                </p>
                {schedule.pending && <p>{t("有自动请求正在处理。")}</p>}
                {schedule.last_call_id && (
                  <button
                    className="text-link"
                    onClick={() => setCallId(schedule.last_call_id)}
                  >
                    {t("查看最近自动请求")}
                  </button>
                )}
                <ErrorBox error={schedule.last_error} />
                <p className="footnote">
                  {t(
                    "自动调用最多保留一个在途请求。周期随已提交进度向前移动，生成内容以实际接收时刻进入输入总线，不补造过去的刺激。",
                  )}
                </p>
              </div>
            )}
          </section>
          <details
            className="panel"
            open={showVersions}
            onToggle={(e) => setShowVersions(e.currentTarget.open)}
          >
            <summary>{t("工具配置历史")}</summary>
            <a className="text-link" href={"/api/v2" + endpoint + "/export"}>
              <Download size={14} />
              {t("导出全部配置版本")}
            </a>
            <ErrorBox error={versions.error} />
            {versions.data?.items.map((v: any) => (
              <details className="ai-advanced" key={v.revision}>
                <summary>
                  v{v.revision} ·{" "}
                  {new Date(v.created_at).toLocaleString(locale())}
                  {t(" · 操作者 ")}
                  {v.actor_id}
                </summary>
                <pre className="ai-preview">
                  {JSON.stringify(v.config, null, 2)}
                </pre>
              </details>
            ))}
            <div className="json-actions">
              <Button
                disabled={!versionCursor}
                onClick={() => setVersionCursor(null)}
              >
                {t("最新版本")}
              </Button>
              <Button
                disabled={!versions.data?.next}
                onClick={() => setVersionCursor(versions.data.next)}
              >
                {t("更早的配置")}
              </Button>
            </div>
          </details>
        </>
      )}
      {callId && (
        <AICallDetail
          callId={callId}
          onClose={() => {
            setCallId(null);
            const next = new URLSearchParams(params);
            next.delete("call");
            setParams(next, { replace: true });
            cache.invalidateQueries({ queryKey: ["ai-tool-status", base] });
          }}
        />
      )}
    </section>
  );
}
