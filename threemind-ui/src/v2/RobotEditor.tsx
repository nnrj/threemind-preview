import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post } from "./api";
import { Button, CodeEditor, ErrorBox, Field, Loading, Modal } from "./ui";
import { WorldEditor, type WorldEditorHandle } from "./WorldEditor";
import { t } from "./i18n";
import { parseJson } from "./JsonEditor";
import PlaygroundEditor from "./PlaygroundEditor";

export const controlNames: Record<string, string> = {
  torque: "原始力矩",
  position: "位置伺服",
  velocity: "速度伺服",
  skill: "外部技能",
};

export default function RobotEditor({
  project,
  value,
  onChange,
  readOnly = false,
}: {
  project: string;
  value: any;
  onChange: (value: any) => void;
  readOnly?: boolean;
}) {
  const catalogue = useQuery({
    queryKey: ["robot-catalogue", project],
    queryFn: () => api<any>(`/projects/${project}/robots/catalogue`),
    staleTime: 60000,
  });
  const [jsonMode, setJsonMode] = useState(false),
    [text, setText] = useState("");
  const [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false),
    [bodyOpen, setBodyOpen] = useState(false);
  const world = useRef<WorldEditorHandle>(null);
  useEffect(() => {
    if (!value && catalogue.data && !readOnly)
      onChange(structuredClone(catalogue.data.templates["custom-arm-reach"]));
  }, [catalogue.data, value, readOnly]);
  if (!value)
    return catalogue.isPending ? (
      <Loading />
    ) : (
      <ErrorBox error={catalogue.error} />
    );
  const patch = (key: string, next: any) => onChange({ ...value, [key]: next });
  const numeric = (
    label: string,
    current: number,
    change: (n: number) => void,
    min = 0,
    step = "any",
  ) => (
    <Field key={label} label={t(label)}>
      <input
        type="number"
        min={min}
        step={step}
        value={current}
        disabled={readOnly}
        onChange={(e) => change(e.target.valueAsNumber)}
      />
    </Field>
  );
  async function choose(id: string) {
    setError(null);
    setBusy(true);
    try {
      const next =
        catalogue.data.templates[id] ??
        (await api(`/projects/${project}/robots/assets/${id}/template`));
      onChange(structuredClone(next));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function applyJSON(switchMode = false) {
    setError(null);
    setBusy(true);
    try {
      const parsed = parseJson(text);
      const result = await post(`/projects/${project}/robots/validate`, {
        protocol: parsed,
      });
      onChange(result.protocol);
      setText(JSON.stringify(result.protocol, null, 2));
      if (switchMode) setJsonMode(false);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="robot-editor">
      <div className="panel-heading">
        <strong>{t("躯体、控制与任务")}</strong>
        <Button
          type="button"
          variant="ghost"
          disabled={busy}
          onClick={() => {
            if (jsonMode) {
              void applyJSON(true);
            } else {
              setText(JSON.stringify(value, null, 2));
              setJsonMode(true);
            }
          }}
        >
          {t(jsonMode ? "切换到图形配置" : "切换到 JSON 编辑")}
        </Button>
      </div>
      <ErrorBox error={error ?? catalogue.error} />
      {jsonMode ? (
        <>
          <CodeEditor
            value={text}
            onChange={(raw) => {
              setText(raw);
              try {
                onChange(parseJson(raw));
                setError(null);
              } catch (e) {
                onChange({ ...value, __invalid_json_draft: raw });
                setError(e);
              }
            }}
            label={t("机器人协议 JSON")}
            readOnly={readOnly}
          />
          {!readOnly && (
            <div className="form-actions">
              <Button
                type="button"
                disabled={busy}
                onClick={() => void applyJSON()}
              >
                {t("校验并应用 JSON")}
              </Button>
            </div>
          )}
          <p className="footnote">
            {t("图形与 JSON 共用配置；保存与创建时会再次校验。")}
          </p>
        </>
      ) : (
        <>
          {!readOnly && (
            <Field label={t("选择机器人模板")}>
              <select
                disabled={busy}
                value=""
                onChange={(e) => void choose(e.target.value)}
              >
                <option value="">{t("更换机器人模板")}</option>
                {Object.entries(catalogue.data?.templates ?? {}).map(
                  ([id, item]: any) => (
                    <option value={id} key={id}>
                      {t(item.name)}
                    </option>
                  ),
                )}
                {Object.entries(catalogue.data?.assets ?? {}).map(
                  ([id, item]: any) => (
                    <option key={id} value={id} disabled={!item.available_here}>
                      {id} {item.available_here ? "" : t("（资产未安装）")}
                    </option>
                  ),
                )}
              </select>
            </Field>
          )}
          {value.schema_id === "threemind.robot-task/2" ? (
            <PlaygroundEditor
              value={value}
              onChange={onChange}
              readOnly={readOnly}
            />
          ) : (
            <>
              <div className="form-grid">
                <Field label={t("任务名称")}>
                  <input
                    value={value.name}
                    disabled={readOnly}
                    onChange={(e) => patch("name", e.target.value)}
                  />
                </Field>
                <Field label={t("控制模式")}>
                  <select
                    value={value.control.mode}
                    disabled={readOnly}
                    onChange={(e) =>
                      patch("control", {
                        ...value.control,
                        mode: e.target.value,
                        actuator_variant:
                          e.target.value === "torque" &&
                          value.asset_id &&
                          !catalogue.data?.assets?.[
                            value.asset_id
                          ]?.modes.includes("torque")
                            ? "ideal-torque"
                            : "profile",
                      })
                    }
                  >
                    {Object.entries(controlNames).map(([id, label]) => (
                      <option value={id} key={id}>
                        {t(label)}
                        {id === "torque" &&
                        value.asset_id &&
                        !catalogue.data?.assets?.[
                          value.asset_id
                        ]?.modes.includes("torque")
                          ? t("（仿真理想执行器）")
                          : ""}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label={t("任务目标")}>
                  <select
                    value={value.objective}
                    disabled={readOnly}
                    onChange={(e) => patch("objective", e.target.value)}
                  >
                    <option value="observe">{t("仅观察，不判断成功")}</option>
                    <option value="reach">{t("端点接近目标")}</option>
                    <option value="push" disabled={!value.object_body}>
                      {t("推动物体到目标")}
                    </option>
                  </select>
                </Field>
                {numeric(
                  "成功距离（m）",
                  value.success_distance,
                  (n) => patch("success_distance", n),
                  0.001,
                )}
                {value.target.map((n: number, i: number) =>
                  numeric(
                    `目标位置 ${["X", "Y", "Z"][i]}（m）`,
                    n,
                    (v) =>
                      patch(
                        "target",
                        value.target.map((x: number, j: number) =>
                          i === j ? v : x,
                        ),
                      ),
                    -100000,
                  ),
                )}
                <Field
                  label={t("目标可观测信标")}
                  hint={t(
                    "模拟安装在端点的理想光学方位／距离感官；不输入奖励或答案。",
                  )}
                >
                  {" "}
                  <input
                    type="checkbox"
                    checked={value.beacon_enabled}
                    disabled={readOnly}
                    onChange={(e) => patch("beacon_enabled", e.target.checked)}
                  />
                </Field>
              </div>
              {value.control.mode !== "torque" && (
                <p className="notice">
                  {t(
                    "此模式使用外部控制器。成绩必须区分意识的响应与控制器贡献。",
                  )}
                </p>
              )}
              {value.control.actuator_variant === "ideal-torque" && (
                <p className="notice" role="status">
                  {t(
                    "已为仿真替换理想力矩执行器，保留机械结构和力矩限值。此模式不代表真实型号具有力矩接口；迁移到实体须另行验证。",
                  )}
                </p>
              )}
              <details>
                <summary>{t("高级控制、采样与感官参数")}</summary>
                <div className="form-grid">
                  {numeric("位置增益 Kp", value.control.kp, (n) =>
                    patch("control", { ...value.control, kp: n }),
                  )}
                  {numeric("速度增益 Kd", value.control.kd, (n) =>
                    patch("control", { ...value.control, kd: n }),
                  )}
                  {numeric(
                    "连续关节位置半范围（rad）",
                    value.control.continuous_position_span,
                    (n) =>
                      patch("control", {
                        ...value.control,
                        continuous_position_span: n,
                      }),
                    0.001,
                  )}
                  {numeric(
                    "最大目标速度（rad/s 或 m/s）",
                    value.control.maximum_velocity,
                    (n) =>
                      patch("control", {
                        ...value.control,
                        maximum_velocity: n,
                      }),
                    0.001,
                  )}
                  {numeric(
                    "物理步长（μs）",
                    value.world.physics.step_us,
                    (n) =>
                      patch("world", {
                        ...value.world,
                        physics: { ...value.world.physics, step_us: n },
                      }),
                    10,
                    "1",
                  )}
                  {numeric(
                    "感官与动作周期（μs）",
                    value.world.physics.sample_us,
                    (n) =>
                      patch("world", {
                        ...value.world,
                        physics: { ...value.world.physics, sample_us: n },
                      }),
                    10,
                    "1",
                  )}
                  {numeric(
                    "信标距离尺度（m）",
                    value.beacon_scale,
                    (n) => patch("beacon_scale", n),
                    0.001,
                  )}
                  {numeric(
                    "信标感受范围（m）",
                    value.beacon_range,
                    (n) => patch("beacon_range", n),
                    0.001,
                  )}
                  {value.target_jitter.map((n: number, i: number) =>
                    numeric(
                      `目标位置变化范围 ${["X", "Y", "Z"][i]}（m）`,
                      n,
                      (v) =>
                        patch(
                          "target_jitter",
                          value.target_jitter.map((x: number, j: number) =>
                            i === j ? v : x,
                          ),
                        ),
                    ),
                  )}
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>{t("感官")}</th>
                        <th>{t("尺度")}</th>
                        <th>{t("开启")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {value.world.sensors.map((s: any, i: number) => (
                        <tr key={s.id}>
                          <td>{s.label || s.id}</td>
                          <td>
                            {s.scale !== undefined && (
                              <input
                                type="number"
                                min="0.001"
                                step="any"
                                aria-label={`${s.id} scale`}
                                value={s.scale}
                                disabled={readOnly}
                                onChange={(e) =>
                                  patch("world", {
                                    ...value.world,
                                    sensors: value.world.sensors.map(
                                      (v: any, j: number) =>
                                        i === j
                                          ? {
                                              ...v,
                                              scale: e.target.valueAsNumber,
                                            }
                                          : v,
                                    ),
                                  })
                                }
                              />
                            )}
                          </td>
                          <td>
                            {s.enabled !== undefined ? (
                              <input
                                type="checkbox"
                                aria-label={`${s.id} enabled`}
                                checked={s.enabled}
                                disabled={readOnly}
                                onChange={(e) =>
                                  patch("world", {
                                    ...value.world,
                                    sensors: value.world.sensors.map(
                                      (v: any, j: number) =>
                                        i === j
                                          ? { ...v, enabled: e.target.checked }
                                          : v,
                                    ),
                                  })
                                }
                              />
                            ) : (
                              "—"
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {!value.asset_id && (
                  <Button type="button" onClick={() => setBodyOpen(true)}>
                    {t("编辑躯体、关节和感官安装")}
                  </Button>
                )}
                {value.asset_id && (
                  <p className="footnote">
                    {t(
                      "真实型号的机械结构固定到资产版本；拓扑改造须另存资产。",
                    )}
                  </p>
                )}
              </details>
            </>
          )}
        </>
      )}
      <Modal
        open={bodyOpen}
        onOpenChange={setBodyOpen}
        title={t("躯体与感官安装")}
        wide
      >
        {bodyOpen && (
          <WorldEditor
            ref={world}
            project={project}
            initial={value.world}
            readOnly={readOnly}
          />
        )}
        <div className="form-actions">
          <Button type="button" onClick={() => setBodyOpen(false)}>
            {t("取消")}
          </Button>
          {!readOnly && (
            <Button
              type="button"
              onClick={async () => {
                const next = await world.current?.validate();
                if (next) {
                  patch("world", next);
                  setBodyOpen(false);
                }
              }}
            >
              {t("应用躯体配置")}
            </Button>
          )}
        </div>
      </Modal>
    </div>
  );
}
