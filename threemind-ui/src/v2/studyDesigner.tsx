import DestinationSelector from "./DestinationSelector";
import { useAccess } from "./access";
import { t } from "./i18n";
import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Copy, Plus, Trash2, Play, Code2 } from "lucide-react";
import { api, post, projectPath } from "./api";
import { Button, CodeEditor, ErrorBox, Field, Loading, Modal } from "./ui";
import {
  ConfigurationEditor,
  NumericRows,
  useCatalogue,
  type Catalogue,
  type ConfigurationHandle,
} from "./configuration";

type Spec = Record<string, any>;
type Design = {
  defaults: Spec;
  runtime_roots: string[];
  legacy_roots: string[];
  shared_paths: string[];
  max_arms: number;
  max_seeds: number;
};
const equal = (a: any, b: any): boolean => {
  if (
    a &&
    b &&
    typeof a === "object" &&
    typeof b === "object" &&
    !Array.isArray(a) &&
    !Array.isArray(b)
  ) {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
    return [...keys].every((k) => equal(a[k], b[k]));
  }
  return JSON.stringify(a) === JSON.stringify(b);
};
function resolved(base: Spec, arm: Spec, design: Design): Spec {
  const value = structuredClone(base);
  value.config = { ...base.config, ...arm.config_patch };
  value.intervention = arm.intervention ?? null;
  for (const root of design.legacy_roots)
    if (arm[root] != null) value[root] = arm[root];
  for (const [root, patch] of Object.entries(arm.runtime_patch ?? {}))
    value[root] =
      patch && typeof patch === "object" ? { ...base[root], ...patch } : patch;
  return value;
}
function condition(base: Spec, next: Spec, arm: Spec, design: Design): Spec {
  const patch: Spec = {},
    runtime: Spec = {};
  for (const key of Object.keys(next.config))
    if (
      !equal(next.config[key], base.config[key]) ||
      key in (arm.config_patch ?? {})
    )
      patch[key] = next.config[key];
  for (const root of design.runtime_roots) {
    if (next[root] && typeof next[root] === "object") {
      const changed: Spec = {};
      for (const key of Object.keys(next[root]))
        if (
          !equal(next[root][key], base[root]?.[key]) ||
          key in (arm.runtime_patch?.[root] ?? {}) ||
          arm[root] != null
        )
          changed[key] = next[root][key];
      if (Object.keys(changed).length) runtime[root] = changed;
    } else if (
      !equal(next[root], base[root]) ||
      root in (arm.runtime_patch ?? {}) ||
      arm[root] != null
    )
      runtime[root] = next[root];
  }
  return {
    name: arm.name,
    config_patch: patch,
    runtime_patch: runtime,
    intervention: next.intervention,
    phases:
      !equal(next.phases, base.phases) || arm.phases != null
        ? next.phases
        : null,
  };
}
function cleanProtocol(value: Spec, catalogue: Catalogue): Spec {
  const base = {
    ...structuredClone(catalogue.defaults),
    ...structuredClone(value.base),
  };
  for (const [key, entry] of Object.entries(catalogue.defaults))
    if (entry && typeof entry === "object" && !Array.isArray(entry))
      base[key] = { ...entry, ...value.base?.[key] };
  return { ...structuredClone(value), base };
}

export function StudyDesigner({
  project,
  initial,
  close,
  created,
}: {
  project: string;
  initial?: Spec;
  close: () => void;
  created: (id: string, project?: string) => void;
}) {
  const catalogue = useCatalogue();
  const design = useQuery({
    queryKey: ["study-configuration"],
    queryFn: () => api<Design>("/study-configuration"),
    staleTime: Infinity,
  });
  return (
    <Modal
      open
      onOpenChange={close}
      title={t("设计配对实验")}
      wide
      description={t(
        "编辑共同基础与各条件差异；冻结前统一校验，执行后保留完整协议。",
      )}
    >
      <ErrorBox error={catalogue.error ?? design.error} />
      {catalogue.data && design.data ? (
        <Designer
          project={project}
          catalogue={catalogue.data}
          design={design.data}
          initial={initial}
          close={close}
          created={created}
        />
      ) : (
        <Loading />
      )}
    </Modal>
  );
}

function Designer({
  project: initialProject,
  catalogue,
  design,
  initial,
  close,
  created,
}: {
  project: string;
  catalogue: Catalogue;
  design: Design;
  initial?: Spec;
  close: () => void;
  created: (id: string, project?: string) => void;
}) {
  const [project, setProject] = useState(initialProject);
  const allowed = useAccess();
  const [protocol, setProtocol] = useState<Spec>(() =>
    cleanProtocol(initial ?? design.defaults, catalogue),
  );
  const [mode, setMode] = useState("form"),
    [raw, setRaw] = useState("");
  const [error, setError] = useState<unknown>(),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  const [template, setTemplate] = useState("mechanisms"),
    [undo, setUndo] = useState<Spec>();
  const [drive, setDrive] = useState(3),
    [quiet, setQuiet] = useState(6),
    [recovery, setRecovery] = useState(3);
  const [sweepPath, setSweepPath] = useState("config.propagation_rate"),
    [sweepValues, setSweepValues] = useState("0, 1, 2, 4.2");
  const [editing, setEditing] = useState<number | "base" | null>(null),
    [block, setBlock] = useState<string | null>(null);
  const editor = useRef<ConfigurationHandle>(null);
  const sweepFields = catalogue.fields.filter(
    (f) =>
      !design.shared_paths.includes(f.path) &&
      (f.path.startsWith("config.") ||
        design.runtime_roots.includes(f.path.split(".")[0])) &&
      !f.nullable,
  );
  function changed(next: Spec) {
    setProtocol(next);
    setNotice("");
    setError(undefined);
  }
  async function value() {
    return mode === "form"
      ? protocol
      : (await import("./JsonEditor")).parseJson(raw);
  }
  async function check(candidate?: Spec): Promise<Spec | null> {
    setError(undefined);
    setNotice("");
    try {
      const result = await post<any>(
        project
          ? `${projectPath(project)}/studies/validate`
          : "/studies/validate",
        candidate ?? (await value()),
      );
      if (!result.valid)
        throw new Error(
          result.errors
            .map((e: any) => `${e.path || "协议"}：${e.message}`)
            .join("\n"),
        );
      setNotice(
        [
          "校验通过：共同身份、所有条件、阶段与重放区组均已检查。",
          ...result.warnings,
        ].join("\n"),
      );
      return result.protocol;
    } catch (e) {
      setError(e);
      return null;
    }
  }
  async function toggle() {
    if (mode === "form") {
      setRaw(JSON.stringify(protocol, null, 2));
      setMode("json");
    } else {
      setBusy(true);
      try {
        const next = await check();
        if (next) {
          setProtocol(next);
          setMode("form");
        }
      } finally {
        setBusy(false);
      }
    }
  }
  async function freeze() {
    setBusy(true);
    try {
      const next = await check();
      if (!next) return;
      const job = await post<any>(`${projectPath(project)}/studies`, next);
      created(job.params.study_id, project);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  function applyTemplate() {
    try {
      const next = structuredClone(protocol);
      const names: Record<string, string> = {
        mechanisms: "局部机制消融",
        withdrawal: "刺激撤除与恢复",
        sensory: "感官与反馈对照",
        sweep: "参数扫描",
        custom: "自定义配对实验",
      };
      next.name = names[template];
      if (template === "mechanisms")
        next.arms = [
          { name: "完整可塑性", config_patch: {} },
          { name: "关闭可塑性", config_patch: { plasticity: false } },
          { name: "关闭局部抑制", config_patch: { inhibition: false } },
        ];
      if (template === "sensory")
        next.arms = [
          { name: "完整感官闭环" },
          { name: "单通道", runtime_patch: { max_channels: 1 } },
          { name: "双通道", runtime_patch: { max_channels: 2 } },
          { name: "关闭动作反馈", runtime_patch: { actuator_feedback: false } },
        ];
      if (template === "withdrawal") {
        if (
          [drive, quiet, recovery].some(
            (v) => !Number.isFinite(v) || v < 0.000001,
          )
        )
          throw new Error(t("三个阶段均须至少一微秒。"));
        next.base.duration_s =
          Math.round((drive + quiet + recovery) * 1e6) / 1e6;
        next.base.phases = [drive, quiet, recovery].map((duration_s, i) => ({
          name: ["驱动", "撤除窗口", "恢复"][i],
          duration_s,
          input_enabled: true,
          close_sources: false,
        }));
        const phases = next.base.phases.map((p: Spec, i: number) => ({
          ...p,
          input_enabled: i !== 1,
        }));
        next.arms = [
          { name: "持续驱动" },
          { name: "撤除与恢复", phases },
          {
            name: "撤除并关闭传播",
            config_patch: { propagation_rate: 0 },
            phases,
          },
        ];
      }
      if (template === "sweep") {
        const field = sweepFields.find((f) => f.path === sweepPath)!;
        const values = sweepValues.split(",").map((v) => {
          if (!v.trim()) throw new Error(t("扫描值不能为空。"));
          return field.type === "boolean"
            ? v.trim() === "true"
              ? true
              : v.trim() === "false"
                ? false
                : undefined
            : field.type === "string"
              ? v.trim()
              : Number(v);
        });
        if (
          values.length < 2 ||
          values.length > 12 ||
          new Set(values).size !== values.length ||
          values.some(
            (v) =>
              v === undefined || (typeof v === "number" && !Number.isFinite(v)),
          )
        )
          throw new Error(
            t("扫描需要 2–12 个互不重复的有效值；布尔值使用 true / false。"),
          );
        const [root, key] = sweepPath.split(".");
        next.arms = values.map((v) => ({
          name: `${field.label} = ${v}`,
          ...(root === "config"
            ? { config_patch: { [key]: v } }
            : { runtime_patch: { [root]: key ? { [key]: v } : v } }),
        }));
      }
      if (template === "custom")
        next.arms = [{ name: "对照" }, { name: "实验条件" }];
      setUndo(protocol);
      changed(next);
    } catch (e) {
      setError(e);
    }
  }
  async function applyConfiguration() {
    setBusy(true);
    try {
      const next = await editor.current?.validate();
      if (!next) return;
      if (editing === "base") changed({ ...protocol, base: next });
      else if (typeof editing === "number") {
        // Server validation also checks read-only identities after JSON edits.
        const changes = design.shared_paths.filter((path) => {
          const at = (s: Spec) =>
            path.split(".").reduce((v, key) => v?.[key], s);
          return !equal(at(next), at(protocol.base));
        });
        if (changes.length) {
          setError(
            new Error(
              t("这些参数在条件间共享，请在基础协议配置：{value0}", {
                value0: String(changes.join("、")),
              }),
            ),
          );
          return;
        }
        const arm = condition(
          protocol.base,
          next,
          protocol.arms[editing],
          design,
        );
        const candidate = {
          ...protocol,
          arms: protocol.arms.map((a: Spec, i: number) =>
            i === editing ? arm : a,
          ),
        };
        const checked = await check(candidate);
        if (!checked) return;
        changed(checked);
      }
      setEditing(null);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="study-designer" aria-label={t("实验协议编辑器")}>
      <div className="configuration-heading">
        <div>
          <h3>{t("研究协议")}</h3>
          <p>
            {t("基础协议提供默认值；条件只保存显式覆盖。现有实验不会被改写。")}
          </p>
        </div>
        <button
          type="button"
          className="text-link"
          onClick={toggle}
          disabled={busy}
        >
          <Code2 size={14} />
          {mode === "form" ? t("切换到协议 JSON") : t("切换到图形设计")}
        </button>
      </div>
      {mode === "json" ? (
        <>
          <CodeEditor
            label={t("实验协议 JSON")}
            value={raw}
            onChange={(v) => {
              setRaw(v);
              setError(undefined);
              setNotice("");
            }}
            rows={22}
          />
          <div className="json-actions">
            <Button
              type="button"
              onClick={async () => {
                try {
                  setRaw(JSON.stringify(await value(), null, 2));
                  setError(undefined);
                } catch (e) {
                  setError(e);
                }
              }}
            >
              {t("格式化协议")}
            </Button>
          </div>
        </>
      ) : (
        <>
          <div className="form-grid">
            <Field label={t("实验名称")}>
              <input
                value={protocol.name}
                maxLength={120}
                onChange={(e) => changed({ ...protocol, name: e.target.value })}
              />
            </Field>
            <Field
              label={t("独立环境种子")}
              hint={t(
                "2–64 个独立区组。重放模式须为每个编号提供独立采集的刺激记录。",
              )}
            >
              <input
                aria-label={t("独立环境种子")}
                value={protocol.seeds.map((s: any) => s ?? "").join(", ")}
                onChange={(e) =>
                  changed({
                    ...protocol,
                    seeds: e.target.value
                      .split(",")
                      .map((s) => (s.trim() === "" ? null : Number(s.trim()))),
                  })
                }
              />
            </Field>
            <Field label={t("共同发育时长（模拟秒）")}>
              <input
                type="number"
                min={0}
                max={300}
                step="any"
                value={protocol.warmup_s ?? ""}
                onChange={(e) =>
                  changed({
                    ...protocol,
                    warmup_s:
                      e.target.value === "" ? null : Number(e.target.value),
                  })
                }
              />
            </Field>
            <Field
              label={t("条件运行时长（模拟秒）")}
              hint={
                protocol.base.phases?.length
                  ? t("已分阶段；请在基础协议中调整阶段与总时长。")
                  : undefined
              }
            >
              <input
                type="number"
                min={0.000001}
                max={catalogue.max_run_seconds}
                step="any"
                readOnly={!!protocol.base.phases?.length}
                aria-label={t("条件运行时长（模拟秒）")}
                value={protocol.base.duration_s ?? ""}
                onChange={(e) =>
                  changed({
                    ...protocol,
                    base: {
                      ...protocol.base,
                      duration_s:
                        e.target.value === "" ? null : Number(e.target.value),
                    },
                  })
                }
              />
            </Field>
          </div>
          <details className="study-template">
            <summary>{t("从研究模板开始")}</summary>
            <div className="form-grid">
              <Field label={t("研究模板")}>
                <select
                  value={template}
                  onChange={(e) => setTemplate(e.target.value)}
                >
                  <option value="mechanisms">{t("局部机制消融")}</option>
                  <option value="withdrawal">{t("刺激撤除与恢复")}</option>
                  <option value="sensory">{t("感官带宽与动作反馈")}</option>
                  <option value="sweep">{t("任意可变参数扫描")}</option>
                  <option value="custom">{t("自定义条件")}</option>
                </select>
              </Field>
              {template === "withdrawal" &&
                [
                  ["驱动阶段（秒）", drive, setDrive],
                  ["撤除窗口（秒）", quiet, setQuiet],
                  ["恢复阶段（秒）", recovery, setRecovery],
                ].map(([label, v, set]) => (
                  <Field key={String(label)} label={t(String(label))}>
                    <input
                      type="number"
                      step="any"
                      min={0.000001}
                      value={v as number}
                      onChange={(e) =>
                        (set as (n: number) => void)(Number(e.target.value))
                      }
                    />
                  </Field>
                ))}
              {template === "sweep" && (
                <>
                  <Field label={t("扫描参数")}>
                    <select
                      aria-label={t("扫描参数")}
                      value={sweepPath}
                      onChange={(e) => setSweepPath(e.target.value)}
                    >
                      {sweepFields.map((f) => (
                        <option key={f.path} value={f.path}>
                          {t(f.label)} · {f.path}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field
                    label={t("参数取值")}
                    hint={t("逗号分隔。数值、布尔或枚举值按实际参数类型校验。")}
                  >
                    <input
                      aria-label={t("参数取值")}
                      value={sweepValues}
                      onChange={(e) => setSweepValues(e.target.value)}
                    />
                  </Field>
                </>
              )}
            </div>
            <div className="json-actions">
              <Button type="button" onClick={applyTemplate}>
                {t("应用模板到草案")}
              </Button>
              {undo && (
                <Button
                  type="button"
                  onClick={() => {
                    changed(undo);
                    setUndo(undefined);
                  }}
                >
                  {t("撤销模板替换")}
                </Button>
              )}
            </div>
            <p className="footnote">
              {t(
                "应用模板替换条件组；撤除模板同时设置阶段。其他基础参数保留，所有条件仍可继续图形编辑。",
              )}
            </p>
          </details>
          <section className="study-base-summary">
            <h3>{t("共同基础协议")}</h3>
            <p>
              {t("核心、感官、来源、身体、读出、记录与阶段，共用")}{" "}
              {catalogue.fields.length}{" "}
              {t("项参数目录。共同身份和阶段时间由这里设置。")}
            </p>
            <Button type="button" onClick={() => setEditing("base")}>
              {t("配置基础协议")}
            </Button>
            {!!protocol.base.replay?.length && (
              <p className="notice">
                {t(
                  "这份旧协议含未参与配对执行的 base.replay。各区组的实际刺激仍在 replay_blocks。",
                )}
                <button
                  type="button"
                  className="text-link"
                  onClick={() =>
                    changed({
                      ...protocol,
                      base: { ...protocol.base, replay: [] },
                    })
                  }
                >
                  {t("移除未使用的基础重放帧")}
                </button>
              </p>
            )}
            <span>
              {catalogue.fields
                .find((f) => f.path === "environment")
                ?.choices?.find(
                  (c) => c[0] === protocol.base.environment,
                )?.[1] ?? protocol.base.environment}{" "}
              ·{" "}
              {catalogue.fields
                .find((f) => f.path === "clock")
                ?.choices?.find((c) => c[0] === protocol.base.clock)?.[1] ??
                protocol.base.clock}{" "}
              · {protocol.base.phases?.length ?? 0}
              {t(" 个阶段")}
            </span>
          </section>
          <div className="panel-heading">
            <h3>
              {t("条件与消融 · ")}
              {protocol.arms.length}
              {t(" 组")}
            </h3>
            <Button
              type="button"
              disabled={protocol.arms.length >= design.max_arms}
              onClick={() =>
                changed({
                  ...protocol,
                  arms: [
                    ...protocol.arms,
                    { name: `条件 ${protocol.arms.length + 1}` },
                  ],
                })
              }
            >
              <Plus size={14} />
              {t("添加条件")}
            </Button>
          </div>
          <div className="study-arm-grid">
            {protocol.arms.map((arm: Spec, i: number) => (
              <article
                className="study-arm-card"
                key={i}
                aria-label={t("实验条件 {value0}", { value0: String(i + 1) })}
              >
                <Field
                  label={t("条件 {value0} 名称", { value0: String(i + 1) })}
                >
                  <input
                    maxLength={80}
                    value={arm.name}
                    onChange={(e) =>
                      changed({
                        ...protocol,
                        arms: protocol.arms.map((a: Spec, k: number) =>
                          k === i ? { ...a, name: e.target.value } : a,
                        ),
                      })
                    }
                  />
                </Field>
                <p>
                  {Object.keys(arm.config_patch ?? {}).length}
                  {t(" 个核心覆盖 ·")}{" "}
                  {Object.keys(arm.runtime_patch ?? {}).length +
                    design.legacy_roots.filter(
                      (k) => k !== "phases" && arm[k] != null,
                    ).length}{" "}
                  {t("个工具分组覆盖")}
                </p>
                {arm.intervention && (
                  <p>
                    {t("已有结构干预：")}
                    {arm.intervention.nodes?.length ?? 0}
                    {t(" 个节点、")}
                    {arm.intervention.edges?.length ?? 0}
                    {t(" 条边")}
                  </p>
                )}
                {arm.phases && (
                  <p>
                    {t("阶段门控：")}
                    {arm.phases
                      .map(
                        (p: Spec) =>
                          `${p.name} ${p.close_sources ? "永久关闭" : p.input_enabled ? "接收" : "撤除"}`,
                      )
                      .join(" · ")}
                  </p>
                )}
                <div className="json-actions">
                  <Button type="button" onClick={() => setEditing(i)}>
                    {t("编辑条件参数")}
                  </Button>
                  <button
                    type="button"
                    className="text-link"
                    disabled={protocol.arms.length >= design.max_arms}
                    onClick={() =>
                      changed({
                        ...protocol,
                        arms: [
                          ...protocol.arms,
                          { ...structuredClone(arm), name: `${arm.name} 副本` },
                        ],
                      })
                    }
                  >
                    <Copy size={13} />
                    {t("复制条件")}
                  </button>
                  <button
                    type="button"
                    className="text-link"
                    disabled={protocol.arms.length <= 2}
                    onClick={() =>
                      changed({
                        ...protocol,
                        arms: protocol.arms.filter(
                          (_: Spec, k: number) => k !== i,
                        ),
                      })
                    }
                  >
                    <Trash2 size={13} />
                    {t("删除条件")}
                  </button>
                </div>
                <details>
                  <summary>{t("查看显式覆盖")}</summary>
                  <pre>{JSON.stringify(arm, null, 2)}</pre>
                  <button
                    type="button"
                    className="text-link"
                    onClick={() =>
                      changed({
                        ...protocol,
                        arms: protocol.arms.map((a: Spec, k: number) =>
                          k === i ? { name: a.name } : a,
                        ),
                      })
                    }
                  >
                    {t("清除覆盖，继承基础协议")}
                  </button>
                </details>
              </article>
            ))}
          </div>
          {protocol.base.environment === "replay" && (
            <section className="study-base-summary">
              <h3>{t("按区组配置重放刺激")}</h3>
              <p>
                {t(
                  "时间从共同培养开始计量；相同记录换编号不会产生新的独立样本。原始匿名帧可逐帧图形编辑或导入 JSON。",
                )}
              </p>
              <div className="json-actions">
                {protocol.seeds.map((seed: any, i: number) => (
                  <Button
                    key={i}
                    type="button"
                    disabled={!Number.isInteger(seed)}
                    onClick={() => setBlock(String(seed))}
                  >
                    {t("区组 ")}
                    {String(seed)} ·{" "}
                    {protocol.replay_blocks?.[seed]?.length ?? t("未配置")}
                    {t(" 帧")}
                  </Button>
                ))}
              </div>
              {Object.keys(protocol.replay_blocks ?? {})
                .filter((k) => !protocol.seeds.map(String).includes(k))
                .map((k) => (
                  <p key={k}>
                    {t("未使用区组 ")}
                    {k}{" "}
                    <button
                      className="text-link"
                      type="button"
                      onClick={() => {
                        const blocks = { ...protocol.replay_blocks };
                        delete blocks[k];
                        changed({ ...protocol, replay_blocks: blocks });
                      }}
                    >
                      {t("移除此区组")}
                    </button>
                  </p>
                ))}
            </section>
          )}
        </>
      )}
      <ErrorBox error={error} />
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      <DestinationSelector
        value={project}
        onChange={setProject}
        disabled={busy}
      />
      <div className="form-actions">
        <Button type="button" onClick={close}>
          {t("取消")}
        </Button>
        <Button
          type="button"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await check();
            } finally {
              setBusy(false);
            }
          }}
        >
          {t("校验协议")}
        </Button>
        <Button
          type="button"
          variant="primary"
          disabled={busy || !project || !allowed("experiments.create")}
          onClick={freeze}
        >
          <Play size={14} />
          {t("冻结协议并运行")}
        </Button>
      </div>
      {editing !== null && (
        <Modal
          open
          wide
          onOpenChange={() => setEditing(null)}
          title={
            editing === "base"
              ? t("共同基础协议")
              : t("条件参数 · {value0}", {
                  value0: String(protocol.arms[editing].name),
                })
          }
          description={
            editing === "base"
              ? t(
                  "参数改变后，未显式覆盖它的条件自动继承。重放区组单独配置，结构干预在各条件中设置。",
                )
              : t(
                  "这里只保存与基础协议的差异。共享身份与阶段时间为只读；阶段接收开关和已有结构干预可单独设置。",
                )
          }
        >
          <ConfigurationEditor
            key={String(editing)}
            ref={editor}
            catalogue={catalogue}
            project={project}
            initial={
              editing === "base"
                ? protocol.base
                : resolved(protocol.base, protocol.arms[editing], design)
            }
            lockedPaths={
              editing === "base"
                ? [
                    "intervention",
                    "replay",
                    "study_id",
                    "condition",
                    "block_seed",
                  ]
                : design.shared_paths
            }
            sharedPhaseStructure={editing !== "base"}
          />
          <ErrorBox error={error} />
          <div className="form-actions">
            <Button type="button" onClick={() => setEditing(null)}>
              {t("放弃本次编辑")}
            </Button>
            <Button
              type="button"
              variant="primary"
              disabled={busy}
              onClick={applyConfiguration}
            >
              {t("应用到协议草案")}
            </Button>
          </div>
        </Modal>
      )}
      {block !== null && (
        <ReplayEditor
          key={block}
          block={block}
          frames={protocol.replay_blocks?.[block] ?? []}
          base={protocol.base}
          project={project}
          close={() => setBlock(null)}
          save={(frames) => {
            changed({
              ...protocol,
              replay_blocks: { ...protocol.replay_blocks, [block]: frames },
            });
            setBlock(null);
          }}
        />
      )}
    </section>
  );
}

function ReplayEditor({
  block,
  frames,
  base,
  project,
  close,
  save,
}: {
  block: string;
  frames: Spec[];
  base: Spec;
  project: string;
  close: () => void;
  save: (frames: Spec[]) => void;
}) {
  const [rows, setRows] = useState(frames),
    [raw, setRaw] = useState(JSON.stringify(frames, null, 2)),
    [mode, setMode] = useState("form");
  const [page, setPage] = useState(0),
    [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  const lastPage = Math.max(0, Math.ceil(rows.length / 5) - 1),
    current = Math.min(page, lastPage);
  async function parse() {
    return mode === "form"
      ? rows
      : (await import("./JsonEditor")).parseJson(raw);
  }
  async function validate() {
    const values = await parse();
    const result = await post<any>(
      project
        ? `${projectPath(project)}/configuration/validate`
        : "/configuration/validate",
      { spec: { ...base, phases: [], intervention: null, replay: values } },
    );
    if (!result.valid)
      throw new Error(
        result.errors.map((e: any) => `${e.path}：${e.message}`).join("\n"),
      );
    return result.spec.replay;
  }
  function update(index: number, patch: Spec) {
    setRows(rows.map((r, i) => (i === index ? { ...r, ...patch } : r)));
    setError(undefined);
  }
  return (
    <Modal
      open
      wide
      onOpenChange={close}
      title={t("重放区组 {value0}", { value0: String(block) })}
      description={t(
        "匿名节点编号、幅值和实际时间组成刺激帧；标签解释不进入核心。导入和保存均按实际 Stimulus 契约校验。",
      )}
    >
      <div className="configuration-heading">
        <p>
          {rows.length}
          {t(" 帧 · 每页最多展示 5 帧")}
        </p>
        <button
          className="text-link"
          type="button"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              if (mode === "form") {
                setRaw(JSON.stringify(rows, null, 2));
                setMode("json");
              } else {
                setRows(await validate());
                setMode("form");
              }
            } catch (e) {
              setError(e);
            } finally {
              setBusy(false);
            }
          }}
        >
          {mode === "form" ? t("切换到刺激 JSON") : t("切换到帧表单")}
        </button>
      </div>
      {mode === "json" ? (
        <>
          <CodeEditor
            value={raw}
            onChange={setRaw}
            label={t("重放刺激 JSON")}
            rows={18}
          />
          <Button
            type="button"
            onClick={async () => {
              try {
                setRaw(JSON.stringify(await parse(), null, 2));
              } catch (e) {
                setError(e);
              }
            }}
          >
            {t("格式化刺激")}
          </Button>
        </>
      ) : (
        <>
          <Button
            type="button"
            disabled={rows.length >= 100000}
            onClick={() => {
              setRows([...rows, { time_us: "0", channels: [], intensity: 1 }]);
              setPage(Math.floor(rows.length / 5));
            }}
          >
            {t("添加刺激帧")}
          </Button>
          {rows.slice(current * 5, current * 5 + 5).map((frame, local) => {
            const index = current * 5 + local;
            return (
              <section className="configuration-row" key={index}>
                <h3>
                  {t("刺激帧 ")}
                  {index + 1}
                </h3>
                <div className="form-grid">
                  <Field
                    label={t("帧 {value0} 时间（微秒）", {
                      value0: String(index + 1),
                    })}
                  >
                    <input
                      inputMode="numeric"
                      value={frame.time_us}
                      onChange={(e) =>
                        update(index, { time_us: e.target.value })
                      }
                    />
                  </Field>
                  <Field
                    label={t("帧 {value0} 强度", { value0: String(index + 1) })}
                  >
                    <input
                      type="number"
                      min={0}
                      max={1}
                      step="any"
                      value={frame.intensity ?? 1}
                      onChange={(e) =>
                        update(index, {
                          intensity:
                            e.target.value === ""
                              ? null
                              : Number(e.target.value),
                        })
                      }
                    />
                  </Field>
                </div>
                <NumericRows
                  rows={frame.channels}
                  columns={[
                    { label: "匿名节点 ID", maximum: 4294967295 },
                    { label: "通道幅值", maximum: 1, fractional: true },
                  ]}
                  readOnly={false}
                  onChange={(channels) => update(index, { channels })}
                />
                <div className="json-actions">
                  <Button
                    type="button"
                    disabled={frame.channels.length >= 1024}
                    onClick={() =>
                      update(index, { channels: [...frame.channels, [0, 0.5]] })
                    }
                  >
                    {t("添加通道")}
                  </Button>
                  <button
                    className="text-link"
                    type="button"
                    onClick={() => setRows(rows.filter((_, i) => i !== index))}
                  >
                    {t("删除刺激帧")}
                  </button>
                </div>
              </section>
            );
          })}
          <div className="json-actions">
            <Button
              type="button"
              disabled={current === 0}
              onClick={() => setPage(current - 1)}
            >
              {t("上一页刺激")}
            </Button>
            <span>
              {current + 1} / {lastPage + 1}
            </span>
            <Button
              type="button"
              disabled={current === lastPage}
              onClick={() => setPage(current + 1)}
            >
              {t("下一页刺激")}
            </Button>
          </div>
        </>
      )}
      <ErrorBox error={error} />
      <div className="form-actions">
        <Button type="button" onClick={close}>
          {t("取消区组编辑")}
        </Button>
        <Button
          type="button"
          variant="primary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              save(await validate());
            } catch (e) {
              setError(e);
            } finally {
              setBusy(false);
            }
          }}
        >
          {t("校验并保存区组")}
        </Button>
      </div>
    </Modal>
  );
}
