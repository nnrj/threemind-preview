import {
  forwardRef,
  lazy,
  Suspense,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus, Trash2 } from "lucide-react";
import { api, post } from "./api";
import { t, messageKeys } from "./i18n";
import { Button, CodeEditor, ErrorBox, Field, Loading } from "./ui";
const WorldScene = lazy(() => import("./WorldScene"));

export type WorldEditorHandle = { validate: () => Promise<any | null> };
export const worldLabels: Record<string, string> = messageKeys({
  label: "名称",
  id: "部件编号",
  wiring_namespace: "感官接线命名空间",
  physics: "物理与时间",
  bodies: "躯体层级",
  geometries: "几何体",
  joints: "关节",
  motors: "执行器",
  sensors: "感官端口",
  forces: "外力",
  position: "局部位置（m）",
  quaternion: "姿态四元数（w、x、y、z）",
  parent_id: "父级躯体",
  body_id: "所属躯体",
  free: "自由躯体（六自由度）",
  shape: "形状",
  size: "尺寸（半长度或半径，m）",
  density: "密度（kg/m³）",
  friction: "滑动、扭转与滚动摩擦",
  rgba: "物理颜色（R、G、B、透明度）",
  collision: "参与碰撞",
  kind: "类型",
  axis: "关节单位轴",
  limits: "关节下限与上限",
  damping: "关节阻尼",
  initial: "初始关节位置",
  initial_jitter: "初始位置随机化半宽",
  port: "稳定端口编号",
  joint_id: "关联关节",
  gear: "传动比例",
  control_limit: "控制量绝对上限",
  projection_gain: "外部激活投影增益",
  scale: "感官归一化尺度",
  geometry_id: "感知接触的几何体",
  maximum_distance: "最远感知距离（m）",
  width: "感官像素宽度",
  height: "感官像素高度",
  fovy: "垂直视场角（度）",
  force: "世界坐标力（N）",
  torque: "世界坐标力矩（N·m）",
  step_us: "物理步长（μs）",
  sample_us: "感官采样间隔（μs）",
  gravity: "重力加速度（m/s²）",
  integrator: "物理积分器",
  iterations: "约束求解迭代上限",
  joint_position: "关节位置感官",
  joint_velocity: "关节速度感官",
  touch: "接触力感官",
  rangefinder: "测距感官",
  camera_rgb: "离屏 RGB 眼睛",
  accelerometer: "三轴加速度计",
  gyroscope: "三轴陀螺仪",
  enabled: "启用感官",
  sphere: "球体",
  box: "长方体",
  capsule: "胶囊体",
  cylinder: "圆柱体",
  plane: "无限平面",
  slide: "平移关节",
  hinge: "转动关节",
});
const titles: Record<string, string> = messageKeys({
  bodies: "添加躯体",
  geometries: "添加几何体",
  joints: "添加关节",
  motors: "添加执行器",
  sensors: "添加感官",
  forces: "添加外力",
});
const groups = [
  "bodies",
  "geometries",
  "joints",
  "motors",
  "sensors",
  "forces",
];
const types: Record<string, string> = {
  bodies: "Body",
  geometries: "Geometry",
  joints: "Joint",
  motors: "Motor",
  forces: "Force",
  joint_position: "JointSensor",
  joint_velocity: "JointSensor",
  touch: "TouchSensor",
  rangefinder: "RangeSensor",
  camera_rgb: "CameraSensor",
  accelerometer: "InertialSensor",
  gyroscope: "InertialSensor",
};
const basic = new Set([
  "label",
  "shape",
  "body_id",
  "parent_id",
  "kind",
  "joint_id",
  "geometry_id",
  "position",
  "size",
  "step_us",
  "sample_us",
  "gravity",
]);

export const WorldEditor = forwardRef<
  WorldEditorHandle,
  { project: string; initial?: any; readOnly?: boolean; onDirty?: () => void }
>(function WorldEditor({ project, initial, readOnly = false, onDirty }, ref) {
  const root = `/projects/${project}/worlds`;
  const fileInput = useRef<HTMLInputElement>(null);
  const catalogue = useQuery({
    queryKey: ["world-catalogue", project],
    queryFn: () => api<any>(root + "/catalogue"),
    staleTime: Infinity,
  });
  const [value, setValue] = useState<any>(initial ?? null),
    [mode, setMode] = useState<"form" | "json">("form"),
    [raw, setRaw] = useState("");
  const [selected, setSelected] = useState<[string, number]>(["physics", 0]),
    [sensorKind, setSensorKind] = useState("joint_position");
  const [error, setError] = useState<unknown>(null),
    [checked, setChecked] = useState<any>(null),
    [busy, setBusy] = useState(false),
    [dirtyPreview, setDirtyPreview] = useState(false);
  const [mobilePane, setMobilePane] = useState("config");
  useEffect(() => {
    if (!value && catalogue.data)
      setValue(structuredClone(catalogue.data.defaults));
  }, [catalogue.data, value]);
  useEffect(() => {
    if (!catalogue.data) return;
    let live = true;
    post<any>(root + "/validate", {
      protocol: initial ?? catalogue.data.defaults,
    })
      .then((result) => {
        if (live) setChecked(result);
      })
      .catch((e) => {
        if (live) setError(e);
      });
    return () => {
      live = false;
    };
  }, [root, catalogue.data]);
  function change(next: any) {
    setValue(next);
    setError(null);
    setDirtyPreview(true);
    onDirty?.();
  }
  async function current() {
    if (mode === "form") return value;
    const { parseJson } = await import("./JsonEditor");
    return parseJson(raw);
  }
  async function validate() {
    if (busy) return null;
    setBusy(true);
    setError(null);
    try {
      const result = await post<any>(root + "/validate", {
        protocol: await current(),
      });
      setChecked(result);
      setDirtyPreview(false);
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
      setRaw(JSON.stringify(value, null, 2));
      setMode("json");
    } else {
      const next = await validate();
      if (next) {
        setValue(next);
        setMode("form");
      }
    }
  }
  async function format() {
    try {
      setRaw(JSON.stringify(await current(), null, 2));
      setError(null);
    } catch (e) {
      setError(e);
    }
  }
  async function importFile(file?: File) {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    try {
      if (file.size > 4 * 1024 * 1024)
        throw new Error(t("世界协议文件不得超过 4 MiB。"));
      const { parseJson } = await import("./JsonEditor");
      const result = await post<any>(root + "/validate", {
        protocol: parseJson(await file.text()),
      });
      change(result.protocol);
      setRaw(JSON.stringify(result.protocol, null, 2));
      setSelected(["physics", 0]);
      setChecked(result);
      setDirtyPreview(false);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }
  if (catalogue.error) return <ErrorBox error={catalogue.error} />;
  if (!value || !catalogue.data) return <Loading />;
  const catalog = catalogue.data,
    [section, index] = selected;
  const obj = section === "physics" ? value.physics : value[section]?.[index];
  const type =
    section === "physics"
      ? "Physics"
      : types[section === "sensors" ? obj?.kind : section];
  const schema = catalog.schema.$defs[type]?.properties ?? {};
  function update(key: string, next: any) {
    const v = structuredClone(value),
      target = section === "physics" ? v.physics : v[section][index];
    target[key] = next;
    if (section === "geometries" && key === "shape")
      target.size = Array.from(
        {
          length:
            next === "sphere" ? 1 : next === "box" || next === "plane" ? 3 : 2,
        },
        () => 0.15,
      );
    if (section === "sensors" && key === "kind")
      v.sensors[index] = {
        ...structuredClone(catalog.components[next]),
        id: target.id,
        label: target.label,
        port: target.port,
      };
    change(v);
  }
  function add(group: string) {
    const v = structuredClone(value),
      item = structuredClone(
        catalog.components[group === "sensors" ? sensorKind : group],
      );
    let n = 1;
    while (v[group].some((a: any) => a.id === `${item.id}_${n}`)) n++;
    item.id = `${item.id}_${n}`;
    item.label = t(worldLabels[group === "sensors" ? sensorKind : group]);
    if ("port" in item) {
      let port = 0;
      while (v[group].some((a: any) => a.port === port)) port++;
      item.port = port;
    }
    if ("body_id" in item)
      item.body_id =
        group === "geometries" ? null : (v.bodies[0]?.id ?? "body");
    if ("joint_id" in item) item.joint_id = v.joints[0]?.id ?? "joint";
    if ("geometry_id" in item)
      item.geometry_id = v.geometries[0]?.id ?? "geometry";
    v[group].push(item);
    setSelected([group, v[group].length - 1]);
    change(v);
  }
  function property(key: string, rule: any) {
    if (key === "kind" && section === "sensors")
      rule = {
        ...rule,
        enum: Object.keys(catalog.components).filter(
          (k) => !groups.includes(k),
        ),
      };
    const label = t(worldLabels[key] ?? key),
      fieldValue = obj?.[key];
    const choices =
      key === "body_id" || key === "parent_id"
        ? value.bodies
        : key === "joint_id"
          ? value.joints
          : key === "geometry_id"
            ? value.geometries
            : null;
    const nullable = rule.anyOf?.some((r: any) => r.type === "null");
    return (
      <Field
        key={key}
        label={label}
        hint={
          key === "port"
            ? t("端口编号决定匿名通道；修改名称不会更换通道。")
            : key === "quaternion"
              ? t("须为单位四元数。测距沿局部 +Z，眼睛朝局部 −Z。")
              : undefined
        }
      >
        {choices ? (
          <select
            aria-label={label}
            value={fieldValue ?? ""}
            disabled={readOnly}
            onChange={(e) => update(key, e.target.value || null)}
          >
            <option value="" disabled={!nullable}>
              {t("世界根级／未选择")}
            </option>
            {fieldValue && !choices.some((a: any) => a.id === fieldValue) && (
              <option value={fieldValue}>{fieldValue}</option>
            )}
            {choices
              .filter((a: any) => key !== "parent_id" || a.id !== obj.id)
              .map((a: any) => (
                <option key={a.id} value={a.id}>
                  {a.label || a.id} · {a.id}
                </option>
              ))}
          </select>
        ) : rule.enum ? (
          <select
            aria-label={label}
            value={fieldValue}
            disabled={readOnly}
            onChange={(e) => update(key, e.target.value)}
          >
            {rule.enum.map((s: string) => (
              <option key={s} value={s}>
                {t(worldLabels[s] ?? s)}
              </option>
            ))}
          </select>
        ) : rule.const ? (
          <input value={t(worldLabels[rule.const] ?? rule.const)} readOnly />
        ) : rule.type === "boolean" ? (
          <input
            aria-label={label}
            type="checkbox"
            checked={!!fieldValue}
            disabled={readOnly}
            onChange={(e) => update(key, e.target.checked)}
          />
        ) : Array.isArray(fieldValue) ? (
          <span className="world-vector">
            {fieldValue.map((n: number, i: number) => (
              <input
                key={i}
                aria-label={`${label} ${i + 1}`}
                type="number"
                step="any"
                value={n ?? ""}
                readOnly={readOnly}
                onChange={(e) =>
                  update(
                    key,
                    fieldValue.map((v: number, j: number) =>
                      j === i
                        ? e.target.value === ""
                          ? null
                          : Number(e.target.value)
                        : v,
                    ),
                  )
                }
              />
            ))}
          </span>
        ) : (
          <input
            aria-label={label}
            type={
              rule.type === "integer" || rule.type === "number"
                ? "number"
                : "text"
            }
            step={rule.type === "integer" ? 1 : "any"}
            value={fieldValue ?? ""}
            readOnly={readOnly}
            min={rule.minimum}
            max={rule.maximum}
            onChange={(e) =>
              update(
                key,
                rule.type === "integer" || rule.type === "number"
                  ? e.target.value === ""
                    ? null
                    : Number(e.target.value)
                  : e.target.value,
              )
            }
          />
        )}
      </Field>
    );
  }
  return (
    <section className="world-editor" aria-label={t("世界与躯体配置")}>
      <div className="world-mode">
        <span>{t("世界、躯体与感官独立于意识内核。")}</span>
        {!readOnly && value.schema_id === "threemind.world/1" && (
          <button
            type="button"
            className="text-link"
            onClick={() => {
              setValue({ ...value, schema_id: "threemind.world/2" });
              setDirtyPreview(true);
              setChecked(null);
              onDirty?.();
            }}
          >
            {t("升级此草稿为世界协议 2（启用惯性感官）")}
          </button>
        )}
        {!readOnly && (
          <select
            aria-label={t("物理场景模板")}
            value=""
            disabled={busy}
            onChange={(e) => {
              const template = catalogue.data?.templates?.[e.target.value];
              if (template) {
                setValue(structuredClone(template));
                setRaw(JSON.stringify(template, null, 2));
                setSelected(["physics", 0]);
                setDirtyPreview(true);
                setChecked(null);
                onDirty?.();
              }
            }}
          >
            <option value="">{t("载入物理场景模板")}</option>
            {Object.entries(catalogue.data?.templates ?? {}).map(
              ([id, doc]: [string, any]) => (
                <option key={id} value={id}>
                  {t(doc.label)}
                </option>
              ),
            )}
          </select>
        )}
        {!readOnly && (
          <>
            <input
              ref={fileInput}
              type="file"
              accept=".json,application/json"
              hidden
              aria-label={t("导入世界协议文件")}
              onChange={(e) => importFile(e.target.files?.[0])}
            />
            <button
              type="button"
              className="text-link"
              disabled={busy}
              onClick={() => fileInput.current?.click()}
            >
              {t("导入世界 JSON")}
            </button>
          </>
        )}
        <button
          type="button"
          className="text-link"
          disabled={busy}
          onClick={toggle}
        >
          {mode === "form" ? t("切换到 JSON 编辑") : t("切换到图形配置")}
        </button>
      </div>
      {(mode === "json" || section === "motors") && (
        <p className="footnote">
          {t(
            "执行器当前使用固定哈希投影，属于工程接入基线；它不代表通过训练形成了器官分工。",
          )}{" "}
          <Link
            to="/docs?doc=docs%2Fzh%2Fembodied-functional-differentiation.md"
            target="_blank"
          >
            {t("查看具身差异与功能分化预测")}
          </Link>
        </p>
      )}
      <div
        className="world-mobile-tabs"
        role="tablist"
        aria-label={t("配置与观察")}
      >
        <button
          type="button"
          role="tab"
          aria-selected={mobilePane === "config"}
          onClick={() => setMobilePane("config")}
        >
          {t("配置")}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mobilePane === "preview"}
          onClick={() => setMobilePane("preview")}
        >
          {t("观察")}
        </button>
      </div>
      <div className={`world-authoring-layout world-pane-${mobilePane}`}>
        <div className="world-config-pane">
          {mode === "json" ? (
            <>
              <div className="world-json-actions">
                <Button type="button" onClick={format}>
                  {t("格式化")}
                </Button>
                <Button type="button" disabled={busy} onClick={validate}>
                  {t("校验与预览")}
                </Button>
              </div>
              <CodeEditor
                label={t("世界协议 JSON")}
                value={raw}
                readOnly={readOnly}
                rows={24}
                onChange={(v) => {
                  setRaw(v);
                  setDirtyPreview(true);
                  onDirty?.();
                }}
              />
            </>
          ) : (
            <>
              <div className="world-title-fields">
                <Field label={t("世界名称")}>
                  <input
                    value={value.label}
                    readOnly={readOnly}
                    onChange={(e) =>
                      change({ ...value, label: e.target.value })
                    }
                  />
                </Field>
                <details>
                  <summary>{t("接线身份（高级）")}</summary>
                  <Field label={t("感官接线命名空间")}>
                    <input
                      value={value.wiring_namespace}
                      readOnly={readOnly}
                      onChange={(e) =>
                        change({ ...value, wiring_namespace: e.target.value })
                      }
                    />
                  </Field>
                </details>
              </div>
              <div className="world-workbench">
                <nav className="world-tree" aria-label={t("世界部件层级")}>
                  <button
                    type="button"
                    className={section === "physics" ? "active" : ""}
                    onClick={() => setSelected(["physics", 0])}
                  >
                    {t("物理与时间")}
                  </button>
                  {groups.map((group) => (
                    <div key={group} className="world-tree-group">
                      <div>
                        <strong>
                          {t(worldLabels[group])}{" "}
                          <small>{value[group].length}</small>
                        </strong>
                        {!readOnly && (
                          <button
                            type="button"
                            aria-label={t(titles[group])}
                            onClick={() => add(group)}
                          >
                            <Plus size={15} />
                          </button>
                        )}
                      </div>
                      {group === "sensors" && !readOnly && (
                        <select
                          aria-label={t("新增感官类型")}
                          value={sensorKind}
                          onChange={(e) => setSensorKind(e.target.value)}
                        >
                          {Object.keys(catalog.components)
                            .filter((k) => !groups.includes(k))
                            .map((k) => (
                              <option value={k} key={k}>
                                {t(worldLabels[k])}
                              </option>
                            ))}
                        </select>
                      )}
                      {value[group].map((v: any, i: number) => (
                        <button
                          key={i}
                          type="button"
                          className={
                            section === group && index === i ? "active" : ""
                          }
                          onClick={() => setSelected([group, i])}
                        >
                          <span>{v.label || v.id}</span>
                          <small>
                            {v.parent_id ? `${v.parent_id} › ` : ""}
                            {v.id}
                          </small>
                        </button>
                      ))}
                    </div>
                  ))}
                </nav>
                <div className="world-inspector" key={`${section}:${index}`}>
                  <div className="panel-heading">
                    <h3>
                      {t(worldLabels[section])}
                      {obj?.label ? ` · ${obj.label}` : ""}
                    </h3>
                    {obj && section !== "physics" && !readOnly && (
                      <Button
                        type="button"
                        variant="small"
                        onClick={() => {
                          const v = structuredClone(value);
                          v[section].splice(index, 1);
                          setSelected(["physics", 0]);
                          change(v);
                        }}
                      >
                        <Trash2 size={14} />
                        {t("删除部件")}
                      </Button>
                    )}
                  </div>
                  {obj ? (
                    <>
                      <div className="world-properties">
                        {Object.entries(schema)
                          .filter(([key]) => basic.has(key))
                          .map(([key, rule]) => property(key, rule))}
                      </div>
                      <details>
                        <summary>{t("高级物理与接线参数")}</summary>
                        <div className="world-properties">
                          {Object.entries(schema)
                            .filter(([key]) => !basic.has(key))
                            .map(([key, rule]) => property(key, rule))}
                        </div>
                      </details>
                      {section === "sensors" && obj.kind === "camera_rgb" && (
                        <p className="notice">
                          {t(
                            "像素分辨率是科学刺激配置，关闭页面或切换显示档位都不会降低它。执行 worker 需要支持离屏渲染。",
                          )}
                        </p>
                      )}
                    </>
                  ) : (
                    <p>{t("请选择部件。")}</p>
                  )}
                </div>
              </div>
            </>
          )}
          <ErrorBox error={error} />
          {mode === "form" && (
            <Button type="button" onClick={validate} disabled={busy}>
              {t("校验与预览")}
            </Button>
          )}
        </div>
        <div className="world-preview-pane">
          <Button type="button" onClick={validate} disabled={busy}>
            {t("更新观察")}
          </Button>
          {checked && (
            <>
              <p className={dirtyPreview ? "notice" : "footnote"}>
                {dirtyPreview
                  ? t("配置已修改；下面仍是上次校验的初始状态，请更新预览。")
                  : t(
                      "协议及物理模型编译已通过。预览为初始姿态，尚未运行意识或生成刺激。",
                    )}
              </p>
              <Suspense fallback={<Loading />}>
                <WorldScene
                  protocol={checked.protocol}
                  observation={checked.layout}
                  selected={obj?.id}
                  selectedGroup={section}
                  onSelect={(id) => {
                    const n = value.geometries.findIndex(
                      (g: any) => g.id === id,
                    );
                    if (n >= 0) setSelected(["geometries", n]);
                  }}
                />
              </Suspense>
            </>
          )}
        </div>
      </div>
    </section>
  );
});
