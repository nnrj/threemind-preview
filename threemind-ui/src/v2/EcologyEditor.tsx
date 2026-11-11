import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { t, messageKeys } from "./i18n";
import { post } from "./api";
import { Button, CodeEditor, ErrorBox, Field } from "./ui";
import {
  ConfigurationEditor,
  type ConfigurationHandle,
  type Catalogue,
} from "./configuration";

export const ecologyLabels = messageKeys({
  root_id: "作为个体复制的根躯体",
  founder_count: "初始个体数",
  ecology_seed: "生态调度种子",
  body_failure_inputs: "躯体失效后的输入",
  close_all: "关闭全部外部输入",
  detach_body: "只断开躯体输入",
  habitat: "栖息策略",
  rules: "资源、生存与繁殖规则",
  shared: "共享物理世界",
  independent: "独立栖息环境",
  allocation: "资源分配规则",
  equal: "等额分配（受各自需求上限约束）",
  demand: "按需求比例分配",
  nearest: "按实际距离优先分配",
  patches: "资源区域",
  hazards: "损伤区域",
  id: "区域编号",
  label: "名称",
  position: "世界位置（m）",
  radius: "作用半径（m）",
  capacity: "区域资源容量",
  initial: "初始资源",
  regeneration_per_s: "每模拟秒再生量",
  minimum_gatherers: "协作采集所需个体数",
  damage_per_s: "每模拟秒损伤",
  reserve_capacity: "身体储备容量",
  founder_reserve: "初始身体储备",
  uptake_per_s: "每模拟秒最大摄取量",
  maintenance_per_s: "每模拟秒维持消耗",
  effort_per_s: "每单位控制量的每秒消耗",
  contact_force_threshold: "接触力损伤阈值（N）",
  damage_per_force_s: "每 N·s 接触损伤",
  fatal_damage: "躯体失效损伤阈值",
  reproduction: "繁殖规则",
  enabled: "启用",
  parent_state: "父本状态要求",
  body_and_viable_core: "躯体有效且内核未死亡",
  body_only: "仅要求躯体有效",
  interval_us: "繁殖检查间隔（μs）",
  minimum_age_us: "最早繁殖年龄（μs）",
  cooldown_us: "繁殖冷却间隔（μs）",
  threshold: "繁殖储备门槛",
  offspring_reserve: "转给后代的初始储备",
  expenditure: "每次繁殖的额外消耗",
  parent_minimum_reserve: "父本最低保留储备",
  population_limit: "同时存活躯体上限",
  offspring_limit: "累计后代预算",
  senses: "躯体状态感官",
  reserve_enabled: "感知身体储备",
  damage_enabled: "感知身体损伤",
  resource_enabled: "感知附近资源",
  reserve_port: "储备感官端口",
  damage_port: "损伤感官端口",
  resource_port: "资源感官端口",
  reserve_scale: "储备归一化尺度",
  damage_scale: "损伤归一化尺度",
  resource_radius_multiplier: "资源感知半径倍数",
  gain: "编码增益",
  intensity: "刺激强度",
  layout: "出生位置",
  origin: "出生区域中心（m）",
  spacing: "出生位置间距（m）",
});
const basic = ["root_id", "founder_count", "ecology_seed"];

function RuleFields({
  value,
  schema,
  definitions,
  path = "",
  change,
  readOnly,
  templates,
}: any) {
  if (schema.$ref) schema = definitions[schema.$ref.split("/").pop()];
  return (
    <div className="ecology-fields">
      {Object.entries(schema.properties ?? {})
        .filter(([key]) => !["schema_id", "inheritance_rule"].includes(key))
        .map(([key, original]) => {
          let rule: any = original;
          if (rule.$ref) rule = definitions[rule.$ref.split("/").pop()];
          const at = path ? path + "." + key : key,
            item = value[key];
          const label = t(
            ecologyLabels[key as keyof typeof ecologyLabels] ?? key,
          );
          const nullable = rule.anyOf?.some((r: any) => r.type === "null");
          const effective =
            rule.anyOf?.find((r: any) => r.type !== "null") ?? rule;
          if (rule.properties)
            return (
              <details key={key} className="ecology-group">
                <summary>{label}</summary>
                <RuleFields
                  value={item}
                  schema={rule}
                  definitions={definitions}
                  path={at}
                  change={change}
                  readOnly={readOnly}
                  templates={templates}
                />
              </details>
            );
          if (rule.type === "array" && rule.items?.$ref)
            return (
              <section key={key} className="ecology-group">
                <h4>{label}</h4>
                {item.map((entry: any, index: number) => (
                  <details key={index} open={item.length === 1}>
                    <summary>{entry.label || entry.id}</summary>
                    <RuleFields
                      value={entry}
                      schema={rule.items}
                      definitions={definitions}
                      path={at + "." + index}
                      change={change}
                      readOnly={readOnly}
                      templates={templates}
                    />
                    {!readOnly && (
                      <Button
                        type="button"
                        variant="quiet"
                        onClick={() =>
                          change(
                            at,
                            item.filter((_: any, i: number) => i !== index),
                          )
                        }
                      >
                        {t("删除区域")}
                      </Button>
                    )}
                  </details>
                ))}
                {!readOnly && (
                  <Button
                    type="button"
                    onClick={() => {
                      let n = 1;
                      while (item.some((i: any) => i.id === key + n)) n++;
                      change(at, [
                        ...item,
                        { ...structuredClone(templates[key]), id: key + n },
                      ]);
                    }}
                  >
                    {t("添加区域")}
                  </Button>
                )}
              </section>
            );
          return (
            <Field
              key={key}
              label={label}
              hint={
                nullable
                  ? t("留空时使用协议中的身体容量或损伤阈值。")
                  : undefined
              }
            >
              {effective.enum ? (
                <select
                  aria-label={label}
                  disabled={readOnly}
                  value={item}
                  onChange={(e) => change(at, e.target.value)}
                >
                  {effective.enum.map((v: string) => (
                    <option value={v} key={v}>
                      {t(ecologyLabels[v as keyof typeof ecologyLabels] ?? v)}
                    </option>
                  ))}
                </select>
              ) : effective.type === "boolean" ? (
                <input
                  type="checkbox"
                  aria-label={label}
                  disabled={readOnly}
                  checked={item}
                  onChange={(e) => change(at, e.target.checked)}
                />
              ) : effective.type === "array" ? (
                <div className="ecology-vector">
                  {item.map((n: number, i: number) => (
                    <input
                      key={i}
                      type="number"
                      step="any"
                      aria-label={label + " " + ["X", "Y", "Z"][i]}
                      value={n}
                      readOnly={readOnly}
                      onChange={(e) =>
                        change(
                          at,
                          item.map((v: number, j: number) =>
                            j === i
                              ? e.target.value === ""
                                ? ""
                                : Number(e.target.value)
                              : v,
                          ),
                        )
                      }
                    />
                  ))}
                </div>
              ) : (
                <input
                  aria-label={label}
                  type={
                    ["number", "integer"].includes(effective.type)
                      ? "number"
                      : "text"
                  }
                  step={effective.type === "integer" ? 1 : "any"}
                  min={effective.minimum}
                  max={effective.maximum}
                  value={item ?? ""}
                  readOnly={readOnly}
                  onChange={(e) =>
                    change(
                      at,
                      ["number", "integer"].includes(effective.type)
                        ? e.target.value === ""
                          ? nullable
                            ? null
                            : ""
                          : Number(e.target.value)
                        : e.target.value,
                    )
                  }
                />
              )}
            </Field>
          );
        })}
    </div>
  );
}

export type EcologyEditorHandle = { validate: () => Promise<any | null> };
export const EcologyEditor = forwardRef<
  EcologyEditorHandle,
  {
    project: string;
    initial: any;
    catalogue: any;
    configuration: Catalogue;
    readOnly?: boolean;
    onDirty?: () => void;
  }
>(function EcologyEditor(
  { project, initial, catalogue, configuration, readOnly = false, onDirty },
  ref,
) {
  const [value, setValue] = useState(initial),
    [mode, setMode] = useState<"form" | "json">("form"),
    [raw, setRaw] = useState("");
  const [error, setError] = useState<unknown>(null),
    [checked, setChecked] = useState(false),
    [busy, setBusy] = useState(false);
  const base = useRef<ConfigurationHandle>(null);
  const dirty = () => {
    setChecked(false);
    setError(null);
    onDirty?.();
  };
  async function current() {
    if (mode === "json") {
      const { parseJson } = await import("./JsonEditor");
      return parseJson(raw);
    }
    const spec = await base.current?.validate();
    return spec ? { ...value, base: spec } : null;
  }
  async function validate() {
    if (busy) return null;
    setBusy(true);
    setError(null);
    try {
      const next = await current();
      if (!next) return null;
      const result = await post<any>(
        "/projects/" + project + "/ecologies/validate",
        next,
      );
      setChecked(true);
      return result.protocol;
    } catch (e) {
      setError(e);
      return null;
    } finally {
      setBusy(false);
    }
  }
  useImperativeHandle(ref, () => ({ validate }));
  async function toggle() {
    if (mode === "form") {
      const next = await current();
      if (next) {
        setValue(next);
        setRaw(JSON.stringify(next, null, 2));
        setMode("json");
      }
    } else {
      const next = await validate();
      if (next) {
        setValue(next);
        setMode("form");
      }
    }
  }
  function change(path: string, next: any) {
    const v = structuredClone(value),
      parts = path.split(".");
    let target = v.ecology;
    for (const key of parts.slice(0, -1)) target = target[key];
    target[parts[parts.length - 1]] = next;
    setValue(v);
    dirty();
  }
  const schema = catalogue.ecology_schema;
  const root = {
    properties: Object.fromEntries(basic.map((k) => [k, schema.properties[k]])),
  };
  const advanced = {
    properties: Object.fromEntries(
      Object.entries(schema.properties).filter(([k]) => !basic.includes(k)),
    ),
  };
  return (
    <div className="ecology-editor">
      <div className="configuration-toolbar">
        <span>{t("生态训练协议")}</span>
        <Button type="button" variant="quiet" disabled={busy} onClick={toggle}>
          {mode === "form" ? t("切换到 JSON") : t("切换到图形配置")}
        </Button>
      </div>
      {mode === "json" ? (
        <>
          <CodeEditor
            value={raw}
            onChange={(v) => {
              setRaw(v);
              dirty();
            }}
            readOnly={readOnly}
            label={t("生态协议 JSON")}
            rows={24}
          />
          <Button
            type="button"
            disabled={busy}
            onClick={async () => {
              try {
                const { parseJson } = await import("./JsonEditor");
                setRaw(JSON.stringify(parseJson(raw), null, 2));
              } catch (e) {
                setError(e);
              }
            }}
          >
            {t("格式化")}
          </Button>
        </>
      ) : (
        <>
          <RuleFields
            value={value.ecology}
            schema={root}
            definitions={schema.$defs}
            change={change}
            readOnly={readOnly}
            templates={catalogue.templates}
          />
          <Field
            label={t("允许人工、媒体及远程输入")}
            hint={t("开启后仍受来源策略与总线约束；接收的刺激保留来源证据。")}
          >
            <input
              type="checkbox"
              checked={value.external_inputs}
              disabled={readOnly}
              onChange={(e) => {
                setValue({ ...value, external_inputs: e.target.checked });
                dirty();
              }}
            />
          </Field>
          <details className="ecology-group">
            <summary>{t("生态高级参数：资源、损伤、繁殖与感官")}</summary>
            <RuleFields
              value={value.ecology}
              schema={advanced}
              definitions={schema.$defs}
              change={change}
              readOnly={readOnly}
              templates={catalogue.templates}
            />
          </details>
          <p className="footnote">
            {t(
              "资源是独立的身体账本单位；损伤和资源感知不会直接改写 Core 能量或连接。遗传采用父本已形成的网络，出生时清空活动状态。",
            )}
          </p>
          <ConfigurationEditor
            allowJsonMode={false}
            ref={base}
            initial={value.base}
            catalogue={configuration}
            project={project}
            readOnly={readOnly}
            lockedPaths={[
              "environment",
              ...(value.initial_version_id
                ? catalogue.inheritance_locked_paths
                : []),
            ]}
            lockedMessage={t("生态训练统一使用所选物理世界。")}
            onDirty={dirty}
          />
        </>
      )}
      <div className="query-controls">
        <Button type="button" disabled={busy} onClick={validate}>
          {t("校验协议")}
        </Button>
        {checked && <span role="status">{t("协议校验通过")}</span>}
      </div>
      <ErrorBox error={error} />
    </div>
  );
});
