import { can } from "./access";
import { t } from "./i18n";
import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  lazy,
  Suspense,
} from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Check,
  Code2,
  LockKeyhole,
  Plus,
  Trash2,
  Pause,
  RotateCcw,
} from "lucide-react";
import { api, post, projectPath, ApiError, type Run } from "./api";
import { KernelSelector } from "./kernelSelector";
import {
  Button,
  Field,
  ErrorBox,
  Loading,
  Modal,
  CodeEditor,
  useWorkspace,
} from "./ui";
const WorldPicker = lazy(() => import("./WorldPicker"));
const RobotEditor = lazy(() => import("./RobotEditor"));

type Spec = Record<string, any>;
type Issue = { path: string; message: string };
type Parameter = {
  path: string;
  label: string;
  hint: string;
  group: string;
  unit: string;
  type: string;
  default: any;
  immutable: boolean;
  kernels?: string[];
  nullable?: boolean;
  null_label?: string | null;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  choices?: [string, string][];
};
export type Catalogue = {
  text_intensity_presets?: Record<string, number>;
  research_presets?: {
    id: string;
    label: string;
    hint: string;
    kernel_id: string;
    config: Spec;
  }[];
  dynamics: string;
  defaults: Spec;
  fields: Parameter[];
  groups: { id: string; label: string }[];
  immutable: string[];
  max_run_seconds: number;
  world_default: any;
  kernel_defaults?: Record<string, Spec>;
  kernel_immutable?: Record<string, string[]>;
  kernels?: any[];
};
export type ConfigurationHandle = {
  validate: () => Promise<Spec | null>;
  reset: (spec: Spec) => void;
  snapshot: () => Promise<Spec>;
};
export const useCatalogue = () =>
  useQuery({
    queryKey: ["configuration"],
    queryFn: () => api<Catalogue>("/configuration"),
    staleTime: Infinity,
  });

function mergeDefaults(defaults: Spec, value: Spec): Spec {
  const result = { ...structuredClone(defaults), ...structuredClone(value) };
  for (const key of Object.keys(defaults)) {
    if (
      defaults[key] &&
      typeof defaults[key] === "object" &&
      !Array.isArray(defaults[key]) &&
      value[key] &&
      typeof value[key] === "object" &&
      !Array.isArray(value[key])
    )
      result[key] = mergeDefaults(defaults[key], value[key]);
  }
  return result;
}
function normalize(spec: Spec, catalogue: Catalogue): Spec {
  const kernel = spec.kernel_id ?? catalogue.defaults.kernel_id;
  const defaults = {
    ...catalogue.defaults,
    config: catalogue.kernel_defaults?.[kernel] ?? catalogue.defaults.config,
  };
  const result = mergeDefaults(defaults, spec);
  if (spec.environment === "host" && !spec.host_telemetry)
    result.host_telemetry.enabled = true;
  return result;
}
const setPath = (spec: Spec, path: string, value: any): Spec => {
  const [root, ...rest] = path.split(".");
  return {
    ...spec,
    [root]: rest.length
      ? setPath(spec[root] ?? {}, rest.join("."), value)
      : value,
  };
};
const getPath = (spec: Spec, path: string): any =>
  path.split(".").reduce<any>((value, key) => value?.[key], spec);

export const ConfigurationEditor = forwardRef<
  ConfigurationHandle,
  {
    initial: Spec;
    catalogue: Catalogue;
    project?: string;
    runId?: string;
    readOnly?: boolean;
    frozen?: boolean;
    onDirty?: () => void;
    initialGroup?: string;
    lockedPaths?: string[];
    lockedMessage?: string;
    sharedPhaseStructure?: boolean;
    allowJsonMode?: boolean;
    managedKernel?: boolean;
  }
>(function ConfigurationEditor(
  {
    initial,
    catalogue,
    project,
    runId,
    readOnly = false,
    frozen = false,
    onDirty,
    initialGroup,
    lockedPaths = [],
    lockedMessage,
    sharedPhaseStructure = false,
    allowJsonMode = true,
    managedKernel = false,
  },
  ref,
) {
  const [spec, setSpec] = useState(() => normalize(initial, catalogue));
  const availableFields = catalogue.fields.filter(
    (field) =>
      field.path !== "kernel_id" &&
      (!field.kernels || field.kernels.includes(spec.kernel_id)) &&
      !(
        [
          "threemind.continuous-memory/3",
          "threemind.continuous-memory/3.1",
          "threemind.continuous-memory/4",
          "threemind.continuous-memory/5",
          "threemind.continuous-memory/5.1",
          "threemind.continuous-memory/5.2",
          "threemind.continuous-memory/5.3",
        "threemind.continuous-memory/6.0", "threemind.continuous-memory/6.1", "threemind.continuous-memory/6.2", "threemind.continuous-memory/6.3",
        ].includes(spec.kernel_id) &&
        ["config.propagation_limit", "config.edge_adaptation_limit"].includes(
          field.path,
        )
      ),
  );
  const [mode, setMode] = useState<"form" | "json">("form"),
    [raw, setRaw] = useState("");
  const [issues, setIssues] = useState<Issue[]>([]),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  const targetGroup = availableFields.some((f) => f.group === initialGroup)
    ? initialGroup!
    : "all";
  const [advanced, setAdvanced] = useState(targetGroup !== "all"),
    [requestedFramePage, setFramePage] = useState(0);
  const [groupFilter, setGroupFilter] = useState(targetGroup),
    [parameterSearch, setParameterSearch] = useState("");
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
    new Set(initialGroup ? [initialGroup] : []),
  );
  const matches = (f: Parameter) =>
    (groupFilter === "all" || f.group === groupFilter) &&
    `${f.label} ${t(f.label)} ${f.path} ${f.hint} ${t(f.hint)}`
      .toLowerCase()
      .includes(parameterSearch.toLowerCase());
  function changed(next: Spec) {
    if (
      [
        "threemind.continuous-memory/3",
        "threemind.continuous-memory/3.1",
        "threemind.continuous-memory/4",
        "threemind.continuous-memory/5",
        "threemind.continuous-memory/5.1",
        "threemind.continuous-memory/5.2",
        "threemind.continuous-memory/5.3",
        "threemind.continuous-memory/6.0", "threemind.continuous-memory/6.1", "threemind.continuous-memory/6.2", "threemind.continuous-memory/6.3",
      ].includes(next.kernel_id) &&
      !next.config.dormant_traces_enabled
    )
      next = setPath(next, "config.revival_enabled", false);
    setSpec(next);
    setNotice("");
    setIssues([]);
    onDirty?.();
  }
  function patch(path: string, value: any) {
    let next = setPath(spec, path, value);
    if (path === "kernel_id" && value !== spec.kernel_id) {
      const defaults = catalogue.kernel_defaults?.[value];
      if (defaults) next.config = structuredClone(defaults);
      if (value === "threemind.lif/1")
        next = setPath(next, "energy_supply.enabled", false);
    }
    if (path === "environment" && value === "host") {
      next = setPath(next, "host_telemetry.enabled", true);
      next.clock = "realtime";
    }
    if (path === "environment" && value === "world" && !next.world_protocol)
      next.world_protocol = structuredClone(catalogue.world_default);
    changed(next);
  }
  async function parsed() {
    if (mode === "form") return spec;
    const { parseJson } = await import("./JsonEditor");
    return parseJson(raw);
  }
  async function validate(): Promise<Spec | null> {
    setBusy(true);
    setIssues([]);
    setNotice("");
    try {
      const value = await parsed();
      if (managedKernel && value.kernel_id !== initial.kernel_id) {
        setIssues([
          {
            path: "kernel_id",
            message: t("请在上方选择内核版本，JSON 不能更换内核。"),
          },
        ]);
        return null;
      }
      if (lockedPaths.length) {
        const proposed = normalize(value, catalogue),
          original = normalize(initial, catalogue);
        const changed = lockedPaths.filter(
          (path) =>
            JSON.stringify(getPath(proposed, path)) !==
            JSON.stringify(getPath(original, path)),
        );
        if (changed.length) {
          setIssues(
            changed.map((path) => ({
              path,
              message: lockedMessage ?? t("条件间共享，请在基础协议中配置"),
            })),
          );
          return null;
        }
      }
      const result = await post<{
        valid: boolean;
        errors: Issue[];
        spec?: Spec;
        adjustments?: Issue[];
      }>(
        runId && project
          ? `${projectPath(project)}/configuration/validate`
          : "/configuration/validate",
        {
          spec: value,
          run_id: runId,
        },
      );
      if (!result.valid) {
        setIssues(result.errors);
        if (mode === "form") {
          setAdvanced(true);
          setGroupFilter("all");
          setParameterSearch("");
        }
        return null;
      }
      setNotice(
        [
          t("校验通过：类型、范围、关联条件与不可变参数均已检查。"),
          ...(result.adjustments ?? []).map((item) => t(item.message)),
        ].join(" "),
      );
      return result.spec!;
    } catch (error) {
      setIssues([{ path: "JSON", message: (error as Error).message }]);
      return null;
    } finally {
      setBusy(false);
    }
  }
  useImperativeHandle(ref, () => ({
    validate,
    snapshot: parsed,
    reset(value) {
      setSpec(normalize(value, catalogue));
      setRaw(JSON.stringify(normalize(value, catalogue), null, 2));
      setIssues([]);
      setNotice("");
    },
  }));
  async function toggle() {
    if (mode === "form") {
      setRaw(JSON.stringify(spec, null, 2));
      setMode("json");
      setIssues([]);
      setNotice("");
    } else {
      // Read-only views still allow both representations, including finished runs.
      const value = readOnly ? spec : await validate();
      if (value) {
        setSpec(value);
        setMode("form");
      }
    }
  }
  async function format() {
    try {
      const value = await parsed();
      setRaw(JSON.stringify(value, null, 2));
      setIssues([]);
    } catch (error) {
      setIssues([{ path: "JSON", message: (error as Error).message }]);
    }
  }
  const locked = (path: string) =>
    readOnly ||
    frozen ||
    (!!runId && catalogue.immutable.includes(path)) ||
    (!!runId &&
      !!catalogue.kernel_immutable?.[spec.kernel_id]?.includes(path)) ||
    lockedPaths.some((key) => path === key || path.startsWith(key + "."));
  function field(item: Parameter) {
    const retention = [
      "threemind.continuous-memory/3",
      "threemind.continuous-memory/3.1",
      "threemind.continuous-memory/4",
      "threemind.continuous-memory/5",
      "threemind.continuous-memory/5.1",
      "threemind.continuous-memory/5.2",
      "threemind.continuous-memory/5.3",
        "threemind.continuous-memory/6.0", "threemind.continuous-memory/6.1", "threemind.continuous-memory/6.2", "threemind.continuous-memory/6.3",
    ].includes(spec.kernel_id);
    const inactive =
      retention &&
      ((["config.node_wake_threshold", "config.edge_wake_threshold"].includes(
        item.path,
      ) &&
        !spec.config.dormant_traces_enabled) ||
        (item.path === "config.revival_enabled" &&
          !spec.config.dormant_traces_enabled) ||
        ([
          "config.prune_support",
          "config.node_prune_after_us",
          "config.dead_node_retention_us",
        ].includes(item.path) &&
          (spec.config.node_retention_mode !== "manual" ||
            spec.config.retain_nodes)) ||
        (item.path === "config.dead_node_retention_us" &&
          spec.config.prune_support !== 0) ||
        (item.path === "config.node_prune_after_us" &&
          spec.config.prune_support === 0));
    const { path, label, hint, choices } = item,
      value = getPath(spec, path),
      lock = locked(path) || inactive;
    const kernelDefaults = catalogue.kernel_defaults?.[spec.kernel_id];
    const defaultValue =
      path.startsWith("config.") &&
      kernelDefaults &&
      Object.prototype.hasOwnProperty.call(kernelDefaults, path.slice(7))
        ? kernelDefaults[path.slice(7)]
        : item.default;
    if (path === "speed" && spec.clock !== "scaled") return null;
    if (path === "robot_protocol") {
      if (spec.environment !== "robot") return null;
      if (!project)
        return (
          <p key={path} className="footnote">
            {t(
              "选择所属项目后可从机器人库选择；自定义协议也可在 JSON 中配置。",
            )}
          </p>
        );
      return (
        <div
          key={path}
          className="parameter-field world-parameter"
          data-parameter={path}
        >
          <Suspense fallback={<Loading />}>
            <RobotEditor
              project={project}
              value={value}
              readOnly={lock}
              onChange={(v) => patch(path, v)}
            />
          </Suspense>
          <small className="immutable-note">{t("创建后不可更改")}</small>
        </div>
      );
    }
    if (path === "world_protocol") {
      if (spec.environment !== "world" && !value) return null;
      if (!project)
        return (
          <p key={path} className="footnote">
            {t("选择所属项目后可从世界库选择；自定义协议也可在 JSON 中配置。")}
          </p>
        );
      return (
        <div
          key={path}
          className="parameter-field world-parameter"
          data-parameter={path}
        >
          <strong>{t(label)}</strong>
          <p className="footnote">{t(hint)}</p>
          <Suspense fallback={<Loading />}>
            <WorldPicker
              project={project}
              value={value}
              readOnly={lock}
              onChange={(v) => patch(path, v)}
            />
          </Suspense>
          <small className="immutable-note">
            <LockKeyhole size={11} />
            {t("创建后不可更改")}
          </small>
        </div>
      );
    }
    const bounds = [
      item.minimum !== undefined ? `≥ ${item.minimum}` : "",
      item.maximum !== undefined ? `≤ ${item.maximum}` : "",
      item.exclusiveMinimum !== undefined ? `> ${item.exclusiveMinimum}` : "",
      item.exclusiveMaximum !== undefined ? `< ${item.exclusiveMaximum}` : "",
    ]
      .filter(Boolean)
      .join("，");
    return (
      <div
        key={path}
        className={`parameter-field ${lock ? "parameter-readonly" : ""}`}
        data-parameter={path}
      >
        <Field label={t(label)} hint={t(hint)}>
          {choices ? (
            <select
              aria-label={t(label)}
              value={value}
              disabled={lock}
              onChange={(e) => patch(path, e.target.value)}
            >
              {choices.map(([v, title]) => (
                <option key={v} value={v}>
                  {path === "kernel_id"
                    ? `${v.replace(/^threemind\./, "")} · ${t(title)}`
                    : t(title)}
                </option>
              ))}
            </select>
          ) : item.type === "boolean" && item.nullable ? (
            <select
              aria-label={t(label)}
              value={value == null ? "inherit" : value ? "true" : "false"}
              disabled={lock}
              onChange={(e) => patch(path, e.target.value === "inherit" ? null : e.target.value === "true")}
            >
              <option value="inherit">{t(item.null_label || "跟随总开关")}</option>
              <option value="true">{t("已开启")}</option>
              <option value="false">{t("已关闭")}</option>
            </select>
          ) : item.type === "boolean" ? (
            <span className="boolean-parameter">
              <input
                aria-label={t(label)}
                type="checkbox"
                checked={!!value}
                disabled={lock}
                onChange={(e) => patch(path, e.target.checked)}
              />
              <span>{value ? t("已开启") : t("已关闭")}</span>
            </span>
          ) : item.type === "string" ? (
            <input
              aria-label={t(label)}
              type="text"
              value={value ?? ""}
              readOnly={lock}
              onChange={(event) => patch(path, event.target.value)}
            />
          ) : (
            <input
              aria-label={t(label)}
              type="number"
              step={item.type === "integer" ? "1" : "any"}
              value={value ?? ""}
              readOnly={lock}
              min={item.minimum ?? item.exclusiveMinimum}
              max={
                path === "duration_s"
                  ? Math.min(
                      item.maximum ?? Infinity,
                      catalogue.max_run_seconds,
                    )
                  : (item.maximum ?? item.exclusiveMaximum)
              }
              placeholder={
                item.nullable ? t(item.null_label || "不限制") : undefined
              }
              onChange={(e) =>
                patch(
                  path,
                  e.target.value === "" ? null : Number(e.target.value),
                )
              }
            />
          )}
        </Field>
        <div className="parameter-meta">
          <code>{path}</code>
          {item.unit && <span>{t(item.unit)}</span>}
          <span title={bounds}>
            {t("默认 ")}
            {defaultValue === null
              ? t(item.null_label || "不限制")
              : String(defaultValue)}
          </span>
        </div>
        {bounds && (
          <small className="parameter-range">
            {t("有效范围：")}
            {bounds}
          </small>
        )}
        {inactive && (
          <small className="immutable-note">{t("当前模式下不生效")}</small>
        )}
        {(item.immutable ||
          frozen ||
          lockedPaths.some(
            (key) => path === key || path.startsWith(key + "."),
          )) && (
          <small className="immutable-note">
            <LockKeyhole size={11} />
            {frozen
              ? t("实验协议已冻结")
              : lockedPaths.some(
                    (key) => path === key || path.startsWith(key + "."),
                  )
                ? (lockedMessage ?? t("条件间共享，请在基础协议中配置"))
                : t("创建后不可更改")}
          </small>
        )}
      </div>
    );
  }
  function listControls(path: string, title: string, next: any, max: number) {
    return (
      <div className="parameter-section-heading">
        <h4>{t(title)}</h4>
        <Button
          type="button"
          variant="small"
          disabled={
            locked(path) ||
            (path === "phases" && sharedPhaseStructure) ||
            (spec[path]?.length ?? 0) >= max
          }
          onClick={() => patch(path, [...(spec[path] ?? []), next])}
        >
          <Plus size={14} />
          {t("添加")}
        </Button>
      </div>
    );
  }
  const phases: any[] = spec.phases ?? [],
    replay: any[] = spec.replay ?? [];
  const framePage = Math.min(
    requestedFramePage,
    Math.max(0, Math.ceil(replay.length / 5) - 1),
  );
  return (
    <section className="configuration-editor" aria-label={t("参数配置")}>
      {!managedKernel && (
        <KernelSelector
          catalogue={catalogue}
          value={spec.kernel_id}
          disabled={locked("kernel_id") || busy || mode === "json"}
          onChange={(value) => patch("kernel_id", value)}
        />
      )}
      {!runId &&
        !managedKernel &&
        catalogue.research_presets?.some(
          (preset) => preset.kernel_id === spec.kernel_id,
        ) && (
          <Field label={t("内置配置模板")}>
            <select
              aria-label={t("内置配置模板")}
              value="current"
              disabled={locked("config.stp_facilitation_tau_s") || busy}
              onChange={(event) => {
                const preset = catalogue.research_presets?.find(
                  (row) =>
                    row.id === event.target.value &&
                    row.kernel_id === spec.kernel_id,
                );
                if (preset)
                  patch("config", {
                    ...(["threemind.continuous-memory/6.2", "threemind.continuous-memory/6.3"].includes(spec.kernel_id)
                      ? spec.config
                      : catalogue.kernel_defaults?.[spec.kernel_id]),
                    ...preset.config,
                  });
              }}
            >
              <option value="current">{t("当前参数")}</option>
              {catalogue.research_presets
                .filter((preset) => preset.kernel_id === spec.kernel_id)
                .map((preset) => (
                  <option
                    key={preset.id}
                    value={preset.id}
                    title={t(preset.hint)}
                  >
                    {t(preset.label)}
                  </option>
                ))}
            </select>
          </Field>
        )}
      <header className="configuration-heading">
        <div>
          <h3>{t("参数配置")}</h3>
          <p>
            {runId
              ? t("保存时再次校验，修改与恢复状态一起记录。")
              : t("基础参数可直接使用默认值；高级参数按机制分类。")}
          </p>
        </div>
        {allowJsonMode && (
          <button
            type="button"
            className="text-link configuration-toggle"
            onClick={toggle}
            disabled={busy}
          >
            <Code2 size={14} />
            {mode === "form" ? t("切换到 JSON") : t("切换到图形配置")}
          </button>
        )}
      </header>
      {mode === "json" ? (
        <>
          <div className="json-actions">
            <span>{t("完整运行协议 · JSON")}</span>
            <button
              type="button"
              className="text-link"
              onClick={format}
              disabled={readOnly}
            >
              {t("格式化")}
            </button>
            <button
              type="button"
              className="text-link"
              onClick={validate}
              disabled={busy}
            >
              {t("校验")}
            </button>
          </div>
          <CodeEditor
            value={raw}
            onChange={(value) => {
              setRaw(value);
              setIssues([]);
              setNotice("");
              onDirty?.();
            }}
            rows={18}
            readOnly={readOnly || busy}
            label={t("JSON 参数")}
          />
          <p className="footnote">
            {t(
              "支持行号、高亮、折叠和 Ctrl+F 查找。不可变字段可在这里输入，但修改会被校验和保存拒绝。",
            )}
          </p>
        </>
      ) : (
        <>
          <fieldset className="configuration-fields" disabled={busy}>
            <div className="form-grid">
              {availableFields
                .filter((f) => f.path === "text_sensor.encoding")
                .map((f) => field({ ...f, label: "节点标记／感官模式" }))}
              {availableFields
                .filter(
                  (f) => f.group === "basic" && !f.path.startsWith("config."),
                )
                .map(field)}
              {availableFields
                .filter(
                  (f) => f.group === "basic" && f.path.startsWith("config."),
                )
                .map(field)}
            </div>
            <details
              className="advanced configuration-advanced"
              open={advanced}
              onToggle={(e) => setAdvanced(e.currentTarget.open)}
            >
              <summary>
                {t("高级参数 ")}
                <span>{t("时间、学习、抑制、感官与研究记录")}</span>
              </summary>
              <div className="parameter-filter">
                <input
                  aria-label={t("搜索高级参数")}
                  placeholder={t("搜索参数名称、说明或键…")}
                  value={parameterSearch}
                  onChange={(e) => setParameterSearch(e.target.value)}
                />
                <select
                  aria-label={t("高级参数分类")}
                  value={groupFilter}
                  onChange={(e) => setGroupFilter(e.target.value)}
                >
                  <option value="all">{t("全部分类")}</option>
                  {catalogue.groups
                    .filter(
                      (g) =>
                        g.id !== "basic" &&
                        availableFields.some((f) => f.group === g.id),
                    )
                    .map((g) => (
                      <option key={g.id} value={g.id}>
                        {t(g.label)}
                      </option>
                    ))}
                  <option value="protocol">{t("阶段、输入与干预")}</option>
                </select>
              </div>
              {catalogue.groups
                .filter(
                  (g) =>
                    g.id !== "basic" &&
                    availableFields.some((f) => f.group === g.id && matches(f)),
                )
                .map((group) =>
                  /_(telemetry|readout)$/.test(group.id) ? (
                    <details
                      className="parameter-group telemetry-parameter-group"
                      key={group.id}
                      open={
                        groupFilter === group.id ||
                        !!parameterSearch ||
                        expandedGroups.has(group.id)
                      }
                      onToggle={(e) => {
                        const open = e.currentTarget.open;
                        if (groupFilter === group.id || parameterSearch) return;
                        setExpandedGroups((old) => {
                          if (old.has(group.id) === open) return old;
                          const next = new Set(old);
                          if (open) next.add(group.id);
                          else next.delete(group.id);
                          return next;
                        });
                      }}
                    >
                      <summary>
                        {t(group.label)}{" "}
                        <span>
                          {spec[group.id]?.enabled ? t("已启用") : t("未启用")}
                          {t(" · 指标与编码配置")}
                        </span>
                      </summary>
                      <div className="form-grid">
                        {availableFields
                          .filter((f) => f.group === group.id && matches(f))
                          .map(field)}
                      </div>
                    </details>
                  ) : (
                    <section className="parameter-group" key={group.id}>
                      <h4>{t(group.label)}</h4>
                      {group.id === "optional" && (
                        <p className="muted">
                          {t(
                            "可选对照默认关闭。旧模型首次修改这些机制参数时，将记录动力学版本升级；旧检查点保留。",
                          )}{" "}
                          <Link to="/docs?doc=docs%2Fzh%2Fv2-optional-core.md">
                            {t("查看机制、公式与版本规则")}
                          </Link>
                        </p>
                      )}
                      {group.id === "resources" && (
                        <p className="muted">
                          {t(
                            "留空表示不限制；0 表示禁止相应操作。容量降低不会删除已有结构。这些参数改变模型演化，独立于显示性能档位。",
                          )}{" "}
                          <Link to="/docs?doc=docs%2Fzh%2Fv2-resource-limits.md">
                            {t("查看预算、计数与版本规则")}
                          </Link>
                        </p>
                      )}
                      {["energy", "energy_supply"].includes(group.id) && (
                        <p className="muted">
                          {t(
                            "能量为可选实验资源，单位未经物理标定。供给来自显式外部端口；模型不会自动补充储备。初始储备只在出生时设置。",
                          )}{" "}
                          <Link to="/docs?doc=docs%2Fzh%2Fv2-energy.md">
                            {t("查看能量、供给与饥饿规则")}
                          </Link>
                        </p>
                      )}
                      <div className="form-grid">
                        {availableFields
                          .filter((f) => f.group === group.id && matches(f))
                          .map(field)}
                      </div>
                    </section>
                  ),
                )}
              <section
                className="parameter-group"
                hidden={
                  !["all", "protocol"].includes(groupFilter) ||
                  !!parameterSearch
                }
              >
                {listControls(
                  "phases",
                  "实验阶段",
                  {
                    name: `阶段 ${phases.length + 1}`,
                    duration_s: 1,
                    input_enabled: true,
                    close_sources: false,
                  },
                  32,
                )}
                <p>
                  {t(
                    "可选。阶段时长之和须等于总运行时长；仅用于模拟环境或重放。",
                  )}
                  {runId
                    ? t("创建后固定。")
                    : t("无阶段时连续接受输入。创建后不可更改。")}
                </p>
                {phases.map((phase, index) => (
                  <div className="configuration-row" key={index}>
                    <div className="form-grid">
                      <Field
                        label={t("阶段 {value0} 名称", {
                          value0: String(index + 1),
                        })}
                      >
                        <input
                          value={phase.name}
                          readOnly={locked("phases") || sharedPhaseStructure}
                          onChange={(e) =>
                            patch(
                              "phases",
                              phases.map((p, i) =>
                                i === index
                                  ? { ...p, name: e.target.value }
                                  : p,
                              ),
                            )
                          }
                        />
                      </Field>
                      <Field
                        label={t("阶段 {value0} 时长（秒）", {
                          value0: String(index + 1),
                        })}
                      >
                        <input
                          type="number"
                          step="any"
                          min="0.000001"
                          value={phase.duration_s ?? ""}
                          readOnly={locked("phases") || sharedPhaseStructure}
                          onChange={(e) =>
                            patch(
                              "phases",
                              phases.map((p, i) =>
                                i === index
                                  ? {
                                      ...p,
                                      duration_s:
                                        e.target.value === ""
                                          ? null
                                          : Number(e.target.value),
                                    }
                                  : p,
                              ),
                            )
                          }
                        />
                      </Field>
                      {[
                        ["input_enabled", "递送环境刺激"],
                        ["close_sources", "永久关闭输入源"],
                      ].map(([key, text]) => (
                        <label className="check" key={key}>
                          <input
                            type="checkbox"
                            checked={phase[key]}
                            disabled={locked("phases")}
                            onChange={(e) =>
                              patch(
                                "phases",
                                phases.map((p, i) =>
                                  i === index
                                    ? { ...p, [key]: e.target.checked }
                                    : p,
                                ),
                              )
                            }
                          />
                          {t(text)}
                        </label>
                      ))}
                    </div>
                    <button
                      type="button"
                      className="text-link"
                      disabled={locked("phases") || sharedPhaseStructure}
                      onClick={() =>
                        patch(
                          "phases",
                          phases.filter((_, i) => i !== index),
                        )
                      }
                    >
                      <Trash2 size={13} />
                      {t("删除阶段")}
                    </button>
                  </div>
                ))}
              </section>
              <section
                className="parameter-group"
                hidden={
                  !["all", "protocol"].includes(groupFilter) ||
                  !!parameterSearch
                }
              >
                {listControls(
                  "replay",
                  "输入帧序列",
                  { time_us: "0", intensity: 1, channels: [[1, 0.5]] },
                  100000,
                )}
                <p>
                  {t(
                    "时间相对于运行起点；仅在“记录输入重放”环境中递送。创建后不可更改。导入长序列可使用 JSON，图形界面每页显示 5 帧。",
                  )}
                </p>
                {replay
                  .slice(framePage * 5, framePage * 5 + 5)
                  .map((frame, local) => {
                    const index = framePage * 5 + local;
                    const update = (key: string, value: any) =>
                      patch(
                        "replay",
                        replay.map((f, i) =>
                          i === index ? { ...f, [key]: value } : f,
                        ),
                      );
                    return (
                      <details className="configuration-row" key={index}>
                        <summary>
                          {t("帧 ")}
                          {index + 1} · {frame.time_us} μs ·{" "}
                          {frame.channels.length}
                          {t(" 通道")}
                        </summary>
                        <div className="form-grid">
                          <Field
                            label={t("帧 {value0} 时间（μs）", {
                              value0: String(index + 1),
                            })}
                          >
                            <input
                              value={frame.time_us}
                              readOnly={locked("replay")}
                              onChange={(e) =>
                                update("time_us", e.target.value)
                              }
                            />
                          </Field>
                          <Field
                            label={t("帧 {value0} 强度", {
                              value0: String(index + 1),
                            })}
                          >
                            <input
                              type="number"
                              min="0"
                              step="any"
                              value={frame.intensity ?? 1}
                              readOnly={locked("replay")}
                              onChange={(e) =>
                                update(
                                  "intensity",
                                  e.target.value === ""
                                    ? null
                                    : Number(e.target.value),
                                )
                              }
                            />
                          </Field>
                        </div>
                        <NumericRows
                          rows={frame.channels}
                          columns={[
                            { label: "通道 ID", maximum: 4294967295 },
                            { label: "幅度", maximum: 1, fractional: true },
                          ]}
                          readOnly={locked("replay")}
                          onChange={(rows) => update("channels", rows)}
                        />
                        <div className="json-actions">
                          <button
                            type="button"
                            className="text-link"
                            disabled={locked("replay")}
                            onClick={() =>
                              update("channels", [...frame.channels, [0, 0.5]])
                            }
                          >
                            {t("添加通道")}
                          </button>
                          <button
                            type="button"
                            className="text-link"
                            disabled={locked("replay")}
                            onClick={() =>
                              patch(
                                "replay",
                                replay.filter((_, i) => i !== index),
                              )
                            }
                          >
                            {t("删除帧")}
                          </button>
                        </div>
                      </details>
                    );
                  })}
                {replay.length > 5 && (
                  <div className="json-actions">
                    <Button
                      type="button"
                      variant="small"
                      disabled={framePage === 0}
                      onClick={() => setFramePage((p) => p - 1)}
                    >
                      {t("上一页")}
                    </Button>
                    <span>
                      {framePage + 1} / {Math.ceil(replay.length / 5)}
                    </span>
                    <Button
                      type="button"
                      variant="small"
                      disabled={(framePage + 1) * 5 >= replay.length}
                      onClick={() => setFramePage((p) => p + 1)}
                    >
                      {t("下一页")}
                    </Button>
                  </div>
                )}
              </section>
              <section
                className="parameter-group"
                hidden={
                  !["all", "protocol"].includes(groupFilter) ||
                  !!parameterSearch
                }
              >
                <h4>{t("初始结构干预")}</h4>
                <p>
                  {t(
                    "可选的研究干预，只作用于已有节点或连接；不会制造拓扑。空白模型一般无需设置。创建后固定，运行中干预使用独立命令。",
                  )}
                </p>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={spec.intervention !== null}
                    disabled={locked("intervention")}
                    onChange={(e) =>
                      patch(
                        "intervention",
                        e.target.checked
                          ? { nodes: [], edges: [], lesion: false }
                          : null,
                      )
                    }
                  />
                  {t("启用初始干预")}
                </label>
                {spec.intervention && (
                  <InterventionFields
                    value={spec.intervention}
                    readOnly={locked("intervention")}
                    onChange={(v) => patch("intervention", v)}
                  />
                )}
              </section>
            </details>
          </fieldset>
          <div className="configuration-foot">
            <Link to="/docs?doc=docs/zh/v2-kernel.md" target="_blank">
              {t("查看内核公式与原理")}
            </Link>
            <button
              type="button"
              className="text-link"
              disabled={busy}
              onClick={validate}
            >
              <Check size={14} />
              {t("校验配置")}
            </button>
          </div>
        </>
      )}
      {!!issues.length && (
        <div className="configuration-errors" role="alert">
          <strong>{t("配置未通过校验，请纠正以下项目：")}</strong>
          <ul>
            {issues.map((issue, i) => (
              <li key={i}>
                {t(
                  catalogue.fields.find((f) => f.path === issue.path)?.label ??
                    "",
                )}{" "}
                <code>{issue.path || t("配置")}</code>：{issue.message}
              </li>
            ))}
          </ul>
        </div>
      )}
      {notice && (
        <p className="configuration-success" role="status">
          <Check size={14} />
          {t(notice)}
        </p>
      )}
    </section>
  );
});

export function InterventionFields({
  value,
  readOnly,
  onChange,
}: {
  value: any;
  readOnly: boolean;
  onChange: (v: any) => void;
}) {
  const action =
    value.action ??
    (value.lesion
      ? value.nodes.length
        ? "delete_nodes"
        : "disconnect_edges"
      : "silence");
  return (
    <>
      <Field label={t("干预操作")}>
        <select
          value={action}
          disabled={readOnly}
          onChange={(e) =>
            onChange({ ...value, action: e.target.value, lesion: false })
          }
        >
          <option value="silence">{t("临时静默")}</option>
          <option value="unsilence">{t("解除静默")}</option>
          <option value="disconnect_edges">{t("断开连接")}</option>
          <option value="delete_nodes">{t("删除节点")}</option>
        </select>
      </Field>
      <p className="footnote">
        {t(
          "断连只选择连接，允许以后自然重连；删点清除身份和历史。已经发出的信号不因断连撤回。",
        )}
      </p>
      <NumericRows
        rows={value.nodes.map((id: number) => [id])}
        columns={[{ label: "干预节点 ID", maximum: 4294967295 }]}
        readOnly={readOnly}
        onChange={(rows) =>
          onChange({ ...value, nodes: rows.map((row) => row[0]) })
        }
      />
      <button
        type="button"
        className="text-link"
        disabled={readOnly}
        onClick={() => onChange({ ...value, nodes: [...value.nodes, 0] })}
      >
        {t("添加节点干预")}
      </button>
      <NumericRows
        rows={value.edges}
        columns={[
          { label: "连接起点", maximum: 4294967295 },
          { label: "连接终点", maximum: 4294967295 },
        ]}
        readOnly={readOnly}
        onChange={(rows) => onChange({ ...value, edges: rows })}
      />
      <button
        type="button"
        className="text-link"
        disabled={readOnly}
        onClick={() => onChange({ ...value, edges: [...value.edges, [1, 2]] })}
      >
        {t("添加连接干预")}
      </button>
    </>
  );
}

export function NumericRows({
  rows,
  columns,
  readOnly,
  onChange,
}: {
  rows: (number | null)[][];
  columns: { label: string; maximum: number; fractional?: boolean }[];
  readOnly: boolean;
  onChange: (rows: (number | null)[][]) => void;
}) {
  const [requestedPage, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(rows.length / 16)),
    page = Math.min(requestedPage, pages - 1);
  return (
    <div className="numeric-rows">
      {rows.slice(page * 16, page * 16 + 16).map((row, local) => {
        const index = page * 16 + local;
        return (
          <div className="channel-row" key={index}>
            {columns.map((column, cell) => (
              <Field key={cell} label={`${t(column.label)} · ${index + 1}`}>
                <input
                  type="number"
                  min={0}
                  max={column.maximum}
                  step={column.fractional ? "any" : 1}
                  value={row[cell] ?? ""}
                  readOnly={readOnly}
                  onChange={(e) =>
                    onChange(
                      rows.map((r, i) =>
                        i === index
                          ? r.map((n, j) =>
                              j === cell
                                ? e.target.value === ""
                                  ? null
                                  : Number(e.target.value)
                                : n,
                            )
                          : r,
                      ),
                    )
                  }
                />
              </Field>
            ))}
            <button
              type="button"
              className="icon-button"
              aria-label={t("删除{value0}第 {value1} 项", {
                value0: t(columns[0].label),
                value1: String(index + 1),
              })}
              disabled={readOnly}
              onClick={() => onChange(rows.filter((_, i) => i !== index))}
            >
              <Trash2 size={14} />
            </button>
          </div>
        );
      })}
      {pages > 1 && (
        <div className="json-actions">
          <button
            type="button"
            className="text-link"
            disabled={page === 0}
            onClick={() => setPage(page - 1)}
          >
            {t("上一组")}
          </button>
          <span>
            {t("第 {page} / {pages} 组 · 共 {count} 项", {
              page: page + 1,
              pages,
              count: rows.length,
            })}
          </span>
          <button
            type="button"
            className="text-link"
            disabled={page + 1 >= pages}
            onClick={() => setPage(page + 1)}
          >
            {t("下一组")}
          </button>
        </div>
      )}
    </div>
  );
}

export function EditRunConfiguration({
  run,
  onClose,
  initialGroup,
}: {
  run: Run;
  onClose: () => void;
  initialGroup?: string;
}) {
  const { project, user } = useWorkspace(),
    catalogue = useCatalogue(),
    client = useQueryClient();
  const [baseline, setBaseline] = useState(run),
    [name, setName] = useState(run.name),
    [dirty, setDirty] = useState(false);
  const editor = useRef<ConfigurationHandle>(null);
  const canEdit =
    can(user, "runs.configure") &&
    project?.role !== "viewer" &&
    ["paused", "blocked"].includes(baseline.status) &&
    baseline.life !== "dead" &&
    !baseline.spec.study_id &&
    !baseline.ecology &&
    !baseline.assessment;
  const pause = useMutation({
    mutationFn: () =>
      post(`${projectPath(project!.id)}/runs/${run.id}/commands`, {
        kind: "pause",
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["run"] }),
  });
  const save = useMutation({
    mutationFn: async () => {
      const spec = await editor.current?.validate();
      if (!spec) return null;
      return api<Run>(
        `${projectPath(project!.id)}/runs/${run.id}/configuration`,
        {
          method: "PUT",
          body: JSON.stringify({
            name,
            spec,
            expected_revision: baseline.revision,
            expected_metadata_revision: baseline.metadata_revision,
          }),
        },
      );
    },
    onSuccess: (result) => {
      if (result) {
        client.invalidateQueries({ queryKey: ["run"] });
        client.invalidateQueries({ queryKey: ["runs"] });
        onClose();
      }
    },
  });
  function reload() {
    setBaseline(run);
    setName(run.name);
    editor.current?.reset(run.spec);
    setDirty(false);
    save.reset();
  }
  useEffect(() => {
    // A pause can finish just after the dialog opens. Refresh an untouched
    // draft automatically; never replace an actual edit with polling data.
    if (
      !dirty &&
      !save.isPending &&
      (run.revision !== baseline.revision ||
        run.status !== baseline.status ||
        run.metadata_revision !== baseline.metadata_revision)
    ) {
      setBaseline(run);
      setName(run.name);
      editor.current?.reset(run.spec);
    }
  }, [
    run,
    baseline.revision,
    baseline.status,
    baseline.metadata_revision,
    dirty,
    save.isPending,
  ]);
  return (
    <Modal
      open
      onOpenChange={(v) => !v && onClose()}
      title={t("意识参数配置")}
      wide
      description={t(
        "配置、状态和修改历史一起保存。关闭窗口会放弃未保存的修改。",
      )}
    >
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          if (canEdit) save.mutate();
        }}
      >
        <Field label={t("意识名称")}>
          <input
            value={name}
            readOnly={!canEdit}
            maxLength={120}
            onChange={(e) => {
              setName(e.target.value);
              setDirty(true);
            }}
          />
        </Field>
        {!canEdit && (
          <div className="notice">
            {project?.role === "viewer"
              ? t("当前项目权限为只读，可以查看配置，不能修改或控制运行。")
              : baseline.assessment
                ? t(
                    "该意识属于独立评估，环境、输入和参数已冻结。请在独立评估页面控制，或先分叉。",
                  )
                : baseline.ecology
                  ? t(
                      "该个体属于生态训练，协议已冻结。请在所属生态训练中管理种群，或创建独立的继承个体。",
                    )
                  : baseline.spec.study_id
                    ? t(
                        "该意识属于冻结实验，协议只读。请分叉为独立意识后调整。",
                      )
                    : ["running", "queued"].includes(baseline.status)
                      ? t(
                          "运行中可查看配置。先暂停，等待检查点保存后即可编辑。",
                        )
                      : t(
                          "此运行已结束或不能直接编辑。可从检查点分叉为独立意识。",
                        )}
            {["running", "queued"].includes(run.status) &&
              project?.role !== "viewer" &&
              !run.spec.study_id &&
              !run.ecology &&
              !run.assessment && (
                <Button
                  type="button"
                  variant="small"
                  onClick={() => pause.mutate()}
                  disabled={pause.isPending || !can(user, "runs.pause")}
                >
                  <Pause size={13} />
                  {t("暂停运行")}
                </Button>
              )}
          </div>
        )}
        {(run.revision !== baseline.revision ||
          run.metadata_revision !== baseline.metadata_revision) && (
          <div className="notice">
            {t("当前数据已更新到 r")}
            {run.revision}。
            {dirty
              ? t("重新载入会替换未保存修改。")
              : t("载入最新状态后可继续操作。")}
            <button type="button" className="text-link" onClick={reload}>
              {t("重新载入配置")}
            </button>
          </div>
        )}
        {catalogue.isPending ? (
          <Loading />
        ) : (
          catalogue.data && (
            <ConfigurationEditor
              ref={editor}
              initial={baseline.spec}
              initialGroup={initialGroup}
              catalogue={catalogue.data}
              project={project!.id}
              runId={run.id}
              readOnly={!canEdit || save.isPending}
              frozen={
                !!baseline.spec.study_id ||
                !!baseline.ecology ||
                !!baseline.assessment
              }
              onDirty={() => setDirty(true)}
            />
          )
        )}
        <ErrorBox error={catalogue.error ?? pause.error ?? save.error} />
        <div className="form-actions config-sticky-actions">
          <span>
            {t("基于数据版本 r")}
            {baseline.revision}
            {dirty ? t(" · 尚未保存") : ""}
          </span>
          <Button type="button" onClick={onClose}>
            {t("关闭")}
          </Button>
          <Button
            variant="primary"
            disabled={!canEdit || save.isPending || !catalogue.data}
          >
            {save.isPending ? t("正在保存…") : t("保存配置")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function ProjectDefaults() {
  const { project, user } = useWorkspace(),
    catalogue = useCatalogue(),
    editor = useRef<ConfigurationHandle>(null);
  const [message, setMessage] = useState(""),
    client = useQueryClient();
  const defaults = useQuery({
    queryKey: ["configuration-defaults", project?.id],
    queryFn: () => api(`${projectPath(project!.id)}/configuration/defaults`),
    enabled: !!project,
    refetchOnWindowFocus: false,
  });
  const [revision, setRevision] = useState<number | null>(null);
  const initialRevision = useRef<number | null>(null);
  if (initialRevision.current === null && defaults.data)
    initialRevision.current = defaults.data.revision;
  const save = useMutation({
    mutationFn: async () => {
      const spec = await editor.current?.validate();
      if (!spec) return null;
      return api(`${projectPath(project!.id)}/configuration/defaults`, {
        method: "PUT",
        body: JSON.stringify({
          spec,
          expected_revision: revision ?? initialRevision.current,
        }),
      });
    },
    onSuccess: (result) => {
      if (result) {
        setRevision(result.revision);
        setMessage(t("项目默认配置已保存，仅用于以后新建的意识。"));
        client.invalidateQueries({
          queryKey: ["configuration-defaults", project?.id],
        });
      }
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) defaults.refetch();
    },
  });
  if (!project) return <p>{t("选择研究项目后，可管理该项目的默认参数。")}</p>;
  if (defaults.isPending || catalogue.isPending) return <Loading />;
  return (
    <section className="panel settings-panel">
      <div className="panel-heading">
        <div>
          <h2>{t("新建意识的默认配置")}</h2>
          <p>
            {t(
              "保存在当前项目的数据库中。修改这里不会改变已有意识；每次新建仍可单独调整。",
            )}
          </p>
        </div>
      </div>
      <ErrorBox error={defaults.error ?? catalogue.error ?? save.error} />
      {defaults.data &&
        defaults.data.revision !== (revision ?? initialRevision.current) && (
          <div className="notice">
            {t("项目默认配置已更新。重新载入会替换未保存修改。")}
            <button
              type="button"
              className="text-link"
              onClick={() => {
                editor.current?.reset(defaults.data.spec);
                setRevision(defaults.data.revision);
                save.reset();
              }}
            >
              {t("重新载入配置")}
            </button>
          </div>
        )}
      {catalogue.data && defaults.data && (
        <form
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <ConfigurationEditor
            ref={editor}
            initial={defaults.data.spec}
            catalogue={catalogue.data}
            project={project.id}
            readOnly={
              project.role !== "owner" ||
              !can(user, "projects.manage") ||
              save.isPending
            }
            onDirty={() => setMessage("")}
          />
          {message && (
            <p className="configuration-success" role="status">
              {message}
            </p>
          )}
          <div className="form-actions">
            <Button
              type="button"
              disabled={
                project.role !== "owner" || !can(user, "projects.manage")
              }
              onClick={() => {
                editor.current?.reset(catalogue.data!.defaults);
                setMessage(t("已载入内核默认值，点击保存后生效。"));
              }}
            >
              <RotateCcw size={14} />
              {t("恢复内核默认值")}
            </Button>
            <Button
              variant="primary"
              disabled={
                project.role !== "owner" ||
                !can(user, "projects.manage") ||
                save.isPending
              }
            >
              {t("保存项目默认配置")}
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}
