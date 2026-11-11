import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import { api, post, projectPath, timeLabel } from "./api";
import { t } from "./i18n";
import {
  Badge,
  Button,
  CodeEditor,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Modal,
  PageTitle,
  useWorkspace,
} from "./ui";
import {
  ConfigurationEditor,
  useCatalogue,
  type ConfigurationHandle,
} from "./configuration";
import AssessmentSummary, { assessmentOperators } from "./AssessmentSummary";
import "./assessments.css";

function AssessmentEditor({ base, metrics, close, created }: any) {
  const { project } = useWorkspace(),
    catalogue = useCatalogue();
  const editor = useRef<ConfigurationHandle>(null);
  const [source, setSource] = useState<any>();
  const [value, setValue] = useState<any>();
  const [name, setName] = useState(t("新的独立评估")),
    [objective, setObjective] = useState("");
  const [search, setSearch] = useState(""),
    [offset, setOffset] = useState(0);
  const [seeds, setSeeds] = useState("202609081, 202609082, 202609083"),
    [excluded, setExcluded] = useState("");
  const [mode, setMode] = useState("form"),
    [raw, setRaw] = useState("");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [valid, setValid] = useState(false);
  const [editorRevision, setEditorRevision] = useState(0);
  const nonce = useRef(crypto.randomUUID());
  const versions = useQuery({
    queryKey: ["assessment-versions", base, search, offset],
    queryFn: () =>
      api(
        `${base}/innate-versions?q=${encodeURIComponent(search)}&offset=${offset}`,
      ),
  });
  function dirty() {
    nonce.current = crypto.randomUUID();
    setValid(false);
    setError(undefined);
  }
  async function selectSource(id: string) {
    setBusy(true);
    setError(undefined);
    try {
      const selected = await api(`${base}/innate-versions/${id}`);
      const spec = structuredClone(selected.protocol);
      Object.assign(spec, {
        environment: ["world", "mujoco", "ambient"].includes(spec.environment)
          ? spec.environment
          : "ambient",
        clock: "unbounded",
        duration_s: 30,
        environment_seed: null,
        study_id: null,
        condition: null,
        block_seed: null,
        replay: [],
        phases: [],
        intervention: null,
      });
      for (const scope of ["host", "process", "runtime"])
        spec[`${scope}_telemetry`].enabled = false;
      setSource(selected);
      setValue({
        schema_id: "threemind.assessment/1",
        inheritance_rule: "threemind.birth/1",
        source_version_id: id,
        evaluation: spec,
        environment_seeds: [],
        excluded_environment_seeds: [],
        criteria: [
          {
            id: "not_dead",
            metric: "not_dead_at_end",
            operator: "gte",
            threshold: 1,
            required_fraction: 1,
          },
        ],
      });
      setEditorRevision((v) => v + 1);
      dirty();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }
  function parseSeeds(text: string) {
    if (!text.trim()) return [];
    return text
      .trim()
      .split(/[\s,，]+/)
      .map((value) => {
        if (!/^\d+$/.test(value))
          throw new Error(t("环境种子请填写整数，以逗号或空格分隔。"));
        return Number(value);
      });
  }
  async function read() {
    if (mode === "json") {
      const { parseJson } = await import("./JsonEditor");
      return parseJson(raw);
    }
    if (!value) throw new Error(t("请先选择已登记的先天版本。"));
    const spec = await editor.current?.validate();
    if (!spec) throw new Error(t("请纠正环境与运行配置中的问题。"));
    return {
      ...value,
      evaluation: spec,
      environment_seeds: parseSeeds(seeds),
      excluded_environment_seeds: parseSeeds(excluded),
    };
  }
  async function action(kind: string) {
    setBusy(true);
    setError(undefined);
    try {
      const proposed = await read();
      if (kind === "format") {
        setRaw(JSON.stringify(proposed, null, 2));
        return;
      }
      const checked = (await post(`${base}/assessments/validate`, proposed))
        .protocol;
      setValid(true);
      if (kind === "toggle") {
        if (mode === "json") {
          setSource(
            await api(`${base}/innate-versions/${checked.source_version_id}`),
          );
          setEditorRevision((v) => v + 1);
          setSeeds(checked.environment_seeds.join(", "));
          setExcluded(checked.excluded_environment_seeds.join(", "));
        }
        setValue(checked);
        setRaw(JSON.stringify(checked, null, 2));
        setMode(mode === "form" ? "json" : "form");
      } else if (kind === "create") {
        const row = await post(`${base}/assessments`, {
          operation_id: nonce.current,
          name,
          objective,
          protocol: checked,
        });
        created(row.id);
      }
    } catch (cause) {
      setError(cause);
      setValid(false);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      open
      wide
      title={t("新建独立评估")}
      onOpenChange={(open) => {
        if (!open && !busy) close();
      }}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void action("create");
        }}
      >
        <fieldset disabled={busy} className="assessment-form">
          <div className="form-grid">
            <Field label={t("评估名称")}>
              <input
                required
                maxLength={120}
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  dirty();
                }}
              />
            </Field>
            <Field label={t("评估目标与限制")}>
              <textarea
                required
                rows={2}
                maxLength={8000}
                value={objective}
                onChange={(e) => {
                  setObjective(e.target.value);
                  dirty();
                }}
              />
            </Field>
          </div>
          <div className="assessment-toolbar">
            <p className="footnote">
              {t(
                "每个种子创建一个独立出生副本；保留继承结构，清空活动，不写回父本。示例规则不是意识质量标准。",
              )}
            </p>
            <button
              type="button"
              className="text-link"
              disabled={!source}
              onClick={() => void action("toggle")}
            >
              {mode === "form" ? t("切换到 JSON 编辑") : t("切换到图形配置")}
            </button>
          </div>
          {mode === "json" ? (
            <>
              <div className="query-controls">
                <Button type="button" onClick={() => void action("format")}>
                  {t("格式化")}
                </Button>
                <Button type="button" onClick={() => void action("validate")}>
                  {t("校验")}
                </Button>
              </div>
              <CodeEditor
                label={t("独立评估 JSON")}
                value={raw}
                onChange={(text) => {
                  setRaw(text);
                  dirty();
                }}
                readOnly={busy}
                rows={24}
              />
            </>
          ) : (
            <>
              <div className="form-grid">
                <Field label={t("检索先天版本")}>
                  <input
                    type="search"
                    value={search}
                    onChange={(e) => {
                      setSearch(e.target.value);
                      setOffset(0);
                    }}
                  />
                </Field>
                <Field label={t("评估来源版本")}>
                  <select
                    aria-label={t("评估来源版本")}
                    value={source?.id ?? ""}
                    onChange={(e) => {
                      if (e.target.value) void selectSource(e.target.value);
                    }}
                  >
                    <option value="">{t("请选择已登记的版本")}</option>
                    {source &&
                      !versions.data?.rows.some(
                        (row: any) => row.id === source.id,
                      ) && <option value={source.id}>{source.name}</option>}
                    {versions.data?.rows.map((row: any) => (
                      <option value={row.id} key={row.id}>
                        {row.name} · {row.state_hash.slice(0, 10)}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>
              <div className="query-controls">
                <Button
                  type="button"
                  disabled={!offset}
                  onClick={() => setOffset(offset - 30)}
                >
                  {t("上一页")}
                </Button>
                <Button
                  type="button"
                  disabled={!versions.data?.more}
                  onClick={() => setOffset(offset + 30)}
                >
                  {t("下一页")}
                </Button>
                <Link to="/studies?tab=development">{t("发育与先天模型")}</Link>
              </div>
              {value && (
                <>
                  <Field
                    label={t("评估环境种子")}
                    hint={t(
                      "每个种子对应一个独立副本，最多 32 个；不与已知谱系训练和选择种子重叠。",
                    )}
                  >
                    <input
                      value={seeds}
                      onChange={(e) => {
                        setSeeds(e.target.value);
                        dirty();
                      }}
                    />
                  </Field>
                  <h3>{t("判定标准")}</h3>
                  {value.criteria.map((rule: any, index: number) => {
                    const patch = (key: string, next: any) => {
                      setValue({
                        ...value,
                        criteria: value.criteria.map((r: any, i: number) =>
                          i === index ? { ...r, [key]: next } : r,
                        ),
                      });
                      dirty();
                    };
                    const metric = metrics.find(
                      (m: any) => m.id === rule.metric,
                    );
                    return (
                      <section className="assessment-rule" key={index}>
                        <div className="assessment-rule-fields">
                          <Field label={t("规则编号")}>
                            <input
                              value={rule.id}
                              onChange={(e) => patch("id", e.target.value)}
                            />
                          </Field>
                          <Field label={t("评估指标")}>
                            <select
                              aria-label={t("评估指标")}
                              value={rule.metric}
                              onChange={(e) => patch("metric", e.target.value)}
                            >
                              {metrics.map((m: any) => (
                                <option key={m.id} value={m.id}>
                                  {t(m.label)}
                                </option>
                              ))}
                            </select>
                          </Field>
                          <Field label={t("比较关系")}>
                            <select
                              aria-label={t("比较关系")}
                              value={rule.operator}
                              onChange={(e) =>
                                patch("operator", e.target.value)
                              }
                            >
                              {Object.entries(assessmentOperators).map(
                                ([key, name]) => (
                                  <option key={key} value={key}>
                                    {name}
                                  </option>
                                ),
                              )}
                            </select>
                          </Field>
                          <Field label={t("阈值")}>
                            <input
                              type="number"
                              step="any"
                              value={rule.threshold ?? ""}
                              onChange={(e) =>
                                patch(
                                  "threshold",
                                  e.target.value === ""
                                    ? null
                                    : Number(e.target.value),
                                )
                              }
                            />
                          </Field>
                          <Field label={t("要求符合比例（%）")}>
                            <input
                              type="number"
                              min={0.01}
                              max={100}
                              step="any"
                              value={rule.required_fraction * 100}
                              onChange={(e) =>
                                patch(
                                  "required_fraction",
                                  Number(e.target.value) / 100,
                                )
                              }
                            />
                          </Field>
                        </div>
                        <div className="query-controls">
                          <small>
                            {t(metric?.unit ?? "")} · {t(metric?.hint ?? "")}
                          </small>
                          <Button
                            type="button"
                            variant="quiet"
                            disabled={value.criteria.length < 2}
                            onClick={() => {
                              setValue({
                                ...value,
                                criteria: value.criteria.filter(
                                  (_: any, i: number) => i !== index,
                                ),
                              });
                              dirty();
                            }}
                          >
                            {t("移除规则")}
                          </Button>
                        </div>
                      </section>
                    );
                  })}
                  <Button
                    type="button"
                    disabled={value.criteria.length >= 8}
                    onClick={() => {
                      setValue({
                        ...value,
                        criteria: [
                          ...value.criteria,
                          {
                            id: `rule_${crypto.randomUUID().slice(0, 8)}`,
                            metric: "nodes",
                            operator: "gte",
                            threshold: 1,
                            required_fraction: 1,
                          },
                        ],
                      });
                      dirty();
                    }}
                  >
                    {t("添加规则")}
                  </Button>
                  <details className="assessment-advanced">
                    <summary>{t("额外排除种子（高级）")}</summary>
                    <Field
                      label={t("已知外部训练或选择种子")}
                      hint={t(
                        "系统只能核对已保存谱系；导入前或外部训练的历史需要研究者声明，种子不同也不证明环境分布独立。",
                      )}
                    >
                      <textarea
                        rows={3}
                        value={excluded}
                        onChange={(e) => {
                          setExcluded(e.target.value);
                          dirty();
                        }}
                      />
                    </Field>
                  </details>
                  <h3>{t("评估环境与运行参数")}</h3>
                  {catalogue.data && (
                    <ConfigurationEditor
                      key={`${source.id}:${editorRevision}`}
                      ref={editor}
                      initial={value.evaluation}
                      catalogue={catalogue.data}
                      project={project!.id}
                      lockedPaths={[
                        ...(source.locked_paths ?? []),
                        "environment_seed",
                      ]}
                      lockedMessage={t(
                        "独立出生保留来源内核和感官身份；环境种子由评估种子表分配。",
                      )}
                      onDirty={dirty}
                      readOnly={busy}
                      allowJsonMode={false}
                    />
                  )}
                </>
              )}
            </>
          )}
        </fieldset>
        {valid && (
          <p role="status">
            {t("校验通过；启动时仍会再次核对来源与完整协议。")}
          </p>
        )}
        <ErrorBox error={error || catalogue.error || versions.error} />
        <div className="modal-actions">
          <Button type="button" variant="quiet" disabled={busy} onClick={close}>
            {t("取消")}
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={busy || !source || catalogue.isPending}
          >
            {t("创建并启动独立评估")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export default function Assessments() {
  const { project } = useWorkspace(),
    base = projectPath(project!.id),
    write = project?.role !== "viewer";
  const [params, setParams] = useSearchParams(),
    selected = params.get("assessment");
  const [open, setOpen] = useState(false),
    [query, setQuery] = useState(""),
    [offset, setOffset] = useState(0);
  const [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  const [frozen, setFrozen] = useState<any>();
  const pending = useRef<any>(undefined);
  const catalogue = useQuery({
    queryKey: ["assessment-catalogue", base],
    queryFn: () => api(`${base}/assessments/catalogue`),
  });
  const listing = useQuery({
    queryKey: ["assessments", base, query, offset],
    queryFn: () =>
      api(
        `${base}/assessments?q=${encodeURIComponent(query)}&offset=${offset}`,
      ),
  });
  const detail = useQuery({
    queryKey: ["assessment-detail", base, selected],
    queryFn: () => api(`${base}/assessments/${selected}`),
    enabled: !!selected,
    refetchInterval: 3000,
  });
  const value = detail.data;
  async function action(kind: string) {
    setBusy(true);
    setError(undefined);
    try {
      const body =
        kind === "capture"
          ? { kind: "assessment", assessment_id: selected }
          : { action: kind, expected_revision: value.control_revision };
      const signature = JSON.stringify({ selected, kind });
      if (!pending.current || pending.current.signature !== signature)
        pending.current = {
          signature,
          body: { ...body, operation_id: crypto.randomUUID() },
        };
      await post(
        kind === "capture"
          ? `${base}/report-sources`
          : `${base}/assessments/${selected}/controls`,
        pending.current.body,
      );
      pending.current = undefined;
      await detail.refetch();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }
  async function inspect(id: string) {
    setBusy(true);
    setError(undefined);
    try {
      setFrozen(await api(`${base}/report-sources/${id}`));
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        eyebrow="INDEPENDENT ASSESSMENT"
        title={t("独立评估")}
        description={t(
          "明确环境、种子和标准，在独立出生副本上测试。所有试验保留依据，不把未完成或缺失当作成功。",
        )}
        actions={
          write && (
            <Button variant="primary" onClick={() => setOpen(true)}>
              {t("新建独立评估")}
            </Button>
          )
        }
      />
      <p className="footnote">
        <Link to="/docs?doc=docs/zh/v2-assessments.md">
          {t("评估边界与使用说明")}
        </Link>
      </p>
      <div className="query-controls">
        <input
          aria-label={t("检索独立评估")}
          placeholder={t("检索独立评估")}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOffset(0);
          }}
        />
        <Button disabled={!offset} onClick={() => setOffset(offset - 30)}>
          {t("上一页")}
        </Button>
        <Button
          disabled={!listing.data?.more}
          onClick={() => setOffset(offset + 30)}
        >
          {t("下一页")}
        </Button>
      </div>
      <ErrorBox
        error={error || listing.error || detail.error || catalogue.error}
      />
      <div className="assessment-layout">
        <aside className="assessment-list">
          {listing.data?.rows.map((row: any) => (
            <button
              key={row.id}
              className={row.id === selected ? "active" : ""}
              onClick={() => {
                setFrozen(undefined);
                setError(undefined);
                pending.current = undefined;
                setParams({ tab: "assessment", assessment: row.id });
              }}
            >
              <strong>{row.name}</strong>
              <small>
                {t("共 {count} 个试验", { count: row.trial_count })}
              </small>
            </button>
          ))}
          {listing.data?.rows.length === 0 && (
            <Empty
              title={t("独立评估")}
              detail={t("尚无独立评估，请先登记先天版本，再创建明确的测试。")}
            />
          )}
        </aside>
        <div className="assessment-detail">
          {selected && detail.isPending ? (
            <Loading />
          ) : (
            value && (
              <section className="panel">
                <h2>{value.batch_name}</h2>
                <p>{value.objective}</p>
                <p className="footnote">
                  {t(
                    "当前已提交状态的评估预览；采集后才成为固定证据。不会改变父本或自动修改筛选规则。",
                  )}
                </p>
                <div className="query-controls">
                  {write && (
                    <>
                      <Button
                        disabled={busy}
                        onClick={() => void action("capture")}
                      >
                        {t("采集当前完整评估证据")}
                      </Button>
                      {["pause", "resume", "retry", "cancel"].map((kind, i) => (
                        <Button
                          key={kind}
                          disabled={
                            busy ||
                            value.control_state === "cancelled" ||
                            !value.trials.some((trial: any) =>
                              (kind === "pause"
                                ? ["queued", "running"]
                                : kind === "resume"
                                  ? ["paused"]
                                  : kind === "retry"
                                    ? ["paused", "blocked", "failed"]
                                    : [
                                        "queued",
                                        "running",
                                        "paused",
                                        "blocked",
                                        "failed",
                                      ]
                              ).includes(trial.status),
                            )
                          }
                          variant="quiet"
                          onClick={() => void action(kind)}
                        >
                          {
                            [
                              t("暂停全部试验"),
                              t("继续已暂停试验"),
                              t("重试失败试验"),
                              t("取消未完成试验"),
                            ][i]
                          }
                        </Button>
                      ))}
                    </>
                  )}
                </div>
                <AssessmentSummary
                  value={value}
                  metrics={catalogue.data?.metrics}
                />
                <details className="assessment-advanced">
                  <summary>{t("试验、来源与冻结协议")}</summary>
                  <p className="mono">{value.source_state_hash}</p>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>{t("环境种子")}</th>
                          <th>{t("状态")}</th>
                          <th>{t("模拟时间")}</th>
                          <th>{t("原始依据")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {value.trials.map((trial: any) => (
                          <tr key={trial.run_id}>
                            <td>{trial.environment_seed}</td>
                            <td>
                              <Badge status={trial.status} />
                            </td>
                            <td>{timeLabel(trial.time_us)}</td>
                            <td>
                              <Link to={`/runs/${trial.run_id}`}>
                                {t("查看意识与证据")}
                              </Link>
                              <small className="mono">
                                {trial.state_hash?.slice(0, 16) ??
                                  t("尚无恢复点")}
                              </small>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <CodeEditor
                    label={t("冻结评估协议")}
                    value={JSON.stringify(value.protocol, null, 2)}
                    onChange={() => {}}
                    readOnly
                    rows={16}
                  />
                </details>
                <h3>{t("固定评估来源")}</h3>
                <p className="footnote">
                  {t(
                    "可多次采集不同阶段。每次保存全部已声明试验，包含未完成和失败；先前来源不会随运行更新。",
                  )}
                </p>
                <div className="assessment-captures">
                  {value.captures.map((row: any) => (
                    <div key={row.id}>
                      <code>{row.id.slice(0, 12)}</code>
                      <Badge status={row.status} />
                      <ErrorBox error={row.error} />
                      {row.status === "done" && (
                        <>
                          <Button
                            variant="quiet"
                            disabled={busy}
                            onClick={() => void inspect(row.id)}
                          >
                            {t("查看固定判定")}
                          </Button>
                          <Link to={`/reports?tab=record&source=${row.id}`}>
                            {t("从此证据创建记录")}
                          </Link>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )
          )}
        </div>
      </div>
      {frozen && (
        <Modal
          open
          wide
          title={t("查看固定判定")}
          onOpenChange={(open) => {
            if (!open) setFrozen(undefined);
          }}
        >
          <p className="mono">{frozen.content_hash}</p>
          <AssessmentSummary
            value={frozen.manifest.assessment}
            metrics={catalogue.data?.metrics}
          />
          <CodeEditor
            label={t("固定来源清单")}
            value={JSON.stringify(frozen.manifest, null, 2)}
            onChange={() => {}}
            readOnly
            rows={14}
          />
        </Modal>
      )}
      {open && catalogue.data && (
        <AssessmentEditor
          base={base}
          metrics={catalogue.data.metrics}
          close={() => setOpen(false)}
          created={(id: string) => {
            setOpen(false);
            void listing.refetch();
            setParams({ tab: "assessment", assessment: id });
          }}
        />
      )}
    </>
  );
}
