import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useProjectSearchParams as useSearchParams } from "./projectRouting";
import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { api, post, projectPath, numberLabel, timeLabel } from "./api";
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
  type ConfigurationHandle,
  useCatalogue,
} from "./configuration";

const stages: Record<string, string> = {
  birth: "准备出生",
  development: "发育",
  evaluation: "筛选评估",
  verification: "最终独立验证",
  complete: "已完成",
};
const at = (value: any, path: string) =>
  path.split(".").reduce((current, key) => current?.[key], value);
function shared(target: any, source: any, paths: string[]) {
  const result = structuredClone(target);
  for (const path of paths) {
    const keys = path.split("."),
      leaf = keys.pop()!;
    let container = result;
    for (const key of keys) container = container[key] ??= {};
    container[leaf] = structuredClone(at(source, path));
  }
  result.environment_seed = null;
  return result;
}

function SpecEditor({ stage, initial, locked, readOnly, close, save }: any) {
  const { project } = useWorkspace(),
    catalogue = useCatalogue(),
    editor = useRef<ConfigurationHandle>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  return (
    <Modal
      open
      wide
      onOpenChange={(open) => !open && !busy && close()}
      title={t(
        stage === "development" ? "发育与共用参数" : "评估环境与记录参数",
      )}
    >
      <p className="footnote">
        {t(
          "内核和感官身份在发育与评估间共享；环境随机化由外面的种子表管理。评估副本的学习不会写回父本。",
        )}
      </p>
      {catalogue.data ? (
        <ConfigurationEditor
          ref={editor}
          project={project!.id}
          catalogue={catalogue.data}
          initial={initial}
          lockedPaths={locked}
          readOnly={readOnly}
          frozen={busy}
          lockedMessage={t(
            "这些参数属于共享内核、感官身份或独立种子计划，请在相应位置设置。",
          )}
        />
      ) : (
        <Loading />
      )}
      <ErrorBox error={error || catalogue.error} />
      <div className="modal-actions">
        <Button type="button" onClick={close} disabled={busy}>
          {t("关闭")}
        </Button>
        {!readOnly && (
          <Button
            type="button"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError(undefined);
              try {
                const value = await editor.current?.validate();
                if (value) save(value);
              } catch (e) {
                setError(e);
              } finally {
                setBusy(false);
              }
            }}
          >
            {t("应用参数")}
          </Button>
        )}
      </div>
    </Modal>
  );
}

function EvolutionEditor({
  catalogue,
  initial,
  close,
  done,
  readOnly = false,
}: any) {
  const { project } = useWorkspace(),
    base = projectPath(project!.id),
    root = `${base}/evolutions`;
  const [p, setP] = useState<any>(() =>
    structuredClone(initial?.protocol ?? catalogue.defaults),
  );
  const [name, setName] = useState(initial?.name ?? t("新的多代定向实验")),
    [objective, setObjective] = useState(initial?.objective ?? "");
  const [jsonMode, setJsonMode] = useState(false),
    [raw, setRaw] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [notice, setNotice] = useState("");
  const [operation, setOperation] = useState(() => crypto.randomUUID()),
    [editing, setEditing] = useState<"development" | "evaluation" | null>(null);
  const [q, setQ] = useState(""),
    [sourceOffset, setSourceOffset] = useState(0),
    [seed, setSeed] = useState(20260907),
    [generation, setGeneration] = useState(0);
  const [evaluationBlocks, setEvaluationBlocks] = useState(
      p.evaluation_seeds.length,
    ),
    [verificationBlocks, setVerificationBlocks] = useState(
      p.verification_seeds.length,
    );
  const versions = useQuery({
    queryKey: ["evolution-origins", project!.id, q, sourceOffset],
    queryFn: () =>
      api<any>(
        `${base}/innate-versions?q=${encodeURIComponent(q)}&offset=${sourceOffset}`,
      ),
    enabled: !readOnly,
  });
  const edit = (next: any) => {
    setP(next);
    setOperation(crypto.randomUUID());
    setError(undefined);
    setNotice("");
  };
  const mark = () => {
    setOperation(crypto.randomUUID());
    setError(undefined);
    setNotice("");
  };
  const action = async (run: () => Promise<void>) => {
    if (busy) return;
    setBusy(true);
    setError(undefined);
    setNotice("");
    try {
      await run();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  const parsed = async () => (await import("./JsonEditor")).parseJson(raw);
  const validated = async () =>
    (await post<any>(`${root}/validate`, jsonMode ? await parsed() : p))
      .protocol;
  const toggle = () =>
    action(async () => {
      if (jsonMode) {
        if (readOnly) setP(await parsed());
        else setP(await validated());
        setGeneration(0);
        setJsonMode(false);
      } else {
        setRaw(JSON.stringify(p, null, 2));
        setJsonMode(true);
      }
    });
  const totalRuns =
    p.generations * p.population_size * (1 + p.evaluation_seeds.length) +
    p.population_size * p.verification_seeds.length;
  const displayedGeneration = Math.min(
    generation,
    p.development_seeds.length - 1,
  );
  const seedRow = p.development_seeds[displayedGeneration] ?? [];
  return (
    <>
      <Modal
        open
        wide
        onOpenChange={(open) => !open && !busy && close()}
        title={t(readOnly ? "冻结的多代实验协议" : "新建多代定向实验")}
      >
        <form
          className="evolution-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (!readOnly)
              void action(async () => {
                const protocol = await validated();
                setP(protocol);
                const result = await post<any>(root, {
                  operation_id: operation,
                  name,
                  objective,
                  protocol,
                });
                done(result.id);
              });
          }}
        >
          <div className="evolution-editor-toolbar">
            <button
              type="button"
              className="text-link"
              onClick={toggle}
              disabled={busy}
            >
              {t(jsonMode ? "切换到图形配置" : "切换到 JSON")}
            </button>
          </div>
          <Field label={t("实验名称")}>
            <input
              required
              maxLength={120}
              value={name}
              readOnly={readOnly}
              disabled={busy}
              onChange={(e) => {
                setName(e.target.value);
                mark();
              }}
            />
          </Field>
          <Field label={t("研究目标与选择依据")}>
            <textarea
              required
              rows={2}
              maxLength={8000}
              value={objective}
              readOnly={readOnly}
              disabled={busy}
              onChange={(e) => {
                setObjective(e.target.value);
                mark();
              }}
            />
          </Field>
          <p className="notice">
            {t(
              "本实验采用明确指标定向选择，并继承完整持久网络。环境生态选择另行实现；这里的指标和排序不代表意识或智能评分。",
            )}
          </p>
          {jsonMode ? (
            <CodeEditor
              value={raw}
              rows={20}
              readOnly={readOnly || busy}
              label={t("多代实验协议 JSON")}
              onChange={(value) => {
                setRaw(value);
                mark();
              }}
            />
          ) : (
            <>
              {!readOnly && (
                <div className="evolution-origin-controls">
                  <Field label={t("搜索起始先天版本")}>
                    <input
                      value={q}
                      disabled={busy}
                      onChange={(e) => {
                        setQ(e.target.value);
                        setSourceOffset(0);
                      }}
                    />
                  </Field>
                  <Field label={t("起始先天版本")}>
                    <select
                      value={p.initial_version_id ?? ""}
                      disabled={busy || versions.isPending}
                      onChange={(e) => {
                        const id = e.target.value;
                        void action(async () => {
                          if (!id) {
                            edit({ ...p, initial_version_id: null });
                            return;
                          }
                          const source = await api<any>(
                            `${base}/innate-versions/${id}`,
                          );
                          const development = shared(
                            p.development,
                            source.protocol,
                            catalogue.shared_paths,
                          );
                          edit({
                            ...p,
                            initial_version_id: id,
                            development,
                            evaluation: shared(
                              p.evaluation,
                              development,
                              catalogue.shared_paths,
                            ),
                          });
                        });
                      }}
                    >
                      <option value="">{t("空白结构，保留当前参数")}</option>
                      {p.initial_version_id &&
                        !versions.data?.rows.some(
                          (v: any) => v.id === p.initial_version_id,
                        ) && (
                          <option value={p.initial_version_id}>
                            {t("当前选择")}: {p.initial_version_id}
                          </option>
                        )}
                      {versions.data?.rows.map((v: any) => (
                        <option key={v.id} value={v.id}>
                          {v.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <div className="development-pagination">
                    <Button
                      type="button"
                      disabled={!sourceOffset || busy}
                      onClick={() =>
                        setSourceOffset(Math.max(0, sourceOffset - 30))
                      }
                    >
                      {t("上一页")}
                    </Button>
                    <Button
                      type="button"
                      disabled={!versions.data?.more || busy}
                      onClick={() => setSourceOffset(sourceOffset + 30)}
                    >
                      {t("下一页")}
                    </Button>
                  </div>
                  <ErrorBox error={versions.error} />
                </div>
              )}
              {readOnly && (
                <p className="mono">
                  {t("起始先天版本")}:{" "}
                  {p.initial_version_id ?? t("从空白结构开始")}
                </p>
              )}
              <div className="evolution-grid">
                {[
                  ["generations", "代数", 1, 1000],
                  ["population_size", "每代个体数", 2, 64],
                  ["survivor_count", "每代父本数", 1, 64],
                ].map(([key, label, min, max]) => (
                  <Field key={String(key)} label={t(String(label))}>
                    <input
                      type="number"
                      required
                      min={min}
                      max={max}
                      step={1}
                      value={p[key]}
                      disabled={busy || readOnly}
                      onChange={(e) =>
                        edit({ ...p, [key]: Number(e.target.value) })
                      }
                    />
                  </Field>
                ))}
              </div>
              <p className="footnote">
                {t(
                  "父本按排名选定，各父本轮流分配相同数量附近的后代。发育种子、筛选环境和最终验证环境彼此独立。",
                )}
              </p>
              <div className="evolution-specs">
                {(["development", "evaluation"] as const).map((stage) => (
                  <section className="panel" key={stage}>
                    <h3>
                      {t(
                        stage === "development"
                          ? "发育与共用参数"
                          : "评估环境与记录参数",
                      )}
                    </h3>
                    <p>
                      {p[stage].environment} · {p[stage].duration_s} s ·{" "}
                      {p[stage].clock}
                    </p>
                    <Button
                      type="button"
                      disabled={busy}
                      onClick={() => setEditing(stage)}
                    >
                      {t(stage === "development" ? "配置发育" : "配置评估")}
                    </Button>
                  </section>
                ))}
              </div>
              <section className="evolution-criteria">
                <h3>{t("筛选指标与优先级")}</h3>
                <p className="footnote">
                  {t(
                    "从上到下依次比较；同分时按声明的个体序号排序。多个指标不混成一个不透明总分。",
                  )}
                </p>
                {p.criteria.map((criterion: any, index: number) => (
                  <div className="evolution-criterion" key={index}>
                    <Field label={t("指标 {index}", { index: index + 1 })}>
                      <select
                        required
                        disabled={busy || readOnly}
                        value={criterion.metric}
                        onChange={(e) =>
                          edit({
                            ...p,
                            criteria: p.criteria.map((c: any, i: number) =>
                              i === index
                                ? { ...c, metric: e.target.value }
                                : c,
                            ),
                          })
                        }
                      >
                        <option value="">{t("请选择指标")}</option>
                        {catalogue.metrics.map((m: any) => (
                          <option value={m.id} key={m.id}>
                            {t(m.label)} · {t(m.unit)}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label={t("方向")}>
                      <select
                        disabled={busy || readOnly}
                        value={criterion.direction}
                        onChange={(e) =>
                          edit({
                            ...p,
                            criteria: p.criteria.map((c: any, i: number) =>
                              i === index
                                ? { ...c, direction: e.target.value }
                                : c,
                            ),
                          })
                        }
                      >
                        <option value="maximize">{t("较高优先")}</option>
                        <option value="minimize">{t("较低优先")}</option>
                      </select>
                    </Field>
                    <Field label={t("跨环境聚合")}>
                      <select
                        disabled={busy || readOnly}
                        value={criterion.aggregate ?? "mean"}
                        onChange={(e) =>
                          edit({
                            ...p,
                            criteria: p.criteria.map((c: any, i: number) =>
                              i === index
                                ? { ...c, aggregate: e.target.value }
                                : c,
                            ),
                          })
                        }
                      >
                        <option value="mean">{t("均值")}</option>
                        <option value="median">{t("中位数")}</option>
                        <option value="worst">{t("最差环境")}</option>
                      </select>
                    </Field>
                    {!readOnly && (
                      <div className="evolution-order">
                        {[-1, 1].map((direction) => (
                          <Button
                            key={direction}
                            type="button"
                            aria-label={t(
                              direction < 0
                                ? "提高指标 {index} 优先级"
                                : "降低指标 {index} 优先级",
                              { index: index + 1 },
                            )}
                            disabled={
                              busy ||
                              index + direction < 0 ||
                              index + direction >= p.criteria.length
                            }
                            onClick={() => {
                              const criteria = [...p.criteria];
                              [criteria[index], criteria[index + direction]] = [
                                criteria[index + direction],
                                criteria[index],
                              ];
                              edit({ ...p, criteria });
                            }}
                          >
                            {direction < 0 ? (
                              <ArrowUp size={15} />
                            ) : (
                              <ArrowDown size={15} />
                            )}
                          </Button>
                        ))}
                        <Button
                          type="button"
                          aria-label={t("移除指标 {index}", {
                            index: index + 1,
                          })}
                          disabled={busy}
                          onClick={() =>
                            edit({
                              ...p,
                              criteria: p.criteria.filter(
                                (_: any, i: number) => i !== index,
                              ),
                            })
                          }
                        >
                          <Trash2 size={15} />
                        </Button>
                      </div>
                    )}
                    <p className="footnote">
                      {t(
                        catalogue.metrics.find(
                          (m: any) => m.id === criterion.metric,
                        )?.hint ?? "请选择指标",
                      )}
                    </p>
                  </div>
                ))}
                {!readOnly && (
                  <Button
                    type="button"
                    disabled={busy || p.criteria.length >= 8}
                    onClick={() =>
                      edit({
                        ...p,
                        criteria: [
                          ...p.criteria,
                          {
                            metric: "",
                            direction: "maximize",
                            aggregate: "mean",
                          },
                        ],
                      })
                    }
                  >
                    <Plus size={15} />
                    {t("添加筛选指标")}
                  </Button>
                )}
              </section>
              <details className="evolution-seeds">
                <summary>{t("高级参数：独立环境种子表")}</summary>
                {!readOnly && (
                  <>
                    <div className="evolution-grid">
                      <Field label={t("种子生成器初值")}>
                        <input
                          type="number"
                          min={0}
                          max={4294967295}
                          step={1}
                          value={seed}
                          disabled={busy}
                          onChange={(e) => setSeed(Number(e.target.value))}
                        />
                      </Field>
                      <Field label={t("筛选环境数")}>
                        <input
                          type="number"
                          min={1}
                          max={32}
                          step={1}
                          value={evaluationBlocks}
                          disabled={busy}
                          onChange={(e) =>
                            setEvaluationBlocks(Number(e.target.value))
                          }
                        />
                      </Field>
                      <Field label={t("最终验证环境数")}>
                        <input
                          type="number"
                          min={1}
                          max={32}
                          step={1}
                          value={verificationBlocks}
                          disabled={busy}
                          onChange={(e) =>
                            setVerificationBlocks(Number(e.target.value))
                          }
                        />
                      </Field>
                    </div>
                    <Button
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        action(async () => {
                          const plan = await post<any>(`${root}/seeds`, {
                            seed,
                            generations: p.generations,
                            population_size: p.population_size,
                            evaluation_blocks: evaluationBlocks,
                            verification_blocks: verificationBlocks,
                          });
                          edit({ ...p, ...plan });
                          setGeneration(0);
                        })
                      }
                    >
                      {t("按当前规模重新生成种子表")}
                    </Button>
                    <p className="footnote">
                      {t(
                        "改变代数或个体数后，请重新生成或编辑下表。提交的是实际种子表，生成器初值不参与内核。",
                      )}
                    </p>
                  </>
                )}
                <Field label={t("查看发育种子的代次")}>
                  <select
                    value={displayedGeneration}
                    onChange={(e) => setGeneration(Number(e.target.value))}
                  >
                    {p.development_seeds.map((_: any, i: number) => (
                      <option value={i} key={i}>
                        {i + 1}
                      </option>
                    ))}
                  </select>
                </Field>
                <div className="evolution-seed-grid">
                  {seedRow.map((value: number, index: number) => (
                    <Field
                      key={index}
                      label={t("个体 {index}", { index: index + 1 })}
                    >
                      <input
                        type="number"
                        min={0}
                        max={4294967295}
                        step={1}
                        value={value}
                        disabled={busy || readOnly}
                        onChange={(e) =>
                          edit({
                            ...p,
                            development_seeds: p.development_seeds.map(
                              (row: number[], g: number) =>
                                g === displayedGeneration
                                  ? row.map((n: number, i: number) =>
                                      i === index ? Number(e.target.value) : n,
                                    )
                                  : row,
                            ),
                          })
                        }
                      />
                    </Field>
                  ))}
                </div>
                {[
                  ["evaluation_seeds", "筛选评估种子"],
                  ["verification_seeds", "最终独立验证种子"],
                ].map(([key, label]) => (
                  <section key={key}>
                    <h4>{t(label)}</h4>
                    <div className="evolution-seed-grid">
                      {p[key].map((value: number, index: number) => (
                        <Field
                          key={index}
                          label={t("环境 {index}", { index: index + 1 })}
                        >
                          <input
                            type="number"
                            min={0}
                            max={4294967295}
                            step={1}
                            value={value}
                            disabled={busy || readOnly}
                            onChange={(e) =>
                              edit({
                                ...p,
                                [key]: p[key].map((n: number, i: number) =>
                                  i === index ? Number(e.target.value) : n,
                                ),
                              })
                            }
                          />
                        </Field>
                      ))}
                    </div>
                  </section>
                ))}
              </details>
              <p className="footnote">
                {t(
                  "按当前规模最多创建 {count} 个发育、筛选或验证个体；暂停与重试复用原个体。",
                  { count: totalRuns },
                )}
              </p>
            </>
          )}
          <ErrorBox error={error} />
          {notice && <p className="configuration-success">{notice}</p>}
          <div className="modal-actions">
            <Button type="button" disabled={busy} onClick={close}>
              {t("关闭")}
            </Button>
            {jsonMode && (
              <Button
                type="button"
                disabled={busy}
                onClick={() =>
                  action(async () =>
                    setRaw(JSON.stringify(await parsed(), null, 2)),
                  )
                }
              >
                {t("格式化")}
              </Button>
            )}
            {!readOnly && (
              <>
                <Button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    action(async () => {
                      const value = await validated();
                      setP(value);
                      if (jsonMode) setRaw(JSON.stringify(value, null, 2));
                      setNotice(t("校验通过，三组种子不重叠，继承身份一致。"));
                    })
                  }
                >
                  {t("校验")}
                </Button>
                <Button type="submit" disabled={busy}>
                  {t("创建多代实验")}
                </Button>
              </>
            )}
          </div>
        </form>
      </Modal>
      {editing && (
        <SpecEditor
          key={editing}
          stage={editing}
          initial={p[editing]}
          readOnly={readOnly}
          locked={[
            "environment_seed",
            ...(editing === "evaluation" || p.initial_version_id
              ? catalogue.shared_paths
              : []),
          ]}
          close={() => setEditing(null)}
          save={(spec: any) => {
            edit(
              editing === "development"
                ? {
                    ...p,
                    development: spec,
                    evaluation: shared(
                      p.evaluation,
                      spec,
                      catalogue.shared_paths,
                    ),
                  }
                : { ...p, evaluation: spec },
            );
            setEditing(null);
          }}
        />
      )}
    </>
  );
}

function Trend({ rows, label }: { rows: any[]; label: string }) {
  if (!rows.length) return null;
  const low = Math.min(...rows.map((r) => r.minimum)),
    high = Math.max(...rows.map((r) => r.maximum)),
    margin = (high - low) * 0.05 || Math.max(Math.abs(high) * 0.05, 0.5),
    floor = low - margin,
    ceiling = high + margin,
    span = ceiling - floor;
  const x = (i: number) => 55 + (i * 540) / Math.max(1, rows.length - 1),
    y = (value: number) => 175 - ((value - floor) / span) * 130;
  const line = (key: string) =>
    rows.map((r, i) => `${x(i)},${y(r[key])}`).join(" ");
  return (
    <figure className="evolution-trend">
      <figcaption>
        {label} · {t("跨代描述统计")}
      </figcaption>
      <svg
        viewBox="0 0 650 220"
        role="img"
        aria-label={`${label} ${t("跨代描述统计")}`}
      >
        <path
          d="M55 25 V175 H610"
          fill="none"
          stroke="currentColor"
          opacity=".3"
        />
        {rows.map((r, i) => (
          <line
            key={r.generation}
            x1={x(i)}
            x2={x(i)}
            y1={y(r.minimum)}
            y2={y(r.maximum)}
            stroke="#79a9a1"
            opacity=".55"
            strokeWidth="4"
          />
        ))}
        <polyline
          points={line("mean")}
          fill="none"
          stroke="#257e70"
          strokeWidth="2"
        />
        <polyline
          points={line("parent_mean")}
          fill="none"
          stroke="#b36c25"
          strokeWidth="2"
        />
        {rows.map((r, i) => (
          <g key={r.generation}>
            <circle cx={x(i)} cy={y(r.mean)} r="3" fill="#257e70" />
            <circle cx={x(i)} cy={y(r.parent_mean)} r="2" fill="#b36c25" />
          </g>
        ))}
        <text x="8" y="48">
          {numberLabel(ceiling, 4)}
        </text>
        <text x="8" y="179">
          {numberLabel(floor, 4)}
        </text>
        <text x="55" y="202">
          {rows[0].generation + 1}
        </text>
        <text x="590" y="202">
          {rows.at(-1).generation + 1}
        </text>
      </svg>
      <p className="footnote">
        {t(
          "绿色：全部候选均值；棕色：已选父本均值；竖线：最小至最大值。只展示所选代及之前最多 100 代；不是置信区间。",
        )}
      </p>
    </figure>
  );
}

function EvolutionDetail({ id, catalogue, write }: any) {
  const { project } = useWorkspace(),
    client = useQueryClient(),
    root = `${projectPath(project!.id)}/evolutions/${id}`;
  const [generation, setGeneration] = useState<number | null>(null),
    [stage, setStage] = useState(""),
    [offset, setOffset] = useState(0),
    [metric, setMetric] = useState(""),
    [showProtocol, setShowProtocol] = useState(false);
  const [exportOperation, setExportOperation] = useState(() =>
    crypto.randomUUID(),
  );
  const query = new URLSearchParams({
    offset: String(offset),
    ...(generation === null ? {} : { generation: String(generation) }),
    ...(stage ? { stage } : {}),
  });
  const detail = useQuery({
    queryKey: ["evolution", project!.id, id, query.toString()],
    queryFn: () => api<any>(`${root}?${query}`),
    refetchInterval: (q) =>
      q.state.data?.status === "active" ||
      q.state.data?.members.some((m: any) =>
        ["queued", "running"].includes(m.run_status),
      )
        ? 2000
        : false,
  });
  const protocol = useQuery({
    queryKey: ["evolution-protocol", project!.id, id],
    queryFn: () => api<any>(`${root}/protocol`),
    staleTime: Infinity,
    enabled: showProtocol,
  });
  const exports = useQuery({
    queryKey: ["evolution-exports", project!.id, id],
    queryFn: () => api<any[]>(`${root}/exports`),
    refetchInterval: (q) =>
      q.state.data?.some((j: any) => ["pending", "leased"].includes(j.status))
        ? 2000
        : false,
  });
  const controls = useMutation({
    mutationFn: (action: string) =>
      post(`${root}/controls`, {
        action,
        expected_revision: detail.data.revision,
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["evolution"] });
      void client.invalidateQueries({ queryKey: ["evolutions"] });
    },
  });
  const exportNow = useMutation({
    mutationFn: () =>
      post(`${root}/exports`, { operation_id: exportOperation }),
    onSuccess: () => {
      setExportOperation(crypto.randomUUID());
      void client.invalidateQueries({ queryKey: ["evolution-exports"] });
    },
  });
  if (detail.isPending) return <Loading />;
  if (!detail.data) return <ErrorBox error={detail.error} />;
  const value = detail.data,
    selectedMetric = metric || value.summary.criteria[0].metric,
    label =
      catalogue.metrics.find((m: any) => m.id === selectedMetric)?.label ??
      selectedMetric;
  return (
    <div className="evolution-detail">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>{value.name}</h2>
            <p>{value.objective}</p>
          </div>
          <Badge
            status={value.status === "active" ? "running" : value.status}
          />
        </div>
        <p>
          {t("当前代 {generation} / {total}", {
            generation: value.generation + 1,
            total: value.summary.generations,
          })}{" "}
          · {t(stages[value.phase])} · r{value.revision}
        </p>
        <p className="footnote">
          {t(
            "最终独立验证在父本选定后执行，不重新排序，不作为下一代遗传来源。所有指标只按冻结协议解释。",
          )}
        </p>
        <div className="query-controls">
          <Button onClick={() => setShowProtocol(true)}>
            {t("查看冻结协议")}
          </Button>
          <Button onClick={() => detail.refetch()}>{t("刷新")}</Button>
          {value.status === "active" && (
            <Button
              disabled={!write || controls.isPending}
              onClick={() => controls.mutate("pause")}
            >
              {t("暂停实验")}
            </Button>
          )}
          {["paused", "blocked"].includes(value.status) && (
            <Button
              disabled={!write || controls.isPending}
              onClick={() =>
                controls.mutate(value.status === "blocked" ? "retry" : "resume")
              }
            >
              {t(value.status === "blocked" ? "重试失败任务" : "继续实验")}
            </Button>
          )}
          {!["completed", "cancelled"].includes(value.status) && (
            <Button
              disabled={!write || controls.isPending}
              onClick={() => controls.mutate("cancel")}
            >
              {t("终止此实验")}
            </Button>
          )}
        </div>
        <ErrorBox error={controls.error || detail.error} />
        {value.error && <p className="notice">{value.error}</p>}
        <div className="evolution-counts">
          {value.counts.map((c: any) => (
            <span key={`${c.stage}:${c.status}`}>
              {t(stages[c.stage])} · <Badge status={c.status} /> {c.count}
            </span>
          ))}
        </div>
      </section>
      <section className="panel">
        <div className="query-controls">
          <Field label={t("查看代次")}>
            <select
              value={generation ?? "latest"}
              onChange={(e) => {
                setGeneration(
                  e.target.value === "latest" ? null : Number(e.target.value),
                );
                setOffset(0);
              }}
            >
              <option value="latest">{t("跟随当前代")}</option>
              {Array.from({ length: value.generation + 1 }, (_, i) => (
                <option key={i} value={i}>
                  {i + 1}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("描述指标")}>
            <select
              value={selectedMetric}
              onChange={(e) => setMetric(e.target.value)}
            >
              {value.summary.criteria.map((c: any) => (
                <option key={c.metric} value={c.metric}>
                  {t(
                    catalogue.metrics.find((m: any) => m.id === c.metric)
                      ?.label ?? c.metric,
                  )}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Trend
          rows={value.progress.filter((r: any) => r.metric === selectedMetric)}
          label={t(label)}
        />
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t("排序")}</th>
                <th>{t("个体")}</th>
                <th>{t("成为父本")}</th>
                {value.summary.criteria.map((c: any) => (
                  <th key={c.metric}>
                    {t(
                      catalogue.metrics.find((m: any) => m.id === c.metric)
                        ?.label ?? c.metric,
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {value.selections.map((s: any) => (
                <tr key={s.slot}>
                  <td>{s.rank}</td>
                  <td>{s.slot + 1}</td>
                  <td>{t(s.selected ? "是" : "否")}</td>
                  {value.summary.criteria.map((c: any) => (
                    <td key={c.metric}>{numberLabel(s.scores[c.metric], 6)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!value.selections.length && (
          <p className="footnote">
            {t("本代尚未完成筛选；不会用未完成或失败的结果填零。")}
          </p>
        )}
      </section>
      <section className="panel">
        <h3>{t("个体、来源与固定证据")}</h3>
        <Field label={t("个体阶段")}>
          <select
            value={stage}
            onChange={(e) => {
              setStage(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">{t("全部阶段")}</option>
            {["development", "evaluation", "verification"].map((key) => (
              <option key={key} value={key}>
                {t(stages[key])}
              </option>
            ))}
          </select>
        </Field>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t("阶段 / 个体 / 环境")}</th>
                <th>{t("环境种子")}</th>
                <th>{t("状态")}</th>
                <th>{t("模拟时间")}</th>
                <th>{t("固定恢复点")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {value.members.map((m: any) => (
                <tr key={m.id}>
                  <td>
                    {t(stages[m.stage])} / {m.slot + 1} / {m.block_index + 1}
                  </td>
                  <td className="mono">{m.environment_seed}</td>
                  <td>
                    <Badge status={m.run_status} />
                  </td>
                  <td>{timeLabel(m.time_us)}</td>
                  <td className="mono" title={m.state_hash ?? ""}>
                    <details className="evolution-provenance">
                      <summary>
                        {m.checkpoint_id?.slice(0, 8) ?? t("尚未固定")}
                      </summary>
                      <dl>
                        <dt>{t("继承来源版本")}</dt>
                        <dd>{m.source_version_id ?? t("从空白结构开始")}</dd>
                        <dt>{t("发育候选版本")}</dt>
                        <dd>{m.candidate_version_id ?? "—"}</dd>
                        <dt>{t("固定恢复点")}</dt>
                        <dd>{m.checkpoint_id ?? "—"}</dd>
                        <dt>{t("状态哈希")}</dt>
                        <dd>{m.state_hash ?? "—"}</dd>
                      </dl>
                      {m.outcome && (
                        <pre>{JSON.stringify(m.outcome, null, 2)}</pre>
                      )}
                    </details>
                    {m.outcome?.lifetime_right_censored && (
                      <small>{t("寿命右删失")}</small>
                    )}
                  </td>
                  <td>
                    <Link to={`/runs/${m.run_id}`}>{t("查看个体")}</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="development-pagination">
          <Button
            disabled={!offset}
            onClick={() => setOffset(Math.max(0, offset - 60))}
          >
            {t("上一页")}
          </Button>
          <span>{t("第 {page} 页", { page: offset / 60 + 1 })}</span>
          <Button
            disabled={!value.members_more}
            onClick={() => setOffset(offset + 60)}
          >
            {t("下一页")}
          </Button>
        </div>
      </section>
      <section className="panel">
        <h3>{t("多代实验证据包")}</h3>
        <p className="footnote">
          {t(
            "后台按执行时的一致快照导出全部个体、指标、选择与日志。原始输入、轨迹和模型仍可从对应个体及恢复点导出；此包不会冒充完整运行档案。",
          )}
        </p>
        <Button
          disabled={!write || exportNow.isPending}
          onClick={() => exportNow.mutate()}
        >
          {t("生成证据 ZIP")}
        </Button>
        <ErrorBox error={exportNow.error || exports.error} />
        <ul className="development-export-list">
          {exports.data?.map((j: any) => (
            <li key={j.id}>
              <Badge status={j.status} />
              {j.result?.artifact_id ? (
                <a
                  href={`/api/v2${projectPath(project!.id)}/artifacts/${j.result.artifact_id}`}
                  download
                >
                  {t("下载证据 ZIP")} · r{j.result.snapshot_revision}
                </a>
              ) : (
                j.error || t("等待后台导出")
              )}
            </li>
          ))}
        </ul>
      </section>
      <section className="panel">
        <details>
          <summary>{t("最近的协调与控制记录")}</summary>
          <ol className="evolution-journal">
            {value.events.map((event: any) => (
              <li key={event.revision}>
                <strong>
                  r{event.revision} · {event.kind}
                </strong>
                <time>{new Date(event.created_at).toLocaleString()}</time>
                <pre>{JSON.stringify(event.payload, null, 2)}</pre>
              </li>
            ))}
          </ol>
          <p className="footnote">
            {t("页面显示最近 30 条记录，证据包保留全部记录。")}
          </p>
        </details>
      </section>
      {showProtocol && protocol.data && (
        <EvolutionEditor
          catalogue={catalogue}
          initial={{ ...value, protocol: protocol.data.protocol }}
          readOnly
          close={() => setShowProtocol(false)}
        />
      )}
      {showProtocol && <ErrorBox error={protocol.error} />}
    </div>
  );
}

export default function Evolution() {
  const [params] = useSearchParams();
  const { project } = useWorkspace(),
    client = useQueryClient(),
    root = `${projectPath(project!.id)}/evolutions`;
  const [q, setQ] = useState(""),
    [offset, setOffset] = useState(0),
    [id, setId] = useState<string | null>(params.get("campaign")),
    [creating, setCreating] = useState(false);
  useEffect(() => {
    setId(params.get("campaign"));
    setOffset(0);
    setQ("");
    setCreating(false);
  }, [project!.id]);
  const catalogue = useQuery({
    queryKey: ["evolution-catalogue", project!.id],
    queryFn: () => api<any>(`${root}/catalogue`),
    staleTime: Infinity,
  });
  const list = useQuery({
    queryKey: ["evolutions", project!.id, q, offset],
    queryFn: () =>
      api<any>(`${root}?q=${encodeURIComponent(q)}&offset=${offset}`),
    refetchInterval: 10000,
  });
  const write = project!.role !== "viewer";
  return (
    <>
      <PageTitle
        eyebrow="DEVELOPMENT & SELECTION"
        title={t("多代定向训练")}
        description={t("以独立副本评估已塑形网络，保留完整选择与遗传证据。")}
      />
      <div className="evolution-search-controls">
        <Field label={t("搜索多代实验")}>
          <input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
          />
        </Field>
        <Button
          disabled={!write || !catalogue.data}
          onClick={() => setCreating(true)}
        >
          <Plus size={16} />
          {t("新建多代实验")}
        </Button>
      </div>
      <ErrorBox error={list.error || catalogue.error} />
      {list.isPending ? (
        <Loading />
      ) : list.data?.rows.length ? (
        <section className="panel">
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{t("实验名称")}</th>
                  <th>{t("状态")}</th>
                  <th>{t("当前代")}</th>
                  <th>{t("阶段")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {list.data.rows.map((row: any) => (
                  <tr key={row.id} className={id === row.id ? "selected" : ""}>
                    <td>{row.name}</td>
                    <td>
                      <Badge
                        status={
                          row.status === "active" ? "running" : row.status
                        }
                      />
                    </td>
                    <td>
                      {row.generation + 1} / {row.summary.generations}
                    </td>
                    <td>{t(stages[row.phase])}</td>
                    <td>
                      <Button onClick={() => setId(row.id)}>{t("查看")}</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="development-pagination">
            <Button
              disabled={!offset}
              onClick={() => setOffset(Math.max(0, offset - 30))}
            >
              {t("上一页")}
            </Button>
            <Button
              disabled={!list.data.more}
              onClick={() => setOffset(offset + 30)}
            >
              {t("下一页")}
            </Button>
          </div>
        </section>
      ) : (
        <Empty
          title={t("还没有多代实验")}
          detail={t("先选择明确的研究目标和筛选指标，再启动可重放的多代流程。")}
        />
      )}
      {id && catalogue.data && (
        <EvolutionDetail
          key={`${project!.id}:${id}`}
          id={id}
          catalogue={catalogue.data}
          write={write}
        />
      )}
      {creating && catalogue.data && (
        <EvolutionEditor
          catalogue={catalogue.data}
          close={() => setCreating(false)}
          done={(identity: string) => {
            setCreating(false);
            setId(identity);
            void client.invalidateQueries({ queryKey: ["evolutions"] });
          }}
        />
      )}
      <Link className="text-link" to="/docs?doc=docs/zh/v2-evolution.md">
        {t("查看遗传规则与演化边界")}
      </Link>
    </>
  );
}
